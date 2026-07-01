"""Testes do ReaderDock (dock em abas do leitor)."""
from PyQt6.QtWidgets import QLabel
from src.gui.widgets.reader_dock import ReaderDock


def test_first_tab_auto_shown(qtbot):
    dock = ReaderDock()
    qtbot.addWidget(dock)
    dock.add_tab("annotations", "Anotações", QLabel("a"))
    assert dock.has_tab("annotations")
    assert dock.current_key() == "annotations"


def test_show_tab_switches(qtbot):
    dock = ReaderDock()
    qtbot.addWidget(dock)
    dock.add_tab("annotations", "Anotações", QLabel("a"))
    dock.add_tab("assistant", "Assistente", QLabel("b"))
    # segunda aba não rouba o foco automaticamente
    assert dock.current_key() == "annotations"
    dock.show_tab("assistant")
    assert dock.current_key() == "assistant"


def test_tab_changed_signal(qtbot):
    dock = ReaderDock()
    qtbot.addWidget(dock)
    dock.add_tab("a", "A", QLabel())
    dock.add_tab("b", "B", QLabel())
    got = []
    dock.tab_changed.connect(got.append)
    dock.show_tab("b")
    assert got and got[-1] == "b"


def test_remove_tab_returns_widget_without_destroying(qtbot):
    dock = ReaderDock()
    qtbot.addWidget(dock)
    keep = QLabel("x")
    dock.add_tab("annotations", "Anotações", QLabel())
    dock.add_tab("assistant", "Assistente", keep)
    returned = dock.remove_tab("assistant")
    assert returned is keep
    assert not dock.has_tab("assistant")
    # após remover, a aba restante vira a ativa
    assert dock.current_key() == "annotations"


def test_closed_signal_on_close_button(qtbot):
    dock = ReaderDock()
    qtbot.addWidget(dock)
    fired = []
    dock.closed.connect(lambda: fired.append(True))
    dock._close_btn.click()
    assert fired == [True]


def test_set_theme_all_modes(qtbot):
    dock = ReaderDock()
    qtbot.addWidget(dock)
    dock.add_tab("a", "A", QLabel())
    for theme in ("dark", "light", "sepia"):
        dock.set_theme(theme)
