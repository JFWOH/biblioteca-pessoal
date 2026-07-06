import pytest
from src.gui.widgets.book_card import BookCard

@pytest.fixture
def app(qtbot):
    # qtbot fixture comes from pytest-qt
    return qtbot

def test_book_card_init_normal(qtbot):
    data = {"id": 1, "title": "Normal Book", "file_path": __file__}  # Usa o próprio teste como arquivo existente
    card = BookCard(data)
    qtbot.addWidget(card)
    
    assert card.is_broken is False
    assert card.is_selected is False
    assert card.book_data == data

def test_book_card_init_broken(qtbot):
    data = {"id": 2, "title": "Ghost Book", "file_path": "/caminho/falso/que/nao/existe.epub"}
    card = BookCard(data)
    qtbot.addWidget(card)
    
    assert card.is_broken is True
    # toolTip is set
    assert "⚠️" in card.toolTip()

def test_book_card_selection(qtbot):
    data = {"id": 1, "title": "Normal Book", "file_path": __file__}
    card = BookCard(data)
    qtbot.addWidget(card)
    
    with qtbot.waitSignal(card.selected_changed, timeout=1000) as blocker:
        card.set_selected(True)
    
    assert blocker.args == [1, True]
    assert card.is_selected is True
    
    card.set_selected(False)
    assert card.is_selected is False
