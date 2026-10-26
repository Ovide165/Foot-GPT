"""
Schémas Pydantic pour le Nœud 4 (Critic / Evaluator).
"""

from typing import Any, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


class AuditAnomaly(BaseModel):
    """Description précise d'une anomalie détectée lors de l'audit."""
    category: Literal[
        "numerical_hallucination", "missing_citation", "invalid_citation",
        "unanchored_principle", "unsupported_claim", "formatting_error"
    ]
    claim_in_text: str = Field(description="Phrase ou chiffre problématique relevé dans le texte")
    truth_in_facts: Optional[str] = Field(default=None, description="Valeur exacte issue de MatchFacts ou RetrievedChunks")
    correction_guidance: str = Field(description="Consigne de correction pour le synthétiseur")


class VerificationVerdict(BaseModel):
    """
    Rapport d'audit émis par le Critic Node (LLM-as-a-Judge)
    pour valider ou rejeter le rapport synthétisé.
    """
    is_faithful: Union[bool, str] = Field(
        description="True si TOUS les chiffres cités sont strictement conformes à MatchFacts"
    )
    faithfulness_score: float = Field(
        ge=0.0, le=1.0,
        description="Score de conformité factuelle entre 0.0 (invalide) et 1.0 (parfait)"
    )
    is_fully_cited: Union[bool, str] = Field(
        description="True si chaque concept théorique est appuyé par une citation formelle [Auteur, Année]"
    )
    citation_coverage_score: float = Field(
        ge=0.0, le=1.0,
        description="Score de couverture des citations"
    )
    is_anchored: Union[bool, str] = Field(
        description="True si chaque principe theorique de la Partie 2 debute par un fait chiffre du match (Golden Anchoring Rule)"
    )
    anomalies: List[AuditAnomaly] = Field(
        default_factory=list,
        description="Liste des anomalies relevées nécessitant correction"
    )
    feedback_for_synthesizer: Optional[str] = Field(
        default=None,
        description="Instructions explicites transmises au Nœud 3 en cas d'itération"
    )
    verdict: Literal["PASS", "FAIL"] = Field(
        description="Décision finale d'acceptation du rapport"
    )

    @field_validator("is_faithful", "is_fully_cited", "is_anchored", mode="before")
    def parse_boolean_fields(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "t")
        return bool(v)
