"""Widget de capa de livro com efeitos visuais."""

from PyQt6.QtWidgets import QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor


class CoverWidget(QLabel):
    """Widget estilizado para exibir capas de livros com efeitos visuais."""

    def __init__(self, width: int = 160, height: int = 220, parent=None):
        super().__init__(parent)
        self._width = width
        self._height = height
        self._has_cover = False
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)
        self._apply_default_style()

    def _apply_default_style(self):
        self.setStyleSheet("""
            QLabel {
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #312e81, stop:0.5 #1e1b4b, stop:1 #0f172a);
            }
        """)

    def set_cover(self, cover_path: str) -> bool:
        """Define a imagem de capa. Retorna True se carregou com sucesso."""
        if not cover_path:
            self._set_placeholder()
            return False

        pixmap = QPixmap(cover_path)
        if pixmap.isNull():
            self._set_placeholder()
            return False

        # Redimensiona mantendo proporção
        scaled = pixmap.scaled(
            self._width, self._height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self._has_cover = True
        self.setStyleSheet("border-radius: 8px;")
        return True

    def set_cover_from_data(self, image_data: bytes) -> bool:
        """Define a capa a partir de bytes de imagem."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data):
            self._set_placeholder()
            return False

        scaled = pixmap.scaled(
            self._width, self._height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self._has_cover = True
        self.setStyleSheet("border-radius: 8px;")
        return True

    def _set_placeholder(self, title: str = ""):
        """Define uma capa placeholder."""
        self._has_cover = False
        if title:
            display = title[:20] + "..." if len(title) > 20 else title
            self.setText(f"📖\n{display}")
        else:
            self.setText("📖")
        self._apply_default_style()
        self.setStyleSheet(self.styleSheet() + """
            QLabel {
                font-size: 36px;
                color: #818cf8;
                padding: 20px;
            }
        """)

    def apply_shadow(self, blur: int = 20, opacity: int = 80):
        """Aplica sombra ao widget de capa."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur)
        shadow.setColor(QColor(0, 0, 0, opacity))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

    @property
    def has_cover(self) -> bool:
        return self._has_cover
