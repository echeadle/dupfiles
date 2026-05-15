# Duplicate File Finder - PLANNING

## Project Objective

Build a lightweight application using FastAPI and Python that scans directories, computes SHA-256 hashes of files, and detects duplicates. The application will use a local SQLite3 database to persist file data and include a simple web UI for basic interactions.

## Scope

- Recursively scan directories (excluding symlinks)
- Hash files using SHA-256 to detect duplicates
- Store each file’s hash, path, size, and mtime in SQLite3
- Provide FastAPI REST API to:
  - Trigger scans
  - List all files
  - List duplicates
- Provide a simple web interface to trigger scans and display duplicates
- Provide ability to configure excluded directories (e.g., `.venv`, `__pycache__`, etc.)

## Technologies

- **Backend Framework**: FastAPI (Python)
- **Config**: Simple `.json` or `.yaml` file for scan exclusions
- **Language**: Python 3.10+
- **Database**: SQLite3 (upgradeable in future)
- **Hash Algorithm**: SHA-256
- **Frontend**: Simple static HTML+JavaScript (served via FastAPI)
- **Environment**: Cross-platform, targeting local machine usage first

## Stretch Goals

- Use file size + partial hash to optimize large file scanning
- Add file deletion support via API
- CLI wrapper to use core logic
- Frontend enhancements (filters, styling, bulk actions)
- DB abstraction for other engines (PostgreSQL, MySQL)

## Assumptions

- Files are not modified during scans
- SQLite is sufficient for initial data volumes
- Symlinks are ignored
- MVP prioritizes correctness and usability over speed

## File Structure

find-dup-files/
├── app
│   ├── api
│   │   └── routes.py
│   ├── core
│   │   ├── db.py
│   │   └── scanner.py
│   ├── main.py
│   └── models
│       └── file_entry.py
├── ascidoc.txt
├── config.json
├── favicon.ico
├── LICENSE
├── PLANNING.md
├── README.md
├── requirements.txt
├── static
│   └── index.html
├── TASK.md
└── tests
    └── test_placeholder.py

## Style Guidelines

- Follow PEP8 standards
- Use type hints for all functions
- Document functions with Google-style docstrings
- Format code with Black
- Use Pydantic for data validation

## Dependencies

- python
- fastapi
- python-dotenv