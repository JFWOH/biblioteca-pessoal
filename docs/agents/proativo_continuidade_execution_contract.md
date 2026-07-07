---
title: "Contrato de Execução — Fase 5: Proativo com Continuidade"
status: "Aprovado para execução autônoma"
version: "1.0"
date: "2026-07-07"
audience:
  - Engenharia
  - QA
owner: "Sessão do workflow de otimização (branch feature/proativo-continuidade)"
phase: "grafo-fase-5"
execution_mode: "autonomous"
requires_manual_confirmation: false
related_docs:
  - "docs/revisao-engenharia-2026-07-05.md"
  - "CLAUDE.md"
  - "AGENTS.md"
rollback_marker: true
mode: "PRODUCTION ENGINEERING"
---

# Contrato de Execução — Fase 5: Proativo com Continuidade

> **Objetivo:** o agente proativo de leitura hoje não sabe o que já disse — pode
> repetir a mesma observação ao reler uma página em outra sessão, e não usa a
> memória acumulada do livro. A Fase 1b já persiste toda observação em
> `ai_observations` (book_id, page, kind, content, dismissed); esta fase fecha o
> ciclo: o proativo passa a CONSULTAR essa memória antes de gerar.

## 0. Decisão executiva

```text
Decisão: APROVAR execução autônoma (workflow contínuo aprovado em 2026-07-06).
Branch: feature/proativo-continuidade (a partir da main pós-PR #11).
Regra central: conflito entre implementação e contrato → contrato prevalece;
  ambiguidade real → perguntar ao usuário (CLAUDE.md §1).
```

## 1. Comportamento contratado

1. **Skip de página já observada:** se a página tem observação NÃO dispensada em
   `ai_observations`, o proativo não dispara para ela (nem entre sessões — o
   ProactiveTriggerEngine só evita repetição na sessão corrente). Observação
   dispensada (dismissed=1) NÃO conta: o usuário descartou, pode receber outra.
2. **Memória no prompt:** ao gerar para uma página nova, as N observações mais
   recentes do livro (default 5, conteúdo truncado a 160 chars) entram no prompt
   num bloco demarcado, com a regra explícita de não repetir nem parafrasear.
3. **Degradação graciosa (ADR-005):** sem banco/sem book_id/erro no SQLite, o
   proativo se comporta exatamente como hoje (sem memória, sem skip).
4. **Fronteira ADR-006:** formatação do bloco de memória e decisão de skip são
   lógica PURA em `src/core/proactive_continuity.py`; o acesso ao banco é
   injetado no serviço da GUI como callable (padrão do `set_cross_reference`).

## 2. Mudanças (4 arquivos de código + testes)

| Arquivo | Mudança |
|---|---|
| `src/core/proactive_continuity.py` (novo) | `build_memory_block(observations, max_items=5, max_chars_each=160) -> str` (vazio se sem observações) e `already_observed_page(observations) -> bool` (ignora dispensadas — o chamador já filtra via `include_dismissed=False`, mas a função re-checa `dismissed` por robustez). |
| `src/gui/workers/proactive_worker.py` | Novo parâmetro `memory_block: str = ""`; `_build_payload` injeta o bloco no prompt entre a REGRA CRÍTICA e o trecho. |
| `src/gui/proactive_reader_service.py` | `set_observations_provider(fn)` — `fn(book_id, page=None) -> list[dict]`; em `process_page_context`: skip se página já observada; monta `memory_block` e passa ao worker. Falha do provider → segue sem memória. |
| `src/gui/reader_view.py` | Injeta o provider: wrapper de `self._db.get_observations(...)` (limit 5 p/ memória; por página p/ skip). |

## 3. Testes contratados

- `tests/test_proactive_continuity.py` (novo): bloco formatado com cabeçalho e
  regra; truncamento; lista vazia → ""; `already_observed_page` True/False e
  ignorando dispensadas.
- `test_proactive_worker.py`: payload contém o bloco quando fornecido; sem
  memória o prompt é idêntico ao atual (regressão).
- `test_proactive_reader_service.py`: página já observada → worker NÃO inicia;
  worker recebe memory_block montado; provider quebrado → dispara sem memória.

## 4. Fora de escopo (explícito)

- Conceitos do grafo no prompt do proativo (enriquecimento futuro; a Fase 5 do
  plano cobre só a continuidade de observações).
- Aprendizado com feedback 👍/👎 (Fase 6).
- Qualquer mudança no ProactiveTriggerEngine ou na cadência de disparo.

## 5. Rollback

Reverter o merge da branch. Nenhuma migração de schema: a fase só LÊ
`ai_observations` (tabela da Fase 1b).

## 6. Registro de execução

- 2026-07-07: contrato criado e executado na mesma sessão (workflow contínuo
  aprovado pelo usuário em 2026-07-06; sprints A0-A5, B1, B2 já entregues).
