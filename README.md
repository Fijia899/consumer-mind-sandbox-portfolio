# 旅游意向人群心智沙盘

基于 JTBD 方法构建的本地 Web 研究工作台，面向正在选择目的地、协调同行、安排预算、规划行程与核验预订的旅游意向人群。

> Job 本体驱动（7 个主任务 + 14 个步骤 + 9 个期望结果）+ 25 个旅游决策维度 + 自设数量生成画像 + Campaign 方案仿真（以「是否推动任务进展」判定）+ Agent 分析过程可视化。

仓库包含可运行应用、研究结构、自动化测试和保留的[项目方案 PPT](01_BP/消费者心智沙盘_BP.pptx)。实现范围见 [SPEC.md](SPEC.md)，操作说明见[使用手册](使用手册.md)，补全记录见[仓库检查报告](docs/repository-audit-20261105.md)。合成画像与仿真反馈用于形成研究假设，不能代替真实访谈或市场统计。

---

## 环境要求

- Python 3.10+。
- Chrome / Edge / Firefox 等现代浏览器。
- DeepSeek 或兼容接口的 API Key（可选）：未配置时可使用规则画像和规则仿真。
- Node.js 20+（仅运行浏览器回归测试时需要）。
- Docker Compose（仅使用容器部署时需要）。

---

## 环境配置

### 方式一：为本项目单独配置

在仓库根目录复制模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填写你使用的服务与模型：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MANCHUANG_ENV_FILE=
TRAVEL_ASR_MODEL=small
```

### 方式二：复用已有配置

在本项目 `.env` 中设置共享文件路径，例如：

```dotenv
MANCHUANG_ENV_FILE=C:/path/to/your-project/.env
```

系统保留进程环境、本项目 `.env` 中已设置的值，再从共享文件补充缺失项。使用共享服务时，请删除本项目中不需要覆盖的 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 行。

### 环境变量说明

| 变量 | 必填 | 说明 |
| --- | :---: | --- |
| `DEEPSEEK_API_KEY` | 否 | 模型密钥；未配置时使用规则模式 |
| `DEEPSEEK_BASE_URL` | 否 | 接口地址；未设置时为 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 否 | 模板为 `deepseek-chat`；代码未设置时为 `deepseek-v4-flash-0731`，请按服务实际支持的型号配置 |
| `MANCHUANG_ENV_FILE` | 否 | 可选共享 `.env` 路径，补充缺失配置 |
| `TRAVEL_ASR_MODEL` | 否 | 研究 API 的可选语音模型，默认 `small`；当前工作台没有录音入口 |

规则模式无需创建 `.env`。模型配置状态可通过工作台顶部提示或 `GET /api/config` 查看；接口不返回密钥。不要将 `.env` 提交到 Git。

---

## 如何打开（启动服务）

### 第一次使用

```powershell
git clone https://github.com/Fijia899/consumer-mind-sandbox-portfolio.git
Set-Location consumer-mind-sandbox-portfolio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

### 方法一：一键启动（Windows 推荐）

```powershell
python launcher.py
```

启动器检查 8000–8009 端口，选用可用端口或复用已核验的本项目服务，并自动打开浏览器。也可在仓库根目录运行 `./start.ps1`，以开发模式启动 8000 端口。

### 方法二：手动启动

```powershell
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即表示成功。macOS / Linux 可使用相同启动命令；虚拟环境激活命令为 `source .venv/bin/activate`。

### 方法三：Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

默认访问 `http://127.0.0.1:8000`，详细配置与数据备份见[部署说明](DEPLOY.md)。

### 停止服务

终端启动时按 `Ctrl+C`；Docker 部署时运行 `docker compose down`。JSON 文件与进程内状态适用于单服务进程，请勿配置多个 worker 同时写入数据。

---

## 打开界面

| 页面 | 默认地址 | 用途 |
| --- | --- | --- |
| 工作台（首页） | <http://127.0.0.1:8000> | 生成旅游画像、测试方案、查看四阶段分析与逐人反馈 |
| 决策维度 | <http://127.0.0.1:8000/admin> | 新增、启停维度，查看定义、关键词和权重 |
| API 文档 | <http://127.0.0.1:8000/docs> | 查看已注册接口和请求结构 |

