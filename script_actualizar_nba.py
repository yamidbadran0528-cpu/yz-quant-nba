import os
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

# ==============================================================================
# CONFIGURACIÓN GENERAL DEL SISTEMA YZ QUANT NBA
# ==============================================================================
ZONA_HORARIA = ZoneInfo("America/Bogota")
HOY = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
FECHA_ESPN = datetime.now(ZONA_HORARIA).strftime("%Y%m%d")

BASE_ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Parámetros del motor de lesiones y redistribución de uso
MIN_JUEGOS_L10_PARA_BOOST = 2      # Debe haber jugado al menos 2 de los últimos 10 partidos
MIN_MINUTOS_L10_PARA_BOOST = 18.0  # Debe promediar >= 18.0 MIN en L10 para disparar boost
BOOST_PTS_PRA = 1.08               # +8% en Puntos y PRA ante baja real de rotación
BOOST_3PT = 1.05                   # +5% en Triples ante baja real de rotación
VENTANA_L10 = 10                   # Últimos 10 partidos disputados por equipo


def normalizar_texto(texto: str) -> str:
    """Elimina tildes, puntos y espacios extra para cruzar nombres entre endpoints."""
    if not isinstance(texto, str):
        return ""
    texto_norm = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    return texto_norm.lower().replace(".", "").replace("-", " ").strip()


def obtener_json(url: str, params: dict = None, reintentos: int = 3) -> dict:
    """Consulta segura con reintentos ante límites temporales de red."""
    for intento in range(reintentos):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if intento == reintentos - 1:
                print(f"[ERROR] Fallo consultando {url}: {e}")
                return {}
            time.sleep(1.2 * (intento + 1))
    return {}


def obtener_cartelera_hoy(fecha_yyyymmdd: str) -> list:
    """Extrae los partidos programados para hoy desde ESPN Scoreboard."""
    data = obtener_json(f"{BASE_ESPN}/scoreboard", params={"dates": fecha_yyyymmdd})
    partidos = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        partidos.append({
            "event_id": event.get("id"),
            "partido": f"{away['team']['displayName']} vs {home['team']['displayName']}",
            "home_id": home["team"]["id"],
            "home_abbr": home["team"]["abbreviation"],
            "home_name": home["team"]["displayName"],
            "away_id": away["team"]["id"],
            "away_abbr": away["team"]["abbreviation"],
            "away_name": away["team"]["displayName"],
        })
    return partidos


def obtener_reporte_lesiones() -> dict:
    """
    Descarga el reporte médico oficial de ESPN y clasifica cada jugador por equipo:
      - 'OUT': Out / Suspension / Injured Reserve
      - 'GTD': Questionable / Doubtful / Day-To-Day
    """
    data = obtener_json(f"{BASE_ESPN}/injuries")
    reporte = {}

    for team_block in data.get("injuries", []):
        team_info = team_block.get("team", {})
        abbr = team_info.get("abbreviation", "")
        if not abbr:
            continue
        reporte.setdefault(abbr, {"OUT": [], "GTD": []})

        for item in team_block.get("injuries", []):
            athlete = item.get("athlete", {})
            nombre = athlete.get("displayName", "")
            status_raw = str(item.get("status", "")).lower()

            if not nombre:
                continue

            if any(k in status_raw for k in ["out", "susp", "inj"]):
                reporte[abbr]["OUT"].append(nombre)
            elif any(k in status_raw for k in ["questionable", "doubtful", "day-to-day", "gtd", "probable"]):
                if "probable" not in status_raw:
                    reporte[abbr]["GTD"].append(nombre)

    return reporte


def obtener_ultimos_eventos_equipo(team_id: str, limite: int = VENTANA_L10) -> list:
    """Obtiene los IDs de los últimos N partidos ya finalizados de un equipo."""
    data = obtener_json(f"{BASE_ESPN}/teams/{team_id}/schedule")
    eventos_finalizados = []

    for ev in data.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {}).get("completed", False)
        if status:
            fecha_ev = ev.get("date", "")
            eventos_finalizados.append((fecha_ev, ev.get("id")))

    eventos_finalizados.sort(key=lambda x: x[0])
    return [ev_id for _, ev_id in eventos_finalizados[-limite:]]


