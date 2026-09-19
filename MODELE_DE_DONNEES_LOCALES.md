# 📊 Documentation du Modèle de Données Local (`statsbomb_foot.db`)

## 1. Vue d'Ensemble de l'Architecture
Le stockage local de l'application **foot-GPT** repose sur une base de données relationnelle **SQLite** ultra-optimisée (`data/statsbomb_foot.db`). 

Le modèle est conçu selon une approche **hybride Relationnelle / Semi-Structurée (JSON)** :
- **Attributs Relationnels (Colonnes standard) :** Permettent des filtrages ultra-rapides (< 10 ms) sur les jointures de matchs, les fenêtres temporelles, les types d'événements et les coordonnées spatiales $(x, y)$.
- **Stockage Documentaire (`raw_data` JSON) :** Conserve l'intégralité des métadonnées brutes StatsBomb pour chaque événement (détails des tirs, angles, pressions, freeze frames, passes, etc.) interrogeables via les fonctions JSON de SQLite.

---

## 2. Diagramme Entité-Association (ERD)

```mermaid
erdiagram
    MATCHES ||--o{ EVENTS : "contient (1:N)"
    PLAYERS ||--o{ EVENTS : "exécute (1:N)"
    
    MATCHES {
        int match_id PK
        string match_date
        string home_team
        string away_team
        int home_score
        int away_score
    }

    PLAYERS {
        int player_id PK
        string player_name
        string team_name
    }

    EVENTS {
        string event_id PK
        int match_id FK
        int index
        int period
        int minute
        int second
        string type
        string team
        string player
        real x
        real y
        string pass_recipient
        json raw_data
    }
```

---

## 3. Spécification Détaillée des Tables

### 3.1. Table `matches`
Stocke les métadonnées de haut niveau de chaque rencontre couverte (ex: Coupe du Monde 2022).

| Colonne | Type SQL | Clé / Contraintes | Description |
| :--- | :--- | :--- | :--- |
| `match_id` | `INTEGER` | **PK**, `UNIQUE` | Identifiant unique StatsBomb de la rencontre (ex: `3869685` pour la Finale 2022). |
| `match_date` | `TEXT` | `NOT NULL` | Date de la rencontre au format ISO (`YYYY-MM-DD`). |
| `home_team` | `TEXT` | `NOT NULL` | Nom de l'équipe à domicile (ex: `"Argentina"`). |
| `away_team` | `TEXT` | `NOT NULL` | Nom de l'équipe à l'extérieur (ex: `"France"`). |
| `home_score` | `INTEGER` | `NOT NULL` | Nombre de buts marqués par l'équipe à domicile (à la fin du temps réglementaire / prolongations). |
| `away_score` | `INTEGER` | `NOT NULL` | Nombre de buts marqués par l'équipe extérieure. |

---

### 3.2. Table `players`
Répertoire des joueurs uniques identifiés dans les événements des matchs ingérés.

| Colonne | Type SQL | Clé / Contraintes | Description |
| :--- | :--- | :--- | :--- |
| `player_id` | `INTEGER` | **PK**, `UNIQUE` | Identifiant unique du joueur dans la base StatsBomb. |
| `player_name` | `TEXT` | `NOT NULL` | Nom complet normé du joueur (ex: `"Kylian Mbappé Lottin"`). |
| `team_name` | `TEXT` | `NOT NULL` | Équipe principale / Sélection nationale associée. |

---

### 3.3. Table `events`
Table centrale contenant la totalité des événements spatio-temporels du match.

