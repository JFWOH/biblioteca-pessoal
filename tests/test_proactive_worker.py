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

    def test_build_payload_num_predict_allows_reasoning(self):
        w = ProactiveWorker("gemma4:e4b", "Texto.", "http://localhost:11434")
        payload = w._build_payload()
        # num_predict é um TETO (não reserva). Modelos de raciocínio gastam tokens
        # "pensando" antes do content; um teto baixo (256) devolvia content vazio.
        # Precisa ser folgado o suficiente para o raciocínio + a observação.
        assert payload["options"]["num_predict"] >= 1024

    def test_build_payload_includes_page_text(self):
        w = ProactiveWorker("m", "CONTEUDO_UNICO_XYZ", "http://localhost:11434")
        payload = w._build_payload()
        assert "CONTEUDO_UNICO_XYZ" in payload["messages"][0]["content"]

    def test_build_payload_injects_memory_block(self):
        """Fase 5: o que o agente já disse entra no prompt, antes do trecho."""
        memory = "VOCÊ JÁ FEZ AS OBSERVAÇÕES ABAIXO:\n- (p.3) MEMORIA_UNICA_ABC"
        w = ProactiveWorker("m", "TRECHO_XYZ", "http://localhost:11434",
                            memory_block=memory)
        prompt = w._build_payload()["messages"][0]["content"]
        assert "MEMORIA_UNICA_ABC" in prompt
        assert prompt.index("MEMORIA_UNICA_ABC") < prompt.index("TRECHO_XYZ")

    def test_build_payload_without_memory_is_unchanged(self):
        """Regressão: sem memória o prompt é idêntico ao formato anterior."""
        w = ProactiveWorker("m", "TRECHO_XYZ", "http://localhost:11434")
        prompt = w._build_payload()["messages"][0]["content"]
        assert "VOCÊ JÁ FEZ" not in prompt
        assert "Trecho para análise:\nTRECHO_XYZ" in prompt

    def test_build_payload_injects_preference_block(self):
        """Fase 6: a preferência aprendida entra antes da memória e do trecho."""
        preference = 'PREFERÊNCIA DO LEITOR: EVITE\n- "TIPO_UNICO_DEF" (dispensou 4 de 5)'
        memory = "VOCÊ JÁ FEZ AS OBSERVAÇÕES ABAIXO:\n- (p.3) MEMORIA_UNICA_ABC"
        w = ProactiveWorker("m", "TRECHO_XYZ", "http://localhost:11434",
                            memory_block=memory, preference_block=preference)
        prompt = w._build_payload()["messages"][0]["content"]
        assert "TIPO_UNICO_DEF" in prompt
        assert (prompt.index("TIPO_UNICO_DEF") < prompt.index("MEMORIA_UNICA_ABC")
                < prompt.index("TRECHO_XYZ"))

    def test_build_payload_without_preference_is_unchanged(self):
        """Regressão: sem preferência o prompt é idêntico ao da Fase 5."""
        w = ProactiveWorker("m", "TRECHO_XYZ", "http://localhost:11434")
        prompt = w._build_payload()["messages"][0]["content"]
        assert "PREFERÊNCIA DO LEITOR" not in prompt
        assert "Trecho para análise:\nTRECHO_XYZ" in prompt


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

    def test_run_appends_cross_reference(self, qtbot):
        """Com search_fn, a observação ganha a conexão com outro livro."""
        def fake_search(text):
            return [{"metadata": {"book_id": 99, "title": "Outro Livro", "page_number": 4}, "distance": 0.1}]

        w = ProactiveWorker("m", "texto da página", "http://localhost:11434",
                            search_fn=fake_search, book_id=1)
        received = []
        w.finished.connect(received.append)
        obs = {"tipo": "Observação do texto", "confianca": "Alta", "texto": "Algo."}
        with patch("urllib.request.urlopen", return_value=_fake_chat_response(json.dumps(obs))):
            w.run()

        assert len(received) == 1
        assert "Outro Livro" in received[0]["texto"]
        assert received[0]["texto"].startswith("Algo.")
