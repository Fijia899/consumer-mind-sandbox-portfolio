from __future__ import annotations

import random
from typing import Dict, List, Optional

from schemas import (
    DesiredOutcome,
    DetachInfo,
    DominantFeature,
    Factor,
    ForceMap,
    JTBDProfile,
    Mindset,
    Persona,
    ReactTemplates,
)
from services.job_store import get_job, load_sub_jobs
from services.persona_archetypes import PERSONA_ARCHETYPES, pick_archetypes
from services.persona_coherence import factor_fits_persona
from services.simulate import ENTRY_THEME_TO_JOBS

# 16 个抚心原型主种子：角色一律「本人」，人口学即分手戒断人群（20-35 岁为主）。
PERSONA_SEEDS: List[Dict] = [
    {
        "name": "小鹿", "emoji": "👩", "gender": "女", "age_range": (22, 26),
        "city": "二线城市", "occupation": "插画师", "income": "个人月入约8千",
        "family": "独居，前任已搬走",
    },
    {
        "name": "阿澄", "emoji": "👩", "gender": "女", "age_range": (25, 29),
        "city": "一线城市", "occupation": "新媒体编辑", "income": "个人月入约1.3万",
        "family": "独居，深夜经常失眠",
    },
    {
        "name": "大齐", "emoji": "👨", "gender": "男", "age_range": (24, 28),
        "city": "一线城市", "occupation": "程序员", "income": "个人月入约1.8万",
        "family": "合租，下班后一个人待着",
    },
    {
        "name": "小满", "emoji": "👩", "gender": "女", "age_range": (23, 27),
        "city": "二线城市", "occupation": "市场专员", "income": "个人月入约9千",
        "family": "独居，节日最难点",
    },
    {
        "name": "也子", "emoji": "👩", "gender": "女", "age_range": (21, 25),
        "city": "一线城市", "occupation": "研究生在读", "income": "学生补贴约2千",
        "family": "合租，室友在谈恋爱",
    },
    {
        "name": "果果", "emoji": "👩", "gender": "女", "age_range": (22, 26),
        "city": "二线城市", "occupation": "自由插画师", "income": "个人月入约7千",
        "family": "独居，备忘录里留着没发出去的话",
    },
    {
        "name": "木子", "emoji": "👨", "gender": "男", "age_range": (26, 30),
        "city": "一线城市", "occupation": "产品经理", "income": "个人月入约2万",
        "family": "独居，生活已基本恢复秩序",
    },
    {
        "name": "叙白", "emoji": "👨", "gender": "男", "age_range": (27, 31),
        "city": "一线城市", "occupation": "建筑师", "income": "个人月入约1.9万",
        "family": "独居，业余在学陶艺",
    },
    {
        "name": "双双", "emoji": "👩", "gender": "女", "age_range": (24, 28),
        "city": "二线城市", "occupation": "会计", "income": "个人月入约8千",
        "family": "独居，被分手后自我怀疑",
    },
    {
        "name": "楠楠", "emoji": "👩", "gender": "女", "age_range": (23, 27),
        "city": "一线城市", "occupation": "运营专员", "income": "个人月入约1万",
        "family": "合租，破戒后容易苛责自己",
    },
    {
        "name": "纪子", "emoji": "👩", "gender": "女", "age_range": (21, 24),
        "city": "二线城市", "occupation": "应届毕业生", "income": "待业，靠存款过活",
        "family": "独居，被抛弃感很强",
    },
    {
        "name": "夏夏", "emoji": "👩", "gender": "女", "age_range": (22, 26),
        "city": "一线城市", "occupation": "自由职业", "income": "个人月入约1万",
        "family": "独居，周末最需要有人陪",
    },
    {
        "name": "卷卷", "emoji": "👩", "gender": "女", "age_range": (24, 28),
        "city": "一线城市", "occupation": "数据分析师", "income": "个人月入约1.6万",
        "family": "独居，睡前反复回放聊天记录",
    },
    {
        "name": "阿默", "emoji": "👨", "gender": "男", "age_range": (25, 29),
        "city": "一线城市", "occupation": "后端工程师", "income": "个人月入约2.2万",
        "family": "独居，连续失眠与崩溃",
    },
    {
        "name": "一舟", "emoji": "👨", "gender": "男", "age_range": (26, 30),
        "city": "二线城市", "occupation": "健身教练", "income": "个人月入约1.2万",
        "family": "独居，分手第30天开始打卡",
    },
    {
        "name": "拾一", "emoji": "👩", "gender": "女", "age_range": (24, 28),
        "city": "一线城市", "occupation": "文案编辑", "income": "个人月入约1.1万",
        "family": "独居，删了又加过几次",
    },
]

