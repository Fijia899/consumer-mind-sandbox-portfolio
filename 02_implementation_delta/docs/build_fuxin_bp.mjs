import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const root = "D:/Xiaofeizheshapan";
const buildDir = path.join(root, ".codex-build-fuxin-bp");
const outputDir = path.join(root, "outputs");
const draftPath = path.join(buildDir, "fuxin-consumer-mind-sandbox-bp-draft.pptx");
const finalPath = path.join(outputDir, "抚心消费者心智沙盘_BP.pptx");
const skillDir = "C:/Users/fkxlucky/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const { resolvePresentationFont } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);

await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });
const font = resolvePresentationFont({ fontFamily: "Aptos" });

const C = {
  ink: "#17252D",
  navy: "#173B4D",
  teal: "#2C8A87",
  mint: "#E8F4F1",
  sand: "#F5F1EA",
  coral: "#E47765",
  line: "#D3DFDE",
  muted: "#64747B",
  white: "#FFFFFF",
};

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function box(slide, x, y, w, h, fill = "none", line = "none", radius = false) {
  const s = slide.shapes.add({ geometry: radius ? "roundRect" : "rect", position: { left: x, top: y, width: w, height: h }, fill, line: { fill: line, width: line === "none" ? 0 : 1 } });
  return s;
}

function text(slide, value, x, y, w, h, size = 22, color = C.ink, opts = {}) {
  const s = slide.shapes.add({ geometry: "textbox", position: { left: x, top: y, width: w, height: h }, fill: "none", line: { fill: "none", width: 0 } });
  s.text = value;
  s.text.style = { typeface: font, fontSize: size, color, bold: Boolean(opts.bold), italic: Boolean(opts.italic), autoFit: "shrink" };
  if (opts.align) s.text.paragraphFormat = { alignment: opts.align };
  return s;
}

function title(slide, kicker, heading, sub = "") {
  text(slide, kicker.toUpperCase(), 70, 48, 500, 22, 13, C.teal, { bold: true });
  text(slide, heading, 70, 78, 1110, 55, 34, C.navy, { bold: true });
  if (sub) text(slide, sub, 70, 140, 1050, 30, 16, C.muted);
}

function footer(slide, n) {
  box(slide, 70, 681, 1140, 1, C.line);
  text(slide, "抚心｜消费者心智沙盘 BP", 70, 690, 400, 16, 10, C.muted);
  text(slide, String(n).padStart(2, "0"), 1160, 690, 50, 16, 10, C.muted, { align: "right" });
}

function note(slide, content) { slide.speakerNotes.textFrame.setText(content); }

// 1 Cover
{
  const s = presentation.slides.add(); s.background.fill = C.sand;
  box(s, 70, 70, 12, 125, C.teal);
  text(s, "抚心 FUXIN", 110, 76, 520, 40, 18, C.teal, { bold: true });
  text(s, "把“放不下”变成\n可以被陪伴和练习的过程", 110, 180, 850, 150, 46, C.navy, { bold: true });
  text(s, "消费者心智沙盘 + 情感戒断服务\n创业项目 BP｜初版方案", 114, 370, 650, 70, 22, C.ink);
  box(s, 900, 165, 240, 240, C.mint, "none", true);
  text(s, "想联系\n前任", 935, 208, 170, 75, 28, C.navy, { bold: true, align: "center" });
  text(s, "10 min", 935, 315, 170, 36, 18, C.teal, { bold: true, align: "center" });
  text(s, "延迟行动，先陪自己", 935, 365, 170, 28, 13, C.muted, { align: "center" });
  text(s, "2026.09", 110, 610, 200, 24, 14, C.muted);
  note(s, "定位说明：本 BP 将已知产品设想与待验证假设分开呈现。当前没有虚构市场规模、收入或疗效数据。");
}

