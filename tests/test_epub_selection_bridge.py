"""Testes da ponte de seleção do EPUB (débito 3.4 / rodada B3; barra de ações
do EPUB na rodada UX ago/2026).

O módulo ``epub_selection_bridge`` importa só ``PyQt6.QtCore`` (não
``QtWebEngineWidgets``), então roda na suíte normal. O ``ReaderView`` completo
NÃO instancia aqui (QtWebEngine), mas seus métodos de decisão rodam de verdade
num harness com os métodos REAIS ligados a um stub (mesmo padrão de
``test_reading_timer_pause.py``) — ver a segunda seção. O que sobra de fiação
(quem chama quem dentro do widget) segue coberto por inspeção estática em
``test_reader_view_guards.py``.
"""
import pytest

from src.gui.reader_view import ReaderView
from src.gui.widgets.epub_selection_bridge import (
    EpubSelectionBridge, EPUB_SELECTION_JS,
)


# ── EpubSelectionBridge (slot → sinal) ──────────────────────────────────

def test_bridge_emits_text_and_rect(qtbot):
    bridge = EpubSelectionBridge()
    got = []
    bridge.selection_ended.connect(lambda t, r: got.append((t, r)))
    bridge.on_selection_end("entropia", '{"x":10,"bottom":50}')
    assert got == [("entropia", '{"x":10,"bottom":50}')]


def test_bridge_empty_selection_emits_empty_strings(qtbot):
    bridge = EpubSelectionBridge()
    got = []
    bridge.selection_ended.connect(lambda t, r: got.append((t, r)))
    bridge.on_selection_end("", "")
    assert got == [("", "")]


def test_bridge_slot_is_registered_qt_slot():
    # O método precisa ser um pyqtSlot(str, str) para o QWebChannel expô-lo.
    from PyQt6.QtCore import pyqtSlot  # noqa: F401
    assert hasattr(EpubSelectionBridge, "on_selection_end")


# ── EPUB_SELECTION_JS (contrato do JS injetado) ─────────────────────────

def test_js_wires_mouseup_and_reads_selection():
    js = EPUB_SELECTION_JS
    assert "mouseup" in js
    assert "getSelection" in js
    assert "getBoundingClientRect" in js


def test_js_uses_qwebchannel_and_matching_names():
    js = EPUB_SELECTION_JS
    # Deve casar com o registerObject("epubBridge") e o slot on_selection_end.
    assert "QWebChannel" in js
    assert "qt.webChannelTransport" in js
    assert "epubBridge" in js
    assert "on_selection_end" in js


def test_js_loads_qwebchannel_resource():
    # Página via setHtml (about:blank) não traz qwebchannel.js — precisa do qrc.
    assert "qrc:///qtwebchannel/qwebchannel.js" in EPUB_SELECTION_JS


def test_js_is_idempotent_per_document():
    # loadFinished pode disparar mais de uma vez para o mesmo doc — a guarda
    # evita listeners de mouseup duplicados.
    assert "__epubWW" in EPUB_SELECTION_JS


def test_js_reports_rect_bottom_for_anchor():
    # O anchor do popover usa rect.bottom (borda inferior da seleção).
    assert "bottom" in EPUB_SELECTION_JS


# ── Roteamento da seleção no ReaderView (harness com métodos REAIS) ─────
# Paridade PDF↔EPUB (rodada UX ago/2026): trecho longo abre a mesma barra de
# ações do PDF; termo curto continua indo direto para a Definição rápida.

_RECT = '{"x":10,"bottom":50}'


class _FakePopover:
    """Duplo do SelectionActionPopover/WordWisePopover (só o que o handler usa)."""

    def __init__(self):
        self.actions: list | None = None
        self.anchor = None
        self.visible = False
        self.hide_calls = 0

    def set_actions(self, keys) -> None:
        self.actions = list(keys)

    def show_at(self, pos) -> None:
        self.anchor = pos
        self.visible = True

    def hide(self) -> None:
        self.visible = False
        self.hide_calls += 1


class _FakeSignal:
    def __init__(self, sink: list):
        self._sink = sink

    def emit(self, *args) -> None:
        self._sink.append(args)


class _SelectionHarness:
    """Stub do ReaderView com os métodos REAIS de decisão da seleção.

    ``_epub_selection_anchor`` (matemática de zoom/viewport, validada no spike
    B3 e por inspeção estática) é substituído por um valor controlado: aqui
    interessa o ROTEAMENTO — curto vs. longo, âncora do bridge vs. cursor.
    """

    _WORD_WISE_MAX_WORDS = ReaderView._WORD_WISE_MAX_WORDS
    _EPUB_SELECTION_ACTIONS = ReaderView._EPUB_SELECTION_ACTIONS
    _on_epub_selection_ended = ReaderView._on_epub_selection_ended
    _show_epub_selection_popover = ReaderView._show_epub_selection_popover
    _dismiss_selection_ui = ReaderView._dismiss_selection_ui
    _on_selection_popover_action = ReaderView._on_selection_popover_action

    def __init__(self, anchor="anchor-do-bridge"):
        self._selection_popover = _FakePopover()
        self._word_wise_popover = _FakePopover()
        self._last_epub_selection = ""
        self._last_selection_anchor = None
        self._last_selection_coords = None   # caminho PDF: sem seleção ativa
        self._anchor = anchor
        self.word_wise_calls: list[str] = []
        self.ai_actions: list[tuple] = []
        self.mapped_from_global: list = []
        self.ai_action_requested = _FakeSignal(self.ai_actions)

    # — Colaboradores substituídos —
    def _epub_selection_anchor(self, rect_json):
        return self._anchor if rect_json else None

    def _start_word_wise(self, term):
        self.word_wise_calls.append(term)

    def mapFromGlobal(self, pos):
        self.mapped_from_global.append(pos)
        return "anchor-do-cursor"

    def _hide_selection_marquee(self):
        pass


