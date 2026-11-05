"""加载 DeepSeek OpenAI-compatible 配置，可直接复用漫创的 .env。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
LOCAL_ENV = PROJECT_ROOT / ".env"


def load_env() -> Path | None:
    """加载环境变量并返回配置文件路径；密钥始终只留在进程环境中。"""
    # 本项目 .env 可只保存共享文件路径；共享文件随后补入 API 配置。
    if LOCAL_ENV.is_file():
        load_dotenv(LOCAL_ENV, override=False)
    shared_value = os.getenv("MANCHUANG_ENV_FILE", "").strip()
    shared_env = Path(shared_value).expanduser() if shared_value else None
    if shared_env and shared_env.is_file():
        load_dotenv(shared_env, override=False)
        return shared_env
    if LOCAL_ENV.is_file():
        return LOCAL_ENV
    return None


def get_api_key() -> str:
    load_env()
    return os.getenv("DEEPSEEK_API_KEY", "")


def get_base_url() -> str:
    load_env()
    return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def get_model_name() -> str:
    load_env()
    raw = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash-0731")
    return raw.split("/", 1)[-1]


def llm_configured() -> bool:
    key = get_api_key()
    return bool(key) and not key.startswith("sk-your")
