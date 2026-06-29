"""Testes da camada de memória persistente (chat_turns, agent_feedback, ai_observations)."""
import pytest

from src.core.database import LibraryDB


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db) -> int:
    return db.add_book(title="Livro", file_path="/tmp/x.pdf", file_format="pdf")


def test_chat_turns_roundtrip_and_isolation(db):
    bid = _book(db)
    db.add_chat_turn(bid, "user", "oi")
    db.add_chat_turn(bid, "assistant", "ola")
    assert db.get_chat_turns(bid) == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "ola"},
    ]
    assert db.get_chat_turns(None) == []  # global isolado do livro


def test_chat_turns_global_null_book(db):
    db.add_chat_turn(None, "user", "pergunta global")
    assert db.get_chat_turns(None) == [{"role": "user", "content": "pergunta global"}]


def test_prune_chat_turns_keeps_latest(db):
    bid = _book(db)
    for i in range(10):
        db.add_chat_turn(bid, "user", f"m{i}")
    db.prune_chat_turns(bid, 4)
    h = db.get_chat_turns(bid, limit=100)
    assert len(h) == 4
    assert h[-1]["content"] == "m9"  # mantém os mais recentes
    assert h[0]["content"] == "m6"


def test_clear_chat_turns(db):
    bid = _book(db)
    db.add_chat_turn(bid, "user", "x")
    db.clear_chat_turns(bid)
    assert db.get_chat_turns(bid) == []


def test_content_truncated_to_2000(db):
    bid = _book(db)
    db.add_chat_turn(bid, "user", "a" * 5000)
    assert len(db.get_chat_turns(bid)[0]["content"]) == 2000


def test_feedback_insert(db):
    db.add_feedback(rating=1, kind="answer", query="q", reason="útil")
    db.add_feedback(rating=-1, kind="proactive", book_id=_book(db), page=3)
    n = db.conn.execute("SELECT COUNT(*) FROM agent_feedback").fetchone()[0]
    assert n == 2


def test_observations_roundtrip_and_dismiss(db):
    bid = _book(db)
    oid = db.add_observation(bid, 3, "uma observacao", kind="insight", confidence=0.8)
    obs = db.get_observations(book_id=bid)
    assert len(obs) == 1
    assert obs[0]["content"] == "uma observacao"
    assert obs[0]["page"] == 3

    db.dismiss_observation(oid)
    assert db.get_observations(book_id=bid) == []  # dismissed ocultas por padrão
    assert len(db.get_observations(book_id=bid, include_dismissed=True)) == 1
