"""Widget de card de livro para a grade da biblioteca."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QColor, QFont, QCursor

from src.utils.constants import COVER_WIDTH, COVER_HEIGHT


class BookCard(QWidget):
    """Card visual para exibir um livro na biblioteca.

    Detecta automaticamente se o arquivo físico existe e aplica
    um estilo âmbar de aviso caso esteja ausente (livro fantasma).
    """

    clicked = pyqtSignal(int)            # book_id
    double_clicked = pyqtSignal(int)     # book_id — abre o leitor
    selected_changed = pyqtSignal(int, bool)  # book_id, selecionado?

    def __init__(self, book_data: dict, parent=None):
        super().__init__(parent)
        self._book = book_data
        self._book_id = book_data.get("id", 0)
        self._is_selected = False

        # Sanity check: arquivo existe no disco?
        file_path = book_data.get("file_path", "")
        self._is_broken = bool(file_path) and not Path(file_path).exists()

        self.setObjectName("bookCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(COVER_WIDTH + 20, COVER_HEIGHT + 80)
        self._setup_ui()
        self._apply_shadow()

        if self._is_broken:
            self.setToolTip(f"⚠️ Arquivo não encontrado:\n{file_path}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Capa
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(COVER_WIDTH, COVER_HEIGHT)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setScaledContents(True)

        if self._is_broken:
            self._set_broken_cover()
        else:
            cover_path = self._book.get("cover_path", "")
            if cover_path:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    self._cover_label.setPixmap(
                        pixmap.scaled(
                            COVER_WIDTH, COVER_HEIGHT,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self._cover_label.setStyleSheet(
                        "border-radius: 8px; background-color: #27272a;"
                    )
                else:
                    self._set_placeholder_cover()
            else:
                self._set_placeholder_cover()

        layout.addWidget(self._cover_label)

        # Título
        title = self._book.get("title", "Sem título")
        title_label = QLabel(title)
        title_label.setObjectName("bookCardTitle")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(36)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        font = title_label.font()
        font.setPointSize(9)
        font.setWeight(QFont.Weight.DemiBold)
        title_label.setFont(font)
        layout.addWidget(title_label)

        # Autor
        author = self._book.get("author", "")
        if author:
            author_label = QLabel(author)
            author_label.setObjectName("bookCardAuthor")
            author_label.setMaximumHeight(18)
            font2 = author_label.font()
            font2.setPointSize(8)
            author_label.setFont(font2)
            layout.addWidget(author_label)

        # Indicadores (formato + badges)
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)

        fmt = self._book.get("file_format", "").upper()
        if fmt:
            fmt_label = QLabel(fmt)
            fmt_label.setObjectName("badge")
            fmt_label.setFixedHeight(18)
            font3 = fmt_label.font()
            font3.setPointSize(7)
            fmt_label.setFont(font3)
            info_layout.addWidget(fmt_label)

        if self._is_broken:
            broken_badge = QLabel("⚠️ Ausente")
            broken_badge.setStyleSheet(
                "color: #f59e0b; font-size: 8px; font-weight: 700;"
            )
            info_layout.addWidget(broken_badge)

        info_layout.addStretch()

        if self._book.get("is_favorite"):
            fav_label = QLabel("⭐")
            fav_label.setFixedSize(18, 18)
            info_layout.addWidget(fav_label)

        layout.addLayout(info_layout)

    def _set_placeholder_cover(self):
        """Capa placeholder quando não há imagem."""
        self._cover_label.setText("📖")
        self._cover_label.setStyleSheet("""
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #312e81, stop:1 #1e1b4b);
            font-size: 48px;
            color: #818cf8;
        """)

    def _set_broken_cover(self):
        """Capa âmbar de alerta para livros com arquivo ausente."""
        self._cover_label.setText("⚠️")
        self._cover_label.setStyleSheet("""
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #451a03, stop:1 #78350f);
            font-size: 48px;
            color: #f59e0b;
            border: 2px solid #f59e0b;
        """)

    def _apply_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def set_selected(self, selected: bool) -> None:
        """Altera o estado de seleção visual do card."""
        self._is_selected = selected
        if selected:
            self.setStyleSheet(
                "QWidget#bookCard { border: 2px solid #6366f1; border-radius: 12px; "
                "background-color: rgba(99,102,241,0.12); }"
            )
        else:
            self.setStyleSheet("")
        self.selected_changed.emit(self._book_id, selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._book_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._book_id)
        super().mouseDoubleClickEvent(event)

    @property
    def book_data(self) -> dict:
        return self._book

    @property
    def is_broken(self) -> bool:
        """True se o arquivo físico associado não existe no disco."""
        return self._is_broken

    @property
    def is_selected(self) -> bool:
        return self._is_selected

