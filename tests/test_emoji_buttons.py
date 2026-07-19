"""Onda 0.1 — bug visual: emoji embutido no texto do botão.

No Windows, ``QPushButton("📖 Ler")`` renderiza o emoji sobreposto ao rótulo.
A correção leva o emoji como ÍCONE (``setIcon(emoji_icon(...))``) e mantém o
``.text()`` do botão SEM emoji. Ver ``src/gui/styles.py::emoji_icon``.

Cobertura:
- ``BookDetails``: widget leve → instanciado e inspecionado ao vivo (pytest-qt).
- ``ReaderView``: NÃO pode ser importado depois de existir uma QApplication
  (puxa ``QtWebEngineWidgets``); a suíte já contorna isso com checagem estática
  do fonte (ver ``tests/test_reader_view_guards.py``). Seguimos o mesmo padrão.

Débito da Onda 4 corrigido nesta rodada (Rodada 5): emoji-em-texto
remanescente em ``collection_dialog.py``, ``import_dialog.py``,
``dialogs/flashcards_dialog.py`` e vários widgets em ``gui/widgets/``
(fora do escopo original 0.1, que cobria só book_details+toolbar do
leitor). Cobertura ao vivo (pytest-qt) na seção final deste arquivo —
mesmas fixtures ``db``/``_FakeAnkiService`` de ``test_styles_migration.py``.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QPushButton, QToolButton

from src.gui.book_details import BookDetails
from src.gui.library_view import LibraryView

# Faixas Unicode de emoji/pictogramas. NÃO inclui setas (← ◀ ▶ = U+2190/25xx),
# operadores (− ⋯ = U+2212/22EF) nem box-drawing (│ = U+2502): glifos
# monocromáticos usados de propósito, que renderizam sem o bug.
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # pictogramas, emoticons, transporte, símbolos ext.
    "\U00002300-\U000023FF"   # técnicos (⏸ ⏹ ⌛ …)
    "\U00002600-\U000027BF"   # símbolos diversos + dingbats (⚙ ⛶ ✅ ❌ …)
    "\U00002B00-\U00002BFF"   # setas/símbolos (⬜ ⭐ …)
    "\U0000FE00-\U0000FE0F"   # seletores de variação (VS16 → apresentação emoji)
    "]"
)

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"
_MAIN_WINDOW = Path(__file__).resolve().parent.parent / "src" / "gui" / "main_window.py"

# Botões de ação do BookDetails que passam a carregar o emoji como ícone.
_BOOK_DETAILS_ICON_BTNS = (
    "_open_btn", "_dossier_btn", "_fav_btn", "_col_btn",
    "_meta_btn", "_remove_col_btn", "_del_btn",
)


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI.search(text or ""))


def _assert_no_emoji_buttons(widget) -> None:
    """Nenhum ``QPushButton``/``QToolButton`` descendente de ``widget``
    embute emoji no texto. Usado pela cobertura ao vivo da Onda 5 (débito
    da Onda 4) — QAction de menu e QLabel estão fora do escopo do bug e não
    são inspecionados aqui."""
    buttons = widget.findChildren(QPushButton) + widget.findChildren(QToolButton)
    for btn in buttons:
        assert not _has_emoji(btn.text()), f"emoji no texto do botão: {btn.text()!r}"


# ── BookDetails (widget ao vivo) ───────────────────────────────────────

def test_book_details_buttons_have_no_emoji_in_text(qtbot):
    panel = BookDetails(db=None)
    qtbot.addWidget(panel)

    buttons = panel.findChildren(QPushButton)
    assert buttons, "esperava botões de ação no BookDetails"
    for btn in buttons:
        assert not _has_emoji(btn.text()), f"emoji no texto do botão: {btn.text()!r}"

    # Os botões de ação levam o emoji como ícone (não como texto).
    for attr in _BOOK_DETAILS_ICON_BTNS:
        assert not getattr(panel, attr).icon().isNull(), f"{attr} sem ícone-emoji"


def test_book_details_favorite_toggle_keeps_text_clean(qtbot):
    """``show_book`` troca o texto do botão favoritar — deve seguir limpo."""
    panel = BookDetails(db=None)
    qtbot.addWidget(panel)
    for is_fav in (1, 0):
        panel.show_book({"id": 1, "title": "T", "is_favorite": is_fav})
        assert not _has_emoji(panel._fav_btn.text())
        assert not panel._fav_btn.icon().isNull()


# ── LibraryView (widget ao vivo) — Onda 4, item 4.5 ─────────────────────
# Mesmo bug de classe da Onda 0.1, achado em library_view.py:289 durante a
# revisão da Onda 4: o botão "Excluir Selecionados" da barra de ação em
# lote embutia o emoji no texto. Corrigido com o mesmo padrão (emoji_icon).

def test_library_view_bulk_delete_button_has_no_emoji_in_text(qtbot):
    view = LibraryView()
    qtbot.addWidget(view)

    delete_buttons = [
        b for b in view.findChildren(QPushButton)
        if "Excluir Selecionados" in b.text()
    ]
    assert delete_buttons, "esperava o botão de exclusão em lote"
    for btn in delete_buttons:
        assert not _has_emoji(btn.text()), f"emoji no texto do botão: {btn.text()!r}"
        assert not btn.icon().isNull(), "botão de excluir sem ícone-emoji"


# ── ReaderView (checagem estática do fonte) ────────────────────────────

def test_reader_view_buttons_have_no_emoji_in_text():
    """Nenhum ``QPushButton``/``QToolButton`` criado com emoji no texto e
    nenhum ``setText("…emoji…")`` no arquivo inteiro. Emoji só via
    ``setIcon(emoji_icon("…"))`` — que esta checagem não inspeciona.
    """
    src = _READER_VIEW.read_text(encoding="utf-8")
    offenders = []
    for m in re.finditer(r'Q(?:Push|Tool)Button\(\s*(["\'])(.*?)\1', src):
        if _has_emoji(m.group(2)):
            offenders.append(f"construtor: {m.group(2)!r}")
    for m in re.finditer(r'\.setText\(\s*(["\'])(.*?)\1', src):
        if _has_emoji(m.group(2)):
            offenders.append(f"setText: {m.group(2)!r}")
    assert not offenders, "emoji no texto de botões do reader_view:\n" + "\n".join(offenders)


# ── Onda 5 (débito da Onda 4): collection_dialog / import_dialog /
# flashcards_dialog / widgets diversos — cobertura ao vivo (pytest-qt) ──────

class _FakeAnkiService:
    """Stub mínimo (mesmo de test_styles_migration.py): Anki "fechado"."""

    def is_available(self) -> bool:
        return False

    def count_pending_fallback(self) -> int:
        return 0


@pytest.fixture
def db(tmp_path):
    from src.core.database import LibraryDB
    database = LibraryDB(tmp_path / "lib.db")
    yield database
    database.close()


def test_collection_dialog_buttons_have_no_emoji_in_text(qtbot, db):
    from src.gui.collection_dialog import CollectionDialog
    dlg = CollectionDialog(db)
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)
    assert not dlg._rename_btn.icon().isNull()
    assert not dlg._delete_btn.icon().isNull()


def test_add_to_collection_dialog_buttons_have_no_emoji_in_text(qtbot, db):
    from src.gui.collection_dialog import AddToCollectionDialog
    bid = db.add_book(title="Livro", file_path="/x.pdf", file_format="pdf")
    dlg = AddToCollectionDialog(db, bid)
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)


def test_import_dialog_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.import_dialog import ImportDialog
    dlg = ImportDialog(MagicMock())
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)
    assert not dlg._import_btn.icon().isNull()


def test_flashcards_dialog_buttons_have_no_emoji_in_text(qtbot, db):
    from src.gui.dialogs.flashcards_dialog import FlashcardsDialog
    bid = db.add_book(title="Livro", file_path="/x.pdf", file_format="pdf")
    db.add_flashcard(front="Q1", back="A1", book_id=bid)
    dlg = FlashcardsDialog(db, current_book_id=bid)
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)  # inclui o "✕" do _FlashcardCard na lista


def test_word_wise_popover_close_button_has_no_emoji_in_text(qtbot):
    from src.gui.widgets.word_wise_popover import WordWisePopover
    popover = WordWisePopover()
    qtbot.addWidget(popover)
    for state in ("loading", "definition", "error"):
        if state == "loading":
            popover.show_loading("termo", popover.pos())
        elif state == "definition":
            popover.show_definition("termo", "definição")
        else:
            popover.show_error()
        _assert_no_emoji_buttons(popover)
    assert not popover._close_btn.icon().isNull()


def test_tag_manager_buttons_have_no_emoji_in_text(qtbot, db):
    from src.gui.widgets.tag_manager import TagManager, AddTagDialog
    bid = db.add_book(title="Livro", file_path="/x.pdf", file_format="pdf")
    tag_id = db.create_tag("Ficção", "#6366f1")
    db.add_tag_to_book(bid, tag_id)

    manager = TagManager(db)
    qtbot.addWidget(manager)
    manager.set_book(bid)  # popula TagBadge com botão remover ("✕")
    _assert_no_emoji_buttons(manager)

    dlg = AddTagDialog(db, bid)
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)


def test_tag_badge_remove_button_has_no_emoji_in_text(qtbot):
    from src.gui.widgets.tag_manager import TagBadge
    badge = TagBadge({"id": 1, "name": "Ficção", "color": "#6366f1"}, removable=True)
    qtbot.addWidget(badge)
    _assert_no_emoji_buttons(badge)


def test_search_overlay_close_button_has_no_emoji_in_text(qtbot):
    from src.gui.widgets.search_overlay import DocumentSearchBar
    bar = DocumentSearchBar()
    qtbot.addWidget(bar)
    _assert_no_emoji_buttons(bar)
    assert not bar._close_btn.icon().isNull()


def test_reader_typography_popover_close_button_has_no_emoji_in_text(qtbot):
    from src.gui.widgets.reader_typography_popover import ReaderTypographyPopover
    popover = ReaderTypographyPopover()
    qtbot.addWidget(popover)
    _assert_no_emoji_buttons(popover)


def test_reader_dock_close_button_has_no_emoji_in_text(qtbot):
    from PyQt6.QtWidgets import QLabel
    from src.gui.widgets.reader_dock import ReaderDock
    dock = ReaderDock()
    qtbot.addWidget(dock)
    # add_tab(icon=...): o emoji vai pro ícone do botão da aba, nunca no texto
    # (débito da Onda 4 — os 3 call sites de reader_view.py embutiam o emoji
    # em label antes desta rodada).
    dock.add_tab("annotations", "Anotações", QLabel("a"), icon="📝")
    _assert_no_emoji_buttons(dock)
    assert not dock._tab_buttons["annotations"].icon().isNull()
    assert not dock._close_btn.icon().isNull()


def test_rag_panel_buttons_have_no_emoji_in_text_across_states(qtbot):
    """Exercita os principais estados dinâmicos do RAGPanel (débito da Onda
    4) — vários botões trocam de texto/ícone em runtime (feedback,
    salvar nota, aplicar modelo) e cada transição precisa continuar limpa."""
    from src.gui.widgets.rag_panel import RAGPanel
    panel = RAGPanel()
    qtbot.addWidget(panel)
    _assert_no_emoji_buttons(panel)  # estado inicial

    # Resposta com contexto de livro: mostra salvar-nota + flashcard + 👍/👎.
    panel.set_reading_context(1, "Livro", 1, "texto")
    panel._last_query = "pergunta"
    panel.on_answer_complete("uma resposta qualquer")
    _assert_no_emoji_buttons(panel)

    # 👍 — confirmação "Obrigado!" (ícone muda de 👍 para ✅).
    panel._thumbs_up_btn.click()
    _assert_no_emoji_buttons(panel)

    # Nova resposta + 👎 com motivo — confirmação "Obrigado!" no botão down.
    panel._feedback_given = False
    panel.on_answer_complete("outra resposta")
    panel._thumbs_down_btn.click()
    panel._on_reason_chosen("incompleta")
    _assert_no_emoji_buttons(panel)

    # Salvar como anotação — "Salvo!" (ícone muda de 💾 para ✅).
    panel._on_save_note_clicked()
    _assert_no_emoji_buttons(panel)

    # Seletor de modelo: instalado vs. não instalado.
    panel._installed_models = {panel._MODEL_CATALOG[0][0]}
    panel._on_model_combo_changed(0)
    _assert_no_emoji_buttons(panel)
    panel._installed_models = set()
    panel._on_model_combo_changed(0)
    _assert_no_emoji_buttons(panel)

    # Conclusão do download (sem worker real — chamado direto).
    panel._on_pull_complete(True, panel._MODEL_CATALOG[0][0])
    _assert_no_emoji_buttons(panel)


def test_proactive_insights_panel_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.widgets.proactive_insights_panel import ProactiveInsightsPanel
    panel = ProactiveInsightsPanel()
    qtbot.addWidget(panel)
    panel.add_observation({"id": 1, "tipo": "Conexão", "confianca": "Alta", "texto": "obs"})
    _assert_no_emoji_buttons(panel)


def test_proactive_footer_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.widgets.proactive_footer import ProactiveFooterWidget
    footer = ProactiveFooterWidget()
    qtbot.addWidget(footer)
    footer.set_observation({"tipo": "Conexão", "confianca": "Alta", "texto": "obs"})
    _assert_no_emoji_buttons(footer)


def test_bookmarks_panel_remove_button_has_no_emoji_in_text(qtbot):
    from src.gui.widgets.bookmarks_panel import BookmarksPanel
    panel = BookmarksPanel()
    qtbot.addWidget(panel)
    panel.set_bookmarks([{"page_number": 0, "label": "Capítulo 1"}])
    _assert_no_emoji_buttons(panel)


def test_annotation_panel_and_item_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.widgets.annotation_panel import AnnotationPanel, AnnotationItem
    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    _assert_no_emoji_buttons(panel)  # "+ Nota" e o botão de marcador

    item = AnnotationItem(
        {"annotation_type": "note", "content": "corpo", "title": "T", "page_number": 1})
    qtbot.addWidget(item)
    _assert_no_emoji_buttons(item)  # renomear ("✏️") e excluir ("✕")


def test_anki_export_dialog_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.widgets.anki_export_dialog import AnkiExportDialog
    dlg = AnkiExportDialog(_FakeAnkiService())
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)
    assert not dlg.save_btn.icon().isNull()

    # Fila com pendências: flush_btn fica visível com texto dinâmico
    # ("↩️ Reenviar N flashcard(s)…" antes desta rodada).
    from unittest.mock import patch
    with patch.object(dlg.service, "count_pending_fallback", return_value=3):
        dlg._refresh_pending_button()
    _assert_no_emoji_buttons(dlg)
    assert not dlg.flush_btn.icon().isNull()


def test_ai_response_card_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.widgets.ai_response_card import AIResponseCard
    card = AIResponseCard()
    qtbot.addWidget(card)
    card.start()
    _assert_no_emoji_buttons(card)
    card.fail("erro")
    _assert_no_emoji_buttons(card)
    assert not card._stop_btn.icon().isNull()
    assert not card._retry_btn.icon().isNull()


# ── Rodada A1 (débito Onda 4, contrato pós-PR #46): varredura final —
# sidebar / settings_dialog / dialogs/ollama_wizard ─────────────────────

def test_sidebar_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.sidebar import Sidebar
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    _assert_no_emoji_buttons(sidebar)
    assert not sidebar.add_collection_btn.icon().isNull()
    assert not sidebar._buttons["stats"].icon().isNull()
    assert not sidebar._opds_btn.icon().isNull()

    # Botão de coleção dinâmico: o nome (dado do usuário) vai pro texto,
    # o emoji fixo ("📁") vai pro ícone — nunca concatenado no texto.
    sidebar.add_collection_button("Ficção Científica", 1)
    _assert_no_emoji_buttons(sidebar)
    collection_btn = sidebar._buttons["collection_1"]
    assert not collection_btn.icon().isNull()
    assert collection_btn.text() == "Ficção Científica"


def test_sidebar_opds_button_text_transition_keeps_icon_and_clean_text(qtbot):
    """Mesma transição de texto feita por ``MainWindow._on_opds_toggled``
    (liga/desliga o servidor OPDS, main_window.py) — o ícone é fixado uma
    única vez no construtor do Sidebar e sobrevive à troca de ``.text()``;
    nenhum dos dois estados pode reintroduzir o emoji no texto."""
    from src.gui.sidebar import Sidebar
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    btn = sidebar._opds_btn
    assert not btn.icon().isNull()
    assert not _has_emoji(btn.text())

    # Estado "ligado" (ramo `checked` de _on_opds_toggled).
    btn.setText("Servidor ON (192.168.0.10)")
    assert not _has_emoji(btn.text())
    assert not btn.icon().isNull()

    # Estado "desligado" (ramo `else` de _on_opds_toggled).
    btn.setText("Iniciar Servidor OPDS")
    assert not _has_emoji(btn.text())
    assert not btn.icon().isNull()


def test_main_window_opds_button_setText_calls_have_no_emoji_in_text():
    """``main_window.py`` não é instanciado em teste (pesado — RAG/DB/GUI
    reais); checagem estática do fonte, mesmo padrão do reader_view: nenhuma
    chamada ``_opds_btn.setText(...)`` pode embutir o emoji no texto."""
    src = _MAIN_WINDOW.read_text(encoding="utf-8")
    offenders = [
        f"setText: {m.group(2)!r}"
        for m in re.finditer(r'_opds_btn\.setText\(\s*f?(["\'])(.*?)\1', src)
        if _has_emoji(m.group(2))
    ]
    assert not offenders, "emoji no texto do botão OPDS (main_window.py):\n" + "\n".join(offenders)


def test_settings_dialog_buttons_have_no_emoji_in_text(qtbot, tmp_path):
    from src.core.config import ConfigManager
    from src.gui.settings_dialog import SettingsDialog
    config = ConfigManager(tmp_path / "config.json")
    dlg = SettingsDialog(config)
    qtbot.addWidget(dlg)
    _assert_no_emoji_buttons(dlg)
    save_buttons = [b for b in dlg.findChildren(QPushButton) if b.objectName() == "primaryBtn"]
    assert save_buttons, "esperava o botão Salvar"
    assert not save_buttons[0].icon().isNull()


def test_ollama_wizard_buttons_have_no_emoji_in_text(qtbot):
    from src.gui.dialogs.ollama_wizard import OllamaWizardDialog
    wizard = OllamaWizardDialog()
    qtbot.addWidget(wizard)
    _assert_no_emoji_buttons(wizard)
    assert not wizard._done_btn.icon().isNull()
    assert not wizard._manual_btn.icon().isNull()

    # Página de conclusão: sucesso e erro trocam ícone/label do QLabel (fora
    # do escopo do bug) mas não devem afetar o texto dos botões.
    wizard._on_install_complete(True, "instalado com sucesso")
    _assert_no_emoji_buttons(wizard)
    wizard._on_install_complete(False, "falhou")
    _assert_no_emoji_buttons(wizard)
