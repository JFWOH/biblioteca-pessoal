"""Onda 0.3 — migração de estilo inline p/ styles.py central.

Cobre os 10 arquivos da whitelist do contrato (book_card, book_details,
collection_dialog, import_dialog, anki_export_dialog, book_dossier_dialog,
tag_manager, settings_dialog, flashcards_dialog, ollama_wizard); desde a
Onda 0b (1/2), também rag_panel e annotation_panel; e desde a Onda 0b (2/2),
sidebar, ai_response_card, proactive_footer, search_overlay e library_view.
reader_view.py também foi migrado na Onda 0b (2/2), mas NÃO entra no build
sob os 3 temas (ver test_reader_view_has_no_inline_stylesheet_source): o
módulo importa QtWebEngineWidgets, que só pode ser importado ANTES de existir
QApplication — instanciá-lo nesta suíte quebraria (mesma razão documentada em
test_reader_view_guards.py e test_security_epub_web.py).

1. Os widgets/diálogos continuam construíveis sob os 3 temas, sem exceção.
2. Os objectNames-chave introduzidos na migração existem (contrato mínimo
   entre .py e as regras QSS em styles.py).
3. As exceções documentadas (cor vinda de DADO — TagBadge, swatch de cor,
   barra/paleta de cor de destaque do AnnotationItem/AnnotationPanel)
   permanecem com ``setStyleSheet`` inline calculado em runtime.

Não reinstancia MainWindow (pesada). Não asserta o valor exato de cor —
isso é responsabilidade de revisão visual manual; aqui validamos apenas o
MECANISMO (objectName aplicado, nenhuma exceção na construção).
"""
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from src.core.config import ConfigManager
from src.core.database import LibraryDB
from src.gui.styles import DARK_THEME, LIGHT_THEME, SEPIA_THEME, get_theme
from src.gui.widgets.book_card import BookCard
from src.gui.book_details import BookDetails
from src.gui.collection_dialog import CollectionDialog, AddToCollectionDialog
from src.gui.import_dialog import ImportDialog
from src.gui.widgets.anki_export_dialog import AnkiExportDialog
from src.gui.dialogs.book_dossier_dialog import BookDossierDialog
from src.gui.widgets.tag_manager import TagManager, TagBadge, AddTagDialog
from src.gui.settings_dialog import SettingsDialog
from src.gui.dialogs.flashcards_dialog import FlashcardsDialog
from src.gui.dialogs.ollama_wizard import OllamaWizardDialog
from src.gui.dialogs.shortcuts_dialog import ShortcutsDialog
from src.gui.widgets.rag_panel import RAGPanel
from src.gui.widgets.annotation_panel import AnnotationItem, AnnotationPanel
from src.gui.sidebar import Sidebar
from src.gui.widgets.ai_response_card import AIResponseCard
from src.gui.widgets.proactive_footer import ProactiveFooterWidget
from src.gui.widgets.search_overlay import DocumentSearchBar
from src.gui.library_view import LibraryView


@pytest.fixture(autouse=True)
def _restore_app_stylesheet(qtbot):
    """Não vaza a stylesheet global entre testes (QApplication é singleton)."""
    app = QApplication.instance()
    before = app.styleSheet()
    yield
    app.setStyleSheet(before)


class _FakeAnkiService:
    """Stub mínimo: Anki "fechado" (ramo offline de _load_decks)."""

    def is_available(self) -> bool:
        return False

    def count_pending_fallback(self) -> int:
        return 0


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


def _exercise_card(card):
    card.set_selected(True)
    card.set_selected(False)


# ids curtos: sem eles, o nodeid embute os ~27KB do QSS de cada tema; ascii-
# escapado passa de 32767 chars e o Windows recusa gravar PYTEST_CURRENT_TEST
# (limite de env var só no Windows). Os ids não mudam o que o teste exercita.
@pytest.mark.parametrize("theme_css", [DARK_THEME, LIGHT_THEME, SEPIA_THEME],
                         ids=["dark", "light", "sepia"])
