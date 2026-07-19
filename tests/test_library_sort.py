"""Tarefa 2.3 — controle de ordenação no header da biblioteca.

Três frentes:
1. ``LibraryDB.get_all_books`` — whitelist de ``sort_by``/``sort_order``
   (interpolados via f-string na SQL): valores fora da whitelist caem no
   padrão em vez de propagar texto arbitrário.
2. ``LibraryView`` — combo + botão asc/desc emitem ``sort_changed`` com os
   valores certos; ``set_sort_state`` sincroniza sem emitir (evita reload
   duplicado).
3. Compatibilidade retroativa: chamadas existentes (ex.: opds_server, com
   sort_order="ASC" maiúsculo) continuam funcionando.
"""
import pytest

from src.core.database import LibraryDB
from src.gui.library_view import LibraryView


# ── DB: whitelist de sort_by/sort_order ─────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "lib.db")
    yield database
    database.close()


def _add_book(db, title, author):
    return db.add_book(title=title, author=author, file_path=f"/tmp/{title}.pdf",
                       file_format="pdf")


def test_sort_by_valid_column(db):
    _add_book(db, "Zebra", "Autor Z")
    _add_book(db, "Alfa", "Autor A")

    titles = [b["title"] for b in db.get_all_books(sort_by="title", sort_order="asc")]
    assert titles == ["Alfa", "Zebra"]


def test_sort_by_invalid_column_falls_back_to_default(db):
    """Coluna fora da whitelist (ex.: injeção via SQL) nunca chega na SQL —
    cai no padrão (date_added) em vez de levantar erro ou expor a superfície."""
    _add_book(db, "Zebra", "Autor Z")
    _add_book(db, "Alfa", "Autor A")

    # Não deve lançar sqlite3.OperationalError nem interpolar o texto malicioso.
    books = db.get_all_books(sort_by="title; DROP TABLE books;--", sort_order="asc")
    assert len(books) == 2


def test_sort_order_invalid_falls_back_to_desc(db):
    b1 = _add_book(db, "Um", "A")
    b2 = _add_book(db, "Dois", "B")
    # date_added tem resolução de segundo — força valores distintos para a
    # ordenação não depender de empate de timestamp.
    db.update_book(b1, date_added="2020-01-01 00:00:00")
    db.update_book(b2, date_added="2020-01-02 00:00:00")
    books = db.get_all_books(sort_by="date_added", sort_order="alfabetica; DROP TABLE books;--")
    # DESC (padrão) = mais recente primeiro = b2 antes de b1
    assert [b["id"] for b in books] == [b2, b1]


def test_sort_order_case_insensitive_backward_compat(db):
    """opds_server.py chama com sort_order="ASC" (maiúsculo) — precisa continuar
    funcionando após a normalização."""
    _add_book(db, "Zebra", "Autor Z")
    _add_book(db, "Alfa", "Autor A")
    titles = [b["title"] for b in db.get_all_books(sort_by="title", sort_order="ASC")]
    assert titles == ["Alfa", "Zebra"]


def test_sort_defaults_unchanged(db):
    """Chamada sem argumentos preserva o comportamento anterior (date_added DESC)."""
    b1 = _add_book(db, "Primeiro", "A")
    b2 = _add_book(db, "Segundo", "B")
    db.update_book(b1, date_added="2020-01-01 00:00:00")
    db.update_book(b2, date_added="2020-01-02 00:00:00")
    assert [b["id"] for b in db.get_all_books()] == [b2, b1]


# ── DB: débito — sort aplicado nas visões filtradas (favoritos/status/coleção) ──

def test_get_favorite_books_respects_sort_by(db):
    _add_book(db, "Zebra", "Autor Z")
    _add_book(db, "Alfa", "Autor A")
    db.update_book(1, is_favorite=1)
    db.update_book(2, is_favorite=1)

    titles = [b["title"] for b in db.get_favorite_books(sort_by="title", sort_order="asc")]
    assert titles == ["Alfa", "Zebra"]


def test_get_favorite_books_default_unchanged(db):
    """Sem sort_by, preserva o comportamento anterior (ORDER BY title)."""
    _add_book(db, "Zebra", "Autor Z")
    _add_book(db, "Alfa", "Autor A")
    db.update_book(1, is_favorite=1)
    db.update_book(2, is_favorite=1)

    titles = [b["title"] for b in db.get_favorite_books()]
    assert titles == ["Alfa", "Zebra"]


