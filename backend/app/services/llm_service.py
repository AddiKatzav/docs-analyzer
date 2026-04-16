import json
import re
from typing import Any

import httpx
from anthropic import Anthropic
from openai import OpenAI

from app.models import Provider

ANTHROPIC_MODEL_CANDIDATES = [
    "claude-3-5-haiku-latest",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]

WEAPON_FILE_NAME_INDICATORS = {
    "mlrs",
    "atgm",
    "icbm",
    "tank",
    "artillery",
    "missile",
    "rocket",
    "warhead",
    "glock",
    "rifle",
    "pistol",
    "grenade",
    "howitzer",
    "mortar",
    "ak47",
    "m16",
}


def _create_openai_client(api_key: str) -> OpenAI:
    try:
        return OpenAI(api_key=api_key)
    except TypeError as exc:
        # Compatibility fallback for environments where OpenAI SDK and httpx versions
        # disagree on the "proxies" argument in the default internal client.
        if "proxies" not in str(exc):
            raise
        return OpenAI(api_key=api_key, http_client=httpx.Client())


def _openai_text_response(client: OpenAI, prompt: str, max_tokens: int) -> str:
    """
    Support both OpenAI SDK styles:
    - newer: client.responses.create(...)
    - older: client.chat.completions.create(...)
    """
    if hasattr(client, "responses"):
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            max_output_tokens=max_tokens,
        )
        return getattr(response, "output_text", "") or ""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def _is_anthropic_model_not_found(exc: Exception) -> bool:
    message = str(exc).lower()
    return "not_found_error" in message or "model:" in message


def _anthropic_text_response(client: Anthropic, prompt: str, max_tokens: int) -> str:
    last_error: Exception | None = None
    for model_name in ANTHROPIC_MODEL_CANDIDATES:
        try:
            response = client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    text += block.text
            if text.strip():
                return text
        except Exception as exc:
            last_error = exc
            if _is_anthropic_model_not_found(exc):
                continue
            raise
    if last_error:
        raise last_error
    raise ValueError("No Anthropic model produced a valid text response.")


def verify_provider_key(provider: Provider, api_key: str) -> None:
    if provider == Provider.OPENAI:
        client = _create_openai_client(api_key=api_key)
        _openai_text_response(client, prompt="Reply only with OK", max_tokens=5)
        return

    client = Anthropic(api_key=api_key)
    _anthropic_text_response(client, prompt="Reply only with OK", max_tokens=5)


def _analysis_prompt(file_name: str, rules_text: str, document_text: str) -> str:
    return (
        "You are a document compliance analyzer.\n"
        "Analyze both the file name and the document content according to the provided system rules.\n"
        "Return only JSON (no markdown, no code fences, no extra text).\n"
        "Return strict JSON with this schema:\n"
        "{\n"
        '  "summary": "short text",\n'
        '  "violations": [\n'
        "    {\n"
        '      "rule": "rule text",\n'
        '      "severity": "low|medium|high",\n'
        '      "evidence": "snippet from document",\n'
        '      "explanation": "why it violates"\n'
        "    }\n"
        "  ],\n"
        '  "compliant": true_or_false\n'
        "}\n\n"
        f"FILE NAME:\n{file_name[:200]}\n\n"
        f"SYSTEM RULES:\n{rules_text}\n\n"
        f"DOCUMENT TEXT:\n{document_text[:12000]}"
    )


def _repair_prompt(raw_response: str) -> str:
    return (
        "You will receive a malformed JSON payload from another model.\n"
        "Your task: convert it into valid strict JSON ONLY (no markdown or explanation).\n"
        "Use this schema exactly:\n"
        "{\n"
        '  "summary": "short text",\n'
        '  "violations": [\n'
        "    {\n"
        '      "rule": "rule text",\n'
        '      "severity": "low|medium|high",\n'
        '      "evidence": "snippet from document",\n'
        '      "explanation": "why it violates"\n'
        "    }\n"
        "  ],\n"
        '  "compliant": true_or_false\n'
        "}\n\n"
        "Fix escaping/commas/quotes as needed, but preserve semantic meaning.\n\n"
        f"MALFORMED INPUT:\n{raw_response[:16000]}"
    )


def _extract_json_slice(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response was not valid JSON.")
    return stripped[start : end + 1]


def _extract_json(raw: str) -> dict[str, Any]:
    candidate = _extract_json_slice(raw)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Common model issue: trailing commas before } or ].
        without_trailing_commas = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(without_trailing_commas)


