"""
Tests du filtre de pertinence (RERANK_MIN_SCORE) : doubles de test, sans modele ni index.
"""

from typing import List, Tuple

from src.rag.chunker import TextChunk
from src.rag.hybrid_retriever import HybridRetriever


def _chunk(cid: str) -> TextChunk:
    return TextChunk(
        chunk_id=cid, content=f"contenu {cid}", source_type="academic_paper",
        title=f"Titre {cid}", authors="Auteur", year=2020, doc_id=cid,
    )


class _FakeBM25:
    def retrieve(self, query: str, top_k: int = 15) -> List[Tuple[TextChunk, float]]:
        return [(_chunk("a"), 3.0), (_chunk("b"), 2.0)]


class _FakeVectors:
    def retrieve(self, query: str, top_k: int = 15) -> List[Tuple[TextChunk, float]]:
        return [(_chunk("c"), 0.9), (_chunk("a"), 0.8)]


class _FakeReranker:
    """Cross-encoder factice : score fixe par chunk_id."""

    def __init__(self, scores, model=object()):
        self.scores = scores
        self.model = model

    def rerank(self, query, candidates, top_n=4):
        self.last_query = query
        scored = sorted(((c, self.scores[c.chunk_id]) for c in candidates), key=lambda x: -x[1])
        return scored[:top_n]


def _retriever(scores, model=object()) -> HybridRetriever:
    return HybridRetriever(bm25=_FakeBM25(), vector_store=_FakeVectors(), reranker=_FakeReranker(scores, model))


def test_chunks_below_threshold_are_filtered():
    r = _retriever({"a": 4.0, "b": -1.0, "c": 1.5})
    outcome = r.search_detailed("q", min_score=0.0)
    assert [c["chunk_id"] for c in outcome.chunks] == ["a", "c"]
    assert outcome.n_below_threshold == 1
    assert outcome.sources_sufficient is True


def test_no_chunk_passing_threshold_means_insufficient_sources():
    r = _retriever({"a": -6.0, "b": -7.0, "c": -8.0})
    outcome = r.search_detailed("q", min_score=0.0)
    assert outcome.chunks == []
    assert outcome.sources_sufficient is False
    assert outcome.top_score == -6.0


def test_search_returns_only_kept_chunks():
    r = _retriever({"a": -6.0, "b": -7.0, "c": 2.0})
    assert [c["chunk_id"] for c in r.search("q", min_score=0.0)] == ["c"]


def test_filter_disabled_when_cross_encoder_missing():
    """Le repli 1/rang n'a pas l'echelle des logits : on ne filtre pas, et on le signale."""
    r = _retriever({"a": 1.0, "b": 0.5, "c": 0.33}, model=None)
    outcome = r.search_detailed("q", min_score=0.0)
    assert outcome.relevance_filter_active is False
    assert len(outcome.chunks) == 3


def test_min_score_none_disables_filter():
    r = _retriever({"a": -6.0, "b": -7.0, "c": -8.0})
    assert len(r.search("q", min_score=None)) == 3


def test_rerank_query_overrides_query_for_cross_encoder_only():
    r = _retriever({"a": 1.0, "b": 1.0, "c": 1.0})
    r.search("question brute en francais", rerank_query="english terms")
    assert r.reranker.last_query == "english terms"
    r.search("only query")
    assert r.reranker.last_query == "only query"
