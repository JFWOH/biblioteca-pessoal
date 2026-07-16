"""Banco de dados SQLite com FTS5 para a biblioteca."""

import sqlite3
import threading
from pathlib import Path
from datetime import datetime

from src.utils.constants import DB_PATH


class LibraryDB:
    """Gerencia o banco de dados SQLite da biblioteca."""

    _write_lock = threading.Lock()
    _local = threading.local()

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            c = sqlite3.connect(str(self._db_path), timeout=5.0)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            self._local.conn = c
        return self._local.conn

    def _create_tables(self) -> None:
        with self._write_lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, author TEXT DEFAULT '',
                    isbn TEXT DEFAULT '', publisher TEXT DEFAULT '',
                    year INTEGER, language TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    file_path TEXT UNIQUE NOT NULL, file_format TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0, file_hash TEXT DEFAULT '',
                    cover_path TEXT DEFAULT '', page_count INTEGER DEFAULT 0,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rating INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
                    read_status TEXT DEFAULT 'unread'
                );
                CREATE TABLE IF NOT EXISTS reading_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL UNIQUE,
                    current_page INTEGER DEFAULT 0, total_pages INTEGER DEFAULT 0,
                    percentage REAL DEFAULT 0.0, last_position TEXT DEFAULT '',
                    last_read TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    time_spent_seconds INTEGER DEFAULT 0,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL, description TEXT DEFAULT '',
                    icon TEXT DEFAULT '📁', color TEXT DEFAULT '#6366f1',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS book_collections (
                    book_id INTEGER NOT NULL, collection_id INTEGER NOT NULL,
                    PRIMARY KEY (book_id, collection_id),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL, color TEXT DEFAULT '#8b5cf6'
                );
                CREATE TABLE IF NOT EXISTS book_tags (
                    book_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
                    PRIMARY KEY (book_id, tag_id),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS annotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL, page_number INTEGER DEFAULT 0,
                    position_data TEXT DEFAULT '{}', content TEXT DEFAULT '',
                    highlight_color TEXT DEFAULT '#fbbf24',
                    annotation_type TEXT DEFAULT 'highlight',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS ocr_pages (
                    book_id INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    content TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (book_id, page_number),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS indexing_state (
                    book_id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    chunks_indexed INTEGER DEFAULT 0,
                    error_message TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    front TEXT NOT NULL,
                    back TEXT DEFAULT '',
                    deck TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    due_date TEXT DEFAULT '',
                    interval_days INTEGER DEFAULT 0,
                    ease REAL DEFAULT 2.5,
                    reps INTEGER DEFAULT 0,
                    lapses INTEGER DEFAULT 0,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS chat_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    session_id TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS agent_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT DEFAULT '',
                    book_id INTEGER,
                    page INTEGER,
                    kind TEXT NOT NULL DEFAULT 'answer',
                    target_ref TEXT DEFAULT '',
                    rating INTEGER NOT NULL DEFAULT 0,
                    reason TEXT DEFAULT '',
                    query TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ai_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    page INTEGER,
                    kind TEXT NOT NULL DEFAULT 'insight',
                    content TEXT NOT NULL DEFAULT '',
                    payload_json TEXT DEFAULT '{}',
                    source TEXT DEFAULT 'proactive',
                    confidence REAL DEFAULT 0.0,
                    dismissed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS concept_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    page INTEGER,
                    weight REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT 'page',
                    extracted_by TEXT NOT NULL DEFAULT 'heuristic',
                    origin_ref TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(concept_id, book_id, origin_ref)
                );
                CREATE TABLE IF NOT EXISTS book_edges (
                    book_a INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    book_b INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    weight REAL NOT NULL DEFAULT 0,
                    shared_concepts TEXT NOT NULL DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (book_a, book_b),
                    CHECK (book_a < book_b)
                );
                CREATE TABLE IF NOT EXISTS graph_ingest_log (
                    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    origin_ref TEXT NOT NULL,
                    mentions INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (book_id, origin_ref)
                );
                CREATE TABLE IF NOT EXISTS dossier_synthesis_cache (
                    book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
                    fingerprint TEXT NOT NULL,
                    synthesis TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_mentions_book ON concept_mentions(book_id);
                CREATE INDEX IF NOT EXISTS idx_mentions_concept ON concept_mentions(concept_id);
                CREATE INDEX IF NOT EXISTS idx_chat_turns_book ON chat_turns(book_id, id);
                CREATE INDEX IF NOT EXISTS idx_ai_obs_book_page ON ai_observations(book_id, page);
                CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
                CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
                CREATE INDEX IF NOT EXISTS idx_books_format ON books(file_format);
                CREATE INDEX IF NOT EXISTS idx_books_status ON books(read_status);
                CREATE INDEX IF NOT EXISTS idx_books_hash ON books(file_hash);
                CREATE INDEX IF NOT EXISTS idx_annotations_book ON annotations(book_id);
                CREATE INDEX IF NOT EXISTS idx_indexing_status ON indexing_state(status);
                CREATE INDEX IF NOT EXISTS idx_flashcards_book ON flashcards(book_id);
                CREATE INDEX IF NOT EXISTS idx_flashcards_due ON flashcards(due_date);
            """)
            try:
                self.conn.execute("""
                    CREATE VIRTUAL TABLE books_fts USING fts5(
                        title, author, description, content='books',
                        content_rowid='id', tokenize='unicode61')
                """)
            except sqlite3.OperationalError:
                pass
            for sql in [
                """CREATE TRIGGER IF NOT EXISTS books_ai AFTER INSERT ON books BEGIN
                    INSERT INTO books_fts(rowid, title, author, description)
                    VALUES (new.id, new.title, new.author, new.description); END""",
                """CREATE TRIGGER IF NOT EXISTS books_ad AFTER DELETE ON books BEGIN
                    INSERT INTO books_fts(books_fts, rowid, title, author, description)
                    VALUES ('delete', old.id, old.title, old.author, old.description); END""",
                """CREATE TRIGGER IF NOT EXISTS books_au AFTER UPDATE ON books BEGIN
                    INSERT INTO books_fts(books_fts, rowid, title, author, description)
                    VALUES ('delete', old.id, old.title, old.author, old.description);
                    INSERT INTO books_fts(rowid, title, author, description)
                    VALUES (new.id, new.title, new.author, new.description); END""",
                # Migração: título opcional para anotações/notas.
                "ALTER TABLE annotations ADD COLUMN title TEXT DEFAULT ''",
            ]:
                try:
                    self.conn.execute(sql)
                except sqlite3.OperationalError:
                    pass
            self.conn.commit()

    # ── CRUD Livros ────────────────────────────────────────────────────

    def add_book(self, **kwargs) -> int:
        cols = ", ".join(kwargs.keys())
        phs = ", ".join(f":{k}" for k in kwargs.keys())
        with self._write_lock:
            cur = self.conn.execute(f"INSERT INTO books ({cols}) VALUES ({phs})", kwargs)
            self.conn.commit()
            return cur.lastrowid

    def get_book(self, book_id: int) -> dict | None:
        r = self.conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(r) if r else None

    def get_book_by_path(self, file_path: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM books WHERE file_path = ?", (file_path,)).fetchone()
        return dict(r) if r else None

    def get_book_by_hash(self, file_hash: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM books WHERE file_hash = ?", (file_hash,)).fetchone()
        return dict(r) if r else None

    def get_all_books(self, sort_by="date_added", sort_order="DESC",
                      limit=None, offset=0) -> list[dict]:
        sql = f"SELECT * FROM books ORDER BY {sort_by} {sort_order}"
        if limit:
            sql += f" LIMIT {limit} OFFSET {offset}"
        return [dict(r) for r in self.conn.execute(sql).fetchall()]

    def update_book(self, book_id: int, **kwargs) -> None:
        kwargs["date_modified"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = :{k}" for k in kwargs.keys())
        kwargs["id"] = book_id
        with self._write_lock:
            self.conn.execute(f"UPDATE books SET {sets} WHERE id = :id", kwargs)
            self.conn.commit()

    def delete_book(self, book_id: int) -> None:
        with self._write_lock:
            # Apaga manualmente os registros relacionados para garantir compatibilidade e isolamento referencial
            self.conn.execute("DELETE FROM annotations WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM reading_progress WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM book_collections WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM ocr_pages WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM indexing_state WHERE book_id = ?", (book_id,))
            # Grafo de conceitos (Fase 2): menções, arestas e log de cobertura do livro.
            self.conn.execute("DELETE FROM concept_mentions WHERE book_id = ?", (book_id,))
            self.conn.execute(
                "DELETE FROM book_edges WHERE book_a = ? OR book_b = ?", (book_id, book_id))
            self.conn.execute("DELETE FROM graph_ingest_log WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM dossier_synthesis_cache WHERE book_id = ?", (book_id,))

            self.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            self.conn.commit()

    def count_books(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    def get_books_by_status(self, status: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM books WHERE read_status = ? ORDER BY date_modified DESC",
            (status,)).fetchall()
        return [dict(r) for r in rows]

    def get_favorite_books(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM books WHERE is_favorite = 1 ORDER BY title").fetchall()
        return [dict(r) for r in rows]

    # ── Progresso ──────────────────────────────────────────────────────

    def update_reading_progress(self, book_id: int, current_page: int,
                                total_pages: int, time_spent: int = 0) -> None:
        pct = (current_page / total_pages * 100) if total_pages > 0 else 0
        status = "read" if pct >= 99.5 else ("reading" if current_page > 0 else "unread")
        with self._write_lock:
            self.conn.execute(
                """INSERT INTO reading_progress (book_id, current_page, total_pages,
                   percentage, last_read, time_spent_seconds)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                   ON CONFLICT(book_id) DO UPDATE SET
                   current_page=excluded.current_page, total_pages=excluded.total_pages,
                   percentage=excluded.percentage, last_read=CURRENT_TIMESTAMP,
                   time_spent_seconds=time_spent_seconds+excluded.time_spent_seconds""",
                (book_id, current_page, total_pages, pct, time_spent))
            self.conn.execute("UPDATE books SET read_status = ? WHERE id = ?", (status, book_id))
            self.conn.commit()

    def get_reading_progress(self, book_id: int) -> dict | None:
        r = self.conn.execute(
            "SELECT * FROM reading_progress WHERE book_id = ?", (book_id,)).fetchone()
        return dict(r) if r else None

    # ── OCR ────────────────────────────────────────────────────────────

    def save_ocr_page(self, book_id: int, page_number: int, content: str) -> None:
        with self._write_lock:
            self.conn.execute(
                """INSERT INTO ocr_pages (book_id, page_number, content)
                   VALUES (?, ?, ?)
                   ON CONFLICT(book_id, page_number) DO UPDATE SET
                   content=excluded.content""",
                (book_id, page_number, content))
            self.conn.commit()

    def get_ocr_page(self, book_id: int, page_number: int) -> dict | None:
        r = self.conn.execute(
            "SELECT * FROM ocr_pages WHERE book_id = ? AND page_number = ?",
            (book_id, page_number)).fetchone()
        return dict(r) if r else None

    def get_all_ocr_pages(self, book_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ocr_pages WHERE book_id = ? ORDER BY page_number",
            (book_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Estado de Indexação ─────────────────────────────────────────────

    def set_indexing_status(self, book_id: int, status: str, chunks_indexed: int = 0, error_message: str = "") -> None:
        with self._write_lock:
            self.conn.execute(
                """INSERT INTO indexing_state (book_id, status, chunks_indexed, error_message, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(book_id) DO UPDATE SET
                   status=excluded.status, chunks_indexed=excluded.chunks_indexed,
                   error_message=excluded.error_message, updated_at=CURRENT_TIMESTAMP""",
                (book_id, status, chunks_indexed, error_message)
            )
            self.conn.commit()

    def get_indexing_status(self, book_id: int) -> dict | None:
        r = self.conn.execute("SELECT * FROM indexing_state WHERE book_id = ?", (book_id,)).fetchone()
        return dict(r) if r else None

    def get_unindexed_books(self) -> list[dict]:
        """Livros sem indexação RAG concluída (sem estado, pendentes ou falhos).

        Base da auto-indexação em ocioso: candidatos a indexar em background.
        """
        rows = self.conn.execute(
            """SELECT b.*, i.status AS indexing_status
               FROM books b
               LEFT JOIN indexing_state i ON i.book_id = b.id
               WHERE i.status IS NULL OR i.status <> 'indexed_ok'
               ORDER BY b.date_added DESC""").fetchall()
        return [dict(r) for r in rows]

    def get_books_by_indexing_status(self, status: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT b.*, i.status as indexing_status, i.chunks_indexed, i.error_message 
               FROM books b 
               JOIN indexing_state i ON b.id = i.book_id 
               WHERE i.status = ?""", (status,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Coleções ───────────────────────────────────────────────────────

    def create_collection(self, name: str, description="", icon="📁",
                          color="#6366f1") -> int:
        with self._write_lock:
            cur = self.conn.execute(
                "INSERT INTO collections (name, description, icon, color) VALUES (?,?,?,?)",
                (name, description, icon, color))
            self.conn.commit()
            return cur.lastrowid

    def get_collections(self) -> list[dict]:
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM collections ORDER BY name").fetchall()]

    def add_book_to_collection(self, book_id: int, collection_id: int) -> None:
        try:
            with self._write_lock:
                self.conn.execute(
                    "INSERT INTO book_collections (book_id, collection_id) VALUES (?,?)",
                    (book_id, collection_id))
                self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_books_in_collection(self, collection_id: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT b.* FROM books b JOIN book_collections bc ON b.id=bc.book_id
               WHERE bc.collection_id=? ORDER BY b.title""",
            (collection_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_all_collections(self) -> list[dict]:
        return self.get_collections()

    def rename_collection(self, collection_id: int, new_name: str) -> None:
        with self._write_lock:
            self.conn.execute(
                "UPDATE collections SET name = ? WHERE id = ?", (new_name, collection_id))
            self.conn.commit()

    def delete_collection(self, collection_id: int) -> None:
        with self._write_lock:
            self.conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
            self.conn.commit()

    def get_book_collections(self, book_id: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT c.* FROM collections c JOIN book_collections bc ON c.id=bc.collection_id
               WHERE bc.book_id=? ORDER BY c.name""", (book_id,)).fetchall()
        return [dict(r) for r in rows]

    def remove_book_from_collection(self, book_id: int, collection_id: int) -> None:
        with self._write_lock:
            self.conn.execute(
                "DELETE FROM book_collections WHERE book_id=? AND collection_id=?",
                (book_id, collection_id))
            self.conn.commit()

    # ── Tags ───────────────────────────────────────────────────────────

    def create_tag(self, name: str, color="#8b5cf6") -> int:
        with self._write_lock:
            cur = self.conn.execute("INSERT INTO tags (name, color) VALUES (?,?)", (name, color))
            self.conn.commit()
            return cur.lastrowid

    def get_tags(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM tags ORDER BY name").fetchall()]

    def add_tag_to_book(self, book_id: int, tag_id: int) -> None:
        try:
            with self._write_lock:
                self.conn.execute("INSERT INTO book_tags (book_id, tag_id) VALUES (?,?)",
                                  (book_id, tag_id))
                self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_book_tags(self, book_id: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT t.* FROM tags t JOIN book_tags bt ON t.id=bt.tag_id
               WHERE bt.book_id=? ORDER BY t.name""", (book_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_all_tags(self) -> list[dict]:
        return self.get_tags()

    def remove_tag_from_book(self, book_id: int, tag_id: int) -> None:
        with self._write_lock:
            self.conn.execute(
                "DELETE FROM book_tags WHERE book_id=? AND tag_id=?", (book_id, tag_id))
            self.conn.commit()

    # ── Anotações ──────────────────────────────────────────────────────

    def add_annotation(self, book_id: int, page_number: int, content="",
                       highlight_color="#fbbf24", annotation_type="highlight",
                       position_data="{}", title="") -> int:
        with self._write_lock:
            # Dedup: cliques repetidos em "Destacar" criavam anotações
            # duplicadas. Para anotações COM texto, a posição é ignorada na
            # comparação — cada re-seleção do mesmo trecho gera coordenadas
            # (floats) ligeiramente diferentes, então exigir position_data
            # igual deixava as duplicatas passarem. Anotações SEM texto
            # (região de imagem) só são duplicatas com a MESMA posição.
            if (content or "").strip():
                existing = self.conn.execute(
                    """SELECT id FROM annotations
                       WHERE book_id=? AND page_number=? AND content=?
                         AND annotation_type=? AND title=? AND highlight_color=?""",
                    (book_id, page_number, content, annotation_type,
                     title, highlight_color)).fetchone()
            else:
                existing = self.conn.execute(
                    """SELECT id FROM annotations
                       WHERE book_id=? AND page_number=? AND content=?
                         AND annotation_type=? AND position_data=? AND title=?
                         AND highlight_color=?""",
                    (book_id, page_number, content, annotation_type,
                     position_data, title, highlight_color)).fetchone()
            if existing:
                return existing["id"]
            cur = self.conn.execute(
                """INSERT INTO annotations (book_id, page_number, content,
                   highlight_color, annotation_type, position_data, title)
                   VALUES (?,?,?,?,?,?,?)""",
                (book_id, page_number, content, highlight_color, annotation_type, position_data, title))
            self.conn.commit()
            return cur.lastrowid

    def get_annotations(self, book_id: int, annotation_type=None) -> list[dict]:
        if annotation_type:
            rows = self.conn.execute(
                """SELECT * FROM annotations WHERE book_id=? AND annotation_type=?
                   ORDER BY page_number, created_at""",
                (book_id, annotation_type)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM annotations WHERE book_id=? ORDER BY page_number, created_at",
                (book_id,)).fetchall()
        return [dict(r) for r in rows]

    def update_annotation_title(self, annotation_id: int, title: str) -> None:
        """Renomeia uma anotação (inclui notas geradas por IA)."""
        with self._write_lock:
            self.conn.execute(
                "UPDATE annotations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title, annotation_id))
            self.conn.commit()

    def delete_annotation(self, annotation_id: int) -> None:
        with self._write_lock:
            row = self.conn.execute(
                "SELECT book_id FROM annotations WHERE id = ?",
                (annotation_id,)).fetchone()
            self.conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
            if row:
                # Coerência com o grafo (Fase 2): menções/log da anotação saem junto.
                ref = f"annotation:{annotation_id}"
                self.conn.execute(
                    "DELETE FROM concept_mentions WHERE book_id=? AND origin_ref=?",
                    (row["book_id"], ref))
                self.conn.execute(
                    "DELETE FROM graph_ingest_log WHERE book_id=? AND origin_ref=?",
                    (row["book_id"], ref))
            self.conn.commit()

    def dedupe_annotations(self) -> int:
        """Remove anotações exatamente duplicadas (mantém a de menor id).

        Limpeza única para duplicatas históricas (cliques repetidos antes da
        guarda de dedup no add_annotation). Purga também as entradas do grafo
        das linhas removidas. Devolve o nº de linhas removidas.
        """
        with self._write_lock:
            # Com texto: posição ignorada (re-seleções geram coords diferentes);
            # sem texto: exige a mesma posição (regiões distintas são legítimas).
            dupes = self.conn.execute(
                """SELECT a.id, a.book_id FROM annotations a
                   WHERE EXISTS (
                       SELECT 1 FROM annotations b
                       WHERE b.book_id = a.book_id
                         AND b.page_number = a.page_number
                         AND b.content = a.content
                         AND b.annotation_type = a.annotation_type
                         AND b.highlight_color = a.highlight_color
                         AND IFNULL(b.title,'') = IFNULL(a.title,'')
                         AND (TRIM(a.content) <> '' OR b.position_data = a.position_data)
                         AND b.id < a.id
                   )""").fetchall()
            for row in dupes:
                ref = f"annotation:{row['id']}"
                self.conn.execute("DELETE FROM annotations WHERE id=?", (row["id"],))
                self.conn.execute(
                    "DELETE FROM concept_mentions WHERE book_id=? AND origin_ref=?",
                    (row["book_id"], ref))
                self.conn.execute(
                    "DELETE FROM graph_ingest_log WHERE book_id=? AND origin_ref=?",
                    (row["book_id"], ref))
            self.conn.commit()
            return len(dupes)

    # ── Flashcards ─────────────────────────────────────────────────────

    def add_flashcard(self, front: str, back: str = "", book_id: int | None = None,
                      deck: str = "", due_date: str = "") -> int:
        with self._write_lock:
            cur = self.conn.execute(
                """INSERT INTO flashcards (book_id, front, back, deck, due_date)
                   VALUES (?,?,?,?,?)""",
                (book_id, front, back, deck, due_date))
            self.conn.commit()
            return cur.lastrowid

    def get_flashcards(self, book_id: int | None = None) -> list[dict]:
        if book_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM flashcards WHERE book_id=? ORDER BY created_at DESC",
                (book_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM flashcards ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_due_flashcards(self, today_iso: str, book_id: int | None = None) -> list[dict]:
        """Cards devidos: nunca revisados (due_date vazio) ou com due_date <= hoje."""
        query = "SELECT * FROM flashcards WHERE (due_date = '' OR due_date <= ?)"
        params: list = [today_iso]
        if book_id is not None:
            query += " AND book_id = ?"
            params.append(book_id)
        # novos primeiro, depois por data de vencimento
        query += " ORDER BY (due_date = '') DESC, due_date ASC, created_at ASC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def update_flashcard_review(self, fc_id: int, due_date: str, interval_days: int,
                                ease: float, reps: int, lapses: int) -> None:
        with self._write_lock:
            self.conn.execute(
                """UPDATE flashcards SET due_date=?, interval_days=?, ease=?, reps=?, lapses=?
                   WHERE id=?""",
                (due_date, interval_days, ease, reps, lapses, fc_id))
            self.conn.commit()

    def delete_flashcard(self, fc_id: int) -> None:
        with self._write_lock:
            self.conn.execute("DELETE FROM flashcards WHERE id=?", (fc_id,))
            self.conn.commit()

    def count_flashcards(self, book_id: int | None = None) -> int:
        if book_id is not None:
            r = self.conn.execute(
                "SELECT COUNT(*) FROM flashcards WHERE book_id=?", (book_id,)).fetchone()
        else:
            r = self.conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()
        return r[0]

    # ── Memória conversacional (chat_turns) ────────────────────────────────
    # book_id NULL = histórico global (sem livro aberto).

    def add_chat_turn(self, book_id, role: str, content: str, session_id: str = "") -> None:
        with self._write_lock:
            self.conn.execute(
                "INSERT INTO chat_turns (book_id, role, content, session_id) VALUES (?,?,?,?)",
                (book_id, role, (content or "")[:2000], session_id))
            self.conn.commit()

    def get_chat_turns(self, book_id, limit: int = 6) -> list[dict]:
        if book_id is None:
            rows = self.conn.execute(
                "SELECT role, content FROM chat_turns WHERE book_id IS NULL "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT role, content FROM chat_turns WHERE book_id=? "
                "ORDER BY id DESC LIMIT ?", (book_id, limit)).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def prune_chat_turns(self, book_id, keep: int) -> None:
        """Mantém apenas os ``keep`` turnos mais recentes do livro (ou do global)."""
        with self._write_lock:
            if book_id is None:
                self.conn.execute(
                    "DELETE FROM chat_turns WHERE book_id IS NULL AND id NOT IN "
                    "(SELECT id FROM chat_turns WHERE book_id IS NULL ORDER BY id DESC LIMIT ?)",
                    (keep,))
            else:
                self.conn.execute(
                    "DELETE FROM chat_turns WHERE book_id=? AND id NOT IN "
                    "(SELECT id FROM chat_turns WHERE book_id=? ORDER BY id DESC LIMIT ?)",
                    (book_id, book_id, keep))
            self.conn.commit()

    def clear_chat_turns(self, book_id=None) -> None:
        with self._write_lock:
            if book_id is None:
                self.conn.execute("DELETE FROM chat_turns WHERE book_id IS NULL")
            else:
                self.conn.execute("DELETE FROM chat_turns WHERE book_id=?", (book_id,))
            self.conn.commit()

    # ── Feedback do usuário sobre respostas/observações ────────────────────

    def add_feedback(self, rating: int, kind: str = "answer", book_id=None, page=None,
                     session_id: str = "", target_ref: str = "", reason: str = "",
                     query: str = "") -> int:
        """Registra um feedback do leitor e retorna o id da linha inserida.

        O id (``lastrowid``) permite à GUI completar o motivo depois, quando o
        leitor escolhe o chip do 👎 (ver :meth:`set_agent_feedback_reason`).
        """
        with self._write_lock:
            cur = self.conn.execute(
                "INSERT INTO agent_feedback (session_id, book_id, page, kind, target_ref, "
                "rating, reason, query) VALUES (?,?,?,?,?,?,?,?)",
                (session_id, book_id, page, kind, target_ref, int(rating), reason, query))
            self.conn.commit()
            return cur.lastrowid

    def set_agent_feedback_reason(self, feedback_id: int, reason: str) -> None:
        """Atualiza o motivo (``reason``) de um feedback já registrado.

        Usado pela GUI para gravar o motivo do 👎 depois que o leitor escolhe
        o chip. ``feedback_id`` inexistente é no-op silencioso (ADR-005).
        """
        with self._write_lock:
            self.conn.execute(
                "UPDATE agent_feedback SET reason=? WHERE id=?", (reason, feedback_id))
            self.conn.commit()

    def get_recent_agent_feedback(self, limit: int = 200) -> list[dict]:
        """Feedbacks recentes (mais novos primeiro) para o aprendizado do agente.

        Campos por linha: id, rating, reason, kind, query, book_id, page,
        created_at.
        """
        rows = self.conn.execute(
            "SELECT id, rating, reason, kind, query, book_id, page, created_at "
            "FROM agent_feedback ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    # ── Observações da IA (proativas/agente) — persistidas ─────────────────

    def add_observation(self, book_id, page, content: str, kind: str = "insight",
                        payload_json: str = "{}", source: str = "proactive",
                        confidence: float = 0.0) -> int:
        with self._write_lock:
            cur = self.conn.execute(
                "INSERT INTO ai_observations (book_id, page, kind, content, payload_json, "
                "source, confidence) VALUES (?,?,?,?,?,?,?)",
                (book_id, page, kind, content, payload_json, source, float(confidence)))
            self.conn.commit()
            return cur.lastrowid

    def get_observations(self, book_id=None, page=None, include_dismissed: bool = False,
                         limit: int = 50) -> list[dict]:
        query = ("SELECT id, book_id, page, kind, content, payload_json, source, confidence, "
                 "dismissed, created_at FROM ai_observations WHERE 1=1")
        params: list = []
        if book_id is not None:
            query += " AND book_id=?"
            params.append(book_id)
        if page is not None:
            query += " AND page=?"
            params.append(page)
        if not include_dismissed:
            query += " AND dismissed=0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def dismiss_observation(self, obs_id: int) -> None:
        with self._write_lock:
            self.conn.execute("UPDATE ai_observations SET dismissed=1 WHERE id=?", (obs_id,))
            self.conn.commit()

    # ── Cache da síntese do dossiê (Fase 4) ─────────────────────────────

    def get_dossier_synthesis_cache(self, book_id: int) -> dict | None:
        r = self.conn.execute(
            "SELECT fingerprint, synthesis FROM dossier_synthesis_cache WHERE book_id = ?",
            (book_id,)).fetchone()
        return dict(r) if r else None

    def set_dossier_synthesis_cache(self, book_id: int, fingerprint: str, synthesis: str) -> None:
        with self._write_lock:
            self.conn.execute(
                """INSERT INTO dossier_synthesis_cache (book_id, fingerprint, synthesis, created_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(book_id) DO UPDATE SET
                   fingerprint=excluded.fingerprint, synthesis=excluded.synthesis,
                   created_at=CURRENT_TIMESTAMP""",
                (book_id, fingerprint, synthesis))
            self.conn.commit()

    # ── Busca ──────────────────────────────────────────────────────────

    def search_books(self, query: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT b.* FROM books b JOIN books_fts fts ON b.id=fts.rowid
               WHERE books_fts MATCH ? ORDER BY rank""", (query,)).fetchall()
        return [dict(r) for r in rows]

    def filter_books(self, format=None, status=None, min_rating=None,
                     author=None) -> list[dict]:
        conds, params = [], []
        if format:
            conds.append("file_format = ?")
            params.append(format)
        if status:
            conds.append("read_status = ?")
            params.append(status)
        if min_rating is not None:
            conds.append("rating >= ?")
            params.append(min_rating)
        if author:
            conds.append("author LIKE ?")
            params.append(f"%{author}%")
        where = " AND ".join(conds) if conds else "1=1"
        rows = self.conn.execute(
            f"SELECT * FROM books WHERE {where} ORDER BY title", params).fetchall()
        return [dict(r) for r in rows]

    # ── Estatísticas ───────────────────────────────────────────────────

    def get_statistics(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        read = self.conn.execute(
            "SELECT COUNT(*) FROM books WHERE read_status='read'").fetchone()[0]
        reading = self.conn.execute(
            "SELECT COUNT(*) FROM books WHERE read_status='reading'").fetchone()[0]
        unread = self.conn.execute(
            "SELECT COUNT(*) FROM books WHERE read_status='unread'").fetchone()[0]
        favs = self.conn.execute(
            "SELECT COUNT(*) FROM books WHERE is_favorite=1").fetchone()[0]
        fmt_rows = self.conn.execute(
            "SELECT file_format, COUNT(*) as c FROM books GROUP BY file_format").fetchall()
        time_s = self.conn.execute(
            "SELECT COALESCE(SUM(time_spent_seconds),0) FROM reading_progress").fetchone()[0]
        return {"total": total, "read": read, "reading": reading, "unread": unread,
                "favorites": favs, "formats": {r["file_format"]: r["c"] for r in fmt_rows},
                "total_reading_time_seconds": time_s}

    def get_unique_authors(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT author FROM books WHERE author!='' ORDER BY author").fetchall()
        return [r["author"] for r in rows]

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
