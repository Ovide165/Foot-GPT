"""
Tests d'intégration pour le moteur RAG Hybride (src/rag/).
"""

import pytest

from src.config import BM25_INDEX_PATH, CHROMA_PERSIST_DIR
from src.rag.bm25_retriever import BM25Retriever
from src.rag.chunker import TextChunk
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.reranker import CrossEncoderReranker
from src.rag.vector_store import VectorStoreManager


def test_bm25_retriever_tokenization_and_search():
    """Vérifie la tokenisation et la recherche BM25."""
    retriever = BM25Retriever(index_path=BM25_INDEX_PATH)
    loaded = retriever.load()
    assert loaded is True
    assert len(retriever.chunks) > 0

    results = retriever.retrieve("rest-defense counterpressing", top_k=5)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert isinstance(top_chunk, TextChunk)
    assert score > 0


def test_vector_store_retrieval():
    """Vérifie l'interrogation de la base vectorielle ChromaDB."""
    vs = VectorStoreManager(persist_dir=CHROMA_PERSIST_DIR)
    assert vs.count() > 0

    results = vs.retrieve("passing networks and centrality measures in football", top_k=5)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert isinstance(top_chunk, TextChunk)
    assert 0.0 <= score <= 1.0


def test_hybrid_retriever_end_to_end():
    """Vérifie l'ensemble du pipeline hybride : BM25 + Vector + RRF + Cross-Encoder."""
    retriever = HybridRetriever(
        bm25=BM25Retriever(index_path=BM25_INDEX_PATH),
        vector_store=VectorStoreManager(persist_dir=CHROMA_PERSIST_DIR),
        reranker=CrossEncoderReranker(),
    )
    # Chargement de l'index BM25
    retriever.bm25.load()

    query = "The Half-Spaces Halbraum tactical advantages"
    results = retriever.search(query, top_n_final=3)
    assert len(results) == 3

    for res in results:
        assert "chunk_id" in res
        assert "content" in res
        assert "citation" in res
        assert "source_type" in res
        assert "rerank_score" in res
        assert len(res["citation"]) > 5
