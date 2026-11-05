# GitHub 仓库检查与整理记录

检查日期：2026-11-05（Asia/Shanghai）。目标仓库为 [consumer-mind-sandbox-portfolio](https://github.com/Fijia899/consumer-mind-sandbox-portfolio)。整理前远端提交为 `12879e68d4005d955bc1369e93fcc29f3a1f9e5d`，只包含 README、项目方案 PPT、忽略规则与资料包测试。

## 缺失与处理

| 检查项 | 发现 | 处理 |
| --- | --- | --- |
| 可运行应用 | 远端缺少后端、页面与研究结构 | 补齐 `backend/`、当前两页 `frontend/`、版本化旅游数据和启动入口 |
| 项目方案 | 已有 PPT 完整 | 保留原文件，继续验证 SHA-256 |
| README | 只描述资料包 | 按参考项目的环境、配置、启动、页面、流程、目录、API、关系、FAQ、验收结构重写 |
| 规格与手册 | 维度数量和部分页面说明已过期 | 对齐实际 25 个维度、两页工作台、可视化流程和记忆行为 |
| 测试复现 | 语料测试依赖未发布的本机台账 | 从版本化来源与导入批次在临时目录重建；画像、研究状态和记忆全部隔离 |
| 依赖与 CI | 缺测试依赖声明、浏览器安装说明和自动验证 | 补齐 Python 测试依赖、Node 锁文件、跨平台浏览器选择与 GitHub Actions |
| 部署 | 旧配置使用多个 worker，说明与 JSON 存储约束不符 | 改为单 worker、本机端口映射、只读配置挂载和健康检查 |
| 仓库边界 | 本地有历史原型、依赖与生成材料 | 仅纳入当前应用和相关研究；忽略私有状态、依赖、缓存与旧原型 |
| GitHub 展示 | 缺少仓库简介和主题 | 补充旅游 JTBD 项目简介，以及 `jtbd`、`travel`、`consumer-research`、`fastapi`、`python`、`sandbox` 主题 |

应用从本地已提交的旅游工作台版本 `eedbcabf238b6f5c0c5afa18ef71a8c2e88d0b05` 整理，保留生成、规则仿真、模型质检、连续触达记忆和四阶段展示。默认画像状态为空，不上传本机当前画像、研究台账、数据库、音频或真实 `.env`。公开材料定位链接移除分享参数，保留路径、研究定位参数和片段。

## 研究版本

通过 `git ls-remote https://github.com/yiqiyao13/Customer-Mind-JTBD-Sandbox.git HEAD refs/heads/main` 核对，远端为 `7747517a36ccd92fb4a5c68866bc565ab18329c1`，与本地记录一致，无新增研究变更需要同步。当前研究对象、画像、示例与场景统一围绕旅游意向人群。

## 验证与边界

本地及全新虚拟环境各有 200 项 Python 测试通过；JavaScript 语法检查、锁文件安装和 Playwright Chromium 浏览器回归通过，项目方案 PPT 的 SHA-256 与整理前一致。交付校验包括全量 Python 测试、仓库与文档检查、JavaScript 语法检查、隔离服务的浏览器回归，以及仅从 Git 跟踪文件生成的干净检出验证。浏览器覆盖画像生成、动画阶段、进度、重播、减少动画设置、失败重试、结果和移动布局。

模型测试使用离线替身，不表示真实模型服务质量验收。本机没有 Docker，因此容器配置仅完成静态检查，未执行镜像构建或容器运行。GitHub Actions 的实际运行状态以仓库 Actions 页面为准。
