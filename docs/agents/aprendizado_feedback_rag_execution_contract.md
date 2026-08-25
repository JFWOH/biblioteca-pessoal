---
title: "Contrato de Execução — Aprendizado com 👍/👎 do RAG"
status: "Aprovado para execução autônoma"
version: "1.0"
date: "2026-07-13"
audience:
  - Engenharia
  - QA
owner: "Sessão do workflow de otimização (branch feature/aprendizado-feedback-rag)"
phase: "grafo-fase-6-followup"
execution_mode: "autonomous"
requires_manual_confirmation: false
related_docs:
  - "docs/agents/aprendizado_dispensas_execution_contract.md"
  - "docs/revisao-engenharia-2026-07-05.md"
  - "CLAUDE.md"
  - "AGENTS.md"
rollback_marker: true
mode: "PRODUCTION ENGINEERING"
---

# Contrato de Execução — Aprendizado com 👍/👎 do RAG

> **Objetivo:** o agente RAG já coleta 👍/👎 do usuário sobre as respostas
> (`agent_feedback`), mas a coluna `reason` nunca é preenchida — o 👎 não captura
> POR QUE a resposta falhou. A revisão de engenharia de 2026-07-05 (§3.3) listou
> isso explicitamente como direção que o alicerce atual já suporta: *"Fase 6
> (aprender dos traces): o feedback 👍/👎 do RAGPanel já é coletado; hoje não
> alimenta nada."* Este contrato fecha essa lacuna: o 👎 ganha captura OPCIONAL
> de motivo (chips de 1 clique) e o orchestrator passa a orientar o modelo, via
> prompt, com base nos padrões recentes de feedback negativo — no mesmo espírito
> do aprendizado com dispensas já entregue (`docs/agents/aprendizado_dispensas_execution_contract.md`,
> que citava esta mesma feature como "candidata a fase futura").

## 0. Decisão executiva

```text
Decisão: APROVAR execução autônoma. Escopo já validado pelo usuário.
Branch: feature/aprendizado-feedback-rag.
Execução: dois agentes em paralelo (ver Seção 2 — divisão por camada evita
  conflito de arquivos; o único ponto de acoplamento é o par de assinaturas
  desta Seção 3, que é contrato fechado, não sujeito a renegociação).
Regra central: conflito entre implementação e contrato → contrato prevalece;
  ambiguidade real (não coberta aqui) → perguntar ao usuário (CLAUDE.md §1).
```

## 1. Comportamento contratado

1. **👍 sem fricção:** fluxo atual inalterado — grava o voto e mostra
   "✅ Obrigado!" (nenhuma captura de motivo no positivo; fora de escopo, ver
   Seção 6).
2. **👎 grava o voto imediatamente**, exatamente como hoje (1 voto por
   resposta, ver `_on_feedback_clicked` em `src/gui/widgets/rag_panel.py:843`),
   e em seguida mostra chips OPCIONAIS de motivo. Ignorar os chips (fazer nova
   pergunta) é um caminho válido: o voto já foi persistido sem motivo.
3. **Aprendizado é só por orientação de prompt** (mesma filosofia da Fase 6 de
   dispensas): nenhuma resposta é bloqueada, reescrita ou suprimida em código
   por causa do histórico de feedback — o bloco entra como instrução para o
   modelo se autocorrigir.
4. **Degradação graciosa (ADR-005):** qualquer falha ao ler `agent_feedback`,
   montar o bloco ou persistir o motivo é engolida com log — a query RAG segue
   normal, sem bloco, sem crash, sem afetar o voto já gravado.
5. **Fronteira ADR-006:** agregação/formatação do bloco é lógica PURA em
   `src/core/feedback_learning.py` (sem Qt, sem SQLite direto — recebe `rows`
   já carregadas). Leitura do banco e UI dos chips ficam na camada GUI/orchestrator.

## 2. Escopo e entregas por camada (divisão para os 2 agentes)

| Camada | Arquivo(s) | Agente sugerido | Entrega |
|---|---|---|---|
| DB | `src/core/database.py` | A (backend) | `add_feedback` passa a retornar `lastrowid`; novos `set_agent_feedback_reason` e `get_recent_agent_feedback` |
| Core (aprendizado) | `src/core/feedback_learning.py` (novo) | A (backend) | `build_feedback_block(rows) -> str \| None`, puro (ADR-006) |
| Injeção no orchestrator | `src/core/rag/orchestrator.py::query_rag` | A (backend) | mensagem `system` extra + evento no `TraceLogger` |
| GUI — chips de motivo | `src/gui/widgets/rag_panel.py` | B (GUI) | chips, `QLineEdit` de texto livre, novo sinal |
| GUI — persistência do motivo | `src/gui/main_window.py` | B (GUI) | usa o `lastrowid` do voto, chama `set_agent_feedback_reason` |

O acoplamento entre os dois agentes é só a Seção 3 (assinaturas exatas) — com
elas fixas, DB/core/orchestrator (Agente A) e GUI (Agente B) podem avançar sem
esperar um pelo outro; a integração final é conectar os pontos já definidos.

