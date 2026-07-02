from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_platform_reproducibility_receipt as mod


def _write_junit(path: Path, *, tests: int = 4, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            f'<testsuite name="developer-preview-platform" tests="{tests}" '
            f'failures="{failures}" errors="{errors}" skipped="{skipped}">'
            '<testcase classname="platform" name="readiness"/>'
            "</testsuite>"
        ),
        encoding="utf-8",
    )


def _write_ai_verify(path: Path, *, ok: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "==> python syntax smoke\nverify ok (smoke)\n" if ok else "verify failed\n"
    path.write_text(text, encoding="utf-8")


def test_platform_reproducibility_receipt_ready_for_linux(tmp_path: Path) -> None:
    ai_verify = tmp_path / ".betelgeuze/developer_preview_linux_ai_verify.log"
    junit = tmp_path / ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml"
    _write_ai_verify(ai_verify)
    _write_junit(junit, skipped=1)

    payload = mod.build_developer_preview_platform_reproducibility_receipt(
        platform_id="linux",
        ai_verify_log=ai_verify,
        pytest_junit_xml=junit,
        observed_system="Linux",
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_platform_reproducibility_receipt_ready"
    assert summary["command_set_passed"] is True
    assert summary["linux_receipt"] is True
    assert summary["windows_receipt"] is False
    assert summary["ai_verify_passed"] is True
    assert summary["pytest_command_set_passed"] is True
    assert summary["blocker_count"] == 0
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_platform_reproducibility_receipt_blocks_failed_inputs(tmp_path: Path) -> None:
    ai_verify = tmp_path / ".betelgeuze/developer_preview_linux_ai_verify.log"
    junit = tmp_path / ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml"
    _write_ai_verify(ai_verify, ok=False)
    _write_junit(junit, failures=1)

    payload = mod.build_developer_preview_platform_reproducibility_receipt(
        platform_id="linux",
        ai_verify_log=ai_verify,
        pytest_junit_xml=junit,
        observed_system="Windows",
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])

    assert summary["status"] == "blocked_developer_preview_platform_reproducibility_receipt"
    assert summary["command_set_passed"] is False
    assert summary["linux_receipt"] is False
    assert summary["ai_verify_passed"] is False
    assert summary["pytest_command_set_passed"] is False
    assert "verify_ok_missing" in blockers
    assert "failure_count_nonzero" in blockers
    assert "platform_mismatch" in blockers


def test_platform_reproducibility_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    ai_verify = tmp_path / ".betelgeuze/developer_preview_linux_ai_verify.log"
    junit = tmp_path / ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml"
    out_json = tmp_path / ".betelgeuze/developer_preview_linux_reproducibility_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_linux_reproducibility_receipt.md"
    _write_ai_verify(ai_verify)
    _write_junit(junit)

    assert mod.main(
        [
            "--platform",
            "linux",
            "--ai-verify-log",
            str(ai_verify),
            "--pytest-junit-xml",
            str(junit),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_platform_reproducibility_receipt"
    assert "Developer Preview Platform Reproducibility Receipt" in out_md.read_text(encoding="utf-8")
