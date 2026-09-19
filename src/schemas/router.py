"""
Schémas Pydantic pour le Nœud 1 (Taxonomic Router).
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """Typologie de question posée par l'entraîneur."""
    DIAGNOSTIC_SEQUENCE = "diagnostic_sequence"      # Diagnostic d'une tranche de jeu précise (ex: 70'-85')
    MACRO_MATCH_FLOW = "macro_match_flow"            # Découpage et dynamique globale du match complet
    PLAYER_IMPACT = "player_impact"                  # Analyse de l'impact individuel / entrant
    TACTICAL_COMPARISON = "tactical_comparison"      # Comparaison entre 2 périodes ou 2 équipes
    GENERAL_KNOWLEDGE = "general_knowledge"          # Question théorique pure de méthodologie


class TacticalPlan(BaseModel):
    """
    Plan d'analyse tactique produit par le Router pour guider
    le SQLMiner et le DeepTacticalRAG.
    """
    query_type: QueryType = Field(
        description="Classification de l'intention de la requête coach"
    )
    game_phases: List[str] = Field(
        default_factory=list,
        description="Phases de jeu concernées (ex: 'Transition Défensive', 'Attaque Placée')"
    )
    time_windows: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Intervalles de minutes à analyser [(start, end)], ex: [(70, 85)] ou [(0, 40), (40, 70), (70, 85), (85, 120)]"
    )
    target_teams: List[str] = Field(
        default_factory=list,
        description="Équipes cibles de l'analyse (ex: ['France', 'Argentina'])"
    )
    target_players: Optional[List[str]] = Field(
        default=None,
        description="Joueurs clés mentionnés ou ciblés (ex: ['Kylian Mbappé Lottin', 'Ángel Fabián Di María Hernández'])"
    )
    spatial_zones: List[str] = Field(
        default_factory=list,
        description="Zones spatiales clés (ex: ['left_half_space', 'zone_14', 'midfield'])"
    )
    key_metrics_needed: List[str] = Field(
        default_factory=list,
        description="Liste des indicateurs à calculer en SQL (ex: ['turnovers_under_pressure', 'passes_final_third', 'xg'])"
    )
    theoretical_topics: List[str] = Field(
        default_factory=list,
        description="Mots-clés théoriques à requêter dans le RAG (ex: ['Rest-Defense', 'Cover Shadow', 'Complex Systems'])"
    )
    reasoning_summary: str = Field(
        default="",
        description="Explication synthétique du raisonnement de cadrage"
    )
