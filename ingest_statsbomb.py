"""
Script d'ingestion de données StatsBomb pour l'assistant tactique de football.

Ce script :
1. Récupère les matchs de la Coupe du Monde 2022 (competition_id=43, season_id=106).
2. Extrait l'intégralité des événements des 3 premiers matchs (dont la finale Argentine vs France).
3. Nettoie et structure les données dans une base SQLite locale (`data/statsbomb_foot.db`).
4. Crée les tables `matches`, `players` et `events` (avec extraction x, y et raw_data JSON).
5. Crée les index SQL pour accélérer les requêtes de l'agent.
6. Effectue une vérification d'intégrité finale.
"""

import json
import os
import sqlite3
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Désactiver les avertissements d'authentification ouverte StatsBomb
warnings.filterwarnings("ignore", message="credentials were not supplied")
from statsbombpy import sb

# --- Configuration & Constantes ---
DB_DIR = Path("data")
DB_PATH = DB_DIR / "statsbomb_foot.db"
COMPETITION_ID = 43  # World Cup
SEASON_ID = 106     # 2022
TARGET_MATCH_COUNT = 3
FINAL_MATCH_ID = 3869685  # Argentina vs France Final


def serialize_raw_event(row_dict: Dict[str, Any]) -> str:
    """
    Nettoie et sérialise un événement brut en chaîne JSON valide,
    en filtrant les valeurs NaN / None et en convertissant les types numpy.
    """
    cleaned = {}
    for key, value in row_dict.items():
        # Ignorer les valeurs nulles/NaN
        if isinstance(value, (list, dict, np.ndarray)):
            pass
        elif pd.isna(value):
            continue

        # Conversion des types numpy et standard
        if isinstance(value, (np.integer, np.int64, np.int32)):
            cleaned[key] = int(value)
        elif isinstance(value, (np.floating, np.float64, np.float32)):
            cleaned[key] = float(value)
        elif isinstance(value, np.ndarray):
            cleaned[key] = value.tolist()
        elif isinstance(value, pd.Timestamp):
            cleaned[key] = value.isoformat()
        else:
            cleaned[key] = value

    return json.dumps(cleaned, ensure_ascii=False)


def fetch_matches(competition_id: int = COMPETITION_ID, season_id: int = SEASON_ID) -> pd.DataFrame:
    """
    Récupère la liste de tous les matchs pour une compétition et une saison données.
    """
    print(f"[INGESTING] Récupération des matchs (competition_id={competition_id}, season_id={season_id})...")
    raw_matches = sb.matches(competition_id=competition_id, season_id=season_id)

    # Sélection et renommage des colonnes selon la spec
    required_cols = ["match_id", "match_date", "home_team", "away_team", "home_score", "away_score"]
    matches_df = raw_matches[required_cols].copy()

    # Typage explicite
    matches_df["match_id"] = matches_df["match_id"].astype(int)
    matches_df["home_score"] = matches_df["home_score"].astype(int)
    matches_df["away_score"] = matches_df["away_score"].astype(int)
    matches_df["match_date"] = matches_df["match_date"].astype(str)

    print(f"[SUCCESS] {len(matches_df)} matchs récupérés.")
    return matches_df


def select_target_matches(matches_df: pd.DataFrame, count: int = TARGET_MATCH_COUNT, priority_id: int = FINAL_MATCH_ID) -> pd.DataFrame:
    """
    Sélectionne les matchs cibles pour l'extraction détaillée des événements.
    Trie par date décroissante pour inclure la finale et les phases finales clés.
    Garantit la présence de la finale Argentina vs France.
    """
    sorted_matches = matches_df.sort_values(by=["match_date", "match_id"], ascending=[False, False]).reset_index(drop=True)

    # Vérification que le match prioritaire est dans les premiers
    top_matches = sorted_matches.head(count).copy()
    if priority_id not in top_matches["match_id"].values:
        priority_row = sorted_matches[sorted_matches["match_id"] == priority_id]
        if not priority_row.empty:
            top_matches = pd.concat([priority_row, top_matches.iloc[:count-1]], ignore_index=True)

    print(f"[INFO] {len(top_matches)} matchs sélectionnés pour l'ingestion des événements :")
    for _, row in top_matches.iterrows():
        print(f"       - Match {row['match_id']}: {row['home_team']} vs {row['away_team']} ({row['match_date']})")

    return top_matches


