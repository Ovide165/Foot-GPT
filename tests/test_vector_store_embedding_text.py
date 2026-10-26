"""
Le vecteur doit etre calcule sur titre + section + contenu, le document stocke rester le contenu.
"""

import numpy as np

from src.rag.chunker import TextChunk, chunk_embedding_text
from src.rag.vector_store import VectorStoreManager


def _chunk(cid: str, content: str, title: str, section=None) -> TextChunk:
    return TextChunk(chunk_id=cid, content=content, source_type="tactical_article",
                     title=title, authors="A", year=2020, section=section, doc_id=cid)


def test_embedding_is_computed_on_title_section_and_content(tmp_path):
    vs = VectorStoreManager(persist_dir=tmp_path / "chroma")
    chunk = _chunk("c1", "Players receive the ball between the lines.", "The Half-Spaces", "Definition")
    vs.add_chunks([chunk])

    stored = vs.collection.get(ids=["c1"], include=["documents", "embeddings"])
    assert stored["documents"][0] == chunk.content  # le contenu affiche au LLM n'est pas pollue

    with_header = np.array(vs.embedding_fn([chunk_embedding_text(chunk)])[0])
    content_only = np.array(vs.embedding_fn([chunk.content])[0])
    vector = np.array(stored["embeddings"][0])
    assert np.allclose(vector, with_header, atol=1e-5)
    assert not np.allclose(vector, content_only, atol=1e-5)


def test_reset_removes_stale_chunks(tmp_path):
    vs = VectorStoreManager(persist_dir=tmp_path / "chroma")
    vs.add_chunks([_chunk("old", "ancien contenu", "Ancien")])
    vs.reset()
    vs.add_chunks([_chunk("new", "nouveau contenu", "Nouveau")])
    assert vs.count() == 1
    assert vs.collection.get(ids=["old"])["ids"] == []
