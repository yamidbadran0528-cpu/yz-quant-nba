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

# Base de datos con los 30 equipos de la NBA para cruce dinámico con la cartelera del día
PLANTILLAS_30_EQUIPOS = {
    "Boston Celtics": ["Jayson Tatum", "Jaylen Brown", "Derrick White", "Jrue Holiday", "Al Horford", "Kristaps Porzingis", "Payton Pritchard"],
    "Brooklyn Nets": ["Michael Porter Jr.", "Cam Thomas", "Dennis Schroder", "Cameron Johnson", "Nic Claxton", "Dorian Finney-Smith"],
    "New York Knicks": ["Jalen Brunson", "Karl-Anthony Towns", "Mikal Bridges", "OG Anunoby", "Josh Hart", "Miles McBride"],
    "Philadelphia 76ers": ["Joel Embiid", "Tyrese Maxey", "Paul George", "Kelly Oubre Jr.", "Caleb Martin", "Kyle Lowry"],
    "Toronto Raptors": ["Scottie Barnes", "RJ Barrett", "Immanuel Quickley", "Jakob Poeltl", "Gradey Dick", "Davion Mitchell"],
    "Chicago Bulls": ["Coby White", "Zach LaVine", "Nikola Vucevic", "Josh Giddey", "Patrick Williams", "Ayo Dosunmu"],
    "Cleveland Cavaliers": ["Donovan Mitchell", "Darius Garland", "Evan Mobley", "Jarrett Allen", "Caris LeVert", "Max Strus"],
    "Detroit Pistons": ["Cade Cunningham", "Jaden Ivey", "Tobias Harris", "Jalen Duren", "Malik Beasley", "Tim Hardaway Jr."],
    "Indiana Pacers": ["Tyrese Haliburton", "Pascal Siakam", "Myles Turner", "Andrew Nembhard", "Bennedict Mathurin", "Aaron Nesmith"],
    "Milwaukee Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Bobby Portis", "Brook Lopez", "Khris Middleton", "Gary Trent Jr."],
    "Atlanta Hawks": ["Trae Young", "Jalen Johnson", "Dyson Daniels", "Zaccharie Risacher", "Clint Capela", "Bogdan Bogdanovic"],
    "Charlotte Hornets": ["LaMelo Ball", "Brandon Miller", "Miles Bridges", "Nick Richards", "Tre Mann", "Grant Williams"],
    "Miami Heat": ["Jimmy Butler", "Bam Adebayo", "Tyler Herro", "Terry Rozier", "Nikola Jovic", "Jaime Jaquez Jr."],
    "Orlando Magic": ["Paolo Banchero", "Franz Wagner", "Jalen Suggs", "Kentavious Caldwell-Pope", "Wendell Carter Jr."],
    "Washington Wizards": ["Jordan Poole", "Kyle Kuzma", "Alexandre Sarr", "Jonas Valanciunas", "Bilal Coulibaly"],
    "Denver Nuggets": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Michael Porter Jr.", "Christian Braun", "Russell Westbrook"],
    "Minnesota Timberwolves": ["Anthony Edwards", "Julius Randle", "Rudy Gobert", "Naz Reid", "Mike Conley", "Jaden McDaniels"],
    "Oklahoma City Thunder": ["Shai Gilgeous-Alexander", "Jalen Williams", "Chet Holmgren", "Luguentz Dort", "Alex Caruso", "Isaiah Hartenstein"],
    "Portland Trail Blazers": ["Anfernee Simons", "Jerami Grant", "Deandre Ayton", "Shaedon Sharpe", "Scoot Henderson"],
    "Utah Jazz": ["Lauri Markkanen", "Collin Sexton", "Walker Kessler", "John Collins", "Keyonte George", "Jordan Clarkson"],
    "Golden State Warriors": ["Stephen Curry", "Jonathan Kuminga", "Buddy Hield", "Draymond Green", "Brandin Podziemski", "Andrew Wiggins"],
    "Los Angeles Clippers": ["James Harden", "Kawhi Leonard", "Norman Powell", "Ivica Zubac", "Terance Mann", "Derrick Jones Jr."],
    "Los Angeles Lakers": ["LeBron James", "Anthony Davis", "Austin Reaves", "D'Angelo Russell", "Rui Hachimura", "Dalton Knecht"],
    "Phoenix Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal", "Tyus Jones", "Jusuf Nurkic", "Grayson Allen"],
    "Sacramento Kings": ["Domantas Sabonis", "DeMar DeRozan", "Malik Monk", "Keegan Murray", "Keon Ellis"],
    "Dallas Mavericks": ["Luka Doncic", "Kyrie Irving", "Klay Thompson", "PJ Washington", "Daniel Gafford", "Dereck Lively II"],
    "Houston Rockets": ["Alperen Sengun", "Jalen Green", "Fred VanVleet", "Jabari Smith Jr.", "Dillon Brooks", "Amen Thompson"],
    "Memphis Grizzlies": ["Ja Morant", "Desmond Bane", "Jaren Jackson Jr.", "Ty Jerome", "Marcus Smart", "Zach Edey", "Santi Aldama"],
    "New Orleans Pelicans": ["Zion Williamson", "CJ McCollum", "Brandon Ingram", "DeJounte Murray", "Herbert Jones", "Trey Murphy III"],
    "San Antonio Spurs": ["Victor Wembanyama", "De'Aaron Fox", "Stephon Castle", "Devin Vassell", "Chris Paul", "Jeremy Sochan"],
}

