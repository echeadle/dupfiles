import json

import app.core.db as db_module
from app.api import routes as routes_module
from app.core.db import upsert_file, get_connection, init_db


# --- Existing tests ---

def test_root_returns_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_scan_invalid_path_returns_error(client):
    r = client.post("/scan", json={"path": "/no/such/directory"})
    assert r.status_code == 200
    assert r.json()["status"] == "error"


def test_scan_already_running_returns_message(client):
    routes_module._scan_status["running"] = True
    r = client.post("/scan", json={"path": "/tmp"})
    assert r.json()["status"] == "already_running"


def test_scan_status_has_expected_fields(client):
    r = client.get("/scan/status")
    data = r.json()
    for key in ("running", "done", "processed", "skipped", "errors"):
        assert key in data


def test_files_empty_on_fresh_db(client):
    r = client.get("/files")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["files"] == []


def test_duplicates_empty_on_fresh_db(client):
    r = client.get("/duplicates")
    assert r.status_code == 200
    data = r.json()
    assert data["total_groups"] == 0
    assert data["duplicate_groups"] == []


def test_duplicates_sorted_by_wasted_space(client, tmp_db):
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, "/tmp/small_a.txt", "hash_small", 100, 1.0)
    upsert_file(conn, "/tmp/small_b.txt", "hash_small", 100, 2.0)
    upsert_file(conn, "/tmp/big_a.txt",   "hash_big",  9999, 3.0)
    upsert_file(conn, "/tmp/big_b.txt",   "hash_big",  9999, 4.0)
    conn.commit()
    conn.close()

    r = client.get("/duplicates")
    groups = r.json()["duplicate_groups"]
    assert groups[0]["hash"] == "hash_big"
    assert groups[1]["hash"] == "hash_small"


def test_scan_response_includes_exclude_patterns(client, tmp_path):
    r = client.post("/scan", json={"path": str(tmp_path)})
    data = r.json()
    assert data["status"] == "started"
    assert "exclude_patterns" in data
    assert isinstance(data["exclude_patterns"], list)


def test_full_scan_finds_duplicates(client, tmp_path):
    content = b"identical content for dedup test"
    (tmp_path / "copy1.txt").write_bytes(content)
    (tmp_path / "copy2.txt").write_bytes(content)
    (tmp_path / "unique.txt").write_bytes(b"different")

    r = client.post("/scan", json={"path": str(tmp_path)})
    assert r.json()["status"] == "started"

    status = client.get("/scan/status").json()
    assert status["done"] is True
    assert status["errors"] == []

    dupes = client.get("/duplicates").json()
    assert dupes["total_groups"] == 1
    group = dupes["duplicate_groups"][0]
    assert group["count"] == 2
    names = {f["path"].split("/")[-1] for f in group["files"]}
    assert names == {"copy1.txt", "copy2.txt"}


# --- Cache tests ---

def test_clear_cache_endpoint(client, tmp_db):
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, "/tmp/a.txt", "h1", 10, 1.0)
    upsert_file(conn, "/tmp/b.txt", "h2", 20, 2.0)
    conn.commit()
    conn.close()
    r = client.post("/cache/clear")
    assert r.status_code == 200
    assert r.json()["cleared"] == 2
    assert client.get("/files").json()["count"] == 0


def test_scan_purges_excluded_entries_before_scanning(client, tmp_db, tmp_path):
    # Put .venv in the exclude list
    client.put("/config", json={"exclude_dirs": [".venv"], "exclude_patterns": []})

    # Pre-populate DB with a file that lives under .venv
    excluded_file = "/home/user/.venv/lib/site.py"
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, excluded_file, "oldhash", 100, 1.0)
    conn.commit()
    conn.close()

    # Scan — pre-scan purge should remove the excluded entry
    r = client.post("/scan", json={"path": str(tmp_path)})
    assert r.json()["purged"] == 1

    from app.core.db import get_file
    conn2 = get_connection(tmp_db)
    assert get_file(conn2, excluded_file) is None
    conn2.close()


