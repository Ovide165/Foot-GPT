"""
Gestionnaire de stockage vectoriel Dense persistant via ChromaDB.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings
from src.config import CHROMA_PERSIST_DIR, DENSE_EMBEDDING_MODEL
from src.rag.chunker import TextChunk, chunk_embedding_text


_CHROMA_CLIENTS: Dict[str, chromadb.ClientAPI] = {}


class VectorStoreManager:
    """
    Gestionnaire de la base vectorielle ChromaDB locale.
    Indexe les TextChunks avec embeddings denses et métadonnées complètes.
    """

    COLLECTION_NAME = "tactical_knowledge_base"

    def __init__(self, persist_dir: Optional[Path] = None, model_name: str = DENSE_EMBEDDING_MODEL):
        self.persist_dir = persist_dir or CHROMA_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name

        path_key = str(self.persist_dir)
        if path_key not in _CHROMA_CLIENTS:
            _CHROMA_CLIENTS[path_key] = chromadb.PersistentClient(path=path_key)
        self.client = _CHROMA_CLIENTS[path_key]

        self._init_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def _init_embedding_function(self) -> None:
        """Initialise la fonction d'embedding (SentenceTransformers ou FastEmbed)."""
        try:
            from chromadb.utils import embedding_functions
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.model_name
            )
        except Exception:
            # Fallback sur fonction d'embedding par défaut de Chroma
            from chromadb.utils import embedding_functions
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

    def add_chunks(self, chunks: List[TextChunk], batch_size: int = 100) -> None:
        """
        Ajoute des chunks par lots dans la collection ChromaDB.

        Le vecteur est calculé sur `chunk_embedding_text` (titre + section + contenu), comme le
        font BM25 et le reranker, mais le document stocké reste le contenu seul.
        """
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            ids = [c.chunk_id for c in batch]
            documents = [c.content for c in batch]
            embeddings = [
                [float(x) for x in vector]
                for vector in self.embedding_fn([chunk_embedding_text(c) for c in batch])
            ]
            metadatas = [
                {
                    "source_type": c.source_type,
                    "title": c.title,
                    "authors": c.authors or "",
                    "year": c.year or 2020,
                    "section": c.section or "",
                    "page_number": c.page_number or 0,
                    "source_url": c.source_url or "",
                    "doc_id": c.doc_id,
                }
                for c in batch
            ]
            self.collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def reset(self) -> None:
        """Vide la collection (ré-indexation complète : évite de garder des chunks périmés)."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def retrieve(self, query: str, top_k: int = 15) -> List[Tuple[TextChunk, float]]:
        """Recherche par similarité vectorielle cosinus."""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        chunks_with_scores: List[Tuple[TextChunk, float]] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for chunk_id, content, meta, dist in zip(ids, docs, metas, distances):
            # Similarité cosinus = 1 - distance cosinus
            similarity = max(0.0, 1.0 - float(dist))
            chunk = TextChunk(
                chunk_id=chunk_id,
                content=content,
                source_type=meta.get("source_type", "academic_paper"),
                title=meta.get("title", ""),
                authors=meta.get("authors") or None,
                year=int(meta.get("year", 2020)),
                section=meta.get("section") or None,
                page_number=int(meta.get("page_number", 0)) if meta.get("page_number") else None,
                source_url=meta.get("source_url") or None,
                doc_id=meta.get("doc_id", ""),
            )
            chunks_with_scores.append((chunk, similarity))

        return chunks_with_scores

    def count(self) -> int:
        """Retourne le nombre total de documents indexés."""
        return self.collection.count()
