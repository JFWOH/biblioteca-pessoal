"""Widget de busca dentro do documento (Ctrl+F overlay)."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal


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
                background-color: #161920;
                border-bottom: 1px solid #2d333f;
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
                background: #0f1115;
                border: 1px solid #2d333f;
                border-radius: 6px;
                padding: 6px 12px;
                color: #e5e7eb;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #10b981;
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
                background: #20242d; border: none; border-radius: 4px;
                color: #e5e7eb; font-size: 12px; padding: 4px 8px;
                min-width: 28px; min-height: 28px;
            }
            QPushButton:hover { background: #2d333f; }
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
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #71717a; font-size: 14px;
            }
            QPushButton:hover { color: #e4e4e7; }
        """)
        self._close_btn.clicked.connect(self.close_bar)
        layout.addWidget(self._close_btn)
        
        self._theme_count_color = "#10b981"

    def set_theme(self, theme: str):
        if theme == "light":
            bg_bar = "#f4f4f5"
            border_bar = "#e4e4e7"
            bg_input = "#ffffff"
            border_input = "#d4d4d8"
            focus_input = "#059669"
            text_main = "#1A1A1A"
            btn_bg = "#e4e4e7"
            btn_hover = "#d4d4d8"
            btn_text = "#1A1A1A"
            count_color = "#059669"
        elif theme == "sepia":
            bg_bar = "#ebe5d9"
            border_bar = "#d4cbb8"
            bg_input = "#EADFCA"
            border_input = "#d4cbb8"
            focus_input = "#059669"
            text_main = "#433422"
            btn_bg = "#dfd8c8"
            btn_hover = "#d4cbb8"
            btn_text = "#433422"
            count_color = "#059669"
        else: # dark
            bg_bar = "#161920"
            border_bar = "#2d333f"
            bg_input = "#0f1115"
            border_input = "#2d333f"
            focus_input = "#10b981"
            text_main = "#e5e7eb"
            btn_bg = "#20242d"
            btn_hover = "#2d333f"
            btn_text = "#e5e7eb"
            count_color = "#10b981"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_bar};
                border-bottom: 1px solid {border_bar};
            }}
        """)
        
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {bg_input};
                border: 1px solid {border_input};
                border-radius: 6px;
                padding: 6px 12px;
                color: {text_main};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {focus_input};
            }}
        """)

        btn_style = f"""
            QPushButton {{
                background: {btn_bg}; border: none; border-radius: 4px;
                color: {btn_text}; font-size: 12px; padding: 4px 8px;
                min-width: 28px; min-height: 28px;
            }}
            QPushButton:hover {{ background: {btn_hover}; }}
            QPushButton:disabled {{ color: #a1a1aa; }}
        """
        self._prev_btn.setStyleSheet(btn_style)
        self._next_btn.setStyleSheet(btn_style)

        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {btn_text}; font-size: 14px;
            }}
            QPushButton:hover {{ color: #ef4444; }}
        """)
        
        self._theme_count_color = count_color
        self._update_count()

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
                f"color: {self._theme_count_color}; font-size: 12px; border: none; min-width: 60px;"
            )
        elif self._input.text().strip():
            self._count_label.setText("0 resultados")
            self._count_label.setStyleSheet(
                "color: #ef4444; font-size: 12px; border: none; min-width: 60px;"
            )
        else:
            self._count_label.setText("")
