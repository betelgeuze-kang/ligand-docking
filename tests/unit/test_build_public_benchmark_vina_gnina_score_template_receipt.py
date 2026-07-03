from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_public_benchmark_vina_gnina_score_template_receipt as mod
from tools.product.build_public_benchmark_vina_gnina_comparison_work_order import APPROVAL_TOKEN


FIELDS = [
    "pose_id",
    "complex_id",
    "vina_score",
    "gnina_score",
    "comparison_score_source",
    "comparison_score_artifact_path",
    "comparison_score_artifact_sha256",
    "operator_engine_versions",
    "operator_prep_policy_sha256",
    "operator_method",
    "operator_reviewed_at_utc",
    "operator_id",
    "license_ok",
    "approval_token",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": payload}, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _work_order(path: Path, *, row_count: int = 2) -> None:
    _write_json(
        path,
        {
            "status": "public_benchmark_vina_gnina_comparison_work_order_ready",
            "work_order_ready": True,
            "pose_row_count": row_count,
            "score_template_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
            "adapter_command_after_fill": (
                "python3 tools/build_pdbbind_casf_pose_affinity_results.py "
                "--comparison-scores-csv runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
            ),
        },
    )


def _ready_row(pose_id: str) -> dict[str, str]:
    return {
        "pose_id": pose_id,
        "complex_id": pose_id.split("_", 1)[0],
        "vina_score": "-7.4",
        "gnina_score": "-8.1",
        "comparison_score_source": "local_same_input_replay",
        "comparison_score_artifact_path": "runs/local_scores.json",
        "comparison_score_artifact_sha256": "a" * 64,
        "operator_engine_versions": "vina=1.2.5;gnina=1.1",
        "operator_prep_policy_sha256": "b" * 64,
        "operator_method": "same receptor, ligand, pose, protonation, and box inputs",
        "operator_reviewed_at_utc": "2026-07-02T00:00:00Z",
        "operator_id": "operator-a",
        "license_ok": "true",
        "approval_token": APPROVAL_TOKEN,
    }


def test_vina_gnina_score_template_receipt_ready_when_all_rows_reviewed(tmp_path: Path) -> None:
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    _work_order(work_order)
    _write_csv(template, [_ready_row("1abc_pose_001"), _ready_row("2def_pose_001")])

    payload = mod.build_public_benchmark_vina_gnina_score_template_receipt(
        work_order_json=work_order,
        score_template_csv=template,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "public_benchmark_vina_gnina_score_template_receipt_ready"
    assert summary["score_template_receipt_ready"] is True
    assert summary["comparison_score_evidence_ready"] is True
    assert summary["score_template_row_count"] == 2
    assert summary["score_template_filled_score_row_count"] == 2
    assert summary["pending_field_count"] == 0
    assert summary["pending_field_counts"] == {}
    assert summary["score_evidence_required_field_count"] == 12
    assert summary["score_evidence_ready_field_count"] == 12
    assert summary["score_evidence_blocked_field_count"] == 0
    assert summary["score_evidence_primary_field_id"] == ""
    assert summary["score_evidence_primary_pending_row_count"] == 0
    assert summary["blocker_count"] == 0
    assert summary["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert {row["status"] for row in payload["rows"]} == {"ready"}
    assert all(
        row["status"] == "pass"
        and row["operator_action_required"] is False
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        and row["claim_promotion_allowed"] is False
        for row in payload["score_evidence_field_rows"]
    )


def test_vina_gnina_score_template_receipt_blocks_empty_operator_template(tmp_path: Path) -> None:
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    _work_order(work_order)
    row = _ready_row("1abc_pose_001")
    for field in ("vina_score", "gnina_score", "operator_reviewed_at_utc", "operator_id", "license_ok", "approval_token"):
        row[field] = ""
    row["comparison_score_source"] = "OPERATOR_FILL_SAME_INPUT_VINA_GNINA_SCORE_SOURCE"
    row["comparison_score_artifact_path"] = "OPERATOR_FILL_LOCAL_SCORE_ARTIFACT"
    _write_csv(template, [row])

    payload = mod.build_public_benchmark_vina_gnina_score_template_receipt(
        work_order_json=work_order,
        score_template_csv=template,
        root=tmp_path,
    )
    summary = payload["summary"]
    blockers = ";".join(summary["blockers"])
    field_rows = {row["field_id"]: row for row in payload["score_evidence_field_rows"]}

    assert summary["status"] == "blocked_public_benchmark_vina_gnina_score_template_receipt"
    assert summary["score_template_receipt_ready"] is False
    assert summary["score_value_pending_count"] == 2
    assert summary["operator_placeholder_pending_count"] == 2
    assert summary["pending_field_counts"]["vina_score"] == 1
    assert summary["pending_field_counts"]["gnina_score"] == 1
    assert summary["pending_field_counts"]["approval_token"] == 1
    assert summary["score_evidence_required_field_ids"] == [
        "vina_score",
        "gnina_score",
        "comparison_score_source",
        "comparison_score_artifact_path",
        "comparison_score_artifact_sha256",
        "operator_engine_versions",
        "operator_prep_policy_sha256",
        "operator_method",
        "operator_reviewed_at_utc",
        "operator_id",
        "license_ok",
        "approval_token",
    ]
    assert summary["score_evidence_required_field_count"] == 12
    assert summary["score_evidence_ready_field_count"] == 4
    assert summary["score_evidence_blocked_field_count"] == 8
    assert summary["score_evidence_primary_field_id"] == "vina_score"
    assert summary["score_evidence_primary_pending_row_count"] == 1
    assert summary["score_evidence_primary_required_action"] == (
        "Fill numeric vina_score values from the same-input engine replay for every pending pose."
    )
    assert "same_input_score_values_pending" in blockers
    assert "approval_token_pending" in blockers
    assert payload["rows"][0]["status"] == "blocked"
    assert "vina_score" in payload["rows"][0]["missing_fields"]
    assert "approval_token" in payload["rows"][0]["missing_fields"]
    assert field_rows["vina_score"]["status"] == "blocked"
    assert field_rows["vina_score"]["pending_row_count"] == 1
    assert field_rows["comparison_score_artifact_sha256"]["status"] == "pass"
    assert field_rows["approval_token"]["required_action"] == (
        f"Fill approval_token with {APPROVAL_TOKEN} after operator review."
    )


def test_vina_gnina_score_template_receipt_blocks_row_count_mismatch(tmp_path: Path) -> None:
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    _work_order(work_order, row_count=2)
    _write_csv(template, [_ready_row("1abc_pose_001")])

    payload = mod.build_public_benchmark_vina_gnina_score_template_receipt(
        work_order_json=work_order,
        score_template_csv=template,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_public_benchmark_vina_gnina_score_template_receipt"
    assert summary["score_template_row_count_match"] is False
    assert "score_template_row_count_mismatch" in summary["blockers"]


def test_vina_gnina_score_template_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    out_json = tmp_path / "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    out_csv = tmp_path / "runs/public_benchmark_vina_gnina_score_template_receipt_current.csv"
    out_md = tmp_path / "runs/public_benchmark_vina_gnina_score_template_receipt_current.md"
    _work_order(work_order)
    _write_csv(template, [_ready_row("1abc_pose_001"), _ready_row("2def_pose_001")])

    assert mod.main(
        [
            "--work-order-json",
            str(work_order),
            "--score-template-csv",
            str(template),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "public_benchmark_vina_gnina_score_template_receipt"
    assert out_csv.read_text(encoding="utf-8").startswith("pose_id,complex_id,status,")
    assert "Public Benchmark Vina/GNINA Score Template Receipt" in out_md.read_text(encoding="utf-8")
    assert "Score Evidence Field Checklist" in out_md.read_text(encoding="utf-8")
