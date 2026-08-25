"""Onda S da rodada UX (ago/2026) — tarefa em segundo plano não abre diálogo.

Quem está lendo não pode ser interrompido por um modal disparado por um worker:
a informação vai para a barra de status e para o painel correspondente. Cobre
os três pontos auditados em ``src/gui/main_window.py``:

  1. ``_handle_rag_error``    — reindexação que falha (inclusive falha de GPU);
  2. ``_on_rag_status_ready`` — assistente do Ollama só na 1ª execução;
  3. ``_on_anki_error``       — envio do flashcard ao Anki que falha.

As janelas destes testes reusam APENAS os métodos em teste sobre um
``QMainWindow`` vazio — mesmo padrão de ``test_startup_deferred._StubWindow``:
instanciar a ``MainWindow`` real abriria banco, leitor e IA de verdade.
"""

import re
from pathlib import Path

import pytest

from PyQt6.QtWidgets import QDialog, QMainWindow, QMessageBox, QPushButton, QStatusBar

from src.core.config import ConfigManager
# QtWebEngineWidgets (via reader_view) precisa ser importado ANTES de o
# pytest-qt criar o QApplication — mesmo motivo de test_startup_deferred.py.
from src.gui.reader_view import ReaderView  # noqa: F401
from src.gui.main_window import (
    ANKI_ERROR_STATUS_MS,
    GPU_ERROR_STATUS_MS,
    OLLAMA_ABSENT_STATUS_MS,
    ONBOARDING_WIZARD_KEY,
    MainWindow,
    gpu_failure_message,
)

_MAIN_WINDOW_SRC = (
    Path(__file__).resolve().parent.parent / "src" / "gui" / "main_window.py"
).read_text(encoding="utf-8")


# ── Dublês ──────────────────────────────────────────────────────────────────

class _RecordingStatusBar(QStatusBar):
    """QStatusBar REAL (para addPermanentWidget) que grava (texto, timeout)."""

    def __init__(self):
        super().__init__()
        self.messages = []

    def showMessage(self, text, timeout=0):  # noqa: N802 (API do Qt)
        self.messages.append((text, timeout))
        super().showMessage(text, timeout)

    @property
    def last(self):
        return self.messages[-1] if self.messages else (None, None)


class _FakePanel:
    def __init__(self):
        self.errors = []
        self.model_lists = []
        self.status = []
        self.indexed = None

    def on_error(self, msg):
        self.errors.append(msg)

    def update_model_list(self, names):
        self.model_lists.append(names)

    def set_ollama_status(self, available, model=""):
        self.status.append((available, model))

    def set_indexed_count(self, n):
        self.indexed = n


class _FakeEngine:
    def __init__(self, available=False, models=None):
        self._available = available
        self._models = models if models is not None else []
        self.probes = 0

    def is_ollama_available(self):
        self.probes += 1
        return self._available

    def list_local_models(self):
        return self._models


def _fake_wizard(monkeypatch, result=QDialog.DialogCode.Rejected):
    """Substitui o OllamaWizardDialog e devolve a lista de instâncias criadas."""
    criados = []

    class _FakeWizardDialog:
        def __init__(self, parent=None):
            criados.append(parent)

        def exec(self):
            return result

    monkeypatch.setattr(
        "src.gui.dialogs.ollama_wizard.OllamaWizardDialog", _FakeWizardDialog)
    return criados


class _StubWindow(QMainWindow):
    """Reusa só os métodos sob teste; o resto é dublê."""

    _handle_rag_error = MainWindow._handle_rag_error
    _on_anki_error = MainWindow._on_anki_error
    _on_rag_status_ready = MainWindow._on_rag_status_ready
    _run_ollama_wizard = MainWindow._run_ollama_wizard
    _show_ollama_wizard_button = MainWindow._show_ollama_wizard_button
    _hide_ollama_wizard_button = MainWindow._hide_ollama_wizard_button
    _open_ollama_wizard = MainWindow._open_ollama_wizard

    def __init__(self, config, engine=None):
        super().__init__()
        self._statusbar = _RecordingStatusBar()
        self.setStatusBar(self._statusbar)
        self._ollama_wizard_btn = None
        self._rag_panel = _FakePanel()
        self._config = config
        # Já preenchido: pula o bloco de injeção tardia do engine, que não é
        # o objeto deste teste.
        self._rag_engine = engine
        self.model_pulls = 0

    def _start_model_pull(self):
        self.model_pulls += 1


