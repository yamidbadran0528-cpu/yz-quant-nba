import glob
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA - YZ QUANT NBA (INTERFAZ DE JUGADORES)
# ==============================================================================
st.set_page_config(
    page_title="YZ Quant NBA | Proyecciones de Jugadores",
    page_icon="🏀",
    layout="wide",
)

ZONA_COL = ZoneInfo("America/Bogota")
HOY_STR = datetime.now(ZONA_COL).strftime("%Y-%m-%d")


# ==============================================================================
# CARGA AUTOMÁTICA DEL CSV DEL REPOSITORIO (CUALQUIER NOMBRE DE ARCHIVO)
# ==============================================================================
def cargar_csv_repositorio() -> tuple[pd.DataFrame | None, str]:
    """Busca automáticamente el CSV generado por el workflow en la carpeta del repo."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    carpetas = list(dict.fromkeys([base_dir, "."]))

    archivos_csv = []
    for carpeta in carpetas:
        for ruta in glob.glob(os.path.join(carpeta, "*.csv")):
            nombre = os.path.basename(ruta).lower()
            if "bitacora" in nombre:
                continue
            archivos_csv.append(ruta)

    if not archivos_csv:
        return None, ""

    # Priorizar archivos de proyecciones / nba / quant y elegir el más reciente
    def prioridad(ruta: str) -> tuple[int, float]:
        nombre = os.path.basename(ruta).lower()
        score = 0
        if any(k in nombre for k in ["proyeccion", "nba", "quant", "datos", "stats"]):
            score = 1
        try:
            mtime = os.path.getmtime(ruta)
        except OSError:
            mtime = 0.0
        return (score, mtime)

    archivos_csv.sort(key=prioridad, reverse=True)
    elegido = archivos_csv[0]
    return pd.read_csv(elegido), os.path.basename(elegido)


# ==============================================================================
# FUNCIONES ESTADÍSTICAS NATIVAS (CERO DEPENDENCIAS EXTERNAS)
# ==============================================================================
def prob_normal_over(mu: float, std: float, linea_entera: int) -> float:
    std_segura = max(float(std), 2.5)
    umbral = float(linea_entera) - 0.5
    z = (umbral - float(mu)) / std_segura
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return float(max(0.0, min(1.0, 1.0 - cdf)))


def prob_poisson_over(lam: float, k_min: int) -> float:
    lam_f = float(lam)
    k = int(k_min)
    if lam_f <= 0.0:
        return 0.0
    if k <= 0:
        return 1.0
    cdf = sum((lam_f ** i) * math.exp(-lam_f) / math.factorial(i) for i in range(k))
    return float(max(0.0, min(1.0, 1.0 - cdf)))


def detectar_columna(df: pd.DataFrame, candidatas: list[str], default: str | None = None) -> str | None:
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidatas:
        if cand in df.columns:
            return cand
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return default


# ==============================================================================
# INTERFAZ PRINCIPAL DE JUGADORES
# ==============================================================================
st.title("🏀 YZ Quant NBA — Proyecciones & Análisis de Jugadores")

df, nombre_archivo = cargar_csv_repositorio()

with st.sidebar:
    st.header("🎛️ Filtros de Cartelera")
    archivo_subido = st.file_uploader("Cargar CSV alternativo (opcional)", type=["csv"])

if archivo_subido is not None:
    df = pd.read_csv(archivo_subido)
    nombre_archivo = archivo_subido.name

if df is None or df.empty:
    st.warning("No se detectó ningún archivo `.csv` en la carpeta del repositorio. Verifica que el workflow haya guardado el CSV en la raíz del repo.")
    st.stop()

# Detección flexible de columnas para compatibilidad total con cualquier versión del script
col_jug = detectar_columna(df, ["Jugador", "Player", "Nombre"], df.columns[0])
col_eq = detectar_columna(df, ["Equipo", "Team"])
col_rival = detectar_columna(df, ["Rival (Hoy)", "Rival", "Opponent", "Matchup"])
col_estado = detectar_columna(df, ["Estado ESPN", "Estado", "Status"])
col_carga = detectar_columna(df, ["Estado Carga", "Contexto", "Uso"])
col_pts = detectar_columna(df, ["PTS Proyectados", "PTS", "Puntos"])
col_pra = detectar_columna(df, ["PRA Promedios", "PRA", "PRA Proyectados"])
col_3pt = detectar_columna(df, ["Triples Prom", "3PT Proyectados", "3PT", "Triples"])
col_std = detectar_columna(df, ["Varianza (std)", "STD", "Desviacion"])
col_estab = detectar_columna(df, ["Estabilidad", "Consistencia"])
col_def = detectar_columna(df, ["Factor Defensivo", "Defensa Rival", "Defensa"])

st.caption(f"Cartelera activa: **`{nombre_archivo}`** | **{len(df)}** jugadores cargados | Fecha: **{HOY_STR}**")

# Calcular probabilidades si no vienen ya en el CSV
if col_pts and col_std and "Prob >19.5 PTS (%)" not in df.columns:
    df["Prob >19.5 PTS (%)"] = df.apply(
        lambda r: round(prob_normal_over(r[col_pts], r[col_std], 20) * 100, 1), axis=1
    )
if col_pra and col_std and "Prob >34.5 PRA (%)" not in df.columns:
    df["Prob >34.5 PRA (%)"] = df.apply(
        lambda r: round(prob_normal_over(r[col_pra], max(float(r[col_std]) * 1.12, 3.5), 35) * 100, 1), axis=1
    )
if col_3pt and "Prob >1.5 Triples (%)" not in df.columns:
    df["Prob >1.5 Triples (%)"] = df.apply(
        lambda r: round(prob_poisson_over(r[col_3pt], 2) * 100, 1), axis=1
    )

# Filtros en barra lateral
with st.sidebar:
    busqueda_jug = st.text_input("🔍 Buscar jugador", placeholder="Ej. Doncic, Brunson, Tatum...")

    if col_eq:
        equipos = ["Todos"] + sorted(df[col_eq].dropna().astype(str).unique().tolist())
        eq_sel = st.selectbox("Equipo", equipos)
    else:
        eq_sel = "Todos"

    solo_activos = st.checkbox("Ocultar jugadores GTD / Lesionados", value=True) if col_estado else False
    quitar_boost = st.checkbox("Simular sin bono +8% (Usage Boost)", value=False) if col_carga else False

    if col_estab:
        estabs = df[col_estab].dropna().astype(str).unique().tolist()
        estab_sel = st.multiselect("Estabilidad", options=estabs, default=estabs)
    else:
        estab_sel = []

df_view = df.copy()

if busqueda_jug.strip():
    df_view = df_view[df_view[col_jug].astype(str).str.contains(busqueda_jug.strip(), case=False, na=False)]
if col_eq and eq_sel != "Todos":
    df_view = df_view[df_view[col_eq].astype(str) == eq_sel]
if col_estado and solo_activos:
    df_view = df_view[~df_view[col_estado].astype(str).str.contains("GTD|OUT", case=False, na=False)]
if col_estab and estab_sel:
    df_view = df_view[df_view[col_estab].astype(str).isin(estab_sel)]

if quitar_boost and col_carga:
    mask_b = df_view[col_carga].astype(str).str.contains("USAGE|BOOST", case=False, na=False)
    if col_pts:
        df_view.loc[mask_b, col_pts] = (df_view.loc[mask_b, col_pts] / 1.08).round(1)
    if col_pra:
        df_view.loc[mask_b, col_pra] = (df_view.loc[mask_b, col_pra] / 1.08).round(1)
    if col_3pt:
        df_view.loc[mask_b, col_3pt] = (df_view.loc[mask_b, col_3pt] / 1.05).round(2)

# ==============================================================================
# PESTAÑAS: 1. INTERFAZ DE JUGADORES | 2. SIMULADOR PARLAY & RUSHBET
# ==============================================================================
tab1, tab2 = st.tabs([
    "🏀 Jugadores & Proyecciones",
    "🧮 Simulador Parlay (3 Patas)",
])

with tab1:
    if col_pts and not df_view.empty:
        st.subheader("🔥 Líderes Proyectados de la Jornada")
        top_df = df_view.sort_values(by=col_pts, ascending=False).head(4)
        cols_top = st.columns(len(top_df))
        for i, (_, row) in enumerate(top_df.iterrows()):
            with cols_top[i]:
                eq_txt = f" ({row[col_eq]})" if col_eq else ""
                pra_txt = f" | {row[col_pra]} PRA" if col_pra else ""
                tri_txt = f"3PT: {row[col_3pt]}" if col_3pt else ""
                est_txt = f" | {row[col_estab]}" if col_estab else ""
                st.metric(
                    label=f"{row[col_jug]}{eq_txt}",
                    value=f"{row[col_pts]} PTS{pra_txt}",
                    delta=f"{tri_txt}{est_txt}".strip(" |"),
                )
                sub_parts = []
                if col_rival:
                    sub_parts.append(str(row[col_rival]))
                if col_carga:
                    sub_parts.append(str(row[col_carga]))
                if sub_parts:
                    st.caption(" • ".join(sub_parts))

        st.divider()

    st.subheader("📋 Tabla Completa de Jugadores")
    st.dataframe(df_view, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Probabilidad Conjunta y Cuota Mínima Rentable (EV > 0)")
    lista_jugadores = df_view[col_jug].dropna().astype(str).tolist()
    if len(lista_jugadores) < 3:
        lista_jugadores = df[col_jug].dropna().astype(str).tolist()

    patas = []
    cols_p = st.columns(3)
    for idx, c in enumerate(cols_p, 1):
        with c:
            st.markdown(f"**Pata #{idx}**")
            j_sel = st.selectbox(f"Jugador {idx}", lista_jugadores, index=min(idx - 1, len(lista_jugadores) - 1), key=f"p_jug_{idx}")
            r_jug = df[df[col_jug].astype(str) == j_sel].iloc[0]

            mercados_disp = []
            if col_pts:
                mercados_disp.append("Puntos (Over)")
            if col_pra:
                mercados_disp.append("PRA (Over)")
            if col_3pt:
                mercados_disp.append("Triples (Over)")

            merc = st.selectbox("Mercado", mercados_disp, key=f"p_merc_{idx}")
            std_val = float(r_jug[col_std]) if col_std else 5.0

            if merc == "Puntos (Over)":
                lin = st.number_input("Línea entera (ej. 20 para 20+)", min_value=5, max_value=55, value=20, key=f"p_lin_{idx}")
                prob = prob_normal_over(float(r_jug[col_pts]), std_val, lin)
            elif merc == "PRA (Over)":
                lin = st.number_input("Línea entera PRA (ej. 35 para 35+)", min_value=15, max_value=70, value=35, step=5, key=f"p_lin_{idx}")
                prob = prob_normal_over(float(r_jug[col_pra]), max(std_val * 1.12, 3.5), lin)
            else:
                lin = st.number_input("Línea entera Triples (ej. 2 para 2+)", min_value=1, max_value=8, value=2, key=f"p_lin_{idx}")
                prob = prob_poisson_over(float(r_jug[col_3pt]), lin)

            st.caption(f"Probabilidad estimada: **{prob*100:.1f}%**")
            patas.append(prob)

    st.divider()
    c_ev1, c_ev2, c_ev3 = st.columns(3)
    cuota_rb = c_ev1.number_input("Cuota en Rushbet (@)", min_value=1.10, max_value=20.00, value=2.25, step=0.01)
    prob_total = patas[0] * patas[1] * patas[2]
    cuota_min = (1.0 / prob_total) if prob_total > 0 else 99.0
    ev = (prob_total * cuota_rb - 1.0) * 100.0

    c_ev2.metric("Probabilidad Conjunta", f"{prob_total*100:.1f}%", f"Cuota mín EV>0: @{cuota_min:.2f}")
    c_ev3.metric("Valor Esperado (EV)", f"{ev:+.1f}%")