# 复用原型时的姓名池（年轻人向；避免与主种子重名）。
EXTRA_SEEDS: List[Dict] = [
    {"name": "小诗", "emoji": "👩", "gender": "女", "age_range": (23, 27), "city": "二线城市", "occupation": "设计师", "income": "个人月入约9千", "family": "独居"},
    {"name": "阿禾", "emoji": "👩", "gender": "女", "age_range": (22, 26), "city": "一线城市", "occupation": "主播助理", "income": "个人月入约8千", "family": "合租"},
    {"name": "桃子", "emoji": "👧", "gender": "女", "age_range": (21, 25), "city": "三线城市", "occupation": "幼师", "income": "个人月入约6千", "family": "与家人同住"},
    {"name": "木木", "emoji": "👩", "gender": "女", "age_range": (24, 28), "city": "一线城市", "occupation": "HR", "income": "个人月入约1.1万", "family": "独居"},
    {"name": "小晚", "emoji": "👩", "gender": "女", "age_range": (23, 27), "city": "二线城市", "occupation": "花艺师", "income": "个人月入约7千", "family": "独居，养了一只猫"},
    {"name": "阿梨", "emoji": "👩", "gender": "女", "age_range": (22, 26), "city": "一线城市", "occupation": "医学生", "income": "个人月入约5千", "family": "独居"},
    {"name": "星儿", "emoji": "👩", "gender": "女", "age_range": (21, 25), "city": "三线城市", "occupation": "奶茶店副店长", "income": "个人月入约5.5千", "family": "与家人同住"},
    {"name": "松松", "emoji": "👩", "gender": "女", "age_range": (23, 27), "city": "一线城市", "occupation": "游戏策划", "income": "个人月入约1.5万", "family": "独居"},
    {"name": "布丁", "emoji": "👩", "gender": "女", "age_range": (22, 26), "city": "二线城市", "occupation": "烘焙师", "income": "个人月入约6.5千", "family": "合租"},
    {"name": "汤圆", "emoji": "👧", "gender": "女", "age_range": (20, 24), "city": "三线城市", "occupation": "大学生(大四)", "income": "生活费用家里给", "family": "宿舍"},
    {"name": "阿泽", "emoji": "👨", "gender": "男", "age_range": (24, 28), "city": "一线城市", "occupation": "运维工程师", "income": "个人月入约1.6万", "family": "独居"},
    {"name": "小野", "emoji": "👨", "gender": "男", "age_range": (21, 25), "city": "二线城市", "occupation": "乐队贝斯手", "income": "个人月入约6千", "family": "合租"},
    {"name": "大宇", "emoji": "👨", "gender": "男", "age_range": (25, 29), "city": "一线城市", "occupation": "数据分析师", "income": "个人月入约1.7万", "family": "独居"},
    {"name": "阿凯", "emoji": "👨", "gender": "男", "age_range": (22, 26), "city": "三线城市", "occupation": "汽修技师", "income": "个人月入约7千", "family": "与家人同住"},
    {"name": "小舟", "emoji": "👨", "gender": "男", "age_range": (23, 27), "city": "一线城市", "occupation": "电商运营", "income": "个人月入约1.2万", "family": "合租"},
    {"name": "阿树", "emoji": "👨", "gender": "男", "age_range": (26, 30), "city": "二线城市", "occupation": "中学教师", "income": "个人月入约9千", "family": "独居"},
    {"name": "江离", "emoji": "👨", "gender": "男", "age_range": (24, 28), "city": "一线城市", "occupation": "策展助理", "income": "个人月入约1万", "family": "独居"},
    {"name": "小北", "emoji": "👨", "gender": "男", "age_range": (22, 26), "city": "二线城市", "occupation": "健身房前台", "income": "个人月入约6千", "family": "合租"},
]

SEED_BY_NAME: Dict[str, Dict] = {s["name"]: s for s in PERSONA_SEEDS}


def _persona_id(index: int) -> str:
    return f"P{index:02d}" if index < 100 else f"P{index:03d}"


def _age_mid(seed: Dict) -> int:
    lo, hi = seed.get("age_range", (24, 30))
    return (lo + hi) // 2


def _seed_age_distance(a: Dict, b: Dict) -> int:
    return abs(_age_mid(a) - _age_mid(b))


def _seed_fit_score(arch: Dict, seed: Dict) -> int:
    """种子与原型契合度：抚心人群年轻化，年龄契合 + 同名种子偏好。"""
    age = _age_mid(seed)
    score = 0
    if 20 <= age <= 36:
        score += 20
    elif age >= 45:
        score -= 50
    elif age <= 18:
        score -= 30
    if "独居" in (seed.get("family") or "") or "合租" in (seed.get("family") or "") or "宿舍" in (seed.get("family") or ""):
        score += 5
    preferred = SEED_BY_NAME.get(arch.get("seed_name", ""))
    if preferred:
        score -= _seed_age_distance(seed, preferred) // 3
    return score


def _unique_clone_name(base_name: str, used_names: set, gender: str = "女") -> str:
    """姓名耗尽时换全新人名，避免「小鹿（乙）」这种一眼假的复制感。"""
    pool = _FRESH_NAMES.get(gender) or _FRESH_NAMES["女"]
    for cand in pool:
        if cand not in used_names:
            return cand
    # 仍冲突时用「阿X / 小X / XX」风格
    for style in ("小", "阿"):
        for mark in ("禾", "屿", "澈", "眠", "栖", "岸", "野"):
            cand = f"{style}{mark}"
            if cand not in used_names:
                return cand
    n = 2
    while f"{base_name}·{n}" in used_names:
        n += 1
    return f"{base_name}·{n}"


# 克隆时的全新人名池（按性别），优先于此而非「（乙）」后缀
_FRESH_NAMES: Dict[str, List[str]] = {
    "女": [
        "小诗", "阿禾", "桃子", "木木", "小晚", "阿梨", "星儿", "松松",
        "布丁", "汤圆", "小樱", "阿枝", "糖糖", "小意", "阿眠", "川川",
    ],
    "男": [
        "阿泽", "小野", "大宇", "阿凯", "小舟", "阿树", "江离", "小北",
        "阿澈", "大倪", "小楼", "阿屿", "一白", "小川", "阿佑", "竹里",
    ],
}


def _pick_unique_seed(
    preferred_name: str,
    used_names: set,
    *,
    gender_hint: str = "",
    arch: Optional[Dict] = None,
) -> Dict:
    """同次生成内姓名不重复；永不跨性别；优先角色匹配的备选。"""
    primary = SEED_BY_NAME.get(preferred_name)
    if primary and preferred_name not in used_names:
        used_names.add(preferred_name)
        return dict(primary)

    gender = gender_hint or (primary or {}).get("gender") or "男"

    def _available(pool: List[Dict]) -> List[Dict]:
        return [s for s in pool if s["gender"] == gender and s["name"] not in used_names]

    pool = _available(EXTRA_SEEDS)
    if not pool:
        pool = _available(PERSONA_SEEDS)
    if not pool:
        # 同性别耗尽：克隆人口学，只改名字
        base = primary or next(
            (s for s in PERSONA_SEEDS if s["gender"] == gender), PERSONA_SEEDS[0]
        )
        seed = dict(base)
        seed["name"] = _unique_clone_name(base["name"], used_names, gender=gender)
        used_names.add(seed["name"])
        return seed

    if arch:
        scored = sorted(
            pool,
            key=lambda s: (-_seed_fit_score(arch, s), _seed_age_distance(s, primary or s)),
        )
        good = [s for s in scored if _seed_fit_score(arch, s) >= 0]
        seed = dict(good[0]) if good else dict(scored[0])
    else:
        if primary:
            pool = sorted(pool, key=lambda s: _seed_age_distance(s, primary))
        seed = dict(pool[0])

    used_names.add(seed["name"])
    return seed


