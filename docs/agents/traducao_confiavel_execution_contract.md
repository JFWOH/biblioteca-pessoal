---
title: "Contrato de Execução — Tradução Confiável (seleção/página) + Leitura Traduzida Contínua"
status: "Aprovado para execução autônoma"
version: "1.0"
date: "2026-07-03"
audience:
Engenharia
QA
owner: "Sessão original (branch feature/graph-mvp / feature/reliable-translation)"
phase: "backlog-ux-followup"
execution_mode: "autonomous"
requires_manual_confirmation: false
related_docs:
"docs/agents/phase_13_execution_contract.md"
"CLAUDE.md"
"AGENTS.md"
rollback_marker: true
mode: "PRODUCTION ENGINEERING"
---

Contrato de Execução — Tradução Confiável (seleção/página) + Leitura Traduzida Contínua

> **Objetivo deste documento:** registrar as decisões já aprovadas para corrigir a
> confiabilidade da tradução offline (NLLB) no leitor — tanto por seleção quanto por
> página inteira — e adicionar leitura contínua traduzida do livro. Permite execução
> autônoma pela sessão responsável, sem novas confirmações manuais, desde que a
> implementação respeite integralmente este contrato e as regras gerais do projeto
> (CLAUDE.md, AGENTS.md, ADRs em `.agents/adr/`).
>
> **Origem:** investigação de um bug relatado pelo usuário em uso real — seleção de um
> parágrafo traduziu a página inteira com falhas graves (loops de repetição do NLLB).
> Este contrato foi produzido por uma sessão de diagnóstico (sem editar código, por
> haver outra sessão com WIP não commitado no mesmo diretório) e deve ser executado
> pela sessão original, que finaliza primeiro seu próprio WIP pendente.

---

## 0. Decisão executiva

```text
Decisão: APROVAR execução autônoma deste contrato.
Modo: Execução sem confirmações humanas adicionais durante os 5 commits descritos.
Pré-condição: a sessão executora finaliza (testa, lint, commita) o WIP pendente da
  feature de seleção-por-fluxo ANTES de iniciar este trabalho.
Branch: nova branch a partir de feature/graph-mvp (a feature de seleção corrigida
  ainda não existe em main; ver Seção 2).
Regra central: se surgir conflito entre uma escolha de implementação e este contrato,
  o contrato prevalece; em caso de ambiguidade real (não coberta aqui), perguntar ao
  usuário em vez de assumir (CLAUDE.md §1).
```

---

## 1. Contexto e diagnóstico (evidência com file:line)

Usuário selecionou um parágrafo de PDF e pediu tradução; o app traduziu a página
inteira com falhas graves (loops de repetição do NLLB). Três causas confirmadas por
leitura de código:

1. **Seleção vaza para a página inteira** — `get_selection_flow`
   (`src/readers/pdf_reader.py:269`) ordena as palavras por `(block, line, word)`, que é
   a ordem de armazenamento no **documento**, não a ordem visual. Quando o rodapé
   ("22") está em um bloco anterior ao corpo da página no PDF do usuário,
   `first_at_or_after` devolve um índice próximo de zero e o span "engole" a página
   inteira. Prova: a tradução exibida ao usuário começava com "22 A Mente...".
2. **NLLB degenera em texto longo** — `src/core/translation_backends/nllb_backend.py:119-128`:
   o texto inteiro é passado numa única chamada ao tokenizer/modelo com
   `truncation=True, max_length=512`; textos que excedem isso truncam e o modelo entra
   em repetição. O modo "Ler Página Traduzida" (item 7 do backlog UX, já em produção)
   sofre do mesmo mal — confirmado pelo usuário.
3. **Superfície de exibição errada** — a tradução por seleção aparece num
   `QMessageBox` não-modal (`src/gui/main_window.py:929-939`), destoante do resto da
   experiência (que usa o painel do assistente).

