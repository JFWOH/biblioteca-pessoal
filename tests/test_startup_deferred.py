"""Testes da rodada E1 — startup adiado (plano de empacotamento jul/2026).

Cobre: RagInitWorker (constrói/sonda fora da GUI thread, caminhos de erro
graciosos), quarentena de livros 'failed' na auto-indexação, setters de
injeção tardia do RAGEngine e a guarda estrutural do __init__ da MainWindow
(nada pesado antes do show — grade/watcher/IA só em _post_show_init).
"""

import ast
from pathlib import Path

import pytest

from src.core.database import LibraryDB
from src.gui.auto_index_service import AutoIndexService
# QtWebEngineWidgets (via reader_view) precisa ser importado ANTES de o
# pytest-qt criar o QApplication — por isso o import fica no topo do módulo.
from src.gui.reader_view import ReaderView
from src.gui.workers.rag_init_worker import RagInitWorker


class FakeEngine:
    def __init__(self, available=True, models=None, count=3, probe_error=False):
        self._available = available
        self._models = models if models is not None else [{"name": "gemma4:e4b"}]
        self._count = count
        self._probe_error = probe_error

    def is_ollama_available(self):
        if self._probe_error:
            raise RuntimeError("rede fora")
        return self._available

    def list_local_models(self):
        return self._models

    def get_indexed_count(self):
        return self._count


def _run_worker(qtbot, **kwargs):
    worker = RagInitWorker(
        db_path="x.db", chroma_path="chroma", ollama_url="http://localhost:11434",
        embed_model="bge-m3", llm_model="gemma4:e4b", **kwargs)
    results = []
    worker.ready.connect(lambda *args: results.append(args))
    worker.run()  # síncrono de propósito: exercita a lógica sem thread real
    assert len(results) == 1
    return results[0]


class TestRagInitWorker:
    def test_constroi_engine_e_sonda(self, qtbot, monkeypatch):
        import src.core.rag_engine as rag_mod
        created = {}

        class FakeRAGEngine(FakeEngine):
            def __init__(self, **kw):
                created.update(kw)
                super().__init__(available=True, count=7)

        monkeypatch.setattr(rag_mod, "RAGEngine", FakeRAGEngine)
        engine, available, models, count = _run_worker(qtbot)
        assert isinstance(engine, FakeRAGEngine)
        assert created["db_path"] == "x.db"
        assert available is True
        assert models == [{"name": "gemma4:e4b"}]
        assert count == 7

    def test_falha_na_construcao_emite_none(self, qtbot, monkeypatch):
        import src.core.rag_engine as rag_mod

        class Explode:
            def __init__(self, **kw):
                raise RuntimeError("chroma indisponível")

        monkeypatch.setattr(rag_mod, "RAGEngine", Explode)
        assert _run_worker(qtbot) == (None, False, [], 0)

    def test_engine_existente_pula_construcao(self, qtbot, monkeypatch):
        import src.core.rag_engine as rag_mod

        def nunca(**kw):
            raise AssertionError("não deveria construir engine novo")

        monkeypatch.setattr(rag_mod, "RAGEngine", nunca)
        existing = FakeEngine(available=False, count=11)
        engine, available, models, count = _run_worker(qtbot, engine=existing)
        assert engine is existing
        assert available is False
        assert models == []
        assert count == 11

    def test_sonda_com_erro_vira_indisponivel(self, qtbot):
        engine, available, models, count = _run_worker(
            qtbot, engine=FakeEngine(probe_error=True, count=2))
        assert engine is not None
        assert available is False
        assert models == []
        assert count == 2


@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "library.db")
    yield database
    database.close()


