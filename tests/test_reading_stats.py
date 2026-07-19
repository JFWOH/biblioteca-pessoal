"""Testes da lógica pura de estatísticas de leitura (Tarefa 5.2).

Sem banco de dados — ``compute_reading_streak``/``compute_weekly_minutes``
recebem listas/dicts diretamente (ADR-006: núcleo puro, testável isolado).
"""

from src.core.reading_stats import (
    MAX_SESSION_SECONDS_PER_PAGE,
    clamp_session_seconds,
    compute_reading_streak,
    compute_weekly_minutes,
    total_elapsed_seconds,
)


# ── compute_reading_streak ──────────────────────────────────────────────────

class TestComputeReadingStreak:
    def test_no_dates_returns_zero(self):
        assert compute_reading_streak([], today="2026-07-16") == 0

    def test_single_day_today(self):
        assert compute_reading_streak(["2026-07-16"], today="2026-07-16") == 1

    def test_consecutive_days_ending_today(self):
        dates = ["2026-07-14", "2026-07-15", "2026-07-16"]
        assert compute_reading_streak(dates, today="2026-07-16") == 3

    def test_streak_does_not_break_if_today_not_read_yet(self):
        """Regra: não leu ainda HOJE, mas leu ONTEM — streak continua
        contando a partir de ontem (não zera antes do dia acabar)."""
        dates = ["2026-07-14", "2026-07-15"]
        assert compute_reading_streak(dates, today="2026-07-16") == 2

    def test_streak_breaks_after_a_full_day_gap(self):
        """Nem hoje nem ontem têm sessão → streak zerado, mesmo com
        histórico de dias consecutivos mais antigos."""
        dates = ["2026-07-10", "2026-07-11", "2026-07-12"]
        assert compute_reading_streak(dates, today="2026-07-16") == 0

    def test_gap_in_the_middle_stops_the_count(self):
        dates = ["2026-07-10", "2026-07-14", "2026-07-15", "2026-07-16"]
        assert compute_reading_streak(dates, today="2026-07-16") == 3

    def test_accepts_set_of_dates(self):
        dates = {"2026-07-15", "2026-07-16"}
        assert compute_reading_streak(dates, today="2026-07-16") == 2

    def test_defaults_to_system_today_when_not_injected(self):
        # Sem 'today' injetado, usa date.today() — só garante que não lança.
        assert compute_reading_streak([]) == 0


# ── compute_weekly_minutes ──────────────────────────────────────────────────

class TestComputeWeeklyMinutes:
    def test_empty_sessions_returns_all_weeks_zeroed(self):
        result = compute_weekly_minutes([], weeks=8, today="2026-07-16")
        assert len(result) == 8
        assert all(w["minutes"] == 0 for w in result)

    def test_result_ordered_oldest_to_newest_current_week_last(self):
        result = compute_weekly_minutes([], weeks=4, today="2026-07-16")
        # 2026-07-16 é uma quinta-feira da semana ISO 29 de 2026.
        assert result[-1]["week"] == "2026-W29"

    def test_sums_seconds_into_minutes_for_matching_week(self):
        sessions = [
            {"date": "2026-07-14", "seconds": 1800},  # semana corrente (S29)
            {"date": "2026-07-15", "seconds": 1800},  # mesma semana
        ]
        result = compute_weekly_minutes(sessions, weeks=4, today="2026-07-16")
        assert result[-1]["minutes"] == 60

    def test_sessions_outside_window_are_ignored(self):
        sessions = [{"date": "2020-01-01", "seconds": 3600}]
        result = compute_weekly_minutes(sessions, weeks=4, today="2026-07-16")
        assert all(w["minutes"] == 0 for w in result)

    def test_malformed_rows_are_skipped_not_raised(self):
        sessions = [{"date": "not-a-date", "seconds": 100}, {"seconds": 100}, {}]
        result = compute_weekly_minutes(sessions, weeks=4, today="2026-07-16")
        assert all(w["minutes"] == 0 for w in result)

    def test_label_is_short_iso_week_form(self):
        result = compute_weekly_minutes([], weeks=1, today="2026-07-16")
        assert result[0]["label"] == "S29"


