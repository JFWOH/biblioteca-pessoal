"""Utilitários puros de sumário (TOC) — item 4 do backlog UX.

Alguns arquivos trazem outlines com entradas-lixo (números de página soltos,
títulos vazios) que poluem o painel de sumário. ``clean_toc`` remove essas
entradas de forma conservadora: só cai o que não tem título útil.
"""

from src.readers.base_reader import TOCEntry

# Pontuação/tracejado comum em volta de números órfãos ("1.", "- 2 -").
_STRIP_CHARS = " .-–—_·:"


def _is_orphan_title(title: str) -> bool:
    """True para títulos sem valor de navegação (vazios ou só número)."""
    text = (title or "").strip()
    if not text:
        return True
    core = text.strip(_STRIP_CHARS)
    return core == "" or core.isdigit()


def clean_toc(entries: list[TOCEntry]) -> list[TOCEntry]:
    """Remove entradas órfãs do sumário (título vazio ou puramente numérico).

    Conservador: "Capítulo 1", "IV. A lógica", "1. Introdução" permanecem —
    só somem entradas cujo título inteiro é um número (ex.: "1", "- 2 -").
    """
    return [e for e in entries if not _is_orphan_title(e.title)]
