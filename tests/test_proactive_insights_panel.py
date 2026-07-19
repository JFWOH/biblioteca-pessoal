"""Testes do ProactiveInsightsPanel (histórico de observações do proativo)."""
from PyQt6.QtWidgets import QLabel, QPushButton

from src.gui.widgets.proactive_insights_panel import ProactiveInsightsPanel


def test_starts_empty(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    assert p._count == 0
    assert p._empty.isVisibleTo(p)


def test_add_observation_shows_card(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_observation({"tipo": "Contexto externo", "confianca": "Alta", "texto": "Algo útil."})
    assert p._count == 1
    assert p._list.count() == 1
    assert not p._empty.isVisibleTo(p)


def test_add_error_shows_card(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_error("modelo indisponível")
    assert p._count == 1
    assert p._list.count() == 1


def test_newest_on_top(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_observation({"tipo": "A", "texto": "primeiro"})
    p.add_observation({"tipo": "B", "texto": "segundo"})
    top = p._list.itemAt(0).widget()
    body = top.findChild(QLabel, "insightBody")
    assert body.text() == "segundo"


def test_flashcard_signal(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    got = []
    p.flashcard_requested.connect(got.append)
    p.add_observation({"tipo": "X", "texto": "conteúdo do card"})
    top = p._list.itemAt(0).widget()
    btn = top.findChild(QPushButton)
    assert btn is not None
    btn.click()
    assert got == ["conteúdo do card"]


def test_clear(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_observation({"tipo": "X", "texto": "a"})
    p.clear()
    assert p._count == 0
    assert p._list.count() == 0
    assert p._empty.isVisibleTo(p)


def test_set_theme_all_modes(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_observation({"tipo": "X", "texto": "a"})
    for theme in ("dark", "light", "sepia"):
        p.set_theme(theme)


def test_dismiss_button_present_with_id(qtbot):
    """O botão de dispensa ("✕") vai como ÍCONE (setIcon), não texto — bug de
    sobreposição do Windows (débito da Onda 4). Card com id tem 2 botões
    (dispensar + flashcard); o de dispensar tem texto vazio e ícone."""
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_observation({"tipo": "X", "texto": "a", "id": 42})
    top = p._list.itemAt(0).widget()
    buttons = top.findChildren(QPushButton)
    assert len(buttons) == 2
    assert any(b.text() == "" and not b.icon().isNull() for b in buttons)


def test_no_dismiss_button_without_id(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.add_observation({"tipo": "X", "texto": "a"})
    top = p._list.itemAt(0).widget()
    buttons = top.findChildren(QPushButton)
    assert len(buttons) == 1  # só o botão de flashcard, sem dispensar
    assert all(b.text() != "" for b in buttons)


def test_empty_text_reflects_agent_inactive_by_default(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    assert "Ative o agente" in p._empty.text()


def test_set_agent_active_updates_empty_text(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    p.set_agent_active(True)
    assert "ativo" in p._empty.text().lower()
    assert "Ative o agente" not in p._empty.text()
    p.set_agent_active(False)
    assert "Ative o agente" in p._empty.text()


def test_dismiss_emits_obs_id_and_removes_card(qtbot):
    p = ProactiveInsightsPanel()
    qtbot.addWidget(p)
    got = []
    p.dismiss_requested.connect(got.append)
    p.add_observation({"tipo": "X", "texto": "a", "id": 42})
    top = p._list.itemAt(0).widget()
    close_btn = next(b for b in top.findChildren(QPushButton) if b.text() == "")
    close_btn.click()
    assert got == [42]
    assert p._count == 0
    assert p._empty.isVisibleTo(p)
