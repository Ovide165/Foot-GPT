# Master Project Ledger & Documentation — foot-GPT

> **Last updated:** 2026-08-27T15:59Z  
> **Status:** 100% Core Requirements & Advanced UI/UX Refinement Implemented  
> **Unit & Integration Tests:** 15/15 PASS (`pytest tests/test_match_miner.py tests/test_phase_generator.py tests/test_guardrails.py tests/test_schemas.py` green)  
> **Visual Validation:** 100% Verified via Chrome DevTools MCP across Desktop (1280px), Semi-Screen (950px), Tablet (780px) & Mobile (550px)  
> **Active Environment:** Python 3.12 (venv)  

---

## 1. Project Vision & Executive Summary

**foot-GPT** is a professional-grade tactical AI assistant designed for elite football coaching and analysis staff (inspired by **Hudl Sportscode, Veo Editor, and StatsBomb IQ**). It bridges the gap between:
1. **Quantitative Event Data:** Raw spatial coordinates ($x, y$), timestamps, passes, pressure turnovers, and Expected Goals ($xG$) derived deterministically from StatsBomb event streams.
2. **Qualitative Tactical Theory:** Structural network analysis, half-space (*Halbräume*) overloads, Rest-Defense, and positional play (*Juego de Posición*) literature.

By combining a **LangGraph state machine**, deterministic **Text-to-SQL mining**, a **Data-Informed Hybrid RAG** engine, automated **Dynamic Match Phase Segmentation**, and a **Human-in-the-Loop (HITL)** validation layer, foot-GPT produces factual, literature-grounded tactical reports strictly structured into UEFA Pro standard sections.

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
[Node 5: HITL Node] ──────────> User/Coach Approval (Streamlit UI)
```

### Flow Logic & Pipeline Capabilities:
1. **Node 1 (Router):** Extracts temporal ranges, spatial zones, target players (*Messi*, *Mbappé*, *Di María*, etc.), and tactical topics using `openai/gpt-oss-20b` (with fallback to `openai/gpt-oss-120b`).
2. **Node 2A (SQL Miner):** Deterministically queries SQLite (`mode=ro`) to extract event streams, compute xG sums, pressure turnovers, and relative team baselines.
3. **Node 2B (Deep RAG):** Queries the dense ChromaDB (305 tactical chunks) + BM25 sparse index via Reciprocal Rank Fusion (RRF), re-ranked with `ms-marco-MiniLM-L-6-v2`.
4. **Node 3 (Synthesizer):** Employs `qwen/qwen3.8-27b` on Groq (~1.8s ultra-low latency) to generate dense, multi-phase tactical reports formatted into 3 indissociable sections:
   - **Part 1 : Factual Diagnosis & Identified Vulnerabilities**
   - **Part 2 : Tactical Principles & Theoretical Foundations**
   - **Part 3 : Practical Training Drills (UEFA Pro / FA Standard)**
5. **Node 4 (Critic):** Verifies all cited quantitative metrics against `MatchFacts` JSON to eliminate numerical hallucinations.
6. **Node 5 (HITL):** LangGraph interrupt capability allowing tactical staff to override, refine, or approve diagnoses.

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
│   │   ├── graph.py                     # LangGraph StateGraph pipeline & HITL definitions
│   │   ├── prompts.py                   # System prompts & few-shot tactical examples
│   │   └── nodes/                       # StateGraph nodes
│   │       ├── router_node.py           # Context extraction & dynamic entity detection
│   │       ├── sql_miner_node.py        # SQLite deterministic metrics & baselines
│   │       ├── deep_rag_node.py         # Knowledge-base hybrid retrieval (RRF)
│   │       ├── synthesizer_node.py      # UEFA Pro 3-part report synthesis
│   │       ├── critic_node.py           # LLM-as-a-Judge faithfulness validation
│   │       └── hitl_node.py             # Human-in-the-loop analyst override node
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
│   │   ├── reranker.py                  # SentenceTransformer MiniLM re-ranking
│   │   └── hybrid_retriever.py          # Reciprocal Rank Fusion coordinator
│   ├── cache/                           # Performance optimization
│   │   └── semantic_cache.py            # Phase-isolated similarity cache (<10ms)
│   ├── security/                        # Security layer
│   │   └── guardrails.py                # Injection protection and query validation
│   └── ui/                              # User Interface
│       ├── styles.css                   # Custom stylesheet (Pro Football Analytics)
│       ├── assets/                      # Visual assets (Hero banner, logo badge)
│       └── components/
│           ├── report_renderer.py       # Accordions, timeline & citations renderer
│           └── admin_dashboard.py       # LLMOps telemetry, RAG explorer, SQL console
│
├── tests/                               # Test suite (15 unit & integration tests)
│   ├── test_match_miner.py              # Tests for deterministic SQL queries & KPIs
│   ├── test_phase_generator.py          # Tests for dynamic phase segmentation
│   ├── test_guardrails.py               # Tests for security guardrails
│   └── test_schemas.py                  # Tests for Pydantic v2 data models
│
└── data/                                # Local persistence datasets
    ├── statsbomb_foot.db                # SQLite StatsBomb database (64 matches)
    ├── chroma_db/                       # ChromaDB persistent vector database (305 chunks)
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
pytest tests/test_match_miner.py tests/test_phase_generator.py tests/test_guardrails.py tests/test_schemas.py
```

---

## 6. Key Development & Operational Rules

1. **Strict Zero-Emoji Standard:** No emojis in generated outputs, labels, badges, or headers.
2. **Deterministic Data Grounding:** Quantitative metrics must originate from SQLite AST-verified queries; qualitative tactical foundations must cite formal references (e.g. `[Spielverlagerung, 2014]`).
3. **Strict High-Contrast Palette:** All text rendered over light surfaces (`#FFFFFF` / `#F8FAFC`) must use `#0F172A` or `#1E293B` (no white-on-white text).
4. **Anti-Concurrency Protection:** UI interactions must remain locked via CSS `:has(.stSpinner)` during report generation.
5. **Database Security:** SQLite connections operate strictly under `mode=ro` with AST query inspection.
