"""
Nœud 2B : Deep Tactical RAG Node (Recherche Hybride Guidée par la Data / Data-Informed RAG).
"""

import time
from typing import Any, Dict, List

from src.rag.bm25_retriever import BM25Retriever
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.reranker import CrossEncoderReranker
from src.rag.vector_store import VectorStoreManager
from src.schemas.miner import MatchFacts
from src.schemas.router import TacticalPlan
from src.schemas.state import TacticalAgentState


# Instance globale partagée pour éviter les rechargements de modèles
_GLOBAL_HYBRID_RETRIEVER: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    global _GLOBAL_HYBRID_RETRIEVER
    if _GLOBAL_HYBRID_RETRIEVER is None:
        bm25 = BM25Retriever()
        bm25.load()
        vector_store = VectorStoreManager()
        reranker = CrossEncoderReranker()
        _GLOBAL_HYBRID_RETRIEVER = HybridRetriever(
            bm25=bm25,
            vector_store=vector_store,
            reranker=reranker,
        )
    return _GLOBAL_HYBRID_RETRIEVER


def deep_rag_node(state: TacticalAgentState) -> Dict[str, Any]:
    """
    Exécute la recherche documentaire hybride en exploitant à la fois
    le TacticalPlan ET les anomalies statistiques réelles révélées par MatchFacts.
    """
    t_start = time.perf_counter()
    plan: TacticalPlan = state.get("tactical_plan")  # type: ignore
    match_facts: MatchFacts = state.get("match_facts")  # type: ignore
    coach_query = state.get("coach_query", "")

    # 1. Construction de la requête RAG enrichie par la data (Data-Informed)
    query_parts: List[str] = []
    
    # Toujours inclure l'intention fondamentale de l'entraîneur
    if coach_query and coach_query.strip():
        query_parts.append(coach_query.strip())
    n_question_parts = len(query_parts)

    if plan and plan.theoretical_topics:
        query_parts.extend(plan.theoretical_topics)
    
    if plan and plan.spatial_zones:
        # Nettoyage des zones pour la recherche documentaire
        query_parts.extend([z.replace("_", " ") for z in plan.spatial_zones])

    n_concept_parts = len(query_parts)

    # Intégration thématique des concepts révélés par les anomalies (sans bruit chiffré)
    if match_facts and match_facts.significant_deltas:
        for delta_key in list(match_facts.significant_deltas.keys())[:2]:
            clean_key = delta_key.replace("_", " ")
            if clean_key not in query_parts:
                query_parts.append(clean_key)

    if not query_parts:
        query_parts.append("Rest-Defense Half-Spaces Counterpressing tactical balance")

    enriched_query = " ".join(query_parts)
    # Le cross-encoder est entraîné sur de l'anglais : la question brute (souvent en français)
    # et les clés de deltas (noms d'équipes, minutes) font chuter les scores sous le seuil de
    # pertinence. On le fait donc scorer sur les seuls concepts du plan (topics + zones, en
    # anglais) ; repli sur la requête complète.
    rerank_query = " ".join(query_parts[n_question_parts:n_concept_parts]) or enriched_query

    # 2. Exécution du Retrieval Hybride (BM25 + Vector + RRF + Cross-Encoder)
    retriever = get_hybrid_retriever()
    outcome = retriever.search_detailed(enriched_query, top_n_final=4, rerank_query=rerank_query)
    retrieved_chunks = outcome.chunks

    t_latency = round((time.perf_counter() - t_start) * 1000, 1)
    telemetry = state.get("execution_telemetry") or {}
    telemetry["deep_rag_latency_ms"] = t_latency
    telemetry["rag_enriched_query"] = enriched_query
    telemetry["rag_rerank_query"] = rerank_query
    telemetry["rag_top_rerank_score"] = outcome.top_score
    telemetry["rag_chunks_below_threshold"] = outcome.n_below_threshold
    telemetry["rag_relevance_filter_active"] = outcome.relevance_filter_active

    return {
        "retrieved_chunks": retrieved_chunks,
        "sources_sufficient": outcome.sources_sufficient,
        "execution_telemetry": telemetry,
    }
