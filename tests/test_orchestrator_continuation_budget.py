"""Testes da correção de resposta incompleta por orçamento de continuação.

Bug relatado (usuário, ação "Explique esta página"): a resposta terminava
cortada no meio de uma frase, com o aviso "[⚠️ Limite de rodadas de
ferramentas atingido]" aparecendo — mesmo sem NENHUMA ferramenta ter sido
chamada nessa consulta (confirmado pelo trace real da sessão,
data/traces/trace_eb8b0172-*.jsonl: só eventos final_answer_started/
completed, nenhum tool_call_completed).

Causa raiz: o modelo local (gemma4, "thinking") já estourava done_reason
"length" na 1ª rodada sozinho; o mecanismo de retomada ("Continue exatamente
de onde parou.") só tinha orçamento para UMA tentativa (continuation_count
< 1), compartilhado entre o loop principal e o fallback de fim de orçamento.
Quando essa única tentativa também vinha truncada, a resposta parava sem
mais retomada, sem erro — e a mensagem de aviso, escrita só para o caso de
"rodadas de ferramentas esgotadas", aparecia mesmo quando o motivo real era
o orçamento de TEMPO (max_time_ms) estourado, sem nenhuma ferramenta.

Este arquivo cobre a correção: _MAX_CONTINUATIONS subiu de 1 para 2 (nos dois
pontos de checagem), a mensagem de aviso deixou de mencionar "rodadas de
ferramentas" especificamente, e o histórico persistido passou a incluir o
conteúdo de TODAS as retomadas (inclusive a que acontece dentro do próprio
fallback), não só da primeira.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.rag.agent_state import AgentState
from src.core.rag.orchestrator import _MAX_CONTINUATIONS


def _create_test_db(path: Path) -> Path:
    from src.core.database import LibraryDB
    db = LibraryDB(path)
    db.conn.execute(
        "INSERT INTO books (id, title, author, description, file_path, file_format) VALUES (?,?,?,?,?,?)",
        (1, "O animal social", "David Brooks", "Não-ficção.", "/tmp/fake1.pdf", "pdf"))
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
    with patch.object(RAGEngine, "_get_embedding", return_value=fake_embedding), \
         patch.object(RAGEngine, "_get_embeddings_batch",
                      side_effect=lambda texts: [fake_embedding for _ in texts]):
        engine = RAGEngine(db_path=test_db, chroma_path=chroma_path,
                           ollama_url="http://localhost:11434")
        yield engine


def _mock_stream_response(lines: list[bytes]) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.__iter__ = lambda s: iter(lines)
    return resp


def _text_round(text: str, done_reason: str) -> list[bytes]:
    """Rodada sem tool_calls: só texto, terminando com o done_reason dado."""
    return [
        json.dumps({"message": {"content": text}}).encode("utf-8"),
        json.dumps({"message": {"content": ""}, "done": True,
                   "done_reason": done_reason}).encode("utf-8"),
    ]


class TestMainLoopContinuationCap:
    def test_two_continuations_allowed_before_giving_up(self, mock_engine):
        """3 rodadas truncadas por comprimento (sem ferramentas): a resposta
        deve incorporar as 3 partes (2 retomadas), não parar na 2ª."""
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            reason = "length" if call_count < 3 else "stop"
            return _mock_stream_response(_text_round(f"Parte{call_count}. ", reason))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag("Explique esta página"))

        full = "".join(tokens)
        assert call_count == 3
        assert "Parte1." in full and "Parte2." in full and "Parte3." in full
        # Nunca precisou do fallback de fim de orçamento (deu conta no loop principal).
        assert "Orçamento do agente esgotado" not in full
        assert "Limite de rodadas" not in full

    def test_max_continuations_constant_is_two(self):
        assert _MAX_CONTINUATIONS == 2


class TestBudgetExhaustedFallback:
    """Reproduz o cenário real: orçamento esgotado no meio de uma retomada,
    sem nenhuma chamada de ferramenta — via monkeypatch direto de
    ``AgentState.is_budget_ok`` (mais confiável que forjar o relógio: várias
    bibliotecas de terceiros também chamam ``time.time()`` internamente, o
    que tornaria uma falsificação global do relógio não-determinística)."""

    def _budget_ok_for_n_rounds(self, n: int):
        """True para as N primeiras checagens do loop; False depois."""
        calls = {"n": 0}

        def fake_is_budget_ok(_self):
            calls["n"] += 1
            return calls["n"] <= n
        return fake_is_budget_ok

    def test_fallback_message_does_not_blame_tool_rounds(self, mock_engine, monkeypatch):
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_stream_response(_text_round("Parte1. ", "length"))
            return _mock_stream_response(_text_round("Parte2 (retomada).", "stop"))

        # Só a 1ª checagem de orçamento passa: a rodada 1 executa, trunca por
        # comprimento e tenta continuar — mas o orçamento já está esgotado
        # (2ª checagem = False), exatamente como no incidente real (tempo
        # esgotado no meio de uma retomada, zero ferramentas chamadas).
        monkeypatch.setattr(AgentState, "is_budget_ok", self._budget_ok_for_n_rounds(1))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag("Explique esta página"))

        full = "".join(tokens)
        assert call_count == 2
        # Conteúdo das duas rodadas chega ao usuário, sem perda.
        assert "Parte1." in full
        assert "Parte2 (retomada)." in full
        # A mensagem não deve mais atribuir o corte a "rodadas de ferramentas"
        # quando nenhuma ferramenta foi chamada.
        assert "Limite de rodadas de ferramentas" not in full
        assert "Orçamento do agente esgotado" in full

    def test_fallback_second_continuation_persists_full_history(self, mock_engine, monkeypatch):
        """A retomada DENTRO do fallback (resp_cont) também deve entrar no
        histórico persistido — antes só os tokens da 1ª chamada eram salvos."""
        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_stream_response(_text_round("Parte1. ", "length"))
            if call_count == 2:
                # 1ª tentativa do fallback também trunca -> aciona resp_cont.
                return _mock_stream_response(_text_round("Parte2. ", "length"))
            return _mock_stream_response(_text_round("Parte3 final.", "stop"))

        monkeypatch.setattr(AgentState, "is_budget_ok", self._budget_ok_for_n_rounds(1))

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag("Explique esta página"))

        full = "".join(tokens)
        assert call_count == 3
        assert "Parte3 final." in full

        history = mock_engine.get_chat_history(None)
        assistant_turns = [h["content"] for h in history if h.get("role") == "assistant"]
        assert assistant_turns, "turno do assistente não foi persistido"
        # Antes da correção, só "Parte1. " (da 1ª chamada) era persistido.
        assert "Parte2." in assistant_turns[-1]
        assert "Parte3 final." in assistant_turns[-1]
