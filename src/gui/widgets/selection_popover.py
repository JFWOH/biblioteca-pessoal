"""Barra de ações flutuante exibida sobre uma seleção de texto/área no leitor.

Oferece ações de IA em um clique (destacar, explicar, traduzir, etc.),
eliminando o fluxo pouco descobrível de 4 passos via clique direito.
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal


class SelectionActionPopover(QFrame):
    """Pequena barra flutuante com ações rápidas para o texto selecionado.

    Emite ``action_requested`` com a chave da ação escolhida e se oculta.
    Chaves: ``highlight``, ``explain``, ``simplify``, ``translate``,
    ``search``, ``save_note``, ``flashcard``, ``word_wise``.

    ``word_wise`` (Tarefa 3.4 — definição rápida) só deve ser incluída pelo
    chamador via :meth:`set_actions` quando a seleção for curta (palavra/
    termo, ~4 palavras); o botão não decide isso sozinho.
    """

    action_requested = pyqtSignal(str)

    _ACTIONS = [
        ("🖍️", "Destacar", "highlight"),
        ("🧠", "Explicar", "explain"),
        ("✨", "Simplificar", "simplify"),
        ("🌐", "Traduzir", "translate"),
        ("🔍", "Web", "search"),
        ("📝", "Anotar", "save_note"),
        ("🃏", "Flashcard", "flashcard"),
        ("📖", "Definição rápida", "word_wise"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SelectionPopover")
        self.setVisible(False)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._buttons: dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        for icon, label, key in self._ACTIONS:
            btn = QPushButton(f"{icon} {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(label)
            btn.clicked.connect(lambda _checked=False, k=key: self._emit(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        self.set_theme("dark")

    def _emit(self, key: str) -> None:
        self.hide()
        self.action_requested.emit(key)

    def set_actions(self, keys) -> None:
        """Exibe apenas as ações cujas chaves estão em ``keys``."""
        allowed = set(keys)
        for key, btn in self._buttons.items():
            btn.setVisible(key in allowed)
        self.adjustSize()

    def show_at(self, pos) -> None:
        """Posiciona (coordenadas do widget pai) e exibe a barra."""
        self.adjustSize()
        self.move(pos)
        self.show()
        self.raise_()

    def set_theme(self, theme: str) -> None:
        if theme == "light":
            bg, border, text, hover = "#ffffff", "#d4d4d8", "#1a1a1a", "#f0fdf4"
        elif theme == "sepia":
            bg, border, text, hover = "#f4ecd8", "#d4cbb8", "#433422", "#eadfca"
        else:  # dark
            bg, border, text, hover = "#1e2227", "#3f3f46", "#e4e4e7", "#2d333f"

        self.setStyleSheet(f"""
            QFrame#SelectionPopover {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#SelectionPopover QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                color: {text};
                font-size: 12px;
                padding: 5px 8px;
            }}
            QFrame#SelectionPopover QPushButton:hover {{
                background: {hover};
                color: #10b981;
            }}
        """)
