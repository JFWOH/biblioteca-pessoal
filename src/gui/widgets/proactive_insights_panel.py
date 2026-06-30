"""Painel de Insights do agente proativo: histórico das observações da sessão.

Complementa o rodapé (que mostra a observação mais recente, transitória) com um
registro persistente dentro do dock do leitor.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal


class ProactiveInsightsPanel(QWidget):
    flashcard_requested = pyqtSignal(str)
    dismiss_requested = pyqtSignal(int)  # obs_id — usuário dispensou a observação

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("proactiveInsights")
        self._count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self._title = QLabel("💡 Insights do Proativo")
        header.addWidget(self._title)
        header.addStretch()
        self._clear_btn = QPushButton("Limpar")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear)
        header.addWidget(self._clear_btn)
        root.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._list = QVBoxLayout(self._container)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(8)
        self._list.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        self._empty = QLabel()
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)

        self._agent_active = False
        self._refresh_empty_text()

        self.set_theme("dark")

    # ── API ───────────────────────────────────────────────────────────

    def set_agent_active(self, active: bool):
        """Reflete no texto-vazio se o agente proativo está ligado.

        Sem isso, o painel pedia 'Ative o agente…' mesmo com ele já ativo.
        """
        self._agent_active = active
        self._refresh_empty_text()

    def _refresh_empty_text(self):
        if self._agent_active:
            self._empty.setText(
                "Agente proativo ativo.\n\n"
                "As observações aparecem aqui e no rodapé conforme você avança "
                "na leitura."
            )
        else:
            self._empty.setText(
                "Nenhuma observação ainda.\n\n"
                "Ative o agente em ⋯ → 🧠 Agente Proativo e navegue pelas páginas; "
                "as observações aparecem aqui e no rodapé."
            )

    def add_observation(self, obs: dict):
        tipo = (obs.get("tipo") or "Observação").strip()
        conf = (obs.get("confianca") or "").strip()
        texto = obs.get("texto", "")
        head = f"{tipo} · {conf}" if conf else tipo
        self._prepend(self._make_card(
            head, texto, "#10b981", with_flashcard=True, obs_id=obs.get("id")))

    def add_error(self, msg: str):
        self._prepend(self._make_card("Aviso", msg, "#f59e0b", with_flashcard=False))

    def clear(self):
        while self._list.count():
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._count = 0
        self._empty.setVisible(True)
        self._scroll.setVisible(False)

    # ── Internos ──────────────────────────────────────────────────────

    def _prepend(self, card: QFrame):
        self._list.insertWidget(0, card)
        self._count += 1
        self._empty.setVisible(False)
        self._scroll.setVisible(True)

    def _dismiss_card(self, frame: QFrame, obs_id: int):
        self.dismiss_requested.emit(obs_id)
        frame.setParent(None)
        frame.deleteLater()
        self._count = max(0, self._count - 1)
        if self._count == 0:
            self._empty.setVisible(True)
            self._scroll.setVisible(False)

    def _make_card(self, header_text: str, body_text: str, accent: str,
                   with_flashcard: bool, obs_id=None) -> QFrame:
        frame = QFrame()
        frame.setObjectName("insightCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        head = QLabel(header_text.upper())
        head.setStyleSheet(f"color: {accent}; font-size: 10px; font-weight: 700; background: transparent; border: none;")
        header_row.addWidget(head)
        header_row.addStretch()
        # ✕ de dispensa: só para observações persistidas (com id).
        if obs_id is not None:
            close_btn = QPushButton("✕")
            close_btn.setFixedSize(18, 18)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; color: #6b7280;"
                " font-size: 11px; } QPushButton:hover { color: #f87171; }"
            )
            close_btn.clicked.connect(
                lambda _checked=False, f=frame, oid=obs_id: self._dismiss_card(f, oid))
            header_row.addWidget(close_btn)
        lay.addLayout(header_row)

        body = QLabel(body_text)
        body.setObjectName("insightBody")
        body.setWordWrap(True)
        lay.addWidget(body)

        if with_flashcard and (body_text or "").strip():
            fc = QPushButton("🃏 Flashcard")
            fc.setCursor(Qt.CursorShape.PointingHandCursor)
            fc.setStyleSheet(
                "QPushButton { background: transparent; color: #3b82f6; border: 1px solid #2563eb;"
                " border-radius: 6px; padding: 3px 8px; font-size: 11px; }"
                " QPushButton:hover { background: rgba(37,99,235,0.15); }"
            )
            fc.clicked.connect(lambda _checked=False, t=body_text: self.flashcard_requested.emit(t))
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(fc)
            lay.addLayout(row)
        return frame

    def set_theme(self, theme: str):
        if theme == "light":
            bg, border, text, muted, card_bg = "#ffffff", "#e4e4e7", "#1a1a1a", "#71717a", "#f4f4f5"
        elif theme == "sepia":
            bg, border, text, muted, card_bg = "#f4ecd8", "#d4cbb8", "#433422", "#8b7355", "#ebe5d9"
        else:
            bg, border, text, muted, card_bg = "#161920", "#2d333f", "#e5e7eb", "#94a3b8", "#20242d"

        self.setStyleSheet(f"""
            #proactiveInsights {{ background-color: {bg}; }}
            QFrame#insightCard {{ background-color: {card_bg}; border: 1px solid {border}; border-radius: 8px; }}
            QLabel#insightBody {{ color: {text}; font-size: 12px; background: transparent; border: none; }}
        """)
        self._title.setStyleSheet(f"color: {text}; font-size: 13px; font-weight: 600;")
        self._empty.setStyleSheet(f"color: {muted}; font-size: 12px;")
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {muted}; font-size: 11px; }}"
            " QPushButton:hover { color: #f87171; }"
        )
