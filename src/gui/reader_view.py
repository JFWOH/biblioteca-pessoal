"""Visualização do leitor de documentos."""

import json
import logging
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QMenu, QRubberBand,
    QToolButton, QSizePolicy, QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize, QEvent
from PyQt6.QtGui import QPixmap, QKeySequence, QShortcut, QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from src.readers.base_reader import BaseReader, PageContent
from src.readers.reader_factory import create_reader
from src.gui.widgets.toc_widget import TOCWidget
from src.gui.widgets.reading_progress import ReadingProgressBar
from src.gui.widgets.annotation_panel import AnnotationPanel
from src.gui.widgets.search_overlay import DocumentSearchBar
from src.gui.widgets.bookmarks_panel import BookmarksPanel
from src.gui.widgets.xray_panel import XRayPanel
from src.gui.widgets.reader_typography_popover import ReaderTypographyPopover
from src.gui.styles import get_reader_css, emoji_icon
from src.utils.constants import (
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_LINE_HEIGHT,
)
from src.gui.widgets.proactive_footer import ProactiveFooterWidget
from src.gui.widgets.selection_popover import SelectionActionPopover
from src.gui.widgets.word_wise_popover import WordWisePopover
from src.gui.widgets.epub_selection_bridge import (
    EpubSelectionBridge, EPUB_SELECTION_JS,
)
from src.gui.widgets.reader_dock import ReaderDock
from src.gui.widgets.proactive_insights_panel import ProactiveInsightsPanel
from src.gui.proactive_reader_service import ProactiveReaderService
from src.core.proactive_observation import confidence_to_float, obs_dict_from_row
from src.core.reading_stats import clamp_session_seconds, total_elapsed_seconds
from src.core.graph.graph_store import GraphStore
from PyQt6.QtWidgets import QComboBox

logger = logging.getLogger(__name__)


