# Proposta de Entrega — MVP Mobile "Biblioteca Pessoal"

> Proposta em nível de aspectos gerais para **análise de entrega**. Consolida três frentes de
> pesquisa paralela (rota técnica/backend, qualidade de software, UX + Claude Design) e uma
> autoavaliação cruzada. Não altera código. Base: [docs/mobile-port-analysis.md](mobile-port-analysis.md).
> Data: 2026-07-01.

## 0. Premissas travadas (decididas com o cliente)

- Arquitetura **cliente-servidor**. Núcleo de IA permanece no PC/servidor doméstico.
- **Android-first**; iOS depois (mesmo código Flutter, sem mudar lógica).
- **Tablet e celular em pé de igualdade** — layout adaptativo por breakpoint, não por tipo de aparelho.
- **MVP depende do servidor acessível.** Offline-on-device é fase posterior (M4).
- Cliente em **Flutter**; backend **FastAPI headless** reaproveitando `src/core/**`.

---

## 1. Visão geral da proposta

Transformar o app desktop num **par**: um **backend headless** (extraído do `core` atual, sem tocar na
GUI PyQt6) e um **cliente Flutter** para tablet/celular. O celular lê e anota **no aparelho**; RAG,
tradução, TTS e busca semântica vêm do **servidor** por HTTP/streaming. Degradação graciosa quando o
servidor não está acessível (alinha ADR-005): leitura, busca por palavra-chave, anotações e flashcards
continuam funcionando; recursos de IA ficam marcados como "precisa do servidor".

**O que se reaproveita:** ~8,5k LOC do `core` (via API) + o servidor OPDS já existente.
**O que se refaz:** a UI (os 10,8k LOC de PyQt6 **não** migram — redesenho para toque).

---

## 2. Arquitetura-alvo (MVP)

```
PC/Servidor (Windows/Linux) ── src/api/main.py (FastAPI headless, novo, thin) ──┐
  monta:  APIRouter(OPDS já existente) + routers novos                          │
  serve:  /health /library /read /search /rag(SSE) /translate /tts(chunked)     │
          /proactive(WebSocket) /feedback                                       │
  usa:    LibraryManager · RAGEngine · orchestrator · TTSRouter · NLLB · OCR    │
          SQLite/FTS5 · ChromaDB(bge-m3) · Ollama(gemma4)                       │
                         ▲ HTTP + SSE + WS  (LAN / Tailscale)                   │
Flutter (Android→iOS) ───┘                                                      
  on-device:  leitor PDF/EPUB · biblioteca(drift/SQLite) · progresso/anotações · flashcards
  via server: RAG · tradução · TTS(stream) · busca semântica · proativo(push)
```

### Decisões técnicas fechadas na autoavaliação
- **Streaming:** **SSE** para RAG chat (HTTP puro, reconecta, passa em Tailscale) e **HTTP chunked** para
  áudio TTS (consumido direto pelo `just_audio`). **WebSocket só** para o canal proativo (push iniciado
  pelo servidor). Feedback 👍/👎 volta por REST simples.
- **Auth:** **bearer token estático** (config/env), via `Depends(verify_token)` em todas as rotas exceto
  `/health`. Sem OAuth/JWT — é servidor doméstico mono-usuário.
- **Conectividade:** **Tailscale** (sem abrir portas, mesmo endereço em LAN e remoto). mDNS
  (`multicast_dns`) para auto-descoberta em LAN é *nice-to-have*, não bloqueia MVP.
- **Concorrência de IA (MVP):** **serializar** requisições de IA (fila + lock + estado "ocupado") porque o
  cancelamento hoje é flag global mutável. Estado por-sessão fica para pós-MVP.

---

## 3. Stack do cliente Flutter (validada 2026)

