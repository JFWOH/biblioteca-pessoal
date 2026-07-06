"""Testes do GraphIngestService: gates, fila com prioridade, dirty→edges, idle."""
import time

import pytest
from unittest.mock import patch

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore
from src.gui.graph_ingest_service import GraphIngestService


class FakeConfig:
    def __init__(self, overrides=None):
        self._data = overrides or {}

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db, indexed=True) -> int:
    bid = db.add_book(title="Livro", file_path="/tmp/x.pdf", file_format="pdf",
                      page_count=10)
    if indexed:
        db.set_indexing_status(bid, "indexed_ok")
    return bid


def _svc(db, config=None) -> GraphIngestService:
    return GraphIngestService(db=db, rag_engine=None, config=config)


def test_disabled_by_config_does_nothing(qtbot, db):
    bid = _book(db)
    svc = _svc(db, FakeConfig({"graph.enabled": False}))
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        svc.on_page_context(bid, "T", 1, "texto da página")
        MockWorker.assert_not_called()
    svc.shutdown()


def test_page_requires_indexed_book(qtbot, db):
    bid = _book(db, indexed=False)
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        svc.on_page_context(bid, "T", 1, "texto da página")
        MockWorker.assert_not_called()
    svc.shutdown()


def test_page_already_ingested_skips(qtbot, db):
    bid = _book(db)
    GraphStore(db).mark_ingested(bid, "page:1")
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        svc.on_page_context(bid, "T", 1, "texto")
        MockWorker.assert_not_called()
    svc.shutdown()


def test_page_task_created_and_sweep_enqueued(qtbot, db):
    bid = _book(db)
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc.on_page_context(bid, "T", 3, "texto da página três")
        assert MockWorker.call_count == 1
        task = MockWorker.call_args[0][0]
        assert task["kind"] == "page" and task["page"] == 3
        assert task["fallback_text"] == "texto da página três"
        # A varredura de anotações do livro ficou na fila (1x por sessão)
        assert [t["kind"] for t in svc._queue] == ["annotations_sweep"]
    svc.shutdown()


def test_skip_if_busy_enqueues_next_page(qtbot, db):
    bid = _book(db)
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc.on_page_context(bid, "T", 1, "um")
        svc.on_page_context(bid, "T", 2, "dois")
        assert MockWorker.call_count == 1  # worker ocupado → só enfileira
        kinds = [(t["kind"], t.get("page")) for t in svc._queue]
        assert ("page", 2) in kinds
    svc.shutdown()


def test_page_dedupe_and_cap(qtbot, db):
    bid = _book(db)
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        for page in (1, 2, 2, 3, 4, 5):
            svc.on_page_context(bid, "T", page, f"pg {page}")
        pages = [t["page"] for t in svc._queue if t["kind"] == "page"]
        assert len(pages) == len(set(pages))  # sem duplicatas
        assert len(pages) <= 3                # teto de page-tasks pendentes
        assert pages[-1] == 5                 # as mais novas sobrevivem
    svc.shutdown()


def test_annotation_task(qtbot, db):
    bid = _book(db)
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc.on_annotation_saved(bid, 42, 7, "Nota sobre entropia")
        task = MockWorker.call_args[0][0]
        assert task["kind"] == "annotation" and task["annotation_id"] == 42
        assert task["page"] == 7 and "entropia" in task["text"]
    svc.shutdown()


def test_full_cycle_dirty_then_edges_then_signal(qtbot, db):
    """página → sweep → edges → graph_updated (drenagem da fila)."""
    bid = _book(db)
    svc = _svc(db)
    updates = []
    svc.graph_updated.connect(updates.append)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        svc.on_page_context(bid, "T", 1, "texto")
        assert MockWorker.call_args_list[0][0][0]["kind"] == "page"

        svc._on_worker_finished({"kind": "page", "book_id": bid, "page": 1,
                                 "mentions": 3})
        assert MockWorker.call_args_list[1][0][0]["kind"] == "annotations_sweep"

        svc._on_worker_finished({"kind": "annotations_sweep", "book_id": bid,
                                 "annotations": 0})
        # fila vazia + dirty → task de edges
        edges_task = MockWorker.call_args_list[2][0][0]
        assert edges_task["kind"] == "edges" and edges_task["book_ids"] == [bid]

        svc._on_worker_finished({"kind": "edges", "book_ids": [bid], "edges": 1})
        assert updates == [bid]
    svc.shutdown()


def test_idle_tick_requires_inactivity(qtbot, db):
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        svc._on_idle_tick()  # atividade recente (construção) → nada
        MockWorker.assert_not_called()
        svc._last_activity = time.monotonic() - 9999
        svc._on_idle_tick()
        assert MockWorker.call_count == 1
        assert MockWorker.call_args[0][0]["kind"] == "idle_batch"
    svc.shutdown()


def test_idle_exhausted_stops_ticking(qtbot, db):
    svc = _svc(db)
    svc._last_activity = time.monotonic() - 9999
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        svc._on_idle_tick()
        svc._on_worker_finished({"kind": "idle_batch", "book_id": None,
                                 "pages": 0, "annotations": 0, "exhausted": True})
        calls_before = MockWorker.call_count
        svc._on_idle_tick()  # exausto → não agenda de novo
        assert MockWorker.call_count == calls_before
    svc.shutdown()


def test_worker_error_does_not_stop_queue(qtbot, db):
    bid = _book(db)
    svc = _svc(db)
    with patch("src.gui.graph_ingest_service.GraphWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        svc.on_page_context(bid, "T", 1, "um")
        svc.on_annotation_saved(bid, 7, 1, "nota")
        svc._on_worker_error("falha qualquer")  # worker 1 morreu
        # A fila continuou: annotation (prioridade sobre sweep) foi despachada
        kinds = [c[0][0]["kind"] for c in MockWorker.call_args_list]
        assert kinds[0] == "page" and "annotation" in kinds
    svc.shutdown()