def _rules_list(rules_text: str) -> list[str]:
    lines = [line.strip() for line in rules_text.splitlines() if line.strip()]
    normalized: list[str] = []
    for line in lines:
        normalized.append(line[2:].strip() if line.startswith("- ") else line)
    return [line for line in normalized if line]


def _file_name_tokens(file_name: str) -> set[str]:
    normalized = file_name.lower().replace("_", " ").replace("-", " ")
    return {token for token in re.findall(r"[a-z0-9]+", normalized) if token}


def _enforce_filename_rule_guards(file_name: str, rules_text: str, analysis: dict[str, Any]) -> dict[str, Any]:
    if str(analysis.get("status", "")).lower() == "parsing_error":
        return analysis
    rules = _rules_list(rules_text)
    if not rules:
        return analysis
    tokens = _file_name_tokens(file_name)
    violations = analysis.get("violations")
    if not isinstance(violations, list):
        violations = []
    existing_payload = json.dumps(violations, ensure_ascii=False).lower()
    matched_indicator = next((term for term in WEAPON_FILE_NAME_INDICATORS if term in tokens), None)
    if not matched_indicator:
        analysis["violations"] = violations
        analysis["compliant"] = bool(analysis.get("compliant", True) and len(violations) == 0)
        return analysis

    for rule in rules:
        lowered_rule = rule.lower()
        if ("weapon" not in lowered_rule) or ("system" not in lowered_rule):
            continue
        if lowered_rule in existing_payload or matched_indicator in existing_payload:
            continue
        violations.append(
            {
                "rule": rule,
                "severity": "high",
                "evidence": f'File name "{file_name}"',
                "explanation": (
                    f'File name contains weapon-system indicator "{matched_indicator.upper()}", '
                    "which violates this rule."
                ),
            }
        )

    analysis["violations"] = violations
    analysis["compliant"] = len(violations) == 0
    if not analysis["compliant"] and not str(analysis.get("summary", "")).strip():
        analysis["summary"] = "File name or content violates one or more configured rules."
    return analysis


def _fallback_analysis_from_parse_error(parse_error: Exception) -> dict[str, Any]:
    return {
        "summary": "Model response could not be parsed as valid JSON. Review output manually.",
        "status": "parsing_error",
        "violations": [
            {
                "rule": "LLM output format validation",
                "severity": "high",
                "evidence": "",
                "explanation": f"Parser error: {parse_error}",
            }
        ],
        "compliant": None,
    }


def _repair_json_response(provider: Provider, api_key: str, malformed_response: str) -> str:
    prompt = _repair_prompt(malformed_response)
    if provider == Provider.OPENAI:
        client = _create_openai_client(api_key=api_key)
        return _openai_text_response(client, prompt=prompt, max_tokens=800)

    client = Anthropic(api_key=api_key)
    return _anthropic_text_response(client, prompt=prompt, max_tokens=800)


def analyze_document(
    provider: Provider, api_key: str, file_name: str, rules_text: str, document_text: str
) -> tuple[dict[str, Any], str]:
    prompt = _analysis_prompt(file_name=file_name, rules_text=rules_text, document_text=document_text)
    if provider == Provider.OPENAI:
        client = _create_openai_client(api_key=api_key)
        text = _openai_text_response(client, prompt=prompt, max_tokens=500)
        try:
            parsed = _extract_json(text)
        except ValueError:
            repaired = _repair_json_response(provider=provider, api_key=api_key, malformed_response=text)
            try:
                parsed = _extract_json(repaired)
            except ValueError as parse_error:
                parsed = _fallback_analysis_from_parse_error(parse_error)
        return _enforce_filename_rule_guards(file_name=file_name, rules_text=rules_text, analysis=parsed), prompt

    client = Anthropic(api_key=api_key)
    text = _anthropic_text_response(client, prompt=prompt, max_tokens=500)
    try:
        parsed = _extract_json(text)
    except ValueError:
        repaired = _repair_json_response(provider=provider, api_key=api_key, malformed_response=text)
        try:
            parsed = _extract_json(repaired)
        except ValueError as parse_error:
            parsed = _fallback_analysis_from_parse_error(parse_error)
    return _enforce_filename_rule_guards(file_name=file_name, rules_text=rules_text, analysis=parsed), prompt
