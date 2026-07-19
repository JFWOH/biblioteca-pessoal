"""Testes do log diário de sessões de leitura (Tarefa 5.2 — estatísticas vivas).

Cobre: a tabela ``reading_sessions`` alimentada por ``update_reading_progress``
(retrocompatibilidade com chamadores que não passam ``time_spent``), os
métodos agregados (streak, minutos/semana, livros lidos no ano), a limpeza
em ``delete_book`` e o wiring GUI do tempo real (reader_view → main_window,
por checagem estática — padrão da suíte para o reader_view, que não é
instanciável em teste sem WebEngine).
"""

from pathlib import Path

import pytest

from src.core.database import LibraryDB

_ROOT = Path(__file__).resolve().parents[1]
_READER_VIEW = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")
_MAIN_WINDOW = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")


@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "lib.db")
    yield database
    database.close()


def _add_book(db, title="Livro"):
    return db.add_book(title=title, file_path=f"/tmp/{title}.pdf", file_format="pdf")


# ── Retrocompatibilidade ─────────────────────────────────────────────────────

class TestUpdateReadingProgressBackwardCompatible:
    def test_call_without_time_spent_still_works(self, db):
        """Assinatura antiga (sem time_spent/today) continua válida — nenhum
        chamador existente (GUI, testes antigos) precisa mudar."""
        book_id = _add_book(db)
        db.update_reading_progress(book_id, current_page=10, total_pages=100)
        progress = db.get_reading_progress(book_id)
        assert progress["current_page"] == 10

    def test_time_spent_zero_does_not_create_session(self, db):
        """time_spent=0 (o padrão, e o que a GUI atual sempre envia) NÃO
        grava linha em reading_sessions — só time_spent>0 alimenta o log."""
        book_id = _add_book(db)
        db.update_reading_progress(book_id, current_page=5, total_pages=100, time_spent=0)
        rows = db.conn.execute(
            "SELECT * FROM reading_sessions WHERE book_id=?", (book_id,)).fetchall()
        assert rows == []


# ── reading_sessions: upsert por dia ─────────────────────────────────────────

