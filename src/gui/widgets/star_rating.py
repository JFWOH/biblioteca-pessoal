"""Widget de avaliação com estrelas."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QCursor, QMouseEvent


class StarRating(QWidget):
    """Widget interativo de avaliação com estrelas (0-5)."""

    rating_changed = pyqtSignal(int)  # nova avaliação

    def __init__(self, rating: int = 0, max_stars: int = 5,
                 interactive: bool = True, size: int = 20, parent=None):
        super().__init__(parent)
        self._rating = rating
        self._max_stars = max_stars
        self._interactive = interactive
        self._hover_rating = -1
        self._size = size
        self._stars: list[QLabel] = []

        if interactive:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._setup_ui()
        self._update_display()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for i in range(self._max_stars):
            star = QLabel("☆")
            star.setAlignment(Qt.AlignmentFlag.AlignCenter)
            star.setFixedSize(self._size + 4, self._size + 4)
            font = star.font()
            # Guard (achado B0): único setPointSize COMPUTADO do projeto. Para
            # size <= 1, ``size // 2`` vira 0/-1 e o Qt emite
            # ``QFont::setPointSize: Point size <= 0``. max(1, ...) evita o
            # warning no console sem alterar a renderização nos tamanhos normais.
            font.setPointSize(max(1, self._size // 2))
            star.setFont(font)
            star.setStyleSheet("color: #3f3f46;")
            self._stars.append(star)
            layout.addWidget(star)

        layout.addStretch()

    def _update_display(self):
        """Atualiza a exibição visual das estrelas."""
        display_rating = self._hover_rating if self._hover_rating >= 0 else self._rating

        for i, star in enumerate(self._stars):
            if i < display_rating:
                star.setText("★")
                if self._hover_rating >= 0:
                    star.setStyleSheet("color: #fbbf24; opacity: 0.7;")
                else:
                    star.setStyleSheet("color: #fbbf24;")
            else:
                star.setText("☆")
                star.setStyleSheet("color: #3f3f46;")

    @property
    def rating(self) -> int:
        return self._rating

    @rating.setter
    def rating(self, value: int):
        self._rating = max(0, min(self._max_stars, value))
        self._update_display()

    def mousePressEvent(self, event: QMouseEvent):
        if not self._interactive:
            return super().mousePressEvent(event)

        # Calcula qual estrela foi clicada
        star_width = self._size + 6
        x = event.position().x()
        clicked_star = int(x / star_width) + 1
        clicked_star = max(1, min(self._max_stars, clicked_star))

        # Toggle: se clicar na mesma estrela, remove avaliação
        if clicked_star == self._rating:
            self._rating = 0
        else:
            self._rating = clicked_star

        self._hover_rating = -1
        self._update_display()
        self.rating_changed.emit(self._rating)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._interactive:
            return super().mouseMoveEvent(event)

        star_width = self._size + 6
        x = event.position().x()
        self._hover_rating = max(1, min(self._max_stars, int(x / star_width) + 1))
        self._update_display()

    def leaveEvent(self, event):
        self._hover_rating = -1
        self._update_display()
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:
        w = (self._size + 6) * self._max_stars
        return QSize(w, self._size + 8)