def calcular_poisson_over(promedio: float, linea: float) -> float:
    k = math.floor(linea)
    prob_acumulada = 0.0
    for i in range(k + 1):
        prob_acumulada += (math.pow(promedio, i) * math.exp(-promedio)) / math.factorial(i)
    return max(0.0, min(1.0, 1.0 - prob_acumulada))

@st.cache_data(ttl=1800)
def obtener_equipos_y_jugadores_del_dia(fecha_str: str):
    fecha_clean = fecha_str.replace('-', '')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_clean}"
    
    juegos = []
    equipos_hoy = []
    jugadores_jornada = []
    mapa_jugador_equipo = {}

    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        data = res.json()
        events = data.get('events', [])
        
        for ev in events:
            juegos.append(ev.get('name', ''))
            comp = ev.get('competitions', [])[0]
            competitors = comp.get('competitors', [])
            
            for c in competitors:
                t_name = c.get('team', {}).get('displayName', '')
                if t_name:
                    equipos_hoy.append(t_name)
                    
                    for eq_key, lista_jugadores in PLANTILLAS_30_EQUIPOS.items():
                        if eq_key.lower() in t_name.lower() or t_name.lower() in eq_key.lower():
                            for j in lista_jugadores:
                                if j not in jugadores_jornada:
                                    jugadores_jornada.append(j)
                                    mapa_jugador_equipo[j] = t_name

        return juegos, equipos_hoy, jugadores_jornada, mapa_jugador_equipo
    except Exception:
        return [], [], [], {}

@st.cache_data(ttl=1800)
def cargar_datos_jornada_en_vivo(fecha_str: str, temporada='2026-27'):
    juegos, equipos_hoy, jugadores_jornada, mapa_equipos = obtener_equipos_y_jugadores_del_dia(fecha_str)
    
    if not jugadores_jornada:
        return pd.DataFrame(), 0, 0

    nba_players_all = players.get_players()
    mapa_nba_ids = {p['full_name'].lower(): p['id'] for p in nba_players_all}

    resultados = []
    for nombre in jugadores_jornada:
        p_id = mapa_nba_ids.get(nombre.lower())
        if not p_id:
            continue
            
        try:
            gamelog = playergamelog.PlayerGameLog(player_id=p_id, season=temporada, headers=HEADERS, timeout=5)
            df = gamelog.get_data_frames()[0]
            if df.empty or len(df) < 3:
                continue
                
            df_l10 = df.head(10).copy()
            df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
            df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
            df_l10['FG3A'] = pd.to_numeric(df_l10.get('FG3A', 0))
            df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
            df_l10['REB'] = pd.to_numeric(df_l10['REB'])
            df_l10['AST'] = pd.to_numeric(df_l10['AST'])

            prom_pts = df_l10['PTS'].mean()
            prom_3pt = df_l10['FG3M'].mean()
            prom_3pa = df_l10['FG3A'].mean() if 'FG3A' in df_l10.columns else (prom_3pt * 2.5)
            prom_min = df_l10['MIN'].mean()
            std_pts = df_l10['PTS'].std()
            prom_pra = (df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean()

            df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], format='%b %d, %Y', errors='coerce')
            fecha_hoy_dt = pd.to_datetime(fecha_str)
            fechas_previas = df[df['GAME_DATE'] < fecha_hoy_dt]['GAME_DATE']
            es_b2b = False
            if not fechas_previas.empty:
                dias_descanso = (fecha_hoy_dt - fechas_previas.max()).days
                es_b2b = (dias_descanso == 1)

            equipo_real = mapa_equipos.get(nombre, "NBA Team")

            resultados.append({
                'Jugador': nombre,
                'Equipo': equipo_real,
                'Minutos L10': round(prom_min, 1),
                'PTS Prom Base': round(prom_pts, 1),
                '3PT Prom Base': round(prom_3pt, 1),
                '3PA (Intentos)': round(prom_3pa, 1),
                'es_b2b': es_b2b,
                'Estabilidad': "⭐ ALTA" if (std_pts <= 6.5 and not math.isnan(std_pts)) else "ESTÁNDAR",
                'PRA Promedios': round(prom_pra, 1),
                'Varianza (std)': round(std_pts, 1) if not math.isnan(std_pts) else 0.0
            })
        except Exception:
            continue

    df_res = pd.DataFrame(resultados).drop_duplicates(subset=['Jugador'])
    return df_res, len(juegos), len(equipos_hoy)

