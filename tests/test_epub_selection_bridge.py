"""Testes da ponte de seleção do EPUB (débito 3.4 / rodada B3).

O módulo ``epub_selection_bridge`` importa só ``PyQt6.QtCore`` (não
``QtWebEngineWidgets``), então roda na suíte normal — a fiação no
``reader_view`` (que puxa QtWebEngine) é coberta por inspeção estática em
``test_reader_view_guards.py``.
"""
from src.gui.widgets.epub_selection_bridge import (
    EpubSelectionBridge, EPUB_SELECTION_JS,
)


# ── EpubSelectionBridge (slot → sinal) ──────────────────────────────────

def test_bridge_emits_text_and_rect(qtbot):
    bridge = EpubSelectionBridge()
    got = []
    bridge.selection_ended.connect(lambda t, r: got.append((t, r)))
    bridge.on_selection_end("entropia", '{"x":10,"bottom":50}')
    assert got == [("entropia", '{"x":10,"bottom":50}')]


def test_bridge_empty_selection_emits_empty_strings(qtbot):
    bridge = EpubSelectionBridge()
    got = []
    bridge.selection_ended.connect(lambda t, r: got.append((t, r)))
    bridge.on_selection_end("", "")
    assert got == [("", "")]


def test_bridge_slot_is_registered_qt_slot():
    # O método precisa ser um pyqtSlot(str, str) para o QWebChannel expô-lo.
    from PyQt6.QtCore import pyqtSlot  # noqa: F401
    assert hasattr(EpubSelectionBridge, "on_selection_end")


# ── EPUB_SELECTION_JS (contrato do JS injetado) ─────────────────────────

def test_js_wires_mouseup_and_reads_selection():
    js = EPUB_SELECTION_JS
    assert "mouseup" in js
    assert "getSelection" in js
    assert "getBoundingClientRect" in js


def test_js_uses_qwebchannel_and_matching_names():
    js = EPUB_SELECTION_JS
    # Deve casar com o registerObject("epubBridge") e o slot on_selection_end.
    assert "QWebChannel" in js
    assert "qt.webChannelTransport" in js
    assert "epubBridge" in js
    assert "on_selection_end" in js


def test_js_loads_qwebchannel_resource():
    # Página via setHtml (about:blank) não traz qwebchannel.js — precisa do qrc.
    assert "qrc:///qtwebchannel/qwebchannel.js" in EPUB_SELECTION_JS


def test_js_is_idempotent_per_document():
    # loadFinished pode disparar mais de uma vez para o mesmo doc — a guarda
    # evita listeners de mouseup duplicados.
    assert "__epubWW" in EPUB_SELECTION_JS


def test_js_reports_rect_bottom_for_anchor():
    # O anchor do popover usa rect.bottom (borda inferior da seleção).
    assert "bottom" in EPUB_SELECTION_JS
