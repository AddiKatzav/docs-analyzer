import json
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from app.models import Provider


def verify_provider_key(provider: Provider, api_key: str) -> None:
    if provider == Provider.OPENAI:
        client = OpenAI(api_key=api_key)
        client.responses.create(
            model="gpt-4o-mini",
            input="Reply only with OK",
            max_output_tokens=5,
        )
        return

    client = Anthropic(api_key=api_key)
    client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=5,
        messages=[{"role": "user", "content": "Reply only with OK"}],
    )


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
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            max_output_tokens=500,
        )
        text = response.output_text
        return _extract_json(text), prompt

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text += block.text
    return _extract_json(text), prompt
