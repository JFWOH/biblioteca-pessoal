"""Diálogo de configurações da aplicação."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QTabWidget, QWidget,
    QGroupBox, QFontComboBox, QSlider, QListWidget, QFileDialog,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.config import ConfigManager
from src.utils.constants import (
    THEME_DARK, THEME_LIGHT, THEME_SEPIA,
    MIN_FONT_SIZE, MAX_FONT_SIZE, DEFAULT_FONT_SIZE,
)


class SettingsDialog(QDialog):
    """Diálogo de configurações com abas."""

    theme_changed = pyqtSignal(str)
    settings_changed = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("⚙️ Configurações")
        self.setMinimumSize(QSize(550, 450))
        self.setModal(True)
        self._setup_ui()
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
        title.setStyleSheet("color: #e4e4e7;")
        layout.addWidget(title)

        # Abas
        tabs = QTabWidget()
        tabs.addTab(self._create_appearance_tab(), "🎨 Aparência")
        tabs.addTab(self._create_reader_tab(), "📖 Leitor")
        tabs.addTab(self._create_library_tab(), "📚 Biblioteca")
        layout.addWidget(tabs)

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
        theme_group.setStyleSheet(self._group_style())
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
        view_group.setStyleSheet(self._group_style())
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
        font_group.setStyleSheet(self._group_style())
        font_layout = QVBoxLayout(font_group)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Fonte:"))
        self._font_combo = QFontComboBox()
        self._font_combo.setFixedWidth(220)
        self._font_combo.setStyleSheet("""
            QFontComboBox {
                background: #18181b; border: 1px solid #27272a;
                border-radius: 6px; padding: 4px 8px; color: #e4e4e7;
            }
        """)
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
        self._font_size.setStyleSheet("""
            QSpinBox {
                background: #18181b; border: 1px solid #27272a;
                border-radius: 6px; padding: 4px 8px; color: #e4e4e7;
            }
        """)
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
        margin_group.setStyleSheet(self._group_style())
        margin_layout = QVBoxLayout(margin_group)

        h_margin = QHBoxLayout()
        h_margin.addWidget(QLabel("Margem horizontal:"))
        self._h_margin = QSpinBox()
        self._h_margin.setRange(20, 200)
        self._h_margin.setValue(60)
        self._h_margin.setSuffix(" px")
        self._h_margin.setFixedWidth(100)
        self._h_margin.setStyleSheet(self._font_size.styleSheet())
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
        self._v_margin.setStyleSheet(self._font_size.styleSheet())
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
        import_group.setStyleSheet(self._group_style())
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
        watch_group.setStyleSheet(self._group_style())
        watch_layout = QVBoxLayout(watch_group)

        self._watch_list = QListWidget()
        self._watch_list.setMaximumHeight(100)
        self._watch_list.setStyleSheet("""
            QListWidget {
                background: #0f0f17; border: 1px solid #27272a;
                border-radius: 6px; color: #e4e4e7; font-size: 12px;
            }
        """)
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
        layout.addStretch()
        return tab

    def _group_style(self) -> str:
        return """
            QGroupBox {
                border: 1px solid #27272a; border-radius: 8px;
                margin-top: 12px; padding: 16px; padding-top: 24px;
                color: #a1a1aa; font-size: 12px; font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 12px; padding: 0 6px;
            }
            QLabel { color: #a1a1aa; font-size: 12px; }
            QCheckBox { color: #a1a1aa; font-size: 12px; }
        """

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
