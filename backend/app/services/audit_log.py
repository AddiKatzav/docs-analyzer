import json
from datetime import UTC, datetime
from typing import Any

from app.services.paths import AUDIT_FILE, ensure_data_dirs


def log_event(event_type: str, payload: dict[str, Any]) -> None:
    ensure_data_dirs()
    record = {
        "event_type": event_type,
        "created_at": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    with AUDIT_FILE.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record) + "\n")