def _align_role_subject_family(arch: Dict, seed: Dict) -> tuple[str, str, str]:
    """抚心角色系统简化：用户一律为「本人」，subject 亦为本人。"""
    return "本人", "本人", seed.get("family", "")


# 同原型复用时的措辞变体（至少动机/恐惧/quote 不同，避免市场部一眼看出「复制粘贴」）
STORY_VARIANTS: Dict[str, List[Dict]] = {
    "night_vulnerable_young": [
        {
            "core_motive": "晚上一个人在出租屋，情绪说来就来，屏幕亮着不知道能找谁。",
            "fear": "怕这种夜晚没有尽头，怕自己越哭越像矫情。",
            "quote": "白天都撑得住，就当晚上会偶尔破防吧。",
            "decision_logic": "夜里要的不是讲道理，是有人能接住我。",
            "blockers": ["睡前手机越刷越清醒", "不想打扰朋友"],
            "drivers": ["夜里有人接住", "睡眠仪式", "被理解不说教"],
        },
        {
            "core_motive": "睡前明明好好的，一躺下就开始想TA，翻个身眼泪就下来了。",
            "fear": "怕第二天顶着肿眼睛上班被问。",
            "quote": "我不是放不下，是夜晚放大了一切。",
            "decision_logic": "先有睡着的办法，才有走出来的力气。",
            "blockers": ["早醒即崩溃", "周末晚上尤其难"],
            "drivers": ["睡前仪式", "即时陪伴", "不被审判"],
        },
    ],
    "night_vulnerable_severe": [
        {
            "core_motive": "夜里冲动最强，短信都打好几遍了，就差手指按下去。",
            "fear": "怕某一晚真的发出去，把这段时间的坚持全作废。",
            "quote": "我知道不该联系，可手会自己动。",
            "decision_logic": "需要一道物理缓冲，把冲动和行动隔开。",
            "blockers": ["深夜独自意志力最弱", "喝多就想打电话"],
            "drivers": ["冲动延迟", "临门一脚前的提醒", "被允许反复"],
        },
        {
            "core_motive": "白天信誓旦旦说放下了，晚上一点信号就能让我全线崩溃。",
            "fear": "怕自己反复无常的样子被朋友当成笑话。",
            "quote": "反反复复不可耻，可耻的是没有缓冲就硬扛。",
            "decision_logic": "得在失控前有人喊停我。",
            "blockers": ["触发物太密集", "自责循环"],
            "drivers": ["冷静缓冲", "有人拉住"],
        },
    ],
    "repeat_contact_impulsive": [
        {
            "core_motive": "消息删了写、写了删，最后晚会还是点开对话框发呆。",
            "fear": "怕自己永远戒不掉这个毛病。",
            "quote": "我不是想复合，是手指有肌肉记忆。",
            "decision_logic": "把发送键藏起来，给冲动搭个台阶下。",
            "blockers": ["手比脑子快", "酒后更冲动"],
            "drivers": ["延迟缓冲", "替代动作", "被拉住"],
        },
        {
            "core_motive": "周末晚上最容易手滑，社交软件点开就停不下来。",
            "fear": "怕某次真的冲动到联系，后悔一整年。",
            "quote": "写下来比发出去强，至少明天不会后悔。",
            "decision_logic": "冲动上头时先做一件无关的事。",
            "blockers": ["无意识刷手机", "深夜空档"],
            "drivers": ["5分钟规则", "可执行替代动作"],
        },
    ],
    "repeat_contact_occasion": [
        {
            "core_motive": "生日提前一周就开始焦虑那句祝福该不该发。",
            "fear": "怕一条「生日快乐」又把戒断清零。",
            "quote": "祝福是真的，可它总是带我滑回老路。",
            "decision_logic": "节日要有预案：那一刻做什么、不做什么。",
            "blockers": ["纪念日记忆自动唤醒", "共同朋友总提起"],
            "drivers": ["高危日预案", "提前备好的替代动作"],
        },
        {
            "core_motive": "系统提醒「你们的纪念日」比我自己记得还准，一下就绷不住了。",
            "fear": "怕这种日子一年比一年多。",
            "quote": "日历会骗人，记忆不会。",
            "decision_logic": "提前把高危日设置成「预案日」而不是「崩溃日」。",
            "blockers": ["节日社交氛围", "凌晨零点最难熬"],
            "drivers": ["提前安排", "陪伴兜底"],
        },
    ],
    "waiting_reunion_secret": [
        {
            "core_motive": "设了免打扰，还是每天十几次点进TA主页，再假装只是路过。",
            "fear": "怕TA官宣新恋情，又怕彻底没有了希望。",
            "quote": "我知道该往前走了，可总想再等等看。",
            "decision_logic": "最需要有人帮我把那条线剪断。",
            "blockers": ["视奸成日常", "潜意识还在等契机"],
            "drivers": ["数字隔离", "被点醒不复合理由"],
        },
        {
            "core_motive": "闺蜜问起来一口咬定「早删干净了」，只有我知道没有。",
            "fear": "怕被发现还在偷偷看，更怕越看越出不来。",
            "quote": "嘴上说放下了，手指还在说谎。",
            "decision_logic": "需要一个不judge的人陪我把真相捋清楚。",
            "blockers": ["说一套做一套", "习惯了睡前刷一眼"],
            "drivers": ["事实清单", "温柔的点破"],
        },
    ],
    "waiting_reunion_stubborn": [
        {
            "core_motive": "「再见面一次就放下」——这句话已经拖了我一个月。",
            "fear": "怕错过唯一可能，又怕见面后更放不下。",
            "quote": "不是说放下就放下，我只是想体面地道别。",
            "decision_logic": "需要有人告诉我最后一面救不了我，还得写清楚理由。",
            "blockers": ["把未来幻想留在备忘录", "不愿承认关系真的结束"],
            "drivers": ["事实回顾", "被允许不舍"],
        },
        {
            "core_motive": "备忘录里还存着没发出去的复合草稿，写了又改、改了又写。",
            "fear": "怕再不行动就真的错过了。",
            "quote": "我等的不是TA，是那个还在等的自己。",
            "decision_logic": "想有人帮我分清「不甘心」和「还爱着」。",
            "blockers": ["总想见最后一面", "朋友劝不动"],
            "drivers": ["理性清单", "缓冲机制"],
        },
    ],
    "rational_clarity_self": [
        {
            "core_motive": "理智到同事都觉得我早就好了，只有我知道周五晚上会破防。",
            "fear": "怕自己坚持得不够久，前功尽弃。",
            "quote": "我不需要劝，我需要方法和看得见的进步。",
            "decision_logic": "用计划和复盘把自己钉住，别让情绪反复打断。",
            "blockers": ["偶尔闪回自我怀疑", "生活还没完全立起来"],
            "drivers": ["生活秩序", "进展可视", "自我价值重建"],
        },
        {
            "core_motive": "道理我都懂，就是「懂」和「做到」之间差着每天的执行。",
            "fear": "怕哪天突然绷不住，把理智人设也摔了。",
            "quote": "理性是我的盔甲，但盔甲里也需要被看见。",
            "decision_logic": "先把微小习惯固定下来，再谈大目标。",
            "blockers": ["只有自己扛", "一点小挫败就动摇"],
            "drivers": ["习惯打卡", "里程碑反馈"],
        },
    ],
    "rational_clarity_rebuilder": [
        {
            "core_motive": "拼图理论——缺的那块不是TA，是「我」。",
            "fear": "怕哪一天被一条消息打回原形。",
            "quote": "我不是在戒断，我是在重建。",
            "decision_logic": "用日程、里程碑和复盘把自己稳稳放进新生活。",
            "blockers": ["偶尔被共同记忆绊一下", "担心复发的自己"],
            "drivers": ["日程秩序", "自我认同重建", "里程碑反馈"],
        },
        {
            "core_motive": "已经能平静聊起前任，但偶尔睡着前还会想「如果」。",
            "fear": "怕重建只是表象，底层还在痛。",
            "quote": "能聊起你不代表走完，走完是我不再被带走。",
            "decision_logic": "继续把精力放在身份重建上，而不是回头论证。",
            "blockers": ["深夜偶尔波动", "对新关系谨慎"],
            "drivers": ["长期规划", "掌控感训练"],
        },
    ],
    "self_esteem_damaged_doubt": [
        {
            "core_motive": "看着镜子觉得陌生，好像分手把我也一起带走了。",
            "fear": "怕再谈一段恋爱也是被丢下。",
            "quote": "不是TA不值得，是我开始怀疑自己值不值得。",
            "decision_logic": "需要先重建一点点「我很好」的证据。",
            "blockers": ["觉得再也没人会爱我", "不敢面对自己"],
            "drivers": ["被肯定的小事", "重建兴趣"],
        },
        {
            "core_motive": "被夸好看，第一反应是「客套话吧」。",
            "fear": "怕这份自我怀疑已经长进骨头里。",
            "quote": "我想找回那个会相信自己的人。",
            "decision_logic": "先收集「我值得」的小证据，再多都不嫌少。",
            "blockers": ["反复复盘是不是我的错", "习惯性贬低自己"],
            "drivers": ["被看见", "一点点成就感"],
        },
    ],
    "self_esteem_damaged_fear": [
        {
            "core_motive": "昨天没忍住看了TA的资料，一整天都在骂自己没出息。",
            "fear": "怕破戒一次就永远戒不掉。",
            "quote": "一次破戒不代表彻底失败，对吗？我需要有人这么说。",
            "decision_logic": "最需要有人告诉我：反复不等于失败。",
            "blockers": ["破戒即自我惩罚", "深夜反复否定自己"],
            "drivers": ["允许反复", "被理解的感觉"],
        },
        {
            "core_motive": "想把进度条清零重来，觉得自己根本不配变好。",
            "fear": "怕朋友失望，更怕自己失望。",
            "quote": "我不缺努力，缺的是赦免自己失败的许可。",
            "decision_logic": "先把「允许反复」练熟，再谈坚持。",
            "blockers": ["完美主义作祟", "忍不住比较"],
            "drivers": ["不完美也可以", "陪伴托底"],
        },
    ],
    "lonely_dependent_abandoned": [
        {
            "core_motive": "手机一整天没有新消息就心慌，好像被全世界丢下了。",
            "fear": "怕从此孤独终老，怕再也没人真正懂我。",
            "quote": "我不缺道理，缺的是有人在我哭的时候坐在旁边。",
            "decision_logic": "得先有人陪着，才有力气独立。",
            "blockers": ["被抛弃感强", "怕朋友觉得我矫情"],
            "drivers": ["不评判的陪伴", "被看见"],
        },
        {
            "core_motive": "深夜给所有朋友发了「在吗」又撤回，怕打扰又怕没人理。",
            "fear": "怕自己变成粘人精被人躲开。",
            "quote": "我需要的不是热闹，是确定有人还在。",
            "decision_logic": "低负担的陪伴比高浓度的安慰更解渴。",
            "blockers": ["不敢主动联系", "一个人呆着就发酵"],
            "drivers": ["低门槛联结", "同路人社群"],
        },
    ],
    "lonely_dependent_empty": [
        {
            "core_motive": "周末双人份的电影票根还夹在书里，一个人躺着到天黑。",
            "fear": "怕被朋友问「你俩怎么了」，怕解释不清。",
            "quote": "我不想解释我的伤，我只想有人陪我慢慢走出来。",
            "decision_logic": "想找一群不用解释、天然懂我处境的人。",
            "blockers": ["社交圈突然空了", "不敢联系老朋友"],
            "drivers": ["同路人社群", "不追问的关心"],
        },
        {
            "core_motive": "点外卖都习惯点两份，收件后对着另一份发呆。",
            "fear": "怕这些空出来的位置永远填不上。",
            "quote": "先把一个人的日子过出声音来。",
            "decision_logic": "需要低成本、不问隐私的陪伴入口。",
            "blockers": ["周末无处可去", "深夜情绪容易上头"],
            "drivers": ["低门槛社交", "陪伴型活动"],
        },
    ],
    "trauma_recovery_ruminate": [
        {
            "core_motive": "播放列表还是那几首歌，一首就能把我送回那个晚上。",
            "fear": "怕越想越陷进去，怕这辈子走不出这个循环。",
            "quote": "道理我都懂，问题是脑子它不听话，一直回放。",
            "decision_logic": "需要能打断反刍的动作和让念头过去的练习。",
            "blockers": ["触歌伤情", "睡前自动回放"],
            "drivers": ["打断反刍的动作", "回到当下"],
        },
        {
            "core_motive": "睡前自动开始复盘，像放幻灯片一样一帧一帧过。",
            "fear": "怕被回忆圈养，再也长不出新的日子。",
            "quote": "我不是放不下TA，是停不下来复盘。",
            "decision_logic": "把「想清楚」换成「先走出去」。",
            "blockers": ["聊天记录翻上百遍", "细节越想越细"],
            "drivers": ["念头流走练习", "身体唤醒动作"],
        },
    ],
    "trauma_recovery_highrisk": [
        {
            "core_motive": "连续失眠到快扛不住，夜里有过「就这样算了」的念头，不敢告诉任何人。",
            "fear": "怕说出来被当笑话，更怕自己真的失控。",
            "quote": "我怕的不是分手，是怕自己撑不到天亮。",
            "decision_logic": "需要绝对安全的通道被专业的人接住。",
            "blockers": ["不敢跟家人说", "独自硬扛"],
            "drivers": ["有人发现我", "专业转介", "安全的紧急出口"],
        },
        {
            "core_motive": "白天强撑正常，夜里翻来覆去，觉得「消失」会不会反而被记住。",
            "fear": "怕这个念头越来越真实。",
            "quote": "我需要有人在那之前发现我不对劲。",
            "decision_logic": "最需要的不是建议，是立刻能被接住的通道。",
            "blockers": ["不愿求助", "情绪失控反复"],
            "drivers": ["危机转介", "紧急联系人", "被注意到"],
        },
    ],
    "high_executor_checkin": [
        {
            "core_motive": "分手第30天开始打卡，第47天没断过——进度是我最大的动力。",
            "fear": "怕打卡断了就真的撑不住。",
            "quote": "给我进度条就行——我要看着自己好起来。",
            "decision_logic": "要的是可视化的坚持记录和无缝的复盘节奏。",
            "blockers": ["偶尔怀疑坚持的意义", "瓶颈期进度变慢"],
            "drivers": ["打卡天数", "里程碑", "看得见的进展"],
        },
        {
            "core_motive": "断签比分手那天还难受，看着日历上的空缺就焦虑。",
            "fear": "怕一次断签毁了全部积累。",
            "quote": "连续纪录会骗人，但习惯不会。",
            "decision_logic": "要允许偶尔断签，更要奖励累计天数。",
            "blockers": ["完美打卡压力", "凌晨想补签却干脆放弃"],
            "drivers": ["进度可视化", "成就反馈"],
        },
    ],
    "high_executor_block": [
        {
            "core_motive": "说过「删干净」就执行到位，讨厌半吊子的自己。",
            "fear": "怕自己半途又心软加回来。",
            "quote": "一次做不利索，就别做了——我说删，就删干净。",
            "decision_logic": "把戒断当项目做：有步骤、有检查项、有进度。",
            "blockers": ["共同朋友的动态防不胜防", "偶尔手滑"],
            "drivers": ["清单化执行", "进度反馈"],
        },
        {
            "core_motive": "拉黑当天的自己像在项目验收：清记录、退群、藏相册，一条条打勾。",
            "fear": "怕验收完又自己偷偷「开工」。",
            "quote": "流程感比意志力可靠。",
            "decision_logic": "把刷TA动态的每个入口都封死，剩下的交给时间。",
            "blockers": ["平台推荐算法老推TA", "空窗期手痒"],
            "drivers": ["数字隔离", "替代活动清单"],
        },
    ],
}


