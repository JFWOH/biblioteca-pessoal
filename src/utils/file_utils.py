"""Utilitários para operações com arquivos."""

from pathlib import Path
import hashlib
import shutil

from src.utils.constants import SUPPORTED_EXTENSIONS


def get_file_extension(filepath: str | Path) -> str:
    """Retorna a extensão do arquivo em minúsculas, sem ponto."""
    return Path(filepath).suffix.lstrip(".").lower()


def is_supported_format(filepath: str | Path) -> bool:
    """Verifica se o formato do arquivo é suportado."""
    return get_file_extension(filepath) in SUPPORTED_EXTENSIONS


def calculate_file_hash(filepath: str | Path, algorithm: str = "sha256") -> str:
    """Calcula o hash do arquivo para detecção de duplicatas."""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def get_file_size(filepath: str | Path) -> int:
    """Retorna o tamanho do arquivo em bytes."""
    return Path(filepath).stat().st_size


def format_file_size(size_bytes: int) -> str:
    """Formata o tamanho do arquivo para exibição humana."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.1f} GB"


def safe_copy(source: str | Path, destination: str | Path) -> Path:
    """Copia um arquivo de forma segura, criando diretórios se necessário."""
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(source, dest))


def find_documents(directory: str | Path, recursive: bool = True) -> list[Path]:
    """Encontra todos os documentos suportados em um diretório."""
    path = Path(directory)
    if not path.is_dir():
        return []

    documents = []
    pattern_func = path.rglob if recursive else path.glob
    for ext in SUPPORTED_EXTENSIONS:
        documents.extend(pattern_func(f"*.{ext}"))

    return sorted(documents)
