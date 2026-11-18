# 旅游意向人群心智沙盘

把一份旅行方案放进不同消费者的出行情境里，观察他们关注什么、在哪些条件下愿意继续了解，以及还需要哪些信息。

沙盘围绕旅游意向人群构建，使用 JTBD（待完成的任务）组织画像：从目的地选择、同行协调、预算安排到预订与变更保障，呈现每个人想完成的任务、期望结果、推动力和顾虑。

```text
生成旅游画像 → 旅行方案测试 → 逐人反馈 → 多人总览 → 导出 Excel
```

## 能做什么

- **生成画像**：按旅游任务筛选，一次生成 1–60 位消费者心智，支持规则生成和 LLM 生成。
- **旅行方案测试**：输入行程、价格、服务与退改条件，查看每位画像的判定、第一人称反馈和下一步。
- **逐人查看**：左侧选择画像，右侧展开任务卡、期望结果、推动力、顾虑与方案反馈。
- **多人总览**：在矩阵中比较不同画像的反应，点击人名查看完整画像。
- **导出 Excel**：把本次旅行方案、画像、判定和关注点整理为表格。
- **记忆管理**：保存每位画像最近 10 次方案反馈，支持记忆包上传、下载及全部或单人清除。
- **研究后台**：查看旅游任务地图，维护决策维度的定义、关键词、权重与启停状态。

研究结构包含 **7 个主任务、14 个步骤、9 个期望结果和 25 个旅游决策维度**。沙盘生成的画像与反馈用于提出研究假设，帮助确定下一轮访谈和方案修改的重点。

## 快速启动

准备 Python 3.10+ 和现代浏览器，在 PowerShell 中执行：

```powershell
git clone https://github.com/Fijia899/consumer-mind-sandbox-portfolio.git
Set-Location consumer-mind-sandbox-portfolio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python launcher.py
```

启动器会在 8000–8009 端口中选择可用服务，并打开浏览器。默认工作台地址为 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

规则模式安装后即可使用。开启 LLM 功能的配置见下方“模型配置”。

### 手动启动

```powershell
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

macOS / Linux 激活虚拟环境的命令为 `source .venv/bin/activate`，安装和启动命令相同。终端中按 `Ctrl+C` 停止服务。

### Docker 启动

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

运行 `docker compose down` 停止。部署、单进程配置与数据备份见[部署说明](DEPLOY.md)。

## 使用流程

1. **选任务、生成画像**：选择要研究的旅游任务和人数，点击“生成消费者心智”。
2. **填写旅行方案**：输入方案，或点击“填入示例”。可以从这段内容开始：

   > 周末两天游，人均1200元，含往返交通和一晚住宿；费用透明，可免费改期一次。

3. **运行测试**：点击“运行测试”，查看每位画像的判定、反馈、已回应的期望结果和下一步。勾选“独立思考（LLM）”可启用模型个性化表达。
4. **比较反馈**：在左侧切换画像，或打开“多人总览”比较方案对不同旅游需求的影响。
5. **保存结果**：点击“导出 Excel”，留存本次方案与反馈，再修改方案进行下一轮测试。

### 连续测试与记忆

勾选“消费者有记忆”后，系统按画像 ID 记录最近 10 次方案反馈。“下载记忆”和“上传记忆”用于保存、恢复旅游记忆包；清除按钮支持重置全部或单人记忆。

跨机器迁移时，将 `data/personas.json` 与记忆包一起保存，保持画像 ID 对应。画像文件保存人物信息，`data/travel_memories.json` 保存方案反馈记录。

## 页面入口

| 页面 | 地址 | 内容 |
| --- | --- | --- |
| 工作台 | [打开工作台](http://127.0.0.1:8000/) | 画像生成、旅行方案测试、多人总览、导出 Excel 与记忆管理 |
| 任务后台 | [打开任务后台](http://127.0.0.1:8000/jobs) | 主任务、子任务及其关联关系 |
| 维度后台 | [打开维度后台](http://127.0.0.1:8000/admin) | 决策维度、说明、关键词、权重与启停设置 |
| API 文档 | [打开 API 文档](http://127.0.0.1:8000/docs) | 接口定义与请求结构 |

启动器使用其他端口时，按终端显示的地址访问。

## 模型配置

在项目根目录复制配置模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填写模型服务信息：

```dotenv
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

重启服务后，可勾选“LLM 生成”或“独立思考（LLM）”。`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 按所用兼容服务填写。

已有共享配置时，可在 `.env` 中指定：

```dotenv
MANCHUANG_ENV_FILE=C:/path/to/your-project/.env
```

配置按进程环境、项目 `.env`、共享文件的顺序补充缺失值。使用共享服务的地址与模型时，删除项目 `.env` 中相应的覆盖项。`.env` 由 Git 忽略规则排除。

## 项目结构

```text
backend/          FastAPI 接口、画像生成、方案仿真与存储
frontend/         工作台、任务后台和维度后台
data/             旅游任务、期望结果、决策维度与画像蓝图
tests/            Python 与浏览器回归测试
03_validation/    仓库、文档和部署检查
scripts/          部署验证脚本
docs/             研究记录与版本说明
01_BP/            项目方案 PPT
launcher.py       一键启动入口
```

操作细节见[使用手册](使用手册.md)，功能定义见[规格说明](SPEC.md)，研究记录见[文档索引](docs/README.md)，项目方案见 [PPT](01_BP/消费者心智沙盘_BP.pptx)。

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health`、`/api/config` | 服务状态与模型配置状态 |
| `GET` | `/api/jobs`、`/api/outcomes` | 旅游任务、步骤与期望结果 |
| `GET` / `POST` | `/api/factors` | 读取 / 新增决策维度 |
| `PUT` / `DELETE` | `/api/factors/{factor_id}` | 编辑 / 停用决策维度 |
| `GET` | `/api/personas` | 当前画像列表 |
| `POST` | `/api/generate` | 按人数、任务和模型模式生成画像 |
| `POST` | `/api/simulate` | 测试旅行方案 |
| `POST` | `/api/export/campaign` | 导出方案与反馈 Excel |
| `GET` | `/api/memories/export` | 下载旅游记忆包 |
| `POST` | `/api/memories/import` | 上传旅游记忆包 |
| `POST` | `/api/memories/reset` | 清除全部记忆 |
| `GET` | `/api/personas/{identifier}/memories` | 查看单人记忆 |
| `POST` | `/api/personas/{identifier}/memories/reset` | 清除单人记忆 |

---

## 研究来源

研究资料来自 [Customer-Mind-JTBD-Sandbox](https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox)，本项目围绕旅游意向人群配置任务、画像、维度和方案场景。

2026-11-19 核对上游 HEAD 为 `7747517a36ccd92fb4a5c68866bc565ab18329c1`。后续研究资料更新按上游变更同步，核对记录见[版本说明](docs/current-state-20261119.md)。

## 开发与验证

安装测试依赖并运行全部 Python 测试：

```powershell
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
```

运行 JavaScript 语法检查和浏览器回归：

```powershell
npm ci
npx playwright install chromium
npm run test:syntax
npm run test:browser
```

浏览器回归使用独立临时数据，覆盖任务筛选、画像生成、方案测试、逐人查看、Excel 导出、记忆操作及移动端布局。本机使用 Edge 时，可先设置 `$env:PLAYWRIGHT_CHANNEL = "msedge"`。

GitHub Actions 执行 Python 3.10 / 3.12 测试、Chromium 浏览器回归和 Docker 启动验证。
