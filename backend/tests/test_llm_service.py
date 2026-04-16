from app.models import Provider
from app.services import llm_service


def test_extract_json_handles_codefence_and_trailing_comma() -> None:
    raw = """```json
{
  "summary": "ok",
  "violations": [],
  "compliant": true,
}
```"""
    parsed = llm_service._extract_json(raw)
    assert parsed["summary"] == "ok"
    assert parsed["violations"] == []
    assert parsed["compliant"] is True


def test_analyze_document_repairs_invalid_json(monkeypatch) -> None:
    calls = {"count": 0}

    class DummyOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    def fake_openai_response(client, prompt, max_tokens):
        calls["count"] += 1
        if calls["count"] == 1:
            # Invalid JSON due to unescaped quote in evidence text.
            return (
                '{"summary":"bad","violations":[{"rule":"r","severity":"high",'
                '"evidence":"מערכת "נחום תקום"","explanation":"x"}],"compliant":false}'
            )
        return (
            '{"summary":"bad","violations":[{"rule":"r","severity":"high",'
            '"evidence":"מערכת \\"נחום תקום\\"","explanation":"x"}],"compliant":false}'
        )

    monkeypatch.setattr(llm_service, "OpenAI", DummyOpenAI)
    monkeypatch.setattr(llm_service, "_openai_text_response", fake_openai_response)

    analysis, _prompt = llm_service.analyze_document(
        provider=Provider.OPENAI,
        api_key="sk-test",
        rules_text="- some rule",
        document_text="doc text",
    )

    assert calls["count"] == 2
    assert analysis["compliant"] is False
    assert analysis["violations"][0]["severity"] == "high"
