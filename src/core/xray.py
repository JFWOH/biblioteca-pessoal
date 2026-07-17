"""Interseção página × conceitos do livro para o painel X-Ray (Tarefa 3.2).

Módulo PURO (ADR-006 — sem Qt, sem LLM, sem rede). Dado o texto de uma página e
os conceitos do livro (vindos do grafo — ``graph_book_concepts``), devolve os
conceitos que efetivamente aparecem NA PÁGINA. O casamento é tolerante a caixa e
acentos e por palavra inteira, evitando falsos positivos por substring
(ex.: 'arte' dentro de 'Bonaparte').

A GUI (``xray_panel``) só orquestra: busca os conceitos do livro (1x, cacheado),
chama :func:`page_concepts` a cada virada de página (barato — string matching) e,
sob demanda, consulta ``graph_concept_lookup`` para "onde mais o conceito aparece".
"""

from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    """casefold + remove acentos (NFKD) + colapsa espaços."""
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())


def concept_in_text(concept: str, normalized_text: str) -> bool:
    """True se *concept* aparece como palavra(s) inteira(s) em *normalized_text*.

    *normalized_text* já deve estar normalizado (ver :func:`normalize`)."""
    norm = normalize(concept)
    if not norm:
        return False
    return re.search(r"(?<!\w)" + re.escape(norm) + r"(?!\w)", normalized_text) is not None


def page_concepts(
    page_text: str,
    book_concepts: list,
    *,
    name_key: str = "concept",
) -> list:
    """Subconjunto de *book_concepts* cujo nome aparece em *page_text*.

    Preserva a ordem de entrada (tipicamente por peso decrescente, como vem de
    ``graph_book_concepts``). Cada item de *book_concepts* pode ser um dict (o
    nome fica em ``item[name_key]``) ou uma string. Página vazia ou lista vazia
    → ``[]``.
    """
    normalized = normalize(page_text)
    if not normalized:
        return []
    matched: list = []
    for c in book_concepts:
        name = c.get(name_key) if isinstance(c, dict) else c
        if name and concept_in_text(name, normalized):
            matched.append(c)
    return matched
