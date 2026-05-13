from app.services.research_source_selection import heuristic_sources_for
from app.services.research_sources import SUPPORTED_SOURCES


def test_biomedical_query_prefers_pubmed() -> None:
    src = heuristic_sources_for("clinical trial outcomes for pancreatic cancer biomarkers")
    assert "pubmed" in src
    assert len(src) >= 2


def test_ml_query_prefers_arxiv() -> None:
    src = heuristic_sources_for("scaling laws for transformer language models on arxiv")
    assert "arxiv" in src
    assert len(src) >= 2


def test_generic_topic_yields_catalogs() -> None:
    src = heuristic_sources_for("urban sociology housing policy citation network")
    for s in src:
        assert s in SUPPORTED_SOURCES
    assert len(src) >= 2


def test_explicit_minimum_padding() -> None:
    """Heuristic helper always returns usable breadth."""
    src = heuristic_sources_for("zzz undefined obscure topic qwerty12345")
    assert len(set(src).intersection(SUPPORTED_SOURCES)) == len(src)
    assert len(src) >= 2
