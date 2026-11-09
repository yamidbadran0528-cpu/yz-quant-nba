import math
import datetime
import requests
import pandas as pd
import streamlit as st
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

st.set_page_config(
    page_title="YZ Quant NBA — Platform (+EV)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
}

# Base de datos cuantitativa de promedios (Los equipos se asignan de forma dinámica en vivo)
BENCHMARKS_JUGADORES = {
    "Victor Wembanyama": {"pts": 29.1, "3pt": 1.9, "min": 30.3, "std": 12.5, "reb": 10.2, "ast": 4.8, "b2b": False},
    "De'Aaron Fox": {"pts": 24.2, "3pt": 1.9, "min": 35.1, "std": 6.8, "reb": 4.1, "ast": 6.2, "b2b": False},
    "Ty Jerome": {"pts": 10.5, "3pt": 1.4, "min": 21.2, "std": 4.1, "reb": 2.2, "ast": 3.4, "b2b": False},
    "Cade Cunningham": {"pts": 22.9, "3pt": 2.1, "min": 34.0, "std": 6.4, "reb": 6.1, "ast": 7.0, "b2b": False},
    "Scottie Barnes": {"pts": 23.5, "3pt": 0.5, "min": 33.4, "std": 11.8, "reb": 7.5, "ast": 5.2, "b2b": False},
    "Zion Williamson": {"pts": 21.0, "3pt": 0.1, "min": 33.1, "std": 4.4, "reb": 5.2, "ast": 2.8, "b2b": False},
    "Jalen Johnson": {"pts": 19.8, "3pt": 1.0, "min": 33.1, "std": 6.1, "reb": 9.8, "ast": 6.5, "b2b": False},
    "Evan Mobley": {"pts": 18.4, "3pt": 0.6, "min": 32.8, "std": 5.0, "reb": 8.5, "ast": 3.3, "b2b": False},
    "Trae Young": {"pts": 18.4, "3pt": 1.8, "min": 35.1, "std": 6.1, "reb": 3.1, "ast": 9.2, "b2b": False},
    "Andrew Nembhard": {"pts": 17.8, "3pt": 2.5, "min": 33.1, "std": 4.7, "reb": 3.2, "ast": 5.8, "b2b": False},
    "Immanuel Quickley": {"pts": 17.4, "3pt": 2.4, "min": 31.8, "std": 5.2, "reb": 3.8, "ast": 5.1, "b2b": False},
    "Jayson Tatum": {"pts": 26.4, "3pt": 2.8, "min": 31.8, "std": 6.6, "reb": 5.8, "ast": 7.6, "b2b": False},
    "Stephen Curry": {"pts": 25.2, "3pt": 4.2, "min": 32.0, "std": 5.8, "reb": 4.5, "ast": 6.1, "b2b": False},
    "Shai Gilgeous-Alexander": {"pts": 28.5, "3pt": 1.8, "min": 34.2, "std": 5.1, "reb": 5.5, "ast": 6.2, "b2b": False},
    "Giannis Antetokounmpo": {"pts": 29.8, "3pt": 0.4, "min": 33.8, "std": 6.2, "reb": 11.5, "ast": 5.8, "b2b": False},
    "Michael Porter Jr.": {"pts": 18.2, "3pt": 2.7, "min": 31.5, "std": 5.5, "reb": 7.0, "ast": 1.5, "b2b": False},
}

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

@st.cache_data(ttl=1800)
def obtener_rosters_espn_dinamicos(fecha_str: str):
    """Obtiene partidos del día y rastrea qué equipo pertenece a cada jugador en tiempo real."""
    fecha_clean = fecha_str.replace('-', '')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_clean}"
    mapa_jugador_equipo = {}
    juegos = []
    equipos = []
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        data = res.json()
        events = data.get('events', [])
        
        for ev in events:
            comp = ev.get('competitions', [])[0]
            competitors = comp.get('competitors', [])
            juegos.append(ev.get('name', ''))
            
            for c in competitors:
                team_name = c.get('team', {}).get('displayName', '')
                equipos.append(team_name)
                
                # Extraer atletas del equipo si vienen en la respuesta
                athletes = c.get('leaders', [])
                for leader in athletes:
                    for l_item in leader.get('leaders', []):
                        athlete_name = l_item.get('athlete', {}).get('displayName', '')
                        if athlete_name:
                            mapa_jugador_equipo[athlete_name] = team_name
                            
        return juegos, equipos, mapa_jugador_equipo
    except Exception:
        return [], [], {}

