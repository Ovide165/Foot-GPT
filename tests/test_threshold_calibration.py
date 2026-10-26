"""
Verrouille la calibration de RERANK_MIN_SCORE sur les snapshots versionnes (aucun modele charge) :
si le seuil ou les requetes de reference changent, le classement attendu doit rester vrai.
"""

import json
from pathlib import Path

from src.config import RERANK_MIN_SCORE

EVAL = Path(__file__).resolve().parent.parent / "eval"
# Hors sujet auquel le routeur a donne des topics de football par defaut : non separable (voir rapport)
KNOWN_NON_SEPARABLE = {"x04"}


def _top1(path: str):
    data = json.loads((EVAL / path).read_text(encoding="utf-8"))
    return [(q["id"], q["type"], q["reranked_top4"][0]["score"]) for q in data["queries"]]


def test_pipeline_shaped_in_corpus_queries_keep_sources():
    in_corpus = [(i, s) for i, t, s in _top1("results_pipeline.json") if t == "in_corpus"]
    assert len(in_corpus) == 12
    assert [i for i, s in in_corpus if s < RERANK_MIN_SCORE] == []


def test_pipeline_shaped_uncovered_queries_are_flagged():
    uncovered = [(i, s) for i, t, s in _top1("results_pipeline.json") if t != "in_corpus" and i not in KNOWN_NON_SEPARABLE]
    assert len(uncovered) == 5
    assert [i for i, s in uncovered if s >= RERANK_MIN_SCORE] == []


def test_clean_baseline_queries_remain_correctly_classified():
    for qid, qtype, score in _top1("results_after.json"):
        assert (score >= RERANK_MIN_SCORE) == (qtype == "in_corpus"), qid


def test_threshold_sits_inside_the_observed_gap():
    scores = _top1("results_pipeline.json")
    lowest_covered = min(s for _, t, s in scores if t == "in_corpus")
    highest_uncovered = max(s for i, t, s in scores if t != "in_corpus" and i not in KNOWN_NON_SEPARABLE)
    assert highest_uncovered < RERANK_MIN_SCORE <= lowest_covered
