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

    response = client.post("/api/rules", json={"text": "rule two"})
    assert response.status_code == 200

    response = client.get("/api/rules")
    body = response.json()
    assert len(body["rules"]) == 2
    assert body["rules"][0]["text"] == "rule one"
    assert body["rules"][1]["text"] == "rule two"

    rule_to_remove = body["rules"][0]["id"]
    removed = client.delete(f"/api/rules/{rule_to_remove}")
    assert removed.status_code == 200
    removed_body = removed.json()
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


def test_rules_reject_script_like_payload() -> None:
    _clear_data_files()
    response = client.post("/api/rules", json={"text": "<script>alert(1)</script>"})
    assert response.status_code == 422
    assert "angle brackets" in str(response.json()["detail"]).lower()


def test_analyze_uses_global_rules(monkeypatch) -> None:
    _clear_data_files()
    client.put("/api/config", json={"provider": "OPENAI", "api_key": "sk-test-1"})
    client.post("/api/rules", json={"text": "never leak secret tokens"})

    def fake_analyze(provider, api_key, file_name, rules_text, document_text):
        assert provider == Provider.OPENAI
        assert api_key == "sk-test-1"
        assert file_name == "sample.docx"
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
    assert body["analysis"]["compliant"] is False
    assert len(body["applied_rules"]) == 1
    assert len(client.get("/api/runs").json()) == 1


def test_bulk_analyze_processes_all_files(monkeypatch) -> None:
    _clear_data_files()
    client.put("/api/config", json={"provider": "OPENAI", "api_key": "sk-test-1"})
    client.post("/api/rules", json={"text": "never leak secret tokens"})

    def fake_analyze(provider, api_key, file_name, rules_text, document_text):
        assert provider == Provider.OPENAI
        assert api_key == "sk-test-1"
        assert "- never leak secret tokens" in rules_text
        assert file_name in {"ok.docx", "bad.docx"}
        if "force failure" in document_text:
            raise RuntimeError("simulated model failure")
        return (
            {
                "summary": "No violations",
                "violations": [],
                "compliant": True,
            },
            "prompt text",
        )

    monkeypatch.setattr("app.api.analyze.analyze_document", fake_analyze)

    ok_file = _build_docx_bytes("Everything is compliant")
    bad_file = _build_docx_bytes("force failure")
    response = client.post(
        "/api/analyze/bulk",
        files=[
            (
                "files",
                (
                    "ok.docx",
                    ok_file,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            (
                "files",
                (
                    "bad.docx",
                    bad_file,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["succeeded"] == 1
    assert body["failed"] == 1
    assert len(body["items"]) == 2
    assert body["items"][0]["ok"] is True
    assert body["items"][0]["result"]["file_name"] == "ok.docx"
    assert body["items"][1]["ok"] is False
    assert "simulated model failure" in body["items"][1]["error"]
    assert len(client.get("/api/runs").json()) == 1


def test_analyze_rejects_large_file_with_user_friendly_message() -> None:
    _clear_data_files()
    client.put("/api/config", json={"provider": "OPENAI", "api_key": "sk-test-1"})
    client.post("/api/rules", json={"text": "never leak secret tokens"})
    oversized_content = b"x" * ((10 * 1024 * 1024) + 1)
    response = client.post(
        "/api/analyze",
        files={
            "file": (
                "large.docx",
                oversized_content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400
    assert "exceeds the maximum allowed size" in response.json()["detail"]


def test_analyze_empty_file_uses_filename_only(monkeypatch) -> None:
    _clear_data_files()
    client.put("/api/config", json={"provider": "OPENAI", "api_key": "sk-test-1"})
    client.post("/api/rules", json={"text": "generic rule"})

    def fake_analyze(provider, api_key, file_name, rules_text, document_text):
        assert provider == Provider.OPENAI
        assert api_key == "sk-test-1"
        assert file_name == "empty.docx"
        assert "- generic rule" in rules_text
        assert document_text == ""
        return (
            {
                "summary": "filename-only analysis",
                "violations": [],
                "compliant": True,
            },
            "prompt text",
        )

    monkeypatch.setattr("app.api.analyze.analyze_document", fake_analyze)

    response = client.post(
        "/api/analyze",
        files={
            "file": (
                "empty.docx",
                b"",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["analysis"]["summary"] == "filename-only analysis"