| Papel | Escolha | Observação |
|---|---|---|
| Estado | **Riverpod** (v3.x) | async-first, casa com telas server-heavy |
| PDF | **pdfrx** (PDFium) | maduro, multiplataforma; preferir a `flutter_pdfview` |
| EPUB | **epub_pro** / avaliar **cosmos_epub** | ⚠️ ecossistema imaturo — **spike na semana 1** antes de comprometer |
| Cache/sync local | **drift** (SQLite reativo) | espelha o design SQLite-first do servidor |
| Áudio | **just_audio** | toca stream de TTS do servidor direto por URL |
| Notificações/BG | flutter_local_notifications + foreground service | WS proativo persistente exige foreground service no Android |
| ONNX on-device | onnxruntime (plugin) | ⚠️ stale — só reavaliar na fase offline (M4) |

---

## 4. UX — princípios e escopo

- **Layout adaptativo por largura** (não por "isTablet"): compacto <600dp = navegação inferior single-pane;
  médio 600–840dp = NavigationRail; expandido >840dp = **dois painéis** (o diferencial do tablet:
  **Leitor | painel RAG** lado a lado, ~65/35).
- **Telas do MVP:** Onboarding/Pareamento · Biblioteca · Detalhe do livro · **Leitor** · Player TTS
  (mini + full) · Busca (palavra-chave on-device + semântica no servidor) · **RAG Chat** · Configurações.
- **Leitura:** scroll contínuo como padrão (EPUB/TXT/DOCX), página fixa para PDF/CBZ; controles de
  fonte/tema em bottom sheet (claro/sépia/escuro/OLED); **seleção → barra contextual** (Destacar ·
  Traduzir · Perguntar à IA · Criar flashcard).
- **TTS:** mini-player fixo + player completo (voz, velocidade, **sleep timer**); nomes de engine
  (Kokoro/Piper) escondidos atrás de um seletor "qualidade da voz".
- **Pareamento:** **QR code + token** exibido pelo app desktop → câmera do celular (zero digitação);
  entrada manual como fallback; toggle "acesso remoto" via Tailscale.
- **Acessibilidade (crítica p/ app de leitura):** dynamic type, contraste WCAG AA, TTS como recurso de
  acessibilidade de primeira classe, reduced-motion.

---

## 5. Integração Claude Design no processo

Usar **Claude Design** (Anthropic Labs) para acelerar mockups de alta fidelidade → Flutter:
1. **Desenhar nesta ordem** (front-load do risco): Leitor → Biblioteca → RAG Chat → Player TTS →
   Onboarding/Settings.
2. **Web-capture** do app PyQt6 atual como referência de marca/estilo, para consistência visual.
3. Iterar **em nível de tela** (layout, hierarquia, estados: vazio/carregando/erro/offline) antes do pixel.
4. **Handoff** via `import-claude-design-from-url` dentro do Claude Code contra o repo Flutter, mapeando
   tokens (spacing/cor/tipografia) num `AppTheme`/`ThemeExtension` compartilhado — não hardcode por tela.
5. Tratar o código importado como **primeiro rascunho**: re-conectar a estado real (Riverpod/API) e
   revalidar breakpoints manualmente.

---

## 6. Rota de implementação (fases)

| Fase | Entregável | Depende de |
|---|---|---|
| **M0 — Backend headless** | `src/api/main.py`: monta OPDS como APIRouter + `/health` + `/library` + auth por token. Sem tocar na GUI. Testes de contrato. | — |
| **M1 — Cliente leitor (MVP tablet+phone)** | Shell Flutter + Riverpod + drift; Biblioteca via OPDS/REST; **Leitor PDF/EPUB**; progresso/anotações on-device. **Sem IA.** Design das telas via Claude Design. | M0; **spike EPUB** |
| **M2 — IA via servidor** | `/search`(+semântica) · `/rag`(SSE) · `/translate` · `/tts`(chunked) + player. | M1; **reindex bge-m3**; **adapter TTS-para-buffer** |
| **M3 — Proativo + push** | WebSocket `/proactive` + notificações + feedback 👍/👎. | M2 |
| **M4 — Offline no bolso (opcional)** | Kokoro-82M ONNX + LLM 1–3B + OCR ONNX no aparelho; degradação total. | M3 |
| **M5 — iOS / publicação** | Build iOS (mesmo código) + distribuição. | M2+ |

