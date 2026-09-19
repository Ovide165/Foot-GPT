"""
Extracteur de texte et de métadonnées pour les fichiers Markdown (Spielverlagerung & Guides).
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.rag.chunker import TextChunk, split_text_by_tokens


class MarkdownParser:
    """
    Parser hiérarchique pour les articles théoriques Markdown.
    Découpe sur la structure des titres pour respecter l'unité des concepts.
    """

    def parse_markdown_file(
        self,
        md_path: Path,
        source_type: str = "tactical_article",
    ) -> List[TextChunk]:
        """Extrait le contenu et les métadonnées YAML d'un fichier Markdown."""
        text = md_path.read_text(encoding="utf-8")
        doc_id = md_path.stem

        # 1. Extraction des métadonnées du header YAML
        meta, body_text = self._extract_yaml_frontmatter(text)
        title = meta.get("title", doc_id.replace("_", " ").title())
        source_url = meta.get("source_url", f"file://{md_path.resolve()}")
        year = meta.get("year")
        if not year and "20" in source_url:
            year_match = re.search(r"/20(\d{2})/", source_url)
            if year_match:
                year = int(f"20{year_match.group(1)}")
            else:
                year = 2020

        # 2. Découpage hiérarchique par sections Markdown (## / ###)
        sections = self._split_by_headers(body_text)
        chunks: List[TextChunk] = []

        chunk_counter = 1
        for header, content in sections:
            if not content.strip() or len(content.split()) < 15:
                continue

            sub_chunks = split_text_by_tokens(content, chunk_size=600, chunk_overlap=100)
            for sub in sub_chunks:
                chunk_id = f"{doc_id}_c{chunk_counter}"
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        content=f"### {header}\n\n{sub}" if header else sub,
                        source_type=source_type,  # type: ignore
                        title=title,
                        authors="Spielverlagerung Editorial Staff" if source_type == "tactical_article" else "foot-GPT Technical Staff",
                        year=year,
                        section=header if header else None,
                        source_url=source_url,
                        doc_id=doc_id,
                    )
                )
                chunk_counter += 1

        return chunks

    def _extract_yaml_frontmatter(self, text: str) -> tuple[Dict[str, Any], str]:
        """Extrait le bloc YAML délimité par --- et renvoie (metadata_dict, remaining_text)."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                yaml_text = parts[1]
                body = parts[2].strip()
                meta = {}
                for line in yaml_text.strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"').strip("'")
                return meta, body
        return {}, text.strip()

    def _split_by_headers(self, text: str) -> List[tuple[str, str]]:
        """Découpe le texte par sections introduites par ## ou ###."""
        lines = text.splitlines()
        sections: List[tuple[str, str]] = []
        current_header = ""
        current_lines: List[str] = []

        for line in lines:
            if line.startswith("## ") or line.startswith("### ") or (line.startswith("# ") and not current_header):
                if current_lines:
                    sections.append((current_header, "\n".join(current_lines).strip()))
                    current_lines = []
                current_header = line.lstrip("#").strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_header, "\n".join(current_lines).strip()))

        return sections
