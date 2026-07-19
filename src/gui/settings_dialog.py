"""Diálogo de configurações da aplicação."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget, QWidget,
    QGroupBox, QFontComboBox, QSlider, QListWidget, QFileDialog,
    QLineEdit, QScrollArea,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.config import ConfigManager, DEFAULT_CONFIG
from src.utils.constants import (
    THEME_DARK, THEME_LIGHT, THEME_SEPIA,
    MIN_FONT_SIZE, MAX_FONT_SIZE, DEFAULT_FONT_SIZE,
)


class SettingsDialog(QDialog):
    """Diálogo de configurações com abas."""

    theme_changed = pyqtSignal(str)
    settings_changed = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("⚙️ Configurações")
        self.setMinimumSize(QSize(550, 450))
        self.setModal(True)
        self._setup_ui()
        if hasattr(self, "_tabs"):
            self._tabs.setCurrentIndex(initial_tab)
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Título
        title = QLabel("⚙️ Configurações")
        font = title.font()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setObjectName("settingsDialogTitle")
        layout.addWidget(title)

        # Abas
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_appearance_tab(), "🎨 Aparência")
        self._tabs.addTab(self._create_reader_tab(), "📖 Leitor")
        self._tabs.addTab(self._create_library_tab(), "📚 Biblioteca")
        self._tabs.addTab(self._create_tts_tab(), "🔊 Narração")
        self._tabs.addTab(self._create_advanced_tab(), "⚙️ Avançado")
        layout.addWidget(self._tabs)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("Restaurar Padrões")
        reset_btn.setObjectName("secondaryBtn")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾  Salvar")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _create_appearance_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Tema
        theme_group = QGroupBox("Tema")
        theme_group.setObjectName("settingsGroup")
        theme_layout = QVBoxLayout(theme_group)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Tema da interface:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("🌙 Escuro", THEME_DARK)
        self._theme_combo.addItem("☀️ Claro", THEME_LIGHT)
        self._theme_combo.addItem("📜 Sépia", THEME_SEPIA)
        self._theme_combo.setFixedWidth(200)
        self._theme_combo.currentIndexChanged.connect(
            lambda: self.theme_changed.emit(self._theme_combo.currentData())
        )
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        theme_layout.addLayout(theme_row)

        layout.addWidget(theme_group)

        # Visualização da biblioteca
        view_group = QGroupBox("Visualização da Biblioteca")
        view_group.setObjectName("settingsGroup")
        view_layout = QVBoxLayout(view_group)

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Modo de visualização:"))
        self._view_combo = QComboBox()
        self._view_combo.addItem("▦ Grade", "grid")
        self._view_combo.addItem("☰ Lista", "list")
        self._view_combo.setFixedWidth(200)
        view_row.addWidget(self._view_combo)
        view_row.addStretch()
        view_layout.addLayout(view_row)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Ordenar por:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Data de adição", "date_added")
        self._sort_combo.addItem("Última atividade", "date_modified")
        self._sort_combo.addItem("Título", "title")
        self._sort_combo.addItem("Autor", "author")
        self._sort_combo.addItem("Avaliação", "rating")
        self._sort_combo.setFixedWidth(200)
        sort_row.addWidget(self._sort_combo)
        sort_row.addStretch()
        view_layout.addLayout(sort_row)

        layout.addWidget(view_group)
        layout.addStretch()
        return tab

    def _create_reader_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Tipografia
        font_group = QGroupBox("Tipografia")
        font_group.setObjectName("settingsGroup")
        font_layout = QVBoxLayout(font_group)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Fonte:"))
        self._font_combo = QFontComboBox()
        self._font_combo.setFixedWidth(220)
        self._font_combo.setObjectName("settingsNumericInput")
        font_row.addWidget(self._font_combo)
        font_row.addStretch()
        font_layout.addLayout(font_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Tamanho:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self._font_size.setValue(DEFAULT_FONT_SIZE)
        self._font_size.setSuffix(" px")
        self._font_size.setFixedWidth(100)
        self._font_size.setObjectName("settingsNumericInput")
        size_row.addWidget(self._font_size)
        size_row.addStretch()
        font_layout.addLayout(size_row)

        # Espaçamento de linha
        line_row = QHBoxLayout()
        line_row.addWidget(QLabel("Espaçamento:"))
        self._line_height = QSlider(Qt.Orientation.Horizontal)
        self._line_height.setRange(10, 30)
        self._line_height.setValue(16)  # 1.6
        self._line_height.setFixedWidth(200)
        self._line_height_label = QLabel("1.6")
        self._line_height_label.setFixedWidth(30)
        self._line_height.valueChanged.connect(
            lambda v: self._line_height_label.setText(f"{v / 10:.1f}")
        )
        line_row.addWidget(self._line_height)
        line_row.addWidget(self._line_height_label)
        line_row.addStretch()
        font_layout.addLayout(line_row)

        layout.addWidget(font_group)

        # Margens
        margin_group = QGroupBox("Margens")
        margin_group.setObjectName("settingsGroup")
        margin_layout = QVBoxLayout(margin_group)

        h_margin = QHBoxLayout()
        h_margin.addWidget(QLabel("Margem horizontal:"))
        self._h_margin = QSpinBox()
        self._h_margin.setRange(20, 200)
        self._h_margin.setValue(60)
        self._h_margin.setSuffix(" px")
        self._h_margin.setFixedWidth(100)
        self._h_margin.setObjectName("settingsNumericInput")
        h_margin.addWidget(self._h_margin)
        h_margin.addStretch()
        margin_layout.addLayout(h_margin)

        v_margin = QHBoxLayout()
        v_margin.addWidget(QLabel("Margem vertical:"))
        self._v_margin = QSpinBox()
        self._v_margin.setRange(10, 100)
        self._v_margin.setValue(40)
        self._v_margin.setSuffix(" px")
        self._v_margin.setFixedWidth(100)
        self._v_margin.setObjectName("settingsNumericInput")
        v_margin.addWidget(self._v_margin)
        v_margin.addStretch()
        margin_layout.addLayout(v_margin)

        layout.addWidget(margin_group)
        layout.addStretch()
        return tab

    def _create_library_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Importação
        import_group = QGroupBox("Importação")
        import_group.setObjectName("settingsGroup")
        import_layout = QVBoxLayout(import_group)

        self._detect_dups = QCheckBox("Detectar duplicatas ao importar")
        self._detect_dups.setChecked(True)
        import_layout.addWidget(self._detect_dups)

        self._auto_meta = QCheckBox("Extrair metadados automaticamente")
        self._auto_meta.setChecked(True)
        import_layout.addWidget(self._auto_meta)

        layout.addWidget(import_group)

        # Diretórios monitorados
        watch_group = QGroupBox("Diretórios Monitorados")
        watch_group.setObjectName("settingsGroup")
        watch_layout = QVBoxLayout(watch_group)

        self._watch_list = QListWidget()
        self._watch_list.setMaximumHeight(100)
        self._watch_list.setObjectName("settingsWatchList")
        watch_layout.addWidget(self._watch_list)

        watch_btns = QHBoxLayout()
        add_dir_btn = QPushButton("+ Adicionar")
        add_dir_btn.setObjectName("secondaryBtn")
        add_dir_btn.clicked.connect(self._add_watch_dir)
        watch_btns.addWidget(add_dir_btn)

        rem_dir_btn = QPushButton("- Remover")
        rem_dir_btn.setObjectName("secondaryBtn")
        rem_dir_btn.clicked.connect(self._remove_watch_dir)
        watch_btns.addWidget(rem_dir_btn)

        watch_btns.addStretch()
        watch_layout.addLayout(watch_btns)

        layout.addWidget(watch_group)

        # Metas de leitura (Tarefa 5.2 — estatísticas vivas)
        goals_group = QGroupBox("Metas de Leitura")
        goals_group.setObjectName("settingsGroup")
        goals_layout = QVBoxLayout(goals_group)

        goal_row = QHBoxLayout()
        goal_row.addWidget(QLabel("Meta anual de livros lidos:"))
        self._annual_goal_spin = QSpinBox()
        self._annual_goal_spin.setRange(0, 999)
        self._annual_goal_spin.setSpecialValueText("Sem meta")
        self._annual_goal_spin.setFixedWidth(100)
        self._annual_goal_spin.setObjectName("settingsNumericInput")
        goal_row.addWidget(self._annual_goal_spin)
        goal_row.addStretch()
        goals_layout.addLayout(goal_row)

        goal_hint = QLabel(
            "0 = meta desativada. O progresso aparece no painel de Estatísticas.")
        goal_hint.setWordWrap(True)
        goals_layout.addWidget(goal_hint)

        layout.addWidget(goals_group)
        layout.addStretch()
        return tab

    def _create_tts_tab(self) -> QWidget:
        """Aba de configurações de narração/TTS (Fase 13)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Narrador do Livro
        book_group = QGroupBox("📖 Narrador do Livro")
        book_group.setObjectName("settingsGroup")
        book_layout = QVBoxLayout(book_group)

        # Provider preferido
        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Engine preferida:"))
        self._tts_book_provider = QComboBox()
        self._tts_book_provider.addItem("Kokoro (Qualidade)", "kokoro")
        self._tts_book_provider.addItem("Piper (Leve)", "piper")
        self._tts_book_provider.addItem("Qwen3-TTS (Avançado)", "qwen3-tts")
        self._tts_book_provider.addItem("Sherpa-ONNX", "sherpa-onnx")
        self._tts_book_provider.addItem("pyttsx3 (Sistema)", "pyttsx3")
        self._tts_book_provider.setFixedWidth(220)
        prov_row.addWidget(self._tts_book_provider)
        prov_row.addStretch()
        book_layout.addLayout(prov_row)

        # Estilo de narração
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Estilo:"))
        self._tts_book_style = QComboBox()
        self._tts_book_style.addItem("🌿 Sereno", "serene")
        self._tts_book_style.addItem("📐 Técnico", "technical")
        self._tts_book_style.addItem("🎭 Expressivo", "expressive")
        self._tts_book_style.setFixedWidth(220)
        style_row.addWidget(self._tts_book_style)
        style_row.addStretch()
        book_layout.addLayout(style_row)

        # Velocidade do livro
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Velocidade:"))
        self._tts_book_rate = QSlider(Qt.Orientation.Horizontal)
        self._tts_book_rate.setRange(50, 200)  # 0.5x to 2.0x
        self._tts_book_rate.setValue(100)  # 1.0x
        self._tts_book_rate.setFixedWidth(200)
        self._tts_book_rate_label = QLabel("1.0x")
        self._tts_book_rate_label.setFixedWidth(40)
        self._tts_book_rate.valueChanged.connect(
            lambda v: self._tts_book_rate_label.setText(f"{v / 100:.1f}x")
        )
        rate_row.addWidget(self._tts_book_rate)
        rate_row.addWidget(self._tts_book_rate_label)
        rate_row.addStretch()
        book_layout.addLayout(rate_row)

        layout.addWidget(book_group)

        # Voz do Assistente
        asst_group = QGroupBox("🤖 Voz do Assistente")
        asst_group.setObjectName("settingsGroup")
        asst_layout = QVBoxLayout(asst_group)

        asst_prov_row = QHBoxLayout()
        asst_prov_row.addWidget(QLabel("Engine preferida:"))
        self._tts_asst_provider = QComboBox()
        self._tts_asst_provider.addItem("Kokoro (Qualidade)", "kokoro")
        self._tts_asst_provider.addItem("Piper (Leve)", "piper")
        self._tts_asst_provider.addItem("Qwen3-TTS (Avançado)", "qwen3-tts")
        self._tts_asst_provider.addItem("Sherpa-ONNX", "sherpa-onnx")
        self._tts_asst_provider.addItem("pyttsx3 (Sistema)", "pyttsx3")
        self._tts_asst_provider.setFixedWidth(220)
        asst_prov_row.addWidget(self._tts_asst_provider)
        asst_prov_row.addStretch()
        asst_layout.addLayout(asst_prov_row)

        asst_style_row = QHBoxLayout()
        asst_style_row.addWidget(QLabel("Estilo:"))
        self._tts_asst_style = QComboBox()
        self._tts_asst_style.addItem("📚 Didático", "didactic")
        self._tts_asst_style.addItem("🌿 Sereno", "serene")
        self._tts_asst_style.addItem("📐 Técnico", "technical")
        self._tts_asst_style.setFixedWidth(220)
        asst_style_row.addWidget(self._tts_asst_style)
        asst_style_row.addStretch()
        asst_layout.addLayout(asst_style_row)

        asst_rate_row = QHBoxLayout()
        asst_rate_row.addWidget(QLabel("Velocidade:"))
        self._tts_asst_rate = QSlider(Qt.Orientation.Horizontal)
        self._tts_asst_rate.setRange(50, 200)
        self._tts_asst_rate.setValue(105)
        self._tts_asst_rate.setFixedWidth(200)
        self._tts_asst_rate_label = QLabel("1.0x")
        self._tts_asst_rate_label.setFixedWidth(40)
        self._tts_asst_rate.valueChanged.connect(
            lambda v: self._tts_asst_rate_label.setText(f"{v / 100:.1f}x")
        )
        asst_rate_row.addWidget(self._tts_asst_rate)
        asst_rate_row.addWidget(self._tts_asst_rate_label)
        asst_rate_row.addStretch()
        asst_layout.addLayout(asst_rate_row)

        layout.addWidget(asst_group)

        # Fallback automático
        fallback_group = QGroupBox("⚡ Comportamento")
        fallback_group.setObjectName("settingsGroup")
        fallback_layout = QVBoxLayout(fallback_group)

        self._tts_auto_fallback = QCheckBox("Fallback automático para engine mais leve")
        self._tts_auto_fallback.setChecked(True)
        fallback_layout.addWidget(self._tts_auto_fallback)

        layout.addWidget(fallback_group)

        layout.addStretch()
        return tab

    def _create_advanced_tab(self) -> QWidget:
        """Aba "Avançado": expõe graph.*, auto_index.* e translation.* do
        DEFAULT_CONFIG (Onda 4, item 4.1). Os padrões já funcionam bem — por
        isso o aviso no topo — mas usuários avançados podem querer ajustar.
        """
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        warning = QLabel(
            "Ajustes avançados — os padrões funcionam bem para a maioria dos casos."
        )
        warning.setObjectName("settingsAdvancedWarning")
        warning.setWordWrap(True)
        warning.setContentsMargins(0, 0, 0, 8)
        outer_layout.addWidget(warning)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        scroll.setWidget(tab)

        graph_defaults = DEFAULT_CONFIG["graph"]
        autoindex_defaults = DEFAULT_CONFIG["auto_index"]
        translation_defaults = DEFAULT_CONFIG["translation"]

        # ── Grafo de conceitos ──────────────────────────────────────────
        graph_group = QGroupBox("Grafo de conceitos")
        graph_group.setObjectName("settingsGroup")
        graph_layout = QVBoxLayout(graph_group)

        self._adv_graph_enabled = QCheckBox("Grafo de conceitos ativo")
        self._adv_graph_enabled.setChecked(graph_defaults["enabled"])
        graph_layout.addWidget(self._adv_graph_enabled)

        self._adv_graph_use_llm_pages = QCheckBox("Usar LLM para extrair conceitos de páginas")
        self._adv_graph_use_llm_pages.setChecked(graph_defaults["use_llm_pages"])
        graph_layout.addWidget(self._adv_graph_use_llm_pages)

        self._adv_graph_use_llm_annotations = QCheckBox("Usar LLM para extrair conceitos de anotações")
        self._adv_graph_use_llm_annotations.setChecked(graph_defaults["use_llm_annotations"])
        graph_layout.addWidget(self._adv_graph_use_llm_annotations)

        self._adv_graph_use_llm_idle = QCheckBox("Usar LLM durante o processamento em ocioso")
        self._adv_graph_use_llm_idle.setChecked(graph_defaults["use_llm_idle"])
        graph_layout.addWidget(self._adv_graph_use_llm_idle)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Modelo LLM do grafo:"))
        self._adv_graph_llm_model = QLineEdit()
        self._adv_graph_llm_model.setPlaceholderText("padrão do sistema")
        self._adv_graph_llm_model.setObjectName("settingsNumericInput")
        model_row.addWidget(self._adv_graph_llm_model, stretch=1)
        graph_layout.addLayout(model_row)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Timeout do LLM:"))
        self._adv_graph_llm_timeout = QSpinBox()
        self._adv_graph_llm_timeout.setRange(5, 300)
        self._adv_graph_llm_timeout.setValue(graph_defaults["llm_timeout_s"])
        self._adv_graph_llm_timeout.setSuffix(" s")
        self._adv_graph_llm_timeout.setFixedWidth(100)
        self._adv_graph_llm_timeout.setObjectName("settingsNumericInput")
        timeout_row.addWidget(self._adv_graph_llm_timeout)
        timeout_row.addStretch()
        graph_layout.addLayout(timeout_row)

        max_page_row = QHBoxLayout()
        max_page_row.addWidget(QLabel("Máx. conceitos por página:"))
        self._adv_graph_max_concepts_page = QSpinBox()
        self._adv_graph_max_concepts_page.setRange(1, 50)
        self._adv_graph_max_concepts_page.setValue(graph_defaults["max_concepts_per_page"])
        self._adv_graph_max_concepts_page.setFixedWidth(100)
        self._adv_graph_max_concepts_page.setObjectName("settingsNumericInput")
        max_page_row.addWidget(self._adv_graph_max_concepts_page)
        max_page_row.addStretch()
        graph_layout.addLayout(max_page_row)

        max_ann_row = QHBoxLayout()
        max_ann_row.addWidget(QLabel("Máx. conceitos por anotação:"))
        self._adv_graph_max_concepts_annotation = QSpinBox()
        self._adv_graph_max_concepts_annotation.setRange(1, 50)
        self._adv_graph_max_concepts_annotation.setValue(graph_defaults["max_concepts_per_annotation"])
        self._adv_graph_max_concepts_annotation.setFixedWidth(100)
        self._adv_graph_max_concepts_annotation.setObjectName("settingsNumericInput")
        max_ann_row.addWidget(self._adv_graph_max_concepts_annotation)
        max_ann_row.addStretch()
        graph_layout.addLayout(max_ann_row)

        self._adv_graph_idle_enabled = QCheckBox("Processar grafo em ocioso")
        self._adv_graph_idle_enabled.setChecked(graph_defaults["idle_enabled"])
        graph_layout.addWidget(self._adv_graph_idle_enabled)

        idle_interval_row = QHBoxLayout()
        idle_interval_row.addWidget(QLabel("Intervalo de verificação (ocioso):"))
        self._adv_graph_idle_interval = QSpinBox()
        self._adv_graph_idle_interval.setRange(10, 3600)
        self._adv_graph_idle_interval.setValue(graph_defaults["idle_interval_s"])
        self._adv_graph_idle_interval.setSuffix(" s")
        self._adv_graph_idle_interval.setFixedWidth(100)
        self._adv_graph_idle_interval.setObjectName("settingsNumericInput")
        idle_interval_row.addWidget(self._adv_graph_idle_interval)
        idle_interval_row.addStretch()
        graph_layout.addLayout(idle_interval_row)

        idle_inactivity_row = QHBoxLayout()
        idle_inactivity_row.addWidget(QLabel("Inatividade mínima (ocioso):"))
        self._adv_graph_idle_min_inactivity = QSpinBox()
        self._adv_graph_idle_min_inactivity.setRange(10, 3600)
        self._adv_graph_idle_min_inactivity.setValue(graph_defaults["idle_min_inactivity_s"])
        self._adv_graph_idle_min_inactivity.setSuffix(" s")
        self._adv_graph_idle_min_inactivity.setFixedWidth(100)
        self._adv_graph_idle_min_inactivity.setObjectName("settingsNumericInput")
        idle_inactivity_row.addWidget(self._adv_graph_idle_min_inactivity)
        idle_inactivity_row.addStretch()
        graph_layout.addLayout(idle_inactivity_row)

        idle_batch_row = QHBoxLayout()
        idle_batch_row.addWidget(QLabel("Páginas por lote (ocioso):"))
        self._adv_graph_idle_batch_pages = QSpinBox()
        self._adv_graph_idle_batch_pages.setRange(1, 200)
        self._adv_graph_idle_batch_pages.setValue(graph_defaults["idle_batch_pages"])
        self._adv_graph_idle_batch_pages.setFixedWidth(100)
        self._adv_graph_idle_batch_pages.setObjectName("settingsNumericInput")
        idle_batch_row.addWidget(self._adv_graph_idle_batch_pages)
        idle_batch_row.addStretch()
        graph_layout.addLayout(idle_batch_row)

        edge_shared_row = QHBoxLayout()
        edge_shared_row.addWidget(QLabel("Mín. de conceitos compartilhados (aresta):"))
        self._adv_graph_edge_min_shared = QSpinBox()
        self._adv_graph_edge_min_shared.setRange(1, 20)
        self._adv_graph_edge_min_shared.setValue(graph_defaults["edge_min_shared"])
        self._adv_graph_edge_min_shared.setFixedWidth(100)
        self._adv_graph_edge_min_shared.setObjectName("settingsNumericInput")
        edge_shared_row.addWidget(self._adv_graph_edge_min_shared)
        edge_shared_row.addStretch()
        graph_layout.addLayout(edge_shared_row)

        edge_cap_row = QHBoxLayout()
        edge_cap_row.addWidget(QLabel("Limite de frequência de conceito (aresta):"))
        self._adv_graph_edge_df_cap = QDoubleSpinBox()
        self._adv_graph_edge_df_cap.setRange(0.0, 1.0)
        self._adv_graph_edge_df_cap.setSingleStep(0.05)
        self._adv_graph_edge_df_cap.setDecimals(2)
        self._adv_graph_edge_df_cap.setValue(graph_defaults["edge_df_cap"])
        self._adv_graph_edge_df_cap.setFixedWidth(100)
        self._adv_graph_edge_df_cap.setObjectName("settingsNumericInput")
        edge_cap_row.addWidget(self._adv_graph_edge_df_cap)
        edge_cap_row.addStretch()
        graph_layout.addLayout(edge_cap_row)

        layout.addWidget(graph_group)

        # ── Auto-indexação RAG ──────────────────────────────────────────
        autoindex_group = QGroupBox("Auto-indexação RAG")
        autoindex_group.setObjectName("settingsGroup")
        autoindex_layout = QVBoxLayout(autoindex_group)

        self._adv_autoindex_enabled = QCheckBox("Auto-indexação RAG ativa")
        self._adv_autoindex_enabled.setChecked(autoindex_defaults["enabled"])
        autoindex_layout.addWidget(self._adv_autoindex_enabled)

        ai_interval_row = QHBoxLayout()
        ai_interval_row.addWidget(QLabel("Intervalo de verificação (ocioso):"))
        self._adv_autoindex_idle_interval = QSpinBox()
        self._adv_autoindex_idle_interval.setRange(10, 3600)
        self._adv_autoindex_idle_interval.setValue(autoindex_defaults["idle_interval_s"])
        self._adv_autoindex_idle_interval.setSuffix(" s")
        self._adv_autoindex_idle_interval.setFixedWidth(100)
        self._adv_autoindex_idle_interval.setObjectName("settingsNumericInput")
        ai_interval_row.addWidget(self._adv_autoindex_idle_interval)
        ai_interval_row.addStretch()
        autoindex_layout.addLayout(ai_interval_row)

        ai_inactivity_row = QHBoxLayout()
        ai_inactivity_row.addWidget(QLabel("Inatividade mínima (ocioso):"))
        self._adv_autoindex_idle_min_inactivity = QSpinBox()
        self._adv_autoindex_idle_min_inactivity.setRange(10, 3600)
        self._adv_autoindex_idle_min_inactivity.setValue(autoindex_defaults["idle_min_inactivity_s"])
        self._adv_autoindex_idle_min_inactivity.setSuffix(" s")
        self._adv_autoindex_idle_min_inactivity.setFixedWidth(100)
        self._adv_autoindex_idle_min_inactivity.setObjectName("settingsNumericInput")
        ai_inactivity_row.addWidget(self._adv_autoindex_idle_min_inactivity)
        ai_inactivity_row.addStretch()
        autoindex_layout.addLayout(ai_inactivity_row)

        layout.addWidget(autoindex_group)

        # ── Tradução ────────────────────────────────────────────────────
        translation_group = QGroupBox("Tradução")
        translation_group.setObjectName("settingsGroup")
        translation_layout = QVBoxLayout(translation_group)

        trans_model_row = QHBoxLayout()
        trans_model_row.addWidget(QLabel("Modelo de tradução:"))
        self._adv_translation_model = QLineEdit()
        self._adv_translation_model.setText(translation_defaults["model"])
        self._adv_translation_model.setObjectName("settingsNumericInput")
        trans_model_row.addWidget(self._adv_translation_model, stretch=1)
        translation_layout.addLayout(trans_model_row)

        trans_src_row = QHBoxLayout()
        trans_src_row.addWidget(QLabel("Idioma de origem padrão:"))
        self._adv_translation_default_src = QLineEdit()
        self._adv_translation_default_src.setText(translation_defaults["default_src"])
        self._adv_translation_default_src.setFixedWidth(80)
        self._adv_translation_default_src.setObjectName("settingsNumericInput")
        trans_src_row.addWidget(self._adv_translation_default_src)
        trans_src_row.addStretch()
        translation_layout.addLayout(trans_src_row)

        trans_tgt_row = QHBoxLayout()
        trans_tgt_row.addWidget(QLabel("Idioma de destino padrão:"))
        self._adv_translation_default_tgt = QLineEdit()
        self._adv_translation_default_tgt.setText(translation_defaults["default_tgt"])
        self._adv_translation_default_tgt.setFixedWidth(80)
        self._adv_translation_default_tgt.setObjectName("settingsNumericInput")
        trans_tgt_row.addWidget(self._adv_translation_default_tgt)
        trans_tgt_row.addStretch()
        translation_layout.addLayout(trans_tgt_row)

        self._adv_translation_revise_llm = QCheckBox("Revisar tradução com LLM local")
        self._adv_translation_revise_llm.setChecked(translation_defaults["revise_with_llm"])
        translation_layout.addWidget(self._adv_translation_revise_llm)

        layout.addWidget(translation_group)
        layout.addStretch()
        return outer

    def _load_settings(self):
        """Carrega configurações atuais nos widgets."""
        # Tema
        theme = self._config.theme
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == theme:
                self._theme_combo.setCurrentIndex(i)
                break

        # Leitor
        reader = self._config.reader_config
        self._font_size.setValue(reader.get("font_size", DEFAULT_FONT_SIZE))
        lh = reader.get("line_height", 1.6)
        self._line_height.setValue(int(lh * 10))
        self._h_margin.setValue(reader.get("margin_horizontal", 60))
        self._v_margin.setValue(reader.get("margin_vertical", 40))

        font_family = reader.get("font_family", "Georgia")
        self._font_combo.setCurrentFont(QFont(font_family))

        # Biblioteca
        lib = self._config.library_config
        for i in range(self._view_combo.count()):
            if self._view_combo.itemData(i) == lib.get("view_mode", "grid"):
                self._view_combo.setCurrentIndex(i)
                break
        for i in range(self._sort_combo.count()):
            if self._sort_combo.itemData(i) == lib.get("sort_by", "date_added"):
                self._sort_combo.setCurrentIndex(i)
                break

        # Importação
        self._detect_dups.setChecked(self._config.get("import.detect_duplicates", True))
        self._auto_meta.setChecked(self._config.get("import.auto_extract_metadata", True))

        # Diretórios
        dirs = self._config.get("watched_directories", [])
        for d in dirs:
            self._watch_list.addItem(d)

        # Metas de leitura (Tarefa 5.2)
        self._annual_goal_spin.setValue(self._config.get("stats.annual_goal_books", 0))

        # TTS — Narração (Fase 13)
        tts_cfg = self._config.tts_config
        book_cfg = tts_cfg.get("book_narrator", {})
        asst_cfg = tts_cfg.get("assistant", {})

        for i in range(self._tts_book_provider.count()):
            if self._tts_book_provider.itemData(i) == book_cfg.get("preferred_provider", "kokoro"):
                self._tts_book_provider.setCurrentIndex(i)
                break
        for i in range(self._tts_book_style.count()):
            if self._tts_book_style.itemData(i) == book_cfg.get("style", "serene"):
                self._tts_book_style.setCurrentIndex(i)
                break
        self._tts_book_rate.setValue(int(book_cfg.get("rate", 1.0) * 100))

        for i in range(self._tts_asst_provider.count()):
            if self._tts_asst_provider.itemData(i) == asst_cfg.get("preferred_provider", "kokoro"):
                self._tts_asst_provider.setCurrentIndex(i)
                break
        for i in range(self._tts_asst_style.count()):
            if self._tts_asst_style.itemData(i) == asst_cfg.get("style", "didactic"):
                self._tts_asst_style.setCurrentIndex(i)
                break
        self._tts_asst_rate.setValue(int(asst_cfg.get("rate", 1.05) * 100))

        self._tts_auto_fallback.setChecked(tts_cfg.get("auto_fallback", True))

        # Avançado — grafo de conceitos, auto-indexação e tradução (Onda 4, item 4.1)
        graph_cfg = self._config.get("graph", DEFAULT_CONFIG["graph"])
        self._adv_graph_enabled.setChecked(graph_cfg.get("enabled", True))
        self._adv_graph_use_llm_pages.setChecked(graph_cfg.get("use_llm_pages", False))
        self._adv_graph_use_llm_annotations.setChecked(graph_cfg.get("use_llm_annotations", True))
        self._adv_graph_use_llm_idle.setChecked(graph_cfg.get("use_llm_idle", False))
        self._adv_graph_llm_model.setText(graph_cfg.get("llm_model") or "")
        self._adv_graph_llm_timeout.setValue(graph_cfg.get("llm_timeout_s", 20))
        self._adv_graph_max_concepts_page.setValue(graph_cfg.get("max_concepts_per_page", 8))
        self._adv_graph_max_concepts_annotation.setValue(graph_cfg.get("max_concepts_per_annotation", 5))
        self._adv_graph_idle_enabled.setChecked(graph_cfg.get("idle_enabled", True))
        self._adv_graph_idle_interval.setValue(graph_cfg.get("idle_interval_s", 60))
        self._adv_graph_idle_min_inactivity.setValue(graph_cfg.get("idle_min_inactivity_s", 90))
        self._adv_graph_idle_batch_pages.setValue(graph_cfg.get("idle_batch_pages", 25))
        self._adv_graph_edge_min_shared.setValue(graph_cfg.get("edge_min_shared", 2))
        self._adv_graph_edge_df_cap.setValue(graph_cfg.get("edge_df_cap", 0.5))

        autoindex_cfg = self._config.get("auto_index", DEFAULT_CONFIG["auto_index"])
        self._adv_autoindex_enabled.setChecked(autoindex_cfg.get("enabled", True))
        self._adv_autoindex_idle_interval.setValue(autoindex_cfg.get("idle_interval_s", 120))
        self._adv_autoindex_idle_min_inactivity.setValue(autoindex_cfg.get("idle_min_inactivity_s", 120))

        translation_cfg = self._config.get("translation", DEFAULT_CONFIG["translation"])
        self._adv_translation_model.setText(translation_cfg.get("model", DEFAULT_CONFIG["translation"]["model"]))
        self._adv_translation_default_src.setText(translation_cfg.get("default_src", "en"))
        self._adv_translation_default_tgt.setText(translation_cfg.get("default_tgt", "pt"))
        self._adv_translation_revise_llm.setChecked(translation_cfg.get("revise_with_llm", True))

    def _save_and_close(self):
        """Salva configurações e fecha o diálogo."""
        self._config.set("theme", self._theme_combo.currentData())
        self._config.set("reader.font_family", self._font_combo.currentFont().family())
        self._config.set("reader.font_size", self._font_size.value())
        self._config.set("reader.line_height", self._line_height.value() / 10)
        self._config.set("reader.margin_horizontal", self._h_margin.value())
        self._config.set("reader.margin_vertical", self._v_margin.value())
        self._config.set("library.view_mode", self._view_combo.currentData())
        self._config.set("library.sort_by", self._sort_combo.currentData())
        self._config.set("import.detect_duplicates", self._detect_dups.isChecked())
        self._config.set("import.auto_extract_metadata", self._auto_meta.isChecked())

        dirs = [self._watch_list.item(i).text() for i in range(self._watch_list.count())]
        self._config.set("watched_directories", dirs)

        # Metas de leitura (Tarefa 5.2)
        self._config.set("stats.annual_goal_books", self._annual_goal_spin.value())

        # TTS — Narração (Fase 13)
        self._config.set("tts.book_narrator.preferred_provider", self._tts_book_provider.currentData())
        self._config.set("tts.book_narrator.style", self._tts_book_style.currentData())
        self._config.set("tts.book_narrator.rate", self._tts_book_rate.value() / 100)
        self._config.set("tts.assistant.preferred_provider", self._tts_asst_provider.currentData())
        self._config.set("tts.assistant.style", self._tts_asst_style.currentData())
        self._config.set("tts.assistant.rate", self._tts_asst_rate.value() / 100)
        self._config.set("tts.auto_fallback", self._tts_auto_fallback.isChecked())

        # Avançado — grafo de conceitos, auto-indexação e tradução (Onda 4, item 4.1)
        self._config.set("graph.enabled", self._adv_graph_enabled.isChecked())
        self._config.set("graph.use_llm_pages", self._adv_graph_use_llm_pages.isChecked())
        self._config.set("graph.use_llm_annotations", self._adv_graph_use_llm_annotations.isChecked())
        self._config.set("graph.use_llm_idle", self._adv_graph_use_llm_idle.isChecked())
        llm_model = self._adv_graph_llm_model.text().strip()
        self._config.set("graph.llm_model", llm_model or None)
        self._config.set("graph.llm_timeout_s", self._adv_graph_llm_timeout.value())
        self._config.set("graph.max_concepts_per_page", self._adv_graph_max_concepts_page.value())
        self._config.set("graph.max_concepts_per_annotation", self._adv_graph_max_concepts_annotation.value())
        self._config.set("graph.idle_enabled", self._adv_graph_idle_enabled.isChecked())
        self._config.set("graph.idle_interval_s", self._adv_graph_idle_interval.value())
        self._config.set("graph.idle_min_inactivity_s", self._adv_graph_idle_min_inactivity.value())
        self._config.set("graph.idle_batch_pages", self._adv_graph_idle_batch_pages.value())
        self._config.set("graph.edge_min_shared", self._adv_graph_edge_min_shared.value())
        self._config.set("graph.edge_df_cap", self._adv_graph_edge_df_cap.value())

        self._config.set("auto_index.enabled", self._adv_autoindex_enabled.isChecked())
        self._config.set("auto_index.idle_interval_s", self._adv_autoindex_idle_interval.value())
        self._config.set("auto_index.idle_min_inactivity_s", self._adv_autoindex_idle_min_inactivity.value())

        self._config.set("translation.model", self._adv_translation_model.text().strip() or DEFAULT_CONFIG["translation"]["model"])
        self._config.set("translation.default_src", self._adv_translation_default_src.text().strip() or "en")
        self._config.set("translation.default_tgt", self._adv_translation_default_tgt.text().strip() or "pt")
        self._config.set("translation.revise_with_llm", self._adv_translation_revise_llm.isChecked())

        self.settings_changed.emit()
        self.accept()

    def _reset_defaults(self):
        """Restaura configurações padrão."""
        from src.core.config import DEFAULT_CONFIG
        self._theme_combo.setCurrentIndex(0)
        self._font_size.setValue(DEFAULT_CONFIG["reader"]["font_size"])
        self._line_height.setValue(int(DEFAULT_CONFIG["reader"]["line_height"] * 10))
        self._font_combo.setCurrentFont(QFont(DEFAULT_CONFIG["reader"]["font_family"]))

    def _add_watch_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Adicionar Diretório")
        if d:
            self._watch_list.addItem(d)

    def _remove_watch_dir(self):
        row = self._watch_list.currentRow()
        if row >= 0:
            self._watch_list.takeItem(row)
