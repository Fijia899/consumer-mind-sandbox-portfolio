"""生成结果逻辑一致性校验。"""
from __future__ import annotations

from typing import List, Optional, Set

from schemas import DesiredOutcome, DominantFeature, Factor, Persona

# 16 个预设原型种子名 — LLM 生成时应避免直接复用
ARCHETYPE_SEED_NAMES: Set[str] = {
    "小鹿", "阿澄", "大齐", "小满", "也子", "果果", "木子", "叙白",
    "双双", "楠楠", "纪子", "夏夏", "卷卷", "阿默", "一舟", "拾一",
}

# Job → 默认核心 Outcome（修复漂移时用；对齐 data/jobs.json 的 outcome_ids）
_JOB_OUTCOME_DEFAULTS = {
    "J1": [("O5", 9, 2), ("O2", 8, 4), ("O1", 7, 5)],
    "J2": [("O4", 9, 2), ("O6", 8, 4), ("O2", 7, 5)],
    "J3": [("O1", 9, 2), ("O3", 8, 4), ("O7", 7, 5)],
    "J4": [("O2", 9, 3), ("O3", 8, 4), ("O5", 7, 5)],
    "J5": [("O7", 9, 2), ("O6", 8, 4), ("O1", 7, 5)],
    "J6": [("O8", 9, 3), ("O6", 8, 4), ("O2", 7, 5)],
    "J7": [("O9", 10, 2), ("O1", 8, 4), ("O7", 7, 5)],
}

# 因子 → 允许出现的分群（8 分群视角）。未列出的因子不限分群。
_SEGMENT_HINT: dict = {
    "A1": {"夜间脆弱型", "孤独依赖型"},
    "A2": {"等待复合型", "高执行打卡型"},
    "A3": {"创伤恢复型"},
    "A4": {"反复联系型", "等待复合型"},
    "A5": {"夜间脆弱型", "反复联系型"},
    "A6": {"孤独依赖型", "等待复合型"},
    "A7": {"理性清醒型", "自我价值受损型", "创伤恢复型"},
    "A8": {"夜间脆弱型", "创伤恢复型"},
    "A9": {"理性清醒型", "孤独依赖型"},
    "A10": {"创伤恢复型"},
    "B1": {"夜间脆弱型", "自我价值受损型", "孤独依赖型"},
    "B2": {"夜间脆弱型", "反复联系型"},
    "B3": {"等待复合型", "高执行打卡型"},
    "B4": {"创伤恢复型", "自我价值受损型"},
    "B5": {"夜间脆弱型", "创伤恢复型", "理性清醒型"},
    "B6": {"理性清醒型", "自我价值受损型", "高执行打卡型"},
    "B7": {"创伤恢复型"},
    "B8": {"创伤恢复型"},
    "B9": {"孤独依赖型", "创伤恢复型"},
    "B10": {"理性清醒型", "自我价值受损型", "高执行打卡型"},
    "B11": {"理性清醒型", "高执行打卡型"},
}

_STAGES = ("应激期", "戒断行动期", "稳定坚持期", "复发应对期", "重建转化期")


def factor_fits_persona(
    factor: Factor,
    role: str,
    subject: str,
    family: str,
    segment: str,
) -> bool:
    fid = factor.id
    allowed = _SEGMENT_HINT.get(fid)
    if allowed is None:
        return True
    return segment in allowed


def validate_persona(persona: Persona, factors: List[Factor]) -> List[str]:
    issues: List[str] = []
    factor_map = {f.id: f for f in factors}
    family = persona.family or ""
    jid = persona.jtbd.job_id if persona.jtbd else ""
    seg = persona.segment or ""
    dom_codes = [d.code for d in persona.dominant_features]

    for d in persona.dominant_features:
        f = factor_map.get(d.code)
        if not f:
            issues.append(f"未知维度 {d.code}")
            continue
        if not factor_fits_persona(f, persona.role, persona.subject, family, persona.segment):
            issues.append(
                f"主导维度「{f.name}」与分群「{persona.segment}」不匹配"
            )

    # —— 高危门控：A10（自伤他伤风险）与 safety_flag 双向闭环 ——
    safety = bool(persona.detach.safety_flag if persona.detach else False)
    if "A10" in dom_codes and not safety:
        issues.append("主导维度含 A10(自伤他伤风险)，但 detach.safety_flag 未置 True")
    if safety and "A10" not in dom_codes:
        issues.append("detach.safety_flag 已触发，但主导维度缺少 A10(高危风险) 维度")
    if safety and persona.detach and persona.detach.stage not in ("应激期", "复发应对期"):
        issues.append(f"高危触发者不应处于「{persona.detach.stage}」，应为应激期或复发应对期")
    if safety and jid and jid != "J7":
        issues.append(f"高危触发者 Job 应为 J7(在高危边界内获得专业支持)，当前为「{jid}」")

    # —— 阶段与复发历史一致性 ——
    if persona.detach:
        if persona.detach.relapse_count > 0 and persona.detach.stage == "应激期":
            issues.append("有复发记录却处于应激期，阶段与复发历史不一致")
        if persona.detach.stage == "复发应对期" and persona.detach.relapse_count == 0:
            issues.append("处于复发应对期却无任何复发记录，阶段与复发历史不一致")

    # —— 分群 vs Job 弱约束（避免明显漂移） ——
    if seg == "高执行打卡型" and jid not in ("J6", "J1"):
        issues.append(f"高执行打卡型对应 J6/J1(重建秩序/数字隔离)，当前为「{jid}」")
    if seg == "等待复合型" and jid not in ("J1", "J2"):
        issues.append(f"等待复合型对应 J1/J2(停止查看/抑制联系冲动)，当前为「{jid}」")
    if seg == "理性清醒型" and jid not in ("J6",):
        issues.append(f"理性清醒型对应 J6(重建自我价值与生活秩序)，当前为「{jid}」")

    if family and ("丈夫" in family or "妻子" in family or "孩子" in family) and "前任" not in family:
        issues.append("家庭描述不应出现现配偶/子女叙事（分手戒断人群为单身状态）")

    return issues


