# foot-GPT : vue d'ensemble de l'architecture (support de présentation orale)

Document produit par lecture du code (aucun code modifié). Chaque point cite `fichier:lignes`.
Quand un élément n'existe pas dans le code, c'est écrit « **Absent du code** ».
Les affirmations vérifiées à l'exécution sont signalées ; les autres viennent de la lecture seule.

**Pitch en une phrase :** un entraîneur choisit un match de la Coupe du monde 2022 et une phase de jeu ; un graphe LangGraph à 5 nœuds calcule des statistiques exactes en SQL, récupère des extraits de littérature tactique (RAG hybride), rédige un rapport en 3 parties, puis un « critique » le vérifie (en partie par du code, en partie par un LLM) avant affichage dans Streamlit.

---

## 1. Données

| Question | Réponse | Source |
|---|---|---|
| Source | API ouverte **StatsBomb** via `statsbombpy` (Coupe du monde 2022, `competition_id=43`, `season_id=106`) | `ingest_statsbomb.py:26-31, 70` |
| Matchs ingérés | Le script vise **3 matchs** (`TARGET_MATCH_COUNT=3`) en forçant la finale `3869685`. La base contient pourtant **4 matchs avec événements** (3857276, 3869552, 3869684, 3869685 ; 3 388 à 4 407 événements chacun, 14 906 au total, requête faite sur `data/statsbomb_foot.db`). L'écart avec le script n'est pas expliqué dans le code | `ingest_statsbomb.py:33, 86-105` ; mesuré sur la base |
| Format / base | **SQLite** `data/statsbomb_foot.db`, 3 tables : `matches`, `players`, `events` | `ingest_statsbomb.py:211-218` ; `src/config.py:14` |
| Schéma `events` | `event_id, match_id, index, period, minute, second, type, team, player, x, y, pass_recipient, raw_data` ; `raw_data` = événement StatsBomb complet en **JSON texte** | `ingest_statsbomb.py:128-172` |
| Index | `match_id`, `minute`, `player`, `type` + index uniques sur les ids | `ingest_statsbomb.py:225-233` |
| Chargement | Script manuel : `sb.matches` → sélection → `sb.events` → `to_sql(if_exists="replace")`. **La base est entièrement réécrite à chaque exécution** | `ingest_statsbomb.py:297-318` |
| Accès à l'exécution | Connexion SQLite en lecture seule (`?mode=ro`), ouverte à chaque requête | `src/data_mining/db_connection.py:57-73` |
| Base de connaissances (texte) | 977 chunks (mesuré : index BM25 = 977, Chroma = 977) issus de 8 PDF scientifiques, 3 guides Markdown « high-level », 10 articles Spielverlagerung. Indexation par `index_knowledge_base.py` : BM25 (pickle `data/bm25_index.pkl`) + ChromaDB (`data/chroma_db/`) | `index_knowledge_base.py:34-92` ; `src/config.py:15-19` |
| Phases de match | Générées par un LLM à partir d'une timeline SQL (buts, remplacements, xG par tranche de 10 min), nettoyées, puis **mises en cache dans `data/cached_phases.json`** (4 matchs présents) | `src/data_mining/phase_generator.py:25-103, 147-225` |

Points à savoir : `data/football_rag.db` existe mais ne contient aucune table et n'est référencé nulle part dans le code (mesuré + grep). Le dossier `data/raw_markdown/` est exclu de git (`.gitignore:41`), tout comme la base et les index (`.gitignore:18-21`) : un clone neuf doit relancer l'ingestion et l'indexation.

---

## 2. Cache sémantique

**Point clé pour l'oral : le cache n'est PAS un nœud du graphe.** Il est appelé par l'interface (`app.py`) *avant* `run_tactical_analysis`. Le graphe ne le connaît pas (`src/agent/graph.py:44-48`).

