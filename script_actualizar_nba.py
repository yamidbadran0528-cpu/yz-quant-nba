import json
import time
import requests
import datetime
import numpy as np

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
                                injuries = ath.get('injuries', [])
                                estado_lesion = "ACTIVO"
                                if injuries and isinstance(injuries, list):
                                    status_raw = str(injuries[0].get('status', '')).strip().upper()
                                    if status_raw in ("OUT", "SUSPENSION", "INACTIVE"):
                                        estado_lesion = "OUT"
                                    elif status_raw in ("DAY-TO-DAY", "QUESTIONABLE", "DOUBTFUL"):
                                        estado_lesion = "GTD"
                                if j_nombre and ath_id:
                                    jugadores_hoy.append({
                                        'nombre': j_nombre,
                                        'equipo': team_name,
                                        'ath_id': ath_id,
                                        'estado_lesion': estado_lesion
                                    })
    except Exception as e:
        print(f"Error consultando cartelera ESPN: {e}")

    return jugadores_hoy, mapa_enfrentamientos

def obtener_l10_desde_espn(ath_id):
    url_gamelog = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{ath_id}/gamelog"
    try:
        res = requests.get(url_gamelog, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            season_types = data.get('seasonTypes', [])
            games = []
            for st_type in season_types:
                categories = st_type.get('categories', [])
                for cat in categories:
                    events_list = cat.get('events', [])
                    for ev in events_list:
                        stats = ev.get('stats', [])
                        if len(stats) >= 14:
                            try:
                                min_val = float(stats[0].split('-')[0]) if '-' in str(stats[0]) else float(stats[0])
                                fg3_str = str(stats[3])
                                fg3m = float(fg3_str.split('-')[0]) if '-' in fg3_str else 0.0
                                fg3a = float(fg3_str.split('-')[1]) if '-' in fg3_str else 0.0
                                reb_val = float(stats[7])
                                ast_val = float(stats[8])
                                pts_val = float(stats[13])
                                games.append({
                                    'MIN': min_val,
                                    'PTS': pts_val,
                                    '3PM': fg3m,
                                    '3PA': fg3a,
                                    'REB': reb_val,
                                    'AST': ast_val,
                                    'PRA': pts_val + reb_val + ast_val
                                })
                            except Exception:
                                continue
            if games:
                l10 = games[:10]
                min_avg = round(sum(g['MIN'] for g in l10) / len(l10), 1)
                pts_avg = round(sum(g['PTS'] for g in l10) / len(l10), 1)
                fg3m_avg = round(sum(g['3PM'] for g in l10) / len(l10), 1)
                fg3a_avg = round(sum(g['3PA'] for g in l10) / len(l10), 1)
                pra_avg = round(sum(g['PRA'] for g in l10) / len(l10), 1)
                pts_list = [g['PTS'] for g in l10]
                std_pts = round(float(np.std(pts_list, ddof=1)), 1) if len(pts_list) > 1 else 5.5
                return {
                    'min': min_avg,
                    'pts': pts_avg,
                    '3pt': fg3m_avg,
                    '3pa': fg3a_avg,
                    'pra': pra_avg,
                    'std': std_pts
                }
    except Exception:
        pass
    return None

def actualizar_datos_nba():
    print("🚀 Consultando tabla defensiva global en vivo...")
    factores_defensivos = obtener_factores_defensivos_dinamicos()

    print("🚀 Extrayendo nóminas activas de HOY...")
    jugadores_hoy, mapa_enfrentamientos = obtener_datos_jornada_hoy()
    print(f"🏀 Jugadores detectados en plantillas de hoy: {len(jugadores_hoy)}")

    if not jugadores_hoy:
        print("⚠️ No hay partidos programados para hoy.")
        with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    registros_crudos = []
    equipos_con_baja_pesada = set()

    for item in jugadores_hoy:
        nombre = item['nombre']
        equipo = item['equipo']
        ath_id = item['ath_id']
        estado_lesion = item['estado_lesion']

        l10_stats = obtener_l10_desde_espn(ath_id)
        if not l10_stats:
            continue

        min_avg = l10_stats['min']
        pts_raw = l10_stats['pts']

        if min_avg < 15.0 or pts_raw < 10.0:
            continue

        # Activar redistribución solo si la baja confirmada (OUT) es un titular de peso
        if estado_lesion == "OUT" and min_avg >= 26.0 and pts_raw >= 16.0:
            equipos_con_baja_pesada.add(equipo)
            print(f"🚑 Baja de alto impacto detectada: {nombre} ({equipo}) - {pts_raw} PTS / {min_avg} MIN")

        registros_crudos.append({
            'nombre': nombre,
            'equipo': equipo,
            'estado_lesion': estado_lesion,
            'stats': l10_stats
        })

    dataset = []
    for reg in registros_crudos:
        nombre = reg['nombre']
        equipo = reg['equipo']
        estado_lesion = reg['estado_lesion']
        s = reg['stats']

        # Excluir automáticamente jugadores ya confirmados OUT en ESPN
        if estado_lesion == "OUT":
            continue

        rival = mapa_enfrentamientos.get(equipo, "N/A")
        factor_defensa = factores_defensivos.get(rival, 1.00)

        # Boost realista (+8% PTS/PRA, +5% 3PT) solo si falta una figura titular del equipo
        factor_usage = 1.08 if equipo in equipos_con_baja_pesada else 1.00

        pts_avg = round(s['pts'] * factor_defensa * factor_usage, 1)
        pra_avg = round(s['pra'] * factor_defensa * factor_usage, 1)
        fg3m_avg = round(s['3pt'] * (1.05 if factor_usage > 1.0 else 1.0), 1)
        std_pts = s['std']

        dataset.append({
            "Jugador": nombre,
            "Equipo": equipo,
            "Rival": f"vs {rival}" if rival != "N/A" else "N/A",
            "Factor Defensivo": round(factor_defensa, 2),
            "Minutos L10": s['min'],
            "PTS Base": pts_avg,
            "3PT Base": fg3m_avg,
            "3PA (Intentos)": s['3pa'],
            "Estabilidad": "⭐ ALTA" if std_pts <= 6.5 else "ESTÁNDAR",
            "PRA Base": pra_avg,
            "Varianza (std)": std_pts,
            "Estado ESPN": estado_lesion,
            "Usage Auto": "🚀 USAGE (+8%)" if factor_usage > 1.0 else "🟢 NORMAL"
        })
        print(f"✅ L10 Real: {nombre} ({equipo}) [{estado_lesion}] vs {rival} -> {pts_avg} PTS (Def: {factor_defensa}x | Usage: {factor_usage}x)")

    dataset.sort(key=lambda x: x["PTS Base"], reverse=True)

    with open("datos_nba_hoy.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    print(f"🎉 Proceso 100% dinámico finalizado. {len(dataset)} jugadores activos guardados.")

if __name__ == "__main__":
    actualizar_datos_nba()
