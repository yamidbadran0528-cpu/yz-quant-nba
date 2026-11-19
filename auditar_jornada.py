import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests

ZONA_HORARIA = ZoneInfo("America/Bogota")
BASE_ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
HEADERS = {"User-Agent": "Mozilla/5.0"}
ARCHIVO_BITACORA = "bitacora_yz_quant.csv"


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
                min_raw = str(m.get("MIN", "0"))
                mins = float(min_raw.split(":")[0]) if ":" in min_raw else float(min_raw)
                pts = float(m.get("PTS", 0))
                reb = float(m.get("REB", 0))
                ast = float(m.get("AST", 0))
                tpt = float(str(m.get("3PT", "0-0")).split("-")[0])
                tpa = float(str(m.get("3PT", "0-0")).split("-")[-1])
                fga = float(str(m.get("FG", "0-0")).split("-")[-1])
                fta = float(str(m.get("FT", "0-0")).split("-")[-1])

                stats_jugadores[nombre.lower().strip()] = {
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
    Cruza los picks guardados de una jornada contra los boxscores reales de ESPN
    y actualiza bitacora_yz_quant.csv con los 4 conjuntos de datos históricos.
    """
    df_picks = pd.read_csv(archivo_picks_dia)
    fecha_espn = fecha_objetivo.replace("-", "")
    stats_obs, margenes = obtener_boxscores_fecha(fecha_espn)

    registros = []
    for _, row in df_picks.iterrows():
        key = str(row["Jugador"]).lower().strip()
        if key not in stats_obs:
            continue
        obs = stats_obs[key]
        mkt = str(row["Mercado"]).upper()
        linea = float(row["Linea"])
        proy = float(row["Proy_Modelo"])
        std = max(float(row.get("Varianza_std", 2.5)), 2.5)
        prob_est = float(row["Prob_Estimada"])

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
        residuo_z = round((val_obs - proy) / std, 2)
        brier = round((prob_est - acierto) ** 2, 4)

        registros.append({
            "Fecha": fecha_objetivo,
            "Jugador": row["Jugador"],
            "Equipo": obs["Equipo"],
            "Mercado": mkt,
            "Linea": linea,
            "Cuota": row.get("Cuota", np.nan),
            "Proy_Modelo": proy,
            "Val_Obs": val_obs,
            "Acierto": acierto,
            "Prob_Estimada": prob_est,
            "Brier_Score": brier,
            "Min_L10": row.get("Minutos_L10", np.nan),
            "Min_Obs": obs["MIN_Obs"],
            "Diff_Min": round(obs["MIN_Obs"] - float(row.get("Minutos_L10", obs["MIN_Obs"])), 1),
            "Margen_Partido": margen,
            "Blowout_15plus": blowout,
            "FGA_Obs": obs["FGA_Obs"],
            "3PA_Obs": obs["3PA_Obs"],
            "FTA_Obs": obs["FTA_Obs"],
            "Estado_Carga": row.get("Estado_Carga", "NORMAL"),
            "Estabilidad": row.get("Estabilidad", "ESTANDAR"),
            "Residuo_Z": residuo_z,
        })

    df_nuevo = pd.DataFrame(registros)
    if os.path.exists(ARCHIVO_BITACORA):
        df_hist = pd.read_csv(ARCHIVO_BITACORA)
        df_total = pd.concat([df_hist, df_nuevo], ignore_index=True)
    else:
        df_total = df_nuevo

    df_total.to_csv(ARCHIVO_BITACORA, index=False)
    print(f"[OK] {len(df_nuevo)} selecciones auditadas y guardadas en {ARCHIVO_BITACORA} (Total acumulado: {len(df_total)}).")

    if len(df_total) >= 10:
        print("\n--- RESUMEN DIAGNÓSTICO ACUMULADO ---")
        print(f"Brier Score Global: {df_total['Brier_Score'].mean():.4f}")
        print(f"Tasa Acierto Real:  {df_total['Acierto'].mean()*100:.1f}% vs Prob Media Estimada: {df_total['Prob_Estimada'].mean()*100:.1f}%")
        print("\nPor Estado de Carga (USAGE AUTO vs NORMAL):")
        print(df_total.groupby("Estado_Carga")[["Acierto", "Prob_Estimada", "Residuo_Z"]].mean().round(3))
        print("\nImpacto de Blowouts (|Margen| >= 15 pts):")
        print(df_total.groupby("Blowout_15plus")[["Acierto", "Diff_Min", "Residuo_Z"]].mean().round(3))


if __name__ == "__main__":
    ayer = (datetime.now(ZONA_HORARIA) - timedelta(days=1)).strftime("%Y-%m-%d")
    if os.path.exists(f"picks_{ayer}.csv"):
        auditar_picks(f"picks_{ayer}.csv", ayer)
    else:
        print(f"[INFO] Crea 'picks_{ayer}.csv' para ejecutar la auditoría automática.")
