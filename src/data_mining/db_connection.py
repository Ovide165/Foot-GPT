"""
Gestionnaire de connexion sécurisé en lecture seule (Read-Only) pour SQLite.
"""

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.config import DB_PATH, SQL_TIMEOUT_SECONDS


class SQLSecurityError(Exception):
    """Exception levée en cas de tentative d'exécution d'une requête SQL non autorisée."""
    pass


class ReadOnlyDBConnection:
    """
    Gestionnaire de connexion SQLite durci :
    - Mode lecture seule strict via URI (?mode=ro)
    - Validation de sécurité interdisant les requêtes non-SELECT
    - Isolation des transactions
    """

    FORBIDDEN_KEYWORDS_REGEX = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|TRUNCATE)\b",
        re.IGNORECASE,
    )

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH

    @classmethod
    def validate_safe_query(cls, sql: str) -> None:
        """
        Vérifie que la requête SQL commence par SELECT ou WITH
        et ne contient aucune instruction de modification.
        """
        cleaned = sql.strip()
        if not cleaned:
            raise SQLSecurityError("Requête SQL vide.")

        first_word = cleaned.split()[0].upper()
        if first_word not in ("SELECT", "WITH", "EXPLAIN"):
            raise SQLSecurityError(
                f"Opération non autorisée '{first_word}'. Seules les requêtes SELECT/WITH sont autorisées."
            )

        if cls.FORBIDDEN_KEYWORDS_REGEX.search(cleaned):
            match = cls.FORBIDDEN_KEYWORDS_REGEX.search(cleaned)
            raise SQLSecurityError(
                f"Mot-clé interdit détecté dans la requête SQL : '{match.group(0)}'."
            )

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Ouvre une connexion SQLite en lecture seule stricte.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Base de données introuvable : {self.db_path}")

        # Connexion via URI en mode lecture seule
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=SQL_TIMEOUT_SECONDS)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            conn.close()

    def execute_safe_query(self, sql: str, params: tuple = ()) -> list:
        """
        Valide et exécute une requête SQL sécurisée, retournant une liste de lignes dict-like.
        """
        self.validate_safe_query(sql)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()
