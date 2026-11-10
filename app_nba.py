import math
import json
import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="YZ Quant NBA — Platform (+EV)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    h1, h2, h3 { color: #F1C40F !important; font-family: 'Helvetica Neue', sans-serif; }
    .stMetric { background-color: #1E222D; padding: 15px; border-radius: 10px; border: 1px solid #2E3440; }
    </style>
""", unsafe_allow_html=True)

def calcular_poisson_over(promedio: float, linea: float) -> float:
    k = math.floor(linea)
    prob_acumulada = 0.0
    for i in range(k + 1):
        prob_acumulada += (math.pow(promedio, i) * math.exp(-promedio)) / math.factorial(i)
    return max(0.0, min(1.0, 1.0 - prob_acumulada))

@st.cache_data(ttl=300)
def cargar_datos_locales():
    try:
        with open("datos_nba_hoy.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
        return pd.DataFrame(datos)
    except Exception:
        return pd.DataFrame()

# --- CABECERA ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")
st.caption("Motor cuantitativo alimentado por automatización diaria (GitHub Actions)")

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_str = now_et.strftime('%Y-%m-%d')

st.sidebar.info(f"📅 Jornada: {fecha_str}")

df_raw = cargar_datos_locales()

st.sidebar.markdown("---")
st.sidebar.header("🚑 Reporte de Bajas / Lesiones")
bajas_confirmadas = st.sidebar.multiselect(
    "Selecciona los jugadores descartados (OUT):",
    options=df_raw['Jugador'].tolist() if not df_raw.empty else []
)

min_minutos = st.sidebar.slider("Minutos Mínimos Promedio", 15, 36, 22)
solo_alta_estabilidad = st.sidebar.checkbox("Mostrar solo estabilidad ⭐ ALTA", False)
filtro_volumen_3pt = st.sidebar.checkbox("Filtrar tiradores con al menos 5.5 intentos (3PA)", False)

if df_raw.empty:
    st.error("⚠️ El archivo de datos del día no se ha encontrado. Se ejecutará en la próxima corrida del servidor.")
else:
    equipos_con_baja = set()
    for b in bajas_confirmadas:
        eq = df_raw[df_raw['Jugador'] == b]['Equipo'].values
        if len(eq) > 0:
            equipos_con_baja.add(eq[0])

    procesados = []
    for _, fila in df_raw.iterrows():
        j_nombre = fila['Jugador']
        if j_nombre in bajas_confirmadas:
            continue
            
        f_usage = 1.15 if fila['Equipo'] in equipos_con_baja and fila['Equipo'] != "NBA Team" else 1.00
        
        pts_proj = fila['PTS Base'] * f_usage
        triples_proj = fila['3PT Base'] * f_usage

        prob_pts = calcular_poisson_over(pts_proj, 19.5)
        prob_3pt = calcular_poisson_over(triples_proj, 1.5)

        colchon_pts = pts_proj - 19.5
        descanso_str = "🚀 USAGE (+15%)" if f_usage > 1.0 else "🟢 NORMAL"

        procesados.append({
            'Jugador': j_nombre,
            'Equipo': fila['Equipo'],
            'Minutos L10': fila['Minutos L10'],
            'PTS Proyectados': round(pts_proj, 1),
            'Colchón PTS (>19.5)': round(colchon_pts, 1),
            'Estado Carga': descanso_str,
            'Estabilidad': fila['Estabilidad'],
            'Prob >19.5 PTS (%)': round(prob_pts * 100, 1),
            'Triples Prom': fila['3PT Base'],
            '3PA (Intentos)': fila['3PA (Intentos)'],
            'Prob >1.5 Triples (%)': round(prob_3pt * 100, 1),
            'PRA Promedios': fila['PRA Base'],
            'Varianza (std)': fila['Varianza (std)']
        })

    df_data = pd.DataFrame(procesados)

    col1, col2, col3 = st.columns(3)
    col1.metric("Jugadores Monitoreados", f"{len(df_data)}")
    top_pick = df_data.sort_values(by='Prob >19.5 PTS (%)', ascending=False).iloc[0]
    col2.metric("Top Pick Anotación", f"{top_pick['Jugador']}", f"{top_pick['Prob >19.5 PTS (%)']}% Prob")
    top_3pt = df_data.sort_values(by='Prob >1.5 Triples (%)', ascending=False).iloc[0]
    col3.metric("Top Pick Triples", f"{top_3pt['Jugador']}", f"{top_3pt['Prob >1.5 Triples (%)']}% Prob")

    st.markdown("---")

    df_filtrado = df_data[df_data['Minutos L10'] >= min_minutos]
    if solo_alta_estabilidad:
        df_filtrado = df_filtrado[df_filtrado['Estabilidad'] == "⭐ ALTA"]
    if filtro_volumen_3pt:
        df_filtrado = df_filtrado[df_filtrado['3PA (Intentos)'] >= 5.5]

    st.subheader("📊 Ranking de Valor Esperado (+EV) — Actualización Automatizada")
    criterio_orden = st.radio("Ordenar por:", ["Puntos (>19.5 PTS)", "Triples (>1.5 3PT)", "PRA (Combo)"], horizontal=True)

    if criterio_orden == "Puntos (>19.5 PTS)":
        df_mostrar = df_filtrado.sort_values(by='Prob >19.5 PTS (%)', ascending=False)
    elif criterio_orden == "Triples (>1.5 3PT)":
        df_mostrar = df_filtrado.sort_values(by='Prob >1.5 Triples (%)', ascending=False)
    else:
        df_mostrar = df_filtrado.sort_values(by='PRA Promedios', ascending=False)

    st.dataframe(
        df_mostrar,
        column_config={
            "Prob >19.5 PTS (%)": st.column_config.ProgressColumn("Prob >19.5 PTS", format="%.1f%%", min_value=0, max_value=100),
            "Prob >1.5 Triples (%)": st.column_config.ProgressColumn("Prob >1.5 Triples", format="%.1f%%", min_value=0, max_value=100),
        },
        use_container_width=True,
        hide_index=True
    )

    # --- SIMULADOR MANUAL INTERACTIVO ---
    st.markdown("---")
    st.subheader("🧮 Simulador de Combinada Manual (+EV)")
    st.caption("Selecciona los logros e ingresa las cuotas reales de Rushbet para auditar el boleto.")

    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        j1 = st.selectbox("Selección 1 (Jugador)", df_mostrar['Jugador'].tolist(), index=0)
        c1 = st.number_input(f"Cuota Rushbet ({j1[:8]}...)", min_value=1.01, value=1.40, step=0.05)
    with col_c2:
        j2 = st.selectbox("Selección 2 (Jugador)", df_mostrar['Jugador'].tolist(), index=min(1, len(df_mostrar)-1))
        c2 = st.number_input(f"Cuota Rushbet ({j2[:8]}...)", min_value=1.01, value=1.45, step=0.05)
    with col_c3:
        j3 = st.selectbox("Selección 3 (Jugador - Opcional)", ["-- Ninguno --"] + df_mostrar['Jugador'].tolist(), index=0)
        c3 = st.number_input("Cuota Rushbet (Tercer Logro)", min_value=1.01, value=1.30, step=0.05) if j3 != "-- Ninguno --" else 1.0

    p1 = df_mostrar[df_mostrar['Jugador'] == j1]['Prob >19.5 PTS (%)'].values[0] / 100
    p2 = df_mostrar[df_mostrar['Jugador'] == j2]['Prob >1.5 Triples (%)'].values[0] / 100
    p3 = (df_mostrar[df_mostrar['Jugador'] == j3]['Prob >19.5 PTS (%)'].values[0] / 100) if j3 != "-- Ninguno --" else 1.0

    cuota_total = c1 * c2 * c3
    prob_real = p1 * p2 * p3
    prob_rushbet = 1 / cuota_total
    ev_margin = (prob_real - prob_rushbet) * 100

    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric("Cuota Combinada Real", f"@{cuota_total:.2f}")
    col_res2.metric("Probabilidad Real Acumulada", f"{prob_real*100:.1f}%")
    col_res3.metric("Ventaja Matemática REAL (+EV)", f"{ev_margin:+.1f}%", delta_color="normal" if ev_margin > 0 else "inverse")

    csv = df_mostrar.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Reporte Filtrado (CSV)",
        data=csv,
        file_name=f"reporte_yz_quant_{fecha_str}.csv",
        mime="text/csv"
    )


