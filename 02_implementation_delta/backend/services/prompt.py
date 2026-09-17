from __future__ import annotations

import json
from typing import Any, List, Optional

from schemas import Factor, Job, Outcome, SubJob
from services.persona_coherence import ARCHETYPE_SEED_NAMES


def build_generation_prompt(
    count: int,
    factors: List[Factor],
    jobs: List[Job],
    sub_jobs: List[SubJob],
    outcomes: List[Outcome],
    *,
    job_ids: Optional[List[str]] = None,
    entry_situations: Optional[List[str]] = None,
    steps: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
) -> str:
    filter_note = ""
    if job_ids:
        filter_note += f"\n优先覆盖 Job: {job_ids}"
    if entry_situations:
        filter_note += f"\n优先起点情境: {entry_situations}"
    if steps:
        filter_note += f"\n优先当前步骤: {steps}"
    if roles:
        filter_note += f"\n优先 Job Owner / 角色: {roles}"

    return f"""你是消费者心智画像生成器。基于以下 JTBD 任务本体与维度数据库，生成 {count} 个分手戒断用户心智（理性已确认不复复合、情感尚未戒断的人群）。

【任务本体 jobs】(id/名称/起点情境/发起者/statement/步骤)
{json.dumps([j.model_dump() for j in jobs], ensure_ascii=False, indent=2)}

【子任务 sub_jobs】
{json.dumps([s.model_dump() for s in sub_jobs], ensure_ascii=False, indent=2)}

【期望结果 outcomes】(id/成功标准)
{json.dumps([o.model_dump() for o in outcomes], ensure_ascii=False, indent=2)}

【决策维度 factors】(id/名称/权重/定义/force_default/job_ids/outcome_ids)
{json.dumps([f.model_dump() for f in factors], ensure_ascii=False, indent=2)}
{filter_note}

【生成顺序 — 严格按此，禁止反向拼装】
1. 先从 jobs 中选一个 entry_situation、job_owner、core_job（job 名称）和当前 job_step（子任务名，取自 sub_jobs.name）；
2. 为该 Job 选 3-5 条 desired_outcomes（id 必须来自 outcomes），给出 importance（1-10）与 satisfaction（1-10，越低越急需改善）；
3. 从 factors 中选有证据关联的 push / pull / anxiety / habit_or_alternative 四类 force（填 factor id）；
4. 再生成与上述任务一致的人口学、家庭、分手情境、segment/role/subject；
5. 最后生成第一人称 react 模板（含 {{{{topic}}}}），不得引入 factors 之外的新临床/行为事实；
6. 输出 evidence_refs；无真实来源时标 synthetic / hypothesis。

【逻辑一致性】
- 角色系统：role/subject/job_owner 一律为「本人」（分手戒断的主角就是用户自己），禁止引入「为父母/为伴侣/为室友」类代理角色
- J1 反复查看 → 核心 O5/O2，factor 偏 B3（数字隔离）/B5；satisfaction 低 ⇒ 戒不掉动态
- J2 联系冲动 → 核心 O4（冲动不落地成行动），factor 偏 B2 pull / A5 anxiety
- J3 夜间复发 → 核心 O1/O3，factor 偏 B10 / A8；场景多为深夜独处
- J4 反刍 → 核心 O2，factor 偏 B5 pull / A3 anxiety
- J5 孤独 → 核心 O7/O6，factor 偏 B9 / B1
- J6 重建 → 核心 O8，factor 偏 B11 / B10
- J7 高危 → 核心 O9，**必须**主导含 A10，safety_flag=true，stage 为应激期或复发应对期
- 高危门控：safety_flag=true ↔ dominant_features 含 A10 ↔ job_id=J7 ↔ stage∈{{应激期,复发应对期}} 四者一致；非高危者禁止把 A10 当主导
- 阶段一致性：relapse_count>0 不得处于应激期；stage=复发应对期 必须 relapse_count>0
- dominant_features 与 forces 中的 factor id 必须来自 factors；desired_outcomes.id 必须来自 outcomes；jtbd.job_id 必须来自 jobs

【覆盖要求】覆盖的对象是 Job × Entry Situation × Step，而非每个 factor 都做成一个人。{count} 个人要尽量覆盖 7 个 Job；job_owner 一律为本人。

【输出】只输出一个 JSON 数组，不要其他文字。每人必须含 jtbd 对象：
[ {{
  "id":"P01", "name":"...", "emoji":"...", "segment":"...", "role":"本人", "subject":"本人",
  "age":27, "gender":"女", "city":"...", "occupation":"...", "family":"...", "income":"...",
  "detach":{{...}}, "mindset":{{...}},
  "dominant_features":[{{"code":"B2","weight":9}}],
  "factor_weights":{{"B2":9,...}},
  "blockers":[], "drivers":[], "decision_style":"理性",
  "react":{{"advance":"...{{{{topic}}}}...","hesitate":"...","reject":"...","na":"..."}},
  "jtbd":{{
    "entry_situation":"聊天框亮了，又想发消息问他",
    "job_id":"J2",
    "job_owner":"本人",
    "core_job":"抑制联系前任的冲动",
    "job_statement":"...",
    "current_step":"为联系冲动设定延迟缓冲（5-10分钟规则）",
    "desired_outcomes":[{{"id":"O4","importance":9,"satisfaction":3}}],
    "forces":{{"push":["B2"],"pull":["B5"],"anxiety":["A5"],"habit_or_alternative":[]}}
  }},
  "evidence_refs":["synthetic"]
}} ]
"""


