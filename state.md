# Master Project Ledger & Documentation — foot-GPT

> **Last updated:** 2026-10-26  
> **Status:** Working prototype on StatsBomb World Cup 2022 data; RAG reliability fixes applied (see `eval/RAPPORT_CORRECTIONS.md`)  
> **Tests:** 104 passing (`pytest`, no API key needed: `MockChatModel` fallback). Retrieval tests require `python index_knowledge_base.py` to have been run  
> **Language:** English only (questions, corpus, reports)  
> **UI validation:** checked manually across Desktop (1280px), Semi-Screen (950px), Tablet (780px) & Mobile (550px); not automated  
> **Active Environment:** Python 3.12 (venv)  

---

## 1. Project Vision & Executive Summary

**foot-GPT** is a professional-grade tactical AI assistant designed for elite football coaching and analysis staff (inspired by **Hudl Sportscode, Veo Editor, and StatsBomb IQ**). It bridges the gap between:
1. **Quantitative Event Data:** Raw spatial coordinates ($x, y$), timestamps, passes, pressure turnovers, and Expected Goals ($xG$) derived deterministically from StatsBomb event streams.
2. **Qualitative Tactical Theory:** Structural network analysis, half-space (*Halbräume*) overloads, Rest-Defense, and positional play (*Juego de Posición*) literature.

By combining a **LangGraph state machine**, deterministic **SQL mining (pre-written parameterised queries, no LLM-generated SQL)**, a **Data-Informed Hybrid RAG** engine, automated **Dynamic Match Phase Segmentation**, and an LLM-as-a-Judge audit loop (numbers by LLM, citations by code), foot-GPT produces factual, literature-grounded tactical reports strictly structured into UEFA Pro standard sections.

---

## 2. Core System Architecture

```
Coach Query / Focus Window
     │
     ▼
[Node 1: Router] ─────────────> TacticalPlan (Pydantic Schema + Dynamic Entity Extraction)
     │
     ▼
[Node 2A: SQL Miner] ─────────> MatchFacts (Deterministic stats, spatial zones & pressure deltas)
     │
     ▼
[Node 2B: Deep RAG] ──────────> Grounding Chunks (Hybrid RRF dense + sparse + Cross-Encoder)
     │
     ▼
[Node 3: Tactical Synthesizer] ──> Draft Report (3 UEFA Pro sections, zero emojis, no preamble)
     │
     ▼
[Node 4: Critic / Evaluator] ───> VerificationVerdict (Faithfulness & citations audit)
     │                     │
     │ (if FAIL, iter<2)   │
     +<────────────────────+
     │
     ▼ (if PASS or iter>=2)
END ───────────────────────────> Report displayed in the Streamlit UI
```

There is no human-in-the-loop node in the graph (`is_human_approved` / `analyst_modifications` exist in the state but are unused).

### Flow Logic & Pipeline Capabilities:
1. **Node 1 (Router):** Extracts temporal ranges, spatial zones, target players (*Messi*, *Mbappé*, *Di María*, etc.), and tactical topics using `openai/gpt-oss-20b` (with fallback to `openai/gpt-oss-120b`).
2. **Node 2A (SQL Miner):** Deterministically queries SQLite (`mode=ro`) to extract event streams, compute xG sums, pressure turnovers, and relative team baselines.
3. **Node 2B (Deep RAG):** Queries the dense ChromaDB (977 tactical chunks of <= 247 tokens) + BM25 sparse index via Reciprocal Rank Fusion (RRF), re-ranked with `ms-marco-MiniLM-L-6-v2`. Chunks below `RERANK_MIN_SCORE` (-4.0) are dropped; if none remain, `sources_sufficient=False` and the report states that no relevant source exists.
4. **Node 3 (Synthesizer):** Employs `qwen/qwen3.8-27b` on Groq (~1.8s ultra-low latency) to generate dense, multi-phase tactical reports formatted into 3 indissociable sections:
   - **Part 1 : Factual Diagnosis & Identified Vulnerabilities**
   - **Part 2 : Tactical Principles & Theoretical Foundations**
   - **Part 3 : Practical Training Drills (UEFA Pro / FA Standard)**
