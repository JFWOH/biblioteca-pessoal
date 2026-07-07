"""Cartão padronizado de resposta de IA (Sprint B1, revisão 2026-07-05 §3.2).

Cada feature de IA inventou o próprio feedback: QProgressDialog (flashcard),
label inline (dossiê), statusbar (tradução), painel (RAG). Este widget
unifica os estados — pensando → streaming → concluído/erro — com botões
Parar e Tentar de novo, para qualquer superfície que hospede uma resposta
de IA. O host conecta ``stop_requested``/``retry_requested`` ao worker.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

_CARD_STYLE = (
    "QFrame#aiResponseCard { background-color: #20242d;"
    " border: 1px solid #2d333f; border-radius: 8px; }"
)
_STATUS_STYLE = "color: #a5b4fc; font-size: 12px; font-style: italic;"
_ERROR_STYLE = "color: #f87171; font-size: 12px;"
_BODY_STYLE = "color: #cbd5e1; font-size: 12px;"
_BTN_STYLE = (
    "QPushButton { background: transparent; border: 1px solid #3f3f46;"
    " border-radius: 6px; padding: 3px 10px; color: #a1a1aa; font-size: 11px; }"
    " QPushButton:hover { border-color: #6366f1; color: #c7d2fe; }"
)


class AIResponseCard(QFrame):
    """Estados: idle → thinking → streaming → done | error.

    - ``start(status)``: entra em *thinking* (status visível + Parar).
    - ``set_status(texto)``: atualiza a linha de status (ex.: ticks de
      raciocínio do A1: "🤔 Raciocinando… 12s").
    - ``append_text(token)`` / ``set_text(texto)``: corpo da resposta
      (*streaming*); Parar continua disponível.
    - ``finish()``: *done* — só o texto fica.
    - ``fail(msg)``: *error* — mensagem + Tentar de novo.
    """

    stop_requested = pyqtSignal()
    retry_requested = pyqtSignal()

    STATE_IDLE = "idle"
    STATE_THINKING = "thinking"
    STATE_STREAMING = "streaming"
    STATE_DONE = "done"
    STATE_ERROR = "error"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiResponseCard")
        self.setStyleSheet(_CARD_STYLE)
        self._state = self.STATE_IDLE

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(_STATUS_STYLE)
        header.addWidget(self._status_lbl, stretch=1)

        self._stop_btn = QPushButton("⏹ Parar")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setStyleSheet(_BTN_STYLE)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        header.addWidget(self._stop_btn)

        self._retry_btn = QPushButton("🔄 Tentar de novo")
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_btn.setStyleSheet(_BTN_STYLE)
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        header.addWidget(self._retry_btn)
        lay.addLayout(header)

        self._body_lbl = QLabel("")
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body_lbl.setStyleSheet(_BODY_STYLE)
        lay.addWidget(self._body_lbl)

        self._apply_state(self.STATE_IDLE)

    # ── API de estados ────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    def start(self, status: str = "🤔 Pensando…") -> None:
        self._body_lbl.setText("")
        self._status_lbl.setStyleSheet(_STATUS_STYLE)
        self._status_lbl.setText(status)
        self._apply_state(self.STATE_THINKING)

    def set_status(self, status: str) -> None:
        """Atualiza a linha de status durante thinking/streaming."""
        if status and self._state in (self.STATE_THINKING, self.STATE_STREAMING):
            self._status_lbl.setText(status)

    def append_text(self, token: str) -> None:
        if not token:
            return
        self._body_lbl.setText(self._body_lbl.text() + token)
        if self._state != self.STATE_STREAMING:
            self._apply_state(self.STATE_STREAMING)

    def set_text(self, text: str) -> None:
        self._body_lbl.setText(text)
        if self._state not in (self.STATE_DONE, self.STATE_ERROR):
            self._apply_state(self.STATE_STREAMING)

    def finish(self) -> None:
        self._apply_state(self.STATE_DONE)

    def fail(self, message: str) -> None:
        self._status_lbl.setStyleSheet(_ERROR_STYLE)
        self._status_lbl.setText(message)
        self._apply_state(self.STATE_ERROR)

    def text(self) -> str:
        return self._body_lbl.text()

    def status_text(self) -> str:
        return self._status_lbl.text()

    # ── Interno ───────────────────────────────────────────────────────

    def _apply_state(self, state: str) -> None:
        self._state = state
        in_progress = state in (self.STATE_THINKING, self.STATE_STREAMING)
        self._status_lbl.setVisible(in_progress or state == self.STATE_ERROR)
        self._stop_btn.setVisible(in_progress)
        self._retry_btn.setVisible(state == self.STATE_ERROR)
        self._body_lbl.setVisible(state in (self.STATE_STREAMING, self.STATE_DONE))
