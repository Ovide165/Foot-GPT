"""
Snapshot du retrieval hybride pour un jeu de requetes de reference.

Pour chaque requete : top 15 BM25, top 15 dense, ordre RRF, scores du reranker sur
tous les candidats fusionnes (top 4 marques), ainsi que les statistiques de chunks
(tokens vus par l'embedding). Les resultats servent a calibrer RERANK_MIN_SCORE.

Usage : python eval/snapshot_retrieval.py eval/results_before.json
        python eval/snapshot_retrieval.py eval/results_pipeline.json --pipeline-queries

Avec --pipeline-queries, les requetes de eval/pipeline_queries.json sont construites comme le fait
le noeud RAG (question + topics + zones + 2 premieres cles de deltas) via build_enriched_query.
"""

import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.rag import chunker
from src.rag.bm25_retriever import BM25Retriever
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.reranker import CrossEncoderReranker
from src.rag.vector_store import VectorStoreManager

QUERIES_PATH = Path(__file__).resolve().parent / "baseline_queries.json"
PIPELINE_QUERIES_PATH = Path(__file__).resolve().parent / "pipeline_queries.json"
EMBEDDING_MAX_TOKENS = 256


def embedded_text(chunk) -> str:
    """Texte reellement envoye a l'embedding (contenu seul avant correction, titre inclus apres)."""
    fn = getattr(chunker, "chunk_embedding_text", None)
    return fn(chunk) if fn else chunk.content


def chunk_stats(chunks: List[Any], tokenizer) -> Dict[str, Any]:
    counts = [len(tokenizer(embedded_text(c), add_special_tokens=False)["input_ids"]) for c in chunks]
    limit = EMBEDDING_MAX_TOKENS - 2  # [CLS] et [SEP]
    return {
        "n_chunks": len(counts),
        "median_tokens": statistics.median(counts),
        "p90_tokens": sorted(counts)[int(0.9 * len(counts))],
        "max_tokens": max(counts),
        "pct_truncated_by_embedding": round(100 * sum(c > limit for c in counts) / len(counts), 1),
        "mean_share_of_text_seen_pct": round(100 * statistics.mean(min(1.0, limit / c) for c in counts), 1),
    }


def brief(chunk, score=None) -> Dict[str, Any]:
    d = {"chunk_id": chunk.chunk_id, "citation": chunk.format_citation()}
    if score is not None:
        d["score"] = round(float(score), 4)
    return d


def load_queries(pipeline_shaped: bool) -> List[Dict[str, Any]]:
    if not pipeline_shaped:
        return json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    from types import SimpleNamespace

    from src.agent.nodes.deep_rag_node import build_enriched_query

    queries = []
    for item in json.loads(PIPELINE_QUERIES_PATH.read_text(encoding="utf-8")):
        plan = SimpleNamespace(theoretical_topics=item["theoretical_topics"], spatial_zones=item["spatial_zones"])
        facts = SimpleNamespace(significant_deltas={k: "" for k in item["delta_keys"]})
        queries.append({"id": item["id"], "type": item["type"],
                        "query": build_enriched_query(item["question"], plan, facts)})
    return queries


def main(out_path: str, pipeline_shaped: bool = False) -> None:
    queries = load_queries(pipeline_shaped)
    bm25 = BM25Retriever()
    assert bm25.load(), "Index BM25 introuvable : lancer index_knowledge_base.py"
    vs = VectorStoreManager()
    reranker = CrossEncoderReranker()
    assert reranker.model is not None, "Cross-encoder indisponible : scores non representatifs"

    pipeline = HybridRetriever(bm25=bm25, vector_store=vs, reranker=reranker)
    tokenizer = vs.embedding_fn._model.tokenizer  # tokenizer MiniLM
    results: List[Dict[str, Any]] = []
    for q in queries:
        sparse = bm25.retrieve(q["query"], top_k=config.TOP_K_SPARSE)
        dense = vs.retrieve(q["query"], top_k=config.TOP_K_DENSE)

        rrf: Dict[str, float] = {}
        cmap = {}
        for results_list in (sparse, dense):
            for rank, (c, _) in enumerate(results_list, start=1):
                cmap[c.chunk_id] = c
                rrf[c.chunk_id] = rrf.get(c.chunk_id, 0.0) + 1.0 / (config.RRF_K + rank)
        order = sorted(rrf, key=lambda k: rrf[k], reverse=True)
        candidates = [cmap[k] for k in order]
        reranked = reranker.rerank(q["query"], candidates, top_n=len(candidates))

        # Pipeline reel (filtre de pertinence inclus) ; absent avant la correction : 4 chunks toujours
        detailed = getattr(pipeline, "search_detailed", None)
        outcome = detailed(q["query"]) if detailed else None
        pipeline_result = (
            {"sources_sufficient": outcome.sources_sufficient, "n_kept": len(outcome.chunks),
             "kept_ids": [c["chunk_id"] for c in outcome.chunks]}
            if outcome else {"sources_sufficient": None, "n_kept": min(4, len(reranked)),
                             "kept_ids": [c.chunk_id for c, _ in reranked[:4]]}
        )

        results.append({
            "pipeline": pipeline_result,
            "id": q["id"], "type": q["type"], "query": q["query"],
            "bm25_top": [brief(c, s) for c, s in sparse],
            "dense_top": [brief(c, s) for c, s in dense],
            "rrf_order": [dict(brief(cmap[k], rrf[k])) for k in order],
            "reranked_all": [brief(c, s) for c, s in reranked],
            "reranked_top4": [brief(c, s) for c, s in reranked[: config.TOP_K_RERANKED]],
        })
        print(f"{q['id']} ({q['type']}): top1 rerank = {reranked[0][1]:.3f}")

    all_chunks = bm25.chunks
    payload = {"chunk_stats": chunk_stats(all_chunks, tokenizer), "queries": results}
    Path(out_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["chunk_stats"], indent=2))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "eval/results_after.json", "--pipeline-queries" in sys.argv)