- **Moment** : `GLOBAL_SEMANTIC_CACHE.get(...)` à trois endroits : clic sur une phase (`app.py:395`), génération automatique initiale (`app.py:435`), bouton « Run Analysis » (`app.py:503`). `set(...)` après une analyse réussie : `app.py:415, 456, 524, 626`.
- **Clé / critères de hit** (`src/cache/semantic_cache.py:62-97`) :
  1. même `match_id` (l. 75) ;
  2. même `time_range` **exacte** si fourni (l. 77) ;
  3. similarité cosinus entre embeddings de la question ≥ seuil (l. 79-84).
- **Seuil** : `similarity_threshold = 0.93` (`semantic_cache.py:38`).
- **Embedding** : `BAAI/bge-small-en-v1.5` via fastembed, sinon `all-MiniLM-L6-v2` (`semantic_cache.py:43-52`).
- **Stockage** : liste Python en mémoire dans un singleton (`semantic_cache.py:40, 129`). Pas de persistance, pas d'expiration.
- **Latence d'un hit** : mesurée par `perf_counter` (`semantic_cache.py:66, 89`).
- **Ce qu'un hit restitue** : le rapport et la télémétrie ; l'interface reconstruit `match_facts=None` et `retrieved_chunks=[]` (`app.py:397-402`), donc **un rapport servi par le cache s'affiche sans panneau de citations ni tableau de faits**.
- **Ce qui est stocké** : tout rapport non vide, **y compris un rapport que le critique a finalement refusé** (aucun test du verdict avant `set`, `app.py:414-422`).

**Défaut vérifié à l'exécution (voir §10, point 1) :** `app.py:9-11` fait `importlib.reload(src.cache.semantic_cache)` à chaque exécution du script Streamlit. Test fait : après un `reload`, `GLOBAL_SEMANTIC_CACHE` est une **nouvelle instance vide** (`same instance: False, entries: 0`). Comme Streamlit ré-exécute le script à chaque interaction (et `st.rerun()` suit chaque `set`), le cache est en pratique vidé avant de pouvoir servir.

---

## 3. Routeur (nœud 1)

