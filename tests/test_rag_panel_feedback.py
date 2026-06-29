"""Testes dos botões de feedback 👍/👎 do RAGPanel (Fase 1b)."""
from src.gui.widgets.rag_panel import RAGPanel


def test_feedback_hidden_until_answer(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    assert not panel._thumbs_up_btn.isVisibleTo(panel)
    assert not panel._thumbs_down_btn.isVisibleTo(panel)


def test_feedback_shown_after_answer(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("uma resposta qualquer")
    assert panel._thumbs_up_btn.isVisibleTo(panel)
    assert panel._thumbs_down_btn.isVisibleTo(panel)


def test_feedback_emits_context(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_reading_context(5, "Livro", 12, "trecho")
    panel._last_query = "minha pergunta"
    panel._current_session_id = "sess-1"
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_submitted.connect(lambda r, c: got.append((r, c)))
    panel._thumbs_up_btn.click()

    assert len(got) == 1
    rating, ctx = got[0]
    assert rating == 1
    assert ctx == {
        "kind": "answer",
        "book_id": 5,
        "page": 12,
        "session_id": "sess-1",
        "query": "minha pergunta",
    }


def test_feedback_single_vote(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_submitted.connect(lambda r, c: got.append(r))
    panel._thumbs_up_btn.click()
    panel._thumbs_down_btn.click()  # ignorado: já votou (e botão fica desabilitado)

    assert got == [1]
    assert panel._feedback_given is True


def test_feedback_global_context_book_none(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")  # sem reading_context

    got = []
    panel.feedback_submitted.connect(lambda r, c: got.append(c))
    panel._thumbs_down_btn.click()

    assert got[0]["book_id"] is None
    assert got[0]["page"] is None
