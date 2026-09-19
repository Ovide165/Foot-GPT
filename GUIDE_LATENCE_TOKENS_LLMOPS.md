# Guide d'Ingénierie LLMOps : Arbitrage Latence, Tokens & Roadmap v2

> **Sujet :** Gestion de la latence, optimisation des tokens, observabilité et roadmap de production.

---

## 1. Arbitrage d'Architecture : Précision vs Latence (*Engineering Trade-off*)

Une exécution complète du graphe prend de 3.5s à 8.0s et consomme de 3 500 à 6 500 tokens. Ce coût est un **choix d'architecture assumé** : dans le football professionnel, une hallucination statistique est rédhibitoire pour un staff technique. foot-GPT privilégie donc la précision factuelle (score Faithfulness 0.95 - 1.00 via un audit Critic LLM-as-a-Judge) plutôt que la rapidité brute d'un appel unique.

### ROI Métier :
- **Sans foot-GPT :** 15 à 25 heures par semaine d'extraction SQL/Python manuelle et de rédaction.
- **Avec foot-GPT :** 4 à 5 secondes de traitement automatisé certifié à 100% sans hallucination.

---

## 2. Observabilité & Mesure Granulaire (*Show, Don't Tell*)

Plutôt que de traiter le système comme une boîte noire, `foot-GPT` intègre un système d'observabilité granulaire qui mesure le coût et la latence de chaque nœud du graphe.

### 2.1 Tracing par Reducer d'État (`merge_telemetry`)
L'état LangGraph (`TacticalAgentState`) accumule les métriques d'exécution sans écrasement de contexte :

```python
# Exemple de télémétrie capturée sur un run complet :
{
    "router_latency_ms": 240.5,      # Parsing Pydantic & Intent Classification
    "sql_miner_latency_ms": 42.1,     # Calcul déterministe SQLite (Zone 14, xG, Deltas)
    "deep_rag_latency_ms": 110.8,    # Double retrieval (BM25 + ChromaDB + RRF + Cross-Encoder)
    "synthesizer_latency_ms": 2450.0, # Génération du rapport en 3 volets UEFA Pro
    "critic_latency_ms": 1120.3,     # Audit réflexif LLM-as-a-Judge (VerificationVerdict)
    "total_execution_ms": 3963.7,    # Latence globale hors cache
    "tokens_consumed_est": 4850      # Estimation des tokens échangés
}
```

### 2.2 Observabilité UI (Dashboard Administration)
Le panneau d'administration (`src/ui/components/admin_dashboard.py`) permet à l'ingénieur de surveiller :
- La distribution de latence par nœud.
- Le ratio de *Cache Hit / Cache Miss*.
- Les requêtes SQL exécutées en temps réel.

---

## 3. La Réponse Technique Immédiate : Caching Multi-Niveaux

Pour neutraliser le coût et la latence sur les requêtes récurrentes, l'architecture déploie 3 niveaux de cache :

1. **Cache Sémantique Vectoriel (`src/cache/semantic_cache.py`) :**
   - Embeddings locaux `FastEmbed` (`BAAI/bge-small-en-v1.5`) avec Cosine Similarity $\ge 0.93$.
   - Clé composite `(query_embedding, match_id, user_time_range)` évitant la contamination entre tranches temporelles.
   - **Performance :** Temps de réponse **$< 10\text{ ms}$** et **0 token consommé**.
2. **Cache de Segmentation Tactique (`MatchPhaseGenerator`) :**
   - Sauvegarde JSON (`data/cached_phases.json`) des découpages en 4-5 phases générés par le LLM.
   - **Performance :** Chargement de la structure du match en **$< 1\text{ ms}$**.
3. **Cache Applicatif UI (`@st.cache_data`) :**
   - Mise en cache mémoire Streamlit des fixtures et métadonnées SQLite.

---

## 4. Vision Production : La Roadmap d'Optimisation v2

Pour faire évoluer foot-GPT vers une utilisation en direct au bord du terrain (SLA $< 1\text{ s}$), la roadmap d'ingénierie définit 3 leviers majeurs :

```mermaid
flowchart TD
    v1["foot-GPT v1 (Actuel)\nLatence: 3.5s - 8s | Tokens: 3.5k - 6.5k\nMulti-passes séquentiel (Groq / OpenAI)"]
    
    v1 --> OPT1["1. Parallélisation Async (LangGraph Async)\nsql_miner + deep_rag en parallèle\n(-30% Latence)"]
    v1 --> OPT2["2. Spécialisation par SLMs (Fine-Tuned 3B)\nQwen-2.5-3B sur Router & Critic\n(Tokens /5 | Latence /3)"]
    v1 --> OPT3["3. Prompt Compression & Speculative Decoding\nCompression sémantique des chunks RAG\n(-50% Fenêtre de contexte)"]
    
    OPT1 & OPT2 & OPT3 --> v2["foot-GPT v2 (Target Production)\nLatence: < 1.2s | Tokens: < 1.2k\nCertifié 100% Faithfulness"]
```

### 4.1 Axe 1 : Parallélisation Asynchrone (LangGraph Async)
- **Le levier :** Dans le graphe actuel, `sql_miner` (Nœud 2A) et `deep_rag` (Nœud 2B) s'exécutent en séquence.
- **La solution v2 :** Basculer sur `ainvoke`/`astream` dans LangGraph pour exécuter la requête SQL et le retrieval RAG en parallèle dès que le `TacticalPlan` est émis, réduisant la latence cumulée de **30%**.

### 4.2 Axe 2 : Spécialisation par Modèles Légers (Fine-Tuned SLMs 3B)
- **Le levier :** Utiliser des grands modèles généralistes (ex: 27B ou 120B) pour le Router ou le Critic est surdimensionné.
- **La solution v2 :** Fine-tuner un Small Language Model (SLM, ex: `Qwen-2.5-3B` ou `Llama-3.2-3B`) via LoRA sur le dataset de validation.
- **Bénéfice :** Réduction de la latence par 3 et division par 5 du coût token sur les étapes de cadrage et d'audit.

### 4.3 Axe 3 : Prompt Compression & Speculative Decoding
- **Le levier :** L'injection de 4 chunks théoriques complets alourdit inutilement le prompt du Synthesizer.
- **La solution v2 :** Appliquer une compression sémantique (via LLMLingua ou extraction de phrases clés) pour réduire la taille des chunks RAG de 50% avant injection.