- **Fichier** : `src/agent/nodes/router_node.py:15-135`.
- **Modèle** : `LLMFactory.get_fast_model(temperature=0.0)` (`router_node.py:23`). Par défaut, avec `LLM_PROVIDER=groq` : `openai/gpt-oss-20b` (variable `GROQ_FAST_MODEL`), avec repli automatique sur `openai/gpt-oss-120b` (`src/llm_factory.py:130-146`). Autres fournisseurs : `gpt-4o-mini` (l. 153), `gemini-2.0-flash` (l. 164), `llama3.1:8b` via Ollama (l. 175). Sans clé valide : **`MockChatModel`** silencieux (l. 179).
- **Sortie structurée** : `llm.with_structured_output(TacticalPlan)` (`router_node.py:24`).
- **Prompt système** : `ROUTER_SYSTEM_PROMPT` (`src/agent/prompts.py:5-22`), en anglais. Il distingue le mode macro (`macro_match_flow`, 4-5 phases) du mode micro (`diagnostic_sequence`) et liste les 9 champs à extraire.
- **Message utilisateur** : question du coach + équipes autorisées lues en base + tranche choisie dans l'interface (`router_node.py:28-37`).
- **Post-traitement en code** (le LLM n'a pas le dernier mot) :
  - détection de joueurs par table de mots-clés **codée en dur** (Messi, Mbappé, Griezmann… 24 entrées, uniquement joueurs de la finale/du Mondial) injectée en tête de `target_players` (`router_node.py:45-88`) ;
  - si la tranche du coach dure < 100 minutes : `time_windows = [tranche]` et `query_type = DIAGNOSTIC_SEQUENCE` (`router_node.py:90-92`).
- **Repli** si l'appel LLM échoue : plan par défaut construit en code (`router_node.py:93-126`).

### Schéma complet de `TacticalPlan` (`src/schemas/router.py:19-58`)

| Champ | Type | Défaut | Rôle |
|---|---|---|---|
| `query_type` | `QueryType` (enum) | requis | `diagnostic_sequence`, `macro_match_flow`, `player_impact`, `tactical_comparison`, `general_knowledge` (l. 10-16) |
| `game_phases` | `List[str]` | `[]` | phases de jeu visées |
| `time_windows` | `List[Tuple[int,int]]` | `[]` | intervalles de minutes à analyser |
| `target_teams` | `List[str]` | `[]` | équipes cibles |
| `target_players` | `Optional[List[str]]` | `None` | joueurs ciblés |
| `spatial_zones` | `List[str]` | `[]` | zones (ex. `zone_14`) |
| `key_metrics_needed` | `List[str]` | `[]` | indicateurs demandés |
| `theoretical_topics` | `List[str]` | `[]` | mots-clés pour le RAG |
| `reasoning_summary` | `str` | `""` | justification |

**Champs réellement exploités en aval** (grep) : `time_windows`, `target_teams`, `target_players`, `query_type`, `reasoning_summary` (SQL miner, `match_miner.py:279-340`) ; `theoretical_topics` et `spatial_zones` (requête RAG, `deep_rag_node.py:47-52`). **`key_metrics_needed` et `game_phases` ne sont lus nulle part** : le LLM les remplit, rien n'en dépend. `general_knowledge` n'a aucune branche dédiée dans le graphe.

---

## 4. SQL miner (nœud 2A)

### 4.1 Requêtes écrites à l'avance ou générées ?

**Écrites à l'avance, aucune génération par LLM.** Les requêtes sont des constantes paramétrées dans `src/data_mining/queries.py:6-140` (métadonnées, métriques de phase, moyennes de référence, métriques joueur, timeline joueur, KPI, événements critiques). Quelques requêtes complémentaires sont inline dans `match_miner.py` (l. 77, 152, 168, 174, 178, 405-425, 449-453). Le LLM ne produit jamais de SQL ; il ne fournit que des paramètres (minutes, équipe, nom de joueur) passés en `?`.

### 4.2 Garde-fous

Tout passe par `ReadOnlyDBConnection.execute_safe_query` (`db_connection.py:75-83`) :
- ouverture en **lecture seule au niveau SQLite** (`?mode=ro`, l. 66) : c'est le garde-fou réel ;
- validation : première instruction ∈ {`SELECT`, `WITH`, `EXPLAIN`} (l. 45-49) ;
- liste noire de mots-clés `INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|TRUNCATE` (l. 27-30, 51-55) ;
- requêtes paramétrées (pas de concaténation de valeurs).

**Absent du code** : liste blanche de tables ou de colonnes. `SQL_TIMEOUT_SECONDS = 0.5` (`config.py:51`) est passé comme `timeout` de `sqlite3.connect` (`db_connection.py:67`) : c'est le délai d'attente de verrou, **pas** un plafond de durée de requête.
Remarque : la console SQL de l'onglet admin exécute du SQL **saisi par l'utilisateur** avec ces seuls garde-fous (`admin_dashboard.py:93-111`) ; elle peut lire n'importe quelle table.

### 4.3 `significant_deltas`

Calcul dans `build_match_facts`, `match_miner.py:307-320` :
- **Métrique unique : les pertes de balle sous pression** (`turnovers_under_pressure`). Aucun autre indicateur n'a de delta.
- **Référence** : moyenne de **l'équipe elle-même sur tout le match, ramenée à 15 minutes** (`SQL_MATCH_BASELINE_AVERAGES`, `queries.py:49-65` : événements de l'équipe / (`MAX(minute)`/15), minute > 0). Ce n'est pas une comparaison à l'adversaire.
- **Formule** : `valeur_phase × (15 / durée_phase)`, puis `(valeur_normalisée − référence) / référence × 100` (l. 314-317).
- **Un delta est produit pour chaque équipe et chaque fenêtre** ; il n'y a **aucun seuil de significativité** malgré le nom. Défaut de référence 1.0 si la clé manque (l. 311).
- **Ordre** : aucun tri. `significant_deltas` est un dictionnaire dans l'ordre d'insertion : équipe par équipe, puis fenêtres dans l'ordre du plan (l. 309-320). Les « 2 premiers » utilisés par le RAG (`deep_rag_node.py:56`) sont donc les deux premières fenêtres de la première équipe, pas les plus marquantes.
- Clé : `"{équipe}_turnovers_{début}_{fin}"` ; valeur : chaîne `[équipe] turnovers under pressure (a-b min): +328% vs équipe match baseline`.

