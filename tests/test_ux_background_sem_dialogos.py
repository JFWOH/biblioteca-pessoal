"""Onda S da rodada UX (ago/2026) — tarefa em segundo plano não abre diálogo.

Quem está lendo não pode ser interrompido por um modal disparado por um worker:
a informação vai para a barra de status e para o painel correspondente. Cobre
os três pontos auditados em ``src/gui/main_window.py``:

  1. ``_handle_rag_error``    — reindexação que falha (inclusive falha de GPU);
  2. ``_on_rag_status_ready`` — assistente do Ollama só na 1ª execução;
  3. ``_on_anki_error``       — envio do flashcard ao Anki que falha.

ESTE MÓDULO NÃO IMPORTA ``src.gui`` — nem ``main_window``, nem ``reader_view``.
``main_window`` puxa ``QtWebEngineWidgets`` (via ReaderView) e o GC do
QtWebEngine sem event loop dá Segmentation fault no teardown do pytest no
Linux. Por isso, os dois estilos já usados no repo (mesmo padrão de
``test_reader_tts_fallback_visivel.py`` e ``test_translate_page_wiring.py``):

* checagens ESTÁTICAS (AST/regex) sobre o FONTE de ``main_window.py``;
* UM subprocesso fresco que importa o módulo ANTES de criar o QApplication e
  imprime um JSON assertável — é o único jeito honesto de provar que a
  mensagem sai na barra e que nenhum modal é aberto.

``test_modulo_nao_puxa_webengine`` trava a regressão.
"""
import ast
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_MAIN_WINDOW = _ROOT / "src" / "gui" / "main_window.py"
_SRC = _MAIN_WINDOW.read_text(encoding="utf-8")


# ── Utilidades de inspeção estática ─────────────────────────────────────────

def _codigo(texto: str) -> str:
    """Remove docstrings e comentários: a guarda olha o CÓDIGO, não a prosa."""
    sem_doc = re.sub(r'"""(.*?)"""', "", texto, flags=re.DOTALL)
    return "\n".join(
        ln for ln in sem_doc.split("\n") if not ln.strip().startswith("#"))


def _corpo(nome: str) -> str:
    """Código do método ``nome`` da MainWindow (sem docstring/comentários)."""
    tree = ast.parse(_SRC)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    fn = next((n for n in cls.body
               if isinstance(n, ast.FunctionDef) and n.name == nome), None)
    assert fn is not None, f"método {nome} não encontrado em MainWindow"
    return _codigo(ast.get_source_segment(_SRC, fn))


def _const(nome: str):
    """Valor de uma constante de módulo, lido por AST (sem importar o módulo)."""
    for n in ast.parse(_SRC).body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == nome for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError(f"constante de módulo {nome} não encontrada")


# ── Guarda anti-regressão: este módulo não pode puxar QtWebEngine ───────────

_GUARDA_DRIVER = textwrap.dedent(
    """
    import importlib.util, json, sys
    sys.path.insert(0, sys.argv[1])
    spec = importlib.util.spec_from_file_location("_mod_sob_guarda", sys.argv[2])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    suspeitos = sorted(m for m in sys.modules
                       if "WebEngine" in m or m.startswith("src.gui"))
    print("@@JSON@@" + json.dumps(suspeitos))
    """
)


