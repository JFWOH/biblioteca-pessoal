"""Testes de build_study_prompt (ações de estudo do agente de leitura)."""
from pathlib import Path

from src.core.study_prompts import build_study_prompt, STUDY_ACTIONS

_ROOT = Path(__file__).resolve().parent.parent


def test_known_action_keys():
    assert set(STUDY_ACTIONS) == {
        "explain_page", "summarize", "glossary", "flashcards", "simplify"}


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


# ── Critérios objetivos da revisão A/B (Q.3) ────────────────────────────
# (a) ancoragem no trecho · (b) tamanho explícito · (c) citação de fonte
# quando aplicável · (d) idioma da resposta.

def test_every_study_prompt_pins_the_answer_language():
    """(d) O trecho pode estar em inglês; a resposta é sempre em pt-BR."""
    for action in STUDY_ACTIONS:
        prompt = build_study_prompt(action, "conteúdo").lower()
        assert "português do brasil" in prompt, action
        assert "outro idioma" in prompt, action


def test_every_study_prompt_is_anchored_to_the_excerpt():
    """(a) Nenhuma ação pode responder solta do trecho selecionado."""
    for action in STUDY_ACTIONS:
        prompt = build_study_prompt(action, "conteúdo").lower()
        assert "trecho" in prompt, action


def test_every_study_prompt_has_an_explicit_size_limit():
    """(b) Resposta de leitura é curta: todo template declara um teto."""
    limits = {
        "explain_page": "no máximo 200 palavras",
        "summarize": "no máximo 5 tópicos",
        "glossary": "no máximo 8 termos",
        "flashcards": "de 3 a 6 flashcards",
        "simplify": "no máximo 4 frases",
    }
    for action, needle in limits.items():
        assert needle in build_study_prompt(action, "conteúdo"), action


def test_explain_page_marks_external_knowledge_and_cites_sources():
    """(a)+(c) Explicar pode ir além do trecho, mas tem de sinalizar e citar."""
    prompt = build_study_prompt("explain_page", "conteúdo")
    assert "(fora do trecho)" in prompt
    assert "citando a fonte" in prompt


def test_summarize_and_glossary_keep_their_no_invention_rule():
    """A revisão B não pode ter afrouxado a regra antiga de não inventar."""
    assert "não esteja no texto" in build_study_prompt("summarize", "x")
    assert "apareçam no texto" in build_study_prompt("glossary", "x")


# ── Ação "Simplificar" (Q.3 / candidato N.4) ────────────────────────────

def test_simplify_prompt_targets_a_lay_reader_without_jargon():
    prompt = build_study_prompt("simplify", "conteúdo técnico").lower()
    assert "linguagem simples" in prompt
    assert "jargão" in prompt
    assert "não conhece o assunto" in prompt


def test_simplify_prompt_forbids_outside_information():
    prompt = build_study_prompt("simplify", "conteúdo").lower()
    assert "apenas o que está no trecho" in prompt
    assert "informação de fora" in prompt


def test_simplify_prompt_carries_the_excerpt():
    trecho = "A entropia mede a incerteza média de uma fonte."
    assert trecho in build_study_prompt("simplify", trecho)


def test_simplify_respects_empty_text_and_unknown_action_contract():
    assert build_study_prompt("simplify", "") is None
    assert build_study_prompt("simplify", None) is None


def test_main_window_routes_simplify_through_build_study_prompt():
    """A ação nova reusa o fluxo do Estudar/Explicar (painel do assistente).

    Guarda estática no mesmo padrão de test_highlight_cards: sem esta chave
    no dispatch, o botão "Simplificar" viraria um no-op silencioso.
    """
    import re

    src = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    dispatch = re.search(
        r"elif action_type in \((?P<keys>[^)]*)\):\s*\n\s*from src\.core\.study_prompts",
        src)
    assert dispatch is not None, "dispatch das ações de estudo não encontrado"
    assert '"simplify"' in dispatch.group("keys")
    assert "build_study_prompt(action_type, text, concepts=concepts)" in src
