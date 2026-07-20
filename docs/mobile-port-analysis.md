# Relatório de Análise — Portar a "Biblioteca Pessoal" para Tablet/Celular

> Documento de estratégia. Não altera código. Data da análise: 2026-07-01.
> Autor: análise assistida (Claude). Base: leitura da arquitetura atual + pesquisa de mercado 2026.

---

## 1. Resumo executivo (TL;DR)

- **Não porte o app PyQt6 para o celular.** Empacotar PyQt6 + torch + transformers + chromadb +
  Kokoro em um APK/IPA é técnica e economicamente inviável (peso, wheels nativas ausentes, calor/RAM).
- **Arquitetura vencedora: cliente-servidor.** O núcleo pesado de IA continua rodando no **PC/servidor
  doméstico** (Ollama, ChromaDB, NLLB, TTS neural, OCR) e o celular/tablet vira um **cliente nativo leve**
  que fala com esse backend por HTTP/REST. O projeto **já tem a semente do backend** (FastAPI + OPDS +
  httpx nas dependências) e a fronteira arquitetural certa (ADR-006: `core` não importa GUI).
- **Sistema-alvo recomendado: Android primeiro** (tablet como foco de leitura), depois iOS.
  Framework: **Flutter** (melhor render de leitura/animação, code-share desktop+mobile, 46% do mercado
  em 2026) — ou **Kotlin Multiplatform** se o alvo for exclusivamente Android/nativo.
- **Trilha "offline no bolso" é possível mas parcial:** LLM 1B–3B on-device (llama.cpp/MLC), Kokoro-82M
  em ONNX Runtime e OCR ONNX rodam no aparelho; **bge-m3 (1024d) e NLLB são pesados demais** para
  celular — mantê-los no servidor ou trocar por versões quantizadas menores.
- **Esforço realista do MVP mobile (leitor + biblioteca + TTS via servidor):** ~2–3 meses de 1 dev
  competente; paridade de IA (RAG + proativo + tradução) via servidor: +1–2 meses.

**Decisão a tomar antes de começar:** o app mobile deve funcionar **100% offline no aparelho**, ou pode
**depender do PC/servidor doméstico ligado**? Essa escolha define tudo abaixo. (Ver §7 e §9.)

---

## 2. O que é o projeto hoje (baseline)

- **~21.300 linhas Python.** GUI (PyQt6) = 10.836 LOC; Core IA = 8.551 LOC; readers = 884; utils/tools ~1.000.
- **Desktop-first, local-first, Windows.** Roda em venv com GPU Blackwell (torch cu128), fallback CPU.
- **Stack pesada:** PyQt6 + WebEngine, PyMuPDF, EbookLib, python-docx, RapidOCR (ONNX), Ollama
  (LLM `gemma4:e4b`), ChromaDB (embeddings `bge-m3` 1024d), NLLB-200 (tradução), Kokoro/Piper/pyttsx3 (TTS),
  Anki/SRS, FastAPI + servidor OPDS.
- **Funcionalidades por fase:** leitura multi-formato (PDF/EPUB/MOBI/DOCX/TXT/CBZ) + OCR; tradução offline;
  RAG agentic (orchestrator + PolicyEngine anti prompt-injection + TraceLogger); agente proativo de leitura;
  flashcards/Anki; Audio Reader 2.0 (TTS em camadas).
- **Ativo arquitetural decisivo:** **ADR-006** já obriga `src/core/**` a NÃO importar PyQt6. Ou seja, boa
  parte da lógica de negócio já é "headless" e pode virar API sem reescrever. Threads/sinais estão isolados
  em `src/gui/workers/**` — exatamente o que se joga fora num port cliente-servidor.

### Por que isso importa para mobile
Cada dependência pesada é um obstáculo de empacotamento. A tabela §5 mapeia o que sobrevive on-device e o
que precisa migrar para o servidor.

---

## 3. O conflito central: stack de IA pesada × restrições de mobile

Pesquisa de mercado 2026 (fontes no fim):

- **LLM on-device:** sweet spot é **1B–3B parâmetros**. iPhone 17 Pro faz ~40 tok/s em Gemma 4 **E2B**;
  modelos ~4B ficam em 8–15 tok/s. O gargalo real **não é RAM, é calor** (throttling em geração longa).
  → O `gemma4:e4b` atual (≈4B efetivos) roda no limite só em topo de linha; inviável em tablet mediano.
- **Embeddings:** `bge-m3` (568M, 1024d) é pesado para celular e o índice real tem ~65k chunks — buscar
  vetorialmente com Chroma no aparelho é impraticável. On-device exigiria embedding menor (e2e menor) e um
  vector store leve (SQLite-VSS/usearch/objectbox).
