import hashlib

from app.core.scanner import hash_file, scan_directory
from app.core.db import get_connection, init_db, get_duplicates


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


def test_scan_directory_finds_duplicates(tmp_path, tmp_db):
    content = b"duplicate file content"
    (tmp_path / "a.txt").write_bytes(content)
    (tmp_path / "b.txt").write_bytes(content)
    (tmp_path / "unique.txt").write_bytes(b"something else entirely")

    status = {}
    scan_directory(str(tmp_path), [], status)

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
    scan_directory(str(tmp_path), [], status)

    assert status["processed"] == 1  # only the real file


def test_scan_directory_cache_hit_on_rescan(tmp_path, tmp_db):
    (tmp_path / "file.txt").write_bytes(b"some bytes")

    status = {}
    scan_directory(str(tmp_path), [], status)
    assert status["processed"] == 1
    assert status["skipped"] == 0

    status2 = {}
    scan_directory(str(tmp_path), [], status2)
    assert status2["processed"] == 0
    assert status2["skipped"] == 1


def test_scan_directory_respects_exclude_dirs(tmp_path, tmp_db):
    excluded = tmp_path / "node_modules"
    excluded.mkdir()
    (excluded / "lib.js").write_bytes(b"js code")
    (tmp_path / "main.py").write_bytes(b"python code")

    status = {}
    scan_directory(str(tmp_path), ["node_modules"], status)

    assert status["processed"] == 1  # only main.py