Autres calculs du mineur : métriques de phase (`SQL_PHASE_METRICS`), Field Tilt (part des passes réussies dans le dernier tiers, x ≥ 80, `match_miner.py:74-82`), zone 14 (x 75-95, y 30-50, `queries.py:23`), joueurs ciblés (`compute_player_highlight`, l. 122-270), remplacements sur **tout** le match 0-120 (l. 325).

---

## 5. Synthétiseur (nœud 3)

- **Fichier** : `src/agent/nodes/synthesizer_node.py:15-161`.
- **Modèle** : `LLMFactory.get_reasoning_model(temperature=0.2)` (l. 110). Groq : `qwen/qwen3.8-27b` (variable `GROQ_REASONING_MODEL`), repli `openai/gpt-oss-120b` (`llm_factory.py:195-211`) ; OpenAI `gpt-4o` (l. 218) ; Gemini `gemini-2.0-flash` (l. 229) ; Ollama `llama3.3:70b` (l. 240) ; sinon Mock (l. 244). Je n'ai pas pu vérifier l'existence de l'identifiant `qwen/qwen3.8-27b` chez Groq : il vient de la configuration, pas d'un test.
- **Prompt système** : `SYNTHESIZER_SYSTEM_PROMPT` (`prompts.py:55-83`), en anglais : pas de préambule, zéro emoji, chiffres uniquement issus de `MATCH_FACTS`, vérification des remplacements, rejet des questions hors sujet (règle 6).
- **Contexte envoyé** (l. 97-101) : `COACH_QUERY`, `MATCH_FACTS` (texte formaté), `THEORETICAL_KNOWLEDGE` (4 extraits max avec citation exacte). En mode micro, seule la phase de la tranche est injectée (l. 35-37, 53-55) ; en macro, la structure des phases est ajoutée (l. 39-49). Si le critique a refusé, son retour est ajouté (l. 103-108).
- Le prompt `FEW_SHOT_GOLD_STANDARD` (`prompts.py:24-53`) est défini mais **n'est importé nulle part** dans le synthétiseur (seul `SYNTHESIZER_SYSTEM_PROMPT` l'est, l. 9) : l'exemple de référence n'est pas envoyé au modèle.
- **Nettoyage de sortie** : suppression des balises `<think>`, coupe de tout ce qui précède « ### Part 1 » (l. 142-150).
- **Repli** si le LLM échoue : rapport générique codé en dur, avec des exercices fixes (l. 117-140).

### Structure du rapport (3 parties, `prompts.py:64-79`)

1. **Part 1 : Tactical Diagnosis & Identified Vulnerabilities.** Macro : phases chronologiques exactes avec leurs noms. Micro : 3 à 4 puces (zone 14, demi-espaces, pertes sous pression, événements décisifs).
2. **Part 2 : Tactical Principles & Theoretical Grounding.** Jusqu'à 2 principes, chacun *commençant* par un fait chiffré du match (« Golden Anchoring »), puis la théorie avec citation exacte `[Auteur, Année - Titre]`. Si aucune source pertinente : phrase imposée « No sufficiently relevant source in the knowledge base… ».
3. **Part 3 : Prescriptions & Training Drills (UEFA Pro Standard).** 2 fiches d'exercice : nom et thème, *Setup & Pitch*, *Rules & Flow*, *Coaching Points / Success Criteria*.

