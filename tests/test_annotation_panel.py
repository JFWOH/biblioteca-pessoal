"""Testes do AnnotationPanel: título da nota e preenchimento de largura."""
from src.gui.widgets.annotation_panel import AnnotationPanel, AnnotationItem


def test_panel_has_title_input_and_no_max_width(qtbot):
    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    assert hasattr(panel, "_title_input")
    # Sem máximo de largura: preenche um dock largo (default ~QWIDGETSIZE_MAX).
    assert panel.maximumWidth() >= 10000


def test_add_note_emits_title_and_clears(qtbot):
    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    panel.set_page(4)
    panel._title_input.setText("Conceito X")
    panel._note_input.setPlainText("explicação")
    got = []
    panel.annotation_added.connect(got.append)
    panel._add_note()
    assert len(got) == 1
    assert got[0]["title"] == "Conceito X"
    assert got[0]["content"] == "explicação"
    assert got[0]["page"] == 4
    assert panel._title_input.text() == ""  # limpa após adicionar


def test_annotation_item_shows_title(qtbot):
    item = AnnotationItem(
        {"annotation_type": "note", "content": "corpo", "title": "Título Y", "page_number": 2}
    )
    qtbot.addWidget(item)
    assert item._title_item_lbl is not None
    assert item._title_item_lbl.text() == "Título Y"


def test_annotation_item_no_title_when_absent(qtbot):
    item = AnnotationItem(
        {"annotation_type": "note", "content": "corpo", "page_number": 2}
    )
    qtbot.addWidget(item)
    assert item._title_item_lbl is None
