import json
import os
import time
import unicodedata
from datetime import datetime
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

MIN_JUEGOS_L10_PARA_BOOST = 2
MIN_MINUTOS_L10_PARA_BOOST = 18.0
BOOST_PTS_PRA = 1.08
BOOST_3PT = 1.05
BOOST_REB = 1.08
BOOST_AST = 1.08
VENTANA_L10 = 10


def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    texto_norm = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    return texto_norm.lower().replace(".", "").replace("-", " ").strip()


def obtener_json(url: str, params: dict = None, reintentos: int = 3) -> dict:
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


def obtener_reporte_lesiones_roster(equipos_hoy: dict) -> dict:
    """
    Lee lesiones directamente desde /teams/{team_id}/roster, donde ESPN sí
    incluye el array 'injuries' por jugador con su estado real (Out, Questionable, Doubtful, Day-To-Day).
    """
    reporte = {}
    for abbr, team_id in equipos_hoy.items():
        reporte[abbr] = {"OUT": [], "GTD": []}
        data = obtener_json(f"{BASE_ESPN}/teams/{team_id}/roster")
        for ath in data.get("athletes", []):
            nombre = ath.get("displayName", "")
            injuries = ath.get("injuries", [])
            if not nombre or not injuries:
                continue

            status_raw = str(injuries[0].get("status", "")).lower()
            if any(k in status_raw for k in ["out", "susp", "inj"]):
                reporte[abbr]["OUT"].append(nombre)
            elif any(k in status_raw for k in ["questionable", "doubtful", "day-to-day", "gtd"]):
                reporte[abbr]["GTD"].append(nombre)

    return reporte


def obtener_ultimos_eventos_equipo(team_id: str, limite: int = VENTANA_L10) -> list:
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
    if event_id in cache_boxscores:
        return cache_boxscores[event_id]

    data = obtener_json(f"{BASE_ESPN}/summary", params={"event": event_id})
    boxscore = data.get("boxscore", {})
    players_groups = boxscore.get("players", [])

    registros_jugadores = []
    puntos_por_equipo = {}
    rebotes_por_equipo = {}
    asistencias_por_equipo = {}

    for group in players_groups:
        team_abbr = group.get("team", {}).get("abbreviation", "")
        stats_blocks = group.get("statistics", [])
        if not stats_blocks:
            continue

        labels = [lbl.upper() for lbl in stats_blocks[0].get("labels", [])]
        athletes = stats_blocks[0].get("athletes", [])
        total_pts_equipo = 0
        total_reb_equipo = 0
        total_ast_equipo = 0

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
                if "-" in tpt_raw:
                    partes_3 = tpt_raw.split("-")
                    tpt_made = float(partes_3[0])
                    tpt_att = float(partes_3[1])
                else:
                    tpt_made = float(tpt_raw)
                    tpt_att = tpt_made
            except ValueError:
                continue

            total_pts_equipo += pts
            total_reb_equipo += reb
            total_ast_equipo += ast
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
                "3PA": tpt_att,
                "PRA": pts + reb + ast,
            })

        puntos_por_equipo[team_abbr] = total_pts_equipo
        rebotes_por_equipo[team_abbr] = total_reb_equipo
        asistencias_por_equipo[team_abbr] = total_ast_equipo

    equipos_en_juego = list(puntos_por_equipo.keys())
    puntos_permitidos = {}
    rebotes_permitidos = {}
    asistencias_permitidas = {}
    if len(equipos_en_juego) == 2:
        eq1, eq2 = equipos_en_juego
        puntos_permitidos[eq1] = puntos_por_equipo[eq2]
        puntos_permitidos[eq2] = puntos_por_equipo[eq1]
        rebotes_permitidos[eq1] = rebotes_por_equipo[eq2]
        rebotes_permitidos[eq2] = rebotes_por_equipo[eq1]
        asistencias_permitidas[eq1] = asistencias_por_equipo[eq2]
        asistencias_permitidas[eq2] = asistencias_por_equipo[eq1]

    resultado = {
        "jugadores": registros_jugadores,
        "puntos_permitidos": puntos_permitidos,
        "rebotes_permitidos": rebotes_permitidos,
        "asistencias_permitidas": asistencias_permitidas,
    }
    cache_boxscores[event_id] = resultado
    return resultado