Il n'y a pas de partie « résumé » ni de section de conclusion. Le rapport est en **anglais** alors que le code et la documentation sont en français.

### Exercices d'entraînement

Générés **dans le même appel LLM** que le reste du rapport (Part 3), selon le gabarit du prompt (`prompts.py:74-79`). **Absent du code** : nœud dédié, base d'exercices, schéma de données pour les exercices, validation des dimensions ou des effectifs. Ni le critique ni un test ne vérifient la partie 3 (voir §6). Les exercices ne sont donc ni sourcés ni contrôlés.

---

## 6. Critique (nœud 4)

Fichier : `src/agent/nodes/critic_node.py:43-139`. Modèle : le même « fast » que le routeur, température 0 (l. 53) ; sortie `VerificationVerdict` (`src/schemas/critic.py:20-58`).

### Vérifié par du code (déterministe)
| Contrôle | Où |
|---|---|
| Toute citation `[Auteur, Année - Titre]` du rapport doit correspondre (après normalisation casse/espaces/tirets) à un des extraits réellement fournis ; sinon anomalie `invalid_citation` et **FAIL forcé** | `critic_node.py:17-40, 113-123` ; `src/rag/citations.py:11-33` |
| Si le LLM juge `is_anchored=False` → anomalie ajoutée et **FAIL forcé** (la décision est prise en code sur un booléen produit par le LLM) | `critic_node.py:97-111` |
| Échec technique du critique → **FAIL** (jamais PASS par défaut) | `critic_node.py:73-93` |
| Boucle de correction : FAIL et `iteration_count < 2` → retour au synthétiseur ; sinon fin | `graph.py:17-30` |
| Coercition des booléens renvoyés en chaîne | `critic.py:54-58` |

### Jugé par le LLM (non vérifié par du code)
- **Fidélité numérique** : les chiffres, pourcentages, minutes, xG correspondent-ils à `MATCH_FACTS` (`is_faithful`, `faithfulness_score`) ; inversion d'équipes ; cohérence des remplacements ; respect des phases (`prompts.py:85-99`). **Aucun contrôle par regex ou comparaison numérique** n'existe dans le code.
- Si une citation *valide* soutient réellement l'affirmation (`is_fully_cited`).
- Le verdict `PASS`/`FAIL` initial et le score de fidélité.
- **Rien ne contrôle la partie 3** (exercices), ni la présence des trois parties.

Limites de forme : le critique reçoit `SOURCES_SUFFICIENT: bool(retrieved_chunks)` et non la valeur de l'état (l. 67). Le motif de citation exige le format `[Auteur, Année - Titre]` ; une citation du format `[Titre, Année]` (cas d'un chunk sans auteur, `chunker.py:38-41`) n'est jamais extraite par la regex, donc jamais contrôlée.

---

## 7. Interface

- **Framework** : **Streamlit** (`app.py`, `requirements.txt:24`), page large, thème clair par CSS maison (`src/ui/styles.css`), Plotly pour le graphique de latence.
- **Onglet 1 « Tactical Analysis »** (`app.py:190-634`) :
  - portail de sélection de match (cartes) puis bandeau de match ;
  - boutons de phases (générées par LLM + « Global ») ;
  - barre de question libre, protégée par `SecurityGuardrails` (regex) et un délai de 3 s entre exécutions (`app.py:490-501`) ;
  - 4 KPI domicile/extérieur recalculés en SQL (`app.py:546-576`) ;
  - colonne gauche : frise des événements décisifs (`report_renderer.py:57-166`) + tableau détaillé des faits **seulement si** `match_facts` est présent (`app.py:591-593`) ;
  - colonne droite : rapport en 3 accordéons (`report_renderer.py:169-237`) + panneau de références (`report_renderer.py:40-54`).
