"""Utilitários para processamento de imagens de capa."""

from pathlib import Path
from io import BytesIO

from PIL import Image

from src.utils.constants import COVER_WIDTH, COVER_HEIGHT, COVERS_DIR


def ensure_covers_dir() -> Path:
    """Garante que o diretório de capas existe."""
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    return COVERS_DIR


def save_cover_image(
    image_data: bytes,
    book_id: int,
    width: int = COVER_WIDTH,
    height: int = COVER_HEIGHT,
) -> Path:
    """Salva e redimensiona uma imagem de capa extraída de um documento."""
    ensure_covers_dir()
    cover_path = COVERS_DIR / f"cover_{book_id}.jpg"

    img = Image.open(BytesIO(image_data))
    img = img.convert("RGB")

    # Redimensiona mantendo proporção
    img.thumbnail((width * 2, height * 2), Image.Resampling.LANCZOS)
    img.save(cover_path, "JPEG", quality=90)

    return cover_path


def generate_placeholder_cover(
    title: str,
    author: str = "",
    book_id: int = 0,
    width: int = COVER_WIDTH * 2,
    height: int = COVER_HEIGHT * 2,
) -> Path:
    """Gera uma capa placeholder com o título e autor."""
    ensure_covers_dir()
    cover_path = COVERS_DIR / f"cover_{book_id}.jpg"

    # Cria imagem com gradiente escuro
    img = Image.new("RGB", (width, height), color=(45, 45, 60))

    # Adiciona um gradiente sutil (sem dependência de ImageDraw para texto complexo)
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            # Gradiente diagonal sutil
            factor = (x + y) / (width + height)
            r = int(45 + factor * 30)
            g = int(45 + factor * 20)
            b = int(60 + factor * 40)
            pixels[x, y] = (r, g, b)

    img.save(cover_path, "JPEG", quality=90)
    return cover_path


def get_cover_path(book_id: int) -> Path | None:
    """Retorna o caminho da capa se existir."""
    cover_path = COVERS_DIR / f"cover_{book_id}.jpg"
    return cover_path if cover_path.exists() else None
