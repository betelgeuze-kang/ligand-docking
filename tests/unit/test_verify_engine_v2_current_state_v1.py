from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_engine_v2_current_state_v1",
    ROOT / "tools/verify_engine_v2_current_state_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RENDERER = ROOT / "tools/render_engine_v2_current_state_v1.py"


def _write_minimal_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)

    registry = json.loads(
        (ROOT / "config/engine_v2_current_state_v1.json").read_text(encoding="utf-8")
    )
    (root / "config/engine_v2_current_state_v1.json").write_text(
        json.dumps(registry, sort_keys=True), encoding="utf-8"
    )
    (root / "docs/engine_v2_current_state_v1.md").write_text(
        MODULE.render_markdown(registry), encoding="utf-8"
    )
    (root / "docs/engine_v2_status.md").write_text(
        "ABI 1.21\nexactly-once-consumed native CPU qualification-v7\n",
        encoding="utf-8",
    )
    (root / "docs/engine_v2_stage0_status.md").write_text(
        "`BLIND_RUN_BLOCKED`\n| Fresh 128 executed | false |\n",
        encoding="utf-8",
    )
    (root / "docs/engine_v2_native_fixed64_cpu_qualification_v7_result.md").write_text(
        "terminal decision is `PASS`\nrecorded_pass_non_authoritative\n",
        encoding="utf-8",
    )
    (root / "config/independent_engine_v2_capabilities.yaml").write_text(
        "\n".join(f"{key}: false" for key in MODULE.FALSE_CLAIMS),
        encoding="utf-8",
    )
    return root


def test_repository_current_state_verifies() -> None:
    result = MODULE.verify_root(ROOT)
    assert result["verified"] is True
    assert result["claim_authority_granted"] is False
    assert result["implementation_stage"] == MODULE.IMPLEMENTATION_STAGE


def test_repository_document_is_the_exact_deterministic_render() -> None:
    registry = json.loads(
        (ROOT / "config/engine_v2_current_state_v1.json").read_text(encoding="utf-8")
    )
    document = (ROOT / "docs/engine_v2_current_state_v1.md").read_text(
        encoding="utf-8"
    )

    assert document == MODULE.render_markdown(registry)


def test_human_summary_drift_fails_closed(tmp_path: Path) -> None:
    root = _write_minimal_root(tmp_path)
    path = root / "docs/engine_v2_current_state_v1.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "manual edit\n", encoding="utf-8"
    )

    with pytest.raises(MODULE.CurrentStateError, match="exact rendered JSON summary"):
        MODULE.verify_root(root)


def test_crlf_summary_is_not_exact_byte_identity(tmp_path: Path) -> None:
    root = _write_minimal_root(tmp_path)
    path = root / "docs/engine_v2_current_state_v1.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    with pytest.raises(MODULE.CurrentStateError, match="exact rendered JSON summary"):
        MODULE.verify_root(root)

    checked = subprocess.run(
        [sys.executable, str(RENDERER), "--root", str(root), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 1
    assert "not the exact rendered JSON summary" in checked.stderr


def test_unrendered_registry_field_fails_closed(tmp_path: Path) -> None:
    root = _write_minimal_root(tmp_path)
    path = root / "config/engine_v2_current_state_v1.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry["claim_policy"]["unreviewed_new_claim"] = False
    path.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(MODULE.CurrentStateError, match="claim_policy keys changed"):
        MODULE.verify_root(root)


def test_fresh_execution_escalation_fails_closed(tmp_path: Path) -> None:
    root = _write_minimal_root(tmp_path)
    path = root / "config/engine_v2_current_state_v1.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry["evidence"]["fresh_128_executed"] = True
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(MODULE.CurrentStateError, match="fresh_128_executed"):
        MODULE.verify_root(root)


def test_claim_escalation_fails_closed(tmp_path: Path) -> None:
    root = _write_minimal_root(tmp_path)
    path = root / "config/engine_v2_current_state_v1.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry["claim_policy"]["docking_accuracy_claim_allowed"] = True
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(MODULE.CurrentStateError, match="docking_accuracy_claim_allowed"):
        MODULE.verify_root(root)


def test_missing_v7_result_marker_fails_closed(tmp_path: Path) -> None:
    root = _write_minimal_root(tmp_path)
    (root / "docs/engine_v2_native_fixed64_cpu_qualification_v7_result.md").write_text(
        "terminal decision unavailable\n", encoding="utf-8"
    )
    with pytest.raises(MODULE.CurrentStateError, match="terminal decision is"):
        MODULE.verify_root(root)