def _schema_example() -> str:
    return """{
  "id":"P01", "name":"...", "emoji":"...", "segment":"...", "role":"本人", "subject":"本人",
  "age":27, "gender":"女", "city":"...", "occupation":"...", "family":"...", "income":"...",
  "detach":{"stage":"应激期","weeks_since_breakup":4,"relationship_months":24,"contact_urge":7,"relapse_count":0,"safety_flag":false},
  "mindset":{"core_motive":"...","fear":"...","decision_logic":"...","price_sensitivity":5,
    "brand_anchor":"...","channel_preference":"...","quote":"..."},
  "dominant_features":[{"code":"B2","weight":9}],
  "factor_weights":{"B2":9},
  "blockers":[],"drivers":[],"decision_style":"理性",
  "react":{"advance":"...{{topic}}...","hesitate":"...","reject":"...","na":"..."},
  "jtbd":{
    "entry_situation":"聊天框亮了，又想发消息问他","job_id":"J2","job_owner":"本人",
    "core_job":"抑制联系前任的冲动","job_statement":"...","current_step":"为联系冲动设定延迟缓冲（5-10分钟规则）",
    "desired_outcomes":[{"id":"O4","importance":9,"satisfaction":3}],
    "forces":{"push":["B2"],"pull":["B5"],"anxiety":["A5"],"habit_or_alternative":[]}
  },
  "evidence_refs":["llm_generated","synthetic"]
}"""


