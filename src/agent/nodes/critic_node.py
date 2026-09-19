"""
Nœud 4 : Critic Evaluator Node (Audit factuel anti-hallucination & vérification des citations).
"""

import time
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from src.agent.prompts import CRITIC_SYSTEM_PROMPT
from src.llm_factory import LLMFactory
from src.schemas.critic import AuditAnomaly, VerificationVerdict
from src.schemas.miner import MatchFacts
from src.schemas.state import TacticalAgentState


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

    t_latency = round((time.perf_counter() - t_start) * 1000, 1)
    telemetry = state.get("execution_telemetry") or {}
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
