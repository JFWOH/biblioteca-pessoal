"""Testes da correção de repetição de texto no loop agentic (Orchestrator).

Bug relatado: quando o modelo escreve uma explicação completa e, na MESMA
rodada, chama uma ferramenta de efeito colateral (highlight_book_text /
create_ai_bookmark), o loop pedia ao modelo para "responder de novo" — e ele
reescrevia (às vezes quase palavra por palavra) a explicação que já tinha
dado. A correção trata essa rodada como a resposta final: aplica o efeito
colateral e encerra, sem pedir mais uma rodada de texto.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.rag.orchestrator import Orchestrator, _ACTION_ONLY_TOOLS


def _create_test_db(path: Path) -> Path:
    from src.core.database import LibraryDB
    db = LibraryDB(path)
    db.conn.execute(
        "INSERT INTO books (id, title, author, description, file_path, file_format) VALUES (?,?,?,?,?,?)",
        (1, "Dom Casmurro", "Machado de Assis", "Romance.", "/tmp/fake1.pdf", "pdf"))
    db.conn.commit()
    db.conn.close()
    return path


@pytest.fixture
def test_db(tmp_path) -> Path:
    return _create_test_db(tmp_path / "test_library.db")


@pytest.fixture
def chroma_path(tmp_path) -> Path:
    return tmp_path / "chroma_test"


@pytest.fixture
def fake_embedding() -> list[float]:
    return [0.1] * 768


@pytest.fixture
def mock_engine(test_db, chroma_path, fake_embedding):
    from src.core.rag_engine import RAGEngine
    # is_model_available/is_ollama_available: hermético mesmo sem Ollama (CI) —
    # sem eles o index_book entrava no pull do modelo e vazava rede real.
    with patch.object(RAGEngine, "_get_embedding", return_value=fake_embedding), \
         patch.object(RAGEngine, "_get_embeddings_batch",
                      side_effect=lambda texts: [fake_embedding for _ in texts]), \
         patch.object(RAGEngine, "is_model_available", return_value=True), \
         patch.object(RAGEngine, "is_ollama_available", return_value=True):
        engine = RAGEngine(db_path=test_db, chroma_path=chroma_path,
                           ollama_url="http://localhost:11434")
        yield engine


def _mock_stream_response(lines: list[bytes]) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.__iter__ = lambda s: iter(lines)
    return resp


def _content_and_toolcall_round(text: str, fn_name: str, args: dict) -> list[bytes]:
    """Simula uma rodada onde o modelo escreve `text` e SÓ NO FINAL emite o
    tool_call (padrão observado: Ollama só anexa tool_calls no chunk final)."""
    lines = [json.dumps({"message": {"content": text}}).encode("utf-8")]
    lines.append(json.dumps({
        "message": {"content": "", "tool_calls": [
            {"function": {"name": fn_name, "arguments": args}}
        ]},
        "done": True, "done_reason": "stop",
    }).encode("utf-8"))
    return lines


def _final_text_round(text: str) -> list[bytes]:
    return [
        json.dumps({"message": {"content": text}}).encode("utf-8"),
        json.dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}).encode("utf-8"),
    ]


class TestActionOnlyShortCircuit:
    def test_highlight_with_content_stops_after_one_round(self, mock_engine):
        """Ferramenta de efeito colateral + texto já escrito -> encerra na hora."""
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            return _mock_stream_response(_content_and_toolcall_round(
                "Esta é a explicação completa do trecho.",
                "highlight_book_text", {"text_to_find": "trecho", "color": "green"}))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag(
                    "Explique este trecho",
                    ui_mutation_callback=lambda *a, **k: None))

        full = "".join(tokens)
        assert "explicação completa" in full
        assert "[⚙️ highlight_book_text(...)…]" in full
        # Só UMA chamada HTTP: nada de "responder de novo" nem "Limite de rodadas".
        assert call_count == 1
        assert "Limite de rodadas" not in full
        assert full.count("explicação completa") == 1  # sem duplicação

    def test_bookmark_with_content_stops_after_one_round(self, mock_engine):
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            return _mock_stream_response(_content_and_toolcall_round(
                "Resumo do capítulo.", "create_ai_bookmark", {"note": "ideia central"}))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag(
                    "Marque isso", ui_mutation_callback=lambda *a, **k: None))

        assert call_count == 1
        assert "Resumo do capítulo." in "".join(tokens)

    def test_info_tool_with_content_still_loops(self, mock_engine):
        """vector_search não é action-only: o loop deve continuar normalmente
        (comportamento pré-existente preservado)."""
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_stream_response(_content_and_toolcall_round(
                    "Deixa eu verificar isso.", "vector_search", {"query": "capitu"}))
            return _mock_stream_response(_final_text_round("Resposta final após a busca."))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag("Quem é Capitu?"))

        assert call_count == 2  # continuou para a segunda rodada, como antes
        assert "Resposta final após a busca." in "".join(tokens)

    def test_mixed_action_and_info_tool_still_loops(self, mock_engine):
        """Rodada com UMA ferramenta de ação e UMA de busca: não encerra cedo
        (conservador — evita cortar antes do modelo incorporar a busca)."""
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                lines = [json.dumps({"message": {"content": "Vou destacar e buscar."}}).encode("utf-8")]
                lines.append(json.dumps({
                    "message": {"content": "", "tool_calls": [
                        {"function": {"name": "highlight_book_text",
                                     "arguments": {"text_to_find": "x"}}},
                        {"function": {"name": "vector_search",
                                     "arguments": {"query": "y"}}},
                    ]},
                    "done": True, "done_reason": "stop",
                }).encode("utf-8"))
                return _mock_stream_response(lines)
            return _mock_stream_response(_final_text_round("Resposta final."))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen), \
                 patch.object(Orchestrator, "_execute_tool_orchestrated",
                             return_value='{"status": "success"}'):
                tokens = list(mock_engine.query_rag(
                    "Faça as duas coisas", ui_mutation_callback=lambda *a, **k: None))

        assert call_count == 2
        assert "Resposta final." in "".join(tokens)

    def test_action_tool_without_content_still_loops(self, mock_engine):
        """Sem texto nesta rodada (só a chamada da ferramenta): não há o que
        encerrar como resposta — o loop segue pedindo a explicação real."""
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_stream_response(_content_and_toolcall_round(
                    "", "highlight_book_text", {"text_to_find": "x"}))
            return _mock_stream_response(_final_text_round("Agora sim, a explicação."))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag(
                    "Explique", ui_mutation_callback=lambda *a, **k: None))

        assert call_count == 2
        assert "Agora sim, a explicação." in "".join(tokens)


class TestRepeatPenaltyOptions:
    def test_payload_includes_repeat_penalty_and_last_n(self, mock_engine):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured.update(json.loads(req.data.decode()))
            return _mock_stream_response(_final_text_round("ok"))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                list(mock_engine.query_rag("Pergunta qualquer"))

        options = captured["options"]
        assert options["repeat_penalty"] == 1.15
        assert options["repeat_last_n"] == 512
        # num_predict/num_ctx preservados (não mexemos na profundidade de raciocínio)
        assert options["num_predict"] == 4096
        assert options["num_ctx"] == 8192


def test_action_only_tools_constant():
    assert _ACTION_ONLY_TOOLS == frozenset({"highlight_book_text", "create_ai_bookmark"})
