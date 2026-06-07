import os
import json
import pytest
from unittest.mock import patch
from src.core.rag.trace_logger import TraceLogger

def test_trace_logger_serialization(tmp_path):
    traces_dir = tmp_path / "traces"
    logger = TraceLogger("test-session-123", traces_dir=str(traces_dir))
    
    payload = {"key": "value", "long_text": "A" * 1500}
    
    logger.emit(
        event_type="test_event",
        step=1,
        query="test query",
        provenance="web",
        confidence=0.9,
        tool_name="test_tool",
        allowed=True,
        reason="test reason",
        round_num=2,
        payload=payload,
        error_type="TestError",
        error_message="Error message"
    )
    
    file_path = traces_dir / "trace_test-session-123.jsonl"
    assert file_path.exists()
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        
    assert data["session_id"] == "test-session-123"
    assert data["event_type"] == "test_event"
    assert data["step"] == 1
    assert data["query"] == "test query"
    assert data["provenance"] == "web"
    assert data["confidence"] == 0.9
    assert data["tool_name"] == "test_tool"
    assert data["allowed"] is True
    assert data["reason"] == "test reason"
    assert data["round"] == 2
    assert data["error_type"] == "TestError"
    assert data["error_message"] == "Error message"
    assert "timestamp" in data
    
    # Check truncation
    assert len(data["payload"]["long_text"]) < 1500
    assert data["payload"]["long_text"].endswith("[TRUNCATED]")

def test_trace_logger_failsafe(tmp_path):
    traces_dir = tmp_path / "traces"
    logger = TraceLogger("test-session-failsafe", traces_dir=str(traces_dir))
    
    # Mock open to raise exception
    with patch("builtins.open", side_effect=PermissionError("Mocked Permission Error")):
        # This should not raise an exception
        try:
            logger.emit("test_event", step=1)
        except Exception:
            pytest.fail("TraceLogger.emit raised Exception unexpectedly!")

def test_trace_logger_list_truncation(tmp_path):
    traces_dir = tmp_path / "traces"
    logger = TraceLogger("test-session-list", traces_dir=str(traces_dir))
    
    long_list = list(range(100))
    logger.emit("list_event", step=1, payload={"items": long_list})
    
    file_path = traces_dir / "trace_test-session-list.jsonl"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.loads(f.readline())
        
    truncated_items = data["payload"]["items"]
    assert len(truncated_items) == 51 # 50 items + 1 truncation message
    assert "TRUNCATED" in str(truncated_items[-1])
