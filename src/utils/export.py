"""Exportação de anotações para Markdown."""

from pathlib import Path
from datetime import datetime

from src.core.database import LibraryDB


def export_annotations_markdown(db: LibraryDB, book_id: int, output_path: str | Path) -> Path:
    """Exporta anotações de um livro para Markdown."""
    book = db.get_book(book_id)
    annotations = db.get_annotations(book_id)
    output = Path(output_path)

    title = book.get("title", "Sem título") if book else "Livro"
    author = book.get("author", "") if book else ""

    lines = [
        f"# 📝 Anotações — {title}",
        "",
        f"**Autor:** {author}" if author else "",
        f"**Exportado em:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        f"**Total:** {len(annotations)} anotações",
        "",
        "---",
        "",
    ]

    # Agrupa por tipo. BUG corrigido (2026-07-18, relato real): o dicionário
    # cobria só note/highlight/bookmark — anotações geradas pela IA
    # (ai_note/ai_bookmark) entravam no TOTAL do cabeçalho mas eram puladas
    # no corpo (arquivo saía "vazio"). Tipos desconhecidos futuros caem na
    # seção "Outras" — o corpo nunca mais diverge do total.
    types = {
        "note": "📝 Notas",
        "highlight": "🖍️ Destaques",
        "bookmark": "🔖 Marcadores",
        "ai_note": "🤖 Notas da IA",
        "ai_bookmark": "🤖 Marcadores da IA",
    }
    grouped: dict[str, list] = {}
    for ann in annotations:
        t = ann.get("annotation_type", "note")
        grouped.setdefault(t, []).append(ann)

    ordered = list(types.items()) + [
        (t, f"📌 Outras ({t})") for t in grouped if t not in types
    ]
    for ann_type, label in ordered:
        items = grouped.get(ann_type, [])
        if not items:
            continue
        lines.append(f"## {label} ({len(items)})")
        lines.append("")
        for ann in sorted(items, key=lambda a: a.get("page_number", 0)):
            page = ann.get("page_number", 0) + 1
            title_ann = (ann.get("title") or "").strip()
            content = ann.get("content", "")
            date = (ann.get("created_at") or "")[:16]
            color = ann.get("highlight_color", "")

            lines.append(f"### Página {page}" + (f" — {title_ann}" if title_ann else ""))
            if content:
                # Blockquote multilinha: cada linha do conteúdo prefixada,
                # senão só a 1ª linha ficaria dentro da citação no Markdown.
                lines.extend(f"> {ln}" for ln in str(content).splitlines())
            if color and ann_type == "highlight":
                lines.append(f"*Cor: {color}*")
            if date:
                lines.append(f"*{date}*")
            lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output
