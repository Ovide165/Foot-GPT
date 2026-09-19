"""
Modèles de données pour les fragments de texte (Chunks) et utilitaires de découpage.
"""

import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """Représentation d'un chunk textuel unifié avec métadonnées de traçabilité."""
    chunk_id: str = Field(description="Identifiant unique du chunk (ex: pena_2012_p3_c1)")
    content: str = Field(description="Contenu textuel nettoyé du fragment")
    source_type: Literal["academic_paper", "tactical_article", "high_level_guide"] = Field(
        description="Type de document source"
    )
    title: str = Field(description="Titre du document source")
    authors: Optional[str] = Field(default=None, description="Auteurs du document")
    year: Optional[int] = Field(default=None, description="Année de publication")
    section: Optional[str] = Field(default=None, description="Titre de la section ou chapitre")
    page_number: Optional[int] = Field(default=None, description="Numéro de page dans le document")
    source_url: Optional[str] = Field(default=None, description="URL source ou arXiv ID")
    doc_id: str = Field(description="Identifiant du document parent")

    def format_citation(self) -> str:
        """Formate la citation normalisée pour le rapport."""
        if self.authors and self.year:
            return f"[{self.authors}, {self.year} - {self.title}]"
        elif self.year:
            return f"[{self.title}, {self.year}]"
        return f"[{self.title}]"


def split_text_by_tokens(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[str]:
    """
    Découpe un texte brut en paragraphes/phrases avec respect des frontières naturelles
    et contrôle de la taille en mots/tokens approximatifs.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for para in paragraphs:
        words = para.split()
        para_len = len(words)

        if current_length + para_len > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            # Gestion de l'overlap : conserve les dernières phrases
            overlap_words = " ".join(current_chunk).split()[-chunk_overlap:]
            current_chunk = [" ".join(overlap_words), para] if overlap_words else [para]
            current_length = len(overlap_words) + para_len
        else:
            current_chunk.append(para)
            current_length += para_len

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
