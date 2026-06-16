from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_energy_force_label_evidence_work_order as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def _write_stage3(path: Path, rows: int) -> None:
    path.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,mean_e_vdw,trajectory_npz,backmapped_pdb\n"
        + "\n".join(
            f"ADRB2_GPCR_BLIND,lig{i},{-8.0 - i * 0.01},{-1.0 - i * 0.01},traj_{i}.npz,pose_{i}.pdb"
            for i in range(rows)
        )
        + "\n",
        encoding="utf-8",
    )


def test_energy_force_work_order_finds_energy_proxy_candidates_but_blocks_validation(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(tmp_path / "a_stage3_scores.csv", 6)
    supervised_rows = [
        {
            "target": "ADRB2_GPCR_BLIND",
            "ligand_id": f"lig{i}",
            "source_csv": str(stage5),
        }
        for i in range(6)
    ]

    payload = mod.build_residual_energy_force_label_evidence_work_order(
        supervised_dataset_packet=_packet(
            {
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"],
                "missing_production_output_labels": ["delta_energy", "delta_force"],
            },
            supervised_rows,
        ),
        validation_packet=_packet({}),
        pdbbind_preflight_packet=_packet({"product_execution_ready": True}),
        force_artifact_recovery_work_order_packet=_packet({"force_artifact_recovery_required": True}),
        force_trajectory_regeneration_queue_packet=_packet(
            {
                "regeneration_queue_ready": True,
                "regeneration_queue_execution_ready": True,
                "queue_rows": 6,
                "engine_command": "python3 tools/generate_ligand_trajectory_engine.py --queue-csv queue.csv",
            }
        ),
        force_trajectory_regeneration_execution_probe_packet=_packet(
            {
                "engine_runtime_ready": False,
                "gpu_backend_unavailable": True,
                "pilot_abort_reason": "RuntimeError: GPU-only mode enabled but CUDA is unavailable.",
            }
        ),
        force_gpu_worker_handoff_packet=_packet(
            {
                "gpu_worker_handoff_ready": True,
                "gpu_worker_handoff_required": True,
                "next_required_step": "Run this handoff package on a GPU-equipped worker.",
            }
        ),
        force_gpu_worker_return_receipt_packet=_packet(
            {
                "gpu_worker_return_receipt_ready": False,
                "blockers": ["full_regeneration_summary_complete"],
                "full_regeneration_summary_manifest_bound": False,
                "summary_manifest_csv": "runs/other_manifest.csv",
                "full_regeneration_summary_out_manifest_csv_present": False,
                "summary_out_manifest_csv": "",
                "full_regeneration_summary_out_manifest_csv_bound": False,
                "full_regeneration_summary_out_summary_json_bound": False,
                "summary_out_summary_json": "",
                "full_regeneration_summary_manifest_row_counts_consistent": False,
                "summary_ok_rows": 0,
                "manifest_ok_row_count": 0,
                "manifest_status_placeholder_count": 1,
                "manifest_status_invalid_count": 2,
                "manifest_allowed_ok_status_values": ["ok", "ok_npz_bundle"],
                "full_regeneration_manifest_npz_paths_complete": False,
                "manifest_npz_path_present_count": 0,
                "manifest_npz_path_missing_count": 2,
                "manifest_ok_row_missing_npz_path_count": 1,
                "manifest_operator_verified_missing_npz_path_count": 1,
                "full_regeneration_manifest_npz_files_exist": False,
                "manifest_npz_file_existing_count": 0,
                "manifest_npz_file_missing_count": 2,
                "manifest_ok_row_missing_npz_file_count": 1,
                "manifest_operator_verified_missing_npz_file_count": 1,
                "full_regeneration_manifest_npz_files_valid": False,
                "manifest_npz_file_valid_count": 0,
                "manifest_npz_file_invalid_count": 2,
                "manifest_ok_row_invalid_npz_file_count": 1,
                "manifest_operator_verified_invalid_npz_file_count": 1,
                "full_regeneration_manifest_npz_schema_valid": False,
                "manifest_npz_schema_valid_count": 0,
                "manifest_npz_schema_invalid_count": 2,
                "manifest_ok_row_invalid_npz_schema_count": 1,
                "manifest_operator_verified_invalid_npz_schema_count": 1,
                "full_regeneration_manifest_npz_identity_valid": False,
                "manifest_npz_identity_valid_count": 0,
                "manifest_npz_identity_invalid_count": 2,
                "manifest_ok_row_invalid_npz_identity_count": 1,
                "manifest_operator_verified_invalid_npz_identity_count": 1,
                "queue_manifest_identity_coverage_ready": False,
                "manifest_matched_queue_id_count": 0,
                "manifest_matched_expected_npz_count": 0,
                "missing_queue_id_count": 2,
                "missing_expected_npz_count": 2,
                "next_required_step": "Return GPU full-regeneration summary/manifest.",
            }
        ),
        min_energy_proxy_rows=5,
        max_sources=4,
        max_rows_per_source=10,
    )

    summary = payload["summary"]
    assert summary["energy_proxy_candidate_ready"] is True
    assert summary["energy_proxy_rows"] == 6
    assert summary["trajectory_npz_rows"] == 6
    assert summary["backmapped_pdb_rows"] == 6
    assert summary["force_trajectory_regeneration_queue_execution_ready"] is True
    assert summary["force_trajectory_regeneration_queue_rows"] == 6
    assert summary["force_trajectory_regeneration_engine_runtime_ready"] is False
    assert summary["force_trajectory_regeneration_gpu_backend_unavailable"] is True
    assert summary["force_gpu_worker_handoff_ready"] is True
    assert summary["force_gpu_worker_return_receipt_ready"] is False
    assert summary["force_gpu_worker_return_receipt_blockers"] == ["full_regeneration_summary_complete"]
    assert summary["force_gpu_worker_return_summary_manifest_bound"] is False
    assert summary["force_gpu_worker_return_summary_manifest_csv"] == "runs/other_manifest.csv"
    assert summary["force_gpu_worker_return_summary_out_manifest_csv_present"] is False
    assert summary["force_gpu_worker_return_summary_out_manifest_csv"] == ""
    assert summary["force_gpu_worker_return_summary_out_manifest_csv_bound"] is False
    assert summary["force_gpu_worker_return_summary_out_summary_json_bound"] is False
    assert summary["force_gpu_worker_return_summary_out_summary_json"] == ""
    assert summary["force_gpu_worker_return_summary_manifest_row_counts_consistent"] is False
    assert summary["force_gpu_worker_return_summary_ok_rows"] == 0
    assert summary["force_gpu_worker_return_manifest_ok_row_count"] == 0
    assert summary["force_gpu_worker_return_manifest_status_placeholder_count"] == 1
    assert summary["force_gpu_worker_return_manifest_status_invalid_count"] == 2
    assert summary["force_gpu_worker_return_manifest_allowed_ok_status_values"] == ["ok", "ok_npz_bundle"]
    assert summary["force_gpu_worker_return_manifest_npz_paths_complete"] is False
    assert summary["force_gpu_worker_return_manifest_npz_path_present_count"] == 0
    assert summary["force_gpu_worker_return_manifest_npz_path_missing_count"] == 2
    assert summary["force_gpu_worker_return_manifest_ok_row_missing_npz_path_count"] == 1
    assert summary["force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count"] == 1
    assert summary["force_gpu_worker_return_manifest_npz_files_exist"] is False
    assert summary["force_gpu_worker_return_manifest_npz_file_existing_count"] == 0
    assert summary["force_gpu_worker_return_manifest_npz_file_missing_count"] == 2
    assert summary["force_gpu_worker_return_manifest_ok_row_missing_npz_file_count"] == 1
    assert summary["force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count"] == 1
    assert summary["force_gpu_worker_return_manifest_npz_files_valid"] is False
    assert summary["force_gpu_worker_return_manifest_npz_file_valid_count"] == 0
    assert summary["force_gpu_worker_return_manifest_npz_file_invalid_count"] == 2
    assert summary["force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count"] == 1
    assert summary["force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count"] == 1
    assert summary["force_gpu_worker_return_manifest_npz_schema_valid"] is False
    assert summary["force_gpu_worker_return_manifest_npz_schema_valid_count"] == 0
    assert summary["force_gpu_worker_return_manifest_npz_schema_invalid_count"] == 2
    assert summary["force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count"] == 1
    assert summary["force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count"] == 1
    assert summary["force_gpu_worker_return_manifest_npz_identity_valid"] is False
    assert summary["force_gpu_worker_return_manifest_npz_identity_valid_count"] == 0
    assert summary["force_gpu_worker_return_manifest_npz_identity_invalid_count"] == 2
    assert summary["force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count"] == 1
    assert summary["force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count"] == 1
    assert summary["force_gpu_worker_return_identity_coverage_ready"] is False
    assert summary["force_gpu_worker_return_matched_queue_id_count"] == 0
    assert summary["force_gpu_worker_return_missing_queue_id_count"] == 2
    assert payload["rows"][2]["next_action"] == "Return GPU full-regeneration summary/manifest."
    assert "gpu_worker_return_manifest_status_placeholder_count=1" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_status_invalid_count=2" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_allowed_ok_status_values=ok,ok_npz_bundle" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_manifest_bound=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_manifest_csv=runs/other_manifest.csv" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv_present=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv=" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_out_manifest_csv_bound=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_out_summary_json_bound=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_out_summary_json=" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_summary_manifest_row_counts_consistent=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_npz_paths_complete=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_ok_row_missing_npz_path_count=1" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_npz_files_exist=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_ok_row_missing_npz_file_count=1" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_npz_files_valid=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_file_count=1" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_npz_schema_valid=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_schema_count=1" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_npz_identity_valid=False" in payload["rows"][2]["observed"]
    assert "gpu_worker_return_manifest_ok_row_invalid_npz_identity_count=1" in payload["rows"][2]["observed"]
    assert summary["force_derivation_effective_min_existing_npz_rows"] == 0
    assert summary["delta_energy_label_evidence_ready"] is False
    assert summary["delta_force_label_evidence_ready"] is False
    assert summary["energy_force_label_evidence_ready"] is False
    assert payload["rows"][0]["status"] == "pass"
    assert payload["rows"][1]["status"] == "fail"


def test_energy_force_work_order_accepts_embedded_supervised_proxy_candidate_rows(tmp_path: Path) -> None:
    missing_stage5 = tmp_path / "missing_stage5_ranking_rows.csv"
    supervised_rows = [
        {
            "target": "ADRB2_GPCR_BLIND",
            "ligand_id": f"lig{i}",
            "source_csv": str(missing_stage5),
            "delta_energy": -8.0 - i * 0.01,
            "delta_energy_label_source": "stage3_energy_proxy:binding_energy_mmpbsa_kcal_mol_proxy",
        }
        for i in range(6)
    ]

    payload = mod.build_residual_energy_force_label_evidence_work_order(
        supervised_dataset_packet=_packet(
            {
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score", "delta_energy"],
                "missing_production_output_labels": ["delta_force"],
            },
            supervised_rows,
        ),
        validation_packet=_packet(
            {
                "delta_energy_proxy_validation_ready": False,
                "joined_energy_proxy_pair_count": 6,
                "stage3_energy_proxy_pair_count": 0,
                "embedded_delta_energy_proxy_pair_count": 6,
                "energy_proxy_source_mode": "embedded_supervised_delta_energy_proxy",
                "blockers": ["pearson_reference_vs_energy_proxy", "delta_force_derivation_validation"],
            }
        ),
        min_energy_proxy_rows=5,
        max_sources=4,
        max_rows_per_source=10,
    )

    summary = payload["summary"]
    assert summary["energy_proxy_candidate_ready"] is True
    assert summary["stage3_energy_proxy_candidate_ready"] is False
    assert summary["embedded_energy_proxy_candidate_ready"] is True
    assert summary["validation_embedded_delta_energy_proxy_pair_count"] == 6
    assert summary["validation_energy_proxy_source_mode"] == "embedded_supervised_delta_energy_proxy"
    assert payload["rows"][0]["status"] == "pass"
    assert "embedded_candidate_ready=True" in payload["rows"][0]["observed"]
    assert payload["rows"][1]["status"] == "fail"


def test_energy_force_work_order_ready_with_validation_evidence(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(tmp_path / "a_stage3_scores.csv", 3)
    supervised_rows = [
        {
            "target": "ADRB2_GPCR_BLIND",
            "ligand_id": f"lig{i}",
            "source_csv": str(stage5),
        }
        for i in range(3)
    ]

    payload = mod.build_residual_energy_force_label_evidence_work_order(
        supervised_dataset_packet=_packet(
            {
                "label_fields": ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"],
                "missing_production_output_labels": ["delta_energy", "delta_force"],
            },
            supervised_rows,
        ),
        validation_packet=_packet(
            {
                "delta_energy_proxy_validation_ready": True,
                "delta_force_derivation_validation_ready": True,
            }
        ),
        pdbbind_preflight_packet=_packet({"product_execution_ready": True}),
        min_energy_proxy_rows=3,
        max_sources=4,
        max_rows_per_source=10,
    )

    assert payload["summary"]["energy_force_label_evidence_ready"] is True
    assert payload["summary"]["delta_energy_label_evidence_ready"] is True
    assert payload["summary"]["delta_force_label_evidence_ready"] is True
    assert payload["rows"][-1]["status"] == "pass"


def test_energy_force_work_order_cli_writes_outputs(tmp_path: Path) -> None:
    stage5 = tmp_path / "a_stage5_ranking_rows.csv"
    _write_stage3(tmp_path / "a_stage3_scores.csv", 2)
    supervised = tmp_path / "supervised.json"
    validation = tmp_path / "validation.json"
    preflight = tmp_path / "preflight.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    supervised.write_text(
        json.dumps(
            _packet(
                {"missing_production_output_labels": ["delta_energy", "delta_force"]},
                [
                    {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig0", "source_csv": str(stage5)},
                    {"target": "ADRB2_GPCR_BLIND", "ligand_id": "lig1", "source_csv": str(stage5)},
                ],
            )
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(json.dumps(_packet({})) + "\n", encoding="utf-8")
    preflight.write_text(json.dumps(_packet({"product_execution_ready": True})) + "\n", encoding="utf-8")

    mod.main(
        [
            "--supervised-dataset-json",
            str(supervised),
            "--validation-json",
            str(validation),
            "--pdbbind-preflight-json",
            str(preflight),
            "--min-energy-proxy-rows",
            "2",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["energy_proxy_rows"] == 2
    assert "delta_energy_proxy_candidate_rows" in out_csv.read_text(encoding="utf-8")
    assert "Residual Energy/Force Label Evidence Work Order" in out_md.read_text(encoding="utf-8")
