# -*- coding: utf-8 -*-
"""旅游意向人群心智沙盘 — 一键启动器。

打包为 exe 后，请与 backend / frontend / data 放在同一目录下双击运行。
关闭本窗口即可停止服务。
"""
from __future__ import annotations

import os
import json
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from urllib.request import urlopen
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, port)) == 0


def service_ready(port: int) -> bool:
    """An occupied port may be an old sandbox process or a different application."""
    try:
        with urlopen(f"http://{HOST}:{port}/api/health", timeout=1) as response:
            health = json.loads(response.read(65536))
        if not isinstance(health, dict) or health.get("app_id") != "travel-mind-sandbox":
            return False
        if health.get("status") != "ok" or "legacy-travel-simulator-v1" not in health.get("capabilities", []):
            return False
        with urlopen(f"http://{HOST}:{port}/", timeout=1) as response:
            return response.status == 200 and 'id="persona-list"' in response.read(65536).decode("utf-8")
    except (OSError, ValueError, TypeError, UnicodeError):
        return False


def choose_service() -> tuple[int, bool]:
    for port in range(PORT, PORT + 10):
        if not port_open(port):
            return port, False
        if service_ready(port):
            return port, True
    raise RuntimeError("8000–8009 端口均被占用且没有可复用的新版服务，请释放一个端口后重试。")


def find_python() -> str | None:
    """找到能 import uvicorn 的 Python（打包成 exe 后不能用 sys.executable）。"""
    candidates: list[str] = []

    if not getattr(sys, "frozen", False):
        candidates.append(sys.executable)

    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    # Windows 常见安装路径
    local = os.environ.get("LOCALAPPDATA", "")
    for extra in (
        Path(sys.base_prefix) / "python.exe" if hasattr(sys, "base_prefix") else None,
        Path(r"C:\Python312\python.exe"),
        Path(r"C:\Python311\python.exe"),
        Path(local) / "Programs" / "Python" / "Python312" / "python.exe",
        Path(local) / "Programs" / "Python" / "Python311" / "python.exe",
    ):
        if extra and Path(extra).is_file():
            candidates.append(str(extra))

    seen: set[str] = set()
    for cand in candidates:
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            check = subprocess.run(
                [cand, "-c", "import uvicorn, fastapi"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if check.returncode == 0:
                return cand
        except Exception:
            continue
    return None


def wait_ready(timeout: float = 30.0, port: int = PORT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if service_ready(port):
            return True
        time.sleep(0.3)
    return False


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = app_root()
    backend = root / "backend"
    if not (backend / "main.py").is_file():
        print("=" * 50)
        print("找不到 backend\\main.py")
        print(f"请把本程序放在项目根目录（与 backend 同级）")
        print(f"当前目录: {root}")
        print("=" * 50)
        input("\n按回车退出...")
        return 1

    print("=" * 50)
    print("  旅游意向人群心智沙盘")
    print("  关闭本窗口 = 停止服务")
    print("=" * 50)
    print(f"项目目录: {root}")

    local_env = root / ".env"
    if local_env.is_file():
        print(f"✓ 将使用配置: {local_env}")
    else:
        print("⚠ 未找到 .env（规则模式可用；DeepSeek 可用 MANCHUANG_ENV_FILE 复用漫创配置）")

    try:
        selected_port, reuse = choose_service()
    except RuntimeError as exc:
        print(str(exc))
        return 1
    url = f"http://{HOST}:{selected_port}"
    if selected_port != PORT:
        print(f"默认端口 {PORT} 上的服务未通过新版检查，本次使用 {selected_port}。")
    if reuse:
        print(f"\n已确认新版服务可用，正在打开浏览器…")
        webbrowser.open(url)
        print(f"地址: {url}")
        print("（不会关闭已有服务；按回车仅退出本窗口）")
        input()
        return 0

    python = find_python()
    if not python:
        print("\n未找到已安装 uvicorn / fastapi 的 Python。")
        print("请先在本机执行: pip install uvicorn fastapi")
        input("\n按回车退出...")
        return 1

    print(f"Python: {python}")
    print(f"\n正在启动服务 → {url}\n")

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        [
            python,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            HOST,
            "--port",
            str(selected_port),
        ],
        cwd=str(backend),
        creationflags=creationflags,
    )

    try:
        if wait_ready(port=selected_port):
            print(f"✓ 启动成功，正在打开浏览器…\n")
            webbrowser.open(url)
        else:
            print("等待新版服务就绪超时，请检查上方启动日志后重试。")
            return 1

        print(f"工作台: {url}")
        print(f"维度后台: {url}/admin")
        print(f"API 文档: {url}/docs")
        print("\n按 Ctrl+C 或直接关闭窗口可停止服务。\n")
        proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止服务…")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("已退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
