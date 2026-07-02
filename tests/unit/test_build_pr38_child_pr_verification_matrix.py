from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_child_pr_verification_matrix as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _acceptance_payload(*, missing_focused_test: bool = False) -> dict[str, object]:
    return {
        "summary": {
            "status": "pr38_split_acceptance_packet_ready",
            "split_acceptance_ready": True,
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "f2g_f2h_preflight",
                "changed_file_count": 5,
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest f2g",
                "claim_boundary": "No G1 claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 2,
                "slice_id": "public_benchmark_phase2",
                "changed_file_count": 14,
                "integration_touchpoint_count": 0,
                "focused_test_command": "" if missing_focused_test else "pytest benchmark",
                "claim_boundary": "No benchmark claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 3,
                "slice_id": "source_of_truth_refresh",
                "changed_file_count": 8,
                "integration_touchpoint_count": 5,
                "focused_test_command": "pytest source",
                "claim_boundary": "No paid-pilot claim.",
                "slice_acceptance_ready": True,
            },
        ],
    }


def test_verification_matrix_requires_focused_tests_ai_verify_and_claim_review(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    _write_json(acceptance, _acceptance_payload())

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "pr38_child_pr_verification_matrix_ready"
    assert summary["verification_matrix_ready"] is True
    assert summary["focused_test_required_count"] == 3
    assert summary["ai_verify_required_count"] == 3
    assert summary["product_mode_required_count"] == 2
    assert summary["hunk_split_review_required_count"] == 1
    assert summary["paid_pilot_wording_allowed"] is False
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["f2g_f2h_preflight"]["product_mode_required"] is False
    assert rows["public_benchmark_phase2"]["product_mode_required"] is True
    assert rows["source_of_truth_refresh"]["hunk_split_review_required"] is True
    assert rows["source_of_truth_refresh"]["child_pr_verification_matrix_ready"] is True
    assert rows["public_benchmark_phase2"]["product_mode_expected_blockers"] == mod.KNOWN_PRODUCT_MODE_BLOCKERS


def test_verification_matrix_blocks_missing_focused_test_command(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    _write_json(acceptance, _acceptance_payload(missing_focused_test=True))

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_child_pr_verification_matrix"
    assert payload["summary"]["verification_matrix_ready"] is False
    assert payload["summary"]["blocked_slice_ids"] == ["public_benchmark_phase2"]
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["public_benchmark_phase2"]["verification_blockers"] == ["focused_test_command_missing"]


def test_main_writes_verification_matrix_artifacts(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    _write_json(acceptance, _acceptance_payload())
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--acceptance-packet-json",
            str(acceptance),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "pr38_child_pr_verification_matrix_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["slice_id"] for row in rows] == [
        "f2g_f2h_preflight",
        "public_benchmark_phase2",
        "source_of_truth_refresh",
    ]
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Child PR Verification Matrix")
