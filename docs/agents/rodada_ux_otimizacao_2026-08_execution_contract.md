# Contrato de Execução — Rodada UX & Otimização de Leitura+IA (ago/2026)

**Objetivo:** rodada autônoma orquestrada focada em (a) polimento de UX, (b) otimização
das ferramentas de LEITURA (desempenho percebido: startup, abertura de livro, narração)
e (c) otimização das ferramentas de IA (latência percebida e qualidade). O escopo NÃO
se limita ao já registrado em `docs/revisao-produto-ux-2026-07-16.md`: a rodada inclui
**PESQUISA de novas possibilidades de melhoria** (Onda N — estado da arte atualizado),
que alimenta as ondas de execução. **Entrega final = versão de TESTE pronta para o
usuário final** (ZIP portátil validado + roteiro de teste atualizado), **sem nenhum
ponto em aberto**: toda pendência conhecida é resolvida internamente pelos agentes
nesta rodada. Modificações e ajustes posteriores ficam para a PRÓXIMA versão, a partir
do feedback do usuário. **NADA de mobile nesta rodada** (ver §IV).

**Planejado em 2026-08-10 (sessão de planejamento); execução em sessão própria.**

---

## I. Modelo de execução (obrigatório — herda o padrão do programa jul/2026)

- **Orquestrador (Fable 5)**: planeja cada onda, congela interfaces, despacha no máx.
  10 subagentes/onda (Opus 4.8 difícil, Sonnet 5 mecânico), sintetiza e VALIDA tudo.
- **Isolamento (NOVO — obrigatório):** a iniciativa mobile/API (`feat/api-m0`) mantém
  trabalho NÃO COMMITADO no clone principal (`main_window.py`, `settings_dialog.py`,
  `mcp_dialog.py`, `test_integrations_first_run.py` + docs). Esta rodada NÃO toca,
  NÃO stasheia e NÃO commita nada daquilo. Executar em **worktree dedicado**:
  `git worktree add ..\Biblioteca-rodada-ux main` e trabalhar SEMPRE lá, usando o
  interpretador do clone principal (`G:\PROGRAMAS PYTHON\Biblioteca-pessoal\venv\Scripts\python.exe`)
  a partir do diretório do worktree. Ao final da rodada: `git worktree remove`.
- **Por onda**: branch `feature/rodada-ux-<onda>` a partir da `main` → executores com
  whitelists estritas → validação do orquestrador (suíte completa + `ruff check src tests`
  + skill `validar-adrs` + revisão de diff) → PR → CI verde → **merge automático
  autorizado por este contrato** → próxima onda.
- **Gate de falha**: onda não verde após 2 tentativas → PARAR e reportar.
- **Regras invioláveis**: CLAUDE.md + ADRs 001/005/006; SEMPRE o python do venv;
  UI PT-BR; **NUNCA `think=False` no proativo/RAG/explicações** (decisão 2026-06-29);
  testes reais com o usuário SÓ após a entrega.
- **Rotação de sessão**: janela pesada → mesclar a onda corrente, marcar checkboxes,
  atualizar registro e continuar em sessão nova a partir deste contrato.
- **Skills do projeto**: usar `validar-adrs` no fechamento de cada onda e
  `relatorio-final` no encerramento da rodada.

## II. Ondas

### Onda R — Reconhecimento e FECHAMENTO DO ESCOPO (read-only, 2-3 agentes)
Produz a lista FECHADA de pendências — a promessa "zero em aberto" é auditada aqui,
contra o repo real, não contra memória. Inventariar:
- [x] **R.1** Checkboxes não marcados e débitos "segue como está" de TODOS os
  contratos em `docs/agents/*execution_contract*.md` e `*_plan_*.md` (programa
  jul/2026, ciclos B/C/D/E, packaging) + Onda 6 (novidades) nunca iniciada.
- [x] **R.2** Backlog do tester (memória `backlog-ajustes-ux`, itens ABERTOS):
  (10) texto cortado em notebook 13" (DPI × alturas px no QSS — hipótese confirmada
  por print; aba Narração some); (11) TTS degradou até pyttsx3 SEM AVISAR na UI;
  (12) Ollama crasha embeddings em driver antigo (CUDA/PTX) + modal indevido durante
  tarefa de background. Item (9) seleção multilinha ao vivo — verificar status real.
