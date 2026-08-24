"""Cache em disco das miniaturas do sumário (Onda P — rodada UX ago/2026).

Núcleo puro (ADR-006): nada aqui importa PyQt6 — o cache é só hash + arquivo.
"""

import os
import time

import pytest

from src.core.thumbnail_cache import ThumbnailCache


PNG = b"\x89PNG\r\n\x1a\n" + b"conteudo falso de miniatura"


@pytest.fixture
def livro(tmp_path):
    p = tmp_path / "livro.pdf"
    p.write_bytes(b"%PDF-1.7\n" + b"x" * 500)
    return p


@pytest.fixture
def cache(tmp_path):
    return ThumbnailCache(cache_dir=tmp_path / "thumbs")


# ── Gravar e ler ──────────────────────────────────────────────────────

def test_miss_antes_de_gravar(cache, livro):
    assert cache.get(livro, 0, 110) is None


def test_grava_e_le_a_mesma_miniatura(cache, livro):
    assert cache.put(livro, 3, 110, PNG) is True
    assert cache.get(livro, 3, 110) == PNG


def test_pagina_e_largura_fazem_parte_da_chave(cache, livro):
    cache.put(livro, 3, 110, PNG)
    assert cache.get(livro, 4, 110) is None    # outra página
    assert cache.get(livro, 3, 220) is None    # outra largura
    assert cache.key(livro, 3, 110) != cache.key(livro, 4, 110)
    assert cache.key(livro, 3, 110) != cache.key(livro, 3, 220)


def test_png_vazio_nao_e_gravado(cache, livro):
    assert cache.put(livro, 0, 110, b"") is False
    assert cache.get(livro, 0, 110) is None


# ── Invalidação pela identidade do arquivo ────────────────────────────

def test_chave_muda_quando_o_arquivo_muda(cache, livro):
    antes = cache.key(livro, 0, 110)
    cache.put(livro, 0, 110, PNG)

    # Conteúdo diferente (tamanho + mtime mudam) = livro diferente para o cache.
    time.sleep(0.01)
    livro.write_bytes(b"%PDF-1.7\n" + b"y" * 900)

    assert cache.key(livro, 0, 110) != antes
    assert cache.get(livro, 0, 110) is None  # a miniatura velha não é servida


def test_chave_muda_so_com_o_mtime(cache, livro):
    antes = cache.key(livro, 0, 110)
    novo = time.time() + 120
    os.utime(livro, (novo, novo))
    assert cache.key(livro, 0, 110) != antes


def test_arquivos_diferentes_tem_chaves_diferentes(cache, tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"mesmo conteudo")
    b.write_bytes(b"mesmo conteudo")
    assert cache.key(a, 0, 110) != cache.key(b, 0, 110)


def test_arquivo_inexistente_degrada_sem_levantar(cache, tmp_path):
    fantasma = tmp_path / "nao_existe.pdf"
    assert cache.key(fantasma, 0, 110) is None
    assert cache.get(fantasma, 0, 110) is None
    assert cache.put(fantasma, 0, 110, PNG) is False


# ── Poda ──────────────────────────────────────────────────────────────

def test_poda_mantem_o_teto_e_descarta_os_mais_antigos(tmp_path, livro):
    cache = ThumbnailCache(cache_dir=tmp_path / "thumbs", max_files=5)
    for page in range(12):
        cache.put(livro, page, 110, PNG + bytes([page]))
        # mtimes distintos: a poda ordena por "mais antigo primeiro".
        caminho = cache.directory / f"{cache.key(livro, page, 110)}.png"
        os.utime(caminho, (1_600_000_000 + page, 1_600_000_000 + page))

    assert cache.prune() == 7
    assert len(list(cache.directory.glob("*.png"))) == 5
    assert cache.get(livro, 0, 110) is None    # os mais antigos saíram
    assert cache.get(livro, 11, 110) is not None  # os mais novos ficaram


def test_poda_no_teto_nao_remove_nada(tmp_path, livro):
    cache = ThumbnailCache(cache_dir=tmp_path / "thumbs", max_files=5)
    for page in range(5):
        cache.put(livro, page, 110, PNG)
    assert cache.prune() == 0
    assert len(list(cache.directory.glob("*.png"))) == 5


def test_poda_em_diretorio_inexistente_nao_levanta(tmp_path):
    cache = ThumbnailCache(cache_dir=tmp_path / "nunca_criado")
    assert cache.prune() == 0


# ── Fronteira ADR-006 ─────────────────────────────────────────────────

def test_modulo_do_cache_nao_importa_pyqt6():
    import ast
    from pathlib import Path

    origem = (Path(__file__).resolve().parent.parent
              / "src" / "core" / "thumbnail_cache.py")
    arvore = ast.parse(origem.read_text(encoding="utf-8"), filename=str(origem))
    for node in ast.walk(arvore):
        modulos = ([a.name for a in node.names] if isinstance(node, ast.Import)
                   else [node.module or ""] if isinstance(node, ast.ImportFrom)
                   else [])
        for mod in modulos:
            assert not mod.startswith(("PyQt6", "src.gui")), (
                f"ADR-006: thumbnail_cache.py não pode importar {mod}")
