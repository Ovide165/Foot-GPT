"""
Logique applicative de l'interface, sans dépendance à Streamlit (donc testable) :
cache des rapports, exécution d'une analyse et lecture du verdict du critique.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.cache.semantic_cache import GLOBAL_SEMANTIC_CACHE, SemanticCache
from src.schemas.critic import VerificationVerdict
from src.schemas.miner import MatchFacts

NOT_EVALUATED = "non évaluée"

TimeRange = Tuple[int, int]
Runner = Callable[..., Dict[str, Any]]


def matches_available_label(count: int) -> str:
    """Libelle du portail : le nombre reel de matchs disposant d'evenements en base."""
    return f"{count} MATCH{'ES' if count != 1 else ''} AVAILABLE"


def corpus_explorer_title(chunk_count: Optional[int]) -> str:
    """Titre de l'explorateur RAG avec le nombre reel de chunks indexes (sans nombre si inconnu)."""
    return "RAG CORPUS EXPLORER" if chunk_count is None else f"RAG CORPUS EXPLORER ({chunk_count} CHUNKS)"


def chunk_rows(items: List[Any], size: int = 3) -> List[List[Any]]:
    """Decoupe en lignes de `size` elements (cartes de matchs : aucune n'est masquee au-dela de 3)."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def scope_of(is_global_view: bool) -> str:
    return "global" if is_global_view else "window"


def is_cacheable(result: Dict[str, Any]) -> bool:
    """Seuls les rapports non vides dont le verdict final du critique est PASS sont mis en cache."""
    verdict = result.get("critic_verdict")
    return bool(result.get("final_report")) and verdict is not None and verdict.verdict == "PASS"


def store_in_cache(
    cache: SemanticCache,
    query: str,
    match_id: int,
    time_range: Optional[TimeRange],
    result: Dict[str, Any],
    is_global_view: bool = False,
) -> bool:
    """Met le résultat en cache s'il est éligible ; renvoie True si c'est fait."""
    if not is_cacheable(result):
        return False
    facts = result.get("match_facts")
    verdict = result.get("critic_verdict")
    cache.set(
        query=query,
        match_id=match_id,
        final_report=result["final_report"],
        match_facts_json=facts.model_dump_json() if facts is not None else "{}",
        execution_telemetry=result.get("execution_telemetry") or {},
        time_range=time_range,
        scope=scope_of(is_global_view),
        extras={
            "retrieved_chunks": result.get("retrieved_chunks") or [],
            "sources_sufficient": result.get("sources_sufficient"),
            "critic_verdict": verdict.model_dump() if verdict is not None else None,
            "iteration_count": result.get("iteration_count"),
        },
    )
    return True


def result_from_cache(cached: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruit un résultat complet (faits, chunks cités, verdict) à partir d'un hit du cache."""
    extras = cached.get("extras") or {}
    facts_json = cached.get("match_facts_json") or "{}"
    verdict = extras.get("critic_verdict")
    return {
        "final_report": cached["final_report"],
        "execution_telemetry": cached["execution_telemetry"],
        "match_facts": MatchFacts.model_validate_json(facts_json) if facts_json != "{}" else None,
        "retrieved_chunks": extras.get("retrieved_chunks") or [],
        "sources_sufficient": extras.get("sources_sufficient"),
        "critic_verdict": VerificationVerdict.model_validate(verdict) if verdict else None,
        "iteration_count": extras.get("iteration_count"),
        "from_cache": True,
    }


def analyze(
    query: str,
    match_id: int,
    time_range: Optional[TimeRange],
    is_global_view: bool = False,
    cache: SemanticCache = GLOBAL_SEMANTIC_CACHE,
    runner: Optional[Runner] = None,
) -> Dict[str, Any]:
    """Sert le rapport du cache s'il existe ; sinon exécute le graphe puis met en cache si éligible."""
    cached = cache.get(query, match_id, time_range=time_range, scope=scope_of(is_global_view))
    if cached:
        return result_from_cache(cached)
    if runner is None:
        from src.agent.graph import run_tactical_analysis as runner
    result = runner(
        coach_query=query,
        match_id=match_id,
        thread_id=f"session_{match_id}_{time.time()}",
        user_time_range=time_range,
        is_global_view=is_global_view,
    )
    result["from_cache"] = False
    store_in_cache(cache, query, match_id, time_range, result, is_global_view)
    return result


def faithfulness_label(result_or_telemetry: Dict[str, Any]) -> str:
    """Note de fidélité du critique en pourcentage, ou « non évaluée » si elle manque (aucune valeur par défaut)."""
    telemetry = result_or_telemetry.get("execution_telemetry", result_or_telemetry)
    score = telemetry.get("critic_faithfulness_score") if isinstance(telemetry, dict) else None
    return NOT_EVALUATED if score is None else f"{score * 100:.0f}%"


def verdict_view(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ce que l'interface doit montrer du critique : statut, message, anomalies et note de fidélité.
    statut : `passed`, `failed_after_retries` (rapport servi malgré un FAIL) ou `not_evaluated`.
    """
    result = result or {}
    verdict: Optional[VerificationVerdict] = result.get("critic_verdict")
    iterations = result.get("iteration_count")
    if verdict is None:
        return {"status": "not_evaluated", "headline": "Critic verdict not available for this report.",
                "anomalies": [], "faithfulness": faithfulness_label(result)}
    anomalies: List[str] = [f"{a.category}: {a.correction_guidance}" for a in verdict.anomalies]
    if verdict.verdict == "PASS":
        attempts = f" after {iterations} attempts" if iterations and iterations > 1 else ""
        return {"status": "passed", "headline": f"Critic verdict: PASS{attempts}.",
                "anomalies": anomalies, "faithfulness": faithfulness_label(result)}
    attempts = f"{iterations} attempts" if iterations else "all attempts"
    return {
        "status": "failed_after_retries",
        "headline": f"WARNING - Critic verdict: FAIL after {attempts}. This report did not pass the audit "
                    "and may contain errors; verify every figure and citation before use.",
        "anomalies": anomalies,
        "faithfulness": faithfulness_label(result),
    }