def evaluar_bajas_rotacion_l10(
    lista_out: list,
    df_logs_equipo: pd.DataFrame,
    min_juegos: int = MIN_JUEGOS_L10_PARA_BOOST,
    min_minutos: float = MIN_MINUTOS_L10_PARA_BOOST,
) -> dict:
    """
    Evalúa en L10 qué bajas OUT son reales y detecta si además cayó:
    - Un reboteador principal (>= 6.5 REB L10) -> activa boost de REB a compañeros reboteadores.
    - Un generador principal (>= 5.0 AST L10) -> activa boost de AST a compañeros pasadores.
    """
    if not lista_out or df_logs_equipo.empty:
        return {
            "aplica_boost_general": False,
            "bajas_reales": [],
            "boost_reb_rol": False,
            "boost_ast_rol": False,
        }

    bajas_reales = []
    boost_reb_rol = False
    boost_ast_rol = False

    for nombre_out in lista_out:
        norm_out = normalizar_texto(nombre_out)
        hist = df_logs_equipo[df_logs_equipo["Jugador_Norm"] == norm_out]
        juegos_recientes = hist["event_id"].nunique()
        minutos_prom = hist["MIN"].mean() if juegos_recientes > 0 else 0.0

        if juegos_recientes >= min_juegos and minutos_prom >= min_minutos:
            reb_out = hist["REB"].mean()
            ast_out = hist["AST"].mean()
            bajas_reales.append(f"{nombre_out} ({minutos_prom:.1f} min L10)")
            if reb_out >= 6.5:
                boost_reb_rol = True
            if ast_out >= 5.0:
                boost_ast_rol = True

    return {
        "aplica_boost_general": len(bajas_reales) > 0,
        "bajas_reales": bajas_reales,
        "boost_reb_rol": boost_reb_rol,
        "boost_ast_rol": boost_ast_rol,
    }


def clasificar_estabilidad(std_pts: float) -> str:
    """Clasificación original de 2 niveles: ⭐ ALTA (<= 6.5) y ESTÁNDAR (> 6.5)."""
    if std_pts <= 6.5:
        return "⭐ ALTA"
    return "ESTÁNDAR"


