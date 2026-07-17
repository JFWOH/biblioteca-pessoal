"""Testes da geração de flashcards a partir dos destaques (tarefa 3.3).

Worker com Ollama mockado (mesmo padrão de test_flashcard_qa), preview
editável/selecionável, e fiação estática da injeção de conceitos.
"""
from pathlib import Path


# ── HighlightCardsWorker (Ollama mockado) ─────────────────────────────

def _fake_chat_ok(url, model, messages, **kw):
    return '{"pergunta": "O que é?", "resposta": "É isso."}'


def test_worker_generates_one_card_per_highlight(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import HighlightCardsWorker
    import src.core.ollama_client as oc
    monkeypatch.setattr(oc, "chat_once", _fake_chat_ok)

    w = HighlightCardsWorker(["destaque um", "destaque dois"], model="fake:1b")
    got, progress = [], []
    w.cards_ready.connect(got.append)
    w.progress.connect(lambda d, t: progress.append((d, t)))
    w.run()

    assert len(got) == 1
    cards = got[0]
    assert len(cards) == 2
    assert cards[0]["front"] == "O que é?" and cards[0]["back"] == "É isso."
    assert cards[0]["source"] == "destaque um"
    assert progress[-1] == (2, 2)


def test_worker_fallback_when_llm_fails(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import HighlightCardsWorker
    import src.core.ollama_client as oc

    def _boom(*a, **k):
        raise OSError("ollama fora")

    monkeypatch.setattr(oc, "chat_once", _boom)
    w = HighlightCardsWorker(["um destaque importante"], model="fake:1b")
    got = []
    w.cards_ready.connect(got.append)
    w.run()

    assert len(got) == 1 and len(got[0]) == 1
    card = got[0][0]
    assert card["front"] == ""                      # pergunta em branco
    assert card["back"] == "um destaque importante"  # destaque no verso (ADR-005)


def test_worker_filters_empty_and_caps_max(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import HighlightCardsWorker
    import src.core.ollama_client as oc
    monkeypatch.setattr(oc, "chat_once", _fake_chat_ok)

    highlights = ["", "   ", "válido"] + [f"h{i}" for i in range(100)]
    w = HighlightCardsWorker(highlights, model="fake:1b")
    assert len(w._highlights) == HighlightCardsWorker.MAX_HIGHLIGHTS
    assert "" not in w._highlights and "   " not in w._highlights


def test_worker_cancel_stops_before_emit(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import HighlightCardsWorker
    import src.core.ollama_client as oc
    monkeypatch.setattr(oc, "chat_once", _fake_chat_ok)

    w = HighlightCardsWorker(["a", "b"], model="fake:1b")
    got = []
    w.cards_ready.connect(got.append)
    w.cancel()
    w.run()
    assert got == []  # cancelado antes de emitir


# ── Preview editável/selecionável ─────────────────────────────────────

def test_preview_selects_only_checked_complete_cards(qtbot):
    from src.gui.dialogs.flashcards_dialog import _HighlightCardsPreview
    cards = [
        {"front": "Q1", "back": "A1"},
        {"front": "", "back": "fallback"},  # incompleto → desmarcado por padrão
        {"front": "Q3", "back": "A3"},
    ]
    dlg = _HighlightCardsPreview(cards)
    qtbot.addWidget(dlg)

    selected = dlg.selected_cards()
    assert {c["front"] for c in selected} == {"Q1", "Q3"}

    # completa e marca o fallback → passa a ser salvo
    check, front_edit, back_edit = dlg._rows[1]
    front_edit.setText("Q2")
    check.setChecked(True)
    selected = dlg.selected_cards()
    assert {c["front"] for c in selected} == {"Q1", "Q2", "Q3"}

    # desmarca um → sai da seleção
    dlg._rows[0][0].setChecked(False)
    selected = dlg.selected_cards()
    assert {c["front"] for c in selected} == {"Q2", "Q3"}


# ── Fiação da injeção de conceitos (checagem estática) ────────────────

_ROOT = Path(__file__).resolve().parent.parent


def test_main_window_injects_concepts_into_flashcards():
    src = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    assert "def _book_graph_concepts" in src
    assert "graph_book_concepts" in src
    # o prompt de flashcards recebe concepts
    assert "build_study_prompt(action_type, text, concepts=concepts)" in src


def test_flashcards_dialog_has_highlights_action():
    src = (_ROOT / "src" / "gui" / "dialogs" / "flashcards_dialog.py").read_text(encoding="utf-8")
    assert "def _generate_from_highlights" in src
    assert "self._highlights_btn" in src
    assert "HighlightCardsWorker" in src
    assert 'get_annotations(book_id, "highlight")' in src
