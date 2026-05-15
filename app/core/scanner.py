import hashlib
import os

from app.core.db import get_connection, init_db, get_file, upsert_file


def hash_file(path: str, block_size: int = 65536) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return None


def scan_directory(directory_path: str, exclude_dirs: list[str], status: dict) -> None:
    """Walk directory_path, hash new/changed files, store in DB.

    Updates `status` dict in-place so the caller can poll progress.
    Skips symlinks, zero-byte files, and dirs listed in exclude_dirs.
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
