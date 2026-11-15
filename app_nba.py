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
    initial_sidebar_state="expanded"
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

def calcular_normal_over(promedio: float, std: float, linea: float) -> float:
    std_safe = max(float(std), 2.5)
    z = (linea - promedio) / (std_safe * math.sqrt(2.0))
    prob_acumulada = 0.5 * (1.0 + math.erf(z))
    return max(0.0, min(1.0, 1.0 - prob_acumulada))

def obtener_ultima_actualizacion_github():
    url_commits = "https://api.github.com/repos/yamidbadran0528-cpu/yz-quant-nba/commits?path=datos_nba_hoy.json&page=1&per_page=1"
    try:
        r = requests.get(url_commits, timeout=4)
        if r.status_code == 200 and r.json():
            fecha_iso = r.json()[0]["commit"]["committer"]["date"]
            dt_utc = datetime.datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
            dt_cot = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
            return dt_cot.strftime("%Y-%m-%d"), dt_cot.strftime("%Y-%m-%d %I:%M %p COT")
    except Exception:
        pass
    return None, "Desconocida"

def cargar_datos_automatizados():
    ts = int(time.time())
    url_raw = f"https://raw.githubusercontent.com/yamidbadran0528-cpu/yz-quant-nba/main/datos_nba_hoy.json?t={ts}"
    headers = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    try:
        res = requests.get(url_raw, headers=headers, timeout=5)
        if res.status_code == 200:
            datos = res.json()
            if isinstance(datos, list) and len(datos) > 0:
                return pd.DataFrame(datos), "🟢 Sincronizado en vivo desde GitHub"
    except Exception:
        pass
        
    try:
        with open("datos_nba_hoy.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
            if isinstance(datos, list) and len(datos) > 0:
                return pd.DataFrame(datos), "🟡 Cargado desde almacenamiento local"
    except Exception:
        pass

    return pd.DataFrame(), "⚠️ Esperando sincronización del Workflow"

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

if st.sidebar.button("🔄 Recargar Datos de Hoy", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

linea_evaluada_pts = st.sidebar.selectbox(
    "Línea Puntos (Pisos Rushbet 2 en 2)",
    [15.5, 17.5, 19.5, 21.5, 23.5, 25.5],
    index=2,
    format_func=lambda x: f">{x} PTS ({int(x + 0.5)}+)"
)

linea_evaluada_pra = st.sidebar.selectbox(
    "Línea PRA (Pisos Rushbet 5 en 5)",
    [29.5, 34.5, 39.5],
    index=1,
    format_func=lambda x: f">{x} PRA ({int(x + 0.5)}+)"
)

min_minutos = st.sidebar.slider("Minutos Mínimos Promedio", 15, 36, 20)
solo_alta_estabilidad = st.sidebar.checkbox("Mostrar solo estabilidad ⭐ ALTA", False)
filtro_volumen_3pt = st.sidebar.checkbox("Filtrar tiradores con al menos 5.5 intentos (3PA)", False)

# --- CABECERA PRINCIPAL ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_cot = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_hoy_str = now_cot.strftime('%Y-%m-%d')

df_raw, estado_conexion = cargar_datos_automatizados()
fecha_commit_dia, fecha_commit_full = obtener_ultima_actualizacion_github()
fecha_archivo = fecha_commit_dia if fecha_commit_dia else fecha_hoy_str

st.caption(f"{estado_conexion} | Última actualización de datos: {fecha_commit_full} | Hoy: {fecha_hoy_str}")

if fecha_commit_dia and fecha_commit_dia != fecha_hoy_str:
    st.warning(
        f"⚠️ Atención: Los datos cargados corresponden al **{fecha_commit_dia}** "
        f"(el Workflow automático de hoy **{fecha_hoy_str}** aún no ha corrido o sigue en cola en GitHub Actions)."
    )

if df_raw.empty:
    st.warning("⚠️ El Workflow de GitHub Actions está extrayendo la cartelera oficial de hoy. Ejecuta 'Run workflow' en Actions.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.header("🚑 Reporte de Bajas / Lesiones")
bajas_confirmadas = st.sidebar.multiselect(
    "Selecciona los jugadores descartados (OUT):",
    options=df_raw['Jugador'].tolist() if 'Jugador' in df_raw.columns else []
)

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
    pra_proj = fila['PRA Base'] * f_usage
    std_val = float(fila['Varianza (std)'])

    prob_pts = calcular_normal_over(pts_proj, std_val, linea_evaluada_pts)
    prob_3pt = calcular_poisson_over(triples_proj, 1.5)
    prob_pra = calcular_normal_over(pra_proj, std_val, linea_evaluada_pra)

    colchon_pts = pts_proj - linea_evaluada_pts
    descanso_str = "🚀 USAGE (+15%)" if f_usage > 1.0 else "🟢 NORMAL"

    procesados.append({
        'Jugador': j_nombre,
        'Equipo': fila['Equipo'],
        'Rival (Hoy)': fila.get('Rival', 'N/A'),
        'Factor Defensivo': f"{fila.get('Factor Defensivo', 1.0):.2f}x",
        'Minutos L10': fila['Minutos L10'],
        'PTS Proyectados': round(pts_proj, 1),
        f'Colchón PTS (>{linea_evaluada_pts})': round(colchon_pts, 1),
        'Estado Carga': descanso_str,
        'Estabilidad': fila['Estabilidad'],
        f'Prob >{linea_evaluada_pts} PTS (%)': round(prob_pts * 100, 1),
        'Triples Prom': round(triples_proj, 1),
        '3PA (Intentos)': fila['3PA (Intentos)'],
        'Prob >1.5 Triples (%)': round(prob_3pt * 100, 1),
        'PRA Promedios': round(pra_proj, 1),
        f'Prob >{linea_evaluada_pra} PRA (%)': round(prob_pra * 100, 1),
        'Varianza (std)': std_val
    })

df_data = pd.DataFrame(procesados)

col1, col2, col3 = st.columns(3)
col1.metric("Jugadores Monitoreados", f"{len(df_data)}")
top_pick = df_data.sort_values(by=f'Prob >{linea_evaluada_pts} PTS (%)', ascending=False).iloc[0]
col2.metric(f"Top Anotación (>{linea_evaluada_pts})", f"{top_pick['Jugador']}", f"{top_pick[f'Prob >{linea_evaluada_pts} PTS (%)']}% Prob (Normal)")
top_3pt = df_data.sort_values(by='Prob >1.5 Triples (%)', ascending=False).iloc[0]
col3.metric("Top Triples (>1.5 3PT)", f"{top_3pt['Jugador']}", f"{top_3pt['Prob >1.5 Triples (%)']}% Prob (Poisson)")

st.markdown("---")

df_filtrado = df_data[df_data['Minutos L10'] >= min_minutos]
if solo_alta_estabilidad:
    df_filtrado = df_filtrado[df_filtrado['Estabilidad'] == "⭐ ALTA"]
if filtro_volumen_3pt:
    df_filtrado = df_filtrado[df_filtrado['3PA (Intentos)'] >= 5.5]

st.subheader("📊 Ranking de Valor Esperado Calibrado (+EV)")
criterio_orden = st.radio(
    "Ordenar por:",
    [f"Puntos (>{linea_evaluada_pts} PTS)", "Triples (>1.5 3PT)", f"PRA (>{linea_evaluada_pra} PRA)"],
    horizontal=True
)

if criterio_orden == f"Puntos (>{linea_evaluada_pts} PTS)":
    df_mostrar = df_filtrado.sort_values(by=f'Prob >{linea_evaluada_pts} PTS (%)', ascending=False)
elif criterio_orden == "Triples (>1.5 3PT)":
    df_mostrar = df_filtrado.sort_values(by='Prob >1.5 Triples (%)', ascending=False)
else:
    df_mostrar = df_filtrado.sort_values(by=f'Prob >{linea_evaluada_pra} PRA (%)', ascending=False)

st.dataframe(
    df_mostrar,
    column_config={
        f"Prob >{linea_evaluada_pts} PTS (%)": st.column_config.ProgressColumn(f"Prob >{linea_evaluada_pts} PTS", format="%.1f%%", min_value=0, max_value=100),
        "Prob >1.5 Triples (%)": st.column_config.ProgressColumn("Prob >1.5 Triples", format="%.1f%%", min_value=0, max_value=100),
        f"Prob >{linea_evaluada_pra} PRA (%)": st.column_config.ProgressColumn(f"Prob >{linea_evaluada_pra} PRA", format="%.1f%%", min_value=0, max_value=100),
    },
    use_container_width=True,
    hide_index=True
)

# --- SIMULADOR MANUAL INTERACTIVO ---
st.markdown("---")
st.subheader("🧮 Simulador de Combinada Manual (+EV)")
st.caption("Selecciona jugador, mercado y cuota real de Rushbet para auditar el boleto.")

opciones_mercado = [
    f"Puntos (>{linea_evaluada_pts})",
    "Triples (>1.5)",
    f"PRA (>{linea_evaluada_pra})"
]

def obtener_prob_seleccion(df_ref, jugador, mercado):
    fila_j = df_ref[df_ref['Jugador'] == jugador].iloc[0]
    if mercado.startswith("Puntos"):
        return fila_j[f'Prob >{linea_evaluada_pts} PTS (%)'] / 100.0
    elif mercado.startswith("Triples"):
        return fila_j['Prob >1.5 Triples (%)'] / 100.0
    else:
        return fila_j[f'Prob >{linea_evaluada_pra} PRA (%)'] / 100.0

jugadores_lista = df_mostrar['Jugador'].tolist()

col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    j1 = st.selectbox("Selección 1 (Jugador)", jugadores_lista, index=0)
    m1 = st.selectbox("Mercado 1", opciones_mercado, index=0)
    c1 = st.number_input(f"Cuota Rushbet ({j1[:10]}...)", min_value=1.01, value=1.28, step=0.01)
with col_c2:
    j2 = st.selectbox("Selección 2 (Jugador)", jugadores_lista, index=min(1, len(jugadores_lista)-1))
    m2 = st.selectbox("Mercado 2", opciones_mercado, index=0)
    c2 = st.number_input(f"Cuota Rushbet ({j2[:10]}...)", min_value=1.01, value=1.28, step=0.01)
with col_c3:
    j3 = st.selectbox("Selección 3 (Jugador - Opcional)", ["-- Ninguno --"] + jugadores_lista, index=min(2, len(jugadores_lista)))
    m3 = st.selectbox("Mercado 3", opciones_mercado, index=0) if j3 != "-- Ninguno --" else ""
    c3 = st.number_input("Cuota Rushbet (Tercer Logro)", min_value=1.01, value=1.28, step=0.01) if j3 != "-- Ninguno --" else 1.0

p1 = obtener_prob_seleccion(df_mostrar, j1, m1)
p2 = obtener_prob_seleccion(df_mostrar, j2, m2)
p3 = obtener_prob_seleccion(df_mostrar, j3, m3) if j3 != "-- Ninguno --" else 1.0

cuota_total = c1 * c2 * c3
prob_real = p1 * p2 * p3
prob_rushbet = 1.0 / cuota_total
ev_margin = (prob_real - prob_rushbet) * 100

col_res1, col_res2, col_res3 = st.columns(3)
col_res1.metric("Cuota Combinada Real", f"@{cuota_total:.2f}")
col_res2.metric("Probabilidad Calibrada Acumulada", f"{prob_real*100:.1f}%")
col_res3.metric("Ventaja Matemática REAL (+EV)", f"{ev_margin:+.1f}%", delta_color="normal" if ev_margin > 0 else "inverse")

# --- BOTÓN DE DESCARGA CSV NATIVO AL FINAL ---
st.markdown("---")
st.subheader("📥 Exportar Datos de la Jornada")
st.caption("Descarga toda la tabla procesada en archivo CSV compatible con Excel para auditar o enviar las selecciones.")

csv_datos = df_mostrar.to_csv(index=False).encode('utf-8')

st.download_button(
    label="🟢 Descargar Archivo CSV para Excel",
    data=csv_datos,
    file_name=f"YZ_Quant_NBA_{fecha_archivo}.csv",
    mime="text/csv",
    use_container_width=True
)
