import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models import AnalyzeResponse, BulkAnalyzeItem, BulkAnalyzeResponse, RuleItem
from app.services.analysis_store import add_run
from app.services.audit_log import log_event
from app.services.config_store import get_decrypted_api_key
from app.services.docx_service import extract_docx_text, save_uploaded_docx
from app.services.llm_service import analyze_document
from app.services.rules_store import get_rules

router = APIRouter(prefix="/analyze", tags=["analyze"])

MAX_FILES_PER_REQUEST = 20
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_FILENAME_LENGTH = 120


def _bytes_to_mb(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.2f}"


def _parse_enabled_rule_ids(raw_enabled_rule_ids: str | None) -> set[str] | None:
    if raw_enabled_rule_ids is None:
        return None
    try:
        parsed = json.loads(raw_enabled_rule_ids)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid rule selection payload.") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise HTTPException(status_code=400, detail="Rule selection must be an array of rule IDs.")
    return {item.strip() for item in parsed if item.strip()}


def _validate_file_name(file_name: str) -> None:
    if len(file_name) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f'File name "{file_name}" is too long. Maximum length is {MAX_FILENAME_LENGTH} characters.',
        )
    if "/" in file_name or "\\" in file_name or ".." in file_name:
        raise HTTPException(status_code=400, detail=f'File name "{file_name}" contains unsupported path characters.')
    if any(ord(char) < 32 for char in file_name):
        raise HTTPException(
            status_code=400,
            detail=f'File name "{file_name}" contains unsupported control characters.',
        )
    invalid_chars = {":", "*", "?", "\"", "<", ">", "|"}
    if any(char in invalid_chars for char in file_name):
        raise HTTPException(status_code=400, detail=f'File name "{file_name}" contains unsupported characters.')


def _validate_upload(file_item: UploadFile) -> int:
    file_name = file_item.filename or ""
    if not file_name or not file_name.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")
    _validate_file_name(file_name)
    raw_bytes = file_item.file.read()
    file_size = len(raw_bytes)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f'File "{file_name}" size of {_bytes_to_mb(file_size)} MB exceeds '
                f"the maximum allowed size of {_bytes_to_mb(MAX_FILE_SIZE_BYTES)} MB."
            ),
        )
    file_item.file.seek(0)
    return file_size


def _load_analysis_context(
    enabled_rule_ids: str | None,
) -> tuple:
    config = get_decrypted_api_key()
    if not config:
        raise HTTPException(status_code=400, detail="No LLM provider configured.")
    provider, api_key = config

    rules = get_rules()
    all_rules = [rule for rule in rules["rules"] if rule.get("text", "").strip()]
    if not all_rules:
        raise HTTPException(status_code=400, detail="Global rules are not configured.")

    requested_rule_ids = _parse_enabled_rule_ids(enabled_rule_ids)
    if requested_rule_ids is None:
        selected_rules = all_rules
    else:
        selected_rules = [rule for rule in all_rules if rule.get("id") in requested_rule_ids]
    if not selected_rules:
        raise HTTPException(status_code=400, detail="Select at least one rule before starting analysis.")

    rule_lines = [rule["text"].strip() for rule in selected_rules if rule.get("text", "").strip()]
    applied_rule_items = [RuleItem(**rule) for rule in selected_rules]
    return provider, api_key, rule_lines, applied_rule_items


def _analyze_single_docx(
    file_item: UploadFile,
    provider,
    api_key: str,
    rule_lines: list[str],
    applied_rule_items: list[RuleItem],
) -> AnalyzeResponse:
    uploaded_file_size = _validate_upload(file_item)
    original_file_name = file_item.filename or "document.docx"
    log_event(
        "analysis.started",
        {
            "file_name": original_file_name,
            "file_size_bytes": uploaded_file_size,
            "rules_count": len(rule_lines),
        },
    )

    try:
        if uploaded_file_size == 0:
            # For empty uploads, analyze file name only and skip DOCX parsing.
            document_text = ""
        else:
            storage_path, original_file_name = save_uploaded_docx(file_item)
            document_text = extract_docx_text(storage_path)
            if not document_text.strip():
                raise HTTPException(status_code=400, detail=f'Document "{original_file_name}" appears to be empty.')

        analysis_json, prompt = analyze_document(
            provider=provider,
            api_key=api_key,
            file_name=original_file_name,
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
                "applied_rule_ids": [rule.id for rule in applied_rule_items],
                "applied_rules_count": len(applied_rule_items),
                "created_at": created_at.isoformat(),
            }
        )
        log_event(
            "analysis.completed",
            {
                "run_id": run_id,
                "file_name": original_file_name,
                "provider": provider.value,
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
            applied_rules=applied_rule_items,
            analysis=analysis_json,
            created_at=created_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log_event("analysis.failed", {"file_name": original_file_name, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@router.post("", response_model=AnalyzeResponse)
def analyze_docx(
    file: UploadFile = File(...),
    enabled_rule_ids: str | None = Form(default=None),
) -> AnalyzeResponse:
    provider, api_key, rule_lines, applied_rule_items = _load_analysis_context(enabled_rule_ids)
    return _analyze_single_docx(file, provider, api_key, rule_lines, applied_rule_items)


@router.post("/bulk", response_model=BulkAnalyzeResponse)
def analyze_docx_bulk(
    files: list[UploadFile] = File(...),
    enabled_rule_ids: str | None = Form(default=None),
) -> BulkAnalyzeResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one .docx file.")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files uploaded ({len(files)}). Maximum allowed is {MAX_FILES_PER_REQUEST}.",
        )

    provider, api_key, rule_lines, applied_rule_items = _load_analysis_context(enabled_rule_ids)
    items: list[BulkAnalyzeItem] = []

    for upload_file in files:
        try:
            result = _analyze_single_docx(upload_file, provider, api_key, rule_lines, applied_rule_items)
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
