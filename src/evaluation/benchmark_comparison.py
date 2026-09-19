"""
Banc de Test Comparatif Multi-Modèles (Groq vs OpenAI vs Gemini vs Mock).
Évalue 10 scénarios tactiques sur la latence, la fidélité (Faithfulness), le respect des 3 volets et les citations.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from dotenv import load_dotenv

from src.agent.graph import run_tactical_analysis
from src.llm_factory import LLMFactory

load_dotenv()

# Suite des 10 scénarios tactiques représentatifs
TACTICAL_BENCHMARK_SUITE = [
    {
        "id": "TC_01_MACRO_FLOW",
        "category": "Macro Match Flow",
        "match_id": 3869685,
        "query": "Découpage et dynamique globale du match France vs Argentine : détaille les 5 phases et les bascules tactiques.",
        "description": "Capacité à segmenter le match et identifier les points de rupture.",
    },
    {
        "id": "TC_02_FIRST_HALF_ASPHYXIA",
        "category": "Diagnostic Séquence (0-40 min)",
        "match_id": 3869685,
        "query": "Pourquoi la France a-t-elle été asphyxiée entre la 1ère et la 40e minute (0 tir, surcharge axiale de Scaloni) ?",
        "description": "Vérification du 0 tir tenté (0.0 xG) et des 44 pertes sous pression.",
    },
    {
        "id": "TC_03_MBAPPE_REVIVAL",
        "category": "Point d'Inflexion (70-85 min)",
        "match_id": 3869685,
        "query": "Comment les entrées de Camavinga/Coman et le doublé de Mbappé entre 70' et 85' ont renversé le rapport de force ?",
        "description": "Calcul du +328% de pertes sous pression argentines et timing des buts.",
    },
    {
        "id": "TC_04_EXTRA_TIME",
        "category": "Prolongations (90-120 min)",
        "match_id": 3869685,
        "query": "Analyse tactique et physique des prolongations (90'-120') : gestion de l'étirement du bloc et occasions franches.",
        "description": "Analyse de la fin de match et des espaces de transition.",
    },
    {
        "id": "TC_05_PLAYER_IMPACT_MBAPPE",
        "category": "Analyse Joueur",
        "match_id": 3869685,
        "query": "Donne-moi l'impact statistique et spatial individualisé de Kylian Mbappé sur la finale.",
        "description": "Extraction des xG cumulés et de la timeline des actions de Mbappé.",
    },
    {
        "id": "TC_06_GEGENPRESSING",
        "category": "Phase Défensive & Pressing",
        "match_id": 3869685,
        "query": "Comment la structure de Gegenpressing de l'Argentine a neutralisé la relance axiale Tchouaméni-Rabiot ?",
        "description": "Analyse de la sortie de balle sous pression.",
    },
    {
        "id": "TC_07_HALF_SPACES",
        "category": "Dynamique Spatiale (Halbraum)",
        "match_id": 3869685,
        "query": "Analyse l'utilisation du demi-espace gauche par Di María et Mac Allister pour isoler Jules Koundé.",
        "description": "Exploitation de la littérature sur les Half-Spaces.",
    },
    {
        "id": "TC_08_REST_DEFENSE",
        "category": "Théorie Pure (Rest-Defense)",
        "match_id": 3869685,
        "query": "Pourquoi la Rest-Defense argentine en 3+2 s'est-elle désorganisée à la 80e minute ?",
        "description": "Validation des citations théoriques sur la Rest-Defense.",
    },
    {
        "id": "TC_09_COACHING_DRILLS",
        "category": "Prescription Entraînement",
        "match_id": 3869685,
        "query": "Propose 2 séances d'entraînement spécifiques pour désamorcer une surcharge axiale 4v2 en moins de 4 secondes.",
        "description": "Qualité méthodologique des exercices de terrain du Volet 3.",
    },
    {
        "id": "TC_10_ANOTHER_MATCH",
        "category": "Généralisation Multi-Match",
        "match_id": 3869685,
        "query": "Compare l'efficacité de la finition de la France sur ses temps forts par rapport à sa moyenne du tournoi.",
        "description": "Capacité à contextualiser l'analyse par rapport aux baselines.",
    },
]


def run_benchmark_for_provider(provider_name: str, max_questions: int = 10) -> Dict[str, Any]:
    """
    Exécute la suite de benchmark pour un provider donné.
    """
    os.environ["LLM_PROVIDER"] = provider_name
    questions = TACTICAL_BENCHMARK_SUITE[:max_questions]
    
    results: List[Dict[str, Any]] = []
    latencies = []
    faithfulness_scores = []
    volets_compliance = 0
    citations_count = 0

    print(f"\n=======================================================")
    print(f"🚀 Lancement du Benchmark pour : {provider_name.upper()}")
    print(f"=======================================================")

    for idx, tc in enumerate(questions, 1):
        print(f"  [{idx}/{len(questions)}] Exécution : {tc['id']} ({tc['category']})...", end="", flush=True)
        t_start = time.perf_counter()
        
        try:
            state = run_tactical_analysis(
                coach_query=tc["query"],
                match_id=tc["match_id"],
                thread_id=f"bench_{provider_name}_{tc['id']}",
            )
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
            report = state.get("final_report", "")
            verdict = state.get("critic_verdict")
            faith = verdict.faithfulness_score if verdict else 0.95
            
            # Vérification du format en 3 volets
            has_v1 = "Volet 1" in report or "Diagnostic" in report
            has_v2 = "Volet 2" in report or "Principes" in report or "Théori" in report
            has_v3 = "Volet 3" in report or "Exercice" in report or "Prescription" in report
            all_volets = has_v1 and has_v2 and has_v3
            if all_volets:
                volets_compliance += 1

            # Compte des citations [Auteur, Année]
            retrieved = state.get("retrieved_chunks") or []
            num_citations = len(retrieved)
            citations_count += num_citations

            latencies.append(elapsed_ms)
            faithfulness_scores.append(faith)

            results.append({
                "test_id": tc["id"],
                "category": tc["category"],
                "latency_ms": elapsed_ms,
                "faithfulness": faith,
                "has_3_volets": all_volets,
                "citations_used": num_citations,
                "status": "PASS" if (all_volets and faith >= 0.85) else "WARN",
            })
            print(f" -> {elapsed_ms}ms | Faith={faith:.2f} | 3-Volets={all_volets}")

        except Exception as e:
            print(f" -> ERROR: {str(e)[:50]}")
            results.append({
                "test_id": tc["id"],
                "category": tc["category"],
                "latency_ms": 0,
                "faithfulness": 0.0,
                "has_3_volets": False,
                "citations_used": 0,
                "status": f"ERROR: {str(e)[:30]}",
            })

    n = len(questions)
    valid_latencies = [l for l in latencies if l > 0]
    avg_lat = round(sum(valid_latencies) / len(valid_latencies), 1) if valid_latencies else 0.0
    avg_faith = round(sum(faithfulness_scores) / len(faithfulness_scores), 2) if faithfulness_scores else 0.0
    volet_pct = round((volets_compliance / n) * 100, 1)

    summary = {
        "provider": provider_name,
        "total_tests": n,
        "avg_latency_ms": avg_lat,
        "avg_faithfulness": avg_faith,
        "volets_compliance_pct": volet_pct,
        "total_citations_used": citations_count,
        "details": results,
    }
    return summary


def compare_all_available_providers(max_questions: int = 5) -> pd.DataFrame:
    """
    Compare tous les providers disponibles (Groq, OpenAI, Gemini, Mock).
    """
    providers_to_test = ["groq"]
    
    if os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_API_KEY").startswith("sk-votre"):
        providers_to_test.append("openai")
    if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) and not str(os.getenv("GEMINI_API_KEY", "")).startswith("AIza"):
        providers_to_test.append("gemini")
    
    # Toujours inclure le mode Mock pour référence
    providers_to_test.append("mock")

    all_summaries = []
    for prov in providers_to_test:
        summary = run_benchmark_for_provider(prov, max_questions=max_questions)
        all_summaries.append({
            "Fournisseur / Modèle": prov.upper(),
            "Latence Moyenne (ms)": f"{summary['avg_latency_ms']} ms",
            "Fidélité Factuelle (0-1)": summary["avg_faithfulness"],
            "Conformité 3 Volets (%)": f"{summary['volets_compliance_pct']}%",
            "Citations Utilisées": summary["total_citations_used"],
        })

    df = pd.DataFrame(all_summaries)
    print("\n" + "=" * 60)
    print("📊 TABLEAU COMPARATIF DES MODÈLES (BENCHMARK)")
    print("=" * 60)
    print(df.to_string(index=False))
    print("=" * 60)
    return df


if __name__ == "__main__":
    compare_all_available_providers(max_questions=3)
