import math
import os
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests

ZONA_HORARIA = ZoneInfo("America/Bogota")
BASE_ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
HEADERS = {"User-Agent": "Mozilla/5.0"}
ARCHIVO_BITACORA = "bitacora_yz_quant.csv"


def normalizar_nombre(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    norm = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    return norm.lower().replace(".", "").strip()


def parse_num(valor, default: float = 0.0) -> float:
    """Convierte valores de ESPN a float de forma segura (maneja '--', ':', vacíos, etc.)."""
    if valor is None:
        return default
    s = str(valor).strip()
    if s in ("", "--", "-", "DNP", "N/A", "nan", "None"):
        return default
    if ":" in s:
        s = s.split(":")[0].strip()
    try:
        return float(s)
    except ValueError:
        return default


def parse_split_part(valor, idx: int, default: float = 0.0) -> float:
    """Extrae aciertos (idx=0) o intentos (idx=-1) en cadenas 'aciertos-intentos' o '--'."""
    if valor is None:
        return default
    s = str(valor).strip()
    if s in ("", "--", "-", "N/A", "nan", "None"):
        return default
    partes = s.split("-")
    if len(partes) < 2:
        return parse_num(s, default)
    return parse_num(partes[idx], default)


def prueba_exacta_fisher_binomial(aciertos: int, total: int, prob_h0: float) -> float:
    """
    Calcula el Valor p exacto unilateral (cola superior) bajo la hipótesis nula H0:
    el modelo no tiene ventaja real sobre la probabilidad implícita de la casa (1 / Cuota).
    """
    if total <= 0:
        return 1.0
    prob_h0 = min(max(prob_h0, 1e-6), 1.0 - 1e-6)
    return sum(
        math.comb(total, i) * (prob_h0 ** i) * ((1.0 - prob_h0) ** (total - i))
        for i in range(aciertos, total + 1)
    )


def obtener_boxscores_fecha(fecha_yyyymmdd: str) -> tuple[dict, dict]:
    """Descarga los resultados reales de jugadores y márgenes de partido desde ESPN."""
    resp = requests.get(f"{BASE_ESPN}/scoreboard", params={"dates": fecha_yyyymmdd}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    stats_jugadores = {}
    margen_equipo = {}

    for ev in data.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed", False):
            continue

        competitors = comp.get("competitors", [])
        if len(competitors) == 2:
            c0, c1 = competitors[0], competitors[1]
            s0, s1 = int(c0.get("score", 0)), int(c1.get("score", 0))
            margen_equipo[c0["team"]["abbreviation"]] = s0 - s1
            margen_equipo[c1["team"]["abbreviation"]] = s1 - s0

        ev_id = ev.get("id")
        box = requests.get(f"{BASE_ESPN}/summary", params={"event": ev_id}, headers=HEADERS, timeout=15).json()
        for grp in box.get("boxscore", {}).get("players", []):
            eq = grp.get("team", {}).get("abbreviation", "")
            blocks = grp.get("statistics", [])
            if not blocks:
                continue
            labels = [l.upper() for l in blocks[0].get("labels", [])]
            for ath in blocks[0].get("athletes", []):
                if ath.get("didNotPlay", False):
                    continue
                nombre = ath.get("athlete", {}).get("displayName", "")
                vals = ath.get("stats", [])
                if not nombre or len(vals) != len(labels):
                    continue
                m = dict(zip(labels, vals))
                mins = parse_num(m.get("MIN", "0"))
                pts = parse_num(m.get("PTS", 0))
                reb = parse_num(m.get("REB", 0))
                ast = parse_num(m.get("AST", 0))
                tpt = parse_split_part(m.get("3PT", "0-0"), 0)
                tpa = parse_split_part(m.get("3PT", "0-0"), -1)
                fga = parse_split_part(m.get("FG", "0-0"), -1)
                fta = parse_split_part(m.get("FT", "0-0"), -1)

                stats_jugadores[normalizar_nombre(nombre)] = {
                    "Equipo": eq,
                    "MIN_Obs": mins,
                    "PTS_Obs": pts,
                    "REB_Obs": reb,
                    "AST_Obs": ast,
                    "3PT_Obs": tpt,
                    "PRA_Obs": pts + reb + ast,
                    "FGA_Obs": fga,
                    "3PA_Obs": tpa,
                    "FTA_Obs": fta,
                }

    return stats_jugadores, margen_equipo


def auditar_picks(archivo_picks_dia: str, fecha_objetivo: str):
    """
    Cruza los picks guardados de una jornada contra los boxscores reales de ESPN,
    actualiza bitacora_yz_quant.csv y ejecuta el diagnóstico estadístico estilo Fisher.
    """
    df_picks = pd.read_csv(archivo_picks_dia)
    df_picks.columns = [c.strip() for c in df_picks.columns]

    fecha_espn = fecha_objetivo.replace("-", "")
    stats_obs, margenes = obtener_boxscores_fecha(fecha_espn)

    if not stats_obs:
        print(f"[INFO] Sin boxscores finalizados en ESPN para {fecha_objetivo}.")
        return

    registros = []
    for _, row in df_picks.iterrows():
        key = normalizar_nombre(str(row["Jugador"]))
        if key not in stats_obs:
            print(f"[AVISO] No se encontró boxscore para: {row['Jugador']} ({fecha_objetivo})")
            continue

        obs = stats_obs[key]
        mkt = str(row["Mercado"]).upper().strip()
        linea = float(row["Linea"])
        proy = float(row["Proy_Modelo"]) if pd.notna(row.get("Proy_Modelo")) else np.nan
        std = max(float(row["Varianza_std"]), 2.5) if pd.notna(row.get("Varianza_std")) else 2.5
        prob_est = float(row["Prob_Estimada"]) if pd.notna(row.get("Prob_Estimada")) else np.nan

        if mkt == "PTS":
            val_obs = obs["PTS_Obs"]
        elif mkt == "PRA":
            val_obs = obs["PRA_Obs"]
        elif mkt == "3PT":
            val_obs = obs["3PT_Obs"]
        elif mkt == "REB":
            val_obs = obs["REB_Obs"]
        else:
            val_obs = obs["AST_Obs"]

        acierto = 1 if val_obs > linea else 0
        margen = margenes.get(obs["Equipo"], 0)
        blowout = 1 if abs(margen) >= 15 else 0
        residuo_z = round((val_obs - proy) / std, 2) if pd.notna(proy) else np.nan
        brier = round((prob_est - acierto) ** 2, 4) if pd.notna(prob_est) else np.nan

        registros.append({
            "Fecha": fecha_objetivo,
            "Boleto": row.get("Boleto", "N/D"),
            "Jugador": row["Jugador"],
            "Equipo": obs["Equipo"],
            "Mercado": mkt,
            "Linea": linea,
            "Cuota": row.get("Cuota", np.nan),
            "Stake": row.get("Stake", np.nan),
            "Proy_Modelo": proy,
            "Val_Obs": val_obs,
            "Acierto": acierto,
            "Prob_Estimada": prob_est,
            "Brier_Score": brier,
            "Min_L10": row.get("Minutos_L10", np.nan),
            "Min_Obs": obs["MIN_Obs"],
            "Diff_Min": round(obs["MIN_Obs"] - float(row["Minutos_L10"]), 1) if pd.notna(row.get("Minutos_L10")) else np.nan,
            "Margen_Partido": margen,
            "Blowout_15plus": blowout,
            "FGA_Obs": obs["FGA_Obs"],
            "3PA_Obs": obs["3PA_Obs"],
            "FTA_Obs": obs["FTA_Obs"],
            "Estado_Carga": row.get("Estado_Carga", "NORMAL"),
            "Estabilidad": row.get("Estabilidad", "ESTANDAR"),
            "Residuo_Z": residuo_z,
        })

    if not registros:
        print(f"[AVISO] No se pudo cruzar ningún jugador de {archivo_picks_dia}.")
        return

    df_nuevo = pd.DataFrame(registros)
    if os.path.exists(ARCHIVO_BITACORA):
        df_hist = pd.read_csv(ARCHIVO_BITACORA)
        df_total = pd.concat([df_hist, df_nuevo], ignore_index=True)
    else:
        df_total = df_nuevo

    df_total.drop_duplicates(subset=["Fecha", "Jugador", "Mercado", "Linea"], keep="last", inplace=True)
    df_total.to_csv(ARCHIVO_BITACORA, index=False)
    print(f"[OK] {len(df_nuevo)} selecciones de {fecha_objetivo} auditadas en {ARCHIVO_BITACORA} (Total acumulado: {len(df_total)}).")

    # --- DIAGNÓSTICO ESTADÍSTICO ESTILO FISHER ---
    n_total = len(df_total)
    if n_total >= 5:
        aciertos = int(df_total["Acierto"].sum())
        tasa_real = aciertos / n_total

        cuotas_validas = pd.to_numeric(df_total["Cuota"], errors="coerce").dropna()
        cuotas_validas = cuotas_validas[cuotas_validas > 1.0]
        prob_casa = float((1.0 / cuotas_validas).mean()) if not cuotas_validas.empty else (1.0 / 1.27)

        p_val = prueba_exacta_fisher_binomial(aciertos, n_total, prob_casa)
        veredicto_h0 = (
            "✅ H0 REFUTADA (p < 0.05): Ventaja estadísticamente significativa sobre la casa."
            if p_val < 0.05
            else f"⏳ Muestra en construcción (necesitas p < 0.05; actual p = {p_val:.4f})."
        )

        print("\n--- RESUMEN DIAGNÓSTICO ACUMULADO (YZ QUANT NBA) ---")
        print(f"Aciertos Acumulados:   {aciertos}/{n_total} ({tasa_real*100:.1f}%)")
        print(f"Prob. Implícita Casa:  {prob_casa*100:.1f}% (Cuota media @{1/prob_casa:.2f})")
        print(f"Prob. Media Modelo:    {df_total['Prob_Estimada'].mean()*100:.1f}% | Brier Score: {df_total['Brier_Score'].mean():.4f}")
        print(f"Test Binomial Fisher:  Valor p = {p_val:.4f} -> {veredicto_h0}")

        print("\n[Grupo Control vs. Intervención] USAGE AUTO (+8%) vs. NORMAL:")
        print(df_total.groupby("Estado_Carga")[["Acierto", "Prob_Estimada", "Residuo_Z"]].mean().round(3))

        print("\n[Análisis por Varianza] Estabilidad ALTA vs. ESTANDAR:")
        print(df_total.groupby("Estabilidad")[["Acierto", "Prob_Estimada", "Residuo_Z"]].mean().round(3))

        print("\n[Rendimiento por Mercado]:")
        print(df_total.groupby("Mercado")[["Acierto", "Prob_Estimada", "Residuo_Z"]].mean().round(3))

        print("\n[Impacto de Blowouts (|Margen| >= 15 pts)]:")
        print(df_total.groupby("Blowout_15plus")[["Acierto", "Diff_Min", "Residuo_Z"]].mean().round(3))


def obtener_fechas_auditadas() -> set[str]:
    if not os.path.exists(ARCHIVO_BITACORA):
        return set()
    df_hist = pd.read_csv(ARCHIVO_BITACORA)
    if "Fecha" not in df_hist.columns:
        return set()
    return set(df_hist["Fecha"].astype(str).str.strip())


if __name__ == "__main__":
    hoy = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
    fechas_auditadas = obtener_fechas_auditadas()
    pendientes = []

    for nombre in sorted(os.listdir(".")):
        m = re.match(r"^picks_(\d{4}-\d{2}-\d{2})\.csv$", nombre)
        if not m:
            continue
        fecha_archivo = m.group(1)
        if fecha_archivo < hoy and fecha_archivo not in fechas_auditadas:
            pendientes.append((fecha_archivo, nombre))

    if pendientes:
        for fecha_archivo, nombre in pendientes:
            print(f"[INFO] Auditando jornada pendiente: {nombre}...")
            auditar_picks(nombre, fecha_archivo)
    else:
        print("[INFO] Sin jornadas pendientes por auditar.")
