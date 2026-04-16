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
        file_name="sample.docx",
        rules_text="- some rule",
        document_text="doc text",
    )

    assert calls["count"] == 2
    assert analysis["compliant"] is False
    assert analysis["violations"][0]["severity"] == "high"


def test_filename_weapon_indicator_forces_violation() -> None:
    analysis = {
        "summary": "No issues found",
        "violations": [],
        "compliant": True,
    }
    updated = llm_service._enforce_filename_rule_guards(
        file_name="MLRS version 5.1 description.docx",
        rules_text="- dont mention weapon systems",
        analysis=analysis,
    )
    assert updated["compliant"] is False
    assert len(updated["violations"]) == 1
    assert "MLRS" in updated["violations"][0]["explanation"]
    assert updated["violations"][0]["rule"] == "dont mention weapon systems"


def test_analyze_document_returns_fallback_when_repair_still_invalid(monkeypatch) -> None:
    class DummyOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    calls = {"count": 0}

    def fake_openai_response(client, prompt, max_tokens):
        calls["count"] += 1
        if calls["count"] == 1:
            return '{"summary":"bad","violations":[{"rule":"r","severity":"high","evidence":"x","explanation":"y"}],"compliant":false'
        return '{"summary":"still bad","violations":[{"rule":"r","severity":"high","evidence":"x","explanation":"y"}],"compliant":false'

    monkeypatch.setattr(llm_service, "OpenAI", DummyOpenAI)
    monkeypatch.setattr(llm_service, "_openai_text_response", fake_openai_response)

    analysis, _prompt = llm_service.analyze_document(
        provider=Provider.OPENAI,
        api_key="sk-test",
        file_name="יונתן הקטן.docx",
        rules_text="- dont mention weapon systems",
        document_text="text",
    )

    assert calls["count"] == 2
    assert analysis["status"] == "parsing_error"
    assert analysis["compliant"] is None
    assert analysis["violations"][0]["rule"] == "LLM output format validation"


def test_create_openai_client_falls_back_when_proxies_typeerror(monkeypatch) -> None:
    calls: list[dict] = []

    class DummyHttpxClient:
        pass

    def fake_httpx_client():
        return DummyHttpxClient()

    class DummyOpenAI:
        def __init__(self, **kwargs) -> None:
            calls.append(kwargs)
            if "http_client" not in kwargs:
                raise TypeError("Client.__init__() got an unexpected keyword argument 'proxies'")
            self.kwargs = kwargs

    monkeypatch.setattr(llm_service.httpx, "Client", fake_httpx_client)
    monkeypatch.setattr(llm_service, "OpenAI", DummyOpenAI)

    client = llm_service._create_openai_client(api_key="sk-test")

    assert isinstance(client, DummyOpenAI)
    assert len(calls) == 2
    assert calls[0] == {"api_key": "sk-test"}
    assert calls[1]["api_key"] == "sk-test"
    assert isinstance(calls[1]["http_client"], DummyHttpxClient)
