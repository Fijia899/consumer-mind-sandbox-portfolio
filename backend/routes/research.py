from fastapi import APIRouter, HTTPException
from services import observed_profiles, participant_store

router = APIRouter(prefix="/api/research", tags=["research-archive"])


def _call(fn, *args):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/observed-profiles")
def observed_profile_collection():
    return _call(observed_profiles.load)


@router.post("/observed-profiles/check")
def check_observed_profiles(body: observed_profiles.CheckRequest):
    return _call(observed_profiles.check_campaign, body)


@router.get("")
@router.get("/export")
def archive():
    return _call(participant_store.archive_view)


@router.api_route("/{legacy_path:path}", methods=["POST", "PUT", "DELETE"])
def retired_research(legacy_path: str):
    raise HTTPException(410, "旧研究记录已只读归档。请通过 /api/participants 导入真人资料，通过 /api/predictions 登记预测和本人反馈。")
