"""Versioned evidence and synthesis contracts."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(Model):
    adapter: str
    query: str = Field(min_length=1, max_length=500)
    status: Literal["retrieved", "unavailable", "blocked"]
    url: HttpUrl | None = None
    title: str = Field(default="", max_length=300)
    excerpt: str = Field(default="", max_length=1200)
    excerpt_kind: Literal["api_fields", "search_snippet", "none"] = "none"
    credibility: Literal["primary", "secondary", "unknown"] = "unknown"
    reason: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def consistent(self):
        if self.status == "retrieved":
            if not self.url or not self.excerpt.strip() or self.excerpt_kind == "none":
                raise ValueError("Retrieved evidence needs a URL, verbatim excerpt and kind")
            if self.reason:
                raise ValueError("Retrieved evidence cannot have a failure reason")
        elif not self.reason or self.excerpt or self.excerpt_kind != "none":
            raise ValueError("Retrieval failures need a reason and cannot contain evidence")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("Evidence timestamps must be timezone-aware")
        return self


class Evidence(Observation):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=r"^E[0-9]{4,}$")
    raw_path: str | None = None
    excerpt_sha256: str | None = None


class Query(Model):
    adapter: Literal["github", "websearch"]
    query: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=300)


class Plan(Model):
    subquestions: list[str] = Field(min_length=1, max_length=4)
    queries: list[Query] = Field(min_length=1, max_length=6)


class Claim(Model):
    text: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    confidence: Literal["high", "medium", "low"]
    rationale: str = Field(min_length=1, max_length=500)


class Synthesis(Model):
    claims: list[Claim] = Field(max_length=20)
    gaps: list[str] = Field(max_length=20)
