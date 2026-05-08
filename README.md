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
tests/              # 48 testes automatizados
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
