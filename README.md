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

# Crie o ambiente virtual
python -m venv venv

# Ative o ambiente (Windows)
venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt

# Execute a aplicação
python -m src.main
```

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
