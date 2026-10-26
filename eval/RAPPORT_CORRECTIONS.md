# Rapport des corrections RAG (branche `fix/rag-reliability`)

Ce rapport mesure le **retrieval** (quels chunks remontent, avec quels scores). Il ne mesure pas encore la qualité des réponses générées (voir section 7). Les données brutes sont dans `eval/results_before.json` et `eval/results_after.json`, produites par `eval/snapshot_retrieval.py` sur `eval/baseline_queries.json` (12 requêtes en corpus, 3 hors sujet).

## 1. Commits

| Commit | Changement |
|---|---|
| `37c2756` | eval: requetes de reference et snapshot du retrieval (etat avant correction) |
| `27b9ebb` | rag: seuil de pertinence du reranker et indicateur sources_sufficient |
| `71119d5` | synthese: jusqu'a 2 principes, uniquement s'ils sont soutenus par les extraits |
| `72ab700` | critique: verification programmatique des citations |
| `a86bd27` | critique: champ is_anchored dans le schema et dans la boucle de correction |
| `467c370` | chunking: tailles mesurees en tokens du modele d'embedding, regle unique PDF/Markdown |
| `ea78709` | embedding: le titre et la section sont inclus dans le texte embedde |
| `274a752` | synthese/critique: chunks transmis en entier (suppression des troncatures 800 et 300 caracteres) |
| `9e2421f` | docs: nombre de chunks apres re-indexation (305 -> 977) |
| `b558c55` | rag: retrieval BM25/dense conserve en sequentiel (gain parallele mesure negligeable) |

Écarts par rapport à la mission, à connaître :

- **Requête du reranker (ajout annulé).** J'avais fait scorer le reranker sur `topics + zones` du plan pour contourner les questions en français. Décision de périmètre ultérieure : foot-GPT est en anglais uniquement, ce changement est annulé et le reranker score la même requête enrichie que BM25 et le dense. Effet constaté : sur 5 questions anglaises réalistes passées dans le pipeline (plan simulé), 4 obtiennent un meilleur score entre -3,6 et -1,2, donc `sources_sufficient=False` au seuil 0,0 ; les clés de deltas (« Argentina turnovers 0 40 ») ajoutées à la requête font baisser les scores. Les 15 requêtes de référence, elles, ne contiennent pas ce bruit : la calibration de la section 4 est optimiste pour les requêtes réelles.
- Le Markdown ne préfixe plus le contenu des chunks par `### section` (la section est une métadonnée, ajoutée au texte embeddé, BM25 et reranker).
- Le brouillon de repli du synthétiseur (erreur LLM) citait en dur `[Bauer & Anzer, 2026 ...]` ; il ne cite plus que les sources récupérées.
- Le `MockChatModel` ne cite plus que les sources présentes dans son prompt, et renvoie `is_anchored=True`.
- Un commit intermédiaire (synthèse) avait été fait alors que 4 tests que je venais d'écrire échouaient (erreur d'import dans le test) ; je l'ai amendé avant la suite. Tous les tests passent à la fin de chaque commit suivant.

## 2. Tableau avant / après

| Mesure | Avant | Après |
|---|---|---|
| Nombre de chunks | 305 | 977 |
| Tokens médians par chunk (texte embeddé) | 565 | 203 |
| Tokens p90 / max | 758 / 1352 | 231 / 247 |
| Chunks tronqués par l'embedding (> 254 tokens) | 85.2 % | 0.0 % |
| Part moyenne du texte vue par l'embedding | 55.0 % | 100.0 % |
| Part moyenne d'un chunk lue par le synthétiseur | 42,6 % (800 car.) | 100 % |
| Part moyenne d'un chunk lue par le critique | 17,2 % (300 car.) | 100 % |
| Contexte théorique du synthétiseur (requêtes en corpus, moyenne) | 853 tokens (3722 car.) | 835 tokens (3945 car.) |
| Contexte théorique du synthétiseur (max) | 1187 tokens | 1001 tokens |
| Extraits reçus par le critique (moyenne) | 391 tokens | 819 tokens |
| Contexte théorique, requêtes hors sujet | ~780 à 860 tokens de sources non pertinentes | 0 (marqueur « aucune source ») |

