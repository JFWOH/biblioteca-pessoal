"""Cartão flutuante com a definição rápida (Word Wise) de um termo.

Tarefa 3.4: quando a seleção no leitor é curta (palavra/termo, ~4 palavras),
o popover de ações ganha a opção "📖 Definição rápida". Ao ser clicada, ESTE
widget aparece perto da seleção mostrando a definição contextual gerada por
um LLM ``think=False`` (tarefa rápida — ver WordWiseWorker). Diferença chave
em relação às outras ações de seleção: NUNCA abre o painel do RAG — o
resultado fica só aqui, inline, como um tooltip persistente.

Mesmo padrão de widget auto-contido do SelectionActionPopover (estilo por
tema aplicado via :meth:`set_theme`, chamado pelo ReaderView a cada troca de
tema — cobre os 3 temas do app).
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


class WordWisePopover(QFrame):
    """Pequeno cartão com a definição rápida de um termo selecionado."""

    _MAX_WIDTH = 280

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WordWisePopover")
        self.setVisible(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMaximumWidth(self._MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self._term_label = QLabel("")
        self._term_label.setObjectName("WordWiseTerm")
        header_row.addWidget(self._term_label, 1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("WordWiseClose")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setToolTip("Fechar")
        self._close_btn.clicked.connect(self.hide)
        header_row.addWidget(self._close_btn, 0)
        layout.addLayout(header_row)

        self._body_label = QLabel("")
        self._body_label.setObjectName("WordWiseBody")
        self._body_label.setWordWrap(True)
        layout.addWidget(self._body_label)

        self.set_theme("dark")

    # ── Estados ──────────────────────────────────────────────────────────

    def show_loading(self, term: str, pos) -> None:
        """Exibe o estado de carregamento para ``term``, ancorado em ``pos``."""
        self._term_label.setText(f"📖 {term}")
        self._body_label.setText("Buscando definição…")
        self.adjustSize()
        self.move(pos)
        self.show()
        self.raise_()

    def show_definition(self, term: str, definition: str) -> None:
        """Substitui o carregamento pela definição gerada."""
        self._term_label.setText(f"📖 {term}")
        self._body_label.setText(definition)
        self.adjustSize()

    def show_error(self, message: str = "Definição indisponível no momento.") -> None:
        """Erro/falha do LLM (ADR-005): mantém o cartão visível com aviso curto."""
        self._body_label.setText(f"⚠️ {message}")
        self.adjustSize()

    # ── Tema ─────────────────────────────────────────────────────────────

    def set_theme(self, theme: str) -> None:
        if theme == "light":
            bg, border, text_main, text_sec = "#ffffff", "#d4d4d8", "#1a1a1a", "#52525b"
        elif theme == "sepia":
            bg, border, text_main, text_sec = "#f4ecd8", "#d4cbb8", "#433422", "#705e4b"
        else:  # dark
            bg, border, text_main, text_sec = "#1e2227", "#3f3f46", "#e4e4e7", "#9ca3af"

        self.setStyleSheet(f"""
            QFrame#WordWisePopover {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel#WordWiseTerm {{
                color: #10b981;
                font-weight: 700;
                font-size: 12px;
            }}
            QLabel#WordWiseBody {{
                color: {text_main};
                font-size: 12px;
            }}
            QPushButton#WordWiseClose {{
                background: transparent;
                border: none;
                color: {text_sec};
                font-size: 11px;
            }}
            QPushButton#WordWiseClose:hover {{
                color: #ef4444;
            }}
        """)