@pytest.fixture
def config(tmp_path):
    """ConfigManager REAL: exercita a chave com ponto e a persistência."""
    return ConfigManager(tmp_path / "config.json")


@pytest.fixture
def janela(qtbot, config):
    def _make(engine=None, cfg=None):
        win = _StubWindow(cfg or config, engine=engine)
        qtbot.addWidget(win)
        return win
    return _make


@pytest.fixture
def sem_dialogos(monkeypatch):
    """Conta QUALQUER modal do QMessageBox aberto durante o teste."""
    chamadas = []
    for nome in ("critical", "warning", "information", "question", "about"):
        monkeypatch.setattr(
            QMessageBox, nome,
            staticmethod(lambda *a, _n=nome, **k: chamadas.append(_n)))
    return chamadas


# ── 1. _handle_rag_error ────────────────────────────────────────────────────

class TestErroRagSemDialogo:
    """A reindexação roda sem o usuário ter pedido nada naquele instante."""

    def test_nao_abre_dialogo_e_alimenta_statusbar_e_painel(
            self, janela, sem_dialogos):
        win = janela()
        win._handle_rag_error("chroma explodiu")

        assert sem_dialogos == [], "worker de background não pode abrir modal"
        assert win._rag_panel.errors == ["chroma explodiu"]
        texto, timeout = win._statusbar.last
        assert "chroma explodiu" in texto
        assert timeout == 5000

    def test_gpu_error_usa_mensagem_orientativa_e_duracao_longa(
            self, janela, sem_dialogos):
        from src.core.rag_engine import GPU_FAILURE_MESSAGE, OllamaGPUError

        win = janela()
        win._handle_rag_error(OllamaGPUError(GPU_FAILURE_MESSAGE))

        assert sem_dialogos == []
        texto, timeout = win._statusbar.last
        assert GPU_FAILURE_MESSAGE in texto
        # A instrução ("atualize o driver / OLLAMA_NUM_GPU=0") precisa ser lida
        # inteira antes de o usuário agir.
        assert timeout == GPU_ERROR_STATUS_MS
        assert timeout >= 15000
        assert win._rag_panel.errors  # painel também recebe

    def test_gpu_reconhecido_pela_string_que_o_sinal_entrega(self, janela):
        """``error_occurred`` é ``pyqtSignal(str)``: o tipo morre na thread."""
        from src.core.rag_engine import GPU_FAILURE_MESSAGE

        win = janela()
        win._handle_rag_error(f"Erro ao indexar o livro 3: {GPU_FAILURE_MESSAGE}")

        texto, timeout = win._statusbar.last
        assert GPU_FAILURE_MESSAGE in texto
        assert timeout == GPU_ERROR_STATUS_MS

    def test_erro_comum_nao_vira_falso_positivo_de_gpu(self, janela):
        win = janela()
        win._handle_rag_error("arquivo não encontrado")
        assert win._statusbar.last[1] == 5000

    def test_helper_reconhece_as_duas_formas(self):
        from src.core.rag_engine import GPU_FAILURE_MESSAGE, OllamaGPUError

        assert gpu_failure_message(OllamaGPUError("qualquer")) == GPU_FAILURE_MESSAGE
        assert gpu_failure_message(GPU_FAILURE_MESSAGE) == GPU_FAILURE_MESSAGE
        assert gpu_failure_message("timeout comum") == ""
        assert gpu_failure_message(RuntimeError("boom")) == ""


