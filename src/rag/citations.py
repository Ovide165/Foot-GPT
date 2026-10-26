"""
Verification programmatique des citations `[Auteur, Annee - Titre]` d'un rapport
par rapport aux seules sources effectivement fournies au synthetiseur.
"""

import re
from typing import Iterable, List

# Les auteurs peuvent contenir des virgules ("Pena, Touchette, 2012 - ...") : le premier
# groupe est donc non gourmand et s'arrete a la premiere ", <annee> -".
CITATION_PATTERN = re.compile(r"\[([^\[\]]+?),\s*(\d{4})\s*[-–—]\s*([^\[\]]+?)\]")


def normalize_citation(citation: str) -> str:
    """Normalise casse, espaces et tirets (- / en dash / em dash) avant comparaison."""
    text = citation.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def extract_citations(report: str) -> List[str]:
    """Toutes les citations au format [Auteur, Annee - Titre] du texte, dans l'ordre, sans doublon."""
    seen: List[str] = []
    for match in CITATION_PATTERN.finditer(report or ""):
        raw = match.group(0)
        if raw not in seen:
            seen.append(raw)
    return seen


def find_invalid_citations(report: str, allowed_citations: Iterable[str]) -> List[str]:
    """Citations du rapport qui ne correspondent a aucune citation des chunks fournis."""
    allowed = {normalize_citation(c) for c in allowed_citations if c}
    return [c for c in extract_citations(report) if normalize_citation(c) not in allowed]
