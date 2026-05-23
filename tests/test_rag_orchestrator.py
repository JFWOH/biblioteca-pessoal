import time
from unittest.mock import MagicMock, patch
import pytest

from src.core.rag.agent_state import AgentState
from src.core.rag.tools.base import create_tool_output, ToolOutput
from src.core.rag.orchestrator import Orchestrator

# ══════════════════════════════════════════════════════════════════════════════
# TestAgentState
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentState:
    """Testes unitários para o gerenciador de orçamento e estado AgentState."""

    def test_agent_state_initial_values(self):
        state = AgentState(max_rounds=3, max_time_ms=5000)
        assert state.max_rounds == 3
        assert state.max_time_ms == 5000
        assert state.current_round == 0
        assert state.history == []
        assert state.called_tools == []
        assert state.provenance == "local"
        assert state.confidence_score == 1.0
        assert state.last_results_digest == ""

    def test_update_provenance_to_web(self):
        state = AgentState()
        assert state.provenance == "local"
        state.update_provenance("local")
        assert state.provenance == "local"
        state.update_provenance("web")
        assert state.provenance == "web"
        state.update_provenance("local")  # Não deve regredir para local se já for web
        assert state.provenance == "web"

    def test_is_budget_ok_within_limits(self):
        state = AgentState(max_rounds=5, max_time_ms=1000)
        state.current_round = 3
        assert state.is_budget_ok() is True

    def test_is_budget_ok_rounds_exceeded(self):
        state = AgentState(max_rounds=5, max_time_ms=1000)
        state.current_round = 5
        assert state.is_budget_ok() is False

    def test_is_budget_ok_time_exceeded(self):
        state = AgentState(max_rounds=5, max_time_ms=10)
        time.sleep(0.02)  # Dorme 20ms (> 10ms do orçamento)
        assert state.is_budget_ok() is False


# ══════════════════════════════════════════════════════════════════════════════
# TestToolOutput
# ══════════════════════════════════════════════════════════════════════════════

class TestToolOutput:
    """Testes unitários para o contrato de ferramentas ToolOutput."""

    def test_create_tool_output_success(self):
        data = [{"text": "Capitu olhos de ressaca", "page": 12, "title": "Dom Casmurro"}]
        output = create_tool_output(
            status="success",
            data=data,
            provenance="local",
            confidence=0.9
        )
        assert output["status"] == "success"
        assert output["data"] == data
        assert output["provenance"] == "local"
        assert output["error_message"] == ""
        assert output["confidence_score"] == 0.9
        assert output["metadata"]["result_count"] == 1
        assert output["metadata"]["error_message"] is None

    def test_create_tool_output_error(self):
        output = create_tool_output(
            status="error",
            data=[],
            provenance="local",
            error_message="ChromaDB locked",
            confidence=0.0
        )
        assert output["status"] == "error"
        assert output["data"] == []
        assert output["provenance"] == "local"
        assert output["error_message"] == "ChromaDB locked"
        assert output["confidence_score"] == 0.0
        assert output["metadata"]["result_count"] == 0
        assert output["metadata"]["error_message"] == "ChromaDB locked"


