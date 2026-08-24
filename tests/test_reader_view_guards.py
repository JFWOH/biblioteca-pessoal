"""Guardas de regressão do ReaderView (checagens estáticas, sem importar Qt).

Não importa o módulo: o reader_view puxa QtWebEngineWidgets, que só pode ser
importado ANTES de existir um QApplication — em suíte cheia (qtbot já criou a
app) o import falharia. Lê o código-fonte direto do disco.
"""
import re
from pathlib import Path

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


def test_current_page_text_method_not_shadowed_by_attribute():
    """Regressão: um atributo self._current_page_text criado no __init__
    sombreava o MÉTODO homônimo e quebrava o menu de estudo com
    "TypeError: 'str' object is not callable" (reader_view._open_study_menu).
    """
    src = _READER_VIEW.read_text(encoding="utf-8")
    # Método deve existir…
    assert re.search(r"def _current_page_text\(self\)", src)
    # …e nenhum ATRIBUTO homônimo pode ser atribuído ([:=] pega "= x" e ": str = x";
    # [^=] exclui comparações "==").
    assert not re.search(r"self\._current_page_text\s*[:=][^=]", src), (
        "atributo self._current_page_text sombrearia o método homônimo "
        "(use outro nome, ex.: _last_page_text)"
    )


# ── Word Wise no EPUB (débito 3.4 / rodada B3) — fiação estática ─────────
# reader_view importa QtWebEngine; a fiação é verificada lendo o fonte, no
# mesmo padrão acima (a ponte em si é testada em test_epub_selection_bridge).

def _reader_src() -> str:
    return _READER_VIEW.read_text(encoding="utf-8")


def test_epub_bridge_is_wired_to_webchannel():
    """A ponte de seleção do EPUB é registrada no QWebChannel da página."""
    src = _reader_src()
    assert "EpubSelectionBridge" in src
    assert "setWebChannel" in src
    assert 'registerObject("epubBridge"' in src
    # O nome registrado tem de bater com o usado no JS injetado.
    from src.gui.widgets.epub_selection_bridge import EPUB_SELECTION_JS
    assert "epubBridge" in EPUB_SELECTION_JS


def test_epub_selection_js_reinjected_on_load_finished():
    """setHtml troca o documento a cada página; o JS é re-injetado no load."""
    src = _reader_src()
    assert "loadFinished.connect(self._inject_epub_selection_js)" in src
    assert "def _inject_epub_selection_js" in src
    assert "runJavaScript(EPUB_SELECTION_JS)" in src


def test_epub_selection_routes_short_selection_to_word_wise():
    """Seleção curta no EPUB dispara o Word Wise; longa é ignorada nesta rodada."""
    src = _reader_src()
    handler = re.search(r"def _on_epub_selection_ended\(self.*?\n    def ",
                        src, re.DOTALL).group(0)
    assert "selection_ended.connect(self._on_epub_selection_ended)" in src
    assert "_WORD_WISE_MAX_WORDS" in handler
    assert "_start_word_wise" in handler


def test_epub_selection_anchor_accounts_for_zoom():
    """O anchor converte coords CSS→widget usando o zoomFactor (não crasha)."""
    src = _reader_src()
    anchor = re.search(r"def _epub_selection_anchor\(self.*?\n    def ",
                       src, re.DOTALL).group(0)
    assert "zoomFactor" in anchor
    assert "mapTo" in anchor


# ── Ação "Simplificar" (Q.3 / candidato N.4) — fiação estática ───────────

def test_selection_menu_offers_simplify_in_ptbr():
    """"Simplificar" no menu de contexto das ações de seleção.

    Segue o padrão das existentes: um QAction que emite ai_action_requested
    com a chave da ação — nenhum worker novo.
    """
    src = _reader_src()
    menu = re.search(r"def _populate_ai_menu\(self.*?\n    def ", src,
                     re.DOTALL).group(0)
    assert "Simplificar" in menu
    assert 'ai_action_requested.emit("simplify", text)' in menu
    assert "menu.addAction(action_simplify)" in menu


def test_selection_popover_includes_simplify_action():
    """A barra flutuante (PDF) também oferece Simplificar, ao lado de Explicar."""
    src = _reader_src()
    show = re.search(r"def _show_selection_popover\(self.*?\n    def ", src,
                     re.DOTALL).group(0)
    assert '"simplify"' in show
    # Excludente do Word Wise: seleção curta → definição; trecho → simplificar.
    # Sem isso a barra iria a 8 botões (~1180px) e cortaria em notebook 13".
    assert 'actions.append("word_wise")' in show
    assert 'actions.insert(2, "simplify")' in show
    # Cai no fallback genérico (emite ai_action_requested), igual ao Explicar:
    # nenhum ramo dedicado no handler — é isso que evita um worker novo.
    handler = re.search(r"def _on_selection_popover_action\(self.*?\n    def ",
                        src, re.DOTALL).group(0)
    assert '"simplify"' not in handler
    assert "ai_action_requested.emit(action, text)" in handler
