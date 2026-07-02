from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_public_benchmark_vina_gnina_comparison_work_order as mod


def _write_results(path: Path, *, contract_ready: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "pdbbind_casf_pose_affinity_results_ready",
                    "pose_count": 4,
                    "subset_pose_file_names": ["1abc_001", "1abc_002", "2def_003", "2def_004"],
                    "subset_identity_sha256": "subset-sha",
                    "vina_gnina_comparison_adapter_contract_ready": contract_ready,
                }
            }
        ),
        encoding="utf-8",
    )


def test_public_benchmark_vina_gnina_work_order_builds_same_input_template(tmp_path: Path) -> None:
    results_json = tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json"
    out_csv = tmp_path / "runs/scores.csv"
    _write_results(results_json)

    payload = mod.build_public_benchmark_vina_gnina_comparison_work_order(
        results_json=results_json,
        out_csv=out_csv,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "public_benchmark_vina_gnina_comparison_work_order_ready"
    assert summary["work_order_ready"] is True
    assert summary["same_input_score_template_ready"] is True
    assert summary["comparison_score_evidence_ready"] is False
    assert summary["score_template_validation_ready"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["pose_row_count"] == 4
    assert summary["complex_count"] == 2
    assert summary["score_value_pending_count"] == 8
    assert summary["score_template_filled_score_row_count"] == 0
    assert summary["operator_metadata_pending_count"] == 8
    assert summary["operator_placeholder_pending_count"] == 24
    assert summary["license_ok_pending_count"] == 4
    assert summary["approval_token_pending_count"] == 4
    assert "same_input_score_values_pending" in summary["score_template_blockers"]
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert "tools/build_pdbbind_casf_pose_affinity_results.py" in summary["adapter_command_after_fill"]
    assert rows[0]["pose_id"] == "1abc_001"
    assert rows[0]["complex_id"] == "1abc"
    assert "vina_score" in rows[0]
    assert "gnina_score" in rows[0]
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_public_benchmark_vina_gnina_score_template_validation_accepts_filled_rows() -> None:
    validation = mod.validate_vina_gnina_score_template(
        [
            {
                "pose_id": "1abc_001",
                "complex_id": "1abc",
                "vina_score": "-8.4",
                "gnina_score": "-8.7",
                "comparison_score_source": "operator_local_same_input_replay",
                "comparison_score_artifact_path": "runs/operator/vina_gnina_scores.json",
                "comparison_score_artifact_sha256": "abc123",
                "operator_engine_versions": "vina=1.2.5;gnina=1.3",
                "operator_prep_policy_sha256": "prep123",
                "operator_method": "same-input local replay",
                "operator_reviewed_at_utc": "2026-07-03T00:00:00Z",
                "operator_id": "operator",
                "license_ok": "true",
                "approval_token": mod.APPROVAL_TOKEN,
            }
        ]
    )

    assert validation["score_template_validation_ready"] is True
    assert validation["score_template_filled_score_row_count"] == 1
    assert validation["score_value_pending_count"] == 0
    assert validation["operator_metadata_pending_count"] == 0
    assert validation["operator_placeholder_pending_count"] == 0
    assert validation["license_ok_pending_count"] == 0
    assert validation["approval_token_pending_count"] == 0
    assert validation["score_template_blockers"] == []


def test_public_benchmark_vina_gnina_work_order_blocks_missing_contract(tmp_path: Path) -> None:
    results_json = tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json"
    _write_results(results_json, contract_ready=False)

    payload = mod.build_public_benchmark_vina_gnina_comparison_work_order(
        results_json=results_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_public_benchmark_vina_gnina_comparison_work_order"
    assert summary["work_order_ready"] is False
    assert summary["blockers"] == ["comparison_adapter_contract_not_ready"]


def test_public_benchmark_vina_gnina_work_order_cli_writes_outputs(tmp_path: Path) -> None:
    results_json = tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json"
    out_json = tmp_path / "runs/work_order.json"
    out_csv = tmp_path / "runs/scores.csv"
    out_md = tmp_path / "runs/work_order.md"
    _write_results(results_json)

    assert mod.main(
        [
            "--results-json",
            str(results_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["summary"]["status"] == "public_benchmark_vina_gnina_comparison_work_order_ready"
    with out_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert rows[0]["comparison_score_source"] == "OPERATOR_FILL_SAME_INPUT_VINA_GNINA_SCORE_SOURCE"
    assert "Public Benchmark Vina/GNINA Comparison Work Order" in out_md.read_text(encoding="utf-8")
