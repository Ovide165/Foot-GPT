"""
Tests unitaires pour le MatchPhaseGenerator (segmentation dynamique et cache).
"""

import os
from pathlib import Path
import pytest

from src.data_mining.phase_generator import MatchPhaseGenerator
from src.schemas.phases import PhaseDefinition


def test_timeline_extraction():
    """Vérifie que la timeline factuelle brute est extraite correctement."""
    generator = MatchPhaseGenerator()
    meta, timeline = generator._get_match_timeline_data(3869685)

    assert meta["match_id"] == 3869685
    assert meta["home_team"] == "Argentina"
    assert meta["away_team"] == "France"
    assert "--- GOALS ---" in timeline
    assert "--- SUBSTITUTIONS ---" in timeline
    assert "--- xG AND SHOTS VOLUME BY 10-MINUTE BINS ---" in timeline


def test_validate_and_clean_phases():
    """Vérifie que le nettoyage des phases corrige les chevauchements, trous et bornes."""
    generator = MatchPhaseGenerator()

    # Liste désordonnée avec des trous et des chevauchements
    raw_phases = [
        PhaseDefinition(minute_start=5, minute_end=40, name="Phase 1", description="desc 1"),
        PhaseDefinition(minute_start=45, minute_end=70, name="Phase 2", description="desc 2"),
        PhaseDefinition(minute_start=65, minute_end=90, name="Phase 3", description="desc 3"),
    ]

    cleaned = generator._validate_and_clean_phases(raw_phases, max_minute=120)

    # 1. Triées par minute
    assert cleaned[0].minute_start == 0
    # 2. Continuité (fin de l'un = début du suivant)
    assert cleaned[0].minute_end == cleaned[1].minute_start
    assert cleaned[1].minute_end == cleaned[2].minute_start
    # 3. Borne de fin maximale respectée
    assert cleaned[-1].minute_end == 120


def test_cache_miss_and_hit(tmp_path):
    """Vérifie que le cache local fonctionne correctement (lecture/écriture)."""
    cache_file = tmp_path / "cached_phases_test.json"
    generator = MatchPhaseGenerator(cache_path=str(cache_file))

    # 1. Premier appel (Cache Miss -> LLM Invoc/Mock & Cache Write)
    phases = generator.get_or_create_phases(3869685)
    assert len(phases) > 0
    assert cache_file.exists()

    # 2. Deuxième appel (Cache Hit -> Lecture directe)
    phases_cached = generator.get_or_create_phases(3869685)
    assert len(phases_cached) == len(phases)
    assert phases_cached[0].name == phases[0].name
