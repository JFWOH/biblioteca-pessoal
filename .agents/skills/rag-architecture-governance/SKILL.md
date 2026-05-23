---
name: rag-architecture-governance
description: Applies governance, ADR compliance, and safe refactoring patterns for the local Agentic RAG architecture. Use when modifying src/core/rag, tools, orchestration, policy, tracing, failure handling, or GUI/RAG boundaries.
---

# RAG Architecture Governance Skill

Use this skill when working on the Biblioteca Pessoal Inteligente RAG runtime.

## Required Reading

1. Inspect `.agents/adr/README.md`.
2. Read only ADRs relevant to the touched subsystem.
3. Follow `AGENTS.md` and `.agents/rules/governance.md`.

## Safe Workflow

1. Identify touched subsystem.
2. Read relevant ADRs.
3. Produce a short implementation plan.
4. Make minimal scoped changes.
5. Run focused tests.
6. Run `python -m pytest tests/` if environment allows.
7. Report files changed, tests, ADRs consulted, and risks.

## Architecture Guardrails

- Keep `src/core/rag/` independent from PyQt6.
- All tools return `ToolOutput`.
- All AI-requested mutations pass through Policy Engine.
- All loop steps emit structured trace events.
- All failures degrade gracefully.

## Refactoring Guidance

Prefer small, reviewable changes. Do not rewrite unrelated modules. Do not introduce new frameworks unless explicitly requested.
