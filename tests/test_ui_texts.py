"""
Les textes de l'interface qui citent un nombre doivent venir des donnees, pas de constantes perimees.
"""

from pathlib import Path

from src.app_service import chunk_rows, corpus_explorer_title, matches_available_label
from src.rag.vector_store import VectorStoreManager

ROOT = Path(__file__).resolve().parent.parent


def test_matches_label_uses_the_given_count():
    assert matches_available_label(4) == "4 MATCHES AVAILABLE"
    assert matches_available_label(1) == "1 MATCH AVAILABLE"


def test_corpus_title_uses_the_given_count():
    assert corpus_explorer_title(977) == "RAG CORPUS EXPLORER (977 CHUNKS)"
    assert corpus_explorer_title(None) == "RAG CORPUS EXPLORER"


def test_all_matches_are_shown_in_rows_of_three():
    rows = chunk_rows(["a", "b", "c", "d"], 3)
    assert rows == [["a", "b", "c"], ["d"]]       # le 4e match n'est plus tronque
    assert sum(len(r) for r in rows) == 4


def test_no_stale_counts_left_in_ui_sources():
    for name in ("app.py", "src/ui/components/admin_dashboard.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "3 MATCHES AVAILABLE" not in text, name
        assert "305" not in text, name
    assert "matches_available_label(len(match_options))" in (ROOT / "app.py").read_text(encoding="utf-8")


def test_labels_match_the_real_data():
    from src.data_mining.db_connection import ReadOnlyDBConnection

    rows = ReadOnlyDBConnection().execute_safe_query(
        "SELECT COUNT(DISTINCT match_id) AS n FROM events"
    )
    n_matches = dict(rows[0])["n"]
    assert matches_available_label(n_matches) == f"{n_matches} MATCHES AVAILABLE"
    n_chunks = VectorStoreManager().count()
    assert corpus_explorer_title(n_chunks) == f"RAG CORPUS EXPLORER ({n_chunks} CHUNKS)"