Notes de lecture :

- « Avant » : l'embedding ne voyait que le contenu ; « après », il voit titre + section + contenu, et ce total est borné. Tokens = tokenizer de `all-MiniLM-L6-v2` (bornes de l'embedding) ; ils servent aussi d'approximation pour le contexte LLM, dont le tokenizer diffère.
- Les chunks sont plus nombreux et plus courts (médiane 203 tokens, soit environ 770 caractères) : le synthétiseur reçoit toujours 4 chunks, mais **complets**, pour un volume de contexte équivalent (835 contre 853 tokens). Le contexte du critique double (391 à 819 tokens), ce qui est le coût de la vérification sur texte complet.
- Le « avant » du contexte est reconstruit en rechargeant le chunking du commit initial (305 chunks retrouvés à l'identique) puis en appliquant les troncatures de 800 et 300 caractères.

## 3. Résultats par requête

Les identifiants de chunks ne sont pas comparables un à un (le découpage a changé) ; comparer les documents et les scores. « Avant » : toujours 4 chunks, sans filtre. « Après » : chunks gardés par le pipeline réel (`search_detailed`, seuil `RERANK_MIN_SCORE = 0.0`).

| Requête | Avant : top 4 (score reranker) | Après : chunks gardés (score) | `sources_sufficient` après |
|---|---|---|---|
| **q01** (en corpus) How does a team protect itself against counters through rest-defense when attacking? Rest- | 02_tactical_structures_and_spatial_dynamics_c3 (4.4199)<br>tactics_rest_defense_forms_c4 (3.9294)<br>tactics_rest_defense_forms_c1 (3.7876)<br>tactics_rest_defense_forms_c15 (3.4983) | tactics_rest_defense_forms_c13 (5.4051)<br>tactics_rest_defense_forms_c3 (5.3869)<br>02_tactical_structures_and_spatial_dynamics_c3 (4.6326)<br>tactics_rest_defense_forms_c46 (3.8112) | True |
| **q02** (en corpus) Exploiting the half-spaces to overload the opponent's defensive line | tactics_the_half_spaces_c7 (4.2304)<br>tactics_the_half_spaces_c10 (4.1365)<br>tactics_the_half_spaces_c11 (4.1267)<br>tactics_the_half_spaces_c9 (3.9646) | tactics_the_half_spaces_c46 (4.191)<br>tactics_the_half_spaces_c45 (3.2956)<br>01_football_game_phases_and_core_principles_c3 (3.1749)<br>tactics_the_half_spaces_c6 (3.1688) | True |
| **q03** (en corpus) Counterpressing after ball loss to win the ball back within seconds | tactics_counter_or_gegenpressing_c3 (4.8727)<br>tactics_counter_or_gegenpressing_c1 (4.2555)<br>tactics_counter_or_gegenpressing_c4 (4.0526)<br>tactics_counter_or_gegenpressing_c5 (3.5898) | tactics_counter_or_gegenpressing_c4 (5.4813)<br>tactics_counter_or_gegenpressing_c16 (5.393)<br>tactics_counter_or_gegenpressing_c2 (5.0895)<br>tactics_counter_or_gegenpressing_c9 (4.9817) | True |
| **q04** (en corpus) Variations of counterpressing and when to drop instead of pressing | tactics_counterpressing_variations_c1 (5.1425)<br>tactics_counterpressing_variations_c2 (5.0316)<br>tactics_counterpressing_variations_c3 (4.6518)<br>tactics_counter_or_gegenpressing_c3 (2.4915) | tactics_counterpressing_variations_c7 (5.6963)<br>tactics_counterpressing_variations_c1 (5.5253)<br>tactics_counterpressing_variations_c11 (5.2449)<br>tactics_counterpressing_variations_c8 (5.1905) | True |
| **q05** (en corpus) Zonal marking and zonal coverage of space in the defensive block | tactics_zonal_marking_coverage_c2 (7.0235)<br>tactics_zonal_marking_coverage_c1 (6.7232)<br>tactics_zonal_marking_coverage_c3 (6.04)<br>tactics_zonal_marking_coverage_c5 (5.8004) | tactics_zonal_marking_coverage_c2 (7.0981)<br>tactics_zonal_marking_coverage_c7 (6.9398)<br>tactics_zonal_marking_coverage_c17 (6.5874)<br>tactics_zonal_marking_coverage_c5 (6.5391) | True |
| **q06** (en corpus) Positional play and juego de posicion principles of Guardiola | tactics_juego_de_posicion_c10 (6.4143)<br>tactics_juego_de_posicion_c2 (5.8909)<br>tactics_juego_de_posicion_c3 (5.6109)<br>tactics_juego_de_posicion_c7 (5.368) | tactics_juego_de_posicion_c2 (5.9731)<br>tactics_juego_de_posicion_c26 (5.3518)<br>tactics_juego_de_posicion_c23 (5.0862)<br>tactics_juego_de_posicion_c22 (4.6038) | True |
| **q07** (en corpus) Vertical build-up passing through the lines against a high press | tactics_vertical_buildup_passing_c8 (6.5072)<br>tactics_vertical_buildup_passing_c9 (5.9391)<br>tactics_vertical_buildup_passing_c10 (5.6573)<br>tactics_vertical_buildup_passing_c1 (5.0524) | tactics_vertical_buildup_passing_c32 (7.6653)<br>tactics_vertical_buildup_passing_c27 (7.4142)<br>tactics_vertical_buildup_passing_c33 (6.3079)<br>tactics_vertical_buildup_passing_c35 (5.9595) | True |
| **q08** (en corpus) Dismarking methods to lose a marker and receive between the lines | tactics_dismarking_methods_c4 (4.3589)<br>tactics_dismarking_methods_c11 (3.8272)<br>tactics_dismarking_methods_c2 (3.5196)<br>tactics_dismarking_methods_c7 (3.3301) | tactics_dismarking_methods_c12 (5.6334)<br>tactics_dismarking_methods_c4 (4.8851)<br>tactics_dismarking_methods_c32 (4.4156)<br>tactics_dismarking_methods_c7 (3.22) | True |
| **q09** (en corpus) Blind side movement and exploiting the blind side of defenders | tactics_blind_side_potential_c6 (8.1227)<br>tactics_blind_side_potential_c13 (6.9627)<br>tactics_blind_side_potential_c16 (6.4347)<br>tactics_blind_side_potential_c10 (6.3129) | tactics_blind_side_potential_c18 (8.49)<br>tactics_blind_side_potential_c39 (7.5089)<br>tactics_blind_side_potential_c52 (7.3866)<br>tactics_blind_side_potential_c4 (7.1154) | True |
| **q10** (en corpus) Passing network centrality and team vulnerability when key players are marked | 03_tactical_periodization_and_complex_systems_c4 (4.0969)<br>zhang_2024_motif_analysis_passing_networks_p13_c1 (3.8759)<br>dandrea_2025_high_performance_passing_networks_p19_c1 (3.8406)<br>zhang_2024_motif_analysis_passing_networks_p9_c1 (2.9633) | zhang_2024_motif_analysis_passing_networks_p13_c2 (4.7406)<br>zhang_2024_motif_analysis_passing_networks_p12_c2 (4.5289)<br>zhang_2024_motif_analysis_passing_networks_p12_c4 (3.9841)<br>dandrea_2025_high_performance_passing_networks_p11_c3 (3.9636) | True |
| **q11** (en corpus) Valuing player actions with VAEP and expected threat models | bauer_2026_structural_pass_analysis_tracking_p5_c1 (3.7253)<br>decroos_2020_valuing_player_actions_vaep_p18_c1 (3.5593)<br>decroos_2020_valuing_player_actions_vaep_p26_c1 (3.5325)<br>decroos_2020_valuing_player_actions_vaep_p3_c1 (3.5221) | bauer_2026_structural_pass_analysis_tracking_p2_c2 (6.3075)<br>decroos_2020_valuing_player_actions_vaep_p19_c1 (5.0905)<br>decroos_2020_valuing_player_actions_vaep_p26_c3 (4.9592)<br>bauer_2026_structural_pass_analysis_tracking_p5_c1 (4.8555) | True |
| **q12** (en corpus) Line-breaking passes and clustering of passing sequences | rijsdijk_2025_line_breaking_passes_clustering_p8_c1 (5.6947)<br>rijsdijk_2025_line_breaking_passes_clustering_p5_c1 (5.2204)<br>rijsdijk_2025_line_breaking_passes_clustering_p12_c1 (5.1942)<br>rijsdijk_2025_line_breaking_passes_clustering_p6_c1 (5.0073) | rijsdijk_2025_line_breaking_passes_clustering_p8_c1 (7.0726)<br>bauer_2026_structural_pass_analysis_tracking_p21_c2 (6.0808)<br>rijsdijk_2025_line_breaking_passes_clustering_p3_c3 (5.9222)<br>rijsdijk_2025_line_breaking_passes_clustering_p5_c1 (5.8086) | True |
| **o01** (hors sujet) What is the correct scrum engagement technique and how do rugby props bind on the loosehea | tactics_the_half_spaces_c7 (-5.1549)<br>tactics_blind_side_potential_c17 (-5.2044)<br>tactics_dismarking_methods_c12 (-6.2141)<br>tactics_blind_side_potential_c16 (-6.3727) | aucun chunk >= seuil | False |
| **o02** (hors sujet) How many grams of protein per day should a marathon runner eat and which carbohydrates are | tactics_dismarking_methods_c10 (-11.1369)<br>tactics_vertical_buildup_passing_c10 (-11.1409)<br>tactics_compactness_c10 (-11.164)<br>rijsdijk_2025_line_breaking_passes_clustering_p9_c1 (-11.1641) | aucun chunk >= seuil | False |
| **o03** (hors sujet) How does the video assistant referee review protocol work for offside and penalty decision | dandrea_2025_high_performance_passing_networks_p17_c1 (-7.7825)<br>tactics_the_half_spaces_c5 (-8.0301)<br>bauer_2026_structural_pass_analysis_tracking_p1_c1 (-8.2936)<br>bauer_2026_structural_pass_analysis_tracking_p43_c1 (-9.0592) | aucun chunk >= seuil | False |

**Requêtes hors sujet signalées comme non couvertes : 3/3.** Requêtes en corpus gardant leurs 4 chunks : 12/12.

## 4. Calibration du seuil `RERANK_MIN_SCORE`

| Indicateur (score brut du cross-encoder) | Avant | Après ré-indexation |
|---|---|---|
| Plus bas score parmi les 48 chunks du top 4 (requêtes en corpus) | 2.4915 | 3.1688 |
| Plus bas top 1 (requêtes en corpus) | 3.7253 | 4.191 |
| Meilleur score toutes requêtes hors sujet | -5.1549 | -6.9322 |

- Le cross-encoder `ms-marco-MiniLM-L-6-v2` sort un logit : 0 correspond à une probabilité de pertinence de 0,5, frontière naturelle du modèle.
- L'écart entre bons et mauvais chunks est large : de -5.1549 à 2.4915 avant, de -6.9322 à 3.1688 après. Toute valeur dans cet intervalle sépare les 15 requêtes ; 0,0 est choisi parce qu'il est à peu près au milieu de l'écart et que ce n'est pas une valeur ajustée aux 15 requêtes.
- Le seuil a été fixé sur l'état « avant » puis revalidé après ré-indexation (les chunks plus courts n'ont pas fait bouger la séparation).
- Limite de cette calibration : les 3 requêtes hors sujet (rugby, nutrition, arbitrage vidéo au cricket) sont très éloignées du football. Une question de football **non couverte** (gardien de but, coups de pied arrêtés) peut obtenir un score entre 0 et 3 et passer le filtre. Il faudrait quelques requêtes « football mais hors corpus » pour affiner ; je n'en ai pas inventé pour ne pas ajuster le seuil à ma propre intuition.
- Le filtre est désactivé si le cross-encoder n'est pas chargé (le repli en 1/rang n'a pas la même échelle) ; `rag_relevance_filter_active` le signale dans la télémétrie.

