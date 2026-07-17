"""Testes de build_study_prompt (ações de estudo do agente de leitura)."""
from src.core.study_prompts import build_study_prompt, STUDY_ACTIONS


def test_known_action_keys():
    assert set(STUDY_ACTIONS) == {"explain_page", "summarize", "glossary", "flashcards"}


def test_all_actions_produce_prompt_with_text():
    trecho = "Texto da página sobre listas em Python."
    for action in STUDY_ACTIONS:
        prompt = build_study_prompt(action, trecho)
        assert prompt is not None
        assert trecho in prompt


def test_unknown_action_returns_none():
    assert build_study_prompt("nope", "qualquer texto") is None


def test_empty_text_returns_none():
    assert build_study_prompt("explain_page", "") is None
    assert build_study_prompt("explain_page", "   ") is None
    assert build_study_prompt("summarize", None) is None


def test_flashcards_prompt_mentions_qa_format():
    prompt = build_study_prompt("flashcards", "conteúdo de exemplo")
    assert "P:" in prompt and "R:" in prompt


def test_glossary_prompt_requests_term_definition_format():
    prompt = build_study_prompt("glossary", "conteúdo de exemplo")
    assert "termo" in prompt.lower()


# ── Injeção de conceitos do grafo (tarefa 3.3) ─────────────────────────

def test_flashcards_prompt_injects_book_concepts():
    prompt = build_study_prompt(
        "flashcards", "conteúdo", concepts=["entropia", "termodinâmica"])
    assert "entropia" in prompt and "termodinâmica" in prompt
    assert "conceitos-chave" in prompt.lower()
    # o trecho continua presente
    assert "conteúdo" in prompt


def test_concepts_none_or_empty_keeps_prompt_identical():
    base = build_study_prompt("flashcards", "conteúdo")
    assert build_study_prompt("flashcards", "conteúdo", concepts=None) == base
    assert build_study_prompt("flashcards", "conteúdo", concepts=[]) == base
    assert build_study_prompt("flashcards", "conteúdo", concepts=["  ", ""]) == base


def test_concepts_are_limited_in_prompt():
    many = [f"c{i}" for i in range(30)]
    prompt = build_study_prompt("flashcards", "conteúdo", concepts=many)
    # limita a 12 conceitos para não inflar o prompt
    assert "c0" in prompt and "c11" in prompt
    assert "c12" not in prompt


def test_concepts_injected_for_any_study_action_when_provided():
    prompt = build_study_prompt("summarize", "conteúdo", concepts=["x"])
    assert "x" in prompt and "conceitos-chave" in prompt.lower()
