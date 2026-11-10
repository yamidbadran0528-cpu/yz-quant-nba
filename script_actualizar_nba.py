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

ABBR_TO_TEAM = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets", "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons", "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz", "WAS": "Washington Wizards"
}

FALLBACK_PLAYERS = {
    "Victor Wembanyama": {"equipo": "San Antonio Spurs", "pts": 29.1, "3pt": 1.9, "3pa": 6.8, "min": 30.3, "std": 12.5, "pra": 44.1},
    "De'Aaron Fox": {"equipo": "San Antonio Spurs", "pts": 24.2, "3pt": 1.9, "3pa": 6.1, "min": 35.1, "std": 6.8, "pra": 34.5},
    "Stephen Curry": {"equipo": "Golden State Warriors", "pts": 25.2, "3pt": 4.2, "3pa": 10.5, "min": 32.0, "std": 5.8, "pra": 35.8},
    "Shai Gilgeous-Alexander": {"equipo": "Oklahoma City Thunder", "pts": 28.5, "3pt": 1.8, "3pa": 5.2, "min": 34.2, "std": 5.1, "pra": 40.2},
    "Giannis Antetokounmpo": {"equipo": "Miami Heat", "pts": 29.8, "3pt": 0.4, "3pa": 1.1, "min": 33.8, "std": 6.2, "pra": 47.1},
    "Jayson Tatum": {"equipo": "Boston Celtics", "pts": 26.4, "3pt": 2.8, "3pa": 8.2, "min": 31.8, "std": 6.6, "pra": 39.8},
    "Cade Cunningham": {"equipo": "Detroit Pistons", "pts": 22.9, "3pt": 2.1, "3pa": 6.2, "min": 34.0, "std": 6.4, "pra": 36.0},
    "Ty Jerome": {"equipo": "Memphis Grizzlies", "pts": 18.6, "3pt": 2.4, "3pa": 5.5, "min": 28.5, "std": 4.1, "pra": 26.2},
    "Andrew Nembhard": {"equipo": "Indiana Pacers", "pts": 17.8, "3pt": 2.5, "3pa": 5.8, "min": 33.1, "std": 4.7, "pra": 26.8},
    "Immanuel Quickley": {"equipo": "Toronto Raptors", "pts": 17.4, "3pt": 2.4, "3pa": 6.9, "min": 31.8, "std": 5.2, "pra": 26.3},
    "Nikola Jokic": {"equipo": "Denver Nuggets", "pts": 29.5, "3pt": 1.5, "3pa": 4.2, "min": 36.8, "std": 6.1, "pra": 52.4},
    "Anthony Edwards": {"equipo": "Minnesota Timberwolves", "pts": 27.8, "3pt": 3.5, "3pa": 9.1, "min": 35.5, "std": 6.3, "pra": 38.5},
    "Luka Doncic": {"equipo": "Dallas Mavericks", "pts": 28.9, "3pt": 3.1, "3pa": 8.8, "min": 36.2, "std": 7.2, "pra": 46.1},
    "Donovan Mitchell": {"equipo": "Cleveland Cavaliers", "pts": 24.5, "3pt": 3.2, "3pa": 8.5, "min": 33.5, "std": 5.9, "pra": 34.0},
    "Michael Porter Jr.": {"equipo": "Brooklyn Nets", "pts": 18.2, "3pt": 2.7, "3pa": 6.5, "min": 31.5, "std": 5.5, "pra": 26.7},
    "Scottie Barnes": {"equipo": "Toronto Raptors", "pts": 23.5, "3pt": 0.5, "3pa": 2.2, "min": 33.4, "std": 11.8, "pra": 36.2},
    "Zion Williamson": {"equipo": "New Orleans Pelicans", "pts": 21.0, "3pt": 0.1, "3pa": 0.3, "min": 33.1, "std": 4.4, "pra": 29.0},
    "Jalen Johnson": {"equipo": "Atlanta Hawks", "pts": 19.8, "3pt": 1.0, "3pa": 3.5, "min": 33.1, "std": 6.1, "pra": 36.1},
    "Evan Mobley": {"equipo": "Cleveland Cavaliers", "pts": 18.4, "3pt": 0.6, "3pa": 1.8, "min": 32.8, "std": 5.0, "pra": 30.2},
    "Trae Young": {"equipo": "Atlanta Hawks", "pts": 18.4, "3pt": 1.8, "3pa": 7.5, "min": 35.1, "std": 6.1, "pra": 30.7}
}

PLANTILLAS_EQUIPOS = {
    "Atlanta Hawks": ["Trae Young", "Jalen Johnson"],
    "Boston Celtics": ["Jayson Tatum"],
    "Brooklyn Nets": ["Michael Porter Jr."],
    "Cleveland Cavaliers": ["Donovan Mitchell", "Evan Mobley"],
    "Dallas Mavericks": ["Luka Doncic"],
    "Denver Nuggets": ["Nikola Jokic"],
    "Detroit Pistons": ["Cade Cunningham"],
    "Golden State Warriors": ["Stephen Curry"],
    "Indiana Pacers": ["Andrew Nembhard"],
    "Memphis Grizzlies": ["Ty Jerome"],
    "Miami Heat": ["Giannis Antetokounmpo"],
    "Minnesota Timberwolves": ["Anthony Edwards"],
    "New Orleans Pelicans": ["Zion Williamson"],
    "Oklahoma City Thunder": ["Shai Gilgeous-Alexander"],
    "San Antonio Spurs": ["Victor Wembanyama", "De'Aaron Fox"],
    "Toronto Raptors": ["Scottie Barnes", "Immanuel Quickley"]
}

