import json
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from app.models import Provider

ANTHROPIC_MODEL_CANDIDATES = [
    "claude-3-5-haiku-latest",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]


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
        client = OpenAI(api_key=api_key)
        _openai_text_response(client, prompt="Reply only with OK", max_tokens=5)
        return

    client = Anthropic(api_key=api_key)
    _anthropic_text_response(client, prompt="Reply only with OK", max_tokens=5)


def _analysis_prompt(rules_text: str, document_text: str) -> str:
    return (
        "You are a document compliance analyzer.\n"
        "Analyze the document according to the provided system rules.\n"
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
        f"SYSTEM RULES:\n{rules_text}\n\n"
        f"DOCUMENT TEXT:\n{document_text[:12000]}"
    )


def _extract_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response was not valid JSON.")
    return json.loads(raw[start : end + 1])


def analyze_document(
    provider: Provider, api_key: str, rules_text: str, document_text: str
) -> tuple[dict[str, Any], str]:
    prompt = _analysis_prompt(rules_text=rules_text, document_text=document_text)
    if provider == Provider.OPENAI:
        client = OpenAI(api_key=api_key)
        text = _openai_text_response(client, prompt=prompt, max_tokens=500)
        return _extract_json(text), prompt

    client = Anthropic(api_key=api_key)
    text = _anthropic_text_response(client, prompt=prompt, max_tokens=500)
    return _extract_json(text), prompt