`/agent` 与首页相同。当前前端只有“工作台”和“决策维度”两个页面，研究与档案后端接口仍保留。若启动器选择其他端口，以终端显示地址为准。样式未更新可按 `Ctrl+F5`。

---

## 使用流程

```text
① 启动服务 → ② 打开工作台 → ③ 生成旅游画像 → ④ 测试旅行方案 → ⑤ 核对任务进展
```

1. **生成画像**：设置数量（1–60），选择优先任务或均衡覆盖，点击“生成画像”。默认使用规则蓝图；配置模型后可勾选 DeepSeek 生成。
2. **输入方案**：粘贴旅游产品或营销话术，写明行程、价格包含项、同行安排、服务和退改条件。
3. **运行测试**：查看“读取旅行方案 → 识别决策维度 → 分析画像与任务进展 → 汇总结果”四阶段流程，以及每位画像的结果、已回应和待解决项。
4. **选择模式**：规则模式提供基线判断；“DeepSeek 个性化表达”增加模型反馈，仍受规则约束；“连续触达记忆”记录多轮方案上下文。
5. **管理维度**：进入 `/admin` 新增或启停维度；后续生成和仿真读取更新后的配置。

### 记忆管理

| 操作 | 作用 |
| --- | --- |
| 勾选“连续触达记忆”后测试 | 按画像 ID 保存最近 10 次方案、判定、已回应结果和下一步 |
| “清除记忆” | 清空所有画像的连续触达记忆 |
| 停止服务后复制 `data/travel_memories.json` | 手动备份记忆；迁移时还需对应的 `data/personas.json` |

记忆默认关闭；当前界面没有记忆上传、下载或单人清除功能。规则模式记录记忆但不据此改变判断，模型表达会接收历史上下文。重新生成画像不自动清除记忆，开始新一轮研究前可先手动清除。

---

## 目录结构

```text
consumer-mind-sandbox-portfolio/
├── README.md                   # 项目入口说明
├── SPEC.md                     # 功能与验收范围
├── 使用手册.md                 # 操作说明
├── DEPLOY.md                   # 部署与备份
├── AGENTS.md                   # 研究、提交和测试约定
├── launcher.py / start.ps1     # Windows 启动入口
├── .env.example                # 无密钥配置模板
├── Dockerfile                  # 单进程服务镜像
├── docker-compose.yml          # 本机端口与持久化配置
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── requirements.txt        # 运行依赖
│   ├── requirements-dev.txt    # Python 测试依赖
│   ├── routes/                 # 工作台、Agent、研究与档案 API
│   └── services/               # 画像、规则、质检、模型及存储
├── frontend/
│   ├── index.html              # 工作台
│   ├── admin.html              # 决策维度
│   ├── css/travel.css
│   └── js/travel.js
├── data/
│   ├── jobs.json               # 7 个主任务、14 个步骤
│   ├── outcomes.json           # 9 个期望结果
│   ├── factors.json            # 当前 25 个维度
│   ├── persona_seeds.json      # 旅游合成画像蓝图
│   ├── personas.json           # 初始为空，运行后保存本机画像
│   └── participant_imports/    # 公开材料导入批次
├── docs/                       # 文档索引、研究记录与检查报告
├── 01_BP/                      # 保留的项目方案 PPT
├── tests/                      # Python 与浏览器回归
├── scripts/smoke_deployment.py  # 容器启动与规则流程验收
├── 03_validation/              # 仓库、文档和部署配置校验
├── package.json                # 浏览器测试命令与依赖
└── .github/workflows/ci.yml    # 干净检出后的自动验证
```

密钥、运行台账、数据库、音频、缓存和依赖目录由忽略规则排除。仓库不携带本机已有的研究运行状态，材料和批次说明见[文档索引](docs/README.md)。