5. **Node 4 (Critic):** An LLM judge checks the cited quantitative metrics against the `MatchFacts` JSON and the anchoring rule (`is_anchored`); code checks that every `[Author, Year - Title]` citation matches a chunk actually provided (`invalid_citation` forces FAIL). Numerical fidelity itself is not checked programmatically.

---

## 3. UI/UX Specifications & Recent Design System Enhancements

### 3.1 Design System & Color Palette
- **Surfaces & Atmosphere:** Warm light monochrome (`#F8FAFC` base, `#FFFFFF` elevated cards) with subtle pitch grid coordinates (`linear-gradient` 36px).
- **Tactical Accents:**
  - *Vert Émeraude Pitch* (`#10B981` / `#059669` / `#ECFDF5`): Live status indicators, goals, recovery badges.
  - *Violet Améthyste & Indigo* (`#6366F1` / `#4F46E5` / `#EEF2FF`): Primary interactive elements, phase focus buttons.
  - *Ardoise & Graphite Profond* (`#0F172A` / `#334155` / `#64748B`): Deep high-contrast typography, eliminating all white-on-white text issues.
- **Editorial Rules:** Strict **Zero Emoji** policy across the entire interface and generated reports.

### 3.2 Key UI Features & Architectural Polish
1. **Suppression of 2D Tactical Pitch:** The obsolete 2D pitch component (`pitch_viz.py`) was fully removed in favor of a clean, immediate dual-column workspace:
   - **Left Column:** Chronological **Key Events Timeline** with uppercase textual action badges (`GOAL`, `ASSIST`, `PENALTY`, `TURNOVER`, `BLOCKED`, `SAVED`) and spatial zone tags (`ZONE 14`, `ATT. 3RD`, `HALF-SPACE`).
   - **Right Column:** 3-section structured tactical report accordions and theoretical citations.
2. **High-Contrast Scoreboard HUD:** Dedicated white card (`#FFFFFF`, border `#E2E8F0`) with emerald live dot, competition title (`#059669`), deep slate team names (`#0F172A`), score badge (`#F1F5F9`), and active tactical focus indicator.
3. **Anti-Concurrency / Dynamic Interaction Lock:**
   - During report generation, CSS rules `:has(.stSpinner)` and `:has([data-testid="stStatusWidget"])` dynamically lock all match dropdowns, fixture cards, phase buttons, and search inputs (`pointer-events: none !important; opacity: 0.55 !important; cursor: wait !important;`).
   - Prevents race conditions, duplicate API requests, and Groq rate-limiting while an analysis is in flight.
4. **Responsive Fixture Cards (Home Portal):**
   - Neutral unified button styling (`type="secondary"`) preventing any artificial pre-selection.
   - Country codes (`ARG`, `FRA`, `CRO`, `MAR`) removed for clean team typography.
   - Fixed height (`116px`) and flexbox row stretching guaranteeing identical height and locked button baselines across desktop (1280px), semi-screen (950px), tablet (780px), and mobile (550px).
5. **High-Contrast KPI Question Mark Tooltips:**
   - Question mark icons (`stTooltipIcon`) styled with explicit slate SVG stroke (`#64748B`, hover `#0F172A`) ensuring visibility on white cards.
   - Dark tooltip popovers (`#0F172A` background, white text) detailing per-team metric breakdowns.
6. **Technical Supervision & Benchmark:**
   - High-contrast `#0F172A` headers for RAG Explorer, SQL Console, and Model Benchmark.
   - Latency distribution chart styled with `plotly_white`.

---

## 4. Codebase Mapping & File Inventory

