# ADR Index — Biblioteca Pessoal Inteligente

This directory contains accepted Architectural Decision Records for the project.
Agents must read only ADRs relevant to the subsystem they are modifying.

## ADRs

| ADR | Title | Read when... |
|---|---|---|
| ADR-001 | Uniform ToolOutput Contract | Creating or modifying any tool used by the RAG/agent runtime |
| ADR-002 | Explicit AgentState | Changing orchestration, loop behavior, budget, confidence, or memory |
| ADR-003 | Policy Engine for AI Actions | Adding UI mutations, web search usage, tool permissions, or safety checks |
| ADR-004 | Structured Agent Trace Logger | Changing logging, debugging, replay, observability, or agent telemetry |
| ADR-005 | Failure Strategy and Graceful Degradation | Handling Ollama, ChromaDB, SQLite, web search, or fallback behavior |
| ADR-006 | GUI/Core AI Boundary | Touching PyQt6, QThreads, workers, application services, or RAG core integration |

## Rule of Thumb

- If editing `src/core/rag/tools/`, read ADR-001, ADR-003, ADR-005.
- If editing `src/core/rag/orchestrator.py`, read ADR-001, ADR-002, ADR-003, ADR-004, ADR-005.
- If editing GUI integration with AI, read ADR-003 and ADR-006.
- If adding logging or replay, read ADR-004.
