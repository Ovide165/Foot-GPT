"""
Configuration centrale et paramètres globaux pour foot-GPT.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Répertoire racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Chemins des données
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "statsbomb_foot.db"
HIGH_LEVEL_DIR = DATA_DIR / "high_level_guides"
RAW_MARKDOWN_DIR = DATA_DIR / "raw_markdown"
RESEARCH_PAPERS_DIR = DATA_DIR / "research_papers"
CHROMA_PERSIST_DIR = DATA_DIR / "chroma_db"
BM25_INDEX_PATH = DATA_DIR / "bm25_index.pkl"

# Paramètres RAG & Chunking (toutes les tailles sont des tokens du tokenizer WordPiece de
# DENSE_EMBEDDING_MODEL, pas des mots)
EMBEDDING_MAX_TOKENS = 256     # max_seq_length de all-MiniLM-L6-v2 (marqueurs [CLS]/[SEP] compris)
CHUNK_TARGET_TOKENS = 220      # taille cible du contenu d'un chunk
CHUNK_OVERLAP_TOKENS = 40      # recouvrement entre deux chunks consécutifs (phrases entières)
CHUNK_MIN_CONTENT_TOKENS = 32  # plancher du budget de contenu si le titre est très long
TOP_K_SPARSE = 15
TOP_K_DENSE = 15
TOP_K_RERANKED = 4
RRF_K = 60  # Constante de Reciprocal Rank Fusion

# Seuil de pertinence du cross-encoder (logit brut de ms-marco-MiniLM-L-6-v2).
# Les chunks dont le score de reranking est inferieur sont ecartes ; si aucun ne passe,
# le noeud RAG signale `sources_sufficient=False` et le rapport doit l'indiquer.
# Calibration sur eval/pipeline_queries.json (18 requetes construites comme le pipeline : question +
# topics + zones + cles de deltas), meilleur chunk par requete :
#   en corpus -3.0 a +1.4 (12 requetes) ; football hors corpus -8.2 et -5.0 ; hors sujet -8.6 a -5.7,
#   sauf un cas a -2.6 (hors sujet auquel le routeur a attribue des topics de football par defaut).
# Le logit 0.0 (sigmoid 0.5) rejetait 7 requetes en corpus sur 12 : les cles de deltas ajoutees a
# la requete abaissent les scores. Toute valeur de ]-5.0, -3.0] garde les 12 requetes en corpus et
# ecarte les 5 requetes hors corpus separables ; -4.0 en est le milieu. Les 15 requetes "propres" de
# eval/baseline_queries.json restent correctement classees (en corpus >= 3.2, hors sujet <= -6.9).
# Voir eval/RAPPORT_CORRECTIONS.md.
RERANK_MIN_SCORE = -4.0

# Modèles par défaut
DENSE_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Paramètres SQL
SQL_TIMEOUT_SECONDS = 0.5
DEFAULT_MATCH_ID = 3869685  # Argentine vs France (Finale 2022)