def _apply_story_variant(
    arch: Dict,
    ms: Dict,
    blockers: List[str],
    drivers: List[str],
    reuse_idx: int,
) -> tuple[Dict, List[str], List[str]]:
    """reuse_idx=0 用原型原文；>0 换措辞变体。变体用尽后仍强制加区分尾巴。"""
    if reuse_idx <= 0:
        return ms, blockers, drivers
    variants = STORY_VARIANTS.get(arch.get("key", "")) or []
    ms = dict(ms)
    if variants:
        v = variants[(reuse_idx - 1) % len(variants)]
        for k in ("core_motive", "fear", "quote", "decision_logic"):
            if v.get(k):
                ms[k] = v[k]
        if v.get("blockers"):
            blockers = list(v["blockers"])
        if v.get("drivers"):
            drivers = list(v["drivers"])
    # 变体表用尽（或无表）时必须改写，避免第 2、第 3 人拿到同一句
    n_var = len(variants)
    if not variants or reuse_idx > n_var:
        tags = (
            "先确认有人能接住我",
            "先算清冲动带来的代价",
            "先给自己留一道缓冲",
            "先想清楚我到底要什么",
            "先允许自己反复一次",
            "先给生活立个最小秩序",
        )
        tag = tags[(reuse_idx - 1) % len(tags)]
        base = (ms.get("core_motive") or "").rstrip("。")
        # 去掉可能已有的同款尾巴再拼，避免叠罗汉
        for t in tags:
            if base.endswith(f"——{t}"):
                base = base[: -len(f"——{t}")].rstrip("。")
        ms["core_motive"] = f"{base}——{tag}。"
        fear = (ms.get("fear") or "").rstrip("。")
        if fear and f"侧重点{reuse_idx}" not in fear:
            ms["fear"] = f"{fear}（侧重点{reuse_idx + 1}）。"
    return ms, blockers, drivers


