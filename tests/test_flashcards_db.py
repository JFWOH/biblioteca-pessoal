"""Testes do armazenamento de flashcards no SQLite."""
from datetime import date

from src.core.database import LibraryDB


def test_add_and_get_flashcards(tmp_path):
    db = LibraryDB(str(tmp_path / "fc.db"))
    bid = db.add_book(title="L", file_path="/a.pdf", file_format="pdf")
    db.add_flashcard(front="Q1", back="A1", book_id=bid, deck="D")
    db.add_flashcard(front="Q2", back="A2")  # sem livro
    cards = db.get_flashcards()
    assert {c["front"] for c in cards} == {"Q1", "Q2"}
    assert db.count_flashcards() == 2
    assert db.count_flashcards(book_id=bid) == 1
    db.close()


def test_get_flashcards_by_book(tmp_path):
    db = LibraryDB(str(tmp_path / "fc2.db"))
    bid = db.add_book(title="L", file_path="/a.pdf", file_format="pdf")
    db.add_flashcard(front="Q1", book_id=bid)
    db.add_flashcard(front="Q2")
    assert len(db.get_flashcards(book_id=bid)) == 1
    db.close()


def test_due_includes_new_and_past_not_future(tmp_path):
    db = LibraryDB(str(tmp_path / "fc3.db"))
    db.add_flashcard(front="novo")                       # due vazio → devido
    db.add_flashcard(front="vencido", due_date="2020-01-01")
    db.add_flashcard(front="futuro", due_date="2999-01-01")
    due = db.get_due_flashcards(date.today().isoformat())
    fronts = {c["front"] for c in due}
    assert "novo" in fronts and "vencido" in fronts
    assert "futuro" not in fronts
    db.close()


def test_update_review_persists(tmp_path):
    db = LibraryDB(str(tmp_path / "fc4.db"))
    fid = db.add_flashcard(front="Q")
    db.update_flashcard_review(fid, due_date="2030-05-05", interval_days=6,
                               ease=2.6, reps=2, lapses=0)
    fc = db.get_flashcards()[0]
    assert fc["due_date"] == "2030-05-05"
    assert fc["interval_days"] == 6
    assert fc["reps"] == 2
    db.close()


def test_delete_flashcard(tmp_path):
    db = LibraryDB(str(tmp_path / "fc5.db"))
    fid = db.add_flashcard(front="Q")
    assert db.count_flashcards() == 1
    db.delete_flashcard(fid)
    assert db.count_flashcards() == 0
    db.close()
