"""
Tests de la logique applicative (cache des rapports, restitution complète, verdict), sans Streamlit
ni appel LLM : le cache utilise un embedding factice et le graphe est remplace par un runner factice.
"""

from pathlib import Path

import numpy as np
import pytest

from src.app_service import analyze, is_cacheable, result_from_cache, store_in_cache
from src.cache.semantic_cache import SemanticCache
from src.data_mining.match_miner import MatchMiner
from src.schemas.critic import AuditAnomaly, VerificationVerdict
from src.schemas.router import QueryType, TacticalPlan

CHUNK = {"chunk_id": "c1", "content": "texte", "citation": "[A, 2014 - T]"}


def verdict(kind="PASS") -> VerificationVerdict:
    anomalies = [] if kind == "PASS" else [AuditAnomaly(
        category="numerical_hallucination", claim_in_text="12 shots", correction_guidance="Use 6 shots")]
    return VerificationVerdict(
        is_faithful=kind == "PASS", faithfulness_score=0.97 if kind == "PASS" else 0.4,
        is_fully_cited=True, is_anchored=True, citation_coverage_score=1.0,
        anomalies=anomalies, verdict=kind)


@pytest.fixture(scope="module")
def match_facts():
    plan = TacticalPlan(query_type=QueryType.DIAGNOSTIC_SEQUENCE, time_windows=[(0, 40)],
                        target_teams=["Argentina", "France"])
    return MatchMiner().build_match_facts(3869685, plan)


@pytest.fixture
def cache(monkeypatch):
    c = SemanticCache()
    monkeypatch.setattr(c, "_get_embedding", lambda text: np.array([1.0, 0.0]))
    return c


def result(kind="PASS", facts=None, report="### Part 1"):
    return {"final_report": report, "critic_verdict": verdict(kind), "match_facts": facts,
            "retrieved_chunks": [CHUNK], "sources_sufficient": True, "iteration_count": 1,
            "execution_telemetry": {"critic_faithfulness_score": 0.97}}


def test_app_does_not_reload_the_cache_module():
    source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert "reload(src.cache.semantic_cache)" not in source


def test_only_pass_reports_are_cacheable():
    assert is_cacheable(result("PASS"))
    assert not is_cacheable(result("FAIL"))
    assert not is_cacheable(result("PASS", report=""))
    assert not is_cacheable({"final_report": "x", "critic_verdict": None})


def test_failed_report_is_not_stored(cache):
    assert store_in_cache(cache, "q", 1, (0, 40), result("FAIL")) is False
    assert cache.count() == 0


def test_hit_restores_facts_chunks_and_verdict(cache, match_facts):
    assert store_in_cache(cache, "q", 1, (0, 40), result("PASS", facts=match_facts))
    restored = result_from_cache(cache.get("q", 1, time_range=(0, 40)))
    assert restored["match_facts"] == match_facts
    assert restored["retrieved_chunks"] == [CHUNK]
    assert restored["critic_verdict"].verdict == "PASS"
    assert restored["sources_sufficient"] is True
    assert restored["from_cache"] is True


def test_analyze_runs_once_then_serves_from_cache(cache, match_facts):
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return result("PASS", facts=match_facts)

    first = analyze("q", 1, (0, 40), cache=cache, runner=runner)
    second = analyze("q", 1, (0, 40), cache=cache, runner=runner)
    assert len(calls) == 1
    assert first["from_cache"] is False and second["from_cache"] is True
    assert second["match_facts"] == match_facts and second["retrieved_chunks"] == [CHUNK]


def test_analyze_reruns_after_a_failed_report(cache):
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return result("FAIL")

    analyze("q", 1, (0, 40), cache=cache, runner=runner)
    analyze("q", 1, (0, 40), cache=cache, runner=runner)
    assert len(calls) == 2


def test_global_and_window_reports_do_not_share_cache_entries(cache):
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return result("PASS")

    analyze("q", 1, (0, 90), is_global_view=True, cache=cache, runner=runner)
    analyze("q", 1, (0, 90), is_global_view=False, cache=cache, runner=runner)
    assert len(calls) == 2


from src.app_service import NOT_EVALUATED, faithfulness_label, verdict_view


def test_pass_verdict_view_shows_score():
    view = verdict_view(result("PASS"))
    assert view["status"] == "passed"
    assert "PASS" in view["headline"]
    assert view["faithfulness"] == "97%"


def test_report_served_after_failures_carries_a_clear_warning_and_anomalies():
    failed = {**result("FAIL"), "iteration_count": 2,
              "execution_telemetry": {"critic_faithfulness_score": 0.4}}
    view = verdict_view(failed)
    assert view["status"] == "failed_after_retries"
    assert view["headline"].startswith("WARNING")
    assert "FAIL after 2 attempts" in view["headline"]
    assert view["anomalies"] == ["numerical_hallucination: Use 6 shots"]
    assert view["faithfulness"] == "40%"


def test_missing_verdict_is_not_evaluated():
    view = verdict_view({"final_report": "x"})
    assert view["status"] == "not_evaluated"
    assert view["faithfulness"] == NOT_EVALUATED


def test_missing_faithfulness_has_no_default_value():
    assert faithfulness_label({}) == NOT_EVALUATED
    assert faithfulness_label({"critic_faithfulness_score": None}) == NOT_EVALUATED
    assert faithfulness_label({"critic_faithfulness_score": 0.0}) == "0%"   # 0 est une vraie note
    assert faithfulness_label({"execution_telemetry": {"critic_faithfulness_score": 0.5}}) == "50%"


def test_no_hardcoded_faithfulness_default_in_ui_or_evaluation():
    root = Path(__file__).resolve().parent.parent
    for name in ("src/ui/components/admin_dashboard.py", "src/evaluation/ragas_eval.py",
                 "src/evaluation/benchmark_comparison.py"):
        assert "else 0.95" not in (root / name).read_text(encoding="utf-8"), name
        assert "faithfulness_score\", 0.95" not in (root / name).read_text(encoding="utf-8"), name


def test_app_displays_the_verdict_panel():
    source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert "render_verdict_panel(verdict_view(res))" in source
