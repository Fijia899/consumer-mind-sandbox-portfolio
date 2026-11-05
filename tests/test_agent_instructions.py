from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_consumer_sandbox_scope_is_tourism_intent_audience():
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "当前消费者沙盘观察对象为旅游意向人群。" in instructions
    assert "后续新增或修改消费者沙盘相关内容时" in instructions
    assert "后续说明和产出不得提及此前使用过的消费者人群。" in instructions
