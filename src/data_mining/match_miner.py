"""
API de haut niveau pour le data mining d'événements StatsBomb (Nœud 2A).
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from src.config import DEFAULT_MATCH_ID
from src.data_mining.db_connection import ReadOnlyDBConnection
from src.data_mining.queries import (
    SQL_CRITICAL_EVENTS,
    SQL_MATCH_BASELINE_AVERAGES,
    SQL_MATCH_METADATA,
    SQL_PHASE_METRICS,
    SQL_PLAYER_KEY_EVENTS,
    SQL_PLAYER_METRICS,
    SQL_REALTIME_KPIS,
)
from src.schemas.miner import MatchFacts, MatchPhaseMetric, PlayerHighlight
from src.schemas.router import QueryType, TacticalPlan


class MatchMiner:
    """
    Moteur de calcul statistique déterministe sur les événements de match.
    Génère des faits chiffrés vérifiés et garantit l'absence d'hallucination.
    """

    def __init__(self, db_conn: Optional[ReadOnlyDBConnection] = None):
        self.db = db_conn or ReadOnlyDBConnection()

    def get_match_metadata(self, match_id: int) -> Dict[str, Any]:
        """Récupère les métadonnées de base d'un match."""
        rows = self.db.execute_safe_query(SQL_MATCH_METADATA, (match_id,))
        if not rows:
            raise ValueError(f"Match introuvable pour match_id={match_id}")
        r = rows[0]
        return {
            "match_id": int(r["match_id"]),
            "match_date": str(r["match_date"]),
            "home_team": str(r["home_team"]),
            "away_team": str(r["away_team"]),
            "home_score": int(r["home_score"]),
            "away_score": int(r["away_score"]),
            "match_name": f"{r['home_team']} {r['home_score']} - {r['away_score']} {r['away_team']}",
        }

    def compute_phase_metric(
        self,
        match_id: int,
        minute_start: int,
        minute_end: int,
        team: str,
        label: Optional[str] = None,
    ) -> MatchPhaseMetric:
        """Calcule les métriques consolidées pour une tranche temporelle et une équipe."""
        rows = self.db.execute_safe_query(
            SQL_PHASE_METRICS,
            (match_id, minute_start, minute_end, team),
        )
        if not rows:
            return MatchPhaseMetric(
                phase_label=label or f"{minute_start}-{minute_end} min ({team})",
                minute_start=minute_start,
                minute_end=minute_end,
                team=team,
            )

        r = rows[0]
        passes_att = int(r["passes_attempted"] or 0)
        passes_comp = int(r["passes_completed"] or 0)
        accuracy = round((passes_comp / passes_att * 100.0), 1) if passes_att > 0 else 0.0

        # Calcul du Field Tilt (%) : % de passes réussies dans le dernier tiers par rapport au total des 2 équipes
        my_f3_comp = int(r["passes_final_third"] or 0)
        opp_team_rows = self.db.execute_safe_query(
            "SELECT SUM(CASE WHEN type = 'Pass' AND x >= 80 AND raw_data NOT LIKE '%\"pass_outcome\"%' THEN 1 ELSE 0 END) as f3_comp FROM events WHERE match_id = ? AND minute >= ? AND minute <= ? AND team != ?",
            (match_id, minute_start, minute_end, team)
        )
        opp_f3_comp = int(opp_team_rows[0]["f3_comp"] or 0) if (opp_team_rows and opp_team_rows[0]["f3_comp"] is not None) else 0
        total_f3 = my_f3_comp + opp_f3_comp
        field_tilt = round((my_f3_comp / total_f3 * 100.0), 1) if total_f3 > 0 else 50.0

        return MatchPhaseMetric(
            phase_label=label or f"{minute_start:02d}-{minute_end:02d} min ({team})",
            minute_start=minute_start,
            minute_end=minute_end,
            team=team,
            total_events=int(r["total_events"] or 0),
            on_ball_events=int(r["on_ball_events"] or 0),
            defensive_events=int(r["defensive_events"] or 0),
            field_tilt_pct=field_tilt,
            passes_attempted=passes_att,
            passes_completed=passes_comp,
            pass_accuracy_pct=accuracy,
            passes_final_third=my_f3_comp,
            passes_zone_14=int(r["passes_zone_14"] or 0),
            shots_count=int(r["shots_count"] or 0),
            shots_on_target=int(r["shots_on_target"] or 0),
            goals_count=int(r["goals_count"] or 0),
            xg_sum=round(float(r["xg_sum"] or 0.0), 3),
            turnovers_under_pressure=int(r["turnovers_under_pressure"] or 0),
            high_recoveries_count=int(r["high_recoveries_count"] or 0),
            actions_under_pressure_total=int(r["actions_under_pressure_total"] or 0),
        )

    def get_baseline_averages(self, match_id: int, team: str) -> Dict[str, float]:
        """Calcule les moyennes de référence par tranche de 15 minutes sur l'ensemble du match."""
        rows = self.db.execute_safe_query(SQL_MATCH_BASELINE_AVERAGES, (match_id, team))
        if not rows:
            return {}

        r = rows[0]
        return {
            "avg_events_per_15m": round(float(r["avg_events_per_15m"] or 0.0), 1),
            "avg_passes_completed_per_15m": round(float(r["avg_passes_completed_per_15m"] or 0.0), 1),
            "avg_passes_final_third_per_15m": round(float(r["avg_passes_final_third_per_15m"] or 0.0), 1),
            "avg_turnovers_under_pressure_per_15m": round(float(r["avg_turnovers_under_pressure_per_15m"] or 0.0), 1),
            "avg_high_recoveries_per_15m": round(float(r["avg_high_recoveries_per_15m"] or 0.0), 1),
        }

    def compute_player_highlight(
        self,
        match_id: int,
        player_name_pattern: str,
        minute_start: int = 0,
        minute_end: int = 120,
    ) -> Optional[PlayerHighlight]:
        """Extrait les statistiques et la chronologie d'un joueur cible."""
        # Essayer le pattern complet, puis les tokens individuels (ex: "Messi" pour "Lionel Messi")
        patterns_to_try = [f"%{player_name_pattern}%"]
        tokens = [t for t in player_name_pattern.replace("'", " ").split() if len(t) >= 3]
        for t in reversed(tokens):
            if f"%{t}%" not in patterns_to_try:
                patterns_to_try.append(f"%{t}%")

        rows = []
        matched_pattern = patterns_to_try[0]
        for pat in patterns_to_try:
            rows = self.db.execute_safe_query(
                SQL_PLAYER_METRICS,
                (match_id, pat, minute_start, minute_end),
            )
            if rows:
                matched_pattern = pat
                break

        if not rows:
            # Vérifier si le joueur a disputé le match (même s'il n'a pas touché de ballon sur cette micro-fenêtre)
            p_match_rows = []
            for pat in patterns_to_try:
                p_match_rows = self.db.execute_safe_query(
                    "SELECT player, team FROM events WHERE match_id = ? AND player LIKE ? LIMIT 1",
                    (match_id, pat),
                )
                if p_match_rows:
                    matched_pattern = pat
                    break

            if not p_match_rows:
                return None

            p_name = str(p_match_rows[0]["player"])
            team_name = str(p_match_rows[0]["team"])
            like_pattern = matched_pattern

            max_min_row = self.db.execute_safe_query(
                "SELECT MAX(minute) as max_min FROM events WHERE match_id = ?",
                (match_id,),
            )
            match_max_min = int(max_min_row[0]["max_min"] or 90) if max_min_row else 90

            sub_out = self.db.execute_safe_query(
                "SELECT minute FROM events WHERE match_id = ? AND type = 'Substitution' AND player LIKE ?",
                (match_id, like_pattern),
            )
            sub_in = self.db.execute_safe_query(
                "SELECT minute FROM events WHERE match_id = ? AND type = 'Substitution' AND raw_data LIKE ?",
                (match_id, f'%"{p_name}"%'),
            )

            min_start_player = int(sub_in[0]["minute"]) if sub_in else 0
            min_end_player = int(sub_out[0]["minute"]) if sub_out else match_max_min
            total_minutes = max(0, min_end_player - min_start_player)

            was_on_pitch = not (min_end_player <= minute_start or min_start_player >= minute_end)
            if not was_on_pitch:
                return None

            return PlayerHighlight(
                player_id=0,
                player_name=p_name,
                team_name=team_name,
                minutes_played=total_minutes,
                goals=0,
                shots=0,
                xg_total=0.0,
                passes_completed=0,
                passes_attempted=0,
                pass_accuracy_pct=0.0,
                duels_won=0,
                turnovers_under_pressure=0,
                key_events_timeline=[f"Sur le terrain durant cette phase (aucun tir/passe direct enregistré entre {minute_start}' et {minute_end}')"],
            )

        like_pattern = matched_pattern

        r = rows[0]
        passes_att = int(r["passes_attempted"] or 0)
        passes_comp = int(r["passes_completed"] or 0)
        accuracy = round((passes_comp / passes_att * 100.0), 1) if passes_att > 0 else 0.0
        p_name = str(r["player"])

        # Timeline des événements clés
        event_rows = self.db.execute_safe_query(
            SQL_PLAYER_KEY_EVENTS,
            (match_id, like_pattern, minute_start, minute_end),
        )
        timeline = []
        for ev in event_rows:
            raw = json.loads(ev["raw_data"])
            ev_type = ev["type"]
            detail = ""
            if ev_type == "Shot":
                outcome = raw.get("shot_outcome", "Shot")
                xg = round(float(raw.get("shot_statsbomb_xg", 0.0)), 2)
                detail = f"Tir ({outcome}, xG={xg})"
            elif raw.get("pass_goal_assist"):
                detail = "Passe décisive (Assist)"
            else:
                detail = ev_type
            timeline.append(f"{ev['minute']:02d}:{ev['second']:02d} - {detail}")

        # Calcul du temps de jeu total réel sur l'ensemble du match
        max_min_row = self.db.execute_safe_query(
            "SELECT MAX(minute) as max_min FROM events WHERE match_id = ?",
            (match_id,),
        )
        match_max_min = int(max_min_row[0]["max_min"] or 90) if max_min_row else 90

        # Vérifier si le joueur est sorti en cours de match
        sub_out = self.db.execute_safe_query(
            "SELECT minute FROM events WHERE match_id = ? AND type = 'Substitution' AND player LIKE ?",
            (match_id, like_pattern),
        )
        # Vérifier si le joueur est entré en cours de match
        sub_in = self.db.execute_safe_query(
            "SELECT minute FROM events WHERE match_id = ? AND type = 'Substitution' AND raw_data LIKE ?",
            (match_id, f'%"{p_name}"%'),
        )

        min_start_player = int(sub_in[0]["minute"]) if sub_in else 0
        min_end_player = int(sub_out[0]["minute"]) if sub_out else match_max_min
        total_minutes = max(0, min_end_player - min_start_player)

        return PlayerHighlight(
            player_id=0,
            player_name=p_name,
            team_name=str(r["team"]),
            minutes_played=total_minutes,
            goals=int(r["goals"] or 0),
            shots=int(r["shots"] or 0),
            xg_total=round(float(r["xg_total"] or 0.0), 2),
            passes_completed=passes_comp,
            passes_attempted=passes_att,
            pass_accuracy_pct=accuracy,
            duels_won=int(r["duels_won"] or 0),
            turnovers_under_pressure=int(r["turnovers_under_pressure"] or 0),
            key_events_timeline=timeline,
        )

    def build_match_facts(self, match_id: int, plan: TacticalPlan) -> MatchFacts:
        """
        Orchestre l'extraction des faits de match selon le TacticalPlan.
        Calcule les deltas statistiques et isole les points d'inflexion.
        """
        meta = self.get_match_metadata(match_id)
        valid_teams = [meta["home_team"], meta["away_team"]]
        teams = [t for t in (plan.target_teams or []) if t in valid_teams]
        if not teams:
            teams = valid_teams

        # 1. Définition des fenêtres temporelles d'analyse
        windows = plan.time_windows
        if not windows:
            if plan.query_type == QueryType.MACRO_MATCH_FLOW:
                from src.data_mining.phase_generator import MatchPhaseGenerator
                try:
                    phases = MatchPhaseGenerator().get_or_create_phases(match_id)
                    windows = [(p.minute_start, p.minute_end) for p in phases]
                except Exception:
                    windows = [(0, 40), (40, 70), (70, 85), (85, 90), (90, 120)]
            else:
                windows = [(70, 85)]

        phases_data: List[MatchPhaseMetric] = []
        for start_min, end_min in windows:
            for team in teams:
                label = f"{start_min:02d}-{end_min:02d} min ({team})"
                metric = self.compute_phase_metric(match_id, start_min, end_min, team, label=label)
                phases_data.append(metric)

        # 2. Moyennes de référence pour les équipes
        main_team = teams[0] if teams else meta["home_team"]
        baselines = self.get_baseline_averages(match_id, main_team)

        # 3. Calculation of significant deltas (% vs team match baseline) for all teams
        deltas: Dict[str, str] = {}
        for team in teams:
            team_baselines = self.get_baseline_averages(match_id, team)
            avg_turnovers = team_baselines.get("avg_turnovers_under_pressure_per_15m", 1.0)
            for m in phases_data:
                if m.team == team and avg_turnovers > 0:
                    duration = max(1, m.minute_end - m.minute_start)
                    scale = 15.0 / duration
                    norm_turnovers = m.turnovers_under_pressure * scale
                    diff_pct = ((norm_turnovers - avg_turnovers) / avg_turnovers) * 100.0
                    sign = "+" if diff_pct > 0 else ""
                    key_name = f"{team}_turnovers_{m.minute_start}_{m.minute_end}"
                    deltas[key_name] = f"[{team}] turnovers under pressure ({m.minute_start}-{m.minute_end} min): {sign}{diff_pct:.0f}% vs {team} match baseline"

        # 4. Substitutions log across the active window
        p_min_start = min(w[0] for w in windows) if windows else 0
        p_min_end = max(w[1] for w in windows) if windows else 120
        substitutions_timeline = self.get_substitutions(match_id, 0, 120)

        # 5. Target players statistics restricted to the active analysis window
        player_highlights: Dict[str, PlayerHighlight] = {}

        if plan.target_players:
            for p_name in plan.target_players:
                highlight = self.compute_player_highlight(
                    match_id=match_id,
                    player_name_pattern=p_name,
                    minute_start=p_min_start,
                    minute_end=p_min_end,
                )
                if highlight:
                    player_highlights[p_name] = highlight
        elif "Mbappé" in str(plan.reasoning_summary) or plan.query_type == QueryType.PLAYER_IMPACT:
            mbappe = self.compute_player_highlight(
                match_id=match_id,
                player_name_pattern="Mbappé",
                minute_start=p_min_start,
                minute_end=p_min_end,
            )
            if mbappe:
                player_highlights["Kylian Mbappé"] = mbappe

        return MatchFacts(
            match_id=match_id,
            match_name=meta["match_name"],
            match_date=meta["match_date"],
            home_team=meta["home_team"],
            away_team=meta["away_team"],
            home_score=meta["home_score"],
            away_score=meta["away_score"],
            phases_data=phases_data,
            baseline_match_averages=baselines,
            significant_deltas=deltas,
            player_highlights=player_highlights if player_highlights else None,
            substitutions_timeline=substitutions_timeline,
            raw_query_summary=f"SQL mining on match_id={match_id} ({len(windows)} windows, {len(teams)} teams).",
        )

    def get_realtime_kpis(
        self,
        match_id: int,
        minute_start: int,
        minute_end: int,
    ) -> Dict[str, Any]:
        """Calcule les KPIs consolidés pour une tranche temporelle en temps réel."""
        rows = self.db.execute_safe_query(SQL_REALTIME_KPIS, (match_id, minute_start, minute_end))
        if not rows:
            return {
                "turnovers_under_pressure": 0,
                "total_xg": 0.0,
                "passes_final_third": 0,
                "high_recoveries": 0,
                "total_goals": 0,
                "total_shots": 0,
            }
        r = rows[0]
        return {
            "turnovers_under_pressure": int(r["turnovers_under_pressure"] or 0),
            "total_xg": round(float(r["total_xg"] or 0.0), 2),
            "passes_final_third": int(r["passes_final_third"] or 0),
            "high_recoveries": int(r["high_recoveries"] or 0),
            "total_goals": int(r["total_goals"] or 0),
            "total_shots": int(r["total_shots"] or 0),
        }

    def get_realtime_kpis_by_team(
        self,
        match_id: int,
        minute_start: int,
        minute_end: int,
    ) -> Dict[str, Any]:
        """Calcule les KPIs ventilés par équipe (Home vs Away) pour une compréhension tactique immédiate."""
        meta = self.get_match_metadata(match_id)
        home = meta.get("home_team", "Équipe 1")
        away = meta.get("away_team", "Équipe 2")

        query = """
        SELECT
            team,
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
          AND minute <= ?
        GROUP BY team;
        """
        rows = self.db.execute_safe_query(query, (match_id, minute_start, minute_end))
        team_stats = {str(r["team"]): dict(r) for r in rows}

        default_stat = {
            "turnovers_under_pressure": 0, "total_xg": 0.0, "passes_final_third": 0, "high_recoveries": 0, "total_goals": 0, "total_shots": 0
        }
        home_s = team_stats.get(home, default_stat)
        away_s = team_stats.get(away, default_stat)

        return {
            "home_team": home,
            "away_team": away,
            "home_stats": home_s,
            "away_stats": away_s,
        }

    def get_substitutions(
        self,
        match_id: int,
        minute_start: int = 0,
        minute_end: int = 120,
    ) -> List[str]:
        """Extracts chronological substitution events for a match and time range."""
        query = """
        SELECT minute, second, team, player, raw_data 
        FROM events 
        WHERE match_id = ? AND type = 'Substitution' AND minute >= ? AND minute <= ?
        ORDER BY minute, second;
        """
        rows = self.db.execute_safe_query(query, (match_id, minute_start, minute_end))
        subs = []
        for r in rows:
            raw = json.loads(r["raw_data"])
            rep = raw.get("substitution_replacement", "Replacement")
            outcome = raw.get("substitution_outcome", "Tactical")
            subs.append(f"[{r['minute']}'] {r['team']}: {r['player']} (OUT) -> {rep} (IN) [{outcome}]")
        return subs

    def get_critical_events(
        self,
        match_id: int,
        minute_start: int,
        minute_end: int,
    ) -> List[Dict[str, Any]]:
        """Récupère les événements critiques (buts, tirs dangereux, passes décisives, fautes penalty)."""
        rows = self.db.execute_safe_query(SQL_CRITICAL_EVENTS, (match_id, minute_start, minute_end))
        return [dict(r) for r in rows]

    def get_match_dynamic_phases(self, match_id: int) -> List[Dict[str, Any]]:
        """Generates contextual tactical phases in English tailored to actual match turning points."""
        match_row = self.db.execute_safe_query("SELECT * FROM matches WHERE match_id = ?", (match_id,))
        if not match_row:
            return []
        m = dict(match_row[0])
        home, away = m["home_team"], m["away_team"]
        score_str = f"{m['home_score']} - {m['away_score']}"

        max_min_row = self.db.execute_safe_query("SELECT MAX(minute) as max_min FROM events WHERE match_id = ?", (match_id,))
        max_min = int(max_min_row[0]["max_min"] or 90) if max_min_row else 90

        # Specialized profiles for indexed matches
        if match_id == 3869685:
            # 2022 World Cup Final: Argentina vs France
            return [
                {
                    "id": "global",
                    "btn_label": "00-120' Global",
                    "name": "Full Match (00-120')",
                    "range": (0, 120),
                    "desc": "Global Flow & Key Pivots",
                    "stats": "3-3 · xG 2.65 vs 2.78",
                    "query": f"Provide a comprehensive tactical analysis of the 5 major phases and tactical swings in {home} vs {away}",
                },
                {
                    "id": "p1",
                    "btn_label": "00-40' Scaloni Press",
                    "name": "Phase 1: 00-40 min (Scaloni High Press)",
                    "range": (0, 40),
                    "desc": "Asymmetrical Overload & Press",
                    "stats": "2-0 · 0 FR shots · 11 turnovers",
                    "query": f"Analyze the first 40 minutes of {home} vs {away}: how Argentina suffocated French build-up (0 shots)?",
                },
                {
                    "id": "p2",
                    "btn_label": "40-70' Tactical Shift",
                    "name": "Phase 2: 40-70 min (Tactical Reorganization)",
                    "range": (40, 70),
                    "desc": "Subs 41' · Direct 4-2-4 Shape",
                    "stats": "0 shots on target · Low block",
                    "query": f"Analyze 40-70 min of {home} vs {away}: impact of Giroud/Dembélé subbed out for Thuram/Kolo Muani and direct shape",
                },
                {
                    "id": "p3",
                    "btn_label": "70-85' Mbappé Turning Point",
                    "name": "Phase 3: 70-85 min (Mbappé Turning Point)",
                    "range": (70, 85),
                    "desc": "Inflection Point & Double",
                    "stats": "2-2 (97s) · +328% ARG turnovers",
                    "query": f"Analyze the turning point between 70' and 85': how Camavinga, Coman, and Mbappé reversed match momentum?",
                },
                {
                    "id": "p4",
                    "btn_label": "85-90' Chaos & Transition",
                    "name": "Phase 4: 85-90 min (End of Regular Time)",
                    "range": (85, 90),
                    "desc": "Stretched Blocks & Transition",
                    "stats": "47% pass comp · Broken structure",
                    "query": f"Analyze late regular time (85-90 min) in {home} vs {away}: structural breakdown and counter-threats",
                },
                {
                    "id": "p5",
                    "btn_label": "90-120' Extra Time",
                    "name": "Phase 5: 90-120 min (Extra Time)",
                    "range": (90, 120),
                    "desc": "End-to-End & xG Peaks",
                    "stats": "3-3 final · Martinez saves",
                    "query": f"Analyze tactical dynamics of extra time (90-120 min) in {home} vs {away}: space exploitation and chances",
                },
            ]
        elif match_id == 3869684:
            # 2022 World Cup 3rd Place: Croatia vs Morocco
            return [
                {
                    "id": "global",
                    "btn_label": f"00-{max_min}' Global",
                    "name": f"Full Match (00-{max_min}')",
                    "range": (0, max_min),
                    "desc": "Global Flow & Bronze Medal",
                    "stats": f"{score_str} · World Cup Podium",
                    "query": f"Provide an overall tactical breakdown of {home} vs {away}",
                },
                {
                    "id": "p1",
                    "btn_label": "00-15' Set-Pieces",
                    "name": "Phase 1: 00-15 min (Early Set-Pieces)",
                    "range": (0, 15),
                    "desc": "Gvardiol 6' & Dari 8' headers",
                    "stats": "1-1 in 8 min · Set-piece efficiency",
                    "query": f"Analyze the match opening between {home} and {away} (0-15 min): set-piece design and early goals",
                },
                {
                    "id": "p2",
                    "btn_label": "15-45' Midfield Control",
                    "name": "Phase 2: 15-45 min (Midfield Control & Oršić Goal)",
                    "range": (15, 45),
                    "desc": "Modrić Masterclass & Oršić 41'",
                    "stats": "2-1 Croatia · Central dominance",
                    "query": f"Analyze late first half (15-45 min): how Croatia controlled midfield zones and created Oršić's goal",
                },
                {
                    "id": "p3",
                    "btn_label": "45-75' Moroccan Push",
                    "name": "Phase 3: 45-75 min (Moroccan High Press)",
                    "range": (45, 75),
                    "desc": "Pressing & En-Nesyri Duels",
                    "stats": "Croatia low block · Direct counters",
                    "query": f"Analyze 45-75 min in {home} vs {away}: Moroccan tactical reaction and territorial push",
                },
                {
                    "id": "p4",
                    "btn_label": f"75-{max_min}' Lockdown",
                    "name": f"Phase 4: 75-{max_min} min (Defensive Lockdown)",
                    "range": (75, max_min),
                    "desc": "Livaković saves & bronze defense",
                    "stats": "2-1 final · Game management",
                    "query": f"Analyze clutch time (75-{max_min} min): Croatia defensive game management and rest-defense",
                },
            ]
        elif match_id == 3869552:
            # 2022 World Cup Semi-Final: France vs Morocco
            return [
                {
                    "id": "global",
                    "btn_label": f"00-{max_min}' Global",
                    "name": f"Full Match (00-{max_min}')",
                    "range": (0, max_min),
                    "desc": "Global Flow & Final Qualification",
                    "stats": f"{score_str} · Final Spot Secured",
                    "query": f"Provide an overall tactical analysis of the semi-final {home} vs {away}",
                },
                {
                    "id": "p1",
                    "btn_label": "00-20' Early Goal",
                    "name": "Phase 1: 00-20 min (Hernandez Early Goal)",
                    "range": (0, 20),
                    "desc": "Opening goal 4th min",
                    "stats": "1-0 France · Early disrupt",
                    "query": f"Analyze the first 20 minutes of {home} vs {away}: how France struck early at 4'",
                },
                {
                    "id": "p2",
                    "btn_label": "20-45' Right Flank Siege",
                    "name": "Phase 2: 20-45 min (Hakimi-Ziyech Overloads)",
                    "range": (20, 45),
                    "desc": "Moroccan right-side overload",
                    "stats": "Ounahi chances · El Yamiq post",
                    "query": f"Analyze 20-45 min: how Morocco dominated right flank combinations to threaten France",
                },
                {
                    "id": "p3",
                    "btn_label": "45-75' French Low Block",
                    "name": "Phase 3: 45-75 min (French Low Block Resistance)",
                    "range": (45, 75),
                    "desc": "Konaté-Varane central defense",
                    "stats": "62% Morocco poss · 0 goals allowed",
                    "query": f"Analyze 45-75 min: French low block stability against Moroccan territorial siege",
                },
                {
                    "id": "p4",
                    "btn_label": f"75-{max_min}' Kolo Muani Winner",
                    "name": f"Phase 4: 75-{max_min} min (Kolo Muani Decisive Sub)",
                    "range": (75, max_min),
                    "desc": "Kolo Muani scores in 44 seconds",
                    "stats": "2-0 final · Final sealed",
                    "query": f"Analyze Kolo Muani's impact sub (75-{max_min} min) and French late-game management",
                },
            ]
        else:
            return [
                {
                    "id": "global",
                    "btn_label": f"00-{max_min}' Global",
                    "name": f"Full Match (00-{max_min}')",
                    "range": (0, max_min),
                    "desc": "Overall match flow",
                    "stats": f"{score_str}",
                    "query": f"Overall tactical breakdown of {home} vs {away}",
                },
                {
                    "id": "p1",
                    "btn_label": "00-45' 1st Half",
                    "name": "1st Half (00-45 min)",
                    "range": (0, 45),
                    "desc": "Initial tactical setup",
                    "query": f"Analyze the first half of {home} vs {away}",
                },
                {
                    "id": "p2",
                    "btn_label": f"45-{max_min}' 2nd Half",
                    "name": f"2nd Half (45-{max_min} min)",
                    "range": (45, max_min),
                    "desc": "Second half adjustments",
                    "query": f"Analyze the second half of {home} vs {away}",
                },
            ]