def validate_persona_uniqueness(
    persona: Persona,
    *,
    used_names: Optional[Set[str]] = None,
) -> List[str]:
    """批次内姓名唯一 + 不得与 16 原型种子名完全相同。"""
    issues: List[str] = []
    base_name = persona.name.split("·")[0].split("（")[0].strip()
    if base_name in ARCHETYPE_SEED_NAMES:
        issues.append(f"姓名「{persona.name}」与预设原型重名，请创造全新姓名")
    if used_names and persona.name in used_names:
        issues.append(f"姓名「{persona.name}」与本批已生成结果重复")
    return issues


def validate_against_blueprint(persona: Persona, blueprint) -> List[str]:
    """LLM 槽位：结构字段不得偏离蓝图。"""
    issues: List[str] = []
    if blueprint is None:
        return issues
    bp_job = getattr(blueprint, "job_id", "") or ""
    bp_seg = getattr(blueprint, "segment", "") or ""
    bp_owner = getattr(blueprint, "job_owner", "") or ""

    if bp_job and persona.jtbd and persona.jtbd.job_id != bp_job:
        issues.append(f"job_id 应为蓝图 {bp_job}，当前为 {persona.jtbd.job_id}")
    if bp_owner and persona.jtbd and persona.jtbd.job_owner and persona.jtbd.job_owner != bp_owner:
        if {persona.jtbd.job_owner, bp_owner} == {"本人", "好友"}:
            issues.append(
                f"job_owner 应为蓝图「{bp_owner}」，当前为「{persona.jtbd.job_owner}」"
            )
    if bp_seg and persona.segment and persona.segment != bp_seg:
        issues.append(f"分群应为蓝图「{bp_seg}」，当前为「{persona.segment}」")
    return issues


def _replace_outcomes(persona: Persona, job_id: str) -> None:
    defaults = _JOB_OUTCOME_DEFAULTS.get(job_id)
    if not defaults or not persona.jtbd:
        return
    persona.jtbd.desired_outcomes = [
        DesiredOutcome(id=oid, importance=imp, satisfaction=sat)
        for oid, imp, sat in defaults
    ]


def fix_persona_coherence(persona: Persona, factors: List[Factor]) -> Persona:
    """剔除不一致主导维度；修正明显的 Job/分群漂移；高危门控闭环；步骤名归一化。"""
    from services.job_store import get_job, resolve_step_name

    family = persona.family or ""
    kept = []
    for d in persona.dominant_features:
        f = next((x for x in factors if x.id == d.code), None)
        if f and factor_fits_persona(f, persona.role, persona.subject, family, persona.segment):
            kept.append(d)
    # 高危者保证 A10 常驻
    dom_codes = [d.code for d in kept]
    if persona.detach and persona.detach.safety_flag and "A10" not in dom_codes:
        kept.append(DominantFeature(code="A10", weight=10))
        dom_codes.append("A10")
    if kept:
        persona.dominant_features = kept[:4]

    for f in factors:
        if f.id in persona.factor_weights and not factor_fits_persona(
            f, persona.role, persona.subject, family, persona.segment
        ):
            if f.id not in [d.code for d in persona.dominant_features]:
                persona.factor_weights[f.id] = 0

    # —— 高危门控修复 ——
    if persona.detach:
        det = persona.detach
        if det.safety_flag and det.stage not in ("应激期", "复发应对期"):
            det.stage = "复发应对期"
        if det.safety_flag and persona.jtbd and persona.jtbd.job_id != "J7":
            persona.jtbd.job_id = "J7"
            job = get_job("J7")
            if job:
                persona.jtbd.core_job = job.name
                persona.jtbd.job_statement = job.statement
            _replace_outcomes(persona, "J7")
        # 阶段与复发历史一致性
        if det.relapse_count > 0 and det.stage == "应激期":
            det.stage = "复发应对期"
        elif det.relapse_count == 0 and (det.stage == "复发应对期" and not det.safety_flag):
            det.stage = "戒断行动期"

    if persona.jtbd:
        persona.jtbd.current_step = resolve_step_name(
            persona.jtbd.current_step, persona.jtbd.job_id
        )

    return persona


def assert_personas_coherent(personas: List[Persona], factors: List[Factor]) -> None:
    """硬错误直接抛；用于生成出口。"""
    hard_markers = (
        "不匹配", "不应", "应为", "不一致", "蓝图",
    )
    for p in personas:
        p = fix_persona_coherence(p, factors)
        issues = validate_persona(p, factors)
        hard = [i for i in issues if any(m in i for m in hard_markers)]
        if hard:
            raise ValueError(f"心智 {p.id}/{p.name} 逻辑不成立：" + "；".join(hard))