class TestReadingSessionsUpsert:
    def test_time_spent_creates_session_row(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(
            book_id, current_page=5, total_pages=100, time_spent=120, today="2026-07-16")
        row = db.conn.execute(
            "SELECT * FROM reading_sessions WHERE book_id=? AND date=?",
            (book_id, "2026-07-16")).fetchone()
        assert row is not None
        assert row["seconds"] == 120

    def test_multiple_calls_same_day_accumulate_seconds(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(
            book_id, current_page=1, total_pages=100, time_spent=60, today="2026-07-16")
        db.update_reading_progress(
            book_id, current_page=2, total_pages=100, time_spent=90, today="2026-07-16")
        row = db.conn.execute(
            "SELECT seconds FROM reading_sessions WHERE book_id=? AND date=?",
            (book_id, "2026-07-16")).fetchone()
        assert row["seconds"] == 150

    def test_different_days_create_separate_rows(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(
            book_id, current_page=1, total_pages=100, time_spent=60, today="2026-07-15")
        db.update_reading_progress(
            book_id, current_page=2, total_pages=100, time_spent=60, today="2026-07-16")
        rows = db.conn.execute(
            "SELECT date, seconds FROM reading_sessions WHERE book_id=? ORDER BY date",
            (book_id,)).fetchall()
        assert [dict(r) for r in rows] == [
            {"date": "2026-07-15", "seconds": 60},
            {"date": "2026-07-16", "seconds": 60},
        ]

    def test_reading_progress_time_spent_seconds_still_accumulates(self, db):
        """A coluna acumulada antiga (reading_progress.time_spent_seconds)
        continua funcionando exatamente como antes — sessão diária é
        aditiva, não substitui o comportamento existente."""
        book_id = _add_book(db)
        db.update_reading_progress(book_id, current_page=1, total_pages=100, time_spent=60)
        db.update_reading_progress(book_id, current_page=2, total_pages=100, time_spent=40)
        progress = db.get_reading_progress(book_id)
        assert progress["time_spent_seconds"] == 100


# ── get_reading_streak ───────────────────────────────────────────────────────

class TestGetReadingStreak:
    def test_zero_when_no_sessions(self, db):
        assert db.get_reading_streak(today="2026-07-16") == 0

    def test_counts_consecutive_days_via_progress_calls(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(
            book_id, current_page=1, total_pages=100, time_spent=60, today="2026-07-15")
        db.update_reading_progress(
            book_id, current_page=2, total_pages=100, time_spent=60, today="2026-07-16")
        assert db.get_reading_streak(today="2026-07-16") == 2

    def test_streak_across_multiple_books(self, db):
        """A sequência é por DIA (qualquer livro), não por livro."""
        b1 = _add_book(db, "A")
        b2 = _add_book(db, "B")
        db.update_reading_progress(
            b1, current_page=1, total_pages=10, time_spent=60, today="2026-07-15")
        db.update_reading_progress(
            b2, current_page=1, total_pages=10, time_spent=60, today="2026-07-16")
        assert db.get_reading_streak(today="2026-07-16") == 2


# ── get_weekly_reading_minutes ───────────────────────────────────────────────

class TestGetWeeklyReadingMinutes:
    def test_returns_eight_weeks_by_default(self, db):
        result = db.get_weekly_reading_minutes(today="2026-07-16")
        assert len(result) == 8

    def test_empty_db_returns_zeroed_series(self, db):
        result = db.get_weekly_reading_minutes(weeks=4, today="2026-07-16")
        assert all(w["minutes"] == 0 for w in result)

    def test_current_week_reflects_logged_minutes(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(
            book_id, current_page=1, total_pages=100, time_spent=1800, today="2026-07-16")
        result = db.get_weekly_reading_minutes(weeks=4, today="2026-07-16")
        assert result[-1]["minutes"] == 30


# ── get_books_read_in_year ───────────────────────────────────────────────────

class TestGetBooksReadInYear:
    def test_zero_when_nothing_read(self, db):
        assert db.get_books_read_in_year(2026) == 0

    def test_counts_book_completed_this_call(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(book_id, current_page=100, total_pages=100)
        book = db.get_book(book_id)
        assert book["read_status"] == "read"
        year = int(book["date_modified"][:4])
        assert db.get_books_read_in_year(year) == 1

    def test_does_not_double_count_on_reopen(self, db):
        """Reabrir um livro já concluído (nova sessão de leitura) não altera
        date_modified de novo — a contagem do ano de conclusão permanece
        estável mesmo com múltiplas releituras."""
        book_id = _add_book(db)
        db.update_reading_progress(book_id, current_page=100, total_pages=100)
        book_first = db.get_book(book_id)
        first_modified = book_first["date_modified"]

        db.update_reading_progress(book_id, current_page=100, total_pages=100)
        book_second = db.get_book(book_id)
        assert book_second["date_modified"] == first_modified

    def test_unread_and_reading_books_not_counted(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(book_id, current_page=50, total_pages=100)
        year = 2026
        assert db.get_books_read_in_year(year) == 0


# ── Limpeza em delete_book ───────────────────────────────────────────────────

class TestDeleteBookCleansSessions:
    def test_delete_book_removes_reading_sessions(self, db):
        book_id = _add_book(db)
        db.update_reading_progress(
            book_id, current_page=1, total_pages=100, time_spent=60, today="2026-07-16")
        db.delete_book(book_id)
        rows = db.conn.execute(
            "SELECT * FROM reading_sessions WHERE book_id=?", (book_id,)).fetchall()
        assert rows == []


# ── Wiring GUI: tempo real de leitura (checagem estática) ────────────────────
# O ReaderView não é instanciável em teste (QWebEngineView); a suíte valida o
# wiring dele por inspeção do fonte (mesmo padrão de test_*_wiring.py).

class TestReadingTimeWiring:
    def test_progress_signal_carries_seconds(self):
        """O payload do progress_changed foi AMPLIADO (não criado sinal
        paralelo): 4º int = segundos lidos desde a última emissão."""
        assert (
            "progress_changed = pyqtSignal(int, int, int, int)" in _READER_VIEW
        )

    def test_reader_view_uses_monotonic_clock(self):
        """Cronômetro usa time.monotonic (imune a ajuste do relógio de
        parede), nunca time.time."""
        assert "time.monotonic()" in _READER_VIEW

    def test_reader_view_clamps_elapsed_with_core_helper(self):
        """O teto anti-idle vem da função pura do core (ADR-006: lógica no
        core, GUI só consome). Desde a correção da limitação 5.2 (janela
        minimizada pausa o cronômetro), o total consumido combina o
        acumulado de pausas com o trecho em curso via total_elapsed_seconds
        (também puro) antes do clamp — ver TestReadingTimerPauseWiring."""
        assert "from src.core.reading_stats import clamp_session_seconds" in _READER_VIEW
        assert "clamp_session_seconds(total)" in _READER_VIEW

    def test_render_page_emits_elapsed_seconds(self):
        assert "self.progress_changed.emit(self._book_id, page, total, seconds)" in _READER_VIEW

    def test_flush_called_on_close_and_on_book_switch(self):
        """O tempo pendente da última página é descarregado ao fechar o
        leitor E ao abrir outro livro (antes de trocar o _book_id)."""
        assert "def _flush_reading_time(self)" in _READER_VIEW
        # Duas chamadas: open_book (troca de livro) e close_reader.
        assert _READER_VIEW.count("self._flush_reading_time()") >= 2

    def test_main_window_handler_accepts_and_persists_seconds(self):
        """_on_progress recebe o 4º argumento e o repassa como time_spent —
        o elo que liga o cronômetro da GUI ao log reading_sessions."""
        assert (
            "def _on_progress(self, book_id: int, page: int, total: int, "
            "seconds: int = 0)" in _MAIN_WINDOW
        )
        assert "time_spent=seconds" in _MAIN_WINDOW


# ── Wiring GUI: pausa do cronômetro ao minimizar (limitação 5.2 corrigida) ──

class TestReadingTimerPauseWiring:
    def test_reader_view_imports_total_elapsed_seconds(self):
        """A combinação acumulado+trecho em curso é lógica PURA no core
        (ADR-006), não reimplementada na GUI."""
        assert (
            "from src.core.reading_stats import clamp_session_seconds, "
            "total_elapsed_seconds" in _READER_VIEW
        )

    def test_pause_and_resume_methods_exist(self):
        assert "def _pause_reading_timer(self)" in _READER_VIEW
        assert "def _resume_reading_timer(self)" in _READER_VIEW
        assert "def _start_reading_timer(self)" in _READER_VIEW

    def test_render_page_starts_timer_via_helper_not_direct_assignment(self):
        """_render_page delega a _start_reading_timer (que respeita a pausa
        por visibilidade) em vez de setar _page_started_at direto — senão um
        re-render durante a minimização religaria o cronômetro."""
        assert "self._start_reading_timer()" in _READER_VIEW

    def test_main_window_wires_window_state_change_to_pause_resume(self):
        """MainWindow.changeEvent detecta minimizar/restaurar e chama os
        métodos do ReaderView — o core (reading_stats.py) não importa PyQt6
        nem QEvent/QWindowState (ADR-006: threads/eventos só na GUI)."""
        assert "def changeEvent(self, event):" in _MAIN_WINDOW
        assert "QEvent.Type.WindowStateChange" in _MAIN_WINDOW
        assert "Qt.WindowState.WindowMinimized" in _MAIN_WINDOW
        assert "self._reader_view._pause_reading_timer()" in _MAIN_WINDOW
        assert "self._reader_view._resume_reading_timer()" in _MAIN_WINDOW

    def test_core_reading_stats_stays_free_of_pyqt6(self):
        """ADR-006: core/reading_stats.py não pode importar PyQt6/GUI (a
        docstring do módulo MENCIONA "Sem PyQt6" como decisão de design —
        checa só as linhas de import, não o texto inteiro)."""
        src = (_ROOT / "src" / "core" / "reading_stats.py").read_text(encoding="utf-8")
        import_lines = [ln for ln in src.splitlines()
                        if ln.strip().startswith(("import ", "from "))]
        assert not any("PyQt6" in ln for ln in import_lines)
