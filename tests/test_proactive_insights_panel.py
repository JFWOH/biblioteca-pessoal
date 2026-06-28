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
