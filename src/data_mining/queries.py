"""
Requêtes SQL paramétrées et optimisées pour l'analyse d'événements StatsBomb.
"""

# 1. Vue d'ensemble du match
SQL_MATCH_METADATA = """
SELECT 
    match_id, match_date, home_team, away_team, home_score, away_score
FROM matches
WHERE match_id = ?;
"""

# 2. Métriques statistiques agrégées par tranche temporelle pour une équipe
SQL_PHASE_METRICS = """
SELECT
    team,
    COUNT(*) as total_events,
    SUM(CASE WHEN type IN ('Pass', 'Carry', 'Shot', 'Dribble', 'Control', 'Ball Receipt') THEN 1 ELSE 0 END) as on_ball_events,
    SUM(CASE WHEN type IN ('Pressure', 'Duel', 'Interception', 'Clearance', 'Block', 'Foul Committed', 'Shield') THEN 1 ELSE 0 END) as defensive_events,
    SUM(CASE WHEN type = 'Pass' THEN 1 ELSE 0 END) as passes_attempted,
    SUM(CASE WHEN type = 'Pass' AND raw_data NOT LIKE '%"pass_outcome"%' THEN 1 ELSE 0 END) as passes_completed,
    SUM(CASE WHEN type = 'Pass' AND x >= 80 AND raw_data NOT LIKE '%"pass_outcome"%' THEN 1 ELSE 0 END) as passes_final_third,
    SUM(CASE WHEN type = 'Pass' AND x >= 75 AND x <= 95 AND y >= 30 AND y <= 50 THEN 1 ELSE 0 END) as passes_zone_14,
    SUM(CASE WHEN type = 'Shot' THEN 1 ELSE 0 END) as shots_count,
    SUM(CASE WHEN type = 'Shot' AND raw_data LIKE '%"shot_outcome": "Goal"%' THEN 1 ELSE 0 END) as goals_count,
    SUM(CASE WHEN type = 'Shot' AND (raw_data LIKE '%"shot_outcome": "Goal"%' OR raw_data LIKE '%"shot_outcome": "Saved"%') THEN 1 ELSE 0 END) as shots_on_target,
    COALESCE(SUM(CASE 
        WHEN type = 'Shot' THEN CAST(json_extract(raw_data, '$.shot_statsbomb_xg') AS REAL)
        ELSE 0.0 
    END), 0.0) as xg_sum,
    SUM(CASE 
        WHEN (type IN ('Dispossessed', 'Miscontrol') OR (type = 'Pass' AND raw_data LIKE '%"pass_outcome"%'))
             AND raw_data LIKE '%"under_pressure": true%' THEN 1 
        ELSE 0 
    END) as turnovers_under_pressure,
    SUM(CASE 
        WHEN type IN ('Ball Recovery', 'Interception') AND x >= 60 THEN 1 
        ELSE 0 
    END) as high_recoveries_count,
    SUM(CASE WHEN raw_data LIKE '%"under_pressure": true%' THEN 1 ELSE 0 END) as actions_under_pressure_total
FROM events
WHERE match_id = ? 
  AND minute >= ? 
  AND minute <= ?
  AND team = ?;
"""

# 3. Moyennes de référence par 15 minutes sur l'ensemble du match (pour calcul des deltas)
SQL_MATCH_BASELINE_AVERAGES = """
SELECT
    team,
    CAST(COUNT(*) AS REAL) / (MAX(minute) / 15.0) as avg_events_per_15m,
    CAST(SUM(CASE WHEN type = 'Pass' THEN 1 ELSE 0 END) AS REAL) / (MAX(minute) / 15.0) as avg_passes_attempted_per_15m,
    CAST(SUM(CASE WHEN type = 'Pass' AND raw_data NOT LIKE '%"pass_outcome"%' THEN 1 ELSE 0 END) AS REAL) / (MAX(minute) / 15.0) as avg_passes_completed_per_15m,
    CAST(SUM(CASE WHEN type = 'Pass' AND x >= 80 THEN 1 ELSE 0 END) AS REAL) / (MAX(minute) / 15.0) as avg_passes_final_third_per_15m,
    CAST(SUM(CASE 
        WHEN (type IN ('Dispossessed', 'Miscontrol') OR (type = 'Pass' AND raw_data LIKE '%"pass_outcome"%'))
             AND raw_data LIKE '%"under_pressure": true%' THEN 1 
        ELSE 0 
    END) AS REAL) / (MAX(minute) / 15.0) as avg_turnovers_under_pressure_per_15m,
    CAST(SUM(CASE WHEN type IN ('Ball Recovery', 'Interception') AND x >= 60 THEN 1 ELSE 0 END) AS REAL) / (MAX(minute) / 15.0) as avg_high_recoveries_per_15m
FROM events
WHERE match_id = ? AND team = ? AND minute > 0
GROUP BY team;
"""

