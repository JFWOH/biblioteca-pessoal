"""Dossiê do livro (Fase 4 — roadmap memória/grafo).

Agrega, em leituras baratas de SQLite, tudo que o app já sabe sobre um livro
(metadados, progresso de leitura, grafo de conceitos, cobertura da ingestão e
anotações) e monta o prompt da síntese em texto. Core puro, sem PyQt6
(ADR-006); apenas LÊ dados já ingeridos — nunca dispara ingestão/indexação.
"""

from __future__ import annotations

import hashlib

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore

# Tamanho do trecho de anotação exibido no dossiê.
_ANNOTATION_SNIPPET_LEN = 160
_RECENT_ANNOTATIONS = 3

_SYNTHESIS_PROMPT = (
    "Você é o assistente de uma biblioteca pessoal. Com base APENAS nos dados "
    "abaixo, escreva UM parágrafo curto (3 a 5 frases), em português, situando "
    "este livro na biblioteca do leitor: os temas centrais, como ele se "
    "conecta aos outros livros e, quando fizer sentido, o perfil de leitura "
    "deste leitor (progresso e anotações). Não invente fatos que não estejam "
    "nos dados.{partial}\n\n"
    "DADOS:\n{facts}\n\n"
    "Responda apenas com o parágrafo, sem título nem marcadores."
)


def build_dossier_data(db: LibraryDB, graph_store: GraphStore,
                       book_id: int) -> dict | None:
    """Agrega o dossiê do livro em uma passada (leituras baratas).

    Devolve ``None`` se o livro não existir. Grafo vazio não é erro: as
    listas vêm vazias e a GUI decide como degradar (ADR-005).
    """
    book = db.get_book(book_id)
    if not book:
        return None
    annotations = db.get_annotations(book_id)
    # Mais recentes primeiro; empate de timestamp desempatado pelo id.
    recent = sorted(
        annotations,
        key=lambda a: (a.get("created_at") or "", a.get("id") or 0),
        reverse=True,
    )[:_RECENT_ANNOTATIONS]
    # Contagem por tipo (highlight/note/ai_note/...) — perfil real do leitor
    # (Tarefa 3.9), usada na seção "perfil do leitor" do prompt de síntese.
    annotations_by_type: dict[str, int] = {}
    for a in annotations:
        kind = (a.get("annotation_type") or "outro").strip() or "outro"
        annotations_by_type[kind] = annotations_by_type.get(kind, 0) + 1
    return {
        "book": book,
        "progress": db.get_reading_progress(book_id),
        "concepts": graph_store.get_book_concepts(book_id, limit=15),
        "related": graph_store.related_books(book_id, limit=5),
        "coverage": graph_store.coverage(book_id),
        "annotations_total": len(annotations),
        "annotations_by_type": annotations_by_type,
        "annotations_recent": [
            {
                "title": a.get("title") or "",
                "content": (a.get("content") or "")[:_ANNOTATION_SNIPPET_LEN],
                "page_number": a.get("page_number"),
            }
            for a in recent
        ],
    }


def coverage_percent(coverage: dict | None) -> int | None:
    """Percentual de páginas processadas, ou ``None`` se desconhecido."""
    if not coverage or not coverage.get("pages_total"):
        return None
    pct = coverage["pages_done"] / coverage["pages_total"] * 100
    return min(100, int(round(pct)))


def format_coverage_label(coverage: dict | None) -> str:
    """Linha de confiança do dossiê, ex.: 'baseado em 60% das páginas…'."""
    pct = coverage_percent(coverage)
    if pct is None:
        return "cobertura desconhecida"
    done = coverage.get("pages_done", 0)
    total = coverage.get("pages_total", 0)
    if done == 0:
        return "livro ainda não processado pelo grafo"
    return f"baseado em {pct}% das páginas processadas ({done} de {total})"


def _format_reader_profile(data: dict) -> str:
    """Linha "Perfil do leitor": progresso real + anotações (Tarefa 3.9).

    Usa só o que já veio de ``build_dossier_data`` (``progress``,
    ``annotations_by_type``, ``annotations_recent``) — nenhuma leitura extra
    ao banco. Degrada graciosamente (ADR-005): sem progresso/anotações, a
    linha ainda sai, só com os fatos neutros ("leitura ainda não iniciada").
    """
    progress = data.get("progress") or {}
    parts = []
    pct = progress.get("percentage")
    if pct is not None:
        page = progress.get("current_page")
        total = progress.get("total_pages")
        page_part = f", página {page} de {total}" if page is not None and total else ""
        parts.append(f"{int(round(pct))}% lido{page_part}")
    time_spent = progress.get("time_spent_seconds") or 0
    if time_spent:
        parts.append(f"{int(time_spent) // 60} min de leitura acumulados")
    progress_line = "; ".join(parts) if parts else "leitura ainda não iniciada"

    by_type = data.get("annotations_by_type") or {}
    if by_type:
        counts = ", ".join(
            f"{n} {kind}" for kind, n in sorted(by_type.items(), key=lambda kv: -kv[1]))
        annotations_line = f"anotações do leitor: {counts}"
    else:
        annotations_line = "nenhuma anotação registrada"

    lines = [f"Progresso de leitura: {progress_line}.", f"Anotações: {annotations_line}."]
    recent = data.get("annotations_recent") or []
    snippets = "; ".join(
        f"\"{(a.get('content') or '').strip()}\"" for a in recent if (a.get("content") or "").strip())
    if snippets:
        lines.append(f"Trechos recentes destacados/anotados pelo leitor: {snippets}.")
    return " ".join(lines)


