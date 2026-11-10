import json
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

PLANTILLAS_EQUIPOS = {
    "Atlanta Hawks": ["Trae Young", "Jalen Johnson", "Dyson Daniels", "Clint Capela"],
    "Boston Celtics": ["Jayson Tatum", "Jaylen Brown", "Derrick White", "Jrue Holiday", "Kristaps Porzingis"],
    "Brooklyn Nets": ["Michael Porter Jr.", "Cam Thomas", "Dennis Schroder", "Cameron Johnson", "Nic Claxton"],
    "Charlotte Hornets": ["LaMelo Ball", "Brandon Miller", "Miles Bridges"],
    "Chicago Bulls": ["Coby White", "Zach LaVine", "Nikola Vucevic", "Josh Giddey"],
    "Cleveland Cavaliers": ["Donovan Mitchell", "Darius Garland", "Evan Mobley", "Jarrett Allen"],
    "Dallas Mavericks": ["Luka Doncic", "Kyrie Irving", "Klay Thompson", "PJ Washington"],
    "Denver Nuggets": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Russell Westbrook"],
    "Detroit Pistons": ["Cade Cunningham", "Jaden Ivey", "Tobias Harris", "Jalen Duren"],
    "Golden State Warriors": ["Stephen Curry", "Jonathan Kuminga", "Buddy Hield", "Draymond Green"],
    "Houston Rockets": ["Alperen Sengun", "Jalen Green", "Fred VanVleet", "Jabari Smith Jr."],
    "Indiana Pacers": ["Tyrese Haliburton", "Pascal Siakam", "Myles Turner", "Andrew Nembhard"],
    "Los Angeles Clippers": ["James Harden", "Kawhi Leonard", "Norman Powell", "Ivica Zubac"],
    "Los Angeles Lakers": ["LeBron James", "Anthony Davis", "Austin Reaves", "D'Angelo Russell"],
    "Memphis Grizzlies": ["Ja Morant", "Desmond Bane", "Jaren Jackson Jr.", "Ty Jerome"],
    "Miami Heat": ["Jimmy Butler", "Bam Adebayo", "Tyler Herro", "Terry Rozier"],
    "Milwaukee Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Bobby Portis", "Brook Lopez"],
    "Minnesota Timberwolves": ["Anthony Edwards", "Julius Randle", "Rudy Gobert", "Naz Reid"],
    "New Orleans Pelicans": ["Zion Williamson", "CJ McCollum", "Brandon Ingram", "DeJounte Murray"],
    "New York Knicks": ["Jalen Brunson", "Karl-Anthony Towns", "Mikal Bridges", "OG Anunoby"],
    "Oklahoma City Thunder": ["Shai Gilgeous-Alexander", "Jalen Williams", "Chet Holmgren", "Luguentz Dort"],
    "Orlando Magic": ["Paolo Banchero", "Franz Wagner", "Jalen Suggs"],
    "Philadelphia 76ers": ["Joel Embiid", "Tyrese Maxey", "Paul George"],
    "Phoenix Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal"],
    "Portland Trail Blazers": ["Anfernee Simons", "Jerami Grant", "Deandre Ayton"],
    "Sacramento Kings": ["Domantas Sabonis", "DeMar DeRozan", "De'Aaron Fox", "Keegan Murray"],
    "San Antonio Spurs": ["Victor Wembanyama", "Devin Vassell", "Stephon Castle", "Chris Paul"],
    "Toronto Raptors": ["Scottie Barnes", "RJ Barrett", "Immanuel Quickley", "Jakob Poeltl"],
    "Utah Jazz": ["Lauri Markkanen", "Collin Sexton", "Walker Kessler", "John Collins"],
    "Washington Wizards": ["Jordan Poole", "Kyle Kuzma", "Alexandre Sarr"]
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
    
    if equipos_hoy:
        print(f"🏀 Equipos jugando hoy ({len(equipos_hoy)}): {list(equipos_hoy)}")
    else:
        print("⚠️ No se pudo confirmar cartelera por API, escaneando plantillas base...")

    jugadores_a_escanear = []
    mapa_jugador_equipo = {}
    
    for eq, lista_j in PLANTILLAS_EQUIPOS.items():
        juega_hoy = any(eq.lower() in eh.lower() or eh.lower() in eq.lower() for eh.lower() in [x.lower() for x in equipos_hoy]) if equipos_hoy else True
        if juega_hoy:
            for j in lista_j:
                jugadores_a_escanear.append(j)
                mapa_jugador_equipo[j] = eq

    print(f"📋 Total jugadores a analizar para la jornada: {len(jugadores_a_escanear)}")

    nba_players_all = players.get_players()
    mapa_ids = {p['full_name'].lower(): p['id'] for p in nba_players_all}

    dataset = []
    for nombre in jugadores_a_escanear:
        pid = mapa_ids.get(nombre.lower())
        if not pid:
            continue
        try:
            gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2026-27', headers=HEADERS, timeout=8)
            df = gamelog.get_data_frames()[0]
            if not df.empty and len(df) >= 3:
                df_l10 = df.head(10).copy()
                df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
                df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
                df_l10['FG3A'] = pd.to_numeric(df_l10.get('FG3A', 0))
                df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
                df_l10['REB'] = pd.to_numeric(df_l10['REB'])
                df_l10['AST'] = pd.to_numeric(df_l10['AST'])

                pts_avg = round(float(df_l10['PTS'].mean()), 1)
                fg3m_avg = round(float(df_l10['FG3M'].mean()), 1)
                fg3a_avg = round(float(df_l10['FG3A'].mean()), 1) if 'FG3A' in df_l10.columns else round(fg3m_avg * 2.5, 1)
                min_avg = round(float(df_l10['MIN'].mean()), 1)
                std_pts = round(float(df_l10['PTS'].std()), 1)
                pra_avg = round(float((df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean()), 1)

                dataset.append({
                    "Jugador": nombre,
                    "Equipo": mapa_jugador_equipo.get(nombre, "NBA Team"),
                    "Minutos L10": min_avg,
                    "PTS Base": pts_avg,
                    "3PT Base": fg3m_avg,
                    "3PA (Intentos)": fg3a_avg,
                    "Estabilidad": "⭐ ALTA" if std_pts <= 6.5 else "ESTÁNDAR",
                    "PRA Base": pra_avg,
                    "Varianza (std)": std_pts
                })
                print(f"✅ Procesado: {nombre} ({pts_avg} PTS | {fg3m_avg} 3PM)")
        except Exception as e:
            print(f"⚠️ Error procesando {nombre}: {e}")

    with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print("🎉 Proceso finalizado. 'datos_nba_hoy.json' actualizado sólo con partidos de la fecha.")

if __name__ == "__main__":
    actualizar_datos_nba()
