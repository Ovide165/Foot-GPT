"""
Module de Cache Sémantique Vectoriel (Phase 6.2).
Fournit des réponses quasi instantanées (quelques ms une fois le modèle d'embedding chargé) et à coût zéro
sur requêtes similaires. La latence d'un hit est mesurée, pas supposée.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class SemanticCacheEntry:
    def __init__(
        self,
        query: str,
        match_id: int,
        embedding: np.ndarray,
        final_report: str,
        match_facts_json: str,
        execution_telemetry: Dict[str, Any],
        time_range: Optional[Tuple[int, int]] = None,
        scope: str = "window",
        extras: Optional[Dict[str, Any]] = None,
    ):
        self.query = query
        self.match_id = match_id
        self.embedding = embedding
        self.final_report = final_report
        self.match_facts_json = match_facts_json
        self.execution_telemetry = execution_telemetry
        self.time_range = time_range
        self.scope = scope
        self.extras = extras or {}
        self.created_at = time.time()


class SemanticCache:
    """
    Cache sémantique basé sur la similarité cosinus d'embeddings locaux et filtrage strict par time_range.
    """

    def __init__(self, similarity_threshold: float = 0.93):
        self.similarity_threshold = similarity_threshold
        self.entries: List[SemanticCacheEntry] = []
        self._embedding_model = None

    def _get_embedding(self, text: str) -> np.ndarray:
        """Calcule le vecteur d'embedding pour une question."""
        if self._embedding_model is None:
            try:
                from fastembed import TextEmbedding
                self._embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            except Exception:
                # Fallback simple SentenceTransformers
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        if hasattr(self._embedding_model, "embed"):
            vec = list(self._embedding_model.embed([text]))[0]
        else:
            vec = self._embedding_model.encode([text])[0]

        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def get(
        self,
        query: str,
        match_id: int,
        time_range: Optional[Tuple[int, int]] = None,
        scope: str = "window",
    ) -> Optional[Dict[str, Any]]:
        """
        Cherche une entrée en cache sémantiquement équivalente pour le même match et la même tranche temporelle.
        """
        t_start = time.perf_counter()
        if not self.entries:
            return None

        q_vec = self._get_embedding(query)
        best_score = -1.0
        best_entry: Optional[SemanticCacheEntry] = None

        for entry in self.entries:
            if entry.match_id != match_id:
                continue
            if time_range and entry.time_range != time_range:
                continue
            if entry.scope != scope:  # un rapport « match entier » n'est jamais servi pour une fenêtre
                continue
            sim = float(np.dot(q_vec, entry.embedding))
            if sim > best_score:
                best_score = sim
                best_entry = entry

        if best_entry and best_score >= self.similarity_threshold:
            telemetry = dict(best_entry.execution_telemetry)
            telemetry["is_semantic_cache_hit"] = True
            telemetry["cache_similarity_score"] = round(best_score, 4)
            # Latence reellement mesuree de ce get() (embedding de la requete + comparaison)
            telemetry["total_pipeline_latency_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
            return {
                "final_report": best_entry.final_report,
                "match_facts_json": best_entry.match_facts_json,
                "execution_telemetry": telemetry,
                "cached_query": best_entry.query,
                "extras": best_entry.extras,
            }

        return None

    def set(
        self,
        query: str,
        match_id: int,
        final_report: str,
        match_facts_json: str,
        execution_telemetry: Dict[str, Any],
        time_range: Optional[Tuple[int, int]] = None,
        scope: str = "window",
        extras: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Stocke une nouvelle réponse en cache avec son time_range et sa portée (`window` ou `global`).
        `extras` (JSON-compatible) restitue avec le rapport ce que l'interface affiche : chunks cités,
        verdict du critique.
        """
        q_vec = self._get_embedding(query)
        entry = SemanticCacheEntry(
            query=query,
            match_id=match_id,
            embedding=q_vec,
            final_report=final_report,
            match_facts_json=match_facts_json,
            execution_telemetry=execution_telemetry,
            time_range=time_range,
            scope=scope,
            extras=extras,
        )
        self.entries.append(entry)

    def clear(self) -> None:
        self.entries.clear()

    def count(self) -> int:
        return len(self.entries)


# Instance globale singleton du cache sémantique
GLOBAL_SEMANTIC_CACHE = SemanticCache()
