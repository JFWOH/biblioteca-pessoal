"""Continuidade do agente proativo (Fase 5 do roadmap de grafo/memória).

O proativo persiste toda observação em ``ai_observations`` (Fase 1b), mas
até agora nunca as consultava — podia repetir a mesma observação ao reler
uma página em outra sessão e ignorava a memória acumulada do livro. Este
módulo é a lógica PURA da continuidade (ADR-006: sem Qt, sem SQLite — as
observações chegam como dicts injetados pela camada GUI):

- :func:`already_observed_page` — a página já tem observação viva? (skip)
- :func:`build_memory_block` — bloco de prompt com o que já foi dito.

Contrato: docs/agents/proativo_continuidade_execution_contract.md.
"""

_MEMORY_HEADER = (
    "VOCÊ JÁ FEZ AS OBSERVAÇÕES ABAIXO NESTE LIVRO. NÃO as repita nem as "
    "parafraseie — traga um ângulo NOVO ou comente outro aspecto do trecho:"
)


def already_observed_page(observations: list[dict]) -> bool:
    """True se há observação NÃO dispensada na lista (observações da página).

    O chamador normalmente já filtra dispensadas na consulta
    (``include_dismissed=False``); o re-check aqui torna a função correta
    para qualquer lista.
    """
    return any(not o.get("dismissed") for o in (observations or []))


def build_memory_block(observations: list[dict], max_items: int = 5,
                       max_chars_each: int = 160) -> str:
    """Bloco de memória para o prompt do proativo ("" se não há o que lembrar).

    Espera as observações em ordem da mais recente para a mais antiga (como
    ``LibraryDB.get_observations`` devolve) e preserva essa ordem.
    """
    lines = []
    for obs in (observations or [])[:max_items]:
        content = (obs.get("content") or "").strip()
        if not content:
            continue
        if len(content) > max_chars_each:
            content = content[:max_chars_each - 1].rstrip() + "…"
        page = obs.get("page")
        prefix = f"(p.{page}) " if page else ""
        lines.append(f"- {prefix}{content}")
    if not lines:
        return ""
    return _MEMORY_HEADER + "\n" + "\n".join(lines)