// 2 Problem
{
  const s = presentation.slides.add(); s.background.fill = C.white; title(s, "01｜机会", "用户知道不该复合，但情绪不会按道理停止", "抚心聚焦“理性结束、情感未戒断”的分手后人群");
  text(s, "用户卡在一个反复循环里", 70, 215, 420, 30, 19, C.navy, { bold: true });
  const steps = [["触发", "夜晚、动态、纪念日"], ["冲动", "想确认、想发消息"], ["行动", "查看、联系、反复"], ["后悔", "短暂缓解后再次自责"]];
  steps.forEach((a, i) => { const x = 70 + i * 280; box(s, x, 275, 220, 120, i === 1 ? C.mint : C.sand, "none", true); text(s, a[0], x + 20, 295, 180, 28, 22, C.teal, { bold: true }); text(s, a[1], x + 20, 340, 180, 40, 16, C.ink); if (i < 3) text(s, "→", x + 232, 315, 35, 30, 25, C.coral, { bold: true, align: "center" }); });
  box(s, 70, 490, 1140, 95, C.navy, "none", true);
  text(s, "产品机会", 100, 512, 150, 25, 16, C.mint, { bold: true });
  text(s, "在用户最容易复发的瞬间，提供低负担、具体、可重复的支持。", 100, 545, 1020, 30, 24, C.white, { bold: true });
  footer(s, 2); note(s, "问题陈述来自当前产品假设，需通过真实用户访谈和行为数据验证。");
}

// 3 User
{
  const s = presentation.slides.add(); s.background.fill = C.white; title(s, "02｜用户", "同样是“放不下”，背后的需求并不相同", "沙盘先区分心理机制，再决定内容和干预");
  const rows = [
    ["夜间脆弱型", "白天清醒，夜晚独处时冲动", "即时情绪急救"],
    ["等待复合型", "嘴上说不复合，仍期待对方回头", "承认矛盾，逐步降低幻想"],
    ["反复联系型", "拉黑、加回、删除、重联反复发生", "延迟行动和复发记录"],
    ["自我价值受损型", "把分手解释为自己不值得被爱", "恢复自我感与生活掌控"],
    ["高执行型", "愿意打卡、记录和完成计划", "结构化 7/14/30 天路径"],
  ];
  text(s, "典型用户", 70, 205, 190, 24, 16, C.teal, { bold: true }); text(s, "第一需求", 825, 205, 240, 24, 16, C.teal, { bold: true });
  rows.forEach((r, i) => { const y = 245 + i * 72; box(s, 70, y, 1140, 58, i % 2 === 0 ? C.sand : C.mint, "none", true); text(s, r[0], 95, y + 15, 210, 25, 17, C.navy, { bold: true }); text(s, r[1], 330, y + 15, 440, 25, 16, C.ink); text(s, r[2], 825, y + 15, 330, 25, 16, C.ink); });
  text(s, "注：这些是待验证的工作分群，不代表临床分类。", 70, 630, 700, 22, 12, C.muted, { italic: true }); footer(s, 3);
}

// 4 Solution
{
  const s = presentation.slides.add(); s.background.fill = C.sand; title(s, "03｜方案", "抚心在冲动发生时，帮助用户先完成一个小动作", "先稳定当下，再逐步重建生活节奏");
  const left = [["识别", "记录当前触发和情绪强度"], ["延迟", "把“马上联系”推迟 5–10 分钟"], ["复盘", "回到关系事实，而不是只记住美好片段"], ["重建", "通过小任务恢复生活中的掌控感"]];
  left.forEach((r, i) => { const y = 220 + i * 82; box(s, 75, y, 500, 62, C.white, "none", true); text(s, String(i + 1), 98, y + 16, 34, 28, 20, C.coral, { bold: true }); text(s, r[0], 150, y + 14, 90, 25, 18, C.navy, { bold: true }); text(s, r[1], 255, y + 15, 280, 25, 15, C.ink); });
  box(s, 700, 235, 380, 255, C.navy, "none", true); text(s, "用户此刻说：", 740, 270, 260, 28, 15, C.mint); text(s, "“我好想给他发消息。”", 740, 320, 300, 50, 27, C.white, { bold: true }); text(s, "抚心先做：\n延迟 10 分钟 + 情绪急救", 740, 405, 300, 55, 18, C.mint, { bold: true }); footer(s, 4);
}

