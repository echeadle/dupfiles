from app.core.db import upsert_file, get_file, get_all_files, get_duplicates


def test_upsert_inserts_new_record(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "abc123", 100, 1000.0)
    db_conn.commit()
    row = get_file(db_conn, "/tmp/a.txt")
    assert row["hash"] == "abc123"
    assert row["size"] == 100
    assert row["mtime"] == 1000.0


def test_upsert_updates_on_conflict(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "old", 50, 999.0)
    db_conn.commit()
    upsert_file(db_conn, "/tmp/a.txt", "new", 60, 1001.0)
    db_conn.commit()
    row = get_file(db_conn, "/tmp/a.txt")
    assert row["hash"] == "new"
    assert row["size"] == 60


def test_get_file_missing_returns_none(db_conn):
    assert get_file(db_conn, "/nonexistent/path.txt") is None


def test_get_all_files_returns_every_record(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "h1", 10, 1.0)
    upsert_file(db_conn, "/tmp/b.txt", "h2", 20, 2.0)
    db_conn.commit()
    rows = get_all_files(db_conn)
    paths = [r["path"] for r in rows]
    assert "/tmp/a.txt" in paths
    assert "/tmp/b.txt" in paths


def test_get_duplicates_groups_by_hash(db_conn):
    shared_hash = "deadbeef"
    upsert_file(db_conn, "/tmp/a.txt", shared_hash, 10, 1.0)
    upsert_file(db_conn, "/tmp/b.txt", shared_hash, 10, 2.0)
    upsert_file(db_conn, "/tmp/c.txt", "unique",    10, 3.0)
    db_conn.commit()
    dups = get_duplicates(db_conn)
    dup_paths = [r["path"] for r in dups]
    assert "/tmp/a.txt" in dup_paths
    assert "/tmp/b.txt" in dup_paths
    assert "/tmp/c.txt" not in dup_paths


def test_get_duplicates_empty_when_no_dupes(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "h1", 10, 1.0)
    db_conn.commit()
    assert get_duplicates(db_conn) == []
