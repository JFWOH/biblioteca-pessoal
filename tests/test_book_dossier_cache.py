"""Cache da síntese do dossiê (Sprint A3, revisão de engenharia 2026-07-05
§1.5): a síntese LLM só precisa mudar quando o grafo ingere algo novo do
livro, não a cada abertura do diálogo.
"""
import pytest

from src.core.book_dossier import get_cached_synthesis, save_synthesis_cache
from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore
from src.gui.dialogs.book_dossier_dialog import BookDossierDialog
from src.gui.workers.dossier_synthesis_worker import DossierSynthesisWorker


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def store(db):
    return GraphStore(db)


@pytest.fixture(autouse=True)
def no_worker_start(monkeypatch):
    """Nunca inicia a QThread real (rede) — só observa SE ela seria iniciada."""
    started = []
    monkeypatch.setattr(DossierSynthesisWorker, "start", lambda self: started.append(self))
    return started


def _book(db, title="Livro", path="/tmp/x.pdf", pages=4) -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf", page_count=pages)


def _seed_graph(db, store, bid, other):
    shared = [("entropia", "Entropia", 0.9), ("calor", "Calor", 0.4)]
    store.add_mentions(bid, "page:1", shared, page=1)
    store.add_mentions(other, "page:1", shared, page=1)
    store.recompute_book_edges(bid)


# ── core: get_cached_synthesis / save_synthesis_cache ──────────────────

def test_no_cache_returns_none(db, store):
    bid = _book(db)
    assert get_cached_synthesis(db, store, bid) is None


def test_save_then_get_returns_cached_text(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", [("x", "X", 0.5)], page=1)
    save_synthesis_cache(db, store, bid, "Texto da síntese.")
    assert get_cached_synthesis(db, store, bid) == "Texto da síntese."


def test_cache_invalidated_when_more_pages_ingested(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", [("x", "X", 0.5)], page=1)
    save_synthesis_cache(db, store, bid, "Síntese antiga.")
    assert get_cached_synthesis(db, store, bid) == "Síntese antiga."

    # Grafo ingere mais uma página → fingerprint muda → cache invalida.
    store.add_mentions(bid, "page:2", [("y", "Y", 0.5)], page=2)
    assert get_cached_synthesis(db, store, bid) is None


def test_ingest_fingerprint_stable_without_new_ingestion(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", [("x", "X", 0.5)], page=1)
    assert store.ingest_fingerprint(bid) == store.ingest_fingerprint(bid)


# ── wiring: BookDossierDialog usa o cache antes de iniciar o worker ─────

def test_dialog_uses_cache_and_skips_worker(qtbot, db, store, no_worker_start):
    bid = _book(db, title="A", path="/tmp/a.pdf")
    other = _book(db, title="B", path="/tmp/b.pdf")
    _seed_graph(db, store, bid, other)
    save_synthesis_cache(db, store, bid, "Síntese pronta em cache.")

    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)

    assert dialog._synthesis_label.text() == "Síntese pronta em cache."
    assert no_worker_start == []


def test_dialog_starts_worker_on_cache_miss(qtbot, db, store, no_worker_start):
    bid = _book(db, title="A", path="/tmp/a.pdf")
    other = _book(db, title="B", path="/tmp/b.pdf")
    _seed_graph(db, store, bid, other)

    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)

    assert dialog._synthesis_label.text() == "Gerando síntese…"
    assert len(no_worker_start) == 1


def test_on_synthesis_ready_saves_cache(qtbot, db, store):
    bid = _book(db, title="A", path="/tmp/a.pdf")
    other = _book(db, title="B", path="/tmp/b.pdf")
    _seed_graph(db, store, bid, other)

    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)
    dialog._on_synthesis_ready("Nova síntese gerada.")

    assert get_cached_synthesis(db, GraphStore(db), bid) == "Nova síntese gerada."
