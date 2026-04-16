# Global-Rules DOCX Analyzer

Web system for uploading `.docx` files, analyzing content against **system-wide free-text rules**, and using external LLM providers (OpenAI or Anthropic Claude) to detect potential confidential-data leakage.

## Tech Stack

- Frontend: React (served as static app via Nginx)
- Backend: FastAPI (Python)
- Storage: Host-mounted local folder (`.local_data/backend`)
- Containerization: Docker Compose

## Features

- Upload `.docx` files from web UI (single or bulk).
- Drag-and-drop upload area for `.docx` files.
- Configure LLM provider:
  - Provider selector: `OPENAI` or `CLAUDE`
  - API key input
  - Verify key button
  - Save key button
  - Saving a new key replaces old key
- Define **global rules** once for the whole system.
- Add/remove individual global rules from the UI.
- Analyze each uploaded document using `{selected_rules + file_name + document_text}`.
- Analyze tab includes a right-side rules pane with per-rule enable/disable checkboxes (default all enabled).
- File-name validation is enforced before analysis (length/path/invalid character checks).
- Friendly size/count limit handling:
  - Maximum files per bulk request: `20`
  - Maximum size per file: `10 MB`
  - User-friendly errors for oversized files and too-many-files uploads
- Empty (`0 B`) uploads are supported as filename-only analysis (no DOCX parsing crash).
- Selected file size is displayed in the upload list and per-file result rows/cards.
- Parsing-safe decision model:
  - `Compliant`
  - `Non-compliant`
  - `Parsing Error` (if model JSON remains invalid after repair)
- Persist analysis run history.
- Audit log for key events (verify/save/rules update/analysis success-failure).
- Assignment prompt log file: `PROMPTS_EVAL_LOG.md`.

## Run with Docker

```bash
docker compose up --build
```

Services:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api/health`
- Note: in Docker split mode, `http://localhost:8000/` is backend-only and points you to the UI URL.

Quick reboot script (cleanup + rebuild):

```bash
cd /home/addi/projects/docs-analyzer
./scripts/reboot_docker.sh
```

Persistent app state (saved API key/rules/history) is kept in:

```bash
.local_data/backend
```

## Run Full MVP on Localhost (No Docker)

This fallback runs both API and frontend from FastAPI, useful when Docker/image pulls are slow.

```bash
cd /home/addi/projects/docs-analyzer
./scripts/run_localhost.sh
```

Open:
- Full app UI: `http://localhost:8000`
- API health: `http://localhost:8000/api/health`

## Demo Flow

1. Open `http://localhost:3000` (Docker) or `http://localhost:8000` (localhost fallback).
2. Go to **Config** tab:
   - Choose provider.
   - Paste API key.
   - Click **Verify**.
   - Click **Save**.
3. Go to **Rules** tab:
   - Add global rules.
   - Save.
4. Go to **Analyze** tab:
   - Drag/drop or browse one or more `.docx` files.
   - Run bulk analysis and review per-file results.
5. Go to **History** tab:
   - Inspect previous runs.

## API Endpoints

- `GET /api/health`
- `GET /api/config/status`
- `POST /api/config/verify`
- `PUT /api/config`
- `GET /api/rules`
- `POST /api/rules`
- `DELETE /api/rules/{rule_id}`
- `POST /api/analyze`
- `POST /api/analyze/bulk`
- `GET /api/runs`

## Local Development (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

When launched this way, FastAPI serves the frontend automatically from the repo `frontend` directory.

## Testing

```bash
cd backend
python -m pytest
```

Tests mock external LLM calls so they run without vendor API access.