**Esforço (ordem de grandeza, 1 dev):** M0 ~1–2 sem · M1 ~3–5 sem · M2 ~3–4 sem · M3 ~1–2 sem.
MVP utilizável (M0→M2) ≈ **2–3 meses**.

---

## 7. Considerações técnicas internas (para a implementação posterior)

Itens **concretos** levantados pela auditoria de código — resolver ao entrar em cada fase:

1. **Adapter TTS → buffer (M2, prioridade alta).** `tts_router.speak()` (`src/core/tts/tts_router.py:525`)
   toca localmente via thread. A API precisa **capturar o áudio sintetizado** (chamar o provider e
   escrever num buffer/stream), não reproduzir. Provável caminho: expor um método `synthesize()` que
   retorna PCM/WAV/Opus em vez de reusar `speak()`.
2. **Estado de cancelamento por-sessão (M2/M3).** `_cancelled` é flag compartilhada no `RAGEngine`
   (`rag_engine.py:768-782`) e lida pelo orchestrator (`orchestrator.py:785`). MVP: serializar IA.
   Pós-MVP: estado por request/sessão.
3. **Override de `DATA_DIR`/`DB_PATH` (M0).** `src/utils/constants.py:11-14` resolve tudo relativo ao
   `PROJECT_ROOT`. Adicionar override por env var para rodar o backend como serviço/detached.
4. **DI/lifespan no OPDS (M0).** `opds_server.py` instancia `db = LibraryDB()` em nível de módulo —
   migrar para dependência gerenciada por `lifespan` ao montar sob a app raiz (evita handles duplicados).
5. **Threadpools para tudo pesado (M2).** Nada no core é `async`; LLM/TTS/NLLB/OCR/embeddings são
   bloqueantes. Usar `run_in_threadpool`/background tasks disciplinadamente para não travar o event loop.
   O `orchestrator.query_rag` já é gerador → encaixa direto em `StreamingResponse`.
6. **Reindex bge-m3 (dependência de M2).** Busca semântica retorna resultados obsoletos até o reindex dos
   ~65k chunks (débito já conhecido). Rodar antes de expor `/search/semantic`.
7. **Latência inicial do Kokoro (M2).** Medir *time-to-first-audio* de `/tts/stream` **antes** de
   construir o player (Fase 13A já sinalizou o problema).
8. **Segurança do FastAPI.** Endurecer auth por token antes de expor além da LAN; `PolicyEngine` (ADR-003)
   e "web como não confiável" permanecem no servidor.

---

## 8. Riscos principais e mitigação

| Risco | Sev. | Mitigação |
|---|---|---|
| Renderer EPUB imaturo no Flutter | Alta | **Spike na semana 1** (epub_pro/cosmos_epub) antes de fechar arquitetura do leitor |
| Débito reindex bge-m3 | Alta | Tratar como dependência bloqueante de M2 |
| Adapter TTS + latência Kokoro | Média-alta | Prototipar `/tts/stream` e medir TTFA cedo em M2 |
| Servidor precisa estar ligado/acessível | Média | Tailscale + degradação graciosa; offline real em M4 |
| Concorrência de IA (estado global) | Média | Serializar no MVP; refactor por-sessão depois |
| iOS (conta/custo/HIG) | Baixa (adiado) | Mesmo código; job de build adicional em M5 |

---

## 9. Definition of Done (por fase) e o que NÃO está coberto

- **DoD:** cada fase fecha com **testes verdes relevantes** (contrato de API por endpoint em M0; testes de
  concorrência/streaming em M2) e relatório (arquivos, testes, ADRs, riscos) — espelha AGENTS.md.
- **NÃO coberto nesta proposta** (próximo nível de detalhe): esquema exato de API/DTOs; modelo de
  sincronização e resolução de conflitos de anotações; mecânica de propagação do token OPDS; passos de
  assinatura/TestFlight iOS; auditoria WCAG linha-a-linha; empacotamento de modelos on-device (M4);
  benchmark real no tablet-alvo. Não li a GUI (`src/gui/**`) para confirmar ausência de imports reversos
  core→GUI; a suíte de testes não foi executada nesta análise.
