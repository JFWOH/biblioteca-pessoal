"""Sprint B2 (item 9 do backlog UX): feedback ao vivo da seleção por fluxo.

Overlay que pinta os quads por linha durante o arrasto no PDF; o
QRubberBand retangular vira fallback para áreas sem texto. O reader_view
não é instanciável na suíte (importa QtWebEngine) — a fiação é verificada
por inspeção de fonte, padrão de test_book_dossier_wiring.py.
"""
import re
from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QWidget

from src.gui.widgets.selection_flow_overlay import SelectionFlowOverlay

_ROOT = Path(__file__).resolve().parent.parent
_READER_VIEW = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")


# ── Widget ─────────────────────────────────────────────────────────────

def test_overlay_starts_hidden_and_mouse_transparent(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = SelectionFlowOverlay(parent)
    assert not overlay.isVisibleTo(parent)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_set_rects_shows_and_covers_parent(qtbot):
    parent = QWidget()
    parent.resize(300, 200)
    qtbot.addWidget(parent)
    overlay = SelectionFlowOverlay(parent)
    overlay.set_rects([QRect(10, 10, 100, 14), QRect(10, 26, 80, 14)])
    assert overlay.isVisibleTo(parent)
    assert overlay.geometry() == parent.rect()


def test_set_rects_empty_hides(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = SelectionFlowOverlay(parent)
    overlay.set_rects([QRect(0, 0, 10, 10)])
    overlay.set_rects([])
    assert not overlay.isVisibleTo(parent)


def test_clear_hides_and_drops_rects(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = SelectionFlowOverlay(parent)
    overlay.set_rects([QRect(0, 0, 10, 10)])
    overlay.clear()
    assert not overlay.isVisibleTo(parent)
    assert overlay._rects == []


# ── Fiação no reader_view (inspeção de fonte) ──────────────────────────

def test_mousemove_uses_live_selection_with_rubber_fallback():
    move_block = re.search(
        r"elif event\.type\(\) == QEvent\.Type\.MouseMove and self\._is_selecting:(.*?)return True",
        _READER_VIEW, re.DOTALL).group(1)
    assert "_update_live_selection" in move_block
    # Geometria do rubber band segue sendo atualizada (release/popover dependem dela).
    assert "self._rubber_band.setGeometry" in move_block


def test_press_clears_overlay_and_starts_throttle():
    press_block = re.search(
        r"MouseButtonPress and event\.button\(\) == Qt\.MouseButton\.LeftButton:(.*?)return True",
        _READER_VIEW, re.DOTALL).group(1)
    assert "_selection_flow_overlay.clear()" in press_block
    assert "_flow_throttle.start()" in press_block


def test_marquee_helper_hides_both_visuals():
    helper = re.search(
        r"def _hide_selection_marquee\(self\).*?\n    def ",
        _READER_VIEW, re.DOTALL).group(0)
    assert "self._rubber_band.setVisible(False)" in helper
    assert "self._selection_flow_overlay.clear()" in helper
    # Nenhum hide() cru do rubber band sobrou fora do fluxo de seleção ao vivo.
    assert _READER_VIEW.count("self._rubber_band.hide()") == 1  # só no MouseMove (fluxo ativo)


def test_escape_also_clears_flow_overlay():
    """O Escape considera o overlay de fluxo, não só o rubber band."""
    assert ("self._rubber_band.isVisible() or "
            "self._selection_flow_overlay.isVisible()") in _READER_VIEW
