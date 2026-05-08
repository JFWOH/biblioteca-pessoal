"""Widget de painel de estatísticas da biblioteca."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class StatCard(QFrame):
    """Card individual de estatística."""

    def __init__(self, value: str, label: str, icon: str = "",
                 color: str = "#818cf8", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 12px;
                padding: 4px;
            }}
            QFrame:hover {{
                border-color: {color};
                background-color: #1e1e24;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        # Ícone + valor
        top_layout = QHBoxLayout()
        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size: 20px; color: {color};")
            top_layout.addWidget(icon_lbl)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Valor grande
        val_lbl = QLabel(str(value))
        val_lbl.setObjectName("statValue")
        font = val_lbl.font()
        font.setPointSize(22)
        font.setWeight(QFont.Weight.Bold)
        val_lbl.setFont(font)
        val_lbl.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(val_lbl)

        # Label
        lbl = QLabel(label)
        lbl.setObjectName("statLabel")
        lbl.setStyleSheet("color: #71717a; font-size: 11px; border: none;")
        layout.addWidget(lbl)

        self._value_label = val_lbl

    def update_value(self, value: str):
        self._value_label.setText(str(value))


class StatsPanel(QWidget):
    """Painel de estatísticas da biblioteca."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, StatCard] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Título
        title = QLabel("📊 Estatísticas")
        font = title.font()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setStyleSheet("color: #e4e4e7;")
        layout.addWidget(title)

        # Grid de cards
        grid = QGridLayout()
        grid.setSpacing(12)

        cards_config = [
            ("total", "0", "Total de livros", "📚", "#818cf8"),
            ("reading", "0", "Lendo agora", "📖", "#60a5fa"),
            ("read", "0", "Lidos", "✅", "#34d399"),
            ("unread", "0", "Não lidos", "📋", "#a78bfa"),
            ("favorites", "0", "Favoritos", "⭐", "#fbbf24"),
            ("time", "0h", "Tempo de leitura", "⏱️", "#f472b6"),
        ]

        for i, (key, value, label, icon, color) in enumerate(cards_config):
            card = StatCard(value, label, icon, color)
            self._cards[key] = card
            row = i // 3
            col = i % 3
            grid.addWidget(card, row, col)

        layout.addLayout(grid)

        # Formatos
        self._formats_label = QLabel()
        self._formats_label.setWordWrap(True)
        self._formats_label.setStyleSheet(
            "color: #71717a; font-size: 12px; padding: 8px 0;"
        )
        layout.addWidget(self._formats_label)

        layout.addStretch()

    def update_stats(self, stats: dict):
        """Atualiza os cards com estatísticas do banco."""
        if "total" in self._cards:
            self._cards["total"].update_value(str(stats.get("total", 0)))
        if "reading" in self._cards:
            self._cards["reading"].update_value(str(stats.get("reading", 0)))
        if "read" in self._cards:
            self._cards["read"].update_value(str(stats.get("read", 0)))
        if "unread" in self._cards:
            self._cards["unread"].update_value(str(stats.get("unread", 0)))
        if "favorites" in self._cards:
            self._cards["favorites"].update_value(str(stats.get("favorites", 0)))

        # Tempo de leitura
        seconds = stats.get("total_reading_time_seconds", 0)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"
        if "time" in self._cards:
            self._cards["time"].update_value(time_str)

        # Formatos
        formats = stats.get("formats", {})
        if formats:
            fmt_parts = [f"{fmt.upper()}: {count}" for fmt, count in sorted(formats.items())]
            self._formats_label.setText(f"📄 Formatos: {' · '.join(fmt_parts)}")
        else:
            self._formats_label.setText("")
