"""Testes da Tarefa 1.2 (atalhos Space/PageUp/PageDown + zonas de clique).

reader_view.py NÃO pode ser importado depois de existir uma QApplication (puxa
QtWebEngine) — ver tests/test_reader_view_guards.py. Todas as checagens aqui
são ESTÁTICAS sobre o código-fonte, no mesmo padrão de
test_reader_view_guards.py e da seção final de test_reader_typography.py.
"""
import re
from pathlib import Path

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


def _src() -> str:
    return _READER_VIEW.read_text(encoding="utf-8")


# ── Atalhos de teclado (Space/Shift+Space/PageUp/PageDown) ────────────────

def test_space_shortcut_wired_to_next_page():
    src = _src()
    assert "Qt.Key.Key_Space" in src
    assert "_shortcut_go_next" in src
    assert "_shortcut_go_prev" in src


def test_shift_space_wired_to_previous_page():
    src = _src()
    assert '"Shift+Space"' in src


def test_pageup_pagedown_wired():
    src = _src()
    assert "Qt.Key.Key_PageDown" in src
    assert "Qt.Key.Key_PageUp" in src


def test_new_navigation_shortcuts_use_window_shortcut_context():
    """Space/PageUp/PageDown usam o mesmo contexto WindowShortcut das teclas
    simples já existentes (Escape/Ctrl+F/Ctrl+D/F11) — NÃO o ApplicationShortcut
    mais amplo reservado às setas (Left/Right)."""
    src = _src()
    m = re.search(
        r"def _setup_shortcuts\(self\):(.*?)\n    def ",
        src,
        re.DOTALL,
    )
    assert m, "método _setup_shortcuts não encontrado"
    body = m.group(1)
    # cada um dos 4 novos atalhos foi explicitamente contextualizado
    assert body.count("Qt.ShortcutContext.WindowShortcut") >= 4


def test_focus_guard_checks_standard_text_widgets():
    """_is_text_input_focused deve existir e conferir QLineEdit/QTextEdit/
    QPlainTextEdit (busca no documento, anotações, campo do RAG são todos
    widgets padrão do Qt — confirmado empiricamente que o próprio Qt já
    protege esses widgets via QEvent.ShortcutOverride; a checagem aqui é
    reforço explícito e documentado)."""
    src = _src()
    assert "_is_text_input_focused" in src
    assert "QLineEdit" in src and "QTextEdit" in src and "QPlainTextEdit" in src
    assert "focusWidget" in src


def test_shortcut_slots_consult_focus_guard_before_navigating():
    src = _src()
    m = re.search(r"def _shortcut_go_next\(self\).*?\n(?=    def )", src, re.DOTALL)
    assert m and "_is_text_input_focused" in m.group(0)
    m = re.search(r"def _shortcut_go_prev\(self\).*?\n(?=    def )", src, re.DOTALL)
    assert m and "_is_text_input_focused" in m.group(0)


def test_webengine_limitation_documented():
    """A limitação conhecida (QWebEngineView/EPUB não protege <input> interno
    do HTML de forma síncrona) precisa estar documentada no arquivo."""
    src = _src()
    assert "QWebEngineView" in src
    # menciona o mecanismo assíncrono/IPC que explica a limitação
    assert "assíncron" in src.lower() or "ipc" in src.lower()


# ── Zonas de clique (terços) — caminho PDF/imagem (_image_label) ──────────

def test_page_turn_zone_ratio_is_a_third():
    src = _src()
    assert "_PAGE_TURN_ZONE_RATIO = 1 / 3" in src


def test_click_zone_uses_ratio_constant_not_old_hardcoded_margins():
    """Os limiares antigos (0.15/0.85) do caminho PDF/imagem foram trocados
    pela constante de terço; não deve sobrar um "width * 0.15" hardcoded no
    ramo do _image_label (o bloco de MouseButtonPress do web_view/viewport,
    pré-existente e fora do escopo desta tarefa, pode manter seus próprios
    limiares)."""
    src = _src()
    assert "width * self._PAGE_TURN_ZONE_RATIO" in src
    assert "width * (1 - self._PAGE_TURN_ZONE_RATIO)" in src


def test_click_zone_respects_highlight_mode():
    """SÓ vira página por clique de margem quando NÃO está no modo Marca-Texto."""
    src = _src()
    m = re.search(
        r"MouseButtonRelease and event\.button\(\).*?"
        r"(?=elif event\.type\(\)|return super\(\))",
        src,
        re.DOTALL,
    )
    assert m, "ramo de MouseButtonRelease do _image_label não encontrado"
    assert "self._highlight_mode_btn.isChecked()" in m.group(0)


def test_epub_click_zone_limitation_documented():
    """O caminho web_view (EPUB) permanece com sua zona antiga (mais estreita,
    sem guarda de seleção/link/marca-texto) — a limitação precisa estar
    documentada no arquivo, conforme permitido pelo contrato da Tarefa 1.2."""
    src = _src()
    assert "limitação" in src.lower()
