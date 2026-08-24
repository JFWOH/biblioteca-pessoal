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

## Onda P — (em execução)

## Onda Q — (pendente)

## Onda S — (pendente)

## Onda T — (pendente)
