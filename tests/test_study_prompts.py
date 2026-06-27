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
