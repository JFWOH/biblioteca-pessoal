"""Testes de acessibilidade mínima (Onda 4, item 4.5).

Cobertura:
- ``LibraryView``: widget leve → instanciado ao vivo (pytest-qt). Verifica
  ``accessibleName`` nos controles só-ícone do header (grade/lista/quebrados/
  ordem) e a ordem de tabulação curada dessa cadeia
  (ordenação → asc/desc → quebrados → grade → lista).
- ``ReaderView``: NÃO pode ser importado depois de existir uma QApplication
  (puxa QtWebEngineWidgets) — checagem estática do fonte, mesmo padrão de
  ``tests/test_emoji_buttons.py`` / ``tests/test_reader_view_guards.py``.
- ``BookDetails``: os 7 botões de ação têm texto visível (não são só-ícone) —
  fora do escopo do item 4.5; teste documenta essa constatação em vez de
  exigir accessibleName onde não se aplica.
- ``search_bar.py`` / ``sidebar.py``: sem botão-ícone customizado (o botão
  "limpar" do QLineEdit é interno do Qt; o toggle de sidebar é um QShortcut
  sem botão associado) — documentado, nada a cobrir aqui.
"""
from pathlib import Path

from PyQt6.QtWidgets import QPushButton

from src.gui.book_details import BookDetails
from src.gui.library_view import LibraryView

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"

# Botões/ferramentas só-ícone (ou de rótulo não-descritivo, ex.: "Aa") da
# toolbar do leitor que passam a carregar accessibleName (Onda 4, item 4.5).
_READER_ACCESSIBLE_ATTRS = [
    "_prev_btn", "_next_btn", "_typography_btn", "_annotations_btn",
    "_bookmark_btn", "_side_panel_toggle_btn", "_fullscreen_btn",
    "_highlight_mode_btn", "_study_btn", "_ai_panel_btn", "_overflow_btn",
]
# Variáveis locais (sem ``self.``) que também recebem accessibleName.
_READER_ACCESSIBLE_LOCALS = ["zoom_out", "zoom_in", "search_btn"]


def test_library_view_header_icon_buttons_have_accessible_name(qtbot):
    view = LibraryView()
    qtbot.addWidget(view)

    assert view._grid_btn.accessibleName() == "Visualização em grade"
    assert view._list_btn.accessibleName() == "Visualização em lista"
    assert view._broken_btn.accessibleName()
    assert view._sort_order_btn.accessibleName()


def test_library_view_header_tab_order(qtbot):
    """Cadeia curada: ordenação → asc/desc → quebrados → grade → lista.

    O campo de busca (SearchBar) fica fora do LibraryView (widget irmão em
    MainWindow) — encadeá-lo exigiria tocar a construção de UI do
    main_window.py, fora do escopo desta Onda. Ver comentário em
    library_view.py::_setup_ui.
    """
    view = LibraryView()
    qtbot.addWidget(view)

    assert view._sort_combo.nextInFocusChain() is view._sort_order_btn
    assert view._sort_order_btn.nextInFocusChain() is view._broken_btn
    assert view._broken_btn.nextInFocusChain() is view._grid_btn
    assert view._grid_btn.nextInFocusChain() is view._list_btn


def test_book_details_action_buttons_have_visible_text_not_accessible_name(qtbot):
    """Os 7 botões de ação do BookDetails têm texto visível — fora do escopo
    4.5 (que pede accessibleName nos REALMENTE só-ícone). Nada a corrigir
    aqui; o teste documenta a constatação para não ser re-perguntado."""
    panel = BookDetails(db=None)
    qtbot.addWidget(panel)
    for attr in ("_open_btn", "_dossier_btn", "_fav_btn", "_col_btn",
                 "_meta_btn", "_remove_col_btn", "_del_btn"):
        btn = getattr(panel, attr)
        assert isinstance(btn, QPushButton)
        assert btn.text().strip() != ""


def test_reader_view_icon_only_toolbar_buttons_have_accessible_name():
    """Checagem estática do fonte (ReaderView não pode ser importado após
    QApplication existir — puxa QtWebEngineWidgets)."""
    src = _READER_VIEW.read_text(encoding="utf-8")
    missing = [
        attr for attr in _READER_ACCESSIBLE_ATTRS
        if f"{attr}.setAccessibleName(" not in src
    ]
    assert not missing, f"sem setAccessibleName: {missing}"

    missing_locals = [
        name for name in _READER_ACCESSIBLE_LOCALS
        if f"{name}.setAccessibleName(" not in src
    ]
    assert not missing_locals, f"sem setAccessibleName: {missing_locals}"
