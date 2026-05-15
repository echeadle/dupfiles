# Duplicate File Finder - TASKS

## Initial Setup
- [x] Initialize Git repository
- [x] Set up Python virtual environment (uv venv .venv, Python 3.12)
- [x] Install FastAPI, Uvicorn, aiofiles (requirements.txt pinned)
- [x] Create initial project structure

## Core Functionality
- [x] Define SQLite schema: `files (id, path, hash, size, mtime)` with WAL mode
- [x] Implement directory walker (os.walk)
- [x] Skip symlinks
- [x] Hash files using SHA-256 (streaming, 65 KB blocks)
- [x] Store/update file entries in database (upsert on path)
- [x] Avoid re-hashing files with unchanged size+mtime (cache hit)
- [x] Detect duplicates by grouping hashes (ORDER BY total_size DESC)

## API Endpoints (FastAPI)
- [x] `POST /scan` - Triggers background scan; returns immediately
- [x] `GET /scan/status` - Poll scan progress (processed, skipped, errors, done)
- [x] `GET /files` - Return list of all scanned files
- [x] `GET /duplicates` - Return duplicate groups sorted by wasted space

## Frontend (Simple Web Interface)
- [x] Form to enter directory path and trigger scan
- [x] Progress status with polling (1.5s interval)
- [x] Table showing duplicates grouped by hash, sorted by size
- [x] Displays path, size, modified date per file
- [x] "Clear" button to reset view

## Testing
- [x] Unit tests for hash function and db functions (test_db.py, test_scanner.py)
- [x] Integration tests for API endpoints (test_api.py)
- [x] Manual smoke test — scan ran, duplicates returned correctly
- [x] 21/21 passing (`uv run pytest`)

## Documentation
- [x] README with setup + run instructions
- [x] OpenAPI docs available at /docs (FastAPI built-in)
