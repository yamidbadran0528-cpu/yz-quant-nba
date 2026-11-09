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

PLANTILLAS_EQUIPOS = {
    "San Antonio Spurs": ["Victor Wembanyama", "De'Aaron Fox", "Stephon Castle", "Devin Vassell"],
    "Detroit Pistons": ["Cade Cunningham", "Jaden Ivey", "Tobias Harris", "Jalen Duren"],
    "Cleveland Cavaliers": ["Donovan Mitchell", "Darius Garland", "Evan Mobley", "Ty Jerome"],
    "Indiana Pacers": ["Tyrese Haliburton", "Pascal Siakam", "Andrew Nembhard", "Myles Turner"],
    "Atlanta Hawks": ["Trae Young", "Jalen Johnson", "Dyson Daniels", "Zaccharie Risacher"],
    "Toronto Raptors": ["Scottie Barnes", "RJ Barrett", "Immanuel Quickley", "Jakob Poeltl"],
    "New Orleans Pelicans": ["Zion Williamson", "CJ McCollum", "Brandon Ingram", "DeJounte Murray"],
    "Brooklyn Nets": ["Michael Porter Jr.", "Cam Thomas", "Dennis Schroder", "Cameron Johnson"],
    "Houston Rockets": ["Alperen Sengun", "Jalen Green", "Fred VanVleet", "Jabari Smith Jr."],
    "Milwaukee Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Bobby Portis", "Brook Lopez"],
    "Golden State Warriors": ["Stephen Curry", "Jonathan Kuminga", "Buddy Hield", "Draymond Green"],
    "Oklahoma City Thunder": ["Shai Gilgeous-Alexander", "Jalen Williams", "Chet Holmgren", "Luguentz Dort"],
    "Boston Celtics": ["Jayson Tatum", "Jaylen Brown", "Derrick White", "Jrue Holiday"],
    "Los Angeles Lakers": ["LeBron James", "Anthony Davis", "Austin Reaves", "D'Angelo Russell"],
    "Phoenix Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal", "Tyus Jones"],
    "Denver Nuggets": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Christian Braun"],
    "Dallas Mavericks": ["Luka Doncic", "Kyrie Irving", "Klay Thompson", "PJ Washington"],
    "Minnesota Timberwolves": ["Anthony Edwards", "Julius Randle", "Rudy Gobert", "Naz Reid"],
}

