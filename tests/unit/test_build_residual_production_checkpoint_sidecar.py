from __future__ import annotations

import json
from pathlib import Path

import torch

from tools import build_residual_production_checkpoint_preflight as preflight
from tools import build_residual_production_checkpoint_sidecar as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def _write_checkpoint(path: Path) -> None:
    torch.save(
        {
            "state_dict": {},
            "output_fields": [
                "delta_score",
                "corrected_score",
                "delta_energy",
                "delta_force",
                "uncertainty",
                "abstention_reason",
                "stage2_route_decision",
            ],
        },
        path,
    )


def _write_ready_contracts(tmp_path: Path) -> tuple[Path, Path]:
    training = tmp_path / "training_contract.json"
    receipt = tmp_path / "force_receipt.json"
    training.write_text(
        json.dumps({"summary": {"status": "residual_production_training_data_contract_ready", "production_training_data_ready": True}})
        + "\n",
        encoding="utf-8",
    )
    receipt.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "residual_force_gpu_worker_return_receipt_ready",
                    "gpu_worker_return_receipt_ready": True,
                    "queue_manifest_identity_coverage_ready": True,
                    "full_regeneration_manifest_operator_verified": True,
                    "manifest_operator_verified_true_count": 2,
                    "manifest_ok_row_count": 2,
                    "manifest_status_placeholder_count": 0,
                    "manifest_status_invalid_count": 0,
                    "manifest_allowed_ok_status_values": [
                        "ok",
                        "ok_full_regeneration",
                        "ok_npz_bundle",
                        "ok_regenerated_npz",
                    ],
                    "expected_queue_rows": 2,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return training, receipt


