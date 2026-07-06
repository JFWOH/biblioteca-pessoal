"""Fiação do Dossiê do Livro (Fase 4): botão no BookDetails + MainWindow.

O BookDetails instancia normalmente com qtbot. O MainWindow NÃO pode ser
instanciado na suíte (importa QtWebEngineWidgets, que quebra com QApplication
já criado por outros testes) — a fiação dele é verificada por inspeção do
código-fonte, padrão de test_translate_page_wiring.py.
"""
import re
from pathlib import Path

import pytest

from src.core.database import LibraryDB
from src.gui.book_details import BookDetails

_ROOT = Path(__file__).resolve().parent.parent
_MAIN_WINDOW = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def test_dossier_button_emits_signal(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    bid = db.add_book(title="Livro", file_path="/tmp/x.pdf",
                      file_format="pdf", page_count=5)
    panel.show_book(db.get_book(bid))

    got = []
    panel.dossier_requested.connect(got.append)
    panel._dossier_btn.click()
    assert got == [bid]


def test_dossier_button_noop_without_book(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    got = []
    panel.dossier_requested.connect(got.append)
    panel._dossier_btn.click()
    assert got == []


def test_main_window_wires_dossier_signal():
    assert ("self._book_details.dossier_requested.connect(self._open_book_dossier)"
            in _MAIN_WINDOW)


def test_main_window_open_dossier_handler():
    match = re.search(
        r"def _open_book_dossier\(self, book_id: int\):(.*?)\n    def ",
        _MAIN_WINDOW, re.DOTALL)
    assert match, "_open_book_dossier não encontrado"
    body = match.group(1)
    assert "BookDossierDialog(" in body
    # Clique em relacionado dentro do dossiê reusa o fluxo de seleção.
    assert "dialog.open_book_requested.connect(self._on_book_selected)" in body
    # Mesmas chaves de config do RAG — sem config nova.
    assert 'self._config.get("rag.ollama_url"' in body
    assert 'self._config.get("rag.llm_model"' in body
