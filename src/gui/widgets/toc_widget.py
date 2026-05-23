"""Widget de sumário (Table of Contents)."""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import pyqtSignal
from src.readers.base_reader import TOCEntry


class TOCWidget(QTreeWidget):
    """Widget de árvore para exibir o sumário de um documento."""

    page_selected = pyqtSignal(int)  # Emite o número da página

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.set_theme("dark")
        self.itemClicked.connect(self._on_item_clicked)

    def set_theme(self, theme: str):
        """Aplica folha de estilos (QSS) correspondente ao tema selecionado (Claro, Sépia ou Escuro)."""
        if theme == "light":
            bg = "#f4f4f5"
            fg = "#1A1A1A"
            hover = "#e4e4e7"
            selected_bg = "rgba(99, 102, 241, 0.1)"
            selected_fg = "#6366f1"
        elif theme == "sepia":
            bg = "#ebe5d9"
            fg = "#5B4636"
            hover = "#dfd8c8"
            selected_bg = "rgba(139, 108, 66, 0.15)"
            selected_fg = "#8b6c42"
        else: # "dark" ou fallback
            bg = "#18181b"
            fg = "#e4e4e7"
            hover = "#27272a"
            selected_bg = "rgba(99, 102, 241, 0.2)"
            selected_fg = "#818cf8"

        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {bg};
                border: none;
                color: {fg};
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 6px 8px;
                border-radius: 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: {hover};
            }}
            QTreeWidget::item:selected {{
                background-color: {selected_bg};
                color: {selected_fg};
            }}
        """)

    def load_toc(self, entries: list[TOCEntry]) -> None:
        """Carrega o sumário no widget."""
        self.clear()
        parent_stack: list[QTreeWidgetItem | None] = [None]

        for entry in entries:
            item = QTreeWidgetItem()
            item.setText(0, entry.title)
            item.setData(0, 256, entry.page)  # Role customizado para a página

            # Determina o pai baseado no nível
            while len(parent_stack) > entry.level + 1:
                parent_stack.pop()

            parent = parent_stack[-1] if parent_stack else None
            if parent:
                parent.addChild(item)
            else:
                self.addTopLevelItem(item)

            parent_stack.append(item)

        self.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        page = item.data(0, 256)
        if page is not None:
            self.page_selected.emit(page)
