from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import load_env
from routes import travel, research, participants, agent
from services.agent_store import interrupt_pending
from services.participant_store import initialize

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"

app = FastAPI(title="旅游意向人群心智沙盘", version="7.0-travel-workbench")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(travel.router)
app.include_router(research.router)
app.include_router(participants.router)
app.include_router(agent.router)


@app.middleware("http")
async def refresh_frontend(request, call_next):
    response = await call_next(request)
    if request.url.path in {"/", "/agent", "/admin"} or request.url.path.startswith(("/static/", "/api/")):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.on_event("startup")
def startup():
    env_path = load_env()
    initialize()
    interrupt_pending()
    if env_path:
        print(f"✓ 已加载 DeepSeek 配置: {env_path}")


@app.get("/")
@app.get("/agent")
def index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "API running. Place frontend/index.html to enable UI."}


@app.get("/admin")
def admin_page():
    admin_path = FRONTEND_DIR / "admin.html"
    if admin_path.exists():
        return FileResponse(admin_path)
    return {"message": "Admin page not found."}


@app.get("/api/health")
def health():
    from config import llm_configured
    return {"status": "ok", "llm_configured": llm_configured(), "audience": "旅游意向人群",
            "app_id": "travel-mind-sandbox", "capabilities": ["legacy-travel-simulator-v1", "visual-analysis-flow-v1", "real-participants-v1", "same-participant-feedback-v1"]}
