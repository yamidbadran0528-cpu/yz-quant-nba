import math
import json
import time
import requests
import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="YZ Quant NBA — Platform (+EV)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_JUGADORES_BACKUP = [
    {"Jugador": "Victor Wembanyama", "Equipo": "San Antonio Spurs", "Minutos L10": 30.3, "PTS Base": 29.1, "3PT Base": 1.9, "3PA (Intentos)": 6.8, "Estabilidad": "⭐ ALTA", "PRA Base": 44.1, "Varianza (std)": 12.5},
    {"Jugador": "De'Aaron Fox", "Equipo": "San Antonio Spurs", "Minutos L10": 35.1, "PTS Base": 24.2, "3PT Base": 1.9, "3PA (Intentos)": 6.1, "Estabilidad": "ESTÁNDAR", "PRA Base": 34.5, "Varianza (std)": 6.8},
    {"Jugador": "Giannis Antetokounmpo", "Equipo": "Miami Heat", "Minutos L10": 33.8, "PTS Base": 29.8, "3PT Base": 0.4, "3PA (Intentos)": 1.1, "Estabilidad": "⭐ ALTA", "PRA Base": 47.1, "Varianza (std)": 6.2},
    {"Jugador": "Stephen Curry", "Equipo": "Golden State Warriors", "Minutos L10": 32.0, "PTS Base": 25.2, "3PT Base": 4.2, "3PA (Intentos)": 10.5, "Estabilidad": "⭐ ALTA", "PRA Base": 35.8, "Varianza (std)": 5.8},
    {"Jugador": "Shai Gilgeous-Alexander", "Equipo": "Oklahoma City Thunder", "Minutos L10": 34.2, "PTS Base": 28.5, "3PT Base": 1.8, "3PA (Intentos)": 5.2, "Estabilidad": "⭐ ALTA", "PRA Base": 40.2, "Varianza (std)": 5.1},
    {"Jugador": "Jayson Tatum", "Equipo": "Boston Celtics", "Minutos L10": 31.8, "PTS Base": 26.4, "3PT Base": 2.8, "3PA (Intentos)": 8.2, "Estabilidad": "ESTÁNDAR", "PRA Base": 39.8, "Varianza (std)": 6.6},
    {"Jugador": "Cade Cunningham", "Equipo": "Detroit Pistons", "Minutos L10": 34.0, "PTS Base": 22.9, "3PT Base": 2.1, "3PA (Intentos)": 6.2, "Estabilidad": "⭐ ALTA", "PRA Base": 36.0, "Varianza (std)": 6.4},
    {"Jugador": "Ty Jerome", "Equipo": "Memphis Grizzlies", "Minutos L10": 28.5, "PTS Base": 18.6, "3PT Base": 2.4, "3PA (Intentos)": 5.5, "Estabilidad": "⭐ ALTA", "PRA Base": 26.2, "Varianza (std)": 4.1},
    {"Jugador": "Andrew Nembhard", "Equipo": "Indiana Pacers", "Minutos L10": 33.1, "PTS Base": 17.8, "3PT Base": 2.5, "3PA (Intentos)": 5.8, "Estabilidad": "⭐ ALTA", "PRA Base": 26.8, "Varianza (std)": 4.7},
    {"Jugador": "Immanuel Quickley", "Equipo": "Toronto Raptors", "Minutos L10": 31.8, "PTS Base": 17.4, "3PT Base": 2.4, "3PA (Intentos)": 6.9, "Estabilidad": "⭐ ALTA", "PRA Base": 26.3, "Varianza (std)": 5.2},
    {"Jugador": "Nikola Jokic", "Equipo": "Denver Nuggets", "Minutos L10": 36.8, "PTS Base": 29.5, "3PT Base": 1.5, "3PA (Intentos)": 4.2, "Estabilidad": "⭐ ALTA", "PRA Base": 52.4, "Varianza (std)": 6.1},
]

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

