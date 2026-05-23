# ADR-006: GUI/Core AI Boundary

## Status
Accepted

## Context

PyQt6 widgets must only be mutated on the main thread. The RAG/agent runtime must remain testable in headless mode and should not depend on GUI imports.

## Decision

The project must enforce a strict boundary between GUI and Core AI.

## Dependency Direction

Allowed:

```text
GUI → Application Service → Core AI/RAG
Core AI/RAG → callback/event DTO → GUI worker/signal → Main Thread UI mutation
```

Forbidden:

```text
Core AI/RAG → PyQt6 import
Core AI/RAG → direct widget mutation
Tool execution thread → direct widget mutation
```

## Consequences

- RAG runtime can be unit-tested without launching GUI.
- UI mutations remain thread-safe.
- Future web/mobile frontends can reuse the Core AI layer.

## Rules

- Core AI code must not import `PyQt6`.
- UI changes requested by AI must be emitted as structured events/callbacks.
- MainWindow or GUI-specific slots perform the actual widget mutation.
- Tests for Core AI must run headless.
