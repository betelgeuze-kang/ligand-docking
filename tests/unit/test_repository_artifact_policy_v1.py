from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_repository_artifact_policy_v1",
    ROOT / "tools/check_repository_artifact_policy_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path, *, existing_wheel: bool = False) -> tuple[Path, str, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    if existing_wheel:
        (root / "legacy.whl").write_bytes(b"existing")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    base = _git(root, "rev-parse", "HEAD")
    policy = json.loads(
        (ROOT / "config/repository_artifact_policy_v1.json").read_text(encoding="utf-8")
    )
    policy_path = root / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return root, base, policy_path


def _commit(root: Path) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "change")
    return _git(root, "rev-parse", "HEAD")


def test_small_source_file_passes(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path)
    (root / "src.py").write_text("print('ok')\n", encoding="utf-8")
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["passed"] is True
    assert result["violation_count"] == 0


def test_new_wheel_is_rejected(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path)
    (root / "engine.whl").write_bytes(b"wheel")
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["passed"] is False
    assert result["violations"][0]["reason"] == "binary_or_archive_suffix_forbidden"


def test_existing_history_is_not_reinterpreted(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path, existing_wheel=True)
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["passed"] is True
    assert result["history_rewrite_performed"] is False


def test_large_new_file_is_rejected(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path)
    (root / "large.txt").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["violations"][0]["reason"] == "changed_file_too_large"


def test_large_generated_html_is_rejected_at_smaller_limit(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path)
    (root / "report.html").write_bytes(b"x" * (262144 + 1))
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["violations"][0]["reason"] == "generated_text_too_large"


def test_generated_directory_is_rejected(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path)
    (root / "runs").mkdir()
    (root / "runs/result.json").write_text("{}\n", encoding="utf-8")
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["violations"][0]["reason"] == "forbidden_generated_path_prefix"


def test_changed_symlink_is_rejected(tmp_path: Path) -> None:
    root, base, policy = _repo(tmp_path)
    os.symlink("README.md", root / "alias")
    head = _commit(root)
    result = MODULE.evaluate(root, base=base, head=head, policy_path=policy)
    assert result["violations"][0]["reason"] == "changed_symlink_forbidden"
