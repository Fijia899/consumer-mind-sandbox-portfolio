"""24 transparent, distinct travel scenario assumptions; not population samples."""
from copy import deepcopy

GROUPS = [
    ("亲子短途", "带孩子的周末出游", [("儿童友好住宿与设施", True), ("每日保留休息时间", True)]),
    ("独自出行", "独自安排短途旅行", [("夜间到达提供安全接站", True), ("费用按单人明确报价", False)]),
    ("双人度假", "两人共同决定的休闲旅行", [("两人住宿与活动总价透明", True), ("留出可自行安排的时间", False)]),
    ("长辈同行", "与长辈共同出游", [("减少连续步行并提供休息点", True), ("住宿交通衔接清楚", False)]),
    ("无障碍出行", "需要无障碍支持的旅行", [("交通住宿及景点全程无障碍可达", True), ("明确可用的无障碍设施与协助", True)]),
    ("朋友结伴", "多人结伴协调行程", [("同行费用分摊和总价透明", True), ("允许活动分组与集合", False)]),
    ("自然探索", "自然体验为主的旅行", [("说明天气及路线变化的备选安排", True), ("保留自然体验时间而非密集购物", False)]),
    ("文化体验", "文化与在地体验旅行", [("提供可信的在地讲解与预约说明", False), ("保留深度体验而非走马观花", False)]),
]
VARIANTS = [
    ("预算明确", [("费用含税且不另收隐藏费用", True), ("出发前明确必付与自选项目", False)]),
    ("灵活调整", [("支持免费改期并明确适用条件", True), ("取消与退款规则清楚", False)]),
    ("轻松节奏", [("避免早出晚归和密集赶路", True), ("行程中有自由活动时间", False)]),
]


def all_profiles():
    output = []
    for g, (group, episode, basics) in enumerate(GROUPS):
        for v, (variant, extras) in enumerate(VARIANTS):
            output.append({"id": f"A{g+1:02d}{v+1}", "type": "archetype", "status": "reviewed", "revision": 1,
                "label": f"{group} · {variant}", "episode": episode,
                "summary": f"假设情境：{episode}，本次重点关注{variant}。不对应真实个人。",
                "dimensions": [group, variant], "weight_source": "原型等权；不是人口权重", "messages": [],
                "needs": [{"id": f"N{i+1}", "label": label, "kind": "assumption", "hard": hard, "evidence": []}
                          for i, (label, hard) in enumerate(basics + extras)],
                "unknowns": ["实际预算金额", "具体出发日期", "是否愿意预订"], "origin": "旅游决策维度组合假设 v1"})
    # Interleave party types before increasing scenario depth, for smaller cohorts.
    return deepcopy(sorted(output, key=lambda p: (p["id"][-1], p["id"])))
