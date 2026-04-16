from fastapi import APIRouter, HTTPException

from app.models import ConfigStatusResponse, SaveConfigRequest, VerifyConfigRequest
from app.services.audit_log import log_event
from app.services.config_store import get_status, save_config
from app.services.llm_service import verify_provider_key

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/status", response_model=ConfigStatusResponse)
def config_status() -> ConfigStatusResponse:
    return get_status()


@router.post("/verify")
def verify_config(payload: VerifyConfigRequest) -> dict[str, bool]:
    try:
        verify_provider_key(payload.provider, payload.api_key)
        log_event(
            "config.verify.success",
            {"provider": payload.provider.value},
        )
        return {"ok": True}
    except Exception as exc:
        log_event(
            "config.verify.failed",
            {"provider": payload.provider.value, "error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=f"Key verification failed: {exc}") from exc


@router.put("")
def save_provider_config(payload: SaveConfigRequest) -> dict[str, bool]:
    save_config(payload.provider, payload.api_key)
    log_event(
        "config.saved",
        {"provider": payload.provider.value, "replaced_previous": True},
    )
    return {"ok": True}
