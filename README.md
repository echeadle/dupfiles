# Duplicate File Finder

A FastAPI web app that scans directories, finds duplicate files by SHA-256 hash, and
displays them grouped by wasted space. Designed for large home directories (tested at 1M+ files).

## Features

- **Background scan** — POST returns immediately; poll `/scan/status` for progress
- **Smart cache** — skips re-hashing files whose size and mtime haven't changed
- **Safe delete** — moves files to the OS trash via `send2trash` (not permanent delete)
- **Server-side pagination** — fetches 50 duplicate groups at a time; handles 300K+ groups without freezing the browser
- **Statistics panel** — files in cache, duplicate groups, recoverable space, DB size
- **Minimum size filter** — show only duplicates above a threshold (bytes / KB / MB / GB)
- **Config UI** — add/remove excluded directories and file patterns from the browser; auto-saved
- **Filesystem browser** — modal directory picker so you don't have to type paths
- **Last path memory** — directory input pre-fills with the last scanned path on page load
- **Auto-load results** — duplicate results reload on page refresh without re-scanning
- **VACUUM on cache clear** — DB file shrinks back to near-zero after clearing
- **Configurable exclusions** — skip directories by name and files by glob pattern
- Skips symlinks and zero-byte files
- Results sorted by most wasted space first
- OpenAPI docs at `http://localhost:8000/docs`

## Setup

```bash
cd dupfiles
uv sync           # creates .venv and installs all deps from uv.lock
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

Open `http://localhost:8000`, enter or browse to a directory, click **Scan**.

## Configuration

`config.json` is created automatically. Edit it directly or use the Config panel in the UI.

```json
{
  "exclude_dirs": [".venv", ".git", "__pycache__", "node_modules", "flatpak"],
  "exclude_patterns": ["*.log", "*.tmp", ".DS_Store", "Thumbs.db", "*.pyc"],
  "last_path": "/home/user/Documents"
}
```

**exclude_dirs** — matched against each directory *name component* in the path (not full paths).
Add `flatpak` to skip `~/.local/share/flatpak/`, for example.

**exclude_patterns** — glob patterns matched against the filename only (uses `fnmatch`).

**last_path** — written automatically by the app on each scan; pre-fills the directory input.

## API

| Method | Path                | Description                                        |
|--------|---------------------|----------------------------------------------------|
| GET    | `/`                 | Web UI                                             |
| GET    | `/browse?path=~`    | List subdirectories for the filesystem browser     |
| GET    | `/config`           | Get current config (excludes + last_path)          |
| PUT    | `/config`           | Update excluded dirs and patterns                  |
| POST   | `/scan`             | Start scan `{"path": "/some/dir"}`                 |
| GET    | `/scan/status`      | Poll scan progress                                 |
| GET    | `/stats`            | File counts, duplicate groups, wasted space, DB size |
| GET    | `/files`            | List all scanned files                             |
| GET    | `/duplicates`       | Paginated duplicate groups `?limit=50&offset=0&min_size=0` |
| POST   | `/files/delete`     | Move files to trash `{"paths": [...]}`             |
| POST   | `/cache/clear`      | Wipe all cached hashes; VACUUMs the DB             |

## Notes

- The SQLite database (`files.db`) is created in the directory you run uvicorn from.
- Subsequent scans of the same directory are fast — unchanged files are skipped via size+mtime cache.
- **Clear Cache** removes all records and VACUUMs the DB (file size returns to ~20 KB).
- Excluded directories are matched by name, not full path — add `flatpak`, not `/home/user/.local/share/flatpak`.

## Testing

A `testdata/` directory is included as a controlled test fixture:

```
testdata/
├── docs/report.txt       ← duplicate pair 1
├── backup/report.txt     ←
├── images/photo.jpg      ← duplicate pair 2
├── archive/photo.jpg     ←
├── docs/summary.txt      unique
├── README.md             unique
├── notes.txt             unique
├── .git/                 excluded by dir
├── .venv/                excluded by dir
├── __pycache__/          excluded by dir
├── node_modules/         excluded by dir
├── flatpak/              excluded by dir
├── docs/debug.log        excluded by pattern
├── backup/archive.tmp    excluded by pattern
└── images/.DS_Store      excluded by pattern
```

Expected result: exactly 2 duplicate groups, 7 files scanned, 0 errors.

```bash
# Run tests
.venv/bin/python -m pytest
```
