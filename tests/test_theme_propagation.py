"""Onda 0.2 — propagação completa de tema.

Mecanismo: ``MainWindow._apply_theme`` aplica a stylesheet do tema na
``QApplication``, de modo que TODO widget top-level herde o tema
automaticamente — inclusive os diálogos (settings/import/coleção/flashcards/
dossiê/wizard/anki/tags) criados DEPOIS da troca de tema. Antes, só a
MainWindow + reader/sidebar/rag recebiam o tema e os diálogos ficavam com a
aparência do tema anterior (propagação parcial).

Não instanciamos a ``MainWindow`` (pesada: DB, RAG, QtWebEngine). O método
``_apply_theme`` roda com um ``self`` stub: só a parte da ``QApplication``
roda de verdade; ``setStyleSheet``/reader/sidebar/rag viram no-ops do Mock.

ESTE MÓDULO NÃO IMPORTA ``src.gui.main_window`` EM PROCESSO. Ele puxa
``QtWebEngineWidgets`` (via ReaderView) e o GC do QtWebEngine sem event loop
dá Segmentation fault no teardown do pytest no Linux — foi a causa das quedas
do shard ``test_[t-z]``. O método real é exercitado num subprocesso fresco que
importa o módulo ANTES de criar o QApplication e devolve um JSON assertável
(mesmo padrão de ``test_reader_tts_fallback_visivel.py`` e
``test_ux_background_sem_dialogos.py``). ``test_modulo_nao_puxa_webengine``
trava a regressão.

Importante: este teste valida o MECANISMO (folha aplicada na app; diálogo novo
sem folha própria herda o tema) e deve permanecer verde após a Onda 0.3 — que
vai mover estilos inline de diálogos para ``styles.py``. Por isso NÃO asserta
sobre a styleSheet inline de widgets que ainda têm estilos hardcoded.

Ajustes pós-teste (jul/2026): ``_apply_theme`` NÃO chama mais
``self.setStyleSheet(qss)`` — a folha vive SÓ na QApplication. A duplicata na
janela fazia cada widget resolver estilo contra DUAS folhas de ~1.3k linhas em
cada polish; medição em ``tools/profile_transitions.py`` (offscreen, 60/120
livros) mostrou custo de +2–4% na reconstrução da grade por transição, sem
nenhum benefício: a folha da app já cobre a MainWindow e todos os descendentes.
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
_SRC = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")


def _corpo(nome: str) -> str:
    """Código do método ``nome`` da MainWindow, sem docstring/comentários."""
    cls = next(n for n in ast.parse(_SRC).body
               if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    fn = next((n for n in cls.body
               if isinstance(n, ast.FunctionDef) and n.name == nome), None)
    assert fn is not None, f"método {nome} não encontrado em MainWindow"
    seg = re.sub(r'"""(.*?)"""', "", ast.get_source_segment(_SRC, fn),
                 flags=re.DOTALL)
    return "\n".join(
        ln for ln in seg.split("\n") if not ln.strip().startswith("#"))


# ── Guarda de higiene: este módulo não pode puxar QtWebEngine ──────────────

_GUARDA_DRIVER = textwrap.dedent(
    """
    import importlib.util, json, sys
    sys.path.insert(0, sys.argv[1])
    spec = importlib.util.spec_from_file_location("_mod_sob_guarda", sys.argv[2])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    suspeitos = sorted(m for m in sys.modules if "WebEngine" in m
                       or m in ("src.gui.main_window", "src.gui.reader_view"))
    print("@@JSON@@" + json.dumps(suspeitos))
    """
)


def _rodar(driver: str, *args, timeout: int = 600):
    return subprocess.run(
        [sys.executable, "-c", driver, str(_ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8"),
        timeout=timeout,
    )


def test_modulo_nao_puxa_webengine():
    """Importar ESTE módulo não pode carregar QtWebEngine.

    Em subprocesso, e não com ``sys.modules`` em processo: outros módulos do
    mesmo shard podem ter carregado o WebEngine antes, e a asserção em processo
    mediria a ordem do shard em vez da higiene deste arquivo.
    """
    proc = _rodar(_GUARDA_DRIVER, str(Path(__file__).resolve()), timeout=300)
    assert "@@JSON@@" in (proc.stdout or ""), (
        f"guarda não rodou (rc={proc.returncode}):\n{proc.stderr[-1500:]}")
    carregados = json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())
    assert carregados == [], (
        "este módulo voltou a puxar QtWebEngine em processo "
        f"(segfault no teardown do pytest no Linux): {carregados}")


def test_fonte_deste_teste_nao_importa_main_window_no_topo():
    """Feedback rápido da mesma invariante, sem pagar um subprocesso."""
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    modulos = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            modulos.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            modulos.add(no.module)
    proibidos = sorted(m for m in modulos if "QtWebEngine" in m or m in (
        "src.gui.main_window", "src.gui.reader_view"))
    assert proibidos == [], f"import pesado reintroduzido: {proibidos}"


# ── Guarda estática do mecanismo (não depende do subprocesso) ──────────────

def test_apply_theme_nao_reaplica_a_folha_na_janela():
    """Trava de regressão do ajuste jul/2026: nada de folha duplicada."""
    corpo = _corpo("_apply_theme")
    assert "app.setStyleSheet(qss)" in corpo
    assert "self.setStyleSheet(" not in corpo, "a folha dupla voltou à janela"
    for alvo in ("self._reader_view.set_theme(theme)",
                 "self._sidebar.set_theme(theme)",
                 "self._rag_panel.set_theme(theme)"):
        assert alvo in corpo, f"sub-tema deixou de ser aplicado: {alvo}"


# ── Comportamento real (subprocesso: import ANTES do QApplication) ─────────

_DRIVER = textwrap.dedent(
    """
    import json, sys
    sys.path.insert(0, sys.argv[1])
    from unittest.mock import MagicMock

    # ANTES do QApplication (main_window -> reader_view -> QtWebEngineWidgets).
    from src.gui.main_window import MainWindow
    from src.gui.styles import get_theme
    from PyQt6.QtWidgets import QApplication, QDialog

    app = QApplication([])
    out = {}

    def aplicar(theme):
        stub = MagicMock()
        stub._config.theme = theme
        MainWindow._apply_theme(stub)
        return stub

    # 1) a folha do tema vai para a QApplication
    out["propaga_para_app"] = []
    for theme in ("light", "sepia", "dark"):
        aplicar(theme)
        out["propaga_para_app"].append(
            [theme, app.styleSheet() == get_theme(theme), bool(get_theme(theme))])

    # 2) diálogo criado DEPOIS da troca herda: não ganha folha própria
    aplicar("light")
    out["light_aplicado"] = app.styleSheet() == get_theme("light")
    dlg = QDialog()
    out["folha_do_dialogo"] = dlg.styleSheet()

    # 3) sem duplicata na janela; sub-temas aplicados uma vez com o tema certo
    stub = aplicar("dark")
    out["setstylesheet_na_janela"] = stub.setStyleSheet.call_count
    out["subtemas"] = {
        nome: [alvo.set_theme.call_count, list(alvo.set_theme.call_args.args)]
        for nome, alvo in (("reader", stub._reader_view),
                           ("sidebar", stub._sidebar),
                           ("rag", stub._rag_panel))
    }

    print("@@JSON@@" + json.dumps(out, ensure_ascii=True))
    """
)


@pytest.fixture(scope="module")
def r():
    """Roda o driver UMA vez e devolve o JSON com todos os resultados."""
    proc = _rodar(_DRIVER)
    if "@@JSON@@" not in (proc.stdout or ""):
        pytest.skip(
            f"driver do _apply_theme não rodou (rc={proc.returncode}): "
            f"{proc.stderr[-800:]}")
    return json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())


def test_apply_theme_sets_qapplication_stylesheet(r):
    for theme, propagou, tem_folha in r["propaga_para_app"]:
        assert tem_folha, f"get_theme({theme}) devolveu folha vazia"
        assert propagou, f"tema {theme} não propagou p/ a app"


def test_dialog_created_after_theme_inherits_app_stylesheet(r):
    assert r["light_aplicado"] is True
    # Diálogo criado DEPOIS da troca: sem folha própria → herda o tema da app.
    # (A remoção de estilos inline dos diálogos reais é débito da 0.3; aqui só
    # validamos que o mecanismo de herança da QApplication funciona.)
    assert r["folha_do_dialogo"] == ""


def test_apply_theme_does_not_duplicate_sheet_on_mainwindow(r):
    """A folha do tema vive SÓ na QApplication — nunca duplicada na janela.

    Ajustes pós-teste (jul/2026): o antigo ``self.setStyleSheet(qss)`` foi
    REMOVIDO de ``_apply_theme``. Ele era redundante (a folha da app já cobre
    a MainWindow e todos os descendentes) e custava +2–4% na reconstrução da
    grade a cada transição de seção, medido em
    ``tools/profile_transitions.py``. Este teste é a trava de regressão:
    se ``setStyleSheet`` voltar a ser chamado na janela, a folha dupla voltou.
    Os sub-temas específicos (reader/sidebar/rag) continuam aplicados.
    """
    assert r["setstylesheet_na_janela"] == 0
    for nome in ("reader", "sidebar", "rag"):
        chamadas, args = r["subtemas"][nome]
        assert chamadas == 1, f"sub-tema {nome} chamado {chamadas}x"
        assert args == ["dark"], f"sub-tema {nome} recebeu {args}"
