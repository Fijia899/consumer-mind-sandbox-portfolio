"""Contracts for source-backed profiles and explicitly hypothetical archetypes."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Message(Strict):
    id: str = Field(pattern=r"^[\w-]{1,80}$")
    speaker: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=4000)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def times(self):
        if (self.start is None) != (self.end is None) or (self.start is not None and self.end < self.start):
            raise ValueError("音频起止时间无效")
        return self


class Evidence(Strict):
    message_id: str
    quote: str = Field(min_length=2, max_length=1200)


class Need(Strict):
    id: str = Field(pattern=r"^[\w-]{1,80}$")
    label: str = Field(min_length=2, max_length=250)
    kind: Literal["fact", "inference", "assumption"]
    hard: bool = False
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)


class ProfileContent(Strict):
    summary: str = Field(min_length=2, max_length=800)
    needs: list[Need] = Field(min_length=1, max_length=16)
    unknowns: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def distinct(self):
        if len({n.id for n in self.needs}) != len(self.needs):
            raise ValueError("需求 ID 不能重复")
        return self


class ProfileRequest(Strict):
    label: str = Field(min_length=2, max_length=100)
    target_speaker: str = Field(default="客户", min_length=1, max_length=80)
    episode: str = Field(min_length=2, max_length=180)
    text: str = Field(default="", max_length=40000)
    messages: list[Message] = Field(default_factory=list, max_length=240)
    media_id: str | None = Field(default=None, pattern=r"^M[a-f0-9]{24}$")
    consent: Literal[True]


class ReviewRequest(ProfileContent):
    expected_revision: int = Field(ge=1)
    reviewer: str = Field(min_length=1, max_length=80)


class PrototypeRequest(ProfileContent):
    label: str = Field(min_length=2, max_length=100)
    episode: str = Field(min_length=2, max_length=180)


class AnalysisRequest(Strict):
    mode: Literal["personal", "general"]
    plan: str = Field(min_length=5, max_length=10000)
    profile_ids: list[str] = Field(default_factory=list, max_length=48)
    constraints: str = Field(default="", max_length=2000)
    discussion: str = Field(default="", max_length=2000)
    cohort_size: int = Field(default=24, ge=1, le=48)


class CompareRequest(Strict):
    plan: str = Field(min_length=5, max_length=10000)
    discussion: str = Field(default="", max_length=2000)


class DiscussionRequest(Strict):
    discussion: str = Field(min_length=5, max_length=2000)


class DimensionMatch(Strict):
    factor_id: str
    rationale: str = Field(min_length=2, max_length=400)
    plan_quote: str = Field(min_length=2, max_length=1200)


class Assessment(Strict):
    need_id: str
    status: Literal["met", "partial", "conflict", "uncovered", "unknown"]
    explanation: str = Field(min_length=2, max_length=600)
    plan_quotes: list[str] = Field(default_factory=list, max_length=5)
    factor_matches: list[DimensionMatch] = Field(default_factory=list, max_length=20)
    question: str = Field(default="", max_length=250)


class CaseAssessment(Strict):
    profile_id: str
    rows: list[Assessment] = Field(min_length=1, max_length=16)


class BatchAssessment(Strict):
    cases: list[CaseAssessment] = Field(min_length=1, max_length=6)


class Candidate(Strict):
    title: str = Field(min_length=2, max_length=100)
    plan: str = Field(min_length=5, max_length=10000)
    tradeoff: str = Field(min_length=2, max_length=800)


class Recommendations(Strict):
    summary: str = Field(min_length=2, max_length=1200)
    questions: list[str] = Field(default_factory=list, max_length=8)
    candidates: list[Candidate] = Field(default_factory=list, max_length=3)
