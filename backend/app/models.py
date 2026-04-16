from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Provider(str, Enum):
    OPENAI = "OPENAI"
    CLAUDE = "CLAUDE"


class VerifyConfigRequest(BaseModel):
    provider: Provider
    api_key: str = Field(min_length=8)


class SaveConfigRequest(BaseModel):
    provider: Provider
    api_key: str = Field(min_length=8)


class ConfigStatusResponse(BaseModel):
    provider: Provider | None
    configured: bool
    updated_at: datetime | None


class RuleCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def validate_rule_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Rule text is required.")
        if any(ord(char) < 32 and char not in {"\n", "\r", "\t"} for char in cleaned):
            raise ValueError("Rule text contains unsupported control characters.")
        if "<" in cleaned or ">" in cleaned:
            raise ValueError("Rule text cannot include angle brackets.")
        if "javascript:" in cleaned.lower():
            raise ValueError("Rule text cannot include script-like URLs.")
        return cleaned


class RuleItem(BaseModel):
    id: str
    text: str


class GlobalRulesResponse(BaseModel):
    rules: list[RuleItem]
    updated_at: datetime | None


class AnalyzeResponse(BaseModel):
    run_id: str
    file_name: str
    provider: Provider
    applied_rules: list[RuleItem]
    analysis: dict[str, Any]
    created_at: datetime


class BulkAnalyzeItem(BaseModel):
    file_name: str
    ok: bool
    result: AnalyzeResponse | None = None
    error: str | None = None


class BulkAnalyzeResponse(BaseModel):
    items: list[BulkAnalyzeItem]
    total: int
    succeeded: int
    failed: int


class AnalyzeBatchResponse(BaseModel):
    results: list[AnalyzeResponse]


class AnalysisRunSummary(BaseModel):
    run_id: str
    file_name: str
    provider: Provider
    applied_rules_count: int
    created_at: datetime