def cargar_datos_automatizados():
    ts = int(time.time())
    url_raw = f"https://raw.githubusercontent.com/yamidbadran0528-cpu/yz-quant-nba/main/datos_nba_hoy.json?v={ts}"
    try:
        res = requests.get(url_raw, timeout=5)
        if res.status_code == 200:
            datos = res.json()
            if datos and len(datos) > 0:
                return pd.DataFrame(datos), "🟢 Datos sincronizados en vivo desde GitHub"
    except Exception:
        pass
    try:
        with open("datos_nba_hoy.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
            if datos and len(datos) > 0:
                return pd.DataFrame(datos), "🟡 Datos cargados localmente"
    except Exception:
        pass
    return pd.DataFrame(BASE_JUGADORES_BACKUP), "⚡ Datos cargados desde matriz de respaldo"

# --- CABECERA ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_str = now_et.strftime('%Y-%m-%d')

df_raw, estado_conexion = cargar_datos_automatizados()
st.caption(f"{estado_conexion} | Fecha de consulta: {fecha_str}")

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

linea_evaluada_pts = st.sidebar.selectbox("Línea Base Puntos (PTS)", [19.5, 24.5, 27.5], index=0)

if st.sidebar.button("🔄 Recargar Datos de Hoy", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚑 Reporte de Bajas / Lesiones")
bajas_confirmadas = st.sidebar.multiselect(
    "Selecciona los jugadores descartados (OUT):",
    options=df_raw['Jugador'].tolist() if not df_raw.empty else []
)

min_minutos = st.sidebar.slider("Minutos Mínimos Promedio", 15, 36, 22)
solo_alta_estabilidad = st.sidebar.checkbox("Mostrar solo estabilidad ⭐ ALTA", False)
filtro_volumen_3pt = st.sidebar.checkbox("Filtrar tiradores con al menos 5.5 intentos (3PA)", False)

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

    prob_pts = calcular_poisson_over(pts_proj, linea_evaluada_pts)
    prob_3pt = calcular_poisson_over(triples_proj, 1.5)

    colchon_pts = pts_proj - linea_evaluada_pts
    descanso_str = "🚀 USAGE (+15%)" if f_usage > 1.0 else "🟢 NORMAL"

    procesados.append({
        'Jugador': j_nombre,
        'Equipo': fila['Equipo'],
        'Minutos L10': fila['Minutos L10'],
        'PTS Proyectados': round(pts_proj, 1),
        f'Colchón PTS (>{linea_evaluada_pts})': round(colchon_pts, 1),
        'Estado Carga': descanso_str,
        'Estabilidad': fila['Estabilidad'],
        f'Prob >{linea_evaluada_pts} PTS (%)': round(prob_pts * 100, 1),
        'Triples Prom': fila['3PT Base'],
        '3PA (Intentos)': fila['3PA (Intentos)'],
        'Prob >1.5 Triples (%)': round(prob_3pt * 100, 1),
        'PRA Promedios': fila['PRA Base'],
        'Varianza (std)': fila['Varianza (std)']
    })

df_data = pd.DataFrame(procesados)

col1, col2, col3 = st.columns(3)
col1.metric("Jugadores Monitoreados", f"{len(df_data)}")
top_pick = df_data.sort_values(by=f'Prob >{linea_evaluada_pts} PTS (%)', ascending=False).iloc[0]
col2.metric("Top Pick Anotación", f"{top_pick['Jugador']}", f"{top_pick[f'Prob >{linea_evaluada_pts} PTS (%)']}% Prob")
top_3pt = df_data.sort_values(by='Prob >1.5 Triples (%)', ascending=False).iloc[0]
col3.metric("Top Pick Triples", f"{top_3pt['Jugador']}", f"{top_3pt['Prob >1.5 Triples (%)']}% Prob")

st.markdown("---")

df_filtrado = df_data[df_data['Minutos L10'] >= min_minutos]
if solo_alta_estabilidad:
    df_filtrado = df_filtrado[df_filtrado['Estabilidad'] == "⭐ ALTA"]
if filtro_volumen_3pt:
    df_filtrado = df_filtrado[df_filtrado['3PA (Intentos)'] >= 5.5]

st.subheader("📊 Ranking de Valor Esperado (+EV)")
criterio_orden = st.radio("Ordenar por:", [f"Puntos (>{linea_evaluada_pts} PTS)", "Triples (>1.5 3PT)", "PRA (Combo)"], horizontal=True)

if criterio_orden == f"Puntos (>{linea_evaluada_pts} PTS)":
    df_mostrar = df_filtrado.sort_values(by=f'Prob >{linea_evaluada_pts} PTS (%)', ascending=False)
elif criterio_orden == "Triples (>1.5 3PT)":
    df_mostrar = df_filtrado.sort_values(by='Prob >1.5 Triples (%)', ascending=False)
else:
    df_mostrar = df_filtrado.sort_values(by='PRA Promedios', ascending=False)

st.dataframe(
    df_mostrar,
    column_config={
        f"Prob >{linea_evaluada_pts} PTS (%)": st.column_config.ProgressColumn(f"Prob >{linea_evaluada_pts} PTS", format="%.1f%%", min_value=0, max_value=100),
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

p1 = df_mostrar[df_mostrar['Jugador'] == j1][f'Prob >{linea_evaluada_pts} PTS (%)'].values[0] / 100
p2 = df_mostrar[df_mostrar['Jugador'] == j2]['Prob >1.5 Triples (%)'].values[0] / 100
p3 = (df_mostrar[df_mostrar['Jugador'] == j3][f'Prob >{linea_evaluada_pts} PTS (%)'].values[0] / 100) if j3 != "-- Ninguno --" else 1.0

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
