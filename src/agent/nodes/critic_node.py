"""
Nœud 4 : Critic Evaluator Node (Audit factuel anti-hallucination & vérification des citations).
"""

import time
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from src.agent.prompts import CRITIC_SYSTEM_PROMPT
from src.llm_factory import LLMFactory
from src.rag.citations import find_invalid_citations
from src.schemas.critic import AuditAnomaly, VerificationVerdict
from src.schemas.miner import MatchFacts
from src.schemas.state import TacticalAgentState


def audit_citations(draft: str, retrieved_chunks: List[Dict[str, Any]]) -> List[AuditAnomaly]:
    """Controle programmatique : toute citation du rapport doit etre celle d'un chunk fourni."""
    allowed = [c.get("citation", "") for c in retrieved_chunks]
    anomalies: List[AuditAnomaly] = []
    for citation in find_invalid_citations(draft, allowed):
        if allowed:
            guidance = (
                f"Citation {citation} does not match any excerpt provided to the synthesizer. "
                f"Remove it or replace it with exactly one of: {'; '.join(a for a in allowed if a)}."
            )
        else:
            guidance = (
                f"Citation {citation} is not allowed: no source excerpt was provided. "
                "Remove every citation and state that no sufficiently relevant source exists."
            )
        anomalies.append(
            AuditAnomaly(
                category="invalid_citation",
                claim_in_text=citation,
                truth_in_facts=None,
                correction_guidance=guidance,
            )
        )
    return anomalies


def critic_node(state: TacticalAgentState) -> Dict[str, Any]:
    """
    Évalue la conformité mathématique (Faithfulness) et la couverture
    des citations du rapport rédigé par le Synthesizer.
    """
    t_start = time.perf_counter()
    draft = state.get("draft_report", "")
    match_facts: MatchFacts = state.get("match_facts")  # type: ignore
    retrieved_chunks = state.get("retrieved_chunks") or []

    llm = LLMFactory.get_fast_model(temperature=0.0)
    structured_llm = llm.with_structured_output(VerificationVerdict)

    facts_summary = match_facts.model_dump_json() if match_facts else "{}"
    chunks_summary = "\n".join(
        [f"- Citation: {c.get('citation')}\n  Content: {c.get('content', '')[:300].strip()}..." for c in retrieved_chunks]
    ) if retrieved_chunks else "[]"

    messages = [
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"REPORT TO AUDIT:\n{draft}\n\n"
                f"GROUND TRUTH MATCH_FACTS:\n{facts_summary}\n\n"
                f"SOURCES_SUFFICIENT: {bool(retrieved_chunks)}\n\n"
                f"AVAILABLE_CITATIONS & THEORETICAL EXCERPTS:\n{chunks_summary}"
            )
        ),
    ]

    try:
        verdict: VerificationVerdict = structured_llm.invoke(messages)
    except Exception as e:
        # Ne PAS valider en cas d'échec technique : consigner l'erreur et forcer un FAIL sécurisé
        verdict = VerificationVerdict(
            is_faithful=False,
            faithfulness_score=0.0,
            is_fully_cited=False,
            is_anchored=False,
            citation_coverage_score=0.0,
            anomalies=[
                AuditAnomaly(
                    category="formatting_error",
                    claim_in_text="Audit execution interrupted",
                    truth_in_facts=None,
                    correction_guidance=f"Critic audit evaluation failed due to service error: {str(e)[:150]}",
                )
            ],
            feedback_for_synthesizer=f"Critic audit evaluation failed due to service error: {str(e)[:150]}",
            verdict="FAIL",
        )

    # Golden Anchoring Rule : un rapport non ancre ne peut pas etre valide, la boucle de
    # correction (should_continue_after_critic) repart alors sur le synthetiseur
    if not verdict.is_anchored:
        anomalies = list(verdict.anomalies)
        if not any(a.category == "unanchored_principle" for a in anomalies):
            anomalies.append(
                AuditAnomaly(
                    category="unanchored_principle",
                    claim_in_text="Part 2 principle without a preceding match fact",
                    truth_in_facts=None,
                    correction_guidance=(
                        "Each theoretical principle in Part 2 must START with a concrete match fact "
                        "(minute, player, zone or metric from MATCH_FACTS) before the theory and its citation."
                    ),
                )
            )
        verdict = verdict.model_copy(update={"verdict": "FAIL", "anomalies": anomalies})

    # Verification deterministe des citations, independante du jugement du LLM
    citation_anomalies = audit_citations(draft, retrieved_chunks)
    if citation_anomalies:
        verdict = verdict.model_copy(
            update={
                "verdict": "FAIL",
                "is_fully_cited": False,
                "anomalies": citation_anomalies + list(verdict.anomalies),
                "feedback_for_synthesizer": "\n".join(a.correction_guidance for a in citation_anomalies),
            }
        )

    t_latency = round((time.perf_counter() - t_start) * 1000, 1)
    telemetry = state.get("execution_telemetry") or {}
    telemetry["critic_invalid_citations"] = len(citation_anomalies)
    telemetry["critic_latency_ms"] = t_latency
    telemetry["critic_faithfulness_score"] = verdict.faithfulness_score

    feedback = None
    if verdict.verdict == "FAIL" and verdict.anomalies:
        feedback = "\n".join([f"- {a.category}: {a.correction_guidance}" for a in verdict.anomalies])

    return {
        "critic_verdict": verdict,
        "critic_feedback": feedback,
        "execution_telemetry": telemetry,
    }