def fetch_events_for_matches(match_ids: List[int]) -> pd.DataFrame:
    """
    Extrait l'intégralité des événements pour une liste d'identifiants de matchs.
    """
    all_events: List[pd.DataFrame] = []

    # Utilise sb.events ou sb.match_events s'il est présent
    events_fetcher = getattr(sb, "match_events", sb.events)

    for m_id in match_ids:
        print(f"[INGESTING] Extraction des événements pour le match {m_id}...")
        events = events_fetcher(match_id=m_id)
        print(f"[SUCCESS] Match {m_id} : {len(events)} événements extraits.")
        all_events.append(events)

    combined_df = pd.concat(all_events, ignore_index=True)
    print(f"[SUCCESS] Total d'événements bruts extraits : {len(combined_df)}")
    return combined_df


def process_events(raw_events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie et transforme les événements bruts au schéma cible SQLite:
    event_id, match_id, index, period, minute, second, type, team, player, x, y, pass_recipient, raw_data.
    """
    print("[INGESTING] Transformation et nettoyage des événements...")
    events_df = pd.DataFrame()

    # 1. event_id (renommé depuis 'id')
    events_df["event_id"] = raw_events_df["id"].astype(str)
    events_df["match_id"] = raw_events_df["match_id"].astype(int)
    events_df["index"] = raw_events_df["index"].astype(int)
    events_df["period"] = raw_events_df["period"].astype(int)
    events_df["minute"] = raw_events_df["minute"].astype(int)
    events_df["second"] = raw_events_df["second"].astype(int)
    events_df["type"] = raw_events_df["type"].astype(str)
    events_df["team"] = raw_events_df["team"].astype(str)

    # 2. player (gérer les NaN pour les événements d'équipe comme Starting XI)
    events_df["player"] = raw_events_df["player"].fillna("").astype(str)

    # 3. Position x, y depuis 'location'
    if "location" in raw_events_df.columns:
        events_df["x"] = raw_events_df["location"].apply(
            lambda loc: float(loc[0]) if isinstance(loc, (list, tuple)) and len(loc) >= 1 else None
        )
        events_df["y"] = raw_events_df["location"].apply(
            lambda loc: float(loc[1]) if isinstance(loc, (list, tuple)) and len(loc) >= 2 else None
        )
    else:
        events_df["x"] = None
        events_df["y"] = None

    # 4. pass_recipient
    if "pass_recipient" in raw_events_df.columns:
        events_df["pass_recipient"] = raw_events_df["pass_recipient"].fillna("").astype(str)
    else:
        events_df["pass_recipient"] = ""

    # 5. raw_data : événement brut nettoyé en JSON
    print("[INGESTING] Sérialisation JSON des propriétés brutes (raw_data)...")
    events_df["raw_data"] = [serialize_raw_event(row) for row in raw_events_df.to_dict(orient="records")]

    print(f"[SUCCESS] {len(events_df)} événements préparés.")
    return events_df


def extract_players(raw_events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrait la liste unique des joueurs à partir des événements bruts.
    Colonnes : player_id (PRIMARY KEY), player_name, team_name.
    """
    print("[INGESTING] Extraction de la liste unique des joueurs...")
    filtered = raw_events_df.dropna(subset=["player_id", "player"]).copy()

    players_df = filtered[["player_id", "player", "team"]].copy()
    players_df["player_id"] = players_df["player_id"].astype(int)
    players_df = players_df.rename(columns={"player": "player_name", "team": "team_name"})

    # Déduplication par player_id
    players_df = players_df.drop_duplicates(subset=["player_id"]).sort_values(by="player_name").reset_index(drop=True)

    print(f"[SUCCESS] {len(players_df)} joueurs uniques extraits.")
    return players_df


def save_to_sqlite(
    matches_df: pd.DataFrame,
    players_df: pd.DataFrame,
    events_df: pd.DataFrame,
    db_path: Path = DB_PATH,
) -> None:
    """
    Insère les DataFrames dans SQLite et crée les index requis.
    """
    # Création du dossier cible si nécessaire
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INGESTING] Connexion à la base SQLite : {db_path}...")
    conn = sqlite3.connect(db_path)

    try:
        # Insertion des tables via to_sql
        print("[INGESTING] Écriture de la table 'matches'...")
        matches_df.to_sql("matches", conn, if_exists="replace", index=False)

        print("[INGESTING] Écriture de la table 'players'...")
        players_df.to_sql("players", conn, if_exists="replace", index=False)

        print("[INGESTING] Écriture de la table 'events'...")
        events_df.to_sql("events", conn, if_exists="replace", index=False)

        # Création des index SQL sur la table events et tables associées
        print("[INGESTING] Création des index SQL pour optimiser les requêtes...")
        cursor = conn.cursor()

        # Index obligatoires sur events
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_match_id ON events(match_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_minute ON events(minute);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_player ON events(player);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);")

        # Index d'intégrité / primaires
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_id ON matches(match_id);")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_players_id ON players(player_id);")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_id ON events(event_id);")

        conn.commit()
        print("[SUCCESS] Données et index SQL insérés avec succès.")
    finally:
        conn.close()