- **Citations** : affichées sous forme de liste de chaînes de citation uniquement (pas d'extrait de texte ni de score).
- **Onglet 2 « Supervision & Benchmark »** (`app.py:639-656`) : télémétrie (latence totale, fidélité, latences par nœud + histogramme, `admin_dashboard.py:17-69`), banc d'essai multi-modèles, explorateur du corpus RAG, console SQL en lecture seule.
- **Non affiché** : le **verdict du critique** (PASS/FAIL) et ses anomalies ne sont montrés nulle part. Seule la note de fidélité apparaît, avec **0,95 par défaut si absente** (`admin_dashboard.py:28`). Un rapport refusé deux fois s'affiche donc exactement comme un rapport validé.
- Textes en dur périmés : « 3 MATCHES AVAILABLE » (`app.py:226`) alors que 4 matchs sont en base ; « 305 chunks » (`admin_dashboard.py:73-74`) alors que le corpus en compte 977.

---

## 8. État LangGraph (`TacticalAgentState`, `src/schemas/state.py:23-59`)

| Champ | Type | Écrit par | Lu par |
|---|---|---|---|
| `coach_query`, `match_id`, `thread_id`, `user_time_range` | entrées | `run_tactical_analysis` (`graph.py:85-102`) | tous |
| `tactical_plan` | `TacticalPlan` | **router** (`router_node.py:133`) | sql_miner, deep_rag |
| `match_facts` | `MatchFacts` | **sql_miner** (`sql_miner_node.py:45`) | deep_rag, synthesizer, critic |
| `retrieved_chunks` | liste de dict | **deep_rag** (`deep_rag_node.py:94`) | synthesizer, critic |
| `sources_sufficient` | `Optional[bool]` | **deep_rag** (l. 95) | synthesizer |
| `draft_report` | `str` | **synthesizer** (`synthesizer_node.py:158`) | critic, fin de pipeline |
| `iteration_count` | `int` | **synthesizer** (+1, l. 159) | arête conditionnelle |
| `critic_verdict` | `VerificationVerdict` | **critic** (`critic_node.py:136`) | arête conditionnelle |
| `critic_feedback` | `Optional[str]` | **critic** (l. 137) | synthesizer (relance) |
| `execution_telemetry` | dict, reducer `merge_telemetry` (l. 13-20, 59) | **tous les nœuds** | UI |
| `final_report` | `Optional[str]` | **aucun nœud** : recopié depuis `draft_report` hors graphe (`graph.py:108-109`) | UI |
| `is_human_approved`, `analyst_modifications` | `bool`, `Optional[str]` | **personne** : initialisés puis jamais lus ni écrits | — |

Le commentaire « Nœud 5 (Human-in-the-loop) » (`state.py:53`) correspond à un nœud **inexistant** (`graph.py:44-48` n'en déclare que 5 : router, sql_miner, deep_rag, synthesizer, critic).

Topologie (`graph.py:51-65`) : `router → sql_miner → deep_rag → synthesizer → critic → (synthesizer | END)`. Les deux branches RAG/SQL sont **séquentielles**, volontairement (RAG guidé par la donnée). Checkpointer : `MemorySaver` en mémoire (l. 33, 68).

---

## 9. Déploiement

**Lancement local**
```bash
pip install -r requirements.txt
cp .env.example .env            # puis renseigner GROQ_API_KEY
python ingest_statsbomb.py      # crée data/statsbomb_foot.db (réseau requis)
python index_knowledge_base.py  # crée BM25 + ChromaDB (documents requis dans data/)
streamlit run app.py            # port 8501
```
**Docker** : `Dockerfile` (Python 3.12-slim, `streamlit run app.py` sur 0.0.0.0:8501, l. 30) et `docker-compose.yml` (port 8501, volume `./data:/app/data`, healthcheck Streamlit, l. 15-22). Les données ne sont pas dans l'image utile : elles doivent exister dans `./data` sur l'hôte.

**Dépendances** (`requirements.txt`) : pydantic, statsbombpy, pandas, numpy, chromadb, rank-bm25, sentence-transformers, fastembed, langchain, langgraph, langchain-groq, python-dotenv, streamlit, plotly, pytest, etc. **Absents du fichier** alors que le code les importe selon le fournisseur : `langchain-openai`, `langchain-google-genai`, `langchain-community` (`llm_factory.py:152, 163, 174`).

**Variables d'environnement**
| Variable | Rôle | Source |
|---|---|---|
| `LLM_PROVIDER` | `groq` (défaut), `openai`, `gemini`/`google`, `ollama` | `llm_factory.py:114` |
| `GROQ_API_KEY` | clé Groq | `llm_factory.py:126` |
| `GROQ_FAST_MODEL`, `GROQ_REASONING_MODEL` | surcharge des modèles | `llm_factory.py:130, 195` |
| `OPENAI_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY` | autres fournisseurs | `llm_factory.py:127-128` |
| `ENVIRONMENT`, `LOG_LEVEL` | présentes dans `.env.example` / compose ; **non lues par le code Python** (grep sur `src/` et `app.py`) | `.env.example:10-11` |

Tests : `pytest` (`pytest.ini`). Lancés dans `.venv` : **72 tests passés en 146 s**. Avec le Python système, la collecte échoue (dépendances absentes) : il faut utiliser le venv.

---

## 10. Les 5 points les plus fragiles (par gravité décroissante)

1. **Le cache sémantique est vidé à chaque exécution du script Streamlit (grave, vérifié).** `app.py:9-11` recharge le module à chaque rerun, ce qui recrée un singleton vide (test exécuté : nouvelle instance, 0 entrée). Les métriques « latence d'un hit » et « coût zéro » du cache ne se réalisent donc pas dans l'application. De plus, un rapport refusé par le critique y serait mémorisé (`app.py:414-422`), et un hit n'affiche ni citations ni faits.
2. **La fidélité numérique, promesse centrale du produit, repose uniquement sur un LLM.** Aucun contrôle programmatique des chiffres (§6) ; le critique est le modèle « rapide » (gpt-oss-20b par défaut). En plus, après 2 tentatives (`graph.py:28`) le brouillon est servi même en FAIL (`graph.py:108-109`) et l'interface n'affiche pas le verdict (§7) ; la note de fidélité par défaut est 0,95 (`admin_dashboard.py:28`). Un utilisateur ne peut pas distinguer un rapport validé d'un rapport refusé.
3. **Repli silencieux sur le modèle factice.** Sans clé valide, ou si l'import du fournisseur échoue, `LLMFactory` renvoie `MockChatModel` sans erreur ni avertissement (`llm_factory.py:179, 244`) ; ce mock produit un critique qui répond toujours PASS (l. 55-66) et un rapport avec des chiffres de la finale **codés en dur** (l. 94-102). Bug supplémentaire : la branche Gemini exige `not key.startswith("AIza")` (`llm_factory.py:161, 226`), alors que `.env.example:7` montre qu'une vraie clé commence par `AIza` : avec une vraie clé Gemini, le fournisseur est ignoré et le mock est utilisé. Le compose injecte aussi une clé factice par défaut (`docker-compose.yml:13`). Un rapport de démonstration peut donc être pris pour une analyse réelle.
4. **Le mode « Global » est mal classé pour 3 matchs sur 4.** Le mode micro est décidé par `durée < 100` (`synthesizer_node.py:27`, `router_node.py:90`). La phase « Global » d'un match de 90-96 minutes (c'est le cas des trois matchs hors finale, d'après `data/cached_phases.json` : fin à 96, 95, 93) est traitée comme une séquence précise : le plan passe en `DIAGNOSTIC_SEQUENCE`, le synthétiseur n'injecte pas la structure des phases et interdit d'analyser d'autres phases (l. 35-37). Seule la finale (0-120) reçoit le vrai traitement macro.
5. **Pipeline calé sur un seul match et sur des données fixes.** La table de joueurs du routeur (`router_node.py:48-73`), les profils de phases par `match_id` (`match_miner.py:487-593`, fonction inutilisée), l'équipe de repli « Argentina/France » (`sql_miner_node.py:34`, `router_node.py:95`) et les équipes de la liste d'exemples sont spécifiques à la finale 2022. S'ajoutent : la finale est le seul match avec un jeu de phases validé à la main ; `significant_deltas` ne porte que sur une métrique et n'est pas filtré ni trié (§4.3) ; la qualité des statistiques de `LIKE '%"pass_outcome"%'` sur du JSON texte dépend du format exact de sérialisation (`queries.py:21, 25`), sans test de non-régression visible ici. Cette fragilité est moins immédiate que les quatre premières, mais elle limite la généralisation à d'autres matchs.

Autres points mineurs repérés : bug latent dans le repli du routeur (`meta` utilisé alors qu'il peut ne pas être défini si la lecture des métadonnées a échoué, `router_node.py:95`) ; latence totale sous-estimée lors d'une relance, car la latence du synthétiseur est écrasée à chaque passage (`synthesizer_node.py:155`, `graph.py:112-118`) ; garde-fous (`guardrails.py`) appliqués uniquement à la question libre, pas aux boutons de phase, et limités à quelques regex.

---

## Parcours d'une requête, de l'entrée au rapport

```
UTILISATEUR (Streamlit, app.py)
  choisit un match ──► SELECT matches/events (SQLite, lecture seule)
  clique une phase  ou  tape une question + « Run Analysis »
        │
        ▼
  [saisie libre uniquement] SecurityGuardrails (regex injection / hors-sujet)   app.py:499
        │
        ▼
  CACHE SÉMANTIQUE .get(question, match_id, time_range)                         app.py:395/435/503
     │ hit (cosinus ≥ 0.93, même match, même tranche) ──► rapport + télémétrie ─┐
     │ miss                                                                      │
     ▼                                                                           │
  run_tactical_analysis → graphe LangGraph (graph.py:36-69)                      │
     │                                                                           │
     ├─► 1. ROUTER  (LLM rapide, sortie TacticalPlan + corrections en code)      │
     │        ▼                                                                  │
     ├─► 2A. SQL MINER  (requêtes fixes SQLite → MatchFacts, deltas vs moyenne)  │
     │        ▼                                                                  │
     ├─► 2B. DEEP RAG  requête = question + topics + zones + 2 clés de deltas    │
     │        BM25 (15) + dense Chroma (15) → fusion RRF → cross-encoder         │
     │        → 4 chunks max, filtre score ≥ -4.0 → sources_sufficient           │
     │        ▼                                                                  │
     ├─► 3. SYNTHESIZER  (LLM raisonnement) → rapport en 3 parties               │
     │        (diagnostic / principes cités / exercices)  ◄─────────┐            │
     │        ▼                                                      │ FAIL      │
     └─► 4. CRITIC  citations vérifiées par code + fidélité par LLM ─┘ et         │
              │                                                      itération<2 │
              ▼ (PASS, ou FAIL après 2 passages)                                 │
            END → final_report = draft_report  (graph.py:108)                    │
        │                                                                        │
        ├─► GLOBAL_SEMANTIC_CACHE.set(...)   (puis st.rerun)                     │
        ▼                                                                        ▼
  AFFICHAGE : 3 accordéons (rapport) + références + frise d'événements + KPI SQL
  ONGLET SUPERVISION : latences par nœud, fidélité, benchmark, corpus, console SQL
```
