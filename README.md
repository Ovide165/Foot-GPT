# foot-GPT

Assistant IA d'analyse tactique de football. Il combine des données d'événements StatsBomb (SQL déterministe) et une base de connaissances tactique (RAG hybride), orchestrées par un graphe **LangGraph**, pour produire des rapports d'analyse structurés, vérifiés et validés par un humain.

## Langue

foot-GPT fonctionne **uniquement en anglais** : les questions du coach, le corpus documentaire (articles, papiers, guides) et les rapports générés. Le cross-encoder de re-ranking (`ms-marco-MiniLM-L-6-v2`) et le modèle d'embedding (`all-MiniLM-L6-v2`) sont entraînés sur de l'anglais ; une question en français dégrade fortement les scores de pertinence et peut faire écarter des sources pertinentes.

## Architecture

```
Question du coach
     │
     ▼
[1. Router] ──────────> TacticalPlan (Pydantic : période, zones, joueurs, thèmes)
     │
     ▼
[2A. SQL Miner] ──────> MatchFacts (stats déterministes, xG, pertes sous pression)
     │
     ▼
[2B. Deep RAG] ───────> Extraits (ChromaDB dense + BM25 sparse, fusion RRF, re-ranking cross-encoder)
     │
     ▼
[3. Synthesizer] ─────> Rapport en 3 parties (diagnostic, principes, exercices)
     │
     ▼
[4. Critic] ──────────> Vérification des chiffres cités vs MatchFacts
     │   └─ FAIL (≤ 2 itérations) → retour au Synthesizer
     ▼
[5. HITL] ────────────> Validation par le staff dans l'UI Streamlit
```

## Stack

- **Orchestration :** LangGraph, LangChain, Pydantic v2
- **LLM :** Groq (par défaut), avec factory multi-fournisseurs (`src/llm_factory.py`)
- **RAG :** ChromaDB, rank-bm25, sentence-transformers / fastembed
- **Données :** StatsBomb Open Data (Coupe du Monde 2022), SQLite
- **UI :** Streamlit, Plotly, mplsoccer
- **Déploiement :** Docker / docker-compose

## Structure

```
app.py                  # Interface Streamlit
src/agent/              # Graphe LangGraph, nœuds et prompts
src/data_mining/        # Requêtes SQL et segmentation en phases de jeu
src/rag/                # Parsers, chunking, retrievers dense/sparse/hybride, reranker
src/schemas/            # Schémas Pydantic (état, router, miner, critic)
src/security/           # Guardrails
src/cache/              # Cache sémantique
src/evaluation/         # Évaluation RAGAS et benchmarks
tests/                  # Tests pytest
data/high_level_guides/ # Guides tactiques générés
```

## Installation

Prérequis : Python 3.12 et une clé API [Groq](https://console.groq.com).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner GROQ_API_KEY
```

## Construire les données

Les bases et index ne sont pas versionnés. Pour les régénérer :

```bash
python ingest_statsbomb.py            # -> data/statsbomb_foot.db (StatsBomb Open Data)
python scrape_tactics.py              # -> data/raw_markdown/ (articles Spielverlagerung)
python download_research_papers.py    # -> data/research_papers/ (articles académiques)
python generate_high_level_guides.py  # -> data/high_level_guides/
python index_knowledge_base.py        # -> data/chroma_db/ + data/bm25_index.pkl
```

## Lancer l'application

```bash
streamlit run app.py
```

Ou avec Docker :

```bash
docker compose up --build
```

L'application est disponible sur http://localhost:8501.

## Tests

```bash
pytest
```

## Documentation

- [Module A : orchestration LangGraph](ARCHITECTURE_LANGGRAPH.md)
- [Module B : RAG hybride](PIPELINE_RAG_HYBRIDE.md)
- [Modèle de données locales](MODELE_DE_DONNEES_LOCALES.md)
- [Latence, tokens et LLMOps](GUIDE_LATENCE_TOKENS_LLMOPS.md)
- [Design de l'interface](DESIGN.md)

## Sources de données

- Données d'événements : [StatsBomb Open Data](https://github.com/statsbomb/open-data), sous la licence de StatsBomb.
- Articles tactiques : [Spielverlagerung](https://spielverlagerung.com), non redistribués dans ce dépôt.
- Articles de recherche : téléchargés depuis leurs sources originales, non redistribués dans ce dépôt.
