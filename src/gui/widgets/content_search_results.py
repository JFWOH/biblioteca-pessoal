"""Painel de resultados da busca no CONTEÚDO dos livros (Tarefa 5.1).

Lista própria (não a grade de cards da biblioteca): cada resultado é
livro + página + trecho destacado (snippet). Clicar abre o livro na página —
o mesmo caminho da Onda 3 (``_on_rag_source_clicked``). Puramente de
apresentação: recebe os resultados já prontos de ``LibraryDB.fts_search`` (via
MainWindow) e não fala com o banco.
"""

import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.fts_search import SNIPPET_CLOSE, SNIPPET_OPEN
from src.gui.styles import emoji_icon

# Verde-accent do app (igual nos 3 temas) — realce do termo casado no snippet.
_HIGHLIGHT = '<span style="color:#10b981; font-weight:600;">'


class _ResultRow(QFrame):
    """Uma linha clicável: título + página + trecho destacado."""

    clicked = pyqtSignal()

    def __init__(self, book_id: int, page_number: int, title: str,
                 snippet_html: str, parent=None):
        super().__init__(parent)
        self.setObjectName("contentResultRow")
        self.book_id = book_id
        self.page_number = page_number
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        head = QLabel(f"{title}   ·   Página {page_number + 1}")
        head.setObjectName("contentResultBook")
        head.setTextFormat(Qt.TextFormat.PlainText)
        head.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        snip = QLabel(snippet_html)
        snip.setObjectName("contentResultSnippet")
        snip.setTextFormat(Qt.TextFormat.RichText)
        snip.setWordWrap(True)
        snip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lay.addWidget(head)
        lay.addWidget(snip)

    def mousePressEvent(self, ev):  # noqa: N802 (override Qt)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class ContentSearchResults(QWidget):
    """Página de resultados da busca por conteúdo (entra no stack principal)."""

    result_activated = pyqtSignal(int, int)  # book_id, page_number (0-based)
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contentSearchResults")
        self._query = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        # ── Cabeçalho: voltar + título + contagem ──
        header = QHBoxLayout()
        header.setSpacing(12)

        self._back_btn = QPushButton("  Voltar")
        self._back_btn.setObjectName("contentSearchBack")
        self._back_btn.setIcon(emoji_icon("⬅️", 14))
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self._back_btn)

        title = QLabel("Busca no conteúdo")
        title.setObjectName("contentSearchTitle")
        header.addWidget(title)

        header.addStretch(1)

        self._count = QLabel("")
        self._count.setObjectName("contentSearchCount")
        header.addWidget(self._count)
        root.addLayout(header)

        # ── Lista rolável de resultados ──
        self._scroll = QScrollArea()
        self._scroll.setObjectName("contentSearchScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._container.setObjectName("contentSearchContainer")
        self._rows_layout = QVBoxLayout(self._container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        self._rows_layout.addStretch(1)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, stretch=1)

        # ── Rodapé: livros ainda sem índice de conteúdo ──
        self._footer = QLabel("")
        self._footer.setObjectName("contentSearchFooter")
        self._footer.setWordWrap(True)
        self._footer.hide()
        root.addWidget(self._footer)

    # ── API ──────────────────────────────────────────────────────────

    def show_results(self, query: str, results: list[dict],
                     pending_count: int = 0) -> None:
        """Popula a página. ``results`` são dicts de ``fts_search`` enriquecidos
        com ``title`` (resolvido pela MainWindow)."""
        self._query = query or ""
        self._clear_rows()

        n = len(results)
        self._count.setText(
            "Nenhum resultado" if n == 0
            else ("1 resultado" if n == 1 else f"{n} resultados"))

        if not results:
            empty = QLabel(
                f'Nenhuma página encontrada para "{self._query}".\n'
                "Tente outros termos ou verifique se o livro já foi indexado.")
            empty.setObjectName("contentSearchEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            self._rows_layout.insertWidget(0, empty)
        else:
            for i, r in enumerate(results):
                row = _ResultRow(
                    r.get("book_id", 0),
                    int(r.get("page_number", 0) or 0),
                    r.get("title") or "Livro",
                    self._render_snippet(r.get("snippet", "")),
                )
                row.clicked.connect(
                    lambda bid=r.get("book_id", 0),
                    pg=int(r.get("page_number", 0) or 0):
                    self.result_activated.emit(bid, pg))
                self._rows_layout.insertWidget(i, row)

        if pending_count and pending_count > 0:
            plural = "s" if pending_count != 1 else ""
            self._footer.setText(
                f"{pending_count} livro{plural} ainda não indexado{plural} no "
                f"conteúdo — a indexação em segundo plano os cobre aos poucos.")
            self._footer.show()
        else:
            self._footer.hide()

    # ── Internos ─────────────────────────────────────────────────────

    def _render_snippet(self, snippet: str) -> str:
        """Escapa o HTML do trecho e só então troca os marcadores por destaque —
        assim conteúdo do livro com <, > ou & nunca quebra o rich text."""
        esc = html.escape(snippet or "")
        esc = esc.replace(SNIPPET_OPEN, _HIGHLIGHT).replace(SNIPPET_CLOSE, "</span>")
        return esc

    def _clear_rows(self) -> None:
        # Remove tudo menos o stretch final (mantido no fim da lista).
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
