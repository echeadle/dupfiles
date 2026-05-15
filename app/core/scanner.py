import fnmatch
import hashlib
import os

from pathlib import Path

from app.core.db import get_all_files, get_connection, init_db, get_file, upsert_file, delete_file


def hash_file(path: str, block_size: int = 65536) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return None


def is_excluded_file(filename: str, patterns: list[str]) -> bool:
    """Return True if filename matches any glob pattern (e.g. '*.log', '.DS_Store')."""
    return any(fnmatch.fnmatch(filename, p) for p in patterns)


def purge_excluded(conn, exclude_dirs: list[str], exclude_patterns: list[str]) -> int:
    """Remove DB records whose path falls under an excluded dir or matches an excluded pattern.

    Returns the number of records removed.
    """
    rows = get_all_files(conn)
    removed = 0
    for row in rows:
        p = Path(row["path"])
        if any(part in exclude_dirs for part in p.parts) or is_excluded_file(p.name, exclude_patterns):
            delete_file(conn, row["path"])
            removed += 1
    conn.commit()
    return removed


def scan_directory(
    directory_path: str,
    exclude_dirs: list[str],
    exclude_patterns: list[str],
    status: dict,
) -> None:
    """Walk directory_path, hash new/changed files, store in DB.

    Updates `status` dict in-place so the caller can poll progress.
    Skips symlinks, zero-byte files, dirs in exclude_dirs, and files
    matching any glob in exclude_patterns.
    Re-hashes only when size or mtime has changed (cache hit = size+mtime match).
    """
    conn = get_connection()
    init_db(conn)

    status.update({"running": True, "done": False, "processed": 0, "skipped": 0, "errors": []})

    try:
        for root, dirs, files in os.walk(directory_path):
            dirs[:] = [
                d for d in dirs
                if d not in exclude_dirs
                and not os.path.islink(os.path.join(root, d))
            ]

            for filename in files:
                fpath = os.path.join(root, filename)
                try:
                    if os.path.islink(fpath):
                        continue

                    if is_excluded_file(filename, exclude_patterns):
                        continue

                    stat = os.stat(fpath)
                    size = stat.st_size
                    mtime = stat.st_mtime

                    if size == 0:
                        continue

                    existing = get_file(conn, fpath)
                    if existing and existing["size"] == size and existing["mtime"] == mtime:
                        status["skipped"] += 1
                        continue

                    file_hash = hash_file(fpath)
                    if file_hash:
                        upsert_file(conn, fpath, file_hash, size, mtime)
                        conn.commit()
                        status["processed"] += 1

                except PermissionError:
                    status["errors"].append(f"Permission denied: {fpath}")
                except Exception as e:
                    status["errors"].append(f"{fpath}: {e}")

    finally:
        conn.close()
        status["running"] = False
        status["done"] = True