## 5. Vérifications de l'étape 3b (constats, sans correction)

**Retrieval parallèle (3a).** Mesuré sur 45 appels (15 requêtes × 3), index de 977 chunks : BM25 1,2 ms, dense 3,8 ms, séquentiel 5,0 ms, `ThreadPoolExecutor` 5,1 ms. Gain nul : le séquentiel est conservé. La documentation qui parle de retrieval « parallèle » est donc inexacte (section 6).

**Cache sémantique.** Il existe : `src/cache/semantic_cache.py`, embeddings FastEmbed `BAAI/bge-small-en-v1.5`, similarité cosinus >= 0,93, clé `(requête, match_id, time_range)`.
- Latence mesurée de `get()` avec le modèle chargé et 2 entrées : **2,5 à 2,8 ms** (hit), 1,6 ms (miss). L'ordre de grandeur « < 10 ms » tient donc, mais seulement à chaud : le premier appel charge le modèle (~240 ms) et le cache est en mémoire du processus (perdu au redémarrage).
- **Mais la latence affichée n'est pas mesurée** : `semantic_cache.py` écrit `telemetry["total_pipeline_latency_ms"] = 8.5` en dur pour tout hit. Le chiffre montré dans l'interface est une constante.
- Les embeddings du cache (`bge-small`) sont différents de ceux du RAG (`all-MiniLM-L6-v2`) ; sans conséquence fonctionnelle, mais la documentation les mélange parfois (`PIPELINE_RAG_HYBRIDE.md` cite FastEmbed pour le RAG).

