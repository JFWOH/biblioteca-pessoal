"""Cartão padronizado de resposta de IA (Sprint B1, revisão 2026-07-05 §3.2).

Cada feature de IA inventou o próprio feedback: QProgressDialog (flashcard),
label inline (dossiê), statusbar (tradução), painel (RAG). Este widget
unifica os estados — pensando → streaming → concluído/erro — com botões
Parar e Tentar de novo, para qualquer superfície que hospede uma resposta
de IA. O host conecta ``stop_requested``/``retry_requested`` ao worker.

Rodada UX ago/2026 (onda S, latência PERCEBIDA), duas adições:

- **Skeleton shimmer**: entre "comecei a pensar" e o 1º token o corpo ficava
  simplesmente OCULTO — o cartão parecia vazio/travado. Agora três linhas de
  placeholder com um brilho deslizante ocupam esse espaço e somem no 1º token.
  As cores saem da paleta do próprio corpo do cartão (nada hardcoded), então
  os 3 temas são respeitados sem QSS nova.
- **Timeline dos passos**: ``set_status`` mostrava só o ÚLTIMO status; os
  anteriores se perdiam. Os passos agora se acumulam numa lista colapsável
  ("▸ 3 passos"), colapsada por padrão, que vira discreta ao terminar.
"""

import re

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from src.gui.styles import emoji_icon

# Parte volátil do tick de raciocínio ("💭 Pensando… (42 tokens · 7s)"): a
# timeline guarda o passo, não o contador — senão cada tick viraria um item.
_VOLATILE_TAIL = re.compile(r"\s*\([^)]*\)\s*$")


class _SkeletonLines(QWidget):
    """Três linhas de placeholder com brilho deslizante (shimmer).

    Ocupa o lugar do corpo da resposta durante o gap pré-primeiro-token. Sem
    cor fixa: a base é injetada por ``set_base_color`` a partir da paleta do
    corpo do cartão, que o QSS do tema corrente já pintou — por isso os 3
    temas funcionam sem folha de estilo nova.

    Custo: um QTimer de ~11 fps que só roda enquanto o skeleton está visível
    (parado em ``stop_animation``/``hideEvent``), pintando 3 retângulos.
    """

    _LINE_RATIOS = (1.0, 0.92, 0.64)   # proporção da largura útil por linha
    _LINE_HEIGHT = 9
    _LINE_GAP = 7
    _TICK_MS = 90
    _PHASE_STEP = 0.06
    _GLOW_HALF_WIDTH = 0.16            # meia-largura do brilho, em fração
    _DIM_ALPHA = 46                    # placeholder "apagado"
    _GLOW_ALPHA = 104                  # crista do brilho

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aiResponseSkeleton")
        self._phase = 0.0
        self._base = QColor(148, 163, 184)   # neutro só até o 1º set_base_color
        self._timer = QTimer(self)           # filho: morre junto com o widget
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)
        n = len(self._LINE_RATIOS)
        self.setFixedHeight(n * self._LINE_HEIGHT + (n - 1) * self._LINE_GAP)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ── API ───────────────────────────────────────────────────────────

    def set_base_color(self, color) -> None:
        """Define a cor-base (a do texto do cartão no tema corrente)."""
        if isinstance(color, QColor) and color.isValid():
            self._base = QColor(color)

    def is_animating(self) -> bool:
        return self._timer.isActive()

    def start_animation(self) -> None:
        self._phase = 0.0
        if not self._timer.isActive():
            self._timer.start()

    def stop_animation(self) -> None:
        self._timer.stop()

    # ── Interno ───────────────────────────────────────────────────────

    def hideEvent(self, event):  # noqa: N802 (assinatura do Qt)
        self.stop_animation()
        super().hideEvent(event)

    def _tick(self) -> None:
        self._phase = (self._phase + self._PHASE_STEP) % 1.0
        self.update()

    def _line_gradient(self, line_w: int) -> QLinearGradient:
        dim = QColor(self._base)
        dim.setAlpha(self._DIM_ALPHA)
        glow = QColor(self._base)
        glow.setAlpha(self._GLOW_ALPHA)
        # A crista passeia dentro de [0.05, 0.95] para as bordas nunca ficarem
        # "acesas" (evita o piscar seco no fim de cada volta).
        pos = 0.05 + self._phase * 0.90
        grad = QLinearGradient(0.0, 0.0, float(line_w), 0.0)
        grad.setColorAt(0.0, dim)
        grad.setColorAt(max(pos - self._GLOW_HALF_WIDTH, 0.001), dim)
        grad.setColorAt(pos, glow)
        grad.setColorAt(min(pos + self._GLOW_HALF_WIDTH, 0.999), dim)
        grad.setColorAt(1.0, dim)
        return grad

    def paintEvent(self, event):  # noqa: N802 (assinatura do Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        width = max(self.width(), 1)
        y = 0
        for ratio in self._LINE_RATIOS:
            line_w = max(int(width * ratio), 1)
            painter.setBrush(QBrush(self._line_gradient(line_w)))
            painter.drawRoundedRect(0, y, line_w, self._LINE_HEIGHT, 4, 4)
            y += self._LINE_HEIGHT + self._LINE_GAP
        painter.end()