- [x] **R.3** Plano de otimização com baselines MEDIDOS (memória
  `perf-baselines-jul2026` e, se existir no clone principal,
  `docs/agents/plano_otimizacao_2026-07.md`): torch custa ~1,9s do startup por cadeia
  acidental de import; 40 miniaturas do sumário = ~88% do congelamento ao abrir PDF
  pesado; TTFB da narração (SLO 3s; caso real 4,79s sob carga).
- [x] **R.4** Reserva de TTS: Piper ausente na prática (caso real 2026-08-10 — sem
  fallback pt quando o Kokoro demora). Decidir mecanismo: pré-seed no pacote OU
  download guiado com aviso honesto.
- [x] **R.5** `TODO/FIXME` novos em `src/` + bugs registrados nas memórias
  (`bugs-conhecidos-rag` e afins) ainda sem fix.
- [x] **R.6** Saída: tabela item → destino (Onda P/Q/S/T) neste contrato. Item só
  pode ficar de fora se for FEATURE NOVA de escopo futuro (registrada no §IV como
  decisão de versão — não como pendência). Defeito ou pendência conhecida NUNCA
  fica de fora.

**R.6 — EXECUTADO (2026-08-24).** Tabela de destino (evidências, file:line e detalhes em
`docs/agents/rodada_ux_2026-08_registro.md`):

| item | destino |
|---|---|
| Torch no startup (cadeia única via `hardware_capability_service.py:11`) | P.1 |
| Miniaturas síncronas sem cache (`toc_widget.py:84-94`) + ADR-006 em `pdf_reader.py:99` | P.2 |
| Warmup Kokoro fora de idle real (`main_window.py:81-83`) + TTFB | P.3 |
| Proativo: frequência/continuidade | Q.1 |
| Orçamentos RAG por tier (§1.4; `orchestrator.py:922`) + defaults divergentes `agent_state` | Q.2 |
| Preload do modelo ao abrir leitor/chat + consolidação cliente Ollama + prompts A/B + "Simplificar" | Q.3 |
| Classificador CUDA/PTX (item 12b) + coexistência FAST_TASK + retry "database is locked" | Q.4 |
| Item 10a (aba Narração some — overflow QTabBar) e 10b (DPI: fixed→minimum + smoke scale) | S.1 |
| Item 11 (degradação TTS visível; pyttsx3 sai do topo do menu) | S.2 |
| Item 12a (zero modal de background: RAG, wizard Ollama, Anki) | S.3 |
| Reserva Piper: dirs configuráveis + catálogo 4 vozes pt-BR (pré-seed na Onda T) + gate qwen3_tts | S.4 |
| Popover EPUB, preset conforto, chips X-Ray, shimmer+timeline, degradação graciosa PDF/EPUB corrompido, contraste dos temas | S.5 |
| Build ZIP + seed_piper + smoke + docs stale (packaging:142, feedback §9) + roteiro do usuário | T |
| Item 9 (seleção multilinha): JÁ FECHADO na main (Sprint B2) — sem ação | — |

### Onda N — PESQUISA: atualização das possibilidades de melhoria (2-3 agentes, WebSearch)
Roda em paralelo à Onda R. A revisão de 2026-07-16 é o piso, não o teto — esta onda
atualiza o mapa de oportunidades com o estado da arte de AGORA. Somente desktop.
- [x] **N.1** Apps de leitura/biblioteca (Readwise Reader, KOReader, Calibre,
  Kindle/Apple Books, Zotero e novos entrantes): o que lançaram de relevante desde
  jul/2026 em UX de leitura, organização e estudo?
- [x] **N.2** Ferramentas de IA para leitura/estudo (NotebookLM, Ghostreader,
  ChatPDF/afins, recursos de estudo com SRS + IA): padrões novos que caibam num app
  100% local com a infra existente (RAG/grafo/dossiê/TTS/tradução).
- [x] **N.3** Stack local: novidades executáveis na classe de hardware do usuário
  (RTX 5060 Ti/16GB) — modelos Ollama melhores para as tarefas atuais, vozes/versões
  novas de TTS local (incl. pt-BR), OCR, embeddings — SEM trocar a arquitetura.
- [x] **N.4** Saída: tabela de candidatos com score (valor × esforço × aderência
  local-first × não-redundância com o que o app já tem), verificada contra o código.
  O orquestrador seleciona: itens P/M entram nas Ondas P/Q/S desta rodada; itens G
  vão para o §IV como candidatos da próxima versão (com justificativa). Máx. 8 buscas
  por agente; toda afirmação de mercado com fonte.