def build_dossier_synthesis_prompt(data: dict | None) -> str | None:
    """Prompt da síntese em texto do dossiê.

    ``None`` quando não há conceitos — sem grafo não há o que sintetizar
    (o chamador simplesmente não dispara o LLM).
    """
    if not data or not data.get("concepts"):
        return None
    book = data.get("book") or {}
    facts = []
    title = book.get("title") or "Sem título"
    author = book.get("author") or ""
    facts.append(f"Livro: {title}" + (f" — {author}" if author else ""))
    facts.append("Conceitos centrais: " + "; ".join(
        f"{c['display_name']} ({int(c.get('mentions') or 0)} menções)"
        for c in data["concepts"]))
    related = data.get("related") or []
    if related:
        facts.append("Livros relacionados: " + "; ".join(
            f"\"{r['title']}\" (em comum: {', '.join(r.get('shared') or [])})"
            for r in related))
    facts.append("Cobertura da análise: " + format_coverage_label(data.get("coverage")))
    # Perfil do leitor (Tarefa 3.9): progresso real + anotações — o dossiê
    # não tinha essa seção; agora a síntese pode personalizar sutilmente
    # (sem inventar fatos — a instrução principal já veda isso).
    facts.append("Perfil do leitor: " + _format_reader_profile(data))

    pct = coverage_percent(data.get("coverage"))
    partial = ""
    if pct is not None and pct < 50:
        partial = (" A análise cobre menos da metade das páginas — deixe claro "
                   "que a visão ainda é parcial.")
    return _SYNTHESIS_PROMPT.format(partial=partial, facts="\n".join(facts))


def _profile_fingerprint(db: LibraryDB, book_id: int) -> str:
    """Hash barato (12 chars) do perfil do leitor: progresso + nº de anotações.

    Tarefa 3.9, opção (a): o cache da síntese (fingerprint só do grafo) não
    invalidava quando o leitor avançava a leitura ou anotava algo novo — a
    seção "perfil do leitor" do prompt ficava presa ao estado de quando a
    síntese foi gerada. Compõe-se com ``ingest_fingerprint`` do grafo em
    :func:`_composite_fingerprint`. Custo: 2 leituras SQLite baratas
    (reading_progress + COUNT de annotations) a cada abertura do dossiê —
    aceitável frente ao ganho de manter o perfil atualizado (mesma ordem de
    grandeza das leituras já feitas por ``build_dossier_data``).
    """
    progress = db.get_reading_progress(book_id) or {}
    annotations_total = len(db.get_annotations(book_id))
    raw = f"{progress.get('current_page', 0)}:{progress.get('percentage', 0)}:{annotations_total}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _composite_fingerprint(db: LibraryDB, graph_store: GraphStore, book_id: int) -> str:
    """Fingerprint do cache: cobertura do grafo + perfil do leitor (3.9)."""
    return f"{graph_store.ingest_fingerprint(book_id)}:{_profile_fingerprint(db, book_id)}"


def get_cached_synthesis(db: LibraryDB, graph_store: GraphStore, book_id: int) -> str | None:
    """Síntese em cache, se a cobertura de ingestão E o perfil do leitor
    (progresso/anotações) não mudaram desde então.

    Evita chamar o LLM a cada abertura do dossiê (§1.5 da revisão de
    engenharia 2026-07-05): a síntese só precisa mudar quando o grafo ingere
    algo novo do livro OU o perfil do leitor muda significativamente
    (Tarefa 3.9) — não a cada clique.
    """
    cached = db.get_dossier_synthesis_cache(book_id)
    if not cached:
        return None
    if cached["fingerprint"] != _composite_fingerprint(db, graph_store, book_id):
        return None
    return cached["synthesis"]


def save_synthesis_cache(db: LibraryDB, graph_store: GraphStore,
                         book_id: int, text: str) -> None:
    """Grava a síntese com a fingerprint composta atual (chave de invalidação)."""
    db.set_dossier_synthesis_cache(book_id, _composite_fingerprint(db, graph_store, book_id), text)
