"""Local CPU transcription with timestamped, unassigned speakers."""
import os
import secrets
import threading
from pathlib import Path
from services import agent_store as store

MODEL_LOCK = threading.Lock()
_model = None
MAX_BYTES = 25 * 1024 * 1024
MAX_SECONDS = 1200


def transcribe(path):
    global _model
    try:
        import av
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("本地转录模块未安装；请运行 python -m pip install -r backend/requirements-audio.txt") from exc
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError("文件不包含可识别的音轨")
        duration = (container.duration or 0) / av.time_base
        if not duration or duration > MAX_SECONDS:
            raise ValueError("录音需有有效时长且不超过 20 分钟")
    with MODEL_LOCK:
        if _model is None:
            _model = WhisperModel(os.getenv("TRAVEL_ASR_MODEL", "small"), device="cpu", compute_type="int8",
                                  download_root=str(store.MEDIA_DIR / "models"))
        segments, info = _model.transcribe(str(path), beam_size=3, vad_filter=True, language="zh", condition_on_previous_text=False)
        rows = [{"id": f"M{i+1}", "speaker": "未标注", "text": seg.text.strip(), "start": round(seg.start, 2),
                 "end": round(seg.end, 2)} for i, seg in enumerate(segments) if seg.text.strip()]
    if not rows:
        raise ValueError("未识别到有效语音；请检查录音，或改为提交文字记录")
    if len(rows) > 240 or sum(len(r["text"]) for r in rows) > 40000:
        raise ValueError("转录内容过长，请按旅行情境分段上传")
    return {"messages": rows, "duration": duration, "notice": "机器转录；请逐段核对文字和说话人，不代表身份识别。"}


async def receive(request, filename):
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp3", ".m4a", ".wav"}:
        raise ValueError("请上传 MP3、M4A 或 WAV 录音")
    identifier = "M" + secrets.token_hex(12)
    store.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    path = store.MEDIA_DIR / (identifier + suffix)
    size = 0
    try:
        with path.open("wb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("录音不能超过 25 MB")
                stream.write(chunk)
        if not size:
            raise ValueError("文件为空")
        return store.put("media", {"id": identifier, "filename": path.name, "label": Path(filename).name[:160],
                                 "status": "pending", "bytes": size, "messages": [], "created_at": store.now()})
    except BaseException:
        path.unlink(missing_ok=True)
        raise
