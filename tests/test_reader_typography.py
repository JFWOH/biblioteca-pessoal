"""Testes da tipografia do leitor (Tarefa 1.1) e do painel de marcadores.

Cobre:
- ``get_reader_css``: agora aplica a tipografia da config (antes ignorava);
- ``ReaderTypographyPopover``: widget isolado (pytest-qt), sinais ao vivo;
- ``BookmarksPanel``: widget isolado, lista/navega/remove;
- ``reader_view.py``: checagem ESTÁTICA da fiação (não pode ser importado
  depois de existir uma QApplication — puxa QtWebEngine; ver
  ``test_reader_view_guards.py``).
"""
from pathlib import Path

from PyQt6.QtWidgets import QPushButton

from src.gui.styles import get_reader_css
from src.gui.widgets.reader_typography_popover import (
    ReaderTypographyPopover,
    _COMFORT_FONT_SIZE,
    _COMFORT_LINE_HEIGHT,
    _COMFORT_MARGIN_HORIZONTAL,
)
from src.gui.widgets.bookmarks_panel import BookmarksPanel

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


# ── get_reader_css: tipografia da config vira CSS ──────────────────────

def test_reader_css_applies_typography():
    css = get_reader_css("dark", font_family="Verdana", font_size=22,
                         line_height=2.1, margin_h=88, margin_v=33)
    assert "font-size: 22px" in css
    assert "line-height: 2.1" in css
    assert "'Verdana'" in css
    assert "padding: 33px 88px" in css


def test_reader_css_defaults_preserve_theme_body():
    css = get_reader_css("dark")
    assert "background-color: #0f1115" in css  # cor do tema preservada
    assert "body {" in css


def test_reader_css_unknown_theme_falls_back_dark():
    css = get_reader_css("inexistente", font_size=10)
    assert "font-size: 10px" in css
    assert "background-color: #0f1115" in css


# ── ReaderTypographyPopover (widget isolado) ───────────────────────────

