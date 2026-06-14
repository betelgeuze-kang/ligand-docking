from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_claim_grade_gap_audit as mod


def _write_json(path: Path, summary: dict) -> None:
    path.write_text(json.dumps({"summary": summary}) + "\n", encoding="utf-8")


def _fixture_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "materialization": tmp_path / "materialization.json",
        "work_order": tmp_path / "statistical_work_order.json",
        "readiness": tmp_path / "metric_readiness.json",
        "templates": tmp_path / "metric_templates.json",
        "r4": tmp_path / "r4.json",
    }
    _write_json(
        paths["materialization"],
        {
            "free_energy_pair_count": 8,
            "free_energy_holdout_pair_count": 3,
            "free_energy_spearman_bootstrap_p05": -0.14285714285714285,
            "free_energy_spearman_bootstrap_p50": 0.6428571428571429,
            "free_energy_spearman_bootstrap_p95": 1.0,
            "claim_grade_public_benchmark_statistical_support_ready": False,
        },
    )
    _write_json(
        paths["work_order"],
        {
            "canonical_intake_promotion_allowed": False,
            "expansion_slot_count": 17,
            "holdout_expansion_slot_count": 5,
            "fit_or_holdout_expansion_slot_count": 12,
        },
    )
    _write_json(
        paths["readiness"],
        {
            "metric_materialization_row_count": 17,
            "coordinate_validation_pass_row_count": 0,
            "coordinate_validation_blocked_row_count": 17,
            "planned_metric_source_payload_count": 51,
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
                "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
            ),
        },
    )
    _write_json(
        paths["templates"],
        {
            "planned_metric_source_payload_count": 51,
            "metric_source_payload_fill_ready_row_count": 0,
            "metric_source_payload_fill_blocked_row_count": 51,
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
        },
    )
    _write_json(
        paths["r4"],
        {
            "r4_preflight_ready": True,
            "fetch_required_row_count": 17,
            "ready_for_r4_review_row_count": 17,
            "blocked_r4_row_count": 0,
            "authorized_for_external_download": False,
            "download_executed": False,
            "external_state_mutated": False,
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
        },
    )
    return paths


def test_claim_grade_gap_audit_tracks_statistical_and_materialization_gaps(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)

    payload = mod.build_refine_tier_public_benchmark_claim_grade_gap_audit(
        materialization_json=paths["materialization"],
        statistical_support_work_order_json=paths["work_order"],
        metric_materialization_readiness_json=paths["readiness"],
        metric_source_templates_json=paths["templates"],
        coordinate_fetch_r4_preflight_json=paths["r4"],
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
    assert summary["claim_grade_gap_audit_ready"] is True
    assert summary["claim_grade_statistical_support_ready"] is False
    assert summary["canonical_intake_promotion_allowed"] is False
    assert summary["observed_public_benchmark_pair_count"] == 8
    assert summary["observed_holdout_pair_count"] == 3
    assert summary["minimum_new_pair_count"] == 17
    assert summary["minimum_new_holdout_pair_count"] == 5
    assert summary["bootstrap_spearman_p05_deficit"] == 0.6428571428571428
    assert summary["coordinate_fetch_r4_fetch_required_row_count"] == 17
    assert summary["coordinate_validation_pass_row_count"] == 0
    assert summary["coordinate_validation_blocked_row_count"] == 17
    assert summary["coordinate_validation_deficit"] == 17
    assert summary["planned_metric_source_payload_count"] == 51
    assert summary["metric_source_payload_fill_ready_row_count"] == 0
    assert summary["metric_source_payload_fill_blocked_row_count"] == 51
    assert summary["metric_source_payload_fill_deficit"] == 51
    assert summary["gap_row_count"] == 5
    assert summary["blocked_gap_row_count"] == 5
    assert summary["blocker_count"] == 5
    assert summary["top_science_gap_id"] == "coordinate_fetch_r4_approval_required"
    assert summary["top_statistical_gap_id"] == "claim_grade_public_benchmark_pair_count_below_minimum"
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert [row["gap_id"] for row in payload["rows"]] == [
        "claim_grade_public_benchmark_pair_count",
        "claim_grade_public_benchmark_holdout_pair_count",
        "claim_grade_public_benchmark_bootstrap_spearman_p05",
        "claim_grade_coordinate_validation",
        "claim_grade_metric_source_payloads",
    ]


def test_claim_grade_gap_audit_allows_canonical_review_when_all_gaps_pass(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    _write_json(
        paths["materialization"],
        {
            "free_energy_pair_count": 25,
            "free_energy_holdout_pair_count": 8,
            "free_energy_spearman_bootstrap_p05": 0.61,
            "claim_grade_public_benchmark_statistical_support_ready": True,
        },
    )
    _write_json(
        paths["work_order"],
        {
            "canonical_intake_promotion_allowed": True,
            "expansion_slot_count": 0,
            "holdout_expansion_slot_count": 0,
            "fit_or_holdout_expansion_slot_count": 0,
        },
    )
    _write_json(
        paths["readiness"],
        {
            "metric_materialization_row_count": 17,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "planned_metric_source_payload_count": 51,
        },
    )
    _write_json(
        paths["templates"],
        {
            "planned_metric_source_payload_count": 51,
            "metric_source_payload_fill_ready_row_count": 51,
            "metric_source_payload_fill_blocked_row_count": 0,
        },
    )
    _write_json(
        paths["r4"],
        {
            "r4_preflight_ready": True,
            "fetch_required_row_count": 0,
            "ready_for_r4_review_row_count": 0,
            "blocked_r4_row_count": 0,
            "authorized_for_external_download": False,
            "download_executed": False,
            "external_state_mutated": False,
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
        },
    )

    payload = mod.build_refine_tier_public_benchmark_claim_grade_gap_audit(
        materialization_json=paths["materialization"],
        statistical_support_work_order_json=paths["work_order"],
        metric_materialization_readiness_json=paths["readiness"],
        metric_source_templates_json=paths["templates"],
        coordinate_fetch_r4_preflight_json=paths["r4"],
    )
    summary = payload["summary"]

    assert summary["claim_grade_statistical_support_ready"] is True
    assert summary["canonical_intake_promotion_allowed"] is True
    assert summary["blocked_gap_row_count"] == 0
    assert summary["blocker_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_claim_grade_gap_audit_cli_writes_outputs(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--materialization-json",
            str(paths["materialization"]),
            "--statistical-support-work-order-json",
            str(paths["work_order"]),
            "--metric-materialization-readiness-json",
            str(paths["readiness"]),
            "--metric-source-templates-json",
            str(paths["templates"]),
            "--coordinate-fetch-r4-preflight-json",
            str(paths["r4"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["blocked_gap_row_count"] == 5
    assert len(rows) == 5
    assert "Claim Grade Gap Audit" in out_md.read_text(encoding="utf-8")
