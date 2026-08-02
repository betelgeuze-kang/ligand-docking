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
    assert summary["platform_reproducibility_ready"] is True
    assert summary["reproducibility_ready"] is True
    assert summary["command_set_passed"] is True
    assert summary["linux_receipt"] is True
    assert summary["windows_receipt"] is False
    assert summary["ai_verify_passed"] is True
    assert summary["pytest_command_set_passed"] is True
    assert summary["blocker_count"] == 0
    assert summary["primary_blocker"] == ""
    assert summary["primary_required_action"] == ""
    assert summary["platform_evidence_required_field_count"] == 9
    assert summary["platform_evidence_ready_field_count"] == 9
    assert summary["platform_evidence_blocked_field_count"] == 0
    assert summary["platform_evidence_primary_field_id"] == ""
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert all(
        row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        and row["claim_promotion_allowed"] is False
        for row in payload["platform_evidence_requirement_rows"]
    )


def test_platform_reproducibility_receipt_accepts_windows_git_bash_system_names(
    tmp_path: Path,
) -> None:
    ai_verify = tmp_path / ".betelgeuze/developer_preview_windows_ai_verify.log"
    junit = tmp_path / ".betelgeuze/developer_preview_windows_reproducibility_pytest.xml"
    _write_ai_verify(ai_verify)
    _write_junit(junit)

    for observed_system in ("MSYS_NT-10.0-22631", "MINGW64_NT-10.0-22631"):
        payload = mod.build_developer_preview_platform_reproducibility_receipt(
            platform_id="windows",
            ai_verify_log=ai_verify,
            pytest_junit_xml=junit,
            observed_system=observed_system,
            root=tmp_path,
        )
        summary = payload["summary"]

        assert summary["status"] == "developer_preview_platform_reproducibility_receipt_ready"
        assert summary["platform_reproducibility_ready"] is True
        assert summary["reproducibility_ready"] is True
        assert summary["command_set_passed"] is True
        assert summary["linux_receipt"] is False
        assert summary["windows_receipt"] is True
        assert summary["platform_match"] is True
        assert summary["blocker_count"] == 0


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
    checklist = {
        row["field_id"]: row for row in payload["platform_evidence_requirement_rows"]
    }

    assert summary["status"] == "blocked_developer_preview_platform_reproducibility_receipt"
    assert summary["platform_reproducibility_ready"] is False
    assert summary["reproducibility_ready"] is False
    assert summary["command_set_passed"] is False
    assert summary["linux_receipt"] is False
    assert summary["ai_verify_passed"] is False
    assert summary["pytest_command_set_passed"] is False
    assert summary["platform_evidence_required_field_ids"] == [
        "platform_supported",
        "ai_verify_log_present",
        "ai_verify_passed",
        "pytest_junit_present",
        "pytest_junit_parseable",
        "pytest_test_count_positive",
        "pytest_failure_count_zero",
        "pytest_error_count_zero",
        "platform_matches_expected",
    ]
    assert summary["platform_evidence_required_field_count"] == 9
    assert summary["platform_evidence_ready_field_count"] == 6
    assert summary["platform_evidence_blocked_field_count"] == 3
    assert summary["platform_evidence_primary_field_id"] == "ai_verify_passed"
    assert summary["platform_evidence_primary_blocker"] == "ai_verify_not_passed"
    assert summary["platform_evidence_primary_required_action"] == (
        "Re-run ai-verify on this platform until the log records verify ok."
    )
    assert (
        summary["primary_blocker"]
        == ".betelgeuze/developer_preview_linux_ai_verify.log:verify_ok_missing"
    )
    assert summary["primary_required_action"] == summary[
        "platform_evidence_primary_required_action"
    ]
    assert summary["next_required_step"] == summary["primary_required_action"]
    assert "verify_ok_missing" in blockers
    assert "failure_count_nonzero" in blockers
    assert "platform_mismatch" in blockers
    assert checklist["platform_supported"]["status"] == "pass"
    assert checklist["ai_verify_log_present"]["status"] == "pass"
    assert checklist["ai_verify_passed"]["status"] == "blocked"
    assert checklist["pytest_failure_count_zero"]["status"] == "blocked"
    assert checklist["platform_matches_expected"]["observed"] == (
        "expected=linux;observed=Windows"
    )


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
    assert "Platform Evidence Checklist" in out_md.read_text(encoding="utf-8")


def test_platform_reproducibility_receipt_cli_allow_blocked_writes_fail_closed_outputs(
    tmp_path: Path,
) -> None:
    out_json = tmp_path / ".betelgeuze/developer_preview_windows_reproducibility_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_windows_reproducibility_receipt.md"

    assert mod.main(
        [
            "--platform",
            "windows",
            "--ai-verify-log",
            str(tmp_path / ".betelgeuze/missing_windows_ai_verify.log"),
            "--pytest-junit-xml",
            str(tmp_path / ".betelgeuze/missing_windows_pytest.xml"),
            "--allow-blocked",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_developer_preview_platform_reproducibility_receipt"
    assert payload["summary"]["windows_receipt"] is False
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert out_md.is_file()


def test_platform_reproducibility_receipt_uses_platform_specific_defaults() -> None:
    assert mod._default_ai_verify_log("linux") == ".betelgeuze/developer_preview_linux_ai_verify.log"
    assert mod._default_pytest_junit_xml("linux") == (
        ".betelgeuze/developer_preview_linux_reproducibility_pytest.xml"
    )
    assert mod._default_out_json("linux") == (
        ".betelgeuze/developer_preview_linux_reproducibility_receipt.json"
    )
    assert mod._default_ai_verify_log("windows") == ".betelgeuze/developer_preview_windows_ai_verify.log"
    assert mod._default_pytest_junit_xml("windows") == (
        ".betelgeuze/developer_preview_windows_reproducibility_pytest.xml"
    )
    assert mod._default_out_json("windows") == (
        ".betelgeuze/developer_preview_windows_reproducibility_receipt.json"
    )
