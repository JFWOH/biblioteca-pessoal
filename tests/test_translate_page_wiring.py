"""Guardas estruturais da ação 'Traduzir Página (texto)' (Commit 4).

ReaderView/MainWindow não podem ser instanciados na suíte: importam
QtWebEngineWidgets, que só pode ser carregado ANTES de existir um
QApplication — e outros testes com qtbot já criaram um quando este módulo
roda (mesmo motivo documentado em test_reader_view_guards.py). Por isso
verificamos a fiação por inspeção do código-fonte, honesto quanto à
limitação: o comportamento real (emitir o sinal, mostrar o cartão) só é
validado manualmente no app (ver contrato, Seção 8.3).
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_READER_VIEW = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")
_MAIN_WINDOW = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")


def test_translate_page_action_exists_and_wired():
    assert re.search(
        r'self\._act_translate_page\s*=\s*QAction\("🌐 Traduzir Página \(texto\)"',
        _READER_VIEW,
    )
    assert re.search(
        r"self\._act_translate_page\.triggered\.connect\(self\._on_translate_page\)",
        _READER_VIEW,
    )
    assert "self._overflow_menu.addAction(self._act_translate_page)" in _READER_VIEW


def test_on_translate_page_emits_correct_signal_key():
    match = re.search(
        r"def _on_translate_page\(self\):(.*?)\n    def ", _READER_VIEW, re.DOTALL)
    assert match, "_on_translate_page não encontrado"
    body = match.group(1)
    assert 'self.ai_action_requested.emit("translate_page", page_text)' in body
    assert "page_text = (page_text or \"\").strip()" in body  # guarda de página vazia


def test_main_window_dispatches_translate_page():
    assert re.search(
        r'elif action_type == "translate_page":\s*\n\s*#.*\n\s*self\._translate_page_as_text\(text\)',
        _MAIN_WINDOW,
    )


def test_translate_page_as_text_reuses_language_detect_and_card():
    match = re.search(
        r"def _translate_page_as_text\(self, text: str\):(.*?)\n    def ",
        _MAIN_WINDOW, re.DOTALL)
    assert match, "_translate_page_as_text não encontrado"
    body = match.group(1)
    assert "from src.core.tts.language_detect import detect_language" in body
    assert "self._rag_panel.show_translation_card(" in body
    assert "_page_translation_pending" in body  # mesmo guard de _read_translated_page
    assert "len(text)" in body  # contagem de caracteres no aviso
