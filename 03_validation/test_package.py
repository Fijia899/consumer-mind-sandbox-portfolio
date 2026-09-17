from pathlib import Path
import hashlib


ROOT = Path(__file__).resolve().parents[1]


def test_bp_is_included_and_matches_user_file():
    bp = ROOT / "01_BP" / "消费者心智沙盘_BP.pptx"
    assert bp.is_file()
    assert hashlib.sha256(bp.read_bytes()).hexdigest() == (
        "86c9d274b339e91f15a501c1d4a741a0c732229e88fa2c"
        "fdf13a0054005259b9"
    )


def test_package_does_not_include_upstream_git_metadata():
    assert (ROOT / ".git").is_dir()
    assert not any((ROOT / ".git" / "objects" / "pack").glob("*"))
    assert not any(ROOT.rglob("node_modules"))


def test_package_has_attribution_and_implementation_delta():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "github.com/" not in readme
    assert "上游" not in readme
    assert (ROOT / "02_implementation_delta").is_dir()
