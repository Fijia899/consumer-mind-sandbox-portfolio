"""Local single-user Agent ledger, separate from the participant research store."""
import json
import sqlite3
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "agent.sqlite3"
MEDIA_DIR = ROOT / "data" / "agent_media"
LOCK = threading.RLock()
TERMINAL = {"completed", "partial", "failed", "cancelled", "interrupted"}


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("CREATE TABLE IF NOT EXISTS objects (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, request TEXT NOT NULL, run_id TEXT NOT NULL)")
    conn.commit()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def put(kind, value):
    with LOCK, connection() as conn:
        conn.execute("INSERT OR REPLACE INTO objects VALUES (?,?,?)", (value["id"], kind, json.dumps(value, ensure_ascii=False)))
    return value


def get(kind, identifier):
    with LOCK, connection() as conn:
        row = conn.execute("SELECT payload FROM objects WHERE id=? AND kind=?", (identifier, kind)).fetchone()
    if not row:
        raise KeyError("记录不存在或已删除")
    return json.loads(row[0])


def listing(kind):
    with LOCK, connection() as conn:
        return [json.loads(row[0]) for row in conn.execute("SELECT payload FROM objects WHERE kind=? ORDER BY rowid DESC", (kind,))]


def remove(kind, identifier):
    with LOCK, connection() as conn:
        conn.execute("DELETE FROM objects WHERE kind=? AND id=?", (kind, identifier))
        if kind == "run":
            conn.execute("DELETE FROM keys WHERE run_id=?", (identifier,))


def new_run(action, snapshot, key=None):
    canonical = json.dumps([action, snapshot], sort_keys=True, ensure_ascii=False)
    with LOCK:
        if key:
            with connection() as conn:
                previous = conn.execute("SELECT request,run_id FROM keys WHERE key=?", (key,)).fetchone()
            if previous:
                if previous[0] != canonical:
                    raise ValueError("同一提交编号不能用于不同输入")
                return get("run", previous[1]), False
        row = {"id": "R" + secrets.token_hex(12), "action": action, "status": "queued", "created_at": now(),
               "updated_at": now(), "snapshot": snapshot, "events": [], "result": None, "error": None,
               "usage": {"calls": 0, "tokens": 0, "unknown_usage_calls": 0}, "cancel_requested": False}
        put("run", row)
        if key:
            with connection() as conn:
                conn.execute("INSERT INTO keys VALUES (?,?,?)", (key, canonical, row["id"]))
        return row, True


def update_run(identifier, **changes):
    with LOCK:
        row = get("run", identifier)
        if row["status"] in TERMINAL:
            return row
        row.update(changes, updated_at=now())
        return put("run", row)


def event(identifier, tool, status, summary):
    with LOCK:
        row = get("run", identifier)
        if row["status"] in TERMINAL:
            return
        row["events"].append({"seq": len(row["events"]) + 1, "at": now(), "tool": tool, "status": status, "summary": summary[:1200]})
        row["updated_at"] = now()
        put("run", row)


def interrupt_pending():
    with LOCK:
        for row in listing("run"):
            if row["status"] not in TERMINAL:
                update_run(row["id"], status="interrupted", error="服务已重启；保留执行记录，请重新提交任务。")


def purge_media(identifier):
    """Delete all derived objects, so private text is not retained in old snapshots."""
    with LOCK:
        media = get("media", identifier)
        for kind in ("profile", "run"):
            for row in listing(kind):
                if identifier in json.dumps(row, ensure_ascii=False):
                    remove(kind, row["id"])
        remove("media", identifier)
        path = MEDIA_DIR / media["filename"]
        if path.parent.resolve() != MEDIA_DIR.resolve():
            raise ValueError("文件位置无效")
        path.unlink(missing_ok=True)
