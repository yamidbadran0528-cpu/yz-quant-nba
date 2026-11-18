import io
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA - YZ QUANT NBA v2
# ==============================================================================
st.set_page_config(
    page_title="YZ Quant NBA v2 | Motor Cuantitativo & Kelly",
    page_icon="🏀",
    layout="wide",
)

ZONA_COL = ZoneInfo("America/Bogota")
HOY_STR = datetime.now(ZONA_COL).strftime("%Y-%m-%d")


# ==============================================================================
# FUNCIONES ESTADÍSTICAS Y DE VALOR ESPERADO
# ==============================================================================
def prob_normal_over(mu: float, std: float, linea_entera: int) -> float:
    """P(X >= linea_entera) usando Normal con corrección de continuidad (linea - 0.5)."""
    std_segura = max(float(std), 2.5)
    umbral = float(linea_entera) - 0.5
    return float(1.0 - stats.norm.cdf(umbral, loc=float(mu), scale=std_segura))


def prob_poisson_over(lam: float, k_min: int) -> float:
    """P(X >= k_min) usando distribución discreta de Poisson."""
    if lam <= 0:
        return 0.0
    return float(1.0 - stats.poisson.cdf(int(k_min) - 1, mu=float(lam)))


def calcular_kelly_fraccion(prob: float, cuota: float) -> float:
    """Fracción de Kelly óptima f* = (p * q - 1) / (q - 1)."""
    if cuota <= 1.0 or prob <= 0.0:
        return 0.0
    b = cuota - 1.0
    q = 1.0 - prob
    f = (prob * b - q) / b
    return max(0.0, float(f))


def evaluar_riesgo_blowout(factor_def_rival: str, pts_proy: float) -> str:
    """Detecta posible riesgo de paliza (blowout) cuando el rival es muy permeable y la estrella proyecta alto."""
    try:
        f_val = float(str(factor_def_rival).replace("x", "").strip())
    except ValueError:
        f_val = 1.0
    if f_val >= 1.05 and pts_proy >= 28.0:
        return "⚠️ RIESGO BLOWOUT"
    return "✅ RITMO NORMAL"


# ==============================================================================
# INTERFAZ PRINCIPAL
# ==============================================================================
st.title("🏀 YZ Quant NBA v2 — Motor Cuantitativo, Kelly & Gestión de Banca")
st.caption(f"Calibrado para Rushbet Colombia | Fecha operativa: {HOY_STR} (Hora Bogotá)")

with st.sidebar:
    st.header("💰 1. Gestión de Banca (Regla 50/50)")
    banca_actual = st.number_input(
        "Saldo actual en Rushbet (COP)",
        min_value=1000,
        max_value=5000000,
        value=10643,
        step=500,
    )
    piso_seguridad = st.number_input(
        "Piso colchón de seguridad (COP)",
        min_value=10000,
        max_value=500000,
        value=45000,
        step=5000,
        help="Mientras la banca esté por debajo de este piso, reinvierte el 100%. Al superarlo, retira el 50% de cada ganancia neta.",
    )
    pct_riesgo_diario = st.slider(
        "% de Banca a arriesgar hoy",
        min_value=20,
        max_value=100,
        value=100 if banca_actual <= 15000 else 40,
        step=5,
        help="Usa 40% (Kelly fraccional) cuando tengas >= $25,000 COP. En saldos iniciales <= $15,000 COP se reparte el saldo operativo.",
    )

    stake_total = int(round(banca_actual * (pct_riesgo_diario / 100.0)))
    stake_a = int(round(stake_total * 0.65))
    stake_b = stake_total - stake_a

    st.metric("Apuesta Total Hoy", f"${stake_total:,} COP")
    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Comb. A (65%)", f"${stake_a:,}")
    col_s2.metric("Comb. B (35%)", f"${stake_b:,}")

    if banca_actual > piso_seguridad:
        st.success(f"🟢 Modo Cosecha 50/50 ACTIVO (Superaste ${piso_seguridad:,} COP).")
    else:
        faltante = piso_seguridad - banca_actual
        st.info(f"🚀 Modo Despegue (100% reinversión). Faltan ${faltante:,} COP para activar retiros 50/50.")

    st.divider()
    st.header("📂 2. Cargar Proyecciones")
    archivo_csv = st.file_uploader("Sube tu CSV diario (YZ_Quant_NBA_YYYY-MM-DD.csv)", type=["csv"])

if archivo_csv is None:
    st.warning("⬅️ Sube el archivo `YZ_Quant_NBA_YYYY-MM-DD.csv` en el panel izquierdo para iniciar el análisis.")
    st.stop()

df = pd.read_csv(archivo_csv)

