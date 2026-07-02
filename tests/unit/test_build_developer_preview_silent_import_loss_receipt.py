from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_developer_preview_silent_import_loss_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_junit(path: Path, *, tests: int = 7, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            f'<testsuite name="developer-preview-import-cli" tests="{tests}" '
            f'failures="{failures}" errors="{errors}" skipped="{skipped}">'
            '<testcase classname="import" name="surface"/>'
            "</testsuite>"
        ),
        encoding="utf-8",
    )


def _write_matrix(path: Path, *, ready: bool = True, blockers: int = 0) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "product_capability_matrix_verified"
                if ready
                else "blocked_product_capability_matrix",
                "capability_matrix_ready": ready,
                "blocker_count": blockers,
            },
            "rows": [
                {
                    "check": "matrix_has_capabilities",
                    "status": "pass" if ready else "blocked",
                    "observed": "missing=none" if ready else "missing=api_surface",
                }
            ],
        },
    )


def test_developer_preview_silent_import_loss_receipt_ready(tmp_path: Path) -> None:
    junit = tmp_path / ".betelgeuze/developer_preview_import_cli_tests.xml"
    matrix = tmp_path / ".betelgeuze/developer_preview_capability_matrix.json"
    _write_junit(junit, skipped=1)
    _write_matrix(matrix)

    payload = mod.build_developer_preview_silent_import_loss_receipt(
        junit_xml=junit,
        capability_matrix_json=matrix,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "developer_preview_silent_import_loss_receipt_ready"
    assert summary["import_cli_tests_passed"] is True
    assert summary["capability_matrix_checked"] is True
    assert summary["silent_import_loss_zero"] is True
    assert summary["blocker_count"] == 0
    assert summary["missing_required_surface_count"] == 0
    assert summary["unimportable_required_surface_count"] == 0
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_developer_preview_silent_import_loss_receipt_blocks_failed_inputs(tmp_path: Path) -> None:
    junit = tmp_path / ".betelgeuze/developer_preview_import_cli_tests.xml"
    matrix = tmp_path / ".betelgeuze/developer_preview_capability_matrix.json"
    _write_junit(junit, failures=1)
    _write_matrix(matrix, ready=False, blockers=1)

    payload = mod.build_developer_preview_silent_import_loss_receipt(
        junit_xml=junit,
        capability_matrix_json=matrix,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_developer_preview_silent_import_loss_receipt"
    assert summary["import_cli_tests_passed"] is False
    assert summary["capability_matrix_checked"] is True
    assert summary["silent_import_loss_zero"] is False
    assert summary["missing_required_surface_count"] == 1
    assert "failure_count_nonzero" in ";".join(summary["blockers"])
    assert "capability_matrix_ready_not_true" in ";".join(summary["blockers"])


def test_developer_preview_silent_import_loss_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    junit = tmp_path / ".betelgeuze/developer_preview_import_cli_tests.xml"
    matrix = tmp_path / ".betelgeuze/developer_preview_capability_matrix.json"
    out_json = tmp_path / ".betelgeuze/developer_preview_silent_import_loss_receipt.json"
    out_md = tmp_path / ".betelgeuze/developer_preview_silent_import_loss_receipt.md"
    _write_junit(junit)
    _write_matrix(matrix)

    assert mod.main(
        [
            "--junit-xml",
            str(junit),
            "--capability-matrix-json",
            str(matrix),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "developer_preview_silent_import_loss_receipt"
    assert "Developer Preview Silent Import Loss Receipt" in out_md.read_text(encoding="utf-8")
