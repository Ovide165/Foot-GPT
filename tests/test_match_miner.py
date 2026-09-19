"""
Tests unitaires pour le moteur de données déterministe (src/data_mining/).
"""

import pytest

from src.data_mining.db_connection import ReadOnlyDBConnection, SQLSecurityError
from src.data_mining.match_miner import MatchMiner
from src.schemas.router import QueryType, TacticalPlan


def test_sql_security_validator():
    """Vérifie que la validation AST bloque les requêtes destructrices."""
    # Requêtes autorisées
    ReadOnlyDBConnection.validate_safe_query("SELECT * FROM matches LIMIT 5;")
    ReadOnlyDBConnection.validate_safe_query("WITH cte AS (SELECT 1) SELECT * FROM cte;")
    ReadOnlyDBConnection.validate_safe_query("SELECT count(*) FROM events WHERE match_id = 3869685;")

    # Requêtes interdites (doivent lever SQLSecurityError)
    with pytest.raises(SQLSecurityError):
        ReadOnlyDBConnection.validate_safe_query("DROP TABLE events;")

    with pytest.raises(SQLSecurityError):
        ReadOnlyDBConnection.validate_safe_query("INSERT INTO matches VALUES (1, '2022-01-01', 'A', 'B', 0, 0);")

    with pytest.raises(SQLSecurityError):
        ReadOnlyDBConnection.validate_safe_query("DELETE FROM players WHERE player_id = 1;")

    with pytest.raises(SQLSecurityError):
        ReadOnlyDBConnection.validate_safe_query("UPDATE events SET type = 'Goal';")

    with pytest.raises(SQLSecurityError):
        ReadOnlyDBConnection.validate_safe_query("PRAGMA table_info(events);")


def test_match_metadata_extraction():
    """Vérifie l'extraction des métadonnées du match 3869685."""
    miner = MatchMiner()
    meta = miner.get_match_metadata(3869685)
    assert meta["match_id"] == 3869685
    assert meta["home_team"] == "Argentina"
    assert meta["away_team"] == "France"
    assert meta["home_score"] == 3
    assert meta["away_score"] == 3


def test_france_argentina_phase_1_metrics():
    """
    Vérifie la réalité statistique de la 1ère mi-temps (0-40 min) :
    La France n'a tenté aucun tir (0 tir, 0.0 xG).
    """
    miner = MatchMiner()
    france_p1 = miner.compute_phase_metric(3869685, 0, 40, "France")
    assert france_p1.shots_count == 0
    assert france_p1.goals_count == 0
    assert france_p1.passes_completed > 0
    assert france_p1.turnovers_under_pressure > 0

    argentina_p1 = miner.compute_phase_metric(3869685, 0, 40, "Argentina")
    assert argentina_p1.shots_count >= 5
    assert argentina_p1.goals_count >= 1
    assert argentina_p1.passes_completed > france_p1.passes_completed


def test_france_argentina_phase_3_mbappe_revival():
    """
    Vérifie la réalité statistique de la phase 70-85 min :
    La France inscrit 2 buts (doublé Mbappé 80' et 81').
    """
    miner = MatchMiner()
    france_p3 = miner.compute_phase_metric(3869685, 70, 85, "France")
    assert france_p3.goals_count == 2
    assert france_p3.shots_count >= 2
    assert france_p3.xg_sum > 0.8


def test_player_highlight_mbappe():
    """Vérifie l'extraction des faits individuels sur Kylian Mbappé."""
    miner = MatchMiner()
    mbappe = miner.compute_player_highlight(3869685, "Mbappé")
    assert mbappe is not None
    assert "Mbappé" in mbappe.player_name
    assert mbappe.team_name == "France"
    assert mbappe.goals >= 2
    assert len(mbappe.key_events_timeline) > 0


def test_build_match_facts_macro_plan():
    """Vérifie la construction globale d'un objet MatchFacts pour un plan macro."""
    miner = MatchMiner()
    plan = TacticalPlan(
        query_type=QueryType.MACRO_MATCH_FLOW,
        game_phases=["Organisation Offensive", "Transition Défensive"],
        time_windows=[(0, 40), (40, 70), (70, 85), (85, 90), (90, 120)],
        target_teams=["Argentina", "France"],
        target_players=["Mbappé"],
        key_metrics_needed=["turnovers_under_pressure", "xg"],
    )
    facts = miner.build_match_facts(3869685, plan)
    assert facts.match_id == 3869685
    # 5 fenêtres * 2 équipes = 10 métriques de phases
    assert len(facts.phases_data) == 10
    assert "avg_turnovers_under_pressure_per_15m" in facts.baseline_match_averages
    assert facts.player_highlights is not None
