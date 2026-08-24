"""Resiliência do SQLite a "database is locked" ENTRE PROCESSOS.

O mesmo arquivo .db é escrito pela GUI, pelo servidor MCP (processo à parte) e
por ferramentas de CLI. ``LibraryDB._write_lock`` só serializa threads do
processo atual, então aqui cada "outro processo" é simulado por uma CONEXÃO
sqlite3 independente segurando ``BEGIN IMMEDIATE`` (o lock de escrita é do
ARQUIVO, não do processo — a simulação é fiel do ponto de vista do SQLite).
"""
import sqlite3
import threading
import time

import pytest

from src.core.database import LibraryDB, _is_lock_error


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "lib.db"


def _book(db) -> int:
    return db.add_book(title="Livro", file_path="/tmp/x.pdf", file_format="pdf")


class ImpatientDB(LibraryDB):
    """Timeouts minúsculos para os testes de lock não travarem a suíte."""

    _BUSY_TIMEOUT_S = 0.05     # 50ms de espera do SQLite
    _LOCK_RETRIES = 2          # 3 tentativas no total
    _LOCK_BACKOFF_S = 0.01     # 10ms → 20ms


class _FlakyConn:
    """Proxy da conexão que falha as primeiras execuções casando com ``needle``.

    ``sqlite3.Connection`` é tipo C (não aceita monkeypatch), então injetamos o
    proxy em ``db._local.conn`` — o mesmo lugar de onde a property ``conn`` lê.
    """

    def __init__(self, real, needle: str, falhas: int = 1):
        self._real = real
        self._needle = needle
        self._restantes = falhas
        self.falhas_injetadas = 0

    def execute(self, sql, *args, **kwargs):
        if self._needle in sql and self._restantes > 0:
            self._restantes -= 1
            self.falhas_injetadas += 1
            raise sqlite3.OperationalError("database is locked")
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _hold_write_lock(path, hold_s: float, ready: threading.Event) -> threading.Thread:
    """Segura o lock de escrita do arquivo numa conexão própria por ``hold_s``.

    A conexão nasce e morre na mesma thread (``check_same_thread`` do sqlite3).
    """

    def _run():
        conn = sqlite3.connect(str(path), timeout=0)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO tags (name, color) VALUES ('travado', '#000')")
            ready.set()
            time.sleep(hold_s)
            conn.rollback()
        finally:
            conn.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    assert ready.wait(timeout=5), "lock concorrente não foi adquirido"
    return t


# ── Configuração da conexão ───────────────────────────────────────────────

def test_conexao_aplica_busy_timeout_e_wal(db_path):
    db = LibraryDB(db_path)
    try:
        assert db.conn.execute("PRAGMA busy_timeout").fetchone()[0] == int(
            LibraryDB._BUSY_TIMEOUT_S * 1000)
        assert db.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        db.close()


# ── (a) lock temporário de outra conexão: a escrita conclui ───────────────

def test_escrita_conclui_apos_lock_temporario_de_outra_conexao(db_path):
    """Outra conexão segura o lock de escrita por ~200ms; a escrita espera e passa."""
    db = LibraryDB(db_path)
    try:
        bid = _book(db)
        holder = _hold_write_lock(db_path, 0.2, threading.Event())

        started = time.monotonic()
        db.add_chat_turn(bid, "user", "escrita sob contenção")
        elapsed = time.monotonic() - started

        holder.join(timeout=5)
        assert not holder.is_alive()
        assert elapsed >= 0.1  # esperou de fato, em vez de estourar na hora
        assert db.get_chat_turns(bid) == [
            {"role": "user", "content": "escrita sob contenção"}]
    finally:
        db.close()


def test_prune_conclui_apos_lock_temporario_de_outra_conexao(db_path):
    db = LibraryDB(db_path)
    try:
        bid = _book(db)
        for i in range(6):
            db.add_chat_turn(bid, "user", f"m{i}")

        holder = _hold_write_lock(db_path, 0.2, threading.Event())
        db.prune_chat_turns(bid, 3)
        holder.join(timeout=5)

        assert [t["content"] for t in db.get_chat_turns(bid, limit=10)] == ["m3", "m4", "m5"]
    finally:
        db.close()