Requisitos aprovados pelo usuário:
- Corrigir a seleção (não vazar para a página).
- Fatiar o NLLB por sentenças (elimina truncamento/repetição).
- Exibir a tradução como cartão no painel do assistente (não mais `QMessageBox`).
- Permitir traduzir por **seleção OU página inteira**, sempre com **aviso do que está
  sendo processado** (statusbar + header do cartão — aviso informativo, sem diálogo de
  confirmação).
- **Leitura traduzida contínua** do livro inteiro (avanço automático, no mesmo espírito
  da leitura contínua já existente).

**Viabilidade: alta.** O loop de encadeamento da leitura contínua já existe
(`_on_audio_finished` → `_continue_narration` → `_toggle_audio`); a feature é ligar a
tradução dentro desse loop existente. Não há nada novo no core além do chunking do NLLB.

---

## 2. Pré-condição: finalizar o WIP da sessão original

Antes de iniciar qualquer commit deste contrato:

1. Rodar `venv\Scripts\python -m pytest tests/ -q` (suíte completa) e
   `venv\Scripts\python -m ruff check src/gui/reader_view.py src/readers/pdf_reader.py
   tests/test_selection_flow.py` sobre o WIP existente (seleção por fluxo de texto +
   fix de clique na margem direita, em `src/gui/reader_view.py` e
   `src/readers/pdf_reader.py`, com `tests/test_selection_flow.py` novo).
2. Se verde: commitar com mensagem convencional (sugestão:
   `feat(reader): seleção de texto por fluxo (multi-linha) + fix de clique na margem direita`)
   na branch atual (`feature/graph-mvp`) e dar `git push`.
