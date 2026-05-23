# ADR-001: Uniform ToolOutput Contract

## Status
Accepted

## Context

Agentic tools currently risk returning inconsistent shapes: strings, dictionaries, lists, exceptions, or mixed objects. This makes orchestration fragile and weakens policy validation, tracing, and fallback logic.

## Decision

Every tool callable by the RAG/agent runtime must return a standardized `ToolOutput` envelope.

```python
{
    "status": "success" | "error",
    "data": list | dict | str | None,
    "provenance": "local" | "web" | "user" | "system" | "unknown",
    "confidence_score": float,
    "metadata": {
        "tool_name": str,
        "latency_ms": int | None,
        "result_count": int | None,
        "error_type": str | None,
        "error_message": str | None
    }
}
```

## Consequences

- The Policy Engine can inspect provenance reliably.
- The Orchestrator can reason over confidence and failure state.
- Trace logs become uniform.
- Tools become easier to test.

## Rules

- Never return raw strings from tools.
- Never raise uncaught exceptions from tools into the orchestrator loop.
- Any exception must be captured as `status="error"` with metadata.
- `confidence_score` must be between `0.0` and `1.0`.
