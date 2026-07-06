"""Testes do ConceptExtractor (Fase 2 — heurística + refino LLM com fallback)."""
import io
import json

import pytest

from src.core.graph.concept_extractor import ConceptExtractor


@pytest.fixture
def ex():
    return ConceptExtractor()


PAGE_PT = (
    "A entropia é uma medida da desordem de um sistema. Em termodinâmica, "
    "a entropia cresce em processos irreversíveis. A teoria da relatividade "
    "não trata de entropia diretamente, mas a teoria da relatividade mudou a "
    "física. Boltzmann relacionou a entropia à probabilidade; Boltzmann é "
    "central na mecânica estatística."
)


def test_normalize():
    assert ConceptExtractor.normalize("  Termodinâmica  Básica ") == "termodinamica basica"
    assert ConceptExtractor.normalize("ENTROPIA") == "entropia"


def test_heuristic_finds_repeated_terms(ex):
    concepts, method = ex.extract(PAGE_PT, max_concepts=8)
    assert method == "heuristic"
    names = [c[0] for c in concepts]
    assert "entropia" in names
    # Bigrama com stopword interna nas bordas válidas: "teoria da relatividade"
    assert "teoria da relatividade" in names


def test_heuristic_capitalization_bonus(ex):
    """Nome próprio no meio da frase ganha bônus (Boltzmann)."""
    concepts, _ = ex.extract(PAGE_PT, max_concepts=8)
    by_name = {c[0]: c for c in concepts}
    assert "boltzmann" in by_name
    assert by_name["boltzmann"][1] == "Boltzmann"  # display preserva a forma original


def test_heuristic_filters_stopwords_and_numbers(ex):
    text = "Em 1905 e 1915, de para com 42 1234 999" * 3
    concepts, _ = ex.extract(text, max_concepts=8)
    assert concepts == []


def test_heuristic_weights_normalized(ex):
    concepts, _ = ex.extract(PAGE_PT, max_concepts=8)
    assert concepts[0][2] == 1.0
    assert all(0 < c[2] <= 1.0 for c in concepts)


def test_short_text_allows_single_occurrence(ex):
    """Anotações são curtas: unigrama com freq 1 entra quando texto < 400 chars."""
    concepts, _ = ex.extract("Conceito fundamental: homeostase.", max_concepts=5)
    assert "homeostase" in [c[0] for c in concepts]


def test_long_text_requires_freq_2_for_unigrams(ex):
    filler = "palavra repetida vale nota. " * 20  # >400 chars
    text = filler + " A homeostase aparece uma única vez aqui."
    concepts, _ = ex.extract(text, max_concepts=20)
    names = [c[0] for c in concepts]
    assert "homeostase" not in names


def test_empty_text(ex):
    assert ex.extract("") == ([], "heuristic")
    assert ex.extract("   ") == ([], "heuristic")


# ── Refino LLM (urllib monkeypatchado) ────────────────────────────────

class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen_factory(content: str):
    body = json.dumps({"message": {"content": content}}).encode()

    def _fake(req, timeout=0):
        return _FakeResp(body)

    return _fake


def test_llm_refine_success(monkeypatch):
    ex = ConceptExtractor(llm_model="fake:1b")
    llm_json = json.dumps({"concepts": [
        {"name": "entropia", "relevance": 0.95},
        {"name": "teoria da relatividade", "relevance": 0.7},
        {"name": "conceito inventado xyz", "relevance": 0.9},  # não está no texto
    ]})
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen_factory(llm_json))
    concepts, method = ex.extract(PAGE_PT, max_concepts=5, use_llm=True)
    assert method == "llm"
    names = [c[0] for c in concepts]
    assert names[0] == "entropia"
    assert "conceito inventado xyz" not in names  # LLM não inventa
    assert concepts[0][2] == 0.95


def test_llm_failure_falls_back_to_heuristic(monkeypatch):
    ex = ConceptExtractor(llm_model="fake:1b")

    def _boom(req, timeout=0):
        raise OSError("ollama fora do ar")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    concepts, method = ex.extract(PAGE_PT, max_concepts=5, use_llm=True)
    assert method == "heuristic"
    assert concepts  # heurística segurou o resultado (ADR-005)


def test_llm_invalid_json_falls_back(monkeypatch):
    ex = ConceptExtractor(llm_model="fake:1b")
    monkeypatch.setattr("urllib.request.urlopen",
                        _fake_urlopen_factory("desculpe, não consigo"))
    concepts, method = ex.extract(PAGE_PT, max_concepts=5, use_llm=True)
    assert method == "heuristic"
    assert concepts


def test_llm_not_used_without_model(monkeypatch):
    ex = ConceptExtractor(llm_model=None)

    def _fail(*a, **k):
        raise AssertionError("não deveria chamar o Ollama sem modelo")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    _, method = ex.extract(PAGE_PT, use_llm=True)
    assert method == "heuristic"
