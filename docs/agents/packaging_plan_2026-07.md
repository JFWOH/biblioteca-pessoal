# Plano — Empacotamento v0.1 para testes com usuários reais (ciclo jul/2026-E)

> **Registro de execução (2026-07-20):** E1 (PR #62 — startup: chroma/Ollama
> fora da GUI thread, grade pós-show, quarentena de failed, splash),
> E3 (manual em `docs/manual_usuario.md`, no PR #62), E2 (PR #63 — aba
> 🔌 Integrações com registro MCP e chave allow_writes viva, auto-import do
> manual, HF_HOME portátil) e E4 (script `src/tools/build_package.py` +
> gerador `src/tools/manual_pdf.py`) EXECUTADAS. Pendente: rodar o build
> real (rede) e a E5 em máquina limpa — roteiro em
> `docs/agents/roteiro_validacao_pacote.md`. Melhorias seguintes só após o
> feedback dos testers (decisão do usuário).

> Preparado em 2026-07-20 (pós-ciclo D/MCP; base `main 0f50671`, suíte 1540).
> Pedido do usuário: (1) revisão de velocidade/otimização para rodar em
> hardwares diferentes; (2) inventário completo do pacote final para o
> usuário usar as funcionalidades diretamente. Medições feitas na máquina
> dev (Windows 11, RTX 5060 Ti, projeto em disco `G:`).

## 1. Medições (evidência, não estimativa)

| Item | Frio (disco) | Morno |
|---|---|---|
| `import PyQt6.QtWidgets` | 11,0 s | 0,5 s |
| `import chromadb` | 27,1 s | 3,0 s |
| `import torch` (cu128) | **60,8 s** | 5,8 s |
| `import transformers` | ~21,7 s | — |
| `import fitz` (PyMuPDF) | 2,2 s | — |

| Footprint | Tamanho |
|---|---|
| venv completo (torch **cu128**) | **5,8 GB** (torch 4,2 GB; PyQt6+WebEngine 551 MB; cv2 109 MB; transformers 94 MB; spacy+en_core_web_sm 107 MB) |
| venv com torch **CPU** (estimado) | ~3,3 GB |
| NLLB-200-distilled-600M (cache HF, 1º uso da tradução) | ~2,4 GB (o cache dev tem 4,7 GB por duplicação bin+safetensors) |
| Kokoro-82M + vozes (cache HF, 1º uso do TTS) | 316 MB |
| RapidOCR (ONNX embutido no pacote pip) | 16 MB — **offline, zero download** |
| Ollama + modelos (externo; wizard já baixa) | instalador ~700 MB + bge-m3 ~1,2 GB + gemma por tier (2–8 GB) |
| dados do DEV (`data/`): chroma 6,95 GB + library.db 249 MB + capas 40 MB | **NÃO vão no pacote** |

## 2. Revisão de performance multi-hardware

### O que o app JÁ faz certo (não mexer)
Degradação GPU→CPU por `torch.cuda.get_arch_list()` (Blackwell/sm_120 coberto);
tiers de modelo LLM por RAM/GPU (`HardwareCapabilityService`); torch/kokoro fora
do startup (TTSInitWorker pós-show, lição B0); NLLB lazy com patch de
`HF_HUB_OFFLINE` para o 1º download; carência de 300 s do auto-index;
reciclagem de cards na grade; `HF_HUB_OFFLINE=1` global evita travas de rede.

### Gargalos confirmados no startup (ordem de impacto em máquina de tester)
1. **P0 — ChromaDB no `__init__` da GUI**: `main_window.py:88 →
   _setup_rag_engine()` importa chromadb e abre o client persistente ANTES do
   `show()`, na GUI thread. Custo medido: ~27 s frio / ~3 s morno. Em HDD, é a
   maior fatia do "app não abre". Fix: mover para worker pós-show (mesmo padrão
   do TTSInitWorker) ou lazy no 1º uso do RAG; RAGPanel exibe "IA iniciando…".
2. **P0 — `_load_library()` no `__init__`** (`main_window.py:113`): monta a
   grade inteira (497 livros no dev) na GUI thread antes do show. Débito já
   registrado no ciclo C. Fix: janela mostra primeiro, grade carrega em
   seguida (chunked/idle), skeleton no lugar.