# --- CABECERA ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")
st.caption("Motor cuantitativo dinámico — Escaneo automático por cruce de plantillas del día")

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_defecto = now_et.date()

fecha_seleccionada = st.sidebar.date_input("Fecha de Jornada NBA", value=fecha_defecto)
fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

with st.spinner(f"⚡ Escaneando cartelera de ESPN y proyecciones L10 ({fecha_str})..."):
    df_raw, n_juegos, n_equipos = cargar_datos_jornada_en_vivo(fecha_str)

st.sidebar.markdown("---")
st.sidebar.header("🚑 Reporte de Bajas / Lesiones")
bajas_confirmadas = st.sidebar.multiselect(
    "Selecciona los jugadores descartados (OUT):",
    options=df_raw['Jugador'].tolist() if not df_raw.empty else []
)

if st.sidebar.button("🔄 Escanear Jornada en Vivo", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

min_minutos = st.sidebar.slider("Minutos Mínimos Promedio", 15, 36, 22)
solo_alta_estabilidad = st.sidebar.checkbox("Mostrar solo estabilidad ⭐ ALTA", False)
filtro_volumen_3pt = st.sidebar.checkbox("Filtrar tiradores con al menos 5.5 intentos (3PA)", False)

if df_raw.empty:
    st.warning(f"⚠️ No se detectaron partidos en vivo para la fecha ({fecha_str}). Si hoy no hay partidos en el calendario NBA, intenta cambiando la fecha al día de mañana.")
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
        
        pts_proj = fila['PTS Prom Base'] * f_fatiga * f_usage
        triples_proj = fila['3PT Prom Base'] * f_fatiga * f_usage

        prob_pts = calcular_poisson_over(pts_proj, 19.5)
        prob_3pt = calcular_poisson_over(triples_proj, 1.5)

        colchon_pts = pts_proj - 19.5
        descanso_str = "⚠️ B2B (-6%)" if fila['es_b2b'] else ("🚀 USAGE (+15%)" if f_usage > 1.0 else "🟢 NORMAL")

        procesados.append({
            'Jugador': j_nombre,
            'Equipo': fila['Equipo'],
            'Minutos L10': fila['Minutos L10'],
            'PTS Proyectados': round(pts_proj, 1),
            'Colchón PTS (>19.5)': round(colchon_pts, 1),
            'Estado Carga': descanso_str,
            'Estabilidad': fila['Estabilidad'],
            'Prob >19.5 PTS (%)': round(prob_pts * 100, 1),
            'Triples Prom': fila['3PT Prom Base'],
            '3PA (Intentos)': fila['3PA (Intentos)'],
            'Prob >1.5 Triples (%)': round(prob_3pt * 100, 1),
            'PRA Promedios': fila['PRA Promedios'],
            'Varianza (std)': fila['Varianza (std)']
        })

    df_data = pd.DataFrame(procesados)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Partidos Hoy", f"{n_juegos}")
    col2.metric("Equipos en Cancha", f"{n_equipos}")
    col3.metric("Jugadores Escaneados", f"{len(df_data)}")
    if not df_data.empty:
        top_pick = df_data.sort_values(by='Prob >19.5 PTS (%)', ascending=False).iloc[0]
        col4.metric("Top Pick Anotación", f"{top_pick['Jugador']}", f"{top_pick['Prob >19.5 PTS (%)']}% Prob")

    st.markdown("---")

    df_filtrado = df_data[df_data['Minutos L10'] >= min_minutos]
    if solo_alta_estabilidad:
        df_filtrado = df_filtrado[df_filtrado['Estabilidad'] == "⭐ ALTA"]
    if filtro_volumen_3pt:
        df_filtrado = df_filtrado[df_filtrado['3PA (Intentos)'] >= 5.5]

    st.subheader("📊 Ranking de Valor Esperado (+EV) — Datos en Vivo")
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