// 5 Sandbox
{
  const s = presentation.slides.add(); s.background.fill = C.white; title(s, "04｜心智沙盘", "先把“心理共性”变成可测试的假设", "沙盘不替代真实用户研究，它帮助你比较方案、发现风险、决定先验证什么");
  const stages = [["用户洞察", "访谈、问卷、专业经验"], ["维度库", "夜间脆弱、复合幻想、联系冲动"], ["Persona", "不同触发、动机和阻力"], ["测试输入", "推送、功能、流程"], ["输出", "打开、尝试、退出、复发风险"]];
  stages.forEach((r, i) => { const x = 70 + i * 225; box(s, x, 260, 180, 145, i === 2 ? C.navy : C.mint, "none", true); text(s, r[0], x + 18, 285, 145, 28, 17, i === 2 ? C.white : C.navy, { bold: true, align: "center" }); text(s, r[1], x + 18, 335, 145, 55, 14, i === 2 ? C.mint : C.ink, { align: "center" }); if (i < 4) text(s, "→", x + 188, 315, 30, 30, 22, C.coral, { bold: true, align: "center" }); });
  box(s, 210, 500, 860, 72, C.sand, "none", true); text(s, "每个结论都标注：已验证｜专家支持｜待验证假设", 250, 523, 780, 28, 21, C.navy, { bold: true, align: "center" }); footer(s, 5); note(s, "核心原则：维度是数据库，Persona 是生成物；沙盘输出用于形成可验证假设，不作为真实用户预测。");
}

// 6 Data flywheel
{
  const s = presentation.slides.add(); s.background.fill = C.sand; title(s, "05｜数据闭环", "真实反馈持续校准沙盘，沙盘持续降低试错成本", "产品越使用，Persona、场景和安全边界越具体");
  const loop = [["真实事件", "触发—想法—行为—结果"], ["结构化", "转成维度、场景、原话"], ["沙盘测试", "比较文案和功能方案"], ["小规模上线", "观察点击、完成和复发"], ["修正模型", "调整分群、规则和风险"]];
  loop.forEach((r, i) => { const x = 90 + (i % 3) * 365; const y = i < 3 ? 230 : 450; box(s, x, y, 275, 95, i === 2 ? C.navy : C.white, "none", true); text(s, r[0], x + 22, y + 20, 230, 25, 18, i === 2 ? C.white : C.teal, { bold: true, align: "center" }); text(s, r[1], x + 22, y + 55, 230, 22, 14, i === 2 ? C.mint : C.ink, { align: "center" }); });
  text(s, "关键判断", 90, 610, 140, 22, 14, C.coral, { bold: true }); text(s, "收集“用户说了什么、做了什么、后来变成什么状态”，三者必须分开记录。", 225, 607, 900, 28, 19, C.navy, { bold: true }); footer(s, 6);
}

// 7 MVP
{
  const s = presentation.slides.add(); s.background.fill = C.white; title(s, "06｜MVP", "第一版只做一个可验证的核心循环", "输入一条推送，让 5 个虚拟用户反馈，并指导下一轮真实测试");
  const steps = [["1", "建立 10–15 个维度", "来自访谈与专业审核"], ["2", "生成 5–10 个 Persona", "每人有不同触发与阻力"], ["3", "测试推送/功能", "模拟打开、尝试、退出"], ["4", "真实用户验证", "访谈 + 小规模原型"], ["5", "更新沙盘", "沉淀新场景和安全规则"]];
  steps.forEach((r, i) => { const x = 70 + i * 230; box(s, x, 260, 185, 235, i === 2 ? C.navy : C.sand, "none", true); text(s, r[0], x + 20, 285, 145, 35, 28, i === 2 ? C.coral : C.teal, { bold: true, align: "center" }); text(s, r[1], x + 20, 345, 145, 55, 18, i === 2 ? C.white : C.navy, { bold: true, align: "center" }); text(s, r[2], x + 20, 430, 145, 45, 14, i === 2 ? C.mint : C.ink, { align: "center" }); }); footer(s, 7);
}

