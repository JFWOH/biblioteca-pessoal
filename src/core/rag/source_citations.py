"""Parser e resolvedor de citações ``[Título, p. X]`` das respostas do RAG.

Módulo PURO (ADR-006 — sem Qt, sem rede, sem LLM). O prompt do RAG exige que as
respostas citem as fontes no formato ``[Título, p. X]``; aqui extraímos essas
citações e resolvemos o *título* para um ``book_id`` via *fuzzy match* tolerante
a caixa e acentos contra a lista de livros do banco (``db.get_all_books()``).

A GUI (``rag_panel``) usa isto para tornar as fontes clicáveis. Título não
resolvido → ``book_id`` ``None`` (item não clicável) — degradação graciosa
(ADR-005), nunca quebra a UI.

A ``page`` retornada é a que aparece na citação (1-based, voltada ao usuário); a
conversão para a página 0-based do leitor é responsabilidade de quem navega.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

# Regex tolerante:
# - título com vírgulas/acentos/pontuação (qualquer coisa menos colchetes),
#   casado de forma NÃO-gulosa até a última vírgula antes do marcador de página;
# - marcador de página: p / pp / pág / pag / pg / página / pagina, com "." opcional;
# - número de página inteiro.
_CITATION_RE = re.compile(
    r"\[\s*"
    r"(?P<title>[^\[\]]+?)\s*,\s*"
    r"(?:p{1,2}|p[áa]g(?:\.|ina)?|pg)\.?\s*"
    r"(?P<page>\d+)"
    r"\s*\]",
    re.IGNORECASE,
)

# Limiar de similaridade para aceitar um casamento aproximado de título.
_DEFAULT_THRESHOLD = 0.82


@dataclass(frozen=True)
class Citation:
    """Uma citação ``[Título, p. X]`` encontrada no texto da resposta."""

    title: str   # título exatamente como escrito na citação
    page: int    # número de página como escrito (1-based, voltado ao usuário)
    start: int   # índice inicial do trecho no texto (para linkificação futura)
    end: int     # índice final (exclusivo)
    raw: str     # trecho cru, ex.: "[Dom Casmurro, p. 12]"


def normalize(text: str) -> str:
    """casefold + remove acentos (NFKD) + colapsa espaços — casamento robusto."""
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())


def parse_citations(text: str) -> list[Citation]:
    """Extrai todas as citações ``[Título, p. X]`` de *text*, na ordem em que
    aparecem. Texto vazio ou sem citações → lista vazia."""
    out: list[Citation] = []
    for m in _CITATION_RE.finditer(text or ""):
        title = m.group("title").strip()
        if not title:
            continue
        try:
            page = int(m.group("page"))
        except (TypeError, ValueError):
            continue
        out.append(Citation(
            title=title, page=page,
            start=m.start(), end=m.end(), raw=m.group(0),
        ))
    return out


def _word_contained(short: str, long_: str) -> bool:
    """True se *short* aparece como palavra(s) inteira(s) dentro de *long_*.

    Evita falsos positivos por substring (ex.: 'arte' em 'bonaparte')."""
    if not short:
        return False
    return re.search(r"(?<!\w)" + re.escape(short) + r"(?!\w)", long_) is not None


def resolve_citation(
    citation: Citation,
    books: list[dict],
    *,
    threshold: float = _DEFAULT_THRESHOLD,
) -> tuple[int | None, int]:
    """Resolve o título da citação para ``(book_id, page)``.

    *books* é a lista de ``db.get_all_books()`` (dicts com ao menos ``id`` e
    ``title``). Estratégia: casamento normalizado exato → contenção por palavra
    inteira → similaridade ``difflib``. Sem casamento acima de *threshold* →
    ``(None, page)`` (degradação graciosa).
    """
    want = normalize(citation.title)
    if not want:
        return None, citation.page

    best_id: int | None = None
    best_score = 0.0
    for b in books:
        bid = b.get("id")
        if bid is None:
            continue
        norm = normalize(b.get("title") or "")
        if not norm:
            continue
        if norm == want:
            return int(bid), citation.page
        score = difflib.SequenceMatcher(None, want, norm).ratio()
        if _word_contained(want, norm) or _word_contained(norm, want):
            score = max(score, 0.9)
        if score > best_score:
            best_score, best_id = score, int(bid)

    if best_id is not None and best_score >= threshold:
        return best_id, citation.page
    return None, citation.page