def test_retry_repete_escrita_quando_sqlite_devolve_busy_na_hora(db_path):
    """Resíduo que o busy_timeout NÃO cobre: SQLITE_BUSY devolvido na hora.

    Determinístico: a 1ª tentativa falha, a 2ª grava — prova que a camada de
    retry (e não só o busy_timeout) está no caminho da escrita.
    """
    db = ImpatientDB(db_path)
    try:
        bid = _book(db)
        real = db.conn
        flaky = _FlakyConn(real, "INSERT INTO chat_turns")
        db._local.conn = flaky
        try:
            db.add_chat_turn(bid, "user", "passou na segunda")
        finally:
            db._local.conn = real

        assert flaky.falhas_injetadas == 1
        assert db.get_chat_turns(bid) == [{"role": "user", "content": "passou na segunda"}]
    finally:
        db.close()


def test_retry_nao_duplica_linhas_em_metodo_multi_statement(db_path):
    """``update_reading_progress`` faz vários INSERT/UPDATE antes do commit.

    Sem o ``rollback`` antes de repetir, o trabalho pendente da tentativa
    abortada somaria de novo (``seconds = seconds + excluded.seconds``).
    """
    db = ImpatientDB(db_path)
    try:
        bid = _book(db)
        real = db.conn
        flaky = _FlakyConn(real, "reading_sessions")
        db._local.conn = flaky
        try:
            db.update_reading_progress(bid, 5, 100, time_spent=60, today="2026-08-24")
        finally:
            db._local.conn = real

        assert flaky.falhas_injetadas == 1
        total = db.conn.execute(
            "SELECT seconds FROM reading_sessions WHERE book_id=?", (bid,)).fetchone()[0]
        assert total == 60  # e não 120
        assert db.get_reading_progress(bid)["current_page"] == 5
    finally:
        db.close()


# ── (b) lock permanente: erro claro, sem travar ───────────────────────────

def test_lock_permanente_propaga_erro_claro_sem_travar(db_path):
    """Espera limitada: o SQLite gasta seu busy_timeout e o erro sobe."""
    db = ImpatientDB(db_path)
    holder = sqlite3.connect(str(db_path), timeout=0)
    try:
        bid = _book(db)
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT INTO tags (name, color) VALUES ('travado', '#000')")

        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError) as excinfo:
            db.add_chat_turn(bid, "user", "nunca entra")
        elapsed = time.monotonic() - started

        assert _is_lock_error(excinfo.value)
        assert "lock" in str(excinfo.value).lower()
        # Desistiu rápido: não multiplicou o busy_timeout pelas tentativas.
        assert elapsed < 2
    finally:
        holder.rollback()
        holder.close()
        db.close()


def test_retry_desiste_apos_o_limite_de_tentativas(db_path):
    """Falha instantânea e permanente: tenta ``_LOCK_RETRIES``+1 vezes e propaga."""
    db = ImpatientDB(db_path)
    try:
        bid = _book(db)
        real = db.conn
        flaky = _FlakyConn(real, "INSERT INTO chat_turns", falhas=99)
        db._local.conn = flaky
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                db.add_chat_turn(bid, "user", "sempre travado")
        finally:
            db._local.conn = real

        assert flaky.falhas_injetadas == ImpatientDB._LOCK_RETRIES + 1
        assert db.get_chat_turns(bid) == []
    finally:
        db.close()


def test_erro_que_nao_e_lock_propaga_sem_repetir(db_path):
    db = ImpatientDB(db_path)
    try:
        bid = _book(db)
        real = db.conn

        class _BoomConn(_FlakyConn):
            def execute(self, sql, *args, **kwargs):
                if self._needle in sql:
                    self.falhas_injetadas += 1
                    raise sqlite3.OperationalError("no such column: xyz")
                return self._real.execute(sql, *args, **kwargs)

        boom = _BoomConn(real, "INSERT INTO chat_turns")
        db._local.conn = boom
        try:
            with pytest.raises(sqlite3.OperationalError, match="no such column"):
                db.add_chat_turn(bid, "user", "erro real")
        finally:
            db._local.conn = real

        assert boom.falhas_injetadas == 1  # sem repetição
    finally:
        db.close()


def test_is_lock_error_classifica_mensagens():
    assert _is_lock_error(sqlite3.OperationalError("database is locked"))
    assert _is_lock_error(sqlite3.OperationalError("database table is locked: books"))
    assert _is_lock_error(sqlite3.OperationalError("database is busy"))
    assert not _is_lock_error(sqlite3.OperationalError("no such table: books"))


