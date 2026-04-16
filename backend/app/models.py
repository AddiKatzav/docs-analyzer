from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    text: str = Field(min_length=1)


class RuleItem(BaseModel):
    id: str
    text: str


class GlobalRulesResponse(BaseModel):
    rules: list[RuleItem]
    version: int
    updated_at: datetime | None


class AnalyzeResponse(BaseModel):
    run_id: str
    file_name: str
    provider: Provider
    rules_version: int
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


class AnalysisRunSummary(BaseModel):
    run_id: str
    file_name: str
    provider: Provider
    rules_version: int
    created_at: datetime
