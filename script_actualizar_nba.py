import json
import time
import requests
import datetime
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
}

# Diccionario de proyecciones base de respaldo (Anti-Bloqueos de IP)
PROYECCIONES_JUGADORES = {
    "Shai Gilgeous-Alexander": {"pts": 28.5, "3pt": 1.8, "3pa": 5.2, "min": 34.2, "pra": 40.2, "std": 5.1},
    "Jalen Williams": {"pts": 21.2, "3pt": 1.6, "3pa": 4.5, "min": 32.5, "pra": 32.1, "std": 5.4},
    "Chet Holmgren": {"pts": 18.2, "3pt": 1.4, "3pa": 4.1, "min": 30.1, "pra": 29.5, "std": 5.8},
    "Jayson Tatum": {"pts": 26.4, "3pt": 2.8, "3pa": 8.2, "min": 31.8, "pra": 39.8, "std": 6.6},
    "Jaylen Brown": {"pts": 23.8, "3pt": 2.1, "3pa": 6.4, "min": 33.1, "pra": 34.2, "std": 5.9},
    "Derrick White": {"pts": 16.5, "3pt": 2.9, "3pa": 7.5, "min": 32.0, "pra": 25.8, "std": 4.8},
    "Giannis Antetokounmpo": {"pts": 29.8, "3pt": 0.4, "3pa": 1.1, "min": 33.8, "pra": 47.1, "std": 6.2},
    "Tyler Herro": {"pts": 22.4, "3pt": 3.1, "3pa": 8.4, "min": 34.5, "pra": 31.2, "std": 6.4},
    "Bam Adebayo": {"pts": 18.6, "3pt": 0.6, "3pa": 1.8, "min": 34.0, "pra": 32.5, "std": 5.2},
    "Stephen Curry": {"pts": 25.2, "3pt": 4.2, "3pa": 10.5, "min": 32.0, "pra": 35.8, "std": 5.8},
    "Tyrese Maxey": {"pts": 27.2, "3pt": 3.2, "3pa": 8.8, "min": 37.5, "pra": 36.5, "std": 6.9},
    "Joel Embiid": {"pts": 28.0, "3pt": 1.2, "3pa": 3.5, "min": 31.5, "pra": 42.0, "std": 7.5},
    "LeBron James": {"pts": 23.5, "3pt": 2.1, "3pa": 5.5, "min": 35.0, "pra": 39.8, "std": 5.9},
    "Anthony Davis": {"pts": 27.5, "3pt": 0.5, "3pa": 1.5, "min": 35.8, "pra": 43.5, "std": 6.0},
    "Luka Doncic": {"pts": 28.9, "3pt": 3.1, "3pa": 8.8, "min": 36.2, "pra": 46.1, "std": 7.2},
    "Kyrie Irving": {"pts": 24.5, "3pt": 2.8, "3pa": 6.7, "min": 34.8, "pra": 33.5, "std": 5.5},
    "Anthony Edwards": {"pts": 27.8, "3pt": 3.5, "3pa": 9.1, "min": 35.5, "pra": 38.5, "std": 6.3},
    "Nikola Jokic": {"pts": 29.5, "3pt": 1.5, "3pa": 4.2, "min": 36.8, "pra": 52.4, "std": 6.1},
    "Kevin Durant": {"pts": 27.6, "3pt": 2.5, "3pa": 6.1, "min": 36.8, "pra": 37.2, "std": 5.5},
    "Devin Booker": {"pts": 24.2, "3pt": 2.4, "3pa": 6.5, "min": 35.5, "pra": 34.5, "std": 5.8},
    "Jalen Brunson": {"pts": 26.2, "3pt": 2.4, "3pa": 6.2, "min": 35.0, "pra": 36.8, "std": 5.8},
    "Karl-Anthony Towns": {"pts": 24.1, "3pt": 2.1, "3pa": 4.8, "min": 34.2, "pra": 38.5, "std": 6.0},
    "Donovan Mitchell": {"pts": 24.5, "3pt": 3.2, "3pa": 8.5, "min": 33.5, "pra": 34.0, "std": 5.9},
    "Victor Wembanyama": {"pts": 29.1, "3pt": 1.9, "3pa": 6.8, "min": 30.3, "pra": 44.1, "std": 12.5},
    "Ja Morant": {"pts": 21.5, "3pt": 1.5, "3pa": 4.5, "min": 29.8, "pra": 33.8, "std": 7.0},
    "Domantas Sabonis": {"pts": 19.8, "3pt": 0.4, "3pa": 1.1, "min": 35.8, "pra": 44.5, "std": 5.2},
    "DeMar DeRozan": {"pts": 22.4, "3pt": 0.8, "3pa": 2.2, "min": 36.0, "pra": 31.8, "std": 5.1},
    "James Harden": {"pts": 20.8, "3pt": 2.6, "3pa": 7.8, "min": 34.5, "pra": 35.2, "std": 5.8},
    "Paolo Banchero": {"pts": 28.5, "3pt": 2.2, "3pa": 5.8, "min": 36.4, "pra": 42.1, "std": 7.5},
    "Pascal Siakam": {"pts": 20.5, "3pt": 1.4, "3pa": 3.5, "min": 33.5, "pra": 31.2, "std": 5.1},
    "Alperen Sengun": {"pts": 18.8, "3pt": 0.5, "3pa": 1.8, "min": 29.5, "pra": 34.5, "std": 5.5},
    "Trae Young": {"pts": 18.4, "3pt": 1.8, "3pa": 7.5, "min": 35.1, "pra": 30.7, "std": 6.1},
    "Coby White": {"pts": 19.5, "3pt": 2.8, "3pa": 7.5, "min": 33.0, "pra": 28.5, "std": 6.2},
    "LaMelo Ball": {"pts": 29.8, "3pt": 4.5, "3pa": 12.1, "min": 33.5, "pra": 42.5, "std": 7.8},
    "Zion Williamson": {"pts": 21.0, "3pt": 0.1, "3pa": 0.3, "min": 33.1, "pra": 29.0, "std": 4.4},
    "Lauri Markkanen": {"pts": 19.5, "3pt": 2.4, "3pa": 6.8, "min": 31.2, "pra": 28.0, "std": 6.5},
    "Anfernee Simons": {"pts": 18.5, "3pt": 2.8, "3pa": 8.1, "min": 32.1, "pra": 25.4, "std": 6.8},
    "Scottie Barnes": {"pts": 23.5, "3pt": 0.5, "3pa": 2.2, "min": 33.4, "pra": 36.2, "std": 11.8},
    "Cade Cunningham": {"pts": 22.9, "3pt": 2.1, "3pa": 6.2, "min": 34.0, "pra": 36.0, "std": 6.4},
    "Jordan Poole": {"pts": 20.8, "3pt": 3.1, "3pa": 8.2, "min": 30.5, "pra": 27.5, "std": 7.1}
}

