"""
Moteur de recherche lexicale Sparse (BM25Okapi) avec tokenisation métier.
"""

import pickle
import re
from pathlib import Path
from typing import List, Optional, Tuple

from rank_bm25 import BM25Okapi
from src.config import BM25_INDEX_PATH
from src.rag.chunker import TextChunk


class BM25Retriever:
    """
    Retriever lexical basé sur BM25Okapi.
    Optimisé pour capturer les mots-clés exacts et le jargon footballistique.
    """

    def __init__(self, index_path: Optional[Path] = None):
        self.index_path = index_path or BM25_INDEX_PATH
        self.chunks: List[TextChunk] = []
        self.bm25: Optional[BM25Okapi] = None

    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        """
        Tokenisation spécialisée :
        - Minuscules
        - Préservation des mots composés (ex: half-space, rest-defense)
        - Élimination de la ponctuation résiduelle
        """
        cleaned = text.lower().replace("_", "-")
        # Isole les tokens alphanumériques et mots avec tirets
        tokens = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)*\b", cleaned)
        return [t for t in tokens if len(t) > 1]

    def build_index(self, chunks: List[TextChunk]) -> None:
        """Construit l'index BM25 à partir d'une liste de TextChunks."""
        self.chunks = chunks
        corpus = [self.tokenize(f"{c.title} {c.section or ''} {c.content}") for c in chunks]
        self.bm25 = BM25Okapi(corpus)

    def save(self, path: Optional[Path] = None) -> None:
        """Persiste l'index BM25 et les chunks sur disque."""
        save_path = path or self.index_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump({"chunks": self.chunks, "bm25": self.bm25}, f)

    def load(self, path: Optional[Path] = None) -> bool:
        """Charge l'index BM25 persisté."""
        load_path = path or self.index_path
        if not load_path.exists():
            return False
        with open(load_path, "rb") as f:
            data = pickle.load(f)
            self.chunks = data["chunks"]
            self.bm25 = data["bm25"]
        return True

    def retrieve(self, query: str, top_k: int = 15) -> List[Tuple[TextChunk, float]]:
        """
        Effectue une recherche lexicale et retourne les (TextChunk, score_bm25).
        """
        if not self.bm25 or not self.chunks:
            return []

        tokens = self.tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        scored_chunks = list(zip(self.chunks, scores))
        # Trier par score décroissant
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]
