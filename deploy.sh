#!/usr/bin/env bash
# 从当前检出的版本部署；更新代码请在部署前显式执行 git pull。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ ! -f .env ]]; then
  echo "请先复制 .env.example 为 .env，并按需填写模型配置。"
  exit 1
fi

docker compose up -d --build
for attempt in {1..20}; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
    echo "服务已就绪：http://127.0.0.1:8000"
    exit 0
  fi
  sleep 3
done

docker compose logs --tail=80
echo "服务未通过健康检查。"
exit 1
