from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools import build_residual_force_gpu_worker_return_receipt as mod


ROOT = Path(__file__).resolve().parents[2]


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def _queue() -> dict[str, object]:
    return {
        "summary": {"regeneration_queue_csv": ""},
        "rows": [
            {"queue_id": "q1", "expected_regenerated_trajectory_npz": "a.npz"},
            {"queue_id": "q2", "expected_regenerated_trajectory_npz": "b.npz"},
        ],
    }


def _write_npz(path: Path, *, queue_id: str | None = None, target: str = "", ligand_id: str = "") -> None:
    inferred_queue_id = queue_id
    if inferred_queue_id is None:
        inferred_queue_id = "q1" if path.stem.startswith("a") else "q2" if path.stem.startswith("b") else path.stem
    np.savez(
        path,
        protein_ca=np.zeros((2, 3), dtype=np.float32),
        ligand_frames=np.zeros((3, 4, 3), dtype=np.float32),
        frame_indices=np.asarray([0, 1, 2], dtype=np.int32),
        queue_id=np.asarray(inferred_queue_id),
        target=np.asarray(target),
        ligand_id=np.asarray(ligand_id),
        simulation_seed=np.asarray(11, dtype=np.int64),
    )


def _handoff(queue_rows: int = 2) -> dict[str, object]:
    return _packet(
        {
            "gpu_worker_handoff_ready": True,
            "queue_rows": queue_rows,
            "post_run_validation_commands": [f"python3 tools/{marker}" for marker in mod.REQUIRED_HANDOFF_VALIDATION_MARKERS],
            "post_return_promotion_ladder_ready": True,
            "post_return_promotion_ladder": [
                {"stage_id": ready_key, "ready_key": ready_key}
                for ready_key in mod.REQUIRED_HANDOFF_PROMOTION_LADDER_READY_KEYS
            ],
            "post_return_output_contract_ready": True,
            "post_return_required_production_output_fields": list(mod.REQUIRED_PRODUCTION_OUTPUT_FIELDS),
            "post_return_gpu_unlock_output_fields": list(mod.REQUIRED_GPU_RETURN_UNLOCK_OUTPUT_FIELDS),
            "post_return_gpu_unlock_artifacts": [
                "runs/residual_force_gpu_worker_return_receipt_current.json",
                "runs/residual_force_derivation_validation_current.json",
            ],
            "post_return_min_expected_label_rows": queue_rows,
        }
    )


def _summary_payload(
    manifest: Path,
    *,
    queue_rows: int = 2,
    processed_rows: int | None = None,
    ok_rows: int | None = None,
    summary_json: Path | None = None,
    backend_counts: dict[str, int] | None = None,
    prod_mode: bool = True,
    require_rust_hip: bool = True,
) -> dict[str, object]:
    return {
        "queue_rows": queue_rows,
        "processed_rows": processed_rows if processed_rows is not None else queue_rows,
        "ok_rows": ok_rows if ok_rows is not None else queue_rows,
        "failed_rows": 0,
        "aborted_early": False,
        "prod_mode": prod_mode,
        "require_rust_hip": require_rust_hip,
        "backend_counts": backend_counts if backend_counts is not None else {"rust_hip_rollout": queue_rows},
        "out_manifest_csv": str(manifest),
        "out_summary_json": str(summary_json or mod.DEFAULT_REGENERATION_SUMMARY_JSON),
    }


def test_gpu_worker_return_receipt_blocks_until_full_outputs_are_returned(tmp_path: Path) -> None:
    manifest = tmp_path / "missing_manifest.csv"
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet={},
        derivation_validation_packet=_packet({}),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["blockers"] == [
        "full_regeneration_summary_complete",
        "full_regeneration_summary_manifest_bound",
        "full_regeneration_summary_out_manifest_csv_present",
        "full_regeneration_summary_out_manifest_csv_bound",
        "full_regeneration_summary_out_summary_json_bound",
        "full_regeneration_summary_manifest_row_counts_consistent",
        "production_gpu_backend_provenance",
        "full_regeneration_manifest_complete",
        "full_regeneration_manifest_npz_paths_complete",
        "full_regeneration_manifest_npz_files_exist",
        "full_regeneration_manifest_npz_files_valid",
        "full_regeneration_manifest_npz_schema_valid",
        "full_regeneration_manifest_npz_identity_valid",
        "full_regeneration_manifest_operator_verified",
        "queue_manifest_identity_coverage",
        "post_run_force_derivation_validation",
    ]
    assert summary["expected_queue_rows"] == 2
    assert payload["rows"][0]["status"] == "pass"
    summary_row = next(row for row in payload["rows"] if row["check_id"] == "full_regeneration_summary_complete")
    assert summary_row["status"] == "fail"


