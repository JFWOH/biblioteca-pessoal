"""Barra lateral de navegação da biblioteca."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


class Sidebar(QWidget):
    """Barra lateral com navegação por seções."""

    section_changed = pyqtSignal(str)  # nome da seção

    SECTIONS = [
        ("all", "📚  Todos os Livros"),
        ("reading", "📖  Lendo"),
        ("unread", "📋  Não Lidos"),
        ("read", "✅  Lidos"),
        ("favorites", "⭐  Favoritos"),
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
        title = QLabel("📚 Biblioteca")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font = title.font()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setStyleSheet("color: #e4e4e7; padding: 0 4px 16px 4px;")
        layout.addWidget(title)

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

        # Seção: Coleções (placeholder para expansão futura)
        layout.addSpacing(16)
        collections_label = QLabel("COLEÇÕES")
        collections_label.setObjectName("sidebarSection")
        layout.addWidget(collections_label)

        add_collection_btn = QPushButton("➕  Nova Coleção")
        add_collection_btn.setObjectName("secondaryBtn")
        layout.addWidget(add_collection_btn)

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

        # Seleciona "Todos" por padrão
        self._buttons["all"].setChecked(True)

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

    def add_collection_button(self, name: str, collection_id: int):
        """Adiciona um botão de coleção à sidebar."""
        # Implementação futura
        pass