```
Foot-GPT/
├── .streamlit/config.toml               # Streamlit theme configuration
├── .venv/                               # Hermetic virtual environment (Python 3.12)
├── app.py                               # Master Streamlit application portal & HUD workspace
├── DESIGN.md                            # Visual design system specifications
├── state.md                             # THIS MASTER LEDGER FILE
├── pytest.ini                           # Pytest configuration
│
├── src/                                 # Core source directory
│   ├── config.py                        # Path variables, DB locations, and RAG constants
│   ├── llm_factory.py                   # Multi-provider LLM factory (Groq Qwen 27B / GPT-OSS 120B/20b, OpenAI)
│   ├── agent/                           # Orchestration logic
│   │   ├── graph.py                     # LangGraph StateGraph pipeline (5 nodes, critic loop)
│   │   ├── prompts.py                   # System prompts & few-shot tactical examples
│   │   └── nodes/                       # StateGraph nodes
│   │       ├── router_node.py           # Context extraction & dynamic entity detection
│   │       ├── sql_miner_node.py        # SQLite deterministic metrics & baselines
│   │       ├── deep_rag_node.py         # Knowledge-base hybrid retrieval (RRF)
│   │       ├── synthesizer_node.py      # UEFA Pro 3-part report synthesis
│   │       └── critic_node.py           # LLM judge + programmatic citation check
│   ├── schemas/                         # Pydantic v2 data schemas
│   │   ├── state.py                     # AgentState schema
│   │   ├── router.py                    # TacticalPlan schema
│   │   ├── miner.py                     # MatchFacts schema
│   │   └── critic.py                    # VerificationVerdict schema
│   ├── data_mining/                     # SQL execution & event mining
│   │   ├── db_connection.py             # Read-Only SQLite engine with AST security check
│   │   ├── phase_generator.py           # Dynamic match phase segmentation
│   │   ├── queries.py                   # Parametric SQL query bank
│   │   └── match_miner.py               # Aggregates passes, turnovers, and player highlights
│   ├── rag/                             # Hybrid search & cross-encoder re-ranking
│   │   ├── vector_store.py              # ChromaDB persistent client (singleton pattern)
│   │   ├── bm25_retriever.py            # Sparse token indexing
│   │   ├── chunker.py                   # Token-based chunking (MiniLM tokenizer), embedding text
│   │   ├── citations.py                 # Citation extraction & verification
│   │   ├── parsers/                     # PDF and Markdown parsers
│   │   ├── reranker.py                  # Cross-encoder re-ranking
│   │   └── hybrid_retriever.py          # RRF coordinator + relevance filter
│   ├── cache/                           # Performance optimization
│   │   └── semantic_cache.py            # In-memory similarity cache (measured hit latency, a few ms)
│   ├── security/                        # Security layer
│   │   └── guardrails.py                # Injection protection and query validation
│   └── ui/                              # User Interface
│       ├── styles.css                   # Custom stylesheet (Pro Football Analytics)
│       ├── assets/                      # Visual assets (Hero banner, logo badge)
│       └── components/
│           ├── report_renderer.py       # Accordions, timeline & citations renderer
│           └── admin_dashboard.py       # LLMOps telemetry, RAG explorer, SQL console
│
├── eval/                                # Reference queries, retrieval snapshots, RAPPORT_CORRECTIONS.md
│
├── tests/                               # Test suite (104 tests: miner, phases, guardrails, schemas, RAG,
│                                        #   chunking, citations, threshold calibration, cache, docs guard)
│
└── data/                                # Local persistence datasets
    ├── statsbomb_foot.db                # SQLite StatsBomb database (64 matches listed, events for 4)
    ├── chroma_db/                       # ChromaDB persistent vector database (977 chunks)
    ├── bm25_index.pkl                   # Sparse index serialization file
    ├── high_level_guides/               # Curated tactical theory guides
    └── raw_markdown/                    # Spielverlagerung tactical articles
```

---

## 5. Running Instructions

### Environment Initialization:
```bash
# Activate virtual environment
source .venv/bin/activate

# Ensure .env contains GROQ_API_KEY
# GROQ_API_KEY=gsk_...
```

### Run Streamlit App:
```bash
streamlit run app.py --server.headless=true --server.port=8501
```

### Run Unit Tests:
```bash
pytest   # use the .venv interpreter; LLM_PROVIDER=mock avoids any network call
```

---

## 6. Key Development & Operational Rules

1. **Strict Zero-Emoji Standard:** No emojis in generated outputs, labels, badges, or headers.
2. **Deterministic Data Grounding:** Quantitative metrics must originate from SQLite AST-verified queries; qualitative tactical foundations must cite formal references (e.g. `[Spielverlagerung Editorial Staff, 2014 - The Half-Spaces]`).
3. **Strict High-Contrast Palette:** All text rendered over light surfaces (`#FFFFFF` / `#F8FAFC`) must use `#0F172A` or `#1E293B` (no white-on-white text).
4. **Anti-Concurrency Protection:** UI interactions must remain locked via CSS `:has(.stSpinner)` during report generation.
5. **Database Security:** SQLite connections operate strictly under `mode=ro` with AST query inspection.
