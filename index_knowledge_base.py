"""
Script d'indexation unifié de la base de connaissances documentaire (foot-GPT).

Ce script :
1. Parse l'ensemble des sources documentaires :
   - 8 Papiers de recherche scientifiques PDF (data/research_papers/)
   - 3 Guides tactiques High-Level (data/high_level_guides/)
   - 10 Articles théoriques Spielverlagerung Markdown (data/raw_markdown/)
2. Construit et persiste l'index Sparse BM25 (data/bm25_index.pkl).
3. Construit et persiste la base vectorielle Dense ChromaDB (data/chroma_db/).
4. Exécute un test de vérification de recherche hybride avec citations.
"""

import sys
from pathlib import Path
from typing import List

from src.config import (
    BM25_INDEX_PATH,
    CHROMA_PERSIST_DIR,
    HIGH_LEVEL_DIR,
    RAW_MARKDOWN_DIR,
    RESEARCH_PAPERS_DIR,
)
from src.rag.bm25_retriever import BM25Retriever
from src.rag.chunker import TextChunk
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.parsers.markdown_parser import MarkdownParser
from src.rag.parsers.pdf_parser import PDFParser
from src.rag.reranker import CrossEncoderReranker
from src.rag.vector_store import VectorStoreManager


def ingest_all_documents() -> List[TextChunk]:
    """Parse l'ensemble des documents et extrait les TextChunks enrichis."""
    all_chunks: List[TextChunk] = []

    # 1. Papiers de recherche scientifiques (PDF)
    print("\n[INGESTING] Ingestion des 8 Papiers Scientifiques (PDF)...")
    metadata_index = RESEARCH_PAPERS_DIR / "papers_metadata_index.json"
    pdf_parser = PDFParser(metadata_index_path=metadata_index)

    research_pdf_files = list(RESEARCH_PAPERS_DIR.glob("*.pdf"))
    for pdf_file in sorted(research_pdf_files):
        chunks = pdf_parser.parse_pdf_file(pdf_file, source_type="academic_paper")
        print(f"  * {pdf_file.name} -> {len(chunks)} chunks extraits")
        all_chunks.extend(chunks)

    # 2. Guides High-Level (Markdown)
    print("\n[INGESTING] Ingestion des 3 Guides High-Level (Markdown)...")
    md_parser = MarkdownParser()
    high_level_files = list(HIGH_LEVEL_DIR.glob("*.md"))
    for md_file in sorted(high_level_files):
        chunks = md_parser.parse_markdown_file(md_file, source_type="high_level_guide")
        print(f"  * {md_file.name} -> {len(chunks)} chunks extraits")
        all_chunks.extend(chunks)

    # 3. Articles théoriques Spielverlagerung (Markdown)
    print("\n[INGESTING] Ingestion des 10 Articles Spielverlagerung (Markdown)...")
    raw_md_files = list(RAW_MARKDOWN_DIR.glob("*.md"))
    for md_file in sorted(raw_md_files):
        chunks = md_parser.parse_markdown_file(md_file, source_type="tactical_article")
        print(f"  * {md_file.name} -> {len(chunks)} chunks extraits")
        all_chunks.extend(chunks)

    print(f"\n[SUCCESS] Total de {len(all_chunks)} chunks préparés pour l'indexation.")
    return all_chunks


def main() -> None:
    """Point d'entrée principal pour l'indexation RAG."""
    print("=== Démarrage du Pipeline d'Indexation RAG Hybride foot-GPT ===")

    # 1. Ingestion et découpage de tous les documents
    chunks = ingest_all_documents()
    if not chunks:
        print("[ERROR] Aucun chunk n'a été extrait.")
        sys.exit(1)

    # 2. Construction de l'index BM25
    print("\n[INDEXING] Construction de l'index lexical Sparse BM25...")
    bm25 = BM25Retriever(index_path=BM25_INDEX_PATH)
    bm25.build_index(chunks)
    bm25.save()
    print(f"[SUCCESS] Index BM25 sauvegardé -> {BM25_INDEX_PATH}")

    # 3. Construction de la base vectorielle ChromaDB
    print("\n[INDEXING] Construction de la base vectorielle Dense ChromaDB...")
    vector_store = VectorStoreManager(persist_dir=CHROMA_PERSIST_DIR)
    vector_store.add_chunks(chunks)
    print(f"[SUCCESS] {vector_store.count()} documents indexés dans ChromaDB -> {CHROMA_PERSIST_DIR}")

    # 4. Test de validation de la recherche hybride avec re-ranking
    print("\n" + "=" * 60)
    print("[VERIFY] Test de recherche hybride avec Re-ranking & Citations :")
    print("=" * 60)

    retriever = HybridRetriever(
        bm25=bm25,
        vector_store=vector_store,
        reranker=CrossEncoderReranker(),
    )

    test_queries = [
        "Rest-Defense and counterpressing defensive balance",
        "Passing network centrality and team vulnerability",
        "The Half-Spaces Halbraum tactical advantages",
    ]

    for q in test_queries:
        print(f"\n🔍 Requête test : '{q}'")
        results = retriever.search(q, top_n_final=2)
        for idx, res in enumerate(results, 1):
            print(f"  [{idx}] Citation : {res['citation']}")
            print(f"      Source Type : {res['source_type']} | Score Re-rank : {res['rerank_score']}")
            snippet = res['content'].replace('\n', ' ')[:140]
            print(f"      Extrait : {snippet}...")

    print("\n" + "=" * 60)
    print("[SUCCESS] Pipeline d'indexation RAG terminé et validé avec succès !")
    print("=" * 60)


if __name__ == "__main__":
    main()
