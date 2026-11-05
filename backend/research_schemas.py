"""Evidence contracts. Unknown attributes stay absent; review is separate from import."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceLabel(StrictModel):
    factor_id: str
    quote: str = Field(min_length=2, max_length=1500)
    terms: list[str] = Field(default_factory=list, max_length=12)
    basis: Literal["explicit", "inferred"] = "explicit"


class ProfileFact(StrictModel):
    field: Literal["departure_window", "trip_length_days", "party_size", "budget_per_person", "booked", "party_description"]
    value: str | int | bool
    quote: str = Field(min_length=2, max_length=1500)
    basis: Literal["self_report", "inferred"] = "self_report"


class EvidenceInput(StrictModel):
    source_url: HttpUrl
    platform: str = Field(min_length=1, max_length=60)
    author_key: str = Field(default="", max_length=200)
    published_at: date | None = None
    text: str = Field(min_length=5, max_length=12000)
    language: str = Field(default="zh", max_length=20)
    context: str = Field(default="", max_length=1500)
    usage_basis: Literal["public_research", "consented", "licensed"]
    authenticity: Literal["unverified", "suspected_marketing", "suspected_fake"] = "unverified"
    job_id: str = ""
    stage: str = ""
    perspective: Literal["planning", "post_trip", "advice"] = "planning"
    labels: list[EvidenceLabel] = Field(default_factory=list, max_length=22)
    profile: list[ProfileFact] = Field(default_factory=list, max_length=6)


class ImportRequest(StrictModel):
    records: list[EvidenceInput] = Field(min_length=1, max_length=500)


class FileImportRequest(StrictModel):
    format: Literal["json", "csv"]
    content: str = Field(min_length=2, max_length=5000000)


class ReviewRequest(StrictModel):
    status: Literal["approved", "excluded"]
    reviewer: str = Field(min_length=1, max_length=80)
    review_method: Literal["human", "assisted"] = "human"
    note: str = Field(min_length=2, max_length=1000)
    job_id: str
    stage: str
    perspective: Literal["planning", "post_trip", "advice"] = "planning"
    labels: list[EvidenceLabel] = Field(default_factory=list, max_length=22)
    profile: list[ProfileFact] = Field(default_factory=list, max_length=6)


class CalibrationRequest(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class TrialRequest(StrictModel):
    persona_id: str
    campaign: str = Field(min_length=5, max_length=8000)
    participant_key: str = Field(min_length=2, max_length=200)
    platform: str = Field(min_length=1, max_length=60)


class ObservationRequest(StrictModel):
    decision: Literal["advance", "hesitate", "reject", "na"]
    note: str = Field(min_length=5, max_length=2000)
    observer: str = Field(min_length=1, max_length=80)
    evidence_source: str = Field(default="", max_length=1000)


class RunTrialRequest(StrictModel):
    persona_id: str = Field(min_length=1)
    participant_key: str = Field(min_length=2, max_length=200)
    platform: str = Field(min_length=1, max_length=60)
    context: str = Field(min_length=5, max_length=1000)