class TestFiacaoDoErroRag:
    """Guardas estruturais: o caminho até _handle_rag_error não pode regredir."""

    def test_sem_qmessagebox_no_corpo_do_handler(self):
        corpo = re.search(
            r"def _handle_rag_error\(self, err\) -> None:(.*?)\n    def ",
            _MAIN_WINDOW_SRC, re.DOTALL).group(1)
        # A docstring cita o modal REMOVIDO; o que não pode voltar é a chamada.
        assert "QMessageBox.critical(" not in corpo
        assert "self._statusbar.showMessage(" in corpo
        assert "self._rag_panel.on_error(" in corpo

    def test_index_all_repassa_a_excecao_crua(self):
        """Passar ``str(e)`` perderia o tipo OllamaGPUError na chamada direta."""
        corpo = re.search(
            r"def _on_rag_index_all\(self\) -> None:(.*?)\n    def ",
            _MAIN_WINDOW_SRC, re.DOTALL).group(1)
        assert "self._handle_rag_error(e)" in corpo
        assert "self._handle_rag_error(str(e))" not in corpo
        assert "self._rag_worker.error_occurred.connect(self._handle_rag_error)" in corpo


# ── 2. Assistente do Ollama (1ª execução × execuções seguintes) ─────────────

class TestAssistenteOllama:
    def test_primeira_execucao_abre_o_assistente(self, janela, config, monkeypatch):
        criados = _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)

        assert len(criados) == 1, "o onboarding da 1ª execução deve abrir"
        assert criados[0] is win  # parenteado na janela
        assert win._ollama_wizard_btn is None  # sem botão: o modal já apareceu

    def test_primeira_execucao_grava_a_flag(self, janela, config, monkeypatch):
        _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)

        assert config.get(ONBOARDING_WIZARD_KEY) is True
        # persistida em disco (chave com ponto → dict aninhado)
        recarregado = ConfigManager(config._path)
        assert recarregado.get(ONBOARDING_WIZARD_KEY) is True

    def test_execucoes_seguintes_nao_abrem_o_assistente(
            self, janela, config, monkeypatch, ):
        config.set(ONBOARDING_WIZARD_KEY, True)
        criados = _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)

        assert criados == [], "não pode abrir modal por cima de quem está lendo"

    def test_execucoes_seguintes_criam_o_botao_discreto(
            self, janela, config, monkeypatch):
        config.set(ONBOARDING_WIZARD_KEY, True)
        _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)

        btn = win._ollama_wizard_btn
        assert isinstance(btn, QPushButton)
        assert btn.text() == "Configurar IA…"
        assert btn.isFlat()
        assert btn in win._statusbar.findChildren(QPushButton)

        texto, timeout = win._statusbar.last
        assert "IA" in texto
        assert timeout == OLLAMA_ABSENT_STATUS_MS

    def test_botao_so_abre_o_assistente_quando_clicado(
            self, janela, config, monkeypatch, qtbot):
        config.set(ONBOARDING_WIZARD_KEY, True)
        criados = _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)
        assert criados == []

        win._ollama_wizard_btn.click()
        assert len(criados) == 1

    def test_botao_nao_duplica_entre_sondagens(self, janela, config, monkeypatch):
        config.set(ONBOARDING_WIZARD_KEY, True)
        _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)
        primeiro = win._ollama_wizard_btn
        win._on_rag_status_ready(engine, False, [], 0)

        assert win._ollama_wizard_btn is primeiro
        assert len(win._statusbar.findChildren(QPushButton)) == 1

    def test_ia_disponivel_esconde_o_botao(self, janela, config, monkeypatch):
        config.set(ONBOARDING_WIZARD_KEY, True)
        _fake_wizard(monkeypatch)
        engine = _FakeEngine(available=False)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 0)
        assert win._ollama_wizard_btn.isVisibleTo(win._statusbar)

        win._on_rag_status_ready(engine, True, [{"name": "gemma4:e4b"}], 5)
        assert not win._ollama_wizard_btn.isVisibleTo(win._statusbar)
        assert win._rag_panel.model_lists[-1] == ["gemma4:e4b"]

    def test_assistente_aceito_resonda_o_daemon(self, janela, config, monkeypatch):
        """Fluxo antigo preservado: instalou → sonda curta → lista de modelos."""
        _fake_wizard(monkeypatch, result=QDialog.DialogCode.Accepted)
        engine = _FakeEngine(available=True, models=[{"name": "gemma4:e4b"}])
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, False, [], 7)

        assert engine.probes == 1
        assert win._rag_panel.model_lists[-1] == ["gemma4:e4b"]
        assert win._rag_panel.status[-1][0] is True
        assert win._rag_panel.indexed == 7

    def test_daemon_sem_modelos_dispara_pull(self, janela, config, monkeypatch):
        config.set(ONBOARDING_WIZARD_KEY, True)
        engine = _FakeEngine(available=True)
        win = janela(engine=engine)

        win._on_rag_status_ready(engine, True, [], 0)

        assert win.model_pulls == 1

    def test_engine_ausente_nao_abre_nada(self, janela, config, monkeypatch):
        criados = _fake_wizard(monkeypatch)
        win = janela()

        win._on_rag_status_ready(None, False, [], 0)

        assert criados == []
        assert win._rag_panel.status == [(False, "")]