def test_widgets_build_under_every_theme(qtbot, db, config, theme_css):
    """Constrói os 10 widgets/diálogos da whitelist sob cada tema, sem erro.

    Higiene de recursos nativos (CI Linux, SIGABRT flaky — ver conftest.py):
    cada widget é construído, exercitado e DESTRUÍDO na hora, em vez de manter
    ~12 widgets vivos até o fim do teste ×3 temas. Widget top-level sem pai é
    propriedade do Python: soltar a última referência destrói o C++ na hora.
    """
    app = QApplication.instance()
    app.setStyleSheet(theme_css)

    bid = db.add_book(title="Livro X", file_path="/x.pdf", file_format="pdf")

    cases = [
        (lambda: BookCard({"id": 1, "title": "Livro", "file_path": __file__}),
         _exercise_card),
        (lambda: BookDetails(db), None),
        (lambda: CollectionDialog(db), None),
        (lambda: AddToCollectionDialog(db, bid), None),
        (lambda: ImportDialog(MagicMock()), None),
        (lambda: AnkiExportDialog(_FakeAnkiService()), None),
        (lambda: BookDossierDialog(db, bid), None),
        (lambda: TagManager(db), lambda w: w.set_book(bid)),
        (lambda: AddTagDialog(db, bid), None),
        (lambda: SettingsDialog(config), None),
        (lambda: FlashcardsDialog(db, current_book_id=bid), None),
        (lambda: OllamaWizardDialog(), None),
        (lambda: ShortcutsDialog(), None),  # Onda 4 — novo diálogo, mesmo padrão de objectName
        # Onda 0b (1/2): rag_panel e annotation_panel. O exercise do RAGPanel
        # percorre os estados dinâmicos (objectName-swap + repolish) do badge.
        (lambda: RAGPanel(),
         lambda w: (w.set_ollama_status(True, "m"), w.set_ollama_status(False))),
        (lambda: AnnotationPanel(),
         lambda w: w.load_annotations([])),
        # AnnotationItem não tem mais set_theme (API morta removida na
        # auditoria da Onda 0b — o QSS central cobre o item por objectName).
        (lambda: AnnotationItem(
            {"annotation_type": "highlight", "content": "c", "title": "t",
             "page_number": 1, "created_at": "2026-07-18 10:00",
             "highlight_color": "#fbbf24", "id": 1}),
         None),
        # Onda 0b (2/2): sidebar, ai_response_card, proactive_footer,
        # search_overlay, library_view. O exercise do AIResponseCard percorre
        # o estado dinâmico (objectName-swap) do status thinking -> erro; o do
        # DocumentSearchBar, o estado (property-swap) do label de contagem.
        (lambda: Sidebar(), None),
        (lambda: AIResponseCard(),
         lambda w: (w.start(), w.set_status("tick"), w.fail("erro"), w.finish())),
        (lambda: ProactiveFooterWidget(),
         lambda w: w.set_observation(
             {"tipo": "insight", "confianca": "Alta", "texto": "x"})),
        (lambda: DocumentSearchBar(),
         lambda w: (w.set_results([{"page": 0}]), w.close_bar())),
        (lambda: LibraryView(), None),
    ]
    for factory, exercise in cases:
        widget = factory()
        if exercise is not None:
            exercise(widget)
        widget.close()
        del widget
        QApplication.processEvents()


