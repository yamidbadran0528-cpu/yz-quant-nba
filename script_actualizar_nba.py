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

# Multiplicador defensivo según la fortaleza defensiva del rival de la jornada (Defensive Rating)
FACTOR_DEFENSA_RIVAL = {
    "Utah Jazz": 1.05, "Portland Trail Blazers": 1.05, "Washington Wizards": 1.06, "Charlotte Hornets": 1.04,
    "Boston Celtics": 0.94, "Oklahoma City Thunder": 0.93, "Minnesota Timberwolves": 0.94, "Houston Rockets": 0.95
}

# Lista amplia de las principales 60+ estrellas y anotadores de la liga
JUGADORES_CLAVE = [
    "Shai Gilgeous-Alexander", "Jayson Tatum", "Giannis Antetokounmpo", "Victor Wembanyama", "Stephen Curry",
    "Nikola Jokic", "Luka Doncic", "Anthony Edwards", "Donovan Mitchell", "De'Aaron Fox", "Cade Cunningham",
    "Tyrese Maxey", "Jalen Brunson", "Karl-Anthony Towns", "Kevin Durant", "Devin Booker", "LeBron James",
    "Anthony Davis", "James Harden", "Ja Morant", "Trae Young", "Zion Williamson", "Paolo Banchero",
    "Franz Wagner", "LaMelo Ball", "Brandon Miller", "Pascal Siakam", "Tyrese Haliburton", "Bam Adebayo",
    "Tyler Herro", "Jaylen Brown", "Derrick White", "Chet Holmgren", "Jalen Williams", "Alperen Sengun",
    "Jalen Green", "Domantas Sabonis", "DeMar DeRozan", "Kyrie Irving", "Jamal Murray", "Michael Porter Jr.",
    "Julius Randle", "Rudy Gobert", "Mikal Bridges", "OG Anunoby", "Coby White", "Zach LaVine",
    "Desmond Bane", "Jaren Jackson Jr.", "Jerami Grant", "Anfernee Simons", "Lauri Markkanen", "Jordan Poole",
    "Kyle Kuzma", "Cam Thomas", "RJ Barrett", "Scottie Barnes", "Immanuel Quickley", "Miles Bridges"
]

FALLBACK_PLAYERS = {
    "Victor Wembanyama": {"equipo": "San Antonio Spurs", "pts": 29.1, "3pt": 1.9, "3pa": 6.8, "min": 30.3, "std": 12.5, "pra": 44.1},
    "Shai Gilgeous-Alexander": {"equipo": "Oklahoma City Thunder", "pts": 28.5, "3pt": 1.8, "3pa": 5.2, "min": 34.2, "std": 5.1, "pra": 40.2},
    "Giannis Antetokounmpo": {"equipo": "Miami Heat", "pts": 29.8, "3pt": 0.4, "3pa": 1.1, "min": 33.8, "std": 6.2, "pra": 47.1},
    "Jayson Tatum": {"equipo": "Boston Celtics", "pts": 26.4, "3pt": 2.8, "3pa": 8.2, "min": 31.8, "std": 6.6, "pra": 39.8},
    "Stephen Curry": {"equipo": "Golden State Warriors", "pts": 25.2, "3pt": 4.2, "3pa": 10.5, "min": 32.0, "std": 5.8, "pra": 35.8},
    "Nikola Jokic": {"equipo": "Denver Nuggets", "pts": 29.5, "3pt": 1.5, "3pa": 4.2, "min": 36.8, "std": 6.1, "pra": 52.4},
    "Anthony Edwards": {"equipo": "Minnesota Timberwolves", "pts": 27.8, "3pt": 3.5, "3pa": 9.1, "min": 35.5, "std": 6.3, "pra": 38.5},
    "De'Aaron Fox": {"equipo": "San Antonio Spurs", "pts": 24.2, "3pt": 1.9, "3pa": 6.1, "min": 35.1, "std": 6.8, "pra": 34.5}
}

