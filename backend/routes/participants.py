import csv
import io
import json

from fastapi import APIRouter, HTTPException
from openai import APIError, APITimeoutError
from pydantic import ValidationError

from participant_schemas import Feedback, ParticipantFile, ParticipantImport, ParticipantInput, ParticipantReview, PredictionRequest
from services import participant_predictions as predictions
from services import participant_store as store

router = APIRouter(prefix="/api", tags=["real-participants"])


def call(fn, *args, model=False):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except APITimeoutError as exc:
        raise HTTPException(504, "模型响应超时；没有生成替代判断，请查看预测记录") from exc
    except (APIError, RuntimeError) as exc:
        raise HTTPException(503, "模型服务不可用或尚未配置；没有生成替代判断") from exc
    except (ValueError, ValidationError) as exc:
        if model and isinstance(exc, (ValidationError, json.JSONDecodeError)):
            raise HTTPException(502, "模型输出未通过原文或结构校验；未写入人物事实") from exc
        raise HTTPException(422, str(exc)) from exc


@router.get("/participants")
def list_participants():
    return call(store.listing)


@router.get("/participants/template")
def template():
    return {"records": [], "schema": ParticipantImport.model_json_schema(),
            "instructions": "records 每项是一位真实来源受访者；来源保存原文，facts.quote 必须逐字摘录。空模板不能作为真实资料导入。"}


@router.post("/participants/import")
def import_participants(body: ParticipantImport):
    return call(store.import_records, body.records)


@router.post("/participants/import-file")
def import_file(body: ParticipantFile):
    try:
        if body.format == "json":
            parsed = json.loads(body.content.lstrip("\ufeff"))
            records = parsed if isinstance(parsed, list) else parsed["records"]
        else:
            records = []
            for row in csv.DictReader(io.StringIO(body.content.lstrip("\ufeff"))):
                if len(records) >= 50:
                    raise ValueError("每批最多 50 人")
                row = {k: v for k, v in row.items() if v != ""}
                if "respondent_key" in row:
                    key = row["respondent_key"]
                    platform = row["platform"]
                    quotes = [q.strip() for q in row.get("quotes", "").splitlines() if q.strip()]
                    source = {"id": "S1", "kind": "questionnaire", "subject_key": key,
                              "platform": platform, "locator": row["record_locator"],
                              "title": row["label"], "text": row["response_text"],
                              "instrument_version": row["instrument_version"],
                              "collected_at": row["collected_at"], "usage_basis": row["usage_basis"],
                              "reviewer": row.get("reviewer", ""), "review_note": row.get("review_note", "")}
                    source["review_status"] = "checked" if source["reviewer"] and source["review_note"] else "pending"
                    records.append({"subject_key": key, "platform": platform, "label": row["label"],
                                    "sources": [source],
                                    "facts": [{"id": f"F{i + 1}", "source_id": "S1", "quote": q} for i, q in enumerate(quotes)],
                                    "episodes": [{"id": "E1", "title": row["episode_title"], "source_ids": ["S1"], "time_scope": "undated"}]})
                    continue
                for key in ("sources", "facts", "insights", "episodes", "limitations", "unknowns"):
                    if key in row:
                        row[key] = json.loads(row[key])
                records.append(row)
        validated = ParticipantImport.model_validate({"records": records})
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, "文件结构或来源引用无效；请核对 JSON/CSV、原文引文和受访者编号") from exc
    return call(store.import_records, validated.records)


@router.post("/participants/extract")
def extract(body: ParticipantInput):
    return call(predictions.extract, body, model=True)


@router.get("/participants/{participant_id}")
def participant(participant_id: str):
    return call(store.get, participant_id)


@router.post("/participants/{participant_id}/review")
def review(participant_id: str, body: ParticipantReview):
    return call(store.review, participant_id, body)


@router.get("/predictions")
def list_predictions():
    return call(predictions.listing)


@router.post("/predictions")
def predict(body: PredictionRequest):
    return call(predictions.create, body, model=True)


@router.post("/predictions/{prediction_id}/feedback")
def feedback(prediction_id: str, body: Feedback):
    return call(predictions.add_feedback, prediction_id, body)


@router.get("/archive")
def archive():
    return call(store.archive_view)
