import glob
import json
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA - YZ QUANT NBA v2.3 (CARGA AUTOMÁTICA + INTERFAZ JUGADORES)
# ==============================================================================
st.set_page_config(
    page_title="YZ Quant NBA v2.3 | Motor Cuantitativo & Kelly",
    page_icon="🏀",
    layout="wide",
)

ZONA_COL = ZoneInfo("America/Bogota")
HOY_STR = datetime.now(ZONA_COL).strftime("%Y-%m-%d")

STATE_FILE = "banca_state.json"
BITACORA_FILE = "bitacora_yz_quant.csv"
SALDO_BASE_INICIAL = 22809  # Saldo real verificado al 2026-11-18


# ==============================================================================
# DETECCIÓN AUTOMÁTICA DEL CSV EN EL REPOSITORIO
# ==============================================================================
def buscar_csv_automatico() -> tuple[pd.DataFrame | None, str]:
    """
    Busca automáticamente YZ_Quant_NBA_HOY.csv en el repositorio; si aún no corre
    el workflow de hoy, carga el YZ_Quant_NBA_*.csv más reciente disponible.
    """
    archivo_hoy = f"YZ_Quant_NBA_{HOY_STR}.csv"
    if os.path.exists(archivo_hoy):
        return pd.read_csv(archivo_hoy), archivo_hoy

    candidatos = sorted(glob.glob("YZ_Quant_NBA_*.csv"), reverse=True)
    if candidatos:
        return pd.read_csv(candidatos[0]), candidatos[0]

    return None, ""


