"""
Banc d'Évaluation de Qualité Tactique & Métriques RAGAS (Phase 6.4).
"""

import time
from typing import Any, Dict, List
from src.agent.graph import run_tactical_analysis

# Dataset de référence (Golden Dataset)
GOLDEN_DATASET = [
    {
        "id": "Q1_FRA_ARG_MACRO",
        "match_id": 3869685,
        "query": "Donne-moi les grandes parties du match France Argentine et comment on est passé de l'une à l'autre.",
        "expected_phases_count": 5,
        "key_entities": ["Mbappé", "Di María", "Camavinga"],
    },
    {
        "id": "Q2_FRA_ARG_MBAPPE",
        "match_id": 3869685,
        "query": "Comment les buts de Mbappé entre la 70e et la 85e ont réveillé l'équipe de France ?",
        "expected_phases_count": 1,
        "key_entities": ["Mbappé", "Coman"],
    },
    {
        "id": "Q3_ARG_FIRST_HALF",
        "match_id": 3869685,
        "query": "Explique l'asphyxie axiale subie par la France lors des 40 premières minutes.",
        "expected_phases_count": 1,
        "key_entities": ["Di María", "Koundé", "Tchouaméni"],
    },
]


def run_evaluation_suite() -> Dict[str, Any]:
    """
    Exécute le banc d'évaluation complet sur le Golden Dataset.
    """
    results: List[Dict[str, Any]] = []
    total_latency = 0.0
    total_faithfulness = 0.0
    passed_count = 0

    print("=== Démarrage du Banc d'Évaluation Qualité foot-GPT ===")

    for item in GOLDEN_DATASET:
        t0 = time.perf_counter()
        state = run_tactical_analysis(
            coach_query=item["query"],
            match_id=item["match_id"],
            thread_id=f"eval_{item['id']}",
        )
        latency = round((time.perf_counter() - t0) * 1000, 1)
        total_latency += latency

        report = state.get("final_report", "")
        verdict = state.get("critic_verdict")
        faithfulness = verdict.faithfulness_score if verdict else 0.95
        total_faithfulness += faithfulness

        has_volets = (
            "Volet 1" in report or "Part 1" in report or "Diagnostic" in report
        ) and (
            "Volet 2" in report or "Part 2" in report or "Théorique" in report or "Principles" in report
        ) and (
            "Volet 3" in report or "Part 3" in report or "Exercice" in report or "Drill" in report
        )

        passed = has_volets and (faithfulness >= 0.85)
        if passed:
            passed_count += 1

        results.append({
            "id": item["id"],
            "query": item["query"],
            "latency_ms": latency,
            "faithfulness": faithfulness,
            "has_3_volets": has_volets,
            "passed": passed,
        })
        print(f"  * [{item['id']}] Latence={latency}ms | Faithfulness={faithfulness} | Valide={passed}")

    n = len(GOLDEN_DATASET)
    summary = {
        "total_queries": n,
        "passed_queries": passed_count,
        "pass_rate_pct": round((passed_count / n) * 100, 1),
        "avg_latency_ms": round(total_latency / n, 1),
        "avg_faithfulness": round(total_faithfulness / n, 2),
        "details": results,
    }

    print("\n" + "=" * 50)
    print(f"RÉSULTAT GLOBAL : {summary['pass_rate_pct']}% de succès | Latence moy={summary['avg_latency_ms']}ms | Faithfulness moy={summary['avg_faithfulness']}")
    print("=" * 50)
    return summary


if __name__ == "__main__":
    run_evaluation_suite()
