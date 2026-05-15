import app.core.db as db_module
from app.api import routes as routes_module
from app.core.db import upsert_file, get_connection, init_db


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
    assert groups[0]["hash"] == "hash_big"   # largest wasted space first
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