class ReaderView(QWidget):
    """Leitor multi-formato com navegação, TOC e progresso."""

    closed = pyqtSignal()
    # Tarefa 5.2: payload AMPLIADO com os segundos lidos desde a última
    # emissão (tempo real medido por time.monotonic, com teto anti-idle —
    # ver clamp_session_seconds). Ampliar o sinal existente (em vez de criar
    # um paralelo) foi a opção menos invasiva: há UMA única conexão no
    # projeto (main_window._on_progress) e um único ponto de emit.
    progress_changed = pyqtSignal(int, int, int, int)  # book_id, page, total, seconds
    annotation_added = pyqtSignal(int, dict)       # book_id, annotation_data
    annotation_deleted = pyqtSignal(int)            # annotation_id
    annotation_renamed = pyqtSignal(int, str)       # annotation_id, novo título
    fullscreen_toggled = pyqtSignal(bool)           # is_fullscreen
    reading_context_updated = pyqtSignal(int, str, int, str) # book_id, title, page_number, page_text
    ai_action_requested = pyqtSignal(str, str)      # action_type, text
    # Rodada 3 de ajustes de TTS: emitido quando a narração começa DE FATO (o
    # áudio já está tocando — ver _on_audio_started). Diferente do gating por
    # busy_check (que só impede novos jobs de indexação), este sinal permite ao
    # MainWindow CANCELAR uma indexação em ocioso JÁ em andamento: a contenção
    # de CPU/GPU dos embeddings elevava o TTFB do Kokoro (24,92s medidos com 900
    # chunks concorrentes → SLO de 3s violado → fallback indevido p/ Piper).
    narration_started = pyqtSignal()

    # Tarefa 1.2 — zona de clique nas margens (só caminho PDF/imagem, ver
    # eventFilter): terço esquerdo = página anterior, terço direito = próxima.
    _PAGE_TURN_ZONE_RATIO = 1 / 3

    # Tarefa 3.4 — Word Wise só aparece no popover de seleção para termos
    # curtos (palavra/expressão), não para trechos/frases inteiras.
    _WORD_WISE_MAX_WORDS = 4

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
        # Leitura contínua (item 5 UX): ao fim da página narrada, avança e segue.
        self._continuous_reading: bool = False
        # Leitura contínua TRADUZIDA: mesma cadeia, mas cada página é traduzida
        # (NLLB) antes de narrar. Ver docs/agents/traducao_confiavel_execution_contract.md.
        self._continuous_translate_mode: bool = False
        # Override de sessão "Ouvir original" (achado B0): quando o usuário pede
        # "Ouvir original" com a Leitura Contínua Traduzida ligada, a cadeia deve
        # SEGUIR no idioma original (página a página) até ele parar — em vez do
        # one-shot antigo, que voltava a traduzir na página seguinte. Enquanto
        # este flag vive, o encadeamento (_toggle_audio) PULA a tradução. É
        # limpo em: stop manual (botão ⏹️), "Ouvir traduzido", mudança do toggle
        # de Leitura Contínua Traduzida, e troca/fechamento de livro. NÃO altera
        # o toggle persistido tts.continuous_translate_reading.
        self._listen_original_override: bool = False
        self._audio_stopped_by_user: bool = False  # stop manual não encadeia a próxima
        self._chain_continuous: bool = False       # só narração de página encadeia (tradução não)
        # Época de narração: incrementa a cada narração NOVA (não em pause/
        # resume). Callbacks assíncronos (ex.: tradução NLLB concluída)
        # comparam com a época capturada no pedido — se o usuário iniciou
        # outra narração no meio-tempo, o resultado atrasado é descartado em
        # vez de atropelar a narração em curso.
        self.narration_epoch: int = 0
        self._translating_for_audio: bool = False  # item E: feedback "Traduzindo…" no botão
        # Pré-síntese TTS da próxima página (tarefa 3.6): cache PURO (core) de
        # 1 página à frente + worker de síntese na GUI. Corta o gap entre páginas.
        from src.core.audio.continuous_player import PreSynthesisCache
        self._presynth_cache = PreSynthesisCache()
        self._presynth_worker = None
        # Parada ASSÍNCRONA da narração (perf/gui): virar página durante a
        # narração ou trocar de narração ("Ouvir original") não pode mais
        # bloquear a GUI com wait(2000). O worker sinalizado para parar fica
        # aqui, DRENANDO, até seu `finished` REAL chegar — só então é solto/
        # deleteLater (nunca destruímos um QThread cuja thread do SO ainda vive
        # — lição do PR #32/SIGABRT). Uma narração NOVA pedida enquanto o antigo
        # drena é ENFILEIRADA (o TTSRouter é COMPARTILHADO e seu estado —
        # _is_cancelled/_active_player/_active_provider — não tolera dois
        # speak() simultâneos): ela só dispara no `finished` do último worker em
        # drenagem, com um QTimer de segurança (nunca um wait bloqueante).
        self._retiring_workers: list = []
        self._pending_narration = None            # callable de lançamento adiado
        self._pending_narration_timer = None      # watchdog de segurança
        self._resume_banner = None  # banner "retomar leitura" (tarefa 3.7)
        # Tarefa 5.2 — cronômetro de leitura por página: timestamp monotônico
        # de quando a página atual entrou em exibição (None = nada correndo)
        # e o último (page, total) emitido, para o flush no fechamento.
        self._page_started_at: float | None = None
        self._last_progress: tuple[int, int] | None = None
        # Pausa por minimizar/perder visibilidade (limitação 5.2 corrigida
        # nesta rodada): trecho em curso é congelado aqui quando a janela
        # minimiza, em vez de continuar contando ocioso. _timer_paused_for_visibility
        # distingue "pausado pela janela" de "nenhum cronômetro rodando"
        # (livro fechado/timer já consumido) — só o primeiro caso deve
        # reiniciar o cronômetro ao restaurar (ver _resume_reading_timer).
        self._accumulated_page_seconds: float = 0.0
        self._timer_paused_for_visibility: bool = False
        self._footer_obs_id = None
        self._proactive_service = ProactiveReaderService(parent=self)
        self._proactive_service.observation_ready.connect(self._on_proactive_observation)
        self._proactive_service.error_occurred.connect(self._on_proactive_error)
        # Cross-reference proativo: dá ao agente acesso de leitura ao índice vetorial
        # para conectar a página atual a outros livros da biblioteca.
        if rag_engine is not None:
            self._proactive_service.set_cross_reference(self._proactive_cross_ref)
        # Continuidade (Fase 5): o proativo consulta as observações persistidas
        # para não repetir o que já disse e pular páginas já observadas.
        self._proactive_service.set_observations_provider(self._proactive_observations)
        # Aprendizado (Fase 6): os tipos de observação que o leitor costuma
        # dispensar orientam o prompt do proativo (sinal global, com dispensadas).
        self._proactive_service.set_dismissal_history_provider(self._proactive_dismissal_history)
        self._setup_ui()
        self._setup_shortcuts()
        self.reading_context_updated.connect(
            lambda b, t, p, txt: self._proactive_service.process_page_context(txt, p, b)
        )

    def _proactive_observations(self, book_id: int, page=None) -> list[dict]:
        """Observações persistidas do livro (Fase 5 — memória do proativo).

        Não dispensadas, mais recentes primeiro; limit curto (o bloco de
        memória usa no máximo 5). Sem banco → lista vazia (ADR-005).
        """
        if self._db is None or not book_id:
            return []
        return self._db.get_observations(book_id=book_id, page=page, limit=5)

    def _proactive_dismissal_history(self) -> list[dict]:
        """Histórico global de observações (Fase 6 — aprendizado com dispensas).

        Todos os livros, INCLUINDO dispensadas (é delas que se aprende); janela
        das 200 mais recentes. Sem banco → lista vazia (ADR-005).
        """
        if self._db is None:
            return []
        return self._db.get_observations(include_dismissed=True, limit=200)

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
        toolbar.setObjectName("readerToolbar")
        # QWidget puro não pinta background vindo de QSS sem este atributo
        # (mesma lição do AnnotationPanel — Onda 0b 1/2, PR #42/#43).
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)

        # Botão voltar
        back_btn = QPushButton("← Biblioteca")
        back_btn.setObjectName("readerBackBtn")
        back_btn.clicked.connect(self.closed.emit)
        tb_layout.addWidget(back_btn)

        # Título do documento
        self._title_label = QLabel()
        self._title_label.setObjectName("readerTitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Deixa o título encolher livremente para nunca empurrar/cortar os botões
        # da direita (ex.: o "⋯" com Página Dupla) quando o espaço fica curto.
        self._title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._title_label.setMinimumWidth(0)
        tb_layout.addWidget(self._title_label, stretch=1)

        # Navegação de páginas
        self._prev_btn = QPushButton("◀")
        self._prev_btn.setAccessibleName("Página anterior")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setObjectName("readerNavBtn")
        self._prev_btn.clicked.connect(self._go_prev)
        tb_layout.addWidget(self._prev_btn)

        self._page_label = QLabel("0/0")
        self._page_label.setFixedWidth(80)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setObjectName("readerPageLabel")
        tb_layout.addWidget(self._page_label)

        self._next_btn = QPushButton("▶")
        self._next_btn.setAccessibleName("Próxima página")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setObjectName("readerNavBtn")
        self._next_btn.clicked.connect(self._go_next)
        tb_layout.addWidget(self._next_btn)

        # Zoom
        zoom_out = QPushButton("−")
        zoom_out.setAccessibleName("Diminuir zoom")
        zoom_out.setFixedSize(28, 28)
        zoom_out.setObjectName("readerZoomBtn")
        zoom_out.clicked.connect(self._zoom_out)
        tb_layout.addWidget(zoom_out)

        zoom_in = QPushButton("+")
        zoom_in.setAccessibleName("Aumentar zoom")
        zoom_in.setFixedSize(28, 28)
        zoom_in.setObjectName("readerZoomBtn")
        zoom_in.clicked.connect(self._zoom_in)
        tb_layout.addWidget(zoom_in)

        # Botão "Aa" — popover de tipografia do leitor (fonte/tamanho/entrelinha/
        # margem/tema, aplicado ao vivo). "Aa" é texto (não emoji).
        self._typography_btn = QPushButton("Aa")
        self._typography_btn.setFixedSize(36, 32)
        self._typography_btn.setCheckable(True)
        self._typography_btn.setToolTip("Tipografia do leitor (fonte, tamanho, tema)")
        self._typography_btn.setAccessibleName("Tipografia do leitor")
        self._typography_btn.setObjectName("readerTypographyBtn")
        self._typography_btn.clicked.connect(self._open_typography_popover)
        tb_layout.addWidget(self._typography_btn)
        self._typography_popover = None

        # Separador
        sep = QLabel("│")
        sep.setObjectName("readerToolbarSep")
        tb_layout.addWidget(sep)

        # Botão de anotações — emoji como ÍCONE (evita sobreposição no Windows);
        # botão só-ícone: texto vazio + tooltip. Ver styles.emoji_icon.
        self._annotations_btn = QPushButton("")
        self._annotations_btn.setIcon(emoji_icon("📝"))
        self._annotations_btn.setFixedSize(32, 32)
        self._annotations_btn.setToolTip("Painel de Anotações")
        self._annotations_btn.setAccessibleName("Painel de Anotações")
        self._annotations_btn.setCheckable(True)
        self._annotations_btn.setObjectName("readerAnnotationsBtn")
        self._annotations_btn.clicked.connect(self._toggle_annotations)
        tb_layout.addWidget(self._annotations_btn)

        # Botão Marcador (🔖) — toggle do bookmark da página atual. Emoji como
        # ÍCONE (nunca no texto); o estado marcado indica que a página tem
        # marcador (atualizado ao navegar).
        self._bookmark_btn = QPushButton("")
        self._bookmark_btn.setIcon(emoji_icon("🔖"))
        self._bookmark_btn.setFixedSize(32, 32)
        self._bookmark_btn.setCheckable(True)
        self._bookmark_btn.setToolTip("Marcar página")
        self._bookmark_btn.setAccessibleName("Marcar página atual")
        self._bookmark_btn.setObjectName("readerBookmarkBtn")
        self._bookmark_btn.clicked.connect(self._toggle_current_bookmark)
        tb_layout.addWidget(self._bookmark_btn)

        # Botão Painel Lateral (📑) — Tarefa 1.3: mostra/oculta
        # self._side_panel_tabs (abas Sumário/Marcadores) por inteiro. Estado
        # persistido em reader.side_panel_visible (default True) e restaurado
        # ao abrir o leitor (ver _apply_side_panel_visibility).
        self._side_panel_toggle_btn = QPushButton("")
        self._side_panel_toggle_btn.setIcon(emoji_icon("📑"))
        self._side_panel_toggle_btn.setFixedSize(32, 32)
        self._side_panel_toggle_btn.setCheckable(True)
        self._side_panel_toggle_btn.setToolTip("Sumário/Marcadores")
        self._side_panel_toggle_btn.setAccessibleName("Painel Sumário/Marcadores")
        self._side_panel_toggle_btn.setObjectName("readerSidePanelToggleBtn")
        self._side_panel_toggle_btn.clicked.connect(self._toggle_side_panel)
        tb_layout.addWidget(self._side_panel_toggle_btn)

        # Botão busca no documento
        search_btn = QPushButton("")
        search_btn.setIcon(emoji_icon("🔍"))
        search_btn.setFixedSize(32, 32)
        search_btn.setToolTip("Buscar no documento (Ctrl+F)")
        search_btn.setAccessibleName("Buscar no documento")
        search_btn.setObjectName("readerSearchBtn")
        search_btn.clicked.connect(self._toggle_search)
        tb_layout.addWidget(search_btn)

        # Botão tela cheia
        self._fullscreen_btn = QPushButton("")
        self._fullscreen_btn.setIcon(emoji_icon("⛶"))
        self._fullscreen_btn.setFixedSize(32, 32)
        self._fullscreen_btn.setToolTip("Tela cheia (F11)")
        self._fullscreen_btn.setAccessibleName("Alternar tela cheia")
        self._fullscreen_btn.setObjectName("readerFullscreenBtn")
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        tb_layout.addWidget(self._fullscreen_btn)

        # Botão Página Dupla (state-holder no menu de overflow)
        self._double_page_btn = QPushButton("Dupla")
        self._double_page_btn.setIcon(emoji_icon("📖"))
        self._double_page_btn.setFixedSize(85, 32)
        self._double_page_btn.setCheckable(True)
        self._double_page_btn.setToolTip("Modo Página Dupla")
        self._double_page_btn.setObjectName("readerDoublePageBtn")
        self._double_page_btn.clicked.connect(self._toggle_double_page)
        # Movido para o menu de overflow ("⋯"): mantido como state-holder.

        # Botão Marca-Texto (modo de destaque)
        self._highlight_mode_btn = QPushButton("")
        self._highlight_mode_btn.setIcon(emoji_icon("🖍️"))
        self._highlight_mode_btn.setFixedSize(32, 32)
        self._highlight_mode_btn.setCheckable(True)
        self._highlight_mode_btn.setToolTip(
            "Modo Marca-Texto (PDF)\n\n"
            "1. Clique e arraste para selecionar uma área\n"
            "2. Solte o mouse\n"
            "3. Clique DIREITO dentro da seleção azul\n"
            "4. Escolha '🖍️ Destacar' no menu"
        )
        self._highlight_mode_btn.setAccessibleName("Modo Marca-Texto")
        self._highlight_mode_btn.setObjectName("readerHighlightModeBtn")
        self._highlight_mode_btn.clicked.connect(self._toggle_highlight_mode)
        # Movido para o menu de overflow ("⋯"): mantido como state-holder.

        # Botão Estudar (ações do agente sobre a página atual)
        self._study_btn = QPushButton("")
        self._study_btn.setIcon(emoji_icon("🎓"))
        self._study_btn.setFixedSize(32, 32)
        self._study_btn.setToolTip("Estudar a página: explicar · resumir · flashcards · glossário")
        self._study_btn.setAccessibleName("Estudar a página")
        self._study_btn.setObjectName("readerStudyBtn")
        self._study_btn.clicked.connect(self._open_study_menu)
        tb_layout.addWidget(self._study_btn)

        # Botão Painel IA
        self._ai_panel_btn = QPushButton("")
        self._ai_panel_btn.setIcon(emoji_icon("🤖"))
        self._ai_panel_btn.setFixedSize(32, 32)
        self._ai_panel_btn.setCheckable(True)
        self._ai_panel_btn.setToolTip("Assistente IA")
        self._ai_panel_btn.setAccessibleName("Assistente IA")
        self._ai_panel_btn.setObjectName("readerAiPanelBtn")
        self._ai_panel_btn.clicked.connect(self._toggle_ai_panel)
        tb_layout.addWidget(self._ai_panel_btn)

        # Botão único de Áudio (🔊) — Tarefa 1.4: consolida os 3 controles
        # antigos (Ouvir / Parar / TTS) num único QToolButton com
        # MenuButtonPopup. Clicar no CORPO do botão dispara _toggle_audio
        # diretamente (ação primária de 1 clique só — preserva o
        # comportamento anterior de _audio_btn); clicar na SETA lateral abre
        # o menu com "Ouvir página" (mesmo toggle, por descoberta/teclado),
        # "Parar" (antes era um botão com setVisible; agora é um QAction com
        # setEnabled — só habilitado durante reprodução/pausa) e "Configurar
        # vozes…" (o que antes era o state-holder _tts_settings_btn, nunca
        # exibido na toolbar). Emoji do botão via emoji_icon (padrão de
        # botão); emoji dos itens do QMenu embutido no texto (padrão já usado
        # pelos demais QAction deste arquivo, ex.: _act_double_page).
        self._audio_btn = QToolButton()
        self._audio_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._audio_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._audio_btn.setText("Ouvir")
        self._audio_btn.setIcon(emoji_icon("🔊"))
        self._audio_btn.setFixedHeight(32)
        self._audio_btn.setMinimumWidth(100)
        self._audio_btn.setToolTip("Ouvir Página (TTS)")
        self._audio_btn.setObjectName("readerAudioBtn")
        self._audio_btn.clicked.connect(self._toggle_audio)

        self._act_audio_toggle = QAction("🔊 Ouvir página", self)
        self._act_audio_toggle.triggered.connect(self._toggle_audio)

        self._act_audio_stop = QAction("⏹️ Parar", self)
        self._act_audio_stop.setEnabled(False)  # só habilitado durante reprodução/pausa
        # Stop MANUAL (ação explícita do usuário) passa por _on_audio_stop_clicked
        # para limpar o override "Ouvir original" (achado B0). O
        # _stop_audio_if_running cru NÃO limpa o override porque também é chamado
        # em transições internas (virar página na cadeia, narrate_text).
        self._act_audio_stop.triggered.connect(self._on_audio_stop_clicked)

        self._act_audio_settings = QAction("⚙️ Configurar vozes…", self)
        self._act_audio_settings.triggered.connect(self._on_tts_settings_clicked)

        self._audio_menu = QMenu(self._audio_btn)
        self._audio_menu.setObjectName("readerPopupMenu")
        self._audio_menu.addAction(self._act_audio_toggle)
        self._audio_menu.addAction(self._act_audio_stop)
        self._audio_menu.addSeparator()
        self._audio_menu.addAction(self._act_audio_settings)
        self._audio_btn.setMenu(self._audio_menu)
        tb_layout.addWidget(self._audio_btn)

        # Proactive Agent Toggle
        self._proactive_combo = QComboBox()
        self._proactive_combo.addItems(["Desligado", "Leve", "Moderado", "Estudo"])
        self._proactive_combo.setToolTip("Agente Proativo de Leitura")
        self._proactive_combo.setFixedSize(90, 32)
        self._proactive_combo.setObjectName("readerProactiveCombo")
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
        self._overflow_btn.setAccessibleName("Mais opções")
        self._overflow_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._overflow_btn.setObjectName("readerOverflowBtn")
        self._overflow_menu = QMenu(self._overflow_btn)
        self._overflow_menu.setObjectName("readerPopupMenu")
        self._act_double_page = QAction("📖 Página Dupla", self, checkable=True)
        self._act_double_page.triggered.connect(self._menu_toggle_double_page)
        self._act_highlight = QAction("🖍️ Modo Marca-Texto", self, checkable=True)
        self._act_highlight.triggered.connect(self._menu_toggle_highlight)
        # Leitura contínua: narração vira páginas automaticamente até o fim.
        self._act_continuous = QAction("🔁 Leitura Contínua (vira páginas)", self, checkable=True)
        _cfg = getattr(self.window(), "_config", None)
        if _cfg is not None:
            self._continuous_reading = bool(_cfg.get("tts.continuous_reading", False))
        self._act_continuous.setChecked(self._continuous_reading)
        self._act_continuous.triggered.connect(self._toggle_continuous_reading)
        # Leitura contínua TRADUZIDA: mesmo mecanismo, cada página passa pelo
        # NLLB antes de narrar (Commit 5 do contrato de tradução confiável).
        self._act_continuous_translate = QAction(
            "🌐🔁 Leitura Contínua Traduzida (PT)", self, checkable=True)
        if _cfg is not None:
            self._continuous_translate_mode = bool(
                _cfg.get("tts.continuous_translate_reading", False))
        self._act_continuous_translate.setChecked(self._continuous_translate_mode)
        self._act_continuous_translate.triggered.connect(self._toggle_continuous_translate_reading)
        # Par explícito "Ouvir original / Ouvir traduzido" (sugestão registrada
        # em 2026-07-17): narração ONE-SHOT da página atual, sem alterar os
        # toggles persistidos de leitura contínua (normal/traduzida).
        self._act_listen_original = QAction("🔊 Ouvir original", self)
        self._act_listen_original.triggered.connect(self._on_listen_original)
        # Ler a página em português: traduz (NLLB offline) e narra o resultado.
        self._act_read_translated = QAction("🌐 Ouvir traduzido (PT)", self)
        self._act_read_translated.triggered.connect(self._on_read_translated_page)
        # Traduzir a página como TEXTO (cartão no painel), sem narrar.
        self._act_translate_page = QAction("🌐 Traduzir Página (texto)", self)
        self._act_translate_page.triggered.connect(self._on_translate_page)
        # Atalho de tradução TAMBÉM no menu do botão de áudio (pedido do
        # usuário, 2026-07-17: o modo traduzido ficava "escondido" no menu ⋯ e
        # a troca era lenta). São as MESMAS QActions dos dois menus — o Qt
        # sincroniza o estado (check) automaticamente entre eles.
        self._audio_menu.addSeparator()
        self._audio_menu.addAction(self._act_listen_original)
        self._audio_menu.addAction(self._act_read_translated)
        self._audio_menu.addAction(self._act_continuous_translate)
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
        self._overflow_menu.addAction(self._act_continuous)
        self._overflow_menu.addAction(self._act_continuous_translate)
        self._overflow_menu.addAction(self._act_listen_original)
        self._overflow_menu.addAction(self._act_read_translated)
        self._overflow_menu.addAction(self._act_translate_page)
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

        # Painel lateral: abas "Sumário" (TOC) e "Marcadores" (bookmarks).
        self._toc_widget = TOCWidget()
        self._toc_widget.page_selected.connect(self._go_to_page)
        self._bookmarks_panel = BookmarksPanel()
        self._bookmarks_panel.bookmark_selected.connect(self._go_to_page)
        self._bookmarks_panel.bookmark_removed.connect(self._on_bookmark_removed)
        # Tarefa 3.2 — aba X-Ray: conceitos do livro presentes NA PÁGINA atual e
        # onde mais aparecem na biblioteca. Sem LLM, só o grafo (GraphStore).
        graph_store = GraphStore(self._db) if self._db is not None else None
        self._xray_panel = XRayPanel(graph_store=graph_store)
        self._side_panel_tabs = QTabWidget()
        self._side_panel_tabs.setObjectName("readerSidePanelTabs")
        self._side_panel_tabs.setMinimumWidth(200)
        self._side_panel_tabs.setMaximumWidth(300)
        self._side_panel_tabs.addTab(self._toc_widget, "Sumário")
        self._side_panel_tabs.addTab(self._bookmarks_panel, "Marcadores")
        self._side_panel_tabs.addTab(self._xray_panel, "X-Ray")
        splitter.addWidget(self._side_panel_tabs)
        # Tarefa 1.3 — aplica a visibilidade persistida (reader.side_panel_visible,
        # default True) já na construção; open_book() reaplica ao abrir um livro.
        self._apply_side_panel_visibility()

        # Stack para diferentes tipos de conteúdo
        self._content_stack = QStackedWidget()

        # Visualizador de imagem (para PDF)
        self._image_scroll = QScrollArea()
        self._image_scroll.setWidgetResizable(True)
        self._image_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_scroll.setObjectName("readerImageScroll")
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_scroll.setWidget(self._image_label)
        self._content_stack.addWidget(self._image_scroll)  # index 0

        # Rubber band para seleção em PDF (fallback para áreas sem texto);
        # o feedback ao vivo da seleção por FLUXO usa o overlay abaixo
        # (item 9 do backlog UX: quads por linha durante o arrasto).
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self._image_label)
        from src.gui.widgets.selection_flow_overlay import SelectionFlowOverlay
        self._selection_flow_overlay = SelectionFlowOverlay(self._image_label)
        from PyQt6.QtCore import QElapsedTimer
        self._flow_throttle = QElapsedTimer()
        self._origin = QPoint()
        self._is_selecting = False
        self._last_selection_coords: tuple | None = None  # Últimas coords normalizadas salvas
        self._last_selection_flow: dict | None = None  # {"text", "quads"} — seleção por fluxo

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

        # Word Wise no EPUB (débito 3.4 / rodada B3): o QWebEngineView roda o
        # Chromium em processo separado e não entrega os mouse events do Qt de
        # forma confiável ao eventFilter. Detectamos o fim da seleção pelo
        # ``mouseup`` do DOM (via QWebChannel — ver EpubSelectionBridge) e
        # roteamos seleções curtas para o mesmo popover do PDF. A fiação JS é
        # re-injetada a cada página no ``loadFinished`` (o setHtml troca o doc).
        self._epub_selection_bridge = EpubSelectionBridge()
        self._epub_web_channel = QWebChannel(self._web_view.page())
        self._epub_web_channel.registerObject("epubBridge", self._epub_selection_bridge)
        self._web_view.page().setWebChannel(self._epub_web_channel)
        self._epub_selection_bridge.selection_ended.connect(self._on_epub_selection_ended)
        self._web_view.page().loadFinished.connect(self._inject_epub_selection_js)

        splitter.addWidget(self._content_stack)
        splitter.setStretchFactor(1, 1)  # área de leitura expande; TOC fica no seu max

        # Painel de anotações — agora vive no dock à direita (não mais inline),
        # liberando largura para a leitura.
        self._annotation_panel = AnnotationPanel()
        self._annotation_panel.annotation_added.connect(self._on_annotation_added)
        self._annotation_panel.annotation_deleted.connect(
            lambda ann_id: self.annotation_deleted.emit(ann_id)
        )
        self._annotation_panel.annotation_renamed.connect(
            lambda ann_id, title: self.annotation_renamed.emit(ann_id, title)
        )
        self._annotation_panel.goto_page.connect(self._go_to_page)

        left_layout.addWidget(splitter, stretch=1)

        # Proactive Footer Widget (starts hidden)
        self._proactive_footer = ProactiveFooterWidget()
        # "flashcard_qa": o LLM destila o insight em pergunta/resposta antes de
        # abrir o diálogo do Anki (o insight não vira mais a "pergunta" crua).
        self._proactive_footer.flashcard_requested.connect(
            lambda text: self.ai_action_requested.emit("flashcard_qa", text)
        )
        self._proactive_footer.closed.connect(self._on_footer_closed)
        left_layout.addWidget(self._proactive_footer)

        # Barra de progresso inferior
        self._progress_bar_widget = QWidget()
        self._progress_bar_widget.setFixedHeight(28)
        self._progress_bar_widget.setObjectName("readerProgressBarWidget")
        # QWidget puro não pinta background vindo de QSS sem este atributo
        # (mesma lição do AnnotationPanel — Onda 0b 1/2, PR #42/#43).
        self._progress_bar_widget.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True)
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
        self._dock.add_tab("annotations", "Anotações", self._annotation_panel, icon="📝")
        # Insights do agente proativo: registro persistente das observações da sessão.
        self._insights_panel = ProactiveInsightsPanel()
        self._insights_panel.flashcard_requested.connect(
            lambda text: self.ai_action_requested.emit("flashcard_qa", text)
        )
        self._insights_panel.dismiss_requested.connect(self._on_observation_dismissed)
        self._dock.add_tab("insights", "Insights", self._insights_panel, icon="💡")
        self._dock.closed.connect(self.hide_dock)
        self._dock.tab_changed.connect(lambda _k: self._sync_dock_buttons())
        self._main_splitter.addWidget(self._dock)
        self._dock.hide()
        # Persiste a proporção do dock quando o usuário arrasta o divisor —
        # o layout escolhido vira o padrão das próximas aberturas.
        self._main_splitter.splitterMoved.connect(self._on_dock_splitter_moved)

        # O painel do Assistente (RAGPanel) é injetado no dock depois (set_ai_panel).
        self._ai_panel_container = None

        # Popover de ações sobre a seleção (PDF) — alternativa rápida ao clique direito.
        self._selection_popover = SelectionActionPopover(self)
        self._selection_popover.action_requested.connect(self._on_selection_popover_action)

        # Cartão de definição rápida (Word Wise, tarefa 3.4) — inline, nunca
        # abre o painel do RAG (diferente das demais ações de seleção).
        self._word_wise_popover = WordWisePopover(self)
        self._word_wise_worker = None

    def _setup_shortcuts(self):
        s_next = QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._go_next)
        s_next.setContext(Qt.ShortcutContext.ApplicationShortcut)

        s_prev = QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._go_prev)
        s_prev.setContext(Qt.ShortcutContext.ApplicationShortcut)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_search)
        QShortcut(QKeySequence("Ctrl+D"), self, self._toggle_current_bookmark)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._toggle_fullscreen)

        # Tarefa 1.2 — Space/Shift+Space/PageUp/PageDown viram página. Contexto
        # WindowShortcut (igual Escape/Ctrl+F/Ctrl+D/F11 acima — NÃO o
        # ApplicationShortcut mais amplo usado nas setas). Investigação
        # empírica (probe manual com QTest.keyClick, fora da suíte): um
        # QShortcut de tecla simples (sem modificador reconhecível como texto)
        # NÃO dispara quando um QLineEdit/QTextEdit focado aceita o evento
        # QEvent.ShortcutOverride para digitar o caractere normalmente — é
        # assim que a barra de busca do documento, o painel de Anotações e o
        # campo do RAG (todos QLineEdit/QTextEdit padrão) já ficam protegidos
        # sem código extra. Como reforço explícito (e documentado) desse
        # comportamento — e para cobrir qualquer widget de composição
        # customizado que não siga o mesmo contrato — os slots abaixo também
        # conferem o focusWidget() antes de virar a página.
        # LIMITAÇÃO CONHECIDA: no QWebEngineView (conteúdo EPUB), o foco de um
        # <input> DENTRO do HTML da página não é visível ao Qt de forma
        # síncrona (a confirmação vem do processo do Chromium via IPC
        # assíncrono), então o atalho SEMPRE vira página quando o web_view
        # tem o foco do Qt — mesmo que um campo editável interno do HTML
        # esteja focado. Risco aceito: o HTML do livro é somente leitura
        # (sanitizado em html_sanitizer.sanitize_book_html, sem formulários).
        s_space_next = QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._shortcut_go_next)
        s_space_next.setContext(Qt.ShortcutContext.WindowShortcut)
        s_space_prev = QShortcut(QKeySequence("Shift+Space"), self, self._shortcut_go_prev)
        s_space_prev.setContext(Qt.ShortcutContext.WindowShortcut)
        s_pgdn = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, self._shortcut_go_next)
        s_pgdn.setContext(Qt.ShortcutContext.WindowShortcut)
        s_pgup = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, self._shortcut_go_prev)
        s_pgup.setContext(Qt.ShortcutContext.WindowShortcut)

    def _is_text_input_focused(self) -> bool:
        """True quando o foco atual está num campo de texto que deve continuar
        recebendo a tecla (busca no documento, anotações, campo do RAG) — ver
        o comentário em _setup_shortcuts para a investigação completa.
        """
        from PyQt6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit
        w = QApplication.focusWidget()
        return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit))

    def _shortcut_go_next(self) -> None:
        """Slot de Space/PageDown — não vira página com um campo de texto focado."""
        if self._is_text_input_focused():
            return
        self._go_next()

    def _shortcut_go_prev(self) -> None:
        """Slot de Shift+Space/PageUp — não vira página com um campo de texto focado."""
        if self._is_text_input_focused():
            return
        self._go_prev()

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
            # No _image_label a SELEÇÃO tem prioridade: a virada por clique na
            # margem é decidida no RELEASE (clique sem arrasto). Antes, pressionar
            # perto da margem direita para selecionar uma palavra virava a página.
            # NOTA (Tarefa 1.2): este ramo (image_scroll.viewport() e web_view/
            # EPUB) já existia antes desta tarefa e fica como está — dispara no
            # PRESS, sem checar seleção/link/modo marca-texto. A versão nova
            # (thirds + guarda de marca-texto, decidida no RELEASE) foi
            # implementada só para o caminho PDF/imagem (_image_label), que já
            # tinha a infraestrutura de "clique sem arrasto" pronta; no
            # web_view o risco de engolir um clique num link ou o início de uma
            # seleção de texto é maior e não foi resolvido aqui — limitação
            # documentada e aceita (ver contrato da Tarefa 1.2).
            if event.button() == Qt.MouseButton.LeftButton and obj is not self._image_label:
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
                self._selection_flow_overlay.clear()
                self._flow_throttle.start()
                self._is_selecting = True
                self._last_selection_coords = None  # Reseta coords ao iniciar
                self._last_selection_flow = None
                if hasattr(self, "_selection_popover"):
                    self._selection_popover.hide()
                if hasattr(self, "_word_wise_popover"):
                    self._word_wise_popover.hide()
                return True
            elif event.type() == QEvent.Type.MouseMove and self._is_selecting:
                pos = event.position().toPoint()
                # A geometria do rubber band é SEMPRE atualizada (o release e o
                # popover dependem dela), mas ele só fica visível quando o
                # fluxo de texto não cobre o arrasto (ex.: área de imagem).
                self._rubber_band.setGeometry(QRect(self._origin, pos).normalized())
                if self._update_live_selection(pos):
                    self._rubber_band.hide()
                else:
                    self._selection_flow_overlay.clear()
                    if not self._rubber_band.isVisible():
                        self._rubber_band.show()
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._is_selecting = False
                # Calcula e armazena as coords normalizadas da seleção atual
                rect = self._rubber_band.geometry()
                # Tarefa 1.2 — CLIQUE (sem arrasto) no terço esquerdo/direito
                # da página vira a página — decidido aqui, no RELEASE, e não
                # no PRESS, para não engolir seleções que começam perto da
                # margem (rect.width()/height() < 6 ⇒ não houve arrasto real).
                # Só quando NÃO está no modo Marca-Texto: nesse modo o
                # clique/arrasto marca uma área para destacar, não deve virar
                # página. Implementado só para este caminho (QLabel/pixmap de
                # PDF/imagem) — no web_view (EPUB) o risco de engolir cliques
                # em links/seleção de texto é maior (ver o bloco de
                # MouseButtonPress logo acima, que já existia antes desta
                # tarefa e permanece com sua própria zona/limitação).
                origin = getattr(self, "_origin", None)
                if (origin is not None and rect.width() < 6 and rect.height() < 6
                        and not self._highlight_mode_btn.isChecked()):
                    width = obj.width()
                    if origin.x() < width * self._PAGE_TURN_ZONE_RATIO:
                        self._hide_selection_marquee()
                        self._go_prev()
                        return True
                    elif origin.x() > width * (1 - self._PAGE_TURN_ZONE_RATIO):
                        self._hide_selection_marquee()
                        self._go_next()
                        return True
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
                        # Seleção por fluxo de texto: usa os PONTOS de início e
                        # fim do arrasto (não o retângulo) — frases que começam/
                        # terminam no meio da linha viram quads por linha.
                        self._last_selection_flow = None
                        if self._reader and hasattr(self._reader, "get_selection_flow"):
                            release_pt = event.position().toPoint()
                            spx = min(max((self._origin.x() - offset_x) / pixmap.width(), 0.0), 1.0)
                            spy = min(max((self._origin.y() - offset_y) / pixmap.height(), 0.0), 1.0)
                            epx = min(max((release_pt.x() - offset_x) / pixmap.width(), 0.0), 1.0)
                            epy = min(max((release_pt.y() - offset_y) / pixmap.height(), 0.0), 1.0)
                            try:
                                self._last_selection_flow = self._reader.get_selection_flow(
                                    self._reader.current_page, (spx, spy), (epx, epy))
                            except Exception:
                                self._last_selection_flow = None
                        self._show_selection_popover(rect)
                # Mantém rubber band visível para clique direito
                return True

        return super().eventFilter(obj, event)

    def _update_live_selection(self, pos) -> bool:
        """Feedback ao vivo da seleção por fluxo durante o arrasto (item 9).

        Converte origem/posição atual em % da página, pede os quads ao
        reader e pinta um retângulo por linha no overlay. Devolve True se o
        fluxo cobriu o arrasto (overlay ativo); False manda o chamador usar
        o rubber band retangular (áreas de imagem / leitor sem fluxo).
        Throttle de 40ms: o get_selection_flow varre as palavras da página.
        """
        if not (self._reader and hasattr(self._reader, "get_selection_flow")):
            return False
        # Dentro da janela de throttle, mantém o que está na tela.
        if self._flow_throttle.isValid() and self._flow_throttle.elapsed() < 40:
            return self._selection_flow_overlay.isVisible()
        self._flow_throttle.restart()

        pixmap = self._image_label.pixmap()
        if pixmap is None or pixmap.width() <= 0 or pixmap.height() <= 0:
            return False
        label_size = self._image_label.size()
        offset_x = (label_size.width() - pixmap.width()) / 2
        offset_y = (label_size.height() - pixmap.height()) / 2

        def to_pct(pt):
            px = min(max((pt.x() - offset_x) / pixmap.width(), 0.0), 1.0)
            py = min(max((pt.y() - offset_y) / pixmap.height(), 0.0), 1.0)
            return px, py

        try:
            flow = self._reader.get_selection_flow(
                self._reader.current_page, to_pct(self._origin), to_pct(pos))
        except Exception:
            flow = None
        quads = (flow or {}).get("quads") or []
        if not quads:
            return False

        rects = [
            QRect(
                int(q[0] * pixmap.width() + offset_x),
                int(q[1] * pixmap.height() + offset_y),
                max(1, int((q[2] - q[0]) * pixmap.width())),
                max(1, int((q[3] - q[1]) * pixmap.height())),
            )
            for q in quads
        ]
        self._selection_flow_overlay.set_rects(rects)
        return True

    def _hide_selection_marquee(self) -> None:
        """Esconde o feedback visual da seleção (rubber band + overlay de fluxo)."""
        self._rubber_band.setVisible(False)
        self._selection_flow_overlay.clear()

    def open_book(self, book_data: dict, start_page: int = 0):
        """Abre um livro para leitura."""
        filepath = book_data.get("file_path", "")
        if not filepath:
            return

        # Tarefa 5.2: tempo pendente da página do livro ANTERIOR é
        # descarregado ANTES de trocar o _book_id (atribuição correta).
        self._flush_reading_time()
        self._last_progress = None

        self._book_id = book_data.get("id", 0)
        self._invalidate_presynth()  # troca de livro descarta pré-síntese (3.6)
        self._listen_original_override = False  # troca de livro reseta o override (B0)
        self._annotation_panel.set_book_id(self._book_id)
        self._title_label.setText(book_data.get("title", ""))
        self._load_persisted_observations()
        self._refresh_bookmarks()
        self._apply_side_panel_visibility()

        # Fecha leitor anterior
        if self._reader and self._reader.is_open:
            self._reader.close()

        # Cria o leitor apropriado
        self._reader = create_reader(filepath)
        self._reader.open()

        # Carrega TOC — sem entradas órfãs (números soltos) e com miniaturas
        # de capítulo quando o leitor renderiza páginas (PDF).
        from src.readers.toc_utils import clean_toc
        toc = clean_toc(self._reader.get_toc())
        self._toc_widget.load_toc(toc, thumb_provider=self._reader.render_thumbnail)

        # Vai para a página inicial
        self._go_to_page(start_page)

        # Tarefa 3.7: banner discreto de retomada quando há progresso (>0),
        # com mini-resumo da última sessão (dados já existentes, sem LLM).
        self._maybe_show_resume_banner()

    def _maybe_show_resume_banner(self) -> None:
        """Mostra o banner "Retomar leitura" (tarefa 3.7), se houver progresso.

        Reusa ``build_resume_info`` (core puro): posição/tempo + anotações
        recentes + conceitos do grafo + síntese do dossiê JÁ em cache — NUNCA
        dispara LLM no caminho de abrir o livro (ADR-005). Sem progresso →
        ``build_resume_info`` devolve None → nenhum banner.
        """
        if self._db is None or not self._book_id:
            return
        try:
            from src.core.graph.graph_store import GraphStore
            from src.core.resume_summary import build_resume_info
            graph_store = GraphStore(self._db)
            info = build_resume_info(self._db, self._book_id, graph_store=graph_store)
        except Exception:
            info = None
        if not info:
            return
        try:
            from src.gui.widgets.resume_banner import ResumeBanner
            old = getattr(self, "_resume_banner", None)
            if old is not None:
                try:
                    old.dismiss()
                except Exception:
                    pass
            self._resume_banner = ResumeBanner(info, parent=self)
            self._resume_banner.closed.connect(self._on_resume_banner_closed)
            self._resume_banner.show_at_top()
        except Exception:
            self._resume_banner = None

    def _on_resume_banner_closed(self) -> None:
        self._resume_banner = None

    def _reader_css(self) -> str:
        """CSS do conteúdo HTML do leitor com a tipografia ATUAL da config.

        Fonte única de verdade: lê as MESMAS chaves ``reader.*`` que o diálogo de
        configurações grava (fonte/tamanho/entrelinha/margens). Sem config
        acessível, cai nos defaults de ``get_reader_css`` (ADR-005).
        """
        config = getattr(self.window(), "_config", None)
        if config is None:
            return get_reader_css(self._theme)
        return get_reader_css(
            self._theme,
            font_family=config.get("reader.font_family", DEFAULT_FONT_FAMILY),
            font_size=config.get("reader.font_size", DEFAULT_FONT_SIZE),
            line_height=config.get("reader.line_height", DEFAULT_LINE_HEIGHT),
            margin_h=config.get("reader.margin_horizontal", 60),
            margin_v=config.get("reader.margin_vertical", 40),
        )

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
            # EPUB/TXT/DOCX — renderiza como HTML. O conteúdo do livro é
            # sanitizado antes do setHtml: o QWebEngineView tem JS habilitado
            # (features próprias do leitor), então <script>/on*/javascript:
            # de um EPUB baixado da internet executariam aqui (§2.1).
            from src.readers.html_sanitizer import sanitize_book_html
            css = self._reader_css()
            html = f"""<!DOCTYPE html>
            <html><head><style>{css}</style></head>
            <body>{sanitize_book_html(content.content)}</body></html>"""
            self._web_view.setHtml(html)
            self._content_stack.setCurrentIndex(1)
            # Fase 9A: Resetar viewport do webview para EPUB/HTML
            self._web_view.page().runJavaScript("window.scrollTo(0, 0);")

        # Atualiza indicadores
        page = content.page_number
        total = content.total_pages
        self._page_label.setText(f"{page + 1}/{total}")
        self._progress_bar.set_page_info(page + 1, total)
        # Tarefa 5.2 — tempo real de leitura: os segundos desde o último
        # render (tempo passado na página ANTERIOR, com teto anti-idle)
        # seguem no próprio progress_changed e o cronômetro reinicia para a
        # página nova. Vale para QUALQUER troca de página — inclusive as
        # viradas automáticas da narração contínua (leitura por áudio conta
        # como leitura). Re-render da MESMA página (zoom/tema) também
        # descarrega e reinicia — sem contagem dupla, o timestamp é resetado
        # a cada descarga.
        seconds = self._take_elapsed_reading_seconds()
        self._start_reading_timer()
        self._last_progress = (page, total)
        self.progress_changed.emit(self._book_id, page, total, seconds)
        self._update_bookmark_button(page)

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

        # Tarefa 3.2 — atualiza o X-Ray com o TEXTO COMPLETO da página (a
        # interseção com os conceitos do livro é barata; ver src/core/xray.py).
        if hasattr(self, "_xray_panel"):
            self._xray_panel.update_context(self._book_id, page, page_text)

    # ── Tempo real de leitura (Tarefa 5.2) ──────────────────────────────
    # time.monotonic (imune a ajuste de relógio) marca a entrada em cada
    # página; na troca/fechamento o decorrido é normalizado pelo teto
    # anti-idle (clamp_session_seconds, 300s/página) e emitido no
    # progress_changed para o main_window persistir em reading_sessions.
    # Limitação 5.2 CORRIGIDA nesta rodada: janela MINIMIZADA agora
    # (perda de foco sem minimizar NÃO pausa — o teto de 300s/pág limita;
    # narração ativa tampouco pausa: modo audiobook conta como leitura)
    # pausa o cronômetro (_pause_reading_timer/_resume_reading_timer, wiring
    # em MainWindow.changeEvent) — o trecho em curso é congelado num
    # acumulado puro (total_elapsed_seconds, core/reading_stats.py) em vez de
    # continuar contando enquanto o app fica oculto. O teto de 300s/página
    # segue como rede de segurança adicional (idle sem minimizar, ex.: app em
    # foco mas usuário ausente).

    def _start_reading_timer(self) -> None:
        """Inicia o cronômetro da página atual — a menos que a janela esteja
        minimizada/sem visibilidade (``_timer_paused_for_visibility``), caso
        em que o início fica pendente até ``_resume_reading_timer``."""
        if self._timer_paused_for_visibility:
            return
        self._page_started_at = time.monotonic()

    def _pause_reading_timer(self) -> None:
        """Suspende o cronômetro ao minimizar/perder visibilidade: congela o
        trecho em curso no acumulado (``total_elapsed_seconds``, puro) em vez
        de descartá-lo ou deixá-lo correr ocioso. Idempotente — chamar duas
        vezes seguidas (dois eventos de minimizar sem restaurar entre eles)
        não conta o trecho duas vezes, pois ``_page_started_at`` já foi
        zerado na primeira chamada."""
        if self._page_started_at is None:
            return
        self._accumulated_page_seconds = total_elapsed_seconds(
            self._accumulated_page_seconds, self._page_started_at, time.monotonic())
        self._page_started_at = None
        self._timer_paused_for_visibility = True

    def _resume_reading_timer(self) -> None:
        """Retoma o cronômetro ao restaurar a janela — só reinicia o
        timestamp se a pausa em curso foi causada por
        ``_pause_reading_timer`` (evita reativar um cronômetro que estava
        parado por outro motivo, ex.: nenhum livro aberto)."""
        if not self._timer_paused_for_visibility:
            return
        self._timer_paused_for_visibility = False
        self._page_started_at = time.monotonic()

    def _take_elapsed_reading_seconds(self) -> int:
        """Consome o cronômetro da página atual (acumulado de pausas + trecho
        em curso, se houver): devolve os segundos decorridos (com teto
        anti-idle) e zera o estado. 0 se não havia nada a consumir (primeira
        página após abrir o livro)."""
        total = total_elapsed_seconds(
            self._accumulated_page_seconds, self._page_started_at, time.monotonic())
        self._accumulated_page_seconds = 0.0
        self._page_started_at = None
        if total <= 0:
            return 0
        return clamp_session_seconds(total)

    def _flush_reading_time(self) -> None:
        """Descarrega o tempo pendente da página atual (fechar livro ou
        trocar de livro) emitindo um progress_changed com a última posição
        conhecida. No-op quando não há cronômetro/livro/posição (ADR-005)."""
        seconds = self._take_elapsed_reading_seconds()
        if seconds <= 0 or self._book_id <= 0 or self._last_progress is None:
            return
        page, total = self._last_progress
        self.progress_changed.emit(self._book_id, page, total, seconds)

    def _go_to_page(self, page: int, *, preserve_audio: bool = False):
        """Renderiza ``page``. Por padrão para a narração (navegação real).

        ``preserve_audio=True``: re-render da MESMA página (zoom +/-, tipografia
        do popover "Aa") — NÃO deve parar/invalidar o áudio nem a pré-síntese
        (item C). A navegação real para OUTRA página continua parando o áudio
        (chamadas sem o argumento).
        """
        if not preserve_audio:
            self._stop_audio_if_running()
        if hasattr(self, "_selection_popover"):
            self._selection_popover.hide()
        if hasattr(self, "_word_wise_popover"):
            self._word_wise_popover.hide()
        if self._reader:
            content = self._reader.go_to_page(page)
            if content:
                self._render_page(content)

    def _go_next(self) -> None:
        self._invalidate_presynth()  # nav. manual descarta pré-síntese (3.6)
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
        self._invalidate_presynth()  # nav. manual descarta pré-síntese (3.6)
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
        self._act_continuous.setChecked(self._continuous_reading)
        self._act_continuous_translate.setChecked(self._continuous_translate_mode)
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
            # Mesma página, só re-render: preserva a narração em curso (item C).
            self._go_to_page(self._reader.current_page, preserve_audio=True)
        elif self._content_stack.currentIndex() == 1:
            self._web_view.setZoomFactor(self._web_view.zoomFactor() + 0.1)

    def _zoom_out(self):
        if self._reader and hasattr(self._reader, 'zoom'):
            self._reader.zoom = self._reader.zoom - 0.25
            # Mesma página, só re-render: preserva a narração em curso (item C).
            self._go_to_page(self._reader.current_page, preserve_audio=True)
        elif self._content_stack.currentIndex() == 1:
            self._web_view.setZoomFactor(self._web_view.zoomFactor() - 0.1)

    def close_reader(self):
        """Fecha o leitor atual."""
        # Tarefa 5.2: o tempo da última página lida é descarregado no
        # fechamento (senão a última página de cada sessão nunca contaria).
        self._flush_reading_time()
        # Teardown: espera (bloqueante, limitado) os workers de áudio — aqui é
        # encerramento, não interação, então nenhum worker órfão pode sobreviver.
        self._listen_original_override = False  # fechar leitor reseta o override (B0)
        self._teardown_audio_workers()
        if getattr(self, "_typography_popover", None) is not None:
            self._typography_popover.hide()
        if self._reader and self._reader.is_open:
            self._reader.close()
            self._reader = None

    def set_theme(self, theme: str):
        """Onda 0b (2/2): o visual da toolbar/scroll/progress bar mora agora
        na QSS central (``styles.py``, seletores ``#readerToolbar``/
        ``#reader*``), aplicada globalmente na QApplication — os widgets
        deste arquivo já herdam a folha via objectName. O que resta aqui é
        o que a QSS de widget NÃO alcança: propagação para os filhos com
        set_theme próprio, reaplicação do CSS do conteúdo do leitor (HTML/
        EPUB/DOCX, que é rich-text e não reage a QSS de widget) e o refresh
        da página atual (recalcula a renderização — ex.: PDF)."""
        self._theme = theme

        # Apply theme to TOC and AnnotationPanel
        self._toc_widget.set_theme(theme)
        if hasattr(self, "_bookmarks_panel"):
            self._bookmarks_panel.set_theme(theme)
        if hasattr(self, "_xray_panel"):
            self._xray_panel.set_theme(theme)
        self._annotation_panel.set_theme(theme)
        if hasattr(self, '_dock'):
            self._dock.set_theme(theme)
        if hasattr(self, '_insights_panel'):
            self._insights_panel.set_theme(theme)
        # search_bar e proactive_footer: 100% QSS central por objectName —
        # sem set_theme (API morta removida na auditoria da Onda 0b 2/2).

        # Apply CSS to current reader if open
        if self._reader and hasattr(self._reader, "set_theme_css"):
            self._reader.set_theme_css(self._reader_css())

        if hasattr(self, "_selection_popover"):
            self._selection_popover.set_theme(theme)
        if hasattr(self, "_word_wise_popover"):
            self._word_wise_popover.set_theme(theme)

        if self._reader and self._reader.is_open:
            self._go_to_page(self._reader.current_page)

    def _toggle_annotations(self):
        """Mostra/oculta a aba de Anotações no dock à direita."""
        if (not self._dock.isHidden()) and self._dock.current_key() == "annotations":
            self.hide_dock()
        else:
            self._show_dock_tab("annotations")

    # ── Painel Lateral recolhível (Sumário/Marcadores) — Tarefa 1.3 ─────────

    def _toggle_side_panel(self) -> None:
        """Mostra/oculta o painel lateral inteiro (self._side_panel_tabs) e
        persiste o novo estado em reader.side_panel_visible."""
        visible = self._side_panel_toggle_btn.isChecked()
        self._side_panel_tabs.setVisible(visible)
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                config.set("reader.side_panel_visible", visible)
            except Exception as exc:
                logger.warning(f"Falha ao salvar visibilidade do painel lateral (ignorado): {exc}")

    def _apply_side_panel_visibility(self) -> None:
        """Aplica reader.side_panel_visible (default True) ao painel e ao
        botão de toggle — chamado na construção e ao abrir um livro (ADR-005:
        sem config acessível, assume visível)."""
        config = getattr(self.window(), "_config", None)
        visible = True
        if config is not None:
            visible = bool(config.get("reader.side_panel_visible", True))
        self._side_panel_tabs.setVisible(visible)
        if hasattr(self, "_side_panel_toggle_btn"):
            self._side_panel_toggle_btn.setChecked(visible)

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
            self._fullscreen_btn.setIcon(emoji_icon("⬜"))
        else:
            self._toolbar.show()
            self._fullscreen_btn.setIcon(emoji_icon("⛶"))

    def _on_escape(self):
        """Escape: fecha popover → busca → limpa rubber band → sai do fullscreen → fecha leitor."""
        if getattr(self, "_typography_popover", None) is not None and self._typography_popover.isVisible():
            self._typography_popover.hide()
            return
        if hasattr(self, "_selection_popover") and self._selection_popover.isVisible():
            self._selection_popover.hide()
            return
        if hasattr(self, "_word_wise_popover") and self._word_wise_popover.isVisible():
            self._word_wise_popover.hide()
            return
        if self._search_bar.isVisible():
            self._search_bar.close_bar()
        elif self._rubber_band.isVisible() or self._selection_flow_overlay.isVisible():
            self._hide_selection_marquee()
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
            self._hide_selection_marquee()
            self._last_selection_coords = None

    # ── Tipografia do Leitor (botão "Aa") ────────────────────────────────────

    def _open_typography_popover(self) -> None:
        """Abre/fecha o popover de tipografia ancorado no botão 'Aa'."""
        if self._typography_popover is None:
            self._typography_popover = ReaderTypographyPopover(self)
            self._typography_popover.typography_changed.connect(self._on_typography_changed)
            self._typography_popover.theme_changed.connect(self._on_reader_theme_changed)
            self._typography_popover.closed.connect(
                lambda: self._typography_btn.setChecked(False))

        pop = self._typography_popover
        if pop.isVisible():
            pop.hide()
            return

        config = getattr(self.window(), "_config", None)
        if config is not None:
            pop.set_values(
                config.get("reader.font_family", DEFAULT_FONT_FAMILY),
                config.get("reader.font_size", DEFAULT_FONT_SIZE),
                config.get("reader.line_height", DEFAULT_LINE_HEIGHT),
                config.get("reader.margin_horizontal", 60),
                self._theme,
            )
        else:
            pop.set_values(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE,
                           DEFAULT_LINE_HEIGHT, 60, self._theme)

        self._typography_btn.setChecked(True)
        btn = self._typography_btn
        anchor = btn.mapToGlobal(QPoint(btn.width(), btn.height() + 4))
        pop.show_at(anchor)

    def _on_typography_changed(self, values: dict) -> None:
        """Persiste a tipografia nas chaves reader.* e re-renderiza (ao vivo)."""
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                config.set("reader.font_family", values["font_family"])
                config.set("reader.font_size", values["font_size"])
                config.set("reader.line_height", values["line_height"])
                config.set("reader.margin_horizontal", values["margin_horizontal"])
            except Exception as exc:
                logger.warning(f"Falha ao salvar tipografia (ignorado): {exc}")
        self._apply_reader_typography()

    def _apply_reader_typography(self) -> None:
        """Re-renderiza a página atual com a tipografia atual (aplicação ao vivo).

        Reusa o pipeline de renderização: ``_render_page`` regenera o CSS via
        ``_reader_css`` a partir da config. Em PDF (imagem) a tipografia não
        afeta o render; o re-render é inócuo.
        """
        if self._reader and self._reader.is_open:
            # Mesma página, só re-render tipográfico: preserva o áudio (item C).
            self._go_to_page(self._reader.current_page, preserve_audio=True)

    def _on_reader_theme_changed(self, theme: str) -> None:
        """Troca o tema do leitor a partir do popover.

        Fonte única de verdade = a chave global ``theme`` (a MESMA do diálogo de
        configurações). Propaga app-wide via ``MainWindow._apply_theme`` quando
        disponível (reader + sidebar + assistente + diálogos); senão aplica só
        ao leitor. Sem chave ``reader.theme`` duplicada.
        """
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                config.set("theme", theme)
            except Exception as exc:
                logger.warning(f"Falha ao salvar tema (ignorado): {exc}")
        win = self.window()
        if win is not None and hasattr(win, "_apply_theme"):
            win._apply_theme()
        else:
            self.set_theme(theme)

    # ── Marcadores de página (bookmarks) ─────────────────────────────────────

    def _short_excerpt(self, text: str, limit: int = 60) -> str:
        """Trecho curto de uma linha (rótulo do marcador), sem quebras."""
        if not text:
            return ""
        snippet = " ".join(text.split())
        return snippet[:limit].rstrip()

    def _toggle_current_bookmark(self) -> None:
        """Alterna o marcador da página atual e atualiza botão + painel."""
        if not self._reader or self._db is None or not self._book_id:
            # Não deixa o botão preso: reflete que não há marcador aplicável.
            if hasattr(self, "_bookmark_btn"):
                self._bookmark_btn.setChecked(False)
            return
        page = self._reader.current_page
        label = self._short_excerpt(self._current_page_text())
        try:
            state = self._db.toggle_bookmark(self._book_id, page, label)
        except Exception as exc:
            logger.warning(f"Falha ao alternar marcador (ignorado): {exc}")
            return
        self._update_bookmark_button(page)
        self._refresh_bookmarks()
        self._show_status("Página marcada." if state else "Marcador removido.", 2500)

    def _update_bookmark_button(self, page: int) -> None:
        """Sincroniza o botão 🔖 com o estado real da página (marcada ou não)."""
        if not hasattr(self, "_bookmark_btn"):
            return
        marked = False
        if self._db is not None and self._book_id:
            try:
                marked = self._db.is_bookmarked(self._book_id, page)
            except Exception:
                marked = False
        # setChecked NÃO dispara clicked → sem reentrância com o toggle.
        self._bookmark_btn.setChecked(marked)
        self._bookmark_btn.setToolTip(
            "Remover marcador da página" if marked else "Marcar página")

    def _refresh_bookmarks(self) -> None:
        """Recarrega o painel de Marcadores a partir do banco (ADR-005)."""
        if not hasattr(self, "_bookmarks_panel"):
            return
        rows = []
        if self._db is not None and self._book_id:
            try:
                rows = self._db.get_bookmarks(self._book_id)
            except Exception as exc:
                logger.warning(f"Falha ao carregar marcadores (ignorado): {exc}")
                rows = []
        self._bookmarks_panel.set_bookmarks(rows)

    def _on_bookmark_removed(self, page: int) -> None:
        """Remove o marcador da página (via botão do item no painel)."""
        if self._db is not None and self._book_id:
            try:
                self._db.remove_bookmark(self._book_id, page)
            except Exception as exc:
                logger.warning(f"Falha ao remover marcador (ignorado): {exc}")
        self._refresh_bookmarks()
        if self._reader and self._reader.current_page == page:
            self._update_bookmark_button(page)

    # ── Integração RAG Lado a Lado ───────────────────────────────────────────

    def set_ai_panel(self, ai_panel: QWidget) -> None:
        """Injeta o RAGPanel como aba 'Assistente' no dock do leitor."""
        if self._dock.has_tab("assistant"):
            return  # Já injetado

        self._ai_panel_container = ai_panel
        self._dock.add_tab("assistant", "Assistente", ai_panel, icon="💬")
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
        """Exibe o dock e seleciona a aba indicada.

        O dock é uma BARRA LATERAL direita (~1/3 da tela), não meia-tela —
        a leitura continua dominante. A proporção que o usuário ajustar no
        divisor é persistida (reader.dock_ratio) e vira o novo padrão.
        """
        self._dock.show_tab(key)
        self._dock.show()
        w = self.width()
        ratio = 0.32
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                ratio = float(config.get("reader.dock_ratio", 0.32))
            except (TypeError, ValueError):
                ratio = 0.32
        ratio = min(max(ratio, 0.15), 0.6)  # sempre sidebar, nunca dominante
        self._main_splitter.setSizes([int(w * (1 - ratio)), int(w * ratio)])
        self._sync_dock_buttons()

    def _on_dock_splitter_moved(self, _pos: int, _index: int) -> None:
        """Salva a proporção do dock escolhida pelo usuário (vira o padrão)."""
        if self._dock.isHidden():
            return
        sizes = self._main_splitter.sizes()
        total = sum(sizes)
        if total <= 0 or len(sizes) < 2 or sizes[1] <= 0:
            return
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                config.set("reader.dock_ratio", round(sizes[1] / total, 3))
            except Exception:
                pass

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
        menu.setObjectName("readerAiMenu")
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

    def _inject_epub_selection_js(self, ok: bool = True) -> None:
        """Re-injeta a fiação de captura de seleção após cada render de EPUB/HTML.

        Chamado no ``loadFinished`` do web_view (dispara só para EPUB/TXT/DOCX —
        o PDF não usa ``setHtml``). O JS é idempotente por documento (guarda
        ``__epubWW``). ADR-005: se o runJavaScript/JS falhar, o efeito é apenas
        "sem popover de seleção no EPUB", nunca um crash.
        """
        if not ok:
            return
        try:
            self._web_view.page().runJavaScript(EPUB_SELECTION_JS)
        except Exception:
            logger.debug("Falha ao injetar a fiação de seleção do EPUB", exc_info=True)

    def _on_epub_selection_ended(self, text: str, rect_json: str) -> None:
        """Fim de uma seleção no EPUB (mouseup do DOM via QWebChannel).

        Espelha o caminho PDF (``_show_selection_popover``): seleção CURTA
        (≤ ``_WORD_WISE_MAX_WORDS``) dispara o Word Wise; seleção vazia (clique
        simples) esconde o popover. Seleções LONGAS ainda NÃO abrem a barra de
        ações (SelectionActionPopover) no EPUB nesta rodada — débito registrado.
        """
        text = (text or "").strip()
        if not text:
            if hasattr(self, "_word_wise_popover"):
                self._word_wise_popover.hide()
            return
        if len(text.split()) > self._WORD_WISE_MAX_WORDS:
            return
        anchor = self._epub_selection_anchor(rect_json)
        if anchor is None:
            return
        self._last_selection_anchor = anchor
        self._start_word_wise(text)

    def _epub_selection_anchor(self, rect_json: str):
        """Converte o retângulo da seleção (coords CSS do viewport) em um ponto
        em coordenadas do ReaderView, ou ``None`` se inválido/fora da vista.

        O ``getBoundingClientRect`` do JS já é relativo ao viewport (acompanha o
        scroll); o ``zoomFactor`` do QWebEngineView escala o conteúdo composto no
        widget, então coord_widget = css * zoomFactor (validado no spike B3).
        ADR-005: qualquer falha de parsing/seleção fora da área ⇒ ``None``.
        """
        if not rect_json:
            return None
        try:
            r = json.loads(rect_json)
            zoom = self._web_view.zoomFactor()
            x = float(r.get("x", 0.0)) * zoom
            bottom = float(r.get("bottom", r.get("y", 0.0))) * zoom
        except Exception:
            return None
        view = self._web_view
        # Seleção rolada para fora da área visível: não ancora um popover solto.
        if bottom < 0 or bottom > view.height() or x < 0 or x > view.width():
            return None
        return view.mapTo(self, QPoint(int(x), int(bottom) + 6))

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
            self._hide_selection_marquee()
            return

        # Esconde rubber band antes de abrir o menu
        self._hide_selection_marquee()
        
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

            text = self._selection_text(coords)

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

    def _selection_text(self, coords: tuple[float, float, float, float]) -> str:
        """Texto da seleção atual: fluxo de texto quando disponível, senão rect.

        O fluxo (get_selection_flow) respeita frases que começam/terminam no
        meio da linha; o rect legado captura pedaços de linhas vizinhas.
        """
        flow = getattr(self, "_last_selection_flow", None)
        if flow and flow.get("text"):
            return flow["text"].strip()
        text = ""
        if self._reader and hasattr(self._reader, "get_text_from_rect"):
            try:
                text = (self._reader.get_text_from_rect(self._reader.current_page, coords) or "").strip()
            except Exception:
                text = ""
        return text

    def _highlight_selection(self, coords: tuple[float, float, float, float], text: str):
        """Salva o destaque no banco de dados e limpa a rubber band."""
        import json
        payload = {"coords": list(coords)}
        # Seleção por fluxo: grava um rect por LINHA (quads) e o bounding box
        # em coords (compatibilidade + hit-test do "Remover Destaque").
        flow = getattr(self, "_last_selection_flow", None)
        if flow and flow.get("quads"):
            qs = flow["quads"]
            payload["coords"] = [min(q[0] for q in qs), min(q[1] for q in qs),
                                 max(q[2] for q in qs), max(q[3] for q in qs)]
            payload["quads"] = qs
        position_data = json.dumps(payload)

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
        self._hide_selection_marquee()

    def _show_selection_popover(self, rect) -> None:
        """Exibe o popover de ações logo abaixo da seleção (PDF)."""
        if not hasattr(self, "_selection_popover"):
            return
        actions = ["highlight", "explain", "translate", "search", "save_note", "flashcard"]
        # Word Wise (3.4): só para seleção curta (palavra/termo) — seleções
        # maiores continuam pelo fluxo normal (Explicar/RAG).
        coords = self._last_selection_coords
        text = self._selection_text(coords) if coords else ""
        if text and len(text.split()) <= self._WORD_WISE_MAX_WORDS:
            actions.append("word_wise")
        self._selection_popover.set_actions(actions)
        # rect está em coordenadas do _image_label (pai da rubber band); mapeia p/ ReaderView.
        anchor_local = QPoint(rect.left(), rect.bottom() + 6)
        anchor = self._image_label.mapTo(self, anchor_local)
        self._last_selection_anchor = anchor
        self._selection_popover.show_at(anchor)

    def _on_selection_popover_action(self, action: str) -> None:
        """Executa a ação escolhida no popover de seleção (PDF)."""
        coords = self._last_selection_coords
        if coords is None:
            return
        text = self._selection_text(coords)
        if action == "highlight":
            self._highlight_selection(coords, text)
        elif action == "word_wise":
            if text:
                self._start_word_wise(text)
        elif text:
            self.ai_action_requested.emit(action, text)
        self._last_selection_coords = None
        self._hide_selection_marquee()

    def _start_word_wise(self, term: str) -> None:
        """Dispara a definição rápida (Word Wise, 3.4) para o termo selecionado.

        Mostra o popover em estado de carregamento imediatamente, perto da
        seleção, e o LLM (``think=False``, worker em background) substitui
        pelo texto da definição ao terminar. NUNCA abre o painel do RAG —
        essa é a diferença chave em relação às outras ações de seleção.
        """
        worker = getattr(self, "_word_wise_worker", None)
        if worker is not None and worker.isRunning():
            return

        anchor = getattr(self, "_last_selection_anchor", None)
        if anchor is None:
            return
        self._word_wise_popover.show_loading(term, anchor)

        # Contexto: texto da página atual, para desambiguar o termo.
        context = ""
        if self._reader:
            page = self._reader.current_page
            if hasattr(self._reader, "get_page_text"):
                context = self._reader.get_page_text(page) or ""
            elif hasattr(self._reader, "get_chapter_text"):
                context = self._reader.get_chapter_text(page) or ""

        config = getattr(self.window(), "_config", None)
        ollama_url = (config.get("rag.ollama_url", "http://localhost:11434")
                     if config else "http://localhost:11434")

        from src.gui.workers.word_wise_worker import WordWiseWorker
        self._word_wise_worker = WordWiseWorker(
            term, context=context, ollama_url=ollama_url, parent=self)
        self._word_wise_worker.definition_ready.connect(self._on_word_wise_ready)
        self._word_wise_worker.failed.connect(self._on_word_wise_failed)
        self._word_wise_worker.start()

    def _on_word_wise_ready(self, term: str, definition: str) -> None:
        if self._word_wise_popover.isVisible():
            self._word_wise_popover.show_definition(term, definition)

    def _on_word_wise_failed(self, _reason: str) -> None:
        if self._word_wise_popover.isVisible():
            self._word_wise_popover.show_error()

    def is_narrating(self) -> bool:
        """Indica se há narração TTS em andamento (worker de áudio rodando).

        Encapsula o atributo privado ``_audio_worker`` para uso por serviços
        externos (ex.: AutoIndexService, via MainWindow) sem acoplá-los à
        implementação interna do player de áudio — o worker é recriado a
        cada nova narração (ver ``_launch_audio_worker``), então este método
        sempre reflete o estado atual, não uma referência potencialmente
        obsoleta.
        """
        worker = getattr(self, "_audio_worker", None)
        return bool(worker and worker.isRunning())

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

        if self._continuous_translate_mode and not self._listen_original_override:
            # Modo traduzido: cada página passa pelo NLLB (via MainWindow)
            # antes de narrar; a cadeia continua em _on_audio_finished igual
            # ao modo normal (chain_continuous é setado por narrate_text lá).
            # Exceção (achado B0): com o override "Ouvir original" ativo, a
            # cadeia SEGUE no original — pula a tradução e narra o texto cru.
            self._begin_translation_feedback()  # item E: feedback imediato
            self.ai_action_requested.emit("read_translated_page_chained", page_text)
            return

        self._launch_audio_worker(page_text, chain_continuous=True)

    def _launch_audio_worker(self, text: str, chain_continuous: bool = False,
                             language: str | None = None) -> None:
        """Cria, conecta e inicia o AudioWorker para o texto dado (TTS).

        ``chain_continuous``: só narração de PÁGINA encadeia a próxima no modo
        contínuo (uma tradução narrada via narrate_text não vira página).
        ``language``: idioma-alvo EXPLÍCITO (ex.: o alvo real de uma tradução).
        Quando dado, o worker o repassa ao roteador em vez de autodetectar —
        evita que uma tradução PT com termos técnicos EN seja lida com voz
        inglesa. ``None`` mantém a autodetecção confiante do worker.
        """
        self._audio_stopped_by_user = False
        self._chain_continuous = chain_continuous
        self.narration_epoch += 1

        def _do_launch() -> None:
            from src.gui.workers.audio_worker import AudioWorker
            from src.core.tts.voice_profile import NarrationRole
            worker = AudioWorker(
                text,
                role=NarrationRole.BOOK_NARRATOR,
                router=self._tts_router,
                language=language,
                parent=self,
            )
            self._connect_audio_worker(worker)
            self._audio_worker = worker
            worker.start()

        # Serializa o INÍCIO da nova narração se um worker antigo ainda drena
        # (o TTSRouter compartilhado não tolera dois speak() simultâneos).
        self._start_or_defer_narration(_do_launch)

    def narrate_text(self, text: str, chain_continuous: bool = False,
                     language: str | None = None) -> None:
        """Narra um texto arbitrário (ex.: uma tradução) via TTS.

        ``language``: idioma-alvo EXPLÍCITO do texto (ex.: o idioma para o qual
        se traduziu). Quando informado, é usado para escolher a voz em vez da
        autodetecção — essencial para traduções PT salpicadas de termos EN, que
        a detecção poderia classificar como inglês. ``None`` → o AudioWorker
        autodetecta de forma confiante (texto ambíguo → voz do perfil).

        ``chain_continuous``: True quando esta narração faz parte da leitura
        contínua traduzida — ao terminar, encadeia a próxima página (ver
        _on_audio_finished). Por padrão False (uma tradução avulsa não vira
        página sozinha).
        """
        if not text or not text.strip():
            return
        self._stop_audio_if_running()
        self._launch_audio_worker(text.strip(), chain_continuous=chain_continuous,
                                  language=language)

    def _set_audio_button_state(self, label: str, icon_emoji: str, tooltip: str,
                                 *, menu_label: str | None = None) -> None:
        """Atualiza em conjunto o botão único de áudio E o item "Ouvir página"
        do seu menu (Tarefa 1.4 — um só QToolButton+QMenu substitui os 3
        controles antigos, então toda transição de estado precisa refletir
        nos dois lugares). O botão usa emoji_icon (padrão de botão); o item de
        menu embute o emoji no texto (padrão dos demais QAction do arquivo).
        """
        self._audio_btn.setText(label)
        self._audio_btn.setIcon(emoji_icon(icon_emoji))
        self._audio_btn.setToolTip(tooltip)
        self._act_audio_toggle.setText(f"{icon_emoji} {menu_label or label}")

    def _pause_audio(self):
        """Pausa a narração (retomável no mesmo ponto)."""
        worker = getattr(self, "_audio_worker", None)
        if worker and worker.isRunning():
            worker.pause()
            self._audio_paused = True
            self._set_audio_button_state("Retomar", "▶️", "Continuar Leitura (TTS)")

    def _resume_audio(self):
        """Retoma a narração pausada a partir do ponto exato."""
        worker = getattr(self, "_audio_worker", None)
        if worker and worker.isRunning():
            worker.resume()
            self._audio_paused = False
            self._set_audio_button_state("Pausar", "⏸️", "Pausar Leitura (TTS)")

    def _begin_translation_feedback(self) -> None:
        """Feedback imediato ao acionar a narração TRADUZIDA (item E).

        O NLLB leva um tempo antes de o áudio começar; sem isto o botão "Ouvir"
        parece inerte. Mostra "Traduzindo…" no próprio botão e na statusbar
        assim que o usuário aciona. O estado é limpo quando o áudio começa
        (_on_audio_started), quando falha (_on_audio_error) ou quando a tradução
        termina sem gerar áudio (watchdog _poll_translation_feedback).
        """
        self._translating_for_audio = True
        self._set_audio_button_state(
            "Traduzindo…", "🌐", "Traduzindo a página para leitura…",
            menu_label="Traduzindo página…")
        self._show_status("🌐 Iniciando tradução para leitura…", 4000)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(600, self._poll_translation_feedback)

    def _poll_translation_feedback(self) -> None:
        """Restaura o botão se a tradução terminar SEM iniciar áudio (falha/vazia).

        Sucesso e "já em português" viram áudio → _on_audio_started limpa o
        estado. Aqui cobrimos só o caso em que nenhum áudio começa: enquanto o
        MainWindow sinaliza tradução pendente, reagenda; quando o flag baixa
        sem worker de áudio ativo, devolve o botão para "Ouvir".
        """
        if not getattr(self, "_translating_for_audio", False):
            return
        worker = getattr(self, "_audio_worker", None)
        if worker is not None and worker.isRunning():
            self._translating_for_audio = False  # áudio começou; _on_audio_started cuida do botão
            return
        if getattr(self.window(), "_page_translation_pending", False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(600, self._poll_translation_feedback)
            return
        self._translating_for_audio = False
        self._set_audio_button_state("Ouvir", "🔊", "Ouvir Página (TTS)", menu_label="Ouvir página")

    def _on_audio_started(self):
        self._audio_paused = False
        self._translating_for_audio = False  # item E: áudio começou → limpa "Traduzindo…"
        self._set_audio_button_state("Pausar", "⏸️", "Pausar Leitura (TTS)")
        self._act_audio_stop.setEnabled(True)
        # Rodada 3: o áudio começou de fato — avisa quem precise ceder recursos
        # (o MainWindow cancela a auto-indexação em ocioso em andamento). Este é
        # o ÚNICO ponto em que a reprodução realmente inicia, tanto no caminho
        # normal (_launch_audio_worker) quanto no da pré-síntese (_play_prepared):
        # ambos conectam playback_started → _on_audio_started, então um só emit
        # cobre os dois.
        self.narration_started.emit()
        # Tarefa 3.6: enquanto esta página toca, sintetiza a próxima em background.
        self._maybe_presynthesize_next()

    def _on_listen_original(self):
        """Narra a página ATUAL no idioma original, sem mexer nos toggles.

        Par explícito "Ouvir original / Ouvir traduzido": com a Leitura
        Contínua Traduzida ligada, o corpo do botão Ouvir narra a tradução —
        este item dá acesso direto ao original DESTA página. A continuidade
        segue os toggles: com um modo contínuo ligado, a cadeia retoma na
        próxima página conforme a preferência (por isso chain_continuous=True;
        com os toggles desligados, nada encadeia). Sem ``language`` explícito,
        o AudioWorker autodetecta (EN → voz EN; misto → voz por sentença).
        """
        if not self._reader:
            return
        page_text = self._current_page_text().strip()
        if not page_text:
            self._show_status("⚠️ Página sem texto para narrar.", 4000)
            return
        # Achado B0: "Ouvir original" liga o override de sessão — a cadeia (se
        # houver um modo contínuo ligado) segue no ORIGINAL até o usuário parar,
        # em vez do one-shot antigo. Harmless quando não há modo contínuo ou
        # quando a Leitura Contínua Traduzida está desligada.
        self._listen_original_override = True
        self.narrate_text(page_text, chain_continuous=True)

    def _on_read_translated_page(self):
        """Narra a página atual traduzida para PT (item 7 do backlog UX).

        O texto vai para o MainWindow (ai_action_requested), que orquestra a
        tradução NLLB em background e devolve via narrate_text.
        """
        if not self._reader:
            return
        page = self._reader.current_page
        page_text = ""
        if hasattr(self._reader, "get_page_text"):
            page_text = self._reader.get_page_text(page)
        elif hasattr(self._reader, "get_chapter_text"):
            page_text = self._reader.get_chapter_text(page)
        page_text = (page_text or "").strip()
        if not page_text:
            self._show_status("⚠️ Página sem texto para traduzir/narrar.", 4000)
            return
        # Pedido explícito de tradução limpa o override "Ouvir original" (B0).
        self._listen_original_override = False
        self._begin_translation_feedback()  # item E: feedback imediato
        self.ai_action_requested.emit("read_translated_page", page_text)

    def _on_translate_page(self):
        """Traduz a página atual como TEXTO — cartão no painel, sem narrar."""
        if not self._reader:
            return
        page_text = ""
        if hasattr(self._reader, "get_page_text"):
            page_text = self._reader.get_page_text(self._reader.current_page)
        elif hasattr(self._reader, "get_chapter_text"):
            page_text = self._reader.get_chapter_text(self._reader.current_page)
        page_text = (page_text or "").strip()
        if not page_text:
            self._show_status("⚠️ Página sem texto para traduzir.", 4000)
            return
        self.ai_action_requested.emit("translate_page", page_text)

    def _toggle_continuous_reading(self, checked: bool):
        """Liga/desliga a leitura contínua (persiste na config)."""
        self._continuous_reading = bool(checked)
        if not self._continuous_reading:
            self._invalidate_presynth()  # desligou → descarta pré-síntese (3.6)
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                config.set("tts.continuous_reading", self._continuous_reading)
            except Exception:
                pass
        self._show_status(
            "🔁 Leitura contínua ativada — a narração vira as páginas." if checked
            else "Leitura contínua desativada.", 4000)

    def _toggle_continuous_translate_reading(self, checked: bool):
        """Liga/desliga a leitura contínua TRADUZIDA (persiste na config)."""
        self._continuous_translate_mode = bool(checked)
        # Mudar o toggle é uma decisão explícita de modo → limpa o override
        # "Ouvir original" (achado B0), em qualquer direção.
        self._listen_original_override = False
        if self._continuous_translate_mode:
            # Áudio pré-sintetizado é do idioma ORIGINAL — inválido p/ tradução.
            self._invalidate_presynth()
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                config.set("tts.continuous_translate_reading", self._continuous_translate_mode)
            except Exception:
                pass
        self._show_status(
            "🌐🔁 Leitura contínua traduzida ativada — cada página é traduzida antes de narrar."
            if checked else "Leitura contínua traduzida desativada.", 4000)

    def _show_status(self, msg: str, ms: int = 4000):
        parent_window = self.window()
        if parent_window and hasattr(parent_window, "_statusbar") and parent_window._statusbar:
            parent_window._statusbar.showMessage(msg, ms)

    def _on_audio_finished(self, chunks):
        """Fim natural da narração: no modo contínuo, encadeia a próxima página.

        Cobre os dois modos (normal e traduzido) — sem o "or", o modo
        traduzido não encadearia quando a leitura contínua normal está
        desligada (são toggles independentes).
        """
        if not ((self._continuous_reading or self._continuous_translate_mode)
                and self._chain_continuous):
            return
        if self._audio_stopped_by_user or not self._reader:
            return
        # Pequena pausa entre páginas; singleShot também deixa o QThread do
        # worker atual terminar antes de criarmos o próximo.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(400, self._continue_narration)

    def _continue_narration(self):
        """Avança para a próxima página com texto e narra (modo contínuo).

        Cobre os DOIS modos contínuos (normal e traduzido, toggles
        independentes); no traduzido, o _toggle_audio do fim re-forka a
        página nova para o caminho de tradução.

        Tarefa 3.6: se a próxima página já foi pré-sintetizada, TOCA o áudio
        pronto (sem gap de síntese); senão, cai no caminho normal (síntese).
        A pré-síntese guarda áudio do idioma ORIGINAL, então só vale para o
        modo contínuo normal — no traduzido ela é ignorada.
        """
        from src.core.audio.continuous_navigation import next_readable_page_with_text

        if not (self._continuous_reading or self._continuous_translate_mode):
            return
        if not self._reader:
            return
        worker = getattr(self, "_audio_worker", None)
        if worker and worker.isRunning():
            return  # algo já narra (ex.: usuário deu play manual no meio)
        if self._audio_stopped_by_user:
            return
        get_text = (getattr(self._reader, "get_page_text", None)
                    or getattr(self._reader, "get_chapter_text", None))
        if get_text is None:
            return
        nxt = next_readable_page_with_text(
            get_text, self._reader.current_page, self._reader.total_pages)
        if nxt is None:
            self._show_status("🔁 Fim do livro — leitura contínua encerrada.", 5000)
            return
        next_page, _next_text = nxt
        # Pega o áudio pré-sintetizado ANTES de _go_to_page (que invalida o
        # cache ao parar o áudio atual). Chave = livro + página + voz.
        # No modo traduzido o cache é ignorado: ele contém áudio do idioma
        # ORIGINAL (a pré-síntese é exclusiva do modo normal) e tocá-lo
        # narraria a página sem tradução.
        prepared = None
        if not self._continuous_translate_mode:
            prepared = self._presynth_cache.take(self._presynth_key(next_page))
        self._go_to_page(next_page)
        if prepared:
            self._play_prepared(prepared)
        else:
            self._toggle_audio()

    # ── Pré-síntese TTS da próxima página (tarefa 3.6) ────────────────

    def _voice_signature(self) -> str:
        """Assinatura da voz/velocidade atual — parte da chave do cache.

        Muda de voz/velocidade → chave diferente → o áudio antigo não é
        reaproveitado (invalidação implícita).
        """
        config = getattr(self.window(), "_config", None)
        if config is None:
            return "default"
        try:
            prof = config.tts_config.get("book_narrator", {}) or {}
            return (f"{prof.get('preferred_provider', '')}:"
                    f"{prof.get('voice_id', '')}:{prof.get('rate', '')}")
        except Exception:
            return "default"

    def _presynth_key(self, page: int):
        return (self._book_id, page, self._voice_signature())

    def _maybe_presynthesize_next(self) -> None:
        """Dispara a síntese em background da PRÓXIMA página (no máx. 1 à frente).

        Só na leitura contínua normal (o modo traduzido passa cada página pelo
        NLLB antes de narrar — o texto cru não bate com a narração). ADR-006: o
        threading fica aqui, na GUI; a decisão de "qual é o próximo texto" e o
        cache são núcleo puro.
        """
        if not self._continuous_reading or self._continuous_translate_mode:
            return
        if self._tts_router is None or not self._reader:
            return
        if self._audio_stopped_by_user:
            return
        if self._presynth_cache.pending_key is not None:
            return  # já há uma página pronta à frente
        worker = getattr(self, "_presynth_worker", None)
        if worker is not None and worker.isRunning():
            return
        get_text = (getattr(self._reader, "get_page_text", None)
                    or getattr(self._reader, "get_chapter_text", None))
        if get_text is None:
            return
        from src.core.audio.continuous_navigation import next_readable_page_with_text
        nxt = next_readable_page_with_text(
            get_text, self._reader.current_page, self._reader.total_pages)
        if nxt is None:
            return
        next_page, next_text = nxt
        try:
            from src.gui.workers.audio_worker import PreSynthesisWorker
            from src.core.tts.voice_profile import NarrationRole
            self._presynth_worker = PreSynthesisWorker(
                text=next_text,
                key=self._presynth_key(next_page),
                cache=self._presynth_cache,
                router=self._tts_router,
                role=NarrationRole.BOOK_NARRATOR,
                parent=self,
            )
            self._presynth_worker.ready.connect(self._on_presynth_ready)
            self._presynth_worker.start()
        except Exception:
            self._presynth_worker = None

    def _on_presynth_ready(self, key):
        """Pré-síntese concluída: os segmentos já estão no cache (nada a fazer)."""
        pass

    def _invalidate_presynth(self) -> None:
        """Descarta a pré-síntese obsoleta (nav. manual / stop / troca de livro)."""
        worker = getattr(self, "_presynth_worker", None)
        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                pass
        cache = getattr(self, "_presynth_cache", None)
        if cache is not None:
            cache.invalidate()

    def _play_prepared(self, segments) -> None:
        """Toca áudio JÁ sintetizado da próxima página (AudioWorker em prepared)."""
        self._audio_stopped_by_user = False
        self._chain_continuous = True
        self.narration_epoch += 1

        def _do_launch() -> None:
            from src.gui.workers.audio_worker import AudioWorker
            from src.core.tts.voice_profile import NarrationRole
            worker = AudioWorker(
                "",
                role=NarrationRole.BOOK_NARRATOR,
                router=self._tts_router,
                prepared=segments,
                parent=self,
            )
            self._connect_audio_worker(worker)
            self._audio_worker = worker
            worker.start()

        self._start_or_defer_narration(_do_launch)

    def _on_audio_error(self, err_msg):
        # item E: se falhou antes de tocar (ex.: durante "Traduzindo…"), não
        # deixa o botão preso nesse estado.
        self._translating_for_audio = False
        self._show_status(f"Erro de Áudio: {err_msg}", 5000)
        worker = getattr(self, "_audio_worker", None)
        if not (worker is not None and worker.isRunning()):
            self._set_audio_button_state("Ouvir", "🔊", "Ouvir Página (TTS)", menu_label="Ouvir página")

    def _on_audio_worker_finished(self):
        """Garante a limpeza de referências e restaura o estado visual do botão."""
        # Modo contínuo: o QThread antigo pode terminar DEPOIS de o próximo
        # worker já ter sido criado — só limpa a UI se este é o worker atual.
        finished_worker = self.sender()
        if finished_worker is not None and finished_worker is not getattr(self, "_audio_worker", None):
            finished_worker.deleteLater()
            return
        self._audio_paused = False
        self._set_audio_button_state("Ouvir", "🔊", "Ouvir Página (TTS)", menu_label="Ouvir página")
        if hasattr(self, "_act_audio_stop"):
            self._act_audio_stop.setEnabled(False)
        if hasattr(self, "_audio_worker") and self._audio_worker:
            self._audio_worker.deleteLater()
            self._audio_worker = None

    def _on_audio_stop_clicked(self):
        """Stop MANUAL da narração (botão ⏹️ Parar — ação explícita do usuário).

        Achado B0: limpa o override "Ouvir original" (a leitura em original só
        segue "até o usuário parar") e então executa a parada assíncrona normal.
        Distinto de ``_stop_audio_if_running`` cru, que também é chamado em
        transições internas (virar página na cadeia, ``narrate_text``) e por
        isso NÃO pode limpar o override — senão a própria virada de página da
        cadeia o apagaria.
        """
        self._listen_original_override = False
        self._stop_audio_if_running()

    def _stop_audio_if_running(self):
        """Para a narração SEM bloquear a GUI (perf/gui): drenagem assíncrona.

        Antes chamava ``wait(2000)``, congelando a GUI ao virar página durante a
        narração e ao trocar de narração ("Ouvir original"). Agora o worker é
        apenas SINALIZADO para parar (stop cooperativo) e movido para
        ``_retiring_workers``; sua referência só é solta quando o ``finished``
        REAL chega (``_on_retiring_worker_finished``) — nunca destruímos um
        QThread cuja thread do SO ainda vive (lição do PR #32/SIGABRT). Para
        teardown (fechar leitor) use ``_teardown_audio_workers``, onde um wait
        bloqueante é aceitável (é encerramento, não interação).
        """
        self._audio_stopped_by_user = True
        self._invalidate_presynth()  # stop/troca de página descarta pré-síntese (3.6)
        # Parar é decisão explícita: cancela qualquer narração ENFILEIRADA.
        self._pending_narration = None
        self._cancel_pending_safety_timer()
        self._retire_current_audio_worker()
        self._audio_paused = False
        self._set_audio_button_state("Ouvir", "🔊", "Ouvir Página (TTS)", menu_label="Ouvir página")
        if hasattr(self, "_act_audio_stop"):
            self._act_audio_stop.setEnabled(False)

    def _audio_worker_signal_pairs(self, worker) -> tuple:
        """Fonte ÚNICA (auditoria A6) dos pares (sinal, handler) do AudioWorker.

        O connect (``_connect_audio_worker``) e o disconnect
        (``_disconnect_audio_worker_signals``, usado por retire e teardown)
        derivam desta lista — a manutenção fica num lugar só.
        """
        return (
            (worker.playback_started, self._on_audio_started),
            (worker.playback_finished, self._on_audio_finished),
            (worker.error_occurred, self._on_audio_error),
            (worker.finished, self._on_audio_worker_finished),
            (worker.provider_changed, self._on_audio_provider_changed),
        )

    def _connect_audio_worker(self, worker) -> None:
        """Conecta os sinais do AudioWorker aos handlers da GUI.

        DRY entre ``_launch_audio_worker`` e ``_play_prepared`` — ambos criam um
        AudioWorker e ligam os MESMOS cinco sinais.
        """
        for sig, slot in self._audio_worker_signal_pairs(worker):
            sig.connect(slot)

    def _disconnect_audio_worker_signals(self, worker) -> None:
        """Desconecta TODOS os sinais do worker (retire/teardown, fonte A6)."""
        for sig, _slot in self._audio_worker_signal_pairs(worker):
            try:
                sig.disconnect()
            except (TypeError, RuntimeError):
                # TypeError: sinal já sem conexões (fluxo normal do retire);
                # RuntimeError: objeto C++ já destruído. Ambos benignos aqui.
                pass

    def _retire_current_audio_worker(self) -> None:
        """Sinaliza o worker atual para parar e o move para a aposentadoria.

        NÃO bloqueia (sem ``wait``). Desconecta os sinais de callback que não
        devem mais agir na UI (``playback_*``, ``error``, ``provider`` —
        senão a narração antiga encadearia página ou mexeria no botão depois de
        substituída) e reconecta ``finished`` a ``_on_retiring_worker_finished``,
        que só solta/deleteLater quando a thread do SO realmente terminou.

        Corrida coberta (auditoria A2): se ``run()`` retornar entre o
        ``isRunning()`` e o ``finished.connect``, o sinal é emitido SEM
        receptor e o worker ficaria preso em ``_retiring_workers`` — por isso
        o re-check após o connect chama o handler diretamente (idempotente).
        """
        worker = getattr(self, "_audio_worker", None)
        self._audio_worker = None
        if worker is None:
            return
        self._disconnect_audio_worker_signals(worker)
        if not worker.isRunning():
            worker.deleteLater()
            return
        self._retiring_workers.append(worker)
        # Conecta ANTES do stop(): o `finished` é queued para a thread da GUI.
        worker.finished.connect(lambda w=worker: self._on_retiring_worker_finished(w))
        try:
            worker.stop()  # cooperativo: sinaliza cancelamento e para player/router
        except Exception:
            logger.warning("Falha ao sinalizar stop ao worker de áudio aposentado",
                           exc_info=True)
        # A2: run() pode ter retornado entre o isRunning() lá em cima e o
        # connect — o finished já teria sido emitido sem receptor. Re-checa e
        # trata direto; se o sinal também chegar depois, a segunda chamada do
        # handler idempotente é no-op.
        if not worker.isRunning():
            self._on_retiring_worker_finished(worker)

    def _on_retiring_worker_finished(self, worker) -> None:
        """A thread do SO do worker aposentado terminou de fato → solta e destrói.

        IDEMPOTENTE (auditoria A2): pode ser chamado pelo ``finished`` queued E
        diretamente pelo re-check do retire/watchdog — a segunda chamada
        encontra o worker fora da lista e retorna. Quando o ÚLTIMO worker em
        drenagem sai, dispara a narração ENFILEIRADA (se houver): garante que
        só UM ``speak()`` use o TTSRouter compartilhado por vez.
        """
        if worker not in self._retiring_workers:
            return  # já tratado (corrida connect × finished)
        self._retiring_workers.remove(worker)
        try:
            worker.deleteLater()
        except RuntimeError:
            # Objeto C++ já destruído (ex.: janela fechando) — nada a liberar.
            logger.debug("deleteLater em worker de áudio já destruído", exc_info=True)
        if not self._retiring_workers and self._pending_narration is not None:
            self._run_pending_narration()

    def _start_or_defer_narration(self, launch_fn) -> None:
        """Inicia a narração agora, ou a ENFILEIRA se um worker antigo drena.

        O TTSRouter é COMPARTILHADO e seu estado interno
        (``_is_cancelled``/``_active_player``/``_active_provider``) não tolera
        dois ``speak()`` concorrentes. Enquanto houver worker em
        ``_retiring_workers``, guardamos o lançamento (o último pedido vence) e
        o disparamos no ``finished`` REAL do último (ver
        ``_on_retiring_worker_finished``), com um QTimer de segurança para nunca
        travar o recurso — jamais um ``wait()`` bloqueante na thread da GUI.
        """
        if self._retiring_workers:
            self._pending_narration = launch_fn
            self._arm_pending_safety_timer()
        else:
            launch_fn()

    def _arm_pending_safety_timer(self) -> None:
        """(Re)arma o watchdog da narração pendente (degradação graciosa).

        O período de 2,5s NÃO é um acoplamento ao join interno de 1s do
        router (auditoria A3): o timeout nunca lança nada com worker antigo
        vivo — apenas purga terminados, re-emite o stop e re-arma. O valor é
        só a cadência de polling da drenagem.
        """
        from PyQt6.QtCore import QTimer
        self._cancel_pending_safety_timer()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_pending_safety_timeout)
        timer.start(2500)
        self._pending_narration_timer = timer

    def _cancel_pending_safety_timer(self) -> None:
        timer = getattr(self, "_pending_narration_timer", None)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                # Objeto C++ do timer já destruído (janela fechando) — benigno.
                logger.debug("Watchdog de narração já destruído ao cancelar",
                             exc_info=True)
            self._pending_narration_timer = None

    def _on_pending_safety_timeout(self) -> None:
        """Watchdog do lançamento adiado (auditoria A3): NUNCA lança um
        ``speak()`` com worker antigo VIVO — o TTSRouter compartilhado não
        tolera dois ``speak()`` concorrentes (o novo resetaria o cancel do
        antigo e clobberaria ``_active_player``; o Parar deixaria de silenciar
        o áudio velho). No timeout: (i) purga da lista os workers já
        terminados (handler idempotente — se esvaziar, ele mesmo dispara o
        pending); (ii) lista vazia → roda o pending; (iii) senão, re-emite o
        ``stop()`` (idempotente) e RE-ARMA o timer, avisando na statusbar.
        """
        self._pending_narration_timer = None
        for w in list(self._retiring_workers):
            try:
                alive = w.isRunning()
            except RuntimeError:
                alive = False  # objeto C++ já destruído — não há thread viva
            if not alive:
                self._on_retiring_worker_finished(w)
        if not self._retiring_workers:
            if self._pending_narration is not None:
                self._run_pending_narration()
            return
        for w in self._retiring_workers:
            try:
                w.stop()
            except Exception:
                logger.warning("Watchdog: falha ao re-sinalizar stop ao worker",
                               exc_info=True)
        self._show_status("⏳ Aguardando a narração anterior encerrar…", 2500)
        self._arm_pending_safety_timer()

    def _run_pending_narration(self) -> None:
        """Dispara o lançamento adiado (se ainda válido)."""
        fn = self._pending_narration
        self._pending_narration = None
        self._cancel_pending_safety_timer()
        if fn is None:
            return
        # O usuário parou de vez nesse meio-tempo → não ressuscita a narração.
        if self._audio_stopped_by_user:
            return
        worker = getattr(self, "_audio_worker", None)
        if worker is not None and worker.isRunning():
            return  # já há algo tocando; não empilha um segundo player
        fn()

    def _teardown_audio_workers(self) -> None:
        """Teardown (fechar leitor / fechar app): garante que NENHUM worker de
        áudio sobreviva. Aqui um ``wait`` BLOQUEANTE é aceitável — é
        encerramento, não interação (a lição do PR #32 é esperar a thread do SO
        antes de destruir). Silencia os sinais de cada worker antes do wait para
        que nenhum callback re-dispare narração durante o teardown.
        """
        self._audio_stopped_by_user = True
        self._pending_narration = None
        self._cancel_pending_safety_timer()
        self._invalidate_presynth()
        worker = getattr(self, "_audio_worker", None)
        self._audio_worker = None
        workers = list(getattr(self, "_retiring_workers", []))
        self._retiring_workers = []
        if worker is not None:
            workers.append(worker)
        for w in workers:
            self._disconnect_audio_worker_signals(w)
            try:
                if w.isRunning():
                    w.stop()
                    w.wait(2000)
            except Exception:
                logger.warning("Teardown: falha ao parar/esperar worker de áudio",
                               exc_info=True)
            try:
                still_running = w.isRunning()
            except RuntimeError:
                still_running = False  # objeto C++ já destruído — nada vivo
            if still_running:
                # Auditoria A4: o wait(2000) EXPIROU com a thread do SO ainda
                # viva — deleteLater aqui é exatamente a classe do SIGABRT do
                # PR #32. Vazamento CONSCIENTE no teardown: solta a referência
                # sem destruir (o SO encerra a thread junto com o processo).
                logger.warning(
                    "Teardown: worker de áudio não encerrou em 2s; referência "
                    "abandonada sem deleteLater (vazamento consciente).")
                continue
            try:
                w.deleteLater()
            except RuntimeError:
                # Objeto C++ já destruído — nada a liberar.
                logger.debug("Teardown: worker já destruído no deleteLater",
                             exc_info=True)
        self._audio_paused = False

    def _on_audio_provider_changed(self, provider_name: str):
        """Item 4 (transparência do motor): mostra qual engine TTS está ativo.

        ``provider_changed`` é emitido pelo AudioWorker ao iniciar a fala (e ao
        final). Se o engine ativo difere do preferido, sinaliza "reserva" tanto
        no tooltip do botão quanto no sufixo do item "Pausar" do menu — assim o
        usuário entende por que uma voz do motor preferido pode não se aplicar.
        """
        pretty = provider_name if provider_name and provider_name != "none" else ""
        if self._audio_paused or not pretty:
            return
        preferred = ""
        config = getattr(self.window(), "_config", None)
        if config is not None:
            try:
                preferred = config.get("tts.book_narrator.preferred_provider", "kokoro") or ""
            except Exception:
                preferred = ""
        is_fallback = bool(preferred) and pretty.lower() != preferred.lower()
        if is_fallback:
            self._audio_btn.setToolTip(f"Narrando via {pretty} (motor reserva)")
            self._act_audio_toggle.setText(f"⏸️ Pausar página · {pretty} (reserva)")
        else:
            self._audio_btn.setToolTip(f"Pausar Leitura · narrando via {pretty}")
            self._act_audio_toggle.setText(f"⏸️ Pausar página · {pretty}")

    def _on_voice_selected(self, voice_id):
        """Grava a voz escolhida e, se houver narração ATIVA, aplica-a já (item 4).

        Sem narração em curso, apenas persiste — a voz nova vale na próxima
        leitura. Com narração ativa, reinicia a página atual com a voz nova
        (ver _restart_current_page_narration).
        """
        config = getattr(self.window(), "_config", None)
        if config is not None:
            config.set("tts.book_narrator.voice_id", voice_id)
        worker = getattr(self, "_audio_worker", None)
        if worker is not None and worker.isRunning():
            self._restart_current_page_narration()

    def _restart_current_page_narration(self):
        """Reinicia a narração da página atual para aplicar a voz nova NA HORA.

        Para o áudio em curso e re-dispara o MESMO fluxo pelo _toggle_audio, que
        respeita o modo vigente (normal ou contínuo traduzido, via
        _continuous_translate_mode). Decisões:
          * Reinicia TOCANDO mesmo se estava pausado — a troca de voz é uma ação
            explícita do usuário; retomar pausado seria surpreendente.
          * Uma leitura traduzida AVULSA (fora do modo contínuo traduzido) é
            reiniciada como leitura normal do texto original — limitação
            conhecida (o modo avulso não é rastreado como estado persistente).
        """
        self._stop_audio_if_running()   # invalida pré-síntese e libera o worker
        # worker agora é None → _toggle_audio executa o ramo de INÍCIO e relê a
        # página atual (recarregando o perfil de voz da config).
        self._toggle_audio()

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
        menu.setObjectName("readerPopupMenu")

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

        # 3. Voz específica da narração (por idioma, vinda do provider ativo)
        voice_menu = menu.addMenu("🎙️ Voz da Narração")
        current_voice = config.get("tts.book_narrator.voice_id", None)

        # Item 4/3: se o motor de RESERVA está ativo agora (fallback em curso),
        # as vozes do motor preferido não se aplicam — avisa com item desabilitado.
        active_engine = "none"
        if self._tts_router is not None:
            try:
                active_engine = self._tts_router.get_active_provider_name()
            except Exception:
                active_engine = "none"
        if active_engine and active_engine.lower() not in ("none", (current_provider or "").lower()):
            warn = QAction(
                f"⚠️ Motor reserva ativo ({active_engine}) — vozes "
                f"{(current_provider or '').title()} indisponíveis", voice_menu)
            warn.setEnabled(False)
            voice_menu.addAction(warn)
            voice_menu.addSeparator()

        auto_action = QAction("🌐 Automática (por idioma)", voice_menu, checkable=True)
        auto_action.setChecked(not current_voice)
        auto_action.triggered.connect(
            lambda checked: self._on_voice_selected(None))
        voice_menu.addAction(auto_action)
        voices_by_lang = {}
        if self._tts_router is not None:
            try:
                voices_by_lang = self._tts_router.voices_by_language(current_provider)
            except Exception:
                voices_by_lang = {}
        lang_labels = {"pt": "🇧🇷 Português", "en": "🇺🇸 English"}
        for lang in sorted(voices_by_lang):
            sub = voice_menu.addMenu(lang_labels.get(lang, lang.upper()))
            for voice in voices_by_lang[lang]:
                gender = getattr(voice, "gender", "") or ""
                label = f"{voice.name} ({gender})" if gender not in ("", "neutral") else voice.name
                v_action = QAction(label, sub, checkable=True)
                v_action.setChecked(current_voice == voice.voice_id)
                v_action.triggered.connect(
                    lambda checked, vid=voice.voice_id: self._on_voice_selected(vid))
                sub.addAction(v_action)
        if not voices_by_lang:
            none_action = QAction("(motor não lista vozes — usa a automática)", voice_menu)
            none_action.setEnabled(False)
            voice_menu.addAction(none_action)

        # 4. Seleção de Estilo / Voz
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
        
        # _tts_settings_btn (state-holder pré-Tarefa 1.4) foi removido: o
        # botão único de áudio (_audio_btn) é agora um âncora sempre presente
        # na toolbar (antes ele nunca era exibido, então mapToGlobal cairia
        # num widget sem posição real).
        anchor = getattr(self, "_overflow_btn", None) or self._audio_btn
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
