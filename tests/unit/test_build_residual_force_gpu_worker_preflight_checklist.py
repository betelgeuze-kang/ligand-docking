from __future__ import annotations

from tools.product.build_residual_force_gpu_worker_preflight_checklist import build_payload


def test_gpu_worker_preflight_checklist_includes_manifest_columns() -> None:
    payload = build_payload(
        handoff_packet={
            "summary": {
                "full_regeneration_command": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv q.csv",
            },
            "rows": [],
        },
        manifest_template_csv="runs/residual_force_gpu_worker_return_manifest_template_current.csv",
        summary_template_json="runs/residual_force_trajectory_regeneration_current_summary_template.json",
        queue_csv="runs/residual_force_trajectory_regeneration_queue_current.csv",
    )
    summary = payload["summary"]
    assert summary["queue_row_count"] == 768
    assert summary["manifest_template_row_count"] == 768
    assert summary["status"] == "residual_force_gpu_worker_preflight_checklist_ready"
    assert any(row["column_name"] == "operator_verified_npz_exists" for row in payload["manifest_column_guide"])
    assert any(row["column_name"] == "failed_rows" for row in payload["summary_field_guide"])
