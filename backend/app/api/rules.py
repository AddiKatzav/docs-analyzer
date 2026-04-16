from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models import GlobalRulesResponse, RuleCreateRequest, RuleItem
from app.services.audit_log import log_event
from app.services.rules_store import add_rule, delete_rule, get_rules

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=GlobalRulesResponse)
def fetch_global_rules() -> GlobalRulesResponse:
    rules = get_rules()
    updated_at = datetime.fromisoformat(rules["updated_at"]) if rules["updated_at"] else None
    return GlobalRulesResponse(
        rules=[RuleItem(**rule) for rule in rules["rules"]],
        updated_at=updated_at,
    )


@router.post("", response_model=GlobalRulesResponse)
def create_global_rule(payload: RuleCreateRequest) -> GlobalRulesResponse:
    saved = add_rule(payload.text)
    log_event(
        "rules.added",
        {
            "rules_count": len(saved["rules"]),
            "added_rule_length": len(payload.text.strip()),
        },
    )
    return GlobalRulesResponse(
        rules=[RuleItem(**rule) for rule in saved["rules"]],
        updated_at=datetime.fromisoformat(saved["updated_at"]),
    )


@router.delete("/{rule_id}", response_model=GlobalRulesResponse)
def remove_global_rule(rule_id: str) -> GlobalRulesResponse:
    saved, removed = delete_rule(rule_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Rule not found.")
    log_event(
        "rules.removed",
        {
            "rules_count": len(saved["rules"]),
            "removed_rule_id": rule_id,
        },
    )
    return GlobalRulesResponse(
        rules=[RuleItem(**rule) for rule in saved["rules"]],
        updated_at=datetime.fromisoformat(saved["updated_at"]),
    )
