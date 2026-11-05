# 旅游意向人群心智沙盘

基于 JTBD 方法构建的研究与原型项目：

> Job 任务模型 + 决策维度 + Persona 画像 + 旅游场景分析与方案比较

## 项目内容

- **JTBD 任务模型**：组织 Job、Step、Outcome 与推动/阻碍因素。
- **决策维度库**：维护研究维度、关联任务与结果，并用于画像和场景分析。
- **Persona 画像**：支持规则生成与 LLM 生成，可按任务、场景和角色筛选。
- **方案情景测试**：输入方案内容，查看画像反馈、任务进展和结果差异。
- **记忆与反馈**：保存测试经历，支持验证记录、记忆导入导出和结果复盘。
- **项目材料**：包含方案文档、原型代码、研究数据结构和自动化验证。

## 仓库目录

```text
├── 01_BP/                         # 项目方案文档
├── 02_implementation_delta/
│   ├── backend/                   # FastAPI 接口与分析服务
│   ├── frontend/                  # 工作台、维度后台、任务页面
│   ├── data/                      # Jobs、Outcomes、决策维度与画像数据
│   ├── tests/                     # 原型功能与数据结构测试
│   └── launcher.py                # Windows 启动器
└── 03_validation/                 # 作品集完整性测试
```

## 环境要求

- Python 3.10+
- Chrome、Edge 或其他现代浏览器
- DeepSeek API Key（可选；未配置时使用规则模式）

## 安装与配置

在项目根目录安装运行依赖：

```powershell
python -m pip install fastapi "uvicorn[standard]" pydantic python-dotenv openai openpyxl
```

需要使用 LLM 时，在 `02_implementation_delta/.env` 中配置：

```env
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

规则模式无需配置 API Key。`.env` 用于本地配置，不要提交密钥。

## 启动服务

### Windows 启动器

```powershell
Set-Location 02_implementation_delta
python launcher.py
```

### 手动启动

```powershell
Set-Location 02_implementation_delta/backend
python -m uvicorn main:app --reload --port 8000
```

服务默认地址为 `http://127.0.0.1:8000`。按 `Ctrl+C` 停止服务。

## 页面入口

| 页面 | 地址 | 功能 |
| --- | --- | --- |
| 工作台 | `http://127.0.0.1:8000` | 生成画像、输入方案并查看分析结果 |
| 决策维度 | `http://127.0.0.1:8000/admin` | 新增、编辑、启用或停用研究维度 |
| JTBD 任务 | `http://127.0.0.1:8000/jobs` | 浏览 Jobs、Sub-Jobs、Outcomes 与干预方式 |
| API 文档 | `http://127.0.0.1:8000/docs` | 查看接口参数与响应结构 |

## 使用流程

1. 启动服务并打开工作台。
2. 选择任务、场景和角色，设置画像生成数量；按需启用 LLM 生成。
3. 输入旅游方案或服务内容，选择规则分析或 LLM 独立思考并运行测试。
4. 查看逐个画像的反馈、任务进展和决策维度命中情况。
5. 按需启用记忆，记录后续触达结果，导出反馈或记忆数据进行复盘。
6. 在决策维度后台维护研究维度，并在 JTBD 页面查看任务结构。

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET /api/jobs` | 获取主 Job 与任务结构 |
| `GET /api/sub_jobs` | 获取任务步骤 |
| `GET /api/outcomes` | 获取期望结果 |
| `GET/POST /api/factors` | 查看或新增决策维度 |
| `PUT/DELETE /api/factors/{id}` | 更新或停用维度 |
| `POST /api/generate` | 生成 Persona 画像 |
| `GET /api/personas` | 查看当前画像 |
| `POST /api/simulate` | 运行方案情景测试 |
| `POST /api/verify` | 记录验证反馈 |
| `GET/POST /api/memories/...` | 查询、导入、导出或清理记忆 |
| `POST /api/export/campaign` | 导出方案测试结果 |

## 验证

运行作品集与原型测试：

```powershell
python -m pytest -q 03_validation
python -m pytest -q -o "python_files=delta_test_*.py" 02_implementation_delta/tests
```
