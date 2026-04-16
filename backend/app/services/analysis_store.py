import json
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.models import AnalysisRunSummary, Provider
from app.services.paths import RUNS_FILE, ensure_data_dirs

_lock = Lock()


def _load_runs() -> list[dict[str, Any]]:
    ensure_data_dirs()
    if not RUNS_FILE.exists():
        return []
    return json.loads(RUNS_FILE.read_text(encoding="utf-8"))


def add_run(run: dict[str, Any]) -> None:
    with _lock:
        runs = _load_runs()
        runs.insert(0, run)
        RUNS_FILE.write_text(json.dumps(runs, indent=2), encoding="utf-8")


def list_runs(limit: int = 50) -> list[AnalysisRunSummary]:
    raw_runs = _load_runs()[:limit]
    output: list[AnalysisRunSummary] = []
    for row in raw_runs:
        output.append(
            AnalysisRunSummary(
                run_id=row["run_id"],
                file_name=row["file_name"],
                provider=Provider(row["provider"]),
                applied_rules_count=int(row.get("applied_rules_count", len(row.get("applied_rule_ids", [])))),
                created_at=datetime.fromisoformat(row["created_at"]).astimezone(UTC),
            )
        )
    return output
