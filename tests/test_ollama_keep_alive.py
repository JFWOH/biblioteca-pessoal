"""Testes do keep_alive nas chamadas ao Ollama + warmup no startup.

Revisão de engenharia 2026-07-05 §1.1: sem keep_alive o Ollama descarrega o
modelo ~5 min após a última chamada e toda primeira ação de IA paga o reload
a frio. Todos os payloads (chat, embed, generate) devem levar OLLAMA_KEEP_ALIVE
e o MainWindow deve disparar o WarmupWorker alguns segundos após abrir.
"""
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE

_ROOT = Path(__file__).resolve().parent.parent


def _mock_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = json.dumps(body).encode("utf-8")
    return resp


def _capture_urlopen(captured: list, responses: dict):
    """Fake urlopen que grava (url, payload) e responde por sufixo de endpoint."""
    def fake(req, timeout=None):
        payload = json.loads(req.data.decode("utf-8")) if req.data else {}
        captured.append((req.full_url, payload))
        for suffix, body in responses.items():
            if req.full_url.endswith(suffix):
                return _mock_response(body)
        return _mock_response({})
    return fake


def test_keep_alive_constant():
    # Formato de duração aceito pelo Ollama (ex.: "30m", "1h") ou -1 (infinito).
    assert re.fullmatch(r"\d+[smh]", OLLAMA_KEEP_ALIVE) or OLLAMA_KEEP_ALIVE == -1


def test_orchestrator_chat_payload(monkeypatch):
    from src.core.rag.orchestrator import Orchestrator
    engine = MagicMock()
    engine._llm_model = "gemma4:e4b"
    engine._ollama_url = "http://localhost:11434"
    captured = []
    with patch("urllib.request.urlopen",
               side_effect=_capture_urlopen(captured, {"/api/chat": {}})):
        Orchestrator(engine)._call_chat_api([{"role": "user", "content": "oi"}])
    assert captured[0][1]["keep_alive"] == OLLAMA_KEEP_ALIVE


def test_proactive_worker_payload(qtbot):
    from src.gui.workers.proactive_worker import ProactiveWorker
    worker = ProactiveWorker(model="gemma4:e4b", page_text="texto da página")
    assert worker._build_payload()["keep_alive"] == OLLAMA_KEEP_ALIVE


def test_flashcard_worker_payload(qtbot):
    from src.gui.workers.flashcard_qa_worker import FlashcardQAWorker
    captured = []
    worker = FlashcardQAWorker("um insight qualquer", model="gemma4:e4b")
    fake = _capture_urlopen(captured, {"/api/chat": {
        "message": {"content": '{"pergunta": "p?", "resposta": "r"}'}}})
    with patch("urllib.request.urlopen", side_effect=fake):
        worker.run()
    assert captured[0][1]["keep_alive"] == OLLAMA_KEEP_ALIVE


def test_dossier_worker_payload(qtbot):
    from src.gui.workers.dossier_synthesis_worker import DossierSynthesisWorker
    captured = []
    worker = DossierSynthesisWorker("prompt do dossiê", model="gemma4:e4b")
    fake = _capture_urlopen(captured, {"/api/chat": {
        "message": {"content": "síntese gerada"}}})
    with patch("urllib.request.urlopen", side_effect=fake):
        worker.run()
    assert captured[0][1]["keep_alive"] == OLLAMA_KEEP_ALIVE


def test_translation_reviser_payload():
    from src.core.translation_backends.translation_reviser import revise_translation
    captured = []
    draft = "uma tradução rascunho longa o suficiente para passar na sanidade"
    fake = _capture_urlopen(captured, {"/api/chat": {
        "message": {"content": draft + " revisada"}}})
    with patch("urllib.request.urlopen", side_effect=fake):
        out = revise_translation("original text here", draft, model="gemma4:e4b")
    assert out is not None
    assert captured[0][1]["keep_alive"] == OLLAMA_KEEP_ALIVE


def test_concept_extractor_llm_payload():
    from src.core.graph.concept_extractor import ConceptExtractor
    captured = []
    extractor = ConceptExtractor(llm_model="gemma4:e4b")
    fake = _capture_urlopen(captured, {"/api/chat": {
        "message": {"content": '{"concepts": []}'}}})
    with patch("urllib.request.urlopen", side_effect=fake):
        extractor._llm_refine("texto", [("tema", "Tema", 1.0)], max_concepts=5)
    assert captured[0][1]["keep_alive"] == OLLAMA_KEEP_ALIVE


def test_rag_engine_embed_payloads(tmp_path, monkeypatch):
    from src.core.rag_engine import RAGEngine
    from src.core.database import LibraryDB
    db_path = tmp_path / "lib.db"
    LibraryDB(db_path).conn.close()
    engine = RAGEngine(db_path=db_path, chroma_path=tmp_path / "chroma",
                       ollama_url="http://localhost:11434")
    # Evita a consulta a /api/tags dentro do fluxo de embedding.
    monkeypatch.setattr(engine, "get_exact_model_name", lambda name: name)

    captured = []
    dim = [0.1] * 1024
    fake = _capture_urlopen(captured, {"/api/embed": {"embeddings": [dim]}})
    with patch("urllib.request.urlopen", side_effect=fake):
        engine._get_embedding("um texto")
        engine._get_embeddings_batch(["um texto"])
    assert all(p["keep_alive"] == OLLAMA_KEEP_ALIVE for _u, p in captured
               if "/api/embed" in _u)
    assert len(captured) == 2


class TestWarmupWorker:
    def test_posts_llm_and_embed_with_keep_alive(self, qtbot):
        from src.gui.workers.warmup_worker import WarmupWorker
        captured = []
        worker = WarmupWorker(llm_model="gemma4:e4b", embed_model="bge-m3")
        fake = _capture_urlopen(captured, {"/api/generate": {}, "/api/embed": {}})
        with patch("urllib.request.urlopen", side_effect=fake):
            worker.run()
        urls = [u for u, _p in captured]
        assert any(u.endswith("/api/generate") for u in urls)
        assert any(u.endswith("/api/embed") for u in urls)
        assert all(p["keep_alive"] == OLLAMA_KEEP_ALIVE for _u, p in captured)

    def test_graceful_when_ollama_down(self, qtbot):
        from src.gui.workers.warmup_worker import WarmupWorker
        worker = WarmupWorker(llm_model="gemma4:e4b", embed_model="bge-m3")
        with patch("urllib.request.urlopen",
                   side_effect=ConnectionError("Ollama fora")):
            worker.run()  # não pode levantar exceção (ADR-005)

    def test_skips_missing_models(self, qtbot):
        from src.gui.workers.warmup_worker import WarmupWorker
        worker = WarmupWorker(llm_model=None, embed_model=None)
        with patch("urllib.request.urlopen") as mock_open:
            worker.run()
        mock_open.assert_not_called()


def test_main_window_warmup_wiring():
    """Estrutural (MainWindow importa QtWebEngine — não instancia na suíte)."""
    src = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    assert "QTimer.singleShot(3000, self._start_llm_warmup)" in src
    match = re.search(r"def _start_llm_warmup\(self\).*?\n    def ", src, re.DOTALL)
    assert match, "_start_llm_warmup não encontrado"
    body = match.group(0)
    assert "WarmupWorker(" in body
    assert 'self._config.get("rag.llm_model"' in body
    assert 'self._config.get("rag.embed_model"' in body
    assert ".start()" in body