class AIResponseCard(QFrame):
    """Estados: idle → thinking → streaming → done | error.

    - ``start(status)``: entra em *thinking* (status visível + Parar +
      skeleton shimmer no corpo).
    - ``set_status(texto)``: atualiza a linha de status (ex.: ticks de
      raciocínio do A1: "🤔 Raciocinando… 12s") e acumula o passo na timeline.
    - ``append_text(token)`` / ``set_text(texto)``: corpo da resposta
      (*streaming*, o skeleton sai de cena); Parar continua disponível.
    - ``finish()``: *done* — o texto fica; a timeline vira discreta.
    - ``fail(msg)``: *error* — mensagem + Tentar de novo.
    """

    stop_requested = pyqtSignal()
    retry_requested = pyqtSignal()

    STATE_IDLE = "idle"
    STATE_THINKING = "thinking"
    STATE_STREAMING = "streaming"
    STATE_DONE = "done"
    STATE_ERROR = "error"

    # Teto da timeline: passos além disso são ruído (e o cartão é pequeno).
    MAX_STEPS = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiResponseCard")
        self._state = self.STATE_IDLE
        self._steps: list[str] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setObjectName("aiResponseStatusLbl")
        header.addWidget(self._status_lbl, stretch=1)

        self._stop_btn = QPushButton("Parar")
        self._stop_btn.setIcon(emoji_icon("⏹"))
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setObjectName("aiResponseActionBtn")
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        header.addWidget(self._stop_btn)

        self._retry_btn = QPushButton("Tentar de novo")
        self._retry_btn.setIcon(emoji_icon("🔄"))
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_btn.setObjectName("aiResponseActionBtn")
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        header.addWidget(self._retry_btn)
        lay.addLayout(header)

        # Timeline colapsável dos passos do agente. O texto do botão é ASCII +
        # triângulo geométrico (▸/▾) — nada de emoji embutido em botão (Onda
        # 0.1: emoji em .text() renderiza sobreposto no Windows).
        self._steps_toggle = QPushButton("")
        self._steps_toggle.setCheckable(True)
        self._steps_toggle.setFlat(True)
        self._steps_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._steps_toggle.setObjectName("aiResponseStepsToggle")
        self._steps_toggle.setVisible(False)
        self._steps_toggle.toggled.connect(lambda _checked: self._sync_steps_ui())
        lay.addWidget(self._steps_toggle, alignment=Qt.AlignmentFlag.AlignLeft)

        self._steps_lbl = QLabel("")
        self._steps_lbl.setWordWrap(True)
        self._steps_lbl.setObjectName("aiResponseStepsLbl")
        self._steps_lbl.setVisible(False)
        lay.addWidget(self._steps_lbl)

        # Skeleton: ocupa o corpo enquanto o 1º token não chega.
        self._skeleton = _SkeletonLines(self)
        lay.addWidget(self._skeleton)

        self._body_lbl = QLabel("")
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body_lbl.setObjectName("aiResponseBodyLbl")
        lay.addWidget(self._body_lbl)

        self._apply_state(self.STATE_IDLE)

    def _swap_object_name(self, widget, object_name: str) -> None:
        """Delegado ao helper compartilhado ``styles.swap_object_name``."""
        from src.gui.styles import swap_object_name
        swap_object_name(widget, object_name)

    # ── API de estados ────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    def start(self, status: str = "🤔 Pensando…") -> None:
        self._body_lbl.setText("")
        self._steps = []
        self._collapse_steps()
        self._swap_object_name(self._status_lbl, "aiResponseStatusLbl")
        self._status_lbl.setText(status)
        self._record_step(status)
        self._apply_state(self.STATE_THINKING)

    def set_status(self, status: str) -> None:
        """Atualiza a linha de status durante thinking/streaming."""
        if status and self._state in (self.STATE_THINKING, self.STATE_STREAMING):
            self._status_lbl.setText(status)
            self._record_step(status)
            self._sync_steps_ui()

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
        self._swap_object_name(self._status_lbl, "aiResponseStatusLblError")
        self._status_lbl.setText(message)
        self._apply_state(self.STATE_ERROR)

    def text(self) -> str:
        return self._body_lbl.text()

    def status_text(self) -> str:
        return self._status_lbl.text()

    def steps(self) -> list[str]:
        """Passos acumulados na timeline (cópia)."""
        return list(self._steps)

    # ── Interno ───────────────────────────────────────────────────────

    @staticmethod
    def _normalize_step(status: str) -> str:
        """Tira o contador volátil do fim do status ("(42 tokens · 7s)")."""
        text = (status or "").strip()
        return _VOLATILE_TAIL.sub("", text).strip() or text

    def _record_step(self, status: str) -> None:
        """Acumula um passo, ignorando repetições consecutivas do mesmo."""
        step = self._normalize_step(status)
        if not step or (self._steps and self._steps[-1] == step):
            return
        self._steps.append(step)
        del self._steps[:-self.MAX_STEPS]

    def _collapse_steps(self) -> None:
        """Colapsa a timeline sem re-entrar em ``_sync_steps_ui``."""
        self._steps_toggle.blockSignals(True)
        self._steps_toggle.setChecked(False)
        self._steps_toggle.blockSignals(False)

    def _sync_steps_ui(self) -> None:
        has_steps = bool(self._steps) and self._state != self.STATE_IDLE
        self._steps_toggle.setVisible(has_steps)
        if not has_steps:
            self._collapse_steps()
            self._steps_lbl.setVisible(False)
            return
        finished = self._state in (self.STATE_DONE, self.STATE_ERROR)
        if finished:
            # Acabou: a timeline volta a colapsar e fica discreta (o QSS
            # diferencia pelo objectName; sem regra, só perde o destaque).
            self._collapse_steps()
        name = "aiResponseStepsToggleDone" if finished else "aiResponseStepsToggle"
        if self._steps_toggle.objectName() != name:
            self._swap_object_name(self._steps_toggle, name)
        expanded = self._steps_toggle.isChecked()
        count = len(self._steps)
        self._steps_toggle.setText(
            f"{'▾' if expanded else '▸'} {count} "
            f"{'passo' if count == 1 else 'passos'}")
        self._steps_lbl.setText("\n".join(f"• {s}" for s in self._steps))
        self._steps_lbl.setVisible(expanded)

    def _apply_state(self, state: str) -> None:
        self._state = state
        in_progress = state in (self.STATE_THINKING, self.STATE_STREAMING)
        self._status_lbl.setVisible(in_progress or state == self.STATE_ERROR)
        self._stop_btn.setVisible(in_progress)
        self._retry_btn.setVisible(state == self.STATE_ERROR)
        self._body_lbl.setVisible(state in (self.STATE_STREAMING, self.STATE_DONE))
        # Skeleton só no gap pré-primeiro-token (thinking); some no 1º chunk.
        show_skeleton = state == self.STATE_THINKING
        self._skeleton.setVisible(show_skeleton)
        if show_skeleton:
            self._skeleton.set_base_color(
                self._body_lbl.palette().color(self._body_lbl.foregroundRole()))
            self._skeleton.start_animation()
        else:
            self._skeleton.stop_animation()
        self._sync_steps_ui()