- **TTS:** **Kokoro-82M roda on-device via ONNX Runtime**, inclusive com phonemizer **PT**. Latência ~8s
  para 10s de áudio em smartphone recente (melhorável com batch/paralelização — NimbleEdge já mostrou).
  → Viável no aparelho, com otimização; ou fica no servidor (menor latência, sem drenar bateria).
- **OCR:** RapidOCR já é ONNX → portável a ONNX Runtime Mobile.
- **Tradução (NLLB-200):** grande; melhor no servidor, ou trocar por modelo de tradução mobile menor.
- **Empacotar Python no celular (Kivy/BeeWare/Chaquopy/pyqtdeploy):** funciona para Python "puro", mas
  **wheels nativas (torch, chromadb, onnxruntime-gpu) raramente têm build Android/iOS**. Confirmado como o
  limite prático de Python-on-mobile em 2026. **Não é o caminho para este app.**

**Conclusão:** rodar o app inteiro no aparelho contradiz as restrições de 2026. A pergunta certa não é
"como empacoto tudo no celular", e sim **"o que fica no aparelho e o que fica no servidor".**

---

## 4. Opções de arquitetura (matriz de decisão)

| # | Estratégia | Como | Prós | Contras | Veredito |
|---|-----------|------|------|---------|----------|
| **A** | **Cliente-servidor** (RECOMENDADA) | PC/servidor doméstico expõe o `core` via FastAPI; app mobile nativo consome REST/WebSocket. Sincroniza biblioteca/progresso. | Reaproveita ~8.5k LOC do core intactos; IA pesada no hardware certo; app leve; multiplataforma; segue ADR-006. | Exige o PC/servidor ligado e alcançável (LAN/VPN/Tailscale). IA "no bolso" só com internet até o servidor. | ✅ **Melhor custo/benefício** |
| **B** | **Full nativo on-device** | Reescrever tudo nativo + modelos quantizados (LLM 1–3B, Kokoro ONNX, embed menor). | 100% offline, privacidade máxima, sem depender de PC. | Reescrita quase total; IA degradada (modelos menores); calor/bateria; meses de trabalho; sem paridade de RAG/tradução. | ⚠️ Só como fase 2 seletiva |
| **C** | **Híbrido (A + subset on-device)** | Cliente do servidor **quando disponível**; quando offline, cai para leitura + TTS on-device (Kokoro ONNX) + LLM 1–3B local. | Melhor experiência real; degradação graciosa (alinha ADR-005). | Mais complexo: dois caminhos de código; sincronização de estado. | 🎯 **Alvo de longo prazo** |
| **D** | **PWA / web responsivo** | Extrair GUI para web (o backend FastAPI serve SPA); "app" é o navegador/PWA. | 1 código para todas as plataformas; zero loja; rápido de prototipar. | Leitura offline e TTS/gestos piores que nativo; WebEngine≠web; menos "app de tablet". | 🔸 Bom para validar rápido / MVP barato |
| **E** | **Empacotar PyQt no celular** (pyqtdeploy/Briefcase) | Buildar o app atual para Android. | "Reaproveita" a GUI. | torch/chromadb/onnx sem wheels mobile; APK gigante; UX de desktop num toque. | ❌ **Descartar** |

---

## 5. Adequação funcionalidade-a-funcionalidade (o que roda onde)

| Funcionalidade | On-device viável? | Recomendação mobile |
|---|---|---|
| Leitura PDF/EPUB/MOBI/DOCX/TXT/CBZ | ✅ Sim (libs nativas: PdfRenderer/pdf.js, readers EPUB nativos) | **No aparelho** — é o coração da UX de tablet. Reescrever os 6 readers em nativo. |
| Biblioteca / metadados / capas | ✅ Sim (SQLite local) | No aparelho, **sincronizada** com o servidor (OPDS já existe → reutilizar!). |
| Progresso de leitura / anotações / tags / rating | ✅ Sim | No aparelho + sync bidirecional. |
| OCR (PDF escaneado) | 🟡 ONNX Runtime Mobile | On-device (RapidOCR já é ONNX) **ou** servidor. |
| TTS / Audio Reader | 🟡 Kokoro-82M ONNX (PT ok) | **Servidor por padrão** (menor latência/bateria); **on-device como fallback offline**. |
| Tradução (NLLB) | 🔴 Pesado | **Servidor.** On-device só com modelo de tradução mobile menor. |
| RAG agentic (orchestrator+tools+policy) | 🔴 Precisa LLM + vetor grande | **Servidor** (Ollama + Chroma + PolicyEngine + TraceLogger intactos). |
| Agente proativo de leitura | 🔴 LLM | **Servidor**; app recebe observações via push/WebSocket. |
| Flashcards / SRS / Anki | ✅ Sim (lógica leve) | On-device; export Anki pelo servidor se necessário. |
| Busca por palavra-chave (FTS5) | ✅ SQLite FTS5 | On-device. |
| Busca vetorial (semântica) | 🔴 bge-m3 + 65k chunks | **Servidor.** |

