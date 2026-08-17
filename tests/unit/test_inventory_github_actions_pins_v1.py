from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "actions_inventory", ROOT / "tools/inventory_github_actions_pins_v1.py"
)
assert SPEC is not None and SPEC.loader is not None
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def test_inventory_classifies_pins_and_risk_contexts(tmp_path: Path) -> None:
    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("""
on:
  pull_request_target:
jobs:
  test:
    runs-on: [self-hosted, linux]
    steps:
      - uses: actions/checkout@1234567890123456789012345678901234567890
      - uses: actions/setup-python@v6
      - uses: ./local-action
      - uses: docker://alpine@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      - uses: actions/checkout@1234567890123456789012345678901234567890
        with:
          sparse-checkout: src
""")
    report = A.inspect(tmp_path)
    row = report["workflows"][0]
    assert row["pull_request_target"] is True
    assert row["self_hosted"] is True
    assert row["sparse_checkout"] is True
    assert row["mutable_remote_count"] == 1
    assert report["mutable_remote_total"] == 1
