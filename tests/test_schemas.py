"""
Tests unitaires pour les schémas Pydantic v2 (src/schemas/).
"""

import pytest
from pydantic import ValidationError

from src.schemas.router import QueryType, TacticalPlan
from src.schemas.miner import MatchFacts, MatchPhaseMetric, PlayerHighlight
from src.schemas.critic import AuditAnomaly, VerificationVerdict


def test_tactical_plan_valid():
    """Vérifie la création et la sérialisation d'un TacticalPlan."""
    plan = TacticalPlan(
        query_type=QueryType.DIAGNOSTIC_SEQUENCE,
        game_phases=["Transition Défensive"],
        time_windows=[(70, 85)],
        target_teams=["France", "Argentina"],
        target_players=["Kylian Mbappé Lottin"],
        spatial_zones=["left_half_space", "zone_14"],
        key_metrics_needed=["turnovers_under_pressure", "passes_final_third"],
        theoretical_topics=["Rest-Defense", "Cover Shadow"],
        reasoning_summary="Analyse du réveil offensif français entre 70' et 85'.",
    )
    assert plan.query_type == QueryType.DIAGNOSTIC_SEQUENCE
    assert len(plan.time_windows) == 1
    assert plan.time_windows[0] == (70, 85)
    assert "France" in plan.target_teams

    # Sérialisation JSON
    json_data = plan.model_dump_json()
    assert "DIAGNOSTIC_SEQUENCE" in json_data or "diagnostic_sequence" in json_data


def test_match_facts_and_metrics():
    """Vérifie la création de MatchPhaseMetric et MatchFacts."""
    metric = MatchPhaseMetric(
        phase_label="70-85 min (France)",
        minute_start=70,
        minute_end=85,
        team="France",
        total_events=249,
        passes_attempted=74,
        passes_completed=57,
        pass_accuracy_pct=77.0,
        passes_final_third=13,
        passes_zone_14=4,
        shots_count=3,
        shots_on_target=2,
        goals_count=2,
        xg_sum=1.62,
        turnovers_under_pressure=9,
        high_recoveries_count=6,
    )
    assert metric.pass_accuracy_pct == 77.0
    assert metric.goals_count == 2

    facts = MatchFacts(
        match_id=3869685,
        match_name="Argentina 3 - 3 France",
        match_date="2022-12-18",
        home_team="Argentina",
        away_team="France",
        home_score=3,
        away_score=3,
        phases_data=[metric],
        baseline_match_averages={"avg_turnovers_under_pressure_per_15m": 1.4},
        significant_deltas={"turnovers_under_pressure_70_85": "+328% vs moyenne match"},
    )
    assert facts.match_id == 3869685
    assert len(facts.phases_data) == 1
    assert "turnovers_under_pressure_70_85" in facts.significant_deltas


def test_verification_verdict():
    """Vérifie le verdict d'audit du Critic Node."""
    verdict = VerificationVerdict(
        is_faithful=True,
        faithfulness_score=1.0,
        is_fully_cited=True,
        citation_coverage_score=0.95,
        anomalies=[],
        verdict="PASS",
    )
    assert verdict.verdict == "PASS"
    assert verdict.is_faithful is True

    # Test avec anomalie
    anomaly = AuditAnomaly(
        category="numerical_hallucination",
        claim_in_text="France completed 12 passes into final third",
        truth_in_facts="MatchFacts states 13 passes",
        correction_guidance="Corrige le chiffre à 13.",
    )
    fail_verdict = VerificationVerdict(
        is_faithful=False,
        faithfulness_score=0.85,
        is_fully_cited=True,
        citation_coverage_score=1.0,
        anomalies=[anomaly],
        feedback_for_synthesizer="Corriger le volume de passes dans le dernier tiers.",
        verdict="FAIL",
    )
    assert fail_verdict.verdict == "FAIL"
    assert len(fail_verdict.anomalies) == 1
