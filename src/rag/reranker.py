"""
Module de Re-ranking haute précision basé sur Cross-Encoder.
"""

from typing import List, Optional, Tuple

from src.config import RERANKER_MODEL, TOP_K_RERANKED
from src.rag.chunker import TextChunk


class CrossEncoderReranker:
    """
    Cross-Encoder Re-ranker qui analyse l'interaction fine
    entre la question et le texte pour réordonner le Top-K candidats.
    """

    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Charge le modèle CrossEncoder avec fallback gracieux."""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name, max_length=512)
        except Exception:
            self.model = None

    def rerank(
        self,
        query: str,
        candidates: List[TextChunk],
        top_n: int = TOP_K_RERANKED,
    ) -> List[Tuple[TextChunk, float]]:
        """
        Réordonne les chunks candidats et retourne les top_n meilleurs avec leurs scores.
        """
        if not candidates:
            return []

        # Si le modèle de CrossEncoder est disponible
        if self.model is not None:
            pairs = [[query, f"{c.title}: {c.content}"] for c in candidates]
            scores = self.model.predict(pairs)
            scored = list(zip(candidates, [float(s) for s in scores]))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_n]

        # Fallback heuristique : conservation du classement initial avec score normalisé
        return [(c, 1.0 / (idx + 1)) for idx, c in enumerate(candidates[:top_n])]
