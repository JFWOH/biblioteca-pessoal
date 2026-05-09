"""Banco de dados SQLite com FTS5 para a biblioteca."""

import sqlite3
from pathlib import Path
from datetime import datetime

from src.utils.constants import DB_PATH


class LibraryDB:
    """Gerencia o banco de dados SQLite da biblioteca."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._connect()
        self._create_tables()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._connect()
        return self._conn

    def _create_tables(self) -> None:
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
            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
            CREATE INDEX IF NOT EXISTS idx_books_format ON books(file_format);
            CREATE INDEX IF NOT EXISTS idx_books_status ON books(read_status);
            CREATE INDEX IF NOT EXISTS idx_books_hash ON books(file_hash);
            CREATE INDEX IF NOT EXISTS idx_annotations_book ON annotations(book_id);
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
        self.conn.execute(f"UPDATE books SET {sets} WHERE id = :id", kwargs)
        self.conn.commit()

    def delete_book(self, book_id: int) -> None:
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
        self.conn.execute(
            """INSERT INTO reading_progress (book_id, current_page, total_pages,
               percentage, last_read, time_spent_seconds)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
               ON CONFLICT(book_id) DO UPDATE SET
               current_page=excluded.current_page, total_pages=excluded.total_pages,
               percentage=excluded.percentage, last_read=CURRENT_TIMESTAMP,
               time_spent_seconds=time_spent_seconds+excluded.time_spent_seconds""",
            (book_id, current_page, total_pages, pct, time_spent))
        status = "read" if pct >= 99.5 else ("reading" if current_page > 0 else "unread")
        self.conn.execute("UPDATE books SET read_status = ? WHERE id = ?", (status, book_id))
        self.conn.commit()

    def get_reading_progress(self, book_id: int) -> dict | None:
        r = self.conn.execute(
            "SELECT * FROM reading_progress WHERE book_id = ?", (book_id,)).fetchone()
        return dict(r) if r else None

    # ── Coleções ───────────────────────────────────────────────────────

    def create_collection(self, name: str, description="", icon="📁",
                          color="#6366f1") -> int:
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
        self.conn.execute(
            "UPDATE collections SET name = ? WHERE id = ?", (new_name, collection_id))
        self.conn.commit()

    def delete_collection(self, collection_id: int) -> None:
        self.conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        self.conn.commit()

    def get_book_collections(self, book_id: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT c.* FROM collections c JOIN book_collections bc ON c.id=bc.collection_id
               WHERE bc.book_id=? ORDER BY c.name""", (book_id,)).fetchall()
        return [dict(r) for r in rows]

    def remove_book_from_collection(self, book_id: int, collection_id: int) -> None:
        self.conn.execute(
            "DELETE FROM book_collections WHERE book_id=? AND collection_id=?",
            (book_id, collection_id))
        self.conn.commit()

    # ── Tags ───────────────────────────────────────────────────────────

    def create_tag(self, name: str, color="#8b5cf6") -> int:
        cur = self.conn.execute("INSERT INTO tags (name, color) VALUES (?,?)", (name, color))
        self.conn.commit()
        return cur.lastrowid

    def get_tags(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM tags ORDER BY name").fetchall()]

    def add_tag_to_book(self, book_id: int, tag_id: int) -> None:
        try:
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
        self.conn.execute(
            "DELETE FROM book_tags WHERE book_id=? AND tag_id=?", (book_id, tag_id))
        self.conn.commit()

    # ── Anotações ──────────────────────────────────────────────────────

    def add_annotation(self, book_id: int, page_number: int, content="",
                       highlight_color="#fbbf24", annotation_type="highlight",
                       position_data="{}") -> int:
        cur = self.conn.execute(
            """INSERT INTO annotations (book_id, page_number, content,
               highlight_color, annotation_type, position_data)
               VALUES (?,?,?,?,?,?)""",
            (book_id, page_number, content, highlight_color, annotation_type, position_data))
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

    def delete_annotation(self, annotation_id: int) -> None:
        self.conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
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
            conds.append("file_format = ?"); params.append(format)
        if status:
            conds.append("read_status = ?"); params.append(status)
        if min_rating is not None:
            conds.append("rating >= ?"); params.append(min_rating)
        if author:
            conds.append("author LIKE ?"); params.append(f"%{author}%")
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
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
