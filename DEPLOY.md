# 旅游沙盘部署说明

## 本机运行

在仓库根目录安装运行依赖并启动：

```powershell
python -m pip install -r backend/requirements.txt
python launcher.py
```

也可使用跨平台命令：

```powershell
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

工作台位于 `/`，决策维度位于 `/admin`，API 文档位于 `/docs`。规则模式不需要模型凭据；配置模型的方法见 [README](README.md)。当前服务适用于本机单用户、单进程使用。

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

默认映射 `127.0.0.1:8000:8000`，浏览器访问 `http://127.0.0.1:8000`。容器使用一个 worker，健康检查访问 `/api/health`，模型密钥仅通过只读 `.env` 挂载提供。容器中不包含宿主机依赖、研究运行台账、录音或 Git 元数据。

```powershell
docker compose ps
docker compose logs -f
docker compose down
```

共享配置位于宿主机其他目录时，需要另加只读卷并将容器中的 `MANCHUANG_ENV_FILE` 指向挂载路径；Windows 主机路径在容器内不能直接读取。Linux / macOS 可使用 `cp .env.example .env`，也可运行 `bash deploy.sh` 部署当前检出版本；脚本不自动拉取或覆盖代码。

## 数据备份与恢复

停止服务后备份 `data/` 和私有 `.env`。当前画像在 `data/personas.json`，连续触达记忆在 `data/travel_memories.json`；研究台账、Agent 数据库和媒体目录均属于本机状态。恢复时将同一份备份中的相关文件一起恢复，再启动服务。Git 回滚只回滚代码和已跟踪研究结构，不自动恢复运行数据。

仓库初始化画像为空；默认档案集合由已提交的公开来源集合生成，追加材料位于 `data/participant_imports/`，不会自动采纳所有批次。不要把本机台账或真实密钥加入提交。

## 验证范围

Python 回归、隔离服务的浏览器回归、部署配置静态检查和干净检出验证由仓库测试覆盖。本次整理环境未安装 Docker，因此没有执行镜像构建和容器运行验收；使用容器部署前需在 Docker 环境运行上述命令并检查健康状态。
