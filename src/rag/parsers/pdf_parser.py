"""
Extracteur de texte et de métadonnées pour les documents PDF (pypdf).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader
from src.config import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS
from src.rag.chunker import TextChunk, split_text_by_tokens


class PDFParser:
    """
    Parser spécialisé pour l'ingestion des papiers de recherche académiques
    et des guides de référence PDF.
    """

    def __init__(self, metadata_index_path: Optional[Path] = None):
        self.metadata_index: Dict[str, Dict[str, Any]] = {}
        if metadata_index_path and metadata_index_path.exists():
            try:
                data = json.loads(metadata_index_path.read_text(encoding="utf-8"))
                for item in data:
                    self.metadata_index[item.get("filename", "")] = item
                    self.metadata_index[item.get("id", "")] = item
            except Exception:
                pass

    def parse_pdf_file(
        self,
        pdf_path: Path,
        source_type: str = "academic_paper",
    ) -> List[TextChunk]:
        """Extrait le texte page par page et découpe en TextChunks enrichis."""
        reader = PdfReader(str(pdf_path))
        doc_id = pdf_path.stem
        filename = pdf_path.name
        
        # Récupération des métadonnées indexées si présentes
        meta = self.metadata_index.get(filename, {})
        title = meta.get("title", pdf_path.stem.replace("_", " ").title())
        authors_list = meta.get("authors", [])
        authors = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)
        year = meta.get("year", 2020)
        source_url = meta.get("url", f"file://{pdf_path.resolve()}")

        chunks: List[TextChunk] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            # Nettoyage des artefacts de numérisation
            cleaned_text = self._clean_page_text(text)
            if not cleaned_text or len(cleaned_text.split()) < 20:
                continue

            page_chunks = split_text_by_tokens(
                cleaned_text,
                chunk_size=CHUNK_SIZE_TOKENS,
                chunk_overlap=CHUNK_OVERLAP_TOKENS,
            )

            for chunk_idx, chunk_text in enumerate(page_chunks, start=1):
                chunk_id = f"{doc_id}_p{page_idx}_c{chunk_idx}"
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        content=chunk_text,
                        source_type=source_type,  # type: ignore
                        title=title,
                        authors=authors if authors else None,
                        year=year,
                        page_number=page_idx,
                        source_url=source_url,
                        doc_id=doc_id,
                    )
                )

        return chunks

    def _clean_page_text(self, text: str) -> str:
        """Nettoie les en-têtes répétitifs, sauts de ligne inutiles et césures de mots."""
        # Remplacement des espaces insécables
        cleaned = text.replace("\xa0", " ")
        # Reconstruction des mots coupés par tiret en fin de ligne (ex: "pass-\ning" -> "passing")
        cleaned = re.sub(r"(\w+)-\n(\w+)", r"\1\2", cleaned)
        # Normalisation des sauts de ligne multiples
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