def obtener_factores_defensivos_dinamicos():
    url_standings = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    factores_defensivos = {}
    try:
        res = requests.get(url_standings, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if res.status_code == 200:
            data = res.json()
            children = data.get('children', [])
            pts_permitidos = {}
            for conf in children:
                for item in conf.get('standings', {}).get('entries', []):
                    team_name = item.get('team', {}).get('displayName')
                    stats = item.get('stats', [])
                    pts_against = None
                    for s in stats:
                        if s.get('name') == 'avgPointsAgainst' or s.get('type') == 'avgpointsagainst':
                            pts_against = float(s.get('value', 0))
                            break
                    if team_name and pts_against:
                        pts_permitidos[team_name] = pts_against
            if pts_permitidos:
                prom_liga = sum(pts_permitidos.values()) / len(pts_permitidos)
                for t, opp in pts_permitidos.items():
                    factores_defensivos[t] = round(max(0.90, min(1.10, opp / prom_liga)), 3)
    except Exception as e:
        print(f"Error consultando defensas en vivo: {e}")
    return factores_defensivos

def obtener_jugadores_y_enfrentamientos_hoy():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
    fecha_clean = now_et.strftime('%Y%m%d')
    url_scoreboard = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_clean}"
    
    jugadores_hoy = []
    mapa_enfrentamientos = {}
    
    try:
        res = requests.get(url_scoreboard, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if res.status_code == 200:
            events = res.json().get('events', [])
            for ev in events:
                comp = ev.get('competitions', [])[0]
                competitors = comp.get('competitors', [])
                
                if len(competitors) == 2:
                    t1_name = competitors[0].get('team', {}).get('displayName', '')
                    t2_name = competitors[1].get('team', {}).get('displayName', '')
                    if t1_name and t2_name:
                        mapa_enfrentamientos[t1_name] = t2_name
                        mapa_enfrentamientos[t2_name] = t1_name

                for c in competitors:
                    team_info = c.get('team', {})
                    team_id = team_info.get('id')
                    team_name = team_info.get('displayName', 'NBA Team')
                    
                    if team_id:
                        url_roster = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
                        r_ros = requests.get(url_roster, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
                        if r_ros.status_code == 200:
                            athletes = r_ros.json().get('athletes', [])
                            for ath in athletes:
                                j_nombre = ath.get('fullName') or ath.get('displayName')
                                if j_nombre:
                                    jugadores_hoy.append({
                                        'nombre': j_nombre,
                                        'equipo': team_name
                                    })
    except Exception as e:
        print(f"Error consultando ESPN: {e}")
        
    return jugadores_hoy, mapa_enfrentamientos

def actualizar_datos_nba():
    print("🚀 Consultando tabla defensiva global en vivo...")
    factores_defensivos = obtener_factores_defensivos_dinamicos()
    
    print("🚀 Extrayendo automáticamente equipos y nóminas de HOY...")
    jugadores_hoy, mapa_enfrentamientos = obtener_jugadores_y_enfrentamientos_hoy()
    print(f"🏀 Jugadores detectados en nóminas activas de hoy: {len(jugadores_hoy)}")
    
    if not jugadores_hoy:
        print("⚠️ No hay partidos programados para la fecha actual.")
        with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    nba_players_all = players.get_players()
    mapa_ids = {p['full_name'].lower(): p['id'] for p in nba_players_all}

    dataset = []
    
    for item in jugadores_hoy:
        nombre = item['nombre']
        equipo = item['equipo']
        
        pts_raw, fg3m_avg, fg3a_avg, min_avg, pra_raw, std_pts = None, None, None, None, None, None
        
        # Intentar refrescar vía NBA API
        pid = mapa_ids.get(nombre.lower())
        if pid:
            try:
                time.sleep(0.3)
                gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2026-27', headers=HEADERS, timeout=4)
                df = gamelog.get_data_frames()[0]
                if not df.empty and len(df) >= 3:
                    df_l10 = df.head(10).copy()
                    df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
                    df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
                    df_l10['FG3A'] = pd.to_numeric(df_l10.get('FG3A', 0))
                    df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
                    df_l10['REB'] = pd.to_numeric(df_l10['REB'])
                    df_l10['AST'] = pd.to_numeric(df_l10['AST'])

                    min_avg = round(float(df_l10['MIN'].mean()), 1)
                    pts_raw = float(df_l10['PTS'].mean())
                    fg3m_avg = round(float(df_l10['FG3M'].mean()), 1)
                    fg3a_avg = round(float(df_l10['FG3A'].mean()), 1) if 'FG3A' in df_l10.columns else round(fg3m_avg * 2.5, 1)
                    pra_raw = float((df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean())
                    std_pts = round(float(df_l10['PTS'].std()), 1) if len(df_l10) > 1 else 5.0
            except Exception:
                pass

        # Fallback de seguridad si la NBA API bloqueó la IP de GitHub Actions
        if pts_raw is None:
            proj = PROYECCIONES_JUGADORES.get(nombre)
            if proj:
                pts_raw = proj["pts"]
                fg3m_avg = proj["3pt"]
                fg3a_avg = proj["3pa"]
                min_avg = proj["min"]
                pra_raw = proj["pra"]
                std_pts = proj["std"]

        if pts_raw is None or min_avg < 15.0 or pts_raw < 10.0:
            continue

        rival = mapa_enfrent
