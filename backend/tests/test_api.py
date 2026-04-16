from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.models import Provider
from app.services import paths

client = TestClient(app)


def _clear_data_files() -> None:
    for path in [paths.CONFIG_FILE, paths.RULES_FILE, paths.RUNS_FILE, paths.AUDIT_FILE]:
        if path.exists():
            path.unlink()
    if paths.UPLOADS_DIR.exists():
        for item in paths.UPLOADS_DIR.iterdir():
            item.unlink()


def _build_docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    data = BytesIO()
    doc.save(data)
    return data.getvalue()


def test_rules_are_global_singleton() -> None:
    _clear_data_files()
    response = client.post("/api/rules", json={"text": "rule one"})
    assert response.status_code == 200
    assert response.json()["version"] == 1

    response = client.post("/api/rules", json={"text": "rule two"})
    assert response.status_code == 200
    assert response.json()["version"] == 2

    response = client.get("/api/rules")
    body = response.json()
    assert len(body["rules"]) == 2
    assert body["rules"][0]["text"] == "rule one"
    assert body["rules"][1]["text"] == "rule two"
    assert body["version"] == 2

    rule_to_remove = body["rules"][0]["id"]
    removed = client.delete(f"/api/rules/{rule_to_remove}")
    assert removed.status_code == 200
    removed_body = removed.json()
    assert removed_body["version"] == 3
    assert len(removed_body["rules"]) == 1
    assert removed_body["rules"][0]["text"] == "rule two"


def test_config_save_replaces_previous_key(monkeypatch) -> None:
    _clear_data_files()

    def fake_verify(provider, api_key):
        assert provider in [Provider.OPENAI, Provider.CLAUDE]
        assert api_key

    monkeypatch.setattr("app.api.config.verify_provider_key", fake_verify)

    verify_response = client.post(
        "/api/config/verify",
        json={"provider": "OPENAI", "api_key": "sk-test-1"},
    )
    assert verify_response.status_code == 200

    save1 = client.put("/api/config", json={"provider": "OPENAI", "api_key": "sk-test-1"})
    assert save1.status_code == 200
    save2 = client.put("/api/config", json={"provider": "CLAUDE", "api_key": "sk-ant-2"})
    assert save2.status_code == 200

    status = client.get("/api/config/status")
    body = status.json()
    assert body["configured"] is True
    assert body["provider"] == "CLAUDE"


def test_analyze_uses_global_rules(monkeypatch) -> None:
    _clear_data_files()
    client.put("/api/config", json={"provider": "OPENAI", "api_key": "sk-test-1"})
    client.post("/api/rules", json={"text": "never leak secret tokens"})

    def fake_analyze(provider, api_key, rules_text, document_text):
        assert provider == Provider.OPENAI
        assert api_key == "sk-test-1"
        assert "- never leak secret tokens" in rules_text
        assert "secret token abc" in document_text
        return (
            {
                "summary": "Found one issue",
                "violations": [
                    {
                        "rule": "never leak secret tokens",
                        "severity": "high",
                        "evidence": "secret token abc",
                        "explanation": "token leaked",
                    }
                ],
                "compliant": False,
            },
            "prompt text",
        )

    monkeypatch.setattr("app.api.analyze.analyze_document", fake_analyze)

    file_bytes = _build_docx_bytes("This file contains secret token abc")
    response = client.post(
        "/api/analyze",
        files={
            "file": (
                "sample.docx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rules_version"] == 1
    assert body["analysis"]["compliant"] is False
    assert len(client.get("/api/runs").json()) == 1
