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
    print("🚀 Consultando cartelera oficial de la jornada...")
    equipos_hoy = obtener_equipos_programados_hoy()
    print(f"🏀 Equipos jugando hoy: {list(equipos_hoy)}")

    # Obtenemos la base total de jugadores activos de la NBA de forma nativa
    nba_players_all = players.get_active_players()
    print(f"📋 Total jugadores activos en la base de la NBA: {len(nba_players_all)}")

    dataset = []
    
    # Escaneamos estrellas y referentes de la liga de forma automatizada
    for p in nba_players_all:
        nombre = p['full_name']
        pid = p['id']
        
        try:
            time.sleep(0.5) # Pausa técnica anti-bloqueo para la API de la NBA
            gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2026-27', headers=HEADERS, timeout=6)
            df = gamelog.get_data_frames()[0]
            
            if not df.empty and len(df) >= 3:
                df_l10 = df.head(10).copy()
                
                # Extraer equipo actual dinámicamente del último partido jugado
                matchup = str(df_l10.iloc[0].get('MATCHUP', ''))
                equipo_actual = "NBA Team"
                if matchup:
                    abbr = matchup.split(' ')[0]
                    equipo_actual = ABBR_TO_TEAM.get(abbr, "NBA Team")

                # Filtrar estrictamente si el equipo juega hoy (si la API de ESPN responde)
                if equipos_hoy:
                    juega_hoy = any(equipo_actual.lower() in eh.lower() or eh.lower() in equipo_actual.lower() for eh in equipos_hoy)
                    if not juega_hoy:
                        continue

                df_l10['PTS'] = pd.to_numeric(df_l10['PTS'])
                df_l10['FG3M'] = pd.to_numeric(df_l10['FG3M'])
                df_l10['FG3A'] = pd.to_numeric(df_l10.get('FG3A', 0))
                df_l10['MIN'] = pd.to_numeric(df_l10['MIN'])
                df_l10['REB'] = pd.to_numeric(df_l10['REB'])
                df_l10['AST'] = pd.to_numeric(df_l10['AST'])

                pts_avg = round(float(df_l10['PTS'].mean()), 1)
                
                # Solo procesamos jugadores con roles principales (promedio >= 15 PPG para evitar ruido de suplentes con pocos minutos)
                if pts_avg < 15.0:
                    continue

                fg3m_avg = round(float(df_l10['FG3M'].mean()), 1)
                fg3a_avg = round(float(df_l10['FG3A'].mean()), 1) if 'FG3A' in df_l10.columns else round(fg3m_avg * 2.5, 1)
                min_avg = round(float(df_l10['MIN'].mean()), 1)
                std_pts = round(float(df_l10['PTS'].std()), 1)
                pra_avg = round(float((df_l10['PTS'] + df_l10['REB'] + df_l10['AST']).mean()), 1)

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
                print(f"✅ Auto-detectado: {nombre} ({equipo_actual}) - {pts_avg} PTS")
        except Exception:
            continue

    with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print(f"🎉 Proceso finalizado. {len(dataset)} jugadores procesados y guardados de forma autónoma.")

if __name__ == "__main__":
    actualizar_datos_nba()
