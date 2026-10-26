"""
Le mode macro / micro depend d'un indicateur explicite (phase « Global »), plus de la duree de la tranche.
"""

import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import src.agent.nodes.router_node  # noqa: F401  (le paquet reexporte la fonction du meme nom)
import src.agent.nodes.synthesizer_node  # noqa: F401
from src.llm_factory import LLMFactory, MockChatModel
from src.schemas.router import QueryType

router_module = sys.modules["src.agent.nodes.router_node"]
synth_module = sys.modules["src.agent.nodes.synthesizer_node"]


@pytest.fixture(autouse=True)
def mock_llms(monkeypatch):
    monkeypatch.setattr(LLMFactory, "get_fast_model", staticmethod(lambda **kw: MockChatModel()))
    monkeypatch.setattr(LLMFactory, "get_reasoning_model", staticmethod(lambda **kw: MockChatModel()))


def route(user_time_range, is_global_view):
    state = {"coach_query": "q", "match_id": 3869685, "user_time_range": user_time_range,
             "is_global_view": is_global_view, "execution_telemetry": {}}
    return router_module.router_node(state)["tactical_plan"]


def test_global_view_keeps_the_macro_plan_even_for_a_short_match():
    plan = route((0, 90), is_global_view=True)       # 90 < 100 : ancien mode micro a tort
    assert plan.query_type == QueryType.MACRO_MATCH_FLOW
    assert plan.time_windows != [(0, 90)]


def test_selected_window_is_micro_whatever_its_length():
    for window in ((0, 40), (0, 90), (0, 120)):       # (0, 120) etait macro avant
        plan = route(window, is_global_view=False)
        assert plan.query_type == QueryType.DIAGNOSTIC_SEQUENCE
        assert plan.time_windows == [window]


def test_no_window_means_macro():
    assert route(None, is_global_view=False).query_type == QueryType.MACRO_MATCH_FLOW


class _CapturingLLM:
    def invoke(self, messages):
        self.prompt = messages[1].content
        return AIMessage(content="### Part 1: ok")


def synth_prompt(monkeypatch, user_time_range, is_global_view):
    llm = _CapturingLLM()
    monkeypatch.setattr(LLMFactory, "get_reasoning_model", staticmethod(lambda **kw: llm))
    from src.data_mining.match_miner import MatchMiner
    plan = route(user_time_range, is_global_view)
    facts = MatchMiner().build_match_facts(3869685, plan)
    synth_module.synthesizer_node({
        "coach_query": "q", "match_facts": facts, "retrieved_chunks": [], "sources_sufficient": False,
        "user_time_range": user_time_range, "is_global_view": is_global_view, "execution_telemetry": {},
    })
    return llm.prompt


def test_synthesizer_global_view_uses_full_match_context(monkeypatch):
    prompt = synth_prompt(monkeypatch, (0, 90), is_global_view=True)
    assert "ACTIVE TARGET TIMEFRAME" not in prompt
    assert "STRUCTURE DES PHASES TACTIQUES" in prompt


def test_synthesizer_selected_window_is_restricted(monkeypatch):
    prompt = synth_prompt(monkeypatch, (0, 120), is_global_view=False)
    assert "ACTIVE TARGET TIMEFRAME: 0'-120' MIN ONLY" in prompt


def test_graph_state_carries_the_flag_end_to_end():
    from src.agent.graph import run_tactical_analysis
    result = run_tactical_analysis("Analyse the whole match.", thread_id="g1", user_time_range=(0, 90), is_global_view=True)
    assert result["is_global_view"] is True
    assert result["tactical_plan"].query_type == QueryType.MACRO_MATCH_FLOW


def test_app_passes_the_global_phase_flag():
    source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert source.count('is_global_view=') >= 4
    assert "< 100" not in source
