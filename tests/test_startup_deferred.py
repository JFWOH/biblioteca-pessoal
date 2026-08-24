"""Testes da rodada E1 — startup adiado (plano de empacotamento jul/2026).

Cobre: RagInitWorker (constrói/sonda fora da GUI thread, caminhos de erro
graciosos), quarentena de livros 'failed' na auto-indexação, setters de
injeção tardia do RAGEngine e a guarda estrutural do __init__ da MainWindow
(nada pesado antes do show — grade/watcher/IA só em _post_show_init).
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QMainWindow

from src.core.database import LibraryDB
from src.gui.auto_index_service import AutoIndexService
# QtWebEngineWidgets (via reader_view) precisa ser importado ANTES de o
# pytest-qt criar o QApplication — por isso o import fica no topo do módulo.
from src.gui.reader_view import ReaderView
from src.gui.main_window import MainWindow, TTS_WARMUP_IDLE_DELAY_MS
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

    def test_warmup_do_tts_sai_do_tick_zero(self):
        """Rodada UX P.3: o start do TTS não pode voltar ao tick do startup."""
        defs = self._main_window_defs()
        assert "singleShot(0, self._tts_init_worker.start)" not in defs["__init__"]
        assert "self._setup_tts_init_timer()" in defs["__init__"]
        # armado só no FIM da carga pós-show, e parado no fechamento
        assert "self._tts_init_timer.start()" in defs["_post_show_init"]
        assert "timer.stop()" in defs["closeEvent"]


_FILHO = """
import os, sys
sys.path.insert(0, sys.argv[1])
import {modulo}
print("torch_carregado=%s" % ("torch" in sys.modules))
sys.stdout.flush()
os._exit(0)
"""


def _torch_veio_junto(modulo: str) -> bool:
    """Importa ``modulo`` num interpretador NOVO e diz se o torch veio junto.

    Só um processo limpo mede isso: o do pytest já teria o torch em
    ``sys.modules`` por causa de outros testes. O filho sai por ``os._exit``
    para que o teardown de Qt não contamine o código de retorno.
    """
    raiz = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", _FILHO.format(modulo=modulo), str(raiz)],
        cwd=str(raiz), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    marcador = "torch_carregado="
    linha = next((ln for ln in proc.stdout.splitlines()
                  if ln.startswith(marcador)), None)
    assert linha is not None, (
        f"o subprocesso não reportou (rc={proc.returncode}).\n"
        f"stdout:\n{proc.stdout[-1500:]}\nstderr:\n{proc.stderr[-1500:]}")
    return linha[len(marcador):].strip() == "True"


@pytest.mark.slow
class TestTorchForaDoStartup:
    """Onda P (rodada UX ago/2026): o torch não pode voltar ao import da janela.

    Medido antes da correção: o import de ``main_window`` custava 2107ms /
    1367 módulos / 513MB de RSS, e a única causa era o ``import torch`` no
    topo de ``hardware_capability_service`` (cadeia main → main_window →
    reader_view → proactive_reader_service). Qualquer import de torch em
    nível de módulo nessa cadeia derruba estes testes.
    """

    def test_hardware_capability_nao_arrasta_torch(self):
        assert _torch_veio_junto("src.core.hardware_capability_service") is False

    def test_cadeia_da_janela_principal_nao_arrasta_torch(self):
        assert _torch_veio_junto("src.gui.main_window") is False


class _FakeTTSWorker:
    """Stand-in do TTSInitWorker: registra os starts e a prioridade pedida."""

    def __init__(self):
        self.starts = []
        self.rodando = False

    def isRunning(self):
        return self.rodando

    def start(self, priority=None):
        self.starts.append(priority)


class _StubWindow(QMainWindow):
    """Janela mínima que reusa APENAS o agendamento do warmup de TTS.

    Instanciar a ``MainWindow`` real num teste abriria banco, leitor e IA de
    verdade; aqui só interessa QUANDO o worker é iniciado, então os dois
    métodos reais são reusados sobre um ``QMainWindow`` vazio.
    """

    _setup_tts_init_timer = MainWindow._setup_tts_init_timer
    _start_tts_init = MainWindow._start_tts_init

    def __init__(self, worker):
        super().__init__()
        self._tts_init_worker = worker
        self._setup_tts_init_timer()


class TestWarmupTTSEmIdle:
    """Onda P (P.3): o warmup do TTS roda em idle REAL, não no fim do startup."""

    def _janela(self, qtbot, worker=None):
        win = _StubWindow(worker or _FakeTTSWorker())
        qtbot.addWidget(win)
        return win

    def test_nao_dispara_no_tick_zero(self, qtbot):
        worker = _FakeTTSWorker()
        win = self._janela(qtbot, worker)
        # Vários ticks do event loop: o antigo singleShot(0) já teria disparado
        # aqui. O timer nem sequer está armado — quem arma é o _post_show_init.
        qtbot.wait(60)
        assert worker.starts == []
        assert not win._tts_init_timer.isActive()

    def test_atraso_de_idle_configurado_e_single_shot(self, qtbot):
        win = self._janela(qtbot)
        assert win._tts_init_timer.isSingleShot()
        assert win._tts_init_timer.interval() == TTS_WARMUP_IDLE_DELAY_MS
        assert 1500 <= TTS_WARMUP_IDLE_DELAY_MS <= 3000

    def test_dispara_apos_o_atraso_em_prioridade_baixa(self, qtbot):
        worker = _FakeTTSWorker()
        win = self._janela(qtbot, worker)
        win._tts_init_timer.setInterval(20)  # mesmo mecanismo, teste rápido
        win._tts_init_timer.start()          # é o que o _post_show_init faz
        assert worker.starts == []           # ainda não: o atraso é real
        qtbot.waitUntil(lambda: bool(worker.starts), timeout=2000)
        assert worker.starts == [QThread.Priority.LowPriority]

    def test_worker_ja_rodando_nao_reinicia(self, qtbot):
        worker = _FakeTTSWorker()
        worker.rodando = True
        win = self._janela(qtbot, worker)
        win._start_tts_init()
        assert worker.starts == []

    def test_destruir_a_janela_antes_do_disparo_nao_inicia_worker(self, qtbot):
        """Fechamento imediato: o timer é filho da janela e morre com ela."""
        worker = _FakeTTSWorker()
        win = _StubWindow(worker)
        win._tts_init_timer.setInterval(20)
        win._tts_init_timer.start()
        win.deleteLater()
        qtbot.wait(200)
        assert worker.starts == []
