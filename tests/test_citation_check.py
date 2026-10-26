"""
Tests de la verification programmatique des citations (module + noeud critique), sans reseau.
"""

import sys

from src.agent.prompts import CRITIC_SYSTEM_PROMPT
from src.llm_factory import LLMFactory, MockChatModel
from src.rag.citations import extract_citations, find_invalid_citations, normalize_citation
from src.schemas.critic import VerificationVerdict

import src.agent.nodes.critic_node  # noqa: F401

critic_module = sys.modules["src.agent.nodes.critic_node"]

ALLOWED = [
    "[Spielverlagerung Editorial Staff, 2014 - The Half-Spaces]",
    "[Pena, Touchette, 2012 - A network theory analysis of football strategies]",
]


def test_extract_citations_handles_multi_author_and_dedup():
    text = (
        "Fact A " + ALLOWED[0] + ". Fact B " + ALLOWED[1] + ". Again " + ALLOWED[0] + ". See [Part 1] and [x]."
    )
    assert extract_citations(text) == ALLOWED


def test_normalization_tolerates_case_spaces_and_dashes():
    assert normalize_citation("[A,  2014 – The  Half-Spaces]") == normalize_citation("[a, 2014 - the half-spaces]")


def test_exact_and_normalized_citations_are_valid():
    report = "x [spielverlagerung editorial staff, 2014 – The Half-Spaces] y"
    assert find_invalid_citations(report, ALLOWED) == []


def test_unknown_citation_is_invalid():
    report = "x [Bauer & Anzer, 2026 - Structural Pass Analysis] y " + ALLOWED[0]
    assert find_invalid_citations(report, ALLOWED) == ["[Bauer & Anzer, 2026 - Structural Pass Analysis]"]


def test_any_citation_invalid_when_no_source_provided():
    assert find_invalid_citations("see " + ALLOWED[0], []) == [ALLOWED[0]]


def _run_critic(monkeypatch, draft, chunks):
    monkeypatch.setattr(LLMFactory, "get_fast_model", staticmethod(lambda **kw: MockChatModel()))
    state = {"draft_report": draft, "match_facts": None, "retrieved_chunks": chunks, "execution_telemetry": {}}
    return critic_module.critic_node(state)


def test_critic_fails_on_citation_not_in_provided_chunks(monkeypatch):
    chunks = [{"citation": ALLOWED[0], "content": "text"}]
    out = _run_critic(monkeypatch, "Part 2 " + "[Bauer & Anzer, 2026 - Structural Pass Analysis]", chunks)
    verdict = out["critic_verdict"]
    assert verdict.verdict == "FAIL"
    assert verdict.is_fully_cited is False
    assert verdict.anomalies[0].category == "invalid_citation"
    assert "Bauer & Anzer" in out["critic_feedback"]
    assert ALLOWED[0] in out["critic_feedback"]  # le retour liste les citations autorisees


def test_critic_does_not_override_when_citations_are_valid(monkeypatch):
    chunks = [{"citation": ALLOWED[0], "content": "text"}]
    out = _run_critic(monkeypatch, "Part 2 " + ALLOWED[0], chunks)
    assert out["critic_verdict"].verdict == "PASS"
    assert out["execution_telemetry"]["critic_invalid_citations"] == 0


def test_critic_fails_any_citation_when_no_chunks(monkeypatch):
    out = _run_critic(monkeypatch, "Part 2 " + ALLOWED[0], [])
    assert out["critic_verdict"].verdict == "FAIL"
    assert "no source excerpt was provided" in out["critic_feedback"]


def test_critic_prompt_mentions_programmatic_check_and_insufficient_sources():
    assert "SOURCES_SUFFICIENT" in CRITIC_SYSTEM_PROMPT
    assert "programmatically" in CRITIC_SYSTEM_PROMPT


class _UnanchoredLLM(MockChatModel):
    """Juge factice qui trouve le rapport non ancre mais le laisse en PASS."""

    def with_structured_output(self, schema):
        class _Runner:
            def invoke(self, messages):
                return VerificationVerdict(
                    is_faithful=True, faithfulness_score=0.98, is_fully_cited=True, is_anchored="false",
                    citation_coverage_score=0.95, anomalies=[], verdict="PASS",
                )
        return _Runner()


def test_unanchored_report_cannot_pass(monkeypatch):
    monkeypatch.setattr(LLMFactory, "get_fast_model", staticmethod(lambda **kw: _UnanchoredLLM()))
    chunks = [{"citation": ALLOWED[0], "content": "text"}]
    state = {"draft_report": "Part 2 " + ALLOWED[0], "match_facts": None, "retrieved_chunks": chunks, "execution_telemetry": {}}
    out = critic_module.critic_node(state)
    assert out["critic_verdict"].is_anchored is False
    assert out["critic_verdict"].verdict == "FAIL"
    assert "START with a concrete match fact" in out["critic_feedback"]


def test_critic_prompt_and_schema_agree_on_is_anchored():
    assert "is_anchored" in CRITIC_SYSTEM_PROMPT
    assert "is_anchored" in VerificationVerdict.model_fields


def test_critic_receives_full_chunk_without_truncation(monkeypatch):
    seen = {}

    class _Spy(MockChatModel):
        def with_structured_output(self, schema):
            outer = super().with_structured_output(schema)

            class _Runner:
                def invoke(self, messages):
                    seen["prompt"] = messages[1].content
                    return outer.invoke(messages)
            return _Runner()

    monkeypatch.setattr(LLMFactory, "get_fast_model", staticmethod(lambda **kw: _Spy()))
    chunk = {"citation": ALLOWED[0], "content": "debut " + "mot " * 1000 + "FIN_DU_CHUNK"}
    critic_module.critic_node({"draft_report": "r", "match_facts": None, "retrieved_chunks": [chunk], "execution_telemetry": {}})
    assert "FIN_DU_CHUNK" in seen["prompt"]
