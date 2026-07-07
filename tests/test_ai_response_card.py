"""Testes do cartão padronizado de resposta de IA (Sprint B1, §3.2).

Máquina de estados: idle → thinking → streaming → done | error, com os
botões Parar (em progresso) e Tentar de novo (erro).
"""

from src.gui.widgets.ai_response_card import AIResponseCard


def test_initial_state_is_idle_everything_hidden(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    assert card.state == card.STATE_IDLE
    assert not card._stop_btn.isVisibleTo(card)
    assert not card._retry_btn.isVisibleTo(card)
    assert not card._body_lbl.isVisibleTo(card)


def test_start_enters_thinking_with_stop_button(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("🤔 Pensando…")
    assert card.state == card.STATE_THINKING
    assert card.status_text() == "🤔 Pensando…"
    assert card._stop_btn.isVisibleTo(card)
    assert not card._retry_btn.isVisibleTo(card)


def test_set_status_updates_during_thinking(qtbot):
    """Os ticks de raciocínio do A1 ("Raciocinando… 12s") fluem pelo set_status."""
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.set_status("🤔 Raciocinando… 12s")
    assert card.status_text() == "🤔 Raciocinando… 12s"


def test_set_status_ignored_when_done_or_idle(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.set_status("não deve aparecer")  # idle
    assert card.status_text() == ""
    card.start()
    card.finish()
    card.set_status("também não")  # done
    assert card.status_text() != "também não"


def test_append_text_streams_and_accumulates(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.append_text("Olá ")
    card.append_text("mundo")
    assert card.state == card.STATE_STREAMING
    assert card.text() == "Olá mundo"
    assert card._stop_btn.isVisibleTo(card)  # ainda dá para parar


def test_finish_keeps_text_hides_controls(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.set_text("Resposta completa.")
    card.finish()
    assert card.state == card.STATE_DONE
    assert card.text() == "Resposta completa."
    assert not card._stop_btn.isVisibleTo(card)
    assert not card._status_lbl.isVisibleTo(card)
    assert card._body_lbl.isVisibleTo(card)


def test_fail_shows_message_and_retry(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.fail("IA offline.")
    assert card.state == card.STATE_ERROR
    assert card.status_text() == "IA offline."
    assert card._retry_btn.isVisibleTo(card)
    assert not card._stop_btn.isVisibleTo(card)


def test_stop_and_retry_signals(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    stops, retries = [], []
    card.stop_requested.connect(lambda: stops.append(1))
    card.retry_requested.connect(lambda: retries.append(1))

    card.start()
    card._stop_btn.click()
    assert stops == [1]

    card.fail("erro")
    card._retry_btn.click()
    assert retries == [1]


def test_restart_after_error_clears_body(qtbot):
    """Tentar de novo → start() limpa o corpo e volta ao thinking."""
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.append_text("resposta pela metade")
    card.fail("caiu")
    card.start("De novo…")
    assert card.state == card.STATE_THINKING
    assert card.text() == ""
    assert card.status_text() == "De novo…"
