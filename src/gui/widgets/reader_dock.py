"""Dock único à direita do leitor, com abas recolhíveis.

Reúne os painéis auxiliares (Assistente, Anotações, …) numa só coluna, exibindo
um por vez. Isso libera espaço de leitura em vez de empilhar vários painéis lado
a lado. Cada conteúdo é um widget arbitrário registrado via ``add_tab``.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.gui.styles import emoji_icon


class ReaderDock(QWidget):
    closed = pyqtSignal()
    tab_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme = "dark"
        self._keys: list[str] = []
        self._labels: dict[str, str] = {}
        self._tab_buttons: dict[str, QPushButton] = {}
        self._widgets: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = QWidget()
        self._header.setObjectName("readerDockHeader")
        self._header.setFixedHeight(40)
        h = QHBoxLayout(self._header)
        h.setContentsMargins(6, 4, 6, 4)
        h.setSpacing(4)
        self._tabs_row = QHBoxLayout()
        self._tabs_row.setSpacing(4)
        h.addLayout(self._tabs_row, 1)
        self._close_btn = QPushButton()
        self._close_btn.setIcon(emoji_icon("✕", 13))
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setToolTip("Recolher painel")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.closed.emit)
        h.addWidget(self._close_btn)
        root.addWidget(self._header)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self.set_theme("dark")

    # ── Gestão de abas ────────────────────────────────────────────────

    def add_tab(self, key: str, label: str, widget: QWidget,
               icon: str | None = None) -> None:
        """Registra um widget como aba. Idempotente por chave.

        ``icon`` (opcional): emoji exibido como ÍCONE do botão da aba
        (``setIcon(emoji_icon(...))``) — nunca embutido em ``label``, senão
        reproduz o bug de sobreposição do Windows (débito da Onda 4). Os
        chamadores devem passar ``label`` SEM emoji e o emoji separadamente
        em ``icon``.
        """
        if key in self._widgets:
            return
        self._keys.append(key)
        self._labels[key] = label
        self._widgets[key] = widget
        self._stack.addWidget(widget)

        btn = QPushButton(label)
        if icon:
            btn.setIcon(emoji_icon(icon, 14))
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked=False, k=key: self.show_tab(k))
        self._tab_buttons[key] = btn
        self._tabs_row.addWidget(btn)

        self._apply_styles()
        if len(self._keys) == 1:
            self.show_tab(key)

    def remove_tab(self, key: str) -> QWidget | None:
        """Remove a aba e devolve o widget (sem destruí-lo)."""
        widget = self._widgets.pop(key, None)
        if widget is not None:
            self._stack.removeWidget(widget)
        btn = self._tab_buttons.pop(key, None)
        if btn is not None:
            self._tabs_row.removeWidget(btn)
            btn.deleteLater()
        self._labels.pop(key, None)
        if key in self._keys:
            self._keys.remove(key)
        if self._keys:
            self.show_tab(self._keys[0])
        return widget

    def has_tab(self, key: str) -> bool:
        return key in self._widgets

    def show_tab(self, key: str) -> None:
        if key not in self._widgets:
            return
        self._stack.setCurrentWidget(self._widgets[key])
        for k, b in self._tab_buttons.items():
            b.setChecked(k == key)
        self.tab_changed.emit(key)

    def current_key(self) -> str | None:
        current = self._stack.currentWidget()
        for k, w in self._widgets.items():
            if w is current:
                return k
        return None

    # ── Tema ──────────────────────────────────────────────────────────

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._apply_styles()

    def _apply_styles(self) -> None:
        if self._theme == "light":
            bg, border, text, muted, accent = "#f4f4f5", "#e4e4e7", "#1a1a1a", "#71717a", "#059669"
            sel_bg = "#ffffff"
        elif self._theme == "sepia":
            bg, border, text, muted, accent = "#ebe5d9", "#d4cbb8", "#433422", "#8b7355", "#8b6c42"
            sel_bg = "#f4ecd8"
        else:
            bg, border, text, muted, accent = "#161920", "#2d333f", "#e5e7eb", "#8b93a1", "#10b981"
            sel_bg = "#0f1115"

        self.setStyleSheet(f"background-color: {bg}; border-left: 1px solid {border};")
        self._header.setStyleSheet(
            f"#readerDockHeader {{ background-color: {bg}; border-bottom: 1px solid {border}; }}"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {muted};"
            f" font-size: 14px; font-weight: bold; border-radius: 4px; }}"
            f" QPushButton:hover {{ color: {text}; background: {border}; }}"
        )
        for key, btn in self._tab_buttons.items():
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {muted};"
                f" font-size: 12px; font-weight: 500; padding: 6px 10px; border-radius: 6px; }}"
                f" QPushButton:hover {{ color: {text}; }}"
                f" QPushButton:checked {{ color: {accent}; background: {sel_bg}; }}"
            )
