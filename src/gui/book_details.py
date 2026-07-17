"""Painel de detalhes do livro."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

from src.utils.file_utils import format_file_size
from src.utils.constants import READ_STATUS_LABELS
from src.gui.widgets.star_rating import StarRating
from src.gui.widgets.tag_manager import TagManager
from src.gui.styles import emoji_icon
from src.core.database import LibraryDB


class BookDetails(QWidget):
    """Painel lateral com detalhes do livro selecionado."""

    open_requested = pyqtSignal(int)
    favorite_toggled = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    rating_changed = pyqtSignal(int, int)  # book_id, rating
    tags_changed = pyqtSignal(int)  # book_id
    add_to_collection_requested = pyqtSignal(int)  # book_id
    remove_from_collection_requested = pyqtSignal(int)  # book_id
    fetch_metadata_requested = pyqtSignal(int)  # book_id
    related_book_clicked = pyqtSignal(int)  # book_id de um livro relacionado (grafo)
    dossier_requested = pyqtSignal(int)  # book_id — abrir o dossiê do livro (Fase 4)

    def __init__(self, db: LibraryDB = None, parent=None):
        super().__init__(parent)
        self._book: dict | None = None
        self._db = db
        # Grafo de conceitos (Fase 2): leitura barata na thread da GUI.
        self._graph_store = None
        if db is not None:
            try:
                from src.core.graph.graph_store import GraphStore
                self._graph_store = GraphStore(db)
            except Exception:
                self._graph_store = None
        self.setMinimumWidth(280)
        self.setMaximumWidth(340)
        self._setup_ui()
        self.hide()  # Oculto até selecionar um livro

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Capa
        self._cover = QLabel()
        self._cover.setFixedHeight(280)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setStyleSheet("border-radius: 8px; background: #18181b;")
        self._cover.setScaledContents(False)
        layout.addWidget(self._cover)

        # Título
        self._title = QLabel()
        self._title.setWordWrap(True)
        font = self._title.font()
        font.setPointSize(14)
        font.setWeight(QFont.Weight.Bold)
        self._title.setFont(font)
        self._title.setStyleSheet("color: #e4e4e7;")
        layout.addWidget(self._title)

        # Autor
        self._author = QLabel()
        self._author.setStyleSheet("color: #818cf8; font-size: 13px;")
        layout.addWidget(self._author)

        # Avaliação com estrelas
        self._star_rating = StarRating(rating=0, size=18, interactive=True)
        self._star_rating.rating_changed.connect(self._on_rating_changed)
        layout.addWidget(self._star_rating)

        # Metadados
        self._meta_label = QLabel()
        self._meta_label.setWordWrap(True)
        self._meta_label.setStyleSheet("color: #71717a; font-size: 12px; line-height: 1.5;")
        layout.addWidget(self._meta_label)

        # Tags
        if self._db:
            self._tag_manager = TagManager(self._db)
            self._tag_manager.tags_changed.connect(lambda bid: self.tags_changed.emit(bid))
            layout.addWidget(self._tag_manager)
        else:
            self._tag_manager = None

        # Descrição
        self._desc = QLabel()
        self._desc.setWordWrap(True)
        self._desc.setMaximumHeight(100)
        self._desc.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        layout.addWidget(self._desc)

        # Grafo de conceitos (Fase 2): conceitos do livro + livros relacionados
        self._graph_section = QWidget()
        graph_lay = QVBoxLayout(self._graph_section)
        graph_lay.setContentsMargins(0, 0, 0, 0)
        graph_lay.setSpacing(6)
        self._concepts_header = QLabel("💡 Conceitos")
        self._concepts_header.setStyleSheet(
            "color: #71717a; font-size: 11px; font-weight: 600;")
        graph_lay.addWidget(self._concepts_header)
        self._concepts_label = QLabel()
        self._concepts_label.setWordWrap(True)
        self._concepts_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        graph_lay.addWidget(self._concepts_label)
        self._related_header = QLabel("🔗 Livros relacionados")
        self._related_header.setStyleSheet(
            "color: #71717a; font-size: 11px; font-weight: 600;")
        graph_lay.addWidget(self._related_header)
        self._related_btns_lay = QVBoxLayout()
        self._related_btns_lay.setSpacing(4)
        graph_lay.addLayout(self._related_btns_lay)
        self._graph_section.hide()
        layout.addWidget(self._graph_section)

        layout.addStretch()

        # Botões de ação
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        # Emoji vai como ÍCONE (setIcon), nunca embutido no texto: no Windows o
        # emoji-no-texto renderiza sobreposto ao rótulo (bug visual). Ver
        # src/gui/styles.py::emoji_icon.
        self._open_btn = QPushButton("Abrir")
        self._open_btn.setIcon(emoji_icon("📖"))
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.setObjectName("primaryBtn")
        self._open_btn.clicked.connect(lambda: self._emit_action("open"))
        btn_layout.addWidget(self._open_btn)

        self._dossier_btn = QPushButton("Dossiê do Livro")
        self._dossier_btn.setIcon(emoji_icon("📋"))
        self._dossier_btn.setObjectName("secondaryBtn")
        self._dossier_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dossier_btn.clicked.connect(lambda: self._emit_action("dossier"))
        btn_layout.addWidget(self._dossier_btn)

        self._fav_btn = QPushButton("Favoritar")
        self._fav_btn.setIcon(emoji_icon("⭐"))
        self._fav_btn.setObjectName("secondaryBtn")
        self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fav_btn.clicked.connect(lambda: self._emit_action("favorite"))
        btn_layout.addWidget(self._fav_btn)

        self._col_btn = QPushButton("Coleção")
        self._col_btn.setIcon(emoji_icon("📂"))
        self._col_btn.setObjectName("secondaryBtn")
        self._col_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._col_btn.clicked.connect(lambda: self._emit_action("collection"))
        btn_layout.addWidget(self._col_btn)

        self._meta_btn = QPushButton("Metadados")
        self._meta_btn.setIcon(emoji_icon("🌐"))
        self._meta_btn.setObjectName("secondaryBtn")
        self._meta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._meta_btn.clicked.connect(lambda: self._emit_action("fetch_metadata"))
        btn_layout.addWidget(self._meta_btn)

        self._remove_col_btn = QPushButton("Tirar desta Coleção")
        self._remove_col_btn.setIcon(emoji_icon("❌"))
        self._remove_col_btn.setObjectName("secondaryBtn")
        self._remove_col_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_col_btn.clicked.connect(lambda: self._emit_action("remove_from_collection"))
        self._remove_col_btn.hide()
        btn_layout.addWidget(self._remove_col_btn)

        self._del_btn = QPushButton("Remover")
        self._del_btn.setIcon(emoji_icon("🗑"))
        self._del_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #3f3f46;
                          border-radius: 8px; padding: 10px; color: #ef4444; }
            QPushButton:hover { background: rgba(239, 68, 68, 0.1); border-color: #ef4444; }
        """)
        self._del_btn.clicked.connect(lambda: self._emit_action("delete"))
        btn_layout.addWidget(self._del_btn)

        layout.addLayout(btn_layout)

    def show_book(self, book: dict):
        """Exibe os detalhes de um livro."""
        self._book = book
        self._title.setText(book.get("title", "Sem título"))
        self._author.setText(book.get("author", "") or "Autor desconhecido")

        # Capa
        cover_path = book.get("cover_path", "")
        if cover_path:
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                self._cover.setPixmap(pixmap.scaled(
                    250, 280, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            else:
                self._cover.setText("📖")
                self._cover.setStyleSheet(
                    "font-size: 64px; background: #18181b; border-radius: 8px;"
                )

        # Metadados
        lines = []
        fmt = book.get("file_format", "").upper()
        if fmt:
            lines.append(f"📄 Formato: {fmt}")
        size = book.get("file_size", 0)
        if size:
            lines.append(f"💾 Tamanho: {format_file_size(size)}")
        pages = book.get("page_count", 0)
        if pages:
            lines.append(f"📃 Páginas: {pages}")
        status = book.get("read_status", "unread")
        lines.append(f"📊 Status: {READ_STATUS_LABELS.get(status, status)}")
        rating = book.get("rating", 0)
        if rating > 0:
            lines.append(f"⭐ Avaliação: {'★' * rating}{'☆' * (5 - rating)}")
        self._meta_label.setText("\n".join(lines))

        # Descrição
        desc = book.get("description", "")
        self._desc.setText(desc if desc else "Sem descrição disponível")
        self._desc.setVisible(bool(desc))

        # Favorito (emoji como ícone; texto sem emoji — ver _setup_ui)
        is_fav = book.get("is_favorite", 0)
        self._fav_btn.setText("Desfavoritar" if is_fav else "Favoritar")
        self._fav_btn.setIcon(emoji_icon("💛" if is_fav else "⭐"))

        # Avaliação
        self._star_rating.rating = book.get("rating", 0)

        # Tags
        if self._tag_manager:
            self._tag_manager.set_book(book["id"])

        # Grafo de conceitos
        self.refresh_graph_section()

        self.show()

    def refresh_graph_section(self):
        """Atualiza conceitos e livros relacionados a partir do grafo.

        Graceful (ADR-005): grafo vazio/indisponível → seção oculta, sem erro.
        """
        # Limpa botões antigos de relacionados
        while self._related_btns_lay.count():
            item = self._related_btns_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._graph_store is None or not self._book:
            self._graph_section.hide()
            return
        try:
            book_id = self._book["id"]
            concepts = self._graph_store.get_book_concepts(book_id, limit=8)
            related = self._graph_store.related_books(book_id, limit=3)
        except Exception:
            self._graph_section.hide()
            return
        if not concepts and not related:
            self._graph_section.hide()
            return

        self._concepts_label.setText(
            " · ".join(c["display_name"] for c in concepts))
        self._concepts_header.setVisible(bool(concepts))
        self._concepts_label.setVisible(bool(concepts))

        self._related_header.setVisible(bool(related))
        for rel in related:
            shared_n = int(rel.get("weight") or 0)
            btn = QPushButton(f"📕 {rel['title']}  ({shared_n} em comum)")
            btn.setObjectName("secondaryBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid #3f3f46;"
                " border-radius: 6px; padding: 6px; color: #a5b4fc; font-size: 11px;"
                " text-align: left; }"
                " QPushButton:hover { border-color: #6366f1; }")
            btn.setToolTip("Em comum: " + ", ".join(rel.get("shared") or []))
            btn.clicked.connect(
                lambda _c=False, bid=rel["book_id"]: self.related_book_clicked.emit(bid))
            self._related_btns_lay.addWidget(btn)

        self._graph_section.show()

    def _emit_action(self, action: str):
        if not self._book:
            return
        book_id = self._book["id"]
        if action == "open":
            self.open_requested.emit(book_id)
        elif action == "favorite":
            self.favorite_toggled.emit(book_id)
        elif action == "collection":
            self.add_to_collection_requested.emit(book_id)
        elif action == "remove_from_collection":
            self.remove_from_collection_requested.emit(book_id)
        elif action == "fetch_metadata":
            self.fetch_metadata_requested.emit(book_id)
        elif action == "dossier":
            self.dossier_requested.emit(book_id)
        elif action == "delete":
            self.delete_requested.emit(book_id)

    def set_collection_mode(self, in_collection: bool):
        """Mostra ou esconde o botão de remover da coleção."""
        self._remove_col_btn.setVisible(in_collection)

    def clear(self):
        self._book = None
        self._star_rating.rating = 0
        if self._tag_manager:
            self._tag_manager.set_book(0)
        self._graph_section.hide()
        self.hide()

    def _on_rating_changed(self, rating: int):
        """Quando o usuário altera a avaliação."""
        if self._book:
            self.rating_changed.emit(self._book["id"], rating)
