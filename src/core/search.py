"""Motor de busca para a biblioteca."""

from src.core.database import LibraryDB


class SearchEngine:
    """Motor de busca unificado para a biblioteca."""

    def __init__(self, db: LibraryDB):
        self._db = db

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        """Busca unificada: full-text + filtros."""
        if not query.strip():
            if filters:
                return self._db.filter_books(**filters)
            return self._db.get_all_books()

        # Busca FTS5
        try:
            results = self._db.search_books(query)
        except Exception:
            # Fallback: busca LIKE simples
            results = self._db.filter_books(author=query)
            like_results = self._db.conn.execute(
                "SELECT * FROM books WHERE title LIKE ? ORDER BY title",
                (f"%{query}%",)
            ).fetchall()
            seen = {r["id"] for r in results}
            for r in like_results:
                d = dict(r)
                if d["id"] not in seen:
                    results.append(d)

        # Aplica filtros adicionais
        if filters:
            results = self._apply_filters(results, filters)

        return results

    def _apply_filters(self, results: list[dict], filters: dict) -> list[dict]:
        """Aplica filtros adicionais aos resultados."""
        filtered = results
        if "format" in filters and filters["format"]:
            filtered = [r for r in filtered if r["file_format"] == filters["format"]]
        if "status" in filters and filters["status"]:
            filtered = [r for r in filtered if r["read_status"] == filters["status"]]
        if "min_rating" in filters and filters["min_rating"] is not None:
            filtered = [r for r in filtered if r["rating"] >= filters["min_rating"]]
        if "author" in filters and filters["author"]:
            author = filters["author"].lower()
            filtered = [r for r in filtered if author in r["author"].lower()]
        return filtered

    def get_suggestions(self, partial: str, limit: int = 10) -> list[str]:
        """Retorna sugestões de autocompletar para busca."""
        if len(partial) < 2:
            return []
        rows = self._db.conn.execute(
            "SELECT DISTINCT title FROM books WHERE title LIKE ? LIMIT ?",
            (f"%{partial}%", limit)
        ).fetchall()
        suggestions = [r["title"] for r in rows]

        # Adiciona autores
        author_rows = self._db.conn.execute(
            "SELECT DISTINCT author FROM books WHERE author LIKE ? AND author!='' LIMIT ?",
            (f"%{partial}%", limit)
        ).fetchall()
        suggestions.extend(r["author"] for r in author_rows)

        return suggestions[:limit]
