# Registro de Execução — Rodada UX & Otimização de Leitura+IA (ago/2026)

Contrato: `docs/agents/rodada_ux_otimizacao_2026-08_execution_contract.md`.
Execução iniciada em 2026-08-24, worktree dedicado `..\Biblioteca-rodada-ux` a partir da
`main` `340c6a4` (PR #72). Baseline da suíte no worktree: **1583 testes coletados**.
Orquestrador: Fable 5; executores Opus/Sonnet; merge automático autorizado pelo contrato.

---

## Onda R — Reconhecimento e fechamento do escopo (CONCLUÍDA)

### R.1 Débitos documentais (agente R-1)

Nenhum contrato antigo em `docs/agents/` tem checkbox `- [ ]` aberto — as ondas 0-5 do
programa jul/2026 estão 100% `[x]`. O débito real vive em prosa e tabelas `⬜`:

| item | origem | evidência | destino |
|---|---|---|---|
| Orçamentos RAG estáticos (`max_rounds=5`, `max_time_ms=150000`) | `revisao-engenharia-2026-07-05.md:59-66` (§1.4) | `src/core/rag/orchestrator.py:922` hardcoded; `agent_state.py:5-8` com default divergente (20000) | **Q** |
| Roteamento de modelo por complexidade | `revisao-engenharia:45-58` | Parcial: existe `FAST_TASK_MODEL` (`hardware_capability_service.py:113`), mas sem coexistência de modelos (recarga ~8GB, `orchestrator.py:925`) | **Q** |
| Consolidação do cliente Ollama incompleta | `revisao-engenharia:119-130` | `orchestrator.py` e `proactive_worker.py` montam `api/chat` próprio; `rag_engine.py:444/465/517` payload à mão | **Q** |
| SelectionActionPopover ausente no EPUB (seleção longa) | `plano_melhorias...:161-163` | Débito autoconfessado em `src/gui/reader_view.py:1885` | **S** |
| God files pioraram (reader_view 3157 / main_window 1986 / orchestrator 1119 linhas) | `revisao-engenharia:156` | `wc -l` atual | **transversal** (higiene ao tocar; sem refactor gratuito) |
| Emoji-em-texto em botão/QActions | `plano_melhorias:63-64` | Débito ACEITO por decisão do usuário ("segue como está") | mantido aceito (sem ação) |
| Build real do ZIP nunca executado | `packaging_plan_2026-07.md:8-11` | Sem registro de build | **T** |
| Roteiro E5 máquina limpa: 17 checkboxes abertos | `roteiro_validacao_pacote.md:25-56` | Exige humano/máquina limpa | **T** (roteiro do usuário) |
| Validação manual MCP no host real | `mcp_server_execution_plan:24-27` | Exige o usuário | **T** (roteiro do usuário) |
| Validação manual Tradução Confiável §8.3 | `traducao_confiavel...:342-348,377` | Exige o usuário | **T** (roteiro do usuário) |
| Contradição doc: Kokoro embutido vs "decisão em aberto" | `packaging_plan:142` vs `:144-145` | Doc stale | **T** |
| Robustez com livros malformados (nunca coberto) | `revisao-engenharia:175-176` | Zero testes de arquivo corrompido | **S** (versão limitada: degradação graciosa ADR-005) |
| Acessibilidade nunca MEDIDA (contraste; temas Light/Sepia) | `revisao-produto-ux:205,208` | Sem medição | **S** (versão limitada: checagem automatizada de contraste) |
| Perf nunca medida na revisão | `revisao-produto-ux:206-207` | — | **P** (medição antes/depois) |
| Onda 6 (novidades §4) | `plano_melhorias:253-255` | Gated por GO explícito — nunca dado | **§IV** |
| MCP M3 (utilitários + SDK v2) | `mcp_server_execution_plan:22-23,83` | Rodada própria por decisão | **§IV** |
| "Outro…" interpretado por LLM; aprender de traces; conceitos do grafo no proativo; throttling de dispensas | contratos de aprendizado/proativo | Fora de escopo declarado | **§IV** |
| Assinatura digital, auto-update, macOS/Linux, MS Store | `packaging_plan:175-176` | Fora do ciclo | **§IV** |

Bookkeeping stale a corrigir na Onda T: tabela §9 de `aprendizado_feedback_rag_execution_contract.md:237-242`
(6 linhas `⬜`, mas código+testes existem).

### R.2 Backlog do tester + bugs de memória (agente R-2)

| item | status REAL na main | evidência | destino |
|---|---|---|---|
| 9 — seleção multilinha | **FECHADO** (Sprint B2) | `selection_flow_overlay.py:1`; `reader_view.py:598-606,918-970,2030-2058` | — |
| 10a — aba "Narração" some | ABERTO — causa ≠ hipótese da memória: **overflow horizontal do QTabBar** (6 abas × `padding 8px 20px` vs diálogo `setMinimumSize(550,450)`); sem elide/scroll buttons | `settings_dialog.py:33,55-61`; `styles.py:1065,2539,4010` | **S** |
| 10b — texto cortado 13"/DPI fracionário | ABERTO — mistura pt (fonte do app) × **551 `font-size: px`** no QSS + `setFixedHeight` em 5 pontos; sem política de rounding | `main.py:51`; `reader_view.py:229,430,665`; `settings_dialog.py:678,692`; `library_view.py:366` | **S** (mecanismo verificável; conversão em massa px→pt fica gated — ver §IV/roteiro) |
| 11 — TTS "degradou p/ pyttsx3 sem avisar" | PARCIAL — degradação automática p/ pyttsx3 NÃO existe (`tts_router.py:162,291,982,990`); pyttsx3 é o **1º item** do menu rápido (`reader_view.py:2997-3001`, grava preferência em 1 clique); aviso de fallback existe mas é passivo (tooltip/submenu: `reader_view.py:2902-2926,3021-3027`) | — | **S** |
| 12a — modal indevido em background | ABERTO — `_handle_rag_error` → `QMessageBox.critical` (`main_window.py:1735,1752-1755`); tb. `OllamaWizardDialog.exec()` automático do `RagInitWorker.ready` (`main_window.py:1152-1156`); Anki warning (`:1714`) | — | **S** |
| 12b — Ollama crasha embeddings (CUDA/PTX driver antigo) | ABERTO — retry só p/ erros de rede (`rag_engine.py:18-26,520-551`); erro CUDA/PTX vira RuntimeError genérico → modal 12a; zero detecção CUDA | — | **Q** |

Bugs de memória: `_cancelled` sem reset **FECHADO** (`rag_engine.py:842-854`); "streaming falso"
**FECHADO** (`orchestrator.py:937-966` + `ollama_client.py:112-136`); ADR-006 **limpo em
`src/core`**, mas **violação em `src/readers/pdf_reader.py:99-100`** (PyQt6 dentro de
`get_page`) → **P** (junto do trabalho de miniaturas); **"database is locked" SEM fix na main**
(`database.py:47-55`: `timeout=5.0`, sem `busy_timeout`, sem retry; `_write_lock` é
intra-processo e não alcança MCP) → **Q** (implementação independente — NÃO copiar da
branch api-m0). TODO real único: `qwen3_tts_provider.py:83` (modelo pesado sem gate de
config) → **S**.

Modais auditados (33): de risco em caminho de background só os 3 acima; padrão correto
(sem modal) já existe em metadata/OPDS/chat/watcher/auto-index.

### R.3 Baselines de performance e MÉTODO (agente R-3)

| métrica | baseline (jul/2026) | meta | método (reproduzir igual) |
|---|---|---|---|
| Import de `src.gui.main_window` | **2418ms**, 1362 módulos, torch carregado, RSS 513,4MB | ~500ms, ~521 módulos, sem torch, RSS ~67MB | `venv\Scripts\python.exe -c "import time,sys; t=time.perf_counter(); import src.gui.main_window; print(f'import={(time.perf_counter()-t)*1000:.0f} ms modulos={len(sys.modules)} torch={\"torch\" in sys.modules}')"` — 2-3 rodadas, mediana, 1ª descartada (I/O frio) |
| Abertura PDF pesado (248,3MB/777pág) | 1819ms = open 92,9 + **miniaturas 1600,7 (88%)** + pág.1 114,9 | eliminar congelamento das miniaturas da thread de GUI | script offscreen no scratchpad cronometrando `PDFReader.open()` / `load_toc` / render por fase, **ordem A/B alternada** (cache do MuPDF infla ~70% sem isso) + pré-aquecimento |
| TTFB narração | SLO=3,0s (`tts_router.py:66`); medições isoladas: 1,69s CPU / 148,64ms GPU (`reports/phase_13b2/13b3`) | warmup em idle real; TTFB medido antes/depois | `tools/validate_kokoro_gpu.py` (existe) + medição no nível do router. Obs.: número "4,79s sob carga" vem da memória `perf-baselines-jul2026`, não reproduzível de doc do repo |

Cadeia única do torch no startup (confirmada): `main.py:78` → `main_window.py:21` →
`reader_view.py:38` → `proactive_reader_service.py:11` → **`hardware_capability_service.py:11`
`import torch` em nível de módulo**. Nenhum outro import pesado no topo de `src/gui/**`.
Miniaturas: `toc_widget.py:10` `_THUMB_MAX=40`, loop síncrono `:84-94`, disparado por
`reader_view.py:1004` na GUI thread, `pdf_reader.render_thumbnail:203-214`, **sem cache algum**.
Warmup Kokoro: existe (`kokoro_provider.py:243-301`), mas `TTSInitWorker` dispara em
`main_window.py:81-83` via `singleShot(0)` — mesmo tick do `show()`, **não é idle real**.
Espera cancelável do PR #68: presente (`tts_router.py:31-32,399-411`).

### R.4 Decisão da reserva Piper: **PRÉ-SEED no pacote, precedido de refactor**

`PiperProvider` só procura vozes em `~/.local/share/piper-tts/models` e `~/piper-models`
(`piper_provider.py:277-281`) — fora da pasta do pacote portátil. Decisão:
1. **Onda S**: `PiperProvider` passa a aceitar diretório de modelos configurável + diretório
   relativo ao pacote/app (portable-safe), mantendo os atuais como fallback; catálogo ganha
   as 4 vozes pt-BR oficiais (`cadu/jeff/faber-medium`, `edresson-low` — rhasspy/piper-voices, MIT).
2. **Onda T**: `build_package.py` ganha estágio `seed_piper` (voz `pt_BR-faber-medium`,
   ~63MB), com o mesmo padrão do `seed_kokoro` (avisa e segue se não conseguir baixar).
Racional: o caso real de 2026-08-10 é exatamente "Kokoro lento SEM reserva instalada" —
download guiado deixaria a 1ª sessão (a pior janela) sem reserva.

### R.6 Tabela final item → onda

**Onda P:** P.1 torch lazy (cadeia acima); P.2 miniaturas assíncronas + cache em disco +
correção ADR-006 do `pdf_reader` (mesma área); P.3 warmup Kokoro em idle real + TTFB.
**Onda Q:** Q.1 proativo (frequência/continuidade, custo por página); Q.2 orçamentos RAG por
tier (§1.4) + divergência `agent_state`; Q.3 preload do modelo ao abrir leitor/chat +
consolidação do cliente Ollama + A/B leve de prompts (Explicar/Word Wise/Estudar) + ação
"Simplificar"; Q.4 classificador CUDA/PTX com mensagem acionável + coexistência
FAST_TASK_MODEL (qwen3.5:4b com fallback gracioso) + retry/backoff independente do
"database is locked".
**Onda S:** S.1 abas das configurações (10a) + mecanismo DPI (10b: fixed→minimum heights,
smoke com scale 1.25/1.5); S.2 degradação de TTS visível + reordenar menu (11); S.3 zero
modal de background (12a: RAG, wizard Ollama fora do 1º uso, Anki); S.4 Piper dirs/catálogo
(decisão R.4) + gate do qwen3_tts; S.5 popover EPUB, preset conforto/dislexia, chips de
perguntas do X-Ray, shimmer + timeline nos cards de IA, testes de degradação graciosa p/
PDF/EPUB corrompidos, checagem automatizada de contraste dos 3 temas.
**Onda T:** build ZIP + `seed_piper`, smoke automatizável do roteiro, docs (contradição
packaging, §9 stale), contrato 100%, relatório final, roteiro do usuário, memória.

---

## Onda N — Pesquisa e seleção (CONCLUÍDA)

3 agentes (apps de leitura; IA de leitura/estudo; stack local), ≤8 buscas cada, fontes em
tudo; candidatos mobile descartados silenciosamente. Piso (revisão 2026-07-16) superado.

### N.4 — Selecionados para ESTA rodada (P/M, polimento)

| candidato | onda | fonte |
|---|---|---|
| Preload/warm-up do modelo Ollama ao abrir leitor/chat (cold start some; `keep_alive` já existe, falta preload) | Q | adhdecode.com/articles/ollama/ollama-keep-alive-preload-model-config |
| Coexistência chat+FAST_TASK (qwen3.5:4b 3,4GB ao lado do modelo de chat — mata recarga ~8GB `orchestrator.py:925`), com fallback gracioso se ausente | Q | ollama.com/library/qwen3.5 |
| Ação "Simplificar este trecho" no menu de seleção (padrão Ghostreader) | Q | speedreadinglounge.com/readwise-reader-review |
| Chips de 3-5 perguntas sugeridas por página derivadas do X-Ray (custo LLM zero) | S | toolsdepth.com/reviews/chatpdf-review-2026 |
| Skeleton shimmer no gap pré-primeiro-token (−40% latência percebida) | S | metacto.com/blogs/ai-chat-ux-patterns-production |
| Timeline colapsável dos passos do agente no card (status já emitido por `_ThinkingStatusTracker`) | S | thefrontkit.com/blogs/what-is-streaming-ui-in-ai-applications |
| Preset "modo conforto/dislexia" em 1 clique no popover de tipografia | S | about.ebooks.com/one-click-dyslexia-mode-for-ebooks |
| 4 vozes pt-BR oficiais do Piper no catálogo (hoje só `faber`) | S | huggingface.co/rhasspy/piper-voices |

### N.4 — Remetidos ao §IV (próxima versão), com justificativa

| candidato | score (valor/esforço/aderência) | justificativa |
|---|---|---|
| Realce sincronizado narração + "anotar sentença ouvida" | A/M-G/A | esforço G no leitor; feature, não polimento |
| Busca global de anotações (texto/tag/cor entre livros) | A/M/A | feature nova de 1ª classe; pede design de UI |
| Régua de leitura / modo foco | A/P-M/A | feature de modo de leitura; pós-feedback |
| Temas de leitor editáveis; flags de busca (regex/acentos); stats por livro; paleta de comandos; seleção por teclado; controles de imagem PDF; lado a lado; "o que ler a seguir" | M/M/A | features novas (polimento não cobre); catálogo mantido com fontes no relatório N-1 |
| OPDS 2.0 (JSON) | B-M/P/A | **colisão direta com a iniciativa api-m0** (OPDS virou router lá); mexer agora cria conflito |
| Provedor LLM OpenAI-compatible (LM Studio etc.) | M/M/A | amplia superfície de suporte; decisão de produto |
| Revisão Diária SRS de destaques; revisão temática por embedding; quiz conversacional; cloze; tabela comparativa de livros; FSRS | A-M/M/A | features de estudo novas (Onda-6-like); FSRS ainda migra dados agendados |
| Citação que rola até o trecho exato; histórico de chat com UI | M/M/A | polimento maior que a janela da rodada; dados já persistem |
| "Meta/persona por livro" no prompt | A/P/A | risco de enfraquecer grounding do system prompt fixo — pede decisão de produto + A/B |
| Upgrade RapidOCR 1.4.4→3.9.x (PP-OCRv6) | A/M/A | qualidade de OCR não é mensurável offline nesta rodada; pede A/B com scans reais do usuário |
| Troca de embeddings (`qwen3-embedding:0.6b`) | M/G/M | exige reindex total; **armadilha: 1024d igual ao bge-m3 → `needs_reindex()` não detecta**; MTEB-PT mostra que ranking multilíngue não prediz pt — medir no acervo |
| NLLB→LLM direto na tradução; NLLB 1.3B | A/M/A | fluxo Tradução Confiável ainda aguarda validação manual do usuário (§8.3) — não trocar motor antes disso |
| Supertonic como provider TTS extra; kokoro-onnx runtime | M/M-G/M | experimento + licença openrail a validar; G |
| piper-tts 1.4.2→1.7.0 | B/P/A | higiene sem ganho pt-BR; não arriscar narração estável na véspera do release |
| Vision-OCR 2º passe (gemma4/qwen3.5) | M/M/A | feature nova de ingestão |
| qwen3.5:9b selecionável na UI | M/P/A | não existe UI de seleção de modelo; criar UI é feature |

Fatos de stack relevantes (N-3): default RAG `gemma4:e4b` (`rag_engine.py:44`), Tier A já sobe
p/ `gemma4:12b` (`hardware_capability_service.py:102`); Kokoro parado em 0.9.4/abr-2025 (sem
upgrade possível — decisão: manter); catálogo Piper do app lista só `faber` (`piper_provider.py:143`).

---

## Onda P — Otimização de leitura (CONCLUÍDA)

Harness de medição COMMITADO em `tools/perf/` (lição de julho: scripts no scratchpad se
perderam). PDF de referência sintético (117,1MB/780pág/80 TOC) regenerável com
`measure_pdf_open.py gen`; números absolutos NÃO são comparáveis ao livro real de julho —
a forma bate (miniaturas = 88% do custo frio, idêntico), o A/B da onda usa sempre o sintético.

### Números antes → depois (mesma máquina, mesmos scripts)

| métrica | ANTES | DEPOIS | Δ |
|---|---|---|---|
| `import src.gui.main_window` | 2107,8ms / 1367 módulos / torch=True / RSS 513,8MB | **508,7ms / 526 módulos / torch=False / RSS 66,6MB** | −76% (meta de julho: ~500ms — atingida) |
| Janela (offscreen, `measure_time_to_window`) | 2706,0ms (import 1972,7) | **1053–1099ms** (import ~424–435) | −59–61% |
| Sumário na thread da GUI (PDF pesado, frio) | 1376,1ms (90,7% do total; NUNCA melhorava com cache: quente 1283,7ms) | **12,6–38,5ms** (placeholder + worker async) | ~35–110× |
| Congelamento total da abertura (thread GUI) | ~1517,6ms | **~109–179ms** | −88% |
| Reabertura do mesmo livro (cache disco) | igual à 1ª (sem cache) | **90,8–112,4ms** (40/40 do cache) | 14–16× vs async sem cache |
| 40 miniaturas prontas (total, async, cache vazio) | 1376ms (bloqueando) | 1490–1645ms (em background, LowPriority) | custo movido p/ fora da GUI |
| TTFB Kokoro warm | 92,13ms | **86,57ms** | preservado (Δ dentro do ruído) |
| TTFB 1ª síntese pós-warmup | 114,19ms | 126,08ms | preservado |

### O que mudou

- **P.1 (torch lazy):** `hardware_capability_service.py` — `import torch` de módulo virou
  `get_torch()` tardio com cache e sentinela; `HAS_TORCH` REMOVIDO (único consumidor eram
  testes; scripts externos que o importem quebram — intencional). ADR-005 preservado
  (torch ausente/DLL quebrada = degradação, não erro). Guard-tests em subprocess
  (`tests/test_startup_deferred.py::TestTorchForaDoStartup`, marcados `slow`) garantem que
  torch não volta à cadeia `main_window`. Custo do torch agora é pago no 1º uso real
  (ex.: 1º `process_page_context` do proativo) — movido, não eliminado (é o objetivo).
- **P.2 (miniaturas + ADR-006):** novos `src/core/thumbnail_cache.py` (disco, chave
  caminho|tamanho|mtime_ns|página|largura, escrita atômica, poda por teto de 2000) e
  `src/gui/workers/thumbnail_worker.py` (QThread, cancelamento cooperativo, abre o próprio
  leitor via `reader_factory.create_reader` — fitz não é thread-safe). `toc_widget.load_toc`
  não renderiza mais nada (placeholder transparente reserva layout; `set_thumbnail` trata
  entrega atrasada/itens destruídos). `reader_view` liga tudo com guard por `sender()` e
  teardown na política do PR #32 (wait limitado, abandono sem deleteLater). **ADR-006:**
  `pdf_reader.get_page` perdeu o import de PyQt6 (página dupla composta em fitz puro,
  resultado idêntico); bônus: `src/mcp/server.py` deixa de puxar PyQt6 via `get_page`.
  Teste AST `TestFronteiraADR006` varre `src/readers/**` inteiro (pega import em função).
- **P.3 (warmup em idle real):** `TTS_WARMUP_IDLE_DELAY_MS=1500`; timer single-shot filho
  da janela, ARMADO no fim de `_post_show_init` (precedente: `singleShot(3000)` do warmup
  de LLM na mesma função); start do worker em `QThread.Priority.LowPriority`; `closeEvent`
  para o timer antes do wait. Espera cancelável do PR #68 intocada.

### Validação da onda

- Suíte completa no worktree: **1622 passed, 2 failed** — as 2 falhas
  (`test_build_package.py::TestManualPdf::test_pdf_tem_fontes_e_texto_de_verdade`,
  `test_drag_drop_import.py::test_drop_overlay_cover_shows_and_hide`) são PRÉ-EXISTENTES e
  ambientais deste Windows offscreen: reproduzidas byte a byte na main limpa `51f3c7e` em
  worktree de verificação (fontes ausentes p/ o PDF do manual; plugin offscreen sem
  `propagateSizeHints`). O CI (Ubuntu) as passa. Endurecimento (skip com razão) vai na Onda S.
- Ruff: limpo em todos os arquivos tocados. ADR-006 (grep PyQt6 em src/core, src/data,
  src/mcp, src/api, src/readers, src/utils): zero imports.
- Riscos aceitos e registrados: janela de ~1,5s pós-startup com `_providers` vazio se o
  usuário pedir narração instantaneamente (na prática inalcançável; o router responde com
  erro explícito, não silêncio); poda do cache de miniaturas só roda ao fim de cada lote;
  validação com o app REAL (não offscreen) fica no roteiro do usuário.

### Infra consertada durante a onda

CI da main estava VERMELHO desde antes da rodada (3 runs): `requirements.txt` tinha
`ruff>=0.1.0` e o CI instalava ruff mais novo que o do lock (869 apontamentos de regras
novas em código que o 0.15.17 aprova). Fix: pino `ruff==0.15.17` (PR #73). Local e CI
voltam a julgar com a mesma régua.

## Onda Q — Otimização de IA (CONCLUÍDA)

### Q.1/Q.2 — proativo e orçamentos (evidência por trace/teste, sem Ollama vivo)

- **Proativo**: memoização dos blocos de prompt (invalidada só por observação nova),
  memo de sessão por `(book_id, página, hash)`, dedup de observações equivalentes na
  memória do prompt, teto de 6000 chars p/ página patológica. Trace de sessão medido
  (30 eventos, nível Moderado): chamadas LLM **12→8**, consultas SQLite **36→10**,
  varreduras de 200 linhas da Fase 6 **12→1**. Cadência documentada em `_POLICY`
  (`proactive_trigger_engine.py`): Leve 5→8 de gap (−37% chamada/página), Moderado 2→3
  (−33%), Estudo intacto (contrato do nível). Regressão nova protege o `think`
  inviolável (`test_payload_never_disables_thinking`).
- **Orçamentos por tier (§1.4)**: `agent_state.TIER_BUDGETS` — A `(6, 90s)`,
  B `(5, 150s)` (comportamento atual preservado como referência), C `(3, 300s)`;
  desconhecido→B (ADR-005). Divergência de defaults do `AgentState` (20s vs 150s)
  eliminada. Tier cacheado em módulo; import tardio (guard do torch da Onda P verde).
  Trace novo `agent_budget` por query — a próxima calibração sai de dado, não palpite.

### Q.3 — prompts das ações de leitura (A/B REAL: 22 pares, gemma4:e4b local, 275s)

| ação | veredito | evidência |
|---|---|---|
| Explicar página | mudado | A: 723/732/957 palavras (EN truncou no teto de tokens); B: 267/252/287 (~2,8× menor, sem truncar) |
| Resumir | teto explícito | efeito neutro medido; seguro p/ outros modelos |
| Glossário | teto explícito | A gerou 9 itens sem teto; B parou em 8 |
| Flashcards | só regra de idioma | formato P:/R: intacto |
| Word Wise | MANTIDO | já cumpria ancoragem/tamanho/idioma |
| Explicar (seleção, inline no main_window) | mudado na integração | pedia "detalhadamente" sem teto; agora ancorado + máx. 200 palavras (flui pelo system prompt do RAG, que já impõe grounding/citação) |

Achado honesto: a regra de idioma é PREVENTIVA (gemma4 já respondia pt em 100% dos
pares, até no trecho EN); o teto de 200 palavras melhora 2,8× mas não é obedecido ao
pé da letra (267-287) — endurecer exigiria `num_predict` no chamador.

- **"Simplificar" (novo, padrão Ghostreader)**: template ancorado/curto/leigo em
  `study_prompts.py`; menu de contexto + barra flutuante (`SelectionActionPopover`);
  exclusão mútua com Word Wise (termo curto → Definição; trecho → Simplificar) — juntas
  a barra teria 1176px e cortaria em notebook 13". Manual do usuário atualizado.

### Q.4 — robustez e stack de IA

- **Preload/re-warm do chat** (candidato N.4): re-warm não-bloqueante com debounce de
  5min ao abrir/focar o painel de chat (`showEvent` + FocusIn no campo), via
  `spawn_warmup` (nunca reinicia QThread vivo). Cobre o modelo descarregado pelo
  keep_alive após horas de app aberto.
- **Coexistência FAST_TASK** (candidato N.4): `qwen3.5:4b` (3,4GB) preferido para
  tarefas rápidas QUANDO instalado (sonda `/api/tags` com cache de classe TTL 10min,
  tag EXATO — base não vale). Gate da integração: `resolve_llm_model(fast_task=False)`
  por default — fluxos de QUALIDADE (revisão de tradução, síntese de dossiê) NUNCA
  trocam de modelo silenciosamente; os rápidos chegam via `get_model_for_task("fast")`.
  **Hoje inerte**: `qwen3.5:4b` não está instalado (18 modelos detectados no daemon
  real; e4b=9,61GB + 12b=7,56GB confirmam que o par atual NÃO cabe em 16GB →
  pré-requisito do usuário no roteiro: `ollama pull qwen3.5:4b`).
- **Classificador CUDA/PTX (item 12b)**: `OllamaGPUError(RuntimeError)` tipado, com
  marcadores case-insensitive checados ANTES do classificador transitório — falha na
  1ª tentativa (sem tempestade de retry) com mensagem PT-BR acionável (driver antigo →
  atualizar ou `OLLAMA_NUM_GPU=0`). Aplicado nos 3 pontos de HTTPError dos embeddings.
  A Onda S reconhece o TIPO (sem casar string) para a UI sem modal.
- **"database is locked" — RESOLVIDO na main (implementação independente)**:
  `busy_timeout` 15s aplicado ANTES do WAL + retry com backoff (4 tentativas,
  50→100→200ms, rollback pré-repetição, guarda anti-acúmulo — nunca 4×15s) nos 9
  métodos de escrita expostos a outros processos; `add_chat_exchange` transacional
  (2 inserts + poda num commit) ligado no `rag_engine.append_chat_turn` — o trio que o
  MCP disputava virou UMA janela de contenção. 14 testes novos de contenção real.
- **Consolidação do cliente Ollama**: embeddings (`/api/embed` + legado) e
  `_reformulate_query` migrados para `ollama_client`; proactive_worker delega ao
  `build_chat_payload` público. `keep_alive` agora presente no último call site que o
  descartava. Payloads comportamentalmente idênticos (testes de contrato).

### Validação da onda

Suíte completa no tree integrado: ver seção de validação final (1707+ verdes, mesmas 2
falhas ambientais pré-existentes). Ruff limpo. ADR-006 limpo. Integração do orquestrador
(6 ajustes): par atômico DB↔rag_engine, gate fast_task, pergunta do Explicar-seleção,
manual, testes do gate e da transação — 158 testes focados verdes.

### Não coberto (Onda Q)

Média móvel de latência por rodada dos traces (§1.4 "melhor"): o trace `agent_budget`
foi criado exatamente para isso — fica para calibração pós-feedback com dado real.
Classificação CUDA no caminho de chat/geração (o tester bateu em embeddings; chat fica
observado). `main_window._start_llm_warmup` segue com disparo próprio (não migrado ao
`spawn_warmup` — arquivo fora do escopo do executor; funcionalmente equivalente).

## Onda S — UX final e robustez do tester (CONCLUÍDA)

Onda atravessou uma QUEDA DE SESSÃO (limite de uso, 24/08 ~23h): 6 executores morreram
em pleno voo com edições parciais em disco; todos foram RETOMADOS com contexto intacto
(SendMessage) e concluíram; 2 tarefas (S-7 robustez, S-8 contraste) foram bloqueadas 2×
pelo classificador de permissões no LANÇAMENTO do agente e executadas INLINE pelo
orquestrador (as edições em si passam pelas permissões normais).

### S.1 — item 10 (notebook 13"/DPI) — causas REAIS corrigidas

- 10a (aba Narração some): causa-raiz ≠ hipótese da memória — `elideMode` era
  `ElideNone` (scroll buttons JÁ eram True): sem elide o QTabBar não encolhe e tira a
  aba corrente da vista. Fix: ElideRight + padding 8px 20px→12px (3 temas) + diálogo
  550→640px. Medido: abas somavam 1084px vs 510px úteis → agora 600 vs 600.
- 10b (texto cortado): o smoke de DPI flagrou **19 widgets cortados** (checkbox com 2px
  de altura!) — conteúdo não cabia em 450px e o layout espremia abaixo do mínimo. Fix:
  5 abas embrulhadas em QScrollArea (padrão da aba Avançado) → **0 cortados**; caixas
  MCP com altura por font-metrics (não px); `setFixedHeight`→`setMinimumHeight` em
  settings/library/reader (toolbar 48, audio_btn 32, progress 28 viram PISO).
- `tests/test_dpi_smoke.py` (18 testes, subprocessos): descoberta metodológica —
  `QT_SCALE_FACTOR` é INERTE no offscreen (só muda devicePixelRatio); o teste varia a
  fonte do app em PONTOS, que é o mecanismo real do bug (pt × 551 font-size px do QSS).
- Não coberto (só o tester confirma): DPI fracionário REAL no 13"; conversão em massa
  px→pt segue gated (§IV).

### S.2 — item 11 (degradação de TTS VISÍVEL)

Menu rápido reordenado Kokoro→Piper→pyttsx3 (legado por último, rotulado "qualidade
inferior" — a causa auditada era clique acidental no 1º item). Fallback agora: aviso
na statusbar (8s, dedup por motor) + indicador persistente `⚠️` no botão de áudio
(propriedade `ttsFallback` estilizável), limpo ao voltar ao preferido. NUNCA modal.
Gate novo `tts.qwen3.enabled` (default False): provider pesado recusa construção ANTES
do import torch/transformers. Ressalva honesta: se o relato do tester tiver outra
causa além do clique acidental, ela continua aberta (roteador nunca degradou sozinho).

### S.3 — item 12a (ZERO modal de background)

`_handle_rag_error` sem `QMessageBox.critical` (statusbar + painel; sinal é `str`,
então o erro de GPU é reconhecido por tipo E conteúdo — `gpu_failure_message()`);
wizard do Ollama: 1º uso mantém modal (roteiro §3 intacto; chave
`onboarding.ollama_wizard_shown` gravada AO EXIBIR), demais viram botão flat
"Configurar IA…" na statusbar; Anki → statusbar. Varredura AST+regex com teste de
invariante; exceção auditada e MANTIDA: diálogo do flashcard após worker é continuação
de clique explícito. 21 testes novos.

### S.4 — reserva Piper REAL (decisão R.4)

`_model_dirs()` agora: config `tts.piper.models_dir` > `<app>/data/piper/models`
(portátil, convenção do Kokoro) > 2 dirs legados do home; dedup preservando ordem.
Catálogo: 4 vozes pt-BR oficiais + pt-PT (faber continua a resolução default de pt).
**Handoff Onda T:** `seed_piper` deve copiar `pt_BR-faber-medium.onnx` **E**
`.onnx.json` para `data/piper/models/` (o `.json` é obrigatório; `.onnx` órfão deixa
health_check True mas síntese falha). 14 testes novos.

### S.5 — preset "Leitura confortável" (candidato N.4)

1 clique: fonte +2 (16px), entrelinha 1,8, margem 100px (proxy de coluna estreita —
único controle que afeta a largura); 2º clique restaura snapshot real. Popover não tem
controle de espaçamento de letra (cláusula "se houver" não aplicável).

### S.5 — chips, shimmer e timeline (candidatos N.4)

Chips de 3-4 perguntas derivadas dos conceitos do grafo/X-Ray (custo LLM ZERO; mesma
fonte `_book_graph_concepts`; refresh só na troca de livro; fiação no main_window feita
pelo orquestrador). Shimmer de 3 linhas no gap pré-primeiro-token (cor da paleta do
card — nada hardcoded; para quando oculto). Timeline colapsável "▸ N passos" acumulando
os status já emitidos pelo orchestrator (dedup, teto 12, colapsa ao concluir).

### S.5 — barra de ações no EPUB (débito autoconfessado pago)

Seleção longa no EPUB abre o MESMO `SelectionActionPopover` do PDF (6 ações, incluindo
a nova Simplificar; termo curto segue para Definição rápida). Âncora: rect do bridge
com fallback no cursor global. Dismiss em render/troca de página/nova seleção.
Decisão registrada: **"Destacar" fora da barra do EPUB** — highlight sem coordenadas
normalizadas nunca re-renderizaria no caminho HTML; paridade plena exige mecanismo de
re-render de destaque no EPUB (candidato futuro, §IV). 17 testes novos.

### S.5 — robustez com arquivos danificados (versão limitada do débito de fuzzing)

Contrato novo `BookOpenError` (ADR-005): `open()` dos readers nunca vaza exceção crua —
PDF/EPUB truncado, conteúdo falso, 0 bytes → erro claro PT-BR; MuPDF que REPARA PDF
truncado é aceito como degradação válida. GUI: abrir livro danificado → aviso na
statusbar, nunca traceback (wrap no main_window). 8 testes novos. Os 2 testes que
falhavam SÓ neste Windows offscreen ganharam SONDAS comportamentais estreitas (skip com
razão: fontes não embutíveis em PDF trivial; minimumSizeHint do overlay maior que o
retângulo do teste) — CI Linux continua cobrindo ambos.

### S.5 — contraste MEDIDO pela primeira vez (débito da revisão §7)

`tools/contrast_qss.py` (WCAG, parser de QSS com strip de comentários regressionado;
nome evita o padrão `check_*.py` do .gitignore, que é para scripts descartáveis)
+ 10 testes. Resultado: dark 22 pares/0 FAIL; light e sépia 23 pares — **1 FAIL cada**
(`QPushButton#ragIndexBtn` #10b981 sobre claro: 2,54:1 e 2,15:1) → CORRIGIDO para
#047857 (tom -700 da mesma paleta): **0 FAIL nos 3 temas**, par agora AA. Limite: só
pares fg/bg declarados na MESMA regra (14-15 não-hex ignorados/tema); auditoria visual
completa segue com o usuário.

### Validação da onda

Suíte completa (rodada 3× por executores diferentes ao longo da onda): **1850 passed,
2 skipped** (as 2 sondas ambientais — antes eram 2 FAILED). Ruff limpo em todos os
tocados. Zero modal de background + zero degradação silenciosa de TTS (critérios de
aceite 4) com testes de invariante.

## Onda T — (pendente)