def test_migrated_widgets_have_no_inline_stylesheet(qtbot, db):
    """Widgets migrados não devem mais ter setStyleSheet residual próprio."""
    card = BookCard({"id": 1, "title": "Livro", "file_path": __file__})
    qtbot.addWidget(card)
    assert card.styleSheet() == ""

    details = BookDetails(db)
    qtbot.addWidget(details)
    assert details._title.styleSheet() == ""
    assert details._author.styleSheet() == ""

    # Onda 0b (1/2): rag_panel — zero setStyleSheet (estado dinâmico virou
    # objectName-swap; troca de tema é coberta pela folha da QApplication).
    rag = RAGPanel()
    qtbot.addWidget(rag)
    assert rag.styleSheet() == ""
    assert rag._send_btn.styleSheet() == ""
    assert rag._status_badge.styleSheet() == ""
    rag.set_ollama_status(True, "gemma4:e4b")
    assert rag._status_badge.styleSheet() == ""  # estado muda via objectName
    rag.set_theme("light")
    assert rag._header.styleSheet() == ""        # set_theme não remonta QSS

    # Onda 0b (1/2): annotation_panel — só as exceções de DADO ficam inline.
    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    assert panel.styleSheet() == ""
    assert panel._title.styleSheet() == ""
    assert panel._add_note_btn.styleSheet() == ""
    panel.set_theme("sepia")
    assert panel.styleSheet() == ""

    item = AnnotationItem({"annotation_type": "note", "content": "c",
                           "page_number": 0, "id": 1})
    qtbot.addWidget(item)
    assert item.styleSheet() == ""
    assert item._page_btn.styleSheet() == ""
    assert item._del_btn.styleSheet() == ""

    # Onda 0b (2/2): sidebar — zero setStyleSheet (título/stats/OPDS via
    # objectName; set_theme virou no-op).
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    assert sidebar.styleSheet() == ""
    assert sidebar._title.styleSheet() == ""
    assert sidebar._opds_btn.styleSheet() == ""
    sidebar.set_theme("light")
    assert sidebar._opds_btn.styleSheet() == ""

    # Onda 0b (2/2): ai_response_card — hoje DARK-ONLY, virou theme-aware; o
    # estado de erro do status label é objectName-swap, não setStyleSheet.
    card = AIResponseCard()
    qtbot.addWidget(card)
    assert card.styleSheet() == ""
    assert card._status_lbl.styleSheet() == ""
    card.fail("erro")
    assert card._status_lbl.styleSheet() == ""

    # Onda 0b (2/2): proactive_footer — QWidget subclasse com WA_StyledBackground.
    footer = ProactiveFooterWidget()
    qtbot.addWidget(footer)
    assert footer.styleSheet() == ""
    assert footer.header_label.styleSheet() == ""
    assert footer.body_label.styleSheet() == ""

    # Onda 0b (2/2): search_overlay — o estado do contador (achou/zerou) é
    # property-swap ("state"), não setStyleSheet.
    search_bar = DocumentSearchBar()
    qtbot.addWidget(search_bar)
    assert search_bar.styleSheet() == ""
    assert search_bar._input.styleSheet() == ""
    search_bar.set_results([{"page": 0}])
    assert search_bar._count_label.styleSheet() == ""
    search_bar._input.setText("xyz")
    search_bar.set_results([])  # sem resultados com texto -> estado "empty"
    assert search_bar._count_label.styleSheet() == ""

    # Onda 0b (2/2): library_view — nunca teve set_theme; elementos estáticos
    # migrados 1:1 (hardcoded, iguais nos 3 temas, como já eram).
    lib = LibraryView()
    qtbot.addWidget(lib)
    assert lib.styleSheet() == ""
    assert lib._count_label.styleSheet() == ""
    assert lib._bulk_bar.styleSheet() == ""


def test_data_driven_colors_remain_inline_exception(qtbot):
    """TagBadge e o swatch de cor: exceção documentada (cor é DADO)."""
    badge = TagBadge({"id": 1, "name": "ficção", "color": "#ef4444"})
    qtbot.addWidget(badge)
    # Continuam inline pois a cor vem do registro da tag, não do tema.
    assert "#ef4444" in badge.styleSheet()

    # Onda 0b: a barra de cor do destaque (AnnotationItem) também é DADO —
    # a cor vem do registro da anotação, não do tema.
    item = AnnotationItem({"annotation_type": "highlight", "content": "c",
                           "page_number": 0, "highlight_color": "#ef4444",
                           "id": 1})
    qtbot.addWidget(item)
    assert any("#ef4444" in w.styleSheet() for w in item.findChildren(QWidget))


