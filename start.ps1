# 在已安装依赖的 Python 环境中启动旅游意向人群心智沙盘。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
exit $LASTEXITCODE
