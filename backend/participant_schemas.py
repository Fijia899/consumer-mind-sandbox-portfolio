"""Evidence, people, situations and forecasts have separate contracts."""
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(Strict):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    kind: Literal["comment", "note", "questionnaire", "interview"]
    subject_key: str = Field(min_length=2, max_length=200)
    platform: str = Field(min_length=1, max_length=80)
    locator: str = Field(min_length=5, max_length=2000)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=5, max_length=20000)
    published_at: date | None = None
    date_display: str = "日期未知"
    collected_at: date
    usage_basis: Literal["public_research", "consented", "licensed"]
    instrument_version: str = Field(default="", max_length=100)
    review_status: Literal["pending", "checked"] = "pending"
    review_method: Literal["human", "assisted"] = "human"
    reviewer: str = Field(default="", max_length=100)
    review_note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def source_requirements(self):
        if self.kind in {"comment", "note"}:
            parts = urlsplit(self.locator)
            if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
                raise ValueError("网络资料必须提供无账号密码的 HTTP(S) 原文链接")
        elif not self.instrument_version or self.usage_basis != "consented":
            raise ValueError("问卷和访谈须有授权依据、原始记录位置与问卷/提纲版本")
        if self.review_status == "checked" and (not self.reviewer or not self.review_note):
            raise ValueError("已核查来源须记录核查人、方式和说明")
        if self.collected_at > date.today():
            raise ValueError("采集日期不能晚于今天")
        return self


class Fact(Strict):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    source_id: str
    quote: str = Field(min_length=2, max_length=1500)


class Insight(Strict):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    label: str = Field(min_length=2, max_length=100)
    question: str = Field(min_length=2, max_length=300)
    fact_ids: list[str] = Field(min_length=1, max_length=30)
    terms: list[str] = Field(default_factory=list, max_length=12)
    method: Literal["human", "assisted"] = "human"


class Episode(Strict):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    title: str = Field(min_length=2, max_length=160)
    source_ids: list[str] = Field(min_length=1, max_length=30)
    time_scope: Literal["historical", "undated", "current"] = "undated"
    current_confirmed_at: date | None = None
    current_valid_until: date | None = None
    confirmation_quote: str = Field(default="", max_length=1000)


class ParticipantInput(Strict):
    subject_key: str = Field(min_length=2, max_length=200)
    platform: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=2, max_length=160)
    profile_url: str = ""
    sources: list[Source] = Field(min_length=1, max_length=100)
    facts: list[Fact] = Field(default_factory=list, max_length=100)
    insights: list[Insight] = Field(default_factory=list, max_length=50)
    episodes: list[Episode] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def graph(self):
        for rows in (self.sources, self.facts, self.insights, self.episodes):
            if len({r.id for r in rows}) != len(rows):
                raise ValueError("同类记录的编号不能重复")
        sources = {s.id: s for s in self.sources}
        facts = {f.id: f for f in self.facts}
        if len({f.quote for f in self.facts}) != len(self.facts):
            raise ValueError("重复引文不能计为多项独立自述")
        if any(s.subject_key != self.subject_key or s.platform != self.platform for s in self.sources):
            raise ValueError("不同账号或受访者、不同渠道的资料不能拼成一人")
        if self.profile_url:
            parts = urlsplit(self.profile_url)
            if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
                raise ValueError("主页须为无账号密码的 HTTP(S) 链接")
        for locator in [self.profile_url] + [s.locator for s in self.sources]:
            if urlsplit(locator).hostname in {"www.xiaohongshu.com", "xiaohongshu.com"} and "/user/profile/" in urlsplit(locator).path:
                if urlsplit(locator).path.split("/user/profile/", 1)[1].split("/")[0] != self.subject_key:
                    raise ValueError("本人笔记与账号 ID 不一致")
        for fact in self.facts:
            if fact.source_id not in sources or fact.quote not in sources[fact.source_id].text:
                raise ValueError("事实必须逐字引用该受访者原始资料，不能用分析或推测补写")
        for insight in self.insights:
            if not set(insight.fact_ids) <= facts.keys():
                raise ValueError("分析引用了不存在的事实")
            if any(len(t.strip()) < 2 for t in insight.terms):
                raise ValueError("核对词至少两个字符")
        for episode in self.episodes:
            if not set(episode.source_ids) <= sources.keys():
                raise ValueError("旅行情境引用了不存在的来源")
            if episode.time_scope == "current":
                if not episode.current_confirmed_at or not episode.current_valid_until:
                    raise ValueError("当前情境需要本人确认日期与有效期")
                if not episode.current_confirmed_at <= date.today() or episode.current_valid_until < episode.current_confirmed_at:
                    raise ValueError("当前情境的确认日期或有效期无效")
                if not episode.confirmation_quote or not any(episode.confirmation_quote in sources[s].text for s in episode.source_ids):
                    raise ValueError("当前情境需要本人关于计划仍有效的原话")
        return self


class ParticipantImport(Strict):
    records: list[ParticipantInput] = Field(min_length=1, max_length=50)


class ParticipantFile(Strict):
    format: Literal["json", "csv"]
    content: str = Field(min_length=2, max_length=5000000)


class ParticipantReview(Strict):
    status: Literal["accepted", "excluded"]
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=5, max_length=1000)
    identity_level: Literal["account_traceable", "consented_response", "identity_verified"]
    identity_evidence: str = Field(default="", max_length=1000)


class PredictionRequest(Strict):
    participant_id: str
    episode_id: str
    campaign: str = Field(min_length=5, max_length=8000)
    context_mode: Literal["source_context", "current"] = "source_context"
    evaluation_split: Literal["development", "holdout"] = "development"


Decision = Literal["advance", "hesitate", "reject", "na", "insufficient"]


class ModelJudgment(Strict):
    decision: Decision
    supporting_fact_ids: list[str] = Field(default_factory=list, max_length=30)
    counter_fact_ids: list[str] = Field(default_factory=list, max_length=30)
    campaign_quotes: list[str] = Field(default_factory=list, max_length=6)
    missing_information: list[str] = Field(default_factory=list, max_length=10)


class Feedback(Strict):
    participant_id: str
    respondent_key: str = Field(min_length=2, max_length=200)
    decision: Literal["advance", "hesitate", "reject", "na"]
    quote: str = Field(min_length=5, max_length=2000)
    evidence_source: str = Field(min_length=5, max_length=1000)
    identity_confirmation: str = Field(min_length=5, max_length=1000)
    recorder: str = Field(min_length=1, max_length=100)
    observed_at: datetime
    consent_confirmed: Literal[True]

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("反馈时间必须含时区")
        return value
