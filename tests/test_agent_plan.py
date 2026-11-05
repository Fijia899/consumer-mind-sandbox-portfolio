"""Check the proposal's navigable implementation references and research baseline."""
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLANS = sorted((ROOT / "docs").glob("agent-upgrade-plan-v*-20261103.md"))


def test_upgrade_plan_and_readme_local_links_resolve():
    assert len(PLANS) >= 2
    for document in (*sorted((ROOT / "docs").glob("agent-*.md")), ROOT / "README.md"):
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8"))
        assert links, f"No navigable references in {document.name}"
        for target in links:
            if "://" in target or target.startswith("#"):
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            assert path.is_relative_to(ROOT), f"Reference escapes project: {target}"
            assert path.is_file(), f"Missing referenced implementation or document: {target}"


@pytest.mark.parametrize("plan", PLANS, ids=lambda path: path.stem)
def test_upgrade_plan_research_revision_matches_documented_project_baseline(plan):
    pattern = r"\b[0-9a-f]{40}\b"
    plan_revisions = set(re.findall(pattern, plan.read_text(encoding="utf-8")))
    project_revisions = set(re.findall(pattern, (ROOT / "README.md").read_text(encoding="utf-8")))
    assert plan_revisions
    assert plan_revisions <= project_revisions
