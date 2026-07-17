"""Testes do Word Wise — definição rápida de um termo selecionado (tarefa 3.4).

Cobre: build_word_wise_prompt (core puro), WordWisePopover (estados), o
WordWiseWorker (Ollama mockado, think=False) e a fiação estática no
ReaderView (seleção curta habilita a ação; ela nunca abre o painel do RAG).
"""
from pathlib import Path

from src.core.study_prompts import build_word_wise_prompt

_ROOT = Path(__file__).resolve().parent.parent


# ── build_word_wise_prompt (core puro) ──────────────────────────────────

def test_empty_term_returns_none():
    assert build_word_wise_prompt("") is None
    assert build_word_wise_prompt("   ") is None
    assert build_word_wise_prompt(None) is None


def test_prompt_contains_term():
    prompt = build_word_wise_prompt("entropia")
    assert prompt is not None
    assert "entropia" in prompt


def test_prompt_without_context_has_no_context_block():
    prompt = build_word_wise_prompt("entropia")
    assert "CONTEXTO (trecho" not in prompt


def test_prompt_with_context_includes_it():
    prompt = build_word_wise_prompt("entropia", context="A entropia sempre cresce em sistemas isolados.")
    assert "CONTEXTO (trecho" in prompt
    assert "sistemas isolados" in prompt


def test_prompt_context_is_truncated():
    long_context = "x" * 5000
    prompt = build_word_wise_prompt("termo", context=long_context)
    # Não infla o prompt indefinidamente (mesmo teto de 800 chars).
    assert len(prompt) < 1200


def test_prompt_requests_short_answer_in_portuguese():
    prompt = build_word_wise_prompt("termo")
    assert "curta" in prompt.lower() or "curto" in prompt.lower()


# ── SelectionActionPopover: chave word_wise ──────────────────────────────

def test_popover_has_word_wise_action(qtbot):
    from src.gui.widgets.selection_popover import SelectionActionPopover

    pop = SelectionActionPopover()
    qtbot.addWidget(pop)
    assert "word_wise" in pop._buttons


def test_popover_word_wise_can_be_filtered_in(qtbot):
    from src.gui.widgets.selection_popover import SelectionActionPopover

    pop = SelectionActionPopover()
    qtbot.addWidget(pop)
    pop.set_actions(["highlight", "word_wise"])
    assert pop._buttons["word_wise"].isVisibleTo(pop)
    assert not pop._buttons["explain"].isVisibleTo(pop)


# ── WordWisePopover (estados) ────────────────────────────────────────────

def test_popover_shows_loading_then_definition(qtbot):
    from PyQt6.QtCore import QPoint
    from src.gui.widgets.word_wise_popover import WordWisePopover

    pop = WordWisePopover()
    qtbot.addWidget(pop)
    pop.show_loading("entropia", QPoint(10, 10))
    assert pop.isVisible()
    assert "entropia" in pop._term_label.text()
    assert "Buscando" in pop._body_label.text()

    pop.show_definition("entropia", "Medida da desordem de um sistema.")
    assert "desordem" in pop._body_label.text()


def test_popover_shows_error():
    from src.gui.widgets.word_wise_popover import WordWisePopover

    pop = WordWisePopover()
    pop.show_error()
    assert "indisponível" in pop._body_label.text()


def test_popover_close_button_hides(qtbot):
    from PyQt6.QtCore import QPoint
    from src.gui.widgets.word_wise_popover import WordWisePopover

    pop = WordWisePopover()
    qtbot.addWidget(pop)
    pop.show_loading("termo", QPoint(0, 0))
    assert pop.isVisible()
    pop._close_btn.click()
    assert not pop.isVisible()


def test_popover_set_theme_does_not_raise():
    from src.gui.widgets.word_wise_popover import WordWisePopover

    pop = WordWisePopover()
    for theme in ("dark", "light", "sepia"):
        pop.set_theme(theme)


# ── WordWiseWorker (Ollama mockado) ──────────────────────────────────────

def test_worker_emits_definition_on_success(qtbot, monkeypatch):
    from src.gui.workers.word_wise_worker import WordWiseWorker
    import src.core.ollama_client as oc

    monkeypatch.setattr(oc, "chat_once", lambda *a, **kw: "Medida da desordem de um sistema.")
    w = WordWiseWorker("entropia", context="trecho", model="fake:1b")
    got = []
    w.definition_ready.connect(lambda term, definition: got.append((term, definition)))
    w.run()
    assert got == [("entropia", "Medida da desordem de um sistema.")]


def test_worker_uses_think_false(qtbot, monkeypatch):
    from src.gui.workers.word_wise_worker import WordWiseWorker
    import src.core.ollama_client as oc

    calls = []

    def _fake_chat_once(url, model, messages, **kw):
        calls.append(kw)
        return "definição curta"

    monkeypatch.setattr(oc, "chat_once", _fake_chat_once)
    w = WordWiseWorker("termo", model="fake:1b")
    w.run()
    assert calls[0]["think"] is False


def test_worker_fails_on_empty_response(qtbot, monkeypatch):
    from src.gui.workers.word_wise_worker import WordWiseWorker
    import src.core.ollama_client as oc

    monkeypatch.setattr(oc, "chat_once", lambda *a, **kw: "")
    w = WordWiseWorker("termo", model="fake:1b")
    failed = []
    w.failed.connect(failed.append)
    w.run()
    assert len(failed) == 1


def test_worker_fails_gracefully_on_exception(qtbot, monkeypatch):
    from src.gui.workers.word_wise_worker import WordWiseWorker
    import src.core.ollama_client as oc

    def _boom(*a, **k):
        raise OSError("ollama fora")

    monkeypatch.setattr(oc, "chat_once", _boom)
    w = WordWiseWorker("termo", model="fake:1b")
    failed = []
    w.failed.connect(failed.append)
    w.run()  # nunca deve lançar (ADR-005)
    assert len(failed) == 1


def test_worker_cancel_stops_before_emit(qtbot, monkeypatch):
    from src.gui.workers.word_wise_worker import WordWiseWorker
    import src.core.ollama_client as oc

    monkeypatch.setattr(oc, "chat_once", lambda *a, **kw: "definição")
    w = WordWiseWorker("termo", model="fake:1b")
    got = []
    w.definition_ready.connect(lambda *a: got.append(a))
    w.cancel()
    w.run()
    assert got == []


def test_worker_empty_term_fails_without_calling_llm(qtbot, monkeypatch):
    from src.gui.workers.word_wise_worker import WordWiseWorker
    import src.core.ollama_client as oc

    called = []
    monkeypatch.setattr(oc, "chat_once", lambda *a, **kw: called.append(1) or "x")
    w = WordWiseWorker("   ", model="fake:1b")
    failed = []
    w.failed.connect(failed.append)
    w.run()
    assert len(failed) == 1
    assert called == []


# ── Fiação estática no ReaderView (3.4) ──────────────────────────────────

def test_reader_view_routes_word_wise_without_ai_panel():
    src = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")
    assert "WordWisePopover" in src
    assert "WordWiseWorker" in src
    assert "_start_word_wise" in src
    # A ação word_wise é tratada ANTES do fallback genérico que emite
    # ai_action_requested — nunca abre o painel do RAG.
    assert 'elif action == "word_wise"' in src


def test_reader_view_limits_word_wise_to_short_selection():
    src = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")
    assert "_WORD_WISE_MAX_WORDS" in src
