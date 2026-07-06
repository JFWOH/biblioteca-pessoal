"""Barra de busca com filtros."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QComboBox
from PyQt6.QtCore import pyqtSignal, QTimer


class SearchBar(QWidget):
    """Barra de busca com filtros de formato e status."""

    search_changed = pyqtSignal(str, dict)  # query, filters

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_search)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Campo de busca
        self._input = QLineEdit()
        self._input.setObjectName("searchBar")
        self._input.setPlaceholderText("🔍  Buscar livros, autores, temas...")
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(lambda: self._debounce_timer.start())
        layout.addWidget(self._input, stretch=1)

        # Filtro de formato
        self._format_filter = QComboBox()
        self._format_filter.addItem("Todos os formatos", "")
        self._format_filter.addItem("PDF", "pdf")
        self._format_filter.addItem("EPUB", "epub")
        self._format_filter.addItem("MOBI", "mobi")
        self._format_filter.addItem("TXT", "txt")
        self._format_filter.addItem("DOCX", "docx")
        self._format_filter.setFixedWidth(150)
        self._format_filter.currentIndexChanged.connect(lambda: self._debounce_timer.start())
        self._format_filter.setObjectName("formatFilter")
        layout.addWidget(self._format_filter)

    def _emit_search(self):
        query = self._input.text().strip()
        filters = {}
        fmt = self._format_filter.currentData()
        if fmt:
            filters["format"] = fmt
        self.search_changed.emit(query, filters)

    def clear(self):
        self._input.clear()
        self._format_filter.setCurrentIndex(0)

    def set_focus(self):
        self._input.setFocus()
