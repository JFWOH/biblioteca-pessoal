"""Diálogo "Atalhos de teclado" (Onda 4, item 4.3).

Lista estática dos atalhos REAIS do app, levantados diretamente do código:
``src/gui/reader_view.py::_setup_shortcuts`` (setas, Space/PageUp/PageDown,
Esc, zoom, busca, marcador, tela cheia) e ``src/gui/main_window.py``
(QActions com ``setShortcut`` no menu + os dois ``QShortcut`` de janela:
Ctrl+B e Ctrl+R). Nenhuma lógica nova — é só uma vitrine somente-leitura.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QWidget, QScrollArea,
)
from PyQt6.QtCore import QSize

# Cada item: (tecla(s) exibida(s), descrição em PT-BR).
_READER_SHORTCUTS = [
    ("→ / Espaço / Page Down", "Próxima página"),
    ("← / Shift+Espaço / Page Up", "Página anterior"),
    ("Esc", "Fechar o leitor / cancelar ação atual"),
    ("Ctrl+=", "Aumentar zoom"),
    ("Ctrl+-", "Diminuir zoom"),
    ("Ctrl+F", "Buscar no documento"),
    ("Ctrl+D", "Marcar/desmarcar a página atual"),
    ("F11", "Alternar tela cheia"),
]

_LIBRARY_SHORTCUTS = [
    ("Ctrl+I", "Importar (diálogo completo)"),
    ("Ctrl+O", "Importar arquivo rápido"),
    ("Ctrl+Shift+O", "Importar pasta"),
]

_GENERAL_SHORTCUTS = [
    ("Ctrl+,", "Abrir Configurações"),
    ("Ctrl+Shift+A", "Abrir o Assistente de Livros (IA)"),
    ("Ctrl+Shift+F", "Abrir Flashcards"),
    ("Ctrl+B", "Mostrar/ocultar a barra lateral"),
    ("Ctrl+R", "Mostrar/ocultar o Assistente IA"),
    ("Ctrl+Q", "Sair do aplicativo"),
    ("F1", "Abrir esta janela de atalhos"),
]

_CATEGORIES = [
    ("Leitor", _READER_SHORTCUTS),
    ("Biblioteca", _LIBRARY_SHORTCUTS),
    ("Geral", _GENERAL_SHORTCUTS),
]


class ShortcutsDialog(QDialog):
    """Diálogo somente-leitura com todos os atalhos de teclado do app."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⌨️ Atalhos de Teclado")
        self.setObjectName("shortcutsDialog")
        self.setMinimumSize(QSize(420, 420))
        self.resize(460, 560)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("⌨️ Atalhos de Teclado")
        title.setObjectName("settingsDialogTitle")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll, stretch=1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        scroll.setWidget(content)

        for category_name, items in _CATEGORIES:
            group = QGroupBox(category_name)
            group.setObjectName("settingsGroup")
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(6)
            for key_text, description in items:
                row = QHBoxLayout()
                key_label = QLabel(key_text)
                key_label.setObjectName("shortcutKeyBadge")
                key_label.setMinimumWidth(150)
                row.addWidget(key_label)
                desc_label = QLabel(description)
                desc_label.setWordWrap(True)
                row.addWidget(desc_label, stretch=1)
                group_layout.addLayout(row)
            content_layout.addWidget(group)

        content_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Fechar")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setTabOrder(scroll, close_btn)
