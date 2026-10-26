"""
Tests du synthetiseur face a des sources suffisantes / insuffisantes (LLM factice, sans reseau).
"""

import sys

from langchain_core.messages import AIMessage

from src.agent.prompts import SYNTHESIZER_SYSTEM_PROMPT
from src.llm_factory import LLMFactory

# `src.agent.nodes` reexporte la fonction du meme nom : on recupere le module via sys.modules
import src.agent.nodes.synthesizer_node  # noqa: F401

synth_module = sys.modules["src.agent.nodes.synthesizer_node"]


class _CapturingLLM:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if self.fail:
            raise RuntimeError("service indisponible")
        return AIMessage(content="### Part 1: ok")


def _chunk():
    return {
        "chunk_id": "x_c1", "content": "Half-spaces are the channels between wing and centre.",
        "citation": "[Auteur A, 2014 - Titre A]",
    }


def _run(monkeypatch, state, fail=False):
    llm = _CapturingLLM(fail=fail)
    monkeypatch.setattr(LLMFactory, "get_reasoning_model", staticmethod(lambda **kw: llm))
    out = synth_module.synthesizer_node({"coach_query": "q", "execution_telemetry": {}, **state})
    prompt = llm.messages[1].content if llm.messages else ""
    return out, prompt


def test_prompt_no_longer_forces_two_citations():
    assert "UP TO 2" in SYNTHESIZER_SYSTEM_PROMPT
    assert "INSUFFICIENT SOURCES" in SYNTHESIZER_SYSTEM_PROMPT
    assert "Provide 2 theoretical principles" not in SYNTHESIZER_SYSTEM_PROMPT


def test_sufficient_sources_are_injected(monkeypatch):
    _, prompt = _run(monkeypatch, {"retrieved_chunks": [_chunk()], "sources_sufficient": True})
    assert "[Auteur A, 2014 - Titre A]" in prompt
    assert "NO RELEVANT SOURCE FOUND" not in prompt


def test_insufficient_sources_inject_explicit_marker_and_no_excerpt(monkeypatch):
    _, prompt = _run(monkeypatch, {"retrieved_chunks": [_chunk()], "sources_sufficient": False})
    assert "NO RELEVANT SOURCE FOUND" in prompt
    assert "[Auteur A, 2014 - Titre A]" not in prompt


def test_fallback_draft_only_cites_retrieved_sources(monkeypatch):
    out, _ = _run(monkeypatch, {"retrieved_chunks": [_chunk()], "sources_sufficient": True}, fail=True)
    assert "[Auteur A, 2014 - Titre A]" in out["draft_report"]
    assert "Bauer" not in out["draft_report"]


def test_fallback_draft_states_limitation_without_sources(monkeypatch):
    out, _ = _run(monkeypatch, {"retrieved_chunks": [], "sources_sufficient": False}, fail=True)
    assert "No sufficiently relevant source" in out["draft_report"]
    assert "[" not in out["draft_report"].split("### Part 2")[1].split("### Part 3")[0]
