"""Testes da coluna 'title' (nome) em anotações."""
from src.core.database import LibraryDB


def test_annotation_title_persists(tmp_path):
    db = LibraryDB(str(tmp_path / "lib.db"))
    book_id = db.add_book(title="L", file_path="/x.pdf", file_format="pdf")
    db.add_annotation(book_id=book_id, page_number=0, content="corpo",
                      annotation_type="note", title="Meu Título")
    anns = db.get_annotations(book_id)
    assert len(anns) == 1
    assert anns[0]["title"] == "Meu Título"
    assert anns[0]["content"] == "corpo"
    db.close()


def test_annotation_title_defaults_empty(tmp_path):
    db = LibraryDB(str(tmp_path / "lib2.db"))
    book_id = db.add_book(title="L", file_path="/y.pdf", file_format="pdf")
    db.add_annotation(book_id=book_id, page_number=0, content="só corpo")
    anns = db.get_annotations(book_id)
    assert anns[0]["title"] == ""
    db.close()
