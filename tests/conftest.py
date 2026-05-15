import json
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
def tmp_config(tmp_path_factory, monkeypatch):
    """Patch CONFIG_PATH to a temp config.json with default-like content."""
    cfg_dir = tmp_path_factory.mktemp("cfg")
    cfg_path = str(cfg_dir / "config.json")
    default = {"exclude_dirs": [".git"], "exclude_patterns": ["*.log"]}
    with open(cfg_path, "w") as f:
        json.dump(default, f)
    monkeypatch.setattr(routes_module, "CONFIG_PATH", cfg_path)
    return cfg_path


@pytest.fixture()
def db_conn(tmp_db):
    """Open an initialized in-temp-file connection."""
    conn = db_module.get_connection(tmp_db)
    db_module.init_db(conn)
    yield conn
    conn.close()


@pytest.fixture()
def client(tmp_db, tmp_config):
    """TestClient with patched DB, patched config, and reset scan status."""
    routes_module._scan_status.update(
        {"running": False, "done": False, "processed": 0, "skipped": 0, "errors": []}
    )
    from app.main import app
    with TestClient(app) as c:
        yield c