# ── (c) comportamento normal intacto ──────────────────────────────────────

def test_escritas_normais_seguem_funcionando(db_path):
    db = LibraryDB(db_path)
    try:
        bid = _book(db)
        db.add_chat_turn(bid, "user", "oi")
        db.add_chat_turn(bid, "assistant", "ola")
        assert db.get_chat_turns(bid) == [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "ola"},
        ]

        for i in range(4):
            db.add_chat_turn(bid, "user", f"m{i}")
        db.prune_chat_turns(bid, 2)
        assert len(db.get_chat_turns(bid, limit=10)) == 2

        # Demais caminhos de escrita decorados mantêm o contrato antigo.
        db.update_book(bid, read_status="reading")
        assert db.get_book(bid)["read_status"] == "reading"
        assert db.add_annotation(bid, 3, content="nota")
        assert len(db.get_annotations(bid)) == 1
        tag_id = db.create_tag("estudo")
        db.add_tag_to_book(bid, tag_id)
        assert [t["name"] for t in db.get_book_tags(bid)] == ["estudo"]
        coll_id = db.create_collection("Favoritos")
        db.add_book_to_collection(bid, coll_id)
        assert len(db.get_books_in_collection(coll_id)) == 1
        db.update_reading_progress(bid, 10, 100, time_spent=30, today="2026-08-24")
        assert db.get_reading_progress(bid)["current_page"] == 10

        # Metadados preservados pelo decorator (functools.wraps).
        assert LibraryDB.add_chat_turn.__name__ == "add_chat_turn"
        assert LibraryDB.prune_chat_turns.__doc__
    finally:
        db.close()


def test_insercao_duplicada_continua_silenciosa(db_path):
    """IntegrityError é tratado dentro do método — o retry não pode interferir."""
    db = LibraryDB(db_path)
    try:
        bid = _book(db)
        tag_id = db.create_tag("dup")
        db.add_tag_to_book(bid, tag_id)
        db.add_tag_to_book(bid, tag_id)  # não levanta
        assert len(db.get_book_tags(bid)) == 1
    finally:
        db.close()


# ── add_chat_exchange: o trio (2 inserts + poda) numa transação única ──────

def test_add_chat_exchange_grava_e_poda_numa_transacao(db_path):
    db = LibraryDB(db_path)
    try:
        bid = _book(db)
        for i in range(4):
            db.add_chat_turn(bid, "user", f"antigo{i}")

        db.add_chat_exchange(bid, "pergunta", "resposta" * 600, keep=4)

        turns = db.get_chat_turns(bid, limit=10)
        assert len(turns) == 4  # podado dentro da MESMA chamada
        assert turns[-2]["content"] == "pergunta"
        assert turns[-1]["role"] == "assistant"
        assert len(turns[-1]["content"]) == 2000  # truncamento preservado
    finally:
        db.close()


def test_add_chat_exchange_sob_lock_permanente_nao_grava_nada_parcial(db_path):
    """Atomicidade: se a troca não entra INTEIRA, não sobra turno órfão."""
    db = ImpatientDB(db_path)
    holder = sqlite3.connect(str(db_path), timeout=0)
    try:
        bid = _book(db)
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT INTO tags (name, color) VALUES ('travado', '#000')")

        with pytest.raises(sqlite3.OperationalError):
            db.add_chat_exchange(bid, "pergunta", "resposta")

        holder.rollback()
        assert db.get_chat_turns(bid, limit=10) == []
    finally:
        holder.close()
        db.close()


def test_add_chat_exchange_retry_nao_duplica_turnos(db_path):
    """Falha no meio do trio → rollback → repetição limpa: 2 turnos, não 3."""
    db = ImpatientDB(db_path)
    try:
        bid = _book(db)
        real = db.conn
        flaky = _FlakyConn(real, "INSERT INTO chat_turns")
        db._local.conn = flaky
        try:
            db.add_chat_exchange(bid, "pergunta", "resposta")
        finally:
            db._local.conn = real

        assert flaky.falhas_injetadas == 1
        assert [t["role"] for t in db.get_chat_turns(bid, limit=10)] == [
            "user", "assistant"]
    finally:
        db.close()
