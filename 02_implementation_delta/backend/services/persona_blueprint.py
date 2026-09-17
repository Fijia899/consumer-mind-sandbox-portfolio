"""从 16 个原型抽取 JTBD 结构槽位，供 LLM 创造全新人格（不复制预设姓名/故事）。"""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.persona_archetypes import PERSONA_ARCHETYPES, pick_archetypes

CITY_TIERS = ["一线城市", "二线城市", "三线城市", "四线城市"]
OCCUPATION_HINTS = [
    "服务业",
    "制造业",
    "物流运输",
    "互联网",
    "金融",
    "教育",
    "医疗护理",
    "个体经营",
    "公职",
    "零售",
]
LIFE_TEXTURES_DEFAULT = [
    "刚分手两周、深夜习惯性刷新动态",
    "搬出共同住处、一个人回到出租屋",
    "纪念日快到了、情绪开始暗涌",
    "工作压力大、白天强撑晚上破防",
    "戒断打卡第30天、开始怀疑有没有意义",
    "被共同朋友问到近况、情绪反复",
    "手机相册里的回忆还没清空",
    "换了城市想重新开始、又舍不得删照片",
]
# 按 Job 收窄生活纹理，避免 LLM 生成与戒断任务无关的机械生活场景
LIFE_TEXTURES_BY_JOB = {
    "J1": [
        "睡前还是忍不住点开TA的动态",
        "发现TA换了头像、反复放大看",
        "共同好友的点赞提醒又弹出来",
        "卸载了APP又偷偷装回来",
    ],
    "J2": [
        "深夜编辑好一条消息又删掉",
        "删了联系方式又偷偷翻聊天记录",
        "路过TA常去的店、想发消息",
        "喝了点酒、手指开始不听话",
    ],
    "J3": [
        "凌晨两三点醒来、脑子里全是TA",
        "一个人回家、楼道灯亮着没人等",
        "雨天/节日情绪格外重",
        "连续几天没睡好、白天恍惚",
    ],
    "J4": [
        "一首歌把回忆全勾起来",
        "反复想「如果当初…」停不下来",
        "翻聊天记录翻到凌晨",
        "白天开会走神、脑子里全是TA",
    ],
    "J5": [
        "周末一个人不知道干嘛",
        "朋友都成双成对、自己插不上话",
        "生病时突然特别想被照顾",
        "深夜想找人说说话又怕打扰",
    ],
    "J6": [
        "照镜子觉得自己不值得被爱",
        "被问「最近怎么样」不知道答什么",
        "工作提不起劲、生活一团乱",
        "想开始运动/收拾房间又没力气",
    ],
    "J7": [
        "情绪崩溃时有闪过伤害自己的念头",
        "半夜哭到发抖、怕自己失控",
        "觉得活着没意义、但不敢说出口",
        "想找人求助又怕被当矫情",
    ],
}


def _life_textures_for(arch: dict) -> list[str]:
    job = (arch.get("jtbd") or {}).get("job_id") or ""
    return LIFE_TEXTURES_BY_JOB.get(job, LIFE_TEXTURES_DEFAULT)



@dataclass
class PersonaBlueprint:
    """单个生成槽位：只约束 Job/角色骨架，不携带预设故事正文。"""

    slot_index: int
    persona_id: str
    job_id: str
    segment: str
    role_hint: str
    subject_hint: str
    entry_situation: str
    job_owner: str
    stage: str
    patient_severity: str
    current_step_id: str
    desired_outcome_ids: List[str]
    dominant_factor_hints: List[str]
    force_hints: Dict[str, List[str]] = field(default_factory=dict)
    city_tier: str = "二线城市"
    occupation_hint: str = "服务业"
    life_texture: str = ""
    creativity_seed: str = ""

    def to_prompt_dict(self) -> dict:
        return {
            "slot_index": self.slot_index,
            "persona_id": self.persona_id,
            "job_id": self.job_id,
            "segment": self.segment,
            "role_hint": self.role_hint,
            "subject_hint": self.subject_hint,
            "entry_situation": self.entry_situation,
            "job_owner": self.job_owner,
            "stage": self.stage,
            "patient_severity": self.patient_severity,
            "current_step_id": self.current_step_id,
            "desired_outcome_ids": self.desired_outcome_ids,
            "dominant_factor_hints": self.dominant_factor_hints,
            "force_hints": self.force_hints,
            "city_tier": self.city_tier,
            "occupation_hint": self.occupation_hint,
            "life_texture": self.life_texture,
            "creativity_seed": self.creativity_seed,
        }


def archetype_seed_names() -> set[str]:
    return {a.get("seed_name", "") for a in PERSONA_ARCHETYPES if a.get("seed_name")}


def build_blueprints(
    count: int,
    *,
    job_ids: Optional[List[str]] = None,
    entry_situations: Optional[List[str]] = None,
) -> List[PersonaBlueprint]:
    """按 Job 轮询分配结构槽；人口学与具体故事留给 LLM 随机创造。"""
    archetypes = pick_archetypes(
        count, job_ids=job_ids, entry_situations=entry_situations
    )
    rng = random.Random(secrets.token_hex(8))
    blueprints: List[PersonaBlueprint] = []

    for i, arch in enumerate(archetypes[:count]):
        jt = arch.get("jtbd") or {}
        forces = jt.get("forces") or {}
        blueprints.append(
            PersonaBlueprint(
                slot_index=i + 1,
                persona_id=f"P{i + 1:02d}" if i + 1 < 100 else f"P{i + 1:03d}",
                job_id=jt.get("job_id", ""),
                segment=arch.get("segment", ""),
                role_hint=arch.get("role", ""),
                subject_hint=arch.get("subject", ""),
                entry_situation=jt.get("entry_situation", ""),
                job_owner=jt.get("job_owner", ""),
                stage=arch.get("stage", "应激期"),
                patient_severity=arch.get("patient_severity", "无"),
                current_step_id=jt.get("current_step_id", ""),
                desired_outcome_ids=list(jt.get("desired_outcome_ids") or [])[:5],
                dominant_factor_hints=list(arch.get("dominant") or [])[:4],
                force_hints={
                    "push": list(forces.get("push") or []),
                    "pull": list(forces.get("pull") or []),
                    "anxiety": list(forces.get("anxiety") or []),
                    "habit_or_alternative": list(forces.get("habit_or_alternative") or []),
                },
                city_tier=rng.choice(CITY_TIERS),
                occupation_hint=rng.choice(OCCUPATION_HINTS),
                life_texture=rng.choice(_life_textures_for(arch)),
                creativity_seed=secrets.token_hex(4),
            )
        )
    return blueprints
