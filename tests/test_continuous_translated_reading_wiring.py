"""Guardas estruturais da leitura contínua traduzida (Commit 5).

Mesma limitação de test_reader_view_guards.py / test_translate_page_wiring.py:
ReaderView/MainWindow não instanciam na suíte (QtWebEngineWidgets). A
verificação é por inspeção do código-fonte; o comportamento real (narrar
página a página em PT com avanço automático) requer validação manual (ver
contrato, Seção 8.3).
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_READER_VIEW = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")
_MAIN_WINDOW = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")


# ── reader_view.py ────────────────────────────────────────────────────

def test_continuous_translate_mode_state_initialized():
    assert "self._continuous_translate_mode: bool = False" in _READER_VIEW


def test_continuous_translate_action_exists_and_wired():
    assert re.search(
        r'self\._act_continuous_translate\s*=\s*QAction\(\s*\n?\s*"🌐🔁 Leitura Contínua Traduzida \(PT\)"',
        _READER_VIEW,
    )
    assert (
        "self._act_continuous_translate.triggered.connect("
        "self._toggle_continuous_translate_reading)" in _READER_VIEW
    )
    assert "self._overflow_menu.addAction(self._act_continuous_translate)" in _READER_VIEW


def test_continuous_translate_persists_to_config():
    match = re.search(
        r"def _toggle_continuous_translate_reading\(self, checked: bool\):(.*?)\n    def ",
        _READER_VIEW, re.DOTALL)
    assert match, "_toggle_continuous_translate_reading não encontrado"
    body = match.group(1)
    assert 'config.set("tts.continuous_translate_reading"' in body
    assert "self._continuous_translate_mode = bool(checked)" in body


def test_toggle_audio_forks_to_translated_chain_on_start_path():
    """O fork deve estar no caminho de INICIAR (após checar page_text), não
    no de pause/resume (que fica ANTES, no bloco worker.isRunning())."""
    match = re.search(r"def _toggle_audio\(self\):(.*?)\n    def ", _READER_VIEW, re.DOTALL)
    assert match, "_toggle_audio não encontrado"
    body = match.group(1)
    pause_idx = body.index("self._resume_audio()")
    fork_idx = body.index("if self._continuous_translate_mode:")
    launch_idx = body.index("self._launch_audio_worker(page_text, chain_continuous=True)")
    assert pause_idx < fork_idx < launch_idx  # fork vem depois do pause/resume, antes do launch direto
    assert (
        'self.ai_action_requested.emit("read_translated_page_chained", page_text)' in body
    )


def test_narrate_text_accepts_and_propagates_chain_continuous():
    match = re.search(
        r"def narrate_text\(self, text: str, chain_continuous: bool = False\) -> None:(.*?)\n    def ",
        _READER_VIEW, re.DOTALL)
    assert match, "narrate_text não aceita chain_continuous"
    body = match.group(1)
    assert "chain_continuous=chain_continuous" in body


def test_on_audio_finished_covers_both_continuous_modes():
    match = re.search(r"def _on_audio_finished\(self, chunks\):(.*?)\n    def ",
                      _READER_VIEW, re.DOTALL)
    assert match, "_on_audio_finished não encontrado"
    body = match.group(1)
    assert "self._continuous_reading or self._continuous_translate_mode" in body


def test_sync_overflow_menu_syncs_translated_action_checkbox():
    match = re.search(r"def _sync_overflow_menu\(self\).*?:(.*?)\n    def ",
                      _READER_VIEW, re.DOTALL)
    assert match, "_sync_overflow_menu não encontrado"
    assert "self._act_continuous_translate.setChecked(self._continuous_translate_mode)" in match.group(1)


# ── main_window.py ────────────────────────────────────────────────────

def test_dispatcher_routes_chained_action_with_chaining_enabled():
    assert re.search(
        r'elif action_type == "read_translated_page_chained":\s*\n(?:.*\n)*?'
        r'\s*self\._translate_and_narrate\(text, enable_chaining=True\)',
        _MAIN_WINDOW,
    )


def test_dispatcher_single_shot_disables_chaining():
    assert re.search(
        r'elif action_type == "read_translated_page":\s*\n(?:.*\n)*?'
        r'\s*self\._translate_and_narrate\(text, enable_chaining=False\)',
        _MAIN_WINDOW,
    )


def test_translate_and_narrate_propagates_chaining_flag_to_narrate_text():
    match = re.search(
        r"def _translate_and_narrate\(self, text: str, enable_chaining: bool\):(.*?)\n    def ",
        _MAIN_WINDOW, re.DOTALL)
    assert match, "_translate_and_narrate não encontrado"
    body = match.group(1)
    # As DUAS chamadas a narrate_text (já-em-PT e pós-tradução) repassam a flag.
    assert body.count("chain_continuous=enable_chaining") == 2


def test_error_path_does_not_chain_next_page():
    """No erro de tradução, o loop contínuo traduzido deve morrer (ADR-005) —
    _on_error não pode chamar narrate_text/emitir nova tradução."""
    match = re.search(
        r"def _translate_and_narrate\(self, text: str, enable_chaining: bool\):(.*?)\n    def ",
        _MAIN_WINDOW, re.DOTALL)
    body = match.group(1)
    on_error_match = re.search(r"def _on_error\(err: str\):(.*?)(?=\n\s*def |\n\s*try:)",
                               body, re.DOTALL)
    assert on_error_match
    assert "narrate_text" not in on_error_match.group(1)