**URL d'archive dans les citations.** Non. La citation est la chaîne `[Auteur, Année - Titre]` ; l'URL source est dans les métadonnées (`source_url`) mais n'est pas affichée (`render_citations_panel` n'affiche que `chunk['citation']`). Les URL sont des liens directs (arXiv pour les papiers, spielverlagerung.com pour les articles, `file://` pour les guides) ; aucune URL d'archive (Wayback ou autre). Les articles Spielverlagerung dépendent donc de la disponibilité du site.

**`generate_high_level_guides.py` désynchronisé : oui.** Ses constantes `GUIDE_*_MD` sont en français (« Guide High-Level 1 : Les 4 Phases du Jeu... »), alors que `data/high_level_guides/*.md` (indexés) sont en anglais (« High-Level Guide 1: The 4 Phases of Play... »). Le script écrit dans ce même dossier : **le relancer écraserait les guides anglais par des versions françaises**, qui seraient ensuite réindexées dans un corpus anglais interrogé par un cross-encoder anglais. Aucun appel LLM dans ce script : les textes sont codés en dur ; je n'ai trouvé aucune trace de leur validation.

Correction ultérieure : les 3 guides ont maintenant `year: 2026` dans leur frontmatter ; leurs citations sont `[foot-GPT Technical Staff, 2026 - High-Level Guide N: ...]` et la regex les reconnaît (21 citations distinctes dans l'index, toutes reconnues). Choix : une année explicite plutôt qu'une regex étendue à `[Titre]`, qui aurait aussi reconnu n'importe quel crochet du rapport (`[Part 1]`) et créé des faux positifs.

## 6. Affirmations de la documentation et du portfolio à corriger ou nuancer

Rien n'a été modifié ici (le portfolio est exclu du dépôt via `.git/info/exclude` et n'a pas été touché). Les chiffres de chunks de `state.md` et `PIPELINE_RAG_HYBRIDE.md` ont été mis à jour (étape 2d) ; le reste est à traiter.

