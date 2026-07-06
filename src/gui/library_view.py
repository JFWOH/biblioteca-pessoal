"""Visualização da biblioteca — grade de livros com suporte a seleção múltipla."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QGridLayout,
    QHBoxLayout, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.gui.widgets.book_card import BookCard
from src.utils.constants import CARD_WIDTH, GRID_SPACING


class LibraryView(QWidget):
    """Exibe a biblioteca como uma grade de cards de livros.

    Suporta seleção múltipla (Ctrl+Click) e exclusão em lote de livros
    com caminhos quebrados ou selecionados pelo usuário.
    """

    book_selected = pyqtSignal(int)          # book_id — clique simples
    book_open = pyqtSignal(int)              # book_id — abre o leitor
    bulk_delete_requested = pyqtSignal(list) # list[int] — ids a excluir

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[BookCard] = []
        self._selected_ids: set[int] = set()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 8)

        self._count_label = QLabel("0 livros")
        self._count_label.setStyleSheet(
            "color: #71717a; font-size: 13px; font-weight: 500;"
        )
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()

        # Botão "Mostrar apenas quebrados"
        self._broken_btn = QPushButton("⚠️ Mostrar quebrados")
        self._broken_btn.setCheckable(True)
        self._broken_btn.setFixedHeight(28)
        self._broken_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #52525b;
                border-radius: 6px; color: #71717a;
                font-size: 11px; padding: 0 10px;
            }
            QPushButton:hover { border-color: #f59e0b; color: #f59e0b; }
            QPushButton:checked {
                background: #451a03; border-color: #f59e0b; color: #f59e0b;
            }
        """)
        self._broken_btn.toggled.connect(self._on_broken_filter_toggled)
        header_layout.addWidget(self._broken_btn)

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

        # ── Barra de ação em lote (flutuante, visível ao selecionar) ─────────
        self._bulk_bar = QFrame()
        self._bulk_bar.setObjectName("bulkBar")
        self._bulk_bar.setStyleSheet("""
            QFrame#bulkBar {
                background: #1e1b4b;
                border-top: 1px solid #4338ca;
                border-bottom: 1px solid #4338ca;
            }
        """)
        self._bulk_bar.setFixedHeight(48)
        bulk_layout = QHBoxLayout(self._bulk_bar)
        bulk_layout.setContentsMargins(24, 0, 24, 0)
        bulk_layout.setSpacing(12)

        self._sel_count_lbl = QLabel("0 livros selecionados")
        self._sel_count_lbl.setStyleSheet("color: #818cf8; font-weight: 600;")
        bulk_layout.addWidget(self._sel_count_lbl)
        bulk_layout.addStretch()

        select_broken_btn = QPushButton("☠️ Selecionar quebrados")
        select_broken_btn.setFixedHeight(30)
        select_broken_btn.setStyleSheet("""
            QPushButton { background: #451a03; color: #f59e0b;
                border: 1px solid #92400e; border-radius: 6px;
                font-size: 11px; padding: 0 10px; }
            QPushButton:hover { background: #78350f; }
        """)
        select_broken_btn.clicked.connect(self._select_all_broken)
        bulk_layout.addWidget(select_broken_btn)

        delete_btn = QPushButton("🗑️ Excluir Selecionados")
        delete_btn.setFixedHeight(30)
        delete_btn.setStyleSheet("""
            QPushButton { background: #7f1d1d; color: #fca5a5;
                border: 1px solid #991b1b; border-radius: 6px;
                font-weight: 600; font-size: 11px; padding: 0 12px; }
            QPushButton:hover { background: #991b1b; color: white; }
        """)
        delete_btn.clicked.connect(self._on_bulk_delete_clicked)
        bulk_layout.addWidget(delete_btn)

        cancel_btn = QPushButton("✕ Cancelar")
        cancel_btn.setFixedHeight(30)
        cancel_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #52525b;
                border: 1px solid #3f3f46; border-radius: 6px;
                font-size: 11px; padding: 0 10px; }
            QPushButton:hover { color: #e4e4e7; border-color: #71717a; }
        """)
        cancel_btn.clicked.connect(self._clear_selection)
        bulk_layout.addWidget(cancel_btn)

        self._bulk_bar.hide()
        layout.addWidget(self._bulk_bar)

        # ── Grade de cards ───────────────────────────────────────────────────
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

        # ── Estado vazio ──────────────────────────────────────────────────────
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
        import_btn.clicked.connect(lambda: self.book_open.emit(-1))
        empty_layout.addWidget(import_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._empty_widget)
        self._empty_widget.hide()

        self._all_books: list[dict] = []

    # ── API pública ───────────────────────────────────────────────────────────

    def load_books(self, books: list[dict]):
        """Carrega a lista de livros na grade."""
        self._all_books = books
        self._selected_ids.clear()
        self._refresh_grid(books)

    def _refresh_grid(self, books: list[dict]):
        """Renderiza a grade com a lista fornecida."""
        self._clear_grid()

        if not books:
            self._empty_widget.show()
            self._count_label.setText("0 livros")
            self._update_bulk_bar()
            return

        self._empty_widget.hide()
        total = len(self._all_books)
        shown = len(books)
        if shown < total:
            self._count_label.setText(
                f"{shown} de {total} livros (filtrado)"
            )
        else:
            self._count_label.setText(
                f"{total} {'livro' if total == 1 else 'livros'}"
            )

        cols = max(1, (self.width() - 48) // (CARD_WIDTH + GRID_SPACING))
        for i, book in enumerate(books):
            card = BookCard(book)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self.book_open.emit)
            self._cards.append(card)
            self._grid_layout.addWidget(card, i // cols, i % cols)

        self._update_bulk_bar()

    # ── Seleção ───────────────────────────────────────────────────────────────

    def _on_card_clicked(self, book_id: int):
        """Toggle de seleção + emite book_selected."""
        from PyQt6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._toggle_selection(book_id)
        else:
            self._clear_selection()
            self.book_selected.emit(book_id)

    def _toggle_selection(self, book_id: int):
        card = self._card_by_id(book_id)
        if card is None:
            return
        if book_id in self._selected_ids:
            self._selected_ids.discard(book_id)
            card.set_selected(False)
        else:
            self._selected_ids.add(book_id)
            card.set_selected(True)
        self._update_bulk_bar()

    def _clear_selection(self):
        for card in self._cards:
            card.set_selected(False)
        self._selected_ids.clear()
        self._update_bulk_bar()

    def _select_all_broken(self):
        for card in self._cards:
            if card.is_broken:
                self._selected_ids.add(card._book_id)
                card.set_selected(True)
        self._update_bulk_bar()

    def _card_by_id(self, book_id: int) -> BookCard | None:
        for card in self._cards:
            if card._book_id == book_id:
                return card
        return None

    def _update_bulk_bar(self):
        n = len(self._selected_ids)
        if n > 0:
            self._sel_count_lbl.setText(
                f"{n} {'livro selecionado' if n == 1 else 'livros selecionados'}"
            )
            self._bulk_bar.show()
        else:
            self._bulk_bar.hide()

    def _on_bulk_delete_clicked(self):
        from PyQt6.QtWidgets import QMessageBox
        ids = list(self._selected_ids)
        n = len(ids)
        reply = QMessageBox.warning(
            self,
            "Confirmar Exclusão",
            f"Remover {n} {'livro' if n == 1 else 'livros'} permanentemente?\n\n"
            "Esta ação não pode ser desfeita. Os arquivos no disco NÃO serão excluídos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.bulk_delete_requested.emit(ids)
            self._clear_selection()

    # ── Filtro de quebrados ───────────────────────────────────────────────────

    def _on_broken_filter_toggled(self, checked: bool):
        if checked:
            broken = [b for b in self._all_books
                      if b.get("file_path") and
                      not __import__("pathlib").Path(b["file_path"]).exists()]
            self._refresh_grid(broken)
        else:
            self._refresh_grid(self._all_books)

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _clear_grid(self):
        for card in self._cards:
            self._grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._cards:
            books = [card.book_data for card in self._cards]
            self._refresh_grid(books)

