from __future__ import annotations

import shutil
from pathlib import Path

from tools.product.github_action_pins import audit_all_action_pins


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
SETUP_PYTHON_V6_SHA = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"


def _copy_workflows(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(WORKFLOW_DIR, root / ".github" / "workflows")
    return root


def test_every_external_action_reference_is_pinned_to_a_full_sha() -> None:
    assert audit_all_action_pins(ROOT) == []


def test_unregistered_workflow_mutable_step_tag_is_rejected(tmp_path: Path) -> None:
    root = _copy_workflows(tmp_path)
    path = root / ".github" / "workflows" / "ci-engine-v2-ai.yml"
    source = path.read_text(encoding="utf-8")
    assert SETUP_PYTHON_V6_SHA in source
    path.write_text(source.replace(SETUP_PYTHON_V6_SHA, "actions/setup-python@v6", 1), encoding="utf-8")

    errors = audit_all_action_pins(root)

    assert any(
        error.endswith("action_not_sha_pinned:actions/setup-python@v6")
        and error.startswith("ci-engine-v2-ai.yml:ai-reference:")
        for error in errors
    )


def test_mutable_reusable_workflow_reference_is_rejected(tmp_path: Path) -> None:
    root = _copy_workflows(tmp_path)
    path = root / ".github" / "workflows" / "mutable-reusable.yml"
    path.write_text(
        "name: mutable-reusable\n"
        "on:\n"
        "  pull_request:\n"
        "jobs:\n"
        "  delegated:\n"
        "    uses: example/example/.github/workflows/ci.yml@v1\n",
        encoding="utf-8",
    )

    errors = audit_all_action_pins(root)

    assert errors == [
        "mutable-reusable.yml:delegated:job:action_not_sha_pinned:"
        "example/example/.github/workflows/ci.yml@v1"
    ]


def test_local_and_container_actions_are_outside_commit_pin_policy(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "local.yml").write_text(
        "name: local\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  local:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: ./actions/local\n"
        "      - uses: docker://python:3.11\n",
        encoding="utf-8",
    )

    assert audit_all_action_pins(root) == []
