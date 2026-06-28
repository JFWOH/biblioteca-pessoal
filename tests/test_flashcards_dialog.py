"""Testes do FlashcardsDialog (lista + fluxo de estudo)."""
from src.core.database import LibraryDB
from src.gui.dialogs.flashcards_dialog import FlashcardsDialog


def _db_with_cards(tmp_path):
    db = LibraryDB(str(tmp_path / "d.db"))
    bid = db.add_book(title="Livro X", file_path="/a.pdf", file_format="pdf")
    db.add_flashcard(front="Q1", back="A1", book_id=bid)
    db.add_flashcard(front="Q2", back="A2", book_id=bid)
    return db, bid


def test_dialog_lists_cards(qtbot, tmp_path):
    db, bid = _db_with_cards(tmp_path)
    dlg = FlashcardsDialog(db, current_book_id=bid)
    qtbot.addWidget(dlg)
    assert dlg._list_layout.count() == 2
    assert dlg._study_btn.isEnabled()  # 2 novos → devidos
    db.close()


def test_dialog_study_flow_updates_due(qtbot, tmp_path):
    db, bid = _db_with_cards(tmp_path)
    dlg = FlashcardsDialog(db, current_book_id=bid)
    qtbot.addWidget(dlg)

    dlg._start_study()
    assert dlg._stack.currentIndex() == 1
    assert dlg._front_lbl.text() in ("Q1", "Q2")
    assert dlg._grade_widget.isHidden()       # notas escondidas até revelar

    dlg._reveal_answer()
    assert not dlg._grade_widget.isHidden()    # notas aparecem
    assert dlg._back_lbl.text() in ("A1", "A2")

    dlg._grade("good")
    # ao menos um card revisado tem due_date preenchido
    due_set = [c for c in db.get_flashcards(bid) if c["due_date"]]
    assert len(due_set) >= 1
    db.close()


def test_dialog_delete_card(qtbot, tmp_path):
    db, bid = _db_with_cards(tmp_path)
    dlg = FlashcardsDialog(db, current_book_id=bid)
    qtbot.addWidget(dlg)
    first = db.get_flashcards(bid)[0]
    dlg._on_delete(first["id"])
    assert db.count_flashcards(bid) == 1
    db.close()
