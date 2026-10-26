"""
Modèles de données pour les fragments de texte (Chunks) et utilitaires de découpage.
"""

import re
from functools import lru_cache
from typing import Callable, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from src.config import (
    CHUNK_MIN_CONTENT_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    DENSE_EMBEDDING_MODEL,
    EMBEDDING_MAX_TOKENS,
)


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


@lru_cache(maxsize=1)
def _embedding_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(DENSE_EMBEDDING_MODEL)


def count_tokens(text: str) -> int:
    """Nombre de tokens WordPiece du modèle d'embedding (sans les marqueurs [CLS]/[SEP])."""
    return len(_embedding_tokenizer()(text, add_special_tokens=False, verbose=False)["input_ids"])


def embedding_header(title: str, section: Optional[str] = None) -> str:
    """Titre (et section) placés en tête du texte embeddé, comme pour BM25 et le reranker."""
    return f"{title} - {section}" if section else title


def chunk_embedding_text(chunk: TextChunk) -> str:
    """Texte effectivement envoyé à l'embedding dense : titre/section puis contenu."""
    return f"{embedding_header(chunk.title, chunk.section)}\n{chunk.content}"


def content_token_budget(
    title: str,
    section: Optional[str] = None,
    count: Callable[[str], int] = count_tokens,
) -> int:
    """
    Budget de tokens du contenu d'un chunk : la cible, réduite si le titre est long pour que
    titre + contenu + [CLS]/[SEP] ne dépassent jamais EMBEDDING_MAX_TOKENS.
    """
    header_tokens = count(embedding_header(title, section)) + 1  # +1 : séparateur de ligne
    available = EMBEDDING_MAX_TOKENS - 2 - header_tokens
    return max(CHUNK_MIN_CONTENT_TOKENS, min(CHUNK_TARGET_TOKENS, available))


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[A-Z0-9])")
_LIST_LINE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")

# Une unité est (texte, séparateur à insérer avant elle lorsqu'elle suit une autre unité)
Unit = Tuple[str, str]


def _paragraph_units(paragraph: str) -> List[Unit]:
    """Phrases d'un paragraphe ; les éléments de liste restent des unités à part entière."""
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    if len(lines) > 1 and sum(bool(_LIST_LINE.match(ln)) for ln in lines) >= 2:
        return [(ln.strip(), "\n") for ln in lines]
    flat = re.sub(r"\s*\n\s*", " ", paragraph).strip()  # lignes repliées des PDF
    return [(sentence, " ") for sentence in _SENTENCE_SPLIT.split(flat) if sentence]


def _split_oversized(text: str, max_tokens: int, count: Callable[[str], int]) -> List[str]:
    """Découpe en dernier recours une unité trop longue (par mots, puis par caractères)."""
    pieces: List[str] = []
    current: List[str] = []
    for word in text.split():
        if count(word) > max_tokens:  # mot pathologique (URL...) : coupe par moitiés
            if current:
                pieces.append(" ".join(current))
                current = []
            pieces.extend(_split_oversized(word[: len(word) // 2], max_tokens, count))
            pieces.extend(_split_oversized(word[len(word) // 2 :], max_tokens, count))
        elif current and count(" ".join(current + [word])) > max_tokens:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _render(units: List[Unit]) -> str:
    return "".join((sep if i else "") + text for i, (text, sep) in enumerate(units))


def split_text_by_tokens(
    text: str,
    max_tokens: int = CHUNK_TARGET_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
    count: Callable[[str], int] = count_tokens,
) -> List[str]:
    """
    Découpe un texte en chunks d'au plus `max_tokens` tokens (mesurés par `count`).

    La structure prime sur la taille : on remplit les chunks avec des paragraphes entiers ; un
    paragraphe n'est coupé (par phrases, puis par mots en dernier recours) que s'il ne tient pas
    dans un chunk. Chaque chunk reprend en tête les dernières phrases du précédent, dans la limite
    de `overlap_tokens`.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    groups: List[List[Unit]] = []
    for para in paragraphs:
        units: List[Unit] = []
        for unit_text, sep in _paragraph_units(para):
            if count(unit_text) > max_tokens:
                units.extend((piece, " ") for piece in _split_oversized(unit_text, max_tokens, count))
            else:
                units.append((unit_text, sep))
        if units:
            groups.append([(t, "\n\n" if i == 0 else sep) for i, (t, sep) in enumerate(units)])

    chunks: List[str] = []
    current: List[Unit] = []
    carried = 0  # nombre d'unités de tête reprises du chunk précédent (overlap)

    def fits(units: List[Unit]) -> bool:
        return count(_render(units)) <= max_tokens

    def flush() -> None:
        nonlocal current, carried
        chunks.append(_render(current))
        tail: List[Unit] = []
        for unit in reversed(current):
            if overlap_tokens <= 0 or not fits_within([unit] + tail, overlap_tokens):
                break
            tail.insert(0, unit)
        current, carried = tail, len(tail)

    def fits_within(units: List[Unit], limit: int) -> bool:
        return count(_render(units)) <= limit

    def add_units(units: List[Unit]) -> None:
        nonlocal current, carried
        for unit in units:
            if fits(current + [unit]):
                current.append(unit)
                continue
            if len(current) > carried:
                flush()
            while current and not fits(current + [unit]):
                current.pop(0)
                carried = max(0, carried - 1)
            current.append(unit)

    for group in groups:
        if current and fits(current + group):
            current.extend(group)
            continue
        if len(current) > carried and fits(group):
            flush()  # le paragraphe tient seul : on ouvre un nouveau chunk plutôt que de le couper
            if fits(current + group):
                current.extend(group)
                continue
        add_units(group)

    if len(current) > carried:
        chunks.append(_render(current))
    return chunks
