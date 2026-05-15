import hashlib

from app.core.scanner import hash_file, is_excluded_file, purge_excluded, scan_directory
from app.core.db import get_connection, get_duplicates, get_all_files, init_db, upsert_file


# --- hash_file ---

def test_hash_file_matches_known_sha256(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert hash_file(str(f)) == expected


def test_hash_file_same_content_same_hash(tmp_path):
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_bytes(b"same content")
    f2.write_bytes(b"same content")
    assert hash_file(str(f1)) == hash_file(str(f2))


def test_hash_file_missing_returns_none():
    assert hash_file("/no/such/file.txt") is None


# --- is_excluded_file ---

def test_is_excluded_file_matches_glob():
    assert is_excluded_file("app.log", ["*.log"]) is True
    assert is_excluded_file("Thumbs.db", ["Thumbs.db"]) is True
    assert is_excluded_file("cache.tmp", ["*.tmp", "*.log"]) is True


def test_is_excluded_file_no_match():
    assert is_excluded_file("main.py", ["*.log", "*.tmp"]) is False
    assert is_excluded_file("data.log.bak", ["*.log"]) is False


def test_is_excluded_file_empty_patterns():
    assert is_excluded_file("anything.txt", []) is False


# --- scan_directory ---

def test_scan_directory_finds_duplicates(tmp_path, tmp_db):
    content = b"duplicate file content"
    (tmp_path / "a.txt").write_bytes(content)
    (tmp_path / "b.txt").write_bytes(content)
    (tmp_path / "unique.txt").write_bytes(b"something else entirely")

    status = {}
    scan_directory(str(tmp_path), [], [], status)

    assert status["done"] is True
    assert status["processed"] == 3
    assert status["errors"] == []

    conn = get_connection(tmp_db)
    dups = get_duplicates(conn)
    conn.close()
    dup_names = {d["path"].split("/")[-1] for d in dups}
    assert dup_names == {"a.txt", "b.txt"}


def test_scan_directory_skips_symlinks(tmp_path, tmp_db):
    real = tmp_path / "real.txt"
    real.write_bytes(b"real content")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    status = {}
    scan_directory(str(tmp_path), [], [], status)

    assert status["processed"] == 1  # only the real file


def test_scan_directory_cache_hit_on_rescan(tmp_path, tmp_db):
    (tmp_path / "file.txt").write_bytes(b"some bytes")

    status = {}
    scan_directory(str(tmp_path), [], [], status)
    assert status["processed"] == 1
    assert status["skipped"] == 0

    status2 = {}
    scan_directory(str(tmp_path), [], [], status2)
    assert status2["processed"] == 0
    assert status2["skipped"] == 1


def test_scan_directory_respects_exclude_dirs(tmp_path, tmp_db):
    excluded = tmp_path / "node_modules"
    excluded.mkdir()
    (excluded / "lib.js").write_bytes(b"js code")
    (tmp_path / "main.py").write_bytes(b"python code")

    status = {}
    scan_directory(str(tmp_path), ["node_modules"], [], status)

    assert status["processed"] == 1  # only main.py


def test_scan_directory_respects_exclude_patterns(tmp_path, tmp_db):
    (tmp_path / "app.log").write_bytes(b"log data")
    (tmp_path / "cache.tmp").write_bytes(b"temp data")
    (tmp_path / "main.py").write_bytes(b"python code")

    status = {}
    scan_directory(str(tmp_path), [], ["*.log", "*.tmp"], status)

    assert status["processed"] == 1  # only main.py


# --- purge_excluded ---

def test_purge_excluded_removes_excluded_dir_entries(tmp_db):
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, "/home/user/.venv/lib/module.py", "h1", 10, 1.0)
    upsert_file(conn, "/home/user/project/main.py",     "h2", 20, 2.0)
    conn.commit()
    removed = purge_excluded(conn, [".venv"], [])
    assert removed == 1
    paths = [r["path"] for r in get_all_files(conn)]
    assert "/home/user/project/main.py" in paths
    assert "/home/user/.venv/lib/module.py" not in paths
    conn.close()


def test_purge_excluded_removes_pattern_matches(tmp_db):
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, "/tmp/app.log",  "h1", 10, 1.0)
    upsert_file(conn, "/tmp/main.py",  "h2", 20, 2.0)
    conn.commit()
    removed = purge_excluded(conn, [], ["*.log"])
    assert removed == 1
    paths = [r["path"] for r in get_all_files(conn)]
    assert "/tmp/main.py" in paths
    assert "/tmp/app.log" not in paths
    conn.close()


def test_purge_excluded_keeps_non_excluded(tmp_db):
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, "/tmp/a.py", "h1", 10, 1.0)
    upsert_file(conn, "/tmp/b.py", "h2", 20, 2.0)
    conn.commit()
    removed = purge_excluded(conn, [".venv"], ["*.log"])
    assert removed == 0
    assert len(get_all_files(conn)) == 2
    conn.close()


def test_scan_directory_patterns_dont_affect_dirs(tmp_path, tmp_db):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "server.txt").write_bytes(b"inside logs dir")
    (tmp_path / "main.py").write_bytes(b"python code")

    status = {}
    scan_directory(str(tmp_path), [], ["*.log"], status)

    assert status["processed"] == 2  # patterns only match filenames, not dirs
