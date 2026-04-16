---
name: data-folder-rules-analyzer
description: Analyze files from the backend data folder using the app's configured provider and global rules. Use when the user asks to analyze local data files, sync rules from the app into global_rules.json, or run coding-agent-side compliance checks.
---

# Data Folder Rules Analyzer

Use this skill to run rule-based file analysis directly from the coding agent, reusing backend logic.

## What this skill does

1. Optionally sync rules from the running app API into `.local_data/backend/global_rules.json`.
2. Load provider and API key from persisted app files (`llm_config.json` + `secret.key`).
3. Analyze files in `.local_data/backend` (or another folder) with the same LLM analysis flow used by the app.
4. Save a machine-readable report to `.local_data/backend/agent_analysis_results.json`.

## Command

Run from repo root:

```bash
./backend/.venv/bin/python .cursor/skills/data-folder-rules-analyzer/scripts/analyze_data_folder.py
```

Common options:

```bash
# Sync rules from API, then analyze backend/data
./backend/.venv/bin/python .cursor/skills/data-folder-rules-analyzer/scripts/analyze_data_folder.py \
  --sync-rules-from-api \
  --api-base-url http://localhost:8000

# Validate configuration/rules/files without LLM calls
./backend/.venv/bin/python .cursor/skills/data-folder-rules-analyzer/scripts/analyze_data_folder.py \
  --dry-run

# Analyze a custom directory and write to a custom report path
./backend/.venv/bin/python .cursor/skills/data-folder-rules-analyzer/scripts/analyze_data_folder.py \
  --data-dir ./data \
  --output ./.local_data/backend/agent_analysis_results.json \
  --storage-dir ./.local_data/backend

# Analyze explicit files only
./backend/.venv/bin/python .cursor/skills/data-folder-rules-analyzer/scripts/analyze_data_folder.py \
  --file "/mnt/c/Users/Addi/Downloads/9mm glock purchase.docx" \
  --file "/mnt/c/Users/Addi/Downloads/עולים לגובה.docx" \
  --file "/mnt/c/Users/Addi/Downloads/שלום עליכם.docx"
```

## Notes

- Supported file types: `.docx`, `.txt`, `.md`.
- Default persisted app storage directory is `.local_data/backend` (falls back to `backend/data` if needed).
- The app config must already have a saved LLM provider/API key.
- If no rules exist, add rules in the app first or sync from API.