---

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 服务健康状态与能力标记 |
| `GET` | `/api/config` | 模型配置状态，不返回密钥 |
| `GET` | `/api/jobs`、`/api/outcomes` | 旅游任务、步骤与期望结果 |
| `GET` / `POST` | `/api/factors` | 读取维度库 / 新增维度 |
| `PUT` / `DELETE` | `/api/factors/{factor_id}` | 编辑 / 停用维度 |
| `GET` | `/api/personas` | 当前画像列表 |
| `POST` | `/api/generate` | `{count, use_llm?, job_ids?}` 生成画像 |
| `POST` | `/api/simulate` | `{campaign, use_llm?, use_memory?, persona_ids?}` 方案仿真 |
| `POST` | `/api/memories/reset` | 清空连续触达记忆 |

其余 Agent、档案和研究接口以运行后的 `/docs` 为准；部分历史研究写入接口明确返回停用状态，不属于当前工作台流程。

---

## 与研究仓库的关系

研究资料以 [Customer-Mind-JTBD-Sandbox](https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox) 为准，本项目按旅游意向人群配置任务、画像、维度和场景。README 沿用参考项目的操作指南结构，能力说明以本仓库实现为准。

2026-11-05（北京时间）通过 `git ls-remote` 核对，研究仓库 `main` 仍为 `7747517a36ccd92fb4a5c68866bc565ab18329c1`，与既有基线一致。再次使用研究资料前应核对最新提交，并同步适用于旅游研究的变更；既往记录见[上游更新说明](docs/upstream-update-20261012.md)。

公开摘录、研究者分析与合成画像分开保存。账号可追溯不等于现实身份验证；历史旅行情境不能自动视为当前计划。仿真结果不表示真实购买概率或人群占比，维度权重表示研究关注程度。

---

## 常见问题

**没有 API Key 能使用吗？**

可以。默认规则模式支持画像生成和方案测试；模型选项在未配置时不可选。

**端口 8000 被占用怎么办？**

运行 `python launcher.py` 自动检查可用端口，或将手动启动命令的端口改为 `8080`，访问对应地址。

**首次打开为什么没有画像？**

仓库中的 `data/personas.json` 初始为空，不上传本机生成记录。点击“生成画像”即可开始。

**记忆存在哪里？如何迁移？**

位于 `data/travel_memories.json`。停止服务后同时备份记忆与画像文件，画像 ID 必须对应。重新生成后的同名或同 ID 画像不代表同一位真实受访者。

**模型失败会发生什么？**

无效 JSON 或结构问题触发修复重试；画像内容质检仍失败时可回退到合成蓝图，并标记 `archetype_fallback`。模型服务或认证错误会明确返回失败。

**如何查看项目方案和历史研究？**

项目方案保留在 [01_BP](01_BP/消费者心智沙盘_BP.pptx)；历史研究和规划见[文档索引](docs/README.md)。历史文档保留当时范围，当前操作以本 README 和使用手册为准。

---

## 验收对照

1. 新克隆仓库安装依赖后，可在无模型凭据时启动两个前端页面。
2. 生成指定数量旅游画像，任务、步骤、期望结果和维度引用通过一致性校验。
3. 输入方案后，展示四阶段分析和 `advance / hesitate / reject / na` 逐人结果。
4. 新增或启停维度后，后续生成与仿真读取更新配置。
5. 启用记忆后按画像保存最近 10 次触达；清除按钮重置记忆。
6. 保留项目方案 PPT，文档链接、配置模板和测试可在干净检出中验证。

安装测试依赖并运行全部 Python 校验：

```powershell
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
```

浏览器回归使用独立临时数据：

```powershell
npm ci
npx playwright install chromium
npm run test:syntax
npm run test:browser
```

浏览器测试默认使用 Playwright Chromium；本机已安装 Edge 时，可在 PowerShell 设置 `$env:PLAYWRIGHT_CHANNEL = "msedge"` 后运行。GitHub Actions 执行 Python 测试、JavaScript 语法检查、Chromium 回归和 Docker 容器构建与启动验证；这些测试不需要真实模型调用。
