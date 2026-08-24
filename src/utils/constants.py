"""Constantes globais da aplicação."""

from pathlib import Path

# ── Diretórios ─────────────────────────────────────────────────────────
APP_NAME = "Biblioteca Pessoal"
APP_VERSION = "0.1.0"
APP_AUTHOR = "Jefferson"

# Raiz do projeto (pasta onde está src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Diretório de dados (criado em runtime)
DATA_DIR = PROJECT_ROOT / "data"
COVERS_DIR = DATA_DIR / "covers"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "library.db"

# Diretório de recursos
RESOURCES_DIR = PROJECT_ROOT / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
THEMES_DIR = RESOURCES_DIR / "themes"

# ── Formatos suportados ───────────────────────────────────────────────
SUPPORTED_FORMATS = {
    "pdf": "Documento PDF",
    "epub": "Livro EPUB",
    "mobi": "Livro MOBI",
    "azw": "Livro Kindle (AZW)",
    "azw3": "Livro Kindle (AZW3)",
    "txt": "Texto Simples",
    "md": "Markdown",
    "docx": "Documento Word",
    "cbz": "Quadrinhos (CBZ)",
    "cbr": "Quadrinhos (CBR)",
    "fb2": "FictionBook (FB2)",
}

SUPPORTED_EXTENSIONS = set(SUPPORTED_FORMATS.keys())

# Filtro para diálogos de arquivo
FILE_FILTER = "Documentos Suportados ({});;".format(
    " ".join(f"*.{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
) + ";;".join(
    f"{desc} (*.{ext})" for ext, desc in sorted(SUPPORTED_FORMATS.items())
) + ";;Todos os arquivos (*)"

# ── Categorias de formato ─────────────────────────────────────────────
PDF_FORMATS = {"pdf"}
EPUB_FORMATS = {"epub"}
MOBI_FORMATS = {"mobi", "azw", "azw3"}
TEXT_FORMATS = {"txt", "md"}
DOCX_FORMATS = {"docx"}
COMIC_FORMATS = {"cbz", "cbr"}

# ── Configurações de leitura ──────────────────────────────────────────
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 48
DEFAULT_FONT_FAMILY = "Georgia"
DEFAULT_LINE_HEIGHT = 1.6

# ── Status de leitura ────────────────────────────────────────────────
READ_STATUS_UNREAD = "unread"
READ_STATUS_READING = "reading"
READ_STATUS_READ = "read"

READ_STATUS_LABELS = {
    READ_STATUS_UNREAD: "Não lido",
    READ_STATUS_READING: "Lendo",
    READ_STATUS_READ: "Lido",
}

# ── Temas ─────────────────────────────────────────────────────────────
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SEPIA = "sepia"

# ── Tamanhos de grid/card ────────────────────────────────────────────
COVER_WIDTH = 160
COVER_HEIGHT = 220
CARD_WIDTH = 180
CARD_HEIGHT = 300
GRID_SPACING = 20