# ==============================================================================
# GESTIÓN PERSISTENTE DE BANCA Y BITÁCORA
# ==============================================================================
def cargar_estado_banca() -> dict:
    estado_default = {
        "saldo": SALDO_BASE_INICIAL,
        "piso_seguridad": 45000,
        "pct_riesgo": 45,
        "ultima_actualizacion": HOY_STR,
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                estado_default.update(data)
        except Exception:
            pass

    if "saldo" in st.query_params:
        try:
            estado_default["saldo"] = int(float(st.query_params["saldo"]))
        except ValueError:
            pass

    return estado_default


def guardar_estado_banca(saldo: int, piso: int, pct_riesgo: int) -> None:
    payload = {
        "saldo": int(saldo),
        "piso_seguridad": int(piso),
        "pct_riesgo": int(pct_riesgo),
        "ultima_actualizacion": HOY_STR,
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    st.query_params["saldo"] = str(int(saldo))


def cargar_bitacora() -> pd.DataFrame:
    cols = ["Fecha", "Boleto", "Selecciones", "Cuota", "Prob_Modelo_%", "Apuesta_COP", "Estado", "Retorno_COP", "Saldo_Post_COP"]
    if os.path.exists(BITACORA_FILE):
        try:
            df_b = pd.read_csv(BITACORA_FILE)
            for c in cols:
                if c not in df_b.columns:
                    df_b[c] = ""
            return df_b[cols]
        except Exception:
            pass
    return pd.DataFrame([
        {
            "Fecha": "2026-11-17",
            "Boleto": "Combinada A",
            "Selecciones": "Luka Doncic 32+ PTS | Jalen Brunson 22+ PTS | Deni Avdija 18+ PTS (Void)",
            "Cuota": 2.02,
            "Prob_Modelo_%": 70.0,
            "Apuesta_COP": 7000,
            "Estado": "GANADA",
            "Retorno_COP": 14140,
            "Saldo_Post_COP": 14140,
        },
        {
            "Fecha": "2026-11-17",
            "Boleto": "Combinada B",
            "Selecciones": "Victor Wembanyama 35+ PRA | Karl-Anthony Towns 35+ PRA | Darryn Peterson 2+ 3PT",
            "Cuota": 2.39,
            "Prob_Modelo_%": 52.5,
            "Apuesta_COP": 3643,
            "Estado": "GANADA",
            "Retorno_COP": 8707,
            "Saldo_Post_COP": 22809,
        },
    ])


def guardar_bitacora(df_b: pd.DataFrame) -> None:
    try:
        df_b.to_csv(BITACORA_FILE, index=False, encoding="utf-8-sig")
    except Exception:
        pass


# ==============================================================================
# FUNCIONES ESTADÍSTICAS EXACTAS (100% STDLIB MATH, CERO SCIPY)
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


def calcular_kelly_fraccion(prob: float, cuota: float) -> float:
    if cuota <= 1.0 or prob <= 0.0:
        return 0.0
    b = cuota - 1.0
    q = 1.0 - prob
    f = (prob * b - q) / b
    return max(0.0, float(f))


def evaluar_riesgo_blowout(factor_def_rival: str, pts_proy: float) -> str:
    try:
        f_val = float(str(factor_def_rival).replace("x", "").strip())
    except ValueError:
        f_val = 1.0
    if f_val >= 1.05 and pts_proy >= 28.0:
        return "⚠️ RIESGO BLOWOUT"
    return "✅ RITMO NORMAL"


# ==============================================================================
# INICIALIZACIÓN DE ESTADO EN SESIÓN
# ==============================================================================
estado_guardado = cargar_estado_banca()
if "saldo_banca" not in st.session_state:
    st.session_state["saldo_banca"] = int(estado_guardado["saldo"])
if "piso_banca" not in st.session_state:
    st.session_state["piso_banca"] = int(estado_guardado["piso_seguridad"])
if "pct_riesgo" not in st.session_state:
    st.session_state["pct_riesgo"] = int(estado_guardado["pct_riesgo"])

st.title("🏀 YZ Quant NBA v2.3 — Proyecciones, Parlay Kelly & Banca")

# ==============================================================================
# BARRA LATERAL: BANCA AUTOMÁTICA + CARGA OPCIONAL DE CSV
# ==============================================================================
with st.sidebar:
    st.header("💰 Banca Automática (Regla 50/50)")
    banca_actual = int(st.session_state["saldo_banca"])
    st.metric("Saldo Guardado en Rushbet", f"${banca_actual:,} COP")

    piso_seguridad = int(st.session_state["piso_banca"])
    pct_riesgo_diario = int(st.session_state["pct_riesgo"])

    stake_total = int(round(banca_actual * (pct_riesgo_diario / 100.0)))
    stake_a = int(round(stake_total * 0.65))
    stake_b = stake_total - stake_a
    reserva = banca_actual - stake_total

    st.metric(f"Apuesta Hoy ({pct_riesgo_diario}% Kelly)", f"${stake_total:,} COP", f"Reserva blindada: ${reserva:,} COP")
    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Comb. A (65%)", f"${stake_a:,}")
    col_s2.metric("Comb. B (35%)", f"${stake_b:,}")

    if banca_actual > piso_seguridad:
        st.success(f"🟢 Modo Cosecha 50/50 ACTIVO (>${piso_seguridad:,}).")
    else:
        faltante = piso_seguridad - banca_actual
        st.info(f"🚀 Modo Despegue (100% reinversión). Faltan ${faltante:,} COP para piso.")

    with st.expander("⚙️ Ajustar saldo o parámetros", expanded=False):
        nuevo_saldo_manual = st.number_input("Corregir saldo (COP)", min_value=1000, max_value=10000000, value=banca_actual, step=100)
        nuevo_piso = st.number_input("Piso colchón (COP)", min_value=10000, max_value=500000, value=piso_seguridad, step=5000)
        nuevo_pct = st.slider("% Riesgo diario", min_value=20, max_value=100, value=pct_riesgo_diario, step=5)
        if st.button("💾 Guardar", use_container_width=True):
            st.session_state["saldo_banca"] = int(nuevo_saldo_manual)
            st.session_state["piso_banca"] = int(nuevo_piso)
            st.session_state["pct_riesgo"] = int(nuevo_pct)
            guardar_estado_banca(nuevo_saldo_manual, nuevo_piso, nuevo_pct)
            st.rerun()

    st.divider()
    archivo_manual = st.file_uploader("📂 Cargar otro CSV manualmente (opcional)", type=["csv"])

# Carga automática del CSV desde el repo (sin bloquear la interfaz)
if archivo_manual is not None:
    df = pd.read_csv(archivo_manual)
    nombre_fuente = archivo_manual.name
else:
    df, nombre_fuente = buscar_csv_automatico()

if df is None or df.empty:
    st.error("No se encontró ningún archivo `YZ_Quant_NBA_*.csv` en el repositorio todavía. Ejecuta `script_actualizar_nba.py` o sube un CSV en la barra lateral.")
    st.stop()

st.caption(f"Fecha operativa: **{HOY_STR}** (Bogotá) | Archivo activo cargado automáticamente: **`{nombre_fuente}`** ({len(df)} jugadores)")

# Compatibilidad de nombres de columnas entre versiones del CSV
col_rival = "Rival (Hoy)" if "Rival (Hoy)" in df.columns else "Rival"
col_estado = "Estado ESPN" if "Estado ESPN" in df.columns else "Estado"
col_carga = "Estado Carga" if "Estado Carga" in df.columns else "Contexto"
col_def = "Factor Defensivo" if "Factor Defensivo" in df.columns else "Defensa Rival"
col_min = "Minutos L10" if "Minutos L10" in df.columns else "MIN Prom"
col_3pt = "Triples Prom" if "Triples Prom" in df.columns else "3PT Proyectados"

# Calcular probabilidades base si el CSV viene de la versión compacta
if "Prob >19.5 PTS (%)" not in df.columns:
    df["Prob >19.5 PTS (%)"] = df.apply(
        lambda r: round(prob_normal_over(r["PTS Proyectados"], r["Varianza (std)"], 20) * 100, 1), axis=1
    )
if "Prob >1.5 Triples (%)" not in df.columns:
    df["Prob >1.5 Triples (%)"] = df.apply(
        lambda r: round(prob_poisson_over(r[col_3pt], 2) * 100, 1), axis=1
    )
if "Prob >34.5 PRA (%)" not in df.columns:
    df["Prob >34.5 PRA (%)"] = df.apply(
        lambda r: round(prob_normal_over(r["PRA Promedios"], max(float(r["Varianza (std)"]) * 1.12, 3.5), 35) * 100, 1), axis=1
    )

# ==============================================================================
# PESTAÑAS PRINCIPALES (INTERFAZ DE JUGADORES VISIBLE AL INSTANTE)
# ==============================================================================
tab1, tab2, tab3 = st.tabs([
    "🏀 1. Interfaz de Jugadores & Proyecciones",
    "🧮 2. Constructor Parlay + Cuota Rushbet (EV)",
    "📒 3. Cierre Automático & Bitácora",
])

with tab1:
    f1, f2, f3, f4 = st.columns(4)
    equipos_disp = ["Todos"] + sorted(df["Equipo"].unique().tolist())
    eq_filtro = f1.selectbox("Equipo", equipos_disp)
    solo_activos = f2.checkbox("Ocultar 🟡 GTD (Solo Activos)", value=True)
    deflactar_boost = f3.checkbox("Quitar bono +8% (Simular base pura)", value=False)
    estabilidad_filtro = f4.multiselect(
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
        df_view["Prob >19.5 PTS (%)"] = df_view.apply(
            lambda r: round(prob_normal_over(r["PTS Proyectados"], r["Varianza (std)"], 20) * 100, 1), axis=1
        )
        df_view["Prob >1.5 Triples (%)"] = df_view.apply(
            lambda r: round(prob_poisson_over(r[col_3pt], 2) * 100, 1), axis=1
        )
        df_view["Prob >34.5 PRA (%)"] = df_view.apply(
            lambda r: round(prob_normal_over(r["PRA Promedios"], max(float(r["Varianza (std)"]) * 1.12, 3.5), 35) * 100, 1), axis=1
        )

    df_view["Alerta Ritmo"] = df_view.apply(
        lambda r: evaluar_riesgo_blowout(r[col_def], r["PTS Proyectados"]), axis=1
    )

    st.subheader("🔥 Top 4 Jugadores Destacados de la Cartelera")
    top4 = df_view.sort_values(by=["PTS Proyectados", "PRA Promedios"], ascending=False).head(4)
    if not top4.empty:
        cards = st.columns(len(top4))
        for idx, (_, r) in enumerate(top4.iterrows()):
            with cards[idx]:
                st.metric(
                    label=f"{r['Jugador']} ({r['Equipo']})",
                    value=f"{r['PTS Proyectados']} PTS | {r['PRA Promedios']} PRA",
                    delta=f"3PT: {r[col_3pt]} | {r['Estabilidad']}",
                )
                st.caption(f"{r[col_rival]} | {r[col_carga]} | σ={r['Varianza (std)']}")

    st.divider()
    st.subheader("📋 Tabla Completa de Jugadores y Probabilidades")
    st.dataframe(df_view, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Constructor de Parlay (3 Patas) con Cuotas Reales de Rushbet")
    jugadores_activos = df[~df[col_estado].astype(str).str.contains("GTD", na=False)]["Jugador"].tolist()
    patas_seleccionadas = []

    cols_patas = st.columns(3)
    for idx, col in enumerate(cols_patas, 1):
        with col:
            st.markdown(f"**Pata #{idx}**")
            jug = st.selectbox(f"Jugador {idx}", jugadores_activos, index=min(idx - 1, len(jugadores_activos) - 1), key=f"jug_{idx}")
            fila = df[df["Jugador"] == jug].iloc[0]

            quitar_boost_pata = st.checkbox("Quitar bono +8%/+5%", value=False, key=f"nb_{idx}")
            mercado = st.selectbox("Mercado", ["Puntos (Over)", "PRA (Over)", "Triples (Over)"], key=f"merc_{idx}")

            if mercado == "Puntos (Over)":
                linea = st.number_input("Línea entera (ej. 20 para 20+)", min_value=8, max_value=55, value=20, key=f"lin_{idx}")
                mu = fila["PTS Proyectados"] / (1.08 if quitar_boost_pata and "USAGE" in str(fila[col_carga]) else 1.0)
                std = float(fila["Varianza (std)"])
                prob = prob_normal_over(mu, std, linea)
                desc = f"{jug} {linea}+ PTS"
            elif mercado == "PRA (Over)":
                linea = st.number_input("Línea entera PRA (ej. 35 para 35+)", min_value=15, max_value=70, value=35, step=5, key=f"lin_{idx}")
                mu = fila["PRA Promedios"] / (1.08 if quitar_boost_pata and "USAGE" in str(fila[col_carga]) else 1.0)
                std_pra = max(float(fila["Varianza (std)"]) * 1.12, 3.5)
                prob = prob_normal_over(mu, std_pra, linea)
                desc = f"{jug} {linea}+ PRA"
            else:
                linea = st.number_input("Línea entera Triples (ej. 2 para 2+)", min_value=1, max_value=8, value=2, key=f"lin_{idx}")
                lam = fila[col_3pt] / (1.05 if quitar_boost_pata and "USAGE" in str(fila[col_carga]) else 1.0)
                prob = prob_poisson_over(lam, linea)
                desc = f"{jug} {linea}+ 3PT"

            partido_norm = " vs ".join(sorted([str(fila["Equipo"]), str(fila[col_rival]).replace("vs ", "")]))
            st.caption(f"Partido: `{partido_norm}` | Prob. Pata: **{prob*100:.1f}%**")
            patas_seleccionadas.append({"desc": desc, "prob": prob, "partido": partido_norm})

    partidos_unicos = {p["partido"] for p in patas_seleccionadas}
    if len(partidos_unicos) < 3:
        st.error("⚠️ ALERTA DE CORRELACIÓN: Dos o más patas pertenecen al mismo partido.")

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

    col_q3.metric("Probabilidad Conjunta", f"{prob_conjunta*100:.1f}%", f"Mín EV>0: @{cuota_minima_ev:.2f}")
    col_q4.metric("Valor Esperado (EV)", f"{ev_pct:+.1f}%", f"Medio Kelly: {kelly_opt*0.5:.1f}%")

    if cuota_rushbet >= 2.00 and ev_pct >= 15.0 and len(partidos_unicos) == 3:
        st.success(
            f"✅ **BOLETO APROBADO:** `{cuota_rushbet:.2f}` con **EV `{ev_pct:+.1f}%`** | "
            f"Apuesta: **`${stake_asignado:,} COP`** $\\rightarrow$ Cobro bruto: **`${cobro_potencial:,} COP`**."
        )
        if st.button("📌 Registrar este boleto como PENDIENTE en Bitácora", use_container_width=True):
            df_bit = cargar_bitacora()
            nueva_fila = pd.DataFrame([{
                "Fecha": HOY_STR,
                "Boleto": "Combinada A" if "A" in boleto_tipo else "Combinada B",
                "Selecciones": " | ".join([p["desc"] for p in patas_seleccionadas]),
                "Cuota": round(cuota_rushbet, 2),
                "Prob_Modelo_%": round(prob_conjunta * 100, 1),
                "Apuesta_COP": stake_asignado,
                "Estado": "PENDIENTE",
                "Retorno_COP": 0,
                "Saldo_Post_COP": banca_actual,
            }])
            df_bit = pd.concat([df_bit, nueva_fila], ignore_index=True)
            guardar_bitacora(df_bit)
            st.toast("Boleto guardado en bitácora.")

with tab3:
    st.subheader("Cierre Rápido de Jornada (Actualiza tu Saldo Automáticamente)")
    c_liq1, c_liq2, c_liq3, c_liq4 = st.columns(4)
    liq_boleto = c_liq1.selectbox("Boleto a liquidar", ["Combinada A", "Combinada B"])
    liq_apuesta = c_liq2.number_input("Monto apostado (COP)", min_value=500, max_value=5000000, value=stake_a if liq_boleto == "Combinada A" else stake_b, step=100)
    liq_cuota = c_liq3.number_input("Cuota final pagada (@)", min_value=1.00, max_value=20.00, value=2.20, step=0.01)
    liq_res = c_liq4.selectbox("Resultado", ["GANADA ✅", "PERDIDA ❌", "ANULADA / VOID ⚪"])

    if st.button("⚡ Liquidar Boleto y Actualizar Saldo Automáticamente", type="primary", use_container_width=True):
        if "GANADA" in liq_res:
            retorno = int(round(liq_apuesta * liq_cuota))
            nuevo_saldo = banca_actual - liq_apuesta + retorno
        elif "PERDIDA" in liq_res:
            retorno = 0
            nuevo_saldo = banca_actual - liq_apuesta
        else:
            retorno = liq_apuesta
            nuevo_saldo = banca_actual

        st.session_state["saldo_banca"] = int(nuevo_saldo)
        guardar_estado_banca(nuevo_saldo, piso_seguridad, pct_riesgo_diario)

        df_bit = cargar_bitacora()
        reg_cierre = pd.DataFrame([{
            "Fecha": HOY_STR,
            "Boleto": liq_boleto,
            "Selecciones": "Cierre directo desde panel",
            "Cuota": round(liq_cuota, 2),
            "Prob_Modelo_%": 0.0,
            "Apuesta_COP": int(liq_apuesta),
            "Estado": liq_res.split()[0],
            "Retorno_COP": retorno,
            "Saldo_Post_COP": int(nuevo_saldo),
        }])
        df_bit = pd.concat([df_bit, reg_cierre], ignore_index=True)
        guardar_bitacora(df_bit)
        st.success(f"Saldo actualizado automáticamente a **`${nuevo_saldo:,} COP`**.")
        st.rerun()

    st.divider()
    df_bit_actual = cargar_bitacora()
    st.dataframe(df_bit_actual, use_container_width=True, hide_index=True)
    csv_bytes = df_bit_actual.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="⬇️ Descargar Respaldo de Bitácora (CSV)",
        data=csv_bytes,
        file_name=f"Bitacora_YZ_Quant_{HOY_STR}.csv",
        mime="text/csv",
    )
