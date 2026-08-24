"""Continuidade do agente proativo (Fase 5 do roadmap de grafo/memória).

O proativo persiste toda observação em ``ai_observations`` (Fase 1b), mas
até agora nunca as consultava — podia repetir a mesma observação ao reler
uma página em outra sessão e ignorava a memória acumulada do livro. Este
módulo é a lógica PURA da continuidade (ADR-006: sem Qt, sem SQLite — as
observações chegam como dicts injetados pela camada GUI):

- :func:`already_observed_page` — a página já tem observação viva? (skip)
- :func:`build_memory_block` — bloco de prompt com o que já foi dito.
- :func:`page_cache_key` — identidade (livro, página, texto) para o memo de sessão.
- :func:`trim_page_excerpt` — teto do trecho enviado ao modelo.

Contrato: docs/agents/proativo_continuidade_execution_contract.md.
"""

import hashlib

_MEMORY_HEADER = (
    "VOCÊ JÁ FEZ AS OBSERVAÇÕES ABAIXO NESTE LIVRO. NÃO as repita nem as "
    "parafraseie — traga um ângulo NOVO ou comente outro aspecto do trecho:"
)

# Prefixo normalizado usado para reconhecer observações equivalentes dentro do
# bloco de memória: duas observações que começam igual dizem a mesma coisa e
# pagariam tokens duas vezes para lembrar o modelo do mesmo ponto.
_FINGERPRINT_CHARS = 60

# Teto do trecho enviado ao modelo. Páginas normais (~1,5k a 3k chars) passam
# intactas; o teto só corta patologias (OCR de tabelão, página com dump), onde
# o custo por página explodia sem ganho de qualidade na observação.
_MAX_EXCERPT_CHARS = 6000
_EXCERPT_GAP = "\n[…]\n"


def already_observed_page(observations: list[dict]) -> bool:
    """True se há observação NÃO dispensada na lista (observações da página).

    O chamador normalmente já filtra dispensadas na consulta
    (``include_dismissed=False``); o re-check aqui torna a função correta
    para qualquer lista.
    """
    return any(not o.get("dismissed") for o in (observations or []))


def _fingerprint(content: str) -> str:
    """Assinatura normalizada de uma observação (para detectar equivalentes)."""
    return " ".join(content.lower().split())[:_FINGERPRINT_CHARS]


def build_memory_block(observations: list[dict], max_items: int = 5,
                       max_chars_each: int = 160) -> str:
    """Bloco de memória para o prompt do proativo ("" se não há o que lembrar).

    Espera as observações em ordem da mais recente para a mais antiga (como
    ``LibraryDB.get_observations`` devolve) e preserva essa ordem.

    Observações equivalentes (mesmo início, ignorando caixa e espaços) entram
    uma única vez: repeti-las paga tokens para lembrar o modelo do mesmo ponto
    e ainda consome a cota de ``max_items``, expulsando memória de verdade.
    """
    lines = []
    seen: set[str] = set()
    for obs in (observations or []):
        if len(lines) >= max_items:
            break
        content = (obs.get("content") or "").strip()
        if not content:
            continue
        fingerprint = _fingerprint(content)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        if len(content) > max_chars_each:
            content = content[:max_chars_each - 1].rstrip() + "…"
        page = obs.get("page")
        prefix = f"(p.{page}) " if page else ""
        lines.append(f"- {prefix}{content}")
    if not lines:
        return ""
    return _MEMORY_HEADER + "\n" + "\n".join(lines)


def page_cache_key(book_id, page, page_text: str) -> str:
    """Identidade de "esta página, com este texto" para o memo de sessão.

    Inclui o hash do texto para que uma página reprocessada com conteúdo
    diferente (re-OCR, outro layout) volte a ser analisada, e para que o memo
    funcione mesmo sem ``book_id`` (arquivo avulso, sem banco).
    """
    digest = hashlib.sha1(
        " ".join((page_text or "").split()).encode("utf-8", "ignore")
    ).hexdigest()[:16]
    return f"{book_id}:{page}:{digest}"


def trim_page_excerpt(text: str, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    """Limita o trecho enviado ao modelo, preservando começo e fim da página.

    Devolve o texto intacto quando cabe no teto (caso normal). Acima dele,
    mantém a abertura e o fecho da página — as duas pontas onde costuma estar
    o que dá contexto — com uma marca de corte no meio.
    """
    text = text or ""
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.7)
    tail = max_chars - head
    return text[:head].rstrip() + _EXCERPT_GAP + text[-tail:].lstrip()
