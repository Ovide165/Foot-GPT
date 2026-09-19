"""
Schémas Pydantic pour la segmentation des phases de match.
"""

from typing import List
from pydantic import BaseModel, Field


class PhaseDefinition(BaseModel):
    """Définition d'une phase tactique individuelle."""
    minute_start: int = Field(ge=0, description="Minute de début de la séquence (inclusive)")
    minute_end: int = Field(ge=0, description="Minute de fin de la séquence (exclusive ou inclusive pour la dernière)")
    name: str = Field(description="Libellé court et professionnel (ex: 'Scaloni High Press')")
    description: str = Field(description="Explication tactique justifiant cette phase")


class MatchPhases(BaseModel):
    """Liste ordonnée et validée de phases couvrant l'ensemble du match."""
    phases: List[PhaseDefinition] = Field(description="Liste chronologique des phases de jeu")
