"""Testes da Tarefa 1.4 (botão único de áudio: Ouvir/Parar/Configurar vozes).

reader_view.py não pode ser importado depois de existir uma QApplication (puxa
QtWebEngine) — ver tests/test_reader_view_guards.py. Checagens ESTÁTICAS do
código-fonte, mesmo padrão de test_reader_view_guards.py.
"""
import re
from pathlib import Path

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


def _src() -> str:
    return _READER_VIEW.read_text(encoding="utf-8")


def _method_body(src: str, name: str) -> str:
    # Não assume "):" logo após a lista de parâmetros — alguns métodos têm
    # anotação de retorno (-> None) ou assinatura em várias linhas.
    m = re.search(rf"def {name}\(.*?\n(?=    def )", src, re.DOTALL)
    assert m, f"método {name} não encontrado"
    return m.group(0)


# ── Estrutura do botão-menu único ──────────────────────────────────────────

def test_audio_button_is_toolbutton_with_menu_button_popup():
    src = _src()
    assert "self._audio_btn = QToolButton()" in src
    assert "QToolButton.ToolButtonPopupMode.MenuButtonPopup" in src


def test_audio_menu_has_toggle_stop_separator_settings():
    src = _src()
    assert "self._audio_menu = QMenu(self._audio_btn)" in src
    assert "self._act_audio_toggle" in src
    assert "self._act_audio_stop" in src
    assert "self._act_audio_settings" in src
    assert "self._audio_menu.addAction(self._act_audio_toggle)" in src
    assert "self._audio_menu.addAction(self._act_audio_stop)" in src
    assert "self._audio_menu.addSeparator()" in src
    assert "self._audio_menu.addAction(self._act_audio_settings)" in src
    assert "self._audio_btn.setMenu(self._audio_menu)" in src


def test_audio_button_body_click_still_toggles_directly():
    """Clique no CORPO do botão continua chamando _toggle_audio diretamente
    (1 clique, sem precisar abrir o menu) — preserva o comportamento anterior."""
    src = _src()
    assert "self._audio_btn.clicked.connect(self._toggle_audio)" in src


def test_stop_action_starts_disabled_and_toggles_via_setEnabled():
    """Antes: _audio_stop_btn.setVisible(...). Agora: _act_audio_stop.setEnabled(...)
    (só habilitado durante reprodução/pausa) — conforme pedido no contrato."""
    src = _src()
    assert 'self._act_audio_stop.setEnabled(False)' in src
    assert 'self._act_audio_stop.setEnabled(True)' in src
    # o widget antigo não deve mais ser referenciado como atributo vivo
    assert "self._audio_stop_btn." not in src


def test_old_tts_settings_button_widget_removed():
    """_tts_settings_btn (state-holder nunca exibido) foi removido — a ação
    'Configurar vozes…' do novo menu cobre o mesmo caso de uso."""
    src = _src()
    assert "self._tts_settings_btn =" not in src
    assert "self._tts_settings_btn." not in src


# ── Preservação do comportamento existente ─────────────────────────────────

def test_preserved_public_behaviors():
    src = _src()
    for name in (
        "_toggle_audio", "_stop_audio_if_running", "_on_tts_settings_clicked",
        "_pause_audio", "_resume_audio", "_on_audio_started",
        "_on_audio_worker_finished", "_on_audio_provider_changed",
    ):
        assert f"def {name}(" in src, f"{name} não deve ter sido removido"


def test_state_transitions_update_button_and_menu_item_together():
    """Cada transição (pausar/retomar/tocando/parado) atualiza o botão E o
    item 'Ouvir página' do menu através do helper único _set_audio_button_state."""
    src = _src()
    assert "_set_audio_button_state" in src
    assert '_set_audio_button_state("Retomar", "▶️", "Continuar Leitura (TTS)")' in _method_body(src, "_pause_audio")
    assert '_set_audio_button_state("Pausar", "⏸️", "Pausar Leitura (TTS)")' in _method_body(src, "_resume_audio")
    assert '_set_audio_button_state("Pausar", "⏸️", "Pausar Leitura (TTS)")' in _method_body(src, "_on_audio_started")
    assert 'menu_label="Ouvir página"' in _method_body(src, "_on_audio_worker_finished")
    assert 'menu_label="Ouvir página"' in _method_body(src, "_stop_audio_if_running")


def test_helper_updates_menu_action_text_with_inline_emoji():
    """O padrão dos demais QAction do arquivo (ex.: _act_double_page) embute o
    emoji no TEXTO, ao invés de usar setIcon — o helper segue essa convenção
    para o item de menu, enquanto o botão continua usando emoji_icon()."""
    src = _src()
    body = _method_body(src, "_set_audio_button_state")
    assert "self._audio_btn.setIcon(emoji_icon(icon_emoji))" in body
    assert 'self._act_audio_toggle.setText(f"{icon_emoji} {menu_label or label}")' in body


def test_audio_menu_has_explicit_original_translated_pair():
    """Par explícito "Ouvir original / Ouvir traduzido" (descobribilidade —
    sugestão registrada em 2026-07-17): as mesmas QActions entram nos DOIS
    menus (padrão do compartilhamento de ações de tradução)."""
    src = _src()
    assert 'self._act_listen_original = QAction("🔊 Ouvir original", self)' in src
    assert "self._act_listen_original.triggered.connect(self._on_listen_original)" in src
    assert 'QAction("🌐 Ouvir traduzido (PT)", self)' in src
    assert "self._audio_menu.addAction(self._act_listen_original)" in src
    assert "self._audio_menu.addAction(self._act_read_translated)" in src
    assert "self._overflow_menu.addAction(self._act_listen_original)" in src
    assert "self._overflow_menu.addAction(self._act_read_translated)" in src


def test_listen_original_delegates_to_shared_helpers():
    """'Ouvir original' reutiliza _current_page_text() (extração) e
    narrate_text() (stop+launch), em vez de re-implementar os dois caminhos.
    chain_continuous=True: a narração é do original DESTA página, mas a
    continuidade segue os toggles (desligados → nada encadeia)."""
    src = _src()
    body = _method_body(src, "_on_listen_original")
    assert "self._current_page_text().strip()" in body
    assert "self.narrate_text(page_text, chain_continuous=True)" in body


def test_anchor_fallback_no_longer_uses_removed_widget():
    """O menu rápido de TTS (_on_tts_settings_clicked) usava _tts_settings_btn
    como âncora de fallback; agora usa o próprio _audio_btn (sempre visível)."""
    src = _src()
    body = _method_body(src, "_on_tts_settings_clicked")
    assert 'getattr(self, "_overflow_btn", None) or self._audio_btn' in body
