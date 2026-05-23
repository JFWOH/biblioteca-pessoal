# ADR-002: Explicit AgentState

## Status
Accepted

## Context

The ReAct loop cannot rely only on natural-language history to remember which tools were called, which sources were consulted, whether web data appeared, or whether confidence is high enough to stop.

## Decision

The agent runtime must maintain an explicit `AgentState` object for each user interaction/session.

Minimum state fields:

```python
{
    "iteration": int,
    "max_iterations": int,
    "sources_used": set[str],
    "books_consulted": set[str],
    "tools_called": list[str],
    "last_tool": str | None,
    "last_result_hash": str | None,
    "repeated_result_count": int,
    "confidence_score": float,
    "web_seen": bool,
    "ui_mutation_requested": bool,
    "errors": list[dict],
    "budget": {
        "started_at": float,
        "elapsed_ms": int,
        "tokens_estimated": int | None
    }
}
```

## Consequences

- Early-exit becomes deterministic.
- Repeated tool results can stop the loop.
- Policy decisions can use source provenance.
- Tests can validate orchestration behavior without PyQt6.

## Rules

- The LLM may propose actions, but deterministic state gates may stop or alter the loop.
- If the same tool returns the same result hash twice, abort further tool calls unless explicitly justified.
- If `confidence_score >= 0.85`, prefer final synthesis over further retrieval.