def test_key_object_names_present(qtbot, db):
    """Contrato mínimo entre o .py e as regras QSS em styles.py."""
    card = BookCard({"id": 1, "title": "Livro", "file_path": __file__})
    qtbot.addWidget(card)
    assert card.objectName() == "bookCard"

    details = BookDetails(db)
    qtbot.addWidget(details)
    assert details._title.objectName() == "bookDetailsTitle"
    assert details._del_btn.objectName() == "dangerBtn"

    wizard = OllamaWizardDialog()
    qtbot.addWidget(wizard)
    assert wizard.objectName() == "wizardDialog"

    # Onda 0b (1/2): rag_panel e annotation_panel.
    rag = RAGPanel()
    qtbot.addWidget(rag)
    assert rag._send_btn.objectName() == "ragSendBtn"
    assert rag._status_badge.objectName() == "ragStatusChecking"
    rag.set_ollama_status(True, "m")
    assert rag._status_badge.objectName() == "ragStatusOnline"
    rag.set_ollama_status(False)
    assert rag._status_badge.objectName() == "ragStatusOffline"
    assert rag._thinking_indicator.objectName() == "ragThinkingIndicator"

    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    assert panel.objectName() == "annotationPanel"

    item = AnnotationItem({"annotation_type": "note", "content": "c",
                           "page_number": 0, "id": 1})
    qtbot.addWidget(item)
    assert item.objectName() == "annotationItem"
    assert item._page_btn.objectName() == "annotationItemPageBtn"

    # Onda 0b (2/2): sidebar, ai_response_card, proactive_footer,
    # search_overlay, library_view.
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    assert sidebar._title.objectName() == "sidebarTitle"
    assert sidebar._opds_btn.objectName() == "sidebarOpdsBtn"

    card = AIResponseCard()
    qtbot.addWidget(card)
    assert card.objectName() == "aiResponseCard"
    assert card._status_lbl.objectName() == "aiResponseStatusLbl"
    card.fail("erro")
    assert card._status_lbl.objectName() == "aiResponseStatusLblError"  # objectName-swap

    footer = ProactiveFooterWidget()
    qtbot.addWidget(footer)
    assert footer.objectName() == "ProactiveFooter"
    assert footer.header_label.objectName() == "proactiveFooterHeader"

    search_bar = DocumentSearchBar()
    qtbot.addWidget(search_bar)
    assert search_bar.objectName() == "documentSearchBar"
    assert search_bar._input.objectName() == "searchBarInput"
    assert search_bar._count_label.property("state") is None
    search_bar._input.setText("xyz")
    search_bar.set_results([])
    assert search_bar._count_label.property("state") == "empty"  # property-swap

    lib = LibraryView()
    qtbot.addWidget(lib)
    assert lib._count_label.objectName() == "libraryCountLabel"
    assert lib._bulk_bar.objectName() == "bulkBar"


def test_theme_propagation_still_works_after_migration(qtbot):
    """Onda 0.2 (F1) continua íntegra: QApplication recebe o QSS do tema."""
    app = QApplication.instance()
    for theme_name in ("dark", "light", "sepia"):
        css = get_theme(theme_name)
        app.setStyleSheet(css)
        assert app.styleSheet() == css


def test_reader_view_has_no_inline_stylesheet_source():
    """reader_view.py (Onda 0b 2/2): contrato via inspeção ESTÁTICA do fonte,
    sem instanciar (o módulo importa QtWebEngineWidgets — ver docstring do
    topo deste arquivo e test_reader_view_guards.py/test_security_epub_web.py
    para o mesmo motivo).

    Cobre: (1) zero setStyleSheet residual; (2) os objectNames-chave da
    migração existem como literais no fonte (contrato mínimo com as regras
    QSS ``#reader*``/``QMenu#readerPopupMenu``/``QMenu#readerAiMenu`` em
    styles.py).
    """
    src_path = (Path(__file__).resolve().parent.parent
                / "src" / "gui" / "reader_view.py")
    text = src_path.read_text(encoding="utf-8")

    assert "setStyleSheet(" not in text

    key_object_names = [
        "readerToolbar", "readerBackBtn", "readerTitleLabel", "readerPageLabel",
        "readerNavBtn", "readerZoomBtn", "readerToolbarSep",
        "readerAnnotationsBtn", "readerDoublePageBtn", "readerAiPanelBtn",
        "readerAudioBtn", "readerStudyBtn", "readerHighlightModeBtn",
        "readerTypographyBtn", "readerBookmarkBtn", "readerSidePanelToggleBtn",
        "readerSearchBtn", "readerFullscreenBtn", "readerOverflowBtn",
        "readerImageScroll", "readerProgressBarWidget", "readerProactiveCombo",
        "readerPopupMenu", "readerAiMenu",
    ]
    for name in key_object_names:
        assert re.search(rf'"{name}"', text), f'objectName "{name}" ausente do fonte'
