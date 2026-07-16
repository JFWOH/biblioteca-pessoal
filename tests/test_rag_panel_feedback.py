"""Testes dos botões de feedback 👍/👎 do RAGPanel (Fase 1b)."""
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

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


def test_changing_book_resets_conversation(qtbot):
    """Trocar de livro limpa a conversa visível do assistente."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_reading_context(1, "Livro A", 3, "trecho A")
    panel._response_area.setPlainText("resposta sobre o Livro A")
    panel._full_answer = "resposta sobre o Livro A"

    panel.set_reading_context(2, "Livro B", 1, "trecho B")

    assert panel._response_area.toPlainText() == ""
    assert panel._full_answer == ""


def test_turning_page_same_book_keeps_conversation(qtbot):
    """Virar página no MESMO livro não apaga a resposta em tela."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_reading_context(1, "Livro A", 3, "trecho p3")
    panel._response_area.setPlainText("resposta atual")

    panel.set_reading_context(1, "Livro A", 4, "trecho p4")

    assert panel._response_area.toPlainText() == "resposta atual"


# ── Motivo do 👎 (chips) ────────────────────────────────────────────────────────


def test_thumbs_down_shows_reason_chips(qtbot):
    """👎 esconde os botões de feedback e abre a linha de chips de motivo."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    panel._thumbs_down_btn.click()

    assert panel._reason_container.isVisibleTo(panel)
    assert not panel._thumbs_up_btn.isVisibleTo(panel)
    assert not panel._thumbs_down_btn.isVisibleTo(panel)


def test_thumbs_up_no_reason_chips(qtbot):
    """👍 mantém o fluxo de zero fricção: '✅ Obrigado!' e nenhum chip."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    panel._thumbs_up_btn.click()

    assert not panel._reason_container.isVisibleTo(panel)
    assert panel._thumbs_up_btn.text() == "✅ Obrigado!"


def test_reason_chip_after_persist_emits_key(qtbot):
    """Chip clicado com id já persistido emite (id, chave canônica) na hora."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_reason_submitted.connect(lambda fid, r: got.append((fid, r)))

    panel._thumbs_down_btn.click()
    panel.on_feedback_persisted(42)
    panel._reason_chip_btns[1].click()  # "Incompleta"

    assert got == [(42, "incompleta")]
    assert not panel._reason_container.isVisibleTo(panel)
    assert panel._thumbs_down_btn.text() == "✅ Obrigado!"


def test_reason_chip_before_persist_emits_when_id_arrives(qtbot):
    """Chip clicado ANTES do id: escolha guardada e emitida quando o id chega."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_reason_submitted.connect(lambda fid, r: got.append((fid, r)))

    panel._thumbs_down_btn.click()
    panel._reason_chip_btns[0].click()  # "Errada" — id ainda não chegou

    assert got == []
    assert panel._pending_reason == "resposta_errada"

    panel.on_feedback_persisted(77)

    assert got == [(77, "resposta_errada")]


def test_reason_other_enter_emits_free_text(qtbot):
    """'Outro…' revela o campo curto; Enter emite o texto livre cru."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_reason_submitted.connect(lambda fid, r: got.append((fid, r)))

    panel._thumbs_down_btn.click()
    panel.on_feedback_persisted(9)
    panel._reason_other_btn.click()

    assert panel._reason_edit.isVisibleTo(panel)
    assert not panel._reason_chip_btns[0].isVisibleTo(panel)

    panel._reason_edit.setText("faltou citar a fonte")
    panel._reason_edit.returnPressed.emit()

    assert got == [(9, "faltou citar a fonte")]
    assert not panel._reason_container.isVisibleTo(panel)


def test_reason_other_esc_returns_to_chips(qtbot):
    """Esc no campo livre descarta o texto e volta aos chips (voto preservado)."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    panel._thumbs_down_btn.click()
    panel._reason_other_btn.click()
    assert panel._reason_edit.isVisibleTo(panel)

    ev = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(panel._reason_edit, ev)

    assert not panel._reason_edit.isVisibleTo(panel)
    assert panel._reason_chip_btns[0].isVisibleTo(panel)
    assert panel._feedback_given is True


def test_empty_free_text_does_not_emit(qtbot):
    """Enter com campo vazio não emite motivo (fricção mínima, opcional)."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_reason_submitted.connect(lambda fid, r: got.append((fid, r)))

    panel._thumbs_down_btn.click()
    panel.on_feedback_persisted(3)
    panel._reason_other_btn.click()
    panel._reason_edit.setText("   ")
    panel._reason_edit.returnPressed.emit()

    assert got == []
    assert panel._reason_edit.isVisibleTo(panel)


def test_new_query_hides_reason_chips(qtbot):
    """Nova pergunta esconde os chips e zera o estado de motivo; voto único."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    panel._thumbs_down_btn.click()
    assert panel._reason_container.isVisibleTo(panel)

    panel._question_input.setText("outra pergunta")
    panel._on_send()

    assert not panel._reason_container.isVisibleTo(panel)
    assert panel._feedback_given is False
    assert panel._last_feedback_id is None
    assert panel._pending_reason is None


def test_reason_never_emitted_if_id_never_arrives(qtbot):
    """Se o id nunca chega, a escolha é descartada silenciosamente (ADR-005)."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_answer_complete("resposta")

    got = []
    panel.feedback_reason_submitted.connect(lambda fid, r: got.append((fid, r)))

    panel._thumbs_down_btn.click()
    panel._reason_chip_btns[2].click()  # "Fora do contexto" — sem id

    assert got == []
    assert panel._pending_reason == "fora_contexto"
    assert not panel._reason_container.isVisibleTo(panel)
