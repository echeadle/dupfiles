import json
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from send2trash import send2trash

from app.core.db import (
    DB_PATH, clear_files, delete_file, get_all_files, get_connection,
    get_duplicate_group_count, get_duplicate_groups_page, get_duplicates,
    get_file, get_stats, init_db,
)
from app.core.scanner import purge_excluded, scan_directory

router = APIRouter()

CONFIG_PATH = "config.json"

# In-memory scan state — fine for a single-process personal tool
_scan_status: dict = {"running": False, "done": False, "processed": 0, "skipped": 0, "errors": []}


# --- Models ---

class Config(BaseModel):
    exclude_dirs: list[str] = []
    exclude_patterns: list[str] = []


class ScanRequest(BaseModel):
    path: str


class DeleteRequest(BaseModel):
    paths: list[str]


# --- Helpers ---

def _load_config() -> dict:
    config_path = Path(CONFIG_PATH)
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


# --- UI ---

@router.get("/", response_class=FileResponse, include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")


# --- Filesystem browser ---

@router.get("/browse")
def browse(path: str = "~"):
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return {"error": f"Not a directory: {path}", "path": str(p), "parent": None, "entries": []}

    entries = []
    try:
        for item in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if item.is_dir() and not item.is_symlink():
                entries.append({"name": item.name, "path": str(item)})
    except PermissionError:
        pass

    parent = str(p.parent) if p != p.parent else None
    return {"path": str(p), "parent": parent, "entries": entries}


# --- Config ---

@router.get("/config")
def get_config() -> Config:
    return Config(**_load_config())


@router.put("/config")
def update_config(config: Config) -> Config:
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
    os.replace(tmp, CONFIG_PATH)
    return config


# --- Scan ---

@router.post("/scan")
def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    if _scan_status.get("running"):
        return {"status": "already_running", "message": "A scan is already in progress."}

    if not Path(request.path).is_dir():
        return {"status": "error", "message": f"Not a directory: {request.path}"}

    cfg = _load_config()
    exclude_dirs = cfg.get("exclude_dirs", [])
    exclude_patterns = cfg.get("exclude_patterns", [])

    conn = get_connection()
    init_db(conn)
    purged = purge_excluded(conn, exclude_dirs, exclude_patterns)
    conn.close()

    background_tasks.add_task(scan_directory, request.path, exclude_dirs, exclude_patterns, _scan_status)
    return {"status": "started", "path": request.path, "exclude_dirs": exclude_dirs, "exclude_patterns": exclude_patterns, "purged": purged}


@router.get("/stats")
def stats():
    conn = get_connection()
    init_db(conn)
    data = get_stats(conn)
    conn.close()
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return {**data, "db_size": db_size}


@router.post("/cache/clear")
def clear_cache():
    """Wipe all cached scan results from the database."""
    conn = get_connection()
    init_db(conn)
    count = clear_files(conn)
    conn.close()
    return {"cleared": count}


@router.get("/scan/status")
def get_scan_status():
    return _scan_status


# --- Files ---

@router.get("/files")
def list_files():
    conn = get_connection()
    init_db(conn)
    files = get_all_files(conn)
    conn.close()
    return {"count": len(files), "files": files}


@router.post("/files/delete")
def trash_files(request: DeleteRequest):
    """Move files to the OS trash. Only trashes files present in the scan database."""
    conn = get_connection()
    init_db(conn)
    trashed = []
    failed = []

    for path in request.paths:
        if not get_file(conn, path):
            failed.append({"path": path, "reason": "not in database"})
            continue
        try:
            send2trash(path)
            delete_file(conn, path)
            trashed.append(path)
        except Exception as e:
            failed.append({"path": path, "reason": str(e)})

    conn.commit()
    conn.close()
    return {"trashed": trashed, "failed": failed}


# --- Duplicates ---

@router.get("/duplicates")
def list_duplicates(min_size: int = 0, limit: int = 50, offset: int = 0):
    """Return a page of duplicate groups sorted by wasted space descending."""
    conn = get_connection()
    init_db(conn)
    total  = get_duplicate_group_count(conn, min_size)
    rows   = get_duplicate_groups_page(conn, limit, offset, min_size)
    conn.close()

    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row["hash"], []).append(row)

    result = [
        {"hash": h, "count": len(files), "total_size": sum(f["size"] for f in files), "files": files}
        for h, files in groups.items()
    ]
    result.sort(key=lambda g: g["total_size"], reverse=True)

    return {
        "total_groups":    total,
        "returned_groups": len(result),
        "offset":          offset,
        "limit":           limit,
        "min_size":        min_size,
        "duplicate_groups": result,
    }
