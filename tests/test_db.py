from app.core.db import (
    upsert_file, get_file, get_all_files, get_duplicates, delete_file,
    clear_files, get_stats, get_duplicate_group_count, get_duplicate_groups_page,
)


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


def test_delete_file_removes_record(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "h1", 10, 1.0)
    db_conn.commit()
    result = delete_file(db_conn, "/tmp/a.txt")
    db_conn.commit()
    assert result is True
    assert get_file(db_conn, "/tmp/a.txt") is None


def test_delete_file_returns_false_for_missing(db_conn):
    assert delete_file(db_conn, "/no/such/file.txt") is False


def test_clear_files_removes_all_records(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "h1", 10, 1.0)
    upsert_file(db_conn, "/tmp/b.txt", "h2", 20, 2.0)
    db_conn.commit()
    count = clear_files(db_conn)
    assert count == 2
    assert get_all_files(db_conn) == []


def test_clear_files_on_empty_db_returns_zero(db_conn):
    assert clear_files(db_conn) == 0


def test_get_stats_empty_db(db_conn):
    s = get_stats(db_conn)
    assert s["total_files"]      == 0
    assert s["total_size"]       == 0
    assert s["duplicate_groups"] == 0
    assert s["duplicate_files"]  == 0
    assert s["wasted_space"]     == 0


def test_get_stats_with_duplicates(db_conn):
    # Two copies of a 1000-byte file, one unique 500-byte file
    upsert_file(db_conn, "/tmp/a.txt", "hash_dup", 1000, 1.0)
    upsert_file(db_conn, "/tmp/b.txt", "hash_dup", 1000, 2.0)
    upsert_file(db_conn, "/tmp/c.txt", "hash_uni",  500, 3.0)
    db_conn.commit()
    s = get_stats(db_conn)
    assert s["total_files"]      == 3
    assert s["total_size"]       == 2500
    assert s["duplicate_groups"] == 1
    assert s["duplicate_files"]  == 2
    assert s["wasted_space"]     == 1000  # 1 extra copy × 1000 bytes


def test_get_duplicate_group_count(db_conn):
    upsert_file(db_conn, "/tmp/a.txt", "h1", 100, 1.0)
    upsert_file(db_conn, "/tmp/b.txt", "h1", 100, 2.0)
    upsert_file(db_conn, "/tmp/c.txt", "h2", 200, 3.0)
    upsert_file(db_conn, "/tmp/d.txt", "h2", 200, 4.0)
    upsert_file(db_conn, "/tmp/e.txt", "h3", 999, 5.0)  # unique
    db_conn.commit()
    assert get_duplicate_group_count(db_conn) == 2
    assert get_duplicate_group_count(db_conn, min_size=150) == 1  # only h2


def test_get_duplicate_groups_page_limit_and_offset(db_conn):
    for i in range(4):
        upsert_file(db_conn, f"/tmp/a{i}.txt", f"hash{i}", (i + 1) * 100, 1.0)
        upsert_file(db_conn, f"/tmp/b{i}.txt", f"hash{i}", (i + 1) * 100, 2.0)
    db_conn.commit()

    page1 = get_duplicate_groups_page(db_conn, limit=2, offset=0)
    page2 = get_duplicate_groups_page(db_conn, limit=2, offset=2)
    hashes1 = {r["hash"] for r in page1}
    hashes2 = {r["hash"] for r in page2}
    assert len(hashes1) == 2
    assert len(hashes2) == 2
    assert hashes1.isdisjoint(hashes2)  # no overlap between pages