def verify_database(db_path: Path = DB_PATH) -> None:
    """
    Effectue un test de vérification de la base SQLite et affiche les métriques.
    """
    print("\n" + "=" * 50)
    print("[VERIFY] Test de vérification de la base de données :")
    print("=" * 50)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Compte des matchs
        cursor.execute("SELECT COUNT(*) FROM matches;")
        matches_count = cursor.fetchone()[0]

        # Compte des joueurs
        cursor.execute("SELECT COUNT(*) FROM players;")
        players_count = cursor.fetchone()[0]

        # Compte des événements
        cursor.execute("SELECT COUNT(*) FROM events;")
        events_count = cursor.fetchone()[0]

        print(f"  * Matches stockés : {matches_count}")
        print(f"  * Joueurs uniques : {players_count}")
        print(f"  * Événements stockés : {events_count}")

        # Vérification d'un événement avec raw_data JSON valide
        cursor.execute("SELECT event_id, match_id, minute, type, player, x, y, raw_data FROM events LIMIT 1;")
        sample_event = cursor.fetchone()
        if sample_event:
            raw_sample = json.loads(sample_event[7])
            print("\n[VERIFY] Exemple d'événement vérifié :")
            print(f"  - Event ID : {sample_event[0]}")
            print(f"  - Match ID : {sample_event[1]}")
            print(f"  - Minute   : {sample_event[2]}")
            print(f"  - Type     : {sample_event[3]}")
            print(f"  - Joueur   : {sample_event[4] or 'N/A'}")
            print(f"  - (x, y)   : ({sample_event[5]}, {sample_event[6]})")
            print(f"  - Propriétés raw_data : {len(raw_sample)} clés JSON décodées avec succès.")

        # Liste des index créés
        cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type = 'index';")
        indexes = cursor.fetchall()
        print("\n[VERIFY] Index SQLite créés :")
        for idx_name, tbl_name in indexes:
            print(f"  - {idx_name} (table: {tbl_name})")

        print("=" * 50)
        print(f"[SUCCESS] Ingestion terminée et validée ! Base SQLite prête : {db_path.resolve()}")
        print("=" * 50)
    finally:
        conn.close()


def main() -> None:
    """Point d'entrée principal du pipeline d'ingestion."""
    print("=== Démarrage du pipeline d'ingestion StatsBomb ===")
    
    # 1. Récupération des matchs
    matches_df = fetch_matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)

    # 2. Sélection des 3 matchs clés (dont la finale Argentina vs France)
    target_matches = select_target_matches(matches_df, count=TARGET_MATCH_COUNT, priority_id=FINAL_MATCH_ID)

    # 3. Extraction des événements
    raw_events_df = fetch_events_for_matches(target_matches["match_id"].tolist())

    # 4. Traitement des événements et extraction des joueurs
    events_df = process_events(raw_events_df)
    players_df = extract_players(raw_events_df)

    # 5. Sauvegarde en SQLite & création des index
    save_to_sqlite(matches_df, players_df, events_df, db_path=DB_PATH)

    # 6. Vérification finale
    verify_database(db_path=DB_PATH)


if __name__ == "__main__":
    main()