| Colonne | Type SQL | Clé / Contraintes | Description |
| :--- | :--- | :--- | :--- |
| `event_id` | `TEXT` | **PK**, `UNIQUE` | UUID unique attribué à l'événement. |
| `match_id` | `INTEGER` | **FK** (`matches.match_id`) | Référence du match associé. |
| `index` | `INTEGER` | `NOT NULL` | Séquence chronologique absolue de l'événement dans le match (1..N). |
| `period` | `INTEGER` | `NOT NULL` | Période du match (1: 1ère mi-temps, 2: 2ème mi-temps, 3-4: prolongations, 5: tirs au but). |
| `minute` | `INTEGER` | `NOT NULL` | Minute de l'événement (`0` à `120+`). |
| `second` | `INTEGER` | `NOT NULL` | Seconde exacte dans la minute (`0` à `59`). |
| `type` | `TEXT` | `NOT NULL` | Type de l'événement (`Pass`, `Shot`, `Dribble`, `Duel`, `Interception`, `Substitution`, etc.). |
| `team` | `TEXT` | `NOT NULL` | Équipe réalisant l'action. |
| `player` | `TEXT` | `NULLABLE` | Nom du joueur effectuant l'action (vide pour les événements collectifs comme *Starting XI*). |
| `x` | `REAL` | `NULLABLE` | Coordonnée $X$ de départ de l'action sur le terrain normé StatsBomb ($[0, 120]$ mètres). |
| `y` | `REAL` | `NULLABLE` | Coordonnée $Y$ de départ de l'action sur le terrain normé StatsBomb ($[0, 80]$ mètres). |
| `pass_recipient` | `TEXT` | `NULLABLE` | Nom du destinataire de la passe (uniquement renseigné si `type = 'Pass'`). |
| `raw_data` | `TEXT (JSON)` | `NOT NULL` | Objet JSON complet sérialisé contenant l'intégralité des attributs spécifiques de l'événement. |

---

## 4. Structure & Attributs du Document `raw_data` (JSON)

La colonne `raw_data` contient les détails avancés interrogeables en SQL via `json_extract(raw_data, '$.cle')`. 

### 🎯 Localisation exacte du xG (Expected Goals)
Dans les événements de type **`Shot`**, la valeur exacte de l'Expected Goals calculée par StatsBomb est stockée au premier niveau de l'objet `raw_data` sous la clé :
$$\mathbf{\text{json\_extract(raw\_data, '\$.shot\_statsbomb\_xg')}}$$

### Exemple d'objet JSON sérialisé (`raw_data`) pour un Tir :

```json
{
  "id": "13b63722-8099-4cdf-818a-d2df3036a633",
  "match_id": 3857276,
  "minute": 3,
  "second": 29,
  "type": "Shot",
  "team": "Morocco",
  "player": "Hakim Ziyech",
  "location": [83.9, 45.0],
  
  "shot_statsbomb_xg": 0.024477,
  "shot_outcome": "Goal",
  "shot_technique": "Lob",
  "shot_type": "Open Play",
  "shot_body_part": "Left Foot",
  "shot_end_location": [120.0, 43.3, 1.4],
  "under_pressure": true
}
```

---

## 5. Optimisation & Indexation SQL

Pour garantir des temps d'exécution sous les **10 ms** même lors des requêtes d'agrégation complexes exécutées par l'agent LangGraph (`SQL Miner Node`), les index suivants sont créés dans SQLite :

```sql
-- Index d'intégrité et clés primaires
CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_id ON matches(match_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_players_id ON players(player_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_id ON events(event_id);

-- Index de performance pour les filtres du SQL Miner Node
CREATE INDEX IF NOT EXISTS idx_events_match_id ON events(match_id);
CREATE INDEX IF NOT EXISTS idx_events_minute ON events(minute);
CREATE INDEX IF NOT EXISTS idx_events_player ON events(player);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
```

---

## 6. Exemple de Requête Métier Utilisée par l'Agent

Extraction déterministe du total d'Expected Goals ($xG$) et des tirs par tranche de minutes via SQLite :

```sql
SELECT 
    team,
    COUNT(*) AS total_tirs,
    SUM(CAST(json_extract(raw_data, '$.shot_statsbomb_xg') AS FLOAT)) AS total_xg
FROM events
WHERE match_id = 3857276
  AND type = 'Shot'
  AND minute BETWEEN 0 AND 20
GROUP BY team;
```