BENCHMARKS_JUGADORES = {
    "Victor Wembanyama": {"pts": 29.1, "3pt": 1.9, "min": 30.3, "std": 12.5, "reb": 10.2, "ast": 4.8, "b2b": False, "equipo": "San Antonio Spurs"},
    "Ty Jerome": {"pts": 26.6, "3pt": 2.5, "min": 30.5, "std": 11.9, "reb": 3.8, "ast": 4.8, "b2b": False, "equipo": "Cleveland Cavaliers"},
    "Scottie Barnes": {"pts": 23.5, "3pt": 0.5, "min": 33.4, "std": 11.8, "reb": 7.5, "ast": 5.2, "b2b": False, "equipo": "Toronto Raptors"},
    "Cade Cunningham": {"pts": 22.9, "3pt": 2.1, "min": 34.0, "std": 6.4, "reb": 6.1, "ast": 7.0, "b2b": False, "equipo": "Detroit Pistons"},
    "Zion Williamson": {"pts": 21.0, "3pt": 0.1, "min": 33.1, "std": 4.4, "reb": 5.2, "ast": 2.8, "b2b": False, "equipo": "New Orleans Pelicans"},
    "Jalen Johnson": {"pts": 19.8, "3pt": 1.0, "min": 33.1, "std": 6.1, "reb": 9.8, "ast": 6.5, "b2b": False, "equipo": "Atlanta Hawks"},
    "Evan Mobley": {"pts": 18.4, "3pt": 0.6, "min": 32.8, "std": 5.0, "reb": 8.5, "ast": 3.3, "b2b": False, "equipo": "Cleveland Cavaliers"},
    "Trae Young": {"pts": 18.4, "3pt": 1.8, "min": 35.1, "std": 6.1, "reb": 3.1, "ast": 9.2, "b2b": False, "equipo": "Atlanta Hawks"},
    "Dylan Harper": {"pts": 18.1, "3pt": 1.2, "min": 31.9, "std": 4.1, "reb": 4.5, "ast": 5.3, "b2b": False, "equipo": "San Antonio Spurs"},
    "Andrew Nembhard": {"pts": 17.8, "3pt": 2.5, "min": 33.1, "std": 4.7, "reb": 3.2, "ast": 5.8, "b2b": False, "equipo": "Indiana Pacers"},
    "Immanuel Quickley": {"pts": 17.4, "3pt": 2.4, "min": 31.8, "std": 5.2, "reb": 3.8, "ast": 5.1, "b2b": False, "equipo": "Toronto Raptors"},
    "Jayson Tatum": {"pts": 26.4, "3pt": 2.8, "min": 31.8, "std": 6.6, "reb": 5.8, "ast": 7.6, "b2b": False, "equipo": "Boston Celtics"},
    "Stephen Curry": {"pts": 25.2, "3pt": 4.2, "min": 32.0, "std": 5.8, "reb": 4.5, "ast": 6.1, "b2b": False, "equipo": "Golden State Warriors"},
    "Shai Gilgeous-Alexander": {"pts": 28.5, "3pt": 1.8, "min": 34.2, "std": 5.1, "reb": 5.5, "ast": 6.2, "b2b": False, "equipo": "Oklahoma City Thunder"},
    "Giannis Antetokounmpo": {"pts": 29.8, "3pt": 0.4, "min": 33.8, "std": 6.2, "reb": 11.5, "ast": 5.8, "b2b": False, "equipo": "Milwaukee Bucks"},
}

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    h1, h2, h3 { color: #F1C40F !important; font-family: 'Helvetica Neue', sans-serif; }
    .stMetric { background-color: #1E222D; padding: 15px; border-radius: 10px; border: 1px solid #2E3440; }
    .parlay-box { background-color: #161B22; border: 2px solid #F1C40F; border-radius: 12px; padding: 20px; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

def calcular_poisson_over(promedio: float, linea: float) -> float:
    k = math.floor(linea)
    prob_acumulada = 0.0
    for i in range(k + 1):
        prob_acumulada += (math.pow(promedio, i) * math.exp(-promedio)) / math.factorial(i)
    return max(0.0, min(1.0, 1.0 - prob_acumulada))

def estimar_cuota_casa(probabilidad: float) -> float:
    margen = 0.90
    return max(1.10, round(1.0 / (probabilidad * margen), 2))

@st.cache_data(ttl=3600)
def obtener_partidos_espn(fecha_str: str):
    fecha_clean = fecha_str.replace('-', '')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_clean}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        data = res.json()
        events = data.get('events', [])
        juegos = []
        equipos = []
        for ev in events:
            comp = ev.get('competitions', [])[0]
            competitors = comp.get('competitors', [])
            for c in competitors:
                team_name = c.get('team', {}).get('displayName', '')
                equipos.append(team_name)
            juegos.append(ev.get('name', ''))
        return juegos, equipos
    except Exception:
        return [], []

@st.cache_data(ttl=1800)
def cargar_datos_jornada(fecha_str: str, temporada='2026-27'):
    juegos, equipos_nombres = obtener_partidos_espn(fecha_str)
    
    if not equipos_nombres:
        jugadores_a_analizar = list(BENCHMARKS_JUGADORES.keys())
        n_juegos_total = 8
        n_equipos_total = 16
    else:
        n_juegos_total = len(juegos)
        n_equipos_total = len(equipos_nombres)
        jugadores_a_analizar = []
        for eq in equipos_nombres:
            if eq in PLANTILLAS_EQUIPOS:
                jugadores_a_analizar.extend(PLANTILLAS_EQUIPOS[eq])
        if not jugadores_a_analizar:
            jugadores_a_analizar = list(BENCHMARKS_JUGADORES.keys())

    resultados = []
    for nombre in jugadores_a_analizar:
        prom_pts, prom_3pt, prom_min, std_pts, prom_pra, es_b2b, equipo_nombre = None, None, None, None, None, False, "Desconocido"
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

                    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], format='%b %d, %Y', errors='coerce')
                    fecha_hoy_dt = pd.to_datetime(fecha_str)
                    fechas_previas = df[df['GAME_DATE'] < fecha_hoy_dt]['GAME_DATE']
                    if not fechas_previas.empty:
                        dias_descanso = (fecha_hoy_dt - fechas_previas.max()).days
                        es_b2b = (dias_descanso == 1)
        except Exception:
            pass

        if prom_pts is None:
            bm = BENCHMARKS_JUGADORES.get(nombre, {"pts": 18.5, "3pt": 1.5, "min": 30.0, "std": 5.5, "reb": 4.5, "ast": 4.0, "b2b": False, "equipo": "Desconocido"})
            prom_pts = bm["pts"]
            prom_3pt = bm["3pt"]
            prom_min = bm["min"]
            std_pts = bm["std"]
            prom_pra = bm["pts"] + bm["reb"] + bm["ast"]
            es_b2b = bm.get("b2b", False)
            equipo_nombre = bm.get("equipo", "Desconocido")

        resultados.append({
            'Jugador': nombre,
            'Equipo': equipo_nombre,
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

def generar_combinada_optima_dinamica(df_data, target_cuota=2.50):
    """Genera combinadas ajustando la línea de cada jugador para buscar cuotas individuales con valor real (@1.45 - @1.85)."""
    cand = df_data[(df_data['Estabilidad'] == "⭐ ALTA") & (df_data['Minutos L10'] >= 25)].copy()
    if len(cand) < 2:
        cand = df_data[df_data['Minutos L10'] >= 25].copy()

    selecciones = []
    for _, fila in cand.iterrows():
        pts_proj = fila['PTS Proyectados']
        triples_proj = fila['Triples Prom']

        # --- OPCIONES DE PUNTOS ESCALADAS DINÁMICAMENTE ---
        lineas_pts_posibles = []
        if pts_proj >= 26.0:
            lineas_pts_posibles = [24.5, 22.5]
        elif pts_proj >= 21.0:
            lineas_pts_posibles = [19.5, 21.5]
        elif pts_proj >= 17.0:
            lineas_pts_posibles = [15.5, 17.5]

        for l_pts in lineas_pts_posibles:
            p_pts = calcular_poisson_over(pts_proj, l_pts)
            # Buscar cuotas con sustancia (entre 55% y 78% de probabilidad)
            if 0.55 <= p_pts <= 0.80:
                c_pts = estimar_cuota_casa(p_pts)
                selecciones.append({
                    'jugador': fila['Jugador'],
                    'mercado': f'Over {l_pts} Puntos',
                    'prob': p_pts,
                    'cuota': c_pts
                })

        # --- OPCIONES DE TRIPLES ESCALADAS DINÁMICAMENTE ---
        lineas_3pt_posibles = []
        if triples_proj >= 3.5:
            lineas_3pt_posibles = [3.5, 2.5] # Para tiradores élite como Curry
        elif triples_proj >= 2.0:
            lineas_3pt_posibles = [2.5, 1.5] # Para tiradores secundarios como Nembhard / Jerome

        for l_3pt in lineas_3pt_posibles:
            p_3pt = calcular_poisson_over(triples_proj, l_3pt)
            if 0.50 <= p_3pt <= 0.78:
                c_3pt = estimar_cuota_casa(p_3pt)
                selecciones.append({
                    'jugador': fila['Jugador'],
                    'mercado': f'Over {l_3pt} Triples',
                    'prob': p_3pt,
                    'cuota': c_3pt
                })

    mejores_combinadas = []
    for i in range(len(selecciones)):
        for j in range(i + 1, len(selecciones)):
            s1, s2 = selecciones[i], selecciones[j]
            if s1['jugador'] == s2['jugador']:
                continue
            c_total = s1['cuota'] * s2['cuota']
            p_real = s1['prob'] * s2['prob']
            
            if c_total >= target_cuota:
                mejores_combinadas.append({'logros': [s1, s2], 'cuota_total': round(c_total, 2), 'prob_real': p_real})
            else:
                for k in range(j + 1, len(selecciones)):
                    s3 = selecciones[k]
                    if s3['jugador'] in [s1['jugador'], s2['jugador']]:
                        continue
                    c_t3 = c_total * s3['cuota']
                    p_r3 = p_real * s3['prob']
                    if c_t3 >= target_cuota:
                        mejores_combinadas.append({'logros': [s1, s2, s3], 'cuota_total': round(c_t3, 2), 'prob_real': p_r3})

    if not mejores_combinadas:
        return None

    mejores_combinadas.sort(key=lambda x: x['prob_real'], reverse=True)
    return mejores_combinadas[0]

# --- CABECERA ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")
st.caption("Motor cuantitativo con Escalado Dinámico de Líneas para Cuota Target (>= 2.50)")

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_defecto = now_et.date()

fecha_seleccionada = st.sidebar.date_input("Fecha de Jornada NBA", value=fecha_defecto)
fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

with st.spinner(f"⚡ Procesando datos cuantitativos ({fecha_str})..."):
    df_raw, n_juegos, n_equipos = cargar_datos_jornada(fecha_str)

st.sidebar.markdown("---")
st.sidebar.header("🚑 Reporte de Bajas / Lesiones")
bajas_confirmadas = st.sidebar.multiselect(
    "Selecciona los jugadores descartados (OUT):",
    options=df_raw['Jugador'].tolist() if not df_raw.empty else []
)

target_cuota_input = st.sidebar.slider("Objetivo Cuota Combinada Mínima", 2.00, 5.00, 2.50, step=0.10)

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
        f_usage = 1.15 if fila['Equipo'] in equipos_con_baja else 1.00
        
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

    # --- COMBINADA AUTOMÁTICA DEL DÍA CON ESCALADO DINÁMICO ---
    comb_top = generar_combinada_optima_dinamica(df_data, target_cuota=target_cuota_input)
    
    if comb_top:
        st.markdown('<div class="parlay-box">', unsafe_allow_html=True)
        st.subheader(f"🔥 COMBINADA AUTOMÁTICA RECOMENDADA DEL DÍA (Target $\\ge {target_cuota_input:.2f}$)")
        st.caption("Líneas escaladas automáticamente para buscar cuotas individuales de valor real (@1.45 - @1.80).")
        
        cols_logros = st.columns(len(comb_top['logros']))
        cuotas_reales_ingresadas = []

        for idx, logro in enumerate(comb_top['logros']):
            with cols_logros[idx]:
                st.markdown(f"**Logro {idx+1}:** {logro['jugador']}")
                st.markdown(f"🎯 *{logro['mercado']}*")
                st.caption(f"Prob. Modelo: {logro['prob']*100:.1f}%")
                
                c_real_val = st.number_input(
                    f"Cuota Rushbet ({logro['jugador'][:8]}...)",
                    min_value=1.01,
                    value=float(logro['cuota']),
                    step=0.02,
                    key=f"cuota_real_banner_{idx}"
                )
                cuotas_reales_ingresadas.append(c_real_val)
                
        st.markdown("---")
        
        cuota_total_real = 1.0
        for c in cuotas_reales_ingresadas:
            cuota_total_real *= c
            
        prob_rush_real = (1.0 / cuota_total_real) * 100
        ev_gain_real = (comb_top['prob_real'] * 100) - prob_rush_real

        m1, m2, m3 = st.columns(3)
        m1.metric("Cuota Combinada Rushbet", f"@{cuota_total_real:.2f}")
        m2.metric("Probabilidad Real Acumulada", f"{comb_top['prob_real']*100:.1f}%")
        m3.metric("Ventaja Matemática REAL (+EV)", f"{ev_gain_real:+.1f}%", delta_color="normal" if ev_gain_real > 0 else "inverse")
        st.markdown('</div>', unsafe_allow_html=True)

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
    st.caption("Prueba alternativas ingresando cuotas específicas de Rushbet.")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        j1 = st.selectbox("Selección 1 (Jugador)", df_mostrar['Jugador'].tolist(), index=0)
        c1 = st.number_input(f"Cuota en Rushbet para {j1}", min_value=1.01, value=1.75, step=0.05)
    with col_c2:
        j2 = st.selectbox("Selección 2 (Jugador)", df_mostrar['Jugador'].tolist(), index=min(1, len(df_mostrar)-1))
        c2 = st.number_input(f"Cuota en Rushbet para {j2}", min_value=1.01, value=1.65, step=0.05)
        
    p1 = df_mostrar[df_mostrar['Jugador'] == j1]['Prob >19.5 PTS (%)'].values[0] / 100
    p2 = df_mostrar[df_mostrar['Jugador'] == j2]['Prob >1.5 Triples (%)'].values[0] / 100
    
    cuota_total = c1 * c2
    prob_real = p1 * p2
    prob_rushbet = 1 / cuota_total
    ev_margin = (prob_real - prob_rushbet) * 100

    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric("Cuota Combinada", f"{cuota_total:.2f}")
    col_res2.metric("Probabilidad Real", f"{prob_real*100:.1f}%")
    col_res3.metric("Ventaja (+EV)", f"{ev_margin:+.1f}%", delta_color="normal" if ev_margin > 0 else "inverse")

    csv = df_mostrar.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Reporte Filtrado (CSV)",
        data=csv,
        file_name=f"reporte_yz_quant_{fecha_str}.csv",
        mime="text/csv"
    )
