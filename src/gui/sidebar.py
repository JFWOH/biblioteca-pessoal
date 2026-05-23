"""Barra lateral de navegação da biblioteca."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


class Sidebar(QWidget):
    """Barra lateral com navegação por seções."""

    section_changed = pyqtSignal(str)  # nome da seção
    opds_toggled = pyqtSignal(bool)    # estado do servidor

    SECTIONS = [
        ("all", "📚  Todos os Livros"),
        ("reading", "📖  Lendo"),
        ("unread", "📋  Não Lidos"),
        ("read", "✅  Lidos"),
        ("favorites", "⭐  Favoritos"),
        ("global_search", "🔍  Pesquisa Global"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setMinimumWidth(220)
        self.setMaximumWidth(280)
        self._buttons: dict[str, QPushButton] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(2)

        # Logo / Título
        self._title = QLabel("📚 Biblioteca")
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font = self._title.font()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        self._title.setFont(font)
        self._title.setStyleSheet("color: #e4e4e7; padding: 0 4px 16px 4px;")
        layout.addWidget(self._title)

        # Seção: Biblioteca
        section_label = QLabel("BIBLIOTECA")
        section_label.setObjectName("sidebarSection")
        layout.addWidget(section_label)

        for key, label in self.SECTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._on_section_click(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        # Seção: Coleções
        layout.addSpacing(16)
        collections_label = QLabel("COLEÇÕES")
        collections_label.setObjectName("sidebarSection")
        layout.addWidget(collections_label)

        self._collections_layout = QVBoxLayout()
        self._collections_layout.setContentsMargins(0, 0, 0, 0)
        self._collections_layout.setSpacing(2)
        layout.addLayout(self._collections_layout)

        self.add_collection_btn = QPushButton("➕  Nova Coleção")
        self.add_collection_btn.setObjectName("secondaryBtn")
        layout.addWidget(self.add_collection_btn)

        # Seção: Tags
        layout.addSpacing(16)
        tags_label = QLabel("TAGS")
        tags_label.setObjectName("sidebarSection")
        layout.addWidget(tags_label)

        layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Botão de Estatísticas
        stats_btn = QPushButton("📊  Estatísticas")
        stats_btn.setCheckable(True)
        stats_btn.clicked.connect(lambda: self._on_section_click("stats"))
        layout.addWidget(stats_btn)
        self._buttons["stats"] = stats_btn

        # Estatísticas no rodapé
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #52525b; font-size: 11px; padding: 8px 4px;")
        self._stats_label.setWordWrap(True)
        layout.addWidget(self._stats_label)

        # Servidor OPDS
        layout.addSpacing(8)
        self._opds_btn = QPushButton("📡  Iniciar Servidor OPDS")
        self._opds_btn.setCheckable(True)
        self._opds_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #3f3f46; border-radius: 6px; color: #a1a1aa; padding: 6px; }
            QPushButton:checked { background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #10b981; }
        """)
        self._opds_btn.toggled.connect(self.opds_toggled.emit)
        layout.addWidget(self._opds_btn)

        # Seleciona "Todos" por padrão
        self._buttons["all"].setChecked(True)

        # Inicializa o tema padrão como escuro
        self.set_theme("dark")

    def set_theme(self, theme: str) -> None:
        """Aplica folha de estilo específica da barra lateral dependendo do tema ativo."""
        if theme == "light":
            title_color = "#1A1A1A"
            stats_color = "#555555"
            opds_color = "#555555"
            opds_border = "#d4d4d8"
        elif theme == "sepia":
            title_color = "#433422"
            stats_color = "#705E4B"
            opds_color = "#433422"
            opds_border = "#d4cbb8"
        else: # dark
            title_color = "#e4e4e7"
            stats_color = "#52525b"
            opds_color = "#a1a1aa"
            opds_border = "#3f3f46"

        self._title.setStyleSheet(f"color: {title_color}; padding: 0 4px 16px 4px;")
        self._stats_label.setStyleSheet(f"color: {stats_color}; font-size: 11px; padding: 8px 4px;")
        self._opds_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid {opds_border}; border-radius: 6px; color: {opds_color}; padding: 6px; }}
            QPushButton:checked {{ background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #10b981; }}
        """)

    def _on_section_click(self, key: str):
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
        self.section_changed.emit(key)

    def update_stats(self, stats: dict):
        """Atualiza estatísticas no rodapé da sidebar."""
        total = stats.get("total", 0)
        reading = stats.get("reading", 0)
        read = stats.get("read", 0)
        self._stats_label.setText(
            f"📊 {total} livros · {reading} lendo · {read} lidos"
        )

    def clear_collections(self):
        """Limpa as coleções carregadas."""
        while self._collections_layout.count():
            item = self._collections_layout.takeAt(0)
            if item.widget():
                key = [k for k, v in self._buttons.items() if v == item.widget()]
                if key:
                    del self._buttons[key[0]]
                item.widget().deleteLater()

    def add_collection_button(self, name: str, collection_id: int):
        """Adiciona um botão de coleção à sidebar."""
        key = f"collection_{collection_id}"
        btn = QPushButton(f"📁  {name}")
        btn.setCheckable(True)
        btn.clicked.connect(lambda checked, k=key: self._on_section_click(k))
        self._collections_layout.addWidget(btn)
        self._buttons[key] = btn