# ── 3. Anki ─────────────────────────────────────────────────────────────────

class TestErroAnkiSemDialogo:
    def test_erro_do_worker_vai_para_a_statusbar(self, janela, sem_dialogos):
        win = janela()
        win._on_anki_error("AnkiConnect recusou a conexão")

        assert sem_dialogos == [], "envio em background não pode abrir modal"
        texto, timeout = win._statusbar.last
        assert "Anki" in texto
        assert "AnkiConnect recusou a conexão" in texto
        assert timeout == ANKI_ERROR_STATUS_MS

    def test_erro_do_anki_e_logado(self, janela, caplog):
        win = janela()
        with caplog.at_level("ERROR", logger="src.gui.main_window"):
            win._on_anki_error("boom")
        assert any("boom" in r.getMessage() for r in caplog.records)

    def test_callback_ligado_ao_sinal_de_erro(self):
        assert "self._anki_worker.error.connect(self._on_anki_error)" in _MAIN_WINDOW_SRC
        assert 'QMessageBox.warning(self, "Erro no Anki"' not in _MAIN_WINDOW_SRC


# ── 4. Varredura: nenhum modal a partir de sinal de worker ──────────────────

def test_nenhuma_conexao_de_worker_abre_dialogo():
    """Todo ``.connect`` vindo de worker/serviço aponta para statusbar/painel.

    Exceção auditada e MANTIDA: ``_generate_flashcard_qa`` abre o diálogo do
    Anki quando o worker termina — é a continuação direta de um clique do
    usuário ("gerar flashcard"), com diálogo de progresso cancelável já na
    tela, e não uma interrupção não solicitada.
    """
    conexoes = re.findall(
        r"self\._[A-Za-z0-9_]*(?:worker|service|watcher)[A-Za-z0-9_]*"
        r"\.[A-Za-z0-9_]+\.connect\(\s*self\.(_[A-Za-z0-9_]+)\s*\)",
        _MAIN_WINDOW_SRC,
    )
    assert conexoes, "regex deixou de casar — revise a varredura"

    for slot in set(conexoes):
        corpo = re.search(
            rf"\n    def {slot}\(.*?\n    def ", _MAIN_WINDOW_SRC, re.DOTALL)
        if corpo is None:
            continue
        sem_comentarios = "\n".join(
            ln for ln in corpo.group(0).split("\n") if not ln.strip().startswith("#"))
        for proibido in ("QMessageBox.critical(", "QMessageBox.warning(",
                         "QMessageBox.information(", "QMessageBox.question("):
            assert proibido not in sem_comentarios, (
                f"{slot} abre modal a partir de sinal de worker: {proibido}")
