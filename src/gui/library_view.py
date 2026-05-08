"""Visualização da biblioteca — grade de livros."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QGridLayout,
    QHBoxLayout, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.gui.widgets.book_card import BookCard
from src.utils.constants import CARD_WIDTH, GRID_SPACING


class LibraryView(QWidget):
    """Exibe a biblioteca como uma grade de cards de livros."""

    book_selected = pyqtSignal(int)     # book_id
    book_open = pyqtSignal(int)         # book_id — abre o leitor

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[BookCard] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header com contagem e controles de visualização
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 8)

        self._count_label = QLabel("0 livros")
        self._count_label.setStyleSheet(
            "color: #71717a; font-size: 13px; font-weight: 500;"
        )
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()

        # Botões de visualização
        self._grid_btn = QPushButton("▦")
        self._grid_btn.setToolTip("Visualização em grade")
        self._grid_btn.setFixedSize(32, 32)
        self._grid_btn.setStyleSheet("""
            QPushButton { background: #27272a; border: none; border-radius: 6px;
                          color: #e4e4e7; font-size: 16px; }
            QPushButton:hover { background: #3f3f46; }
        """)
        header_layout.addWidget(self._grid_btn)

        self._list_btn = QPushButton("☰")
        self._list_btn.setToolTip("Visualização em lista")
        self._list_btn.setFixedSize(32, 32)
        self._list_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 6px;
                          color: #71717a; font-size: 16px; }
            QPushButton:hover { background: #27272a; color: #e4e4e7; }
        """)
        header_layout.addWidget(self._list_btn)

        layout.addWidget(header)

        # Área de scroll com grade de cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(24, 8, 24, 24)
        self._grid_layout.setSpacing(GRID_SPACING)
        self._grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        scroll.setWidget(self._grid_container)
        layout.addWidget(scroll)

        # Mensagem de biblioteca vazia
        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_icon = QLabel("📚")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 64px;")
        empty_layout.addWidget(empty_icon)

        empty_text = QLabel("Sua biblioteca está vazia")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_text.setStyleSheet("color: #71717a; font-size: 18px; font-weight: 600;")
        empty_layout.addWidget(empty_text)

        empty_sub = QLabel("Importe livros usando o menu Arquivo → Importar")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_sub.setStyleSheet("color: #52525b; font-size: 13px;")
        empty_layout.addWidget(empty_sub)

        import_btn = QPushButton("📂  Importar Livros")
        import_btn.setObjectName("primaryBtn")
        import_btn.setFixedWidth(200)
        import_btn.clicked.connect(lambda: self.book_open.emit(-1))  # Signal especial
        empty_layout.addWidget(import_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._empty_widget)
        self._empty_widget.hide()

    def load_books(self, books: list[dict]):
        """Carrega a lista de livros na grade."""
        # Limpa grade atual
        self._clear_grid()

        if not books:
            self._empty_widget.show()
            self._count_label.setText("0 livros")
            return

        self._empty_widget.hide()
        self._count_label.setText(
            f"{len(books)} {'livro' if len(books) == 1 else 'livros'}"
        )

        # Calcula colunas baseado na largura disponível
        cols = max(1, (self.width() - 48) // (CARD_WIDTH + GRID_SPACING))

        for i, book in enumerate(books):
            card = BookCard(book)
            card.clicked.connect(self.book_selected.emit)
            card.double_clicked.connect(self.book_open.emit)
            self._cards.append(card)
            row = i // cols
            col = i % cols
            self._grid_layout.addWidget(card, row, col)

    def _clear_grid(self):
        """Remove todos os cards da grade."""
        for card in self._cards:
            self._grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def resizeEvent(self, event):
        """Reorganiza a grade ao redimensionar."""
        super().resizeEvent(event)
        if self._cards:
            books = [card.book_data for card in self._cards]
            self.load_books(books)
