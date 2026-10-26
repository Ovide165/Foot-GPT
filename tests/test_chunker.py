"""
Tests du chunking en tokens : compteur factice (1 mot = 1 token) pour la logique, vrai
tokenizer pour la garantie de taille sur le corpus Markdown.
"""

from pathlib import Path

from src.config import CHUNK_OVERLAP_TOKENS, EMBEDDING_MAX_TOKENS, HIGH_LEVEL_DIR, RAW_MARKDOWN_DIR
from src.rag.chunker import (
    TextChunk,
    chunk_embedding_text,
    content_token_budget,
    count_tokens,
    split_text_by_tokens,
)
from src.rag.parsers.markdown_parser import MarkdownParser


def words(text: str) -> int:
    return len(text.split())


def sentence(i: int, n: int = 10) -> str:
    return f"S{i} " + " ".join(f"w{i}x{j}" for j in range(n - 2)) + "."


def test_short_text_is_a_single_chunk():
    assert split_text_by_tokens("Une phrase courte. Une autre.", 50, 10, count=words) == ["Une phrase courte. Une autre."]


def test_chunks_never_exceed_budget():
    text = "\n\n".join(" ".join(sentence(p * 10 + s) for s in range(6)) for p in range(8))
    chunks = split_text_by_tokens(text, 40, 10, count=words)
    assert len(chunks) > 3
    assert all(words(c) <= 40 for c in chunks)


def test_paragraph_kept_whole_when_it_fits_in_a_new_chunk():
    para_a = " ".join(sentence(i) for i in range(3))   # 30 tokens
    para_b = " ".join(sentence(10 + i) for i in range(3))  # 30 tokens
    chunks = split_text_by_tokens(para_a + "\n\n" + para_b, 40, 0, count=words)
    assert chunks == [para_a, para_b]  # B n'est pas coupe pour remplir le chunk de A


def test_oversized_paragraph_is_split_on_sentences_with_overlap():
    para = " ".join(sentence(i) for i in range(12))  # 120 tokens
    chunks = split_text_by_tokens(para, 45, 12, count=words)
    assert all(words(c) <= 45 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        # le chunk suivant commence par la derniere phrase entiere du precedent
        last_sentence = prev.split(". ")[-1].rstrip(".") if ". " in prev else prev
        assert nxt.startswith(last_sentence.split(". ")[-1][:6])


def test_overlap_is_bounded_and_made_of_whole_sentences():
    para = " ".join(sentence(i) for i in range(10))
    chunks = split_text_by_tokens(para, 35, 10, count=words)
    for prev, nxt in zip(chunks, chunks[1:]):
        overlap = [s for s in prev.split(". ") if nxt.startswith(s.rstrip("."))]
        assert overlap, "le chunk suivant doit reprendre la fin du precedent"
        assert words(overlap[-1]) <= 10


def test_no_overlap_when_disabled():
    para = " ".join(sentence(i) for i in range(10))
    chunks = split_text_by_tokens(para, 35, 0, count=words)
    assert " ".join(chunks).count("S3 ") == 1


def test_sentence_longer_than_budget_is_split_by_words():
    long_sentence = " ".join(f"mot{i}" for i in range(100)) + "."
    chunks = split_text_by_tokens(long_sentence, 30, 5, count=words)
    assert all(words(c) <= 30 for c in chunks)
    assert "mot99." in chunks[-1]


def test_hard_wrapped_pdf_text_is_unwrapped_and_split():
    page = "\n".join(f"{sentence(i, 6)}" for i in range(30))  # une seule "ligne par phrase", un seul paragraphe
    chunks = split_text_by_tokens(page, 40, 6, count=words)
    assert len(chunks) > 1
    assert all(words(c) <= 40 for c in chunks)


def test_list_items_are_kept_as_separate_lines():
    items = "\n".join(f"- point {i} " + "x " * 8 for i in range(12))
    chunks = split_text_by_tokens(items, 30, 0, count=words)
    assert all(line.startswith("- point") for c in chunks for line in c.splitlines())


def test_embedding_text_contains_title_and_section():
    chunk = TextChunk(chunk_id="a", content="corps", source_type="tactical_article",
                      title="Mon titre", section="Ma section", doc_id="d")
    assert chunk_embedding_text(chunk) == "Mon titre - Ma section\ncorps"


def test_content_budget_shrinks_with_long_titles_and_has_a_floor():
    short = content_token_budget("Titre", None, count=words)
    long = content_token_budget(" ".join(["mot"] * 100), None, count=words)
    assert short == 220 and long < short
    assert content_token_budget(" ".join(["mot"] * 400), None, count=words) == 32


def test_real_corpus_markdown_chunks_fit_the_embedding_window():
    """Titre + section + contenu + [CLS]/[SEP] <= 256 tokens du vrai tokenizer, sur tout le Markdown."""
    parser = MarkdownParser()
    files = sorted(Path(HIGH_LEVEL_DIR).glob("*.md")) + sorted(Path(RAW_MARKDOWN_DIR).glob("*.md"))
    assert files
    n = 0
    for f in files:
        for chunk in parser.parse_markdown_file(f):
            assert count_tokens(chunk_embedding_text(chunk)) + 2 <= EMBEDDING_MAX_TOKENS, chunk.chunk_id
            n += 1
    assert n > 0


def test_every_corpus_markdown_citation_is_recognised_by_the_citation_check(tmp_path):
    """Guides inclus : chaque citation produite doit avoir le format [Auteur, Annee - Titre]."""
    from src.rag.citations import extract_citations

    parser = MarkdownParser()
    files = sorted(Path(HIGH_LEVEL_DIR).glob("*.md")) + sorted(Path(RAW_MARKDOWN_DIR).glob("*.md"))
    for f in files:
        for chunk in parser.parse_markdown_file(f):
            citation = chunk.format_citation()
            assert extract_citations(citation) == [citation], f"{f.name}: {citation}"


def test_markdown_year_comes_from_frontmatter(tmp_path):
    md = tmp_path / "guide.md"
    md.write_text('---\ntitle: "Mon guide"\nyear: 2026\n---\n\n## Section\n\n' + "Une phrase utile sur le pressing. " * 20, encoding="utf-8")
    chunks = MarkdownParser().parse_markdown_file(md, source_type="high_level_guide")
    assert chunks and all(c.year == 2026 for c in chunks)
    assert chunks[0].format_citation() == "[foot-GPT Technical Staff, 2026 - Mon guide]"
