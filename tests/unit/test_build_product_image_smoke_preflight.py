from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_image_smoke_preflight as mod


def _container_runtime_proof_fields() -> dict[str, object]:
    return {
        "container_runtime_proof_present": True,
        "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1",
        "container_runtime_proof_ready": True,
        "container_runtime_in_container": True,
        "container_runtime_device_nodes_ready": True,
        "container_runtime_torch_rocm_ready": True,
        "container_runtime_torch_cuda_available": True,
        "container_runtime_visible_device_count": 1,
        "container_runtime_visible_device_name": "AMD Radeon RX 6900 XT",
        "container_runtime_rust_hip_backend_enabled": True,
        "container_runtime_rust_hip_kernel_name": "compute_nonbonded_gpu",
    }


def _hbond_claim_metadata_schema_fields() -> dict[str, object]:
    return {
        "backmapping_hbond_claim_metadata_schema_version": "hbond_evidence_v1",
        "backmapping_hbond_claim_metadata_schema_ready_row_count": 2,
    }


def test_product_image_smoke_preflight_contract_ready_with_docker_path() -> None:
    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker")
    summary = payload["summary"]

    assert summary["status"] == "product_image_smoke_preflight_ready"
    assert summary["preflight_ready"] is True
    assert summary["docker_cli_present"] is True
    assert summary["script_contract_ready"] is True
    assert summary["workflow_contract_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["receipt_present"] is False
    assert summary["container_runtime_receipt_ready"] is False
    assert summary["product_runner_smoke_ready"] is False
    assert summary["product_runner_claim_metadata_ready"] is False
    assert "rocm-runtime" in summary["rocm_runtime_runner_smoke_command"]
    assert payload["blockers"] == []
    assert all(row["execution_enabled"] is False for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_product_image_smoke_preflight_blocks_without_docker_cli() -> None:
    payload = mod.build_product_image_smoke_preflight(docker_cli_path="")
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["docker_cli_present"] is False
    assert {"code": "docker_cli_missing"} in payload["blockers"]
    assert summary["clean_container_smoke_ready"] is False


def test_product_image_smoke_preflight_accepts_rocm_runtime_receipt(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "rocm-runtime",
                "image": "betelgeuze-md-product:test",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": True,
                "product_runner_smoke_ready": True,
                "product_runner_claim_metadata_ready": True,
                "tier_alpha_result_manifest_signature_verified": True,
                "tier_alpha_result_manifest_status": "completed",
                "backmapping_runner_claim_metadata_ready": True,
                **_container_runtime_proof_fields(),
                "backmapping_ligand_topology_valid": True,
                "backmapping_ligand_topology_claim_safe": True,
                "backmapping_ligand_topology_claim_safe_row_count": 2,
                "backmapping_ligand_topology_invalid_row_count": 0,
                "backmapping_ligand_topology_schema_version": "ligand_topology_validity_v1",
                "backmapping_ligand_topology_schema_ready_row_count": 2,
                "backmapping_ligand_topology_receipt_ready": True,
                "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1",
                **_hbond_claim_metadata_schema_fields(),
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 2,
                "backmapping_onsps_backmap_claim_safe_row_count": 1,
                "rocm_runtime_visible_device_required": True,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)
    summary = payload["summary"]

    assert summary["status"] == "product_image_smoke_preflight_ready"
    assert summary["preflight_ready"] is True
    assert summary["clean_container_smoke_ready"] is True
    assert summary["receipt_present"] is True
    assert summary["receipt_status"] == "product_image_smoke_ready"
    assert summary["receipt_mode"] == "rocm-runtime"
    assert summary["receipt_simulate_missing_profile_http"] == 422
    assert summary["container_runtime_proof_schema_version"] == "rocm_container_runtime_proof_v1"
    assert summary["container_runtime_receipt_ready"] is True
    assert summary["container_runtime_in_container"] is True
    assert summary["container_runtime_device_nodes_ready"] is True
    assert summary["container_runtime_torch_rocm_ready"] is True
    assert summary["container_runtime_visible_device_count"] == 1
    assert summary["container_runtime_rust_hip_backend_enabled"] is True
    assert summary["product_runner_smoke_ready"] is True
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["tier_alpha_result_manifest_signature_verified"] is True
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_ligand_topology_valid"] is True
    assert summary["backmapping_ligand_topology_claim_safe"] is True
    assert summary["backmapping_ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert summary["backmapping_ligand_topology_schema_ready_row_count"] == 2
    assert summary["backmapping_ligand_topology_claim_safe_row_count"] == 2
    assert summary["backmapping_ligand_topology_invalid_row_count"] == 0
    assert summary["backmapping_ligand_topology_receipt_ready"] is True
    assert summary["backmapping_hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert summary["backmapping_hbond_claim_metadata_schema_version"] == "hbond_evidence_v1"
    assert summary["backmapping_hbond_claim_metadata_schema_ready_row_count"] == 2
    assert summary["backmapping_onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert summary["backmapping_hbond_evaluated_row_count"] == 2
    assert summary["backmapping_onsps_backmap_claim_safe_row_count"] == 1
    assert summary["backmapping_hbond_evidence_receipt_ready"] is True
    assert summary["backmapping_onsps_backmap_receipt_ready"] is True
    assert summary["container_runner_smoke_receipt_attached"] is True
    assert payload["blockers"] == []


def test_product_image_smoke_preflight_rejects_rocm_receipt_without_container_runtime_proof(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "rocm-runtime",
                "image": "betelgeuze-md-product:test",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": True,
                "product_runner_smoke_ready": True,
                "product_runner_claim_metadata_ready": True,
                "tier_alpha_result_manifest_signature_verified": True,
                "tier_alpha_result_manifest_status": "completed",
                "backmapping_runner_claim_metadata_ready": True,
                "backmapping_ligand_topology_valid": True,
                "backmapping_ligand_topology_claim_safe": True,
                "backmapping_ligand_topology_claim_safe_row_count": 2,
                "backmapping_ligand_topology_invalid_row_count": 0,
                "backmapping_ligand_topology_receipt_ready": True,
                "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1",
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 2,
                "backmapping_onsps_backmap_claim_safe_row_count": 1,
                "rocm_runtime_visible_device_required": True,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)
    summary = payload["summary"]

    assert summary["preflight_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["container_runtime_proof_present"] is False
    assert summary["container_runtime_receipt_ready"] is False
    assert summary["product_runner_claim_metadata_ready"] is True


def test_product_image_smoke_preflight_rejects_rocm_receipt_without_runner_claim_metadata(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "rocm-runtime",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": True,
                "product_runner_smoke_ready": True,
                "product_runner_claim_metadata_ready": False,
                "tier_alpha_result_manifest_signature_verified": True,
                "backmapping_runner_claim_metadata_ready": False,
                "rocm_runtime_visible_device_required": True,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)

    assert payload["summary"]["preflight_ready"] is True
    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert payload["summary"]["product_runner_smoke_ready"] is True
    assert payload["summary"]["product_runner_claim_metadata_ready"] is False
    assert payload["summary"]["backmapping_runner_claim_metadata_ready"] is False


def test_product_image_smoke_preflight_rejects_rocm_receipt_without_backmapping_schema_rows(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "rocm-runtime",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": True,
                "product_runner_smoke_ready": True,
                "product_runner_claim_metadata_ready": True,
                "tier_alpha_result_manifest_signature_verified": True,
                "tier_alpha_result_manifest_status": "completed",
                "backmapping_runner_claim_metadata_ready": True,
                "backmapping_ligand_topology_valid": True,
                "backmapping_ligand_topology_claim_safe": True,
                "backmapping_ligand_topology_claim_safe_row_count": 2,
                "backmapping_ligand_topology_invalid_row_count": 0,
                "backmapping_ligand_topology_receipt_ready": True,
                "backmapping_hbond_evidence_schema_version": "",
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 0,
                "backmapping_onsps_backmap_claim_safe_row_count": 0,
                "rocm_runtime_visible_device_required": True,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)
    summary = payload["summary"]

    assert summary["preflight_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_hbond_evidence_receipt_ready"] is False
    assert summary["backmapping_onsps_backmap_receipt_ready"] is False


def test_product_image_smoke_preflight_rejects_rocm_receipt_without_ligand_topology_gate(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "rocm-runtime",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": True,
                "product_runner_smoke_ready": True,
                "product_runner_claim_metadata_ready": True,
                "tier_alpha_result_manifest_signature_verified": True,
                "tier_alpha_result_manifest_status": "completed",
                "backmapping_runner_claim_metadata_ready": True,
                "backmapping_ligand_topology_valid": True,
                "backmapping_ligand_topology_claim_safe": False,
                "backmapping_ligand_topology_claim_safe_row_count": 0,
                "backmapping_ligand_topology_invalid_row_count": 1,
                "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1",
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 2,
                "backmapping_onsps_backmap_claim_safe_row_count": 1,
                "rocm_runtime_visible_device_required": True,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)
    summary = payload["summary"]

    assert summary["preflight_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_ligand_topology_valid"] is True
    assert summary["backmapping_ligand_topology_claim_safe"] is False
    assert summary["backmapping_ligand_topology_receipt_ready"] is False


def test_product_image_smoke_preflight_rejects_rocm_receipt_without_ligand_topology_schema(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "rocm-runtime",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": True,
                "product_runner_smoke_ready": True,
                "product_runner_claim_metadata_ready": True,
                "tier_alpha_result_manifest_signature_verified": True,
                "tier_alpha_result_manifest_status": "completed",
                "backmapping_runner_claim_metadata_ready": True,
                **_container_runtime_proof_fields(),
                "backmapping_ligand_topology_valid": True,
                "backmapping_ligand_topology_claim_safe": True,
                "backmapping_ligand_topology_claim_safe_row_count": 2,
                "backmapping_ligand_topology_invalid_row_count": 0,
                "backmapping_ligand_topology_receipt_ready": True,
                "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1",
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 2,
                "backmapping_onsps_backmap_claim_safe_row_count": 1,
                "rocm_runtime_visible_device_required": True,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)
    summary = payload["summary"]

    assert summary["preflight_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["backmapping_ligand_topology_schema_version"] == ""
    assert summary["backmapping_ligand_topology_schema_ready_row_count"] == 0
    assert summary["backmapping_ligand_topology_receipt_ready"] is False


def test_product_image_smoke_preflight_rejects_build_mode_receipt(tmp_path: Path) -> None:
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text(
        json.dumps(
            {
                "status": "product_image_smoke_ready",
                "mode": "build",
                "simulate_missing_profile_http": 422,
                "clean_container_smoke_ready": False,
                "product_runner_smoke_ready": False,
                "product_runner_claim_metadata_ready": False,
                "rocm_runtime_visible_device_required": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(docker_cli_path="/usr/bin/docker", receipt_json=receipt_json)

    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert payload["summary"]["receipt_present"] is True
    assert payload["summary"]["receipt_mode"] == "build"


def test_product_image_smoke_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "preflight.json"
    out_md = tmp_path / "preflight.md"

    rc = mod.main(["--out-json", str(out_json), "--out-md", str(out_md)])

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "product_image_smoke_preflight"
    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert "Product Image Smoke Preflight" in out_md.read_text(encoding="utf-8")
