"""Widget de sumário (Table of Contents)."""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import pyqtSignal, QSize, Qt
from PyQt6.QtGui import QPixmap, QIcon
from src.readers.base_reader import TOCEntry

# Miniaturas: só nos capítulos (nível 0) e com teto — sumários enormes não
# podem custar segundos de renderização ao abrir o livro.
THUMB_MAX = 40
THUMB_WIDTH = 110
_ICON_SIZE = QSize(44, 60)

_PLACEHOLDER: QIcon | None = None


def _placeholder_icon() -> QIcon:
    """Ícone vazio do tamanho da miniatura, criado sob demanda.

    Reserva a altura da linha ANTES de a miniatura real chegar: sem ele, cada
    miniatura que aterrissa mudaria a altura do item e o sumário inteiro
    saltaria. Transparente de propósito — nada a mais aparece na tela. Criado
    preguiçosamente porque ``QPixmap`` exige uma ``QApplication`` viva.
    """
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        vazio = QPixmap(_ICON_SIZE)
        vazio.fill(Qt.GlobalColor.transparent)
        _PLACEHOLDER = QIcon(vazio)
    return _PLACEHOLDER


class TOCWidget(QTreeWidget):
    """Widget de árvore para exibir o sumário de um documento."""

    page_selected = pyqtSignal(int)  # Emite o número da página

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.setIconSize(_ICON_SIZE)
        self.set_theme("dark")
        self.itemClicked.connect(self._on_item_clicked)
        # página -> itens que esperam a miniatura daquela página (uma mesma
        # página pode aparecer em mais de uma entrada do sumário).
        self._thumb_targets: dict[int, list[QTreeWidgetItem]] = {}

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

    def load_toc(self, entries: list[TOCEntry], with_thumbnails: bool = False) -> None:
        """Carrega o sumário no widget — SEM renderizar miniatura alguma.

        Onda P: renderizar as miniaturas aqui custava ~1,2s de janela congelada
        em PDFs grandes. Agora as entradas aparecem na hora; quando
        ``with_thumbnails`` é ``True`` (leitor que renderiza páginas), os
        capítulos de nível 0 — até ``THUMB_MAX`` — recebem um ícone placeholder
        transparente, que reserva o espaço para a miniatura real chegar depois
        por ``set_thumbnail`` sem sacudir o layout. Quem produz as miniaturas é
        o ``ThumbnailWorker``; as páginas a pedir vêm de ``pending_thumbnails``.
        """
        self.clear()
        self._thumb_targets = {}
        parent_stack: list[QTreeWidgetItem | None] = [None]
        placeholder: QIcon | None = None

        for entry in entries:
            item = QTreeWidgetItem()
            item.setText(0, entry.title)
            item.setData(0, 256, entry.page)  # Role customizado para a página

            if (with_thumbnails and entry.level == 0
                    and len(self._thumb_targets) < THUMB_MAX):
                if placeholder is None:
                    placeholder = _placeholder_icon()
                item.setIcon(0, placeholder)
                self._thumb_targets.setdefault(entry.page, []).append(item)

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

    def pending_thumbnails(self) -> list[int]:
        """Páginas que ainda esperam miniatura, na ordem do sumário."""
        return list(self._thumb_targets.keys())

    def set_thumbnail(self, page: int, png: bytes) -> bool:
        """Aplica a miniatura já renderizada nos itens daquela página.

        Devolve ``False`` (sem quebrar) quando o PNG não decodifica ou a página
        não está mais na lista — entrega atrasada de um livro já fechado.
        """
        alvos = self._thumb_targets.get(int(page))
        if not alvos or not png:
            return False
        pixmap = QPixmap()
        if not pixmap.loadFromData(png):
            return False
        icone = QIcon(pixmap)
        for item in alvos:
            try:
                item.setIcon(0, icone)
            except RuntimeError:
                # Item já destruído (troca de livro no meio da entrega).
                return False
        return True

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        page = item.data(0, 256)
        if page is not None:
            self.page_selected.emit(page)