def test_popover_emits_typography_changed_on_size(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    pop.set_values("Georgia", 14, 1.6, 60, "dark")
    received = []
    pop.typography_changed.connect(received.append)
    pop._font_size.setValue(20)
    assert received
    assert received[-1]["font_size"] == 20


def test_popover_set_values_does_not_emit(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    received = []
    pop.typography_changed.connect(received.append)
    pop.set_values("Georgia", 18, 1.8, 50, "sepia")
    assert received == []  # carregar valores não dispara aplicação ao vivo
    vals = pop.current_values()
    assert vals["font_size"] == 18
    assert vals["line_height"] == 1.8
    assert vals["margin_horizontal"] == 50


def test_popover_theme_button_emits(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    pop.set_values("Georgia", 14, 1.6, 60, "dark")
    received = []
    pop.theme_changed.connect(received.append)
    pop._theme_buttons["sepia"].click()
    assert received == ["sepia"]
    assert pop._theme_buttons["sepia"].isChecked()


def test_popover_comfort_preset_applies_calibrated_values(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    pop.set_values("Georgia", 14, 1.6, 60, "dark")
    # Família real resolvida pelo QFontComboBox no ambiente do teste (o
    # offscreen QPA não tem "Georgia" instalada e cai num fallback) — o que
    # importa aqui é que o preset não MUDE a família, não qual ela é.
    baseline_family = pop.current_values()["font_family"]
    received = []
    pop.typography_changed.connect(received.append)
    pop._comfort_btn.click()
    assert len(received) == 1  # um único sinal consolidado, não um por controle
    vals = received[-1]
    assert vals["font_size"] == _COMFORT_FONT_SIZE
    assert vals["line_height"] == _COMFORT_LINE_HEIGHT
    assert vals["margin_horizontal"] == _COMFORT_MARGIN_HORIZONTAL
    assert vals["font_family"] == baseline_family  # preset não mexe na família da fonte
    # Controles refletem o preset (mesma fonte que os sinais existentes usam)
    assert pop._font_size.value() == _COMFORT_FONT_SIZE
    assert pop.current_values()["line_height"] == _COMFORT_LINE_HEIGHT
    assert pop._margin.value() == _COMFORT_MARGIN_HORIZONTAL
    assert pop._comfort_btn.text() == "Restaurar"


def test_popover_comfort_preset_second_click_restores_snapshot(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    pop.set_values("Verdana", 13, 1.4, 45, "light")
    baseline = pop.current_values()  # valores REAIS resolvidos pelos widgets
    received = []
    pop.typography_changed.connect(received.append)
    pop._comfort_btn.click()  # aplica o preset
    pop._comfort_btn.click()  # restaura
    assert len(received) == 2
    restored = received[-1]
    assert restored == baseline
    assert pop.current_values() == restored
    assert pop._comfort_btn.text() == "Leitura confortável"
    assert pop._comfort_snapshot is None


def test_popover_set_values_resets_pending_preset(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    pop.set_values("Georgia", 14, 1.6, 60, "dark")
    pop._comfort_btn.click()
    assert pop._comfort_snapshot is not None
    assert pop._comfort_btn.text() == "Restaurar"
    # Reabrir o popover (nova chamada externa) descarta o preset pendente
    pop.set_values("Georgia", 14, 1.6, 60, "dark")
    assert pop._comfort_snapshot is None
    assert pop._comfort_btn.text() == "Leitura confortável"


def test_popover_closed_signal_on_hide(qtbot):
    pop = ReaderTypographyPopover()
    qtbot.addWidget(pop)
    pop.show()
    fired = []
    pop.closed.connect(lambda: fired.append(True))
    pop.hide()
    assert fired == [True]


# ── BookmarksPanel (widget isolado) ────────────────────────────────────

def _row_button(panel, index, object_name):
    row = panel._list.itemWidget(panel._list.item(index))
    for b in row.findChildren(QPushButton):
        if b.objectName() == object_name:
            return b
    raise AssertionError(f"botão {object_name!r} não encontrado na linha {index}")


def test_bookmarks_panel_lists_and_navigates(qtbot):
    panel = BookmarksPanel()
    qtbot.addWidget(panel)
    panel.set_bookmarks([
        {"page_number": 0, "label": "Início"},
        {"page_number": 4, "label": ""},
    ])
    assert panel._list.count() == 2
    selected = []
    panel.bookmark_selected.connect(selected.append)
    _row_button(panel, 1, "bookmarkGotoBtn").click()
    assert selected == [4]


def test_bookmarks_panel_remove_emits(qtbot):
    panel = BookmarksPanel()
    qtbot.addWidget(panel)
    panel.set_bookmarks([{"page_number": 2, "label": "x"}])
    removed = []
    panel.bookmark_removed.connect(removed.append)
    _row_button(panel, 0, "bookmarkRemoveBtn").click()
    assert removed == [2]


def test_bookmarks_panel_empty_state(qtbot):
    panel = BookmarksPanel()
    qtbot.addWidget(panel)
    panel.set_bookmarks([])
    assert panel._list.count() == 0
    assert panel._empty.isVisibleTo(panel)


# ── reader_view.py: fiação (checagem estática do fonte) ────────────────

def test_reader_view_wires_typography_and_bookmarks():
    src = _READER_VIEW.read_text(encoding="utf-8")
    # Tarefa 1.1 — botão "Aa" + popover + pipeline de re-render
    assert 'QPushButton("Aa")' in src
    assert "ReaderTypographyPopover" in src
    assert "_open_typography_popover" in src
    assert "_reader_css" in src
    # Tarefa 1.5 — bookmark toggle + painel em abas
    assert "_bookmark_btn" in src
    assert "_toggle_current_bookmark" in src
    assert "BookmarksPanel" in src
    assert '"Sumário"' in src
    assert '"Marcadores"' in src


def test_reader_css_reuses_settings_reader_keys():
    """A tipografia sai das MESMAS chaves reader.* que o settings_dialog grava."""
    src = _READER_VIEW.read_text(encoding="utf-8")
    for key in ("reader.font_family", "reader.font_size", "reader.line_height",
                "reader.margin_horizontal", "reader.margin_vertical"):
        assert key in src, f"chave ausente na fiação do leitor: {key}"
