from unittest.mock import MagicMock, patch

from src.core.rag.policy_engine import PolicyEngine
from src.core.rag.agent_state import AgentState
from src.core.rag.orchestrator import Orchestrator

class TestRAGPolicyEngine:
    def test_highlight_blocked_if_web_provenance(self):
        """ADR-003: Bloqueia highlight se proveniência for web."""
        state = AgentState(session_id="test_session")
        state.update_provenance("web")
        
        mock_engine = MagicMock()
        orchestrator = Orchestrator(mock_engine)
        
        args = {"text_to_find": "teste", "color": "yellow"}
        
        result_json = orchestrator._execute_tool_orchestrated(
            "highlight_book_text", args, state, MagicMock(), book_id=1, ui_mutation_callback=MagicMock()
        )
        
        assert "blocked" in result_json
        assert "Policy Engine" in result_json

    def test_highlight_allowed_if_local_provenance(self):
        """ADR-003: Permite highlight se proveniência for local."""
        state = AgentState(session_id="test_session")
        state.update_provenance("local")
        
        mock_engine = MagicMock()
        orchestrator = Orchestrator(mock_engine)
        
        args = {"text_to_find": "teste", "color": "yellow"}
        ui_callback = MagicMock()
        
        result_json = orchestrator._execute_tool_orchestrated(
            "highlight_book_text", args, state, MagicMock(), book_id=1, ui_mutation_callback=ui_callback
        )
        
        assert "success" in result_json
        ui_callback.assert_called_once()

    def test_bookmark_blocked_if_web_provenance(self):
        """ADR-003: Bloqueia bookmark se proveniência for web."""
        state = AgentState(session_id="test_session")
        state.update_provenance("web")
        
        mock_engine = MagicMock()
        orchestrator = Orchestrator(mock_engine)
        
        args = {"note": "nota perigosa"}
        
        result_json = orchestrator._execute_tool_orchestrated(
            "create_ai_bookmark", args, state, MagicMock(), book_id=1, ui_mutation_callback=MagicMock()
        )
        
        assert "blocked" in result_json
        assert "Policy Engine" in result_json

    def test_bookmark_allowed_if_local_provenance(self):
        """ADR-003: Permite bookmark se proveniência for local."""
        state = AgentState(session_id="test_session")
        state.update_provenance("local")
        
        mock_engine = MagicMock()
        orchestrator = Orchestrator(mock_engine)
        
        args = {"note": "nota segura"}
        ui_callback = MagicMock()
        
        result_json = orchestrator._execute_tool_orchestrated(
            "create_ai_bookmark", args, state, MagicMock(), book_id=1, ui_mutation_callback=ui_callback
        )
        
        assert "success" in result_json
        ui_callback.assert_called_once()
