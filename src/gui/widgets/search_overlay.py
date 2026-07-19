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
        self.setObjectName("documentSearchBar")
        # Sem este atributo, QWidget SUBCLASSE não pinta background vindo de
        # QSS (#documentSearchBar { background-color } seria regra morta) —
        # mesma lição do AnnotationPanel (Onda 0b 1/2, PR #42/#43).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        # Ícone
        icon = QLabel("🔍")
        icon.setObjectName("searchBarIcon")
        layout.addWidget(icon)

        # Campo de busca
        self._input = QLineEdit()
        self._input.setPlaceholderText("Buscar no documento...")
        self._input.setObjectName("searchBarInput")
        self._input.returnPressed.connect(self._on_search)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input, stretch=1)

        # Contagem de resultados — cor muda com o ESTADO (achou/zerou), não só
        # o tema: property "state" + seletor QSS, mesmo padrão de
        # BookCard[selected="true"].
        self._count_label = QLabel()
        self._count_label.setObjectName("searchCountLabel")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._count_label)

        # Navegação
        self._prev_btn = QPushButton("▲")
        self._prev_btn.setObjectName("searchNavBtn")
        self._prev_btn.setToolTip("Resultado anterior (Shift+Enter)")
        self._prev_btn.clicked.connect(self._go_prev)
        self._prev_btn.setEnabled(False)
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("▼")
        self._next_btn.setObjectName("searchNavBtn")
        self._next_btn.setToolTip("Próximo resultado (Enter)")
        self._next_btn.clicked.connect(self._go_next)
        self._next_btn.setEnabled(False)
        layout.addWidget(self._next_btn)

        # Fechar
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setObjectName("searchBarCloseBtn")
        self._close_btn.clicked.connect(self.close_bar)
        layout.addWidget(self._close_btn)

    def set_theme(self, theme: str):
        """No-op de compat: o tema vem do QSS central da QApplication
        (styles.py, seletores #documentSearchBar/#searchBar*, Onda 0b 2/2) —
        nada a propagar por widget. Mantido porque reader_view chama a cada
        troca de tema."""

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

    def _set_count_state(self, state: str) -> None:
        """Troca a propriedade "state" do label de contagem (achou/zerou) e
        força o repolish do QSS — mesmo padrão de BookCard[selected]."""
        if self._count_label.property("state") == state:
            return  # estado inalterado — evita repolish à toa
        self._count_label.setProperty("state", state)
        self._count_label.style().unpolish(self._count_label)
        self._count_label.style().polish(self._count_label)

    def _update_count(self):
        if self._results:
            self._count_label.setText(
                f"{self._current_index + 1}/{len(self._results)}"
            )
            self._set_count_state("found")
        elif self._input.text().strip():
            self._count_label.setText("0 resultados")
            self._set_count_state("empty")
        else:
            self._count_label.setText("")