def _effective_reuse_idx(arch: Dict, seed: Dict, reuse_idx: int) -> int:
    """非种子本人 / 克隆名，至少按第 2 套叙事处理，杜绝「换皮同文案」。"""
    name = seed.get("name") or ""
    if name != arch.get("seed_name"):
        return max(reuse_idx, 1)
    if any(x in name for x in ("（", "(", "·")):
        return max(reuse_idx, 1)
    return reuse_idx


def _adapt_story_to_seed(
    arch: Dict,
    seed: Dict,
    *,
    subject: str,
    family: str,
    reuse_idx: int = 0,
) -> tuple[Dict, List[str], List[str]]:
    """
    原型复用换姓名后，按新人口学改写文案；同 key 第 2+ 次强制措辞差异化。
    角色系统已简化为「本人」，无需伴侣/孝道/合租等角色改写。
    """
    ms = dict(arch["mindset"])
    blockers = list(arch.get("blockers") or [])
    drivers = list(arch.get("drivers") or [])

    # 原装种子且未复用：保留原型；若 reuse>0 仍要换变体
    if (
        seed["name"] == arch.get("seed_name")
        and reuse_idx == 0
    ):
        return ms, blockers, drivers

    # 换姓名后按年龄段/场景做轻量修正，再切变体
    age = _age_mid(seed)
    if age >= 40:
        ms["core_motive"] = (
            f"{ms.get('core_motive', '').rstrip('。')}——到了这个年纪，更想把日子过踏实。"
        )
    elif age <= 20:
        ms["core_motive"] = (
            f"{ms.get('core_motive', '').rstrip('。')}——我还这么年轻，不想困在这一段里。"
        )

    ms, blockers, drivers = _apply_story_variant(arch, ms, blockers, drivers, reuse_idx)
    return ms, blockers, drivers