def obtener_equipos_programados_hoy():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
    fecha_clean = now_et.strftime('%Y%m%d')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_clean}"
    
    equipos_hoy = set()
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if res.status_code == 200:
            events = res.json().get('events', [])
            for ev in events:
                comp = ev.get('competitions', [])[0]
                for c in comp.get('competitors', []):
                    t_name = c.get('team', {}).get('displayName', '')
                    if t_name:
                        equipos_hoy.add(t_name)
    except Exception as e:
        print(f"Error consultando cartelera: {e}")
    return equipos_hoy

def actualizar_datos_nba():
    print("🚀 Verificando cartelera del día...")
    equipos_hoy = obtener_equipos_programados_hoy()
    equipos_hoy_lower = [x.lower() for x in equipos_hoy]
    
    if equipos_hoy:
        print(f"🏀 Equipos jugando hoy ({len(equipos_hoy)}): {list(equipos_hoy)}")
    else:
        print("⚠️ No se pudo confirmar cartelera por API o día sin partidos programados.")

    jugadores_a_escanear = []
    mapa_jugador_equipo = {}
    
    for eq, lista_j in PLANTILLAS_EQUIPOS.items():
        juega_hoy = any(eq.lower() in eh or eh in eq.lower() for eh in equipos_hoy_lower) if equipos_hoy else True
        if juega_hoy:
            for j in lista_j:
                jugadores_a_escanear.append(j)
                mapa_jugador_equipo[j] = eq

    print(f"📋 Total jugadores a analizar: {len(jugadores_a_escanear)}")

    nba_players_all = players.get_players()
    mapa_ids = {p['full_name'].lower(): p['id'] for p in nba_players_all}

    dataset = []
    for nombre in jugadores_a_escanear:
        fb = FALLBACK_PLAYERS.get(nombre, {"pts": 20.0, "3pt": 1.5, "3pa": 4.5, "min": 30.0, "std": 5.5, "pra": 30.0, "equipo": mapa_jugador_equipo.get(nombre, "NBA Team")})
        
        pts_avg, fg3m_avg, fg3a_avg, min_avg, std_pts, pra_avg = fb["pts"], fb["3pt"], fb["3pa"], fb["min"], fb["std"], fb["pra"]
        equipo_detectado = fb.get("equipo", mapa_jugador_equipo.get(nombre, "NBA Team"))

        pid = mapa_ids.get(nombre.lower())
        if pid:
            try:
                time.sleep(0.6)
                gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2026-27', headers=HEADERS, timeout=6)
                df = gamelog.get_data_frames()[0]
                if not df.empty and len(df) >= 3:
                    df_l10 = df.head(10).copy()
                    df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
                    df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
                    df_l10['FG3A'] = pd.to_numeric(df_l10.get('FG3A', 0))
                    df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
                    df_l10['REB'] = pd.to_numeric(df_l10['REB'])
                    df_l10['AST'] = pd.to_numeric(df_l10['AST'])

                    matchup = str(df_l10.iloc[0].get('MATCHUP', ''))
                    if matchup:
                        abbr = matchup.split(' ')[0]
                        if abbr in ABBR_TO_TEAM:
                            equipo_detectado = ABBR_TO_TEAM[abbr]

                    pts_avg = round(float(df_l10['PTS'].mean()), 1)
                    fg3m_avg = round(float(df_l10['FG3M'].mean()), 1)
                    fg3a_avg = round(float(df_l10['FG3A'].mean()), 1) if 'FG3A' in df_l10.columns else round(fg3m_avg * 2.5, 1)
                    min_avg = round(float(df_l10['MIN'].mean()), 1)
                    std_pts = round(float(df_l10['PTS'].std()), 1)
                    pra_avg = round(float((df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean()), 1)
                    print(f"✅ En vivo NBA API: {nombre} ({equipo_detectado} - {pts_avg} PTS)")
            except Exception as e:
                print(f"⚠️ Usando fallback para {nombre}: {e}")

        dataset.append({
            "Jugador": nombre,
            "Equipo": equipo_detectado,
            "Minutos L10": min_avg,
            "PTS Base": pts_avg,
            "3PT Base": fg3m_avg,
            "3PA (Intentos)": fg3a_avg,
            "Estabilidad": "⭐ ALTA" if std_pts <= 6.5 else "ESTÁNDAR",
            "PRA Base": pra_avg,
            "Varianza (std)": std_pts
        })

    if not dataset:
        for nombre, fb in FALLBACK_PLAYERS.items():
            dataset.append({
                "Jugador": nombre,
                "Equipo": fb["equipo"],
                "Minutos L10": fb["min"],
                "PTS Base": fb["pts"],
                "3PT Base": fb["3pt"],
                "3PA (Intentos)": fb["3pa"],
                "Estabilidad": "⭐ ALTA" if fb["std"] <= 6.5 else "ESTÁNDAR",
                "PRA Base": fb["pra"],
                "Varianza (std)": fb["std"]
            })

    with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print("🎉 Proceso finalizado. 'datos_nba_hoy.json' actualizado.")

if __name__ == "__main__":
    actualizar_datos_nba()
