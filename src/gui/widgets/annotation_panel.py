"""Painel de anotações, destaques e marcadores."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QComboBox, QLineEdit,
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
        self._setup_ui()
        self.set_theme("dark")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: tipo + página
        header = QHBoxLayout()
        ann_type = self._annotation.get("annotation_type", "highlight")
        type_icons = {"highlight": "🖍️", "note": "📝", "bookmark": "🔖"}
        type_labels = {"highlight": "Destaque", "note": "Nota", "bookmark": "Marcador"}

        self._type_lbl = QLabel(f"{type_icons.get(ann_type, '📝')} {type_labels.get(ann_type, ann_type)}")
        self._type_lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 600;")
        header.addWidget(self._type_lbl)

        header.addStretch()

        page = self._annotation.get("page_number", 0)
        self._page_btn = QPushButton(f"Pág. {page + 1}")
        self._page_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.15);
                border: none; border-radius: 4px;
                padding: 2px 8px; color: #818cf8;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.3); }
        """)
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
            self._title_item_lbl.setStyleSheet("color: #e5e7eb; font-size: 13px; font-weight: 600;")
            layout.addWidget(self._title_item_lbl)

        # Conteúdo
        content = self._annotation.get("content", "")
        self._content_lbl = None
        if content:
            self._content_lbl = QLabel(content)
            self._content_lbl.setWordWrap(True)
            self._content_lbl.setStyleSheet("color: #d4d4d8; font-size: 12px; line-height: 1.5;")
            layout.addWidget(self._content_lbl)

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
        self._date_lbl = None
        if date:
            self._date_lbl = QLabel(date[:16])
            self._date_lbl.setStyleSheet("color: #52525b; font-size: 10px;")
            footer.addWidget(self._date_lbl)

        footer.addStretch()

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedSize(20, 20)
        self._del_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #52525b; font-size: 12px;
            }
            QPushButton:hover { color: #ef4444; }
        """)
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._annotation.get("id", 0))
        )
        footer.addWidget(self._del_btn)

        layout.addLayout(footer)

    def set_theme(self, theme: str):
        if theme == "light":
            bg_color = "#ffffff"
            border_color = "#e4e4e7"
            hover_border = "#a1a1aa"
            hover_bg = "#f4f4f5"
            type_color = "#059669"
            page_bg = "rgba(16, 185, 129, 0.1)"
            page_fg = "#059669"
            page_hover = "rgba(16, 185, 129, 0.2)"
            content_color = "#1A1A1A"
            date_color = "#71717a"
            del_color = "#71717a"
        elif theme == "sepia":
            bg_color = "#faf5ed"
            border_color = "#d4cbb8"
            hover_border = "#8b7355"
            hover_bg = "#ebe5d9"
            type_color = "#059669"
            page_bg = "rgba(16, 185, 129, 0.15)"
            page_fg = "#059669"
            page_hover = "rgba(16, 185, 129, 0.3)"
            content_color = "#5B4636"
            date_color = "#8b7355"
            del_color = "#8b7355"
        else: # dark
            bg_color = "#20242d"
            border_color = "#2d333f"
            hover_border = "#475569"
            hover_bg = "#2a3241"
            type_color = "#10b981"
            page_bg = "rgba(16, 185, 129, 0.15)"
            page_fg = "#10b981"
            page_hover = "rgba(16, 185, 129, 0.3)"
            content_color = "#cbd5e1"
            date_color = "#94a3b8"
            del_color = "#94a3b8"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 2px;
            }}
            QFrame:hover {{
                border-color: {hover_border};
                background-color: {hover_bg};
            }}
        """)
        self._type_lbl.setStyleSheet(f"color: {type_color}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        self._page_btn.setStyleSheet(f"""
            QPushButton {{
                background: {page_bg};
                border: none; border-radius: 4px;
                padding: 2px 8px; color: {page_fg};
                font-size: 11px;
            }}
            QPushButton:hover {{ background: {page_hover}; }}
        """)
        if hasattr(self, "_title_item_lbl") and self._title_item_lbl:
            self._title_item_lbl.setStyleSheet(f"color: {content_color}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        if hasattr(self, "_content_lbl") and self._content_lbl:
            self._content_lbl.setStyleSheet(f"color: {content_color}; font-size: 12px; line-height: 1.5; background: transparent; border: none;")
        if hasattr(self, "_date_lbl") and self._date_lbl:
            self._date_lbl.setStyleSheet(f"color: {date_color}; font-size: 10px; background: transparent; border: none;")
        self._del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {del_color}; font-size: 12px;
            }}
            QPushButton:hover {{ color: #ef4444; }}
        """)


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
        self._title.setStyleSheet("color: #e4e4e7;")
        layout.addWidget(self._title)

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
        self._add_frame = QFrame()
        self._add_frame.setStyleSheet("""
            QFrame {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        add_layout = QVBoxLayout(self._add_frame)
        add_layout.setContentsMargins(10, 8, 10, 8)
        add_layout.setSpacing(6)

        # Título opcional da nota
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Título da nota (opcional)")
        self._title_input.setStyleSheet("""
            QLineEdit {
                background: #0f0f17; border: 1px solid #27272a;
                border-radius: 6px; padding: 5px 6px; color: #e4e4e7;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #6366f1; }
        """)
        add_layout.addWidget(self._title_input)

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
        self._add_note_btn = QPushButton("+ Nota")
        self._add_note_btn.setStyleSheet("""
            QPushButton {
                background: #6366f1; border: none; border-radius: 4px;
                padding: 4px 12px; color: white; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #818cf8; }
        """)
        self._add_note_btn.clicked.connect(self._add_note)
        actions.addWidget(self._add_note_btn)

        # Botão marcador
        self._bookmark_btn = QPushButton("🔖")
        self._bookmark_btn.setFixedSize(28, 28)
        self._bookmark_btn.setToolTip("Adicionar marcador nesta página")
        self._bookmark_btn.setStyleSheet("""
            QPushButton {
                background: #27272a; border: none; border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background: #3f3f46; }
        """)
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
        self._count_label.setStyleSheet("color: #52525b; font-size: 11px;")
        layout.addWidget(self._count_label)

        self.set_theme("dark")

    def set_theme(self, theme: str):
        self._theme = theme

        if theme == "light":
            text_main = "#1A1A1A"
            text_sec = "#71717a"
            bg_input = "#f4f4f5"
            border_color = "#d4d4d8"
            bg_panel = "#ffffff"
            add_bg = "#f4f4f5"
            btn_primary_bg = "#059669"
            btn_primary_hover = "#10b981"
            btn_sec_bg = "#e4e4e7"
            btn_sec_hover = "#d4d4d8"
            btn_sec_fg = "#1A1A1A"
        elif theme == "sepia":
            text_main = "#5B4636"
            text_sec = "#8b7355"
            bg_input = "#ebe5d9"
            border_color = "#d4cbb8"
            bg_panel = "#faf5ed"
            add_bg = "#ebe5d9"
            btn_primary_bg = "#059669"
            btn_primary_hover = "#10b981"
            btn_sec_bg = "#dfd8c8"
            btn_sec_hover = "#d4cbb8"
            btn_sec_fg = "#5B4636"
        else: # dark
            text_main = "#e5e7eb"
            text_sec = "#cbd5e1"
            bg_input = "#161920"
            border_color = "#2d333f"
            bg_panel = "#0f1115"
            add_bg = "#20242d"
            btn_primary_bg = "#10b981"
            btn_primary_hover = "#059669"
            btn_sec_bg = "#2d333f"
            btn_sec_hover = "#475569"
            btn_sec_fg = "#e5e7eb"

        # Apply styles to self
        self.setStyleSheet(f"background-color: {bg_panel};")

        # Título
        self._title.setStyleSheet(f"color: {text_main};")

        # Filtro
        self._type_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg_panel}; border: 1px solid {border_color};
                border-radius: 6px; padding: 6px 10px; color: {text_main};
                font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: {bg_panel}; border: 1px solid {border_color};
                selection-background-color: {bg_input};
                color: {text_main};
            }}
        """)

        # Add frame
        self._add_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {add_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """)

        # Title + Note input
        self._title_input.setStyleSheet(f"""
            QLineEdit {{
                background: {bg_input}; border: 1px solid {border_color};
                border-radius: 6px; padding: 5px 6px; color: {text_main};
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {btn_primary_bg}; }}
        """)
        self._note_input.setStyleSheet(f"""
            QTextEdit {{
                background: {bg_input}; border: 1px solid {border_color};
                border-radius: 6px; padding: 6px; color: {text_main};
                font-size: 12px;
            }}
            QTextEdit:focus {{ border-color: {btn_primary_bg}; }}
        """)

        # Note button
        self._add_note_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_primary_bg}; border: none; border-radius: 4px;
                padding: 4px 12px; color: white; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {btn_primary_hover}; }}
        """)

        # Bookmark button
        self._bookmark_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_sec_bg}; border: none; border-radius: 4px;
                color: {btn_sec_fg};
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {btn_sec_hover}; }}
        """)

        # Count label
        self._count_label.setStyleSheet(f"color: {text_sec}; font-size: 11px;")

        # Propagar tema para os itens da lista
        for i in range(self._list_layout.count()):
            w = self._list_layout.itemAt(i).widget()
            if isinstance(w, AnnotationItem):
                w.set_theme(theme)

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
            if hasattr(self, "_theme"):
                widget.set_theme(self._theme)
            widget.delete_requested.connect(self.annotation_deleted.emit)
            widget.goto_requested.connect(self.goto_page.emit)
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
