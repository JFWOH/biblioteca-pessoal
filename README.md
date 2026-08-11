# 📚 Biblioteca Pessoal

Gerenciador de biblioteca pessoal e leitor multi-formato sofisticado, desenvolvido com Python e PyQt6.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green?logo=qt)
![SQLite](https://img.shields.io/badge/SQLite-FTS5-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

## ✨ Funcionalidades

### 📖 Leitor Multi-Formato
- **PDF** — Renderização via PyMuPDF com zoom e navegação por página
- **EPUB** — Parsing completo de capítulos com TOC interativo
- **DOCX** — Conversão para HTML com preservação de estilos
- **TXT/Markdown** — Com syntax highlighting e geração de TOC automática
- **MOBI** — Suporte básico (stub para integração futura)

### 📚 Gerenciamento de Biblioteca
- Importação em lote com detecção automática de duplicatas (SHA-256) — por diálogo ou **arrastar-e-soltar** na janela
- Extração automática de metadados (título, autor, capa, páginas)
- Busca full-text ultrarrápida via **SQLite FTS5** — inclusive no conteúdo (OCR de PDFs escaneados indexado na hora)
- Prateleira **"Continuar lendo"** e % de progresso nas capas
- Coleções e tags personalizáveis; menu de contexto nos cards
- Avaliação com estrelas interativa (0-5)
- Estatísticas vivas: sequência de dias lidos (streak) e minutos por semana

### 📝 Anotações e Destaques
- Notas de texto por página
- Marcadores de página
- Seleção de cores para destaques
- Navegação rápida entre anotações

### 🎨 Interface Premium
- 3 temas: **Escuro**, **Claro** e **Sépia** — aplicados a todas as superfícies
- Botão **Aa** no leitor: fonte, tamanho, entrelinha e margens ajustados ao vivo
- Painel lateral recolhível com **Sumário** (miniaturas de capítulo) e **Marcadores**
- Visualização em grade com capas extraídas automaticamente
- Busca dentro do documento (Ctrl+F)
- Modo tela cheia (F11)
- Painel de estatísticas com dashboard visual
- Diálogos ricos para importação e configurações

### 🤖 Assistente de IA 100% local (Ollama)
- **Chat com seus livros (RAG agentic)**: buscas vetoriais, full-text, no grafo de conceitos e na web — com **citações clicáveis** `[Título, p. X]` que saltam direto à página
- **Agente proativo de leitura**: insights por página, com continuidade entre sessões e aprendizado com as suas dispensas e avaliações 👍/👎 (com motivo)
- **Dossiê do livro**: síntese, conceitos centrais e livros relacionados da sua própria biblioteca
- **X-Ray da página**: conceitos da página atual e onde mais aparecem — via grafo, sem custo de LLM
- **Flashcards gerados por IA** (pergunta/resposta) com revisão SRS e **export para Anki**
- **Word Wise**: definição rápida de qualquer palavra selecionada
- Governança: **Policy Engine** (ADR-003) valida toda interação da IA com a GUI; **Trace Logger** (ADR-004) registra as sessões em JSONL

### 🔊 Leitura em Áudio (TTS neural local)
- Narração com voz neural local (**Kokoro**; reserva Piper → pyttsx3), estilos de narração e seleção de voz
- Detecção automática de idioma (PT/EN) com voz adequada por sentença
- **Leitura contínua** com virada de página automática e pré-síntese da próxima página
- **"Ouvir original / Ouvir traduzido"**: narração da página traduzida (NLLB) em um clique

### 🌐 Tradução Offline Local-First
- Tradução de trechos selecionados (em PDFs escaneados com OCR ou EPUBs) suportada pelo modelo **NLLB-200** (`facebook/nllb-200-distilled-600M`).
- **Limites e Hardware**: Operação em GPU/CPU otimizada (~1.2GB VRAM). Texto limitado a blocos curtos (máximo 2000 caracteres por disparo) para prevenir travamentos (Graceful Fallback incluído). Processamento ocorre 100% fora da Main Thread da UI.
- **Ressalva Offline**: A operação é offline, porém **exige obrigatoriamente conexão à internet na primeira execução** para efetuar o download/bootstrap dos pesos do modelo para a cache local. Em seguida, roda 100% localmente sem qualquer envio de dados do usuário.

## 🚀 Instalação

Pré-requisito: **Python 3.11** instalado ([python.org](https://www.python.org/downloads/)).
O app roda em Windows (plataforma primária, testada), com código preparado para Linux e macOS.

```bash
# Clone o repositório (qualquer pasta/drive)
git clone https://github.com/JFWOH/biblioteca-pessoal.git
cd biblioteca-pessoal

# Crie o ambiente virtual com o Python 3.11
python -m venv venv
#   (se o comando "python" não for o 3.11 na sua máquina, use:
#    Windows:  py -3.11 -m venv venv
#    Linux/Mac: python3.11 -m venv venv)

# Instale as dependências (sempre pelo python do venv)
venv\Scripts\python.exe -m pip install -r requirements.txt      # Windows
# ./venv/bin/python -m pip install -r requirements.txt          # Linux/Mac
```

> **Dica — múltiplos Pythons instalados:** nunca rode o app com o `python` "solto"
> do sistema. Use sempre o interpretador do venv do projeto
> (`venv\Scripts\python.exe` no Windows, `./venv/bin/python` no Linux/Mac).
> Para conferir qual está ativo: `python -c "import sys; print(sys.executable)"`.

### 📦 App portátil (ZIP) — sem instalar Python

Para gerar um pacote portátil (Python embutido + dependências CPU) e usar ou
distribuir em máquinas sem nenhum pré-requisito:

```bash
venv\Scripts\python.exe -m src.tools.build_package --out build\BibliotecaPessoal
```

O roteiro de validação em máquina limpa está em
`docs/agents/roteiro_validacao_pacote.md`.

### 🤖 Assistente de IA (Ollama) — instalação automática

O assistente local usa o **Ollama**. **Você não precisa instalar nada manualmente**:
na primeira execução, se o Ollama não for detectado, o app abre um assistente de
configuração que baixa e instala o Ollama sozinho (Windows/Linux/macOS) e, em
seguida, **baixa os modelos de IA adequados ao seu hardware**:

- **`gemma4:e4b`** (leve) — padrão universal, roda até em notebook básico;
- **`gemma4:12b`** — usado automaticamente apenas se a GPU comportar (>10 GB VRAM);
- **`bge-m3`** — embeddings para a busca semântica nos livros.

Se o Ollama já estiver instalado mas sem modelos, o app detecta e baixa os
modelos em segundo plano no próximo início (aviso na barra de status).

O mesmo vale para os demais modelos locais (tradução NLLB-200, vozes do TTS
Kokoro): são baixados **sob demanda no primeiro uso** — por isso a primeira
execução de cada recurso exige internet; depois, tudo roda 100% offline.

### ⚡ Aceleração por GPU (NVIDIA)

Por padrão o `torch` do PyPI roda em CPU. Para ativar a aceleração CUDA — incluindo
GPUs Blackwell / RTX série 50 (`sm_120`, ex.: RTX 5060 Ti) — instale a build CUDA 12.8
**a partir do índice oficial do PyTorch** (substitui o torch de CPU):

```powershell
venv\Scripts\python.exe -m pip install torch==2.11.0+cu128 --index-url https://download.pytorch.org/whl/cu128
```

> O download é grande (~2.75 GB, com as bibliotecas CUDA embarcadas). O código detecta a
> GPU automaticamente (`get_arch_list()`): se a GPU for suportada, tradução (NLLB) e TTS
> (Kokoro) usam CUDA; caso contrário caem para CPU sem travar (ADR-005). Não é preciso
> mudar nenhuma configuração.
>
> Para reproduzir exatamente a stack GPU validada, use o freeze:
> `reports/phase_13b3_gpu_lab_requirements.txt`. O conjunto baseado em `cu128` foi
> homologado com a suíte completa de testes. Alternativa mais à prova de futuro: `cu130`
> (CUDA 13.0), já que o `cu128` será deprecado a partir do PyTorch 2.12.

## ▶️ Inicialização

**Windows** — a forma mais simples é o script na raiz do projeto (usa o caminho
relativo do próprio clone, funciona em qualquer pasta):

```
iniciar.bat
```

Ou manualmente, em qualquer sistema:

```bash
# Windows
venv\Scripts\python.exe -m src.main

# Linux / macOS
./venv/bin/python -m src.main
```

Os dados do usuário (biblioteca, capas, índice de busca, configurações) ficam
na pasta `data/` dentro do próprio clone — nada é gravado fora do projeto.

### 🧩 Adaptação automática ao hardware

O app detecta o hardware no início e se ajusta sozinho — não há configuração
obrigatória:

| Recurso | Como se adapta |
|---|---|
| Modelo de IA do assistente | GPU >10 GB VRAM → `gemma4:12b`; caso contrário → `gemma4:e4b` (leve) |
| Agente proativo de leitura | Desligado automaticamente em máquinas com <8 GB de RAM |
| Tradução (NLLB) e TTS (Kokoro) | GPU CUDA compatível → acelera; senão → CPU, sem travar |
| TTS (voz) | Cadeia de fallback: Kokoro → Piper → pyttsx3, conforme a máquina |
| OCR de PDFs escaneados | RapidOCR via ONNX, roda em CPU em qualquer máquina |

## 📦 Dependências Principais

| Pacote | Função |
|--------|--------|
| PyQt6 | Interface gráfica |
| PyQt6-WebEngine | Renderização HTML (EPUB/TXT) |
| PyMuPDF | Leitura de PDF |
| EbookLib | Leitura de EPUB |
| python-docx | Leitura de DOCX |
| BeautifulSoup4 | Parsing de HTML |
| Pillow | Processamento de imagens |
| natsort | Ordenação natural |
| torch | Inferência local (Tradução Offline) |
| transformers | Pipeline NLLB-200 (Tradução Offline) |
| sentencepiece | Tokenizador (exigido pelo NLLB-200) |

## ⌨️ Atalhos de Teclado

| Atalho | Ação |
|--------|------|
| `Ctrl+I` / `Ctrl+O` / `Ctrl+Shift+O` | Importar documentos / arquivo / pasta |
| `Ctrl+F` | Buscar no documento |
| `Space` / `Shift+Space` | Próxima página / anterior |
| `←` `→` / `PageUp` `PageDown` | Navegação de página |
| `Ctrl+D` | Marcar/desmarcar página (bookmark) |
| `Ctrl+B` | Mostrar/ocultar barra lateral |
| `Ctrl+R` / `Ctrl+Shift+A` | Painel do assistente de IA |
| `Ctrl+Shift+F` | Flashcards |
| `Ctrl+,` | Configurações |
| `F11` | Tela cheia |
| `Ctrl++` / `Ctrl+-` | Zoom in / out |
| `Escape` | Voltar / sair de tela cheia |

Lista completa dentro do app: **Ajuda → Atalhos de Teclado**.

## 🏗 Arquitetura

```
src/
├── core/           # Lógica de negócio (sem PyQt6 — ADR-006)
│   ├── database.py / library.py / metadata.py / search.py / config.py
│   ├── rag/            # RAG agentic: orchestrator, tools, PolicyEngine, traces
│   ├── graph/          # Grafo de conceitos (X-Ray, livros relacionados)
│   ├── tts/            # TTS: router, Kokoro/Piper, pré-síntese
│   └── audio/          # Player contínuo de narração
├── readers/        # Leitores de formato: PDF, EPUB, DOCX, TXT/MD (factory)
├── gui/            # Interface PyQt6
│   ├── main_window.py / reader_view.py / library_view.py / sidebar.py / styles.py
│   ├── dialogs/        # Configurações, importação, dossiê, flashcards, atalhos…
│   ├── widgets/        # Cards, painéis (RAG, anotações, insights), overlays
│   └── workers/        # Threads de IA, áudio e indexação
├── mcp/            # Servidor MCP local (stdio)
├── tools/          # build_package, manual, trace_inspector, eval harness
├── utils/          # Utilitários
└── main.py         # Entry point
tests/              # Suíte pytest (1590+ testes)
```

## 🛠️ Utilitários de Operabilidade (CLI)

O projeto conta com ferramentas dedicadas via linha de comando para governança e inspeção do Agentic RAG:

- **Housekeeping de Traces (Limpeza)**:
  Mantém o disco limpo restringindo a pasta `data/traces/` aos últimos 100 arquivos criados.
  ```bash
  python -m src.core.rag.trace_retention --max 100
  ```

- **Trace Inspector (Inspeção e Debug)**:
  Explore sessões armazenadas do assistente de forma legível.
  ```bash
  python -m src.tools.trace_inspector --list
  python -m src.tools.trace_inspector --session <session_id>
  python -m src.tools.trace_inspector --errors
  ```

- **Evaluation Harness (Testes Estruturais)**:
  Analisa os traces buscando falhas lógicas no pipeline, quebras de policy ou sessões anômalas.
  ```bash
  python -m src.tools.rag_eval_harness
  ```

## 🔌 Servidor MCP (integração com LLMs)

O app expõe a biblioteca a hosts MCP (Claude Desktop/Code ou outro cliente
compatível) via um servidor local **stdio** — sem rede.

- **Leitura (sempre disponível):** explorar livros, buscas (metadados,
  full-text e semântica), texto de páginas (máx. 10 por chamada), anotações e
  estatísticas; `ask_library` consulta o RAG local (Ollama + Chroma) com
  citações resolvidas — pode levar minutos (o modelo local "pensa" antes).
- **Escrita (opcional, desligada por padrão):** notas da IA (`ai_note` com
  origem `mcp`), tags, coleções, status de leitura e favorito — tudo
  **aditivo**, nada destrutivo. Para ativar, edite `data/config.json` com
  `{"mcp": {"allow_writes": true}}` (vale na hora, sem reiniciar o servidor).

O caminho fácil: **⚙️ Configurações → 🔌 Integrações** dentro do app — o
comando de registro (com os caminhos da sua máquina), o bloco `mcpServers`
para outros hosts (Cursor, VS Code, Gemini CLI…) e a chave de escrita
(`mcp.allow_writes`) estão lá, com botões de copiar.

Registro manual no Claude Code (Windows — use o python do venv do projeto; o
`PYTHONPATH` garante que `src.mcp.server` resolva a partir de qualquer pasta):

```bash
claude mcp add biblioteca -e "PYTHONPATH=G:\PROGRAMAS PYTHON\Biblioteca-pessoal" -- "G:\PROGRAMAS PYTHON\Biblioteca-pessoal\venv\Scripts\python.exe" -m src.mcp.server
```

Observações:
- O servidor abre o mesmo `data/library.db` do app (SQLite em WAL): pode rodar
  com o app aberto; a escrita de índices (RAG/FTS) continua exclusiva do app.
- A busca semântica exige o Ollama local em execução; sem ele a ferramenta
  devolve um erro amigável (nada trava).

## 🧪 Testes

Sempre pelo python do venv do projeto:

```bash
# Windows
venv\Scripts\python.exe -m pytest tests/ -q

# Linux / macOS
./venv/bin/python -m pytest tests/ -q

# Com coverage
venv\Scripts\python.exe -m pytest tests/ --cov=src --cov-report=html
```

## 📄 Licença

MIT License
