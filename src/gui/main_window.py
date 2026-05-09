"""Janela principal da aplicação Biblioteca Pessoal."""

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
from src.gui.settings_dialog import SettingsDialog
from src.gui.collection_dialog import CollectionDialog, AddToCollectionDialog
from src.gui.widgets.stats_panel import StatsPanel
from src.utils.constants import FILE_FILTER, DATA_DIR
from src.utils.export import export_annotations_markdown
from src.core.watcher import DirectoryWatcher


class MainWindow(QMainWindow):
    """Janela principal da Biblioteca Pessoal."""

    def __init__(self):
        super().__init__()

        # Inicializa core
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._db = LibraryDB()
        self._config = ConfigManager()
        self._library = LibraryManager(self._db, self._config)
        self._search_engine = SearchEngine(self._db)

        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._setup_statusbar()
        self._apply_theme()
        self._load_library()
        self._setup_watcher()

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

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.section_changed.connect(self._on_section_changed)
        main_layout.addWidget(self._sidebar)

        # Conteúdo principal (stack: biblioteca | leitor)
        self._main_stack = QStackedWidget()

        # ── Página da Biblioteca ──
        library_page = QWidget()
        lib_layout = QVBoxLayout(library_page)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(0)

        # Search bar
        search_container = QWidget()
        search_container.setStyleSheet(
            "background-color: #0f0f17; border-bottom: 1px solid #1e1e24;"
        )
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
        lib_splitter.addWidget(self._library_view)

        self._book_details = BookDetails(db=self._db)
        self._book_details.open_requested.connect(self._on_book_open)
        self._book_details.favorite_toggled.connect(self._on_favorite_toggle)
        self._book_details.delete_requested.connect(self._on_delete_book)
        self._book_details.rating_changed.connect(self._on_rating_changed)
        self._book_details.add_to_collection_requested.connect(self._add_book_to_collection)
        lib_splitter.addWidget(self._book_details)

        lib_splitter.setStretchFactor(0, 1)
        lib_splitter.setStretchFactor(1, 0)

        lib_layout.addWidget(lib_splitter, stretch=1)
        self._main_stack.addWidget(library_page)  # index 0

        # ── Página do Leitor ──
        self._reader_view = ReaderView()
        self._reader_view.closed.connect(self._close_reader)
        self._reader_view.progress_changed.connect(self._on_progress)
        self._reader_view.annotation_added.connect(self._on_annotation_added)
        self._reader_view.annotation_deleted.connect(self._on_annotation_deleted)
        self._reader_view.fullscreen_toggled.connect(self._on_fullscreen)
        self._main_stack.addWidget(self._reader_view)  # index 1

        # ── Página de Estatísticas ──
        self._stats_panel = StatsPanel()
        self._main_stack.addWidget(self._stats_panel)  # index 2

        main_layout.addWidget(self._main_stack, stretch=1)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._update_statusbar()

    def _apply_theme(self):
        theme = self._config.theme
        self.setStyleSheet(get_theme(theme))
        self._reader_view.set_theme(theme)

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
        else:
            books = self._db.get_all_books()

        self._library_view.load_books(books)
        stats = self._db.get_statistics()
        self._sidebar.update_stats(stats)
        self._update_statusbar()

    # ── Handlers ───────────────────────────────────────────────────────

    def _on_section_changed(self, section: str):
        self._book_details.clear()
        if section == "stats":
            stats = self._db.get_statistics()
            self._stats_panel.update_stats(stats)
            self._main_stack.setCurrentIndex(2)
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
        self._main_stack.setCurrentIndex(1)
        self._sidebar.hide()
        self._config.add_recent_file(filepath)

        # Carrega anotações existentes
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)

    def _close_reader(self):
        self._reader_view.close_reader()
        self._main_stack.setCurrentIndex(0)
        self._sidebar.show()
        self._load_library()

    def _on_progress(self, book_id: int, page: int, total: int):
        self._db.update_reading_progress(book_id, page, total)
        self._reader_view.set_annotation_page(page)

    def _on_annotation_added(self, book_id: int, data: dict):
        """Persiste uma nova anotação no banco."""
        self._db.add_annotation(
            book_id=book_id,
            page_number=data.get("page", 0),
            content=data.get("content", ""),
            highlight_color=data.get("color", "#fbbf24"),
            annotation_type=data.get("type", "note"),
        )
        # Recarrega anotações no painel
        annotations = self._db.get_annotations(book_id)
        self._reader_view.load_annotations(annotations)

    def _on_annotation_deleted(self, annotation_id: int):
        """Remove uma anotação do banco."""
        self._db.delete_annotation(annotation_id)
        # Recarrega (precisa saber o book_id — pega do reader)
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

    def _show_settings(self):
        """Abre o diálogo de configurações."""
        dialog = SettingsDialog(self._config, self)
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

    def _add_book_to_collection(self, book_id: int):
        """Abre diálogo para adicionar livro a uma coleção."""
        dialog = AddToCollectionDialog(self._db, book_id, self)
        dialog.exec()

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