# Compatibilidad con nombres de columnas v1 y v2
col_rival = "Rival (Hoy)" if "Rival (Hoy)" in df.columns else "Rival"
col_estado = "Estado ESPN" if "Estado ESPN" in df.columns else "Estado"
col_carga = "Estado Carga" if "Estado Carga" in df.columns else "Contexto"
col_def = "Factor Defensivo" if "Factor Defensivo" in df.columns else "Defensa Rival"
col_min = "Minutos L10" if "Minutos L10" in df.columns else "MIN Prom"
col_3pt = "Triples Prom" if "Triples Prom" in df.columns else "3PT Proyectados"

# ==============================================================================
# PESTAÑAS DEL SISTEMA
# ==============================================================================
tab1, tab2, tab3 = st.tabs([
    "🎯 1. Buscador de Patas & Deflactor",
    "🧮 2. Constructor Parlay + Valor Esperado (EV)",
    "📒 3. Bitácora & Calibración",
])

with tab1:
    st.subheader("Explorador de Oportunidades con Control Anti-Inflación")
    c1, c2, c3, c4 = st.columns(4)
    equipos_disp = ["Todos"] + sorted(df["Equipo"].unique().tolist())
    eq_filtro = c1.selectbox("Filtrar Equipo", equipos_disp)
    solo_activos = c2.checkbox("Solo 🟢 ACTIVO (Excluir GTD)", value=True)
    deflactar_boost = c3.checkbox(
        "Simular sin bono +8% en equipo seleccionado",
        value=False,
        help="Útil si detectas en el reporte médico un jugador OUT que aún no debuta esta temporada.",
    )
    estabilidad_filtro = c4.multiselect(
        "Estabilidad",
        options=df["Estabilidad"].unique().tolist(),
        default=df["Estabilidad"].unique().tolist(),
    )

    df_view = df.copy()
    if eq_filtro != "Todos":
        df_view = df_view[df_view["Equipo"] == eq_filtro]
    if solo_activos:
        df_view = df_view[~df_view[col_estado].astype(str).str.contains("GTD", na=False)]
    if estabilidad_filtro:
        df_view = df_view[df_view["Estabilidad"].isin(estabilidad_filtro)]

    if deflactar_boost:
        mask_b = df_view[col_carga].astype(str).str.contains("USAGE", na=False)
        df_view.loc[mask_b, "PTS Proyectados"] = (df_view.loc[mask_b, "PTS Proyectados"] / 1.08).round(1)
        df_view.loc[mask_b, "PRA Promedios"] = (df_view.loc[mask_b, "PRA Promedios"] / 1.08).round(1)
        df_view.loc[mask_b, col_3pt] = (df_view.loc[mask_b, col_3pt] / 1.05).round(2)

    df_view["Alerta Ritmo"] = df_view.apply(
        lambda r: evaluar_riesgo_blowout(r[col_def], r["PTS Proyectados"]), axis=1
    )

    st.dataframe(df_view, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Simulador de Parlay de 3 Patas con Cuotas Reales de Rushbet")
    st.markdown("Selecciona **3 jugadores de partidos distintos**, ingresa la cuota que ofrece Rushbet y verifica que el **EV sea positivo (`> +15%`)**.")

    jugadores_activos = df[~df[col_estado].astype(str).str.contains("GTD", na=False)]["Jugador"].tolist()
    patas_seleccionadas = []

    cols_patas = st.columns(3)
    for idx, col in enumerate(cols_patas, 1):
        with col:
            st.markdown(f"**Pata #{idx}**")
            jug = st.selectbox(f"Jugador {idx}", jugadores_activos, index=min(idx - 1, len(jugadores_activos) - 1), key=f"jug_{idx}")
            fila = df[df["Jugador"] == jug].iloc[0]

            quitar_boost_pata = st.checkbox(
                "Quitar bono +8%/+5% a este jugador",
                value=False,
                key=f"nb_{idx}",
            )

            mercado = st.selectbox(
                "Mercado",
                ["Puntos (Over)", "PRA (Over)", "Triples (Over)"],
                key=f"merc_{idx}",
            )

            if mercado == "Puntos (Over)":
                linea = st.number_input("Línea entera (ej. 20 para 20+)", min_value=8, max_value=55, value=20, key=f"lin_{idx}")
                mu = fila["PTS Proyectados"] / (1.08 if quitar_boost_pata and "USAGE" in str(fila[col_carga]) else 1.0)
                std = float(fila["Varianza (std)"])
                prob = prob_normal_over(mu, std, linea)
                desc = f"{jug}: {linea}+ PTS (Proy {mu:.1f}, σ={std:.1f})"
            elif mercado == "PRA (Over)":
                linea = st.number_input("Línea entera PRA (ej. 35 para 35+)", min_value=15, max_value=70, value=35, step=5, key=f"lin_{idx}")
                mu = fila["PRA Promedios"] / (1.08 if quitar_boost_pata and "USAGE" in str(fila[col_carga]) else 1.0)
                # Factor 1.12 sobre std_pts para capturar covarianza real de PRA
                std_pra = max(float(fila["Varianza (std)"]) * 1.12, 3.5)
                prob = prob_normal_over(mu, std_pra, linea)
                desc = f"{jug}: {linea}+ PRA (Proy {mu:.1f}, σ_PRA={std_pra:.1f})"
            else:
                linea = st.number_input("Línea entera Triples (ej. 2 para 2+)", min_value=1, max_value=8, value=2, key=f"lin_{idx}")
                lam = fila[col_3pt] / (1.05 if quitar_boost_pata and "USAGE" in str(fila[col_carga]) else 1.0)
                prob = prob_poisson_over(lam, linea)
                desc = f"{jug}: {linea}+ Triples (Proy {lam:.2f} 3PT)"

            partido_norm = " vs ".join(sorted([str(fila["Equipo"]), str(fila[col_rival]).replace("vs ", "")]))
            st.caption(f"Partido: `{partido_norm}` | Prob. Pata: **{prob*100:.1f}%**")
            patas_seleccionadas.append({"desc": desc, "prob": prob, "partido": partido_norm})

    partidos_unicos = {p["partido"] for p in patas_seleccionadas}
    if len(partidos_unicos) < 3:
        st.error("⚠️ ALERTA DE CORRELACIÓN: Dos o más patas pertenecen al mismo partido. Cambia una selección para mantener 3 partidos distintos.")

    st.divider()
    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    cuota_rushbet = col_q1.number_input("Cuota Total en Rushbet (@)", min_value=1.10, max_value=20.00, value=2.25, step=0.01)
    boleto_tipo = col_q2.selectbox("Asignación de Boleto", ["Combinada A (65%)", "Combinada B (35%)"])

    prob_conjunta = patas_seleccionadas[0]["prob"] * patas_seleccionadas[1]["prob"] * patas_seleccionadas[2]["prob"]
    cuota_minima_ev = (1.0 / prob_conjunta) if prob_conjunta > 0 else 99.0
    ev_pct = (prob_conjunta * cuota_rushbet - 1.0) * 100.0
    kelly_opt = calcular_kelly_fraccion(prob_conjunta, cuota_rushbet) * 100.0

    stake_asignado = stake_a if "A" in boleto_tipo else stake_b
    cobro_potencial = int(round(stake_asignado * cuota_rushbet))

    col_q3.metric("Probabilidad Conjunta", f"{prob_conjunta*100:.1f}%", f"Cuota mín EV>0: @{cuota_minima_ev:.2f}")
    col_q4.metric("Valor Esperado (EV)", f"{ev_pct:+.1f}%", f"Medio Kelly: {kelly_opt*0.5:.1f}% banca")

    if cuota_rushbet >= 2.00 and ev_pct >= 15.0 and len(partidos_unicos) == 3:
        st.success(
            f"✅ **BOLETO APROBADO:** Cuota `@{cuota_rushbet:.2f}` con **EV `{ev_pct:+.1f}%`**. "
            f"Apostando **`${stake_asignado:,} COP`**, el cobro bruto es **`${cobro_potencial:,} COP`**."
        )
    else:
        st.warning("⚠️ Revisa que la cuota sea >= @2.00, el EV sea >= +15% y los 3 partidos sean distintos.")

with tab3:
    st.subheader("Registro Rápido de Bitácora Diaria")
    st.markdown("Descarga o actualiza tu registro de control para medir calibración real día a día:")
    bitacora_ejemplo = pd.DataFrame([
        {
            "Fecha": HOY_STR,
            "Boleto": "Combinada A",
            "Selecciones": "Luka Doncic 32+ PTS | Jalen Brunson 22+ PTS | Deni Avdija 18+ PTS",
            "Cuota": 2.42,
            "Prob_Modelo_%": 70.0,
            "Apuesta_COP": 7000,
            "Cobro_Potencial_COP": 16940,
            "Estado": "PENDIENTE",
        },
        {
            "Fecha": HOY_STR,
            "Boleto": "Combinada B",
            "Selecciones": "Victor Wembanyama 35+ PRA | Karl-Anthony Towns 35+ PRA | Darryn Peterson 2+ 3PT",
            "Cuota": 2.39,
            "Prob_Modelo_%": 52.5,
            "Apuesta_COP": 3643,
            "Cobro_Potencial_COP": 8707,
            "Estado": "PENDIENTE",
        },
    ])
    st.dataframe(bitacora_ejemplo, use_container_width=True, hide_index=True)
    csv_bytes = bitacora_ejemplo.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="⬇️ Descargar Bitácora de Hoy (CSV)",
        data=csv_bytes,
        file_name=f"Bitacora_YZ_Quant_{HOY_STR}.csv",
        mime="text/csv",
    )
