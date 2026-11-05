"""旅游心智沙盘 harness：结构蓝图、LLM 生成、质检修复、规则判定与可选 LLM 表达。"""
from __future__ import annotations

import json
import re
import random
from copy import deepcopy
from pathlib import Path
from typing import Any

from openai import APIError, OpenAI

from config import get_api_key, get_base_url, get_model_name, llm_configured
from schemas import Factor, Job, Outcome, Persona, SimulateResult, SubJob

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MAX_QC_RETRIES = 3

# 旅游方案助力点属于规则假设，编码只连接本项目的旅游维度。
INTERVENTIONS = {
    "budget_clarity": ("费用透明", ["B1", "B2"], ["费用透明", "预算明细", "总价", "人均", "隐藏费用", "附加费"]),
    "flexible_booking": ("灵活退改", ["B9"], ["退改", "可退", "可改", "免费改期", "退款"]),
    "authentic_information": ("近期真实信息", ["B5", "B6"], ["近期真实", "真实评价", "近期实拍", "酒店实拍"]),
    "party_coordination": ("同行协调", ["B3", "B4"], ["统一档期", "协调日期", "兼顾老人", "兼顾孩子", "兼顾偏好"]),
    "route_support": ("路线与接驳", ["B7"], ["路线", "交通接驳", "减少换乘", "避免折返"]),
    "local_support": ("当地客服与售后", ["B10"], ["当地客服", "售后", "客服", "平台责任"]),
    "contingency_plan": ("天气与安全预案", ["B8"], ["天气预案", "雨天备选", "安全保障", "避开人流"]),
    "preparation_support": ("出行准备支持", ["B11"], ["签证指导", "证件清单", "无障碍", "语言支持", "电话卡"]),
    "comparison_support": ("省心比价", ["B12"], ["统一比价", "统一报价", "比较口径", "不用反复比价"]),
    "pace_support": ("同行体力适配", ["B13"], ["步行强度", "体力安排", "缩短车程", "减少坐车"]),
    "experience_support": ("核心体验安排", ["A12"], ["在地体验", "当地生活", "本地生活", "自然体验"]),
}


def _clauses(campaign: str) -> list[str]:
    return [x.strip() for x in re.split(r"[，,。；;！!？?\n]+", campaign) if x.strip()]


def _negative(text: str) -> bool:
    # 描述消除顾虑与真实限制分开，避免双重否定误伤。
    for phrase in ("无隐藏费用", "没有隐藏费用", "不收附加费", "无附加费", "不另收费", "不用担心", "无需担心", "避免", "无需"):
        text = text.replace(phrase, "")
    return bool(re.search(r"不含|不退|不可退|不可改|另收费|不保障|不负责|无法|不支持|不提供|不能|不包含|不真实|退款难|拒绝退款", text))


def _supportive(text: str) -> bool:
    if _negative(text):
        return False
    return any(word in text for word in (
        "透明", "明细", "包含", "保障", "可退", "可改", "支持", "清楚", "提供", "官方", "近期",
        "真实", "安排", "统一", "协调", "兼顾", "减少", "避免", "预案", "备选", "避开", "指导", "缩短",
        "清单", "无隐藏费用", "没有隐藏费用", "无附加费", "不收附加费", "不另收费",
    )) or bool(re.search(r"人均\s*[¥￥]?\s*\d+", text))


def detect_interventions(campaign: str, factors: list[Factor]) -> list[str]:
    enabled = {f.id for f in factors if f.enabled}
    return [key for key, (_, ids, words) in INTERVENTIONS.items()
            if enabled.intersection(ids) and any(_supportive(clause) and any(word in clause for word in words) for clause in _clauses(campaign))]