## 3. Contratos de interface (exatos)

### 3.1 `LibraryDB` (`src/core/database.py`)

```python
def add_feedback(self, rating: int, kind: str = "answer", book_id=None, page=None,
                 session_id: str = "", target_ref: str = "", reason: str = "",
                 query: str = "") -> int:
    """Grava o voto (assinatura existente, inalterada) e retorna o lastrowid
    do INSERT — necessário para o UPDATE posterior do motivo. Hoje não
    retorna nada; a mudança é só adicionar o retorno."""

def set_agent_feedback_reason(self, feedback_id: int, reason: str) -> None:
    """UPDATE agent_feedback SET reason=? WHERE id=?. No-op silencioso se
    feedback_id não existir (0 linhas afetadas não é erro)."""

def get_recent_agent_feedback(self, limit: int = 200) -> list[dict]:
    """SELECT * FROM agent_feedback ORDER BY id DESC LIMIT ?. Linhas mais
    recentes primeiro, como dicts (mesmo padrão de outros getters de LibraryDB)."""
```

### 3.2 `src/core/feedback_learning.py` (novo, core puro — ADR-006)

```python
def build_feedback_block(rows: list[dict]) -> str | None:
    """Bloco de orientação para o prompt do RAG a partir do histórico recente
    de agent_feedback (None se nada qualifica — ver limiares na Seção 5).
    Espera dicts com pelo menos as chaves `rating` e `reason` (formato de
    get_recent_agent_feedback). Linhas malformadas (chaves ausentes, tipos
    inesperados) são ignoradas, nunca levantam exceção (ADR-005)."""
```

Nome e padrão (`build_<algo>_block(rows/observations) -> str`) espelham
deliberadamente `src/core/proactive_learning.py::build_preference_block` da
Fase 6 de dispensas — mesma convenção do projeto para blocos de aprendizado
injetados em prompt.

### 3.3 GUI (`src/gui/widgets/rag_panel.py`, `src/gui/main_window.py`)

```python
# RAGPanel — novo sinal, ao lado de feedback_submitted (rag_panel.py:43)
feedback_reason_submitted = pyqtSignal(int, str)  # (feedback_id, reason)

# RAGPanel — novo método público, chamado pela MainWindow após persistir o voto
def on_feedback_persisted(self, feedback_id: int) -> None:
    """Associa o feedback_id do voto (lastrowid do add_feedback) ao painel,
    permitindo que os chips (se e quando clicados) emitam
    feedback_reason_submitted(feedback_id, reason) com o id correto."""
```

`MainWindow._on_rag_feedback` (`main_window.py:476-481`) passa a capturar o
retorno de `add_feedback(...)` e, só quando `rating == -1`, chamar
`self._rag_panel.on_feedback_persisted(feedback_id)`. Um novo slot conecta
`feedback_reason_submitted` a uma chamada de
`self._db.set_agent_feedback_reason(feedback_id, reason)` (mesmo padrão
try/except com log de aviso do handler atual — nunca propaga exceção para a UI).

## 4. UX dos chips (fluxo)

| Chip | valor gravado em `reason` |
|---|---|
| Errada | `resposta_errada` |
| Incompleta | `incompleta` |
| Fora do contexto | `fora_contexto` |
| Genérica | `generica` |
| Outro… | texto livre digitado pelo usuário, **cru** (sem normalização) |

Fluxo: clique em 👎 → voto gravado imediatamente (comportamento já existente,
inalterado) → linha de chips aparece abaixo dos botões de feedback, todos
opcionais → usuário escolhe um chip **ou** clica "Outro…" (abre um
`QLineEdit`; `Enter` confirma o texto digitado, `Esc` volta para a linha de
chips sem gravar nada) → ao escolher qualquer opção, o painel emite
`feedback_reason_submitted(feedback_id, reason)`, que dispara o `UPDATE` na
MESMA linha do voto (nunca uma nova linha), e o botão mostra "✅ Obrigado!" —
os chips desaparecem. Ignorar os chips (fazer nova pergunta) é um caminho
válido; `on_answer_complete`/`set_reading_context` (que já resetam
`_feedback_given`, `rag_panel.py:741-742` e `948-951`) também devem esconder
qualquer chip pendente da resposta anterior. Voto único por resposta
continua garantido pelo `_feedback_given` existente — os chips não reabrem
esse portão.

**Corrida id/chip:** `on_feedback_persisted` é chamado pela MainWindow dentro
do próprio handler de `feedback_submitted` (conexão direta, mesma thread) —
ou seja, o `feedback_id` já é conhecido antes de `_on_feedback_clicked`
terminar de mostrar os chips. A implementação deve garantir que um clique em
chip nunca perca o motivo nem o associe ao `feedback_id` errado; a forma
exata (armar os chips só depois de `on_feedback_persisted`, desabilitá-los
até lá, ou bufferizar a escolha) fica a critério do agente que implementar a
GUI, desde que um teste de regressão cubra essa ordem (ver Seção 7).

