"""Cross-reference do agente proativo: conecta a página a outros livros.

Lógica pura (sem GUI / sem rede): recebe os hits de uma busca vetorial e
devolve uma nota de conexão para o livro MAIS relevante diferente do atual,
ou None. A busca em si é injetada (roda na thread do worker).
"""

from __future__ import annotations

from typing import Optional


def format_cross_reference(hits, current_book_id, min_similarity: float = 0.5) -> Optional[str]:
    """Monta a nota de conexão para o melhor hit em OUTRO livro.

    Args:
        hits: lista de dicts {metadata: {book_id, title, page_number}, distance}.
        current_book_id: livro atual (excluído da conexão).
        min_similarity: similaridade mínima (1 - distância de cosseno) para conectar.

    Returns:
        Texto da conexão (ex.: 'também aparece em ...') ou None.
    """
    best = None  # (similaridade, título, página)
    for hit in hits or []:
        meta = hit.get("metadata", {}) or {}
        book_id = meta.get("book_id")
        if book_id == current_book_id:
            continue
        dist = hit.get("distance")
        if not isinstance(dist, (int, float)) or isinstance(dist, bool):
            continue
        sim = 1.0 - dist
        if sim < min_similarity:
            continue
        if best is None or sim > best[0]:
            title = (meta.get("title") or "").strip() or "outro livro"
            page = (meta.get("page_number") or 0) + 1
            best = (sim, title, page)

    if best is None:
        return None
    return f"🔗 Conexão: este tema também aparece em “{best[1]}” (p. {best[2]})."
