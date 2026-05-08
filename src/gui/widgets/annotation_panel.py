"""Painel de anotações, destaques e marcadores."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class AnnotationItem(QFrame):
    """Widget individual de anotação."""

    delete_requested = pyqtSignal(int)  # annotation_id
    goto_requested = pyqtSignal(int)    # page_number

    def __init__(self, annotation: dict, parent=None):
        super().__init__(parent)
        self._annotation = annotation
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e24;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 2px;
            }
            QFrame:hover {
                border-color: #3f3f46;
                background-color: #23232b;
            }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: tipo + página
        header = QHBoxLayout()
        ann_type = self._annotation.get("annotation_type", "highlight")
        type_icons = {"highlight": "🖍️", "note": "📝", "bookmark": "🔖"}
        type_labels = {"highlight": "Destaque", "note": "Nota", "bookmark": "Marcador"}

        type_lbl = QLabel(f"{type_icons.get(ann_type, '📝')} {type_labels.get(ann_type, ann_type)}")
        type_lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 600;")
        header.addWidget(type_lbl)

        header.addStretch()

        page = self._annotation.get("page_number", 0)
        page_btn = QPushButton(f"Pág. {page + 1}")
        page_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.15);
                border: none; border-radius: 4px;
                padding: 2px 8px; color: #818cf8;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.3); }
        """)
        page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        page_btn.clicked.connect(lambda: self.goto_requested.emit(page))
        header.addWidget(page_btn)

        layout.addLayout(header)

        # Conteúdo
        content = self._annotation.get("content", "")
        if content:
            content_lbl = QLabel(content)
            content_lbl.setWordWrap(True)
            content_lbl.setStyleSheet("color: #d4d4d8; font-size: 12px; line-height: 1.5;")
            layout.addWidget(content_lbl)

        # Cor do destaque
        color = self._annotation.get("highlight_color", "#fbbf24")
        if ann_type == "highlight":
            color_bar = QWidget()
            color_bar.setFixedHeight(3)
            color_bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            layout.addWidget(color_bar)

        # Footer: data + deletar
        footer = QHBoxLayout()
        date = self._annotation.get("created_at", "")
        if date:
            date_lbl = QLabel(date[:16])
            date_lbl.setStyleSheet("color: #52525b; font-size: 10px;")
            footer.addWidget(date_lbl)

        footer.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #52525b; font-size: 12px;
            }
            QPushButton:hover { color: #ef4444; }
        """)
        del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._annotation.get("id", 0))
        )
        footer.addWidget(del_btn)

        layout.addLayout(footer)


class AnnotationPanel(QWidget):
    """Painel lateral para gerenciar anotações de um livro."""

    annotation_deleted = pyqtSignal(int)    # annotation_id
    goto_page = pyqtSignal(int)             # page_number
    annotation_added = pyqtSignal(dict)     # {page, content, type, color}

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
        self.setMinimumWidth(280)
        self.setMaximumWidth(340)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Título
        title = QLabel("📝 Anotações")
        font = title.font()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setStyleSheet("color: #e4e4e7;")
        layout.addWidget(title)

        # Filtro por tipo
        filter_layout = QHBoxLayout()
        self._type_filter = QComboBox()
        self._type_filter.addItem("Todas", None)
        self._type_filter.addItem("🖍️ Destaques", "highlight")
        self._type_filter.addItem("📝 Notas", "note")
        self._type_filter.addItem("🔖 Marcadores", "bookmark")
        self._type_filter.setStyleSheet("""
            QComboBox {
                background-color: #18181b; border: 1px solid #27272a;
                border-radius: 6px; padding: 6px 10px; color: #e4e4e7;
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #18181b; border: 1px solid #27272a;
                selection-background-color: #6366f1;
            }
        """)
        self._type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._type_filter, stretch=1)
        layout.addLayout(filter_layout)

        # Área de nova anotação
        add_frame = QFrame()
        add_frame.setStyleSheet("""
            QFrame {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        add_layout = QVBoxLayout(add_frame)
        add_layout.setContentsMargins(10, 8, 10, 8)
        add_layout.setSpacing(6)

        self._note_input = QTextEdit()
        self._note_input.setPlaceholderText("Escreva uma nota para esta página...")
        self._note_input.setFixedHeight(60)
        self._note_input.setStyleSheet("""
            QTextEdit {
                background: #0f0f17; border: 1px solid #27272a;
                border-radius: 6px; padding: 6px; color: #e4e4e7;
                font-size: 12px;
            }
            QTextEdit:focus { border-color: #6366f1; }
        """)
        add_layout.addWidget(self._note_input)

        # Cores + botões de ação
        actions = QHBoxLayout()
        actions.setSpacing(4)

        # Seleção de cor
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
        add_note_btn = QPushButton("+ Nota")
        add_note_btn.setStyleSheet("""
            QPushButton {
                background: #6366f1; border: none; border-radius: 4px;
                padding: 4px 12px; color: white; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #818cf8; }
        """)
        add_note_btn.clicked.connect(self._add_note)
        actions.addWidget(add_note_btn)

        # Botão marcador
        bookmark_btn = QPushButton("🔖")
        bookmark_btn.setFixedSize(28, 28)
        bookmark_btn.setToolTip("Adicionar marcador nesta página")
        bookmark_btn.setStyleSheet("""
            QPushButton {
                background: #27272a; border: none; border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background: #3f3f46; }
        """)
        bookmark_btn.clicked.connect(self._add_bookmark)
        actions.addWidget(bookmark_btn)

        add_layout.addLayout(actions)
        layout.addWidget(add_frame)

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
        self._count_label.setStyleSheet("color: #52525b; font-size: 11px;")
        layout.addWidget(self._count_label)

    def set_page(self, page: int):
        """Define a página atual para novas anotações."""
        self._current_page = page

    def load_annotations(self, annotations: list[dict]):
        """Carrega lista de anotações no painel."""
        # Limpa lista atual
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ann in annotations:
            widget = AnnotationItem(ann)
            widget.delete_requested.connect(self.annotation_deleted.emit)
            widget.goto_requested.connect(self.goto_page.emit)
            self._list_layout.addWidget(widget)

        count = len(annotations)
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
        })
        self._note_input.clear()

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
