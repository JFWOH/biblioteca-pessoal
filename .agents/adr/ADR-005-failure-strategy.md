# ADR-005: Failure Strategy and Graceful Degradation

## Status
Accepted

## Context

Local-first systems depend on services that can fail or be unavailable: Ollama, ChromaDB, SQLite, DuckDuckGo/web search, file parsing, and PDF extraction.

## Decision

Failures must be handled through graceful degradation rather than crashes.

## Fallback Matrix

| Failure | Fallback |
|---|---|
| vector search fails | keyword search |
| keyword search fails | page/context-only answer |
| web search fails | local-only answer |
| Ollama timeout | retry once, then explain partial result |
| ChromaDB lock/error | keyword search fallback |
| SQLite lock/error | retry once with backoff, then safe error output |
| UI mutation denied | textual explanation only |

## Consequences

- User experience remains stable.
- The agent can still produce useful partial answers.
- Failures become traceable and testable.

## Rules

- Never crash the GUI because of a tool failure.
- Never swallow exceptions silently.
- Report degraded mode clearly to the user when it affects answer quality.
- Encode failures as `ToolOutput(status="error")`.
