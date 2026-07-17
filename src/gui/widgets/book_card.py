"""Widget de card de livro para a grade da biblioteca."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsDropShadowEffect,
    QProgressBar, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QFont, QCursor

from src.utils.constants import COVER_WIDTH, COVER_HEIGHT


class BookCard(QWidget):
    """Card visual para exibir um livro na biblioteca.

    Detecta automaticamente se o arquivo físico existe e aplica
    um estilo âmbar de aviso caso esteja ausente (livro fantasma).
    """

    clicked = pyqtSignal(int)            # book_id
    double_clicked = pyqtSignal(int)     # book_id — abre o leitor
    selected_changed = pyqtSignal(int, bool)  # book_id, selecionado?
    # book_id, ação escolhida no menu de contexto (Tarefa 2.5):
    # "open" | "favorite" | "collection" | "fetch_metadata" | "delete"
    context_action = pyqtSignal(int, str)

    def __init__(self, book_data: dict, parent=None):
        super().__init__(parent)
        self._book = book_data
        self._book_id = book_data.get("id", 0)
        self._is_selected = False

        # Sanity check: arquivo existe no disco?
        file_path = book_data.get("file_path", "")
        self._is_broken = bool(file_path) and not Path(file_path).exists()

        self.setObjectName("bookCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(COVER_WIDTH + 20, COVER_HEIGHT + 80)
        self._setup_ui()
        self._apply_shadow()

        if self._is_broken:
            self.setToolTip(f"⚠️ Arquivo não encontrado:\n{file_path}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Capa
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(COVER_WIDTH, COVER_HEIGHT)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setScaledContents(True)

        if self._is_broken:
            self._set_broken_cover()
        else:
            cover_path = self._book.get("cover_path", "")
            if cover_path:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    self._cover_label.setPixmap(
                        pixmap.scaled(
                            COVER_WIDTH, COVER_HEIGHT,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self._cover_label.setObjectName("bookCoverImage")
                else:
                    self._set_placeholder_cover()
            else:
                self._set_placeholder_cover()

        layout.addWidget(self._cover_label)

        # Barra fina de progresso de leitura (Tarefa 2.1): só aparece com
        # progresso > 0 — discreta, sob a capa, sem disputar espaço com o
        # badge de "quebrado" (que fica na linha de indicadores, abaixo).
        pct = self._book.get("percentage") or 0
        try:
            pct = max(0, min(100, int(round(float(pct)))))
        except (TypeError, ValueError):
            pct = 0
        self._progress_bar = None
        if pct > 0:
            self._progress_bar = QProgressBar()
            self._progress_bar.setObjectName("bookCardProgress")
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(pct)
            self._progress_bar.setTextVisible(False)
            self._progress_bar.setFixedHeight(4)
            self._progress_bar.setToolTip(f"{pct}% lido")
            layout.addWidget(self._progress_bar)

        # Título
        title = self._book.get("title", "Sem título")
        title_label = QLabel(title)
        title_label.setObjectName("bookCardTitle")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(36)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        font = title_label.font()
        font.setPointSize(9)
        font.setWeight(QFont.Weight.DemiBold)
        title_label.setFont(font)
        layout.addWidget(title_label)

        # Autor
        author = self._book.get("author", "")
        if author:
            author_label = QLabel(author)
            author_label.setObjectName("bookCardAuthor")
            author_label.setMaximumHeight(18)
            font2 = author_label.font()
            font2.setPointSize(8)
            author_label.setFont(font2)
            layout.addWidget(author_label)

        # Indicadores (formato + badges)
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)

        fmt = self._book.get("file_format", "").upper()
        if fmt:
            fmt_label = QLabel(fmt)
            fmt_label.setObjectName("badge")
            fmt_label.setFixedHeight(18)
            font3 = fmt_label.font()
            font3.setPointSize(7)
            fmt_label.setFont(font3)
            info_layout.addWidget(fmt_label)

        if self._is_broken:
            broken_badge = QLabel("⚠️ Ausente")
            broken_badge.setObjectName("bookCardBrokenBadge")
            info_layout.addWidget(broken_badge)

        info_layout.addStretch()

        if self._book.get("is_favorite"):
            fav_label = QLabel("⭐")
            fav_label.setFixedSize(18, 18)
            info_layout.addWidget(fav_label)

        layout.addLayout(info_layout)

    def _set_placeholder_cover(self):
        """Capa placeholder quando não há imagem."""
        self._cover_label.setText("📖")
        self._cover_label.setObjectName("bookCoverPlaceholder")

    def _set_broken_cover(self):
        """Capa âmbar de alerta para livros com arquivo ausente."""
        self._cover_label.setText("⚠️")
        self._cover_label.setObjectName("bookCoverBroken")

    def _apply_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def set_selected(self, selected: bool) -> None:
        """Altera o estado de seleção visual do card."""
        self._is_selected = selected
        # Estado dinâmico via propriedade Qt + seletor QSS (#bookCard[selected="true"])
        # em vez de setStyleSheet inline — repolish força o QSS a reavaliar o seletor.
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.selected_changed.emit(self._book_id, selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._book_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._book_id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Botão direito (Tarefa 2.5): ações rápidas sem abrir o livro.

        Reaproveita o roteamento de ações já existente no MainWindow (via
        LibraryView → context_action) — nenhuma lógica de negócio nova aqui,
        só o menu e o sinal.
        """
        menu = self._build_context_menu()
        chosen = menu.exec(self.mapToGlobal(event.pos()))
        self._handle_context_action(chosen)

    def _build_context_menu(self) -> QMenu:
        """Monta o QMenu de contexto. Separado de ``contextMenuEvent`` para
        ser testável sem precisar chamar ``exec()`` (que bloqueia esperando
        interação do usuário)."""
        menu = QMenu(self)
        menu.setObjectName("bookCardContextMenu")

        self._ctx_open = menu.addAction("📂 Abrir")
        fav_label = "☆ Desfavoritar" if self._book.get("is_favorite") else "⭐ Favoritar"
        self._ctx_favorite = menu.addAction(fav_label)
        self._ctx_collection = menu.addAction("📁 Adicionar à coleção…")
        self._ctx_metadata = menu.addAction("🌐 Buscar metadados")
        menu.addSeparator()
        self._ctx_delete = menu.addAction("🗑️ Remover")
        return menu

    def _handle_context_action(self, chosen) -> None:
        """Traduz a QAction escolhida (ou None, se o menu foi fechado sem
        escolha) no sinal ``context_action(book_id, action)``."""
        if chosen is None:
            return
        mapping = {
            self._ctx_open: "open",
            self._ctx_favorite: "favorite",
            self._ctx_collection: "collection",
            self._ctx_metadata: "fetch_metadata",
            self._ctx_delete: "delete",
        }
        action = mapping.get(chosen)
        if action:
            self.context_action.emit(self._book_id, action)

    @property
    def book_data(self) -> dict:
        return self._book

    @property
    def is_broken(self) -> bool:
        """True se o arquivo físico associado não existe no disco."""
        return self._is_broken

    @property
    def is_selected(self) -> bool:
        return self._is_selected