def ejecutar_pipeline():
    print(f"=== INICIANDO ACTUALIZACIÓN YZ QUANT NBA ({HOY}) ===")
    partidos = obtener_cartelera_hoy(FECHA_ESPN)
    if not partidos:
        print(f"[AVISO] No se encontraron partidos NBA programados para {HOY}.")
        return

    print(f"[INFO] Partidos detectados hoy: {len(partidos)}")
    cache_boxscores = {}

    equipos_hoy = {}
    for p in partidos:
        equipos_hoy[p["home_abbr"]] = p["home_id"]
        equipos_hoy[p["away_abbr"]] = p["away_id"]

    lesiones = obtener_reporte_lesiones_roster(equipos_hoy)

    logs_por_equipo = {}
    def_rating_relativo = {}
    reb_rating_relativo = {}
    ast_rating_relativo = {}
    todos_pts_permitidos = []
    todos_reb_permitidos = []
    todos_ast_permitidos = []

    for abbr, team_id in equipos_hoy.items():
        ev_ids = obtener_ultimos_eventos_equipo(team_id, limite=VENTANA_L10)
        filas_eq = []
        pts_perm_eq = []
        reb_perm_eq = []
        ast_perm_eq = []

        for eid in ev_ids:
            box = extraer_boxscore_evento(eid, cache_boxscores)
            for reg in box["jugadores"]:
                if reg["Equipo"] == abbr:
                    filas_eq.append(reg)
            if abbr in box["puntos_permitidos"] and box["puntos_permitidos"][abbr] > 0:
                pts_perm_eq.append(box["puntos_permitidos"][abbr])
                todos_pts_permitidos.append(box["puntos_permitidos"][abbr])
            if abbr in box["rebotes_permitidos"] and box["rebotes_permitidos"][abbr] > 0:
                reb_perm_eq.append(box["rebotes_permitidos"][abbr])
                todos_reb_permitidos.append(box["rebotes_permitidos"][abbr])
            if abbr in box["asistencias_permitidas"] and box["asistencias_permitidas"][abbr] > 0:
                ast_perm_eq.append(box["asistencias_permitidas"][abbr])
                todos_ast_permitidos.append(box["asistencias_permitidas"][abbr])

        logs_por_equipo[abbr] = pd.DataFrame(filas_eq)
        def_rating_relativo[abbr] = np.mean(pts_perm_eq) if pts_perm_eq else 113.5
        reb_rating_relativo[abbr] = np.mean(reb_perm_eq) if reb_perm_eq else 43.5
        ast_rating_relativo[abbr] = np.mean(ast_perm_eq) if ast_perm_eq else 26.0

    promedio_liga_pts = np.mean(todos_pts_permitidos) if todos_pts_permitidos else 113.5
    promedio_liga_reb = np.mean(todos_reb_permitidos) if todos_reb_permitidos else 43.5
    promedio_liga_ast = np.mean(todos_ast_permitidos) if todos_ast_permitidos else 26.0

    factor_def_equipo = {
        abbr: round(float(def_rating_relativo[abbr] / promedio_liga_pts), 2)
        for abbr in equipos_hoy
    }
    factor_reb_equipo = {
        abbr: round(float(reb_rating_relativo[abbr] / promedio_liga_reb), 2)
        for abbr in equipos_hoy
    }
    factor_ast_equipo = {
        abbr: round(float(ast_rating_relativo[abbr] / promedio_liga_ast), 2)
        for abbr in equipos_hoy
    }

    registros_json = []

    for p in partidos:
        enfrentamientos = [
            (p["away_abbr"], f"@ {p['home_abbr']}", p["home_abbr"]),
            (p["home_abbr"], f"vs {p['away_abbr']}", p["away_abbr"]),
        ]

        for eq_abbr, rival_label, rival_abbr in enfrentamientos:
            df_eq = logs_por_equipo.get(eq_abbr, pd.DataFrame())
            if df_eq.empty:
                continue

            info_les = lesiones.get(eq_abbr, {"OUT": [], "GTD": []})
            out_norms = {normalizar_texto(n) for n in info_les["OUT"]}
            gtd_norms = {normalizar_texto(n) for n in info_les["GTD"]}

            eval_bajas = evaluar_bajas_rotacion_l10(info_les["OUT"], df_eq)
            aplica_boost = eval_bajas["aplica_boost_general"]
            bajas_confirmadas = eval_bajas["bajas_reales"]
            boost_reb_rol = eval_bajas["boost_reb_rol"]
            boost_ast_rol = eval_bajas["boost_ast_rol"]

            if info_les["OUT"] and not aplica_boost:
                print(
                    f"[FILTRO L10] {eq_abbr}: OUT en ESPN {info_les['OUT']} sin minutos recientes en L10 -> Boost +8% DESACTIVADO."
                )
            elif aplica_boost:
                print(
                    f"[BOOST ACTIVO] {eq_abbr}: Baja real confirmada {bajas_confirmadas} -> +8% aplicado."
                )

            # Multiplicadores intactos para PTS / 3PT / PRA
            f_def = factor_def_equipo.get(rival_abbr, 1.00)
            multiplicador_def = 1.0 + (f_def - 1.0) * 0.50

            # Multiplicadores calibrados por ritmo/oportunidad rival para REB y AST (amortiguados 50%)
            f_reb_rival = factor_reb_equipo.get(rival_abbr, 1.00)
            f_ast_rival = factor_ast_equipo.get(rival_abbr, 1.00)
            multiplicador_reb_rival = 1.0 + (f_reb_rival - 1.0) * 0.50
            multiplicador_ast_rival = 1.0 + (f_ast_rival - 1.0) * 0.50

            for (jug_norm, jug_nombre), grp in df_eq.groupby(["Jugador_Norm", "Jugador"]):
                if jug_norm in out_norms:
                    continue

                if len(grp) < 4 or grp["MIN"].mean() < 18.0:
                    continue

                estado_espn = "GTD" if jug_norm in gtd_norms else "ACTIVO"

                min_l10 = round(float(grp["MIN"].mean()), 1)
                es_rotacion_alta = grp["MIN"].mean() >= 24.0
                tiene_boost = aplica_boost and es_rotacion_alta

                # 1. Cálculos originales intactos (PTS, 3PT, PRA, Varianza, Estabilidad)
                mult_pts_pra = (BOOST_PTS_PRA if tiene_boost else 1.0) * multiplicador_def
                mult_3pt = (BOOST_3PT if tiene_boost else 1.0) * multiplicador_def

                pts_base = round(float(grp["PTS"].mean() * mult_pts_pra), 2)
                tpt_base = round(float(grp["3PT"].mean() * mult_3pt), 2)
                pra_base = round(float(grp["PRA"].mean() * mult_pts_pra), 2)
                std_pts = round(max(float(grp["PTS"].std(ddof=1)), 2.5), 2)
                tpa_prom = round(float(grp["3PA"].mean()), 1)

                # 2. Nuevas proyecciones calibradas de REB y AST (ritmo rival + baja de rol específico)
                reb_raw = float(grp["REB"].mean())
                ast_raw = float(grp["AST"].mean())

                tiene_boost_reb = es_rotacion_alta and boost_reb_rol and (reb_raw >= 5.0)
                tiene_boost_ast = es_rotacion_alta and boost_ast_rol and (ast_raw >= 3.5)

                reb_base = round(reb_raw * (BOOST_REB if tiene_boost_reb else 1.0) * multiplicador_reb_rival, 2)
                ast_base = round(ast_raw * (BOOST_AST if tiene_boost_ast else 1.0) * multiplicador_ast_rival, 2)
                std_reb = round(max(float(grp["REB"].std(ddof=1)), 1.0), 2)
                std_ast = round(max(float(grp["AST"].std(ddof=1)), 1.0), 2)

                usage_auto = "🚀 USAGE AUTO (+8%)" if tiene_boost else "🟢 NORMAL"
                estabilidad = clasificar_estabilidad(std_pts)

                registros_json.append({
                    "Jugador": jug_nombre,
                    "Equipo": eq_abbr,
                    "Rival": rival_label,
                    "Estado ESPN": estado_espn,
                    "Usage Auto": usage_auto,
                    "Factor Defensivo": f_def,
                    "Factor Ritmo REB": f_reb_rival,
                    "Factor Ritmo AST": f_ast_rival,
                    "Minutos L10": min_l10,
                    "PTS Base": pts_base,
                    "3PT Base": tpt_base,
                    "PRA Base": pra_base,
                    "REB Base": reb_base,
                    "AST Base": ast_base,
                    "Varianza (std)": std_pts,
                    "Varianza REB (std)": std_reb,
                    "Varianza AST (std)": std_ast,
                    "Estabilidad": estabilidad,
                    "3PA (Intentos)": tpa_prom,
                    "Fecha_Actualizacion": HOY,
                })

    if not registros_json:
        print("[AVISO] No se generaron proyecciones válidas para hoy.")
        return

    registros_json.sort(key=lambda x: (x["PTS Base"], x["PRA Base"]), reverse=True)

    with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
        json.dump(registros_json, f, ensure_ascii=False, indent=2)

    print(f"[OK] datos_nba_hoy.json actualizado exitosamente para {HOY} ({len(registros_json)} jugadores).")


if __name__ == "__main__":
    ejecutar_pipeline()