def test_sidecar_builder_writes_preflight_ready_sidecar(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    sidecar = tmp_path / "score.pt.json"
    score_json = tmp_path / "score.json"
    dataset_json = tmp_path / "dataset.json"
    assist_json = tmp_path / "assist.json"
    public_json = tmp_path / "public.json"
    training_json = tmp_path / "training_contract.json"
    receipt_json = tmp_path / "force_receipt.json"
    _write_checkpoint(ckpt)
    training_json, receipt_json = _write_ready_contracts(tmp_path)
    score_json.write_text(
        json.dumps(
            _packet(
                {
                    "status": "residual_production_score_model_trained",
                    "production_checkpoint_ready": True,
                    "missing_production_output_fields": [],
                    "policy_output_adapter_ready": True,
                    "val_rows": 200,
                    "best": {"pr_auc": 0.75},
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    dataset_json.write_text(json.dumps(_packet({"production_supervised_dataset_ready": True})) + "\n", encoding="utf-8")
    assist_json.write_text(json.dumps(_packet({"assist_promotion_allowed": True})) + "\n", encoding="utf-8")
    public_json.write_text(json.dumps(_packet({"assist_comparison_gate_ready": True})) + "\n", encoding="utf-8")

    payload = mod.build_residual_production_checkpoint_sidecar(
        checkpoint_path=str(ckpt),
        score_model_packet=json.loads(score_json.read_text(encoding="utf-8")),
        supervised_dataset_packet=json.loads(dataset_json.read_text(encoding="utf-8")),
        assist_gate_packet=json.loads(assist_json.read_text(encoding="utf-8")),
        public_assist_gate_packet=json.loads(public_json.read_text(encoding="utf-8")),
        training_data_contract_packet=json.loads(training_json.read_text(encoding="utf-8")),
        force_gpu_return_receipt_packet=json.loads(receipt_json.read_text(encoding="utf-8")),
        score_model_path=str(score_json),
        supervised_dataset_path=str(dataset_json),
        assist_gate_path=str(assist_json),
        public_assist_gate_path=str(public_json),
        training_data_contract_path=str(training_json),
        force_gpu_return_receipt_path=str(receipt_json),
        sidecar_path=str(sidecar),
    )

    assert payload["summary"]["sidecar_ready"] is True
    assert sidecar.exists()
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["production_training_data_contract_artifact"]["artifact"] == str(training_json)
    assert sidecar_payload["production_training_data_contract_artifact"]["status"] == "ready"
    assert sidecar_payload["production_training_data_contract_artifact"]["observed_ready"] is True
    assert sidecar_payload["production_training_data_contract_artifact"]["observed_missing_label_fields"] == []
    assert sidecar_payload["production_training_data_contract_artifact"]["observed_missing_output_fields"] == []
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["artifact"] == str(receipt_json)
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["status"] == "ready"
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_ready"] is True
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_provenance_ready"] is True
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified"] is True
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified_true_count"] == 2
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_expected_queue_rows"] == 2
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_manifest_ok_row_count"] == 2
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_manifest_status_invalid_count"] == 0
    assert sidecar_payload["force_gpu_worker_return_receipt_artifact"]["observed_manifest_allowed_ok_status_values"] == [
        "ok",
        "ok_full_regeneration",
        "ok_npz_bundle",
        "ok_regenerated_npz",
    ]
    assert all(item["status"] == "ready" for item in sidecar_payload["benchmark_gate_artifacts"])
    assert sidecar_payload["adapter_output_policy"]["delta_energy"] == "validated_energy_head_or_fail_closed_guard"
    preflight_payload = preflight.build_residual_production_checkpoint_preflight(models_dir=str(tmp_path))
    assert preflight_payload["summary"]["checkpoint_preflight_ready"] is True
    assert preflight_payload["rows"][0]["ready_for_guarded_promotion"] is True


def test_sidecar_builder_blocks_missing_score_outputs(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    torch.save({"state_dict": {}, "output_fields": ["delta_score"]}, ckpt)

    payload = mod.build_residual_production_checkpoint_sidecar(
        checkpoint_path=str(ckpt),
        score_model_packet=_packet({"status": "residual_production_score_model_trained", "val_rows": 200, "best": {"pr_auc": 0.75}}),
        supervised_dataset_packet=_packet({"production_supervised_dataset_ready": True}),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        sidecar_path=str(tmp_path / "score.pt.json"),
    )

    assert payload["summary"]["sidecar_ready"] is False
    assert "payload_has_score_outputs" in payload["summary"]["blockers"]


def test_sidecar_builder_blocks_score_candidate_missing_energy_force_heads(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    sidecar = tmp_path / "score.pt.json"
    _write_checkpoint(ckpt)

    payload = mod.build_residual_production_checkpoint_sidecar(
        checkpoint_path=str(ckpt),
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": False,
                "missing_production_output_fields": ["delta_energy", "delta_force"],
                "policy_output_adapter_ready": True,
                "val_rows": 200,
                "best": {"pr_auc": 0.75},
            }
        ),
        supervised_dataset_packet=_packet({"production_supervised_dataset_ready": True}),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        training_data_contract_packet=_packet(
            {
                "status": "blocked_residual_production_training_data_contract",
                "production_training_data_ready": False,
                "missing_energy_force_label_fields": ["delta_force"],
                "production_missing_output_fields": ["delta_force"],
                "primary_blocker": "production_delta_force_label_evidence",
            }
        ),
        sidecar_path=str(sidecar),
    )

    assert payload["summary"]["sidecar_ready"] is False
    assert payload["summary"]["policy_output_adapter_ready"] is True
    assert payload["summary"]["missing_production_output_fields"] == ["delta_energy", "delta_force"]
    assert payload["summary"]["training_contract_missing_label_fields"] == ["delta_force"]
    assert payload["summary"]["training_contract_missing_output_fields"] == ["delta_force"]
    assert payload["summary"]["training_contract_primary_blocker"] == "production_delta_force_label_evidence"
    assert payload["sidecar"]["production_training_data_contract_artifact"]["status"] == "blocked"
    assert payload["sidecar"]["production_training_data_contract_artifact"]["observed_ready"] is False
    assert payload["sidecar"]["production_training_data_contract_artifact"]["observed_missing_label_fields"] == ["delta_force"]
    assert payload["sidecar"]["production_training_data_contract_artifact"]["observed_missing_output_fields"] == ["delta_force"]
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["status"] == "blocked"
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_ready"] is False
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_provenance_ready"] is False
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified"] is False
    assert payload["sidecar"]["benchmark_gate_artifacts"][0]["status"] == "blocked"
    assert payload["sidecar"]["benchmark_gate_artifacts"][1]["status"] == "ready"
    assert "score_model_production_ready" in payload["summary"]["blockers"]
    assert "production_output_heads_complete" in payload["summary"]["blockers"]
    assert "production_training_data_contract_ready" in payload["summary"]["blockers"]
    assert "force_gpu_return_receipt_ready" in payload["summary"]["blockers"]
    assert not sidecar.exists()


def test_sidecar_builder_blocks_receipt_without_operator_verification(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    sidecar = tmp_path / "score.pt.json"
    _write_checkpoint(ckpt)

    payload = mod.build_residual_production_checkpoint_sidecar(
        checkpoint_path=str(ckpt),
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": True,
                "missing_production_output_fields": [],
                "policy_output_adapter_ready": True,
                "val_rows": 200,
                "best": {"pr_auc": 0.75},
            }
        ),
        supervised_dataset_packet=_packet({"production_supervised_dataset_ready": True}),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        training_data_contract_packet=_packet(
            {"status": "residual_production_training_data_contract_ready", "production_training_data_ready": True}
        ),
        force_gpu_return_receipt_packet=_packet(
            {
                "status": "residual_force_gpu_worker_return_receipt_ready",
                "gpu_worker_return_receipt_ready": True,
                "queue_manifest_identity_coverage_ready": True,
                "full_regeneration_manifest_operator_verified": False,
                "manifest_operator_verified_true_count": 1,
                "manifest_ok_row_count": 2,
                "manifest_status_placeholder_count": 0,
                "manifest_status_invalid_count": 0,
                "manifest_allowed_ok_status_values": [
                    "ok",
                    "ok_full_regeneration",
                    "ok_npz_bundle",
                    "ok_regenerated_npz",
                ],
                "expected_queue_rows": 2,
            }
        ),
        sidecar_path=str(sidecar),
    )

    assert payload["summary"]["sidecar_ready"] is False
    assert payload["summary"]["force_gpu_return_receipt_ready"] is False
    assert payload["summary"]["force_gpu_return_receipt_operator_verified"] is False
    assert payload["summary"]["force_gpu_return_receipt_operator_verified_true_count"] == 1
    assert payload["summary"]["force_gpu_return_receipt_expected_queue_rows"] == 2
    assert "force_gpu_return_receipt_ready" in payload["summary"]["blockers"]
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified"] is False
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_operator_verified_true_count"] == 1
    assert not sidecar.exists()


def test_sidecar_builder_blocks_receipt_with_invalid_manifest_status(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    sidecar = tmp_path / "score.pt.json"
    _write_checkpoint(ckpt)

    payload = mod.build_residual_production_checkpoint_sidecar(
        checkpoint_path=str(ckpt),
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": True,
                "missing_production_output_fields": [],
                "policy_output_adapter_ready": True,
                "val_rows": 200,
                "best": {"pr_auc": 0.75},
            }
        ),
        supervised_dataset_packet=_packet({"production_supervised_dataset_ready": True}),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        training_data_contract_packet=_packet(
            {"status": "residual_production_training_data_contract_ready", "production_training_data_ready": True}
        ),
        force_gpu_return_receipt_packet=_packet(
            {
                "status": "residual_force_gpu_worker_return_receipt_ready",
                "gpu_worker_return_receipt_ready": True,
                "queue_manifest_identity_coverage_ready": True,
                "full_regeneration_manifest_operator_verified": True,
                "manifest_operator_verified_true_count": 2,
                "manifest_ok_row_count": 2,
                "manifest_status_placeholder_count": 0,
                "manifest_status_invalid_count": 1,
                "manifest_allowed_ok_status_values": ["ok", "ok_npz_bundle"],
                "expected_queue_rows": 2,
            }
        ),
        sidecar_path=str(sidecar),
    )

    assert payload["summary"]["sidecar_ready"] is False
    assert payload["summary"]["force_gpu_return_receipt_ready"] is False
    assert payload["summary"]["force_gpu_return_receipt_manifest_status_invalid_count"] == 1
    assert payload["summary"]["force_gpu_return_receipt_manifest_status_vocab_ready"] is False
    assert "force_gpu_return_receipt_ready" in payload["summary"]["blockers"]
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_manifest_status_invalid_count"] == 1
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["required_manifest_allowed_ok_status_values"] == [
        "ok",
        "ok_full_regeneration",
        "ok_npz_bundle",
        "ok_regenerated_npz",
    ]
    assert not sidecar.exists()


def test_sidecar_builder_blocks_receipt_with_partial_manifest_row_counts(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    sidecar = tmp_path / "score.pt.json"
    _write_checkpoint(ckpt)

    payload = mod.build_residual_production_checkpoint_sidecar(
        checkpoint_path=str(ckpt),
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": True,
                "missing_production_output_fields": [],
                "policy_output_adapter_ready": True,
                "val_rows": 200,
                "best": {"pr_auc": 0.75},
            }
        ),
        supervised_dataset_packet=_packet({"production_supervised_dataset_ready": True}),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
        training_data_contract_packet=_packet(
            {"status": "residual_production_training_data_contract_ready", "production_training_data_ready": True}
        ),
        force_gpu_return_receipt_packet=_packet(
            {
                "status": "residual_force_gpu_worker_return_receipt_ready",
                "gpu_worker_return_receipt_ready": True,
                "queue_manifest_identity_coverage_ready": True,
                "full_regeneration_manifest_operator_verified": True,
                "manifest_operator_verified_true_count": 1,
                "manifest_ok_row_count": 1,
                "manifest_status_placeholder_count": 0,
                "manifest_status_invalid_count": 0,
                "manifest_allowed_ok_status_values": [
                    "ok",
                    "ok_full_regeneration",
                    "ok_npz_bundle",
                    "ok_regenerated_npz",
                ],
                "expected_queue_rows": 2,
            }
        ),
        sidecar_path=str(sidecar),
    )

    assert payload["summary"]["sidecar_ready"] is False
    assert payload["summary"]["force_gpu_return_receipt_ready"] is False
    assert payload["summary"]["force_gpu_return_receipt_manifest_ok_row_count"] == 1
    assert payload["summary"]["force_gpu_return_receipt_operator_verified_true_count"] == 1
    assert payload["summary"]["force_gpu_return_receipt_expected_queue_rows"] == 2
    assert payload["summary"]["force_gpu_return_receipt_manifest_row_count_ready"] is False
    assert payload["sidecar"]["force_gpu_worker_return_receipt_artifact"]["observed_manifest_ok_row_count"] == 1
    assert not sidecar.exists()


def test_sidecar_builder_cli_writes_outputs(tmp_path: Path) -> None:
    ckpt = tmp_path / "score.pt"
    _write_checkpoint(ckpt)
    score_json = tmp_path / "score.json"
    dataset_json = tmp_path / "dataset.json"
    assist_json = tmp_path / "assist.json"
    public_json = tmp_path / "public.json"
    training_json, receipt_json = _write_ready_contracts(tmp_path)
    score_json.write_text(
        json.dumps(
            _packet(
                {
                    "status": "residual_production_score_model_trained",
                    "production_checkpoint_ready": True,
                    "missing_production_output_fields": [],
                    "policy_output_adapter_ready": True,
                    "val_rows": 200,
                    "best": {"pr_auc": 0.75},
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    dataset_json.write_text(json.dumps(_packet({"production_supervised_dataset_ready": True})) + "\n", encoding="utf-8")
    assist_json.write_text(json.dumps(_packet({"assist_promotion_allowed": True})) + "\n", encoding="utf-8")
    public_json.write_text(json.dumps(_packet({"assist_comparison_gate_ready": True})) + "\n", encoding="utf-8")
    sidecar = tmp_path / "score.pt.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    mod.main(
        [
            "--checkpoint",
            str(ckpt),
            "--score-model-json",
            str(score_json),
            "--supervised-dataset-json",
            str(dataset_json),
            "--assist-gate-json",
            str(assist_json),
            "--public-assist-gate-json",
            str(public_json),
            "--training-data-contract-json",
            str(training_json),
            "--force-gpu-return-receipt-json",
            str(receipt_json),
            "--sidecar-path",
            str(sidecar),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["sidecar_written"] is True
    assert "Residual Production Checkpoint Sidecar" in out_md.read_text(encoding="utf-8")
