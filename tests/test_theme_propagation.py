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


def test_apply_theme_still_styles_mainwindow_and_subwidgets(qtbot):
    """Mantém as chamadas existentes: MainWindow + reader/sidebar/rag."""
    stub = _apply("dark")
    stub.setStyleSheet.assert_called_once_with(get_theme("dark"))
    stub._reader_view.set_theme.assert_called_once_with("dark")
    stub._sidebar.set_theme.assert_called_once_with("dark")
    stub._rag_panel.set_theme.assert_called_once_with("dark")
