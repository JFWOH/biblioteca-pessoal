"""Visualização da biblioteca — grade de livros com suporte a seleção múltipla."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QGridLayout,
    QHBoxLayout, QPushButton, QFrame, QProgressBar, QComboBox, QSizePolicy,
    QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor

from src.gui.widgets.book_card import BookCard
from src.gui.styles import emoji_icon
from src.utils.constants import CARD_WIDTH, GRID_SPACING

# ── Dimensões do card compacto da prateleira "Continuar lendo" ─────────────
CONTINUE_CARD_W = 120
CONTINUE_CARD_H = 206  # soma exata do conteúdo (capa+título+barra+meta+margens)
CONTINUE_THUMB_W = 100
CONTINUE_THUMB_H = 128


class _ContinueReadingCard(QWidget):
    """Card compacto da prateleira "Continuar lendo" (capa + título + progresso).

    Variante enxuta do ``BookCard``: além do essencial, exibe a barra de
    progresso da leitura — o dado central desta prateleira, que o ``BookCard``
    padrão não mostra. Reutilizar o ``BookCard`` (fixo em 180×300 e sem
    progresso) deixaria a faixa alta demais e sem a informação-chave; por isso
    um card próprio, definido aqui em ``library_view`` (whitelist), sem tocar
    em ``book_card.py``. Emite os mesmos sinais que o ``BookCard``
    (``clicked``/``double_clicked``) para reaproveitar o roteamento existente.
    """

    clicked = pyqtSignal(int)          # book_id — clique simples seleciona
    double_clicked = pyqtSignal(int)   # book_id — duplo clique abre o leitor
    # book_id, ação escolhida no menu de contexto (débito da Onda 2 — a
    # prateleira não tinha menu de botão direito): mesmo vocabulário do
    # BookCard.context_action ("open"/"favorite"/"collection"/
    # "fetch_metadata"/"delete"), acrescido de "details" (mostrar o painel
    # de detalhes — o que o clique simples já faz, mas sem exigir o clique).
    context_action = pyqtSignal(int, str)

    def __init__(self, book: dict, parent=None):
        super().__init__(parent)
        self._book = book
        self._book_id = book.get("id", 0)
        self.setObjectName("continueCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(CONTINUE_CARD_W, CONTINUE_CARD_H)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        cover = QLabel()
        cover.setFixedSize(CONTINUE_THUMB_W, CONTINUE_THUMB_H)
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_path = book.get("cover_path", "")
        pixmap = QPixmap(cover_path) if cover_path else QPixmap()
        if not pixmap.isNull():
            cover.setPixmap(
                pixmap.scaled(
                    CONTINUE_THUMB_W, CONTINUE_THUMB_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            cover.setObjectName("continueCardCover")
        else:
            cover.setText("📖")
            cover.setObjectName("continueCardCoverPlaceholder")
        layout.addWidget(cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(book.get("title", "Sem título"))
        title.setObjectName("continueCardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(28)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)

        pct = int(round(book.get("percentage", 0) or 0))
        pct = max(0, min(100, pct))

        bar = QProgressBar()
        bar.setObjectName("continueProgress")
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        layout.addWidget(bar)

        meta = QLabel(self._meta_text(book, pct))
        meta.setObjectName("continueCardMeta")
        layout.addWidget(meta)

        layout.addStretch()

    @staticmethod
    def _meta_text(book: dict, pct: int) -> str:
        cur = book.get("current_page") or 0
        total = book.get("total_pages") or 0
        if total > 0:
            return f"{pct}% · pág. {cur}/{total}"
        return f"{pct}%"

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._book_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._book_id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Botão direito: espelha o menu do ``BookCard`` normal (débito da
        Onda 2 — a prateleira não tinha menu de contexto), adaptado ao
        contexto de "livro em andamento" ("Abrir" vira "Continuar lendo";
        ganha "Detalhes", já que aqui o clique simples SELECIONA em vez de
        abrir o painel isoladamente)."""
        menu = self._build_context_menu()
        chosen = menu.exec(self.mapToGlobal(event.pos()))
        try:
            self._handle_context_action(chosen)
        except RuntimeError:
            # A prateleira é RECRIADA (deleteLater) a cada _load_library em
            # background (auto-import/metadados); se isso ocorrer com o menu
            # aberto, o wrapper C++ deste card já morreu quando exec retorna
            # — descarta a ação em vez de propagar o RuntimeError.
            pass

    def _build_context_menu(self) -> QMenu:
        """Monta o QMenu de contexto. Separado de ``contextMenuEvent`` (como
        em ``BookCard``) para ser testável sem chamar ``exec()``."""
        menu = QMenu(self)
        menu.setObjectName("continueCardContextMenu")

        self._ctx_open = menu.addAction("▶️ Continuar lendo")
        self._ctx_details = menu.addAction("ℹ️ Detalhes")
        fav_label = "☆ Desfavoritar" if self._book.get("is_favorite") else "⭐ Favoritar"
        self._ctx_favorite = menu.addAction(fav_label)
        self._ctx_collection = menu.addAction("📁 Adicionar à coleção…")
        self._ctx_metadata = menu.addAction("🌐 Buscar metadados")
        menu.addSeparator()
        self._ctx_delete = menu.addAction("🗑️ Remover")
        return menu

    def _handle_context_action(self, chosen) -> None:
        """Traduz a QAction escolhida (ou None) no sinal
        ``context_action(book_id, action)``."""
        if chosen is None:
            return
        mapping = {
            self._ctx_open: "open",
            self._ctx_details: "details",
            self._ctx_favorite: "favorite",
            self._ctx_collection: "collection",
            self._ctx_metadata: "fetch_metadata",
            self._ctx_delete: "delete",
        }
        action = mapping.get(chosen)
        if action:
            self.context_action.emit(self._book_id, action)