@st.cache_data(ttl=1800)
def cargar_datos_jornada(fecha_str: str, temporada='2026-27'):
    juegos, equipos_nombres, mapa_equipos_espn = obtener_rosters_espn_dinamicos(fecha_str)
    
    n_juegos_total = len(juegos) if juegos else 8
    n_equipos_total = len(equipos_nombres) if equipos_nombres else 16
    jugadores_a_analizar = list(BENCHMARKS_JUGADORES.keys())

    resultados = []
    for nombre in jugadores_a_analizar:
        prom_pts, prom_3pt, prom_min, std_pts, prom_pra, es_b2b, equipo_real = None, None, None, None, None, False, "NBA Team"
        
        # 1. Mapeo dinámico del equipo desde ESPN o NBA API
        if nombre in mapa_equipos_espn:
            equipo_real = mapa_equipos_espn[nombre]
            
        try:
            nba_players = players.get_players()
            coincidencias = [p for p in nba_players if p['full_name'].lower() == nombre.lower()]
            if coincidencias:
                player_id = coincidencias[0]['id']
                gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=temporada, headers=HEADERS, timeout=5)
                df = gamelog.get_data_frames()[0]
                if not df.empty and len(df) >= 5:
                    df_l10 = df.head(10).copy()
                    df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
                    df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
                    df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
                    df_l10['REB'] = pd.to_numeric(df_l10['REB'])
                    df_l10['AST'] = pd.to_numeric(df_l10['AST'])
                    
                    prom_pts = df_l10['PTS'].mean()
                    prom_3pt = df_l10['FG3M'].mean()
                    prom_min = df_l10['MIN'].mean()
                    std_pts = df_l10['PTS'].std()
                    prom_pra = (df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean()

                    # Si el equipo no venía de ESPN, tomar el código del último partido en vivo
                    if equipo_real == "NBA Team" and 'MATCHUP' in df.columns:
                        matchup = df.iloc[0]['MATCHUP']
                        equipo_real = matchup.split(' ')[0] # Ej: "CLE vs. MEM" -> "CLE"

                    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], format='%b %d, %Y', errors='coerce')
                    fecha_hoy_dt = pd.to_datetime(fecha_str)
                    fechas_previas = df[df['GAME_DATE'] < fecha_hoy_dt]['GAME_DATE']
                    if not fechas_previas.empty:
                        dias_descanso = (fecha_hoy_dt - fechas_previas.max()).days
                        es_b2b = (dias_descanso == 1)
        except Exception:
            pass

        if prom_pts is None:
            bm = BENCHMARKS_JUGADORES.get(nombre, {"pts": 18.5, "3pt": 1.5, "min": 30.0, "std": 5.5, "reb": 4.5, "ast": 4.0, "b2b": False})
            prom_pts = bm["pts"]
            prom_3pt = bm["3pt"]
            prom_min = bm["min"]
            std_pts = bm["std"]
            prom_pra = bm["pts"] + bm["reb"] + bm["ast"]
            es_b2b = bm.get("b2b", False)

        resultados.append({
            'Jugador': nombre,
            'Equipo': equipo_real,
            'Minutos L10': round(prom_min, 1),
            'PTS Base': round(prom_pts, 1),
            '3PT Base': round(prom_3pt, 1),
            'es_b2b': es_b2b,
            'Estabilidad': "⭐ ALTA" if std_pts <= 6.5 else "ESTÁNDAR",
            'PRA Base': round(prom_pra, 1),
            'Varianza (std)': round(std_pts, 1)
        })

    df_res = pd.DataFrame(resultados).drop_duplicates(subset=['Jugador'])
    return df_res, n_juegos_total, n_equipos_total

# --- CABECERA ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")
st.caption("Motor cuantitativo con asignación dinámica de equipos en vivo")

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_defecto = now_et.date()

fecha_seleccionada = st.sidebar.date_input("Fecha de Jornada NBA", value=fecha_defecto)
fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