@pytest.fixture
def harness(qtbot):
    """Harness já ligado a uma ponte REAL (sinal do bridge → handler real)."""
    h = _SelectionHarness()
    bridge = EpubSelectionBridge()
    bridge.selection_ended.connect(h._on_epub_selection_ended)
    h.bridge = bridge
    return h


def test_long_selection_opens_action_popover(harness):
    """Trecho longo no EPUB abre a MESMA barra de ações do PDF."""
    texto = "a entropia de um sistema isolado nunca diminui com o tempo"
    harness.bridge.on_selection_end(texto, _RECT)

    pop = harness._selection_popover
    assert pop.visible is True
    assert harness._last_epub_selection == texto
    # Nada de Word Wise: trecho não é termo.
    assert harness.word_wise_calls == []


def test_long_selection_popover_offers_simplify_and_ai_actions(harness):
    harness.bridge.on_selection_end("um trecho bem longo com varias palavras aqui", _RECT)

    actions = harness._selection_popover.actions
    assert set(actions) == {"explain", "simplify", "translate", "search",
                            "save_note", "flashcard"}
    # Simplificar (Q.3) é o botão de TRECHO — é ele que faltava no EPUB.
    assert "simplify" in actions
    # Destacar exige coords de página (só PDF re-desenha destaques) e a
    # Definição rápida é do termo curto — nenhum dos dois entra na barra.
    assert "highlight" not in actions
    assert "word_wise" not in actions


def test_popover_actions_exist_in_the_real_widget():
    """As chaves da barra do EPUB são de fato botões do SelectionActionPopover."""
    from src.gui.widgets.selection_popover import SelectionActionPopover
    validas = {key for _icon, _label, key in SelectionActionPopover._ACTIONS}
    assert set(ReaderView._EPUB_SELECTION_ACTIONS) <= validas


def test_short_selection_triggers_word_wise_without_the_bar(harness):
    """Termo curto continua indo direto para a Definição rápida."""
    harness.bridge.on_selection_end("entropia", _RECT)

    assert harness.word_wise_calls == ["entropia"]
    assert harness._selection_popover.visible is False
    assert harness._last_epub_selection == ""
    assert harness._last_selection_anchor == "anchor-do-bridge"


def test_short_selection_without_anchor_does_not_open_word_wise(harness):
    """Seleção rolada para fora da vista: nada de cartão solto (comportamento
    do B3 preservado — o fallback no cursor é só da barra de ações)."""
    harness.bridge.on_selection_end("entropia", "")
    assert harness.word_wise_calls == []


def test_empty_selection_dismisses_open_bar(harness):
    """Clique simples (seleção perdida) fecha a barra e esquece o texto."""
    harness.bridge.on_selection_end("um trecho longo o bastante para a barra", _RECT)
    assert harness._selection_popover.visible is True

    harness.bridge.on_selection_end("", "")
    assert harness._selection_popover.visible is False
    assert harness._word_wise_popover.visible is False
    assert harness._last_epub_selection == ""


def test_new_selection_replaces_the_previous_one(harness):
    harness.bridge.on_selection_end("primeiro trecho longo com varias palavras", _RECT)
    harness.bridge.on_selection_end("segundo trecho longo com varias palavras", _RECT)
    assert harness._last_epub_selection == "segundo trecho longo com varias palavras"
    assert harness._selection_popover.hide_calls >= 2  # 1 por seleção nova


def test_anchor_prefers_the_bridge_rect(harness):
    harness.bridge.on_selection_end("um trecho longo o bastante para a barra", _RECT)
    assert harness._selection_popover.anchor == "anchor-do-bridge"
    assert harness.mapped_from_global == []  # não precisou do cursor


def test_anchor_falls_back_to_cursor_when_rect_is_unusable(harness):
    """Rect vazio/fora da vista: ancora no cursor (o mouseup acabou de ocorrer
    ali) em vez de engolir a seleção do usuário."""
    harness.bridge.on_selection_end("um trecho longo o bastante para a barra", "")
    assert harness._selection_popover.visible is True
    assert harness._selection_popover.anchor == "anchor-do-cursor"
    assert len(harness.mapped_from_global) == 1  # QCursor.pos()


def test_popover_action_emits_ai_action_with_the_epub_text(harness):
    harness.bridge.on_selection_end("um trecho longo o bastante para a barra", _RECT)
    harness._on_selection_popover_action("simplify")

    assert harness.ai_actions == [
        ("simplify", "um trecho longo o bastante para a barra")]
    # Consumida: um segundo clique não repete a ação sobre texto velho.
    assert harness._last_epub_selection == ""
    harness._on_selection_popover_action("explain")
    assert len(harness.ai_actions) == 1


def test_popover_action_without_epub_selection_uses_pdf_path(harness):
    """Sem seleção de EPUB pendente, o handler segue pelo caminho PDF (que,
    sem coords, apenas não faz nada) — o ramo novo não sequestra o PDF."""
    harness._on_selection_popover_action("explain")
    assert harness.ai_actions == []


def test_dismiss_closes_both_popovers_and_clears_state(harness):
    """Ciclo de vida: troca de página/livro chama este método (ver
    _render_page/_go_to_page em test_reader_view_guards)."""
    harness.bridge.on_selection_end("um trecho longo o bastante para a barra", _RECT)
    harness._word_wise_popover.visible = True

    harness._dismiss_selection_ui()

    assert harness._selection_popover.visible is False
    assert harness._word_wise_popover.visible is False
    assert harness._last_epub_selection == ""