3. **P0 — Ollama-check na GUI thread** (`main_window.py:1117/1125`):
   `is_ollama_available()` é HTTP com timeout; sem Ollama instalado (caso
   típico de tester no 1º uso) o timeout congela a UI. Fix: worker + cache.
4. **P0 — retry de livros `failed` a cada sessão** (débito do ciclo C): em
   máquina fraca o indexador reextrai PDF pesado toda vez que abre. Fix:
   backoff/quarentena de `failed`.
5. **P1 — sem splash/feedback**: a janela só aparece no fim do `__init__`
   inteiro. Splash nativo imediato (ou show antecipado + skeleton) muda a
   percepção mais que qualquer otimização real.
6. **P1 — 1º uso de TTS/tradução em HDD**: torch frio ~60 s antes do primeiro
   áudio/tradução. Já é assíncrono; garantir mensagem de progresso explícita
   ("preparando motor de voz — primeira vez demora").
7. **P2 — bytecode pré-compilado** (`compileall` no build) e pacote em disco
   único: reduz I/O de import frio; ganho moderado, custo quase zero.

### Perfil esperado por classe de máquina (após P0s)
| Máquina | Startup hoje | Startup pós-P0 | Observações |
|---|---|---|---|
| SSD + GPU (dev) | ~5–10 s | ~2–3 s | tier alto de LLM |
| SSD sem GPU | ~15–30 s frio | ~3–5 s | torch CPU; TTS/tradução mais lentos porém funcionais |
| HDD, 8 GB RAM | 60 s+ frio | ~10–15 s | tier mínimo de LLM; 1º uso de cada motor de IA lento (avisar) |

Requisitos mínimos propostos p/ documentar: Windows 10/11 64-bit, 8 GB RAM
(16 GB recomendado p/ IA completa), ~6 GB de disco sem IA local / ~15 GB com
Ollama+modelos; GPU opcional.

## 3. Inventário do pacote final

### Decisões do usuário (2026-07-20)
1. **Formato: ZIP portátil** — mas com requisito-guia: **zero conhecimento
   técnico**. O app deve vir completo ou automatizar toda a configuração de
   forma transparente. Consequências práticas:
   - lançador sem terminal visível (`pythonw`), nome amigável, duplo-clique
     e abre; nunca pedir comando ao usuário;
   - **Kokoro (316 MB) EMBUTIDO** no pacote (TTS funciona offline de cara);
   - downloads restantes (NLLB, Ollama+modelos) acontecem por dentro do app,
     com um clique de consentimento e barra de progresso — nunca via terminal;
   - toda falha vira mensagem em português com ação sugerida (nunca stack).
2. **Manual/tutorial em PDF incluído — e consumível pela IA** (seção 3.1).

PyInstaller/onefile segue **desaconselhado** nesta stack (torch + QtWebEngine +
chromadb + onnxruntime + espeakng = hooks frágeis, quebra silenciosa);
instalador Inno fica como evolução pós-feedback.

### 3.1 Manual do usuário (PDF) usado pela própria IA
- Fonte versionada em `docs/manual_usuario.md` (PT-BR, capturas de tela);
  conteúdo: extrair e abrir, primeiro uso (o que o wizard vai fazer), importar
  livros, ler/anotar/marcar, narração (e a espera do 1º uso), tradução, IA
  local (o que esperar de latência), flashcards/SRS, estatísticas, solução de
  problemas comuns, como reportar bugs.
- O build gera `Manual - Biblioteca Pessoal.pdf` na raiz do ZIP (geração via
  QTextDocument→PDF do próprio Qt do venv — zero dependência nova; validar
  qualidade, senão fallback `fpdf2`/`weasyprint` só no ambiente de build).
- **Integração com a IA (o pulo do gato — infra já existe):** no 1º uso o app
  auto-importa o manual como livro da biblioteca e o auto-index o indexa no
  RAG/FTS. Resultado: o usuário pergunta "como importo livros?" no painel de
  IA (ou via MCP) e recebe resposta com citações de página do manual. Também
  serve de conteúdo-demonstração imediato (biblioteca nunca abre vazia).
- Acesso clássico em paralelo: menu Ajuda → "Abrir manual (PDF)".

