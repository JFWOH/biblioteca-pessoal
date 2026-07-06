"""Testes do cliente Ollama unificado (src/core/ollama_client.py).

Sprint A2 do workflow de otimização (revisão de engenharia 2026-07-05 §3.1):
consolida ~6 implementações independentes de "montar payload + chamar
/api/chat" num único módulo core puro. Estes testes cobrem o contrato do
cliente isoladamente; os chamadores (orchestrator, workers) têm seus
próprios testes de regressão inalterados.
"""

import json
from unittest.mock import MagicMock, patch

from src.core import ollama_client
from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE


def _mock_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = json.dumps(body).encode("utf-8")
    return resp


class TestBuildChatPayload:
    def test_minimal_payload_has_keep_alive_and_num_predict(self):
        payload = ollama_client.build_chat_payload(
            "gemma4:e4b", [{"role": "user", "content": "oi"}])
        assert payload["keep_alive"] == OLLAMA_KEEP_ALIVE
        assert payload["options"]["num_predict"] == 4096
        assert "tools" not in payload
        assert "format" not in payload

    def test_optional_fields_only_added_when_set(self):
        payload = ollama_client.build_chat_payload(
            "gemma4:e4b", [], tools=[{"type": "function"}],
            response_format="json", temperature=0.2,
            num_ctx=8192, repeat_penalty=1.15, repeat_last_n=512)
        assert payload["tools"] == [{"type": "function"}]
        assert payload["format"] == "json"
        assert payload["options"]["temperature"] == 0.2
        assert payload["options"]["num_ctx"] == 8192
        assert payload["options"]["repeat_penalty"] == 1.15
        assert payload["options"]["repeat_last_n"] == 512

    def test_think_false_included_default_absent(self):
        """think=False desliga o raciocínio (tarefas estruturadas); None
        não envia o campo — o default do modelo prevalece (tarefas profundas)."""
        with_think = ollama_client.build_chat_payload(
            "gemma4:e4b", [], think=False)
        assert with_think["think"] is False
        default = ollama_client.build_chat_payload("gemma4:e4b", [])
        assert "think" not in default


class TestChatOnce:
    def test_returns_stripped_content(self):
        resp = _mock_response({"message": {"content": "  olá mundo  "}})
        with patch("urllib.request.urlopen", return_value=resp):
            content = ollama_client.chat_once(
                "http://localhost:11434", "gemma4:e4b",
                [{"role": "user", "content": "oi"}])
        assert content == "olá mundo"

    def test_missing_message_returns_empty_string(self):
        resp = _mock_response({})
        with patch("urllib.request.urlopen", return_value=resp):
            content = ollama_client.chat_once(
                "http://localhost:11434", "gemma4:e4b", [])
        assert content == ""

    def test_payload_reaches_correct_endpoint_non_streaming(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _mock_response({"message": {"content": "ok"}})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ollama_client.chat_once(
                "http://localhost:11434/", "gemma4:e4b",
                [{"role": "user", "content": "oi"}],
                response_format="json", temperature=0.1, num_predict=512,
                timeout_s=20, think=False)

        assert captured["url"] == "http://localhost:11434/api/chat"
        assert captured["payload"]["stream"] is False
        assert captured["payload"]["format"] == "json"
        assert captured["payload"]["think"] is False
        assert captured["payload"]["options"]["temperature"] == 0.1
        assert captured["payload"]["options"]["num_predict"] == 512
        assert captured["timeout"] == 20

    def test_propagates_exceptions(self):
        with patch("urllib.request.urlopen", side_effect=OSError("conexão recusada")):
            try:
                ollama_client.chat_once("http://localhost:11434", "gemma4:e4b", [])
                assert False, "deveria ter propagado a exceção"
            except OSError:
                pass


class TestStreamChat:
    @staticmethod
    def _mock_stream(lines: list[bytes]) -> MagicMock:
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.__iter__ = lambda s: iter(lines)
        return resp

    def test_yields_message_dicts_with_done_merged_in(self):
        lines = [
            json.dumps({"message": {"content": "Olá "}}).encode("utf-8"),
            json.dumps({"message": {"content": "mundo"}, "done": True,
                       "done_reason": "stop"}).encode("utf-8"),
        ]
        with patch("urllib.request.urlopen", return_value=self._mock_stream(lines)):
            chunks = list(ollama_client.stream_chat(
                "http://localhost:11434", "gemma4:e4b",
                [{"role": "user", "content": "oi"}]))

        assert [c["content"] for c in chunks] == ["Olá ", "mundo"]
        assert chunks[0]["done"] is False
        assert chunks[1]["done"] is True
        assert chunks[1]["done_reason"] == "stop"

    def test_skips_empty_and_invalid_lines(self):
        lines = [
            b"",
            b"not-json{{{",
            json.dumps({"message": {"content": "ok"}, "done": True}).encode("utf-8"),
        ]
        with patch("urllib.request.urlopen", return_value=self._mock_stream(lines)):
            chunks = list(ollama_client.stream_chat(
                "http://localhost:11434", "gemma4:e4b", []))
        assert len(chunks) == 1
        assert chunks[0]["content"] == "ok"

    def test_thinking_field_passed_through(self):
        lines = [
            json.dumps({"message": {"thinking": "raciocinando..."}}).encode("utf-8"),
            json.dumps({"message": {"content": "resposta"}, "done": True}).encode("utf-8"),
        ]
        with patch("urllib.request.urlopen", return_value=self._mock_stream(lines)):
            chunks = list(ollama_client.stream_chat(
                "http://localhost:11434", "gemma4:e4b", []))
        assert chunks[0].get("thinking") == "raciocinando..."
        assert "content" not in chunks[0] or not chunks[0]["content"]

    def test_tools_and_options_reach_payload(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return self._mock_stream([
                json.dumps({"message": {"content": "ok"}, "done": True}).encode("utf-8"),
            ])

        tools_def = [{"type": "function", "function": {"name": "vector_search"}}]
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            list(ollama_client.stream_chat(
                "http://localhost:11434", "gemma4:e4b",
                [{"role": "user", "content": "oi"}],
                tools=tools_def, temperature=0.1, num_predict=4096,
                num_ctx=8192, repeat_penalty=1.15, repeat_last_n=512,
                timeout_s=120))

        assert captured["payload"]["stream"] is True
        assert captured["payload"]["tools"] == tools_def
        assert captured["payload"]["options"]["repeat_penalty"] == 1.15
        assert captured["payload"]["options"]["repeat_last_n"] == 512
        assert captured["timeout"] == 120
