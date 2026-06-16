from __future__ import annotations

from pathlib import Path

from tools.product.build_ai_md_contract_source_of_truth_gate import (
    REQUIRED_SOURCE_FILES,
    build_ai_md_contract_source_of_truth_gate,
)


AI_MD_GATE_COMMAND = "python3 tools/product/build_ai_md_contract_source_of_truth_gate.py"


def test_ai_md_contract_source_of_truth_gate_passes_current_contract_surfaces() -> None:
    payload = build_ai_md_contract_source_of_truth_gate()
    summary = payload["summary"]
    rows = {row["check_id"]: row for row in payload["rows"]}

    assert summary["status"] == "ai_md_contract_source_of_truth_gate_ready"
    assert summary["ai_md_contract_source_of_truth_gate_ready"] is True
    assert summary["contract_source_files_ready"] is True
    assert summary["ai_md_contract_layer_ready"] is True
    assert summary["api_evidence_bundle_attachment_ready"] is True
    assert summary["api_runtime_evidence_bundle_surface_ready"] is True
    assert summary["numpy_reference_oracle_ready"] is True
    assert summary["claim_widening_guard_ready"] is True
    assert summary["topology_validity_contract_ready"] is True
    assert summary["topology_factory_adapter_ready"] is True
    assert summary["backmapping_interaction_adapter_ready"] is True
    assert summary["full_commercial_claim_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["blocker_count"] == 0
    assert rows["api_evidence_bundle_adapter_fail_closed"]["status"] == "pass"
    assert rows["api_job_store_evidence_bundle_persistence"]["status"] == "pass"
    assert rows["api_main_evidence_bundle_surface"]["status"] == "pass"
    assert rows["api_worker_evidence_bundle_attachment"]["status"] == "pass"
    assert rows["api_validated_runner_native_evidence_bundle_support"]["status"] == "pass"
    assert rows["api_validated_runner_native_evidence_bundle_support"]["missing_fragment_count"] == 0
    assert "delivery_bundle_validation_not_attached" in rows["api_evidence_bundle_adapter_fail_closed"]["failure_flags"]
    assert rows["api_evidence_bundle_adapter_fail_closed"]["topology_typed"] is True
    assert rows["api_evidence_bundle_adapter_fail_closed"]["topology_fail_closed"] is True
    assert rows["topology_validity_contract_surface"]["status"] == "pass"
    assert rows["topology_validity_contract_surface"]["placeholder_blocked"] is True
    assert rows["topology_validity_contract_surface"]["blocker_blocked"] is True
    assert rows["topology_validity_contract_surface"]["fail_closed_ok"] is True
    assert rows["topology_factory_adapter_surface"]["status"] == "pass"
    assert rows["topology_factory_adapter_surface"]["no_torch_import"] is True
    assert rows["topology_factory_adapter_surface"]["placeholder_ok"] is True
    assert rows["topology_factory_adapter_surface"]["sequence_mapped_ok"] is True
    assert rows["backmapping_interaction_adapter_surface"]["status"] == "pass"
    assert rows["backmapping_interaction_adapter_surface"]["ok_pose_ok"] is True
    assert rows["backmapping_interaction_adapter_surface"]["no_sites_fail_closed"] is True
    assert rows["backmapping_interaction_adapter_surface"]["empty_fail_closed"] is True
    assert rows["backmapping_interaction_adapter_surface"]["missing_ok"] is True
    assert rows["backmapping_interaction_adapter_surface"]["role_invalid_ok"] is True
    assert rows["backmapping_interaction_adapter_surface"]["unsupported_ok"] is True
    assert rows["numpy_reference_oracle_smoke"]["status"] == "pass"


def test_ai_md_contract_source_of_truth_gate_blocks_missing_required_file(tmp_path: Path) -> None:
    payload = build_ai_md_contract_source_of_truth_gate(
        root=Path.cwd(),
        required_source_files=[*REQUIRED_SOURCE_FILES, str(tmp_path / "missing_contract.py")],
    )
    summary = payload["summary"]
    rows = {row["check_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_ai_md_contract_source_of_truth_gate"
    assert summary["ai_md_contract_source_of_truth_gate_ready"] is False
    assert summary["blocker_count"] >= 1
    assert summary["missing_source_file_count"] == 1
    assert rows["required_source_files_present"]["status"] == "fail"


def test_product_release_source_of_truth_tracks_ai_md_contract_gate() -> None:
    from tools.product import build_product_release_source_of_truth_gate as release_mod

    artifact_spec = next(
        spec
        for spec in release_mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "ai_md_contract_source_of_truth_gate"
    )
    status_spec = next(
        spec
        for spec in release_mod.DEFAULT_STATUS_SPECS
        if spec["artifact_id"] == "ai_md_contract_source_of_truth_gate_semantic_ready"
    )

    assert AI_MD_GATE_COMMAND in release_mod.RELEASE_REFRESH_COMMANDS
    assert artifact_spec["artifact_path"] == "runs/ai_md_contract_source_of_truth_gate_current.json"
    assert artifact_spec["builder_command"] == AI_MD_GATE_COMMAND
    assert "api/job_store.py" in artifact_spec["depends_on"]
    assert "api/main.py" in artifact_spec["depends_on"]
    assert "api/models.py" in artifact_spec["depends_on"]
    assert "api/validated_runner.py" in artifact_spec["depends_on"]
    assert "api/worker.py" in artifact_spec["depends_on"]
    assert "betelgeuze_ai_md/contracts/api_adapter.py" in artifact_spec["depends_on"]
    assert "betelgeuze_ai_md/contracts/topology_adapter.py" in artifact_spec["depends_on"]
    assert "betelgeuze_ai_md/contracts/backmapping_adapter.py" in artifact_spec["depends_on"]
    assert "betelgeuze_ai_md/contracts/interaction_adapter.py" in artifact_spec["depends_on"]
    assert "betelgeuze_ai_md/coarse_md/numpy_ref.py" in artifact_spec["depends_on"]
    assert "tools/product/validate_api_runner_profiles.py" in artifact_spec["depends_on"]
    assert "tests/unit/test_betelgeuze_ai_md_topology_adapter.py" in artifact_spec["depends_on"]
    assert "tests/unit/test_betelgeuze_ai_md_backmapping_interaction_adapters.py" in artifact_spec["depends_on"]
    assert "tests/unit/test_api_validated_runner_adapter.py" in artifact_spec["depends_on"]
    assert "tests/unit/test_api_job_store.py" in artifact_spec["depends_on"]
    assert status_spec["required_status"] == "ai_md_contract_source_of_truth_gate_ready"
    assert "api_evidence_bundle_attachment_ready" in status_spec["required_true_fields"]
    assert "api_runtime_evidence_bundle_surface_ready" in status_spec["required_true_fields"]
    assert "numpy_reference_oracle_ready" in status_spec["required_true_fields"]
    assert "topology_validity_contract_ready" in status_spec["required_true_fields"]
    assert "topology_factory_adapter_ready" in status_spec["required_true_fields"]
    assert "backmapping_interaction_adapter_ready" in status_spec["required_true_fields"]
    assert status_spec["required_int_exact_fields"]["full_commercial_claim_allowed"] == 0