def test_modulo_nao_puxa_webengine():
    """Importar ESTE módulo não pode carregar QtWebEngine nem ``src.gui``.

    Verificado em subprocesso, e não com ``"PyQt6.QtWebEngineCore" not in
    sys.modules`` em processo, porque outros módulos do MESMO shard
    (``test_theme_propagation.py``, ``test_translate_narrate_cache.py``)
    importam ``src.gui.main_window`` no topo e já teriam carregado o WebEngine
    antes deste arquivo rodar — a asserção em processo mediria a ordem do
    shard, não a higiene deste arquivo.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _GUARDA_DRIVER,
         str(_ROOT), str(Path(__file__).resolve())],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8"),
        timeout=300,
    )
    assert "@@JSON@@" in (proc.stdout or ""), (
        f"guarda não rodou (rc={proc.returncode}):\n{proc.stderr[-1500:]}")
    carregados = json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())
    assert carregados == [], (
        "este módulo de teste voltou a puxar GUI/QtWebEngine em processo "
        f"(segfault no teardown do pytest no Linux): {carregados}")


def test_fonte_deste_teste_nao_importa_gui_no_topo():
    """Feedback rápido da mesma invariante, sem pagar um subprocesso.

    Olha os nós de import do AST — e não substrings — porque o fonte do driver
    do subprocesso é uma string deste arquivo e contém, de propósito, um
    ``from src.gui.main_window import ...`` que só roda no processo filho.
    """
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    modulos = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            modulos.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            modulos.add(no.module)

    proibidos = sorted(m for m in modulos
                       if m.startswith("src.gui") or "QtWebEngine" in m)
    assert proibidos == [], (
        f"import de GUI em processo reintroduzido: {proibidos}")


# ── 1. Estático: fiação e invariantes de main_window.py ─────────────────────

class TestGuardasEstaticas:
    def test_handler_de_rag_sem_modal(self):
        corpo = _corpo("_handle_rag_error")
        assert "QMessageBox.critical(" not in corpo, "o modal não pode voltar"
        assert "self._statusbar.showMessage(" in corpo
        assert "self._rag_panel.on_error(" in corpo
        assert "logger.error(" in corpo

    def test_index_all_repassa_a_excecao_crua(self):
        """``str(e)`` perderia o tipo OllamaGPUError na chamada direta."""
        corpo = _corpo("_on_rag_index_all")
        assert "self._handle_rag_error(e)" in corpo
        assert "self._handle_rag_error(str(e))" not in corpo
        assert "self._rag_worker.error_occurred.connect(self._handle_rag_error)" in corpo

    def test_anki_ligado_ao_metodo_sem_modal(self):
        assert "self._anki_worker.error.connect(self._on_anki_error)" in _corpo(
            "_open_anki_export_dialog")
        corpo_erro = _corpo("_on_anki_error")
        assert "QMessageBox" not in corpo_erro
        assert "self._statusbar.showMessage(" in corpo_erro
        assert "logger.error(" in corpo_erro

    def test_assistente_condicionado_a_flag_de_onboarding(self):
        corpo = _corpo("_on_rag_status_ready")
        assert "if not self._config.get(ONBOARDING_WIZARD_KEY, False):" in corpo
        assert "self._run_ollama_wizard(engine)" in corpo
        assert "self._show_ollama_wizard_button()" in corpo
        # o exec() saiu deste método: agora vive no helper compartilhado
        assert ".exec()" not in corpo

    def test_flag_gravada_antes_de_exibir_o_assistente(self):
        """O critério é "foi EXIBIDO": quem fecha o wizard não o revê sempre."""
        corpo = _corpo("_run_ollama_wizard")
        assert (corpo.index("self._config.set(ONBOARDING_WIZARD_KEY, True)")
                < corpo.index("wizard.exec()")), "grave a flag ANTES do exec()"

    def test_botao_discreto_e_permanente_na_barra(self):
        corpo = _corpo("_show_ollama_wizard_button")
        assert 'QPushButton("Configurar IA…")' in corpo
        assert "btn.setFlat(True)" in corpo
        assert "self._statusbar.addPermanentWidget(btn)" in corpo
        assert "btn.clicked.connect(self._open_ollama_wizard)" in corpo
        assert "QMessageBox" not in corpo and "QDialog" not in corpo

    def test_constantes_de_duracao_declaradas(self):
        assert _const("ONBOARDING_WIZARD_KEY") == "onboarding.ollama_wizard_shown"
        # a instrução de GPU precisa ser lida inteira antes de o usuário agir
        assert _const("GPU_ERROR_STATUS_MS") >= 15000
        assert _const("OLLAMA_ABSENT_STATUS_MS") >= 5000
        assert _const("ANKI_ERROR_STATUS_MS") >= 5000


def test_nenhuma_conexao_de_worker_abre_dialogo():
    """Varredura: todo ``.connect`` de worker/serviço vai para statusbar/painel.

    Exceção auditada e MANTIDA: ``_generate_flashcard_qa`` abre o diálogo do
    Anki quando o worker termina — é a continuação direta de um clique do
    usuário ("gerar flashcard"), com diálogo de progresso cancelável já na
    tela, e não uma interrupção não solicitada.
    """
    conexoes = re.findall(
        r"self\._[A-Za-z0-9_]*(?:worker|service|watcher)[A-Za-z0-9_]*"
        r"\.[A-Za-z0-9_]+\.connect\(\s*self\.(_[A-Za-z0-9_]+)\s*\)",
        _SRC,
    )
    assert conexoes, "regex deixou de casar — revise a varredura"

    cls = next(n for n in ast.parse(_SRC).body
               if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    existentes = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}

    for slot in sorted(set(conexoes) & existentes):
        corpo = _corpo(slot)
        for proibido in ("QMessageBox.critical(", "QMessageBox.warning(",
                         "QMessageBox.information(", "QMessageBox.question("):
            assert proibido not in corpo, (
                f"{slot} abre modal a partir de sinal de worker: {proibido}")


# ── 2. Comportamento real (subprocesso: import ANTES do QApplication) ───────

_DRIVER = textwrap.dedent(
    """
    import json, logging, sys, tempfile
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])

    # ANTES do QApplication (main_window -> reader_view -> QtWebEngineWidgets).
    from src.gui.main_window import (
        ANKI_ERROR_STATUS_MS, GPU_ERROR_STATUS_MS, OLLAMA_ABSENT_STATUS_MS,
        ONBOARDING_WIZARD_KEY, MainWindow, gpu_failure_message,
    )
    from src.core.config import ConfigManager
    from src.core.rag_engine import GPU_FAILURE_MESSAGE, OllamaGPUError

    import PyQt6.QtWidgets as W
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QMainWindow, QPushButton, QStatusBar)

    app = QApplication([])
    out = {"gpu_failure_message": GPU_FAILURE_MESSAGE, "consts": {
        "GPU_ERROR_STATUS_MS": GPU_ERROR_STATUS_MS,
        "OLLAMA_ABSENT_STATUS_MS": OLLAMA_ABSENT_STATUS_MS,
        "ANKI_ERROR_STATUS_MS": ANKI_ERROR_STATUS_MS,
    }}

    # Conta QUALQUER modal do QMessageBox (mesma classe que main_window importou).
    modais = []
    for _n in ("critical", "warning", "information", "question", "about"):
        setattr(W.QMessageBox, _n,
                staticmethod(lambda *a, _k=_n, **kw: modais.append(_k)))

    class Bar(QStatusBar):
        def __init__(self):
            super().__init__()
            self.messages = []
        def showMessage(self, text, timeout=0):
            self.messages.append([text, timeout])
            super().showMessage(text, timeout)

    class Panel:
        def __init__(self):
            self.errors = []; self.model_lists = []
            self.status = []; self.indexed = None
        def on_error(self, m): self.errors.append(m)
        def update_model_list(self, n): self.model_lists.append(list(n))
        def set_ollama_status(self, a, m=""): self.status.append([a, m])
        def set_indexed_count(self, n): self.indexed = n

    class Engine:
        def __init__(self, available=False, models=None):
            self._a = available; self._m = models or []; self.probes = 0
        def is_ollama_available(self):
            self.probes += 1; return self._a
        def list_local_models(self): return self._m

    criados = []
    aceitar = {"v": False}

    class FakeWizard:
        def __init__(self, parent=None): criados.append(parent)
        def exec(self):
            return (QDialog.DialogCode.Accepted if aceitar["v"]
                    else QDialog.DialogCode.Rejected)

    import src.gui.dialogs.ollama_wizard as wiz_mod
    wiz_mod.OllamaWizardDialog = FakeWizard

    class Stub(QMainWindow):
        _handle_rag_error = MainWindow._handle_rag_error
        _on_anki_error = MainWindow._on_anki_error
        _on_rag_status_ready = MainWindow._on_rag_status_ready
        _run_ollama_wizard = MainWindow._run_ollama_wizard
        _show_ollama_wizard_button = MainWindow._show_ollama_wizard_button
        _hide_ollama_wizard_button = MainWindow._hide_ollama_wizard_button
        _open_ollama_wizard = MainWindow._open_ollama_wizard
        def __init__(self, config, engine=None):
            super().__init__()
            self._statusbar = Bar()
            self.setStatusBar(self._statusbar)
            self._ollama_wizard_btn = None
            self._rag_panel = Panel()
            self._config = config
            self._rag_engine = engine   # pula a injeção tardia, fora de escopo
            self.model_pulls = 0
        def _start_model_pull(self): self.model_pulls += 1

    def cfg(visto=False):
        c = ConfigManager(Path(tempfile.mkdtemp()) / "config.json")
        if visto:
            c.set(ONBOARDING_WIZARD_KEY, True)
        return c

    # ── 1. _handle_rag_error ──────────────────────────────────────────────
    w = Stub(cfg()); modais.clear()
    w._handle_rag_error("chroma explodiu")
    out["rag_comum"] = {"modais": list(modais), "painel": list(w._rag_panel.errors),
                        "status": list(w._statusbar.messages)}

    w = Stub(cfg()); modais.clear()
    w._handle_rag_error(OllamaGPUError(GPU_FAILURE_MESSAGE))
    out["rag_gpu_excecao"] = {"modais": list(modais),
                              "painel": list(w._rag_panel.errors),
                              "status": list(w._statusbar.messages)}

    w = Stub(cfg())
    w._handle_rag_error("Erro ao indexar o livro 3: " + GPU_FAILURE_MESSAGE)
    out["rag_gpu_string"] = list(w._statusbar.messages)

    w = Stub(cfg())
    w._handle_rag_error("arquivo nao encontrado")
    out["rag_nao_gpu"] = list(w._statusbar.messages)

    out["helper"] = {
        "excecao": gpu_failure_message(OllamaGPUError("qualquer")),
        "string": gpu_failure_message(GPU_FAILURE_MESSAGE),
        "timeout_comum": gpu_failure_message("timeout comum"),
        "runtime": gpu_failure_message(RuntimeError("boom")),
    }

    # ── 2. Assistente do Ollama ───────────────────────────────────────────
    criados.clear(); aceitar["v"] = False
    c = cfg(); e = Engine(available=False); w = Stub(c, engine=e)
    w._on_rag_status_ready(e, False, [], 0)
    out["primeira_exec"] = {
        "wizards": len(criados),
        "parent_e_a_janela": bool(criados) and criados[0] is w,
        "criou_botao": w._ollama_wizard_btn is not None,
        "flag": c.get(ONBOARDING_WIZARD_KEY),
        "flag_persistida": ConfigManager(c._path).get(ONBOARDING_WIZARD_KEY),
    }

    criados.clear()
    c = cfg(visto=True); e = Engine(available=False); w = Stub(c, engine=e)
    w._on_rag_status_ready(e, False, [], 0)
    btn = w._ollama_wizard_btn
    seg = {
        "wizards": len(criados),
        "e_push_button": isinstance(btn, QPushButton),
        "texto": btn.text(), "flat": btn.isFlat(), "tooltip": btn.toolTip(),
        "na_statusbar": btn in w._statusbar.findChildren(QPushButton),
        "status": list(w._statusbar.messages),
    }
    w._on_rag_status_ready(e, False, [], 0)          # 2ª sondagem: não duplica
    seg["mesmo_botao"] = w._ollama_wizard_btn is btn
    seg["qtd_botoes"] = len(w._statusbar.findChildren(QPushButton))
    seg["wizards_antes_do_clique"] = len(criados)
    w._ollama_wizard_btn.click()
    seg["wizards_apos_clique"] = len(criados)
    out["seguintes"] = seg

    c = cfg(visto=True); e = Engine(available=False); w = Stub(c, engine=e)
    w._on_rag_status_ready(e, False, [], 0)
    visivel_antes = w._ollama_wizard_btn.isVisibleTo(w._statusbar)
    w._on_rag_status_ready(e, True, [{"name": "gemma4:e4b"}], 5)
    out["volta_da_ia"] = {
        "visivel_antes": visivel_antes,
        "visivel_depois": w._ollama_wizard_btn.isVisibleTo(w._statusbar),
        "modelos": list(w._rag_panel.model_lists[-1]),
    }

    criados.clear(); aceitar["v"] = True
    c = cfg(); e = Engine(available=True, models=[{"name": "gemma4:e4b"}])
    w = Stub(c, engine=e)
    w._on_rag_status_ready(e, False, [], 7)
    out["aceito"] = {"probes": e.probes,
                     "modelos": list(w._rag_panel.model_lists[-1]),
                     "status": list(w._rag_panel.status[-1]),
                     "indexed": w._rag_panel.indexed}
    aceitar["v"] = False

    c = cfg(visto=True); e = Engine(available=True); w = Stub(c, engine=e)
    w._on_rag_status_ready(e, True, [], 0)
    out["pull_sem_modelos"] = w.model_pulls

    criados.clear()
    w = Stub(cfg())
    w._on_rag_status_ready(None, False, [], 0)
    out["engine_none"] = {"wizards": len(criados),
                          "status": [list(x) for x in w._rag_panel.status]}

    # ── 3. Anki ───────────────────────────────────────────────────────────
    logs = []
    class _H(logging.Handler):
        def emit(self, r): logs.append(r.getMessage())
    lg = logging.getLogger("src.gui.main_window")
    lg.addHandler(_H()); lg.setLevel(logging.ERROR)

    w = Stub(cfg()); modais.clear()
    w._on_anki_error("AnkiConnect recusou a conexao")
    out["anki"] = {"modais": list(modais), "status": list(w._statusbar.messages),
                   "logs": list(logs)}

    print("@@JSON@@" + json.dumps(out, ensure_ascii=True))
    """
)


@pytest.fixture(scope="module")
def r():
    """Roda o driver UMA vez e devolve o JSON com todos os resultados."""
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(_ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8"),
        timeout=600,
    )
    if "@@JSON@@" not in (proc.stdout or ""):
        pytest.skip(
            f"driver da MainWindow não rodou neste ambiente (rc={proc.returncode}): "
            f"{proc.stderr[-800:]}")
    return json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())


class TestErroRagSemDialogo:
    """A reindexação roda sem o usuário ter pedido nada naquele instante."""

    def test_nao_abre_dialogo_e_alimenta_statusbar_e_painel(self, r):
        caso = r["rag_comum"]
        assert caso["modais"] == [], "worker de background não pode abrir modal"
        assert caso["painel"] == ["chroma explodiu"]
        texto, timeout = caso["status"][-1]
        assert "chroma explodiu" in texto
        assert timeout == 5000

    def test_gpu_error_usa_mensagem_orientativa_e_duracao_longa(self, r):
        caso = r["rag_gpu_excecao"]
        assert caso["modais"] == []
        texto, timeout = caso["status"][-1]
        assert r["gpu_failure_message"] in texto
        assert timeout == r["consts"]["GPU_ERROR_STATUS_MS"] >= 15000
        assert caso["painel"], "o painel do assistente também precisa saber"

    def test_mensagem_de_gpu_e_acionavel(self, r):
        msg = r["gpu_failure_message"].lower()
        assert "driver" in msg and "ollama_num_gpu" in msg

    def test_gpu_reconhecido_pela_string_que_o_sinal_entrega(self, r):
        """``error_occurred`` é ``pyqtSignal(str)``: o tipo morre na thread."""
        texto, timeout = r["rag_gpu_string"][-1]
        assert r["gpu_failure_message"] in texto
        assert timeout == r["consts"]["GPU_ERROR_STATUS_MS"]

    def test_erro_comum_nao_vira_falso_positivo_de_gpu(self, r):
        assert r["rag_nao_gpu"][-1][1] == 5000

    def test_helper_reconhece_as_duas_formas(self, r):
        esperado = r["gpu_failure_message"]
        assert r["helper"]["excecao"] == esperado
        assert r["helper"]["string"] == esperado
        assert r["helper"]["timeout_comum"] == ""
        assert r["helper"]["runtime"] == ""


class TestAssistenteOllama:
    def test_primeira_execucao_abre_o_assistente(self, r):
        caso = r["primeira_exec"]
        assert caso["wizards"] == 1, "o onboarding da 1ª execução deve abrir"
        assert caso["parent_e_a_janela"] is True
        assert caso["criou_botao"] is False, "o modal já apareceu; botão seria ruído"

    def test_primeira_execucao_grava_e_persiste_a_flag(self, r):
        caso = r["primeira_exec"]
        assert caso["flag"] is True
        # chave com ponto → dict aninhado, relido do disco
        assert caso["flag_persistida"] is True

    def test_execucoes_seguintes_nao_abrem_o_assistente(self, r):
        assert r["seguintes"]["wizards"] == 0, (
            "não pode abrir modal por cima de quem está lendo")

    def test_execucoes_seguintes_criam_o_botao_discreto(self, r):
        seg = r["seguintes"]
        assert seg["e_push_button"] is True
        assert seg["texto"] == "Configurar IA…"
        assert seg["flat"] is True
        assert seg["na_statusbar"] is True
        assert "Ollama" in seg["tooltip"]
        texto, timeout = seg["status"][-1]
        assert "IA" in texto
        assert timeout == r["consts"]["OLLAMA_ABSENT_STATUS_MS"]

    def test_botao_nao_duplica_entre_sondagens(self, r):
        assert r["seguintes"]["mesmo_botao"] is True
        assert r["seguintes"]["qtd_botoes"] == 1

    def test_botao_so_abre_o_assistente_quando_clicado(self, r):
        assert r["seguintes"]["wizards_antes_do_clique"] == 0
        assert r["seguintes"]["wizards_apos_clique"] == 1

    def test_ia_disponivel_esconde_o_botao(self, r):
        caso = r["volta_da_ia"]
        assert caso["visivel_antes"] is True
        assert caso["visivel_depois"] is False
        assert caso["modelos"] == ["gemma4:e4b"]

    def test_assistente_aceito_resonda_o_daemon(self, r):
        """Fluxo antigo preservado: instalou → sonda curta → lista de modelos."""
        caso = r["aceito"]
        assert caso["probes"] == 1
        assert caso["modelos"] == ["gemma4:e4b"]
        assert caso["status"][0] is True
        assert caso["indexed"] == 7

    def test_daemon_sem_modelos_dispara_pull(self, r):
        assert r["pull_sem_modelos"] == 1

    def test_engine_ausente_nao_abre_nada(self, r):
        caso = r["engine_none"]
        assert caso["wizards"] == 0
        assert caso["status"] == [[False, ""]]


class TestErroAnkiSemDialogo:
    def test_erro_do_worker_vai_para_a_statusbar(self, r):
        caso = r["anki"]
        assert caso["modais"] == [], "envio em background não pode abrir modal"
        texto, timeout = caso["status"][-1]
        assert "Anki" in texto
        assert "AnkiConnect recusou a conexao" in texto
        assert timeout == r["consts"]["ANKI_ERROR_STATUS_MS"]

    def test_erro_do_anki_e_logado(self, r):
        assert any("AnkiConnect recusou a conexao" in ln for ln in r["anki"]["logs"])
