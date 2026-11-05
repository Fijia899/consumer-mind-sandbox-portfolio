# 旅游心智沙盘：参考仓库更新记录

> 历史研究或实施记录：本页保留当时范围与验证结果。当前操作、页面和测试命令请以[项目 README](../README.md)及[文档索引](README.md)为准。

核对日期：2026-10-12（北京时间）。通过 GitHub API 核对默认分支 main，并读取最新提交及相关差异。

参考仓库：[Customer-Mind-JTBD-Sandbox](https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox)。

| 参考提交 | 提交日期 | 可迁移改动 | 本项目适配 |
| --- | --- | --- | --- |
| [7747517](https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox/commit/7747517a36ccd92fb4a5c68866bc565ab18329c1) | 2026-09-06 | 助力点优先、结果状态卡、画像联动、页面缓存修正 | 旅游方案助力点、已回应/待确认/下一步核对、查看对应画像、HTML 和静态资源禁缓存 |
| [d1266b6](https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox/commit/d1266b6b844311b57bb2b75aaa41bdd072c8280b) | 2026-09-04 | 按画像过滤不适用干预、负面语义误伤修正、关键缺口门控 | 限制条件按旅游画像关联维度判断；消除双重否定误伤；拒绝时清空回应项；LLM 不能升级规则犹豫结果 |
| [f7d0c4b](https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox/commit/f7d0c4b35c0a3208f37a92b2a17af9763da5deb7) | 2026-09-03 | 随机人格生成 | 随机排列旅游蓝图、微调关注权重和满意度；可指定种子；每轮仍覆盖选定任务 |

参考文件：`frontend/js/app.js`、`frontend/css/app.css`、`backend/main.py`、`backend/services/simulate.py`、`backend/services/llm_simulate.py`。采用机制适配，旅游任务与数据保留为本项目研究假设。

## 研究与判定边界

- 8 类旅游助力点：费用透明、灵活退改、近期真实信息、同行协调、路线与接驳、当地客服与售后、天气与安全预案、出行准备支持。
- 按标点分句，通过关键词和已启用维度识别助力点；对单个画像只保留其决策力量中关联的维度。不能替代自然语言理解、方案真实性核实或真人访谈。
- “已回应”表示话术回应了画像的期望结果，不表示真实满意度、实际成交或实测改善。下一步显示需核对的当前任务步骤，不自动改变旅行阶段或预订状态。
- 随机规则模式保留人物叙事和旅行事实，只调整蓝图顺序、关注权重（±1）与满意度（±1）。原创姓名与生活细节继续由 DeepSeek 模式负责。
- DeepSeek 若缺少关键结果回应，不能判定推进；所有未回应结果重新计算，下一步限于该主任务的合法步骤。模型调用由离线替身测试验证，本次未使用真实 API。
- 画像质检核对角色与任务承担者、阶段与当前步骤、主导特征与维度权重的一致性，并拒绝重复期望结果。模型首次返回无效 JSON 或字段不全时，修复重试仍携带完整结构上下文。

## 验证

运行 `python -m pytest -q`、`node --check frontend/js/travel.js` 和 `node tests/travel_browser.cjs`（需可解析 Playwright，已安装 Edge）。浏览器检查使用临时画像数据，覆盖生成、仿真、助力点、结果摘要、中文结果名、画像联动、390px 布局、文本转义及重新生成后的旧结果清理。

本次验证结果：34 项 Python 测试通过；JavaScript 语法检查通过；Edge 浏览器回归全部通过；桌面与手机长截图已检查；`git diff --check` 通过。
