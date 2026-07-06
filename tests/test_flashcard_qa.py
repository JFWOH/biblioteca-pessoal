"""Testes do flashcard pergunta/resposta gerado a partir de insights (item 1 UX)."""
import io
import json

from src.core.study_prompts import build_flashcard_qa_prompt, parse_flashcard_qa


# ── Helpers puros ─────────────────────────────────────────────────────

def test_build_prompt_contains_insight():
    p = build_flashcard_qa_prompt("A entropia mede a desordem.")
    assert "A entropia mede a desordem." in p
    assert "pergunta" in p and "resposta" in p


def test_build_prompt_empty_returns_none():
    assert build_flashcard_qa_prompt("") is None
    assert build_flashcard_qa_prompt("   ") is None


def test_parse_valid_pt_keys():
    content = '{"pergunta": "O que mede a entropia?", "resposta": "A desordem."}'
    assert parse_flashcard_qa(content) == ("O que mede a entropia?", "A desordem.")


def test_parse_accepts_front_back_keys():
    content = '{"front": "Q?", "back": "A."}'
    assert parse_flashcard_qa(content) == ("Q?", "A.")


def test_parse_sanitizes_noise_around_json():
    content = 'Claro! Aqui está:\n{"pergunta": "Q?", "resposta": "A."}\nEspero que ajude.'
    assert parse_flashcard_qa(content) == ("Q?", "A.")


def test_parse_invalid_or_incomplete_returns_none():
    assert parse_flashcard_qa("sem json aqui") is None
    assert parse_flashcard_qa('{"pergunta": "só pergunta"}') is None
    assert parse_flashcard_qa('{"pergunta": "", "resposta": "x"}') is None
    assert parse_flashcard_qa(None) is None


# ── Worker (Ollama mockado) ───────────────────────────────────────────

class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(content: str):
    body = json.dumps({"message": {"content": content}}).encode()

    def _fake(req, timeout=0):
        return _FakeResp(body)

    return _fake


def test_worker_emits_generated(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker

    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen('{"pergunta": "O que é X?", "resposta": "É Y."}'))
    w = FlashcardQAWorker("insight sobre X", model="fake:1b")
    got, fails = [], []
    w.generated.connect(lambda f, b: got.append((f, b)))
    w.failed.connect(fails.append)
    w.run()  # síncrono no teste (sem start)
    assert got == [("O que é X?", "É Y.")]
    assert fails == []


def test_worker_failure_emits_failed(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker

    def _boom(req, timeout=0):
        raise OSError("ollama fora")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    w = FlashcardQAWorker("insight", model="fake:1b")
    fails = []
    w.failed.connect(fails.append)
    w.run()
    assert len(fails) == 1  # chamador aplica o fallback (insight no verso)


def test_worker_invalid_model_response_emits_failed(qtbot, monkeypatch):
    from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen("não sei fazer json"))
    w = FlashcardQAWorker("insight", model="fake:1b")
    fails = []
    w.failed.connect(fails.append)
    w.run()
    assert fails == ["resposta do modelo inválida"]


def test_worker_empty_text_fails_fast(qtbot):
    from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker

    w = FlashcardQAWorker("   ", model="fake:1b")
    fails = []
    w.failed.connect(fails.append)
    w.run()
    assert fails == ["insight vazio"]
