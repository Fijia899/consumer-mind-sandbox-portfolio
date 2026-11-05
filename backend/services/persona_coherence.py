"""通用画像结构检查；旅游领域的硬规则由 travel_harness 负责。"""
from __future__ import annotations

from typing import List

from schemas import Factor, Persona

ARCHETYPE_SEED_NAMES: set[str] = set()


def factor_fits_persona(factor: Factor, role: str, subject: str, family: str, segment: str) -> bool:
    return True


def validate_persona(persona: Persona, factors: List[Factor]) -> List[str]:
    issues: list[str] = []
    allowed = {f.id for f in factors}
    used = set(persona.factor_weights) | {x.code for x in persona.dominant_features}
    used |= {fid for group in persona.jtbd.forces.model_dump().values() for fid in group}
    unknown = used - allowed
    if unknown:
        issues.append(f"未知决策维度：{sorted(unknown)}")
    if not persona.jtbd.job_id or not persona.jtbd.current_step:
        issues.append("画像缺少主任务或当前步骤")
    if not persona.evidence_refs:
        issues.append("画像缺少证据标签")
    return issues


def validate_persona_uniqueness(persona: Persona, *, used_names: set[str]) -> List[str]:
    return [f"画像姓名重复：{persona.name}"] if persona.name in used_names else []


def validate_against_blueprint(persona: Persona, blueprint) -> List[str]:
    job_id = getattr(blueprint, "job_id", None)
    if isinstance(blueprint, dict):
        job_id = blueprint.get("jtbd", {}).get("job_id") or blueprint.get("job_id")
    return ["画像任务与蓝图不一致"] if job_id and persona.jtbd.job_id != job_id else []


def fix_persona_coherence(persona: Persona, factors: List[Factor]) -> Persona:
    allowed = {f.id for f in factors}
    persona.dominant_features = [x for x in persona.dominant_features if x.code in allowed]
    persona.factor_weights = {k: v for k, v in persona.factor_weights.items() if k in allowed}
    for group in persona.jtbd.forces.model_dump():
        setattr(persona.jtbd.forces, group, [x for x in getattr(persona.jtbd.forces, group) if x in allowed])
    return persona


def assert_personas_coherent(personas: List[Persona], factors: List[Factor]) -> None:
    for persona in personas:
        issues = validate_persona(persona, factors)
        if issues:
            raise ValueError(f"{persona.id}: {'; '.join(issues)}")
