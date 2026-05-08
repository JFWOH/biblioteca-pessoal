"""Widget de busca dentro do documento (Ctrl+F overlay)."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QKeySequence, QShortcut


class DocumentSearchBar(QWidget):
    """Barra de busca overlay para buscar dentro do documento aberto."""

    search_requested = pyqtSignal(str)       # query
    navigate_result = pyqtSignal(int)         # result index
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[dict] = []
        self._current_index = -1
        self.setFixedHeight(48)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e24;
                border-bottom: 1px solid #27272a;
            }
        """)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        # Ícone
        icon = QLabel("🔍")
        icon.setStyleSheet("border: none; font-size: 14px;")
        layout.addWidget(icon)

        # Campo de busca
        self._input = QLineEdit()
        self._input.setPlaceholderText("Buscar no documento...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: #0f0f17;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 6px 12px;
                color: #e4e4e7;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """)
        self._input.returnPressed.connect(self._on_search)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input, stretch=1)

        # Contagem de resultados
        self._count_label = QLabel()
        self._count_label.setStyleSheet(
            "color: #71717a; font-size: 12px; border: none; min-width: 60px;"
        )
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._count_label)

        # Navegação
        btn_style = """
            QPushButton {
                background: #27272a; border: none; border-radius: 4px;
                color: #e4e4e7; font-size: 12px; padding: 4px 8px;
                min-width: 28px; min-height: 28px;
            }
            QPushButton:hover { background: #3f3f46; }
            QPushButton:disabled { color: #52525b; }
        """

        self._prev_btn = QPushButton("▲")
        self._prev_btn.setStyleSheet(btn_style)
        self._prev_btn.setToolTip("Resultado anterior (Shift+Enter)")
        self._prev_btn.clicked.connect(self._go_prev)
        self._prev_btn.setEnabled(False)
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("▼")
        self._next_btn.setStyleSheet(btn_style)
        self._next_btn.setToolTip("Próximo resultado (Enter)")
        self._next_btn.clicked.connect(self._go_next)
        self._next_btn.setEnabled(False)
        layout.addWidget(self._next_btn)

        # Fechar
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #71717a; font-size: 14px;
            }
            QPushButton:hover { color: #e4e4e7; }
        """)
        close_btn.clicked.connect(self.close_bar)
        layout.addWidget(close_btn)

    def show_bar(self):
        """Exibe a barra de busca e foca no input."""
        self.show()
        self._input.setFocus()
        self._input.selectAll()

    def close_bar(self):
        """Oculta a barra de busca."""
        self.hide()
        self._input.clear()
        self._results = []
        self._current_index = -1
        self._update_count()
        self.closed.emit()

    def set_results(self, results: list[dict]):
        """Define os resultados da busca."""
        self._results = results
        self._current_index = 0 if results else -1
        self._update_count()
        self._prev_btn.setEnabled(len(results) > 1)
        self._next_btn.setEnabled(len(results) > 1)

        if results and self._current_index >= 0:
            self.navigate_result.emit(self._current_index)

    def _on_search(self):
        query = self._input.text().strip()
        if query:
            self.search_requested.emit(query)

    def _on_text_changed(self, text: str):
        if len(text) >= 2:
            self.search_requested.emit(text)
        elif not text:
            self._results = []
            self._current_index = -1
            self._update_count()

    def _go_next(self):
        if self._results:
            self._current_index = (self._current_index + 1) % len(self._results)
            self._update_count()
            self.navigate_result.emit(self._current_index)

    def _go_prev(self):
        if self._results:
            self._current_index = (self._current_index - 1) % len(self._results)
            self._update_count()
            self.navigate_result.emit(self._current_index)

    def _update_count(self):
        if self._results:
            self._count_label.setText(
                f"{self._current_index + 1}/{len(self._results)}"
            )
            self._count_label.setStyleSheet(
                "color: #818cf8; font-size: 12px; border: none; min-width: 60px;"
            )
        elif self._input.text().strip():
            self._count_label.setText("0 resultados")
            self._count_label.setStyleSheet(
                "color: #ef4444; font-size: 12px; border: none; min-width: 60px;"
            )
        else:
            self._count_label.setText("")
