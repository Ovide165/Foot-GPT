"""
Script de scraping et nettoyage d'articles tactiques de référence (Spielverlagerung).

Ce script :
1. Cible 10 articles théoriques majeurs (Pressing, Half-spaces, Rest Defense, Cover Shadows, Passing Lanes, etc.).
2. Extrait le contenu textuel au format Markdown propre via Trafilatura.
3. Nettoie les artefacts, espaces insécables, footers récurrents et normalise les espacements.
4. Ajoute un header YAML structuré avec les métadonnées (titre, URL source, date).
5. Enregistre chaque fichier dans `data/raw_markdown/`.
6. Gère la robustesse avec temporisation (rate limiting) et gestion d'erreurs.
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import trafilatura

# --- Configuration & Chemins ---
OUTPUT_DIR = Path("data/raw_markdown")

# Liste des 10 articles clés de tactique théorique sur Spielverlagerung
URLS: List[Dict[str, str]] = [
    {
        "filename": "tactics_the_half_spaces.md",
        "url": "https://spielverlagerung.com/2014/09/16/the-half-spaces/",
        "title": "The Half-Spaces (Halbraum) - Spatial Theory and Tactical Advantages",
    },
    {
        "filename": "tactics_counter_or_gegenpressing.md",
        "url": "https://spielverlagerung.com/2014/10/07/counter-or-gegenpressing/",
        "title": "Counter- or Gegenpressing - Fundamentals and Mechanisms",
    },
    {
        "filename": "tactics_counterpressing_variations.md",
        "url": "https://spielverlagerung.com/2014/07/07/counterpressing-variations/",
        "title": "Counterpressing Variations - Space, Man, and Passing-Lane Orientation",
    },
    {
        "filename": "tactics_zonal_marking_coverage.md",
        "url": "https://spielverlagerung.com/2014/07/01/zonal-marking-zonal-coverage/",
        "title": "Zonal Marking and Zonal Coverage - Spatial Defense and Cover Shadows",
    },
    {
        "filename": "tactics_juego_de_posicion.md",
        "url": "https://spielverlagerung.com/2014/12/25/juego-de-posicion-under-pep-guardiola/",
        "title": "Juego de Posición (Positional Play) - Principles, Overloads and Superiorities",
    },
    {
        "filename": "tactics_compactness.md",
        "url": "https://spielverlagerung.com/2015/05/08/tactical-theory-compactness/",
        "title": "Tactical Theory: Compactness - Horizontal, Vertical and Spatial Constriction",
    },
    {
        "filename": "tactics_vertical_buildup_passing.md",
        "url": "https://spielverlagerung.com/2016/05/12/tactical-theory-vertical-build-up-passing/",
        "title": "Tactical Theory: Vertical Build-up Passing and Breaking Lines",
    },
    {
        "filename": "tactics_blind_side_potential.md",
        "url": "https://spielverlagerung.com/2016/09/05/tactical-theory-the-offensive-and-defensive-potential-of-the-blind-side/",
        "title": "Tactical Theory: The Offensive and Defensive Potential of the Blind Side",
    },
    {
        "filename": "tactics_rest_defense_forms.md",
        "url": "https://spielverlagerung.com/2021/07/05/tactical-theory-the-various-forms-of-rest-defence/",
        "title": "Tactical Theory: The Various Forms of Rest-Defence (Restverteidigung)",
    },
    {
        "filename": "tactics_dismarking_methods.md",
        "url": "https://spielverlagerung.com/2017/08/04/tactical-theory-the-various-methods-of-dismarking/",
        "title": "Tactical Theory: The Various Methods of Dismarking and Creating Passing Lanes",
    },
]


def clean_markdown_content(raw_markdown: str, default_title: str, url: str) -> str:
    """
    Nettoie le texte Markdown extrait :
    - Remplace les espaces insécables \xa0
    - Supprime les blocs de bas de page récurrents (signatures, partage, newsletters, etc.)
    - Normalise les sauts de ligne multiples (maximum 2 consécutifs)
    - Formate les en-têtes Markdown (# et ##)
    - Ajoute les métadonnées YAML en en-tête.
    """
    # 1. Remplacement des espaces insécables
    text = raw_markdown.replace("\xa0", " ")

    # 2. Suppression des blocs récurrents de bas de page et de métadonnées de blog
    footer_patterns = [
        r"\*Written by[^\n]+\*",
        r"Written by[^\n]+",
        r"Share this article[^\n]*",
        r"Share this:[^\n]*",
        r"Subscribe to newsletter[^\n]*",
        r"Related Posts?:?[^\n]*",
        r"Leave a [Cc]omment:?[^\n]*",
        r"Comments are closed\.",
        r"Post navigation[^\n]*",
    ]
    for pattern in footer_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # 3. Nettoyage des espaces de fin de ligne et normalisation des retours à la ligne (max 2 \n)
    cleaned_lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    # 4. Extraction ou validation du titre principal
    lines = text.splitlines()
    article_title = default_title
    if lines and lines[0].startswith("# "):
        # Titre déjà présent en Markdown H1
        extracted_from_md = lines[0].lstrip("#").strip()
        if extracted_from_md:
            article_title = extracted_from_md
    else:
        # S'assurer que l'article commence par un titre H1 propre
        text = f"# {article_title}\n\n{text}"

    # 5. Construction du header YAML
    scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yaml_header = f"""---
title: "{article_title}"
source_url: "{url}"
scraped_date: "{scraping_date}"
---

"""
    return yaml_header + text


def scrape_article(item: Dict[str, str], output_dir: Path) -> bool:
    """
    Scrape un article unique, le nettoie et l'écrit sur le disque.
    """
    filename = item["filename"]
    url = item["url"]
    title = item["title"]
    filepath = output_dir / filename

    print(f"[SCRAPING] Téléchargement : {url}...")
    try:
        # Téléchargement via trafilatura
        html = trafilatura.fetch_url(url)
        if not html:
            print(f"[ERROR] Impossible de télécharger la page (HTML vide ou indisponible) : {url}")
            return False

        # Extraction textuelle en Markdown sans images/liens/commentaires
        raw_md = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=False,
            include_images=False,
            include_comments=False,
        )

        if not raw_md or len(raw_md.strip()) == 0:
            print(f"[ERROR] L'extraction Trafilatura n'a retourné aucun contenu pour : {url}")
            return False

        # Nettoyage et ajout des métadonnées YAML
        cleaned_md = clean_markdown_content(raw_md, default_title=title, url=url)

        # Écriture dans le fichier
        filepath.write_text(cleaned_md, encoding="utf-8")
        print(f"[SUCCESS] Article sauvegardé -> {filepath} ({len(cleaned_md)} caractères)")
        return True

    except Exception as e:
        print(f"[ERROR] Exception levée lors du scraping de {url} : {e}")
        return False


def main() -> None:
    """Point d'entrée principal du script de scraping tactique."""
    print("=== Démarrage du scraping des articles tactiques (Spielverlagerung) ===")
    
    # Création du dossier cible
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Dossier de destination : {OUTPUT_DIR.resolve()}")
    print(f"[INFO] {len(URLS)} articles cibles programmés.\n")

    success_count = 0
    failure_count = 0

    for i, item in enumerate(URLS, 1):
        print(f"--- [{i}/{len(URLS)}] ---")
        ok = scrape_article(item, OUTPUT_DIR)
        if ok:
            success_count += 1
        else:
            failure_count += 1

        # Pause pour éviter le rate-limiting
        if i < len(URLS):
            time.sleep(1)

    print("\n" + "=" * 50)
    print("[RÉSUMÉ DU SCRAPING]")
    print(f"  * Succès : {success_count}/{len(URLS)}")
    print(f"  * Échecs : {failure_count}/{len(URLS)}")
    print(f"  * Emplacement : {OUTPUT_DIR.resolve()}")
    print("=" * 50)

    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
