"""Popover de tipografia do leitor (aberto pelo botão "Aa" da toolbar).

Controles de fonte, tamanho, entrelinha, margem e tema do leitor. Cada mudança
é emitida na hora (aplicação AO VIVO) — o ``ReaderView`` persiste nas MESMAS
chaves ``reader.*`` da config e re-renderiza a página atual.

Decisão (popover vs QMenu): é um ``QDialog`` frameless NÃO-modal, e não um
``QMenu``/``Qt.Popup``. Um QMenu/Popup fecha ao interagir com o dropdown do
``QFontComboBox`` (popup aninhado) e pode ficar ATRÁS do ``QWebEngineView``
(superfície nativa) na leitura de EPUB. Uma janela de topo frameless aparece
acima do web view e não se fecha ao abrir o combo. O fechamento é explícito:
botão "Aa" (toggle), o "✕" do cabeçalho, ou Esc.

Estilização por object-name nos 3 temas de ``styles.py`` (folha global da
QApplication) — sem QSS inline com cores hardcoded.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QSlider, QFontComboBox, QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.gui.styles import emoji_icon
from src.utils.constants import (
    MIN_FONT_SIZE, MAX_FONT_SIZE, DEFAULT_FONT_SIZE,
    DEFAULT_FONT_FAMILY, DEFAULT_LINE_HEIGHT,
)

_THEMES = [("dark", "Escuro"), ("light", "Claro"), ("sepia", "Sépia")]


class ReaderTypographyPopover(QDialog):
    """Popover flutuante com os controles de tipografia do leitor.

    Sinais:
      - ``typography_changed(dict)``: {font_family, font_size, line_height,
        margin_horizontal} — a cada ajuste de fonte/tamanho/entrelinha/margem.
      - ``theme_changed(str)``: "dark" | "light" | "sepia".
      - ``closed()``: o popover foi ocultado/fechado (sincroniza o botão "Aa").
    """

    typography_changed = pyqtSignal(dict)
    theme_changed = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("readerTypographyPopover")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(False)
        self.setFixedWidth(290)

        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        # Cabeçalho: título + botão de fechar
        header = QHBoxLayout()
        title = QLabel("Tipografia")
        title.setObjectName("readerTypographyTitle")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton()
        close_btn.setIcon(emoji_icon("✕", 12))
        close_btn.setObjectName("readerTypographyClose")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Fechar")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Fonte
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Fonte:"))
        self._font_combo = QFontComboBox()
        self._font_combo.currentFontChanged.connect(self._on_typography_changed)
        font_row.addWidget(self._font_combo, stretch=1)
        layout.addLayout(font_row)

        # Tamanho
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Tamanho:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self._font_size.setValue(DEFAULT_FONT_SIZE)
        self._font_size.setSuffix(" px")
        self._font_size.valueChanged.connect(self._on_typography_changed)
        size_row.addStretch()
        size_row.addWidget(self._font_size)
        layout.addLayout(size_row)

        # Entrelinha (10..30 → 1.0..3.0)
        line_row = QHBoxLayout()
        line_row.addWidget(QLabel("Entrelinha:"))
        self._line_height = QSlider(Qt.Orientation.Horizontal)
        self._line_height.setRange(10, 30)
        self._line_height.setValue(int(DEFAULT_LINE_HEIGHT * 10))
        self._line_label = QLabel(f"{DEFAULT_LINE_HEIGHT:.1f}")
        self._line_label.setFixedWidth(30)
        self._line_height.valueChanged.connect(self._on_line_changed)
        line_row.addWidget(self._line_height, stretch=1)
        line_row.addWidget(self._line_label)
        layout.addLayout(line_row)

        # Margem (horizontal, 20..200 px)
        margin_row = QHBoxLayout()
        margin_row.addWidget(QLabel("Margem:"))
        self._margin = QSlider(Qt.Orientation.Horizontal)
        self._margin.setRange(20, 200)
        self._margin.setValue(60)
        self._margin_label = QLabel("60px")
        self._margin_label.setFixedWidth(40)
        self._margin.valueChanged.connect(self._on_margin_changed)
        margin_row.addWidget(self._margin, stretch=1)
        margin_row.addWidget(self._margin_label)
        layout.addLayout(margin_row)

        # Tema
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Tema:"))
        theme_row.addStretch()
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_buttons: dict[str, QPushButton] = {}
        for key, label in _THEMES:
            btn = QPushButton(label)
            btn.setObjectName("readerThemeButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self._on_theme_clicked(k))
            self._theme_group.addButton(btn)
            self._theme_buttons[key] = btn
            theme_row.addWidget(btn)
        layout.addLayout(theme_row)

    # ── Estado ──────────────────────────────────────────────────────────

    def set_values(self, font_family: str, font_size: int, line_height: float,
                   margin_horizontal: int, theme: str) -> None:
        """Carrega os valores atuais nos controles SEM emitir sinais."""
        self._loading = True
        try:
            self._font_combo.setCurrentFont(QFont(font_family or DEFAULT_FONT_FAMILY))
            self._font_size.setValue(int(font_size))
            self._line_height.setValue(int(round(float(line_height) * 10)))
            self._line_label.setText(f"{float(line_height):.1f}")
            self._margin.setValue(int(margin_horizontal))
            self._margin_label.setText(f"{int(margin_horizontal)}px")
            for key, btn in self._theme_buttons.items():
                btn.setChecked(key == theme)
        finally:
            self._loading = False

    def current_values(self) -> dict:
        return {
            "font_family": self._font_combo.currentFont().family(),
            "font_size": self._font_size.value(),
            "line_height": self._line_height.value() / 10,
            "margin_horizontal": self._margin.value(),
        }

    # ── Sinais internos ─────────────────────────────────────────────────

    def _on_line_changed(self, value: int) -> None:
        self._line_label.setText(f"{value / 10:.1f}")
        self._on_typography_changed()

    def _on_margin_changed(self, value: int) -> None:
        self._margin_label.setText(f"{value}px")
        self._on_typography_changed()

    def _on_typography_changed(self, *args) -> None:
        if self._loading:
            return
        self.typography_changed.emit(self.current_values())

    def _on_theme_clicked(self, theme: str) -> None:
        self._theme_buttons[theme].setChecked(True)
        if self._loading:
            return
        self.theme_changed.emit(theme)

    # ── Ciclo de vida ───────────────────────────────────────────────────

    def show_at(self, global_pos) -> None:
        """Posiciona o canto superior-direito perto de *global_pos* e exibe."""
        self.adjustSize()
        x = global_pos.x() - self.width()
        if x < 0:
            x = global_pos.x()
        self.move(x, global_pos.y())
        self.show()
        self.raise_()
        self.activateWindow()

    def hideEvent(self, event) -> None:
        # Cobre tanto close() quanto hide(): ambos passam por hideEvent.
        self.closed.emit()
        super().hideEvent(event)
