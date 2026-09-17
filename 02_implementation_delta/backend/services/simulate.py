"""JTBD 驱动的 Campaign 仿真：以 Outcome / Force balance 判定，而非纯关键词命中。

抚心版：干预映射为分手戒断服务的功能点；高危（safety_flag）走危机转介门控。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from schemas import Factor, Outcome, Persona, SimulateResult
from services.job_store import load_outcomes, next_step_name, resolve_step_name

# 阈值：抬高推进门槛，避免「陪伴+打卡」人人满分
ADVANCE_THRESHOLD = 14
HESITATE_THRESHOLD = 5
SOFT_ADVANCE_THRESHOLD = 11
# 单独出现时偏弱、不宜只靠 soft 大面积 advance
WEAK_INTERVENTIONS = frozenset({
    "rational_list",
    "value_remind",
    "sleep_anchor",
})

INTERVENTION_MAP: Dict[str, dict] = {
    "impulse_buffer": {
        "outcomes": ["O4", "O2"],
        "forces": [("B2", "pull", 2), ("A5", "anxiety", -2)],
        "keywords": [
            "5分钟", "延迟", "缓冲", "先等一等", "冷静一下", "写下来", "倒数",
            "转移注意力", "冲动", "先别发", "别急着发", "先做别的事",
        ],
    },
    "relapse_prepare": {
        "outcomes": ["O4"],
        "forces": [("B2", "pull", 1), ("A5", "anxiety", -1)],
        "keywords": [
            "节日预案", "高危日", "纪念日", "生日预案", "预案", "提前准备",
            "破戒日", "触发日", "节日提醒",
        ],
    },
    "digital_clean": {
        "outcomes": ["O5"],
        "forces": [("B3", "pull", 2), ("A2", "anxiety", -2)],
        "keywords": [
            "屏蔽", "取关", "拉黑", "删除好友", "删除", "卸载", "数字隔离",
            "不关注", "不再看", "清空", "隐藏",
        ],
    },
    "rumination_stop": {
        "outcomes": ["O2", "O5"],
        "forces": [("B5", "pull", 2), ("A3", "anxiety", -2)],
        "keywords": [
            "替代动作", "打断", "离场", "身体唤醒", "起来走走", "做点别的",
            "打断循环", "念头来了又走", "看着它过去", "呼吸练习", "冥想",
        ],
    },
    "sleep_anchor": {
        "outcomes": ["O1", "O3"],
        "forces": [("B10", "pull", 2), ("A8", "anxiety", -1)],
        "keywords": [
            "睡前仪式", "睡眠", "入睡", "早睡", "作息", "睡个好觉", "安稳睡",
            "醒来处理", "睡前一小时", "晚上情绪",
        ],
    },
    "companion": {
        "outcomes": ["O6", "O1"],
        "forces": [("B1", "pull", 3), ("A11", "anxiety", -2)],
        "keywords": [
            "有人懂", "被理解", "倾诉", "倾听", "接住", "不说教", "抱抱",
            "陪伴", "有人陪", "陪着", "不评判", "听完", "安心", "说出来",
        ],
    },
    "community": {
        "outcomes": ["O7", "O6"],
        "forces": [("B9", "pull", 2), ("A1", "anxiety", -2)],
        "keywords": [
            "同路人", "社群", "匿名", "小组", "同类", "一起打卡", "树洞",
            "同病相怜", "大家抱团",
        ],
    },
    "checkin_progress": {
        "outcomes": ["O8"],
        "forces": [("B11", "pull", 2)],
        "keywords": [
            "打卡", "坚持天数", "天数", "进度", "里程碑", "完成记录", "签到",
            "进展", "连续坚持", "记录",
        ],
    },
    "life_rebuild": {
        "outcomes": ["O8", "O6"],
        "forces": [("B10", "pull", 2), ("A7", "anxiety", -1)],
        "keywords": [
            "作息", "早睡", "运动", "健身", "吃饭", "生活秩序", "重建生活",
            "兴趣爱好", "新生活", "回归日常", "把日子过起来", "找回自己",
        ],
    },
    "value_remind": {
        "outcomes": ["O3", "O8"],
        "forces": [("B4", "pull", 2), ("A7", "anxiety", -2)],
        "keywords": [
            "允许反复", "反复没关系", "破戒没关系", "失败不是结束", "重来",
            "慢慢来", "不苛责", "宽恕自己", "今天重新开始",
        ],
    },
    "rational_list": {
        "outcomes": ["O1"],
        "forces": [("A6", "anxiety", -1), ("B3", "pull", 1)],
        "keywords": [
            "不复合理由", "理性清单", "分手事实", "写下理由", "复合清单",
            "为什么不能复合", "把理由写下来", "清醒清单", "理清事实",
        ],
    },
    # 高危转介：只对 safety_flag / J7 生效；触发即给推进，绝不重复「想开点」式的孤立
    "crisis_referral": {
        "outcomes": ["O9"],
        "forces": [("B8", "pull", 3), ("A10", "anxiety", -3), ("B7", "pull", 2)],
        "keywords": [
            "热线", "紧急联系人", "危机干预", "自杀", "轻生", "自伤", "伤害自己",
            "安全网", "立即求助", "紧急预案", "别一个人", "心理援助", "救命",
        ],
    },
}

ENTRY_THEME_TO_JOBS = {
    "反复查看动态": ["J1"],
    "联系冲动": ["J2"],
    "夜间情绪复发": ["J3"],
    "反刍回忆循环": ["J4"],
    "孤独与被抛弃感": ["J5"],
    "自我价值与生活重建": ["J6"],
    "高危危机转介": ["J7"],
}

# 劝阻 / 反向话术信号：与其区隔「没说到点上」的无关，命中则倾向「拒绝」
NEGATIVE_SIGNAL_KEYWORDS = [
    "不用戒", "别戒了", "没必要戒", "戒什么戒", "戒断没必要",
    "复合算了", "回去找他", "回去找她", "找TA就算了", "联系TA算了",
    "想联系就联系", "想TA就发消息", "忍不住就发", "发就发了", "别忍了",
    "忍忍就过去了", "忍忍就好", "别想太多", "想开点", "至于吗",
    "矫情", "小题大做", "多大点事", "谁没分过手", "别这么脆弱",
    "玻璃心", "连这都扛不住", "别当回事",
]

# 正向语境里容易被误读成劝阻词的短语，先遮罩再匹配（长度降序替换）
_DIAGNOSTIC_SAFE_PHRASES = (
    "先理清楚要不要复合",
    "先分清是舍不得还是不甘心",
    "先搞清楚是不甘心还是放不下",
    "理清分手事实",
    "写下不复合理由",
    "别急着发消息",
    "先别急着联系",
    "别一个人硬扛",
    "想开点不是劝你戒",
)

# 较强正向干预：即使话术里夹杂负面词，仍可能被这些拉回犹豫/推进
STRONG_POSITIVE_INTERVENTIONS = frozenset({
    "impulse_buffer",
    "digital_clean",
    "companion",
    "crisis_referral",
    "checkin_progress",
    "life_rebuild",
    "rumination_stop",
})

INTERVENTION_LABELS = {
    "impulse_buffer": "冲动延迟缓冲",
    "relapse_prepare": "复发/高危日预案",
    "digital_clean": "数字隔离指导",
    "rumination_stop": "反刍打断与替代动作",
    "sleep_anchor": "睡眠与作息锚点",
    "companion": "共情陪伴/接住情绪",
    "community": "同路人社群",
    "checkin_progress": "打卡与进度反馈",
    "life_rebuild": "生活秩序重建",
    "value_remind": "允许反复的自我对话",
    "rational_list": "理性清单/分手事实",
    "crisis_referral": "高危危机转介",
}


def identify_factors(campaign: str, factors: List[Factor]) -> List[str]:
    text = campaign.lower()
    hits: List[str] = []
    for f in factors:
        if not f.enabled:
            continue
        for kw in f.keywords:
            if kw.lower() in text:
                hits.append(f.id)
                break
    return hits


def detect_interventions(
    campaign: str,
    explicit: Optional[List[str]] = None,
) -> List[str]:
    if explicit:
        return [i for i in explicit if i in INTERVENTION_MAP]
    text = campaign.lower()
    active: List[str] = []
    for key, meta in INTERVENTION_MAP.items():
        for kw in meta.get("keywords", []):
            if kw.lower() in text:
                active.append(key)
                break
    return active


def detect_negative_signals(campaign: str) -> List[str]:
    """劝阻信号检测：先遮罩正向语境短语，再做子串匹配。

    避免「先别急着联系」被「别」类短语误伤。
    """
    text = campaign or ""
    masked = text
    for phrase in sorted(_DIAGNOSTIC_SAFE_PHRASES, key=len, reverse=True):
        if phrase in masked:
            masked = masked.replace(phrase, "〔正〕")
    lowered = masked.lower()
    return [kw for kw in NEGATIVE_SIGNAL_KEYWORDS if kw.lower() in lowered]


def intervention_label(key: str) -> str:
    return INTERVENTION_LABELS.get(key, key)


def _is_high_risk(persona: Persona) -> bool:
    return bool(persona.detach.safety_flag if persona.detach else False)


def _interventions_for_persona(active: List[str], persona: Persona) -> List[str]:
    """按人设过滤不适用的干预：危机转介只对高危者 / J7 生效。"""
    out: List[str] = []
    jid = persona.jtbd.job_id if persona.jtbd else ""
    for key in active:
        if key == "crisis_referral" and not _is_high_risk(persona) and jid != "J7":
            continue
        out.append(key)
    return out


def _factor_name_map(factors: List[Factor]) -> Dict[str, str]:
    return {f.id: f.name for f in factors}


def _factor_weight_map(factors: List[Factor]) -> Dict[str, int]:
    return {f.id: f.weight for f in factors}


def _outcomes_improved_by(active: List[str]) -> set[str]:
    improved: set[str] = set()
    for key in active:
        meta = INTERVENTION_MAP.get(key, {})
        improved.update(meta.get("outcomes", []))
    return improved


def _force_deltas(active: List[str]) -> List[Tuple[str, str, int]]:
    out: List[Tuple[str, str, int]] = []
    for key in active:
        for item in INTERVENTION_MAP.get(key, {}).get("forces", []):
            if len(item) == 3:
                out.append((item[0], item[1], item[2]))
            elif len(item) == 2:
                out.append((item[0], item[1], 1))
    return out


def _required_outcome(persona: Persona):
    """关键 Outcome：缺口（importance−satisfaction）优先，Job/分群偏好仅作同分加权。

    避免「分群标签写错 → 关键缺口被硬锁成错误 Outcome」的连锁误判。
    """
    dos = persona.jtbd.desired_outcomes
    if not dos:
        return None

    preferred: List[str] = []
    jid = persona.jtbd.job_id or ""
    seg = persona.segment or ""
    drivers = " ".join(persona.drivers or [])
    dom = {d.code for d in (persona.dominant_features or [])}

    # Job / 分群偏好（比 segment 标签更可靠时用 Job）
    if jid == "J1" or "隔离" in drivers or "B3" in dom:
        preferred = ["O5", "O2", "O1"]
    elif jid == "J2" or "缓冲" in drivers or "B2" in dom:
        preferred = ["O4", "O2", "O6"]
    elif jid == "J3" or "夜里" in drivers or "睡眠" in drivers:
        preferred = ["O1", "O3", "O7"]
    elif jid == "J4" or "打断" in drivers or "B5" in dom:
        preferred = ["O2", "O3", "O5"]
    elif jid == "J5" or "陪伴" in drivers or "B9" in dom:
        preferred = ["O7", "O6", "O1"]
    elif jid == "J6" or "打卡" in drivers or "B11" in dom or seg == "高执行打卡型":
        preferred = ["O8", "O6", "O2"]
    elif jid == "J7" or "转介" in drivers or "A10" in dom:
        preferred = ["O9", "O1", "O7"]

    pref_set = set(preferred)

    def _score(d):
        gap = d.importance - d.satisfaction
        # 同分时：在偏好列表里的靠前；仍不覆盖更大缺口
        pref_bonus = 0
        if d.id in pref_set:
            pref_bonus = 1 + max(0, 3 - preferred.index(d.id))
        return (gap, pref_bonus, d.importance)

    return max(dos, key=_score)


def _outcome_short(oid: str, outcomes: List[Outcome]) -> str:
    for o in outcomes:
        if o.id == oid:
            if o.label:
                return o.label
            m = None
            if "「" in (o.name or ""):
                try:
                    m = o.name.split("「", 1)[1].split("」", 1)[0]
                except Exception:
                    m = None
            return m or o.name or oid
    return oid


def _high_importance_coverage(persona: Persona, improved_set: set[str]) -> bool:
    """高重要度 Outcome 至少半数被回应，才允许推进。"""
    high = [d for d in persona.jtbd.desired_outcomes if d.importance >= 7]
    if not high:
        return True
    hit = sum(1 for d in high if d.id in improved_set)
    need = max(1, (len(high) + 1) // 2)
    return hit >= need


def _human_reasoning(
    persona: Persona,
    decision: str,
    improved: List[str],
    unresolved: List[str],
    next_step: str,
    outcomes: List[Outcome],
) -> str:
    """市场可读的内心独白，禁止 O编码 / Force balance 等实现术语。"""
    imp = "、".join(_outcome_short(i, outcomes) for i in improved) or "还没有真正打到点上"
    unr = "、".join(_outcome_short(i, outcomes) for i in unresolved)
    step = next_step or persona.jtbd.current_step or "下一步"
    if decision == "advance":
        extra = f"还挂着：{unr}。" if unr else "关键顾虑这轮基本对上了。"
        return f"这句话里，「{imp}」对我有用。{extra}我可以先往「{step}」走一步。"
    if decision == "hesitate":
        return (
            f"有听到「{imp}」，但我最卡的「{unr or persona.jtbd.current_step}」还没说透。"
            f"暂时还在「{persona.jtbd.current_step or '纠结'}」，不会立刻下单。"
        )
    if decision == "reject":
        return f"我真正在乎的是「{unr or persona.jtbd.core_job}」，这段推广几乎没碰到，倾向先放放。"
    return f"跟我现在在忙的「{persona.jtbd.core_job or '这件事'}」关系不大。"


def _scene_phrase(persona: Persona) -> str:
    """口语场景（按戒断 Job 给出），禁止把「独居，前任已搬走」原样塞进反馈。"""
    jid = persona.jtbd.job_id if persona.jtbd else ""
    scenes = {
        "J1": "把TA从视野里拿掉这件事",
        "J2": "别让联系冲动变成行动这件事",
        "J3": "熬过夜里情绪复发这件事",
        "J4": "停掉反刍与回忆循环这件事",
        "J5": "面对孤独和被抛弃感这件事",
        "J6": "把日子重新立起来这件事",
        "J7": "在高危边缘找到专业支持这件事",
    }
    return scenes.get(jid, "戒断这件事")


def _pick_reaction(persona: Persona, decision: str, topic: str) -> str:
    """按戒断 Job / 恐惧拼口语，避免全员同一机器人句式。"""
    j = persona.jtbd
    job = j.core_job or persona.segment
    step = j.current_step or "当前这步"
    blocker = (persona.blockers or ["心里没底"])[0]
    fear = (persona.mindset.fear or "").strip()
    quote_bit = (persona.mindset.quote or "").strip().strip("「」")
    occ = persona.occupation or ""
    scene = _scene_phrase(persona)
    identity = f"我自己（{occ or '在戒断的人'}）"

    # 人格模板若是「听到…这正好推进」机器人句，一律不用
    tpl = getattr(persona.react, decision, "") or ""
    robotic = any(
        x in tpl
        for x in ("这正好推进", "想深入了解", "有点相关", "跟我现在的任务关系不大")
    )
    if tpl and ("{{topic}}" in tpl or "{topic}" in tpl) and not robotic:
        return tpl.replace("{{topic}}", topic).replace("{topic}", topic)

    fear_bit = _fear_clause(fear, blocker)
    # 引号内已带句末标点时不再在」外补「。」，避免「。」。」
    if quote_bit:
        qb = quote_bit.rstrip("。！？.!?")
        quote_tail = f"我心里那句一直是：「{qb}」。"
    else:
        quote_tail = ""
    discourage = any(x in (topic or "") for x in ("不用戒", "别戒", "复合算了", "劝阻"))

    by_decision = {
        "advance": (
            f"{identity}。就{scene}，我卡在「{step}」好久了。"
            f"你们提到的「{topic}」算对上了我在做的「{job}」——"
            f"{fear_bit}，这点要是能落地，我愿意先往下走。{quote_tail}"
        ),
        "hesitate": (
            f"{identity}。{scene}还搁在「{step}」。"
            f"「{topic}」听着沾边，但{fear_bit}，这话没解开。"
            f"对「{job}」来说，还差一口气，我得再想想。{quote_tail}"
        ),
        "reject": (
            (
                f"{identity}。你们这是在劝我「{topic}」，等于否定我正在做的「{job}」。"
                f"{fear_bit}，这种说法我听着抵触，更不会往下走。{quote_tail}"
            )
            if discourage
            else (
                f"{identity}。你们讲的「{topic}」跟我真正卡的「{step}」不是一回事。"
                f"{fear_bit}，这段几乎没答到。{quote_tail}"
            )
        ),
        "na": (
            f"{identity}。这段话跟我正在忙的「{job}」基本不沾边，"
            f"我还是卡在「{step}」，先当没听到。"
        ),
    }
    return by_decision.get(decision, by_decision["hesitate"])


def _fear_clause(fear: str, blocker: str) -> str:
    """拼恐惧短句：避免「我最怕」+「最怕…」叠成「最怕最怕」，并去掉句末标点以免「。，」。"""
    f = (fear or "").strip().strip("「」\"'")
    f = f.rstrip("。．.，,；;！!？?")
    prefixes = (
        "我最怕", "我怕", "我最担心", "我担心",
        "最怕", "很怕", "特怕", "有点怕", "怕",
        "最担心", "担心",
    )
    # 可叠多层「最怕最怕」
    changed = True
    while changed and f:
        changed = False
        for prefix in prefixes:
            if f.startswith(prefix):
                f = f[len(prefix):].lstrip("的了，, ")
                changed = True
                break
    f = f.strip().rstrip("。．.，,；;！!？?")
    if not f:
        b = (blocker or "心里没底").strip().rstrip("。．.，,；;")
        for prefix in ("最怕", "怕"):
            if b.startswith(prefix):
                b = b[len(prefix):].lstrip("的了，, ")
        return f"我顾虑的是{b or '心里没底'}"
    return f"我最怕{f}"


def decide_for(
    persona: Persona,
    campaign: str,
    factors: List[Factor],
    *,
    hit_ids: Optional[List[str]] = None,
    interventions: Optional[List[str]] = None,
    outcomes: Optional[List[Outcome]] = None,
) -> Tuple[str, str, List[str], List[str], int, List[str], List[str], str, List[str]]:
    enabled = [f for f in factors if f.enabled]
    name_map = _factor_name_map(enabled)
    weight_map = _factor_weight_map(enabled)
    outcomes = outcomes or load_outcomes()
    outcome_names = {o.id: o.name for o in outcomes}
    safety = _is_high_risk(persona)
    jid = persona.jtbd.job_id if persona.jtbd else ""

    hit_ids = hit_ids if hit_ids is not None else identify_factors(campaign, enabled)
    # 高危维度不对普通戒断人群计分（A10 只对 safety_flag 生效）
    if not safety:
        hit_ids = [h for h in hit_ids if h != "A10"]
    active_global = detect_interventions(campaign, interventions)
    active = _interventions_for_persona(active_global, persona)
    negative_hits = detect_negative_signals(campaign)
    has_strong_positive = any(k in STRONG_POSITIVE_INTERVENTIONS for k in active)
    # 劝阻话术主导时，清掉可能误触发的「改善」，避免「复合算了」又被算成推进
    if negative_hits and not has_strong_positive:
        active = []

    improved_set = _outcomes_improved_by(active)
    force_deltas = _force_deltas(active)
    high_risk_discouraged = False

    improved: List[str] = []
    unresolved: List[str] = []
    score = 0.0

    for do in persona.jtbd.desired_outcomes:
        if do.id in improved_set:
            strength = 1 + sum(
                1 for k in active if do.id in INTERVENTION_MAP.get(k, {}).get("outcomes", [])
            )
            score += do.importance * strength * 0.7
            improved.append(do.id)
        else:
            unresolved.append(do.id)

    forces = persona.jtbd.forces
    activated_force_ids = {fid for fid, _, _ in force_deltas} | set(hit_ids)

    for fid in forces.push:
        if fid in activated_force_ids:
            score += weight_map.get(fid, persona.factor_weights.get(fid, 3))
    for fid in forces.pull:
        if fid in activated_force_ids:
            score += weight_map.get(fid, persona.factor_weights.get(fid, 3))

    # 高危者：被接住的焦虑降权，避免「售后没提」压死危机转介
    life_critical = safety and (
        "A10" in activated_force_ids or "O9" in improved
    )
    anxiety_scale = 0.25 if life_critical else 0.5
    # 最关键 Outcome 已被功能话术改善时，勿被无关 anxiety 轻易压死
    required = _required_outcome(persona)
    if required and required.id in improved_set:
        anxiety_scale = min(anxiety_scale, 0.25)
        score += 2.0  # 关键缺口被填的确认加成（控制幅度，避免弱词刷分）

    for fid in forces.anxiety:
        addressed = any(
            f == fid and force == "anxiety" and delta < 0
            for f, force, delta in force_deltas
        )
        if not addressed:
            score -= weight_map.get(fid, persona.factor_weights.get(fid, 4)) * anxiety_scale
        else:
            score += 2

    for fid in forces.habit_or_alternative:
        raised = any(
            f == fid and force == "habit_or_alternative" and delta > 0
            for f, force, delta in force_deltas
        )
        if raised:
            score += 1
        else:
            score -= weight_map.get(fid, 3) * 0.35

    # —— 高危门控：危机转介对高危者优先推进，绝不因普通话术/劝阻加深孤立 ——
    if safety:
        if "crisis_referral" in active:
            decision = "advance"
            next_step = next_step_name(persona.jtbd.current_step, persona.jtbd.job_id)
            improved = [do.id for do in persona.jtbd.desired_outcomes if do.id in improved_set]
            if not improved:
                improved = ["O9"]
            unresolved = [do.id for do in persona.jtbd.desired_outcomes if do.id not in improved]
            score = max(score, ADVANCE_THRESHOLD + 2)
            topic = "危机转介与专业支持"
            reaction = _pick_reaction(persona, decision, topic)
            willingness = 8 + min(2, len(improved))
            return (
                decision, reaction, hit_ids, [h for h in hit_ids if h in [d.code for d in persona.dominant_features]],
                min(willingness, 10), improved, unresolved, next_step, active,
            )
        if negative_hits and not has_strong_positive:
            # 高危者遭遇「别想太多」：不当拒绝处理，维持犹豫（避免被推开），也避免无关
            negative_hits = []
            high_risk_discouraged = True

    # 话术触发的干预对该人设全部不适用（如普通人听到危机转介话术）→ 无关
    interventions_irrelevant = bool(active_global) and not active

    if negative_hits and not has_strong_positive:
        # 劝阻 / 反向宣传 → 拒绝（不是无关）
        decision = "reject"
        next_step = persona.jtbd.current_step
        topic = "别戒了、复合算了这类说法"
        # 负面话术下不记「已改善」
        improved = []
        unresolved = [do.id for do in persona.jtbd.desired_outcomes]
        score = -5
    elif interventions_irrelevant or (not active and not hit_ids):
        # 完全跑题，或干预与人设互斥 → 无关；高危者被劝阻而又无正向命中 → 犹豫不拒绝
        if high_risk_discouraged:
            decision = "hesitate"
        else:
            decision = "na"
        next_step = persona.jtbd.current_step
        topic = "别想太多、想开点这类说法" if high_risk_discouraged else "这个活动"
        improved = []
        unresolved = [do.id for do in persona.jtbd.desired_outcomes]
    else:
        required_addressed = True if not required else required.id in improved
        coverage_ok = _high_importance_coverage(persona, improved_set)

        # 理性清单话术只打 O1：对卡在「要不要复合/为什么不能复合」的人，单点命中关键缺口即可算覆盖
        if (
            "rational_list" in active
            and required
            and required.id == "O1"
            and required.id in improved_set
        ):
            coverage_ok = True
            score += 3.0

        anxiety_eased = any(
            f == fid and force == "anxiety" and delta < 0
            for fid in forces.anxiety
            for f, force, delta in force_deltas
        )
        pull_hit = any(fid in activated_force_ids for fid in forces.pull)
        push_hit = any(fid in activated_force_ids for fid in forces.push)
        only_weak = bool(active) and set(active).issubset(WEAK_INTERVENTIONS)

        # 推进必须：关键缺口被回应 + 高重要度覆盖过半 + 分数够；弱干预组合不能单独撑推进
        hard_advance = (
            score >= ADVANCE_THRESHOLD
            and required_addressed
            and coverage_ok
            and not only_weak
        )
        soft_advance = (
            score >= SOFT_ADVANCE_THRESHOLD
            and required_addressed
            and coverage_ok
            and (push_hit or pull_hit or anxiety_eased or len(improved) >= 2)
            and not only_weak
        )
        # 生命危急特例：高危被接住仍可 soft
        if life_critical and required_addressed and score >= SOFT_ADVANCE_THRESHOLD:
            soft_advance = True

        # 夹杂劝阻词时，即使有弱命中也不给推进
        if negative_hits:
            hard_advance = False
            soft_advance = False

        if hard_advance or soft_advance:
            decision = "advance"
            next_step = next_step_name(persona.jtbd.current_step, persona.jtbd.job_id)
        elif score >= HESITATE_THRESHOLD or (active or hit_ids):
            # 有命中但没过推进门 → 犹豫（而不是轻易无关）
            decision = "hesitate" if (score >= HESITATE_THRESHOLD or required_addressed or improved) else "reject"
            if score < HESITATE_THRESHOLD and not improved:
                decision = "reject"
            if negative_hits:
                decision = "reject"
            next_step = persona.jtbd.current_step
        else:
            decision = "reject"
            next_step = persona.jtbd.current_step

        # 正向「理性清单」话术：遮罩后无真实劝阻时，不得因未覆盖其 Outcome 而 reject
        if (
            "rational_list" in active
            and not negative_hits
            and decision == "reject"
        ):
            decision = "hesitate"
            next_step = persona.jtbd.current_step

        # 「共情陪伴/接住」价值主张：有 Outcome 命中至少犹豫；零重叠 → 无关，勿 reject
        if "companion" in active and not negative_hits and decision == "reject":
            decision = "hesitate" if improved else "na"
            next_step = persona.jtbd.current_step

        if improved:
            topic = "、".join(_outcome_short(i, outcomes) for i in improved[:2])
        elif hit_ids:
            topic = "、".join(name_map.get(h, h) for h in hit_ids[:2])
        else:
            topic = "、".join(intervention_label(a) for a in active[:2]) if active else "这个活动"

    reaction = _pick_reaction(persona, decision, topic)

    dom_codes = [d.code for d in persona.dominant_features]
    hit_dom = [h for h in hit_ids if h in dom_codes]

    # 意愿分：与决策绑定，并对「高重要度未解决」扣分，禁止核心顾虑未解却 10 分
    unresolved_high = [
        d for d in persona.jtbd.desired_outcomes
        if d.id in unresolved and d.importance >= 7
    ]
    if decision == "advance":
        willingness = 6 + min(3, int(score // 6))
        willingness -= len(unresolved_high)
        willingness = max(6, min(9, willingness))  # 推进最高 9，满分留给几乎无未解
        if not unresolved:
            willingness = min(10, willingness + 1)
    elif decision == "hesitate":
        willingness = 4 + min(2, int(score // 6))
        willingness -= len(unresolved_high)
        willingness = max(3, min(6, willingness))
    elif decision == "na":
        willingness = max(1, min(4, 2 + int(score // 8)))
    else:
        willingness = max(1, min(3, 2 - len(unresolved_high) // 2))

    # 最关键 Outcome 未解 → 绝不能显示高意愿推进感
    if required and required.id in unresolved:
        willingness = min(willingness, 5)
        if decision == "advance":
            decision = "hesitate"
            reaction = _pick_reaction(persona, decision, topic)
            next_step = persona.jtbd.current_step

    return (
        decision,
        reaction,
        hit_ids,
        hit_dom,
        willingness,
        improved,
        unresolved,
        next_step,
        active,
    )


def simulate_campaign(
    campaign: str,
    personas: List[Persona],
    factors: List[Factor],
    persona_ids: List[str] | None = None,
    interventions: Optional[List[str]] = None,
) -> Tuple[List[SimulateResult], Dict[str, int], List[str], List[str]]:
    enabled = [f for f in factors if f.enabled]
    campaign_hits = identify_factors(campaign, enabled)
    hit_names = [f.name for f in enabled if f.id in campaign_hits]
    active_global = detect_interventions(campaign, interventions)
    outcomes = load_outcomes()

    targets = personas
    if persona_ids:
        id_set = set(persona_ids)
        targets = [p for p in personas if p.id in id_set]

    results: List[SimulateResult] = []
    summary = {"advance": 0, "hesitate": 0, "na": 0, "reject": 0}

    for persona in targets:
        (
            decision,
            reaction,
            hits,
            hit_dom,
            willingness,
            improved,
            unresolved,
            next_step,
            active,
        ) = decide_for(
            persona,
            campaign,
            enabled,
            hit_ids=campaign_hits,
            interventions=interventions,
            outcomes=outcomes,
        )
        summary[decision] = summary.get(decision, 0) + 1
        results.append(
            SimulateResult(
                persona_id=persona.id,
                persona_name=persona.name,
                decision=decision,
                reaction=reaction,
                hit_factors=[f.name for f in enabled if f.id in hits],
                hit_dominant=[f.name for f in enabled if f.id in hit_dom],
                willingness=willingness,
                mode="rule",
                outcome_improved=improved,
                unresolved_outcomes=unresolved,
                next_step=next_step,
                interventions=active,
                reasoning=_human_reasoning(
                    persona, decision, improved, unresolved, next_step, outcomes
                ),
            )
        )

    # 对外返回中文干预名，避免 impulse_buffer 等内部键
    active_labels = [intervention_label(k) for k in active_global]
    return results, summary, hit_names, active_labels