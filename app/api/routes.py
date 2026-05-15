import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.db import get_connection, get_all_files, get_duplicates, init_db
from app.core.scanner import scan_directory

router = APIRouter()

# In-memory scan state — fine for a single-process personal tool
_scan_status: dict = {"running": False, "done": False, "processed": 0, "skipped": 0, "errors": []}


def _load_config() -> dict:
    config_path = Path("config.json")
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


# --- UI ---

@router.get("/", response_class=FileResponse, include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")


# --- Scan ---

class ScanRequest(BaseModel):
    path: str


@router.post("/scan")
def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    if _scan_status.get("running"):
        return {"status": "already_running", "message": "A scan is already in progress."}

    if not Path(request.path).is_dir():
        return {"status": "error", "message": f"Not a directory: {request.path}"}

    config = _load_config()
    exclude_dirs = config.get("exclude_dirs", [])
    exclude_patterns = config.get("exclude_patterns", [])
    background_tasks.add_task(scan_directory, request.path, exclude_dirs, exclude_patterns, _scan_status)
    return {"status": "started", "path": request.path, "exclude_dirs": exclude_dirs, "exclude_patterns": exclude_patterns}


@router.get("/scan/status")
def get_scan_status():
    return _scan_status


# --- Results ---

@router.get("/files")
def list_files():
    conn = get_connection()
    init_db(conn)
    files = get_all_files(conn)
    conn.close()
    return {"count": len(files), "files": files}


@router.get("/duplicates")
def list_duplicates():
    conn = get_connection()
    init_db(conn)
    rows = get_duplicates(conn)
    conn.close()

    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row["hash"], []).append(row)

    result = [
        {"hash": h, "count": len(files), "total_size": sum(f["size"] for f in files), "files": files}
        for h, files in groups.items()
    ]
    # sort largest wasted space first
    result.sort(key=lambda g: g["total_size"], reverse=True)

    return {"total_groups": len(result), "duplicate_groups": result}
