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
    # Achado B0: o fork traduzido agora é guardado pelo override "Ouvir original".
    fork_idx = body.index(
        "if self._continuous_translate_mode and not self._listen_original_override:")
    launch_idx = body.index("self._launch_audio_worker(page_text, chain_continuous=True)")
    assert pause_idx < fork_idx < launch_idx  # fork vem depois do pause/resume, antes do launch direto
    assert (
        'self.ai_action_requested.emit("read_translated_page_chained", page_text)' in body
    )


def test_narrate_text_accepts_and_propagates_chain_continuous():
    # Rodada 2 (TTS): a assinatura ganhou o parâmetro opcional ``language``
    # (idioma-alvo explícito da tradução) — a regex tolera parâmetros extras,
    # mantendo a garantia original: aceita E propaga chain_continuous.
    match = re.search(
        r"def narrate_text\(self, text: str, chain_continuous: bool = False,?"
        r"[^)]*\) -> None:(.*?)\n    def ",
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


def test_continue_narration_chains_translated_mode_independently():
    """Regressão: _continue_narration exigia _continuous_reading e matava a
    cadeia quando SÓ a leitura contínua TRADUZIDA estava ligada — o loop
    traduzido morria em silêncio após a 1ª página. A guarda deve aceitar
    qualquer um dos dois modos, como _on_audio_finished já promete."""
    match = re.search(r"def _continue_narration\(self\):(.*?)\n    def ",
                      _READER_VIEW, re.DOTALL)
    assert match, "_continue_narration não encontrado"
    body = match.group(1)
    assert "if not (self._continuous_reading or self._continuous_translate_mode):" in body


def test_continue_narration_skips_presynth_cache_in_translate_mode():
    """A pré-síntese guarda áudio do idioma ORIGINAL (só o modo normal a
    produz); no modo traduzido a cadeia deve ignorar o cache — senão um
    resto pré-sintetizado antes de ligar o modo tocaria a página SEM
    tradução."""
    match = re.search(r"def _continue_narration\(self\):(.*?)\n    def ",
                      _READER_VIEW, re.DOTALL)
    body = match.group(1)
    take_idx = body.index("self._presynth_cache.take(")
    guard_idx = body.index("if not self._continuous_translate_mode:")
    assert guard_idx < take_idx


def test_enabling_translate_mode_invalidates_presynth():
    """Ligar a leitura contínua traduzida descarta a pré-síntese pendente
    (áudio do original não vale para o modo traduzido)."""
    match = re.search(
        r"def _toggle_continuous_translate_reading\(self, checked: bool\):(.*?)\n    def ",
        _READER_VIEW, re.DOTALL)
    assert "self._invalidate_presynth()" in match.group(1)


# ── Achado B0: override de sessão "Ouvir original" ────────────────────
#
# "Ouvir original" com a Leitura Contínua Traduzida ligada deve SEGUIR no
# original até o usuário parar (antes: one-shot que voltava a traduzir). Guardas
# estruturais dos pontos de set/consult/clear (ReaderView não instancia na suíte
# por causa do QtWebEngine — mesmo padrão dos testes acima). O comportamento
# encadeado é coberto também por test_listen_original_override.py (harness).


def _body(name: str, sig: str = r"self\)") -> str:
    m = re.search(rf"def {name}\({sig}[^\n]*:(.*?)\n    def ", _READER_VIEW, re.DOTALL)
    assert m, f"{name} não encontrado"
    return m.group(1)


def test_override_flag_initialized():
    assert "self._listen_original_override: bool = False" in _READER_VIEW


def test_listen_original_sets_override():
    body = _body("_on_listen_original")
    assert "self._listen_original_override = True" in body
    # A ordem importa: o override é setado ANTES de narrar.
    assert body.index("self._listen_original_override = True") < body.index(
        "self.narrate_text(page_text, chain_continuous=True)")


def test_toggle_audio_consults_override():
    body = _body("_toggle_audio")
    assert (
        "if self._continuous_translate_mode and not self._listen_original_override:"
        in body)


def test_manual_stop_clears_override_via_dedicated_handler():
    # O botão ⏹️ passa por _on_audio_stop_clicked (limpa o override) e NÃO
    # direto por _stop_audio_if_running (que é chamado em transições internas).
    assert (
        "self._act_audio_stop.triggered.connect(self._on_audio_stop_clicked)"
        in _READER_VIEW)
    body = _body("_on_audio_stop_clicked")
    assert "self._listen_original_override = False" in body
    assert "self._stop_audio_if_running()" in body


def test_stop_audio_if_running_does_not_touch_override():
    # Crítico: _stop_audio_if_running é chamado ao virar página NA cadeia e por
    # narrate_text; se limpasse o override, a própria cadeia o apagaria.
    body = _body("_stop_audio_if_running")
    assert "_listen_original_override" not in body


def test_read_translated_clears_override():
    body = _body("_on_read_translated_page")
    assert "self._listen_original_override = False" in body


def test_toggle_translate_reading_clears_override():
    body = _body("_toggle_continuous_translate_reading", sig=r"self, checked: bool\)")
    assert "self._listen_original_override = False" in body


def test_book_switch_and_teardown_clear_override():
    assert "self._listen_original_override = False  # troca de livro reseta o override (B0)" in _READER_VIEW
    assert "self._listen_original_override = False  # fechar leitor reseta o override (B0)" in _READER_VIEW


def test_persisted_translate_toggle_key_unchanged():
    # O override NÃO altera o toggle persistido (garantia explícita do achado).
    assert _READER_VIEW.count('config.set("tts.continuous_translate_reading"') == 1


def test_delayed_translation_result_is_discarded_by_narration_epoch():
    """Corrida: com a tradução NLLB em andamento, o usuário inicia OUTRA
    narração (ex.: 'Ouvir original'); o resultado atrasado não pode
    atropelá-la. A época é capturada no pedido e conferida no sucesso; toda
    narração nova (normal e pré-sintetizada) avança a época."""
    match = re.search(
        r"def _translate_and_narrate\(self, text: str, enable_chaining: bool\):(.*?)\n    def ",
        _MAIN_WINDOW, re.DOTALL)
    body = match.group(1)
    assert "epoch_at_request = self._reader_view.narration_epoch" in body
    assert "self._reader_view.narration_epoch != epoch_at_request" in body
    assert _READER_VIEW.count("self.narration_epoch += 1") == 2  # _launch_audio_worker e _play_prepared


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
    # As TRÊS chamadas a narrate_text (já-em-PT, HIT do cache — rodada B1 —
    # e pós-tradução) repassam a flag.
    assert body.count("chain_continuous=enable_chaining") == 3


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
