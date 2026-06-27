"""Testes do ProactiveWorker: payload (format=json, num_predict) e cancelamento."""
import json
from unittest.mock import MagicMock, patch

from src.gui.workers.proactive_worker import ProactiveWorker


def _fake_chat_response(content: str):
    fake = MagicMock()
    fake.__enter__ = lambda s: s
    fake.__exit__ = MagicMock(return_value=False)
    fake.read.return_value = json.dumps({"message": {"content": content}}).encode("utf-8")
    return fake


class TestProactiveWorkerPayload:
    def test_build_payload_uses_json_format(self):
        w = ProactiveWorker("gemma4:e4b", "Texto da página de teste.", "http://localhost:11434")
        payload = w._build_payload()
        assert payload["format"] == "json"
        assert payload["stream"] is False
        assert payload["model"] == "gemma4:e4b"

    def test_build_payload_reduces_num_predict(self):
        w = ProactiveWorker("gemma4:e4b", "Texto.", "http://localhost:11434")
        payload = w._build_payload()
        # Observação curta (1-4 frases): não deve reservar os antigos 4096 tokens.
        assert payload["options"]["num_predict"] <= 512

    def test_build_payload_includes_page_text(self):
        w = ProactiveWorker("m", "CONTEUDO_UNICO_XYZ", "http://localhost:11434")
        payload = w._build_payload()
        assert "CONTEUDO_UNICO_XYZ" in payload["messages"][0]["content"]


class TestProactiveWorkerRun:
    def test_run_emits_observation_on_success(self, qtbot):
        w = ProactiveWorker("m", "Texto da página.", "http://localhost:11434")
        received = []
        w.finished.connect(received.append)

        obs = {"tipo": "Observação do texto", "confianca": "Alta", "texto": "Algo interessante."}
        with patch("urllib.request.urlopen", return_value=_fake_chat_response(json.dumps(obs))):
            w.run()

        assert len(received) == 1
        assert received[0]["tipo"] == "Observação do texto"

    def test_cancel_suppresses_emit(self, qtbot):
        """Cancelamento cooperativo: nenhum sinal é emitido após cancel()."""
        w = ProactiveWorker("m", "Texto da página.", "http://localhost:11434")
        received = []
        errors = []
        w.finished.connect(received.append)
        w.error.connect(errors.append)

        w.cancel()  # cancelado antes de processar
        obs = {"tipo": "Observação do texto", "confianca": "Alta", "texto": "x"}
        with patch("urllib.request.urlopen", return_value=_fake_chat_response(json.dumps(obs))):
            w.run()

        assert received == []  # resultado descartado, sem mutação tardia da UI
        assert errors == []

    def test_run_emits_error_on_invalid_json(self, qtbot):
        w = ProactiveWorker("m", "Texto.", "http://localhost:11434")
        errors = []
        w.error.connect(errors.append)

        with patch("urllib.request.urlopen", return_value=_fake_chat_response("isso não é json")):
            w.run()

        assert len(errors) == 1
