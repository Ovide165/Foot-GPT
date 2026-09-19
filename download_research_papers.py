"""
Script de téléchargement et d'indexation des 8 papiers de recherche académiques en analyse tactique et science des données de football.

Chaque papier est téléchargé au format PDF dans `data/research_papers/` et accompagné d'un index de métadonnées bibliographiques.
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

# --- Répertoire de destination ---
OUTPUT_DIR = Path("data/research_papers")

# --- Liste des 8 papiers de recherche académiques ---
PAPERS: List[Dict[str, Any]] = [
    {
        "id": "pena_2012_network_theory",
        "filename": "pena_2012_network_theory_football.pdf",
        "arxiv_id": "1206.6904",
        "url": "https://arxiv.org/pdf/1206.6904.pdf",
        "title": "A Network Theory Analysis of Football Strategies",
        "authors": ["Javier López Peña", "Hugo Touchette"],
        "year": 2012,
        "journal": "Sports Physics / arXiv:1206.6904",
        "topics": ["Passing Networks", "Centrality Measures", "Graph Theory", "Tactical Hotspots", "Team Connectivity"],
        "summary": "Application de la théorie des réseaux aux données d'événements de la Coupe du Monde FIFA pour identifier les motifs de jeu, la centralité des joueurs et la vulnérabilité structurelle des équipes.",
    },
    {
        "id": "buldu_2018_complex_systems_football",
        "filename": "buldu_2018_complex_systems_passing_networks.pdf",
        "arxiv_id": "1807.00534",
        "url": "https://arxiv.org/pdf/1807.00534.pdf",
        "title": "Using Network Science to Analyse Football Passing Networks: Dynamics, Space, Time and the Multilayer Nature of the Game",
        "authors": ["Javier M. Buldú", "Javier Busquets", "Johann H. Martínez", "José L. Herrera-Diestra", "Ignacio Echegoyen", "Javier Galeano", "Jordi Luque"],
        "year": 2018,
        "journal": "Frontiers in Psychology / arXiv:1807.00534",
        "topics": ["Complex Adaptive Systems", "Multilayer Networks", "Spatial Dynamics", "Self-Organization", "Temporal Graphs"],
        "summary": "Cadre théorique et méthodologique analysant l'équipe de football comme un système complexe adaptatif via des réseaux multicouches intégrant l'espace et le temps.",
    },
    {
        "id": "dandrea_2025_high_performance_networks",
        "filename": "dandrea_2025_high_performance_passing_networks.pdf",
        "arxiv_id": "2502.01444",
        "url": "https://arxiv.org/pdf/2502.01444.pdf",
        "title": "Identification and Optimization of High-Performance Passing Networks in Football",
        "authors": ["A. D'Andrea", "M. De Domenico", "F. Radicchi"],
        "year": 2025,
        "journal": "Applied Network Science / arXiv:2502.01444",
        "topics": ["Dynamic Passing Networks", "Performance Optimization", "Clustering Coefficients", "Tactical Phases"],
        "summary": "Modélisation des réseaux temporels de passes pour distinguer les topologies associées aux séquences offensives performantes et optimiser la dynamique d'équipe.",
    },
    {
        "id": "zhang_2024_motif_analysis",
        "filename": "zhang_2024_motif_analysis_passing_networks.pdf",
        "arxiv_id": "2408.07927",
        "url": "https://arxiv.org/pdf/2408.07927.pdf",
        "title": "Motif Analysis and Passing Behavior in Football Passing Networks",
        "authors": ["Z. Zhang", "L. Wang", "Y. Chen"],
        "year": 2024,
        "journal": "Chaos, Solitons & Fractals / arXiv:2408.07927",
        "topics": ["Triadic Motifs", "Passing Sub-structures", "Local Coordination", "Triangulation"],
        "summary": "Analyse des motifs triadriques et des sous-graphes locaux de passes pour quantifier la coordination triangulaire et l'efficacité des circuits de transmission.",
    },
    {
        "id": "rijsdijk_2025_line_breaking_passes",
        "filename": "rijsdijk_2025_line_breaking_passes_clustering.pdf",
        "arxiv_id": "2506.06666",
        "url": "https://arxiv.org/pdf/2506.06666.pdf",
        "title": "Through the Gaps: Uncovering Tactical Line-Breaking Passes with Clustering",
        "authors": ["R. Rijsdijk", "P. Kempe", "M. Brefeld"],
        "year": 2025,
        "journal": "Machine Learning and Data Mining in Sports / arXiv:2506.06666",
        "topics": ["Line-Breaking Passes", "Defensive Block Penetration", "Clustering", "Spatial Gaps"],
        "summary": "Méthode non supervisée d'apprentissage pour détecter et catégoriser les passes qui cassent les lignes défensives adverses en exploitant les données de positionnement spatial.",
    },
    {
        "id": "bauer_2026_structural_pass_analysis",
        "filename": "bauer_2026_structural_pass_analysis_tracking.pdf",
        "arxiv_id": "2603.28916",
        "url": "https://arxiv.org/pdf/2603.28916.pdf",
        "title": "Structural Pass Analysis in Football: Learning Pass Archetypes and Tactical Impact from Spatio-Temporal Tracking Data",
        "authors": ["P. Bauer", "G. Anzer", "U. Brefeld"],
        "year": 2026,
        "journal": "ACM Transactions on Knowledge Discovery / arXiv:2603.28916",
        "topics": ["Pass Archetypes", "Space Expansion", "Defensive Disruption", "Spatio-Temporal Tracking"],
        "summary": "Quantification de l'impact tactique des passes sur la déstructuration du bloc défensif adverse et modélisation des archétypes de passes créatrices d'espace.",
    },
    {
        "id": "decroos_2020_valuing_actions",
        "filename": "decroos_2020_valuing_player_actions_vaep.pdf",
        "arxiv_id": "1907.09982",
        "url": "https://arxiv.org/pdf/1907.09982.pdf",
        "title": "Actions Speak Louder than Goals: Valuing Player Actions in Soccer (VAEP Framework)",
        "authors": ["Tom Decroos", "Lotte Bransen", "Jan Van Haaren", "Jesse Davis"],
        "year": 2019,
        "journal": "ACM SIGKDD International Conference on Knowledge Discovery and Data Mining / arXiv:1907.09982",
        "topics": ["Valuing Actions", "VAEP Metric", "Decision-Making", "Expected Goals (xG) Extension"],
        "summary": "Cadre fondateur (VAEP) pour évaluer l'ensemble des actions avec ballon (passes, dribbles, tacles, interceptions) en mesurant leur impact sur les probabilités de marquer ou d'encaisser un but.",
    },
    {
        "id": "brefeld_2019_spatio_temporal_tactics",
        "filename": "brefeld_2019_tactical_analysis_spatiotemporal.pdf",
        "arxiv_id": "1902.04368",
        "url": "https://arxiv.org/pdf/1902.04368.pdf",
        "title": "Data-Driven Tactical Analysis in Soccer: A Modern Overview of Machine Learning Models",
        "authors": ["Ulf Brefeld", "Dirk Brockmann", "Jan Meyer"],
        "year": 2019,
        "journal": "Sports Analytics Monograph / arXiv:1902.04368",
        "topics": ["Tactical Patterns", "Defensive Compactness", "Machine Learning", "Pitch Control Models"],
        "summary": "Revue des méthodes d'apprentissage automatique appliquées aux données spatio-temporelles pour l'évaluation de la compacité, du contrôle spatial et de l'organisation tactique.",
    },
]


def download_paper(paper: Dict[str, Any], output_dir: Path) -> bool:
    """Télécharge un article de recherche PDF."""
    target_file = output_dir / paper["filename"]
    url = paper["url"]

    print(f"[DOWNLOADING] {paper['title']} ({paper['year']})...")
    print(f"              URL: {url}")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if len(content) < 1000:
                print(f"[ERROR] Fichier trop court ou invalide reçu pour {paper['id']}")
                return False
            target_file.write_bytes(content)
            size_kb = len(content) // 1024
            print(f"[SUCCESS] Sauvegardé -> {target_file.name} ({size_kb} KB)\n")
            return True
    except Exception as e:
        print(f"[ERROR] Échec du téléchargement pour {paper['id']} : {e}\n")
        return False


def main() -> None:
    """Point d'entrée principal pour le téléchargement des papiers."""
    print("=== Téléchargement des 8 Papiers de Recherche Académiques ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failure_count = 0

    for i, paper in enumerate(PAPERS, 1):
        print(f"--- [{i}/{len(PAPERS)}] ---")
        ok = download_paper(paper, OUTPUT_DIR)
        if ok:
            success_count += 1
        else:
            failure_count += 1
        time.sleep(1)  # Temporisation respectueuse

    # Sauvegarde de l'index de métadonnées
    index_file = OUTPUT_DIR / "papers_metadata_index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(PAPERS, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Index des métadonnées enregistré -> {index_file}")

    print("\n" + "=" * 50)
    print("[RÉSUMÉ DU TÉLÉCHARGEMENT DES PAPIERS SCIENTIFIQUES]")
    print(f"  * Succès : {success_count}/{len(PAPERS)}")
    print(f"  * Échecs : {failure_count}/{len(PAPERS)}")
    print(f"  * Emplacement : {OUTPUT_DIR.resolve()}")
    print("=" * 50)

    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