### Onda P — Otimização de LEITURA (desempenho percebido, com medição antes/depois)
- [x] **P.1** Startup: quebrar a cadeia acidental de import do torch (lazy import) —
  meta: janela visível sem o custo de ~1,9s; medir com o mesmo método do baseline.
  *(2107,8→508,7ms de import; janela 2706→1053ms; registro §Onda P)*
- [x] **P.2** Abertura de PDF pesado: miniaturas do sumário assíncronas/lazy com
  cache em disco — meta: eliminar o congelamento (~88% do custo medido).
  *(GUI thread 1376→12-39ms; reabertura ~0,1s; +ADR-006 no pdf_reader)*
- [x] **P.3** Narração: warmup do Kokoro em idle pós-startup (nunca competindo com
  OCR/indexação em prioridade); manter a espera cancelável do PR #68; medir TTFB.
  *(timer idle 1500ms pós _post_show_init, LowPriority; TTFB warm 86,6ms preservado)*
- [x] **P.4** O que mais as Ondas R/N classificarem como perf/UX de leitura.
  *(R/N não classificaram itens extras de perf de leitura além de P.1-P.3; harness de
  medição commitado em `tools/perf/`)*
- Critério: números antes/depois REGISTRADOS no registro da onda.

### Onda Q — Otimização de IA (latência percebida e qualidade)
- [x] **Q.1** Custo do proativo por página: usar a continuidade (Fases 5/6) para não
  reprocessar o já dito; revisar frequência por nível SEM tocar em `think` (inviolável).
  *(LLM 12→8 chamadas/sessão; SQLite 36→10; cadência em `_POLICY`; regressão do think)*
- [x] **Q.2** Latência percebida do RAG: revisar `max_rounds`/orçamentos por hardware
  (§1.4 da revisão de engenharia — item nunca executado) e prefetch/cache onde a
  Onda R apontar (ex.: dossiê pré-aquecido ao abrir o livro).
  *(TIER_BUDGETS A/B/C + trace agent_budget; re-warm do chat com debounce 5min; cache
  do dossiê já existia — validado)*
- [x] **Q.3** Qualidade dos prompts das ações de leitura (Explicar, Word Wise,
  Estudar): revisão A/B leve pelos agentes com critérios objetivos (fidelidade ao
  contexto, tamanho, citação de fonte).
  *(A/B REAL 22 pares no gemma4 local; Explicar ~2,8× mais curto sem truncar; Word Wise
  mantido; + ação nova "Simplificar")*
- [x] **Q.4** O que mais as Ondas R/N classificarem como IA (ex.: limiares do feedback 👎
  se ainda não aplicados; polimento do X-Ray).
  *(classificador CUDA/PTX tipado; retry de "database is locked" + add_chat_exchange
  atômico; coexistência FAST_TASK gated por disponibilidade; consolidação do cliente
  Ollama; limiares do 👎 já estavam aplicados — verificado; chips do X-Ray ficaram
  para a Onda S por serem GUI)*
- Critério: cada mudança de prompt/parâmetro com teste ou trace comparativo registrado.

### Onda S — UX final e robustez do tester
- [ ] **S.1** Item 10: layout quebrado em notebook 13"/DPI fracionário — remover
  alturas fixas em px do QSS onde quebram; garantir aba Narração visível; teste de
  fumaça com fonte/scale ampliados.
- [ ] **S.2** Item 11: degradação de TTS passa a ser VISÍVEL — aviso não-modal na UI
  quando a narração cair de Kokoro para reserva/legacy (nunca silencioso).
- [ ] **S.3** Item 12: driver NVIDIA antigo (erro CUDA/PTX no Ollama) → detectar e
  degradar com mensagem acionável; NENHUM diálogo modal disparado por tarefa de
  background (auditar todos os `QMessageBox` em caminhos de worker).
- [ ] **S.4** Reserva Piper conforme decisão da Onda R (pré-seed no pacote ou
  download guiado) — a cadeia de fallback do TTS deixa de ser teórica.
- [ ] **S.5** O que mais as Ondas R/N classificarem como UX.

### Onda T — RELEASE DE TESTE (fecha a rodada)
- [ ] **T.1** Verificação integral no worktree: suíte completa + ruff + `validar-adrs`
  + CI verde na main após o último merge.
