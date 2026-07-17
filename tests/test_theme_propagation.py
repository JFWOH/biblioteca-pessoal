"""Onda 0.2 — propagação completa de tema.

Mecanismo: ``MainWindow._apply_theme`` aplica a stylesheet do tema na
``QApplication``, de modo que TODO widget top-level herde o tema
automaticamente — inclusive os diálogos (settings/import/coleção/flashcards/
dossiê/wizard/anki/tags) criados DEPOIS da troca de tema. Antes, só a
MainWindow + reader/sidebar/rag recebiam o tema e os diálogos ficavam com a
aparência do tema anterior (propagação parcial).

Não instanciamos a ``MainWindow`` (pesada: DB, RAG, QtWebEngine). Testamos o
método ``_apply_theme`` com um ``self`` stub: só a parte da ``QApplication``
roda de verdade; ``setStyleSheet``/reader/sidebar/rag viram no-ops do Mock.

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
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from src.gui.main_window import MainWindow
from src.gui.styles import get_theme


@pytest.fixture(autouse=True)
def _restore_app_stylesheet(qtbot):
    """Não vaza a stylesheet global entre testes (QApplication é singleton)."""
    app = QApplication.instance()
    before = app.styleSheet()
    yield
    app.setStyleSheet(before)


def _apply(theme: str) -> MagicMock:
    """Chama MainWindow._apply_theme com um self stub e devolve o stub."""
    stub = MagicMock()
    stub._config.theme = theme
    MainWindow._apply_theme(stub)
    return stub


def test_apply_theme_sets_qapplication_stylesheet(qtbot):
    app = QApplication.instance()
    for theme in ("light", "sepia", "dark"):
        _apply(theme)
        assert app.styleSheet() == get_theme(theme), f"tema {theme} não propagou p/ a app"


def test_dialog_created_after_theme_inherits_app_stylesheet(qtbot):
    app = QApplication.instance()
    _apply("light")
    assert app.styleSheet() == get_theme("light")
    # Diálogo criado DEPOIS da troca: sem folha própria → herda o tema da app.
    # (A remoção de estilos inline dos diálogos reais é débito da 0.3; aqui só
    # validamos que o mecanismo de herança da QApplication funciona.)
    dlg = QDialog()
    qtbot.addWidget(dlg)
    assert dlg.styleSheet() == ""


def test_apply_theme_does_not_duplicate_sheet_on_mainwindow(qtbot):
    """A folha do tema vive SÓ na QApplication — nunca duplicada na janela.

    Ajustes pós-teste (jul/2026): o antigo ``self.setStyleSheet(qss)`` foi
    REMOVIDO de ``_apply_theme``. Ele era redundante (a folha da app já cobre
    a MainWindow e todos os descendentes) e custava +2–4% na reconstrução da
    grade a cada transição de seção, medido em
    ``tools/profile_transitions.py``. Este teste é a trava de regressão:
    se ``setStyleSheet`` voltar a ser chamado na janela, a folha dupla voltou.
    Os sub-temas específicos (reader/sidebar/rag) continuam aplicados.
    """
    stub = _apply("dark")
    stub.setStyleSheet.assert_not_called()
    stub._reader_view.set_theme.assert_called_once_with("dark")
    stub._sidebar.set_theme.assert_called_once_with("dark")
    stub._rag_panel.set_theme.assert_called_once_with("dark")