# 4. Statistiques individualisées par joueur
SQL_PLAYER_METRICS = """
SELECT
    player,
    team,
    COUNT(*) as total_actions,
    SUM(CASE WHEN type = 'Pass' THEN 1 ELSE 0 END) as passes_attempted,
    SUM(CASE WHEN type = 'Pass' AND raw_data NOT LIKE '%"pass_outcome"%' THEN 1 ELSE 0 END) as passes_completed,
    SUM(CASE WHEN type = 'Shot' THEN 1 ELSE 0 END) as shots,
    SUM(CASE WHEN type = 'Shot' AND raw_data LIKE '%"shot_outcome": "Goal"%' THEN 1 ELSE 0 END) as goals,
    COALESCE(SUM(CASE WHEN type = 'Shot' THEN CAST(json_extract(raw_data, '$.shot_statsbomb_xg') AS REAL) ELSE 0 END), 0.0) as xg_total,
    SUM(CASE WHEN type IN ('Duel', '50_50') AND raw_data NOT LIKE '%"duel_outcome": "Lost"%' THEN 1 ELSE 0 END) as duels_won,
    SUM(CASE WHEN (type IN ('Dispossessed', 'Miscontrol') OR (type = 'Pass' AND raw_data LIKE '%"pass_outcome"%')) AND raw_data LIKE '%"under_pressure": true%' THEN 1 ELSE 0 END) as turnovers_under_pressure,
    MIN(minute) as first_action_min,
    MAX(minute) as last_action_min
FROM events
WHERE match_id = ? 
  AND player LIKE ?
  AND minute >= ? 
  AND minute <= ?
GROUP BY player, team;
"""

# 5. Timeline des événements marquants d'un joueur
SQL_PLAYER_KEY_EVENTS = """
SELECT
    minute, second, type, x, y, raw_data
FROM events
WHERE match_id = ?
  AND player LIKE ?
  AND minute >= ? 
  AND minute <= ?
  AND (type IN ('Shot', 'Goal', 'Foul Won', 'Substitution') OR raw_data LIKE '%"pass_goal_assist": true%')
ORDER BY minute, second;
"""

# 6. Métriques consolidées temps réel pour la tranche temporelle active (KPIs dynamiques)
SQL_REALTIME_KPIS = """
SELECT
    COALESCE(SUM(CASE 
        WHEN (type IN ('Dispossessed', 'Miscontrol') OR (type = 'Pass' AND raw_data LIKE '%"pass_outcome"%'))
             AND raw_data LIKE '%"under_pressure": true%' THEN 1 
        ELSE 0 
    END), 0) as turnovers_under_pressure,
    COALESCE(SUM(CASE 
        WHEN type = 'Shot' THEN CAST(json_extract(raw_data, '$.shot_statsbomb_xg') AS REAL)
        ELSE 0.0 
    END), 0.0) as total_xg,
    COALESCE(SUM(CASE WHEN type = 'Pass' AND x >= 80 THEN 1 ELSE 0 END), 0) as passes_final_third,
    COALESCE(SUM(CASE WHEN type IN ('Ball Recovery', 'Interception') AND x >= 60 THEN 1 ELSE 0 END), 0) as high_recoveries,
    COALESCE(SUM(CASE WHEN type = 'Shot' AND raw_data LIKE '%"shot_outcome": "Goal"%' THEN 1 ELSE 0 END), 0) as total_goals,
    COALESCE(SUM(CASE WHEN type = 'Shot' THEN 1 ELSE 0 END), 0) as total_shots
FROM events
WHERE match_id = ? 
  AND minute >= ? 
  AND minute <= ?;
"""

# 7. Événements décisifs et critiques du match (Buts, tirs dangereux, passes décisives, fautes penalty, pertes fatales)
SQL_CRITICAL_EVENTS = """
SELECT 
    minute, second, type, team, player, x, y, raw_data
FROM events
WHERE match_id = ?
  AND minute >= ?
  AND minute <= ?
  AND (
      (type = 'Shot') OR
      (raw_data LIKE '%"pass_goal_assist": true%') OR
      (raw_data LIKE '%"foul_committed_penalty": true%') OR
      (type IN ('Dispossessed', 'Miscontrol') AND raw_data LIKE '%"under_pressure": true%' AND x <= 35)
  )
ORDER BY minute, second;
"""
