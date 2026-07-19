"""Widget de painel de estatísticas da biblioteca."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QProgressBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class StatCard(QFrame):
    """Card individual de estatística."""

    def __init__(self, value: str, label: str, icon: str = "",
                 color: str = "#818cf8", parent=None):
        super().__init__(parent)
        # Onda A1: era DARK-ONLY (fundo/borda fixos em setStyleSheet inline).
        # Migrado p/ objectName + regras QSS nos 3 temas (#statCard em
        # styles.py, mesma paleta de #continueCard). QFrame já pinta o
        # próprio background/borda via QSS sem precisar de
        # WA_StyledBackground (esse atributo só é necessário em subclasses
        # de QWidget puro — lição da Onda 0b, não se aplica aqui).
        self.setObjectName("statCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        # Ícone + valor
        top_layout = QHBoxLayout()
        if icon:
            icon_lbl = QLabel(icon)
            # "background: transparent" é necessário mesmo sem cor de fundo
            # própria: sem ele, o QLabel herda o `QWidget { background-color }`
            # global do tema (mais escuro que o #statCard), criando uma caixa
            # visível atrás do glifo — mesma lição do proactive_insights_panel.
            icon_lbl.setStyleSheet(
                f"font-size: 20px; color: {color}; background: transparent; border: none;")
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
        val_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        layout.addWidget(val_lbl)

        # Label — cor/tamanho vêm de #statLabel (styles.py, 3 temas); antes
        # era um cinza fixo (#71717a) via setStyleSheet inline, DARK-ONLY.
        lbl = QLabel(label)
        lbl.setObjectName("statLabel")
        layout.addWidget(lbl)

        self._value_label = val_lbl

    def update_value(self, value: str):
        self._value_label.setText(str(value))


class WeeklyBarChart(QWidget):
    """Gráfico de barras simples com os minutos lidos por semana (Tarefa 5.2).

    Decisão de implementação: em vez de um ``QPainter`` customizado, cada
    barra é um ``QFrame`` cuja altura em pixels é proporcional ao valor —
    assim o gráfico herda o tema (escuro/claro/sépia) via QSS por objectName
    (``#weeklyBarTrack``/``#weeklyBarFill``/``#weeklyBarLabel`` em
    ``styles.py``), sem precisar hardcodar cores no Python nem redesenhar em
    ``paintEvent`` a cada troca de tema. Sem dependência nova (sem
    matplotlib) — só widgets Qt padrão.
    """

    BAR_AREA_HEIGHT = 72
    BAR_WIDTH = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

    def set_data(self, weeks: list[dict]) -> None:
        """Redesenha as barras a partir de ``weeks`` (formato de
        ``reading_stats.compute_weekly_minutes``: lista de dicts com
        ``label`` e ``minutes``). Degradação graciosa: lista vazia (ou sem
        nenhum minuto) mostra uma dica textual, nunca lança exceção.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not weeks:
            hint = QLabel("Nenhuma sessão de leitura registrada ainda.")
            hint.setObjectName("statsEmptyHint")
            self._layout.addWidget(hint)
            self._layout.addStretch()
            return

        max_minutes = max((int(w.get("minutes", 0) or 0) for w in weeks), default=0)

        for week in weeks:
            minutes = int(week.get("minutes", 0) or 0)

            col_widget = QWidget()
            col = QVBoxLayout(col_widget)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(4)

            track = QFrame()
            track.setObjectName("weeklyBarTrack")
            track.setFixedSize(self.BAR_WIDTH, self.BAR_AREA_HEIGHT)
            track.setToolTip(f"{week.get('label', '')}: {minutes} min")
            track_layout = QVBoxLayout(track)
            track_layout.setContentsMargins(2, 2, 2, 2)
            track_layout.setSpacing(0)
            track_layout.addStretch()

            if minutes > 0 and max_minutes > 0:
                fill_h = max(3, int((self.BAR_AREA_HEIGHT - 4) * minutes / max_minutes))
                fill = QFrame()
                fill.setObjectName("weeklyBarFill")
                fill.setFixedSize(self.BAR_WIDTH - 4, fill_h)
                track_layout.addWidget(fill)

            col.addWidget(track, alignment=Qt.AlignmentFlag.AlignHCenter)

            lbl = QLabel(week.get("label", ""))
            lbl.setObjectName("weeklyBarLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(lbl)

            self._layout.addWidget(col_widget)

        self._layout.addStretch()


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
            ("streak", "0", "Sequência", "🔥", "#fb923c"),
            ("week", "0m", "Esta semana", "⏱️", "#22d3ee"),
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

        # Progresso semanal (Tarefa 5.2) — últimas 8 semanas.
        week_title = QLabel("📈 Minutos de leitura — últimas 8 semanas")
        week_title.setObjectName("statsSectionTitle")
        layout.addWidget(week_title)

        self._weekly_chart = WeeklyBarChart()
        layout.addWidget(self._weekly_chart)

        # Meta anual (Tarefa 5.2) — só aparece quando configurada (> 0).
        self._goal_title = QLabel("📚 Meta do ano")
        self._goal_title.setObjectName("statsSectionTitle")
        self._goal_bar = QProgressBar()
        self._goal_bar.setTextVisible(False)
        self._goal_caption = QLabel()
        self._goal_caption.setObjectName("statsGoalCaption")
        self._goal_title.hide()
        self._goal_bar.hide()
        self._goal_caption.hide()
        layout.addWidget(self._goal_title)
        layout.addWidget(self._goal_bar)
        layout.addWidget(self._goal_caption)

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

        # Sequência de leitura (streak) — Tarefa 5.2. Ausência da chave (ex.:
        # chamador antigo/teste com dict mínimo) degrada para 0.
        if "streak" in self._cards:
            self._cards["streak"].update_value(str(stats.get("streak_days", 0)))

        # Série semanal + card "Esta semana" (última entrada da série).
        weekly = stats.get("weekly_minutes") or []
        week_minutes = int(weekly[-1].get("minutes", 0)) if weekly else 0
        if "week" in self._cards:
            if week_minutes >= 60:
                self._cards["week"].update_value(
                    f"{week_minutes // 60}h{week_minutes % 60:02d}")
            else:
                self._cards["week"].update_value(f"{week_minutes}m")
        self._weekly_chart.set_data(weekly)

        # Meta anual — só exibida quando configurada (> 0); degrada
        # ocultando os widgets quando ausente/zero (sem meta definida).
        annual_goal = int(stats.get("annual_goal_books") or 0)
        if annual_goal > 0:
            read_count = int(stats.get("books_read_this_year") or 0)
            self._goal_bar.setRange(0, annual_goal)
            self._goal_bar.setValue(min(read_count, annual_goal))
            self._goal_caption.setText(f"{read_count} de {annual_goal} livros")
            self._goal_title.show()
            self._goal_bar.show()
            self._goal_caption.show()
        else:
            self._goal_title.hide()
            self._goal_bar.hide()
            self._goal_caption.hide()