def extraer_boxscore_evento(event_id: str, cache_boxscores: dict) -> dict:
    """
    Descarga y parsea el boxscore de un partido finalizado (con caché en memoria).
    Retorna registros individuales por jugador y puntos permitidos por cada equipo.
    """
    if event_id in cache_boxscores:
        return cache_boxscores[event_id]

    data = obtener_json(f"{BASE_ESPN}/summary", params={"event": event_id})
    boxscore = data.get("boxscore", {})
    players_groups = boxscore.get("players", [])

    registros_jugadores = []
    puntos_por_equipo = {}

    for group in players_groups:
        team_abbr = group.get("team", {}).get("abbreviation", "")
        stats_blocks = group.get("statistics", [])
        if not stats_blocks:
            continue

        labels = [lbl.upper() for lbl in stats_blocks[0].get("labels", [])]
        athletes = stats_blocks[0].get("athletes", [])
        total_pts_equipo = 0

        for ath in athletes:
            if ath.get("didNotPlay", False):
                continue
            nombre = ath.get("athlete", {}).get("displayName", "")
            vals = ath.get("stats", [])
            if not nombre or not vals or len(vals) != len(labels):
                continue

            stat_map = dict(zip(labels, vals))
            try:
                min_raw = str(stat_map.get("MIN", "0"))
                minutos = float(min_raw.split(":")[0]) if ":" in min_raw else float(min_raw)
            except ValueError:
                minutos = 0.0

            if minutos <= 0:
                continue

            try:
                pts = float(stat_map.get("PTS", 0))
                reb = float(stat_map.get("REB", 0))
                ast = float(stat_map.get("AST", 0))
                tpt_raw = str(stat_map.get("3PT", "0-0"))
                tpt_made = float(tpt_raw.split("-")[0]) if "-" in tpt_raw else float(tpt_raw)
            except ValueError:
                continue

            total_pts_equipo += pts
            registros_jugadores.append({
                "event_id": event_id,
                "Equipo": team_abbr,
                "Jugador": nombre,
                "Jugador_Norm": normalizar_texto(nombre),
                "MIN": minutos,
                "PTS": pts,
                "REB": reb,
                "AST": ast,
                "3PT": tpt_made,
                "PRA": pts + reb + ast,
            })

        puntos_por_equipo[team_abbr] = total_pts_equipo

    # Calcular puntos permitidos por cada equipo en ese partido
    equipos_en_juego = list(puntos_por_equipo.keys())
    puntos_permitidos = {}
    if len(equipos_en_juego) == 2:
        eq1, eq2 = equipos_en_juego
        puntos_permitidos[eq1] = puntos_por_equipo[eq2]
        puntos_permitidos[eq2] = puntos_por_equipo[eq1]

    resultado = {
        "jugadores": registros_jugadores,
        "puntos_permitidos": puntos_permitidos,
    }
    cache_boxscores[event_id] = resultado
    return resultado


def tiene_baja_real_rotacion(
    equipo_abbr: str,
    lista_out: list,
    df_logs_equipo: pd.DataFrame,
    min_juegos: int = MIN_JUEGOS_L10_PARA_BOOST,
    min_minutos: float = MIN_MINUTOS_L10_PARA_BOOST,
) -> tuple[bool, list]:
    """
    FILTRO ANTI-FALSOS POSITIVOS (Ej. Tobias Harris en Spurs):
    Verifica si los jugadores reportados como OUT en ESPN realmente jugaron en la
    rotación reciente (L10) del equipo. Si un fichaje aún no debuta (0 juegos en L10)
    o es una baja de larga duración, NO dispara el +8% de usage sobre sus compañeros.
    """
    if not lista_out or df_logs_equipo.empty:
        return False, []

    bajas_reales = []
    for nombre_out in lista_out:
        norm_out = normalizar_texto(nombre_out)
        hist = df_logs_equipo[df_logs_equipo["Jugador_Norm"] == norm_out]
        juegos_recientes = hist["event_id"].nunique()
        minutos_prom = hist["MIN"].mean() if juegos_recientes > 0 else 0.0

        if juegos_recientes >= min_juegos and minutos_prom >= min_minutos:
            bajas_reales.append(f"{nombre_out} ({minutos_prom:.1f} min L10)")

    return (len(bajas_reales) > 0), bajas_reales


def clasificar_estabilidad(std_pts: float) -> str:
    if std_pts <= 5.2:
        return "⭐ ALTA"
    elif std_pts <= 7.2:
        return "⚖️ MEDIA"
    return "⚠️ VOLÁTIL"


