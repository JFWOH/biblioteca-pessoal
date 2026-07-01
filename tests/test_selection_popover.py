"""Testes do SelectionActionPopover (barra de ações de seleção)."""
from src.gui.widgets.selection_popover import SelectionActionPopover


def test_popover_has_all_actions(qtbot):
    pop = SelectionActionPopover()
    qtbot.addWidget(pop)
    assert set(pop._buttons.keys()) == {
        "highlight", "explain", "translate", "search", "save_note", "flashcard"
    }


def test_popover_emits_action_key(qtbot):
    pop = SelectionActionPopover()
    qtbot.addWidget(pop)
    received = []
    pop.action_requested.connect(received.append)
    pop._buttons["highlight"].click()
    assert received == ["highlight"]


def test_popover_hides_after_action(qtbot):
    pop = SelectionActionPopover()
    qtbot.addWidget(pop)
    pop.show()
    pop._buttons["explain"].click()
    assert not pop.isVisible()


def test_popover_set_actions_filters_buttons(qtbot):
    pop = SelectionActionPopover()
    qtbot.addWidget(pop)
    pop.set_actions(["explain", "translate"])
    assert pop._buttons["explain"].isVisibleTo(pop)
    assert pop._buttons["translate"].isVisibleTo(pop)
    assert not pop._buttons["highlight"].isVisibleTo(pop)