def test_scan_response_includes_purged_count(client, tmp_path):
    r = client.post("/scan", json={"path": str(tmp_path)})
    assert "purged" in r.json()


# --- Browser tests ---

def test_browse_returns_subdirs(client, tmp_path):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "file.txt").write_bytes(b"x")   # files should not appear
    r = client.get(f"/browse?path={tmp_path}")
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == str(tmp_path)
    names = [e["name"] for e in data["entries"]]
    assert "alpha" in names
    assert "beta" in names
    assert "file.txt" not in names


def test_browse_returns_parent(client, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    r = client.get(f"/browse?path={sub}")
    assert r.json()["parent"] == str(tmp_path)


def test_browse_invalid_path_returns_error(client):
    r = client.get("/browse?path=/no/such/dir")
    assert "error" in r.json()


def test_browse_entries_sorted(client, tmp_path):
    (tmp_path / "zoo").mkdir()
    (tmp_path / "ant").mkdir()
    (tmp_path / "mid").mkdir()
    names = [e["name"] for e in client.get(f"/browse?path={tmp_path}").json()["entries"]]
    assert names == sorted(names, key=str.lower)


# --- Config tests ---

def test_get_config_returns_current_config(client, tmp_config):
    r = client.get("/config")
    assert r.status_code == 200
    data = r.json()
    assert "exclude_dirs" in data
    assert "exclude_patterns" in data
    assert isinstance(data["exclude_dirs"], list)
    assert isinstance(data["exclude_patterns"], list)


def test_put_config_updates_file(client, tmp_config):
    new_config = {"exclude_dirs": [".venv", "dist"], "exclude_patterns": ["*.tmp"]}
    r = client.put("/config", json=new_config)
    assert r.status_code == 200
    assert r.json() == new_config

    with open(tmp_config) as f:
        saved = json.load(f)
    assert saved == new_config


def test_put_config_adds_new_dir(client, tmp_config):
    original = client.get("/config").json()
    original["exclude_dirs"].append("build")
    r = client.put("/config", json=original)
    assert "build" in r.json()["exclude_dirs"]


def test_put_config_removes_pattern(client, tmp_config):
    client.put("/config", json={"exclude_dirs": [], "exclude_patterns": ["*.log", "*.tmp"]})
    updated = {"exclude_dirs": [], "exclude_patterns": ["*.tmp"]}
    r = client.put("/config", json=updated)
    assert "*.log" not in r.json()["exclude_patterns"]
    assert "*.tmp" in r.json()["exclude_patterns"]


# --- Delete (trash) tests ---

def test_trash_files_moves_to_trash(client, tmp_db, tmp_path):
    f = tmp_path / "dupe.txt"
    f.write_bytes(b"content")
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, str(f), "abc", f.stat().st_size, f.stat().st_mtime)
    conn.commit()
    conn.close()

    r = client.post("/files/delete", json={"paths": [str(f)]})
    assert r.status_code == 200
    data = r.json()
    assert str(f) in data["trashed"]
    assert data["failed"] == []
    assert not f.exists()


def test_trash_rejects_path_not_in_db(client):
    r = client.post("/files/delete", json={"paths": ["/tmp/not_scanned.txt"]})
    data = r.json()
    assert data["trashed"] == []
    assert len(data["failed"]) == 1
    assert data["failed"][0]["reason"] == "not in database"


def test_trash_removes_record_from_db(client, tmp_db, tmp_path):
    f = tmp_path / "gone.txt"
    f.write_bytes(b"data")
    conn = get_connection(tmp_db)
    init_db(conn)
    upsert_file(conn, str(f), "xyz", f.stat().st_size, f.stat().st_mtime)
    conn.commit()
    conn.close()

    client.post("/files/delete", json={"paths": [str(f)]})

    conn2 = get_connection(tmp_db)
    from app.core.db import get_file
    assert get_file(conn2, str(f)) is None
    conn2.close()
