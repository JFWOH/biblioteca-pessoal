---
title: "Contrato de Execução — Fase 6: Aprendizado com Dispensas"
status: "Aprovado para execução autônoma"
version: "1.0"
date: "2026-07-07"
audience:
  - Engenharia
  - QA
owner: "Sessão do workflow de otimização (branch feature/aprendizado-dispensas)"
phase: "grafo-fase-6"
execution_mode: "autonomous"
requires_manual_confirmation: false
related_docs:
  - "docs/agents/proativo_continuidade_execution_contract.md"
  - "docs/revisao-engenharia-2026-07-05.md"
  - "CLAUDE.md"
  - "AGENTS.md"
rollback_marker: true
mode: "PRODUCTION ENGINEERING"
---

# Contrato de Execução — Fase 6: Aprendizado com Dispensas

> **Objetivo:** o leitor dispensa observações proativas que não o ajudam, e esse
> sinal (`ai_observations.dismissed`, por tipo) hoje não alimenta nada. Esta fase
> fecha o ciclo de aprendizado do MVP: o proativo passa a conhecer os tipos de
> observação que o leitor costuma descartar e a evitá-los — **apenas via
> orientação no prompt** (decisão do usuário em 2026-07-07: sem supressão dura;
> RAG 👍/👎 e traces ficam fora do MVP).

## 0. Decisão executiva

```text
Decisão: APROVAR execução autônoma (workflow contínuo aprovado em 2026-07-06).
Escopo escolhido pelo usuário (AskUserQuestion 2026-07-07):
  - MVP = proativo aprende com dispensas;
  - ação = SÓ orientar o prompt (nada de suprimir tipos).
Branch: feature/aprendizado-dispensas (empilhada sobre feature/proativo-
  continuidade — a fase estende a fiação de providers da Fase 5).
Regra central: conflito entre implementação e contrato → contrato prevalece;
  ambiguidade real → perguntar ao usuário (CLAUDE.md §1).
```

## 1. Comportamento contratado

1. **Preferência aprendida no prompt:** ao gerar uma observação, o proativo
   recebe um bloco demarcado com os tipos que o leitor costuma dispensar
   (taxa de dispensa ≥ 60% com amostra mínima de 4 observações do tipo),
   instruindo a EVITÁ-los e a preferir os demais tipos vistos no histórico.
2. **Sinal global e recente:** a preferência é do LEITOR, não do livro —
   agrega as observações de todos os livros, janela das 200 mais recentes
   (padrões antigos perdem peso conforme saem da janela).
3. **Sem bloco sem evidência:** histórico vazio, amostras insuficientes ou
   nenhuma taxa acima do limiar → bloco vazio e prompt idêntico ao da Fase 5.
4. **Degradação graciosa (ADR-005):** sem banco/erro no provider → proativo
   dispara exatamente como hoje, sem preferência.
5. **Fronteira ADR-006:** agregação e formatação do bloco são lógica PURA em
   `src/core/proactive_learning.py`; o acesso ao banco é injetado no serviço
   da GUI como callable (padrão `set_observations_provider` da Fase 5).

## 2. Mudanças (4 arquivos de código + testes)

| Arquivo | Mudança |
|---|---|
| `src/core/proactive_learning.py` (novo) | `build_preference_block(observations, min_samples=4, dismiss_threshold=0.6) -> str` — agrega `kind`/`dismissed` das linhas injetadas; lista (máx. 3) os tipos a evitar com contagem "dispensou D de T"; cláusula "prefira" só quando resta tipo não evitado no histórico; vazio se nada qualifica. |
| `src/gui/workers/proactive_worker.py` | Novo parâmetro `preference_block: str = ""`; `_build_payload` injeta o bloco entre a REGRA CRÍTICA e o bloco de memória da Fase 5 (antes do trecho). |
| `src/gui/proactive_reader_service.py` | `set_dismissal_history_provider(fn)` — `fn() -> list[dict]` (global, com dispensadas); em `process_page_context` monta o `preference_block` e passa ao worker. Falha do provider → segue sem preferência. |
| `src/gui/reader_view.py` | Injeta o provider: wrapper de `self._db.get_observations(include_dismissed=True, limit=200)` (global — sem book_id). |

## 3. Testes contratados

- `tests/test_proactive_learning.py` (novo): vazio/None → ""; amostra abaixo do
  mínimo → ""; taxa abaixo do limiar → ""; tipo qualificado → bloco com nome,
  contagem e instrução de evitar; "prefira" presente só quando há tipo não
  evitado; linhas sem `kind` ignoradas; limite de 3 tipos no bloco.
- `test_proactive_worker.py`: payload contém o bloco quando fornecido, antes da
  memória e do trecho; sem preferência o prompt é idêntico ao atual (regressão).
- `test_proactive_reader_service.py`: worker recebe `preference_block` montado
  do histórico; provider quebrado → dispara sem preferência (ADR-005).

## 4. Fora de escopo (explícito)

- Supressão/throttling de tipos dispensados (decisão do usuário: só prompt).
- Aprendizado com 👍/👎 do RAG (`agent_feedback`) — exigiria coleta de motivo
  no 👎; candidato a fase futura.
- Aprender dos traces do TraceLogger.
- Qualquer mudança no ProactiveTriggerEngine, na cadência ou nos 3 tipos de
  observação do prompt.
- Migração de schema (a fase só LÊ `ai_observations`).

## 5. Rollback

Reverter o merge da branch. Nenhuma migração de schema.

## 6. Registro de execução

- 2026-07-07: contrato criado e executado na mesma sessão, após escolha de
  escopo pelo usuário via AskUserQuestion (proativo+dispensas, só prompt).
