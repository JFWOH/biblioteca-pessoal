"""Testes do StatsPanel com estatísticas vivas (Tarefa 5.2).

Cobre: cards novos (streak, semana), o gráfico de barras semanal
(``WeeklyBarChart``) e a meta anual — incluindo degradação graciosa quando
as chaves novas do dict ``stats`` estão ausentes (chamador antigo/dict
mínimo) ou quando não há sessões registradas.
"""

from src.gui.widgets.stats_panel import StatsPanel, WeeklyBarChart

BASE_STATS = {
    "total": 10, "reading": 2, "read": 5, "unread": 3, "favorites": 1,
    "total_reading_time_seconds": 3600, "formats": {"pdf": 8, "epub": 2},
}


def _stats(**overrides):
    data = dict(BASE_STATS)
    data.update(overrides)
    return data


# ── StatsPanel: cards novos ──────────────────────────────────────────────────

class TestStatsPanelNewCards:
    def test_has_streak_and_week_cards(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        assert "streak" in panel._cards
        assert "week" in panel._cards

    def test_streak_value_rendered(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        panel.update_stats(_stats(streak_days=5))
        assert panel._cards["streak"]._value_label.text() == "5"

    def test_missing_streak_key_degrades_to_zero(self, qtbot):
        """Dict sem 'streak_days' (chamador antigo) não deve lançar exceção
        nem deixar o card em estado indefinido."""
        panel = StatsPanel()
        qtbot.addWidget(panel)
        panel.update_stats(_stats())
        assert panel._cards["streak"]._value_label.text() == "0"

    def test_week_minutes_under_an_hour_shows_minutes(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        weekly = [{"week": "2026-W29", "label": "S29", "minutes": 45}]
        panel.update_stats(_stats(weekly_minutes=weekly))
        assert panel._cards["week"]._value_label.text() == "45m"

    def test_week_minutes_over_an_hour_shows_hours(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        weekly = [{"week": "2026-W29", "label": "S29", "minutes": 125}]
        panel.update_stats(_stats(weekly_minutes=weekly))
        assert panel._cards["week"]._value_label.text() == "2h05"


# ── StatsPanel: meta anual ───────────────────────────────────────────────────

class TestStatsPanelAnnualGoal:
    def test_goal_hidden_when_not_configured(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        panel.update_stats(_stats())
        assert panel._goal_bar.isHidden() is True

    def test_goal_hidden_when_zero(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        panel.update_stats(_stats(annual_goal_books=0))
        assert panel._goal_bar.isHidden() is True

    def test_goal_shown_and_progress_set_when_configured(self, qtbot):
        panel = StatsPanel()
        qtbot.addWidget(panel)
        panel.update_stats(_stats(annual_goal_books=24, books_read_this_year=6))
        assert panel._goal_bar.isHidden() is False
        assert panel._goal_bar.maximum() == 24
        assert panel._goal_bar.value() == 6
        assert panel._goal_caption.text() == "6 de 24 livros"

    def test_goal_progress_clamped_to_goal(self, qtbot):
        """Mais livros lidos que a meta (ultrapassou a meta) não deve
        estourar a barra de progresso."""
        panel = StatsPanel()
        qtbot.addWidget(panel)
        panel.update_stats(_stats(annual_goal_books=5, books_read_this_year=9))
        assert panel._goal_bar.value() == 5


# ── WeeklyBarChart ────────────────────────────────────────────────────────────

class TestWeeklyBarChart:
    def test_empty_data_shows_hint_no_crash(self, qtbot):
        chart = WeeklyBarChart()
        qtbot.addWidget(chart)
        chart.set_data([])
        assert chart._layout.count() >= 1

    def test_set_data_creates_one_column_per_week(self, qtbot):
        chart = WeeklyBarChart()
        qtbot.addWidget(chart)
        weeks = [
            {"week": f"2026-W{i:02d}", "label": f"S{i:02d}", "minutes": i * 10}
            for i in range(20, 28)
        ]
        chart.set_data(weeks)
        # 8 colunas de semana + 1 stretch final.
        assert chart._layout.count() == 9

    def test_set_data_replaces_previous_bars(self, qtbot):
        chart = WeeklyBarChart()
        qtbot.addWidget(chart)
        chart.set_data([{"week": "2026-W20", "label": "S20", "minutes": 10}])
        chart.set_data([{"week": "2026-W21", "label": "S21", "minutes": 20}])
        # 1 coluna + 1 stretch — não acumula barras de chamadas anteriores.
        assert chart._layout.count() == 2

    def test_all_zero_minutes_does_not_crash(self, qtbot):
        chart = WeeklyBarChart()
        qtbot.addWidget(chart)
        weeks = [{"week": "2026-W20", "label": "S20", "minutes": 0}]
        chart.set_data(weeks)
        assert chart._layout.count() == 2
