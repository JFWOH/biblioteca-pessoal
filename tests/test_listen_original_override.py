"""Achado B0 — override de sessão "Ouvir original".

Com a Leitura Contínua Traduzida ligada, "Ouvir original" deve fazer a leitura
contínua SEGUIR no idioma original até o usuário parar (antes: one-shot que
voltava a traduzir na página seguinte). Um flag de sessão
``_listen_original_override`` faz o encadeamento (``_toggle_audio``) pular a
tradução enquanto vive; é limpo em stop manual, "Ouvir traduzido", mudança do
toggle de Leitura Contínua Traduzida e troca/fechamento de livro.

Como o ReaderView completo não instancia na suíte (QtWebEngine), montamos um
harness com os métodos REAIS ligados (mesmo padrão de test_audio_stop_async) e
stubamos só os colaboradores. Guardas ESTRUTURAIS complementares (set/clear em
open_book/close_reader etc.) vivem em test_continuous_translated_reading_wiring.
"""
from unittest.mock import MagicMock

from src.gui.reader_view import ReaderView


class _FakeReader:
    current_page = 3

    def get_page_text(self, page):
        return f"Texto original da página {page}"


class _Harness:
    # Métodos REAIS sob teste (unbound → chamados com self=harness).
    _on_listen_original = ReaderView._on_listen_original
    narrate_text = ReaderView.narrate_text
    _toggle_audio = ReaderView._toggle_audio
    _on_read_translated_page = ReaderView._on_read_translated_page
    _toggle_continuous_translate_reading = ReaderView._toggle_continuous_translate_reading
    _on_audio_stop_clicked = ReaderView._on_audio_stop_clicked

    def __init__(self, translate_mode=False, override=False):
        self._reader = _FakeReader()
        self._continuous_translate_mode = translate_mode
        self._continuous_reading = False
        self._listen_original_override = override
        self._audio_worker = None
        self._audio_paused = False
        self.ai_action_requested = MagicMock()
        self.launched = []       # (text, chain_continuous)
        self.stopped = 0
        self.begin_feedback = 0
        self.status = []

    # ── colaboradores stubados ────────────────────────────────────────
    def _current_page_text(self):
        return "Texto original da página atual"

    def _launch_audio_worker(self, text, chain_continuous=False, language=None):
        self.launched.append((text, chain_continuous))

    def _stop_audio_if_running(self):
        # Emula o REAL no que importa aqui: NÃO limpa o override (invariante).
        self.stopped += 1
        self._audio_worker = None

    def _begin_translation_feedback(self):
        self.begin_feedback += 1

    def _show_status(self, msg, ms=4000):
        self.status.append(msg)

    def _invalidate_presynth(self):
        pass

    def window(self):
        return None  # config None → toggle não persiste (irrelevante ao teste)


# ── set do override ───────────────────────────────────────────────────

def test_listen_original_sets_override_and_survives_internal_stop():
    h = _Harness(translate_mode=True)
    h._on_listen_original()
    # Override ligado E preservado através do _stop_audio_if_running interno
    # que a narrate_text dispara antes de lançar.
    assert h._listen_original_override is True
    assert h.stopped == 1
    assert h.launched == [("Texto original da página atual", True)]
    # Narrou o ORIGINAL: não passou pela tradução.
    h.ai_action_requested.emit.assert_not_called()


# ── consulta do override no encadeamento ──────────────────────────────

def test_toggle_audio_skips_translation_when_override_active():
    h = _Harness(translate_mode=True, override=True)
    h._toggle_audio()
    # Narrou o original (launch direto), NÃO a tradução.
    assert h.launched == [("Texto original da página 3", True)]
    h.ai_action_requested.emit.assert_not_called()
    assert h.begin_feedback == 0


def test_toggle_audio_translates_when_override_inactive():
    h = _Harness(translate_mode=True, override=False)
    h._toggle_audio()
    # Sem override, o modo traduzido segue traduzindo.
    assert h.launched == []
    h.ai_action_requested.emit.assert_called_once_with(
        "read_translated_page_chained", "Texto original da página 3")
    assert h.begin_feedback == 1


# ── clear do override ─────────────────────────────────────────────────

def test_manual_stop_clears_override():
    h = _Harness(translate_mode=True, override=True)
    h._on_audio_stop_clicked()
    assert h._listen_original_override is False
    assert h.stopped == 1  # delega ao stop assíncrono real


def test_read_translated_clears_override():
    h = _Harness(translate_mode=True, override=True)
    h._on_read_translated_page()
    assert h._listen_original_override is False
    h.ai_action_requested.emit.assert_called_once_with(
        "read_translated_page", "Texto original da página 3")


def test_toggle_translate_reading_clears_override_both_directions():
    h = _Harness(translate_mode=True, override=True)
    h._toggle_continuous_translate_reading(False)
    assert h._listen_original_override is False
    assert h._continuous_translate_mode is False
    h2 = _Harness(translate_mode=False, override=True)
    h2._toggle_continuous_translate_reading(True)
    assert h2._listen_original_override is False
    assert h2._continuous_translate_mode is True
