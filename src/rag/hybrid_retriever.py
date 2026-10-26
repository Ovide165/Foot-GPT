"""
Orchestrateur de Recherche Hybride (BM25 + Vector Store + RRF + Re-ranker).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.config import RERANK_MIN_SCORE, RRF_K, TOP_K_DENSE, TOP_K_RERANKED, TOP_K_SPARSE
from src.rag.bm25_retriever import BM25Retriever
from src.rag.chunker import TextChunk
from src.rag.reranker import CrossEncoderReranker
from src.rag.vector_store import VectorStoreManager


@dataclass
class SearchOutcome:
    """Resultat d'une recherche hybride, avec les diagnostics du filtre de pertinence."""
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    n_candidates: int = 0
    n_below_threshold: int = 0
    top_score: Optional[float] = None
    relevance_filter_active: bool = True

    @property
    def sources_sufficient(self) -> bool:
        return len(self.chunks) > 0


class HybridRetriever:
    """
    Système de recherche documentaire hybride multi-sources :
    - Fusion Sparse (BM25) et Dense (Vector Store) via Reciprocal Rank Fusion (RRF)
    - Re-ranking haute précision via Cross-Encoder
    - Formatage des extraits pour l'injection dans le prompt de synthèse
    """

    def __init__(
        self,
        bm25: Optional[BM25Retriever] = None,
        vector_store: Optional[VectorStoreManager] = None,
        reranker: Optional[CrossEncoderReranker] = None,
    ):
        self.bm25 = bm25 or BM25Retriever()
        self.vector_store = vector_store or VectorStoreManager()
        self.reranker = reranker or CrossEncoderReranker()

    def search(
        self,
        query: str,
        top_k_sparse: int = TOP_K_SPARSE,
        top_k_dense: int = TOP_K_DENSE,
        top_n_final: int = TOP_K_RERANKED,
        min_score: Optional[float] = RERANK_MIN_SCORE,
    ) -> List[Dict[str, Any]]:
        """Recherche hybride filtrée par pertinence ; renvoie uniquement les chunks retenus."""
        return self.search_detailed(
            query, top_k_sparse, top_k_dense, top_n_final, min_score
        ).chunks

    def search_detailed(
        self,
        query: str,
        top_k_sparse: int = TOP_K_SPARSE,
        top_k_dense: int = TOP_K_DENSE,
        top_n_final: int = TOP_K_RERANKED,
        min_score: Optional[float] = RERANK_MIN_SCORE,
    ) -> SearchOutcome:
        """
        Exécute la recherche hybride complète :
        1. Retrieval BM25
        2. Retrieval Vector Store
        3. Fusion RRF (Reciprocal Rank Fusion)
        4. Re-ranking Cross-Encoder
        5. Filtre de pertinence (score de reranking >= min_score)
        6. Retourne les métadonnées et textes formatés

        Le filtre n'est appliqué que si le cross-encoder est réellement chargé : le repli
        heuristique (1/rang) n'a pas la même échelle de score et ne permet pas de juger.
        """
        # Les deux recherches restent sequentielles : mesure sur 15 requetes (index de 977 chunks),
        # BM25 ~1.2 ms + dense ~3.8 ms = 5.0 ms contre 5.1 ms avec un ThreadPoolExecutor.
        # Le temps du pipeline est domine par le cross-encoder et les appels LLM.
        # 1. Recherche Sparse (BM25)
        sparse_results = self.bm25.retrieve(query, top_k=top_k_sparse)
        
        # 2. Recherche Dense (Vector)
        dense_results = self.vector_store.retrieve(query, top_k=top_k_dense)

        # 3. Fusion Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, TextChunk] = {}

        # Intégration des rangs BM25
        for rank, (chunk, _) in enumerate(sparse_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (RRF_K + rank))

        # Intégration des rangs Vectoriels
        for rank, (chunk, _) in enumerate(dense_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (RRF_K + rank))

        # Tri des candidats par score RRF
        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        candidates = [chunk_map[cid] for cid in sorted_cids[: (top_k_sparse + top_k_dense)]]

        # 4. Re-ranking Cross-Encoder sur les candidats fusionnés
        reranked = self.reranker.rerank(query, candidates, top_n=top_n_final)

        # 5. Filtre de pertinence
        filter_active = min_score is not None and self.reranker.model is not None
        kept = [(c, s) for c, s in reranked if not filter_active or s >= min_score]

        # 6. Formatage final des résultats
        results: List[Dict[str, Any]] = []
        for chunk, score in kept:
            results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "source_type": chunk.source_type,
                    "title": chunk.title,
                    "authors": chunk.authors,
                    "year": chunk.year,
                    "section": chunk.section,
                    "page_number": chunk.page_number,
                    "source_url": chunk.source_url,
                    "doc_id": chunk.doc_id,
                    "rerank_score": round(score, 4),
                    "citation": chunk.format_citation(),
                }
            )

        return SearchOutcome(
            chunks=results,
            n_candidates=len(candidates),
            n_below_threshold=len(reranked) - len(kept),
            top_score=round(reranked[0][1], 4) if reranked else None,
            relevance_filter_active=filter_active,
        )
