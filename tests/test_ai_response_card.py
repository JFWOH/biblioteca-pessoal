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


# ── Skeleton shimmer no gap pré-primeiro-token (onda S) ────────────────────

def test_skeleton_hidden_while_idle(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    assert not card._skeleton.isVisibleTo(card)
    assert not card._skeleton.is_animating()


def test_skeleton_shows_and_animates_during_thinking(qtbot):
    """O gap "pensando, corpo vazio" agora tem placeholder animado."""
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    assert card._skeleton.isVisibleTo(card)
    assert card._skeleton.is_animating()
    assert not card._body_lbl.isVisibleTo(card)


def test_skeleton_disappears_on_first_chunk(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.append_text("primeiro token")
    assert not card._skeleton.isVisibleTo(card)
    assert not card._skeleton.is_animating(), "timer parado: nada anima à toa"
    assert card._body_lbl.isVisibleTo(card)


def test_skeleton_stops_on_finish_and_fail(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    card.finish()
    assert not card._skeleton.is_animating()
    card.start()
    card.fail("caiu")
    assert not card._skeleton.isVisibleTo(card)
    assert not card._skeleton.is_animating()


def test_skeleton_color_comes_from_card_palette(qtbot):
    """Sem cor hardcoded: a base sai da paleta do corpo do cartão (tema)."""
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    expected = card._body_lbl.palette().color(card._body_lbl.foregroundRole())
    assert card._skeleton._base == expected


# ── Timeline colapsável dos passos do agente (onda S) ──────────────────────

def test_steps_accumulate_instead_of_only_last_status(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("🔎 Buscando nos livros…")
    card.set_status("🕸 Consultando o grafo…")
    card.set_status("✍️ Redigindo…")
    assert card.steps() == ["🔎 Buscando nos livros…", "🕸 Consultando o grafo…",
                            "✍️ Redigindo…"]
    assert card.status_text() == "✍️ Redigindo…", "a linha de status é a última"


def test_steps_ignore_volatile_tick_repetitions(qtbot):
    """"💭 Pensando… (N tokens · Ns)" é UM passo, não um por tick."""
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("💭 Pensando… (1 tokens · 0s)")
    card.set_status("💭 Pensando… (42 tokens · 7s)")
    card.set_status("💭 Pensando… (91 tokens · 13s)")
    assert card.steps() == ["💭 Pensando…"]


def test_steps_toggle_collapsed_by_default_and_expands(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("🔎 Buscando…")
    card.set_status("🕸 Grafo…")
    card.set_status("✍️ Redigindo…")
    assert card._steps_toggle.isVisibleTo(card)
    assert not card._steps_toggle.isChecked()
    assert not card._steps_lbl.isVisibleTo(card)
    assert "3 passos" in card._steps_toggle.text()

    card._steps_toggle.setChecked(True)   # clique do usuário
    assert card._steps_lbl.isVisibleTo(card)
    assert "Buscando" in card._steps_lbl.text()
    assert "Redigindo" in card._steps_lbl.text()


def test_steps_singular_label_with_one_step(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("🔎 Buscando…")
    assert "1 passo" in card._steps_toggle.text()
    assert "passos" not in card._steps_toggle.text()


def test_steps_collapse_and_become_discreet_when_answer_ends(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("🔎 Buscando…")
    card.set_status("✍️ Redigindo…")
    card._steps_toggle.setChecked(True)
    card.append_text("resposta")
    card.finish()
    assert not card._steps_toggle.isChecked(), "volta a colapsar ao terminar"
    assert not card._steps_lbl.isVisibleTo(card)
    assert card._steps_toggle.objectName() == "aiResponseStepsToggleDone"


def test_steps_reset_on_new_question(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("🔎 Buscando…")
    card.set_status("✍️ Redigindo…")
    card.finish()
    card.start("🔎 Buscando de novo…")
    assert card.steps() == ["🔎 Buscando de novo…"]
    assert card._steps_toggle.objectName() == "aiResponseStepsToggle"


def test_steps_capped_at_max(qtbot):
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start("passo 0")
    for i in range(1, 40):
        card.set_status(f"passo {i}")
    assert len(card.steps()) == card.MAX_STEPS
    assert card.steps()[-1] == "passo 39"
