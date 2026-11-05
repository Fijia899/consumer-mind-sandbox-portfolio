"""Source-bound public travel observations, separate from simulated people."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "xiaohongshu_travel_profiles.json"


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign: str = Field(min_length=1, max_length=12000)
    profile_ids: list[str] | None = Field(default=None, max_length=50)

    @field_validator("campaign")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请填写旅行方案")
        return value.strip()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"公开样本资料校验失败：{message}")


def _url_path(url: str) -> str:
    parsed = urlsplit(url)
    _require(parsed.scheme == "https" and parsed.netloc == "www.xiaohongshu.com", "来源须为小红书 HTTPS 链接")
    return parsed.path.rstrip("/")


def _account(url: str) -> str:
    match = re.fullmatch(r"/user/profile/([0-9a-f]{24})", _url_path(url))
    _require(bool(match), "账号主页链接无效")
    return match.group(1)


def validate_bundle(bundle: dict) -> None:
    """Check provenance integrity; these checks cannot establish a post's truth."""
    _require(bundle["schema_version"] == 1, "不支持的资料版本")
    profiles, screening = bundle["profiles"], bundle["screening"]
    _require(len({r["id"] for r in screening}) == len(screening), "筛选编号重复")
    _require(len({r["account_id"] for r in screening}) == len(screening), "同一账号重复计数")
    _require(len({p["id"] for p in profiles}) == len(profiles), "采纳编号重复")
    for row in screening:
        _require(row["decision"] in {"included", "excluded"}, "筛选状态无效")
        _require(row["profile_checked"] and bool(row["reason"].strip()), "须有主页核查与采纳或排除理由")
        _require(_account(row["profile_url"]) == row["account_id"], "筛选账号不一致")
        _url_path(row["entry_note_url"])
        _require(bool(row["entry_comment_ids"]), "缺少入口评论定位")
        for url in row["reviewed_note_urls"]:
            _url_path(url)
    included = {r["id"]: r for r in screening if r["decision"] == "included"}
    _require(set(included) == {p["id"] for p in profiles}, "采纳清单与筛选台账不一致")
    for profile in profiles:
        account = profile["account_id"]
        _require(_account(profile["profile_url"]) == account == included[profile["id"]]["account_id"], "画像账号不一致")
        sources = {s["id"]: s for s in profile["sources"]}
        _require(len(sources) == len(profile["sources"]), "来源编号重复")
        for source in sources.values():
            path = _url_path(source["url"])
            _require(path == _url_path(source["canonical_url"]), "规范链接与原链接不一致")
            _require(source["account_id"] == account == _account(source["author_profile_url"]), "来源作者与账号不一致")
            _require(bool(source["excerpt"].strip()) and bool(source["date_display"].strip()), "缺少短引文或页面日期")
            _require(source["kind"] in {"comment", "note"}, "来源种类无效")
            if source["kind"] == "note":
                _require(bool(re.fullmatch(rf"/user/profile/{account}/[0-9a-f]{{24}}", path)), "本人笔记链接不一致")
            else:
                _require(source["comment_id"] in included[profile["id"]]["entry_comment_ids"], "评论不在入口核查记录中")
                _require(path == _url_path(included[profile["id"]]["entry_note_url"]), "评论讨论页不一致")
        _require(len(profile["claims"]) >= 4, "不足四项具体旅行自述")
        referenced = set()
        for collection, basis in ((profile["claims"], "explicit_self_report"), (profile["needs"], "researcher_mapping")):
            _require(len({r["id"] for r in collection}) == len(collection), "事实或需求编号重复")
            for row in collection:
                _require(row["basis"] == basis, "自述与研究者整理须区分")
                _require(bool(row["source_ids"]) and set(row["source_ids"]) <= sources.keys(), "引用不存在或跨账号的来源")
            if basis == "explicit_self_report":
                referenced = {sid for row in collection for sid in row["source_ids"]}
        note_paths = {_url_path(sources[sid]["url"]) for sid in referenced if sources[sid]["kind"] == "note"}
        _require(len(note_paths) >= 2, "事实依据不足两篇不同的本人笔记")
        _require(any(sources[sid]["kind"] == "comment" for sid in referenced), "事实须关联入口评论")
        _require(bool(profile["limitations"]) and bool(profile["unknowns"]), "须保留局限与未知项")
        for need in profile["needs"]:
            _require(bool(need["question"].strip()) and bool(need["terms"]) and all(t.strip() for t in need["terms"]), "需求须有追问与有效核对词")


def load() -> dict:
    bundle = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    validate_bundle(bundle)
    sources = [s for p in bundle["profiles"] for s in p["sources"]]
    bundle["counts"] = {
        "screened": len(bundle["screening"]),
        "included": len(bundle["profiles"]),
        "excluded": sum(r["decision"] == "excluded" for r in bundle["screening"]),
        "sources": len(sources),
        "distinct_note_pages": len({s["canonical_url"] for s in sources}),
        "claims": sum(len(p["claims"]) for p in bundle["profiles"]),
    }
    return bundle


def check_campaign(request: CheckRequest) -> dict:
    bundle = load()
    allowed = {p["id"] for p in bundle["profiles"]}
    selected = allowed if request.profile_ids is None else set(request.profile_ids)
    if not selected or not selected <= allowed:
        raise ValueError("请选择已采纳的公开样本；排除账号不能用于核对")
    clauses = [c.strip() for c in re.split(r"[。！？!?；;\n]+", request.campaign) if c.strip()]
    results = []
    for profile in bundle["profiles"]:
        if profile["id"] not in selected:
            continue
        needs = []
        for need in profile["needs"]:
            mentions = [c for c in clauses if any(term.casefold() in c.casefold() for term in need["terms"])]
            # A negative statement still mentions a topic; it never resolves it.
            needs.append({
                "id": need["id"], "label": need["label"], "question": need["question"],
                "source_ids": need["source_ids"],
                "status": "mentioned_not_resolved" if mentions else "not_mentioned",
                "mentions": [c[:400] for c in mentions[:3]],
            })
        results.append({"id": profile["id"], "label": profile["label"], "needs": needs})
    return {
        "dataset_id": bundle["id"], "campaign": request.campaign,
        "method": "literal_topic_mentions",
        "limitation": "仅按关键词定位方案中涉及的主题，可能漏掉同义表达；提及、否定或承诺均不代表需求已满足。所有问题仍需核实，也不代表作者当前态度。",
        "profiles": results,
    }
