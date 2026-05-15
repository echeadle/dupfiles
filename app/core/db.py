import sqlite3

DB_PATH = "files.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            path  TEXT    NOT NULL UNIQUE,
            hash  TEXT    NOT NULL,
            size  INTEGER NOT NULL,
            mtime REAL    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files (hash)")
    conn.commit()


def upsert_file(conn: sqlite3.Connection, path: str, hash: str, size: int, mtime: float) -> None:
    conn.execute("""
        INSERT INTO files (path, hash, size, mtime) VALUES (?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            hash  = excluded.hash,
            size  = excluded.size,
            mtime = excluded.mtime
    """, (path, hash, size, mtime))


def get_file(conn: sqlite3.Connection, path: str) -> dict | None:
    row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
    return dict(row) if row else None


def get_all_files(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM files ORDER BY path").fetchall()
    return [dict(r) for r in rows]


def clear_files(conn: sqlite3.Connection) -> int:
    """Delete all records from the files table. Returns the count removed."""
    cursor = conn.execute("DELETE FROM files")
    conn.commit()
    return cursor.rowcount


def delete_file(conn: sqlite3.Connection, path: str) -> bool:
    """Remove a file record from the DB. Returns True if a row was deleted."""
    cursor = conn.execute("DELETE FROM files WHERE path = ?", (path,))
    return cursor.rowcount > 0


def get_duplicates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM files
        WHERE hash IN (
            SELECT hash FROM files GROUP BY hash HAVING COUNT(*) > 1
        )
        ORDER BY hash, size DESC, path
    """).fetchall()
    return [dict(r) for r in rows]
