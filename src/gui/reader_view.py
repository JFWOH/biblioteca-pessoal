"""Visualização do leitor de documentos."""

import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QMenu, QRubberBand,
    QToolButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize, QEvent
from PyQt6.QtGui import QPixmap, QKeySequence, QShortcut, QAction, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src.readers.base_reader import BaseReader, PageContent
from src.readers.reader_factory import create_reader
from src.gui.widgets.toc_widget import TOCWidget
from src.gui.widgets.reading_progress import ReadingProgressBar
from src.gui.widgets.annotation_panel import AnnotationPanel
from src.gui.widgets.search_overlay import DocumentSearchBar
from src.gui.styles import get_reader_css
from src.gui.widgets.proactive_footer import ProactiveFooterWidget
from src.gui.widgets.selection_popover import SelectionActionPopover
from src.gui.widgets.reader_dock import ReaderDock
from src.gui.widgets.proactive_insights_panel import ProactiveInsightsPanel
from src.gui.proactive_reader_service import ProactiveReaderService
from src.core.proactive_observation import confidence_to_float, obs_dict_from_row
from PyQt6.QtWidgets import QComboBox

logger = logging.getLogger(__name__)


class ReaderView(QWidget):
    """Leitor multi-formato com navegação, TOC e progresso."""

    closed = pyqtSignal()
    progress_changed = pyqtSignal(int, int, int)  # book_id, page, total
    annotation_added = pyqtSignal(int, dict)       # book_id, annotation_data
    annotation_deleted = pyqtSignal(int)            # annotation_id
    fullscreen_toggled = pyqtSignal(bool)           # is_fullscreen
    reading_context_updated = pyqtSignal(int, str, int, str) # book_id, title, page_number, page_text
    ai_action_requested = pyqtSignal(str, str)      # action_type, text

    def __init__(self, parent=None, tts_router=None, rag_engine=None, db=None):
        super().__init__(parent)
        self._tts_router = tts_router
        self._rag_engine = rag_engine
        self._db = db  # LibraryDB (core puro) para persistir observações proativas
        self._reader: BaseReader | None = None
        self._book_id: int = 0
        self._theme = "dark"
        self._is_fullscreen = False
        self._search_results: list[dict] = []
        self._annotations: list[dict] = []
        # Página 1-based da última observação proativa e id da obs no rodapé
        # (para persistir/dispensar em ai_observations — Fase 1b).
        self._current_proactive_page: int = 0
        # Texto da página atual (p/ avaliar ao ligar o proativo). NÃO usar o nome
        # _current_page_text: colidiria com o MÉTODO homônimo do menu de estudo.
        self._last_page_text: str = ""
        self._audio_paused: bool = False   # narração pausada (retomável no mesmo ponto)
        self._footer_obs_id = None
        self._proactive_service = ProactiveReaderService(parent=self)
        self._proactive_service.observation_ready.connect(self._on_proactive_observation)
        self._proactive_service.error_occurred.connect(self._on_proactive_error)
        # Cross-reference proativo: dá ao agente acesso de leitura ao índice vetorial
        # para conectar a página atual a outros livros da biblioteca.
        if rag_engine is not None:
            self._proactive_service.set_cross_reference(self._proactive_cross_ref)
        self._setup_ui()
        self._setup_shortcuts()
        self.reading_context_updated.connect(
            lambda b, t, p, txt: self._proactive_service.process_page_context(txt, p, b)
        )

    def _proactive_cross_ref(self, page_text: str):
        """Busca o conceito da página em toda a biblioteca (roda na thread do worker).

        A exclusão do livro atual e o limiar de relevância são aplicados em
        format_cross_reference. Devolve [] em caso de qualquer falha.
        """
        try:
            return self._rag_engine.search_similar(page_text[:600], n_results=5)
        except Exception:
            return []

    def _setup_ui(self):
        # O layout raiz agora é um QSplitter horizontal para Side-by-Side
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_layout.addWidget(self._main_splitter)

        # Container esquerdo (Documento)
        self._left_pane = QWidget()
        left_layout = QVBoxLayout(self._left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Toolbar do leitor
        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet("background-color: #20242d; border-bottom: 1px solid #2d333f;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)

        # Botão voltar
        back_btn = QPushButton("← Biblioteca")
        back_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #10b981;
                          font-size: 13px; font-weight: 500; padding: 8px 12px; }
            QPushButton:hover { color: #34d399; }
        """)
        back_btn.clicked.connect(self.closed.emit)
        tb_layout.addWidget(back_btn)

        # Título do documento
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            "color: #e5e7eb; font-size: 13px; font-weight: 600;"
        )
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Deixa o título encolher livremente para nunca empurrar/cortar os botões
        # da direita (ex.: o "⋯" com Página Dupla) quando o espaço fica curto.
        self._title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._title_label.setMinimumWidth(0)
        tb_layout.addWidget(self._title_label, stretch=1)

        # Navegação de páginas
        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setStyleSheet("""
            QPushButton { background: #161920; border: none; border-radius: 6px;
                          color: #cbd5e1; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._prev_btn.clicked.connect(self._go_prev)
        tb_layout.addWidget(self._prev_btn)

        self._page_label = QLabel("0/0")
        self._page_label.setFixedWidth(80)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        tb_layout.addWidget(self._page_label)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setStyleSheet("""
            QPushButton { background: #161920; border: none; border-radius: 6px;
                          color: #cbd5e1; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._next_btn.clicked.connect(self._go_next)
        tb_layout.addWidget(self._next_btn)

        # Zoom
        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(28, 28)
        zoom_out.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 4px; color: #94a3b8; font-size: 16px; }
            QPushButton:hover { background: #2d333f; }
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
        sep.setStyleSheet("color: #2d333f; font-size: 16px;")
        tb_layout.addWidget(sep)

        # Botão de anotações
        self._annotations_btn = QPushButton("📝")
        self._annotations_btn.setFixedSize(32, 32)
        self._annotations_btn.setToolTip("Painel de Anotações")
        self._annotations_btn.setCheckable(True)
        self._annotations_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 16px; }
            QPushButton:hover { background: #2d333f; }
            QPushButton:checked { background: rgba(16, 185, 129, 0.2);
                                  border-color: #10b981; }
        """)
        self._annotations_btn.clicked.connect(self._toggle_annotations)
        tb_layout.addWidget(self._annotations_btn)

        # Botão busca no documento
        search_btn = QPushButton("🔍")
        search_btn.setFixedSize(32, 32)
        search_btn.setToolTip("Buscar no documento (Ctrl+F)")
        search_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        search_btn.clicked.connect(self._toggle_search)
        tb_layout.addWidget(search_btn)

        # Botão tela cheia
        self._fullscreen_btn = QPushButton("⛶")
        self._fullscreen_btn.setFixedSize(32, 32)
        self._fullscreen_btn.setToolTip("Tela cheia (F11)")
        self._fullscreen_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        tb_layout.addWidget(self._fullscreen_btn)
        
        # Botão Página Dupla
        self._double_page_btn = QPushButton("📖 Dupla")
        self._double_page_btn.setFixedSize(85, 32)
        self._double_page_btn.setCheckable(True)
        self._double_page_btn.setToolTip("Modo Página Dupla")
        self._double_page_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 13px; color: #94a3b8; }
            QPushButton:hover { background: #2d333f; }
            QPushButton:checked { background: rgba(16, 185, 129, 0.2);
                                  border-color: #10b981; color: #10b981; }
        """)
        self._double_page_btn.clicked.connect(self._toggle_double_page)
        # Movido para o menu de overflow ("⋯"): mantido como state-holder.

        # Botão Marca-Texto (modo de destaque)
        self._highlight_mode_btn = QPushButton("🖍️")
        self._highlight_mode_btn.setFixedSize(32, 32)
        self._highlight_mode_btn.setCheckable(True)
        self._highlight_mode_btn.setToolTip(
            "Modo Marca-Texto (PDF)\n\n"
            "1. Clique e arraste para selecionar uma área\n"
            "2. Solte o mouse\n"
            "3. Clique DIREITO dentro da seleção azul\n"
            "4. Escolha '🖍️ Destacar' no menu"
        )
        self._highlight_mode_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
            QPushButton:checked { background: rgba(251, 191, 36, 0.2);
                                  border-color: #fbbf24; }
        """)
        self._highlight_mode_btn.clicked.connect(self._toggle_highlight_mode)
        # Movido para o menu de overflow ("⋯"): mantido como state-holder.

        # Botão Estudar (ações do agente sobre a página atual)
        self._study_btn = QPushButton("🎓")
        self._study_btn.setFixedSize(32, 32)
        self._study_btn.setToolTip("Estudar a página: explicar · resumir · flashcards · glossário")
        self._study_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._study_btn.clicked.connect(self._open_study_menu)
        tb_layout.addWidget(self._study_btn)

        # Botão Painel IA
        self._ai_panel_btn = QPushButton("🤖")
        self._ai_panel_btn.setFixedSize(32, 32)
        self._ai_panel_btn.setCheckable(True)
        self._ai_panel_btn.setToolTip("Assistente IA")
        self._ai_panel_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
            QPushButton:checked { background: rgba(16, 185, 129, 0.2);
                                  border-color: #10b981; }
        """)
        self._ai_panel_btn.clicked.connect(self._toggle_ai_panel)
        tb_layout.addWidget(self._ai_panel_btn)

        # Botão Áudio/TTS (Leitura de página) — Ouvir / Pausar / Retomar
        self._audio_btn = QPushButton("🔊 Ouvir")
        self._audio_btn.setFixedSize(95, 32)
        self._audio_btn.setToolTip("Ouvir Página (TTS)")
        self._audio_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._audio_btn.clicked.connect(self._toggle_audio)
        tb_layout.addWidget(self._audio_btn)

        # Botão Parar (full stop) — só visível durante a reprodução/pausa.
        self._audio_stop_btn = QPushButton("⏹️")
        self._audio_stop_btn.setFixedSize(36, 32)
        self._audio_stop_btn.setToolTip("Parar Leitura (TTS)")
        self._audio_stop_btn.setVisible(False)
        self._audio_stop_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 14px; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._audio_stop_btn.clicked.connect(self._stop_audio_if_running)
        tb_layout.addWidget(self._audio_stop_btn)

        # Botão de Configuração de TTS (atalho Phase 13)
        self._tts_settings_btn = QPushButton("⚙️ TTS")
        self._tts_settings_btn.setFixedSize(65, 32)
        self._tts_settings_btn.setToolTip("Configurar Vozes e Engines de Narração")
        self._tts_settings_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 13px; color: #94a3b8; }
            QPushButton:hover { background: #2d333f; }
        """)
        self._tts_settings_btn.clicked.connect(self._on_tts_settings_clicked)
        # Movido para o menu de overflow ("⋯"): mantido como state-holder.

        # Proactive Agent Toggle
        self._proactive_combo = QComboBox()
        self._proactive_combo.addItems(["Desligado", "Leve", "Moderado", "Estudo"])
        self._proactive_combo.setToolTip("Agente Proativo de Leitura")
        self._proactive_combo.setFixedSize(90, 32)
        self._proactive_combo.setStyleSheet("""
            QComboBox { background: transparent; border: 1px solid #2d333f; border-radius: 6px; color: #94a3b8; padding-left: 5px; }
            QComboBox::drop-down { border: none; }
        """)
        self._proactive_combo.currentTextChanged.connect(self._proactive_service.set_intensity)
        # Conectado DEPOIS de set_intensity: ao reagir, a intensidade nova já está
        # aplicada e o trigger engine resetado, então a avaliação imediata vale.
        self._proactive_combo.currentTextChanged.connect(self._on_proactive_intensity_changed)
        # Movido para o submenu do overflow ("⋯"): mantido como state-holder de intensidade.

        # Menu de overflow ("⋯") — agrupa controles secundários para desafogar a toolbar.
        self._overflow_btn = QToolButton()
        self._overflow_btn.setText("⋯")
        self._overflow_btn.setFixedSize(32, 32)
        self._overflow_btn.setToolTip("Mais opções")
        self._overflow_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._overflow_btn.setStyleSheet("""
            QToolButton { background: transparent; border: 1px solid #2d333f;
                          border-radius: 6px; font-size: 16px; color: #94a3b8; }
            QToolButton:hover { background: #2d333f; }
            QToolButton::menu-indicator { image: none; }
        """)
        self._overflow_menu = QMenu(self._overflow_btn)
        self._overflow_menu.setStyleSheet("""
            QMenu { background: #1e2227; border: 1px solid #3f3f46; color: #e4e4e7; border-radius: 4px; padding: 4px; }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background: #3f3f46; }
        """)
        self._act_double_page = QAction("📖 Página Dupla", self, checkable=True)
        self._act_double_page.triggered.connect(self._menu_toggle_double_page)
        self._act_highlight = QAction("🖍️ Modo Marca-Texto", self, checkable=True)
        self._act_highlight.triggered.connect(self._menu_toggle_highlight)
        self._act_tts = QAction("⚙️ Voz / Narração (TTS)", self)
        self._act_tts.triggered.connect(self._on_tts_settings_clicked)
        self._overflow_menu.addAction(self._act_double_page)
        self._overflow_menu.addAction(self._act_highlight)
        self._overflow_menu.addSeparator()
        # Submenu do Agente Proativo (antes era um combo sempre visível na toolbar)
        self._proactive_acts = {}
        proactive_menu = self._overflow_menu.addMenu("🧠 Agente Proativo")
        for level in ["Desligado", "Leve", "Moderado", "Estudo"]:
            p_act = QAction(level, self, checkable=True)
            p_act.triggered.connect(lambda _c=False, lv=level: self._set_proactive_intensity(lv))
            proactive_menu.addAction(p_act)
            self._proactive_acts[level] = p_act
        self._act_insights = QAction("💡 Insights do Proativo", self)
        self._act_insights.triggered.connect(lambda: self._show_dock_tab("insights"))
        self._overflow_menu.addAction(self._act_insights)
        self._overflow_menu.addSeparator()
        self._overflow_menu.addAction(self._act_tts)
        self._overflow_menu.aboutToShow.connect(self._sync_overflow_menu)
        self._overflow_btn.setMenu(self._overflow_menu)
        tb_layout.addWidget(self._overflow_btn)

        self._toolbar = toolbar
        left_layout.addWidget(toolbar)

        # Barra de busca overlay (abaixo da toolbar)
        self._search_bar = DocumentSearchBar()
        self._search_bar.search_requested.connect(self._on_document_search)
        self._search_bar.navigate_result.connect(self._on_search_navigate)
        self._search_bar.closed.connect(lambda: self._search_results.clear())
        left_layout.addWidget(self._search_bar)

        # Conteúdo: Splitter com TOC + Visualização
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

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
        self._image_scroll.setStyleSheet("background-color: #0f1115;")
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_scroll.setWidget(self._image_label)
        self._content_stack.addWidget(self._image_scroll)  # index 0

        # Rubber band para seleção em PDF
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self._image_label)
        self._origin = QPoint()
        self._is_selecting = False
        self._last_selection_coords: tuple | None = None  # Últimas coords normalizadas salvas

        # Visualizador HTML (para EPUB, TXT, DOCX)
        self._web_view = QWebEngineView()
        self._content_stack.addWidget(self._web_view)  # index 1

        self._image_scroll.viewport().installEventFilter(self)
        self._image_label.installEventFilter(self)
        self._web_view.installEventFilter(self)

        # Context Menus
        self._image_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._image_label.customContextMenuRequested.connect(self._on_pdf_context_menu)
        
        self._web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._web_view.customContextMenuRequested.connect(self._on_epub_context_menu)

        splitter.addWidget(self._content_stack)
        splitter.setStretchFactor(1, 1)  # área de leitura expande; TOC fica no seu max

        # Painel de anotações — agora vive no dock à direita (não mais inline),
        # liberando largura para a leitura.
        self._annotation_panel = AnnotationPanel()
        self._annotation_panel.annotation_added.connect(self._on_annotation_added)
        self._annotation_panel.annotation_deleted.connect(
            lambda ann_id: self.annotation_deleted.emit(ann_id)
        )
        self._annotation_panel.goto_page.connect(self._go_to_page)

        left_layout.addWidget(splitter, stretch=1)

        # Proactive Footer Widget (starts hidden)
        self._proactive_footer = ProactiveFooterWidget()
        self._proactive_footer.flashcard_requested.connect(
            lambda text: self.ai_action_requested.emit("flashcard", text)
        )
        self._proactive_footer.closed.connect(self._on_footer_closed)
        left_layout.addWidget(self._proactive_footer)

        # Barra de progresso inferior
        self._progress_bar_widget = QWidget()
        self._progress_bar_widget.setFixedHeight(28)
        self._progress_bar_widget.setStyleSheet(
            "background-color: #161920; border-top: 1px solid #2d333f;"
        )
        pb_layout = QHBoxLayout(self._progress_bar_widget)
        pb_layout.setContentsMargins(16, 4, 16, 4)
        self._progress_bar = ReadingProgressBar()
        pb_layout.addWidget(self._progress_bar)
        left_layout.addWidget(self._progress_bar_widget)

        # Adiciona o painel esquerdo ao splitter principal
        self._main_splitter.addWidget(self._left_pane)

        # Dock único à direita: abas recolhíveis (Anotações / Assistente),
        # exibindo um painel por vez para maximizar o espaço de leitura.
        self._dock = ReaderDock()
        self._dock.add_tab("annotations", "📝 Anotações", self._annotation_panel)
        # Insights do agente proativo: registro persistente das observações da sessão.
        self._insights_panel = ProactiveInsightsPanel()
        self._insights_panel.flashcard_requested.connect(
            lambda text: self.ai_action_requested.emit("flashcard", text)
        )
        self._insights_panel.dismiss_requested.connect(self._on_observation_dismissed)
        self._dock.add_tab("insights", "💡 Insights", self._insights_panel)
        self._dock.closed.connect(self.hide_dock)
        self._dock.tab_changed.connect(lambda _k: self._sync_dock_buttons())
        self._main_splitter.addWidget(self._dock)
        self._dock.hide()

        # O painel do Assistente (RAGPanel) é injetado no dock depois (set_ai_panel).
        self._ai_panel_container = None

        # Popover de ações sobre a seleção (PDF) — alternativa rápida ao clique direito.
        self._selection_popover = SelectionActionPopover(self)
        self._selection_popover.action_requested.connect(self._on_selection_popover_action)

    def _setup_shortcuts(self):
        s_next = QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._go_next)
        s_next.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        s_prev = QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._go_prev)
        s_prev.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_search)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._toggle_fullscreen)

    def wheelEvent(self, event) -> None:
        """Manipulador de evento da roda do mouse para Zoom Interativo."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self._zoom_in()
            else:
                self._zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:
        """Manipulador de clique na visualização do leitor."""
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.angleDelta().y() > 0:
                    self._zoom_in()
                else:
                    self._zoom_out()
                return True
        elif event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                width = obj.width()
                if hasattr(event, "scenePosition"):
                    x = event.scenePosition().x()
                else:
                    x = event.position().x()
                # Verifica se clicou nas margens laterais
                if x < width * 0.15:
                    self._go_prev()
                    return True
                elif x > width * 0.85:
                    self._go_next()
                    return True

        # Manipulação do Rubber Band no _image_label
        if obj == self._image_label:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                # Clique esquerdo inicia nova seleção — limpa a seleção anterior
                self._origin = event.position().toPoint()
                self._rubber_band.setGeometry(QRect(self._origin, QSize()))
                self._rubber_band.show()
                self._is_selecting = True
                self._last_selection_coords = None  # Reseta coords ao iniciar
                if hasattr(self, "_selection_popover"):
                    self._selection_popover.hide()
                return True
            elif event.type() == QEvent.Type.MouseMove and self._is_selecting:
                self._rubber_band.setGeometry(QRect(self._origin, event.position().toPoint()).normalized())
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._is_selecting = False
                # Calcula e armazena as coords normalizadas da seleção atual
                rect = self._rubber_band.geometry()
                label_size = self._image_label.size()
                pixmap = self._image_label.pixmap()
                if pixmap and pixmap.width() > 0:
                    offset_x = (label_size.width() - pixmap.width()) / 2
                    offset_y = (label_size.height() - pixmap.height()) / 2
                    x0 = rect.left() - offset_x
                    y0 = rect.top() - offset_y
                    x1 = rect.right() - offset_x
                    y1 = rect.bottom() - offset_y
                    px0 = max(0.0, x0 / pixmap.width())
                    py0 = max(0.0, y0 / pixmap.height())
                    px1 = min(1.0, x1 / pixmap.width())
                    py1 = min(1.0, y1 / pixmap.height())
                    if (px1 - px0) > 0.005 and (py1 - py0) > 0.005:  # Seleção mínima 0.5%
                        self._last_selection_coords = (px0, py0, px1, py1)
                        self._show_selection_popover(rect)
                # Mantém rubber band visível para clique direito
                return True

        return super().eventFilter(obj, event)

    def open_book(self, book_data: dict, start_page: int = 0):
        """Abre um livro para leitura."""
        filepath = book_data.get("file_path", "")
        if not filepath:
            return

        self._book_id = book_data.get("id", 0)
        self._annotation_panel.set_book_id(self._book_id)
        self._title_label.setText(book_data.get("title", ""))
        self._load_persisted_observations()

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
            # Fase 9A: Resetar viewport para o topo ao mudar página
            # Usa event loop para garantir que o layout atualizou antes de scrollar
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._image_scroll.verticalScrollBar().setValue(0))
            QTimer.singleShot(0, lambda: self._image_scroll.horizontalScrollBar().setValue(0))
        elif content.content_type in ("html", "text"):
            # EPUB/TXT/DOCX — renderiza como HTML
            css = get_reader_css(self._theme)
            html = f"""<!DOCTYPE html>
            <html><head><style>{css}</style></head>
            <body>{content.content}</body></html>"""
            self._web_view.setHtml(html)
            self._content_stack.setCurrentIndex(1)
            # Fase 9A: Resetar viewport do webview para EPUB/HTML
            self._web_view.page().runJavaScript("window.scrollTo(0, 0);")

        # Atualiza indicadores
        page = content.page_number
        total = content.total_pages
        self._page_label.setText(f"{page + 1}/{total}")
        self._progress_bar.set_page_info(page + 1, total)
        self.progress_changed.emit(self._book_id, page, total)
        
        # Emite contexto para a IA
        # Pega as primeiras 1000 letras do texto da página para contexto
        page_text = ""
        if self._reader and hasattr(self._reader, "get_page_text"):
            page_text = self._reader.get_page_text(page)
        elif self._reader and hasattr(self._reader, "get_chapter_text"):
            page_text = self._reader.get_chapter_text(page)
        
        if page_text:
            # Página 1-based passada ao serviço proativo; guardada para persistir
            # a observação resultante em ai_observations.
            self._current_proactive_page = page + 1
            self._last_page_text = page_text[:1500]
            self.reading_context_updated.emit(
                self._book_id,
                self._title_label.text(),
                page + 1,
                page_text[:1500]
            )

    def _go_to_page(self, page: int):
        self._stop_audio_if_running()
        if hasattr(self, "_selection_popover"):
            self._selection_popover.hide()
        if self._reader:
            content = self._reader.go_to_page(page)
            if content:
                self._render_page(content)

    def _go_next(self) -> None:
        if self._reader:
            if self._content_stack.currentIndex() == 1:
                is_double = hasattr(self._reader, 'is_double_page') and self._reader.is_double_page
                if is_double:
                    script = """
                    var maxScrollLeft = document.body.scrollWidth - window.innerWidth;
                    if (window.scrollX < maxScrollLeft - 10) {
                        window.scrollBy({top: 0, left: window.innerWidth, behavior: 'smooth'});
                        'scrolled';
                    } else {
                        'next';
                    }
                    """
                else:
                    script = """
                    var atBottom = (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 10;
                    if (!atBottom) {
                        window.scrollBy({top: window.innerHeight - 40, left: 0, behavior: 'smooth'});
                        'scrolled';
                    } else {
                        'next';
                    }
                    """
                self._web_view.page().runJavaScript(script, self._handle_next_scroll)
            else:
                self._handle_next_scroll("next")

    def _handle_next_scroll(self, result):
        if result == "next":
            content = self._reader.next_page()
            if content:
                self._render_page(content)

    def _go_prev(self) -> None:
        if self._reader:
            if self._content_stack.currentIndex() == 1:
                is_double = hasattr(self._reader, 'is_double_page') and self._reader.is_double_page
                if is_double:
                    script = """
                    if (window.scrollX > 10) {
                        window.scrollBy({top: 0, left: -window.innerWidth, behavior: 'smooth'});
                        'scrolled';
                    } else {
                        'prev';
                    }
                    """
                else:
                    script = """
                    var atTop = window.scrollY <= 10;
                    if (!atTop) {
                        window.scrollBy({top: -(window.innerHeight - 40), left: 0, behavior: 'smooth'});
                        'scrolled';
                    } else {
                        'prev';
                    }
                    """
                self._web_view.page().runJavaScript(script, self._handle_prev_scroll)
            else:
                self._handle_prev_scroll("prev")

    def _handle_prev_scroll(self, result):
        if result == "prev":
            content = self._reader.previous_page()
            if content:
                self._render_page(content)

    def _toggle_double_page(self) -> None:
        """Ativa ou desativa o modo de página dupla (Spread View)."""
        if self._reader and hasattr(self._reader, 'set_double_page'):
            self._reader.set_double_page(self._double_page_btn.isChecked())
            self._go_to_page(self._reader.current_page)

    def _menu_toggle_double_page(self, checked: bool) -> None:
        """Aciona o modo página dupla a partir do menu de overflow ('⋯')."""
        self._double_page_btn.setChecked(checked)
        self._toggle_double_page()

    def _menu_toggle_highlight(self, checked: bool) -> None:
        """Aciona o modo marca-texto a partir do menu de overflow ('⋯')."""
        self._highlight_mode_btn.setChecked(checked)
        self._toggle_highlight_mode()

    def _sync_overflow_menu(self) -> None:
        """Sincroniza os checkmarks do menu de overflow com o estado real."""
        self._act_double_page.setChecked(self._double_page_btn.isChecked())
        self._act_highlight.setChecked(self._highlight_mode_btn.isChecked())
        current = self._proactive_combo.currentText()
        for level, act in getattr(self, "_proactive_acts", {}).items():
            act.setChecked(level == current)

    def _set_proactive_intensity(self, level: str) -> None:
        """Ajusta a intensidade do agente proativo a partir do submenu de overflow."""
        # setCurrentText dispara currentTextChanged → ProactiveReaderService.set_intensity
        self._proactive_combo.setCurrentText(level)

    def _on_proactive_intensity_changed(self, level: str) -> None:
        """Reage à mudança de intensidade do agente proativo.

        Dois efeitos: (1) atualiza o texto-vazio do painel de Insights para
        refletir se o agente está ligado; (2) avalia a página atual na hora,
        para que ligar o agente não exija virar página antes de gerar a primeira
        observação.
        """
        active = level != "Desligado"
        if hasattr(self, "_insights_panel"):
            self._insights_panel.set_agent_active(active)
        if active and self._last_page_text:
            # set_intensity (conectado antes) já resetou o trigger engine, então
            # a página atual passa no critério de distância.
            self._proactive_service.process_page_context(
                self._last_page_text, self._current_proactive_page, self._book_id
            )

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
        self._stop_audio_if_running()
        if self._reader and self._reader.is_open:
            self._reader.close()
            self._reader = None

    def set_theme(self, theme: str):
        self._theme = theme

        # Apply theme to TOC and AnnotationPanel
        self._toc_widget.set_theme(theme)
        self._annotation_panel.set_theme(theme)
        if hasattr(self, '_dock'):
            self._dock.set_theme(theme)
        if hasattr(self, '_insights_panel'):
            self._insights_panel.set_theme(theme)
        if hasattr(self, '_search_bar') and hasattr(self._search_bar, 'set_theme'):
            self._search_bar.set_theme(theme)
        if hasattr(self, '_proactive_footer') and hasattr(self._proactive_footer, 'set_theme'):
            self._proactive_footer.set_theme(theme)

        # Apply CSS to current reader if open
        if self._reader and hasattr(self._reader, "set_theme_css"):
            self._reader.set_theme_css(get_reader_css(theme))

        if theme == "light":
            bg_toolbar = "#f4f4f5"
            border_toolbar = "#e4e4e7"
            text_toolbar = "#1A1A1A"
            btn_bg = "#e4e4e7"
            btn_hover_bg = "#d4d4d8"
            btn_color = "#52525b"
            sep_color = "#e4e4e7"
            page_lbl_color = "#71717a"
            bg_scroll = "#FFFFFF"
            bg_progress = "#f4f4f5"
            border_progress = "#e4e4e7"

            # Action button checked style
            checked_style = """
                background: rgba(5, 150, 105, 0.1);
                border-color: #059669;
                color: #059669;
            """
            hl_checked_style = """
                background: rgba(251, 191, 36, 0.2);
                border-color: #fbbf24;
            """
        elif theme == "sepia":
            bg_toolbar = "#ebe5d9"
            border_toolbar = "#d4cbb8"
            text_toolbar = "#5B4636"
            btn_bg = "#dfd8c8"
            btn_hover_bg = "#d4cbb8"
            btn_color = "#5b4636"
            sep_color = "#d4cbb8"
            page_lbl_color = "#8b7355"
            bg_scroll = "#F4ECD8"
            bg_progress = "#ebe5d9"
            border_progress = "#d4cbb8"

            checked_style = """
                background: rgba(139, 108, 66, 0.15);
                border-color: #8b6c42;
                color: #8b6c42;
            """
            hl_checked_style = """
                background: rgba(251, 191, 36, 0.2);
                border-color: #fbbf24;
            """
        else: # dark
            bg_toolbar = "#20242d"     # Dark elevated
            border_toolbar = "#2d333f" # Dark border
            text_toolbar = "#e5e7eb"   # Text primary
            btn_bg = "#161920"         # Dark surface
            btn_hover_bg = "#2d333f"   # Dark border
            btn_color = "#cbd5e1"      # Text secondary
            sep_color = "#2d333f"
            page_lbl_color = "#94a3b8" # Text muted
            bg_scroll = "#0f1115"      # Dark base
            bg_progress = "#161920"    # Dark surface
            border_progress = "#2d333f"

            checked_style = """
                background: rgba(16, 185, 129, 0.2);
                border-color: #10b981;
            """
            hl_checked_style = """
                background: rgba(251, 191, 36, 0.2);
                border-color: #fbbf24;
            """

        # 1. Toolbar and controls inside it
        self._toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_toolbar};
                border-bottom: 1px solid {border_toolbar};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {btn_color};
            }}
            QPushButton:hover {{
                background: {btn_hover_bg};
            }}
        """)

        self._title_label.setStyleSheet(f"color: {text_toolbar}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        self._page_label.setStyleSheet(f"color: {page_lbl_color}; font-size: 12px; background: transparent; border: none;")

        # Navigation/control buttons with backgrounds
        for btn in (self._prev_btn, self._next_btn):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {btn_bg};
                    border: none;
                    border-radius: 6px;
                    color: {btn_color};
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background: {btn_hover_bg};
                }}
            """)

        # Toolbar actions (checkable)
        self._annotations_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {btn_bg};
                border-radius: 6px;
                font-size: 16px;
            }}
            QPushButton:hover {{ background: {btn_hover_bg}; }}
            QPushButton:checked {{ {checked_style} }}
        """)
        self._double_page_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {btn_bg};
                border-radius: 6px;
                font-size: 13px;
                color: {btn_color};
            }}
            QPushButton:hover {{ background: {btn_hover_bg}; }}
            QPushButton:checked {{ {checked_style} }}
        """)
        self._ai_panel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {btn_bg};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {btn_hover_bg}; }}
            QPushButton:checked {{ {checked_style} }}
        """)
        self._audio_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {btn_bg};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {btn_hover_bg}; }}
        """)
        if hasattr(self, "_audio_stop_btn"):
            self._audio_stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {btn_bg};
                    border-radius: 6px;
                    font-size: 14px;
                }}
                QPushButton:hover {{ background: {btn_hover_bg}; }}
            """)
        if hasattr(self, "_study_btn"):
            self._study_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {btn_bg};
                    border-radius: 6px;
                    font-size: 14px;
                }}
                QPushButton:hover {{ background: {btn_hover_bg}; }}
            """)
        self._highlight_mode_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {btn_bg};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {btn_hover_bg}; }}
            QPushButton:checked {{ {hl_checked_style} }}
        """)

        # 2. Scroll area
        self._image_scroll.setStyleSheet(f"background-color: {bg_scroll};")

        # 3. Progress bar container
        self._progress_bar_widget.setStyleSheet(f"""
            background-color: {bg_progress};
            border-top: 1px solid {border_progress};
        """)

        # Overflow ("⋯") e popover de seleção acompanham o tema
        if hasattr(self, "_overflow_btn"):
            self._overflow_btn.setStyleSheet(f"""
                QToolButton {{ background: transparent; border: 1px solid {btn_bg};
                              border-radius: 6px; font-size: 16px; color: {btn_color}; }}
                QToolButton:hover {{ background: {btn_hover_bg}; }}
                QToolButton::menu-indicator {{ image: none; }}
            """)
        if hasattr(self, "_selection_popover"):
            self._selection_popover.set_theme(theme)

        if self._reader and self._reader.is_open:
            self._go_to_page(self._reader.current_page)

    def _toggle_annotations(self):
        """Mostra/oculta a aba de Anotações no dock à direita."""
        if (not self._dock.isHidden()) and self._dock.current_key() == "annotations":
            self.hide_dock()
        else:
            self._show_dock_tab("annotations")

    def _on_annotation_added(self, data: dict):
        """Emite sinal quando uma anotação é adicionada."""
        self.annotation_added.emit(self._book_id, data)

    def load_annotations(self, annotations: list[dict]):
        """Carrega anotações no painel."""
        self._annotation_panel.set_book_id(self._book_id)
        self._annotation_panel.load_annotations(annotations)
        self._annotations = annotations
        from src.readers.pdf_reader import PDFReader
        if self._reader and isinstance(self._reader, PDFReader):
            self._reader.highlights = annotations
            # Re-renderiza a página atual para exibir o destaque imediatamente
            self._go_to_page(self._reader.current_page)

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
        """Escape: fecha popover → busca → limpa rubber band → sai do fullscreen → fecha leitor."""
        if hasattr(self, "_selection_popover") and self._selection_popover.isVisible():
            self._selection_popover.hide()
            return
        if self._search_bar.isVisible():
            self._search_bar.close_bar()
        elif self._rubber_band.isVisible():
            self._rubber_band.hide()
            self._last_selection_coords = None
        elif self._is_fullscreen:
            self._toggle_fullscreen()
        else:
            self.closed.emit()

    def _toggle_highlight_mode(self) -> None:
        """Ativa/desativa o modo de Marca-Texto e mostra dica visual."""
        from src.readers.pdf_reader import PDFReader
        is_active = self._highlight_mode_btn.isChecked()
        
        if is_active:
            # Só funciona para PDF
            if not (self._reader and isinstance(self._reader, PDFReader)):
                self._highlight_mode_btn.setChecked(False)
                from PyQt6.QtWidgets import QToolTip
                QToolTip.showText(
                    self._highlight_mode_btn.mapToGlobal(
                        self._highlight_mode_btn.rect().center()
                    ),
                    "⚠️ Marca-Texto só funciona em documentos PDF",
                    self._highlight_mode_btn,
                    self._highlight_mode_btn.rect(),
                    3000
                )
                return
            # Muda o cursor para indicar modo de seleção
            from PyQt6.QtCore import Qt
            self._image_label.setCursor(Qt.CursorShape.CrossCursor)
        else:
            # Restaura cursor padrão
            self._image_label.unsetCursor()
            self._rubber_band.hide()
            self._last_selection_coords = None

    # ── Integração RAG Lado a Lado ───────────────────────────────────────────

    def set_ai_panel(self, ai_panel: QWidget) -> None:
        """Injeta o RAGPanel como aba 'Assistente' no dock do leitor."""
        if self._dock.has_tab("assistant"):
            return  # Já injetado

        self._ai_panel_container = ai_panel
        self._dock.add_tab("assistant", "💬 Assistente", ai_panel)
        # Mantém Anotações como aba padrão ao injetar (não rouba foco).
        if self._dock.has_tab("annotations"):
            self._dock.show_tab("annotations")

        # Conecta o sinal de fechar do painel (evita conexão duplicada).
        if hasattr(ai_panel, 'close_requested'):
            try:
                ai_panel.close_requested.disconnect(self.hide_dock)
            except (TypeError, RuntimeError):
                pass
            ai_panel.close_requested.connect(self.hide_dock)

        if hasattr(ai_panel, 'set_standalone_mode'):
            ai_panel.set_standalone_mode(False)

    def _show_dock_tab(self, key: str) -> None:
        """Exibe o dock e seleciona a aba indicada."""
        self._dock.show_tab(key)
        self._dock.show()
        w = self.width()
        self._main_splitter.setSizes([int(w * 0.58), int(w * 0.42)])
        self._sync_dock_buttons()

    def hide_dock(self) -> None:
        """Recolhe o dock à direita."""
        self._dock.hide()
        self._sync_dock_buttons()

    def _sync_dock_buttons(self) -> None:
        """Sincroniza os toggles da toolbar (Anotações/Assistente) com o dock."""
        visible = (not self._dock.isHidden())
        key = self._dock.current_key() if visible else None
        self._annotations_btn.setChecked(bool(visible and key == "annotations"))
        self._ai_panel_btn.setChecked(bool(visible and key == "assistant"))

    def _toggle_ai_panel(self) -> None:
        """Abre/fecha a aba do assistente no dock via botão da toolbar."""
        if self._ai_panel_container is None or not self._dock.has_tab("assistant"):
            return
        if (not self._dock.isHidden()) and self._dock.current_key() == "assistant":
            self.hide_dock()
        else:
            self.show_ai_panel()

    def show_ai_panel(self) -> None:
        """Exibe o dock na aba do assistente."""
        if self._ai_panel_container and self._dock.has_tab("assistant"):
            self._show_dock_tab("assistant")

    def hide_ai_panel(self) -> None:
        """Compat.: recolhe o dock (usado ao fechar o leitor / iniciar livro)."""
        self.hide_dock()

    # ── Controle ───────────────────────────────────────────────────────────────
    
    def _create_ai_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #161920; border: 1px solid #2d333f; 
                    border-radius: 6px; padding: 4px; color: #e5e7eb; }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background-color: #059669; }
        """)
        return menu

    def _populate_ai_menu(self, menu: QMenu, text: str):
        if not text or not text.strip():
            return
            
        action_translate = QAction("🌐 Traduzir Seleção", self)
        action_translate.triggered.connect(lambda: self.ai_action_requested.emit("translate", text))
        
        action_explain = QAction("🧠 Explicar Contexto", self)
        action_explain.triggered.connect(lambda: self.ai_action_requested.emit("explain", text))
        
        action_search = QAction("🔍 Buscar na Web", self)
        action_search.triggered.connect(lambda: self.ai_action_requested.emit("search", text))
        
        action_save = QAction("📝 Salvar Anotação Auto.", self)
        action_save.triggered.connect(lambda: self.ai_action_requested.emit("save_note", text))
        
        action_flashcard = QAction("🃏 Criar Flashcard", self)
        action_flashcard.triggered.connect(lambda: self.ai_action_requested.emit("flashcard", text))

        action_translate_audio = QAction("🔊 Ouvir Tradução", self)
        action_translate_audio.triggered.connect(lambda: self.ai_action_requested.emit("translate_audio", text))

        menu.addAction(action_translate)
        menu.addAction(action_translate_audio)
        menu.addAction(action_explain)
        menu.addAction(action_search)
        menu.addAction(action_save)
        menu.addAction(action_flashcard)

    def _current_page_text(self) -> str:
        """Retorna o texto da página/capítulo atual do leitor."""
        if not self._reader:
            return ""
        page = self._reader.current_page
        if hasattr(self._reader, "get_page_text"):
            return self._reader.get_page_text(page) or ""
        if hasattr(self._reader, "get_chapter_text"):
            return self._reader.get_chapter_text(page) or ""
        return ""

    def _open_study_menu(self) -> None:
        """Menu de ações de estudo do agente sobre a página/capítulo atual."""
        text = self._current_page_text().strip()
        menu = self._create_ai_menu()
        actions = [
            ("🧠 Explicar esta página", "explain_page"),
            ("📄 Resumir", "summarize"),
            ("🃏 Flashcards do trecho", "flashcards"),
            ("📚 Glossário", "glossary"),
        ]
        for label, key in actions:
            act = QAction(label, self)
            act.setEnabled(bool(text))
            act.triggered.connect(
                lambda _checked=False, k=key, t=text: self.ai_action_requested.emit(k, t)
            )
            menu.addAction(act)
        menu.exec(self._study_btn.mapToGlobal(QPoint(0, self._study_btn.height() + 2)))

    def _on_epub_context_menu(self, pos: QPoint):
        """Extrai texto selecionado via JS no EPUB e mostra menu."""
        def callback(selected_text):
            if selected_text and selected_text.strip():
                menu = self._create_ai_menu()
                self._populate_ai_menu(menu, selected_text)
                global_pos = self._web_view.mapToGlobal(pos)
                menu.exec(global_pos)
                
        self._web_view.page().runJavaScript("window.getSelection().toString()", callback)

    def _on_pdf_context_menu(self, pos: QPoint):
        """Mostra menu de contexto do PDF.
        
        Suporta atalhos de IA de seleção de área, atalhos de IA para destaques
        existentes, e a remoção ("desmarcar") de destaques clicados com botão direito.
        """
        import json
        
        # 1. Mapeia a posição do clique com o botão direito para coordenadas de página normalizadas
        label_size = self._image_label.size()
        pixmap = self._image_label.pixmap()
        cx, cy = None, None
        if pixmap and pixmap.width() > 0:
            offset_x = (label_size.width() - pixmap.width()) / 2
            offset_y = (label_size.height() - pixmap.height()) / 2
            click_x = pos.x() - offset_x
            click_y = pos.y() - offset_y
            cx = click_x / pixmap.width()
            cy = click_y / pixmap.height()

        # 2. Verifica se o clique com o botão direito ocorreu dentro de um destaque existente
        clicked_highlight = None
        if cx is not None and cy is not None and 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0:
            for ann in self._annotations:
                if (
                    ann.get("page_number") == self._reader.current_page
                    and ann.get("annotation_type") == "highlight"
                ):
                    try:
                        pos_data = json.loads(ann.get("position_data", "{}"))
                        coords_list = pos_data.get("coords")
                        if coords_list and len(coords_list) == 4:
                            px0, py0, px1, py1 = coords_list
                            # Adiciona uma margem de tolerância fina de 0.01
                            if (px0 - 0.01) <= cx <= (px1 + 0.01) and (py0 - 0.01) <= cy <= (py1 + 0.01):
                                clicked_highlight = ann
                                break
                    except Exception:
                        continue

        coords = self._last_selection_coords
        
        # Tenta capturar coords a partir de um rubber band visível se coords for None
        if coords is None and self._rubber_band.isVisible():
            rect = self._rubber_band.geometry()
            if pixmap and pixmap.width() > 0:
                offset_x = (label_size.width() - pixmap.width()) / 2
                offset_y = (label_size.height() - pixmap.height()) / 2
                x0 = rect.left() - offset_x
                y0 = rect.top() - offset_y
                x1 = rect.right() - offset_x
                y1 = rect.bottom() - offset_y
                px0 = max(0.0, x0 / pixmap.width())
                py0 = max(0.0, y0 / pixmap.height())
                px1 = min(1.0, x1 / pixmap.width())
                py1 = min(1.0, y1 / pixmap.height())
                if (px1 - px0) > 0.005 and (py1 - py0) > 0.005:
                    coords = (px0, py0, px1, py1)

        # Se não há seleção ativa e não clicou em nenhum destaque, cancela o menu de contexto
        if coords is None and clicked_highlight is None:
            self._rubber_band.hide()
            return

        # Esconde rubber band antes de abrir o menu
        self._rubber_band.hide()
        
        menu = self._create_ai_menu()
        
        # Caso 1: Clicou em cima de um destaque existente
        if clicked_highlight is not None:
            action_remove = QAction("🗑️ Remover Destaque", self)
            action_remove.triggered.connect(
                lambda: self.annotation_deleted.emit(clicked_highlight["id"])
            )
            menu.addAction(action_remove)
            
            # Se não há seleção geométrica ativa, permite aplicar ações de IA no texto do destaque!
            highlight_text = clicked_highlight.get("content", "")
            if coords is None and highlight_text and highlight_text.strip():
                menu.addSeparator()
                self._populate_ai_menu(menu, highlight_text)

        # Caso 2: Há uma seleção geométrica ativa (prioridade para criar novo destaque ou usar IA na área)
        if coords is not None:
            if clicked_highlight is not None:
                menu.addSeparator()

            text = ""
            if self._reader and hasattr(self._reader, "get_text_from_rect"):
                try:
                    text = self._reader.get_text_from_rect(self._reader.current_page, coords) or ""
                except Exception:
                    text = ""

            action_highlight = QAction("🖍️ Destacar", self)
            action_highlight.triggered.connect(
                lambda: self._highlight_selection(coords, text.strip())
            )
            menu.addAction(action_highlight)
            
            if text and text.strip():
                menu.addSeparator()
                self._populate_ai_menu(menu, text)

        global_pos = self._image_label.mapToGlobal(pos)
        menu.exec(global_pos)
        
        # Limpa a seleção armazenada após usar o menu
        self._last_selection_coords = None

    def _highlight_selection(self, coords: tuple[float, float, float, float], text: str):
        """Salva o destaque no banco de dados e limpa a rubber band."""
        import json
        position_data = json.dumps({"coords": list(coords)})
        
        # Emite sinal para adicionar a anotação
        data = {
            "page_number": self._reader.current_page,
            "content": text,
            "highlight_color": "#fbbf24",
            "annotation_type": "highlight",
            "position_data": position_data
        }
        self.annotation_added.emit(self._book_id, data)

        # Esconde a rubber band após destacar
        self._rubber_band.hide()

    def _show_selection_popover(self, rect) -> None:
        """Exibe o popover de ações logo abaixo da seleção (PDF)."""
        if not hasattr(self, "_selection_popover"):
            return
        self._selection_popover.set_actions(
            ["highlight", "explain", "translate", "search", "save_note", "flashcard"]
        )
        # rect está em coordenadas do _image_label (pai da rubber band); mapeia p/ ReaderView.
        anchor_local = QPoint(rect.left(), rect.bottom() + 6)
        anchor = self._image_label.mapTo(self, anchor_local)
        self._selection_popover.show_at(anchor)

    def _on_selection_popover_action(self, action: str) -> None:
        """Executa a ação escolhida no popover de seleção (PDF)."""
        coords = self._last_selection_coords
        if coords is None:
            return
        text = ""
        if self._reader and hasattr(self._reader, "get_text_from_rect"):
            try:
                text = (self._reader.get_text_from_rect(self._reader.current_page, coords) or "").strip()
            except Exception:
                text = ""
        if action == "highlight":
            self._highlight_selection(coords, text)
        elif text:
            self.ai_action_requested.emit(action, text)
        self._last_selection_coords = None
        self._rubber_band.hide()

    def _toggle_audio(self):
        """Alterna a leitura de áudio (TTS) da página atual.

        Tocando → pausa; pausado → retoma no mesmo ponto; parado → inicia.
        O botão Parar (⏹️) faz o stop completo.
        Phase 13: Uses TTSRouter with voice profiles for book narration.
        """
        worker = getattr(self, "_audio_worker", None)
        if worker and worker.isRunning():
            if self._audio_paused:
                self._resume_audio()
            else:
                self._pause_audio()
            return

        if not self._reader:
            return

        page = self._reader.current_page
        page_text = ""
        if hasattr(self._reader, "get_page_text"):
            page_text = self._reader.get_page_text(page)
        elif hasattr(self._reader, "get_chapter_text"):
            page_text = self._reader.get_chapter_text(page)

        page_text = page_text.strip()
        if not page_text:
            return

        self._launch_audio_worker(page_text)

    def _launch_audio_worker(self, text: str) -> None:
        """Cria, conecta e inicia o AudioWorker para o texto dado (TTS)."""
        from src.gui.workers.audio_worker import AudioWorker
        from src.core.tts.voice_profile import NarrationRole

        self._audio_worker = AudioWorker(
            text,
            role=NarrationRole.BOOK_NARRATOR,
            router=self._tts_router,
            parent=self,
        )

        self._audio_worker.playback_started.connect(self._on_audio_started)
        self._audio_worker.playback_finished.connect(self._on_audio_finished)
        self._audio_worker.error_occurred.connect(self._on_audio_error)
        self._audio_worker.finished.connect(self._on_audio_worker_finished)
        self._audio_worker.provider_changed.connect(self._on_audio_provider_changed)

        self._audio_worker.start()

    def narrate_text(self, text: str) -> None:
        """Narra um texto arbitrário (ex.: uma tradução) via TTS.

        O idioma é autodetectado pelo AudioWorker: uma tradução em português é lida
        com voz em português; um trecho em inglês, com voz em inglês.
        """
        if not text or not text.strip():
            return
        self._stop_audio_if_running()
        self._launch_audio_worker(text.strip())

    def _pause_audio(self):
        """Pausa a narração (retomável no mesmo ponto)."""
        worker = getattr(self, "_audio_worker", None)
        if worker and worker.isRunning():
            worker.pause()
            self._audio_paused = True
            self._audio_btn.setText("▶️ Retomar")
            self._audio_btn.setToolTip("Continuar Leitura (TTS)")

    def _resume_audio(self):
        """Retoma a narração pausada a partir do ponto exato."""
        worker = getattr(self, "_audio_worker", None)
        if worker and worker.isRunning():
            worker.resume()
            self._audio_paused = False
            self._audio_btn.setText("⏸️ Pausar")
            self._audio_btn.setToolTip("Pausar Leitura (TTS)")

    def _on_audio_started(self):
        self._audio_paused = False
        self._audio_btn.setText("⏸️ Pausar")
        self._audio_btn.setToolTip("Pausar Leitura (TTS)")
        self._audio_stop_btn.setVisible(True)

    def _on_audio_finished(self, chunks):
        pass

    def _on_audio_error(self, err_msg):
        parent_window = self.window()
        if parent_window and hasattr(parent_window, "_statusbar") and parent_window._statusbar:
            parent_window._statusbar.showMessage(f"Erro de Áudio: {err_msg}", 5000)

    def _on_audio_worker_finished(self):
        """Garante a limpeza de referências e restaura o estado visual do botão."""
        self._audio_paused = False
        self._audio_btn.setText("🔊 Ouvir")
        self._audio_btn.setToolTip("Ouvir Página (TTS)")
        if hasattr(self, "_audio_stop_btn"):
            self._audio_stop_btn.setVisible(False)
        if hasattr(self, "_audio_worker") and self._audio_worker:
            self._audio_worker.deleteLater()
            self._audio_worker = None

    def _stop_audio_if_running(self):
        """Para a narração por completo (libera o worker) e restaura a UI."""
        if hasattr(self, '_audio_worker') and self._audio_worker and self._audio_worker.isRunning():
            self._audio_worker.stop()
            self._audio_worker.wait(2000)
            self._audio_worker = None
        self._audio_paused = False
        self._audio_btn.setText("🔊 Ouvir")
        self._audio_btn.setToolTip("Ouvir Página (TTS)")
        if hasattr(self, "_audio_stop_btn"):
            self._audio_stop_btn.setVisible(False)

    def _on_audio_provider_changed(self, provider_name: str):
        """Phase 13: Updates UI to show which TTS engine is active."""
        if not self._audio_paused:
            self._audio_btn.setToolTip(f"Pausar Leitura (via {provider_name})")

    def _on_tts_settings_clicked(self):
        """Abre o menu rápido de configurações TTS."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        from PyQt6.QtCore import QPoint
        
        parent_window = self.window()
        config = getattr(parent_window, "_config", None)
        if not config:
            if parent_window and hasattr(parent_window, "_show_settings"):
                parent_window._show_settings(initial_tab=3)
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1e2227; border: 1px solid #3f3f46; color: #e4e4e7; border-radius: 4px; padding: 4px; }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background: #3f3f46; }
        """)
        
        # 1. Ajuste rápido de Velocidade
        speed_menu = menu.addMenu("⚡ Velocidade da Leitura")
        current_rate = config.get("tts.book_narrator.rate", 1.0)
        
        rates = [
            ("🐢 Lenta (0.8x)", 0.8),
            ("🟢 Normal (1.0x)", 1.0),
            ("⚡ Rápida (1.2x)", 1.2),
            ("🚀 Muito Rápida (1.5x)", 1.5),
        ]
        
        for name, value in rates:
            action = QAction(name, speed_menu, checkable=True)
            action.setChecked(abs(current_rate - value) < 0.05)
            # Use default arguments in lambda to capture value correctly
            action.triggered.connect(lambda checked, val=value: config.set("tts.book_narrator.rate", val))
            speed_menu.addAction(action)

        # 2. Seleção de Motor (Provider)
        provider_menu = menu.addMenu("🔊 Motor de Voz (Engine)")
        current_provider = config.get("tts.book_narrator.preferred_provider", "kokoro")
        
        providers = [
            ("pyttsx3 (Legado Local)", "pyttsx3"),
            ("Kokoro (Neural Local)", "kokoro"),
            ("Piper (Neural Rápido)", "piper"),
        ]
        
        for name, key in providers:
            action = QAction(name, provider_menu, checkable=True)
            action.setChecked(current_provider == key)
            action.triggered.connect(lambda checked, k=key: config.set("tts.book_narrator.preferred_provider", k))
            provider_menu.addAction(action)

        # 3. Seleção de Estilo / Voz
        style_menu = menu.addMenu("🗣️ Voz / Estilo")
        current_style = config.get("tts.book_narrator.style", "serene")
        
        styles = [
            ("🌿 Leitura Serena (Feminina)", "serene"),
            ("📐 Leitura Técnica (Masculina)", "technical"),
            ("🎭 Leitura Expressiva (Masculina)", "expressive"),
        ]
        
        for name, key in styles:
            action = QAction(name, style_menu, checkable=True)
            action.setChecked(current_style == key)
            action.triggered.connect(lambda checked, k=key: config.set("tts.book_narrator.style", k))
            style_menu.addAction(action)
            
        menu.addSeparator()
        
        # 3. Atalho de configurações completas
        settings_action = QAction("⚙️ Configurações Completas...", menu)
        settings_action.triggered.connect(
            lambda: parent_window._show_settings(initial_tab=3) if hasattr(parent_window, "_show_settings") else None
        )
        menu.addAction(settings_action)
        
        anchor = getattr(self, "_overflow_btn", None) or self._tts_settings_btn
        menu.exec(anchor.mapToGlobal(QPoint(0, anchor.height() + 2)))

    def _on_proactive_observation(self, obs: dict):
        """Persiste a observação proativa e a exibe no rodapé + painel de Insights."""
        # Persistência (Fase 1b): grava em ai_observations e enriquece o dict com
        # id/page para permitir dismiss e reload. Graceful (ADR-005): se o banco
        # falhar, ainda exibimos o card.
        self._footer_obs_id = None
        if self._db is not None and self._book_id:
            try:
                conf = confidence_to_float(obs.get("confianca", ""))
                obs_id = self._db.add_observation(
                    self._book_id,
                    self._current_proactive_page,
                    obs.get("texto", ""),
                    kind=obs.get("tipo", "insight"),
                    payload_json=json.dumps(obs, ensure_ascii=False),
                    confidence=conf,
                )
                obs["id"] = obs_id
                obs["page"] = self._current_proactive_page
                self._footer_obs_id = obs_id
            except Exception as exc:
                logger.warning(f"Falha ao persistir observação proativa (ignorado): {exc}")

        self._proactive_footer.set_observation(obs)
        if hasattr(self, "_insights_panel"):
            self._insights_panel.add_observation(obs)

    def _load_persisted_observations(self):
        """Recarrega no painel de Insights as observações salvas deste livro.

        Reabertura/restart: traz de volta as observações não dispensadas
        (Fase 1b). Graceful (ADR-005): sem banco ou em erro, apenas limpa o painel.
        """
        if not hasattr(self, "_insights_panel"):
            return
        self._insights_panel.clear()
        if self._db is None or not self._book_id:
            return
        try:
            rows = self._db.get_observations(book_id=self._book_id, limit=30)
        except Exception as exc:
            logger.warning(f"Falha ao carregar observações do livro (ignorado): {exc}")
            return
        # get_observations vem DESC (mais nova primeiro); add_observation faz
        # prepend, então iteramos em reversed para a mais nova terminar no topo.
        for row in reversed(rows):
            self._insights_panel.add_observation(obs_dict_from_row(row))

    def _on_observation_dismissed(self, obs_id: int):
        """Marca a observação como dispensada (não reaparece ao reabrir o livro)."""
        if self._db is not None and obs_id:
            try:
                self._db.dismiss_observation(obs_id)
            except Exception as exc:
                logger.warning(f"Falha ao dispensar observação {obs_id} (ignorado): {exc}")

    def _on_footer_closed(self):
        """Fechar o rodapé dispensa a observação exibida nele."""
        if self._footer_obs_id:
            self._on_observation_dismissed(self._footer_obs_id)
            self._footer_obs_id = None

    def _on_proactive_error(self, msg: str):
        """Mostra falhas do agente proativo no statusbar e no painel de Insights
        (antes eram silenciosas)."""
        parent_window = self.window()
        if parent_window and hasattr(parent_window, "_statusbar") and parent_window._statusbar:
            parent_window._statusbar.showMessage(f"⚠️ {msg}", 6000)
        if hasattr(self, "_insights_panel"):
            self._insights_panel.add_error(msg)