Legenda: ✅ nativo simples · 🟡 possível com ONNX/otimização · 🔴 melhor no servidor.

---

## 6. Escolha de sistema e framework

### Sistema-alvo
- **Android primeiro.** Público de leitura em tablet é fortemente Android; distribuição fora de loja é
  possível (APK), o que casa com a filosofia local-first/privado do projeto. **iOS depois** (App Store
  impõe mais fricção e custo de conta de dev).
- Tablet como forma-fator primário (tela grande favorece leitura + painéis RAG/anotação); celular como
  secundário (leitura + TTS + captura).

### Framework do cliente (recomendação)
1. **Flutter** — *recomendado default.* Render consistente e 60–120 FPS (bom para leitor), code-share
   mobile+desktop+web (permite futuramente aposentar o PyQt no desktop também), maior fatia de mercado
   (≈46% em 2026), ótimo ecossistema de leitores (pdfx, epub renderers) e ONNX Runtime.
2. **Kotlin Multiplatform (KMP)** — se o alvo for **exclusivamente Android/nativo** e você quiser UI 100%
   nativa (Jetpack Compose) com lógica compartilhada. Melhor integração on-device (llama.cpp, ORT, MediaPipe).
3. **React Native** — só se já houver familiaridade com JS/TS no time. Bom para app-cliente; menos ideal
   para render de leitura pesado.
4. **PWA (web responsivo)** — caminho mais barato para um **MVP de validação** reaproveitando o backend.

> Recomendação prática: **Flutter para o cliente + FastAPI headless para o backend.** Se a prioridade for
> IA on-device robusta e nativa, considerar **KMP**.

---

## 7. Arquitetura recomendada (alvo)

