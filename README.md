# Duplicate File Finder

A FastAPI app that scans directories, finds duplicate files by SHA-256 hash, and displays
them grouped by wasted space via a simple web UI.

## Features

- Background scan — POST returns immediately; poll `/scan/status` for progress
- Smart cache — skips re-hashing files whose size and mtime haven't changed
- Configurable exclusions via `config.json` (`.git`, `.venv`, `node_modules`, etc.)
- Skips symlinks and zero-byte files
- Results sorted by most wasted space first
- Interactive web UI at `http://localhost:8000`
- OpenAPI docs at `http://localhost:8000/docs`

## Setup

```bash
cd dupfiles2
uv sync           # creates .venv and installs all deps from uv.lock
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

Open `http://localhost:8000`, enter a directory path, click **Scan**.

## Configuration

Edit `config.json` to add directories to skip:

```json
{
  "exclude_dirs": [".venv", ".git", "__pycache__", "node_modules", "anaconda3"]
}
```

## API

| Method | Path            | Description                          |
|--------|-----------------|--------------------------------------|
| GET    | `/`             | Web UI                               |
| POST   | `/scan`         | Start scan `{"path": "/some/dir"}`   |
| GET    | `/scan/status`  | Poll scan progress                   |
| GET    | `/files`        | List all scanned files               |
| GET    | `/duplicates`   | List duplicate groups by hash        |

## Notes

- The SQLite database (`files.db`) is created in the directory you run uvicorn from.
- Scan results persist across restarts — subsequent scans of the same directory are fast
  because unchanged files are skipped (size+mtime cache).
- To clear all scan history: delete `files.db` and restart.
