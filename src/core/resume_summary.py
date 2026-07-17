"""Mini-resumo da última sessão de leitura (tarefa 3.7 — "Retomar leitura").

Lógica pura (ADR-006 — sem PyQt6/threads): monta, a partir de dados JÁ
existentes, um resumo curto para o banner de retomada quando um livro com
progresso é reaberto. Reaproveita, sem custo de LLM síncrono:

  - ``reading_progress`` (posição / percentual / tempo de leitura);
  - anotações recentes do livro (destaques / notas);
  - conceitos-chave do grafo (opcional, se um ``GraphStore`` for passado);
  - síntese do dossiê JÁ em cache (``get_cached_synthesis`` NUNCA chama o LLM;
    devolve None quando não há cache).

Se a síntese não estiver em cache, o banner sai só com posição + anotações /
conceitos (degradação graciosa — ADR-005). O banner e o timer de auto-fechar
ficam na GUI (``src/gui/widgets/resume_banner.py``).
"""

from __future__ import annotations


def _percent(progress: dict) -> float:
    try:
        return float(progress.get("percentage") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _recent_notes(db, book_id: int, limit: int = 3) -> list[dict]:
    """Últimas anotações do livro (destaques/notas), curtas.

    ``get_annotations`` ordena por (página, created_at); percorremos de trás
    para frente para privilegiar as mais avançadas/recentes. Marcadores
    (bookmarks) são ignorados — não trazem contexto de conteúdo.
    """
    try:
        anns = db.get_annotations(book_id) or []
    except Exception:
        return []
    notes: list[dict] = []
    for ann in reversed(anns):
        atype = ann.get("annotation_type", "highlight")
        if atype == "bookmark":
            continue
        text = (ann.get("content") or ann.get("title") or "").strip()
        if not text:
            continue
        notes.append({
            "type": atype,
            "page": int(ann.get("page_number", 0) or 0),
            "snippet": text[:160],
        })
        if len(notes) >= limit:
            break
    return notes


def _concepts(graph_store, book_id: int, limit: int = 6) -> list[str]:
    """Conceitos-chave do livro segundo o grafo (vazio se sem grafo/erro)."""
    if graph_store is None:
        return []
    try:
        from src.core.rag.tools.graph_tools import graph_book_concepts
        out = graph_book_concepts(graph_store, book_id, limit=limit)
        data = getattr(out, "data", None)
        if data is None and isinstance(out, dict):
            data = out.get("data")
        return [d.get("concept") for d in (data or []) if d.get("concept")]
    except Exception:
        return []


def _cached_synthesis(db, graph_store, book_id: int) -> str | None:
    """Síntese do dossiê em cache (None se ausente) — sem chamar o LLM."""
    if graph_store is None:
        return None
    try:
        from src.core.book_dossier import get_cached_synthesis
        text = get_cached_synthesis(db, graph_store, book_id)
        return (text or "").strip() or None
    except Exception:
        return None


def build_resume_info(db, book_id: int, graph_store=None) -> dict | None:
    """Info para o banner de retomada, ou ``None`` se não há o que retomar.

    Devolve ``None`` quando não há progresso (percentual <= 0) — livro
    novo/nunca aberto não mostra banner.
    """
    if not book_id:
        return None
    try:
        progress = db.get_reading_progress(book_id)
    except Exception:
        progress = None
    if not progress:
        return None
    pct = _percent(progress)
    if pct <= 0:
        return None

    info = {
        "current_page": int(progress.get("current_page") or 0),  # 0-based
        "total_pages": int(progress.get("total_pages") or 0),
        "percentage": pct,
        "time_spent_seconds": int(progress.get("time_spent_seconds") or 0),
        "last_read": progress.get("last_read") or "",
        "recent_notes": _recent_notes(db, book_id),
        "concepts": _concepts(graph_store, book_id),
        "synthesis": _cached_synthesis(db, graph_store, book_id),
    }
    info["summary_line"] = format_resume_summary_line(info)
    return info


def format_resume_summary_line(info: dict) -> str:
    """"Você parou na p. X (N% lido)" — página exibida é 1-based."""
    page = int(info.get("current_page") or 0) + 1
    pct = int(round(float(info.get("percentage") or 0)))
    return f"Você parou na p. {page} ({pct}% lido)"


def format_resume_banner_text(info: dict) -> str:
    """Texto do banner: posição + UM gancho de contexto (curto).

    Prioridade do gancho: síntese em cache → anotação mais recente →
    conceitos-chave. Mantém o banner discreto.
    """
    if not info:
        return ""
    parts = [format_resume_summary_line(info)]
    detail = ""
    synthesis = (info.get("synthesis") or "").strip()
    notes = info.get("recent_notes") or []
    concepts = info.get("concepts") or []
    if synthesis:
        detail = synthesis.split("\n")[0][:180]
    elif notes:
        n = notes[0]
        detail = f"Última anotação (p. {int(n.get('page', 0)) + 1}): {n.get('snippet', '')}"
    elif concepts:
        detail = "Conceitos: " + ", ".join(concepts[:5])
    if detail:
        parts.append(detail)
    return " — ".join(parts)
