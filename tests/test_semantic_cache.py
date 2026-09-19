"""
Tests unitaires pour le Cache Sémantique (src/cache/semantic_cache.py).
"""

import pytest
from src.cache.semantic_cache import SemanticCache


def test_semantic_cache_hit_and_miss():
    """Vérifie le fonctionnement du hit/miss sur similarité cosinus."""
    cache = SemanticCache(similarity_threshold=0.88)
    cache.clear()

    q1 = "Pourquoi la France a coulé entre la 70e et la 85e minute ?"
    match_id = 3869685
    report = "Rapport d'analyse du réveil français."

    cache.set(
        query=q1,
        match_id=match_id,
        final_report=report,
        match_facts_json="{}",
        execution_telemetry={"total_pipeline_latency_ms": 1200},
    )

    assert cache.count() == 1

    # 1. Requête quasi identique -> Doit être un HIT
    q2 = "Pourquoi l'équipe de France a coulé entre 70e et 85e ?"
    hit = cache.get(q2, match_id)
    assert hit is not None
    assert hit["final_report"] == report
    assert hit["execution_telemetry"]["is_semantic_cache_hit"] is True

    # 2. Requête sur un autre match -> Doit être un MISS
    miss_match = cache.get(q2, match_id=999999)
    assert miss_match is None

    # 3. Requête sémantiquement très différente -> Doit être un MISS
    q3 = "Quelle est la météo à Buenos Aires ?"
    miss_topic = cache.get(q3, match_id)
    assert miss_topic is None
