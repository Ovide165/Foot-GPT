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

# Paramètres RAG & Chunking
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 100
TOP_K_SPARSE = 15
TOP_K_DENSE = 15
TOP_K_RERANKED = 4
RRF_K = 60  # Constante de Reciprocal Rank Fusion

# Modèles par défaut
DENSE_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Paramètres SQL
SQL_TIMEOUT_SECONDS = 0.5
DEFAULT_MATCH_ID = 3869685  # Argentine vs France (Finale 2022)
