from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models import AnalyzeResponse, BulkAnalyzeItem, BulkAnalyzeResponse
from app.services.analysis_store import add_run
from app.services.audit_log import log_event
from app.services.config_store import get_decrypted_api_key
from app.services.docx_service import extract_docx_text, save_uploaded_docx
from app.services.llm_service import analyze_document
from app.services.rules_store import get_rules

router = APIRouter(prefix="/analyze", tags=["analyze"])

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


def _load_analysis_context() -> tuple:
    config = get_decrypted_api_key()
    if not config:
        raise HTTPException(status_code=400, detail="No LLM provider configured.")
    provider, api_key = config

    rules = get_rules()
    rule_lines = [rule["text"].strip() for rule in rules["rules"] if rule.get("text", "").strip()]
    if not rule_lines:
        raise HTTPException(status_code=400, detail="Global rules are not configured.")
    return provider, api_key, rules, rule_lines


def _analyze_single_docx(
    file: UploadFile, provider, api_key: str, rules: dict, rule_lines: list[str]
) -> AnalyzeResponse:
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Please upload a .docx file.")

    raw_bytes = file.file.read()
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 5MB size limit.")
    file.file.seek(0)
    uploaded_file_size = len(raw_bytes)

    log_event(
        "analysis.started",
        {
            "file_name": file.filename,
            "file_size_bytes": uploaded_file_size,
            "rules_version": rules["version"],
            "rules_count": len(rule_lines),
        },
    )

    try:
        storage_path, original_file_name = save_uploaded_docx(file)
        document_text = extract_docx_text(storage_path)
        if not document_text.strip():
            raise HTTPException(status_code=400, detail="Document appears to be empty.")

        analysis_json, prompt = analyze_document(
            provider=provider,
            api_key=api_key,
            rules_text="\n".join(f"- {line}" for line in rule_lines),
            document_text=document_text,
        )

        created_at = datetime.now(UTC)
        run_id = uuid4().hex
        add_run(
            {
                "run_id": run_id,
                "file_name": original_file_name,
                "provider": provider.value,
                "rules_version": rules["version"],
                "created_at": created_at.isoformat(),
            }
        )
        log_event(
            "analysis.completed",
            {
                "run_id": run_id,
                "file_name": original_file_name,
                "provider": provider.value,
                "rules_version": rules["version"],
                "file_size_bytes": uploaded_file_size,
                "rules_count": len(rule_lines),
                "document_chars": len(document_text),
                "prompt_chars": len(prompt),
                "analysis_keys": list(analysis_json.keys()),
                "summary": analysis_json.get("summary"),
                "compliant": analysis_json.get("compliant"),
                "violations_count": len(analysis_json.get("violations", [])),
                "violations": analysis_json.get("violations", []),
            },
        )

        return AnalyzeResponse(
            run_id=run_id,
            file_name=original_file_name,
            provider=provider,
            rules_version=rules["version"],
            analysis=analysis_json,
            created_at=created_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log_event("analysis.failed", {"file_name": file.filename, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@router.post("", response_model=AnalyzeResponse)
def analyze_docx(file: UploadFile = File(...)) -> AnalyzeResponse:
    provider, api_key, rules, rule_lines = _load_analysis_context()
    return _analyze_single_docx(file, provider, api_key, rules, rule_lines)


@router.post("/bulk", response_model=BulkAnalyzeResponse)
def analyze_docx_bulk(files: list[UploadFile] = File(...)) -> BulkAnalyzeResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one .docx file.")

    provider, api_key, rules, rule_lines = _load_analysis_context()
    items: list[BulkAnalyzeItem] = []

    for upload_file in files:
        try:
            result = _analyze_single_docx(upload_file, provider, api_key, rules, rule_lines)
            items.append(
                BulkAnalyzeItem(file_name=result.file_name, ok=True, result=result, error=None)
            )
        except HTTPException as exc:
            items.append(
                BulkAnalyzeItem(
                    file_name=upload_file.filename or "unknown.docx",
                    ok=False,
                    result=None,
                    error=str(exc.detail),
                )
            )

    succeeded = sum(1 for item in items if item.ok)
    failed = len(items) - succeeded
    return BulkAnalyzeResponse(items=items, total=len(items), succeeded=succeeded, failed=failed)
