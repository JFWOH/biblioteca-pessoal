"""Janela principal da aplicação Biblioteca Pessoal."""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QSplitter, QFileDialog, QMessageBox,
    QStatusBar, QMenuBar, QApplication,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QKeySequence

from src.core.database import LibraryDB
from src.core.config import ConfigManager
from src.core.library import LibraryManager
from src.core.search import SearchEngine
from src.gui.sidebar import Sidebar
from src.gui.search_bar import SearchBar
from src.gui.library_view import LibraryView
from src.gui.reader_view import ReaderView
from src.gui.book_details import BookDetails
from src.gui.styles import get_theme
from src.gui.import_dialog import ImportDialog
from src.gui.collection_dialog import CollectionDialog, AddToCollectionDialog
from src.gui.workers.metadata_worker import MetadataWorker
from src.gui.workers.opds_worker import OPDSWorker
from src.gui.workers.rag_worker import RAGWorker
import os
from PyQt6.QtGui import QPixmap
from src.gui.widgets.stats_panel import StatsPanel
from src.gui.widgets.rag_panel import RAGPanel
from src.utils.constants import FILE_FILTER, DATA_DIR
from src.utils.export import export_annotations_markdown
from src.gui.watcher import DirectoryWatcher

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Janela principal da Biblioteca Pessoal."""

    def __init__(self):
        super().__init__()

        # Inicializa core
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._db = LibraryDB()
        # Limpeza única de anotações duplicadas históricas (cliques repetidos
        # antes da guarda de dedup no add_annotation). Nunca bloqueia o start.
        try:
            removed = self._db.dedupe_annotations()
            if removed:
                logger.info(f"Anotações duplicadas removidas na limpeza: {removed}")
        except Exception as exc:
            logger.warning(f"Falha na limpeza de anotações duplicadas (ignorado): {exc}")
        self._config = ConfigManager()
        self._library = LibraryManager(self._db, self._config)
        self._search_engine = SearchEngine(self._db)

        # Inicializa TTS router persistente
        from src.core.tts.tts_router import TTSRouter
        from src.core.tts.text_preprocessor import TTSTextPreprocessor
        self._tts_router = TTSRouter(TTSTextPreprocessor())
        self._tts_router.auto_register_providers()
        self._tts_router.initialize()

        # Inicializa RAG engine (graceful — não trava se Ollama offline)
        self._rag_engine = None
        self._rag_worker = None
        self._setup_rag_engine()

        # Grafo de conceitos (Fase 2): ingestão em background dirigida pela leitura.
        from src.gui.graph_ingest_service import GraphIngestService
        self._graph_service = GraphIngestService(
            db=self._db, rag_engine=self._rag_engine, config=self._config, parent=self)

        # Auto-indexação RAG em ocioso: livros sem indexed_ok são indexados em
        # background (1 por vez), destravando RAG e grafo para toda a biblioteca.
        from src.gui.auto_index_service import AutoIndexService
        self._auto_index_service = AutoIndexService(
            db=self._db, rag_engine=self._rag_engine, config=self._config,
            busy_check=lambda: bool(self._rag_worker and self._rag_worker.isRunning()),
            parent=self)
        self._auto_index_service.indexing_started.connect(
            lambda _bid, title: self._statusbar.showMessage(
                f"📚 Indexando em segundo plano: {title}…", 10000))
        self._auto_index_service.indexing_finished.connect(self._on_auto_index_finished)

        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._setup_statusbar()
        self._apply_theme()
        self._load_library()
        self._setup_watcher()

        # Workers
        self._metadata_worker = None
        self._opds_worker = None

        # Verifica status do Ollama após UI pronta
        self._check_ollama_status()

    def _setup_window(self):
        self.setWindowTitle("📚 Biblioteca Pessoal")
        w = self._config.get("window.width", 1280)
        h = self._config.get("window.height", 800)
        self.resize(w, h)
        self.setMinimumSize(QSize(900, 600))
        if self._config.get("window.maximized", False):
            self.showMaximized()

    def _setup_menu(self):
        menubar = self.menuBar()

        # Menu Arquivo
        file_menu = menubar.addMenu("&Arquivo")

        import_action = QAction("📥 Importar...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._show_import_dialog)
        file_menu.addAction(import_action)

        import_file = QAction("📄 Importar Arquivo Rápido...", self)
        import_file.setShortcut(QKeySequence("Ctrl+O"))
        import_file.triggered.connect(self._import_file)
        file_menu.addAction(import_file)

        import_dir = QAction("📂 Importar Pasta...", self)
        import_dir.setShortcut(QKeySequence("Ctrl+Shift+O"))
        import_dir.triggered.connect(self._import_directory)
        file_menu.addAction(import_dir)

        file_menu.addSeparator()

        quit_action = QAction("Sair", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Menu Visualizar
        view_menu = menubar.addMenu("&Visualizar")

        for theme_name, theme_label in [
            ("dark", "🌙 Tema Escuro"),
            ("light", "☀️ Tema Claro"),
            ("sepia", "📜 Tema Sépia"),
        ]:
            action = QAction(theme_label, self)
            action.triggered.connect(lambda checked, t=theme_name: self._set_theme(t))
            view_menu.addAction(action)

        view_menu.addSeparator()

        settings_action = QAction("⚙️ Configurações...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._show_settings)
        view_menu.addAction(settings_action)

        # Menu Organizar
        org_menu = menubar.addMenu("&Organizar")

        col_action = QAction("📂 Gerenciar Coleções...", self)
        col_action.triggered.connect(self._show_collections)
        org_menu.addAction(col_action)

        org_menu.addSeparator()

        export_action = QAction("📝 Exportar Anotações...", self)
        export_action.triggered.connect(self._export_annotations)
        org_menu.addAction(export_action)

        # Menu Ferramentas (RAG)
        tools_menu = menubar.addMenu("&Ferramentas")
        ai_action = QAction("🧠 Assistente de Livros (IA)", self)
        ai_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        ai_action.triggered.connect(self._show_rag_panel)
        tools_menu.addAction(ai_action)

        flashcards_action = QAction("🃏 Flashcards", self)
        flashcards_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        flashcards_action.triggered.connect(self._show_flashcards)
        tools_menu.addAction(flashcards_action)

        tools_menu.addSeparator()

        reindex_action = QAction("🔄 Reindexar Biblioteca (IA)", self)
        reindex_action.triggered.connect(self._on_rag_index_all)
        tools_menu.addAction(reindex_action)

        # Menu Ajuda
        help_menu = menubar.addMenu("A&juda")
        about = QAction("Sobre", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main horizontal splitter
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setHandleWidth(1)
        self._main_splitter.setStyleSheet("QSplitter::handle { background: #27272a; }")

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.section_changed.connect(self._on_section_changed)
        self._sidebar.add_collection_btn.clicked.connect(self._on_new_collection)
        self._sidebar.opds_toggled.connect(self._on_opds_toggled)
        self._main_splitter.addWidget(self._sidebar)

        # Conteúdo principal (stack: biblioteca | leitor)
        self._main_stack = QStackedWidget()

        # ── Página da Biblioteca ──
        library_page = QWidget()
        lib_layout = QVBoxLayout(library_page)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(0)

        # Search bar
        search_container = QWidget()
        search_container.setObjectName("searchContainer")
        sc_layout = QHBoxLayout(search_container)
        sc_layout.setContentsMargins(24, 12, 24, 12)
        self._search_bar = SearchBar()
        self._search_bar.search_changed.connect(self._on_search)
        sc_layout.addWidget(self._search_bar)
        lib_layout.addWidget(search_container)

        # Splitter: library view + book details
        lib_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._library_view = LibraryView()
        self._library_view.book_selected.connect(self._on_book_selected)
        self._library_view.book_open.connect(self._on_book_open)
        self._library_view.bulk_delete_requested.connect(self._on_bulk_delete)
        lib_splitter.addWidget(self._library_view)

        self._book_details = BookDetails(db=self._db)
        self._book_details.open_requested.connect(self._on_book_open)
        self._book_details.favorite_toggled.connect(self._on_favorite_toggle)
        self._book_details.delete_requested.connect(self._on_delete_book)
        self._book_details.rating_changed.connect(self._on_rating_changed)
        self._book_details.add_to_collection_requested.connect(self._add_book_to_collection)
        self._book_details.remove_from_collection_requested.connect(self._remove_from_collection)
        self._book_details.fetch_metadata_requested.connect(self._on_fetch_metadata)
        self._book_details.related_book_clicked.connect(self._on_book_selected)
        self._graph_service.graph_updated.connect(self._on_graph_updated)
        lib_splitter.addWidget(self._book_details)

        lib_splitter.setStretchFactor(0, 1)
        lib_splitter.setStretchFactor(1, 0)

        lib_layout.addWidget(lib_splitter, stretch=1)
        self._main_stack.addWidget(library_page)  # index 0

        # ── Página do Leitor ──
        self._reader_view = ReaderView(parent=self, tts_router=self._tts_router, rag_engine=self._rag_engine, db=self._db)
        self._reader_view.closed.connect(self._close_reader)
        self._reader_view.progress_changed.connect(self._on_progress)
        self._reader_view.annotation_added.connect(self._on_annotation_added)
        self._reader_view.annotation_deleted.connect(self._on_annotation_deleted)
        self._reader_view.annotation_renamed.connect(self._on_annotation_renamed)
        self._reader_view.fullscreen_toggled.connect(self._on_fullscreen)
        self._reader_view.reading_context_updated.connect(lambda b, t, p, txt: self._rag_panel.set_reading_context(b, t, p, txt))
        self._reader_view.reading_context_updated.connect(self._graph_service.on_page_context)
        # Auto-indexação: leitura ativa adia o processamento em ocioso.
        self._reader_view.reading_context_updated.connect(self._auto_index_service.on_activity)
        self._reader_view.ai_action_requested.connect(self._on_ai_action_requested)
        self._main_stack.addWidget(self._reader_view)  # index 1

        # ── Página de Estatísticas ──
        self._stats_panel = StatsPanel()
        self._main_stack.addWidget(self._stats_panel)  # index 2

        # ── Página do Assistente IA (RAG) ──
        self._rag_panel = RAGPanel()
        self._rag_panel.query_requested.connect(self._on_rag_query)
        self._rag_panel.index_requested.connect(self._on_rag_index_all)
        self._rag_panel.stop_requested.connect(self._on_rag_stop)
        self._rag_panel.model_changed.connect(self._on_model_changed)
        self._rag_panel.save_annotation_requested.connect(self._on_rag_annotation_save)
        self._rag_panel.feedback_submitted.connect(self._on_rag_feedback)
        self._rag_panel.clear_chat_requested.connect(self._on_clear_chat)
        self._rag_panel.back_requested.connect(lambda: self._main_stack.setCurrentIndex(0))
        self._main_stack.addWidget(self._rag_panel)  # index 3

        self._main_splitter.addWidget(self._main_stack)
        main_layout.addWidget(self._main_splitter, stretch=1)

        # Splitter stretch factors
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([240, 1040])

        # Shortcuts
        from PyQt6.QtGui import QShortcut, QKeySequence
        self._shortcut_sidebar = QShortcut(QKeySequence("Ctrl+B"), self)
        self._shortcut_sidebar.activated.connect(self._toggle_sidebar)

        self._shortcut_rag = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_rag.activated.connect(self._toggle_rag)

    def _toggle_sidebar(self):
        self._sidebar.setVisible(not self._sidebar.isVisible())

    def _toggle_rag(self):
        current_index = self._main_stack.currentIndex()
        if current_index == 1:
            # Se o leitor (ReaderView) estiver ativo, delega o toggle do painel RAG interno
            self._reader_view._ai_panel_btn.setChecked(not self._reader_view._ai_panel_btn.isChecked())
            self._reader_view._toggle_ai_panel()
        else:
            # Se estiver na visualização da biblioteca/estatísticas, alterna a visibilidade do RAGPanel como página standalone
            if current_index == 3:
                self._main_stack.setCurrentIndex(0)
            else:
                self._show_rag_panel()

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._update_statusbar()

    def _apply_theme(self):
        theme = self._config.theme
        self.setStyleSheet(get_theme(theme))
        self._reader_view.set_theme(theme)
        self._sidebar.set_theme(theme)
        self._rag_panel.set_theme(theme)

    def _set_theme(self, theme: str):
        self._config.theme = theme
        self._apply_theme()

    # ── Carregamento de Dados ──────────────────────────────────────────

    def _load_library(self, section: str = "all"):
        """Carrega livros baseado na seção selecionada."""
        if section == "all":
            books = self._db.get_all_books()
        elif section == "favorites":
            books = self._db.get_favorite_books()
        elif section in ("unread", "reading", "read"):
            books = self._db.get_books_by_status(section)
        elif section.startswith("collection_"):
            try:
                col_id = int(section.split("_")[1])
                books = self._db.get_books_in_collection(col_id)
            except ValueError:
                books = self._db.get_all_books()
        else:
            books = self._db.get_all_books()

        self._load_collections()
        self._library_view.load_books(books)
        stats = self._db.get_statistics()
        self._sidebar.update_stats(stats)
        self._update_statusbar()

    def _load_collections(self):
        """Carrega coleções na barra lateral."""
        self._sidebar.clear_collections()
        collections = self._db.get_collections()
        for col in collections:
            self._sidebar.add_collection_button(col["name"], col["id"])

    # ── Handlers ───────────────────────────────────────────────────────

    def _on_section_changed(self, section: str):
        self._current_section = section
        self._book_details.clear()
        self._book_details.set_collection_mode(section.startswith("collection_"))
        if section == "stats":
            stats = self._db.get_statistics()
            self._stats_panel.update_stats(stats)
            self._main_stack.setCurrentIndex(2)
        elif section in ("ai_assistant", "global_search"):
            if section == "global_search":
                self._rag_panel.clear_reading_context()
            self._show_rag_panel()
        else:
            self._main_stack.setCurrentIndex(0)
            self._load_library(section)

    def _on_search(self, query: str, filters: dict):
        if query or filters:
            results = self._search_engine.search(query, filters)
            self._library_view.load_books(results)
        else:
            self._load_library()

    def _on_book_selected(self, book_id: int):
        book = self._db.get_book(book_id)
        if book:
            self._book_details.show_book(book)

    def _on_book_open(self, book_id: int):
        if book_id == -1:
            # Signal especial: abrir diálogo de importação
            self._import_file()
            return

        book = self._db.get_book(book_id)
        if not book:
            return

        filepath = book.get("file_path", "")
        if not Path(filepath).exists():
            QMessageBox.warning(
                self, "Arquivo não encontrado",
                f"O arquivo não foi encontrado:\n{filepath}"
            )
            return

        # Recupera progresso anterior
        progress = self._db.get_reading_progress(book_id)
        start_page = progress["current_page"] if progress else 0

        self._reader_view.open_book(book, start_page)
        
        # Injeta o RAGPanel no leitor e o esconde por padrão
        if self._rag_panel.parentWidget() != self._reader_view:
            self._reader_view.set_ai_panel(self._rag_panel)
        self._reader_view.hide_ai_panel()
        
        self._main_stack.setCurrentIndex(1)
        self._sidebar.hide()
        self._config.add_recent_file(filepath)

        # Carrega anotações existentes
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)

    def _close_reader(self):
        self._reader_view.close_reader()
        self._reader_view.hide_ai_panel()
        self._main_stack.setCurrentIndex(0)
        self._sidebar.show()
        self._load_library()

    def _on_progress(self, book_id: int, page: int, total: int):
        self._db.update_reading_progress(book_id, page, total)
        self._reader_view.set_annotation_page(page)

    def _on_rag_annotation_save(self, book_id: int, page: int, content: str):
        """Salva uma anotação gerada pela IA, capturando o book_id de forma explícita."""
        current_book_id = self._reader_view._book_id
        if current_book_id <= 0:
            current_book_id = book_id
        
        self._on_annotation_added(
            current_book_id,
            {"page": page, "content": content, "type": "ai_note", "color": "#6366f1"}
        )

    def _on_rag_feedback(self, rating: int, context: dict):
        """Persiste 👍/👎 do usuário sobre a resposta do RAG em agent_feedback."""
        try:
            self._db.add_feedback(rating=rating, **context)
        except Exception as exc:
            logger.warning(f"Falha ao registrar feedback do RAG (ignorado): {exc}")

    def _on_annotation_added(self, book_id: int, data: dict):
        """Persiste uma nova anotação no banco."""
        if self._reader_view._book_id > 0 and book_id != self._reader_view._book_id:
            book_id = self._reader_view._book_id

        ann_id = self._db.add_annotation(
            book_id=book_id,
            page_number=data.get("page", data.get("page_number", 0)),
            content=data.get("content", ""),
            highlight_color=data.get("color", data.get("highlight_color", "#fbbf24")),
            annotation_type=data.get("type", data.get("annotation_type", "note")),
            position_data=data.get("position_data", "{}"),
            title=data.get("title", ""),
        )
        # Recarrega anotações no painel
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)
        # Grafo de conceitos: anotação nova alimenta o grafo (nunca quebra o salvar).
        try:
            text = f"{data.get('title', '')} {data.get('content', '')}".strip()
            self._graph_service.on_annotation_saved(
                book_id, ann_id, data.get("page", data.get("page_number", 0)), text)
        except Exception as exc:
            logger.warning(f"Falha ao alimentar o grafo com a anotação (ignorado): {exc}")

    def _on_auto_index_finished(self, book_id: int, title: str, status: str):
        """Feedback discreto da auto-indexação + atualização do contador RAG."""
        if status == "indexed_ok":
            self._statusbar.showMessage(f"✅ '{title}' indexado em segundo plano.", 5000)
            try:
                self._rag_panel.set_indexed_count(
                    self._rag_engine.get_indexed_count() if self._rag_engine else 0)
            except Exception as exc:
                logger.warning(f"Falha ao atualizar contador de indexados (ignorado): {exc}")
        else:
            self._statusbar.showMessage(
                f"⚠️ Indexação de '{title}' não concluída ({status}).", 5000)

    def _on_graph_updated(self, book_id: int):
        """Grafo ganhou dados novos: atualiza o painel se o livro está em foco."""
        try:
            current = self._book_details._book
            if current and current.get("id") == book_id:
                self._book_details.refresh_graph_section()
        except Exception as exc:
            logger.warning(f"Falha ao atualizar a seção do grafo (ignorado): {exc}")

    def _on_annotation_deleted(self, annotation_id: int):
        """Remove uma anotação do banco."""
        self._db.delete_annotation(annotation_id)
        # Recarrega (precisa saber o book_id — pega do reader)
        book_id = self._reader_view._book_id
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)

    def _on_annotation_renamed(self, annotation_id: int, title: str):
        """Renomeia o título de uma anotação (inclui notas da IA)."""
        try:
            self._db.update_annotation_title(annotation_id, title)
        except Exception as exc:
            logger.warning(f"Falha ao renomear anotação (ignorado): {exc}")
            return
        book_id = self._reader_view._book_id
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)

    def _on_favorite_toggle(self, book_id: int):
        self._library.toggle_favorite(book_id)
        book = self._db.get_book(book_id)
        if book:
            self._book_details.show_book(book)
        self._load_library()

    def _on_rating_changed(self, book_id: int, rating: int):
        """Persiste a avaliação do livro."""
        self._db.update_book(book_id, rating=rating)
        self._statusbar.showMessage(
            f"⭐ Avaliação atualizada: {'★' * rating}{'☆' * (5 - rating)}", 3000
        )

    def _on_fullscreen(self, is_fullscreen: bool):
        """Alterna tela cheia."""
        if is_fullscreen:
            self._sidebar.hide()
            self.showFullScreen()
        else:
            self._sidebar.show()
            self.showNormal()

    def _on_delete_book(self, book_id: int):
        book = self._db.get_book(book_id)
        if not book:
            return
        reply = QMessageBox.question(
            self, "Remover Livro",
            f'Remover "{book["title"]}" da biblioteca?\n'
            "(O arquivo original não será apagado)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._library.remove_book(book_id)
            self._book_details.clear()
            self._load_library()

    # ── Importação ─────────────────────────────────────────────────────

    def _show_import_dialog(self):
        """Abre o diálogo rico de importação."""
        dialog = ImportDialog(self._library, self)
        dialog.import_completed.connect(self._load_library)
        dialog.exec()
        self._load_library()

    def _import_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Importar Arquivos", "", FILE_FILTER,
        )
        if files:
            count = 0
            for f in files:
                book, is_new = self._library.import_file(f)
                if book and is_new:
                    count += 1
            self._statusbar.showMessage(
                f"✅ {count} arquivo(s) importado(s)", 5000
            )
            self._load_library()

    def _import_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Importar Pasta",
        )
        if directory:
            imported = self._library.import_directory(directory)
            self._statusbar.showMessage(
                f"✅ {len(imported)} arquivo(s) importado(s)", 5000
            )
            self._load_library()

    def _show_settings(self, initial_tab: int = 0):
        """Abre o diálogo de configurações."""
        from src.gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._config, self, initial_tab=initial_tab)
        dialog.theme_changed.connect(self._set_theme)
        dialog.settings_changed.connect(lambda: self._apply_theme())
        dialog.exec()

    def _update_statusbar(self):
        stats = self._db.get_statistics()
        total = stats["total"]
        self._statusbar.showMessage(
            f"📚 {total} livros na biblioteca"
        )

    def _show_about(self):
        QMessageBox.about(
            self, "Sobre — Biblioteca Pessoal",
            "<h2>📚 Biblioteca Pessoal</h2>"
            "<p>Versão 0.1.0</p>"
            "<p>Gerenciador de biblioteca pessoal e leitor "
            "multi-formato sofisticado.</p>"
            "<p>Formatos: PDF, EPUB, MOBI, TXT, DOCX, Markdown</p>",
        )
    # ── Organização ─────────────────────────────────────────────────────

    def _show_collections(self):
        """Abre o diálogo de gerenciamento de coleções."""
        dialog = CollectionDialog(self._db, self)
        dialog.collections_changed.connect(self._update_sidebar_collections)
        dialog.exec()

    def _update_sidebar_collections(self):
        """Atualiza a sidebar com coleções do banco."""
        collections = self._db.get_all_collections()
        for col in collections:
            self._sidebar.add_collection_button(col["name"], col["id"])

    def _export_annotations(self):
        """Exporta anotações do livro selecionado."""
        # Determina o livro (do details ou do reader)
        book_id = None
        if self._main_stack.currentIndex() == 1:
            book_id = self._reader_view._book_id
        elif self._book_details._book:
            book_id = self._book_details._book.get("id")

        if not book_id:
            QMessageBox.information(
                self, "Exportar Anotações",
                "Selecione um livro primeiro para exportar suas anotações."
            )
            return

        book = self._db.get_book(book_id)
        annotations = self._db.get_annotations(book_id)
        if not annotations:
            QMessageBox.information(
                self, "Exportar Anotações",
                f'O livro "{book["title"]}" não possui anotações.'
            )
            return

        # Seleciona local de salvamento
        default_name = f"anotacoes_{book['title'][:30].replace(' ', '_')}.md"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Salvar Anotações", default_name,
            "Markdown (*.md);;Todos (*.*)"
        )
        if filepath:
            output = export_annotations_markdown(self._db, book_id, filepath)
            self._statusbar.showMessage(
                f"📝 Anotações exportadas: {output.name}", 5000
            )

    def _on_new_collection(self):
        """Cria uma nova coleção através da sidebar."""
        from src.gui.widgets.collection_dialog import CollectionDialog
        dialog = CollectionDialog(self._db, self)
        if dialog.exec():
            self._load_collections()

    def _add_book_to_collection(self, book_id: int):
        """Abre diálogo para adicionar livro a uma coleção."""
        from src.gui.collection_dialog import AddToCollectionDialog
        dialog = AddToCollectionDialog(self._db, book_id, self)
        if dialog.exec():
            self._load_collections()
            
            # Recarrega a biblioteca para atualizar a view se estiver em uma coleção
            for key, btn in self._sidebar._buttons.items():
                if btn.isChecked():
                    self._load_library(key)
                    break

    def _remove_from_collection(self, book_id: int):
        """Remove o livro apenas da coleção que está sendo visualizada."""
        if hasattr(self, "_current_section") and self._current_section.startswith("collection_"):
            col_id = int(self._current_section.split("_")[1])
            self._db.remove_book_from_collection(book_id, col_id)
            self._book_details.clear()
            self._load_collections()
            self._load_library(self._current_section)

    def _on_fetch_metadata(self, book_id: int):
        book = self._db.get_book(book_id)
        if not book:
            return
            
        title = book.get("title", "")
        author = book.get("author", "")
        
        self._statusbar.showMessage("🌐 Buscando metadados na web...")
        
        self._metadata_worker = MetadataWorker(title, author)
        self._metadata_worker.metadata_found.connect(lambda md: self._on_metadata_found(book_id, md))
        self._metadata_worker.cover_downloaded.connect(lambda cover_bytes: self._on_cover_downloaded(book_id, cover_bytes))
        self._metadata_worker.error_occurred.connect(lambda err: self._statusbar.showMessage(f"⚠️ {err}", 5000))
        self._metadata_worker.finished_work.connect(lambda: self._statusbar.showMessage("✅ Busca concluída", 3000))
        self._metadata_worker.start()
        
    def _on_metadata_found(self, book_id: int, md: dict):
        # Atualiza apenas os campos importantes e ignora os vazios
        updates = {}
        if md.get("title"): updates["title"] = md["title"]
        if md.get("author"): updates["author"] = md["author"]
        if md.get("publisher"): updates["publisher"] = md["publisher"]
        if md.get("published_year"): updates["published_year"] = md["published_year"]
        if md.get("description"): updates["description"] = md["description"]
        if md.get("isbn"): updates["isbn"] = md["isbn"]
        
        if updates:
            self._db.update_book(book_id, **updates)
            self._load_library(getattr(self, "_current_section", "all"))
            # Atualiza o painel de detalhes
            self._book_details.show_book(self._db.get_book(book_id))

    def _on_cover_downloaded(self, book_id: int, cover_bytes: bytes):
        covers_dir = self._config.get("library.covers_dir", "data/covers")
        os.makedirs(covers_dir, exist_ok=True)
        cover_path = os.path.join(covers_dir, f"cover_{book_id}.jpg")
        
        try:
            with open(cover_path, "wb") as f:
                f.write(cover_bytes)
            self._db.update_book(book_id, cover_path=cover_path)
            self._load_library(getattr(self, "_current_section", "all"))
            self._book_details.show_book(self._db.get_book(book_id))
        except Exception as e:
            self._statusbar.showMessage(f"Erro ao salvar capa: {e}", 5000)

    def _on_opds_toggled(self, checked: bool):
        from src.utils.network import obter_ip_local
        if checked:
            ip = obter_ip_local()
            self._statusbar.showMessage("Iniciando Servidor OPDS...")
            self._opds_worker = OPDSWorker(host="0.0.0.0", port=8000)
            self._opds_worker.server_started.connect(
                lambda url: self._sidebar._opds_btn.setText(f"Servidor ON ({ip})")
            )
            self._opds_worker.error_occurred.connect(
                lambda err: self._statusbar.showMessage(f"⚠️ {err}", 5000)
            )
            self._opds_worker.start()
            
            # QMessageBox com instruções - Não modal para não bloquear a interface principal indefinidamente,
            # ou bloqueante mas com a certeza que o worker já está rodando em background.
            full_url = f"http://{ip}:8000/opds"
            msg = QMessageBox(self)
            msg.setWindowTitle("Servidor OPDS Ativo")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("O servidor OPDS está rodando em background.")
            msg.setInformativeText(
                f"Você pode conectar seus aplicativos de leitura usando o endereço abaixo:\n\n"
                f"<b>{full_url}</b>\n\n"
                "Instruções para aplicativos móveis (ex: Moon+ Reader):\n"
                "• Abra a aba de 'Rede' ou 'Net Library'.\n"
                "• Escolha a opção para 'Adicionar novo catálogo' (Add new catalog).\n"
                f"• Insira a URL exata: {full_url}\n"
                "• Salve e atualize para carregar todos os livros."
            )
            # Torna o diálogo não-modal para permitir o uso da biblioteca enquanto o servidor roda
            msg.setModal(False)
            msg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            msg.show()
            self._opds_msg = msg
        else:
            if self._opds_worker:
                self._opds_worker.stop()
                self._sidebar._opds_btn.setText("📡  Iniciar Servidor OPDS")
                self._statusbar.showMessage("Servidor OPDS Parado", 3000)

    # ── RAG / IA ───────────────────────────────────────────────────────

    def _setup_rag_engine(self) -> None:
        """Inicializa o RAGEngine. Falha silenciosamente se ChromaDB indisponível."""
        try:
            from src.core.rag_engine import RAGEngine
            from src.utils.constants import DATA_DIR
            chroma_path = DATA_DIR / "chroma_db"
            db_path = self._db._db_path
            self._rag_engine = RAGEngine(
                db_path=db_path,
                chroma_path=chroma_path,
                ollama_url=self._config.get("rag.ollama_url", "http://localhost:11434"),
                embed_model=self._config.get("rag.embed_model", "bge-m3"),
                llm_model=self._config.get("rag.llm_model", "gemma4:e4b"),
            )
        except Exception as exc:
            import traceback
            print(
                f"[RAGEngine][INIT ERROR] Falha ao inicializar o motor RAG: {exc}",
                flush=True,
            )
            traceback.print_exc()
            self._rag_engine = None

    def _check_ollama_status(self) -> None:
        """Verifica status do Ollama, aciona o wizard se ausente, e atualiza o painel RAG."""
        if self._rag_engine is None:
            self._rag_panel.set_ollama_status(False)
            return

        available = self._rag_engine.is_ollama_available()

        # Se não detectado e usuário abriu o assistente de IA
        if not available:
            from PyQt6.QtWidgets import QDialog
            from src.gui.dialogs.ollama_wizard import OllamaWizardDialog
            wizard = OllamaWizardDialog(self)
            if wizard.exec() == QDialog.DialogCode.Accepted:
                available = self._rag_engine.is_ollama_available()

        if available:
            # Atualiza lista de modelos no UI
            models = self._rag_engine.list_local_models()
            installed_names = [m["name"] for m in models]
            self._rag_panel.update_model_list(installed_names)
            # Daemon presente mas SEM modelos (instalado por fora / wizard
            # pulado): puxa em background os recomendados pelo hardware —
            # o usuário nunca precisa abrir terminal para baixar modelo.
            if not installed_names:
                self._start_model_pull()

        model = self._config.get("rag.llm_model", "gemma4:e4b")
        self._rag_panel.set_ollama_status(available, model if available else "")
        count = self._rag_engine.get_indexed_count()
        self._rag_panel.set_indexed_count(count)

    def _on_model_changed(self, model_id: str) -> None:
        """Salva a preferência de modelo do usuário e atualiza o motor RAG."""
        self._config.set("rag.llm_model", model_id)
        if self._rag_engine:
            self._rag_engine.set_llm_model(model_id)
        self._statusbar.showMessage(f"🤖 Modelo IA alterado para {model_id}", 3000)
        # Sincroniza o indicador de status da interface
        self._rag_panel.set_ollama_status(True, model_id)

    def _show_rag_panel(self) -> None:
        """Navega para o painel do Assistente IA (visão cheia)."""
        # Se estiver ancorado no dock do leitor, devolve para a stack principal
        if self._rag_panel.parentWidget() != self._main_stack:
            if hasattr(self._reader_view, "_dock") and self._reader_view._dock.has_tab("assistant"):
                self._reader_view._dock.remove_tab("assistant")
            self._reader_view._ai_panel_container = None
            self._main_stack.insertWidget(3, self._rag_panel)
            self._reader_view._ai_panel_btn.setChecked(False)

        self._sidebar.show()
        self._rag_panel.set_standalone_mode(True)
        self._main_stack.setCurrentIndex(3)
        self._check_ollama_status()

    def _start_model_pull(self) -> None:
        """Baixa em background os modelos de IA recomendados pelo hardware."""
        worker = getattr(self, "_model_pull_worker", None)
        if worker is not None and worker.isRunning():
            return
        try:
            from src.core.hardware_capability_service import HardwareCapabilityService
            from src.gui.workers.install_worker import OllamaModelPullWorker

            hw = HardwareCapabilityService()
            models = [hw.get_recommended_llm_model(), HardwareCapabilityService.EMBED_MODEL]
            self._statusbar.showMessage(
                f"🤖 Baixando modelos de IA recomendados ({', '.join(models)})…", 10000)
            self._model_pull_worker = OllamaModelPullWorker(models, parent=self)
            self._model_pull_worker.progress_updated.connect(
                lambda msg: self._statusbar.showMessage(msg, 10000))
            self._model_pull_worker.finished_pull.connect(self._on_model_pull_finished)
            self._model_pull_worker.start()
        except Exception as exc:
            logger.warning(f"Falha ao iniciar o download de modelos (ignorado): {exc}")

    def _on_model_pull_finished(self, all_ok: bool) -> None:
        if all_ok:
            self._statusbar.showMessage("✅ Modelos de IA prontos — assistente disponível.", 6000)
        else:
            self._statusbar.showMessage(
                "⚠️ Download de modelos incompleto — verifique a conexão e reabra o app.", 8000)
        # Atualiza a lista de modelos no painel com o que chegou.
        try:
            if self._rag_engine is not None:
                models = self._rag_engine.list_local_models()
                self._rag_panel.update_model_list([m["name"] for m in models])
        except Exception as exc:
            logger.warning(f"Falha ao atualizar lista de modelos (ignorado): {exc}")

    def _on_rag_query(self, question: str) -> None:
        """Inicia uma consulta RAG em background."""
        if self._rag_engine is None:
            self._rag_panel.on_error(
                "RAGEngine não inicializado. Verifique se o ChromaDB está instalado."
            )
            return
        if self._rag_worker and self._rag_worker.isRunning():
            return
            
        ctx = self._rag_panel.get_reading_context()
        is_global = getattr(self._rag_panel, "_is_standalone", False)
        
        book_id = None
        if ctx and not is_global:
            book_id = ctx.get("book_id")
            # Anexa o contexto invisivelmente à query
            question_payload = f"Contexto de Leitura Atual:\nLivro: '{ctx['title']}' | ID do Livro: {ctx['book_id']} | Página: {ctx['page']}\nTexto visível:\n{ctx['text']}\n\n---\nPedido do Usuário: {question}"
        else:
            question_payload = question

        self._rag_worker = RAGWorker(
            self._rag_engine, mode=RAGWorker.MODE_QUERY, question=question_payload, book_id=book_id
        )
        self._rag_worker.token_received.connect(self._rag_panel.on_token_received)
        self._rag_worker.answer_complete.connect(self._rag_panel.on_answer_complete)
        self._rag_worker.sources_found.connect(self._rag_panel.on_sources_found)
        self._rag_worker.error_occurred.connect(self._rag_panel.on_error)
        self._rag_worker.ui_mutation_requested.connect(self._on_ui_mutation)
        self._rag_worker.finished_work.connect(
            lambda: self._rag_panel.set_indexed_count(
                self._rag_engine.get_indexed_count() if self._rag_engine else 0
            )
        )
        self._rag_worker.start()
        self._statusbar.showMessage("🧠 Consultando Assistente IA…")

    def _on_clear_chat(self) -> None:
        """Limpa a memória conversacional do contexto atual (livro ou global)."""
        if self._rag_engine is None:
            return
        ctx = self._rag_panel.get_reading_context()
        is_global = getattr(self._rag_panel, "_is_standalone", False)
        book_id = ctx.get("book_id") if (ctx and not is_global) else None
        self._rag_engine.clear_chat_history(book_id)

    def _on_ai_action_requested(self, action_type: str, text: str) -> None:
        """Processa requisições de IA vindas do menu de contexto de leitura."""
        if action_type == "translate":
            # Cartão no painel do assistente (substitui o antigo QMessageBox — a
            # tradução fica no mesmo lugar onde o resto da conversa acontece).
            if self._rag_panel.parentWidget() != self._reader_view:
                self._reader_view.set_ai_panel(self._rag_panel)
            self._reader_view.show_ai_panel()

            self._statusbar.showMessage(
                f"🌐 Traduzindo seleção ({len(text)} caracteres)...", 15000)
            from src.gui.translation_service import TranslationService

            def on_success(result):
                self._statusbar.clearMessage()
                self._rag_panel.show_translation_card(
                    f"Seleção ({len(text)} caracteres)", text, result)

            def on_error(err):
                self._statusbar.showMessage(f"⚠️ Erro na tradução offline: {err}", 5000)

            TranslationService.get_instance().translate_async(
                text=text,
                on_success=on_success,
                on_error=on_error
            )
            return

        elif action_type == "translate_audio":
            self._statusbar.showMessage("🌐 Traduzindo para narrar...", 5000)
            from src.gui.translation_service import TranslationService

            def on_audio_success(result):
                self._statusbar.clearMessage()
                self._reader_view.narrate_text(result)

            def on_audio_error(err):
                self._statusbar.showMessage(f"⚠️ Erro na tradução: {err}", 5000)

            TranslationService.get_instance().translate_async(
                text=text,
                on_success=on_audio_success,
                on_error=on_audio_error,
            )
            return

        elif action_type == "explain":
            question = f"Explique o contexto e o significado deste trecho detalhadamente: '{text}'"
        elif action_type == "search":
            question = f"Busque na web informações complementares sobre: '{text}' e resuma os achados."
        elif action_type == "save_note":
            question = f"Gere uma anotação sucinta, clara e em formato Markdown para o seguinte trecho (não precisa usar ferramentas, apenas responda com o texto da anotação): '{text}'"
        elif action_type == "flashcard":
            self._open_anki_export_dialog(front=text, back="")
            return
        elif action_type == "flashcard_qa":
            # Insight do proativo → LLM destila em pergunta/resposta (item 1 UX).
            self._generate_flashcard_qa(text)
            return
        elif action_type == "read_translated_page":
            # Página inteira: traduz offline (NLLB) e narra o resultado (item 7 UX).
            self._translate_and_narrate(text, enable_chaining=False)
            return
        elif action_type == "read_translated_page_chained":
            # Leitura contínua TRADUZIDA (Commit 5): narra e, ao terminar,
            # encadeia a tradução+narração da próxima página com texto.
            self._translate_and_narrate(text, enable_chaining=True)
            return
        elif action_type == "translate_page":
            # Página inteira como TEXTO: cartão no painel, sem narrar.
            self._translate_page_as_text(text)
            return
        elif action_type in ("explain_page", "summarize", "glossary", "flashcards"):
            from src.core.study_prompts import build_study_prompt
            question = build_study_prompt(action_type, text)
            if not question:
                self._statusbar.showMessage("⚠️ Nenhum texto na página para estudar.", 3000)
                return
        else:
            return
            
        # Garante que o painel esteja ancorado ao leitor e o mostra
        if self._rag_panel.parentWidget() != self._reader_view:
            self._reader_view.set_ai_panel(self._rag_panel)
            
        self._reader_view.show_ai_panel()
        
        # Preenche o input e envia automaticamente
        self._rag_panel._question_input.setText(question)
        self._rag_panel._on_send()

    def _show_flashcards(self) -> None:
        """Abre o diálogo de Flashcards (lista + modo estudo)."""
        from src.gui.dialogs.flashcards_dialog import FlashcardsDialog
        current_book_id = None
        if self._main_stack.currentIndex() == 1 and self._reader_view._book_id > 0:
            current_book_id = self._reader_view._book_id
        dialog = FlashcardsDialog(self._db, current_book_id=current_book_id, parent=self)
        dialog.exec()

    def _translate_and_narrate(self, text: str, enable_chaining: bool):
        """Traduz a página em background (NLLB) e narra o resultado em PT.

        Página já em português → narra direto (traduzir seria inútil).
        Graceful (ADR-005): erro de tradução vira aviso na statusbar E não
        encadeia a próxima página — o loop contínuo traduzido morre
        naturalmente em vez de continuar num estado inconsistente.

        ``enable_chaining``: False para a ação avulsa "Ler Página Traduzida"
        (Commit 4 e anteriores); True para a leitura contínua traduzida
        (Commit 5) — repassado para narrate_text(chain_continuous=...), que
        aciona _on_audio_finished → _continue_narration ao terminar.
        """
        from src.core.tts.language_detect import detect_language

        if getattr(self, "_page_translation_pending", False):
            self._statusbar.showMessage("🌐 Já estou traduzindo uma página — aguarde…", 3000)
            return

        reader = self._reader_view._reader
        page_label = f"{reader.current_page + 1}/{reader.total_pages}" if reader else "?"

        if detect_language(text).lower().startswith("pt"):
            self._statusbar.showMessage(
                f"ℹ️ Página {page_label} já está em português — narrando o original.", 4000)
            self._reader_view.narrate_text(text, chain_continuous=enable_chaining)
            return

        self._statusbar.showMessage(f"🌐 Traduzindo página {page_label}…", 60000)
        self._page_translation_pending = True

        def _on_success(result: str):
            self._page_translation_pending = False
            if not (result or "").strip():
                self._statusbar.showMessage("⚠️ Tradução vazia — nada a narrar.", 5000)
                return
            self._statusbar.showMessage(f"🔊 Narrando página {page_label}…", 5000)
            self._reader_view.narrate_text(result, chain_continuous=enable_chaining)

        def _on_error(err: str):
            self._page_translation_pending = False
            self._statusbar.showMessage(f"⚠️ Erro na tradução offline: {err}", 6000)
            # Sem encadear: o loop contínuo traduzido morre aqui (ADR-005) em
            # vez de tentar continuar a partir de um estado de erro.

        try:
            from src.gui.translation_service import TranslationService
            TranslationService.get_instance().translate_async(
                text, src_lang="en", tgt_lang="pt",
                on_success=_on_success, on_error=_on_error)
        except Exception as exc:
            self._page_translation_pending = False
            logger.warning(f"Falha ao iniciar a tradução da página (ignorado): {exc}")
            self._statusbar.showMessage("⚠️ Tradução indisponível no momento.", 5000)

    def _translate_page_as_text(self, text: str):
        """Traduz a página inteira como TEXTO (cartão no painel), sem narrar.

        Página já em português → mostra o texto original direto no cartão
        (evita chamar o NLLB à toa). Graceful (ADR-005): erro vira aviso na
        statusbar. O "aviso do que está sendo processado" é a contagem de
        caracteres na statusbar + no header do cartão.
        """
        from src.core.tts.language_detect import detect_language

        if getattr(self, "_page_translation_pending", False):
            self._statusbar.showMessage("🌐 Já estou traduzindo uma página — aguarde…", 3000)
            return

        page = self._reader_view._reader.current_page + 1 if self._reader_view._reader else 0
        source_desc = f"Página {page} inteira"

        if self._rag_panel.parentWidget() != self._reader_view:
            self._reader_view.set_ai_panel(self._rag_panel)
        self._reader_view.show_ai_panel()

        if detect_language(text).lower().startswith("pt"):
            self._statusbar.showMessage("ℹ️ A página já está em português.", 4000)
            self._rag_panel.show_translation_card(source_desc, text, text)
            return

        self._statusbar.showMessage(
            f"🌐 Traduzindo {source_desc.lower()} ({len(text)} caracteres)…", 60000)
        self._page_translation_pending = True

        def _on_success(result: str):
            self._page_translation_pending = False
            if not (result or "").strip():
                self._statusbar.showMessage("⚠️ Tradução vazia.", 5000)
                return
            self._statusbar.clearMessage()
            self._rag_panel.show_translation_card(source_desc, text, result)

        def _on_error(err: str):
            self._page_translation_pending = False
            self._statusbar.showMessage(f"⚠️ Erro na tradução offline: {err}", 6000)

        try:
            from src.gui.translation_service import TranslationService
            TranslationService.get_instance().translate_async(
                text, src_lang="en", tgt_lang="pt",
                on_success=_on_success, on_error=_on_error)
        except Exception as exc:
            self._page_translation_pending = False
            logger.warning(f"Falha ao iniciar a tradução da página (ignorado): {exc}")
            self._statusbar.showMessage("⚠️ Tradução indisponível no momento.", 5000)

    def _generate_flashcard_qa(self, text: str):
        """Gera pergunta/resposta a partir de um insight e abre o diálogo do Anki.

        Fallback (Ollama fora / resposta inválida): abre o diálogo com o insight
        no VERSO e a pergunta em branco — nunca mais o insight como "pergunta".
        """
        from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker

        worker = getattr(self, "_flashcard_qa_worker", None)
        if worker is not None and worker.isRunning():
            self._statusbar.showMessage("🃏 Já estou gerando um flashcard — aguarde…", 3000)
            return

        self._statusbar.showMessage("🃏 Gerando flashcard (pergunta/resposta)…", 15000)
        self._flashcard_qa_worker = FlashcardQAWorker(
            text,
            ollama_url=self._config.get("rag.ollama_url", "http://localhost:11434"),
            parent=self,
        )

        # Feedback visível: a geração pode levar alguns segundos; o diálogo de
        # progresso (indeterminado, com Cancelar) deixa claro que algo acontece.
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog("🃏 Gerando flashcard (pergunta/resposta)…",
                                   "Cancelar", 0, 0, self)
        progress.setWindowTitle("Flashcard")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.canceled.connect(self._flashcard_qa_worker.cancel)
        progress.show()
        self._flashcard_qa_progress = progress

        def _close_progress():
            try:
                progress.canceled.disconnect(self._flashcard_qa_worker.cancel)
            except (TypeError, RuntimeError):
                pass
            progress.close()

        def _on_generated(front: str, back: str):
            _close_progress()
            self._statusbar.clearMessage()
            self._open_anki_export_dialog(front=front, back=back)

        def _on_failed(reason: str):
            _close_progress()
            logger.warning(f"Flashcard P/R indisponível ({reason}); usando fallback.")
            self._statusbar.showMessage(
                "⚠️ Sem LLM agora — complete a pergunta manualmente.", 5000)
            self._open_anki_export_dialog(front="", back=text)

        self._flashcard_qa_worker.generated.connect(_on_generated)
        self._flashcard_qa_worker.failed.connect(_on_failed)
        self._flashcard_qa_worker.start()

    def _open_anki_export_dialog(self, front: str, back: str):
        """Abre o diálogo de exportação para o Anki."""
        from src.core.anki_service import AnkiService
        from src.gui.widgets.anki_export_dialog import AnkiExportDialog
        from src.gui.workers.anki_worker import AnkiAddNoteWorker
        from PyQt6.QtWidgets import QMessageBox

        service = AnkiService()
        dialog = AnkiExportDialog(service=service, initial_front=front, initial_back=back, parent=self)
        if dialog.exec() == AnkiExportDialog.DialogCode.Accepted and dialog.saved:
            self._statusbar.showMessage("⏳ Enviando card para o Anki...", 3000)

            # Persiste o flashcard localmente (fonte de verdade consultável no app + estudo)
            try:
                fc_book_id = self._reader_view._book_id if self._reader_view._book_id > 0 else None
                self._db.add_flashcard(
                    front=dialog.result_front,
                    back=dialog.result_back,
                    book_id=fc_book_id,
                    deck=dialog.result_deck,
                )
            except Exception as exc:
                print(f"[Flashcards] Falha ao salvar card localmente: {exc}", flush=True)


            self._anki_worker = AnkiAddNoteWorker(
                service=service,
                deck_name=dialog.result_deck,
                front=dialog.result_front,
                back=dialog.result_back
            )
            
            def on_finished(note_id):
                if note_id is not None:
                    self._statusbar.showMessage("✅ Flashcard salvo no Anki com sucesso!", 5000)
                else:
                    self._statusbar.showMessage("⚠️ Anki fechado. Flashcard salvo na fila local de fallback.", 5000)
            
            def on_error(err):
                QMessageBox.warning(self, "Erro no Anki", f"Falha ao salvar flashcard:\n{err}")
                
            self._anki_worker.finished.connect(on_finished)
            self._anki_worker.error.connect(on_error)
            self._anki_worker.start()

    def _on_rag_index_all(self) -> None:
        """Reindexação completa da biblioteca em background."""
        if self._rag_engine is None:
            self._rag_panel.on_error(
                "RAGEngine não inicializado. Certifique-se de que o Ollama está rodando."
            )
            return
        if self._rag_worker and self._rag_worker.isRunning():
            self._statusbar.showMessage("⚠️ Uma operação RAG já está em andamento.", 3000)
            return

        try:
            self._rag_worker = RAGWorker(self._rag_engine, mode=RAGWorker.MODE_INDEX_ALL)
            self._rag_worker.progress_updated.connect(self._rag_panel.on_progress_updated)
            self._rag_worker.file_not_found.connect(self._on_file_not_found)
            self._rag_worker.error_occurred.connect(self._handle_rag_error)
            self._rag_worker.finished_work.connect(self._rag_panel.on_indexing_complete)
            self._rag_worker.finished_work.connect(
                lambda: self._rag_panel.set_indexed_count(
                    self._rag_engine.get_indexed_count() if self._rag_engine else 0
                )
            )
            self._rag_worker.finished_work.connect(
                lambda: self._statusbar.showMessage("✅ Indexação RAG concluída", 4000)
            )
            self._rag_worker.start()
            self._statusbar.showMessage("🔄 Indexando biblioteca para IA…")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._handle_rag_error(str(e))

    def _handle_rag_error(self, err: str) -> None:
        self._statusbar.showMessage(f"⚠️ Erro RAG: {err}", 5000)
        self._rag_panel.on_error(err)
        QMessageBox.critical(self, "Falha na IA", f"Ocorreu um erro no processamento do assistente:\n\n{err}")

    def _on_rag_stop(self) -> None:
        """Para o worker RAG em andamento."""
        if self._rag_worker and self._rag_worker.isRunning():
            self._rag_worker.stop()
            self._statusbar.showMessage("⛔ Operação IA cancelada.", 3000)

    def _on_ui_mutation(self, action_type: str, data: dict) -> None:
        """Processa mutações visuais solicitadas pela IA (Main Thread).

        Chamado via sinal Qt a partir da worker thread, portanto já está
        na Main Thread e é seguro manipular widgets.
        """
        try:
            if action_type == "highlight":
                self._handle_ai_highlight(data)
            elif action_type == "bookmark":
                self._handle_ai_bookmark(data)
            else:
                print(f"[UI Mutation] Ação desconhecida: {action_type}", flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._statusbar.showMessage(f"⚠️ Erro na mutação visual: {exc}", 4000)

    def _handle_ai_highlight(self, data: dict) -> None:
        """Destaca texto na página atual do livro aberto."""
        from src.readers.pdf_reader import PDFReader

        text_to_find = data.get("text_to_find", "")
        color = data.get("color", "#fbbf24")

        # Verifica se temos um leitor PDF aberto
        reader = self._reader_view._reader
        if not reader or not isinstance(reader, PDFReader):
            self._statusbar.showMessage("⚠️ Destaque só disponível em PDFs.", 3000)
            return

        current_page = reader.current_page

        # Usa PyMuPDF search_for para encontrar o texto na página
        page_obj = reader._doc[current_page]
        instances = page_obj.search_for(text_to_find)

        if not instances:
            # Tenta busca parcial (primeiras 40 chars)
            if len(text_to_find) > 40:
                instances = page_obj.search_for(text_to_find[:40])

        if not instances:
            self._statusbar.showMessage(
                f"🔍 Texto não encontrado na pág. {current_page + 1} para destaque.", 3000
            )
            return

        # Para cada ocorrência, salva no banco e re-renderiza
        import json
        for rect in instances:
            # Normaliza coordenadas para percentual
            page_rect = page_obj.rect
            coords = (
                rect.x0 / page_rect.width,
                rect.y0 / page_rect.height,
                rect.x1 / page_rect.width,
                rect.y1 / page_rect.height,
            )
            position_data = json.dumps({"coords": list(coords)})
            book_id = self._reader_view._book_id

            self._db.add_annotation(
                book_id=book_id,
                page_number=current_page,
                content=text_to_find[:200],
                highlight_color=color,
                annotation_type="highlight",
                position_data=position_data,
            )

        # Recarrega anotações para renderizar os destaques
        book_id = self._reader_view._book_id
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)
        self._statusbar.showMessage(
            f"📝 IA destacou \"{text_to_find[:30]}...\" na pág. {current_page + 1}", 4000
        )

    def _handle_ai_bookmark(self, data: dict) -> None:
        """Cria um marcador inteligente (anotação tipo bookmark) na página atual."""
        note = data.get("note", "")
        book_id = self._reader_view._book_id

        if book_id <= 0:
            self._statusbar.showMessage("⚠️ Nenhum livro aberto para criar marcador.", 3000)
            return

        current_page = 0
        if self._reader_view._reader:
            current_page = self._reader_view._reader.current_page

        self._db.add_annotation(
            book_id=book_id,
            page_number=current_page,
            content=f"🔖 {note}",
            highlight_color="#6366f1",
            annotation_type="ai_bookmark",
            position_data="{}",
        )

        # Recarrega anotações
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)
        self._statusbar.showMessage(
            f"🔖 Marcador IA criado na pág. {current_page + 1}", 4000
        )

    def _on_bulk_delete(self, book_ids: list) -> None:
        """Remove livros do SQLite e do ChromaDB simultaneamente."""
        removed = 0
        for book_id in book_ids:
            try:
                self._db.delete_book(book_id)
                removed += 1
            except Exception as exc:
                self._statusbar.showMessage(f"⚠️ Erro ao remover livro {book_id}: {exc}", 4000)
            if self._rag_engine:
                try:
                    self._rag_engine.delete_book_index(book_id)
                except Exception:
                    pass
        self._load_library()
        self._book_details.clear()
        self._statusbar.showMessage(
            f"🗑️ {removed} {'livro removido' if removed == 1 else 'livros removidos'} "
            "do banco e do índice vetorial.", 5000
        )

    def _on_file_not_found(self, book_id: int) -> None:
        """Notificação visual quando a indexação encontra arquivo ausente."""
        self._statusbar.showMessage(
            f"⚠️ Livro #{book_id}: arquivo não encontrado no disco — ignorado na indexação.",
            6000,
        )

    # ── Monitoramento ──────────────────────────────────────────────────

    def _setup_watcher(self):
        """Inicia o monitoramento de diretórios configurados."""
        watch_dirs = self._config.get("library.watch_directories", [])
        self._watcher = None
        if watch_dirs:
            self._watcher = DirectoryWatcher(
                self._library, watch_dirs, interval_seconds=60
            )
            self._watcher.import_completed.connect(self._on_watcher_import)
            self._watcher.error_occurred.connect(
                lambda msg: self._statusbar.showMessage(f"⚠️ {msg}", 5000)
            )
            self._watcher.start()

    def _on_watcher_import(self, count: int):
        """Callback quando o watcher importa novos arquivos."""
        self._statusbar.showMessage(
            f"📂 Auto-importação: {count} novo(s) arquivo(s) detectado(s)", 5000
        )
        self._load_library()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Para o serviço do grafo (cancel cooperativo)
        try:
            self._graph_service.shutdown()
        except Exception as exc:
            logger.warning(f"Falha ao encerrar o serviço do grafo (ignorado): {exc}")
        # Para a auto-indexação
        try:
            self._auto_index_service.shutdown()
        except Exception as exc:
            logger.warning(f"Falha ao encerrar a auto-indexação (ignorado): {exc}")
        # Para o worker RAG
        if self._rag_worker and self._rag_worker.isRunning():
            self._rag_worker.stop()
            self._rag_worker.wait(2000)
        # Para o watcher
        if self._watcher and self._watcher.is_active:
            self._watcher.stop()
            self._watcher.wait(3000)
        # Salva dimensões da janela
        if not self.isMaximized():
            self._config.set("window.width", self.width())
            self._config.set("window.height", self.height())
        self._config.set("window.maximized", self.isMaximized())
        self._reader_view.close_reader()
        self._db.close()
        super().closeEvent(event)
