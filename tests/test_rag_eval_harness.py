
from src.tools.rag_eval_harness import evaluate_session

def test_evaluate_perfect_session():
    events = [
        {"session_id": "1", "event_type": "query_started"},
        {"session_id": "1", "event_type": "tool_call_requested", "tool_name": "vector_search"},
        {"session_id": "1", "event_type": "query_completed"}
    ]
    anomalies = evaluate_session(events)["anomalies"]
    assert len(anomalies) == 0

def test_evaluate_missing_start():
    events = [
        {"session_id": "2", "event_type": "tool_call_requested"},
        {"session_id": "2", "event_type": "query_completed"}
    ]
    anomalies = evaluate_session(events)["anomalies"]
    assert len(anomalies) == 1
    assert "não começa com 'query_started'" in anomalies[0]

def test_evaluate_missing_end():
    events = [
        {"session_id": "3", "event_type": "query_started"},
        {"session_id": "3", "event_type": "tool_call_requested"}
    ]
    anomalies = evaluate_session(events)["anomalies"]
    assert len(anomalies) == 1
    assert "não possui finalização válida" in anomalies[0]

def test_evaluate_error_end():
    events = [
        {"session_id": "4", "event_type": "query_started"},
        {"session_id": "4", "event_type": "error", "error_message": "boom"}
    ]
    anomalies = evaluate_session(events)["anomalies"]
    assert len(anomalies) == 0

def test_evaluate_missing_policy_for_ui():
    events = [
        {"session_id": "5", "event_type": "query_started"},
        {"session_id": "5", "event_type": "tool_call_requested", "tool_name": "highlight_book_text"},
        {"session_id": "5", "event_type": "query_completed"}
    ]
    anomalies = evaluate_session(events)["anomalies"]
    assert len(anomalies) == 1
    assert "sem nenhuma decisão de Policy" in anomalies[0]

def test_evaluate_with_policy_for_ui():
    events = [
        {"session_id": "6", "event_type": "query_started"},
        {"session_id": "6", "event_type": "tool_call_requested", "tool_name": "highlight_book_text"},
        {"session_id": "6", "event_type": "policy_decision", "allowed": True},
        {"session_id": "6", "event_type": "query_completed"}
    ]
    anomalies = evaluate_session(events)["anomalies"]
    assert len(anomalies) == 0

def test_evaluate_classification_redundant():
    events = [
        {"session_id": "7", "event_type": "query_started"},
        {"session_id": "7", "event_type": "tool_call_requested", "tool_name": "vector_search"},
        {"session_id": "7", "event_type": "early_exit", "reason": "resultados_identicos"},
        {"session_id": "7", "event_type": "query_completed"}
    ]
    res = evaluate_session(events)
    assert res["classification"] == "redundant"

def test_evaluate_classification_fallback():
    events = [
        {"session_id": "8", "event_type": "query_started"},
        {"session_id": "8", "event_type": "fallback_activated", "reason": "vector_search_failed"},
        {"session_id": "8", "event_type": "query_completed"}
    ]
    res = evaluate_session(events)
    assert res["classification"] == "fallback_heavy"
