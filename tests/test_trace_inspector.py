import tempfile
import json
from pathlib import Path

from src.tools.trace_inspector import summarize_session, get_all_summaries

def create_mock_trace(dir_path: Path, session_id: str, events: list[dict]):
    file_path = dir_path / f"trace_{session_id}.jsonl"
    with open(file_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

def test_summarize_session():
    events = [
        {"session_id": "abc", "timestamp": "12:00", "event_type": "query_started", "query": "hello"},
        {"session_id": "abc", "event_type": "tool_call_requested"},
        {"session_id": "abc", "event_type": "policy_decision"},
        {"session_id": "abc", "event_type": "error", "error_message": "boom"},
        {"session_id": "abc", "event_type": "query_completed"}
    ]
    
    summary = summarize_session(events)
    assert summary["session_id"] == "abc"
    assert summary["query"] == "hello"
    assert summary["has_policy"] is True
    assert summary["has_error"] is True
    assert summary["has_fallback"] is False
    assert summary["status"] == "query_completed"
    assert summary["total_steps"] == 5

def test_get_all_summaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        
        create_mock_trace(dir_path, "1", [
            {"session_id": "1", "event_type": "query_started", "query": "q1", "timestamp": "A"},
            {"session_id": "1", "event_type": "early_exit"}
        ])
        
        create_mock_trace(dir_path, "2", [
            {"session_id": "2", "event_type": "query_started", "query": "q2", "timestamp": "B"},
            {"session_id": "2", "event_type": "fallback_activated"},
            {"session_id": "2", "event_type": "query_completed"}
        ])
        
        summaries = get_all_summaries(dir_path)
        assert len(summaries) == 2
        
        s1 = next(s for s in summaries if s["session_id"] == "1")
        assert s1["has_fallback"] is False
        assert s1["status"] == "early_exit"
        
        s2 = next(s for s in summaries if s["session_id"] == "2")
        assert s2["has_fallback"] is True
        assert s2["status"] == "query_completed"
