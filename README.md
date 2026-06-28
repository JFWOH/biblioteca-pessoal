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
- Importação em lote com detecção automática de duplicatas (SHA-256)
- Extração automática de metadados (título, autor, capa, páginas)
- Busca full-text ultrarrápida via **SQLite FTS5**
- Coleções e tags personalizáveis
- Avaliação com estrelas interativa (0-5)
- Progresso de leitura persistido

### 📝 Anotações e Destaques
- Notas de texto por página
- Marcadores de página
- Seleção de cores para destaques
- Navegação rápida entre anotações

### 🎨 Interface Premium
- 3 temas: **Escuro**, **Claro** e **Sépia**
- Visualização em grade com capas extraídas automaticamente
- Busca dentro do documento (Ctrl+F)
- Modo tela cheia (F11)
- Painel de estatísticas com dashboard visual
- Diálogos ricos para importação e configurações

### 🤖 Agentic RAG & Governança
- Assistente local com inteligência contextual capaz de buscas vetoriais, pesquisas na web e referências cruzadas.
- **UI Mutators Seguros**: A IA interage com a GUI (marcadores automáticos, texto destacado) validada estritamente pelo **Policy Engine** (ADR-003).
- **Trace Logger**: Log estruturado das sessões do RAG persistido localmente em JSONL (ADR-004).

### 🌐 Tradução Offline Local-First
- Tradução de trechos selecionados (em PDFs escaneados com OCR ou EPUBs) suportada pelo modelo **NLLB-200** (`facebook/nllb-200-distilled-600M`).
- **Limites e Hardware**: Operação em GPU/CPU otimizada (~1.2GB VRAM). Texto limitado a blocos curtos (máximo 2000 caracteres por disparo) para prevenir travamentos (Graceful Fallback incluído). Processamento ocorre 100% fora da Main Thread da UI.
- **Ressalva Offline**: A operação é offline, porém **exige obrigatoriamente conexão à internet na primeira execução** para efetuar o download/bootstrap dos pesos do modelo para a cache local. Em seguida, roda 100% localmente sem qualquer envio de dados do usuário.

## 🚀 Instalação

```bash
# Clone o repositório
git clone <repo-url>
cd Biblioteca-pessoal

# Crie o ambiente virtual (use o Python 3.11 do sistema)
C:\Users\jefer\AppData\Local\Programs\Python\Python311\python.exe -m venv venv

# Instale as dependências
venv\Scripts\python.exe -m pip install -r requirements.txt
```

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

A forma mais simples é usar o script de inicialização na raiz do projeto:

```
iniciar.bat
```

Ou manualmente no PowerShell:

```powershell
cd "G:\PROGRAMAS PYTHON\Biblioteca-pessoal"
.\venv\Scripts\Activate.ps1
python -m src.main
```

> **Importante — múltiplos interpretadores no sistema**
>
> Esta máquina tem 5 instalações de Python no PATH:
>
> | # | Caminho | Status |
> |---|---------|--------|
> | 1 | `G:\PROGRAMAS PYTHON\Biblioteca-pessoal\venv\Scripts\python.exe` | ✅ correto — venv do projeto |
> | 2 | `H:\PYTHON\assistente-virtual\venv\Scripts\python.exe` | ❌ torch corrompido (WinError 193) |
> | 3 | `C:\Users\jefer\AppData\Local\Programs\Python\Python311\python.exe` | base do sistema |
> | 4 | `H:\ANACONDA\python.exe` | Anaconda |
> | 5 | `C:\Users\jefer\AppData\Local\Microsoft\WindowsApps\python.exe` | stub da Store |
>
> **Nunca** rodar `python -m src.main` sem ativar o venv do projeto primeiro — o intérprete de `H:\PYTHON\assistente-virtual\venv` aparece em 2º no PATH global e travará o app com erro de DLL ao importar `torch`.
>
> Para verificar qual intérprete está ativo:
> ```powershell
> python -c "import sys; print(sys.executable)"
> # deve retornar: G:\PROGRAMAS PYTHON\Biblioteca-pessoal\venv\Scripts\python.exe
> ```

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
| `Ctrl+I` | Importar documentos |
| `Ctrl+O` | Importação rápida |
| `Ctrl+F` | Buscar no documento |
| `Ctrl+,` | Configurações |
| `F11` | Tela cheia |
| `←` / `→` | Página anterior / próxima |
| `Ctrl++` / `Ctrl+-` | Zoom in / out |
| `Escape` | Voltar / sair de tela cheia |

## 🏗 Arquitetura

```
src/
├── core/           # Lógica de negócio
│   ├── database.py     # SQLite + FTS5
│   ├── library.py      # Gerenciamento de livros
│   ├── metadata.py     # Extração de metadados
│   ├── search.py       # Motor de busca
│   └── config.py       # Configurações persistentes
├── readers/        # Leitores de formato
│   ├── base_reader.py  # Interface abstrata
│   ├── pdf_reader.py   # PyMuPDF
│   ├── epub_reader.py  # EbookLib
│   ├── docx_reader.py  # python-docx
│   ├── txt_reader.py   # TXT/Markdown
│   └── reader_factory.py  # Factory pattern
├── gui/            # Interface gráfica
│   ├── main_window.py  # Janela principal
│   ├── reader_view.py  # Visualizador de documentos
│   ├── library_view.py # Grade de livros
│   ├── sidebar.py      # Navegação lateral
│   ├── styles.py       # Temas CSS/QSS
│   └── widgets/        # Componentes reutilizáveis
│       ├── annotation_panel.py
│       ├── book_card.py
│       ├── cover_widget.py
│       ├── reading_progress.py
│       ├── search_overlay.py
│       ├── star_rating.py
│       ├── stats_panel.py
│       └── toc_widget.py
├── utils/          # Utilitários
└── main.py         # Entry point
tests/              # Testes automatizados (pytest)
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

## 🧪 Testes

```bash
# Executar todos os testes
python -m pytest tests/ -v

# Com coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## 📄 Licença

MIT License
