import json
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
}

JUGADORES_OBJETIVO = [
    "Victor Wembanyama", "Stephen Curry", "Shai Gilgeous-Alexander", 
    "Giannis Antetokounmpo", "Jayson Tatum", "Cade Cunningham", 
    "Ty Jerome", "Andrew Nembhard", "Immanuel Quickley", "Scottie Barnes",
    "Zion Williamson", "Jalen Johnson", "Evan Mobley", "Trae Young",
    "De'Aaron Fox", "Michael Porter Jr.", "Anthony Edwards", "Luka Doncic",
    "Nikola Jokic", "Donovan Mitchell", "Jalen Brunson", "Karl-Anthony Towns",
    "Tyrese Haliburton", "Bam Adebayo", "Ja Morant", "LaMelo Ball"
]

def actualizar_datos_nba():
    print("🚀 Iniciando extracción de estadísticas L10...")
    nba_players_all = players.get_players()
    mapa_ids = {p['full_name'].lower(): p['id'] for p in nba_players_all}

    dataset = []
    for nombre in JUGADORES_OBJETIVO:
        pid = mapa_ids.get(nombre.lower())
        if not pid:
            continue
        try:
            gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2026-27', headers=HEADERS, timeout=10)
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

                # Extraer último equipo registrado
                matchup = str(df.iloc[0].get('MATCHUP', ''))
                equipo = matchup.split(' ')[0] if matchup else "NBA Team"

                dataset.append({
                    "Jugador": nombre,
                    "Equipo": equipo,
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
    print("🎉 Proceso finalizado. 'datos_nba_hoy.json' actualizado con éxito.")

if __name__ == "__main__":
    actualizar_datos_nba()
