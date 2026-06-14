import json
from pathlib import Path

from tools.product import (
    build_refine_tier_public_benchmark_statistical_support_metric_source_templates as mod,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _metric_readiness_payload() -> dict:
    return {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready",
            "metric_materialization_readiness_ready": True,
            "metric_materialization_row_count": 2,
            "metric_materialization_candidate_ready_count": 1,
            "metric_materialization_candidate_blocked_count": 1,
            "coordinate_validation_pass_row_count": 1,
            "coordinate_validation_blocked_row_count": 1,
            "planned_metric_source_payload_count": 6,
            "existing_metric_source_payload_count": 0,
        },
        "rows": [
            {
                "candidate_queue_id": "candidate_001",
                "expansion_slot_id": "expansion_001",
                "suggested_work_order_id": "work_001",
                "target_id": "new1",
                "pose_id": "new1_001",
                "required_split": "holdout",
                "suggested_split": "holdout",
                "dockq_source_artifact": "runs/sources/work_001_dockq.json",
                "lddt_pli_source_artifact": "runs/sources/work_001_lddt_pli.json",
                "internal_deltaG_source_artifact": "runs/sources/work_001_internal_deltaG.json",
                "required_metric_input_artifacts": "dataset/data_5_sdf/new1_001;dataset/new1/new1_complex.pdb",
                "required_metric_input_artifact_sha256s": "ligand_sha;receptor_sha",
                "required_metric_input_artifact_count": 2,
                "present_required_metric_input_artifact_count": 2,
                "missing_required_metric_input_artifact_count": 0,
                "coordinate_validation_status": "pass",
                "metric_materialization_status": "ready_for_metric_source_materialization",
                "metric_materialization_candidate_ready": True,
            },
            {
                "candidate_queue_id": "candidate_002",
                "expansion_slot_id": "expansion_002",
                "suggested_work_order_id": "work_002",
                "target_id": "new2",
                "pose_id": "new2_002",
                "required_split": "fit_or_holdout",
                "suggested_split": "fit",
                "dockq_source_artifact": "runs/sources/work_002_dockq.json",
                "lddt_pli_source_artifact": "runs/sources/work_002_lddt_pli.json",
                "internal_deltaG_source_artifact": "runs/sources/work_002_internal_deltaG.json",
                "required_metric_input_artifacts": "dataset/data_5_sdf/new2_002;dataset/new2/new2_complex.pdb",
                "required_metric_input_artifact_sha256s": "ligand_sha;",
                "required_metric_input_artifact_count": 2,
                "present_required_metric_input_artifact_count": 1,
                "missing_required_metric_input_artifact_count": 1,
                "coordinate_validation_status": "blocked",
                "metric_materialization_status": "blocked_metric_source_materialization_inputs",
                "metric_materialization_candidate_ready": False,
            },
        ],
    }


def test_metric_source_templates_expand_readiness_rows_to_payload_templates(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "metric_readiness.json"
    _write_json(readiness_json, _metric_readiness_payload())

    payload = mod.build_refine_tier_public_benchmark_statistical_support_metric_source_templates(
        metric_materialization_readiness_json=readiness_json,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
    )
    assert summary["metric_source_templates_ready"] is True
    assert summary["metric_materialization_readiness_present"] is True
    assert summary["metric_materialization_readiness_ready"] is True
    assert summary["metric_materialization_row_count"] == 2
    assert summary["metric_materialization_candidate_ready_count"] == 1
    assert summary["metric_materialization_candidate_blocked_count"] == 1
    assert summary["planned_metric_source_payload_count"] == 6
    assert summary["template_row_count"] == 6
    assert summary["template_candidate_row_count"] == 2
    assert summary["template_metric_name_count"] == 3
    assert summary["template_metric_source_artifact_path_row_count"] == 6
    assert summary["template_payload_required_fields_present_row_count"] == 6
    assert summary["metric_source_payload_fill_ready_row_count"] == 3
    assert summary["metric_source_payload_fill_blocked_row_count"] == 3
    assert summary["coordinate_validation_blocked_template_row_count"] == 3
    assert summary["missing_required_input_template_row_count"] == 3
    assert summary["existing_metric_source_payload_present_row_count"] == 0
    assert summary["placeholder_value_count"] == 6
    assert summary["placeholder_method_count"] == 6
    assert summary["placeholder_operator_id_count"] == 6
    assert summary["placeholder_reviewed_at_utc_count"] == 6
    assert summary["placeholder_license_ok_count"] == 6
    assert summary["external_engine_calls_total"] == 0
    assert summary["canonical_intake_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False

    first = payload["rows"][0]
    assert first["template_status"] == "ready_for_operator_metric_source_payload_fill"
    assert first["metric_name"] == "dockq"
    assert first["metric_source_artifact"] == "runs/sources/work_001_dockq.json"
    template_payload = json.loads(first["template_payload_json"])
    assert template_payload["metric_name"] == "dockq"
    assert template_payload["value"] == "OPERATOR_FILL_NUMERIC_METRIC_VALUE"
    assert template_payload["license_ok"] == "OPERATOR_CONFIRM_TRUE"
    assert template_payload["external_engine_calls"] == 0

    blocked = payload["rows"][-1]
    assert blocked["template_status"] == "blocked_until_coordinate_validation_passes"
    assert blocked["template_blockers"] == (
        "coordinate_validation_not_pass;required_metric_input_artifacts_missing"
    )


def test_metric_source_templates_block_missing_readiness(tmp_path: Path) -> None:
    payload = mod.build_refine_tier_public_benchmark_statistical_support_metric_source_templates(
        metric_materialization_readiness_json=tmp_path / "missing.json",
        root=tmp_path,
    )

    assert payload["summary"]["status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_metric_source_templates"
    )
    assert payload["summary"]["blockers"] == [
        "metric_materialization_readiness_missing",
        "metric_materialization_readiness_not_ready",
        "metric_source_template_rows_missing",
    ]


def test_metric_source_templates_cli_writes_outputs(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "metric_readiness.json"
    out_json = tmp_path / "runs" / "templates.json"
    out_csv = tmp_path / "runs" / "templates.csv"
    out_md = tmp_path / "runs" / "templates.md"
    _write_json(readiness_json, _metric_readiness_payload())

    mod.main(
        [
            "--metric-materialization-readiness-json",
            str(readiness_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["template_row_count"] == 6
    assert "OPERATOR_FILL_NUMERIC_METRIC_VALUE" in out_csv.read_text(encoding="utf-8")
    assert "R9 Statistical Support Metric Source Templates" in out_md.read_text(encoding="utf-8")