class LibraryView(QWidget):
    """Exibe a biblioteca como uma grade de cards de livros.

    Suporta seleção múltipla (Ctrl+Click) e exclusão em lote de livros
    com caminhos quebrados ou selecionados pelo usuário.
    """

    book_selected = pyqtSignal(int)          # book_id — clique simples
    book_open = pyqtSignal(int)              # book_id — abre o leitor
    bulk_delete_requested = pyqtSignal(list) # list[int] — ids a excluir
    sort_changed = pyqtSignal(str, str)      # sort_by, sort_order ("asc"/"desc")
    # Ações do menu de contexto do card (Tarefa 2.5), repassadas 1:1 aos
    # handlers que o MainWindow já usa para o BookDetails — sem duplicar
    # lógica de negócio aqui.
    favorite_toggle_requested = pyqtSignal(int)   # book_id
    add_to_collection_requested = pyqtSignal(int) # book_id
    fetch_metadata_requested = pyqtSignal(int)    # book_id
    delete_requested = pyqtSignal(int)            # book_id — exclusão única

    # Colunas de ordenação exibidas no combo do header — MESMOS valores de
    # settings_dialog.py (fonte única com library.sort_by/library.sort_order
    # em config.py, Tarefa 2.3).
    _SORT_OPTIONS = [
        ("Data de adição", "date_added"),
        ("Última atividade", "date_modified"),
        ("Título", "title"),
        ("Autor", "author"),
        ("Avaliação", "rating"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[BookCard] = []
        self._selected_ids: set[int] = set()
        self._is_search_result = False
        # Última lista efetivamente renderizada pela grade (ajustes pós-teste,
        # jul/2026): base do atalho de ``load_books`` que evita destruir e
        # recriar todos os cards quando NADA mudou desde a última renderização.
        self._rendered_books: list[dict] = []
        # Nº de colunas da última renderização (perf/gui — reciclagem): a
        # posição do card i é (i // cols, i % cols), então os cards existentes
        # só precisam de re-layout quando ``cols`` muda (reflow no resize).
        self._grid_cols: int = 0
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
        self._count_label.setObjectName("libraryCountLabel")
        header_layout.addWidget(self._count_label)

        # Título da prateleira "Continuar lendo" na MESMA linha da contagem
        # (ajuste de layout 2026-07-17: a faixa ocupava uma linha própria com
        # vãos verticais — o usuário pediu a informação compartilhando a linha
        # do header). Visível só quando a prateleira aparece.
        self._continue_title_lbl = QLabel("·  Continuar lendo")
        self._continue_title_lbl.setObjectName("continueShelfTitle")
        self._continue_title_lbl.hide()
        header_layout.addSpacing(10)
        header_layout.addWidget(self._continue_title_lbl)
        header_layout.addStretch()

        # Ordenação (Tarefa 2.3): combo + botão asc/desc. Persistência nas
        # MESMAS chaves library.sort_by/library.sort_order do settings_dialog
        # — quem grava/recarrega é o MainWindow (fonte única de verdade).
        self._sort_combo = QComboBox()
        self._sort_combo.setObjectName("librarySortCombo")
        for label, value in self._SORT_OPTIONS:
            self._sort_combo.addItem(label, value)
        self._sort_combo.setFixedWidth(150)
        self._sort_combo.currentIndexChanged.connect(self._emit_sort_changed)
        header_layout.addWidget(self._sort_combo)

        self._sort_order_btn = QPushButton("↓")
        self._sort_order_btn.setObjectName("librarySortOrderBtn")
        self._sort_order_btn.setCheckable(True)
        self._sort_order_btn.setFixedSize(28, 28)
        self._sort_order_btn.setToolTip("Ordem decrescente")
        self._sort_order_btn.setAccessibleName("Inverter ordem de classificação")
        self._sort_order_btn.toggled.connect(self._on_sort_order_toggled)
        header_layout.addWidget(self._sort_order_btn)

        # Botão "Mostrar apenas quebrados"
        self._broken_btn = QPushButton("Mostrar quebrados")
        self._broken_btn.setIcon(emoji_icon("⚠️", 14))
        self._broken_btn.setCheckable(True)
        self._broken_btn.setAccessibleName("Mostrar apenas livros com caminho quebrado")
        self._broken_btn.setFixedHeight(28)
        self._broken_btn.setObjectName("libraryBrokenBtn")
        self._broken_btn.toggled.connect(self._on_broken_filter_toggled)
        header_layout.addWidget(self._broken_btn)

        # Botões de visualização
        self._grid_btn = QPushButton("▦")
        self._grid_btn.setToolTip("Visualização em grade")
        self._grid_btn.setAccessibleName("Visualização em grade")
        self._grid_btn.setFixedSize(32, 32)
        self._grid_btn.setObjectName("libraryGridBtn")
        header_layout.addWidget(self._grid_btn)

        self._list_btn = QPushButton("☰")
        self._list_btn.setToolTip("Visualização em lista")
        self._list_btn.setAccessibleName("Visualização em lista")
        self._list_btn.setFixedSize(32, 32)
        self._list_btn.setObjectName("libraryListBtn")
        header_layout.addWidget(self._list_btn)

        # Ordem de tabulação curada do header (Onda 4, item 4.5): ordenação →
        # asc/desc → quebrados → grade → lista. O campo de busca (SearchBar)
        # é um widget IRMÃO fora do LibraryView (instanciado em
        # MainWindow._setup_ui, acima do splitter da biblioteca) — encadeá-lo
        # aqui exigiria tocar a construção de UI do main_window.py, fora do
        # escopo desta Onda (whitelist restringe main_window.py a "menu Ajuda
        # + integração"). Documentado como não coberto.
        self.setTabOrder(self._sort_combo, self._sort_order_btn)
        self.setTabOrder(self._sort_order_btn, self._broken_btn)
        self.setTabOrder(self._broken_btn, self._grid_btn)
        self.setTabOrder(self._grid_btn, self._list_btn)

        layout.addWidget(header)

        # ── Prateleira "Continuar lendo" (topo, acima da grade) ──────────────
        # Só aparece quando há livros em progresso E a seção é "all" — o
        # MainWindow controla isso via load_continue_reading([]) nas demais.
        self._continue_widget = QWidget()
        self._continue_widget.setObjectName("continueShelf")
        cont_layout = QVBoxLayout(self._continue_widget)
        # Faixa compacta: o título mora no header (mesma linha da contagem),
        # então a prateleira é só a fileira de cards, colada ao header.
        cont_layout.setContentsMargins(24, 0, 24, 4)
        cont_layout.setSpacing(0)

        self._continue_scroll = QScrollArea()
        self._continue_scroll.setObjectName("continueShelfScroll")
        self._continue_scroll.setWidgetResizable(True)
        self._continue_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._continue_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._continue_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._continue_scroll.setFixedHeight(CONTINUE_CARD_H + 14)

        self._continue_container = QWidget()
        self._continue_layout = QHBoxLayout(self._continue_container)
        self._continue_layout.setContentsMargins(0, 0, 0, 0)
        self._continue_layout.setSpacing(GRID_SPACING)
        # AlignTop: a folga do viewport (espaço da barra de rolagem) fica toda
        # ABAIXO dos cards, colando-os no header — faixa visualmente menor.
        self._continue_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._continue_scroll.setWidget(self._continue_container)
        cont_layout.addWidget(self._continue_scroll)

        self._continue_cards: list[_ContinueReadingCard] = []
        self._continue_widget.hide()
        # Política vertical FIXED: sem isto o QVBoxLayout distribui espaço
        # excedente também para a faixa (Preferred cresce), esticando-a de
        # ~224px para 400+px com vazios acima/abaixo do scroll interno —
        # medido pela sonda offscreen em 2026-07-17 (faixa 423px, scroll a
        # y=99). Todo o excedente deve ir para a GRADE (stretch=1 abaixo).
        self._continue_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self._continue_widget)

        # ── Barra de ação em lote (flutuante, visível ao selecionar) ─────────
        self._bulk_bar = QFrame()
        self._bulk_bar.setObjectName("bulkBar")
        self._bulk_bar.setFixedHeight(48)
        bulk_layout = QHBoxLayout(self._bulk_bar)
        bulk_layout.setContentsMargins(24, 0, 24, 0)
        bulk_layout.setSpacing(12)

        self._sel_count_lbl = QLabel("0 livros selecionados")
        self._sel_count_lbl.setObjectName("librarySelCountLbl")
        bulk_layout.addWidget(self._sel_count_lbl)
        bulk_layout.addStretch()

        select_broken_btn = QPushButton("Selecionar quebrados")
        select_broken_btn.setIcon(emoji_icon("☠️", 14))
        select_broken_btn.setFixedHeight(30)
        select_broken_btn.setObjectName("librarySelectBrokenBtn")
        select_broken_btn.clicked.connect(self._select_all_broken)
        bulk_layout.addWidget(select_broken_btn)

        # Emoji vai como ÍCONE (setIcon), nunca embutido no texto: no Windows o
        # emoji-no-texto renderiza sobreposto ao rótulo (bug visual). Ver
        # src/gui/styles.py::emoji_icon (mesma correção da Onda 0.1).
        delete_btn = QPushButton("Excluir Selecionados")
        delete_btn.setIcon(emoji_icon("🗑️", 14))
        delete_btn.setFixedHeight(30)
        delete_btn.setObjectName("libraryBulkDeleteBtn")
        delete_btn.clicked.connect(self._on_bulk_delete_clicked)
        bulk_layout.addWidget(delete_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setIcon(emoji_icon("✕", 12))
        cancel_btn.setFixedHeight(30)
        cancel_btn.setObjectName("libraryBulkCancelBtn")
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
        layout.addWidget(scroll, stretch=1)

        # ── Estado vazio ──────────────────────────────────────────────────────
        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_icon = QLabel("📚")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setObjectName("libraryEmptyIcon")
        empty_layout.addWidget(empty_icon)

        empty_text = QLabel("Sua biblioteca está vazia")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_text.setObjectName("libraryEmptyText")
        empty_layout.addWidget(empty_text)

        empty_sub = QLabel(
            "Importe pelo menu Arquivo → Importar\n"
            "ou arraste arquivos para esta janela"
        )
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_sub.setObjectName("libraryEmptySub")
        empty_layout.addWidget(empty_sub)

        import_btn = QPushButton("Importar Livros")
        import_btn.setIcon(emoji_icon("📂", 14))
        import_btn.setObjectName("primaryBtn")
        import_btn.setFixedWidth(200)
        import_btn.clicked.connect(lambda: self.book_open.emit(-1))
        empty_layout.addWidget(import_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._empty_widget)
        self._empty_widget.hide()

        # ── Estado "busca sem resultado" (Tarefa 2.6) ──────────────────────────
        # Distinto do estado "biblioteca vazia": sem convite de importação,
        # já que os livros existem — só não bateram com a busca/filtro atual.
        self._search_empty_widget = QWidget()
        search_empty_layout = QVBoxLayout(self._search_empty_widget)
        search_empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        search_empty_icon = QLabel("🔍")
        search_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_empty_icon.setObjectName("searchEmptyIcon")
        search_empty_layout.addWidget(search_empty_icon)

        search_empty_text = QLabel("Nenhum resultado para sua busca")
        search_empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_empty_text.setObjectName("searchEmptyText")
        search_empty_layout.addWidget(search_empty_text)

        search_empty_hint = QLabel("Tente outros termos ou limpe a busca")
        search_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_empty_hint.setObjectName("searchEmptyHint")
        search_empty_layout.addWidget(search_empty_hint)

        layout.addWidget(self._search_empty_widget)
        self._search_empty_widget.hide()

        self._all_books: list[dict] = []

    # ── Ordenação (Tarefa 2.3) ──────────────────────────────────────────────

    def _emit_sort_changed(self, *_args):
        sort_by = self._sort_combo.currentData()
        sort_order = "asc" if self._sort_order_btn.isChecked() else "desc"
        self.sort_changed.emit(sort_by, sort_order)

    def _on_sort_order_toggled(self, checked: bool):
        self._sort_order_btn.setText("↑" if checked else "↓")
        self._sort_order_btn.setToolTip(
            "Ordem crescente" if checked else "Ordem decrescente"
        )
        self._emit_sort_changed()

    def set_sort_state(self, sort_by: str, sort_order: str) -> None:
        """Sincroniza combo/botão de ordenação com a config, SEM emitir
        ``sort_changed`` (evita recarregar a biblioteca em duplicidade —
        quem chama isto já está prestes a carregar os livros com o mesmo
        valor). Usado pelo MainWindow para refletir a config no início."""
        self._sort_combo.blockSignals(True)
        self._sort_order_btn.blockSignals(True)
        try:
            idx = self._sort_combo.findData(sort_by)
            if idx >= 0:
                self._sort_combo.setCurrentIndex(idx)
            ascending = str(sort_order).strip().lower() == "asc"
            self._sort_order_btn.setChecked(ascending)
            self._sort_order_btn.setText("↑" if ascending else "↓")
            self._sort_order_btn.setToolTip(
                "Ordem crescente" if ascending else "Ordem decrescente"
            )
        finally:
            self._sort_combo.blockSignals(False)
            self._sort_order_btn.blockSignals(False)

    # ── API pública ───────────────────────────────────────────────────────────

    def load_books(self, books: list[dict], progress_map: dict | None = None,
                   is_search: bool = False):
        """Carrega a lista de livros na grade.

        ``progress_map`` (book_id → percentual, Tarefa 2.1) enriquece cada
        dict com ``percentage`` antes de criar os cards — consulta em lote
        feita pelo chamador (``LibraryDB.get_progress_map()``); uma consulta
        por card seria inaceitável (N+1).

        ``is_search`` sinaliza que ``books`` é resultado de busca/filtro
        (Tarefa 2.6): uma lista vazia nesse caso mostra o estado "sem
        resultado" em vez do convite de importação da biblioteca vazia.
        """
        if progress_map:
            books = [
                {**b, "percentage": progress_map.get(b.get("id"), b.get("percentage", 0))}
                for b in books
            ]
        self._all_books = books
        self._is_search_result = is_search
        # Rodada A1 (débito Onda 2, "filtro-quebrados-após-busca" — mesma
        # classe de bug do estado vazio de busca, Tarefa 2.6): o filtro
        # "Mostrar quebrados" opera sobre ``self._all_books`` e é aplicado
        # via ``_refresh_grid`` diretamente (fora deste método). Sem este
        # reset, uma nova carga aqui (busca, troca de seção/coleção,
        # reordenação) substitui ``_all_books`` e re-renderiza a lista
        # CHEIA, mas o botão continua marcado — a grade deixa de refletir o
        # que o toggle diz estar filtrando. ``blockSignals`` evita disparar
        # ``_on_broken_filter_toggled`` (que reescreveria ``_is_search_result``
        # acima de volta p/ False mesmo quando ``is_search=True``).
        if self._broken_btn.isChecked():
            self._broken_btn.blockSignals(True)
            self._broken_btn.setChecked(False)
            self._broken_btn.blockSignals(False)
        # Atalho (ajustes pós-teste, jul/2026): se a lista enriquecida é
        # IDÊNTICA (por valor, mesma ordem) à última renderizada, não destrói
        # nem recria os cards — a reconstrução completa custa ~1 ms/card
        # (medido em tools/profile_transitions.py) e era paga à toa nas
        # transições que voltam à biblioteca sem mudança de dados (ex.:
        # estatísticas → biblioteca, assistente → biblioteca). Lista vazia
        # nunca usa o atalho: o widget de estado vazio depende de
        # ``is_search``, que pode ter mudado entre as chamadas.
        if books and self._cards and books == self._rendered_books:
            if self._selected_ids:
                self._clear_selection()
            return
        self._selected_ids.clear()
        self._refresh_grid(books)

    def load_continue_reading(self, books: list[dict]):
        """Preenche (ou esconde) a prateleira "Continuar lendo".

        ``books`` já vem filtrado/ordenado pelo core
        (``LibraryDB.get_in_progress_books``). Lista vazia esconde a faixa —
        é assim que o MainWindow a suprime fora da seção "all" (coleções,
        favoritos, busca): basta chamar ``load_continue_reading([])``.
        """
        self._clear_continue()
        if not books:
            self._continue_widget.hide()
            self._continue_title_lbl.hide()
            return
        for book in books:
            card = _ContinueReadingCard(book)
            card.clicked.connect(self.book_selected.emit)
            card.double_clicked.connect(self.book_open.emit)
            card.context_action.connect(self._on_card_context_action)
            self._continue_cards.append(card)
            self._continue_layout.addWidget(card)
        self._continue_widget.show()
        self._continue_title_lbl.show()

    def _clear_continue(self):
        for card in self._continue_cards:
            self._continue_layout.removeWidget(card)
            card.deleteLater()
        self._continue_cards.clear()

    def _refresh_grid(self, books: list[dict]):
        """Renderiza a grade com a lista fornecida.

        Ajustes pós-teste (jul/2026): a reconstrução acontece com os repaints
        suspensos (``setUpdatesEnabled(False)``) — um único repaint ao final,
        em vez de um por card adicionado/removido durante a transição.

        Rodada 4 (perf/gui): RECICLAGEM in-place. Em vez de destruir e recriar
        TODOS os cards (~1 ms/card), os cards existentes são RECONFIGURADOS por
        posição (``BookCard.update_book``) e só o DELTA de tamanho é
        criado/removido. Como a posição do card i é ``(i // cols, i % cols)``,
        os cards pré-existentes só precisam de re-layout quando ``cols`` muda
        (reflow no ``resizeEvent``) — nunca são destruídos/recriados por isso.
        """
        self._rendered_books = books
        self.setUpdatesEnabled(False)
        try:
            if not books:
                self._clear_grid()
                if self._is_search_result:
                    self._empty_widget.hide()
                    self._search_empty_widget.show()
                else:
                    self._search_empty_widget.hide()
                    self._empty_widget.show()
                self._count_label.setText("0 livros")
                self._update_bulk_bar()
                return

            self._empty_widget.hide()
            self._search_empty_widget.hide()
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
            relayout_existing = cols != self._grid_cols
            self._grid_cols = cols

            # 1) Encolhe: remove só os cards excedentes.
            while len(self._cards) > len(books):
                card = self._cards.pop()
                self._grid_layout.removeWidget(card)
                card.deleteLater()

            # 2) Recicla in-place os existentes (posição a posição).
            for i, card in enumerate(self._cards):
                card.update_book(books[i])

            # 3) Reposiciona os existentes SÓ se o nº de colunas mudou.
            if relayout_existing:
                for i, card in enumerate(self._cards):
                    self._grid_layout.removeWidget(card)
                    self._grid_layout.addWidget(card, i // cols, i % cols)

            # 4) Cresce: cria só o delta.
            for i in range(len(self._cards), len(books)):
                card = BookCard(books[i])
                card.clicked.connect(self._on_card_clicked)
                card.double_clicked.connect(self.book_open.emit)
                card.context_action.connect(self._on_card_context_action)
                self._cards.append(card)
                self._grid_layout.addWidget(card, i // cols, i % cols)

            self._update_bulk_bar()
        finally:
            self.setUpdatesEnabled(True)

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

    def _on_card_context_action(self, book_id: int, action: str) -> None:
        """Repassa a ação do menu de contexto do card (Tarefa 2.5; reutilizado
        também pela prateleira "Continuar lendo" — débito da Onda 2) ao sinal
        correspondente. O MainWindow conecta esses sinais diretamente aos
        handlers que já existem para o BookDetails — nenhuma lógica de
        negócio nova aqui, só o roteamento. "details" (só emitido pelo card
        da prateleira) reaproveita o MESMO sinal ``book_selected`` do clique
        simples num ``BookCard``."""
        if action == "open":
            self.book_open.emit(book_id)
        elif action == "details":
            self.book_selected.emit(book_id)
        elif action == "favorite":
            self.favorite_toggle_requested.emit(book_id)
        elif action == "collection":
            self.add_to_collection_requested.emit(book_id)
        elif action == "fetch_metadata":
            self.fetch_metadata_requested.emit(book_id)
        elif action == "delete":
            self.delete_requested.emit(book_id)

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
        # Auditoria B4: espelha o clear do load_books — a reciclagem
        # (update_book) só reseta o VISUAL de seleção sob a premissa de que a
        # view limpou _selected_ids; sem isto a bulk bar ficaria armada com
        # cards que não parecem selecionados.
        self._selected_ids.clear()
        if checked:
            broken = [b for b in self._all_books
                      if b.get("file_path") and
                      not __import__("pathlib").Path(b["file_path"]).exists()]
            # Filtro sem resultado != biblioteca vazia (Tarefa 2.6): mesmo
            # tratamento do estado "sem resultado" da busca.
            self._is_search_result = True
            self._refresh_grid(broken)
        else:
            self._is_search_result = False
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