```
┌────────────────────────── PC / Servidor doméstico (Windows/Linux) ──────────────────────────┐
│  Reaproveita src/core/** SEM GUI (ADR-006 já garante isso)                                    │
│                                                                                              │
│   FastAPI (headless)  ──►  /library  /read  /rag  /translate  /tts  /proactive (WebSocket)   │
│        │                     │        │      │        │         │                            │
│   Ollama (gemma4)      ChromaDB(bge-m3)  NLLB   Kokoro/Piper  OCR(RapidOCR)  SQLite/FTS5      │
│                                                                                              │
│   OPDS server (já existe) ──► catálogo/sync de biblioteca                                     │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                     ▲  HTTP/REST + WebSocket (LAN / Tailscale / VPN)  ▲
┌────────────────────────────────── App móvel (Flutter) ──────────────────────────────────────┐
│  ON-DEVICE:  leitor multi-formato · biblioteca/SQLite · progresso/anotações · flashcards/SRS │
│  VIA SERVIDOR: RAG · tradução · TTS · busca semântica · agente proativo (push)               │
│  FALLBACK OFFLINE (fase 2): Kokoro-82M ONNX · LLM 1–3B (MLC/llama.cpp) · OCR ONNX            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Pontos-chave:
- **Passo zero é extrair um backend headless** do `core` atual. Como o ADR-006 já proíbe `core`→GUI, isso é
  sobretudo **expor endpoints** sobre serviços que já existem (`library`, `rag_engine`, `orchestrator`,
  `tts_router`, `nllb_backend`, `ocr_service`). Baixo risco.
- **Conectividade:** LAN direta em casa; **Tailscale/WireGuard** para acesso remoto sem abrir portas
  (mantém o local-first/privado).
- **Sync de biblioteca:** OPDS já implementado → o cliente móvel pode consumir o catálogo desde o dia 1.
- **Segurança:** o `PolicyEngine` (ADR-003) e o tratamento de "web como não confiável" continuam no
  servidor; adicionar **auth por token** no FastAPI (hoje o servidor é doméstico/local).

---

## 8. Roadmap sugerido (fasejado, alinhado ao estilo do projeto)

- **Fase M0 — Backend headless (habilitador).** Extrair FastAPI cobrindo `library/read/search`; auth por
  token; reutilizar OPDS. *Sem tocar na GUI desktop.* Entregável: API documentada + testes de contrato.
- **Fase M1 — Cliente leitor (MVP tablet).** Flutter: biblioteca (via OPDS/REST), leitor PDF/EPUB nativo,
  progresso/anotações on-device + sync. **Sem IA ainda.** Valida UX de tablet.
- **Fase M2 — IA via servidor.** Endpoints `/rag`, `/translate`, `/tts` no cliente; player de áudio
  streaming do servidor; painel RAG e seleção→tradução.
- **Fase M3 — Proativo + push.** WebSocket para observações do agente proativo; notificações.
- **Fase M4 — Offline no bolso (opcional).** Kokoro-82M ONNX + LLM 1–3B on-device + OCR ONNX; degradação
  graciosa quando o servidor não está acessível (alinha ADR-005).
- **Fase M5 — iOS / publicação.** Port iOS (Flutter reduz o custo), empacotamento e distribuição.

---

## 9. Riscos, limitações e decisões abertas

- **Dependência do servidor ligado.** O maior contra do modelo A/C. Mitigar com Tailscale + fallback M4.
- **Reescrita da GUI é inevitável.** Os 10.836 LOC de PyQt6 **não** se reaproveitam no mobile; a UI é
  redesenhada para toque. O que se reaproveita é o **core** (~8.5k LOC) via API.
- **Paridade de IA on-device é parcial.** Modelos mobile (1–3B, embed menor) entregam qualidade inferior ao
  `gemma4:e4b` + `bge-m3`. Gerir expectativa: on-device = conveniência offline, não paridade.
- **Reindex bge-m3 pendente** (memória do projeto): a busca semântica no servidor depende do reindex de
  ~65k chunks já sinalizado. Não é bloqueio do mobile, mas afeta o endpoint `/rag`.
- **Auth/segurança do FastAPI** precisa endurecer antes de expor além da LAN.
- **iOS App Store** pode impor fricção a recursos "IA local/servidor próprio" — validar políticas.

### Decisões que só o Jeferson pode tomar (pré-requisito para detalhar implementação)
1. **Offline-first no aparelho** vs **depende do servidor doméstico**? (define A vs C, e o escopo de M4)
2. **Android-only** vs **Android+iOS**? (define Flutter vs KMP)
3. **Tablet** como forma primária, ou **celular** também em pé de igualdade?
4. Aceita **Flutter** (nova stack, Dart) ou prefere manter tudo no **ecossistema Python/nativo Android**?

---

## 10. O que este relatório NÃO cobriu (honestidade sobre escopo)

- **Não** li o conteúdo integral dos ADRs 001–007 nem de cada módulo — a análise se apoiou na estrutura,
  dependências, memória do projeto e nos contratos de fase. Detalhes finos de cada serviço podem ajustar §5.
- **Não** fiz prova de conceito nem benchmark real dos modelos on-device **neste hardware/tablet-alvo** —
  os números de tok/s vêm de benchmarks públicos 2026, não de medição local.
- **Não** desenhei o esquema de API (endpoints, contratos, DTOs) nem o modelo de sincronização/conflitos —
  é o próximo passo se a arquitetura A/C for aprovada.
- **Não** estimei custo de conta de desenvolvedor (Apple/Google) nem detalhei distribuição/atualização.
- **Não** avaliei acessibilidade, i18n além de PT/EN, nem requisitos legais de conteúdo/DRM de ebooks.
- **Estimativas de esforço** são de ordem de grandeza (1 dev), não um cronograma comprometido.

---

## Fontes (pesquisa 2026)

- Awesome Mobile LLMs — https://github.com/stevelaskaridis/awesome-mobile-llm
- Run an LLM on Your Phone (2026) — https://localaimaster.com/blog/run-llm-on-phone
- MLC LLM vs Ollama Android 2026 — https://www.promptquorum.com/local-llms/mobile-local-llms
- llama.cpp on Android (perf) — https://github.com/ggml-org/llama.cpp/discussions/14356
- expo-kokoro-onnx — https://github.com/isaiahbjork/expo-kokoro-onnx
- How to run Kokoro TTS on-device (NimbleEdge) — https://www.nimbleedge.com/blog/how-to-run-kokoro-tts-model-on-device/
- kokoro-onnx — https://github.com/thewh1teagle/kokoro-onnx
- Flutter vs React Native 2026 (market share) — https://tech-insider.org/flutter-vs-react-native-2026/
- Best Cross-Platform Frameworks 2026 (Uno) — https://platform.uno/articles/best-cross-platform-frameworks-2026/
- Using Python on Android — https://docs.python.org/3/using/android.html
- BeeWare Briefcase 2026 — https://johal.in/beeware-briefcase-packaging-native-python-ios-android-builds-2026/
- PEP 738 (Android support) — https://peps.python.org/pep-0738/
