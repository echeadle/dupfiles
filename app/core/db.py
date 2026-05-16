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


def get_stats(conn: sqlite3.Connection) -> dict:
    """Return aggregate statistics computed directly from the DB."""
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_size  = conn.execute("SELECT COALESCE(SUM(size), 0) FROM files").fetchone()[0]

    dup_groups = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT hash FROM files GROUP BY hash HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    dup_files = conn.execute("""
        SELECT COUNT(*) FROM files
        WHERE hash IN (SELECT hash FROM files GROUP BY hash HAVING COUNT(*) > 1)
    """).fetchone()[0]

    # wasted = size × (copies − 1) summed across all duplicate groups
    wasted_space = conn.execute("""
        SELECT COALESCE(SUM(grp_size * (grp_count - 1)), 0)
        FROM (
            SELECT MIN(size) AS grp_size, COUNT(*) AS grp_count
            FROM files
            GROUP BY hash
            HAVING grp_count > 1
        )
    """).fetchone()[0]

    return {
        "total_files":    total_files,
        "total_size":     total_size,
        "duplicate_groups": dup_groups,
        "duplicate_files":  dup_files,
        "wasted_space":   wasted_space,
    }


def get_duplicate_group_count(conn: sqlite3.Connection, min_size: int = 0) -> int:
    """Total number of duplicate groups matching min_size filter."""
    return conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT hash FROM files
            GROUP BY hash
            HAVING COUNT(*) > 1 AND MIN(size) >= ?
        )
    """, (min_size,)).fetchone()[0]


def get_duplicate_groups_page(
    conn: sqlite3.Connection,
    limit: int,
    offset: int,
    min_size: int = 0,
) -> list[dict]:
    """Return one page of duplicate files, sorted by wasted space descending."""
    hashes = [r[0] for r in conn.execute("""
        SELECT hash FROM (
            SELECT hash,
                   COUNT(*) AS cnt,
                   MIN(size) AS file_size,
                   (COUNT(*) - 1) * MIN(size) AS wasted
            FROM files
            GROUP BY hash
            HAVING cnt > 1 AND file_size >= ?
            ORDER BY wasted DESC
            LIMIT ? OFFSET ?
        )
    """, (min_size, limit, offset)).fetchall()]

    if not hashes:
        return []

    placeholders = ",".join("?" * len(hashes))
    rows = conn.execute(
        f"SELECT * FROM files WHERE hash IN ({placeholders}) ORDER BY hash, path",
        hashes,
    ).fetchall()
    return [dict(r) for r in rows]


def get_duplicates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM files
        WHERE hash IN (
            SELECT hash FROM files GROUP BY hash HAVING COUNT(*) > 1
        )
        ORDER BY hash, size DESC, path
    """).fetchall()
    return [dict(r) for r in rows]
