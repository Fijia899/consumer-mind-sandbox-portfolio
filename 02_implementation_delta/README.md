# 抚心 App｜JTBD 心智模拟原型

基于 JTBD 方法构建的情绪支持服务研究原型：

> Job / Step / Outcome 任务模型 + 决策维度 + Persona 画像 + 方案情景模拟与反馈

## 项目功能

- **JTBD 任务模型**：维护 Jobs、Sub-Jobs、期望结果和干预方式。
- **决策维度库**：浏览、添加、编辑和停用研究维度，查看维度关联的任务与结果。
- **Persona 生成**：按任务、场景和角色生成画像，支持规则模式与 DeepSeek LLM 模式。
- **方案模拟**：输入服务方案或沟通内容，查看逐个画像的反馈、任务进展和维度命中情况。
- **情景记忆**：保存模拟经历，供后续触达参考；支持记忆查询、导入、导出和清理。
- **反馈验证**：记录方案反馈，并将结果导出为 Excel，便于比较和复盘。
- **风险识别**：对高风险输入执行额外门控，并显示相应处理提示。

## 项目目录

```text
├── launcher.py                 # Windows 一键启动器
├── backend/
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 模型配置加载
│   ├── routes/                 # 维度、画像、模拟与任务接口
│   └── services/               # JTBD、生成、模拟、记忆与导出逻辑
├── frontend/
│   ├── index.html              # 工作台
│   ├── admin.html              # 决策维度后台
│   ├── jobs.html               # JTBD 任务页面
│   ├── css/app.css             # 页面样式
│   └── js/app.js               # 页面交互
├── data/
│   ├── jobs.json               # Job 与 Sub-Job
│   ├── outcomes.json           # 期望结果
│   ├── factors.json            # 决策维度
│   ├── personas.json           # 当前画像
│   └── evolution.json          # 画像经历与记忆
└── tests/                      # 数据结构、生成、模拟与风险门控测试
```

## 环境要求

- Python 3.10+
- Chrome、Edge 或其他现代浏览器
- DeepSeek API Key（可选；规则生成与规则模拟可独立运行）

## 安装与配置

在 `02_implementation_delta/` 目录执行：

```powershell
python -m pip install fastapi "uvicorn[standard]" pydantic python-dotenv openai openpyxl
```

启用 DeepSeek 时，在项目根目录创建 `.env`：

```env
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

未配置密钥时，在工作台选择规则生成和规则模拟。`.env` 保存本地密钥，不要提交到 Git。

## 启动服务

### Windows 启动器

```powershell
python launcher.py
```

### 手动启动

```powershell
Set-Location backend
python -m uvicorn main:app --reload --port 8000
```

服务地址为 `http://127.0.0.1:8000`。在运行窗口按 `Ctrl+C` 停止服务。

## 页面入口

| 页面 | 地址 | 功能 |
| --- | --- | --- |
| 工作台 | `http://127.0.0.1:8000` | 生成画像、运行方案模拟、查看结果与记忆 |
| 决策维度 | `http://127.0.0.1:8000/admin` | 管理维度及启用状态 |
| JTBD 任务 | `http://127.0.0.1:8000/jobs` | 浏览 Jobs、Sub-Jobs、Outcomes 与干预方式 |
| API 文档 | `http://127.0.0.1:8000/docs` | 查看接口参数与响应结构 |

## 使用流程

1. 打开工作台，选择任务、场景和角色，设置画像数量。
2. 选择规则模式或 LLM 模式，生成 Persona 画像。
3. 输入方案内容，设置模拟方式与记忆选项，运行情景测试。
4. 查看各画像的反馈、任务进展和决策维度结果。
5. 记录验证反馈，导出测试结果或记忆数据进行复盘。
6. 在决策维度后台维护维度，在 JTBD 页面查看任务结构。

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET /api/jobs` | 获取 Jobs |
| `GET /api/sub_jobs` | 获取 Sub-Jobs |
| `GET /api/outcomes` | 获取 Outcomes |
| `GET /api/interventions` | 获取干预方式 |
| `GET/POST /api/factors` | 查看或新增决策维度 |
| `PUT/DELETE /api/factors/{id}` | 更新或停用维度 |
| `POST /api/generate` | 生成 Persona 画像 |
| `GET /api/personas` | 获取当前画像 |
| `POST /api/simulate` | 运行方案模拟 |
| `POST /api/verify` | 记录验证反馈 |
| `GET/POST /api/memories/...` | 查询、导入、导出或清理记忆 |
| `POST /api/export/campaign` | 导出方案模拟结果 |

## 验证

在项目根目录运行：

```powershell
python -m pytest -q tests/delta_test_data_integrity.py tests/delta_test_generate.py tests/delta_test_simulate.py tests/delta_test_high_risk_gate_e2e.py
```