- [ ] **T.2** ZIP portátil: `venv\Scripts\python.exe -m src.tools.build_package --out
  build\BibliotecaPessoal` com o pré-seed decidido (vozes/modelos que couberem) e
  smoke do pacote executado por agente conforme
  `docs/agents/roteiro_validacao_pacote.md` (tudo que não exigir interação humana).
- [ ] **T.3** README/docs atualizados se algo de usuário mudou; este contrato 100%
  marcado; memória persistente atualizada.
- [ ] **T.4** Relatório final (skill `relatorio-final`) + **Roteiro de teste do
  usuário** desta versão: o que mudou, onde olhar, como reportar (o feedback dele
  define a próxima versão).
- Critério de encerramento: ZIP gerado e smoke-testado; ZERO checkbox aberto neste
  contrato; "o que NÃO foi coberto" do relatório contém APENAS itens do §IV.

## III. Critérios de aceite da rodada
1. Todas as ondas mescladas na main com CI verde; gate de falha respeitado.
2. Nenhum débito novo do tipo "segue como está" sem estar no §IV.
3. Medições antes/depois para TODA otimização de desempenho.
4. Zero modal disparado por background; zero degradação silenciosa de TTS.
5. Pacote de teste entregue com roteiro — pronto para o usuário final.

## IV. Fora desta rodada (decisão de versão — NÃO são pendências)
- Novidades §4 da revisão de produto (Audio Overview local, STT/voz, Vocabulary
  Builder, Leitura aumentada, Study Guide): continuam gated para a versão pós-feedback.
- **Candidatos da Onda N remetidos à próxima versão** (scores, fontes e justificativa
  individual em `docs/agents/rodada_ux_2026-08_registro.md`, seção N.4): realce
  sincronizado com a narração; busca global de anotações; régua de leitura/modo foco;
  temas editáveis; flags de busca; stats por livro; paleta de comandos; seleção por
  teclado; controles de imagem em PDF escaneado; leitura lado a lado; "o que ler a
  seguir"; OPDS 2.0 (colide com a iniciativa api-m0); provedor OpenAI-compatible;
  SRS de destaques/revisão temática/quiz/cloze/FSRS/tabela comparativa; citação que
  rola ao trecho; UI de histórico do chat; persona por livro; upgrade RapidOCR 3.x
  (pede A/B com scans reais); troca de embeddings (reindex + armadilha de dimensão
  igual); NLLB→LLM na tradução (aguarda validação §8.3); Supertonic/kokoro-onnx;
  piper-tts 1.7; vision-OCR 2º passe; seletor de modelo na UI.
- Onda 6 (novidades) segue exigindo GO explícito do usuário; MCP M3 em rodada própria;
  "Outro…" via LLM, aprendizado de traces, conceitos do grafo no proativo, throttling
  de dispensas, assinatura digital/auto-update/lojas: mantidos fora (decisões antigas).
- Conversão em massa das 551 regras `font-size: px` do QSS: a rodada corrige o
  MECANISMO verificável (alturas fixas → mínimas, elide de abas, smoke com scale
  1.25/1.5); a conversão integral px→pt só com a máquina/print do tester validando
  (roteiro do usuário) — mexer às cegas em 551×3 regras arrisca regressão visual geral.
- **MOBILE: FORA POR COMPLETO.** A rodada não toca em NADA de mobile — nem código
  (`src/api/`, `feat/api-m0`), nem docs/planos de mobile, nem itens de pesquisa
  voltados a mobile (a Onda N descarta candidatos mobile sem registrá-los). A
  iniciativa mobile/API corre em ciclo próprio (worktree desta rodada garante o
  isolamento físico).
- Qualquer ajuste decorrente do feedback do usuário sobre esta versão de teste.

## V. Prompt de disparo (colar na sessão de execução)
> Execute a rodada conforme `docs/agents/rodada_ux_otimizacao_2026-08_execution_contract.md`:
> crie o worktree dedicado e rode as ondas R+N (em paralelo) → P → Q → S → T com merge
> automático autorizado. A Onda N atualiza por PESQUISA as possibilidades de melhoria
> (a revisão de 2026-07-16 é piso, não teto) e alimenta P/Q/S. Resolva TODAS as
> pendências internamente (gate: parar só em falha dupla), NÃO toque em nada de mobile,
> e entregue ao final o ZIP de teste + roteiro do usuário. Sem perguntas intermediárias;
> testes reais ficam com o usuário após a entrega.
