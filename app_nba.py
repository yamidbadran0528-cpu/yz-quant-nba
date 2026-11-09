import math
import datetime
import pandas as pd
import streamlit as st
from nba_api.stats.static import players
from nba_api.stats.endpoints import scoreboardv3, commonteamroster, playergamelog, leaguedashteamstats

st.set_page_config(
    page_title="YZ Quant NBA — Platform (+EV)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Encabezados para evitar bloqueos IP de los servidores de la NBA
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
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

@st.cache_data(ttl=3600)
def obtener_metricas_defensivas(temporada='2026-27'):
    try:
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season=temporada,
            measure_type_detailed_defense='Opponent',
            per_mode_detailed='PerGame',
            headers=HEADERS,
            timeout=15
        )
        df_def = stats.get_data_frames()[0]
        avg_pts = df_def['OPP_PTS'].mean()
        avg_3pt = df_def['OPP_FG3M'].mean()
        
        def_map = {}
        for _, fila in df_def.iterrows():
            def_map[fila['TEAM_ID']] = {
                'factor_pts': fila['OPP_PTS'] / avg_pts,
                'factor_3pt': fila['OPP_FG3M'] / avg_3pt
            }
        return def_map
    except Exception:
        return {}

@st.cache_data(ttl=1800)
def cargar_datos_jornada(fecha_consulta: str, temporada='2026-27'):
    def_map = obtener_metricas_defensivas(temporada)
    
    try:
        sb = scoreboardv3.ScoreboardV3(game_date=fecha_consulta, headers=HEADERS, timeout=15)
        dict_data = sb.get_dict()
        juegos = dict_data.get('scoreboard', {}).get('games', [])
    except Exception:
        return pd.DataFrame(), 0, 0

    if not juegos:
        return pd.DataFrame(), 0, 0

    mapa_rivales = {}
    equipos_ids = set()
    for juego in juegos:
        h_id = juego.get('homeTeam', {}).get('teamId')
        a_id = juego.get('awayTeam', {}).get('teamId')
        if h_id and a_id:
            equipos_ids.add(h_id)
            equipos_ids.add(a_id)
            mapa_rivales[h_id] = a_id
            mapa_rivales[a_id] = h_id

    jugadores = []
    for team_id in equipos_ids:
        try:
            roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=temporada, headers=HEADERS, timeout=15)
            df_roster = roster.get_data_frames()[0]
            top_jugadores = df_roster['PLAYER'].head(4).tolist()
            rival_id = mapa_rivales.get(team_id)
            for j in top_jugadores:
                jugadores.append({'nombre': j, 'rival_id': rival_id})
        except Exception:
            continue

    resultados = []
    for item in jugadores:
        nombre = item['nombre']
        rival_id = item['rival_id']
        nba_players = players.get_players()
        coincidencias = [p for p in nba_players if p['full_name'].lower() == nombre.lower()]
        
        if not coincidencias:
            continue
            
        player_id = coincidencias[0]['id']
        try:
            gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=temporada, headers=HEADERS, timeout=15)
            df = gamelog.get_data_frames()[0]
            if df.empty or len(df) < 5:
                continue
                
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

            datos_rival = def_map.get(rival_id, {'factor_pts': 1.0, 'factor_3pt': 1.0})
            f_pts = datos_rival['factor_pts']
            f_3pt = datos_rival['factor_3pt']

            pts_ajustados = prom_pts * f_pts
            triples_ajustados = prom_3pt * f_3pt

            prob_pts = calcular_poisson_over(pts_ajustados, 19.5)
            prob_3pt = calcular_poisson_over(triples_ajustados, 1.5)

            estabilidad = "⭐ ALTA" if std_pts <= 6.5 else "ESTÁNDAR"
            def_str = "🟢 SUAVE" if f_pts >= 1.04 else ("🔴 DURA" if f_pts <= 0.96 else "🟡 NEUTRA")

            resultados.append({
                'Jugador': nombre,
                'Minutos L10': round(prom_min, 1),
                'PTS Prom': round(prom_pts, 1),
                'PTS Proyectados': round(pts_ajustados, 1),
                'Defensa Rival': def_str,
                'Estabilidad': estabilidad,
                'Prob >19.5 PTS (%)': round(prob_pts * 100, 1),
                'Triples Prom': round(prom_3pt, 1),
                'Prob >1.5 Triples (%)': round(prob_3pt * 100, 1),
                'PRA Promedio': round(prom_pra, 1),
                'Varianza (std)': round(std_pts, 1)
            })
        except Exception:
            continue

    df_res = pd.DataFrame(resultados)
    return df_res, len(juegos), len(equipos_ids)

# --- CABECERA ---
st.title("🤖 YZ Quant NBA — Platform (+EV)")
st.caption("Motor cuantitativo con distribución de Poisson y Matchup Defensivo")

# --- BARRA LATERAL ---
st.sidebar.header("🎛️ Panel de Control")

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
fecha_defecto = now_et.date()

fecha_seleccionada = st.sidebar.date_input("Fecha de Jornada NBA", value=fecha_defecto)
fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

if st.sidebar.button("🔄 Escanear Jornada en Vivo", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

min_minutos = st.sidebar.slider("Minutos Mínimos Promedio", 15, 36, 25)
solo_alta_estabilidad = st.sidebar.checkbox("Mostrar solo estabilidad ⭐ ALTA", False)
filtro_defensa = st.sidebar.multiselect("Defensa Rival", ["🟢 SUAVE", "🟡 NEUTRA", "🔴 DURA"], default=["🟢 SUAVE", "🟡 NEUTRA", "🔴 DURA"])

with st.spinner(f"⚡ Procesando métricas cuantitativas para la fecha {fecha_str}..."):
    df_data, n_juegos, n_equipos = cargar_datos_jornada(fecha_str)

if df_data.empty:
    st.warning(f"⚠️ No se detectaron partidos o datos disponibles para la fecha ({fecha_str}). Abre el menú desplegable (flechitas '>>' arriba a la izquierda) y prueba cambiar la fecha.")
else:
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
    df_filtrado = df_filtrado[df_filtrado['Defensa Rival'].isin(filtro_defensa)]

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

    st.markdown("---")
    st.subheader("🧮 Simulador de Combinada (+EV)")
    st.caption("Selecciona 2 logros de la tabla anterior e ingresa las cuotas de Rushbet para evaluar la ventaja matemática.")
    
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