class TestQuarentenaFailed:
    def _service(self, qtbot, db):
        return AutoIndexService(db=db, rag_engine=None, config=None, parent=None)

    def _seed(self, db):
        old = db.add_book(title="Antigo", file_path="/a.pdf", file_format="pdf",
                          date_added="2026-01-01 00:00:00")
        new = db.add_book(title="Novo", file_path="/n.pdf", file_format="pdf",
                          date_added="2026-06-01 00:00:00")
        return old, new

    def test_failed_recente_fica_em_quarentena(self, qtbot, db):
        old, new = self._seed(db)
        service = self._service(qtbot, db)
        # baseline: mais recente primeiro
        assert service._pick_candidate()["id"] == new
        db.set_indexing_status(new, "failed", error_message="boom")
        assert service._pick_candidate()["id"] == old

    def test_failed_antigo_volta_a_ser_candidato(self, qtbot, db):
        old, new = self._seed(db)
        db.set_indexing_status(new, "failed", error_message="boom")
        with db._write_lock:
            db.conn.execute(
                "UPDATE indexing_state SET updated_at = datetime('now', '-25 hours') "
                "WHERE book_id = ?", (new,))
            db.conn.commit()
        service = self._service(qtbot, db)
        assert service._pick_candidate()["id"] == new

    def test_failed_sem_timestamp_segue_elegivel(self, qtbot, db):
        old, new = self._seed(db)
        db.set_indexing_status(new, "failed", error_message="boom")
        with db._write_lock:
            db.conn.execute(
                "UPDATE indexing_state SET updated_at = NULL WHERE book_id = ?",
                (new,))
            db.conn.commit()
        service = self._service(qtbot, db)
        assert service._pick_candidate()["id"] == new

    def test_attempted_da_sessao_continua_respeitado(self, qtbot, db):
        old, new = self._seed(db)
        service = self._service(qtbot, db)
        service._attempted.add(new)
        assert service._pick_candidate()["id"] == old

    def test_get_unindexed_books_expoe_updated_at(self, db):
        _old, new = self._seed(db)
        db.set_indexing_status(new, "failed", error_message="boom")
        rows = {b["id"]: b for b in db.get_unindexed_books()}
        assert "indexing_updated_at" in rows[new]
        assert rows[new]["indexing_updated_at"]  # timestamp preenchido


class TestInjecaoTardiaDoEngine:
    def test_auto_index_setter(self, qtbot, db):
        service = AutoIndexService(db=db, rag_engine=None)
        fake = object()
        service.set_rag_engine(fake)
        assert service._rag_engine is fake

    def test_graph_service_setter(self, qtbot, db):
        from src.gui.graph_ingest_service import GraphIngestService
        service = GraphIngestService(db=db, rag_engine=None)
        fake = object()
        service.set_rag_engine(fake)
        assert service._rag_engine is fake

    def test_reader_view_setter_religa_cross_reference(self, qtbot):
        view = ReaderView(parent=None, tts_router=None, rag_engine=None, db=None)
        qtbot.addWidget(view)
        registered = []
        view._proactive_service.set_cross_reference = registered.append
        fake = object()
        view.set_rag_engine(fake)
        assert view._rag_engine is fake
        assert registered == [view._proactive_cross_ref]

    def test_reader_view_setter_none_nao_religa(self, qtbot):
        view = ReaderView(parent=None, tts_router=None, rag_engine=None, db=None)
        qtbot.addWidget(view)
        registered = []
        view._proactive_service.set_cross_reference = registered.append
        view.set_rag_engine(None)
        assert registered == []


class TestGuardaEstruturalStartup:
    """__init__ da MainWindow não pode voltar a fazer trabalho pesado pré-show."""

    def _main_window_defs(self):
        src = (Path(__file__).resolve().parent.parent
               / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        defs = {n.name: ast.get_source_segment(src, n)
                for n in cls.body if isinstance(n, ast.FunctionDef)}
        return defs

    def test_init_delega_para_post_show(self):
        defs = self._main_window_defs()
        init = defs["__init__"]
        for banned in ("self._load_library(", "self._setup_watcher(",
                       "self._check_ollama_status(", "self._setup_rag_engine(",
                       "RAGEngine("):
            assert banned not in init, f"__init__ voltou a chamar {banned} pré-show"
        assert "_post_show_init" in init

    def test_post_show_cobre_grade_watcher_e_ia(self):
        defs = self._main_window_defs()
        post = defs["_post_show_init"]
        for required in ("self._load_library()", "self._setup_watcher()",
                         "self._check_ollama_status()"):
            assert required in post

    def test_check_ollama_nao_bloqueia_gui(self):
        defs = self._main_window_defs()
        check = defs["_check_ollama_status"]
        # a sonda bloqueante vive no worker; o método da GUI só o dispara
        assert "is_ollama_available()" not in check
        assert "RagInitWorker" in check
