import pytest
from fastapi.testclient import TestClient

import app.core.db as db_module
from app.api import routes as routes_module


@pytest.fixture()
def tmp_db(tmp_path_factory, monkeypatch):
    """Patch DB_PATH to a temp file in its own dir, separate from any scanned directories."""
    db_path = str(tmp_path_factory.mktemp("db") / "test.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    return db_path


@pytest.fixture()
def db_conn(tmp_db):
    """Open an initialized in-temp-file connection."""
    conn = db_module.get_connection(tmp_db)
    db_module.init_db(conn)
    yield conn
    conn.close()


@pytest.fixture()
def client(tmp_db):
    """TestClient with patched DB and reset scan status."""
    routes_module._scan_status.update(
        {"running": False, "done": False, "processed": 0, "skipped": 0, "errors": []}
    )
    from app.main import app
    with TestClient(app) as c:
        yield c