## 5. Limiares e mapeamento categoria → instrução

| Parâmetro | Valor |
|---|---|
| Janela de linhas consideradas | 200 mais recentes (`get_recent_agent_feedback(limit=200)`) |
| Mínimo de negativos (`rating == -1`) para existir bloco | 4 |
| Mínimo de ocorrências para uma categoria qualificar | 3 (contadas só entre os negativos) |
| Teto de categorias no bloco | 2 — ordenadas por contagem desc; empate resolvido pela ordem canônica abaixo |
| Ordem canônica (para desempate) | `resposta_errada` → `incompleta` → `fora_contexto` → `generica` |
| Texto livre ("Outro…") | conta no total de negativos, **nunca** vira categoria própria |
| ≥4 negativos mas nenhuma categoria qualificada (ex.: tudo texto livre ou disperso) | bullet genérico, sem apontar categoria específica |
| <4 negativos no total | `build_feedback_block` retorna `None` (sem bloco) |

Mapeamento fixo categoria → instrução injetada (uma linha por categoria
qualificada, respeitando o teto de 2):

| Categoria | Instrução (PT) |
|---|---|
| `resposta_errada` | Verificar as afirmações contra o conteúdo do livro/contexto antes de responder — evitar alegações não sustentadas pelo texto recuperado. |
| `incompleta` | Responder com completude: cobrir os pontos relevantes da pergunta e citar as páginas/fontes usadas. |
| `fora_contexto` | Restringir-se ao contexto do livro fornecido — não responder com conhecimento geral fora do que foi recuperado. |
| `generica` | Evitar respostas genéricas — trazer detalhes concretos e específicos do livro. |

## 6. Fora de escopo (registrar como futuro)

- Interpretar o texto livre do "Outro…" via LLM (hoje só conta para o total
  de negativos, nunca vira categoria).
- Aprender dos traces do `TraceLogger` (ADR-004) — fonte de sinal diferente,
  fora deste MVP.
- Qualquer UX de captura de motivo no 👍 (positivo permanece sem fricção).
- Supressão/bloqueio de respostas em código com base no histórico de feedback
  — decisão já tomada na Fase 6 de dispensas e reafirmada aqui: só prompt.
- Migração de schema (a feature só lê/atualiza `agent_feedback`, que já tem a
  coluna `reason`).

## 7. Critérios de aceite / Definition of Done

- **Core (`feedback_learning.py`):** testes unitários cobrindo os limiares da
  Seção 5 (abaixo do mínimo de negativos, categoria abaixo do mínimo de
  ocorrências, teto de 2 categorias com empate resolvido pela ordem canônica,
  texto livre não vira categoria, linhas malformadas ignoradas sem exceção) —
  arquivo sem nenhum import de PyQt6 (guarda estrutural, mesmo padrão de
  `tests/test_proactive_learning.py`).
- **GUI (`rag_panel.py`):** testes com `qtbot` cobrindo os chips (aparecem só
  após 👎, valores corretos de `reason` por chip), o fluxo "Outro…" (Enter
  confirma, Esc cancela sem emitir sinal), a corrida id/chip descrita na
  Seção 4, e o reset dos chips ao trocar de resposta/pergunta — seguir o
  padrão de `tests/test_rag_panel_feedback.py` já existente.
- **Orchestrator:** teste cobrindo a injeção do bloco como mensagem `system`
  na posição correta (depois das tools, antes do contexto) e o evento
  `feedback_block_injected` no `TraceLogger` quando o bloco existe; ausência
  de bloco não deve alterar o prompt atual (regressão).
- Suíte completa verde (`venv\Scripts\python -m pytest tests/ -q`) e
  `venv\Scripts\python -m ruff check` limpo nos arquivos tocados.
- Nenhum commit/push sem pedido explícito do usuário nesta sessão.

## 8. Rollback

Reverter o merge da branch. Sem migração de schema — `agent_feedback.reason`
já existe e seu valor default (`''`) continua válido para linhas antigas e
para votos onde o usuário ignorou os chips.

## 9. Registro de execução (a preencher pelas sessões executoras)

| Item | Status | Commit | Observações |
|---|---|---|---|
| DB — `add_feedback` retorna lastrowid + novos métodos | ✅ | | Bookkeeping regularizado na rodada ago/2026 (Onda T): código e testes JÁ estavam entregues (`src/core/feedback_learning.py`, `tests/test_feedback_learning.py`, `tests/test_rag_panel_feedback.py`) — a tabela ficara sem preencher |
| Core — `feedback_learning.py` + testes | ✅ | | idem |
| Injeção no `orchestrator.query_rag` + evento de trace | ✅ | | idem |
| GUI — chips + sinal `feedback_reason_submitted` | ✅ | | idem |
| GUI — `on_feedback_persisted` + persistência do motivo | ✅ | | idem |
| Suíte completa final | ✅ | | verde nas rodadas subsequentes (1850+ testes em ago/2026) |