def _factor_map(factors: List[Factor]) -> Dict[str, Factor]:
    return {f.id: f for f in factors}


def _dominant_from_archetype(
    arch: Dict, factors: List[Factor], *, role: str, subject: str
) -> List[Factor]:
    fmap = _factor_map(factors)
    dom: List[Factor] = []
    for fid in arch["dominant"]:
        if fid in fmap:
            dom.append(fmap[fid])
    if len(dom) < 2:
        for f in factors:
            if f.id not in [x.id for x in dom] and factor_fits_persona(
                f, role, subject, "", arch["segment"]
            ):
                dom.append(f)
            if len(dom) >= 3:
                break
    return dom[:4]


def _build_factor_weights(
    factors: List[Factor],
    dominant: List[Factor],
    arch: Dict,
    *,
    role: str,
    subject: str,
) -> Dict[str, int]:
    """不匹配分群的维度权重为 0，避免高危因子污染普通戒断者。"""
    dom_ids = {f.id for f in dominant}
    segment = arch["segment"]
    weights: Dict[str, int] = {}
    for f in factors:
        if f.id in dom_ids:
            weights[f.id] = min(10, max(6, f.weight))
        elif not factor_fits_persona(f, role, subject, "", segment):
            weights[f.id] = 0
        else:
            weights[f.id] = random.choice([0, 1, 2])
    return weights


def _react_from_archetype(arch: Dict, primary_name: str, motive: str = "") -> ReactTemplates:
    job = get_job((arch.get("jtbd") or {}).get("job_id", ""))
    job_label = job.name if job else arch.get("segment", "这件事")
    step_id = (arch.get("jtbd") or {}).get("current_step_id", "")
    sub_map = {s.id: s for s in load_sub_jobs()}
    step = sub_map[step_id].name if step_id in sub_map else "当前步骤"
    # 用已适配的动机短句，避免复用时仍露出原型种子原文
    bit = (motive or (arch.get("mindset") or {}).get("core_motive") or primary_name)[:28]
    return ReactTemplates(
        advance=f"听到{{{{topic}}}}，这正好推进我在「{job_label}」上的任务（我卡在{step}），尤其是{bit}…想深入了解。",
        hesitate=f"{{{{topic}}}}有点相关，但我还卡在「{step}」，得再想想。",
        reject=f"推广没解开我真正卡点（{step} / {bit}…），不太信。",
        na=f"跟我现在的任务「{job_label}」关系不大。",
    )


def _detach_for_archetype(arch: Dict) -> DetachInfo:
    stage = arch.get("detach_stage") or arch.get("stage", "应激期")
    if stage not in ("应激期", "戒断行动期", "稳定坚持期", "复发应对期", "重建转化期"):
        stage = "应激期"
    urge = int(arch.get("contact_urge", 7))
    return DetachInfo(
        stage=stage,
        weeks_since_breakup=int(arch.get("weeks_since_breakup", random.randint(2, 12))),
        relationship_months=int(arch.get("relationship_months", random.randint(6, 48))),
        contact_urge=urge,
        relapse_count=int(arch.get("relapse_count", 0)),
        safety_flag=bool(arch.get("safety_flag", False)),
    )


