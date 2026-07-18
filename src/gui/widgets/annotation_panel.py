"""Painel de anotações, destaques e marcadores."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QComboBox, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class AnnotationItem(QFrame):
    """Widget individual de anotação."""

    delete_requested = pyqtSignal(int)       # annotation_id
    goto_requested = pyqtSignal(int)         # page_number
    rename_requested = pyqtSignal(int, str)  # annotation_id, novo título

    def __init__(self, annotation: dict, parent=None):
        super().__init__(parent)
        self._annotation = annotation
        self.setObjectName("annotationItem")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: tipo + página
        header = QHBoxLayout()
        ann_type = self._annotation.get("annotation_type", "highlight")
        type_icons = {"highlight": "🖍️", "note": "📝", "bookmark": "🔖", "ai_note": "🤖"}
        type_labels = {"highlight": "Destaque", "note": "Nota", "bookmark": "Marcador",
                       "ai_note": "Nota da IA"}

        self._type_lbl = QLabel(f"{type_icons.get(ann_type, '📝')} {type_labels.get(ann_type, ann_type)}")
        self._type_lbl.setObjectName("annotationItemType")
        header.addWidget(self._type_lbl)

        header.addStretch()

        page = self._annotation.get("page_number", 0)
        self._page_btn = QPushButton(f"Pág. {page + 1}")
        self._page_btn.setObjectName("annotationItemPageBtn")
        self._page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._page_btn.clicked.connect(lambda: self.goto_requested.emit(page))
        header.addWidget(self._page_btn)

        layout.addLayout(header)

        # Título (opcional) — destaque acima do conteúdo
        title = self._annotation.get("title", "")
        self._title_item_lbl = None
        if title:
            self._title_item_lbl = QLabel(title)
            self._title_item_lbl.setWordWrap(True)
            self._title_item_lbl.setObjectName("annotationItemTitle")
            layout.addWidget(self._title_item_lbl)

        # Conteúdo
        content = self._annotation.get("content", "")
        self._content_lbl = None
        if content:
            self._content_lbl = QLabel(content)
            self._content_lbl.setWordWrap(True)
            self._content_lbl.setObjectName("annotationItemContent")
            layout.addWidget(self._content_lbl)

        # Cor do destaque — vem do DADO (cor escolhida pelo usuário para a
        # anotação), não do tema: exceção legítima, permanece inline.
        color = self._annotation.get("highlight_color", "#fbbf24")
        if ann_type == "highlight":
            color_bar = QWidget()
            color_bar.setFixedHeight(3)
            color_bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            layout.addWidget(color_bar)

        # Footer: data + deletar
        footer = QHBoxLayout()
        date = self._annotation.get("created_at", "")
        self._date_lbl = None
        if date:
            self._date_lbl = QLabel(date[:16])
            self._date_lbl.setObjectName("annotationItemDate")
            footer.addWidget(self._date_lbl)

        footer.addStretch()

        # Renomear (título) — vale para notas, destaques e notas da IA.
        self._rename_btn = QPushButton("✏️")
        self._rename_btn.setFixedSize(20, 20)
        self._rename_btn.setToolTip("Renomear título")
        self._rename_btn.setObjectName("annotationItemRenameBtn")
        self._rename_btn.clicked.connect(self._on_rename_clicked)
        footer.addWidget(self._rename_btn)

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedSize(20, 20)
        self._del_btn.setObjectName("annotationItemDelBtn")
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._annotation.get("id", 0))
        )
        footer.addWidget(self._del_btn)

        layout.addLayout(footer)

    def _on_rename_clicked(self):
        """Abre um diálogo simples para renomear o título da anotação."""
        from PyQt6.QtWidgets import QInputDialog
        current = self._annotation.get("title", "") or ""
        new_title, ok = QInputDialog.getText(
            self, "Renomear anotação", "Título:", text=current)
        if ok and new_title.strip() != current:
            self.rename_requested.emit(
                self._annotation.get("id", 0), new_title.strip())


class AnnotationPanel(QWidget):
    """Painel lateral para gerenciar anotações de um livro."""

    annotation_deleted = pyqtSignal(int)     # annotation_id
    goto_page = pyqtSignal(int)              # page_number
    annotation_added = pyqtSignal(dict)      # {page, content, type, color}
    annotation_renamed = pyqtSignal(int, str)  # annotation_id, novo título

    HIGHLIGHT_COLORS = [
        ("#fbbf24", "Amarelo"),
        ("#f87171", "Vermelho"),
        ("#34d399", "Verde"),
        ("#60a5fa", "Azul"),
        ("#c084fc", "Roxo"),
        ("#fb923c", "Laranja"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._book_id = 0
        self._current_page = 0
        self.setObjectName("annotationPanel")
        # Sem este atributo, QWidget SUBCLASSE não pinta background vindo de
        # QSS (#annotationPanel { background-color } seria regra morta) — o
        # antigo setStyleSheet inline pintava por cascata; o QSS central não.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Largura mínima razoável; sem máximo, para preencher todo o dock.
        self.setMinimumWidth(240)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Título
        self._title = QLabel("📝 Anotações")
        font = self._title.font()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.Bold)
        self._title.setFont(font)
        self._title.setObjectName("annotationPanelTitle")
        layout.addWidget(self._title)

        # Filtro por tipo
        filter_layout = QHBoxLayout()
        self._type_filter = QComboBox()
        self._type_filter.addItem("Todas", None)
        self._type_filter.addItem("🖍️ Destaques", "highlight")
        self._type_filter.addItem("📝 Notas", "note")
        self._type_filter.addItem("🔖 Marcadores", "bookmark")
        self._type_filter.setObjectName("annotationTypeFilter")
        self._type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._type_filter, stretch=1)
        layout.addLayout(filter_layout)

        # Área de nova anotação
        self._add_frame = QFrame()
        self._add_frame.setObjectName("annotationAddFrame")
        add_layout = QVBoxLayout(self._add_frame)
        add_layout.setContentsMargins(10, 8, 10, 8)
        add_layout.setSpacing(6)

        # Título opcional da nota
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Título da nota (opcional)")
        self._title_input.setObjectName("annotationTitleInput")
        add_layout.addWidget(self._title_input)

        self._note_input = QTextEdit()
        self._note_input.setPlaceholderText("Escreva uma nota para esta página...")
        self._note_input.setFixedHeight(60)
        self._note_input.setObjectName("annotationNoteInput")
        add_layout.addWidget(self._note_input)

        # Cores + botões de ação
        actions = QHBoxLayout()
        actions.setSpacing(4)

        # Seleção de cor — swatch vem do DADO (paleta de destaque), não do
        # tema: exceção legítima, permanece inline (mesmo padrão de TagBadge).
        self._selected_color = "#fbbf24"
        for color, name in self.HIGHLIGHT_COLORS[:4]:
            color_btn = QPushButton()
            color_btn.setFixedSize(22, 22)
            color_btn.setToolTip(name)
            color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}; border: 2px solid transparent;
                    border-radius: 11px;
                }}
                QPushButton:hover {{ border-color: white; }}
            """)
            color_btn.clicked.connect(lambda _, c=color: self._set_color(c))
            actions.addWidget(color_btn)

        actions.addStretch()

        # Botão adicionar nota
        self._add_note_btn = QPushButton("+ Nota")
        self._add_note_btn.setObjectName("annotationAddNoteBtn")
        self._add_note_btn.clicked.connect(self._add_note)
        actions.addWidget(self._add_note_btn)

        # Botão marcador
        self._bookmark_btn = QPushButton("🔖")
        self._bookmark_btn.setFixedSize(28, 28)
        self._bookmark_btn.setToolTip("Adicionar marcador nesta página")
        self._bookmark_btn.setObjectName("annotationBookmarkBtn")
        self._bookmark_btn.clicked.connect(self._add_bookmark)
        actions.addWidget(self._bookmark_btn)

        add_layout.addLayout(actions)
        layout.addWidget(self._add_frame)

        # Lista de anotações (scroll)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_container)

        layout.addWidget(self._scroll, stretch=1)

        # Contagem
        self._count_label = QLabel("0 anotações")
        self._count_label.setObjectName("annotationCountLabel")
        layout.addWidget(self._count_label)

    def set_theme(self, theme: str):
        """No-op de compat: o tema vem do QSS central da QApplication
        (styles.py, seletores #annotation*, Onda 0b) — nada a propagar por
        widget. Mantido porque reader_view chama a cada troca de tema."""

    def set_page(self, page: int):
        """Define a página atual para novas anotações."""
        self._current_page = page

    def set_book_id(self, book_id: int):
        """Define o book_id para filtrar as anotações."""
        self._book_id = book_id

    def load_annotations(self, annotations: list[dict]):
        """Carrega lista de anotações no painel com filtragem estrita por book_id."""
        # Limpa lista atual
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Filtro estrito em memória para garantir isolamento na UI
        filtered_annotations = [
            ann for ann in annotations
            if ann.get("book_id") == self._book_id
        ]

        for ann in filtered_annotations:
            widget = AnnotationItem(ann)
            widget.delete_requested.connect(self.annotation_deleted.emit)
            widget.goto_requested.connect(self.goto_page.emit)
            widget.rename_requested.connect(self.annotation_renamed.emit)
            self._list_layout.addWidget(widget)

        count = len(filtered_annotations)
        self._count_label.setText(
            f"{count} {'anotação' if count == 1 else 'anotações'}"
        )

    def _set_color(self, color: str):
        self._selected_color = color

    def _add_note(self):
        content = self._note_input.toPlainText().strip()
        if not content:
            return
        self.annotation_added.emit({
            "page": self._current_page,
            "content": content,
            "type": "note",
            "color": self._selected_color,
            "title": self._title_input.text().strip(),
        })
        self._note_input.clear()
        self._title_input.clear()

    def _add_bookmark(self):
        self.annotation_added.emit({
            "page": self._current_page,
            "content": f"Marcador — Página {self._current_page + 1}",
            "type": "bookmark",
            "color": "#6366f1",
        })

    def _on_filter_changed(self):
        # Emite sinal para recarregar com filtro — implementado pelo pai
        pass
