"""Widget de sumário (Table of Contents)."""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon
from src.readers.base_reader import TOCEntry

# Miniaturas: só nos capítulos (nível 0) e com teto — sumários enormes não
# podem custar segundos de renderização ao abrir o livro.
_THUMB_MAX = 40
_THUMB_WIDTH = 110


class TOCWidget(QTreeWidget):
    """Widget de árvore para exibir o sumário de um documento."""

    page_selected = pyqtSignal(int)  # Emite o número da página

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.setIconSize(QSize(44, 60))
        self.set_theme("dark")
        self.itemClicked.connect(self._on_item_clicked)

    def set_theme(self, theme: str):
        """Aplica folha de estilos (QSS) correspondente ao tema selecionado (Claro, Sépia ou Escuro)."""
        if theme == "light":
            bg = "#f4f4f5"
            fg = "#1A1A1A"
            hover = "#e4e4e7"
            selected_bg = "rgba(16, 185, 129, 0.15)"
            selected_fg = "#059669"
        elif theme == "sepia":
            bg = "#ebe5d9"
            fg = "#5B4636"
            hover = "#dfd8c8"
            selected_bg = "rgba(16, 185, 129, 0.15)"
            selected_fg = "#059669"
        else: # "dark" ou fallback
            bg = "#161920"
            fg = "#e5e7eb"
            hover = "#20242d"
            selected_bg = "rgba(16, 185, 129, 0.15)"
            selected_fg = "#10b981"

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

    def load_toc(self, entries: list[TOCEntry], thumb_provider=None) -> None:
        """Carrega o sumário no widget.

        ``thumb_provider``: callable(page, width) -> bytes PNG | None. Quando
        fornecido (PDF), os capítulos de nível 0 ganham miniatura da página.
        """
        self.clear()
        parent_stack: list[QTreeWidgetItem | None] = [None]
        thumbs_rendered = 0

        for entry in entries:
            item = QTreeWidgetItem()
            item.setText(0, entry.title)
            item.setData(0, 256, entry.page)  # Role customizado para a página

            if (thumb_provider is not None and entry.level == 0
                    and thumbs_rendered < _THUMB_MAX):
                try:
                    png = thumb_provider(entry.page, _THUMB_WIDTH)
                except Exception:
                    png = None
                if png:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(png):
                        item.setIcon(0, QIcon(pixmap))
                        thumbs_rendered += 1

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
