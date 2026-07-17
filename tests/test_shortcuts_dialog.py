"""Testes do ShortcutsDialog (Onda 4, item 4.3).

Diálogo somente-leitura — cobre a contagem mínima de atalhos publicados
(>= 14), o agrupamento por categoria e a presença do F1 (o próprio atalho
que abre este diálogo).
"""
from src.gui.dialogs.shortcuts_dialog import (
    ShortcutsDialog, _CATEGORIES, _GENERAL_SHORTCUTS,
)


def test_at_least_14_shortcuts_published():
    total = sum(len(items) for _name, items in _CATEGORIES)
    assert total >= 14


def test_categories_are_leitor_biblioteca_geral():
    names = [name for name, _items in _CATEGORIES]
    assert names == ["Leitor", "Biblioteca", "Geral"]


def test_f1_opens_this_dialog_is_listed():
    keys = [key for key, _desc in _GENERAL_SHORTCUTS]
    assert "F1" in keys


def test_dialog_renders_a_group_per_category(qtbot):
    dialog = ShortcutsDialog()
    qtbot.addWidget(dialog)

    from PyQt6.QtWidgets import QGroupBox
    groups = dialog.findChildren(QGroupBox)
    assert len(groups) == len(_CATEGORIES)
    titles = {g.title() for g in groups}
    assert titles == {name for name, _items in _CATEGORIES}


def test_dialog_is_resizable_not_fixed(qtbot):
    dialog = ShortcutsDialog()
    qtbot.addWidget(dialog)
    # setFixedSize trava minimumSize == maximumSize; aqui deve haver folga.
    assert dialog.maximumSize().width() > dialog.minimumSize().width() or \
        dialog.maximumSize().height() > dialog.minimumSize().height()