with st.spinner(f"⚡ Escaneando plantillas y proyecciones ({fecha_str})..."):
    df_raw, n_juegos, n_equipos = cargar_datos_jornada(fecha_str)

st.sidebar.markdown("---")
st.sidebar.header("🚑 Reporte de Bajas / Lesiones")
bajas_confirmadas = st.sidebar.multiselect(
    "Selecciona los jugadores descartados (OUT):",
    options=df_raw['Jugador'].tolist() if not df_raw.empty else []
)

if st.sidebar.button("🔄 Escanear Jornada en Vivo", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

min_minutos = st.sidebar.slider("Minutos Mínimos Promedio", 15, 36, 25)
solo_alta_estabilidad = st.sidebar.checkbox("Mostrar solo estabilidad ⭐ ALTA", False)

if df_raw.empty:
    st.warning("⚠️ No se pudieron cargar los partidos.")
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
            
        f_fatiga = 0.94 if fila['es_b2b'] else 1.00
        f_usage = 1.15 if fila['Equipo'] in equipos_con_baja and fila['Equipo'] != "NBA Team" else 1.00
        
        pts_proj = fila['PTS Base'] * f_fatiga * f_usage
        triples_proj = fila['3PT Base'] * f_fatiga * f_usage

        prob_pts = calcular_poisson_over(pts_proj, 19.5)
        prob_3pt = calcular_poisson_over(triples_proj, 1.5)

        descanso_str = "⚠️ B2B (-6%)" if fila['es_b2b'] else ("🚀 USAGE (+15%)" if f_usage > 1.0 else "🟢 NORMAL")

        procesados.append({
            'Jugador': j_nombre,
            'Equipo': fila['Equipo'],
            'Minutos L10': fila['Minutos L10'],
            'PTS Prom': fila['PTS Base'],
            'PTS Proyectados': round(pts_proj, 1),
            'Estado Carga': descanso_str,
            'Estabilidad': fila['Estabilidad'],
            'Prob >19.5 PTS (%)': round(prob_pts * 100, 1),
            'Triples Prom': fila['3PT Base'],
            'Prob >1.5 Triples (%)': round(prob_3pt * 100, 1),
            'PRA Promedio': fila['PRA Base'],
            'Varianza (std)': fila['Varianza (std)']
        })

    df_data = pd.DataFrame(procesados)

    # --- MÉTRICAS GENERALES ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Partidos Hoy", f"{n_juegos}")
    col2.metric("Equipos en Cancha", f"{n_equipos}")
    col3.metric("Jugadores Escaneados", f"{len(df_data)}")
    top_pick = df_data.sort_values(by='Prob >19.5 PTS (%)', ascending=False).iloc[0]
    col4.metric("Top Pick Anotación", f"{top_pick['Jugador']}", f"{top_pick['Prob >19.5 PTS (%)']}% Prob")

    st.markdown("---")

    df_filtrado = df_data[df_data['Minutos L10'] >= min_minutos]
    if solo_alta_estabilidad:
        df_filtrado = df_filtrado[df_filtrado['Estabilidad'] == "⭐ ALTA"]

    st.subheader("📊 Ranking de Valor Esperado (+EV)")
    criterio_orden = st.radio("Ordenar por:", ["Puntos (>19.5 PTS)", "Triples (>1.5 3PT)", "PRA (Combo)"], horizontal=True)
    
    if criterio_orden == "Puntos (>19.5 PTS)":
        df_mostrar = df_filtrado.sort_values(by='Prob >19.5 PTS (%)', ascending=False)
    elif criterio_orden == "Triples (>1.5 3PT)":
        df_mostrar = df_filtrado.sort_values(by='Prob >1.5 Triples (%)', ascending=False)
    else:
        df_mostrar = df_filtrado.sort_values(by='PRA Promedio', ascending=False)

    st.dataframe(
        df_mostrar,
        column_config={
            "Prob >19.5 PTS (%)": st.column_config.ProgressColumn("Prob >19.5 PTS", format="%.1f%%", min_value=0, max_value=100),
            "Prob >1.5 Triples (%)": st.column_config.ProgressColumn("Prob >1.5 Triples", format="%.1f%%", min_value=0, max_value=100),
        },
        use_container_width=True,
        hide_index=True
    )

    # --- SIMULADOR MANUAL ---
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