### O que VAI no pacote
1. Runtime Python 3.11 + dependências com **torch CPU** (~3,3 GB; corta 2,5 GB
   do cu128). GPU vira upgrade opcional oferecido PELO APP quando detectar
   NVIDIA (nunca um comando pedido ao usuário).
2. `src/` completo (inclui servidor MCP), `resources/` (temas/ícones, ~0 MB).
3. Lançador amigável sem console (`pythonw`), nome "Biblioteca Pessoal";
   atalho "Diagnóstico" (roda checagens e mostra log legível).
4. `data/` **vazio** (o app cria tudo no 1º uso — confirmado: `mkdir` em
   runtime). Config default de fábrica (`mcp.allow_writes=false`).
5. RapidOCR já embutido (OCR funciona offline de cara).
6. **Kokoro-82M + vozes pré-copiados** no cache local do pacote (decisão do
   usuário: TTS offline de cara; formato do seed = snapshot HF dentro do ZIP
   com `HF_HOME` apontado para pasta do pacote — mantém o app portátil e não
   polui o perfil do usuário).
7. `Manual - Biblioteca Pessoal.pdf` (seção 3.1) + `LEIA-ME.txt` curto
   (2 parágrafos: "extraia e dê dois cliques"; o resto está no manual).

### O que é baixado no 1º uso (por dentro do app, com progresso — nunca terminal)
| Asset | Quando | Tamanho | Mecanismo |
|---|---|---|---|
| NLLB-600M | 1ª tradução | ~2,4 GB | patch HF_HUB_OFFLINE (já implementado) |
| Ollama (daemon) | wizard de IA (1 clique) | ~700 MB | `OllamaInstaller` (/SILENT) — já implementado |
| bge-m3 + gemma (tier) | wizard de IA | 1,2 + 2–8 GB | `pull_model` por `HardwareCapabilityService` |

(Kokoro saiu desta tabela — vai embutido no pacote, decisão do usuário.
Rodada ago/2026: a voz de RESERVA do Piper, `pt_BR-faber-medium` ~63 MB,
também vai embutida — estágio `piper` do build, decisão R.4. NLLB segue no
1º uso: 2,4 GB no ZIP é caro demais.)

### O que NÃO vai (checklist de exclusão do build)
`data/` do dev (chroma_db 6,9 GB, library.db, covers, traces, recovery*.sql),
`venv/` do dev (cu128), `tests/`, `reports/`, `docs/agents/`, `.git/`,
caches HF do dev, `.claude/`.

### Riscos do pacote
SmartScreen/antivírus sem assinatura digital (mitigar: zip + instruções, ou
assinar depois); caminhos com acento/espaço (testar); primeira execução
sempre mais lenta (comunicar no LEIA-ME); downloads grandes do wizard em
conexão lenta (wizard já tem progresso); porta 11434 ocupada.

## 4. Rodadas propostas (cada uma com o protocolo padrão: branch→testes→PR→auditoria→CI)
- **E1 — Otimizações P0 de startup** (itens 1–4 da seção 2 + splash P1): é o
  pré-requisito real de "rodar bem em hardware diferente".
- **E2 — Primeira execução transparente** (requisito zero-fricção): wizard
  único de boas-vindas (detecta hardware → 1 clique instala IA local com
  progresso), auto-import + auto-index do manual como livro nº 1, mensagens
  de 1º uso nos motores lentos (TTS/tradução), `HF_HOME` portátil apontando
  para o pacote, lançador `pythonw` sem console, erros sempre em PT com ação.
- **E3 — Manual do usuário**: escrever `docs/manual_usuario.md` (com capturas)
  + gerador md→PDF; menu Ajuda → abrir PDF.
- **E4 — Script de build do pacote** (`src/tools/build_package.py`): monta o
  layout portátil (python embutido + site-packages torch CPU), pré-seed do
  Kokoro, gera o PDF do manual, `compileall`, checklist de exclusão, smoke
  test automatizado do pacote (abre, importa 1 PDF, busca, fecha).
- **E5 — Teste em máquina limpa** (VM Windows sem Python/GPU): roteiro de
  validação manual + ajustes do manual/LEIA-ME.

## Fora de escopo deste ciclo
Assinatura digital, auto-update, build macOS/Linux, loja (MS Store), telemetria.
