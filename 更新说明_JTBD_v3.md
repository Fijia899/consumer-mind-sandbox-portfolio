# 旅游意向人群沙盘说明

## 当前版本

- 研究对象：旅游意向人群，覆盖目的地选择、同行协调、预算、行程、预订、变更准备和核心体验。
- JTBD：7 个主任务、14 个步骤、9 个期望结果。
- 决策结构：当前 25 个启停可控的维度。
- 画像：按蓝图生成的合成样本；研究验证前只作为假设。
- Harness：结构化上下文、LLM JSON 生成、Pydantic 解析、任务/结果/维度一致性校验、最多 3 次修复重试、规则模式和规则门控仿真。
- DeepSeek：支持通过 `MANCHUANG_ENV_FILE` 引用漫创的配置文件；凭据不进代码库。

## 验证状态

本地规则生成与仿真由 `pytest -q` 验证。若没有提供有效的 DeepSeek 配置，LLM 在线调用无法验证；规则模式仍可完整使用。

## 数据文件

- `data/jobs.json`：任务、步骤和旅程阶段。
- `data/outcomes.json`：期望结果。
- `data/factors.json`：出行触发和决策顾虑。
- `data/persona_seeds.json`：画像蓝图。
- `data/personas.json`：当前画像状态。