3. Criar **nova branch** a partir de `feature/graph-mvp` para este contrato — sugestão
   de nome: `feature/reliable-translation`. Justificativa: a Fase 2/3 do grafo e o
   backlog UX completo já vivem em `feature/graph-mvp` (PR #2 aberto); a correção de
   seleção que este trabalho depende (`get_selection_flow`) só existe ali, não em
   `main`.
4. **Não tocar**: arquivo `nul` (artefato espúrio do Windows na raiz — apenas
   sinalizar, nunca commitar); `docs/mobile-*.md` (documentação de outra sessão, ficam
   untracked até decisão do usuário).

---

## 3. Fonte de verdade

A implementação deve obedecer, nesta ordem:
1. Este contrato de execução.
2. `CLAUDE.md` (Definition of Done, regras de ambiente/venv).
3. `AGENTS.md` e ADRs em `.agents/adr/` (ADR-005 degradação graciosa, ADR-006 fronteira
   GUI↔Core).
4. Padrões já estabelecidos no código (ex.: `_toggle_continuous_reading`,
   `find_next_readable_page`, `TranslationService`).

---

## 4. Decisões humanas já aprovadas (não perguntar novamente)

- Tradução por seleção **e** por página inteira coexistem (não é "ou").
- Aviso de processamento é **informativo** (statusbar + header do cartão) — não exige
  diálogo de confirmação bloqueante.
- Cartão de tradução vive no **painel do assistente** (`RagPanel`), não em popup/dialog
  separado.
- Leitura contínua traduzida é **sequencial e simples** no MVP: a tradução da próxima
  página só começa quando a narração da atual termina (não há pré-tradução/pipeline
  paralelo). Latência aceita como trade-off do MVP.
- PDFs de duas colunas (ordenação ainda imperfeita mesmo com `sort=True`) são uma
  **limitação conhecida e documentada**, não um bloqueador desta entrega.
- `max_length=512` no NLLB permanece como rede de segurança (defesa em profundidade),
  mesmo com o chunking por sentenças evitando estourá-lo na prática.

## 5. Limites de autonomia

**Pode decidir autonomamente:** nomes exatos de funções/variáveis internas (desde que
sigam os padrões do arquivo), formatação exata do cartão HTML, mensagens de
statusbar (mantendo o tom/emoji já usado no projeto), limite de caracteres por lote do
NLLB dentro da faixa sugerida (1200–1600).

**Não pode decidir autonomamente:** introduzir dependências novas (nenhuma é
necessária); mudar a superfície de exibição da tradução para algo além do cartão no
painel; tornar o aviso de processamento um diálogo bloqueante; paralelizar a tradução
contínua (fora do escopo do MVP); fazer merge do PR/branch sem autorização explícita do
usuário; commitar/pushar sem que o usuário tenha pedido nesta sessão (ou seguindo a
mesma convenção já estabelecida nas sessões anteriores deste projeto, onde o usuário
pediu "commite" a cada marco).

---

## 6. Implementação — 5 commits

### Commit 1 — `fix(reader): seleção por fluxo usa ordem visual das palavras`

**Arquivo:** `src/readers/pdf_reader.py`

- Linha ~269: trocar `page.get_text("words")` por
  `page.get_text("words", sort=True)` (ordem visual topo→baixo / esquerda→direita; os
  campos da tupla continuam os mesmos, o agrupamento por `(block, line)` nas linhas
  ~300-309 continua válido).
- Comentar a limitação conhecida: PDFs de duas colunas com bandas horizontalmente
  sobrepostas ainda podem ordenar de forma imperfeita mesmo com `sort=True` — não é o
  alvo desta correção (o alvo é o caso comum: rodapé/cabeçalho fora de ordem no fluxo
  de leitura de uma coluna).

**Testes:**
- Corrigir `tests/test_selection_flow.py:37` (`_word_center_pct`) — usa o mesmo
  `sorted(page.get_text("words"), key=lambda w: (w[5], w[6], w[7]))` que tinha o bug;
  trocar para `page.get_text("words", sort=True)` também, para que o teste helper
  reflita a mesma ordem de leitura usada pela função real.
- Novo teste de regressão: montar um PDF sintético (fitz) onde o texto do **rodapé é
  inserido PRIMEIRO** no documento (block_no menor) e o corpo do parágrafo depois;
  selecionar por fluxo um trecho do meio/fim do corpo; `assert` que o texto resultante
  é **só** o parágrafo, sem o rodapé. Este teste deve **falhar antes do fix** (prova de
  regressão) **e passar depois**.

### Commit 2 — `fix(translation): NLLB fatiado por sentenças (corrige repetição/truncamento)`

**Arquivo:** `src/core/translation_backends/nllb_backend.py` (core puro, ADR-006 ok,
sem novas dependências)

- `_split_sentences(text: str) -> list[str]`: `re.split(r'(?<=[.!?…])\s+|\n+', text)`,
  remove vazios/whitespace.
- `_batch_sentences(sentences: list[str], max_chars: int = 1400) -> list[str]`:
  empacotamento guloso das sentenças em lotes sob o orçamento de caracteres
  (~350-400 tokens equivalentes); uma sentença sozinha maior que o orçamento vira seu
  próprio lote (nunca quebra no meio de uma sentença).
- Extrair o bloco atual de tokenizar/gerar/decodificar (linhas ~115-132) para
  `_translate_one_batch(self, batch: str, src_nllb: str, tgt_nllb: str) -> str`.
- `translate()` passa a: validar/truncar por `max_input_length` (comportamento
  existente, mantido como rede de segurança) → `_split_sentences` → `_batch_sentences`
  → loop chamando `_translate_one_batch` por lote → `" ".join(...)` dos resultados na
  ordem original. Assinatura pública (`translate(text, src_lang, tgt_lang)`) inalterada.
- `max_length=512` no `_translate_one_batch` mantido (defesa em profundidade — decisão
  aprovada, Seção 4).

**Testes:** unitários puros de `_split_sentences`/`_batch_sentences` (fronteiras de
sentença comuns — ponto, exclamação, interrogação, reticências, quebra de linha;
entrada vazia; sentença única maior que o orçamento; N sentenças curtas empacotadas
num só lote). Teste de `translate()` com `_translate_one_batch` mockado (não carrega
modelo real) verificando: chamado uma vez por lote esperado, e o resultado final é o
join na ORDEM correta. Adicionar em `tests/test_nllb_offline.py` (arquivo já existe,
padrão de mock com `monkeypatch`/`patch` já estabelecido) ou em novo
`tests/test_nllb_chunking.py`, à escolha da sessão executora.

### Commit 3 — `feat(gui): cartão de tradução no painel do assistente (substitui QMessageBox)`

**Arquivos:** `src/gui/widgets/rag_panel.py`, `src/gui/main_window.py`

- Novo método público `RAGPanel.show_translation_card(source_desc: str, original: str,
  translated: str) -> None`: usa `self._response_area` (QTextEdit, já existe — ver
  `rag_panel.py:165-176`), move o cursor para o fim
  (`QTextCursor.MoveOperation.End`) e `insertHtml` com: separador visual, header
  `🌐 Tradução — {source_desc} ({len(original)} caracteres)`, e o texto traduzido
  (sempre `html.escape` no texto do usuário/modelo antes de inserir — nunca HTML cru).
  Usar as MESMAS variáveis de cor que `set_theme` já define para o tema atual
  (`rag_panel.py:473-680`; ex. `text_main`/`bg_input`/`border_color` conforme o tema
  ativo) — não hardcodar cores novas.
- Em `main_window.py:923-949` (handler `action_type == "translate"`): remover o bloco
  do `QMessageBox` e a referência `self._translation_msg` (única ocorrência no
  projeto — grep confirma; seguro remover sem deixar `_msg` órfão). `on_success` passa
  a chamar `self._rag_panel.show_translation_card("Seleção (N caracteres)",
  original_text, result)` — garantir que o painel esteja visível/ancorado ao leitor
  antes (mesmo padrão de `_reader_view.set_ai_panel`/`show_ai_panel` já usado em
  `_on_ai_action_requested` para as demais ações, linhas ~995-999). Statusbar continua
  mostrando o aviso de "traduzindo".

**Testes:** teste com `qtbot` instanciando `RAGPanel`, chamando `show_translation_card`
e verificando que `_response_area.toPlainText()` contém o header (com a contagem de
caracteres) e o texto traduzido.

### Commit 4 — `feat(reader): traduzir página inteira com aviso do que é processado`

**Arquivos:** `src/gui/reader_view.py`, `src/gui/main_window.py`

- Nova `QAction("🌐 Traduzir Página (texto)", self)` no overflow menu, próxima de
  `_act_read_translated` (`reader_view.py:370-372`) — esta é a versão **texto** (mostra
  o cartão), distinta da já existente "Ler Página Traduzida (PT)" (que narra). Usa
  `get_page_text` do mesmo jeito que `_on_read_translated_page` (`reader_view.py:1598-1616`)
  e emite `ai_action_requested("translate_page", page_text)`.
- Novo ramo no dispatcher `_on_ai_action_requested` (`main_window.py`, perto do handler
  `"read_translated_page"`, linha ~982-985): `"translate_page"` → mostra
  statusbar `"🌐 Traduzindo página X inteira (N caracteres)…"` → ao concluir, chama
  `self._rag_panel.show_translation_card(f"Página {X} inteira", page_text, result)`.
  Reusar `detect_language` (`src/core/tts/language_detect.py`) exatamente como
  `_read_translated_page` já faz (`main_window.py:1014-1029`) — se a página já está em
  PT, avisar na statusbar e **não** traduzir (mostrar só o texto original no cartão, ou
  pular o cartão — decisão de implementação livre, mas sem chamar o NLLB à toa).
- O "aviso do que está sendo processado" é a mensagem de statusbar + o header do
  cartão (`source_desc` com a contagem de caracteres) — nenhum diálogo de confirmação
  novo.

**Testes:** a ação existe no menu overflow e, ao disparar, emite o sinal
`ai_action_requested` com a chave e o texto corretos (mock/qtbot); mensagem de
statusbar contém a contagem de caracteres esperada.

### Commit 5 — `feat(audio): leitura contínua traduzida do livro inteiro`

**Arquivos:** `src/gui/reader_view.py`, `src/gui/main_window.py`

- `ReaderView.__init__`: novo `self._continuous_translate_mode = False`; persistir em
  config na chave `"tts.continuous_translate_reading"` — espelhar exatamente o padrão
  de `_toggle_continuous_reading` (`reader_view.py:1618-1632`, incluindo o
  `_cfg.get(...)` na criação da action e o `config.set(...)` no toggle).
- Nova `QAction` checável `"🌐🔁 Leitura Contínua Traduzida (PT)"` no overflow menu,
  junto das outras actions de áudio/tradução.
- Fork em `_toggle_audio` (`reader_view.py:1506`): **apenas no caminho de INICIAR**
  narração (isto é, dentro do `if not worker or not worker.isRunning()` — ou seja,
  DEPOIS do bloco de pause/resume em 1513-1519, que não muda) — se
  `self._continuous_translate_mode` estiver ativo, em vez de
  `self._launch_audio_worker(page_text, chain_continuous=True)` (linha 1535), emitir
  `self.ai_action_requested.emit("read_translated_page_chained", page_text)`.
- `narrate_text` (`reader_view.py:1563`): novo parâmetro opcional
  `chain_continuous: bool = False`, repassado para `_launch_audio_worker(text.strip(),
  chain_continuous=chain_continuous)` (hoje a chamada em 1572 não passa o parâmetro —
  ajustar).
- `_on_audio_finished` (`reader_view.py:1636`): condição de entrada passa de
  `self._continuous_reading and self._chain_continuous` para
  `(self._continuous_reading or self._continuous_translate_mode) and
  self._chain_continuous` — sem este ajuste, o modo traduzido não encadeia quando a
  leitura contínua normal (não-traduzida) está desligada.
- Em `main_window.py`: refatorar `_read_translated_page(self, text)` (linhas
  ~1014-1046) para `_translate_and_narrate(self, text: str, enable_chaining: bool)`;
  a chamada existente para a ação `"read_translated_page"` (single-shot, sem
  encadeamento) passa `enable_chaining=False`; nova chave de ação
  `"read_translated_page_chained"` no dispatcher chama com `enable_chaining=True`. Em
  ambos os casos, `on_success` chama `self._reader_view.narrate_text(result,
  chain_continuous=enable_chaining)` (usa o novo parâmetro do Commit 5, item acima).
- Statusbar durante o loop contínuo traduzido: alterna entre
  `"🌐 Traduzindo página X/N…"` (durante a chamada ao NLLB) e
  `"🔊 Narrando página X/N…"` (durante a reprodução) — reusar `self._reader.current_page`
  e `self._reader.total_pages` para X/N.
- Tratamento de erro no meio do loop: se a tradução de uma página falhar, mostrar o
  aviso na statusbar e **não** encadear a próxima (o loop morre naturalmente — ADR-005,
  graceful degradation, sem crash). Página sem texto: `find_next_readable_page` já
  pula (comportamento existente, sem mudança). Tradução que resulta em texto vazio:
  avisar e parar o encadeamento (mesmo padrão do Commit 4).
- **Sem mudanças** em `_continue_narration`, `find_next_readable_page`
  (`src/core/audio/continuous_navigation.py`) ou `AudioWorker` — o encadeamento
  reaproveita o mecanismo existente por completo; a única diferença é QUE texto é
  narrado (traduzido vs. original) no ponto de entrada do `_toggle_audio`.

**Testes:** com worker/`TranslationService` mockados — (a) com o modo traduzido
ativo, `_toggle_audio` roteia para o sinal `read_translated_page_chained` em vez de
`_launch_audio_worker` direto; (b) a flag `chain_continuous` se propaga
fim-a-fim (do dispatcher até `_launch_audio_worker`); (c) parar a narração
(`_stop_audio_if_running`) ou desligar o modo no meio do loop efetivamente encerra o
encadeamento (não continua narrando a próxima página).

---

## 7. O que NÃO tocar

- Caminho de seleção do EPUB/visualizador web (JavaScript) — fora de escopo.
- `docs/mobile-*.md` — pertencem a outra sessão/trabalho.
- Internals de `AudioWorker`, `_launch_audio_worker` (além do novo parâmetro opcional
  do Commit 5), `find_next_readable_page` — reaproveitar como estão.
- Refactors não relacionados em `main_window.py`/`reader_view.py` — CLAUDE.md §3
  ("não toque em código não relacionado, mesmo que pudesse ser melhorado").
- O arquivo `nul` na raiz do repositório (artefato do Windows) — nunca adicionar ao
  commit.

---

## 8. Verificação

1. **Por commit:** teste focado do commit → suíte completa
   (`venv\Scripts\python -m pytest tests/ -q`, SEMPRE via `venv\Scripts\python.exe`) →
   lint dos arquivos tocados
   (`venv\Scripts\python -m ruff check <arquivos>`) — só then commitar.
2. **Ao final dos 5 commits:** suíte completa mais uma vez (drift entre commits) e
   relatório final espelhando o Definition of Done do CLAUDE.md (arquivos alterados,
   testes rodados + resultado, ADRs consultados, riscos/limitações, o que NÃO foi
   coberto).
3. **Validação manual (app via `iniciar.bat`)** — não substituível por teste
   automatizado (exige QtWebEngine/GUI real):
   - Selecionar (arrastar) o último parágrafo de uma página que tem rodapé/número de
     página → "Traduzir" → o cartão deve mostrar a tradução **só** do parágrafo, sem
     repetição/degeneração.
   - "Traduzir Página" (Commit 4) → aviso "Página X inteira (N caracteres)" no
     header do cartão; texto traduzido coerente, sem loop de repetição.
   - Ativar "Leitura Contínua Traduzida" (Commit 5) → deve narrar em PT página a
     página com avanço automático até o fim do livro (ou até parar manualmente).
   - Parar a leitura contínua traduzida no meio → deve encerrar limpo (sem next-page
     fantasma).
   - Testar em página já em português (ambos os modos) → deve pular a tradução e
     avisar, narrando/mostrando o original.
4. **Riscos residuais conhecidos (aceitos, não bloqueiam a entrega):**
   - PDFs de duas colunas: ordenação de palavras ainda pode ficar imperfeita mesmo com
     `sort=True` — limitação documentada no Commit 1, não resolvida aqui.
   - Latência do NLLB por página no modo contínuo: o MVP é sequencial (traduz, depois
     narra, depois avança) — não há pré-tradução da próxima página em paralelo. Se a
     latência incomodar no uso real, é candidato a uma iteração futura (pipeline
     paralelo), fora deste contrato.

---

## 9. Registro de execução (a preencher pela sessão executora)

| Item | Status | Commit | Observações |
|---|---|---|---|
| WIP finalizado (seleção por fluxo + margem) | ⬜ | | |
| Branch `feature/reliable-translation` criada | ⬜ | | |
| Commit 1 — sort=True | ⬜ | | |
| Commit 2 — NLLB chunking | ⬜ | | |
| Commit 3 — cartão de tradução | ⬜ | | |
| Commit 4 — traduzir página inteira | ⬜ | | |
| Commit 5 — leitura contínua traduzida | ⬜ | | |
| Suíte completa final | ⬜ | | |
| Validação manual | ⬜ | | Requer o usuário — ver Seção 8.3 |
