# ADR-004: Structured Agent Trace Logger

## Status
Accepted

## Context

Without structured tracing, agent behavior appears magical and debugging becomes difficult. Failures must be attributable to a step, tool, decision, policy denial, or fallback.

## Decision

Every agent loop must emit structured trace events.

Minimum trace event:

```python
{
    "session_id": str,
    "step": int,
    "event_type": "thought" | "tool_request" | "tool_result" | "policy_decision" | "fallback" | "final" | "error",
    "tool_name": str | None,
    "reason": str | None,
    "input_summary": str | None,
    "output_summary": str | None,
    "status": "success" | "error" | "blocked" | "skipped",
    "latency_ms": int | None,
    "metadata": dict
}
```

## Consequences

- Debugging becomes systematic.
- Future replay mode becomes possible.
- Policy blocks and fallbacks are visible.
- Performance bottlenecks can be measured.

## Rules

- Do not log secrets.
- Summarize large payloads instead of dumping full documents.
- Log every policy block.
- Log every fallback.
