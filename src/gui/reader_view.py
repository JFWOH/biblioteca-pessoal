"""Visualização do leitor de documentos."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QKeySequence, QShortcut
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src.readers.base_reader import BaseReader, PageContent
from src.readers.reader_factory import create_reader
from src.gui.widgets.toc_widget import TOCWidget
from src.gui.widgets.reading_progress import ReadingProgressBar
from src.gui.widgets.annotation_panel import AnnotationPanel
from src.gui.widgets.search_overlay import DocumentSearchBar
from src.gui.styles import get_reader_css


class ReaderView(QWidget):
    """Leitor multi-formato com navegação, TOC e progresso."""

    closed = pyqtSignal()
    progress_changed = pyqtSignal(int, int, int)  # book_id, page, total
    annotation_added = pyqtSignal(int, dict)       # book_id, annotation_data
    annotation_deleted = pyqtSignal(int)            # annotation_id
    fullscreen_toggled = pyqtSignal(bool)           # is_fullscreen

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reader: BaseReader | None = None
        self._book_id: int = 0
        self._theme = "dark"
        self._is_fullscreen = False
        self._search_results: list[dict] = []
        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar do leitor
        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet("background-color: #18181b; border-bottom: 1px solid #27272a;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)

        # Botão voltar
        back_btn = QPushButton("← Biblioteca")
        back_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #818cf8;
                          font-size: 13px; font-weight: 500; padding: 8px 12px; }
            QPushButton:hover { color: #a5b4fc; }
        """)
        back_btn.clicked.connect(self.closed.emit)
        tb_layout.addWidget(back_btn)

        # Título do documento
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            "color: #e4e4e7; font-size: 13px; font-weight: 600;"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_layout.addWidget(self._title_label, stretch=1)

        # Navegação de páginas
        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setStyleSheet("""
            QPushButton { background: #27272a; border: none; border-radius: 6px;
                          color: #e4e4e7; font-size: 14px; }
            QPushButton:hover { background: #3f3f46; }
        """)
        self._prev_btn.clicked.connect(self._go_prev)
        tb_layout.addWidget(self._prev_btn)

        self._page_label = QLabel("0/0")
        self._page_label.setFixedWidth(80)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("color: #71717a; font-size: 12px;")
        tb_layout.addWidget(self._page_label)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setStyleSheet("""
            QPushButton { background: #27272a; border: none; border-radius: 6px;
                          color: #e4e4e7; font-size: 14px; }
            QPushButton:hover { background: #3f3f46; }
        """)
        self._next_btn.clicked.connect(self._go_next)
        tb_layout.addWidget(self._next_btn)

        # Zoom
        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(28, 28)
        zoom_out.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #27272a;
                          border-radius: 4px; color: #a1a1aa; font-size: 16px; }
            QPushButton:hover { background: #27272a; }
        """)
        zoom_out.clicked.connect(self._zoom_out)
        tb_layout.addWidget(zoom_out)

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(28, 28)
        zoom_in.setStyleSheet(zoom_out.styleSheet())
        zoom_in.clicked.connect(self._zoom_in)
        tb_layout.addWidget(zoom_in)

        # Separador
        sep = QLabel("│")
        sep.setStyleSheet("color: #27272a; font-size: 16px;")
        tb_layout.addWidget(sep)

        # Botão de anotações
        self._annotations_btn = QPushButton("📝")
        self._annotations_btn.setFixedSize(32, 32)
        self._annotations_btn.setToolTip("Painel de Anotações")
        self._annotations_btn.setCheckable(True)
        self._annotations_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #27272a;
                          border-radius: 6px; font-size: 16px; }
            QPushButton:hover { background: #27272a; }
            QPushButton:checked { background: rgba(99, 102, 241, 0.2);
                                  border-color: #6366f1; }
        """)
        self._annotations_btn.clicked.connect(self._toggle_annotations)
        tb_layout.addWidget(self._annotations_btn)

        # Botão busca no documento
        search_btn = QPushButton("🔍")
        search_btn.setFixedSize(32, 32)
        search_btn.setToolTip("Buscar no documento (Ctrl+F)")
        search_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #27272a;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #27272a; }
        """)
        search_btn.clicked.connect(self._toggle_search)
        tb_layout.addWidget(search_btn)

        # Botão tela cheia
        self._fullscreen_btn = QPushButton("⛶")
        self._fullscreen_btn.setFixedSize(32, 32)
        self._fullscreen_btn.setToolTip("Tela cheia (F11)")
        self._fullscreen_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #27272a;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #27272a; }
        """)
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        tb_layout.addWidget(self._fullscreen_btn)

        self._toolbar = toolbar
        layout.addWidget(toolbar)

        # Barra de busca overlay (abaixo da toolbar)
        self._search_bar = DocumentSearchBar()
        self._search_bar.search_requested.connect(self._on_document_search)
        self._search_bar.navigate_result.connect(self._on_search_navigate)
        self._search_bar.closed.connect(lambda: self._search_results.clear())
        layout.addWidget(self._search_bar)

        # Conteúdo: Splitter com TOC + Visualização
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Painel TOC
        self._toc_widget = TOCWidget()
        self._toc_widget.setMinimumWidth(200)
        self._toc_widget.setMaximumWidth(300)
        self._toc_widget.page_selected.connect(self._go_to_page)
        splitter.addWidget(self._toc_widget)

        # Stack para diferentes tipos de conteúdo
        self._content_stack = QStackedWidget()

        # Visualizador de imagem (para PDF)
        self._image_scroll = QScrollArea()
        self._image_scroll.setWidgetResizable(True)
        self._image_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_scroll.setStyleSheet("background-color: #0a0a0f;")
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_scroll.setWidget(self._image_label)
        self._content_stack.addWidget(self._image_scroll)  # index 0

        # Visualizador HTML (para EPUB, TXT, DOCX)
        self._web_view = QWebEngineView()
        self._content_stack.addWidget(self._web_view)  # index 1

        splitter.addWidget(self._content_stack)

        # Painel de anotações (inicialmente oculto)
        self._annotation_panel = AnnotationPanel()
        self._annotation_panel.hide()
        self._annotation_panel.annotation_added.connect(self._on_annotation_added)
        self._annotation_panel.annotation_deleted.connect(
            lambda ann_id: self.annotation_deleted.emit(ann_id)
        )
        self._annotation_panel.goto_page.connect(self._go_to_page)
        splitter.addWidget(self._annotation_panel)

        splitter.setStretchFactor(0, 0)  # TOC fixo
        splitter.setStretchFactor(1, 1)  # Conteúdo expande
        splitter.setStretchFactor(2, 0)  # Anotações fixo

        layout.addWidget(splitter, stretch=1)

        # Barra de progresso inferior
        progress_bar_widget = QWidget()
        progress_bar_widget.setFixedHeight(28)
        progress_bar_widget.setStyleSheet(
            "background-color: #18181b; border-top: 1px solid #27272a;"
        )
        pb_layout = QHBoxLayout(progress_bar_widget)
        pb_layout.setContentsMargins(16, 4, 16, 4)
        self._progress_bar = ReadingProgressBar()
        pb_layout.addWidget(self._progress_bar)
        layout.addWidget(progress_bar_widget)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._go_next)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._go_prev)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_search)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._toggle_fullscreen)

    def open_book(self, book_data: dict, start_page: int = 0):
        """Abre um livro para leitura."""
        filepath = book_data.get("file_path", "")
        if not filepath:
            return

        self._book_id = book_data.get("id", 0)
        self._title_label.setText(book_data.get("title", ""))

        # Fecha leitor anterior
        if self._reader and self._reader.is_open:
            self._reader.close()

        # Cria o leitor apropriado
        self._reader = create_reader(filepath)
        self._reader.open()

        # Carrega TOC
        toc = self._reader.get_toc()
        self._toc_widget.load_toc(toc)

        # Vai para a página inicial
        self._go_to_page(start_page)

    def _render_page(self, content: PageContent):
        """Renderiza o conteúdo da página."""
        if content.content_type == "image":
            # PDF — renderiza como imagem
            pixmap = QPixmap()
            pixmap.loadFromData(content.content)
            self._image_label.setPixmap(pixmap)
            self._content_stack.setCurrentIndex(0)
        elif content.content_type in ("html", "text"):
            # EPUB/TXT/DOCX — renderiza como HTML
            css = get_reader_css(self._theme)
            html = f"""<!DOCTYPE html>
            <html><head><style>{css}</style></head>
            <body>{content.content}</body></html>"""
            self._web_view.setHtml(html)
            self._content_stack.setCurrentIndex(1)

        # Atualiza indicadores
        page = content.page_number
        total = content.total_pages
        self._page_label.setText(f"{page + 1}/{total}")
        self._progress_bar.set_page_info(page + 1, total)
        self.progress_changed.emit(self._book_id, page, total)

    def _go_to_page(self, page: int):
        if self._reader:
            content = self._reader.go_to_page(page)
            if content:
                self._render_page(content)

    def _go_next(self):
        if self._reader:
            content = self._reader.next_page()
            if content:
                self._render_page(content)

    def _go_prev(self):
        if self._reader:
            content = self._reader.previous_page()
            if content:
                self._render_page(content)

    def _zoom_in(self):
        if self._reader and hasattr(self._reader, 'zoom'):
            self._reader.zoom = self._reader.zoom + 0.25
            self._go_to_page(self._reader.current_page)
        elif self._content_stack.currentIndex() == 1:
            self._web_view.setZoomFactor(self._web_view.zoomFactor() + 0.1)

    def _zoom_out(self):
        if self._reader and hasattr(self._reader, 'zoom'):
            self._reader.zoom = self._reader.zoom - 0.25
            self._go_to_page(self._reader.current_page)
        elif self._content_stack.currentIndex() == 1:
            self._web_view.setZoomFactor(self._web_view.zoomFactor() - 0.1)

    def close_reader(self):
        """Fecha o leitor atual."""
        if self._reader and self._reader.is_open:
            self._reader.close()
            self._reader = None

    def set_theme(self, theme: str):
        self._theme = theme
        if self._reader and self._reader.is_open:
            self._go_to_page(self._reader.current_page)

    def _toggle_annotations(self):
        """Mostra/oculta o painel de anotações."""
        visible = self._annotation_panel.isVisible()
        self._annotation_panel.setVisible(not visible)

    def _on_annotation_added(self, data: dict):
        """Emite sinal quando uma anotação é adicionada."""
        self.annotation_added.emit(self._book_id, data)

    def load_annotations(self, annotations: list[dict]):
        """Carrega anotações no painel."""
        self._annotation_panel.load_annotations(annotations)

    def set_annotation_page(self, page: int):
        """Atualiza a página atual para o painel de anotações."""
        self._annotation_panel.set_page(page)

    # ── Busca no Documento ────────────────────────────────────────────

    def _toggle_search(self):
        """Mostra/oculta a barra de busca."""
        if self._search_bar.isVisible():
            self._search_bar.close_bar()
        else:
            self._search_bar.show_bar()

    def _on_document_search(self, query: str):
        """Realiza busca no documento."""
        if not self._reader:
            return
        self._search_results = self._reader.search_text(query)
        self._search_bar.set_results(self._search_results)

    def _on_search_navigate(self, index: int):
        """Navega para um resultado de busca."""
        if 0 <= index < len(self._search_results):
            result = self._search_results[index]
            page = result.get("page", 0)
            self._go_to_page(page)

    # ── Tela Cheia ─────────────────────────────────────────────────

    def _toggle_fullscreen(self):
        """Alterna modo tela cheia."""
        self._is_fullscreen = not self._is_fullscreen
        self.fullscreen_toggled.emit(self._is_fullscreen)
        if self._is_fullscreen:
            self._toolbar.hide()
            self._fullscreen_btn.setText("⬜")
        else:
            self._toolbar.show()
            self._fullscreen_btn.setText("⛶")

    def _on_escape(self):
        """Escape: fecha busca → sai do fullscreen → fecha leitor."""
        if self._search_bar.isVisible():
            self._search_bar.close_bar()
        elif self._is_fullscreen:
            self._toggle_fullscreen()
        else:
            self.closed.emit()
