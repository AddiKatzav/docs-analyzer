import json
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from app.services.paths import RULES_FILE, ensure_data_dirs

_lock = Lock()


def _default_rules() -> dict:
    return {"rules": [], "updated_at": None}


def _normalize_payload(payload: dict) -> dict:
    # Backward compatibility for early MVP format that stored a single text blob.
    if "rules" in payload:
        return payload
    rules_text = str(payload.get("rules_text", "")).strip()
    rules = []
    if rules_text:
        for line in [chunk.strip() for chunk in rules_text.splitlines() if chunk.strip()]:
            rules.append({"id": uuid4().hex, "text": line})
    return {
        "rules": rules,
        "updated_at": payload.get("updated_at"),
    }


def get_rules() -> dict:
    ensure_data_dirs()
    if not RULES_FILE.exists():
        return _default_rules()
    with _lock:
        raw = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    normalized = _normalize_payload(raw)
    if normalized != raw:
        with _lock:
            RULES_FILE.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized


def _save_payload(rules: list[dict]) -> dict:
    payload = {
        "rules": rules,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with _lock:
        RULES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def add_rule(rule_text: str) -> dict:
    existing = get_rules()
    rules = list(existing["rules"])
    rules.append({"id": uuid4().hex, "text": rule_text.strip()})
    return _save_payload(rules=rules)


def delete_rule(rule_id: str) -> tuple[dict, bool]:
    existing = get_rules()
    rules = list(existing["rules"])
    filtered = [rule for rule in rules if rule.get("id") != rule_id]
    if len(filtered) == len(rules):
        return existing, False
    updated = _save_payload(rules=filtered)
    return updated, True
