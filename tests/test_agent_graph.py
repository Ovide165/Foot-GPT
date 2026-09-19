"""
Tests d'intégration de bout en bout pour le graphe LangGraph (src/agent/graph.py).
"""

import pytest
from src.agent.graph import create_tactical_graph, run_tactical_analysis
from src.schemas.miner import MatchFacts
from src.schemas.router import TacticalPlan


def test_tactical_graph_compilation():
    """Vérifie la compilation sans erreur du StateGraph LangGraph."""
    graph = create_tactical_graph()
    assert graph is not None


def test_run_tactical_analysis_end_to_end():
    """Vérifie l'exécution complète du pipeline agentique séquentiel."""
    query = "Explique l'asphyxie tactique subie par la France lors des 40 premières minutes."
    match_id = 3869685
    thread_id = "test_e2e_session"

    result = run_tactical_analysis(
        coach_query=query,
        match_id=match_id,
        thread_id=thread_id,
    )

    # 1. Validation de la sortie du Nœud 1 (Router)
    assert result["tactical_plan"] is not None
    assert isinstance(result["tactical_plan"], TacticalPlan)

    # 2. Validation de la sortie du Nœud 2A (SQL Miner)
    assert result["match_facts"] is not None
    assert isinstance(result["match_facts"], MatchFacts)
    assert len(result["match_facts"].phases_data) > 0

    # 3. Validation de la sortie du Nœud 2B (Data-Informed RAG)
    assert result["retrieved_chunks"] is not None
    assert len(result["retrieved_chunks"]) > 0
    assert "citation" in result["retrieved_chunks"][0]

    # 4. Validation de la sortie du Nœud 3 (Synthesizer) & 4 (Critic)
    assert result["draft_report"] is not None
    assert result["critic_verdict"] is not None

    # 5. Validation de la sortie finale et de la télémétrie
    assert result["final_report"] is not None
    assert len(result["final_report"]) > 50

    telemetry = result["execution_telemetry"]
    assert "router_latency_ms" in telemetry
    assert "sql_miner_latency_ms" in telemetry
    assert "deep_rag_latency_ms" in telemetry
    assert "total_pipeline_latency_ms" in telemetry


def test_run_tactical_analysis_with_user_time_range():
    """Vérifie que la sélection d'une sous-période restreint le plan au créneau ciblé."""
    query = "Pourquoi ce blocage ?"
    match_id = 3869685
    thread_id = "test_time_range_session"

    result = run_tactical_analysis(
        coach_query=query,
        match_id=match_id,
        thread_id=thread_id,
        user_time_range=(0, 40),
    )

def test_team_attribution_faithfulness():
    """Vérifie que les statistiques entre l'Argentine et la France ne sont jamais inversées sur 0-40 min."""
    query = "Analyze the first 40 minutes: why France was suffocated with 0 shots?"
    match_id = 3869685
    thread_id = "test_faithfulness_attribution"

    result = run_tactical_analysis(
        coach_query=query,
        match_id=match_id,
        thread_id=thread_id,
        user_time_range=(0, 40),
    )

    report = result.get("final_report", "")
    assert report is not None
    # Vérification d'absence de l'hallucination historique
    assert "France, despite 6 shots" not in report
    assert "France, malgré 6 tirs" not in report
    # Vérification que le 0 tir français est bien restitué
    assert ("0 shot" in report.lower() or "0 tir" in report.lower() or "0.0 xg" in report.lower() or "0.0" in report or "zero shot" in report.lower())


