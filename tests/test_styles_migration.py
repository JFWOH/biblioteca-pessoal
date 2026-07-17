"""Onda 0.3 — migração de estilo inline p/ styles.py central.

Cobre os 10 arquivos da whitelist do contrato (book_card, book_details,
collection_dialog, import_dialog, anki_export_dialog, book_dossier_dialog,
tag_manager, settings_dialog, flashcards_dialog, ollama_wizard):

1. Os widgets/diálogos continuam construíveis sob os 3 temas, sem exceção.
2. Os objectNames-chave introduzidos na migração existem (contrato mínimo
   entre .py e as regras QSS em styles.py).
3. As exceções documentadas (cor vinda de DADO — TagBadge, swatch de cor)
   permanecem com ``setStyleSheet`` inline calculado em runtime.

Não reinstancia MainWindow (pesada). Não asserta o valor exato de cor —
isso é responsabilidade de revisão visual manual; aqui validamos apenas o
MECANISMO (objectName aplicado, nenhuma exceção na construção).
"""
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication

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


@pytest.mark.parametrize("theme_css", [DARK_THEME, LIGHT_THEME, SEPIA_THEME])
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


def test_data_driven_colors_remain_inline_exception(qtbot):
    """TagBadge e o swatch de cor: exceção documentada (cor é DADO)."""
    badge = TagBadge({"id": 1, "name": "ficção", "color": "#ef4444"})
    qtbot.addWidget(badge)
    # Continuam inline pois a cor vem do registro da tag, não do tema.
    assert "#ef4444" in badge.styleSheet()


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


def test_theme_propagation_still_works_after_migration(qtbot):
    """Onda 0.2 (F1) continua íntegra: QApplication recebe o QSS do tema."""
    app = QApplication.instance()
    for theme_name in ("dark", "light", "sepia"):
        css = get_theme(theme_name)
        app.setStyleSheet(css)
        assert app.styleSheet() == css