def ejecutar_pipeline():
    print(f"=== INICIANDO ACTUALIZACIÓN YZ QUANT NBA ({HOY}) ===")
    partidos = obtener_cartelera_hoy(FECHA_ESPN)
    if not partidos:
        print(f"[AVISO] No se encontraron partidos NBA programados para {HOY}.")
        return

    print(f"[INFO] Partidos detectados hoy: {len(partidos)}")
    lesiones = obtener_reporte_lesiones()
    cache_boxscores = {}

    # Recolectar los últimos 10 partidos de todos los equipos que juegan hoy
    equipos_hoy = {}
    for p in partidos:
        equipos_hoy[p["home_abbr"]] = p["home_id"]
        equipos_hoy[p["away_abbr"]] = p["away_id"]

    logs_por_equipo = {}
    def_rating_relativo = {}
    todos_pts_permitidos = []

    for abbr, team_id in equipos_hoy.items():
        ev_ids = obtener_ultimos_eventos_equipo(team_id, limite=VENTANA_L10)
        filas_eq = []
        pts_perm_eq = []

        for eid in ev_ids:
            box = extraer_boxscore_evento(eid, cache_boxscores)
            for reg in box["jugadores"]:
                if reg["Equipo"] == abbr:
                    filas_eq.append(reg)
            if abbr in box["puntos_permitidos"] and box["puntos_permitidos"][abbr] > 0:
                pts_perm_eq.append(box["puntos_permitidos"][abbr])
                todos_pts_permitidos.append(box["puntos_permitidos"][abbr])

        logs_por_equipo[abbr] = pd.DataFrame(filas_eq)
        def_rating_relativo[abbr] = np.mean(pts_perm_eq) if pts_perm_eq else 113.5

    promedio_liga_pts = np.mean(todos_pts_permitidos) if todos_pts_permitidos else 113.5
    factor_def_equipo = {
        abbr: round(def_rating_relativo[abbr] / promedio_liga_pts, 3)
        for abbr in equipos_hoy
    }

    filas_salida = []

    for p in partidos:
        enfrentamientos = [
            (p["away_abbr"], p["home_abbr"], p["partido"]),
            (p["home_abbr"], p["away_abbr"], p["partido"]),
        ]

        for eq_abbr, rival_abbr, nombre_partido in enfrentamientos:
            df_eq = logs_por_equipo.get(eq_abbr, pd.DataFrame())
            if df_eq.empty:
                continue

            info_les = lesiones.get(eq_abbr, {"OUT": [], "GTD": []})
            out_norms = {normalizar_texto(n) for n in info_les["OUT"]}
            gtd_norms = {normalizar_texto(n) for n in info_les["GTD"]}

            # Verificar si existe una baja REAL de rotación en L10 antes de aplicar +8%
            aplica_boost, bajas_confirmadas = tiene_baja_real_rotacion(
                eq_abbr, info_les["OUT"], df_eq
            )
            if info_les["OUT"] and not aplica_boost:
                print(
                    f"[FILTRO L10] {eq_abbr}: OUT en ESPN {info_les['OUT']} sin minutos recientes en L10 -> Boost +8% DESACTIVADO."
                )
            elif aplica_boost:
                print(
                    f"[BOOST ACTIVO] {eq_abbr}: Baja real confirmada {bajas_confirmadas} -> +8% PTS/PRA aplicado."
                )

            f_def = factor_def_equipo.get(rival_abbr, 1.00)
            # Amortiguamos el factor defensivo al 50% para evitar sobreajuste extremo
            multiplicador_def = 1.0 + (f_def - 1.0) * 0.50

            for (jug_norm, jug_nombre), grp in df_eq.groupby(["Jugador_Norm", "Jugador"]):
                # 1. Excluir jugadores confirmados OUT
                if jug_norm in out_norms:
                    continue

                # 2. Filtrar jugadores de rotación real (>= 4 juegos en L10 y >= 18 min)
                if len(grp) < 4 or grp["MIN"].mean() < 18.0:
                    continue

                estado = "🟡 GTD" if jug_norm in gtd_norms else "🟢 ACTIVO"

                # Solo los titulares/rotación principal (>= 24 min) reciben el boost de usage
                es_rotacion_alta = grp["MIN"].mean() >= 24.0
                mult_pts_pra = (BOOST_PTS_PRA if (aplica_boost and es_rotacion_alta) else 1.0) * multiplicador_def
                mult_3pt = (BOOST_3PT if (aplica_boost and es_rotacion_alta) else 1.0) * multiplicador_def

                pts_proy = round(grp["PTS"].mean() * mult_pts_pra, 1)
                reb_proy = round(grp["REB"].mean(), 1)
                ast_proy = round(grp["AST"].mean(), 1)
                tpt_proy = round(grp["3PT"].mean() * mult_3pt, 1)
                pra_proy = round(grp["PRA"].mean() * mult_pts_pra, 1)
                std_pts = round(max(float(grp["PTS"].std(ddof=1)), 2.5), 1)
                std_pra = round(max(float(grp["PRA"].std(ddof=1)), 3.5), 1)

                contexto = "🚀 USAGE +8%" if (aplica_boost and es_rotacion_alta) else "🟢 NORMAL"
                estabilidad = clasificar_estabilidad(std_pts)

                filas_salida.append({
                    "Jugador": jug_nombre,
                    "Equipo": eq_abbr,
                    "Rival": rival_abbr,
                    "Partido": nombre_partido,
                    "Estado": estado,
                    "Contexto": contexto,
                    "Estabilidad": estabilidad,
                    "MIN Prom": round(grp["MIN"].mean(), 1),
                    "Defensa Rival": f"{f_def:.2f}x",
                    "PTS Proyectados": pts_proy,
                    "REB Proyectados": reb_proy,
                    "AST Proyectados": ast_proy,
                    "3PT Proyectados": tpt_proy,
                    "PRA Promedios": pra_proy,
                    "Varianza (std)": std_pts,
                    "Varianza PRA (std)": std_pra,
                })

    df_final = pd.DataFrame(filas_salida)
    if df_final.empty:
        print("[AVISO] No se generaron proyecciones válidas para hoy.")
        return

    df_final = df_final.sort_values(by=["PTS Proyectados", "PRA Promedios"], ascending=False)
    nombre_csv = f"YZ_Quant_NBA_{HOY}.csv"
    df_final.to_csv(nombre_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] Archivo generado exitosamente: {nombre_csv} ({len(df_final)} jugadores activos/GTD)")


if __name__ == "__main__":
    ejecutar_pipeline()
