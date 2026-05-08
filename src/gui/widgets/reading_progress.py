"""Widget de progresso de leitura."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt


class ReadingProgressBar(QWidget):
    """Barra de progresso de leitura estilizada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)

        self._label = QLabel("0%")
        self._label.setFixedWidth(40)
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._label.setStyleSheet("color: #71717a; font-size: 11px;")

        layout.addWidget(self._progress)
        layout.addWidget(self._label)

    def set_progress(self, value: float):
        """Define o progresso (0.0 a 100.0)."""
        v = int(max(0, min(100, value)))
        self._progress.setValue(v)
        self._label.setText(f"{v}%")

    def set_page_info(self, current: int, total: int):
        """Define o progresso baseado em páginas."""
        if total > 0:
            self.set_progress(current / total * 100)
        self._label.setText(f"{current}/{total}")