def _raw(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def load_jobs() -> list[Job]:
    return [Job.model_validate(x) for x in _raw("jobs.json")["jobs"]]


def load_steps() -> list[SubJob]:
    return [SubJob.model_validate(x) for x in _raw("jobs.json")["sub_jobs"]]


def load_outcomes() -> list[Outcome]:
    return [Outcome.model_validate(x) for x in _raw("outcomes.json")["outcomes"]]


def load_factors(enabled_only: bool = False) -> list[Factor]:
    rows = [Factor.model_validate(x) for x in _raw("factors.json")["factors"]]
    return [x for x in rows if x.enabled] if enabled_only else rows


def _client() -> OpenAI:
    if not llm_configured():
        raise RuntimeError("未配置 DeepSeek API；请设置 DEEPSEEK_API_KEY 和漫创共享配置路径。")
    return OpenAI(api_key=get_api_key(), base_url=get_base_url(), timeout=60.0, max_retries=2)


def _json_object(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("模型没有返回 JSON 对象")
    value = json.loads(match.group())
    if not isinstance(value, dict):
        raise ValueError("模型输出必须是 JSON 对象")
    return value


def _complete(client: OpenAI, prompt: str, *, temperature: float = 0.75) -> str:
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=3500,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise ValueError("DeepSeek 返回空内容")
    return content


def _blueprints(count: int, job_ids: list[str] | None = None, *, randomize: bool = False, random_seed: int | None = None) -> list[dict]:
    seeds = _raw("persona_seeds.json")
    if job_ids:
        allowed = set(job_ids)
        seeds = [p for p in seeds if p["job_id"] in allowed]
        if not seeds:
            raise ValueError("筛选条件没有匹配的旅游任务")
    jobs = {j.id: j for j in load_jobs()}
    steps = {s.id: s for s in load_steps()}
    factors = load_factors(True)
    factor_ids = {f.id for f in factors}
    result = []
    rng = random.Random(random_seed)
    for idx in range(count):
        if randomize and idx % len(seeds) == 0:
            rng.shuffle(seeds)
        seed = deepcopy(seeds[idx % len(seeds)])
        job = jobs[seed["job_id"]]
        step = next((steps[sid] for sid in job.step_ids if steps[sid].stage == seed["stage"]), steps[job.step_ids[0]])
        preferred_outcomes = [oid for oid in seed.get("desired_outcomes", job.outcome_ids) if oid in job.outcome_ids]
        desired = [
            {"id": oid, "importance": 9 - pos, "satisfaction": 3 + pos}
            for pos, oid in enumerate(preferred_outcomes[:3])
        ]
        features = [{"code": code, "weight": weight} for code, weight in seed["features"] if code in factor_ids]
        if randomize:
            for item in features:
                item["weight"] = max(1, min(10, item["weight"] + rng.choice([-1, 0, 1])))
            for item in desired:
                item["satisfaction"] = max(1, min(10, item["satisfaction"] + rng.choice([-1, 0, 1])))
        weights = {f.id: 0 for f in factors}
        weights.update({code: weight for code, weight in seed["features"] if code in factor_ids})
        weights.update({item["code"]: item["weight"] for item in features})
        name = seed["name"] if idx < len(seeds) else f"{seed['name']}{idx // len(seeds) + 1}"
        bp = {
            "id": f"P{idx + 1:02d}", "name": name, "emoji": seed["emoji"],
            "segment": seed["segment"], "role": seed["role"], "subject": seed["subject"],
            "age": seed["age"], "gender": seed["gender"], "city": seed["city"],
            "occupation": seed["occupation"], "family": seed["family"], "income": seed["income"],
            "travel": {"stage": seed["stage"], "departure_window": seed["departure_window"],
                       "trip_length_days": seed["trip_length_days"], "party_size": seed["party_size"],
                       "budget_per_person": seed["budget_per_person"], "booked": seed["booked"]},
            "mindset": {"core_motive": seed["motive"], "fear": seed["fear"],
                        "decision_logic": seed["decision_logic"], "price_sensitivity": seed["price_sensitivity"],
                        "brand_anchor": seed["brand_anchor"], "channel_preference": seed["channel_preference"],
                        "quote": seed["quote"]},
            "dominant_features": features, "factor_weights": weights,
            "blockers": seed["blockers"], "drivers": seed["drivers"],
            "decision_style": seed["segment"],
            "react": {
                "advance": f"{seed['quote']} 这个方案回应了我最在意的部分，我愿意继续了解。",
                "hesitate": f"我还需要确认「{seed['fear']}」",
                "reject": f"这个安排没有解决「{seed['fear']}」",
                "na": f"这和我当前的「{job.name}」任务关系不大。",
            },
            "jtbd": {"entry_situation": job.entry_situations[0], "job_id": job.id,
                     "job_owner": seed["role"], "core_job": job.name, "job_statement": job.statement,
                     "current_step": step.name, "desired_outcomes": desired,
                     "forces": {"push": seed["push"], "pull": seed["pull"],
                                "anxiety": seed["anxiety"], "habit_or_alternative": []}},
            "evidence_refs": ["synthetic", "hypothesis"],
        }
        result.append(Persona.model_validate(bp).model_dump())
    return result


def _generation_prompt(blueprint: dict, factors: list[Factor], jobs: list[Job], steps: list[SubJob], outcomes: list[Outcome]) -> str:
    context = {
        "blueprint": blueprint,
        "jobs": [x.model_dump() for x in jobs],
        "steps": [x.model_dump() for x in steps],
        "outcomes": [x.model_dump() for x in outcomes],
        "factors": [x.model_dump() for x in factors],
    }
    return f"""你是旅游意向人群的 JTBD 心智画像生成器。为蓝图中的一个槽位生成一位原创、具体的人物。

【研究边界】当前旅游需求是研究假设，不得写成真实访谈发现；evidence_refs 必须包含 synthetic 和 hypothesis。不得编造研究数据或外部证据。
【结构上下文】
{json.dumps(context, ensure_ascii=False, indent=2)}

【生成步骤】
1. 保持蓝图 job_id、job_owner、entry_situation 与 current_step；current_step 必须是步骤中文名称。
2. 从对应任务的 outcome_ids 中选 2-4 项，importance、satisfaction 用 1-10 分，低满意度表示未满足。
3. forces 只能使用给定 factors 的 id；画像故事、担忧、报价敏感度和旅行方式须互相一致。
4. 生成真实感生活细节，但只能作为合成示例；旅行时间、天数、同行人数、人均预算与已预订状态写入 travel。
5. react 用第一人称，分别描述方案打动、仍犹豫、拒绝和无关时的反应。

【一致性约束】
- 目标人群是有明确或初步旅游意向、正在决定/规划/预订/准备出行的人。
- 禁止虚构调查、访谈、市场规模、转化率或统计比例。
- JTBD、步骤、期望结果、维度编码必须来自上述结构上下文。
- 不要复制蓝图的故事原句；可以保留任务结构并原创姓名、职业、情境和口语表达。

【输出】只返回一个 JSON 对象，不要 Markdown。字段结构如下：
{{"id":"{blueprint['id']}","name":"","emoji":"🧳","segment":"","role":"","subject":"","age":30,"gender":"","city":"","occupation":"","family":"","income":"","travel":{{"stage":"目的地筛选","departure_window":"未来三个月","trip_length_days":4,"party_size":2,"budget_per_person":5000,"booked":false}},"mindset":{{"core_motive":"","fear":"","decision_logic":"","price_sensitivity":5,"brand_anchor":"","channel_preference":"","quote":""}},"dominant_features":[{{"code":"B1","weight":7}}],"factor_weights":{{"B1":7}},"blockers":[],"drivers":[],"decision_style":"","react":{{"advance":"","hesitate":"","reject":"","na":""}},"jtbd":{{"entry_situation":"","job_id":"{blueprint['jtbd']['job_id']}","job_owner":"","core_job":"","job_statement":"","current_step":"","desired_outcomes":[{{"id":"O1","importance":8,"satisfaction":3}}],"forces":{{"push":[],"pull":[],"anxiety":[],"habit_or_alternative":[]}}}},"evidence_refs":["synthetic","hypothesis"]}}"""


def _validate(persona: Persona, factors: list[Factor], jobs: list[Job], steps: list[SubJob], outcomes: list[Outcome], blueprint: dict, names: set[str]) -> list[str]:
    issues: list[str] = []
    factor_ids = {f.id for f in factors}
    job_map = {j.id: j for j in jobs}
    step_map = {s.id: s for s in steps}
    outcome_ids = {o.id for o in outcomes}
    if persona.jtbd.job_id not in job_map:
        issues.append("job_id 不在任务本体中")
    elif persona.jtbd.job_id != blueprint["jtbd"]["job_id"]:
        issues.append("画像任务与蓝图不一致")
    if persona.jtbd.job_owner != blueprint["jtbd"]["job_owner"]:
        issues.append("任务承担者与蓝图不一致")
    if persona.role != persona.jtbd.job_owner:
        issues.append("画像角色与任务承担者不一致")
    if persona.jtbd.entry_situation != blueprint["jtbd"]["entry_situation"]:
        issues.append("起始情境与蓝图不一致")
    if persona.jtbd.core_job != blueprint["jtbd"]["core_job"]:
        issues.append("核心任务与蓝图不一致")
    if persona.name in names:
        issues.append("画像姓名重复")
    job = job_map.get(persona.jtbd.job_id)
    step = next((s for s in steps if s.name == persona.jtbd.current_step), None)
    if not step or (job and step.id not in job.step_ids):
        issues.append("当前步骤不属于画像主任务")
    elif persona.travel.stage != step.stage:
        issues.append("旅行阶段与当前步骤不一致")
    if persona.jtbd.current_step != blueprint["jtbd"]["current_step"]:
        issues.append("当前步骤与蓝图不一致")
    for outcome in persona.jtbd.desired_outcomes:
        if outcome.id not in outcome_ids or (job and outcome.id not in job.outcome_ids):
            issues.append(f"期望结果 {outcome.id} 不属于该任务")
    if len(persona.jtbd.desired_outcomes) < 2:
        issues.append("至少选择两项期望结果")
    if len({o.id for o in persona.jtbd.desired_outcomes}) != len(persona.jtbd.desired_outcomes):
        issues.append("期望结果重复")
    force_ids = {x for values in persona.jtbd.forces.model_dump().values() for x in values}
    used_ids = force_ids | {x.code for x in persona.dominant_features} | set(persona.factor_weights)
    unknown = used_ids - factor_ids
    if unknown:
        issues.append(f"包含未知决策维度：{sorted(unknown)}")
    if any(not 0 <= weight <= 10 for weight in persona.factor_weights.values()):
        issues.append("决策维度权重超出 0-10")
    if any(persona.factor_weights.get(feature.code) != feature.weight for feature in persona.dominant_features):
        issues.append("主导特征权重与维度权重不一致")
    if persona.travel.trip_length_days < 1 or persona.travel.party_size < 1:
        issues.append("旅行天数和同行人数必须为正数")
    if persona.travel.stage not in {x for j in jobs for x in [s.stage for s in steps if s.id in j.step_ids]}:
        issues.append("旅行阶段不在任务阶段列表中")
    if not {"synthetic", "hypothesis"}.issubset(set(persona.evidence_refs)):
        issues.append("证据标签必须明确标记 synthetic 与 hypothesis")
    return issues


def generate_personas(count: int, *, use_llm: bool = False, job_ids: list[str] | None = None, randomize: bool = False, random_seed: int | None = None, use_evidence: bool = False, use_profile: bool = True) -> list[Persona]:
    blueprints = _blueprints(count, job_ids, randomize=randomize, random_seed=random_seed)
    if use_evidence:
        from services.persona_evidence import adjust
        blueprints = [p.model_dump() for p in adjust([Persona.model_validate(bp) for bp in blueprints], use_profile=use_profile)]
    if not use_llm:
        return [Persona.model_validate(bp) for bp in blueprints]
    client = _client()
    factors, jobs, steps, outcomes = load_factors(True), load_jobs(), load_steps(), load_outcomes()
    personas: list[Persona] = []
    names: set[str] = set()
    for bp in blueprints:
        prompt = _generation_prompt(bp, factors, jobs, steps, outcomes)
        issues: list[str] = []
        candidate: Persona | None = None
        for attempt in range(MAX_QC_RETRIES):
            current = prompt
            if attempt:
                current = prompt + f"""\n修复以下旅游心智画像，最小化修改，并解决所有质检问题。只能依据给出的结构上下文、原画像和问题修复；不要添加真实研究证据。
问题：{json.dumps(issues, ensure_ascii=False)}
原画像：{json.dumps(candidate.model_dump() if candidate else {}, ensure_ascii=False)}
蓝图：{json.dumps(bp, ensure_ascii=False)}
只返回修复后的 JSON 对象。"""
            try:
                raw = _json_object(_complete(client, current, temperature=0.72 if attempt == 0 else 0.25))
                raw["id"] = bp["id"]
                # Provenance is owned by the harness; the LLM cannot invent evidence.
                raw["evidence_refs"] = bp["evidence_refs"]
                raw["research"] = bp.get("research", {})
                if bp.get("research", {}).get("record_ids"):
                    for key in ("travel", "family", "dominant_features", "factor_weights", "jtbd", "blockers", "drivers"):
                        raw[key] = deepcopy(bp[key])
                    raw.setdefault("mindset", {}).update({key: bp["mindset"][key] for key in ("fear", "quote")})
                candidate = Persona.model_validate(raw)
                issues = _validate(candidate, factors, jobs, steps, outcomes, bp, names)
                if not issues:
                    personas.append(candidate)
                    names.add(candidate.name)
                    break
            except APIError:
                # SDK 已重试接口故障；它不属于画像内容问题，不能进入质检修复。
                raise
            except Exception as exc:
                issues = [str(exc)[:500]]
        else:
            # 内容质检连续失败时回退到确定性结构蓝图；服务/API 故障仍在上方原样抛出。
            fallback = Persona.model_validate(deepcopy(bp))
            fallback.evidence_refs = list(dict.fromkeys([*fallback.evidence_refs, "archetype_fallback", "synthetic", "hypothesis"]))
            fallback_issues = _validate(fallback, factors, jobs, steps, outcomes, bp, names)
            if fallback_issues:
                raise ValueError(f"{bp['id']} 生成质检及蓝图回退均未通过：{'；'.join(fallback_issues)}")
            personas.append(fallback)
            names.add(fallback.name)
    return personas


def identify_factors(campaign: str, factors: list[Factor]) -> list[str]:
    text = campaign.casefold()
    support_ids = {fid for key in detect_interventions(campaign, factors) for fid in INTERVENTIONS[key][1]}
    return [f.id for f in factors if f.enabled and (f.id in support_ids or any(k.casefold() in text for k in f.keywords if k))]


def _rule_result(persona: Persona, campaign: str, factors: list[Factor], outcomes: list[Outcome], hits: list[str]) -> SimulateResult:
    hit_factors = [f for f in factors if f.enabled and f.id in hits]
    force_values = persona.jtbd.forces.model_dump()
    persona_factor_ids = {x for values in force_values.values() for x in values}
    matched = [f for f in hit_factors if f.id in persona_factor_ids]
    outcome_map = {f.id: set(f.outcome_ids) for f in factors}
    active = detect_interventions(campaign, factors)
    applicable = [key for key in active if persona_factor_ids.intersection(f.id for f in hit_factors if f.id in INTERVENTIONS[key][1])]
    positive_ids = {fid for clause in _clauses(campaign) if _supportive(clause)
                    for fid in identify_factors(clause, factors)}
    improved_ids = {oid for f in matched if f.id in positive_ids for oid in outcome_map.get(f.id, set())}
    desired = persona.jtbd.desired_outcomes
    improved = [x.id for x in desired if x.id in improved_ids]
    negative = any(_negative(clause) and persona_factor_ids.intersection(identify_factors(clause, factors)) for clause in _clauses(campaign))
    # Compare only an explicit per-person quotation in RMB, not arbitrary numbers.
    prices = re.findall(r"人均\s*(?:总价|费用|报价|价格)?\s*[¥￥]?\s*(\d+(?:,\d{3})*)\s*元", campaign)
    known_budget = not persona.research.get("evidence_only") or "travel.budget_per_person" in persona.research.get("field_sources", {})
    over_budget = bool(known_budget and persona.travel.budget_per_person is not None and len(prices) == 1 and int(prices[0].replace(',', '')) > persona.travel.budget_per_person)
    positive = any(_supportive(clause) for clause in _clauses(campaign))
    top_outcome = max(desired, key=lambda x: (x.importance - x.satisfaction, x.importance), default=None)
    key_improved = bool(top_outcome and top_outcome.id in improved)
    if over_budget:
        decision, willingness = "reject", 2
        improved = []
        applicable = []
    elif not matched:
        decision, willingness = "na", 2
    elif negative:
        decision, willingness = "reject", 2
        improved = []
        applicable = []
    elif key_improved and (positive or applicable):
        decision, willingness = "advance", 7
    elif matched or improved:
        decision, willingness = "hesitate", 5
    else:
        decision, willingness = "na", 3
    factor_names = [f.name for f in matched]
    if decision == "advance":
        reaction = f"{persona.mindset.quote} 这次方案回应了我最在意的「{next((o.label or o.name for o in outcomes if o.id == top_outcome.id), '')}」，我愿意继续了解。"
    elif decision == "reject":
        reaction = (f"方案人均报价超过了我这次 ¥{persona.travel.budget_per_person} 的预算，我需要降低费用后再考虑。" if over_budget else f"我担心的「{'; '.join(persona.blockers[:2])}」没有得到解决，反而看到限制条件，不会继续预订。")
    elif decision == "hesitate":
        reaction = f"这和我计划的「{persona.jtbd.core_job}」有些相关，但「{persona.jtbd.current_step}」还需要再确认。"
    else:
        reaction = f"我当前正在处理「{persona.jtbd.core_job}」，这段内容没有碰到这个任务。"
    return SimulateResult(
        persona_id=persona.id,
        persona_name=persona.name,
        decision=decision,
        reaction=reaction,
        hit_factors=factor_names,
        hit_dominant=[x.code for x in persona.dominant_features if x.code in hits],
        willingness=willingness,
        reasoning=f"规则初判：话术命中 {', '.join(factor_names) or '无画像关联维度'}；关键结果{'得到回应' if key_improved else '尚未确认'}。" + ("明确人均人民币报价超过画像预算，触发预算约束。" if over_budget else ""),
        activated_factors=factor_names,
        outcome_improved=improved,
        unresolved_outcomes=[x.id for x in desired if x.id not in improved],
        next_step=persona.jtbd.current_step,
        interventions=applicable,
        mode="rule",
    )


def _simulation_prompt(persona: Persona, campaign: str, rule: SimulateResult, outcomes: list[Outcome], memory: list[dict] | None = None) -> str:
    outcome_names = {o.id: o.name for o in outcomes}
    context = persona.model_dump()
    context.get("research", {}).pop("base_persona", None)
    if persona.research.get("evidence_only"):
        known = persona.research.get("field_sources", {})
        for field in ("age", "gender", "city", "occupation", "income", "family"):
            if field not in known:
                context.pop(field, None)
        context["travel"] = {k: v for k, v in context["travel"].items() if "travel." + k in known}
        context["mindset"] = {k: context["mindset"][k] for k in ("core_motive", "fear", "decision_logic", "quote")}
        context.pop("react", None)
    return f"""你只扮演这位旅游意向用户。根据自己的旅行阶段、任务和决策顾虑，评价下面的旅行方案/营销话术。不得把合成画像说成真实访谈。

画像：{json.dumps(context, ensure_ascii=False)}
话术：{campaign}
规则初判：{json.dumps(rule.model_dump(), ensure_ascii=False)}
期望结果字典：{json.dumps(outcome_names, ensure_ascii=False)}
此前触达记忆：{json.dumps(memory or [], ensure_ascii=False)}

要求：reaction 用口语第一人称，必须指出一个具体旅行细节；reasoning 说明回应了什么、还缺什么；不得把未解决的高重要性结果判为 advance；不新增画像中没有的家庭、预算或出行事实。
只输出 JSON：{{"reaction":"","reasoning":"","decision":"advance|hesitate|na|reject","willingness":1,"outcome_improved":[],"unresolved_outcomes":[],"next_step":"中文步骤名"}}"""


def simulate_persona(persona: Persona, campaign: str, factors: list[Factor], outcomes: list[Outcome], hits: list[str], *, use_llm: bool = False, memory: list[dict] | None = None) -> SimulateResult:
    rule = _rule_result(persona, campaign, factors, outcomes, hits)
    if not use_llm:
        return rule
    client = _client()
    raw = _json_object(_complete(client, _simulation_prompt(persona, campaign, rule, outcomes, memory), temperature=0.35))
    decision = str(raw.get("decision", rule.decision)).lower()
    if decision not in {"advance", "hesitate", "na", "reject"}:
        decision = rule.decision
    # 硬门控：模型不能把规则侧无推进的结果升级成 advance。
    blocked_upgrade = rule.decision != "advance" and decision == "advance"
    if blocked_upgrade:
        decision = rule.decision
    if rule.decision == "reject":
        decision = "reject"
    improved = list(dict.fromkeys(x for x in raw.get("outcome_improved", []) if x in rule.outcome_improved))
    unresolved = [x.id for x in persona.jtbd.desired_outcomes if x.id not in improved]
    required = max(persona.jtbd.desired_outcomes, key=lambda x: (x.importance - x.satisfaction, x.importance), default=None)
    if decision == "advance" and required and required.id not in improved:
        decision = "hesitate"
    willingness = max(1, min(10, int(raw.get("willingness", rule.willingness))))
    if decision == "advance":
        willingness = max(6, willingness)
    elif decision == "reject":
        willingness = min(3, willingness)
    elif decision == "na":
        willingness = min(3, willingness)
    else:
        willingness = min(5, willingness)
    valid_steps = {s.name for s in load_steps() if persona.jtbd.job_id in s.job_ids}
    return rule.model_copy(update={
        "decision": decision,
        "reaction": rule.reaction if blocked_upgrade or rule.decision == "reject" else str(raw.get("reaction") or rule.reaction),
        "reasoning": rule.reasoning if rule.decision == "reject" else str(raw.get("reasoning") or rule.reasoning),
        "willingness": willingness,
        "outcome_improved": improved,
        "unresolved_outcomes": unresolved,
        "next_step": raw.get("next_step") if raw.get("next_step") in valid_steps else rule.next_step,
        "mode": "llm",
    })