# Outcome 与典型驱动的关联（对齐 data/outcomes.json 的 factor_ids，用于按主导维度微调重要度）
_OUTCOME_FACTOR_HINTS: Dict[str, List[str]] = {
    "O1": ["A7", "A11", "B1"],
    "O2": ["A4", "B2", "B5"],
    "O3": ["A7", "B4", "B10"],
    "O4": ["A5", "A6", "B2"],
    "O5": ["A2", "A3", "B3"],
    "O6": ["B1", "A9", "B9"],
    "O7": ["A8", "A1", "B9"],
    "O8": ["A7", "B10", "B6"],
    "O9": ["A10", "B8", "B9"],
}

# 戒断阶段越靠前，暴露/冲动类越不满意；越靠后，重建/掌控类越有进展感
_STAGE_SAT_BIAS: Dict[str, Dict[str, int]] = {
    "应激期": {"O5": -2, "O7": -2, "O1": -1, "O4": -1},
    "戒断行动期": {"O5": -1, "O4": -1, "O2": -1},
    "稳定坚持期": {"O2": 1, "O8": 1, "O3": -1},
    "复发应对期": {"O3": -2, "O4": -2, "O1": -1, "O7": -1},
    "重建转化期": {"O8": 2, "O6": 1, "O3": 1},
}


def _clamp_score(v: int, lo: int = 1, hi: int = 10) -> int:
    return max(lo, min(hi, int(v)))


def _score_desired_outcomes(arch: Dict, *, salt: str = "") -> List[DesiredOutcome]:
    """
    按 Job / 戒断阶段 / 主导维度 / 价格敏感度 拉开 importance·satisfaction，
    避免全员同款 9/2、8/3、7/4。
    """
    jt = arch.get("jtbd") or {}
    job = get_job(jt.get("job_id", ""))
    desired_ids = list(jt.get("desired_outcome_ids") or (job.outcome_ids if job else []))[:5]
    if not desired_ids:
        return []

    # 稳定随机：同一原型+盐值可复现，不同人不同分布
    rng = random.Random(f"{arch.get('key','')}|{salt}|{','.join(desired_ids)}")
    stage = arch.get("stage", "")
    dominant = set(arch.get("dominant") or [])
    forces = jt.get("forces") or {}
    push = set(forces.get("push") or [])
    pull = set(forces.get("pull") or [])
    anxiety = set(forces.get("anxiety") or [])
    price_sens = int((arch.get("mindset") or {}).get("price_sensitivity") or 5)
    blockers = " ".join(arch.get("blockers") or [])
    drivers = " ".join(arch.get("drivers") or [])
    safety = bool(arch.get("safety_flag", False))

    # 显式覆盖（原型可写 outcome_scores: {O4: {importance, satisfaction}}）
    overrides = jt.get("outcome_scores") or {}

    scored: List[DesiredOutcome] = []
    for rank, oid in enumerate(desired_ids):
        if oid in overrides:
            ov = overrides[oid]
            scored.append(
                DesiredOutcome(
                    id=oid,
                    importance=_clamp_score(ov.get("importance", 7)),
                    satisfaction=_clamp_score(ov.get("satisfaction", 4)),
                )
            )
            continue

        # —— 重要度：列表位次只作弱基线，再用故事要素拉开 ——
        importance = 7 - min(rank, 2)  # 7/6/5 …
        hints = set(_OUTCOME_FACTOR_HINTS.get(oid, []))
        # 主导/push 对齐 → 更在乎
        overlap_dom = len(hints & dominant)
        overlap_push = len(hints & push)
        importance += overlap_dom * 1 + overlap_push * 2
        if oid in ("O6",) and price_sens >= 8:
            importance += 2
        elif oid in ("O6",) and price_sens <= 3:
            importance -= 2
        if oid == "O9" and safety:
            importance += 3
        if oid == "O3" and any(k in blockers + drivers for k in ("反复", "破戒", "复发", "前功尽弃")):
            importance += 1
        if oid == "O8" and any(k in blockers + drivers for k in ("打卡", "进度", "秩序", "立起来")):
            importance += 1
        if oid == "O2" and any(k in drivers for k in ("缓冲", "延迟", "掌控", "带走")):
            importance += 1
        if oid == "O1" and stage in ("应激期", "复发应对期"):
            importance += 1
        # 人物微扰
        importance += rng.choice([-1, 0, 0, 1, 1])

        # —— 满意度：阶段偏见 + 焦虑未解则更低 ——
        satisfaction = 4 + rng.choice([-1, 0, 0, 1])
        for k, delta in (_STAGE_SAT_BIAS.get(stage) or {}).items():
            if k == oid:
                satisfaction += delta
        # 相关 anxiety 未解除 → 满意更低
        if hints & anxiety:
            satisfaction -= 2
        if hints & pull and stage in ("戒断行动期", "稳定坚持期", "重建转化期"):
            satisfaction += 1  # 已在尝试解法，略有着落感
        if oid == "O9" and safety:
            satisfaction = min(satisfaction, 2)  # 高危生命缺口始终很尖锐
        if oid == "O6" and price_sens >= 8:
            satisfaction = min(satisfaction, 3)
        # 列表越往后通常不是最疼，满意可略高
        satisfaction += min(rank, 2)
        satisfaction += rng.choice([-1, 0, 0, 1])

        # 保证缺口存在：最靠前的至少差 2 分
        importance = _clamp_score(importance, 4, 10)
        satisfaction = _clamp_score(satisfaction, 1, 8)
        satisfaction = min(satisfaction, importance)  # 满意不超过在乎
        if rank == 0 and importance - satisfaction < 2:
            satisfaction = _clamp_score(importance - 2 - rng.choice([0, 1]), 1, 8)
        if rank == 0 and importance < 7:
            importance = _clamp_score(importance + rng.choice([1, 2]), 7, 10)
            satisfaction = min(satisfaction, importance - 1)

        scored.append(DesiredOutcome(id=oid, importance=importance, satisfaction=satisfaction))

    # 按「缺口」重排展示顺序（不改 ids 集合）：最渴的排前面，UI 更直观
    scored.sort(key=lambda d: (d.satisfaction / max(d.importance, 1), -d.importance))
    return scored