def build_single_persona_prompt(
    blueprint: Any,
    factors: List[Factor],
    jobs: List[Job],
    sub_jobs: List[SubJob],
    outcomes: List[Outcome],
    *,
    used_names: Optional[List[str]] = None,
    banned_names: Optional[List[str]] = None,
) -> str:
    bp = blueprint.to_prompt_dict() if hasattr(blueprint, "to_prompt_dict") else blueprint
    job = next((j for j in jobs if j.id == bp.get("job_id")), None)
    used = used_names or []
    banned = banned_names or sorted(ARCHETYPE_SEED_NAMES)

    return f"""你是分手戒断用户心智画像生成器。请基于 JTBD 结构槽位，创造**一个全新的、独立的真实人物**（理性确认不再复合、情感上还在戒断的人）。

【重要 — 禁止复制预设原型】
- 不得使用以下已有原型姓名：{json.dumps(banned, ensure_ascii=False)}
- 本批已用姓名（不可重复）：{json.dumps(used, ensure_ascii=False)}
- 不得照搬任何预设原型的故事正文；姓名、职业、家庭、分手细节、口语 quote 必须原创
- 16 个原型只提供 Job/角色/分群等**结构约束**，不是让你抄写内容

【本槽位结构蓝图 — 必须遵守】
{json.dumps(bp, ensure_ascii=False, indent=2)}

【对应 Job 详情】
{json.dumps(job.model_dump() if job else {}, ensure_ascii=False, indent=2)}

【子任务 sub_jobs】
{json.dumps([s.model_dump() for s in sub_jobs], ensure_ascii=False, indent=2)}

【期望结果 outcomes】
{json.dumps([o.model_dump() for o in outcomes], ensure_ascii=False, indent=2)}

【决策维度 factors】
{json.dumps([f.model_dump() for f in factors], ensure_ascii=False, indent=2)}

【生成顺序】
1. 严格按蓝图 job_id / job_owner / entry_situation / current_step_id 设定 jtbd
   - **current_step 必须写中文步骤名**（查 sub_jobs.name，如「为联系冲动设定延迟缓冲（5-10分钟规则）」），**禁止**只填字母 id（如 a、e、j）
2. segment、role、subject 与蓝图 role_hint / subject_hint **同类但可改写**（换具体职业与分手场景）；role/subject 一律为「本人」
3. 创造全新人口学：age(20-35)/gender/city/occupation/family/income — 须与 role/subject 逻辑自洽；family 可写独居/合租/与父母同住，**禁止**出现现任配偶或子女（除非明确「前任」）
4. desired_outcomes 从蓝图 desired_outcome_ids 中选 3-5 条，importance/satisfaction 拉开差距（最急缺口 satisfaction 低）
   - 反复联系型（J2）：核心务必是 O4「冲动不落地成行动」；等待复合型易把 O1 当第一优先，注意理性上已确认不复复合
   - 高危型（J7）：核心务必是 O9「高危期获得专业支持」，A10 必须为主导维度
5. dominant_features 与 forces 的 factor id 必须来自 factors，且与 Job 匹配（J7→A10，J2→B2/A5，J3→B10/A8，J5→B9/B1，J6→B11/B10 等）
6. mindset 与 react 第一人称，口语化，体现 creativity_seed 带来的随机生活细节
7. detach：stage 必须来自（应激期/戒断行动期/稳定坚持期/复发应对期/重建转化期）；weeks_since_breakup 为分手周数，contact_urge 反映当前联系冲动；safety_flag 仅高危（A10 主导）者可置 true
8. id 必须为 "{bp.get("persona_id", "P01")}"

【逻辑红线】
- role/subject/job_owner 一律为本人；**禁止**「为父母/为伴侣（推动者）/为室友」类代理角色叙事
- 高危（J7）：A10 主导、safety_flag=true、stage 为应激期或复发应对期、relapse_count≥1；非高危者**禁止**把 A10 当主导或置 safety_flag=true
- 阶段一致性：relapse_count>0 不得处于应激期；stage=复发应对期 必须 relapse_count>0
- 分群↔Job：夜间脆弱型→J3；反复联系型→J2；等待复合型→J1/J2；理性清醒型→J6；自我价值受损型→J6；孤独依赖型→J5；创伤恢复型→J3/J4（高危变体→J7）；高执行打卡型→J6/J1
- Job 核心 Outcome：J1→O5/O2、J2→O4、J3→O1/O3、J4→O2、J5→O7/O6、J6→O8、J7→O9
- 生活纹理只作细节调味，不得推翻蓝图的 job_id / role / segment

【随机创意提示】
- 城市层级参考：{bp.get("city_tier")}
- 职业方向参考：{bp.get("occupation_hint")}
- 生活纹理：{bp.get("life_texture")}
- 创意种子（用于差异化）：{bp.get("creativity_seed")}

【输出】只输出一个 JSON 对象，不要 markdown 或解释。格式：
{_schema_example()}
"""


def build_repair_prompt(
    persona_dict: dict,
    issues: List[str],
    factors: List[Factor],
    jobs: List[Job],
    sub_jobs: List[SubJob],
    outcomes: List[Outcome],
    *,
    blueprint: Any = None,
) -> str:
    bp = (
        blueprint.to_prompt_dict()
        if blueprint is not None and hasattr(blueprint, "to_prompt_dict")
        else {}
    )
    return f"""你是消费者心智画像 QC 修复器。下面这份 JSON 未通过逻辑质检，请**最小改动**修复全部问题后重新输出。

【质检问题 — 必须全部解决】
{json.dumps(issues, ensure_ascii=False, indent=2)}

【结构蓝图（不可偏离 Job/角色骨架）】
{json.dumps(bp, ensure_ascii=False, indent=2)}

【当前错误画像】
{json.dumps(persona_dict, ensure_ascii=False, indent=2)}

【jobs / sub_jobs / outcomes / factors 参照】
jobs: {json.dumps([j.model_dump() for j in jobs], ensure_ascii=False)}
outcomes: {json.dumps([o.model_dump() for o in outcomes], ensure_ascii=False)}
factors ids: {json.dumps([f.id for f in factors], ensure_ascii=False)}

【修复要求】
- 保留 id 不变；尽量保留已合理的原创姓名与故事，只修逻辑矛盾处
- 若姓名与预设原型重名，换一个全新姓名
- dominant_features / factor_weights / jtbd / family / role / subject 须彼此一致
- evidence_refs 保留 "llm_generated"

【输出】只输出修复后的单个 JSON 对象，格式同生成 schema。
"""