def test_gpu_worker_return_receipt_ready_with_summary_manifest_and_derivation(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_force_gpu_worker_return_receipt_ready"
    assert summary["gpu_worker_return_receipt_ready"] is True
    assert summary["full_regeneration_summary_complete"] is True
    assert summary["full_regeneration_summary_manifest_bound"] is True
    assert summary["full_regeneration_summary_out_manifest_csv_bound"] is True
    assert summary["full_regeneration_summary_manifest_row_counts_consistent"] is True
    assert summary["production_gpu_backend_provenance_ready"] is True
    assert summary["production_gpu_backend_rows"] == 2
    assert summary["production_gpu_backend_non_production_rows"] == 0
    assert summary["production_gpu_backend_prod_mode"] is True
    assert summary["production_gpu_backend_require_rust_hip"] is True
    assert summary["summary_manifest_csv"] == str(manifest)
    assert summary["full_regeneration_manifest_complete"] is True
    assert summary["full_regeneration_manifest_operator_verified"] is True
    assert summary["handoff_post_run_validation_chain_current"] is True
    assert summary["handoff_post_return_promotion_ladder_current"] is True
    assert summary["handoff_post_return_promotion_ladder_stage_count"] == 10
    assert summary["handoff_post_return_promotion_ladder_missing_ready_keys"] == []
    assert summary["handoff_post_return_output_contract_current"] is True
    assert summary["handoff_post_return_gpu_unlock_output_fields"] == [
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert summary["handoff_post_return_min_expected_label_rows"] == 2
    assert summary["queue_manifest_identity_coverage_ready"] is True
    assert summary["manifest_matched_queue_id_count"] == 2
    assert summary["manifest_matched_expected_npz_count"] == 2
    assert summary["manifest_ok_row_count"] == 2
    assert summary["full_regeneration_manifest_npz_paths_complete"] is True
    assert summary["manifest_npz_path_column_present"] is True
    assert summary["manifest_npz_path_present_count"] == 2
    assert summary["manifest_ok_row_missing_npz_path_count"] == 0
    assert summary["manifest_operator_verified_missing_npz_path_count"] == 0
    assert summary["full_regeneration_manifest_npz_files_exist"] is True
    assert summary["manifest_npz_file_existing_count"] == 2
    assert summary["manifest_npz_file_missing_count"] == 0
    assert summary["manifest_ok_row_missing_npz_file_count"] == 0
    assert summary["manifest_operator_verified_missing_npz_file_count"] == 0
    assert summary["full_regeneration_manifest_npz_files_valid"] is True
    assert summary["manifest_npz_file_valid_count"] == 2
    assert summary["manifest_npz_file_invalid_count"] == 0
    assert summary["manifest_ok_row_invalid_npz_file_count"] == 0
    assert summary["manifest_operator_verified_invalid_npz_file_count"] == 0
    assert summary["full_regeneration_manifest_npz_schema_valid"] is True
    assert summary["manifest_npz_schema_valid_count"] == 2
    assert summary["manifest_npz_schema_invalid_count"] == 0
    assert summary["manifest_ok_row_invalid_npz_schema_count"] == 0
    assert summary["manifest_operator_verified_invalid_npz_schema_count"] == 0
    assert summary["full_regeneration_manifest_npz_identity_valid"] is True
    assert summary["manifest_npz_identity_valid_count"] == 2
    assert summary["manifest_npz_identity_invalid_count"] == 0
    assert summary["manifest_ok_row_invalid_npz_identity_count"] == 0
    assert summary["manifest_operator_verified_invalid_npz_identity_count"] == 0
    assert summary["manifest_operator_verified_true_count"] == 2
    assert summary["post_run_derivation_validation_ready"] is True
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_gpu_worker_return_receipt_blocks_cpu_diagnostic_backend_for_production(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(
            manifest,
            backend_counts={"cpu_per_row_fallback": 2},
            require_rust_hip=False,
        ),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert "production_gpu_backend_provenance" in summary["blockers"]
    assert summary["production_gpu_backend_provenance_ready"] is False
    assert summary["production_gpu_backend_rows"] == 0
    assert summary["production_gpu_backend_non_production_rows"] == 2
    assert summary["production_gpu_backend_require_rust_hip"] is False
    row = next(row for row in payload["rows"] if row["check_id"] == "production_gpu_backend_provenance")
    assert row["status"] == "fail"


def test_gpu_worker_return_receipt_accepts_fingerprint_identity_coverage(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    returned = tmp_path / "returned"
    returned.mkdir()
    _write_npz(returned / "a.npz")
    _write_npz(returned / "b.npz")
    q_rows = _queue()["rows"]
    fp1 = mod._queue_row_fingerprint(q_rows[0])
    fp2 = mod._queue_row_fingerprint(q_rows[1])
    manifest.write_text(
        "status,queue_row_fingerprint,trajectory_npz,operator_verified_npz_exists\n"
        f"ok_npz_bundle,{fp1},returned/a.npz,true\n"
        f"ok_npz_bundle,{fp2},returned/b.npz,true\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is True
    assert summary["manifest_matched_queue_id_count"] == 0
    assert summary["manifest_matched_expected_npz_count"] == 0
    assert summary["manifest_matched_queue_fingerprint_count"] == 2


def test_gpu_worker_return_receipt_blocks_overprocessed_summary_without_matching_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )

    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest, processed_rows=3, ok_rows=3),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_summary_complete"] is True
    assert summary["full_regeneration_summary_manifest_row_counts_consistent"] is False
    assert summary["summary_processed_rows"] == 3
    assert summary["summary_ok_rows"] == 3
    assert summary["manifest_row_count"] == 2
    assert summary["manifest_ok_row_count"] == 2
    assert summary["blockers"] == ["full_regeneration_summary_manifest_row_counts_consistent"]


def test_gpu_worker_return_receipt_blocks_duplicate_manifest_identity(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "a-copy.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q1,a-copy.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_complete"] is True
    assert summary["full_regeneration_manifest_npz_files_exist"] is True
    assert summary["full_regeneration_manifest_npz_files_valid"] is True
    assert summary["full_regeneration_manifest_npz_schema_valid"] is True
    assert summary["full_regeneration_manifest_npz_identity_valid"] is True
    assert summary["full_regeneration_manifest_operator_verified"] is True
    assert summary["manifest_duplicate_queue_id_count"] == 1
    assert summary["manifest_duplicate_identity_count"] == 1
    assert summary["queue_manifest_identity_coverage_ready"] is False
    assert summary["blockers"] == [
        "full_regeneration_summary_manifest_row_counts_consistent",
        "queue_manifest_identity_coverage",
    ]


def test_gpu_worker_return_receipt_blocks_summary_manifest_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet={
            "queue_rows": 2,
            "processed_rows": 2,
            "ok_rows": 2,
            "failed_rows": 0,
            "aborted_early": False,
            "prod_mode": True,
            "require_rust_hip": True,
            "backend_counts": {"rust_hip_rollout": 2},
            "out_manifest_csv": str(tmp_path / "other_manifest.csv"),
            "out_summary_json": mod.DEFAULT_REGENERATION_SUMMARY_JSON,
        },
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_summary_complete"] is True
    assert summary["full_regeneration_summary_manifest_bound"] is False
    assert summary["full_regeneration_summary_out_manifest_csv_bound"] is False
    assert summary["summary_manifest_csv"].endswith("other_manifest.csv")
    assert summary["blockers"] == [
        "full_regeneration_summary_manifest_bound",
        "full_regeneration_summary_out_manifest_csv_bound",
    ]


def test_gpu_worker_return_receipt_blocks_placeholder_operator_verification(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,OPERATOR_FILL_TRUE_OR_FALSE\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_complete"] is True
    assert summary["queue_manifest_identity_coverage_ready"] is True
    assert summary["full_regeneration_manifest_npz_files_exist"] is True
    assert summary["full_regeneration_manifest_npz_files_valid"] is True
    assert summary["full_regeneration_manifest_npz_schema_valid"] is True
    assert summary["full_regeneration_manifest_npz_identity_valid"] is True
    assert summary["full_regeneration_manifest_operator_verified"] is False
    assert summary["manifest_operator_verified_true_count"] == 1
    assert summary["manifest_operator_verification_placeholder_count"] == 1
    assert summary["blockers"] == ["full_regeneration_manifest_operator_verified"]


def test_gpu_worker_return_receipt_blocks_ok_row_missing_npz_path(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_complete"] is True
    assert summary["full_regeneration_manifest_npz_paths_complete"] is False
    assert summary["full_regeneration_manifest_operator_verified"] is True
    assert summary["queue_manifest_identity_coverage_ready"] is True
    assert summary["manifest_npz_path_column_present"] is True
    assert summary["manifest_npz_path_present_count"] == 1
    assert summary["manifest_npz_path_missing_count"] == 1
    assert summary["manifest_ok_row_missing_npz_path_count"] == 1
    assert summary["manifest_operator_verified_missing_npz_path_count"] == 1
    assert summary["blockers"] == [
        "full_regeneration_manifest_npz_paths_complete",
        "full_regeneration_manifest_npz_files_exist",
        "full_regeneration_manifest_npz_files_valid",
        "full_regeneration_manifest_npz_schema_valid",
        "full_regeneration_manifest_npz_identity_valid",
    ]


def test_gpu_worker_return_receipt_blocks_operator_verified_missing_npz_file(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_complete"] is True
    assert summary["full_regeneration_manifest_npz_paths_complete"] is True
    assert summary["full_regeneration_manifest_npz_files_exist"] is False
    assert summary["full_regeneration_manifest_npz_files_valid"] is False
    assert summary["full_regeneration_manifest_operator_verified"] is True
    assert summary["queue_manifest_identity_coverage_ready"] is True
    assert summary["manifest_npz_file_existing_count"] == 1
    assert summary["manifest_npz_file_missing_count"] == 1
    assert summary["manifest_ok_row_missing_npz_file_count"] == 1
    assert summary["manifest_operator_verified_missing_npz_file_count"] == 1
    assert summary["blockers"] == [
        "full_regeneration_manifest_npz_files_exist",
        "full_regeneration_manifest_npz_files_valid",
        "full_regeneration_manifest_npz_schema_valid",
        "full_regeneration_manifest_npz_identity_valid",
    ]


def test_gpu_worker_return_receipt_blocks_invalid_npz_file(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    (tmp_path / "a.npz").write_bytes(b"not-a-zip")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_complete"] is True
    assert summary["full_regeneration_manifest_npz_paths_complete"] is True
    assert summary["full_regeneration_manifest_npz_files_exist"] is True
    assert summary["full_regeneration_manifest_npz_files_valid"] is False
    assert summary["full_regeneration_manifest_npz_schema_valid"] is False
    assert summary["full_regeneration_manifest_npz_identity_valid"] is False
    assert summary["full_regeneration_manifest_operator_verified"] is True
    assert summary["queue_manifest_identity_coverage_ready"] is True
    assert summary["manifest_npz_file_existing_count"] == 2
    assert summary["manifest_npz_file_valid_count"] == 1
    assert summary["manifest_npz_file_invalid_count"] == 1
    assert summary["manifest_ok_row_invalid_npz_file_count"] == 1
    assert summary["manifest_operator_verified_invalid_npz_file_count"] == 1
    assert summary["blockers"] == [
        "full_regeneration_manifest_npz_files_valid",
        "full_regeneration_manifest_npz_schema_valid",
        "full_regeneration_manifest_npz_identity_valid",
    ]


def test_gpu_worker_return_receipt_blocks_npz_missing_production_schema(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    np.savez(tmp_path / "a.npz", arr=np.zeros((1,), dtype=np.float32))
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_npz_files_exist"] is True
    assert summary["full_regeneration_manifest_npz_files_valid"] is True
    assert summary["full_regeneration_manifest_npz_schema_valid"] is False
    assert summary["full_regeneration_manifest_npz_identity_valid"] is False
    assert summary["manifest_npz_file_valid_count"] == 2
    assert summary["manifest_npz_schema_valid_count"] == 1
    assert summary["manifest_npz_schema_invalid_count"] == 1
    assert summary["manifest_ok_row_invalid_npz_schema_count"] == 1
    assert summary["manifest_operator_verified_invalid_npz_schema_count"] == 1
    assert summary["blockers"] == [
        "full_regeneration_manifest_npz_schema_valid",
        "full_regeneration_manifest_npz_identity_valid",
    ]


def test_gpu_worker_return_receipt_blocks_npz_identity_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz", queue_id="wrong-q")
    _write_npz(tmp_path / "b.npz", queue_id="q2")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["full_regeneration_manifest_npz_files_valid"] is True
    assert summary["full_regeneration_manifest_npz_schema_valid"] is True
    assert summary["full_regeneration_manifest_npz_identity_valid"] is False
    assert summary["manifest_npz_identity_valid_count"] == 1
    assert summary["manifest_npz_identity_invalid_count"] == 1
    assert summary["manifest_ok_row_invalid_npz_identity_count"] == 1
    assert summary["manifest_operator_verified_invalid_npz_identity_count"] == 1
    assert summary["blockers"] == ["full_regeneration_manifest_npz_identity_valid"]


def test_gpu_worker_return_receipt_blocks_unapproved_ok_prefixed_status(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_placeholder,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_handoff(),
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert summary["manifest_ok_row_count"] == 1
    assert summary["manifest_status_invalid_count"] == 1
    assert summary["manifest_allowed_ok_status_values"] == [
        "ok",
        "ok_full_regeneration",
        "ok_npz_bundle",
        "ok_regenerated_npz",
    ]
    assert summary["blockers"] == [
        "full_regeneration_summary_manifest_row_counts_consistent",
        "full_regeneration_manifest_complete",
        "queue_manifest_identity_coverage",
    ]


def test_gpu_worker_return_receipt_blocks_stale_handoff_validation_chain(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_npz(tmp_path / "a.npz")
    _write_npz(tmp_path / "b.npz")
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\n"
        "ok_npz_bundle,q1,a.npz,true\n"
        "ok_npz_bundle,q2,b.npz,true\n",
        encoding="utf-8",
    )
    stale_handoff = _packet(
        {
            "gpu_worker_handoff_ready": True,
            "queue_rows": 2,
            "post_run_validation_commands": [
                "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                "python3 tools/build_residual_force_derivation_validation.py",
                "python3 tools/build_residual_production_training_data_contract.py",
            ],
        }
    )

    payload = mod.build_residual_force_gpu_worker_return_receipt(
        handoff_packet=stale_handoff,
        regeneration_queue_packet=_queue(),
        regeneration_summary_packet=_summary_payload(manifest),
        derivation_validation_packet=_packet(
            {
                "delta_force_derivation_validation_ready": True,
                "existing_remapped_trajectory_npz_rows": 2,
                "effective_min_existing_npz_rows": 2,
                "derivation_input_sample_count": 2,
                "min_npz_probe_successes": 2,
            }
        ),
        regeneration_manifest_csv=str(manifest),
    )

    summary = payload["summary"]
    assert summary["gpu_worker_return_receipt_ready"] is False
    assert "handoff_post_run_validation_chain_current" in summary["blockers"]
    assert "handoff_post_return_promotion_ladder_current" in summary["blockers"]
    assert "handoff_post_return_output_contract_current" in summary["blockers"]
    assert "build_residual_uncertainty_policy_evidence_contract.py" in summary["handoff_post_run_validation_missing_markers"]
    assert "production_promotion_allowed" in summary["handoff_post_return_promotion_ladder_missing_ready_keys"]
    assert "delta_force" in summary["handoff_post_return_output_contract_missing_required_outputs"]


def test_gpu_worker_return_receipt_cli_writes_outputs(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    queue = tmp_path / "queue.json"
    summary = tmp_path / "summary.json"
    derivation = tmp_path / "derivation.json"
    manifest = tmp_path / "manifest.csv"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"
    _write_npz(tmp_path / "a.npz")
    handoff.write_text(json.dumps(_handoff(queue_rows=1)), encoding="utf-8")
    queue.write_text(
        json.dumps({"summary": {}, "rows": [{"queue_id": "q1", "expected_regenerated_trajectory_npz": "a.npz"}]}),
        encoding="utf-8",
    )
    summary.write_text(
        json.dumps(
                {
                    "queue_rows": 1,
                    "processed_rows": 1,
                    "ok_rows": 1,
                    "failed_rows": 0,
                    "aborted_early": False,
                    "prod_mode": True,
                    "require_rust_hip": True,
                    "backend_counts": {"rust_hip_rollout": 1},
                    "out_manifest_csv": str(manifest),
                    "out_summary_json": str(summary),
                }
        ),
        encoding="utf-8",
    )
    derivation.write_text(
        json.dumps(
            _packet(
                {
                    "delta_force_derivation_validation_ready": True,
                    "existing_remapped_trajectory_npz_rows": 1,
                    "effective_min_existing_npz_rows": 1,
                    "derivation_input_sample_count": 1,
                    "min_npz_probe_successes": 1,
                }
            )
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        "status,queue_id,trajectory_npz,operator_verified_npz_exists\nok_npz_bundle,q1,a.npz,true\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "tools/build_residual_force_gpu_worker_return_receipt.py",
            "--handoff-json",
            str(handoff),
            "--regeneration-queue-json",
            str(queue),
            "--regeneration-summary-json",
            str(summary),
            "--regeneration-manifest-csv",
            str(manifest),
            "--derivation-validation-json",
            str(derivation),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["gpu_worker_return_receipt_ready"] is True
    assert "queue_manifest_identity_coverage" in out_csv.read_text(encoding="utf-8")
    assert "Residual Force GPU Worker Return Receipt" in out_md.read_text(encoding="utf-8")