def obtener_cartelera_espn():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_et = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
    fecha_clean = now_et.strftime('%Y%m%d')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_clean}"
    
    equipos_hoy = set()
    mapa_enfrentamientos = {}
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if res.status_code == 200:
            events = res.json().get('events', [])
            for ev in events:
                comp = ev.get('competitions', [])[0]
                competitors = comp.get('competitors', [])
                if len(competitors) == 2:
                    t1 = competitors[0].get('team', {}).get('displayName', '')
                    t2 = competitors[1].get('team', {}).get('displayName', '')
                    if t1 and t2:
                        equipos_hoy.add(t1)
                        equipos_hoy.add(t2)
                        mapa_enfrentamientos[t1] = t2
                        mapa_enfrentamientos[t2] = t1
    except Exception as e:
        print(f"Error consultando cartelera ESPN: {e}")
    return equipos_hoy, mapa_enfrentamientos

def actualizar_datos_nba():
    print("🚀 Consultando cartelera oficial de la jornada...")
    equipos_hoy, mapa_enfrentamientos = obtener_cartelera_espn()
    equipos_hoy_lower = [x.lower() for x in equipos_hoy]
    
    if equipos_hoy:
        print(f"🏀 Equipos jugando hoy ({len(equipos_hoy)}): {list(equipos_hoy)}")
    else:
        print("⚠️ Cartelera vacía o no confirmada por API.")

    nba_players_all = players.get_players()
    mapa_ids = {p['full_name'].lower(): p['id'] for p in nba_players_all}

    dataset = []
    
    for nombre in JUGADORES_CLAVE:
        pid = mapa_ids.get(nombre.lower())
        if not pid:
            continue
        try:
            time.sleep(0.4) # Pausa técnica anti-bloqueo
            gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2026-27', headers=HEADERS, timeout=6)
            df = gamelog.get_data_frames()[0]
            
            if not df.empty and len(df) >= 3:
                df_l10 = df.head(10).copy()
                
                # Extraer equipo actual dinámicamente del MATCHUP del último partido
                matchup = str(df_l10.iloc[0].get('MATCHUP', ''))
                equipo_actual = "NBA Team"
                if matchup:
                    abbr = matchup.split(' ')[0]
                    equipo_actual = ABBR_TO_TEAM.get(abbr, "NBA Team")

                # Verificar si el equipo del jugador juega hoy
                juega_hoy = any(equipo_actual.lower() in eh or eh in equipo_actual.lower() for eh in equipos_hoy_lower) if equipos_hoy else True
                if not juega_hoy:
                    continue

                df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
                df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
                df_l10['FG3A'] = pd.to_numeric(df_l10.get('FG3A', 0))
                df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
                df_l10['REB'] = pd.to_numeric(df_l10['REB'])
                df_l10['AST'] = pd.to_numeric(df_l10['AST'])

                # Factor defensivo según el rival de hoy
                rival = mapa_enfrentamientos.get(equipo_actual, "")
                f_def = FACTOR_DEFENSA_RIVAL.get(rival, 1.00)

                pts_avg = round(float(df_l10['PTS'].mean()) * f_def, 1)
                fg3m_avg = round(float(df_l10['FG3M'].mean()), 1)
                fg3a_avg = round(float(df_l10['FG3A'].mean()), 1) if 'FG3A' in df_l10.columns else round(fg3m_avg * 2.5, 1)
                min_avg = round(float(df_l10['MIN'].mean()), 1)
                std_pts = round(float(df_l10['PTS'].std()), 1)
                pra_avg = round(float((df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean()) * f_def, 1)

                dataset.append({
                    "Jugador": nombre,
                    "Equipo": equipo_actual,
                    "Minutos L10": min_avg,
                    "PTS Base": pts_avg,
                    "3PT Base": fg3m_avg,
                    "3PA (Intentos)": fg3a_avg,
                    "Estabilidad": "⭐ ALTA" if std_pts <= 6.5 else "ESTÁNDAR",
                    "PRA Base": pra_avg,
                    "Varianza (std)": std_pts
                })
                print(f"✅ {nombre} ({equipo_actual}) -> PTS Proyectados: {pts_avg} (vs {rival if rival else 'Desconocido'})")
        except Exception as e:
            print(f"⚠️ Omisión/Error en {nombre}: {e}")

    if not dataset:
        print("⚠️ Activando respaldo automático (Fallback)...")
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
    print(f"🎉 Proceso finalizado. {len(dataset)} jugadores guardados en 'datos_nba_hoy.json'.")

if __name__ == "__main__":
    actualizar_datos_nba()