def test_get_favorite_books_invalid_sort_falls_back(db):
    _add_book(db, "Zebra", "Autor Z")
    db.update_book(1, is_favorite=1)
    # Não deve lançar nem interpolar texto malicioso — cai no padrão (title).
    books = db.get_favorite_books(sort_by="x; DROP TABLE books;--", sort_order="asc")
    assert len(books) == 1


def test_get_books_by_status_respects_sort(db):
    _add_book(db, "Zebra", "Autor Z")
    _add_book(db, "Alfa", "Autor A")
    db.update_book(1, read_status="reading")
    db.update_book(2, read_status="reading")

    titles = [b["title"] for b in
              db.get_books_by_status("reading", sort_by="title", sort_order="asc")]
    assert titles == ["Alfa", "Zebra"]


def test_get_books_by_status_default_unchanged(db):
    """Sem sort_by, preserva o comportamento anterior (ORDER BY date_modified DESC).

    ``update_book`` sempre grava ``date_modified=datetime.now()`` (não aceita
    override via kwarg — o valor é sobrescrito), então a ordem é controlada
    pela SEQUÊNCIA das chamadas: a atualizada por último fica mais recente.
    """
    import time
    b1 = _add_book(db, "Um", "A")
    b2 = _add_book(db, "Dois", "B")
    db.update_book(b1, read_status="reading")
    time.sleep(0.01)  # garante date_modified distinto (resolução do relógio)
    db.update_book(b2, read_status="reading")
    assert [b["id"] for b in db.get_books_by_status("reading")] == [b2, b1]


def test_get_books_in_collection_respects_sort(db):
    col_id = db.create_collection("Coleção")
    b1 = _add_book(db, "Zebra", "Autor Z")
    b2 = _add_book(db, "Alfa", "Autor A")
    db.add_book_to_collection(b1, col_id)
    db.add_book_to_collection(b2, col_id)

    titles = [b["title"] for b in
              db.get_books_in_collection(col_id, sort_by="title", sort_order="asc")]
    assert titles == ["Alfa", "Zebra"]


def test_get_books_in_collection_default_unchanged(db):
    """Sem sort_by, preserva o comportamento anterior (ORDER BY b.title)."""
    col_id = db.create_collection("Coleção")
    b1 = _add_book(db, "Zebra", "Autor Z")
    b2 = _add_book(db, "Alfa", "Autor A")
    db.add_book_to_collection(b1, col_id)
    db.add_book_to_collection(b2, col_id)

    titles = [b["title"] for b in db.get_books_in_collection(col_id)]
    assert titles == ["Alfa", "Zebra"]


# ── Widget: LibraryView ──────────────────────────────────────────────────────

@pytest.fixture
def view(qtbot):
    v = LibraryView()
    qtbot.addWidget(v)
    return v


def test_sort_combo_has_same_options_as_settings_dialog(view):
    values = [view._sort_combo.itemData(i) for i in range(view._sort_combo.count())]
    assert values == ["date_added", "title", "author", "rating"]


def test_changing_combo_emits_sort_changed(view, qtbot):
    with qtbot.waitSignal(view.sort_changed, timeout=1000) as blocker:
        idx = view._sort_combo.findData("title")
        view._sort_combo.setCurrentIndex(idx)
    assert blocker.args == ["title", "desc"]


def test_toggling_order_button_emits_sort_changed(view, qtbot):
    with qtbot.waitSignal(view.sort_changed, timeout=1000) as blocker:
        view._sort_order_btn.setChecked(True)
    assert blocker.args[1] == "asc"
    assert view._sort_order_btn.text() == "↑"


def test_set_sort_state_does_not_emit_signal(view, qtbot):
    received = []
    view.sort_changed.connect(received.append)

    view.set_sort_state("author", "asc")

    assert received == []
    assert view._sort_combo.currentData() == "author"
    assert view._sort_order_btn.isChecked() is True
    assert view._sort_order_btn.text() == "↑"


def test_set_sort_state_unknown_column_keeps_previous_selection(view):
    view.set_sort_state("author", "desc")
    view.set_sort_state("coluna_inexistente", "asc")
    # findData retorna -1 para valor desconhecido: o combo permanece no
    # último valor válido (author) — não quebra nem seleciona algo aleatório.
    assert view._sort_combo.currentData() == "author"
