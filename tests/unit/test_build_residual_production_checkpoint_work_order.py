from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_production_checkpoint_work_order as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def test_checkpoint_work_order_ranks_candidates() -> None:
    payload = mod.build_residual_production_checkpoint_work_order(
        preflight_packet=_packet(
            {"checkpoint_preflight_ready": False, "candidate_checkpoint_count": 2, "sidecar_metadata_count": 0, "ready_checkpoint_count": 0},
            [
                {"checkpoint_path": "models/a.pth", "sha256": "aaa", "size_bytes": 10, "model_family": "unknown", "blockers": "missing_sidecar_metadata"},
                {"checkpoint_path": "models/residual_b.pth", "sha256": "bbb", "size_bytes": 5, "model_family": "residual_candidate", "blockers": "missing_sidecar_metadata"},
            ],
        ),
        registry_packet=_packet(
            {
                "default_residual_mode": "shadow",
                "production_promotion_allowed": False,
                "production_checkpoint_blocked": True,
                "checkpoint_primary_blocker": "missing_output_fields:delta_energy,delta_force",
                "checkpoint_missing_output_fields": ["delta_energy", "delta_force"],
                "checkpoint_missing_adapter_output_policy_fields": ["delta_force"],
            }
        ),
        sidecar_packet=_packet(
            {
                "status": "blocked_residual_production_checkpoint_sidecar",
                "sidecar_ready": False,
                "blockers": ["force_gpu_return_receipt_ready"],
                "missing_production_output_fields": ["delta_force"],
                "training_contract_missing_label_fields": ["delta_force"],
                "force_gpu_return_receipt_ready": False,
                "force_gpu_return_receipt_operator_verified": False,
                "force_gpu_return_receipt_operator_verified_true_count": 0,
                "force_gpu_return_receipt_expected_queue_rows": 768,
                "force_gpu_return_receipt_manifest_ok_row_count": 0,
                "force_gpu_return_receipt_manifest_status_invalid_count": 1,
                "force_gpu_return_receipt_manifest_status_vocab_ready": False,
                "force_gpu_return_receipt_manifest_row_count_ready": False,
            }
        ),
        candidate_limit=1,
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_production_checkpoint_work_order_ready"
    assert summary["ranked_candidate_count"] == 1
    assert payload["rows"][0]["checkpoint_path"] == "models/residual_b.pth"
    assert payload["rows"][0]["compatibility_status"] == "unknown_candidate_requires_architecture_proof"
    assert "ready_for_guarded_promotion=true" in payload["rows"][0]["acceptance_criteria"]
    assert "checkpoint_missing_output_fields empty" in payload["rows"][0]["acceptance_criteria"]
    assert summary["registry_production_checkpoint_blocked"] is True
    assert summary["registry_checkpoint_primary_blocker"] == "missing_output_fields:delta_energy,delta_force"
    assert summary["registry_checkpoint_missing_output_fields"] == ["delta_energy", "delta_force"]
    assert summary["registry_checkpoint_missing_adapter_output_policy_fields"] == ["delta_force"]
    assert payload["rows"][0]["registry_checkpoint_missing_output_fields"] == "delta_energy,delta_force"
    assert payload["rows"][0]["registry_checkpoint_missing_adapter_output_policy_fields"] == "delta_force"
    assert payload["summary"]["sidecar_builder_status"] == "blocked_residual_production_checkpoint_sidecar"
    assert payload["summary"]["sidecar_builder_ready"] is False
    assert payload["summary"]["sidecar_builder_blockers"] == ["force_gpu_return_receipt_ready"]
    assert payload["summary"]["sidecar_builder_missing_production_output_fields"] == ["delta_force"]
    assert payload["summary"]["sidecar_builder_training_contract_missing_label_fields"] == ["delta_force"]
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_ready"] is False
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_operator_verified"] is False
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_operator_verified_true_count"] == 0
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_expected_queue_rows"] == 768
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_manifest_ok_row_count"] == 0
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_manifest_status_invalid_count"] == 1
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_manifest_status_vocab_ready"] is False
    assert payload["summary"]["sidecar_builder_force_gpu_return_receipt_manifest_row_count_ready"] is False
    assert "sidecar_missing_production_output:delta_force" in payload["summary"]["checkpoint_closure_blockers"]
    assert "force_gpu_return_receipt_operator_not_verified" in payload["summary"]["checkpoint_closure_blockers"]
    assert "force_gpu_return_receipt_manifest_status_invalid" in payload["summary"]["checkpoint_closure_blockers"]
    assert "force_gpu_return_receipt_manifest_status_vocab_not_ready" in payload["summary"]["checkpoint_closure_blockers"]
    assert "force_gpu_return_receipt_manifest_row_count_not_ready" in payload["summary"]["checkpoint_closure_blockers"]
    assert payload["rows"][0]["sidecar_builder_missing_production_output_fields"] == "delta_force"
    assert payload["rows"][0]["sidecar_builder_force_gpu_return_receipt_expected_queue_rows"] == 768
    assert "training_missing_label:delta_force" in payload["rows"][0]["checkpoint_closure_blockers"]
    assert payload["summary"]["source_artifacts"][2] == "runs/residual_production_checkpoint_sidecar_current.json"
    assert "build_residual_production_checkpoint_sidecar.py" in payload["rows"][0]["verification_command"]
    assert payload["rows"][0]["verification_command"].index("build_residual_production_checkpoint_sidecar.py") < payload["rows"][0][
        "verification_command"
    ].index("build_residual_production_checkpoint_preflight.py")


def test_checkpoint_work_order_includes_sidecar_schema() -> None:
    payload = mod.build_residual_production_checkpoint_work_order(
        preflight_packet=_packet({"checkpoint_preflight_ready": True, "candidate_checkpoint_count": 1, "sidecar_metadata_count": 1, "ready_checkpoint_count": 1}),
        registry_packet=_packet({"default_residual_mode": "production_guarded", "production_promotion_allowed": True}),
    )

    schema = payload["summary"]["required_sidecar_schema"]
    assert schema["promotion_mode"] == "production_guarded"
    assert "delta_score" in schema["required_output_fields"]
    assert "adapter_output_policy" in schema
    assert schema["adapter_output_policy"]["abstention_reason"].startswith("policy_output_reason")
    assert "physics_guard_policy" in schema
    assert "abstention_policy" in schema
    assert schema["production_training_data_contract_artifact"]["required_ready_key"] == "production_training_data_ready"
    assert schema["force_gpu_worker_return_receipt_artifact"]["required_provenance_key"] == "queue_manifest_identity_coverage_ready"
    assert schema["production_training_data_contract_artifact"]["status"] == "blocked"
    assert schema["production_training_data_contract_artifact"]["observed_ready"] is False
    assert schema["force_gpu_worker_return_receipt_artifact"]["status"] == "blocked"
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_ready"] is False
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_provenance_ready"] is False
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified"] is False
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified_true_count"] == 0
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_manifest_status_vocab_ready"] is False


def test_checkpoint_work_order_schema_reflects_ready_sidecar_inputs() -> None:
    payload = mod.build_residual_production_checkpoint_work_order(
        preflight_packet=_packet({"checkpoint_preflight_ready": False, "candidate_checkpoint_count": 1}),
        registry_packet=_packet({"default_residual_mode": "shadow", "production_promotion_allowed": False}),
        sidecar_packet=_packet(
            {
                "status": "blocked_residual_production_checkpoint_sidecar",
                "sidecar_ready": False,
                "production_training_data_contract_ready": True,
                "force_gpu_return_receipt_ready": True,
                "force_gpu_return_receipt_operator_verified": True,
                "force_gpu_return_receipt_operator_verified_true_count": 2,
                "force_gpu_return_receipt_expected_queue_rows": 2,
                "force_gpu_return_receipt_manifest_ok_row_count": 2,
                "force_gpu_return_receipt_manifest_status_placeholder_count": 0,
                "force_gpu_return_receipt_manifest_status_invalid_count": 0,
                "force_gpu_return_receipt_manifest_allowed_ok_status_values": [
                    "ok",
                    "ok_full_regeneration",
                    "ok_npz_bundle",
                    "ok_regenerated_npz",
                ],
                "force_gpu_return_receipt_manifest_status_vocab_ready": True,
                "force_gpu_return_receipt_manifest_row_count_ready": True,
            }
        ),
    )

    schema = payload["summary"]["required_sidecar_schema"]
    assert schema["production_training_data_contract_artifact"]["status"] == "ready"
    assert schema["production_training_data_contract_artifact"]["observed_ready"] is True
    assert schema["force_gpu_worker_return_receipt_artifact"]["status"] == "ready"
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_ready"] is True
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_provenance_ready"] is True
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified"] is True
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified_true_count"] == 2
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_expected_queue_rows"] == 2
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_manifest_ok_row_count"] == 2
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_manifest_status_invalid_count"] == 0
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_manifest_status_vocab_ready"] is True
    assert schema["force_gpu_worker_return_receipt_artifact"]["observed_manifest_row_count_ready"] is True


def test_checkpoint_work_order_prioritizes_score_candidate() -> None:
    payload = mod.build_residual_production_checkpoint_work_order(
        preflight_packet=_packet(
            {"checkpoint_preflight_ready": False, "candidate_checkpoint_count": 2, "sidecar_metadata_count": 0, "ready_checkpoint_count": 0},
            [
                {"checkpoint_path": "models/airouter_v1.pt", "sha256": "aaa", "size_bytes": 5000, "model_family": "airouter_candidate", "blockers": "missing_sidecar_metadata"},
                {
                    "checkpoint_path": "models/residual_production_score_model_current.pt",
                    "sha256": "bbb",
                    "size_bytes": 10,
                    "model_family": "protein_ligand_residual_score_candidate",
                    "blockers": "missing_sidecar_metadata",
                },
            ],
        ),
        registry_packet=_packet({"default_residual_mode": "shadow"}),
        candidate_limit=1,
    )

    row = payload["rows"][0]
    assert row["checkpoint_path"] == "models/residual_production_score_model_current.pt"
    assert row["compatibility_status"] == "score_candidate_requires_output_head_guard_and_sidecar"
    assert "production output head" in row["required_action"]
    assert "force GPU receipt provenance" in row["required_action"]
    assert "force GPU receipt provenance" in payload["summary"]["next_required_step"]


def test_checkpoint_work_order_cli_writes_outputs(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    registry = tmp_path / "registry.json"
    sidecar = tmp_path / "sidecar.json"
    preflight.write_text(
        json.dumps(
            _packet(
                {"checkpoint_preflight_ready": False, "candidate_checkpoint_count": 1},
                [{"checkpoint_path": "models/a.pth", "sha256": "aaa", "size_bytes": 10, "model_family": "airouter_candidate", "blockers": "missing_sidecar_metadata"}],
            )
        )
        + "\n",
        encoding="utf-8",
    )
    registry.write_text(json.dumps(_packet({"default_residual_mode": "shadow"})) + "\n", encoding="utf-8")
    sidecar.write_text(json.dumps(_packet({"sidecar_ready": False, "blockers": ["production_training_data_contract_ready"]})) + "\n", encoding="utf-8")
    out_json = tmp_path / "work.json"
    out_csv = tmp_path / "work.csv"
    out_md = tmp_path / "work.md"

    mod.main(
        [
            "--preflight-json",
            str(preflight),
            "--registry-json",
            str(registry),
            "--sidecar-json",
            str(sidecar),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["ranked_candidate_count"] == 1
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["source_artifacts"][2] == str(sidecar)
    assert "checkpoint_path" in out_csv.read_text(encoding="utf-8")
    assert "Residual Production Checkpoint Work Order" in out_md.read_text(encoding="utf-8")
