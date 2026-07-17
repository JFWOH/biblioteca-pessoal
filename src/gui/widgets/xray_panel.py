"""Painel X-Ray da página (Tarefa 3.2) — SEM LLM, só o grafo de conceitos.

Mostra os conceitos do livro atual que aparecem NA PÁGINA ATUAL e, ao expandir
cada conceito, onde mais ele aparece na biblioteca (outros livros + contagem de
menções). Clicar num livro relacionado navega para ele (``open_book_requested``).

Degradação graciosa (ADR-005): sem grafo / livro ainda não ingerido / página sem
conceitos → estado vazio explicativo, nunca crash. A lógica de interseção
página×conceitos vive em ``src/core/xray.py`` (puro); aqui só orquestramos a GUI
e as consultas de leitura ao ``GraphStore`` via as tools do RAG (ADR-001).

Performance: os conceitos do livro são buscados 1x por livro (cache), e a
interseção roda a cada virada de página (barato — string matching). A consulta
"onde mais aparece" só ocorre sob demanda, ao expandir um conceito (lazy).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.rag.tools.graph_tools import graph_book_concepts, graph_concept_lookup
from src.core.xray import page_concepts

# Papéis de dados nos itens da árvore.
_ROLE_KIND = Qt.ItemDataRole.UserRole          # "concept" | "book"
_ROLE_BOOK = Qt.ItemDataRole.UserRole + 1       # book_id (int) para itens "book"
_ROLE_CONCEPT = Qt.ItemDataRole.UserRole + 2    # nome do conceito para itens "concept"
_ROLE_LOADED = Qt.ItemDataRole.UserRole + 3     # bool: filhos já carregados


class XRayPanel(QWidget):
    """Aba "X-Ray" do painel lateral do leitor.

    Signals:
        open_book_requested(int): book_id de um livro relacionado a ser aberto.
    """

    open_book_requested = pyqtSignal(int)

    _CONCEPT_LIMIT = 50   # top-N conceitos do livro considerados na interseção
    _RELATED_LIMIT = 12   # máx. de livros relacionados por conceito

    def __init__(self, graph_store=None, parent=None) -> None:
        super().__init__(parent)
        self._store = graph_store
        self._book_id: int = 0
        self._current_theme = "dark"
        # book_id -> lista de conceitos (data de graph_book_concepts). Cache p/
        # não bater no grafo a cada virada de página.
        self._concepts_cache: dict[int, list] = {}
        self._setup_ui()

    # ── Construção ──────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._title = QLabel("🔬 X-Ray da Página")
        self._title.setObjectName("xrayTitle")
        root.addWidget(self._title)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # Página 0 — árvore de conceitos → livros relacionados.
        self._tree = QTreeWidget()
        self._tree.setObjectName("xrayTree")
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setUniformRowHeights(True)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._stack.addWidget(self._tree)

        # Página 1 — estado vazio (explicativo).
        self._empty = QLabel()
        self._empty.setObjectName("xrayEmpty")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._stack.addWidget(self._empty)

        self._show_empty("Abra um livro para ver o X-Ray da página.")

    # ── API pública (orquestrada pelo reader_view) ──────────────────────────

    def set_graph_store(self, store) -> None:
        """Define/troca o GraphStore e invalida o cache de conceitos."""
        self._store = store
        self._concepts_cache.clear()

    def update_context(self, book_id: int, page: int, page_text: str) -> None:
        """Atualiza o X-Ray para a página atual do livro (chamado a cada página).

        ``page`` é informativo; a interseção usa apenas ``page_text``.
        """
        self._book_id = int(book_id or 0)
        concepts = self._book_concepts(self._book_id)
        if not concepts:
            self._show_empty(
                "Livro ainda não analisado pelo grafo.\n\n"
                "Os conceitos aparecem aqui conforme você lê e o grafo de "
                "conceitos é construído em segundo plano."
            )
            return
        matched = page_concepts(page_text or "", concepts)
        if not matched:
            self._show_empty("Nenhum conceito do livro foi identificado nesta página.")
            return
        self._populate(matched)

    def clear(self) -> None:
        """Limpa a árvore e volta ao estado vazio inicial."""
        self._tree.clear()
        self._show_empty("Abra um livro para ver o X-Ray da página.")

    def set_theme(self, theme: str) -> None:
        """Compat com reader_view.set_theme. O visual vem do QSS global por
        objectName (styles.py, 3 temas); só guardamos o tema atual."""
        self._current_theme = theme

    # ── Internos ────────────────────────────────────────────────────────────

    def _book_concepts(self, book_id: int) -> list:
        if not book_id or self._store is None:
            return []
        if book_id in self._concepts_cache:
            return self._concepts_cache[book_id]
        data: list = []
        try:
            out = graph_book_concepts(self._store, book_id, limit=self._CONCEPT_LIMIT)
            if isinstance(out, dict):
                data = out.get("data") or []
        except Exception:
            data = []  # ADR-005: qualquer falha do grafo → estado vazio
        self._concepts_cache[book_id] = data
        return data

    def _populate(self, matched: list) -> None:
        self._tree.clear()
        for c in matched:
            name = c.get("concept", "") if isinstance(c, dict) else str(c)
            if not name:
                continue
            item = QTreeWidgetItem([name])
            item.setData(0, _ROLE_KIND, "concept")
            item.setData(0, _ROLE_CONCEPT, name)
            item.setData(0, _ROLE_LOADED, False)
            item.setToolTip(0, f"Onde mais “{name}” aparece na biblioteca")
            # Filho placeholder p/ exibir a seta de expandir (removido no expand).
            item.addChild(QTreeWidgetItem(["…"]))
            self._tree.addTopLevelItem(item)
        self._stack.setCurrentWidget(self._tree)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.data(0, _ROLE_KIND) != "concept" or item.data(0, _ROLE_LOADED):
            return
        item.setData(0, _ROLE_LOADED, True)
        item.takeChildren()  # remove o placeholder
        concept = item.data(0, _ROLE_CONCEPT) or ""
        for b in self._related_books(concept):
            title = b.get("title", "?")
            bid = b.get("book_id")
            mentions = b.get("mentions", 0)
            child = QTreeWidgetItem([f"📖 {title}  ·  {mentions}×"])
            if bid is not None:
                child.setData(0, _ROLE_KIND, "book")
                child.setData(0, _ROLE_BOOK, int(bid))
                child.setToolTip(0, "Clique para abrir este livro")
            item.addChild(child)
        if item.childCount() == 0:
            placeholder = QTreeWidgetItem(["(não aparece em outros livros)"])
            placeholder.setDisabled(True)
            item.addChild(placeholder)

    def _related_books(self, concept: str) -> list:
        if self._store is None or not concept:
            return []
        data: list = []
        try:
            out = graph_concept_lookup(self._store, concept, limit=self._RELATED_LIMIT)
            if isinstance(out, dict):
                data = out.get("data") or []
        except Exception:
            data = []
        # "onde MAIS aparece" → exclui o próprio livro atual.
        return [b for b in data if b.get("book_id") != self._book_id]

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int = 0) -> None:
        if item is None:
            return
        kind = item.data(0, _ROLE_KIND)
        if kind == "book":
            bid = item.data(0, _ROLE_BOOK)
            if bid is not None:
                self.open_book_requested.emit(int(bid))
        elif kind == "concept":
            # Clique no conceito expande/recolhe (lazy-load via itemExpanded).
            item.setExpanded(not item.isExpanded())

    def _show_empty(self, message: str) -> None:
        self._empty.setText(message)
        self._stack.setCurrentWidget(self._empty)
