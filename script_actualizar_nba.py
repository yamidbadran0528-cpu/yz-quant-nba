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
        print(f"Error consultando defensas ESPN: {e}")
    return factores_defensivos

def obtener_datos_jornada_hoy():
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
                                ath_id = ath.get('id')
                                
                                # Leemos métricas oficiales directamente del perfil de ESPN
                                ppg = float(ath.get('ppg', 0)) if ath.get('ppg') else 0.0
                                rpg = float(ath.get('rpg', 0)) if ath.get('rpg') else 0.0
                                apg = float(ath.get('apg', 0)) if ath.get('apg') else 0.0
                                
                                if j_nombre:
                                    jugadores_hoy.append({
                                        'nombre': j_nombre,
                                        'equipo': team_name,
                                        'espn_id': ath_id,
                                        'espn_ppg': ppg,
                                        'espn_rpg': rpg,
                                        'espn_apg': apg
                                    })
    except Exception as e:
        print(f"Error consultando ESPN: {e}")
        
    return jugadores_hoy, mapa_enfrentamientos

def actualizar_datos_nba():
    print("🚀 Consultando factores defensivos de los 30 equipos en vivo...")
    factores_defensivos = obtener_factores_defensivos_dinamicos()
    
    print("🚀 Extrayendo cartelera y nóminas activas de HOY de forma 100% dinámica...")
    jugadores_hoy, mapa_enfrentamientos = obtener_datos_jornada_hoy()
    print(f"🏀 Jugadores detectados en plantillas oficiales de hoy: {len(jugadores_hoy)}")
    
    if not jugadores_hoy:
        print("⚠️ No hay partidos programados para la fecha de hoy.")
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
        
        # 1. Intentamos refrescar L10 en vivo desde NBA API
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

        # 2. Si la API de la NBA bloqueó la IP de GitHub, leemos el promedio en vivo del objeto atleta de ESPN
        if pts_raw is None and item['espn_ppg'] > 0:
            pts_raw = item['espn_ppg']
            pra_raw = item['espn_ppg'] + item['espn_rpg'] + item['espn_apg']
            min_avg = 30.0
            fg3m_avg = round(pts_raw * 0.1, 1)
            fg3a_avg = round(fg3m_avg * 2.5, 1)
            std_pts = 5.5

        # Filtramos suplentes con bajo protagonismo (puntos < 11.0)
        if pts_raw is None or pts_raw < 11.0:
            continue

        rival = mapa_enfrentamientos.get(equipo, "")
        factor_defensa = factores_defensivos.get(rival, 1.00)

        pts_avg = round(pts_raw * factor_defensa, 1)
        pra_avg = round(pra_raw * factor_defensa, 1)

        dataset.append({
            "Jugador": nombre,
            "Equipo": equipo,
            "Minutos L10": min_avg if min_avg else 30.0,
            "PTS Base": pts_avg,
            "3PT Base": fg3m_avg if fg3m_avg else 1.5,
            "3PA (Intentos)": fg3a_avg if fg3a_avg else 4.0,
            "Estabilidad": "⭐ ALTA" if (std_pts and std_pts <= 6.5) else "ESTÁNDAR",
            "PRA Base": pra_avg,
            "Varianza (std)": std_pts if std_pts else 5.5
        })
        print(f"✅ Auto-detectado dinámicamente: {nombre} ({equipo}) vs {rival} -> {pts_avg} PTS")

    with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print(f"🎉 Proceso 100% dinámico finalizado. {len(dataset)} jugadores guardados.")

if __name__ == "__main__":
    actualizar_datos_nba()