def _build_jtbd(arch: Dict, *, salt: str = "") -> JTBDProfile:
    jt = arch.get("jtbd") or {}
    job = get_job(jt.get("job_id", ""))
    sub_map = {s.id: s for s in load_sub_jobs()}
    step_id = jt.get("current_step_id", "")
    step_name = sub_map[step_id].name if step_id in sub_map else ""

    desired = _score_desired_outcomes(arch, salt=salt)

    forces_raw = jt.get("forces") or {}
    forces = ForceMap(
        push=list(forces_raw.get("push", [])),
        pull=list(forces_raw.get("pull", [])),
        anxiety=list(forces_raw.get("anxiety", [])),
        habit_or_alternative=list(forces_raw.get("habit_or_alternative", [])),
    )

    return JTBDProfile(
        entry_situation=jt.get("entry_situation", ""),
        job_id=jt.get("job_id", ""),
        job_owner=jt.get("job_owner", ""),
        core_job=job.name if job else "",
        job_statement=job.statement if job else "",
        current_step=step_name,
        desired_outcomes=desired,
        forces=forces,
    )


def _persona_from_archetype(
    arch: Dict,
    index: int,
    factors: List[Factor],
    used_names: set,
    *,
    reuse_idx: int = 0,
    used_motives: Optional[set] = None,
) -> Persona:
    seed_name = arch["seed_name"]
    preferred = SEED_BY_NAME.get(seed_name) or PERSONA_SEEDS[index % len(PERSONA_SEEDS)]
    seed = _pick_unique_seed(
        seed_name,
        used_names,
        gender_hint=preferred.get("gender", ""),
        arch=arch,
    )
    role, subject, family = _align_role_subject_family(arch, seed)

    try_idx = _effective_reuse_idx(arch, seed, reuse_idx)
    ms, blockers, drivers = _adapt_story_to_seed(
        arch, seed, subject=subject, family=family, reuse_idx=try_idx
    )
    # 同批动机撞车时再换一档变体
    if used_motives is not None:
        guard = 0
        while ms.get("core_motive") in used_motives and guard < 10:
            try_idx += 1
            ms, blockers, drivers = _adapt_story_to_seed(
                arch, seed, subject=subject, family=family, reuse_idx=try_idx
            )
            guard += 1
        if ms.get("core_motive") in used_motives:
            ms = dict(ms)
            ms["core_motive"] = (
                (ms.get("core_motive") or "").rstrip("。")
                + f"——按{seed['name']}自家情况再比一比。"
            )
            ms["fear"] = ((ms.get("fear") or "").rstrip("。") + f"（{seed['name']}版）。")
            if ms.get("quote"):
                ms["quote"] = (ms["quote"].rstrip("。") + f"（{seed['name']}）")
        used_motives.add(ms.get("core_motive", ""))

    segment = arch["segment"]

    dom = _dominant_from_archetype(arch, factors, role=role, subject=subject)
    primary_name = dom[0].name if dom else "这件事"
    jtbd = _build_jtbd(arch, salt=f"{seed['name']}|{index}|{family}|{try_idx}")

    return Persona(
        id=_persona_id(index + 1),
        name=seed["name"],
        emoji=seed["emoji"],
        segment=segment,
        role=role,
        subject=subject,
        age=random.randint(*seed["age_range"]),
        gender=seed["gender"],
        city=seed["city"],
        occupation=seed["occupation"],
        family=family,
        income=seed["income"],
        detach=_detach_for_archetype(arch),
        mindset=Mindset(**ms),
        dominant_features=[DominantFeature(code=f.id, weight=f.weight) for f in dom],
        factor_weights=_build_factor_weights(
            factors, dom, arch, role=role, subject=subject
        ),
        blockers=blockers,
        drivers=drivers,
        decision_style=arch["decision_style"],
        react=_react_from_archetype(arch, primary_name, motive=ms.get("core_motive", "")),
        jtbd=jtbd,
        evidence_refs=["synthetic", arch.get("key", "archetype")],
    )


def _resolve_job_filter(
    job_ids: Optional[List[str]],
    entry_themes: Optional[List[str]],
) -> Optional[List[str]]:
    resolved = set(job_ids or [])
    for theme in entry_themes or []:
        resolved.update(ENTRY_THEME_TO_JOBS.get(theme, []))
    return list(resolved) if resolved else None


def generate_personas_fallback(
    count: int,
    factors: List[Factor],
    *,
    job_ids: Optional[List[str]] = None,
    entry_situations: Optional[List[str]] = None,
    entry_themes: Optional[List[str]] = None,
    **_kwargs,
) -> List[Persona]:
    if not factors:
        raise ValueError("无可用维度")

    resolved_jobs = _resolve_job_filter(job_ids, entry_themes)
    archetypes = pick_archetypes(
        count, job_ids=resolved_jobs, entry_situations=entry_situations
    )
    archetypes = archetypes[:count]
    used_names: set = set()
    used_motives: set = set()
    key_seen: Dict[str, int] = {}
    out: List[Persona] = []
    for i, arch in enumerate(archetypes):
        k = arch.get("key", "")
        reuse_idx = key_seen.get(k, 0)
        key_seen[k] = reuse_idx + 1
        out.append(
            _persona_from_archetype(
                arch,
                i,
                factors,
                used_names,
                reuse_idx=reuse_idx,
                used_motives=used_motives,
            )
        )
    return out