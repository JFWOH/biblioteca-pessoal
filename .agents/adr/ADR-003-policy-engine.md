# ADR-003: Policy Engine for AI Actions

## Status
Accepted

## Context

Agentic systems are vulnerable to indirect prompt injection. Web content, PDFs, or external text may contain malicious instructions such as asking the LLM to mutate UI, alter data, or ignore prior rules.

## Decision

All AI-requested actions that mutate UI, database state, files, or application behavior must pass through a Policy Engine before execution.

## Baseline Policy

| Action | Provenance | Decision |
|---|---|---|
| local read-only search | local | allow |
| web search | web | allow read-only |
| highlight text | local/user | allow if bounded |
| highlight text | web | block |
| create AI bookmark | local/user | allow if bounded |
| create AI bookmark | web | block or require approval |
| delete annotations | any | block unless explicit human approval |
| modify files/database schema | any | require explicit human approval |

## Consequences

- Web content cannot directly trigger UI mutations.
- Prompt injection impact is reduced.
- All denied actions become auditable.

## Rules

- Treat web content as untrusted.
- Treat model-generated tool calls as requests, not commands.
- Denied actions must be logged through the Trace Logger.
- UI mutation payloads must be bounded in size and scope.