# ── clamp_session_seconds (teto anti-idle por página) ───────────────────────

class TestClampSessionSeconds:
    def test_normal_value_truncated_to_int(self):
        assert clamp_session_seconds(42.7) == 42

    def test_above_cap_returns_cap(self):
        """Página aberta por horas (idle) conta só o teto — anti-distorção."""
        assert clamp_session_seconds(7200.0) == MAX_SESSION_SECONDS_PER_PAGE

    def test_default_cap_is_300_seconds(self):
        assert MAX_SESSION_SECONDS_PER_PAGE == 300

    def test_exactly_cap_is_kept(self):
        assert clamp_session_seconds(300.0) == 300

    def test_custom_cap_respected(self):
        assert clamp_session_seconds(100.0, cap=60) == 60

    def test_zero_returns_zero(self):
        assert clamp_session_seconds(0.0) == 0

    def test_negative_returns_zero(self):
        """monotonic nunca regride, mas entrada inválida não pode virar
        sessão negativa."""
        assert clamp_session_seconds(-5.0) == 0

    def test_nan_returns_zero(self):
        assert clamp_session_seconds(float("nan")) == 0

    def test_non_numeric_returns_zero(self):
        assert clamp_session_seconds(None) == 0
        assert clamp_session_seconds("abc") == 0


# ── total_elapsed_seconds (pausa por minimizar — limitação 5.2 corrigida) ───

class TestTotalElapsedSeconds:
    def test_no_running_segment_returns_accumulated(self):
        """started_at=None (cronômetro pausado/nunca iniciado): só o
        acumulado conta."""
        assert total_elapsed_seconds(accumulated=42.0, started_at=None, now=100.0) == 42.0

    def test_running_segment_added_to_accumulated(self):
        assert total_elapsed_seconds(accumulated=10.0, started_at=90.0, now=100.0) == 20.0

    def test_zero_accumulated_and_no_running_segment(self):
        assert total_elapsed_seconds(accumulated=0.0, started_at=None, now=100.0) == 0.0

    def test_started_at_in_future_does_not_go_negative(self):
        """Relógio nunca deveria regredir, mas por segurança um started_at
        maior que now não pode subtrair do acumulado."""
        assert total_elapsed_seconds(accumulated=5.0, started_at=200.0, now=100.0) == 5.0

    def test_multiple_pause_resume_cycles_accumulate(self):
        """Simula 2 ciclos de pausa/retomada (minimizar/restaurar 2x) antes
        do consumo final — o acumulado cresce a cada pausa."""
        acc = 0.0
        # Trecho 1: lê por 30s, minimiza.
        acc = total_elapsed_seconds(acc, started_at=0.0, now=30.0)
        assert acc == 30.0
        # Restaura, lê por mais 20s, minimiza de novo.
        acc = total_elapsed_seconds(acc, started_at=50.0, now=70.0)
        assert acc == 50.0
        # Restaura, lê 10s, troca de página (consumo final).
        total = total_elapsed_seconds(acc, started_at=80.0, now=90.0)
        assert total == 60.0

    def test_cap_only_applied_by_clamp_at_final_consumption(self):
        """O teto anti-idle não é aplicado por trecho aqui — pausar/retomar
        repetidamente não deve burlar o cap; ele é aplicado 1x, no total,
        por clamp_session_seconds no ponto de consumo."""
        acc = total_elapsed_seconds(0.0, started_at=0.0, now=250.0)
        acc = total_elapsed_seconds(acc, started_at=300.0, now=400.0)  # +100s → 350s
        assert acc == 350.0  # sem teto ainda
        assert clamp_session_seconds(acc) == MAX_SESSION_SECONDS_PER_PAGE  # teto no consumo
