from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
FRONTEND_DIR = REPO_ROOT / "frontend"

CONFIG_FILE = DATA_DIR / "llm_config.json"
RULES_FILE = DATA_DIR / "global_rules.json"
RUNS_FILE = DATA_DIR / "analysis_runs.json"
AUDIT_FILE = DATA_DIR / "audit_log.jsonl"
SECRET_FILE = DATA_DIR / "secret.key"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
