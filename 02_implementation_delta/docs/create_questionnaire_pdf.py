from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "抚心App_消费者心智与戒断功能咨询问卷.pdf"
FONT = Path(r"C:\Windows\Fonts\Deng.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\Dengb.ttf")

pdfmetrics.registerFont(TTFont("NotoSC", str(FONT)))
pdfmetrics.registerFont(TTFont("NotoSC-Bold", str(FONT_BOLD)))

NAVY = colors.HexColor("#1F3A5F")
TEAL = colors.HexColor("#2A7F84")
LIGHT = colors.HexColor("#F2F7F7")
MID = colors.HexColor("#D6E5E5")
TEXT = colors.HexColor("#24313A")
MUTED = colors.HexColor("#66737A")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("TitleCN", fontName="NotoSC-Bold", fontSize=20, leading=28, alignment=TA_CENTER, textColor=NAVY, spaceAfter=5 * mm))
styles.add(ParagraphStyle("SubTitleCN", fontName="NotoSC", fontSize=10, leading=16, alignment=TA_CENTER, textColor=MUTED, spaceAfter=7 * mm))
styles.add(ParagraphStyle("SectionCN", fontName="NotoSC-Bold", fontSize=13, leading=19, textColor=NAVY, spaceBefore=3 * mm, spaceAfter=2 * mm))
styles.add(ParagraphStyle("QuestionCN", fontName="NotoSC-Bold", fontSize=10.2, leading=16, textColor=TEXT, spaceAfter=1.2 * mm))
styles.add(ParagraphStyle("OptionCN", fontName="NotoSC", fontSize=9.2, leading=14, textColor=TEXT, leftIndent=2 * mm, spaceAfter=0.5 * mm))
styles.add(ParagraphStyle("NoteCN", fontName="NotoSC", fontSize=8.5, leading=13, textColor=MUTED))


def p(text, style):
    return Paragraph(text, styles[style])


def checkbox_options(options):
    return "<br/>".join(f"□ {item}" for item in options)


def question(number, text, options, multi=False):
    suffix = "（可多选）" if multi else "（单选）"
    return KeepTogether([
        p(f"{number}. {text} <font color='#2A7F84'>{suffix}</font>", "QuestionCN"),
        p(checkbox_options(options), "OptionCN"),
        Spacer(1, 1.5 * mm),
    ])


def footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(MID)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("NotoSC", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8 * mm, "抚心 App｜消费者心智与戒断功能咨询问卷")
    canvas.drawRightString(width - 18 * mm, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="抚心 App 消费者心智与戒断功能咨询问卷",
        author="抚心 App 项目组",
    )

    story = [
        p("抚心 App 消费者心智与戒断功能咨询问卷", "TitleCN"),
        p("面向心理咨询老师｜预计用时 10–15 分钟", "SubTitleCN"),
        Table(
            [[p("填写说明", "QuestionCN")], [p("本问卷仅了解分手后情绪戒断人群的共性特征、功能建议与安全边界，不涉及任何具体来访者身份或隐私。除特别注明外，每题请选择一个答案。", "NoteCN")]],
            colWidths=[174 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.6, MID),
                ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]),
        ),
        Spacer(1, 5 * mm),
        Table([[p("咨询老师：________________", "NoteCN"), p("日期：____________", "NoteCN")]], colWidths=[90 * mm, 84 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    ]

    story += [p("一、目标人群特征", "SectionCN")]
    story += [
        question(1, "您接触过分手、失恋或关系结束相关来访者吗？", ["经常接触", "偶尔接触", "很少接触", "没有接触过"]),
        question(2, "这类来访者通常在分手后多久寻求帮助？", ["1 周内", "1 周至 1 个月", "1 至 3 个月", "3 个月以上", "没有明显规律"]),
        question(3, "他们最常见的主要诉求是什么？", ["想复合", "不想复合但放不下", "停止联系或查看前任动态", "恢复学习或工作", "缓解孤独和痛苦", "重建自信", "其他：____________"], True),
        question(4, "他们最常见的情绪是什么？", ["思念", "痛苦", "焦虑", "愤怒", "后悔或自责", "孤独", "麻木", "期待前任回头", "其他：____________"], True),
        question(5, "他们最容易在哪些情境下情绪复发？", ["夜晚或失眠时", "独处时", "看到前任动态时", "节日、生日或纪念日", "工作或学习压力大时", "饮酒后", "与朋友谈起前任时", "其他：____________"], True),
        question(6, "“理性上不想复合、情感上仍未戒断”的人，最典型的行为是什么？", ["反复查看前任动态", "删除又恢复联系方式", "想发消息但忍住", "反复回看聊天记录", "反复回忆关系细节", "期待前任主动联系", "通过朋友打听前任", "其他：____________"], True),
    ]

    story += [p("二、戒断功能与文案", "SectionCN")]
    story += [
        question(7, "您认为最值得优先解决的问题是什么？", ["停止联系前任", "停止查看前任动态", "缓解夜间情绪", "减少反刍和回忆", "应对孤独", "重建生活节奏", "重建自我价值"]),
        question(8, "用户产生联系冲动时，最适合的第一步是什么？", ["延迟行动 5–10 分钟", "记录当前冲动", "回顾分手事实", "进行呼吸或放松练习", "转移注意力", "联系朋友", "直接寻求专业帮助", "不确定"]),
        question(9, "哪类功能最可能被用户接受？", ["情绪打卡", "冲动记录", "前任动态屏蔽辅助", "不复合事实卡片", "每日小任务", "情绪急救", "戒断进度记录", "AI 陪伴对话", "专业内容课程"], True),
        question(10, "每次情绪干预的合适时长是？", ["1–3 分钟", "3–5 分钟", "5–10 分钟", "10–20 分钟", "20 分钟以上"]),
        question(11, "“戒断”这个词对用户可能产生什么影响？", ["有行动力量", "容易理解", "可能产生羞耻感", "可能让人感到压力", "可能强化“我生病了”的感觉", "需要根据用户类型区别使用", "不建议使用"], True),
        question(12, "哪类表达最容易让用户反感？", ["“你应该赶快放下”", "“前任不值得”", "“你要学会爱自己”", "“时间会治愈一切”", "过度积极的鸡汤", "过度批判前任", "绝对化表达，如“永远不要回头”", "其他：____________"], True),
        question(13, "哪类表达更可能让用户感到被理解？", ["承认想念是正常的", "不要求用户马上放下", "允许用户反复和退步", "提供具体可执行的小行动", "帮助用户看清关系事实", "强调恢复需要时间", "其他：____________"], True),
    ]

    story += [PageBreak(), p("三、用户分群与沙盘建模", "SectionCN")]
    story += [
        question(14, "您认为这类用户最适合分成哪些类型？", ["夜间脆弱型", "反复联系型", "等待复合型", "理性清醒型", "自我价值受损型", "孤独依赖型", "创伤恢复型", "高执行打卡型", "其他：____________"], True),
        question(15, "判断一个用户是否真正需要“戒断服务”，最重要的指标是什么？", ["联系前任频率", "查看前任动态频率", "情绪痛苦程度", "对日常生活的影响", "复合冲动强度", "失眠或食欲变化", "工作学习受影响程度", "其他：____________"]),
        question(16, "一个真实可信的虚拟用户画像，最应该包含哪些信息？", ["分手时间", "关系持续时间", "分手原因", "当前联系状态", "复合冲动", "主要触发场景", "核心恐惧", "自我价值状态", "对鸡汤的接受程度", "执行任务的能力", "是否有朋友或专业支持"], True),
        question(17, "对同一条 App 文案，沙盘最好模拟哪些结果？", ["是否愿意打开", "是否愿意继续阅读", "是否愿意尝试功能", "是否觉得被理解", "是否产生反感", "是否加重情绪", "是否增强复合幻想", "是否可能中途退出", "是否需要专业转介"], True),
    ]

    story += [p("四、安全边界", "SectionCN")]
    story += [
        question(18, "哪些情况出现时，App 应停止普通自助流程并建议寻求人工帮助？", ["出现自伤或轻生表达", "出现伤害前任或他人的想法", "严重失眠", "无法正常学习或工作", "持续极度绝望", "明显跟踪、骚扰或报复行为", "严重饮酒或药物依赖", "其他：____________"], True),
    ]

    story += [Spacer(1, 5 * mm), HRFlowable(width="100%", thickness=0.6, color=MID), Spacer(1, 3 * mm), p("感谢您的专业建议。若您愿意参与后续 Persona 审阅或高风险场景评估，请留下联系方式：____________________________", "NoteCN")]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    assert OUTPUT.exists() and OUTPUT.stat().st_size > 10000
    print(OUTPUT)


if __name__ == "__main__":
    build()
