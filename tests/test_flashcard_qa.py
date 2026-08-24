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


def test_worker_without_explicit_model_prefers_fast_task_model(qtbot, monkeypatch):
    """Sem model= explícito, o worker roteia para o modelo "fast" do tier e
    desliga o thinking (§1.3 da revisão: flashcard P/R é tarefa estruturada;
    benchmark 2026-07-06: e4b 9,8s → 3,3s com think=false)."""
    from src.core.hardware_capability_service import HardwareCapabilityService
    from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker

    # Onda Q: cache de CLASSE da sonda de coexistência — zera para o
    # roteamento não depender dos modelos instalados na máquina da suíte.
    HardwareCapabilityService.reset_fast_task_probe()

    captured = {}

    def fake_resolve(url, preferred=None, timeout=3):
        captured["preferred"] = preferred
        return preferred or "gemma4:e4b"

    def fake_urlopen(req, timeout=0):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        body = json.dumps({"message": {
            "content": '{"pergunta": "Q?", "resposta": "A."}'}}).encode()
        return _FakeResp(body)

    monkeypatch.setattr(
        "src.core.graph.concept_extractor.resolve_llm_model", fake_resolve)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    w = FlashcardQAWorker("insight sobre X")  # model=None (default)
    got = []
    w.generated.connect(lambda f, b: got.append((f, b)))
    w.run()

    assert captured["preferred"] == "gemma4:e4b"
    assert captured["payload"]["think"] is False
    assert got == [("Q?", "A.")]
