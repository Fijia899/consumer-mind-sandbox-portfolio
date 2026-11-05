# 旅游意向心智沙盘规格

## 产品范围

面向有明确或初步出行意向、正在做目的地选择、同行协调、预算安排、行程规划、预订核验与出行准备的人群。系统用于组织研究假设和比较方案反应，不预测真实转化率，也不替代用户研究。

现有样本全部标记为合成假设。没有直接研究证据时，不得把生成反馈描述为真实用户原话或市场事实。

## JTBD 数据

- 7 个主任务：目的地、同行协调、预算、路线、预订、变更保障、核心体验。
- 14 个步骤：按出行阶段排序，可在多个任务间共用。
- 9 个期望结果：以用户想要的结果描述，不把具体产品功能写成任务。
- 当前 25 个维度：A 组表示出行触发，B 组表示决策顾虑；关键词用于规则初筛，权重用于结果解释。

源数据位于 `data/jobs.json`、`data/outcomes.json`、`data/factors.json`。画像蓝图位于 `data/persona_seeds.json`，最近一次生成结果写入 `data/personas.json`。

## Harness 流程

### 画像生成

1. 根据任务筛选蓝图，组成结构化上下文：主任务、步骤、期望结果、决策维度和旅游计划字段。
2. 将蓝图和 JSON schema 注入生成提示词；限制证据标签并禁止编造访谈与统计。
3. 解析模型 JSON，并检查人物任务、当前步骤、期望结果、维度引用、预算与同行人数。
4. 校验失败后将问题和原画像提交给修复提示词，最多尝试 3 次；内容质检仍失败时回退到有效蓝图并标记 `archetype_fallback`，不保存无效画像。模型服务故障明确返回错误。
5. 规则模式使用同一套蓝图生成可复现画像，不需要外部模型。

### Campaign 仿真

1. 关键词识别话术涉及的维度。
2. 用用户当前任务、主要期望结果和力量字段进行规则初判，形成反应、结果变化、意愿分和下一步骤。
3. 可选调用 DeepSeek 生成自然语言表达。
4. LLM 结果经过规则门控：不能把规则侧拒绝/无关的结果升级成推进，不能引入无关期望结果。

## 技术结构

- FastAPI 路由：`backend/routes/travel.py`
- Harness：`backend/services/travel_harness.py`
- Pydantic 数据结构：`backend/schemas.py`
- DeepSeek 配置：`backend/config.py`
- 静态界面：`frontend/index.html`（主工作台）、`frontend/admin.html`（决策维度）
- 当前画像状态：`backend/services/persona_store.py`

## DeepSeek 配置

本地 `.env` 可设置 `MANCHUANG_ENV_FILE`，指向漫创正在使用的 `.env`。该文件应包含 `DEEPSEEK_API_KEY`；`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 可沿用漫创配置。也支持直接通过进程环境设置对应 DeepSeek 变量。密钥不能进入源代码、测试夹具、日志或 Git。

## API

- `GET /api/config`：模型配置状态，不返回密钥。
- `GET /api/jobs`、`GET /api/outcomes`、`GET /api/factors`：读取 JTBD 研究结构。
- `POST /api/factors`、`PUT /api/factors/{id}`、`DELETE /api/factors/{id}`：维护决策维度。
- `POST /api/generate`：按数量、模型模式和任务筛选生成画像。
- `GET /api/personas`：读取画像。
- `POST /api/simulate`：规则或 LLM 仿真。
- `GET /api/health`：健康状态与模型是否已配置。

## 验收

- `python -m pytest -q` 全部通过（包含应用测试和 `03_validation` 仓库校验）。
- `npm run test:syntax`、`npm run test:browser` 通过；浏览器运行使用隔离数据。
- 规则模式无需 API 凭据即可生成画像并完成仿真。
- 所有输出任务、步骤、期望结果和维度 ID 均可在数据源中找到。
- 不把合成假设包装为已验证证据。
