"""Armazenamento do grafo de conceitos (Fase 2).

Camada fina sobre as tabelas ``concepts``, ``concept_mentions``, ``book_edges``
e ``graph_ingest_log`` do :class:`LibraryDB` (schema criado em
``LibraryDB._create_tables``). Core puro, sem PyQt6 (ADR-006); escrita segura
entre threads via a conexão thread-local e o ``_write_lock`` do próprio db.
"""

import json
import logging

from src.core.database import LibraryDB

logger = logging.getLogger(__name__)


class GraphStore:
    """Leitura/escrita do grafo de conceitos sobre um LibraryDB existente."""

    def __init__(self, db: LibraryDB):
        self._db = db

    # ── Conceitos e menções ───────────────────────────────────────────

    def upsert_concept(self, name: str, display_name: str) -> int:
        """Garante o conceito e devolve seu id (idempotente)."""
        with self._db._write_lock:
            cid = self._upsert_concept_nolock(name, display_name)
            self._db.conn.commit()
            return cid

    def _upsert_concept_nolock(self, name: str, display_name: str) -> int:
        """Upsert sem lock/commit — para uso dentro de transações maiores.

        O ``_write_lock`` do LibraryDB não é reentrante; chamadas aninhadas ao
        método público causariam deadlock.
        """
        self._db.conn.execute(
            "INSERT OR IGNORE INTO concepts (name, display_name) VALUES (?, ?)",
            (name, display_name))
        row = self._db.conn.execute(
            "SELECT id FROM concepts WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def add_mentions(self, book_id: int, origin_ref: str,
                     concepts: list[tuple[str, str, float]],
                     page: int | None = None, source: str = "page",
                     extracted_by: str = "heuristic") -> int:
        """Registra menções de uma origem e marca a origem como ingerida.

        Transação única e idempotente: re-visitar a mesma página/anotação não
        duplica nada (UNIQUE em (concept_id, book_id, origin_ref)).
        Devolve o nº de menções efetivamente inseridas.
        """
        inserted = 0
        with self._db._write_lock:
            for name, display_name, weight in concepts:
                cid = self._upsert_concept_nolock(name, display_name)
                cur = self._db.conn.execute(
                    """INSERT OR IGNORE INTO concept_mentions
                       (concept_id, book_id, page, weight, source, extracted_by, origin_ref)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cid, book_id, page, weight, source, extracted_by, origin_ref))
                inserted += cur.rowcount if cur.rowcount > 0 else 0
            self._db.conn.execute(
                """INSERT OR REPLACE INTO graph_ingest_log (book_id, origin_ref, mentions)
                   VALUES (?, ?, ?)""",
                (book_id, origin_ref, inserted))
            self._db.conn.commit()
        return inserted

    # ── Cobertura / idempotência ──────────────────────────────────────

    def is_ingested(self, book_id: int, origin_ref: str) -> bool:
        row = self._db.conn.execute(
            "SELECT 1 FROM graph_ingest_log WHERE book_id = ? AND origin_ref = ?",
            (book_id, origin_ref)).fetchone()
        return row is not None

    def mark_ingested(self, book_id: int, origin_ref: str, mentions: int = 0) -> None:
        with self._db._write_lock:
            self._db.conn.execute(
                """INSERT OR REPLACE INTO graph_ingest_log (book_id, origin_ref, mentions)
                   VALUES (?, ?, ?)""",
                (book_id, origin_ref, mentions))
            self._db.conn.commit()

    def ingested_refs(self, book_id: int, prefix: str = "") -> set[str]:
        if prefix:
            rows = self._db.conn.execute(
                "SELECT origin_ref FROM graph_ingest_log WHERE book_id = ? AND origin_ref LIKE ?",
                (book_id, prefix + "%")).fetchall()
        else:
            rows = self._db.conn.execute(
                "SELECT origin_ref FROM graph_ingest_log WHERE book_id = ?",
                (book_id,)).fetchall()
        return {r["origin_ref"] for r in rows}

    def coverage(self, book_id: int, pages_total: int | None = None) -> dict:
        """Progresso da ingestão do livro (páginas e anotações)."""
        pages_done = self._db.conn.execute(
            "SELECT COUNT(*) FROM graph_ingest_log WHERE book_id = ? AND origin_ref LIKE 'page:%'",
            (book_id,)).fetchone()[0]
        annotations_done = self._db.conn.execute(
            """SELECT COUNT(*) FROM graph_ingest_log
               WHERE book_id = ? AND origin_ref LIKE 'annotation:%'""",
            (book_id,)).fetchone()[0]
        annotations_total = self._db.conn.execute(
            "SELECT COUNT(*) FROM annotations WHERE book_id = ?", (book_id,)).fetchone()[0]
        if pages_total is None:
            row = self._db.conn.execute(
                "SELECT page_count FROM books WHERE id = ?", (book_id,)).fetchone()
            pages_total = (row["page_count"] if row else 0) or 0
        complete = (pages_total > 0 and pages_done >= pages_total
                    and annotations_done >= annotations_total)
        return {
            "pages_done": pages_done, "pages_total": pages_total,
            "annotations_done": annotations_done, "annotations_total": annotations_total,
            "complete": complete,
        }

    # ── Consultas (payoff GUI + Fases 3-6) ────────────────────────────

    def get_book_concepts(self, book_id: int, limit: int = 10) -> list[dict]:
        """Top conceitos do livro por peso agregado."""
        rows = self._db.conn.execute(
            """SELECT c.id, c.name, c.display_name,
                      SUM(m.weight) AS weight, COUNT(m.id) AS mentions
               FROM concept_mentions m JOIN concepts c ON c.id = m.concept_id
               WHERE m.book_id = ?
               GROUP BY c.id ORDER BY weight DESC, mentions DESC LIMIT ?""",
            (book_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_concept_books(self, name: str, limit: int = 10) -> list[dict]:
        """Livros (e páginas) onde o conceito aparece — base do 'onde mais?'."""
        rows = self._db.conn.execute(
            """SELECT m.book_id, b.title, COUNT(m.id) AS mentions,
                      GROUP_CONCAT(DISTINCT m.page) AS pages
               FROM concept_mentions m
               JOIN concepts c ON c.id = m.concept_id
               JOIN books b ON b.id = m.book_id
               WHERE c.name = ?
               GROUP BY m.book_id ORDER BY mentions DESC LIMIT ?""",
            (name, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            pages = [int(p) for p in (d.pop("pages") or "").split(",") if p and p != "None"]
            d["pages"] = sorted(set(pages))
            out.append(d)
        return out

    def related_books(self, book_id: int, limit: int = 5) -> list[dict]:
        """Livros conectados por conceitos compartilhados (lê book_edges)."""
        rows = self._db.conn.execute(
            """SELECT e.book_a, e.book_b, e.weight, e.shared_concepts, b.title, b.id AS other_id
               FROM book_edges e
               JOIN books b ON b.id = CASE WHEN e.book_a = ? THEN e.book_b ELSE e.book_a END
               WHERE e.book_a = ? OR e.book_b = ?
               ORDER BY e.weight DESC LIMIT ?""",
            (book_id, book_id, book_id, limit)).fetchall()
        out = []
        for r in rows:
            try:
                shared = json.loads(r["shared_concepts"] or "[]")
            except (json.JSONDecodeError, TypeError):
                shared = []
            out.append({
                "book_id": r["other_id"], "title": r["title"],
                "weight": r["weight"], "shared": shared,
            })
        return out

    def recompute_book_edges(self, book_id: int, min_shared: int = 2,
                             df_cap_ratio: float = 0.5) -> int:
        """Recalcula as arestas do livro com os demais.

        Conceitos "promíscuos" (presentes em mais livros que o teto derivado de
        ``df_cap_ratio``) não contam — evita conectar tudo por termos genéricos.
        O teto tem piso 2 para bibliotecas pequenas (com 2-4 livros, um corte de
        50% excluiria qualquer conceito compartilhado e nunca haveria aresta).
        Devolve o nº de arestas gravadas.
        """
        conn = self._db.conn
        total_books = conn.execute(
            "SELECT COUNT(DISTINCT book_id) FROM concept_mentions").fetchone()[0]
        if total_books < 2:
            return 0
        df_cap = max(2, int(total_books * df_cap_ratio))

        shared_rows = conn.execute(
            """WITH eligible AS (
                   SELECT concept_id FROM concept_mentions
                   GROUP BY concept_id
                   HAVING COUNT(DISTINCT book_id) <= ?
               )
               SELECT m2.book_id AS other_id, COUNT(DISTINCT m1.concept_id) AS shared
               FROM concept_mentions m1
               JOIN concept_mentions m2 ON m2.concept_id = m1.concept_id
               WHERE m1.book_id = ? AND m2.book_id <> ?
                 AND m1.concept_id IN (SELECT concept_id FROM eligible)
               GROUP BY m2.book_id HAVING shared >= ?""",
            (df_cap, book_id, book_id, min_shared)).fetchall()

        with self._db._write_lock:
            conn.execute(
                "DELETE FROM book_edges WHERE book_a = ? OR book_b = ?",
                (book_id, book_id))
            written = 0
            for row in shared_rows:
                other_id, shared_count = row["other_id"], row["shared"]
                top = conn.execute(
                    """SELECT c.display_name
                       FROM concept_mentions m1
                       JOIN concept_mentions m2 ON m2.concept_id = m1.concept_id
                       JOIN concepts c ON c.id = m1.concept_id
                       WHERE m1.book_id = ? AND m2.book_id = ?
                       GROUP BY m1.concept_id
                       ORDER BY SUM(m1.weight) + SUM(m2.weight) DESC LIMIT 5""",
                    (book_id, other_id)).fetchall()
                shared_names = [t["display_name"] for t in top]
                a, b = (book_id, other_id) if book_id < other_id else (other_id, book_id)
                conn.execute(
                    """INSERT OR REPLACE INTO book_edges
                       (book_a, book_b, weight, shared_concepts, updated_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (a, b, float(shared_count), json.dumps(shared_names, ensure_ascii=False)))
                written += 1
            conn.commit()
        return written

    # ── Manutenção / debug ────────────────────────────────────────────

    def stats(self) -> dict:
        conn = self._db.conn
        return {
            "concepts": conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0],
            "mentions": conn.execute("SELECT COUNT(*) FROM concept_mentions").fetchone()[0],
            "edges": conn.execute("SELECT COUNT(*) FROM book_edges").fetchone()[0],
            "books_covered": conn.execute(
                "SELECT COUNT(DISTINCT book_id) FROM graph_ingest_log").fetchone()[0],
        }

    def purge_book(self, book_id: int) -> None:
        """Remove tudo do livro no grafo (menções, arestas, log)."""
        with self._db._write_lock:
            self._db.conn.execute(
                "DELETE FROM concept_mentions WHERE book_id = ?", (book_id,))
            self._db.conn.execute(
                "DELETE FROM book_edges WHERE book_a = ? OR book_b = ?",
                (book_id, book_id))
            self._db.conn.execute(
                "DELETE FROM graph_ingest_log WHERE book_id = ?", (book_id,))
            self._db.conn.commit()
