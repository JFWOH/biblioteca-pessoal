"""Limitação 5.2 corrigida nesta rodada — cronômetro de leitura pausa quando
a janela minimiza (antes: continuava contando ocioso; só o teto de 300s/
página limitava a distorção).

``ReaderView`` completo não instancia na suíte (QtWebEngine) — harness com os
métodos REAIS ligados (mesmo padrão de ``test_audio_stop_async.py``), com
``time.monotonic()`` controlado via monkeypatch para determinismo.
"""
from src.gui.reader_view import ReaderView


class _TimerHarness:
    # Métodos REAIS sob teste (unbound → chamados com self=harness).
    _start_reading_timer = ReaderView._start_reading_timer
    _pause_reading_timer = ReaderView._pause_reading_timer
    _resume_reading_timer = ReaderView._resume_reading_timer
    _take_elapsed_reading_seconds = ReaderView._take_elapsed_reading_seconds

    def __init__(self):
        self._page_started_at = None
        self._accumulated_page_seconds = 0.0
        self._timer_paused_for_visibility = False


def _patch_clock(monkeypatch, value: float):
    """Fixa time.monotonic() no módulo reader_view (o mesmo `import time`
    usado pelos métodos reais copiados no harness)."""
    from src.gui import reader_view
    monkeypatch.setattr(reader_view.time, "monotonic", lambda: value)


# ── Fluxo básico: iniciar → consumir (sem pausa) ────────────────────────────

def test_start_then_take_returns_elapsed(monkeypatch):
    h = _TimerHarness()
    _patch_clock(monkeypatch, 100.0)
    h._start_reading_timer()
    assert h._page_started_at == 100.0

    _patch_clock(monkeypatch, 130.0)
    assert h._take_elapsed_reading_seconds() == 30
    # Consumido: timestamp e acumulado zerados.
    assert h._page_started_at is None
    assert h._accumulated_page_seconds == 0.0


def test_take_without_any_timer_running_returns_zero():
    h = _TimerHarness()
    assert h._take_elapsed_reading_seconds() == 0


# ── Pausar/retomar (minimizar/restaurar a janela) ───────────────────────────

def test_pause_freezes_running_segment_into_accumulated(monkeypatch):
    h = _TimerHarness()
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()

    _patch_clock(monkeypatch, 20.0)  # minimiza 20s depois
    h._pause_reading_timer()

    assert h._page_started_at is None          # cronômetro parado
    assert h._accumulated_page_seconds == 20.0  # trecho congelado
    assert h._timer_paused_for_visibility is True


def test_pause_without_running_timer_is_noop():
    """Minimizar sem nenhuma leitura em andamento (livro fechado, ou
    cronômetro já consumido) não deve marcar pausa nem inventar tempo."""
    h = _TimerHarness()
    h._pause_reading_timer()
    assert h._timer_paused_for_visibility is False
    assert h._accumulated_page_seconds == 0.0


def test_pause_is_idempotent_double_minimize_event(monkeypatch):
    """Dois eventos WindowStateChange seguidos com o bit Minimized ligado
    (ex.: minimizar duas vezes sem restaurar) não devem contar o trecho
    duas vezes."""
    h = _TimerHarness()
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()
    _patch_clock(monkeypatch, 10.0)
    h._pause_reading_timer()
    assert h._accumulated_page_seconds == 10.0

    _patch_clock(monkeypatch, 999.0)  # muito tempo depois, ainda minimizado
    h._pause_reading_timer()  # segunda chamada: no-op (_page_started_at já é None)
    assert h._accumulated_page_seconds == 10.0


def test_resume_restarts_timer_only_if_paused_for_visibility(monkeypatch):
    h = _TimerHarness()
    # Sem pausa ativa: resume não faz nada (não inventa um cronômetro do nada).
    _patch_clock(monkeypatch, 50.0)
    h._resume_reading_timer()
    assert h._page_started_at is None

    # Pausa real, depois resume.
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()
    _patch_clock(monkeypatch, 5.0)
    h._pause_reading_timer()

    _patch_clock(monkeypatch, 60.0)  # restaura 55s depois de minimizar
    h._resume_reading_timer()
    assert h._page_started_at == 60.0
    assert h._timer_paused_for_visibility is False
    assert h._accumulated_page_seconds == 5.0  # preservado da pausa


def test_full_cycle_pause_resume_then_take_sums_both_segments(monkeypatch):
    """Cenário completo: lê 30s, minimiza, fica minimizado 1h (não conta),
    restaura, lê mais 15s, muda de página — total = 30+15 = 45s."""
    h = _TimerHarness()
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()

    _patch_clock(monkeypatch, 30.0)
    h._pause_reading_timer()  # minimiza — acumulado=30

    _patch_clock(monkeypatch, 3630.0)  # 1h minimizado — NÃO deve contar
    h._resume_reading_timer()  # restaura — reinicia o cronômetro em t=3630

    _patch_clock(monkeypatch, 3645.0)  # lê mais 15s
    assert h._take_elapsed_reading_seconds() == 45  # 30 (antes) + 15 (depois), sem a 1h ociosa


def test_multiple_pause_resume_cycles_before_final_take(monkeypatch):
    h = _TimerHarness()
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()
    _patch_clock(monkeypatch, 10.0)
    h._pause_reading_timer()   # +10 → acumulado=10

    _patch_clock(monkeypatch, 100.0)
    h._resume_reading_timer()
    _patch_clock(monkeypatch, 108.0)
    h._pause_reading_timer()   # +8 → acumulado=18

    _patch_clock(monkeypatch, 500.0)
    h._resume_reading_timer()
    _patch_clock(monkeypatch, 502.0)
    assert h._take_elapsed_reading_seconds() == 20  # 10 + 8 + 2


def test_anti_idle_cap_still_applies_to_combined_total(monkeypatch):
    """O teto de 300s/página (MAX_SESSION_SECONDS_PER_PAGE) continua valendo
    sobre o TOTAL combinado — pausar/retomar não deve permitir burlar o cap
    somando vários trechos abaixo do teto individualmente."""
    h = _TimerHarness()
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()
    _patch_clock(monkeypatch, 250.0)
    h._pause_reading_timer()  # +250

    _patch_clock(monkeypatch, 300.0)
    h._resume_reading_timer()
    _patch_clock(monkeypatch, 400.0)  # +100 → total bruto 350s
    assert h._take_elapsed_reading_seconds() == 300  # teto de MAX_SESSION_SECONDS_PER_PAGE


# ── Re-render durante a janela minimizada (_start_reading_timer) ───────────

def test_start_reading_timer_does_not_run_while_paused_for_visibility(monkeypatch):
    """Se uma página é renderizada (ex.: virada automática da narração
    contínua) enquanto a janela ainda está minimizada, o cronômetro NÃO deve
    religar — senão o tempo minimizado voltaria a ser contado."""
    h = _TimerHarness()
    _patch_clock(monkeypatch, 0.0)
    h._start_reading_timer()
    _patch_clock(monkeypatch, 5.0)
    h._pause_reading_timer()
    assert h._timer_paused_for_visibility is True

    _patch_clock(monkeypatch, 50.0)  # ainda minimizado, uma "renderização" tenta reiniciar
    h._start_reading_timer()
    assert h._page_started_at is None  # continua pendente, não reinicia