| Affirmation | Où | Statut |
|---|---|---|
| « 305 chunks » / « Corpus (305 Chunks) » | PORTFOLIO_CASE_STUDY.md (l. 51, 150, 276) | Faux après ré-indexation : 977 chunks |
| « Double Retrieval Parallèle (Top 15 chacun) » | PIPELINE_RAG_HYBRIDE.md (schéma l. 27) | Faux : BM25 puis dense en séquence ; gain parallèle mesuré nul (5,0 contre 5,1 ms) |
| « les 4 chunks finaux injectés au LLM », « retourne les 4 chunks les plus pertinents » | PIPELINE_RAG_HYBRIDE.md §3.3, ARCHITECTURE_LANGGRAPH.md l. 89, PORTFOLIO_CASE_STUDY.md l. 198 | À nuancer : jusqu'à 4, après filtre de pertinence ; 0 si aucune source n'atteint le seuil |
| « Les 30 candidats fusionnés » | PIPELINE_RAG_HYBRIDE.md §3.3 | À nuancer : jusqu'à 30 (union dédoublonnée de 15 + 15) |
| Chaque principe est appuyé par une citation réelle / « Tout principe doit être cité » (au moins 2 principes) | ARCHITECTURE_LANGGRAPH.md l. 100, PORTFOLIO_CASE_STUDY.md l. 27, 201 | À nuancer : jusqu'à 2 principes, uniquement si les extraits les soutiennent ; sinon le rapport indique l'absence de source |
| Sortie du critique `VerificationVerdict` (`is_faithful`, `faithfulness_score`, `is_fully_cited`, `citation_coverage_score`, `anomalies`, `verdict`) | ARCHITECTURE_LANGGRAPH.md l. 101 | Incomplet : champ `is_anchored` ajouté, catégories d'anomalie `invalid_citation` et `unanchored_principle` ajoutées |
| « Citations formelles vérifiées » / « analyse certifiée à 100 % sans hallucination » | PORTFOLIO_CASE_STUDY.md l. 251, GUIDE_LATENCE_TOKENS_LLMOPS.md l. 13, 73 | À nuancer : la vérification des citations est maintenant programmatique mais partielle (section 7) ; le « 100 % » n'est mesuré nulle part (score du juge LLM) |
| Score Faithfulness « 0,95 à 1,00 » | PIPELINE_RAG_HYBRIDE.md §4, GUIDE_LATENCE_TOKENS_LLMOPS.md l. 9 | Mesuré avant ces corrections et par un juge LLM ; à re-mesurer. Pas de ré-évaluation faite ici |
| Cache « < 10 ms » | GUIDE_LATENCE_TOKENS_LLMOPS.md l. 52, PORTFOLIO_*.md | À nuancer : ~2,5 ms mesuré à chaud, mais la valeur affichée (8,5 ms) est une constante codée en dur, et le premier appel coûte ~240 ms |
| « L'injection de 4 chunks théoriques complets alourdit le prompt » | GUIDE_LATENCE_TOKENS_LLMOPS.md l. 86 | Faux avant (chunks tronqués à 800 caractères, 42,6 % du texte) ; vrai maintenant, pour un volume équivalent (~835 tokens) |
| « Parallélisation async sql_miner + deep_rag (-30 % latence) » | GUIDE_LATENCE_TOKENS_LLMOPS.md l. 69, 78 ; ARCHITECTURE_LANGGRAPH.md l. 111 | Non concerné par ces corrections (c'est une roadmap), mais le « -30 % » n'est pas mesuré ; le retrieval lui-même ne coûte que ~5 ms |
| Le RAG utilise FastEmbed ; Tech Stack « FastEmbed » | PIPELINE_RAG_HYBRIDE.md l. 4, PORTFOLIO_CASE_STUDY.md l. 4 | Inexact : le RAG utilise sentence-transformers (`all-MiniLM-L6-v2`) ; FastEmbed n'est utilisé que par le cache sémantique |
| « 32 tests automatisés (100 % pass) » | PORTFOLIO_MODULE_C_PRODUCTION_LLMOPS.md l. 124 | Périmé : 25 tests au départ, 63 maintenant |
| Liens de fichiers `file:///Users/oscarbrunet/Projects/Football_Agent_LangGraph_RAG/...` | PORTFOLIO_CASE_STUDY.md l. 142, 144 | Chemin d'un ancien emplacement du projet, qui n'existe plus |
| « Chunking avec overlap » (chunker.py) | PORTFOLIO_CASE_STUDY.md l. 330 | À préciser : overlap de 40 tokens en phrases entières, taille cible 220 tokens (au lieu de 500 ou 600 mots) |

## 7. Limites restantes

1. **Ce rapport mesure le retrieval, pas la qualité des réponses.** Aucune évaluation de bout en bout avec un vrai LLM n'a été faite (tests avec `MockChatModel`, sans clé API). Une évaluation sur un golden set annoté (pertinence des chunks jugée par un humain, fidélité et citations des rapports) reste à faire ; sans elle, on ne sait pas si les 4 chunks gardés sont les bons, seulement qu'ils sont au-dessus du seuil.
2. **Le jeu de 15 requêtes est petit et optimiste.** Les 12 requêtes en corpus reprennent les titres des documents indexés ; elles sont plus faciles que de vraies questions de coach. Les 3 hors sujet sont extrêmes. La séparation observée (de -6,9 à +3,2) ne dit rien sur les cas intermédiaires.
3. **Vérification des citations de niveau document.** La regex reconnaît `[Auteur, Année - Titre]`, format désormais produit pour tous les documents du corpus. Elle prouve que la citation existe parmi les chunks fournis, pas que le chunk cité soutient l'affirmation : cela reste jugé par le LLM, qui lit maintenant les chunks complets. Un nouveau document sans année dans ses métadonnées produirait une citation non vérifiée (un test du corpus Markdown le détecte).
4. **`is_anchored` dépend du juge LLM** ; aucun contrôle déterministe de la Golden Anchoring Rule.
5. **Langue et forme de la requête.** Le cross-encoder est anglais seulement (périmètre : anglais uniquement, voir README). La requête enrichie réelle contient des clés de deltas qui font baisser les scores ; le seuil de 0,0, calibré sur des requêtes propres, rejette alors des questions pertinentes (voir section 1). Une recalibration sur des requêtes construites comme le pipeline les construit est nécessaire.
6. **Modèles inchangés.** Embedding `all-MiniLM-L6-v2` et cross-encoder `ms-marco-MiniLM-L-6-v2` n'ont pas été comparés à d'autres ; seuls leurs entrées ont été corrigées. `top_k` (15/15), RRF k=60 et top 4 gardent la justification reconstruite, pas mesurée.
7. **Dérives du corpus non traitées** : guides désynchronisés du script de génération (section 5), année absente ou 2020 par défaut pour les Markdown sans année explicite, auteur des articles codé en dur.
8. **Reproductibilité.** `data/` (index, PDFs) est ignoré par git : la ré-indexation (`python index_knowledge_base.py`) doit être refaite sur chaque machine, et les 977 chunks en dépendent.
9. **Fallback sans cross-encoder** : le seuil est désactivé, donc le comportement « toujours 4 chunks » revient dans ce cas (signalé en télémétrie, pas dans le rapport).