// 8 validation
{
  const s = presentation.slides.add(); s.background.fill = C.sand; title(s, "07｜验证", "先验证“用户是否真的愿意使用”，再验证长期效果", "没有真实数据的部分，在 BP 中明确写成假设");
  const cols = [["阶段 1", "10 次访谈", "收集触发场景、用户原话、已有应对方式"], ["阶段 2", "50–100 份匿名问卷", "确认高频场景和用户分群是否稳定"], ["阶段 3", "10 人原型测试", "观察是否打开、完成、退出或复发"], ["阶段 4", "小规模连续使用", "观察 7 天留存、冲动变化和安全事件"]];
  cols.forEach((r, i) => { const x = 70 + i * 285; box(s, x, 245, 235, 255, C.white, "none", true); text(s, r[0], x + 20, 275, 195, 22, 14, C.teal, { bold: true }); text(s, r[1], x + 20, 325, 195, 45, 22, C.navy, { bold: true }); text(s, r[2], x + 20, 405, 195, 70, 15, C.ink); });
  box(s, 70, 550, 1140, 62, C.mint, "none", true); text(s, "不先承诺“治愈”，先验证：能否在关键时刻帮助用户少做一次冲动行为。", 105, 568, 1070, 26, 19, C.navy, { bold: true, align: "center" }); footer(s, 8);
}

// 9 business
{
  const s = presentation.slides.add(); s.background.fill = C.white; title(s, "08｜商业化", "先做用户价值，再选择收入路径", "商业模式与市场规模暂列为待验证假设");
  text(s, "产品层", 75, 220, 200, 24, 16, C.teal, { bold: true }); text(s, "抚心 App", 75, 258, 300, 40, 28, C.navy, { bold: true }); text(s, "面向个人用户的情绪戒断与生活重建服务", 75, 315, 390, 50, 17, C.ink);
  text(s, "研究层", 490, 220, 200, 24, 16, C.teal, { bold: true }); text(s, "消费者心智沙盘", 490, 258, 400, 40, 28, C.navy, { bold: true }); text(s, "面向内容、产品和增长团队的测试与研究工具", 490, 315, 410, 50, 17, C.ink);
  text(s, "可能的收入方向", 75, 445, 250, 24, 16, C.teal, { bold: true });
  const revenue = ["会员订阅：连续戒断路径", "专业内容：课程与工具包", "机构合作：心理服务转介", "研究工具：团队版沙盘"];
  revenue.forEach((r, i) => { const x = 75 + (i % 2) * 520; const y = 490 + Math.floor(i / 2) * 58; box(s, x, y, 450, 42, C.sand, "none", true); text(s, "□  " + r, x + 18, y + 10, 410, 22, 16, C.ink); }); footer(s, 9); note(s, "商业化方向为假设，不代表已验证的付费意愿或市场规模。");
}

// 10 roadmap
{
  const s = presentation.slides.add(); s.background.fill = C.navy; text(s, "09｜下一步", 70, 55, 400, 24, 14, C.mint, { bold: true }); text(s, "用一个小闭环，验证抚心是否值得继续做", 70, 92, 1100, 55, 36, C.white, { bold: true });
  const roadmap = [["本周", "完成咨询师访谈\n整理第一版维度库"], ["第 2–3 周", "访谈 10 位用户\n建立 Persona 和场景"], ["第 4–6 周", "做最小沙盘\n测试 20 条推送/功能"], ["之后", "做抚心原型\n用真实行为校准模型"]];
  roadmap.forEach((r, i) => { const x = 75 + i * 285; box(s, x, 235, 235, 190, i === 0 ? C.teal : "#28546A", "none", true); text(s, r[0], x + 20, 260, 195, 25, 16, C.mint, { bold: true }); text(s, r[1], x + 20, 315, 195, 70, 20, C.white, { bold: true }); });
  text(s, "需要的第一批合作", 75, 520, 260, 26, 16, C.mint, { bold: true }); text(s, "心理咨询专业意见｜真实用户访谈｜10 人原型测试｜隐私与安全审阅", 75, 565, 1080, 30, 22, C.white, { bold: true });
  text(s, "抚心的第一版，不是让用户立刻忘掉一个人，而是帮他少做一次违背长期目标的冲动行为。", 75, 650, 1120, 22, 12, C.mint, { italic: true }); note(s, "结尾信息：项目当前处于研究与 MVP 验证阶段，下一步是建立维度库、访谈真实用户并制作最小沙盘。");
}

const candidate = await (await PresentationFile.exportPptx(presentation)).save(draftPath);
console.log(`draft=${candidate}`);
console.log(`final=${finalPath}`);
