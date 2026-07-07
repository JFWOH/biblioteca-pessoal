"""Overlay de seleção por fluxo de texto (Sprint B2, item 9 do backlog UX).

Durante o arrasto no PDF, o feedback visual era um retângulo (QRubberBand)
mesmo quando a seleção final seguia o fluxo do texto (quads por linha) — o
usuário só via o resultado real ao soltar o mouse. Este widget pinta os
quads ao vivo, linha a linha, como uma seleção de texto normal.

Transparente para eventos de mouse (o arrasto continua fluindo para o
_image_label por baixo); o chamador o redimensiona junto com o label pai.
"""

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

# Azul de seleção translúcido (mesma família do destaque de texto padrão).
_FILL = QColor(59, 130, 246, 70)
_BORDER = QColor(59, 130, 246, 120)


class SelectionFlowOverlay(QWidget):
    """Pinta uma lista de retângulos (um por linha de texto selecionada)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._rects: list[QRect] = []
        self.hide()

    def set_rects(self, rects: list[QRect]) -> None:
        """Mostra os quads (coordenadas do widget pai). Lista vazia esconde."""
        self._rects = list(rects)
        if not self._rects:
            self.hide()
            return
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        self.update()

    def clear(self) -> None:
        self._rects = []
        self.hide()

    def paintEvent(self, event) -> None:
        if not self._rects:
            return
        painter = QPainter(self)
        painter.setPen(_BORDER)
        for rect in self._rects:
            painter.fillRect(rect, _FILL)
            painter.drawRect(rect)
        painter.end()
