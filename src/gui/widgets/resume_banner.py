"""Banner discreto de "Retomar leitura" (tarefa 3.7).

Ao reabrir um livro com progresso, mostra no topo do leitor onde a leitura
parou + um gancho de contexto da última sessão (síntese em cache / última
anotação / conceitos-chave). Fechável e some sozinho após ~10s (QTimer — a
camada de threads/timers Qt fica na GUI, ADR-006). Recebe um dict JÁ montado
por ``src.core.resume_summary.build_resume_info`` — nenhum LLM é chamado aqui.
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from src.core.resume_summary import format_resume_banner_text
from src.gui.styles import emoji_icon


class ResumeBanner(QFrame):
    """Faixa fina no topo do leitor com o resumo da última sessão."""

    closed = pyqtSignal()

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self._info = info or {}
        self.setObjectName("resumeBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._setup_ui()

    def _setup_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 8, 8)
        lay.setSpacing(10)

        icon = QLabel("🔖")
        icon.setObjectName("resumeBannerIcon")
        lay.addWidget(icon)

        text = QLabel(format_resume_banner_text(self._info))
        text.setObjectName("resumeBannerText")
        text.setWordWrap(True)
        lay.addWidget(text, 1)

        close_btn = QPushButton()
        close_btn.setObjectName("resumeBannerClose")
        close_btn.setIcon(emoji_icon("✕", 12))
        close_btn.setFixedSize(24, 24)
        close_btn.setToolTip("Fechar")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.dismiss)
        lay.addWidget(close_btn)

    def show_at_top(self, auto_hide_ms: int = 10000):
        """Exibe o banner no topo do widget-pai e agenda o auto-fechamento."""
        parent = self.parentWidget()
        if parent is not None:
            width = max(320, parent.width() - 32)
            self.setFixedWidth(width)
            self.adjustSize()
            self.move(16, 12)
        self.raise_()
        self.show()
        if auto_hide_ms and auto_hide_ms > 0:
            self._timer.start(auto_hide_ms)

    def dismiss(self):
        """Fecha o banner (clique no ✕ ou fim do timer)."""
        self._timer.stop()
        self.closed.emit()
        self.hide()
        self.deleteLater()
