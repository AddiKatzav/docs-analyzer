#!/usr/bin/env python3
# pylint: disable=import-error,broad-exception-caught
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from cryptography.fernet import Fernet

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SUPPORTED_SUFFIXES = {".docx", ".txt", ".md"}


def _default_storage_dir() -> Path:
    local_data_dir = REPO_ROOT / ".local_data" / "backend"
    if local_data_dir.exists():
        return local_data_dir
    return REPO_ROOT / "backend" / "data"


def _rules_file(storage_dir: Path) -> Path:
    return storage_dir / "global_rules.json"


def _config_file(storage_dir: Path) -> Path:
    return storage_dir / "llm_config.json"


def _secret_file(storage_dir: Path) -> Path:
    return storage_dir / "secret.key"


def _sync_rules_from_api(api_base_url: str, storage_dir: Path) -> None:
    normalized = api_base_url.rstrip("/")
    endpoint = f"{normalized}/api/rules"
    try:
        with urlopen(endpoint, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Failed to sync rules (HTTP {exc.code}) from {endpoint}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to connect to {endpoint}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Rules endpoint returned invalid JSON.") from exc

    rules = payload.get("rules", [])
    if not isinstance(rules, list):
        raise RuntimeError("Rules endpoint payload is invalid: 'rules' must be a list.")

    normalized_rules: list[dict[str, str]] = []
    for item in rules:
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("id", "")).strip()
        text = str(item.get("text", "")).strip()
        if rule_id and text:
            normalized_rules.append({"id": rule_id, "text": text})

    updated_at = payload.get("updated_at")
    storage_dir.mkdir(parents=True, exist_ok=True)
    _rules_file(storage_dir).write_text(
        json.dumps({"rules": normalized_rules, "updated_at": updated_at}, indent=2),
        encoding="utf-8",
    )


def _extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        from docx import Document

        document = Document(str(file_path))
        return "\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())
    return file_path.read_text(encoding="utf-8", errors="ignore")


def _collect_files(data_dir: Path, max_files: int, explicit_files: list[Path] | None = None) -> list[Path]:
    if explicit_files:
        resolved: list[Path] = []
        for file_path in explicit_files:
            candidate = file_path.resolve()
            if not candidate.exists() or not candidate.is_file():
                raise RuntimeError(f"Explicit file does not exist or is not a file: {candidate}")
            if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
                raise RuntimeError(
                    f"Unsupported file type for explicit file: {candidate.name}. "
                    f"Supported types: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
                )
            resolved.append(candidate)
        return resolved[:max_files]
    candidates = [path for path in sorted(data_dir.rglob("*")) if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES]
    return candidates[:max_files]


def _load_provider_and_key(storage_dir: Path) -> tuple[str, str]:
    config_path = _config_file(storage_dir)
    secret_path = _secret_file(storage_dir)
    if not config_path.exists() or not secret_path.exists():
        raise RuntimeError(f"Config files not found in {storage_dir}. Save provider/API key in app first.")
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    encrypted_api_key = str(config_payload.get("encrypted_api_key", "")).strip()
    provider_raw = str(config_payload.get("provider", "")).strip().upper()
    if not encrypted_api_key or not provider_raw:
        raise RuntimeError("Stored config is invalid: missing provider or encrypted_api_key.")
    if provider_raw not in {"OPENAI", "CLAUDE"}:
        raise RuntimeError(f"Stored provider '{provider_raw}' is not supported.")
    fernet = Fernet(secret_path.read_bytes())
    api_key = fernet.decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")
    return provider_raw, api_key


def _load_rules(storage_dir: Path) -> list[dict]:
    rules_path = _rules_file(storage_dir)
    if not rules_path.exists():
        raise RuntimeError(f"Rules file not found: {rules_path}")
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    if "rules" in payload and isinstance(payload["rules"], list):
        rules = payload["rules"]
    else:
        # Backward compatibility with older rules_text blob format.
        rules_text = str(payload.get("rules_text", "")).strip()
        rules = [{"id": f"legacy-{idx}", "text": line.strip()} for idx, line in enumerate(rules_text.splitlines(), start=1) if line.strip()]
    active_rules = [rule for rule in rules if str(rule.get("text", "")).strip()]
    return active_rules


def _analyze_files(
    data_dir: Path,
    output_path: Path,
    max_files: int,
    storage_dir: Path,
    dry_run: bool,
    explicit_files: list[Path] | None = None,
) -> None:
    provider, api_key = _load_provider_and_key(storage_dir=storage_dir)
    active_rules = _load_rules(storage_dir=storage_dir)
    if not active_rules:
        raise RuntimeError("No global rules found. Add rules in app or sync from API.")

    rule_lines = [str(rule["text"]).strip() for rule in active_rules]
    files = _collect_files(data_dir=data_dir, max_files=max_files, explicit_files=explicit_files)
    if not files:
        raise RuntimeError(f"No supported files found in {data_dir}.")

    if dry_run:
        print("Dry run OK")
        print(f"- storage_dir: {storage_dir}")
        print(f"- rules_file: {_rules_file(storage_dir)}")
        print(f"- provider: {provider}")
        print(f"- rules_count: {len(rule_lines)}")
        print(f"- files_discovered: {len(files)}")
        print(f"- first_file: {files[0]}")
        return

    from app.models import Provider as AppProvider
    from app.services.llm_service import analyze_document

    provider_enum = AppProvider(provider)
    results = []
    for file_path in files:
        document_text = _extract_text(file_path)
        try:
            report_path = str(file_path.relative_to(REPO_ROOT))
        except ValueError:
            report_path = str(file_path)
        analysis, _prompt = analyze_document(
            provider=provider_enum,
            api_key=api_key,
            file_name=file_path.name,
            rules_text="\n".join(f"- {line}" for line in rule_lines),
            document_text=document_text,
        )
        violations = analysis.get("violations", [])
        results.append(
            {
                "file_path": report_path,
                "summary": analysis.get("summary"),
                "compliant": analysis.get("compliant"),
                "violations_count": len(violations) if isinstance(violations, list) else 0,
                "analysis": analysis,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "provider": provider,
                "rules_count": len(rule_lines),
                "files_analyzed": len(results),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze files from data folder using app global rules.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / ".local_data" / "backend",
        help="Directory containing files to analyze.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / ".local_data" / "backend" / "agent_analysis_results.json",
        help="JSON output file path.",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=_default_storage_dir(),
        help="Directory containing app persisted files (global_rules.json, llm_config.json, secret.key).",
    )
    parser.add_argument(
        "--sync-rules-from-api",
        action="store_true",
        help="Sync rules from /api/rules before analysis.",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://localhost:8000",
        help="Base URL for the running app when syncing rules.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=200,
        help="Maximum number of files to analyze.",
    )
    parser.add_argument(
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="Explicit file path to analyze. Repeat for multiple files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate storage/config/rules/files without calling an external LLM.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        storage_dir = args.storage_dir.resolve()
        data_dir = args.data_dir.resolve()
        output_path = args.output.resolve()
        if args.sync_rules_from_api:
            _sync_rules_from_api(args.api_base_url, storage_dir=storage_dir)
        _analyze_files(
            data_dir=data_dir,
            output_path=output_path,
            max_files=args.max_files,
            storage_dir=storage_dir,
            dry_run=args.dry_run,
            explicit_files=args.files,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    if not args.dry_run:
        print(f"Analysis completed. Report saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
