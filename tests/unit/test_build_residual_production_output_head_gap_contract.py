from __future__ import annotations

from tools import build_residual_production_output_head_gap_contract as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_output_head_gap_contract_accepts_delta_force_when_derivation_evidence_ready() -> None:
    payload = mod.build_payload(
        training_data_packet=_packet(
            {
                "production_training_data_ready": True,
                "dataset_label_fields": [
                    "is_binder",
                    "reference_binding_kcal_mol",
                    "delta_score",
                    "corrected_score",
                    "delta_energy",
                ],
                "missing_energy_force_label_fields": ["delta_force"],
                "delta_force_label_evidence_ready": True,
                "uncertainty_learned_output_ready": True,
                "policy_output_fields_ready": True,
                "uncertainty_policy_evidence_ready": True,
            }
        ),
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": True,
                "learned_output_fields": [
                    "delta_score",
                    "corrected_score",
                    "uncertainty",
                    "delta_energy",
                    "delta_force",
                ],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
            }
        ),
        sidecar_packet=_packet(
            {
                "sidecar_ready": True,
                "payload_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
                "adapter_output_policy": {field: f"{field}_policy" for field in mod.REQUIRED_OUTPUT_FIELDS},
            }
        ),
        preflight_packet=_packet(
            {
                "checkpoint_preflight_ready": True,
                "required_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        registry_packet=_packet(
            {
                "production_promotion_allowed": True,
                "checkpoint_missing_output_fields": [],
                "checkpoint_missing_adapter_output_policy_fields": [],
            }
        ),
        work_order_packet=_packet({"checkpoint_closure_blockers": []}),
    )

    summary = payload["summary"]
    assert summary["production_output_heads_complete"] is True
    assert summary["blocked_output_fields"] == []


def test_output_head_gap_contract_identifies_delta_force_as_first_blocker() -> None:
    payload = mod.build_payload(
        training_data_packet=_packet(
            {
                "production_training_data_ready": False,
                "dataset_label_fields": [
                    "is_binder",
                    "reference_binding_kcal_mol",
                    "delta_score",
                    "corrected_score",
                    "delta_energy",
                ],
                "production_missing_output_fields": ["delta_force"],
                "dataset_missing_output_labels": ["delta_force"],
                "uncertainty_learned_output_ready": True,
                "policy_output_fields_ready": True,
            }
        ),
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "production_checkpoint_ready": False,
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty", "delta_energy"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
            }
        ),
        sidecar_packet=_packet(
            {
                "sidecar_ready": False,
                "payload_output_fields": [
                    "delta_score",
                    "corrected_score",
                    "delta_energy",
                    "uncertainty",
                    "abstention_reason",
                    "stage2_route_decision",
                ],
                "adapter_output_policy": {
                    field: f"{field}_policy"
                    for field in [
                        "delta_score",
                        "corrected_score",
                        "delta_energy",
                        "delta_force",
                        "uncertainty",
                        "abstention_reason",
                        "stage2_route_decision",
                    ]
                },
            }
        ),
        preflight_packet=_packet(
            {
                "checkpoint_preflight_ready": False,
                "required_output_fields": list(mod.REQUIRED_OUTPUT_FIELDS),
            }
        ),
        registry_packet=_packet(
            {
                "production_promotion_allowed": False,
                "checkpoint_missing_output_fields": ["delta_force"],
                "checkpoint_missing_adapter_output_policy_fields": [],
            }
        ),
        work_order_packet=_packet(
            {
                "checkpoint_closure_blockers": [
                    "registry_missing_output:delta_force",
                    "sidecar:payload_has_score_outputs",
                ]
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_production_output_head_gap_contract"
    assert summary["output_head_gap_contract_ready"] is True
    assert summary["production_output_heads_complete"] is False
    assert summary["required_output_field_count"] == 7
    assert summary["ready_output_field_count"] == 6
    assert summary["blocked_output_field_count"] == 1
    assert summary["blocked_output_fields"] == ["delta_force"]
    assert summary["registry_output_publication_pending_field_count"] == 1
    assert summary["registry_output_publication_pending_fields"] == ["delta_force"]
    assert summary["first_blocked_output_field"] == "delta_force"
    delta_force = next(row for row in payload["rows"] if row["output_field"] == "delta_force")
    assert delta_force["training_label_ready"] is False
    assert delta_force["score_model_output_ready"] is False
    assert delta_force["sidecar_payload_output_ready"] is False
    assert delta_force["adapter_policy_ready"] is True
    assert delta_force["registry_publication_pending"] is True
    assert "sidecar_payload_output_missing" in delta_force["blockers"]
