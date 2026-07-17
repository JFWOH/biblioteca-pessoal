"""Painel de Marcadores de página (aba ao lado do Sumário no leitor).

Lista os marcadores do livro (página + trecho curto). Clicar navega; cada
item tem um botão de remover. É um widget puro de apresentação: a persistência
fica no ``LibraryDB`` (tabela ``bookmarks``), orquestrada pelo ``ReaderView``.

Estilização por object-name nos 3 temas de ``styles.py`` (sem QSS inline com
cores hardcoded) — a folha global da QApplication cuida das cores.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal


class BookmarksPanel(QWidget):
    """Lista de marcadores de página do livro atual.

    Sinais:
      - ``bookmark_selected(page)``: pediu para ir à página (0-based).
      - ``bookmark_removed(page)``: pediu para remover o marcador da página.
    A remoção efetiva no banco e a atualização da lista são responsabilidade
    do chamador (``ReaderView``), que reenvia ``set_bookmarks`` depois.
    """

    bookmark_selected = pyqtSignal(int)  # page_number (0-based)
    bookmark_removed = pyqtSignal(int)   # page_number (0-based)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bookmarksPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("Marcadores")
        self._header.setObjectName("bookmarksHeader")
        layout.addWidget(self._header)

        self._empty = QLabel("Nenhum marcador ainda.\nUse o botão de marcador na barra do leitor.")
        self._empty.setObjectName("bookmarksEmpty")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._empty)

        self._list = QListWidget()
        self._list.setObjectName("bookmarksList")
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        layout.addWidget(self._list, stretch=1)

        self._bookmarks: list[dict] = []
        self.set_bookmarks([])

    def set_bookmarks(self, bookmarks: list[dict]) -> None:
        """Recarrega a lista a partir das linhas de ``LibraryDB.get_bookmarks``.

        Cada item: dict com ``page_number`` (0-based) e ``label`` opcional.
        """
        self._bookmarks = list(bookmarks or [])
        self._list.clear()
        has_items = bool(self._bookmarks)
        self._empty.setVisible(not has_items)
        self._list.setVisible(has_items)

        for bm in self._bookmarks:
            page = int(bm.get("page_number", 0))
            label = (bm.get("label") or "").strip()
            row = self._build_row(page, label)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _build_row(self, page: int, label: str) -> QWidget:
        row = QWidget()
        row.setObjectName("bookmarkRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(2)

        text = f"Pág. {page + 1}"
        if label:
            short = label if len(label) <= 42 else label[:41].rstrip() + "…"
            text = f"{text} · {short}"
        goto = QPushButton(text)
        goto.setObjectName("bookmarkGotoBtn")
        goto.setCursor(Qt.CursorShape.PointingHandCursor)
        goto.setToolTip(f"Ir para a página {page + 1}")
        goto.clicked.connect(lambda _checked=False, p=page: self.bookmark_selected.emit(p))
        h.addWidget(goto, stretch=1)

        remove = QPushButton("✕")
        remove.setObjectName("bookmarkRemoveBtn")
        remove.setFixedSize(24, 24)
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setToolTip("Remover marcador")
        remove.clicked.connect(lambda _checked=False, p=page: self.bookmark_removed.emit(p))
        h.addWidget(remove)

        return row

    def set_theme(self, theme: str) -> None:
        """Compat.: o tema é aplicado pela folha global (object-names). No-op.

        Mantido para simetria com os demais painéis do leitor, que expõem
        ``set_theme``. As cores vêm do QSS global da QApplication.
        """
        return None
