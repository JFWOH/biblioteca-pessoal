"""Testes do rename de anotações no painel (item 3 do backlog UX)."""
from PyQt6.QtWidgets import QInputDialog

from src.gui.widgets.annotation_panel import AnnotationItem, AnnotationPanel


def _ann(**over) -> dict:
    base = {"id": 7, "book_id": 1, "page_number": 0, "title": "velho",
            "content": "corpo", "annotation_type": "ai_note",
            "highlight_color": "#fbbf24", "created_at": "2026-07-01 10:00:00"}
    base.update(over)
    return base


def test_rename_button_emits_new_title(qtbot, monkeypatch):
    item = AnnotationItem(_ann())
    qtbot.addWidget(item)
    got = []
    item.rename_requested.connect(lambda i, t: got.append((i, t)))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Novo título", True)))
    item._rename_btn.click()
    assert got == [(7, "Novo título")]


def test_rename_cancelled_does_not_emit(qtbot, monkeypatch):
    item = AnnotationItem(_ann())
    qtbot.addWidget(item)
    got = []
    item.rename_requested.connect(lambda i, t: got.append((i, t)))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("qualquer", False)))
    item._rename_btn.click()
    assert got == []


def test_ai_note_has_friendly_label(qtbot):
    item = AnnotationItem(_ann())
    qtbot.addWidget(item)
    assert "Nota da IA" in item._type_lbl.text()


def test_panel_relays_rename_signal(qtbot, monkeypatch):
    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    panel.set_book_id(1)
    panel.load_annotations([_ann()])
    got = []
    panel.annotation_renamed.connect(lambda i, t: got.append((i, t)))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Renomeada", True)))
    item = panel._list_layout.itemAt(0).widget()
    item._rename_btn.click()
    assert got == [(7, "Renomeada")]