# ══════════════════════════════════════════════════════════════════════════════
# TestOrchestrator
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestrator:
    """Testes unitários para o Orchestrator, cobrindo fallbacks e early-exits."""

    def test_execute_vector_search_success(self):
        # Configura motor mockado
        mock_engine = MagicMock()
        mock_engine.search_similar.return_value = [
            {
                "document": "Texto do trecho do livro",
                "metadata": {"title": "Livro A", "author": "Autor A", "page_number": 5, "book_id": 10}
            }
        ]
        
        state = AgentState()
        orchestrator = Orchestrator(mock_engine)
        
        output = orchestrator.execute_vector_search("busca", book_id=10, state=state)
        
        assert output["status"] == "success"
        assert output["provenance"] == "local"
        assert len(output["data"]) == 1
        assert output["data"][0]["text"] == "Texto do trecho do livro"
        assert output["data"][0]["page"] == 6  # 5 + 1
        assert output["data"][0]["title"] == "Livro A"
        assert "vector_search" in state.called_tools

    def test_execute_vector_search_fallback_to_keyword_search(self):
        # Simula erro de busca vetorial (ex: ChromaDB travado)
        mock_engine = MagicMock()
        mock_engine.search_similar.side_effect = RuntimeError("ChromaDB Error")
        
        # SQLite retorna dados no fallback
        mock_engine.keyword_search_db.return_value = [
            {
                "text": "Texto do SQLite",
                "page": 2,
                "title": "Livro B",
                "author": "Autor B",
                "book_id": 11
            }
        ]
        
        state = AgentState()
        orchestrator = Orchestrator(mock_engine)
        
        output = orchestrator.execute_vector_search("busca", book_id=11, state=state)
        
        # Status deve ser "error" sinalizando a falha, mas contendo os dados do SQLite
        assert output["status"] == "error"
        assert output["error_message"] == "ChromaDB Error"
        assert len(output["data"]) == 1
        assert output["data"][0]["text"] == "Texto do SQLite"
        assert output["data"][0]["title"] == "Livro B"
        assert output["data"][0]["page"] == 2
        
        # O histórico de rounds no estado deve conter a notificação do fallback
        assert any("fallback" in h["content"] for h in state.history)

    def test_execute_search_web_success(self):
        mock_engine = MagicMock()
        orchestrator = Orchestrator(mock_engine)
        state = AgentState()

        mock_results = [{"body": "Resultado da web", "title": "Titulo Web", "href": "http://web.com"}]
        
        with patch("src.core.rag.tools.web_search.search_duckduckgo") as mock_search:
            mock_search.return_value = mock_results
            
            output = orchestrator.execute_search_web("pergunta web", state=state)
            
            assert output["status"] == "success"
            assert output["provenance"] == "web"
            assert len(output["data"]) == 1
            assert output["data"][0]["text"] == "Resultado da web"
            assert state.provenance == "web"

    def test_execute_search_web_failure_degrades_to_local(self):
        mock_engine = MagicMock()
        # Fallback local retorna dados do ChromaDB
        mock_engine.search_similar.return_value = [
            {
                "document": "Dado local de fallback",
                "metadata": {"title": "Livro Local", "author": "Autor Local", "page_number": 1, "book_id": 3}
            }
        ]
        
        state = AgentState()
        orchestrator = Orchestrator(mock_engine)
        
        # Simula falha na busca web externa (ex: falta de conexão)
        with patch("src.core.rag.tools.web_search.search_duckduckgo") as mock_search:
            mock_search.side_effect = ConnectionError("Sem internet")
            
            output = orchestrator.execute_search_web("pergunta web", state=state)
            
            assert output["status"] == "error"
            assert output["provenance"] == "local"
            assert len(output["data"]) == 1
            assert output["data"][0]["text"] == "Dado local de fallback"
            assert output["data"][0]["title"] == "Livro Local"
            assert "degraded_info" in output["data"][0]

    def test_early_exit_on_identical_results(self):
        mock_engine = MagicMock()
        # Sempre retorna o mesmo documento
        mock_engine.search_similar.return_value = [
            {
                "document": "Texto fixo",
                "metadata": {"title": "Livro Fixo", "page_number": 0, "book_id": 1}
            }
        ]
        
        orchestrator = Orchestrator(mock_engine)
        
        # Executa o loop do agente. Como o resultado é sempre idêntico, 
        # a heurística de Early-Exit deve parar o loop no round 2 (ao invés de rodar max_rounds=5).
        result = orchestrator.run_agent_loop("Qual o sentido da vida?", max_rounds=5)
        
        assert result["rounds_executed"] == 2
        assert len(result["history"]) == 1  # O primeiro round rodou, o segundo causou early-exit antes de comitar a história

    def test_query_reformulation_cardano_offline(self):
        """1 & 2. Testa _reformulate_query para Cardano com Ollama indisponível (offline)."""
        mock_engine = MagicMock()
        mock_engine.is_ollama_available.return_value = False
        
        orchestrator = Orchestrator(mock_engine)
        query = "Cardano foi um dos primeiros a perceber que tais jogos podiam ser analisados matematicamente"
        
        alternatives = orchestrator._reformulate_query(query)
        
        # Confirma que há múltiplas queries reformuladas geradas pela heurística offline
        assert len(alternatives) > 1
        
        # Confirma que as alternativas contêm os termos obrigatórios (Liber, probability, etc)
        has_cardano = any("cardano" in a.lower() for a in alternatives)
        has_liber = any("liber de ludo aleae" in a.lower() or "book on games of chance" in a.lower() for a in alternatives)
        has_prob = any("probability" in a.lower() or "probabilidade" in a.lower() for a in alternatives)
        has_games = any("games of chance" in a.lower() or "jogos de azar" in a.lower() for a in alternatives)
        
        assert has_cardano is True
        assert has_liber is True
        assert has_prob is True
        assert has_games is True

    def test_execute_search_web_retry_on_empty_and_metadata(self):
        """3 & 4. Simula primeira query vazia e segunda com resultado, confirmando sucesso e metadata.attempted_queries."""
        mock_engine = MagicMock()
        mock_engine.is_ollama_available.return_value = False
        
        orchestrator = Orchestrator(mock_engine)
        query = "Cardano foi um dos primeiros a perceber que tais jogos podiam ser analisados matematicamente"
        
        call_count = 0
        def fake_text_search(q, provider_errors):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # Primeira falha (vazio)
            else:
                return [{"body": f"Resultado para {q}", "title": "Sucesso", "href": "http://sucesso.com"}]

        state = AgentState()
        with patch("src.core.rag.tools.web_search.search_duckduckgo", side_effect=fake_text_search):
            output = orchestrator.execute_search_web(query, state=state)
            
            assert output["status"] == "success"
            assert output["provenance"] == "web"
            assert len(output["data"]) == 1
            assert "Cardano Book on Games of Chance probability" in output["data"][0]["text"]
            
            # Confirma que attempted_queries e successful_query foram gravados corretamente em metadata
            assert "attempted_queries" in output["metadata"]
            assert "successful_query" in output["metadata"]
            assert len(output["metadata"]["attempted_queries"]) > 1
            assert output["metadata"]["successful_query"] == "Cardano Book on Games of Chance probability"

    def test_normalize_web_result_accepts_href_body(self):
        """Requisito 2 & 3: Valida que normalize_web_result aceita e extrai o formato com href e body."""
        from src.core.rag.tools.web_search import normalize_web_result
        item = {"title": "Britannica", "href": "http://britannica.com", "body": "Cardano foi um grande matemático."}
        res = normalize_web_result(item)
        assert res["title"] == "Britannica"
        assert res["href"] == "http://britannica.com"
        assert res["text"] == "Cardano foi um grande matemático."

    def test_normalize_web_result_accepts_url_snippet(self):
        """Requisito 2 & 3: Valida que normalize_web_result aceita e extrai o formato com url e snippet."""
        from src.core.rag.tools.web_search import normalize_web_result
        item = {"title": "MAA", "url": "http://maa.org", "snippet": "O Liber de ludo aleae..."}
        res = normalize_web_result(item)
        assert res["title"] == "MAA"
        assert res["href"] == "http://maa.org"
        assert res["text"] == "O Liber de ludo aleae..."

    def test_normalize_web_result_accepts_link_description(self):
        """Requisito 2 & 3: Valida que normalize_web_result aceita e extrai o formato com link e description."""
        from src.core.rag.tools.web_search import normalize_web_result
        item = {"title": "Google Books", "link": "http://books.google.com", "description": "Jogos de azar analisados matematicamente."}
        res = normalize_web_result(item)
        assert res["title"] == "Google Books"
        assert res["href"] == "http://books.google.com"
        assert res["text"] == "Jogos de azar analisados matematicamente."

    def test_execute_search_web_keeps_raw_results_not_discarded(self):
        """Requisito 3 & 4: Valida que execute_search_web preserva os resultados crus e não os descarta indevidamente."""
        mock_engine = MagicMock()
        mock_engine.is_ollama_available.return_value = False
        orchestrator = Orchestrator(mock_engine)
        
        mock_results = [
            {"title": "Britannica", "href": "http://britannica.com", "body": "Conteudo A"},
            {"title": "MAA", "url": "http://maa.org", "snippet": "Conteudo B"},
            {"title": "Google Books", "link": "http://books.google.com", "description": "Conteudo C"}
        ]
        
        state = AgentState()
        with patch("src.core.rag.tools.web_search.search_duckduckgo", return_value=mock_results):
            output = orchestrator.execute_search_web("Cardano jogos de azar", state=state)
            
            assert output["status"] == "success"
            assert len(output["data"]) == 3
            assert output["data"][0]["title"] == "Britannica"
            assert output["data"][1]["title"] == "MAA"
            assert output["data"][2]["title"] == "Google Books"

    def test_execute_search_web_metadata_counts(self):
        """Requisito 5: Valida que execute_search_web popula corretamente os contadores em metadata."""
        mock_engine = MagicMock()
        mock_engine.is_ollama_available.return_value = False
        orchestrator = Orchestrator(mock_engine)
        
        mock_results = [
            {"title": "Britannica", "href": "http://britannica.com", "body": "Conteudo A"},
            {"title": "Resultado Invalido"}  # Sem link/corpo válido, deve ser descartado
        ]
        
        state = AgentState()
        with patch("src.core.rag.tools.web_search.search_duckduckgo", return_value=mock_results):
            output = orchestrator.execute_search_web("Cardano jogos de azar", state=state)
            
            assert output["status"] == "success"
            assert output["metadata"]["raw_result_count"] == 2
            assert output["metadata"]["normalized_result_count"] == 1
            assert output["metadata"]["provider"] == "duckduckgo_search"

    def test_cardano_web_search_provider_mock_success(self):
        """Requisito 6 & Caso de Teste: Valida o fluxo completo Cardano com sucesso mockado."""
        mock_engine = MagicMock()
        mock_engine.is_ollama_available.return_value = False
        orchestrator = Orchestrator(mock_engine)
        
        query = "Cardano foi um dos primeiros a perceber que tais jogos podiam ser analisados matematicamente"
        mock_results = [{"title": "Girolamo Cardano", "link": "http://britannica.com", "snippet": "Cardano publicou o Liber de ludo aleae."}]
        
        state = AgentState()
        with patch("src.core.rag.tools.web_search.search_duckduckgo", return_value=mock_results):
            output = orchestrator.execute_search_web(query, state=state)
            
            assert output["status"] == "success"
            assert output["provenance"] == "web"
            assert len(output["data"]) == 1
            assert output["data"][0]["title"] == "Girolamo Cardano"
            assert output["metadata"]["normalized_result_count"] == 1
