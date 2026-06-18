from __future__ import annotations

import json
import tarfile
from pathlib import Path

from tools.product import build_ai_md_product_evidence_bundle as mod


def _write(path: Path, payload: str = "artifact\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def _kpi_packet(
    *,
    ready: bool,
    runner_claim_metadata_signed: bool = True,
    force_term_claim_metadata_ready: bool = True,
    force_term_claim_metadata_schema_ready: bool = True,
    core_forcefield_bridge_ready: bool = True,
    core_compatibility_layer_ready: bool = True,
    force_residual_bounded_policy_ready: bool = True,
    force_residual_confidence_abstention_ready: bool = True,
    force_term_physics_validation_ready: bool = True,
    manifest_ligand_topology_claim_safe: bool = True,
) -> dict:
    force_term_rows = [
        {
            "force_term_name": "directional_hbond",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
        {
            "force_term_name": "hydrophobic_contact",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
        {
            "force_term_name": "legacy_lj",
            "force_term_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    ] if force_term_claim_metadata_schema_ready else []
    return {
        "packet_type": "ai_md_engine_kpi_report",
        "status": "ai_md_engine_kpi_report_ready" if ready else "blocked_ai_md_engine_kpi_report",
        "report_ready": ready,
        "product_kpi": {
            "runner_claim_metadata_signed": runner_claim_metadata_signed,
            "runner_claim_metadata_manifest_smoke": {
                "ready": runner_claim_metadata_signed,
                "manifest_ligand_topology_valid": manifest_ligand_topology_claim_safe,
                "manifest_ligand_topology_claim_safe": manifest_ligand_topology_claim_safe,
                "manifest_ligand_topology_claim_safe_row_count": 2
                if manifest_ligand_topology_claim_safe
                else 0,
            },
            "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
            "force_term_claim_metadata_smoke": {
                "ready": force_term_claim_metadata_ready,
                "forcefield_claim_metadata_schema_version": "force_term_claim_metadata_v1"
                if force_term_claim_metadata_schema_ready
                else "",
                "forcefield_claim_safe_count": len(force_term_rows),
                "forcefield_blocked_count": 0,
                "forcefield_claim_rows": force_term_rows,
            },
            "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
            "core_forcefield_bridge_smoke": {"ready": core_forcefield_bridge_ready},
            "core_compatibility_layer_ready": core_compatibility_layer_ready,
            "core_compatibility_layer_smoke": {"ready": core_compatibility_layer_ready},
        },
        "pm_kpi_summary": {
            "runtime": {
                "force_residual_bounded_policy_ready": force_residual_bounded_policy_ready,
                "force_residual_confidence_abstention_ready": force_residual_confidence_abstention_ready,
            },
            "physics": {
                "force_term_physics_validation_ready": force_term_physics_validation_ready,
            },
            "product": {
                "runner_claim_metadata_signed": runner_claim_metadata_signed,
                "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
                "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
                "core_compatibility_layer_ready": core_compatibility_layer_ready,
            }
        },
    }


def _rocm_packet(*, ready: bool) -> dict:
    return {
        "summary": {
            "status": "rocm_environment_manifest_ready",
            "manifest_ready": True,
            "commercial_compute_default": "rocm_hip",
            "torch_rocm_ready": ready,
            "visible_device_count": 1 if ready else 0,
            "device_nodes_ready": ready,
            "production_execution_ready": ready,
            "cpu_fallback_allowed_for_product": False,
        }
    }


def _image_preflight_packet(*, clean_ready: bool) -> dict:
    return {
        "summary": {
            "status": "product_image_smoke_preflight_ready" if clean_ready else "blocked_product_image_smoke_preflight",
            "preflight_ready": clean_ready,
            "clean_container_smoke_ready": clean_ready,
            "receipt_present": clean_ready,
            "receipt_status": "product_image_smoke_ready" if clean_ready else "",
            "receipt_mode": "rocm-runtime" if clean_ready else "",
            "receipt_simulate_missing_profile_http": 422 if clean_ready else 0,
            "container_runtime_receipt_ready": clean_ready,
            "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1" if clean_ready else "",
            "container_runtime_in_container": clean_ready,
            "container_runtime_device_nodes_ready": clean_ready,
            "container_runtime_torch_rocm_ready": clean_ready,
            "container_runtime_torch_cuda_available": clean_ready,
            "container_runtime_visible_device_count": 1 if clean_ready else 0,
            "container_runtime_rust_hip_backend_enabled": clean_ready,
            "product_runner_smoke_ready": clean_ready,
            "product_runner_claim_metadata_ready": clean_ready,
            "tier_alpha_result_manifest_signature_verified": clean_ready,
            "tier_alpha_result_manifest_status": "completed" if clean_ready else "",
            "backmapping_runner_claim_metadata_ready": clean_ready,
            "backmapping_ligand_topology_valid": clean_ready,
            "backmapping_ligand_topology_claim_safe": clean_ready,
            "backmapping_ligand_topology_claim_safe_row_count": 2 if clean_ready else 0,
            "backmapping_ligand_topology_invalid_row_count": 0,
            "backmapping_ligand_topology_receipt_ready": clean_ready,
            "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1" if clean_ready else "",
            "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1" if clean_ready else "",
            "backmapping_hbond_evaluated_row_count": 2 if clean_ready else 0,
            "backmapping_onsps_backmap_claim_safe_row_count": 1 if clean_ready else 0,
            "backmapping_hbond_evidence_receipt_ready": clean_ready,
            "backmapping_onsps_backmap_receipt_ready": clean_ready,
        }
    }


def _artifact_specs(tmp_path: Path, *, kpi_packet: dict | None = None) -> list[dict[str, object]]:
    kpi_packet = kpi_packet or _kpi_packet(ready=True)
    return [
        {
            "artifact_id": "kpi_json",
            "artifact_path": str(_write(tmp_path / "kpi.json", json.dumps(kpi_packet))),
            "role": "local_pc_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "kpi_md",
            "artifact_path": str(_write(tmp_path / "kpi.md")),
            "role": "human_readable_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "rocm",
            "artifact_path": str(_write(tmp_path / "rocm.json", json.dumps(_rocm_packet(ready=True)))),
            "role": "gpu_rocm_hip_runtime_gate",
            "required": True,
        },
        {
            "artifact_id": "image_preflight",
            "artifact_path": str(_write(tmp_path / "image_preflight.json", json.dumps(_image_preflight_packet(clean_ready=True)))),
            "role": "clean_container_smoke_gate",
            "required": True,
        },
        {
            "artifact_id": "doc",
            "artifact_path": str(_write(tmp_path / "next.md")),
            "role": "engineering_plan",
            "required": True,
        },
    ]


def test_ai_md_product_evidence_bundle_exports_claim_ready_tar(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is True
    assert summary["runner_claim_metadata_signed"] is True
    assert summary["force_term_claim_metadata_ready"] is True
    assert summary["core_forcefield_bridge_ready"] is True
    assert summary["core_compatibility_layer_ready"] is True
    assert summary["kpi_claim_metadata_gates_validated"] is True
    assert summary["kpi_claim_metadata_gate_count"] == 1
    assert summary["kpi_claim_metadata_gate_validated_count"] == 1
    assert summary["rocm_hip_rust_runtime_ready"] is True
    assert summary["clean_container_smoke_ready"] is True
    assert summary["product_image_receipt_present"] is True
    assert summary["container_runtime_receipt_ready"] is True
    assert summary["container_runtime_proof_schema_version"] == "rocm_container_runtime_proof_v1"
    assert summary["container_runtime_in_container"] is True
    assert summary["container_runtime_visible_device_count"] == 1
    assert summary["container_runtime_rust_hip_backend_enabled"] is True
    assert summary["product_runner_smoke_ready"] is True
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["product_image_receipt_mode"] == "rocm-runtime"
    assert summary["tier_alpha_result_manifest_signature_verified"] is True
    assert summary["tier_alpha_result_manifest_status"] == "completed"
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_ligand_topology_receipt_ready"] is True
    assert summary["backmapping_ligand_topology_valid"] is True
    assert summary["backmapping_ligand_topology_claim_safe"] is True
    assert summary["backmapping_ligand_topology_claim_safe_row_count"] == 2
    assert summary["backmapping_ligand_topology_invalid_row_count"] == 0
    assert summary["backmapping_hbond_evidence_receipt_ready"] is True
    assert summary["backmapping_onsps_backmap_receipt_ready"] is True
    assert summary["backmapping_hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert summary["backmapping_onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert summary["backmapping_hbond_evaluated_row_count"] == 2
    assert summary["backmapping_onsps_backmap_claim_safe_row_count"] == 1
    assert summary["cpu_fallback_allowed_for_product"] is False
    assert summary["bundle_validation_pass"] is True
    assert summary["bundle_validation_error_count"] == 0
    assert summary["bundle_validation_errors"] == []
    assert len(summary["bundle_tar_sha256"]) == 64
    assert payload["blockers"] == []
    assert all(row["execution_enabled"] is False for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])

    with tarfile.open(out_tar, "r:gz") as tar:
        assert set(tar.getnames()) == {row["bundle_arcname"] for row in payload["rows"]}
    validation = mod.validate_product_evidence_bundle(bundle_packet=payload)
    assert validation["bundle_validation_pass"] is True
    assert validation["kpi_claim_metadata_gates_validated"] is True
    assert validation["bundle_validation_error_count"] == 0

    source_kpi = Path(payload["rows"][0]["artifact_path"])
    source_kpi.write_text("local source changed after tar export\n", encoding="utf-8")
    validation_after_local_change = mod.validate_product_evidence_bundle(bundle_packet=payload)
    assert validation_after_local_change["bundle_validation_pass"] is True
    assert validation_after_local_change["bundle_validation_error_count"] == 0


def test_ai_md_product_evidence_bundle_exports_blocked_claim_when_gpu_not_visible(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=False),
        rocm_manifest_packet=_rocm_packet(ready=False),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["rocm_hip_rust_runtime_ready"] is False
    assert {"code": "rocm_hip_rust_runtime_not_ready"} in payload["blockers"]
    assert {"code": "kpi_report_not_ready"} in payload["blockers"]


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_clean_container_smoke(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=False),
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["status"] == "ai_md_product_evidence_bundle_ready"
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["next_required_step"].startswith("Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime")
    assert {"code": "clean_container_smoke_not_ready"} in payload["blockers"]


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_backmapping_schema_receipt(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["backmapping_hbond_evidence_schema_version"] = ""
    image_packet["summary"]["backmapping_hbond_evaluated_row_count"] = 0
    image_packet["summary"]["backmapping_hbond_evidence_receipt_ready"] = False

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["product_runner_smoke_ready"] is True
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["backmapping_runner_claim_metadata_ready"] is True
    assert summary["backmapping_hbond_evidence_receipt_ready"] is False
    assert summary["backmapping_onsps_backmap_receipt_ready"] is True
    assert {"code": "clean_container_smoke_not_ready"} in payload["blockers"]


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_ligand_topology_receipt(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["backmapping_ligand_topology_claim_safe"] = False
    image_packet["summary"]["backmapping_ligand_topology_claim_safe_row_count"] = 0
    image_packet["summary"]["backmapping_ligand_topology_invalid_row_count"] = 1
    image_packet["summary"]["backmapping_ligand_topology_receipt_ready"] = False

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["backmapping_ligand_topology_valid"] is True
    assert summary["backmapping_ligand_topology_claim_safe"] is False
    assert summary["backmapping_ligand_topology_receipt_ready"] is False
    assert {"code": "clean_container_smoke_not_ready"} in payload["blockers"]


def test_ai_md_product_evidence_bundle_rejects_clean_container_without_runtime_proof(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["container_runtime_receipt_ready"] = False
    image_packet["summary"]["container_runtime_proof_schema_version"] = ""
    image_packet["summary"]["container_runtime_in_container"] = False
    image_packet["summary"]["container_runtime_visible_device_count"] = 0
    image_packet["summary"]["container_runtime_rust_hip_backend_enabled"] = False

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["container_runtime_receipt_ready"] is False
    assert summary["container_runtime_in_container"] is False
    assert summary["container_runtime_visible_device_count"] == 0
    assert summary["container_runtime_rust_hip_backend_enabled"] is False
    assert summary["product_runner_claim_metadata_ready"] is True
    assert {"code": "clean_container_smoke_not_ready"} in payload["blockers"]


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_signed_runner_metadata_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, runner_claim_metadata_signed=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["runner_claim_metadata_signed"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "runner_claim_metadata_not_signed"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_runner_claim_metadata_not_signed:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_signed_ligand_topology_metadata(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, manifest_ligand_topology_claim_safe=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_manifest_ligand_topology_claim_safe_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_manifest_ligand_topology_claim_safe_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_term_claim_schema(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_term_claim_metadata_schema_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_force_term_claim_metadata_schema_missing:")
        for error in summary["bundle_validation_errors"]
    )
    assert any(
        error.startswith("kpi_force_term_claim_rows_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_core_forcefield_bridge_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, core_forcefield_bridge_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["core_forcefield_bridge_ready"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "core_forcefield_bridge_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_forcefield_bridge_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_product_claim_without_core_compatibility_layer_gate(
    tmp_path: Path,
) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, core_compatibility_layer_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert summary["core_compatibility_layer_ready"] is False
    assert summary["kpi_claim_metadata_gates_validated"] is False
    assert {"code": "core_compatibility_layer_not_ready"} in payload["blockers"]
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("kpi_core_compatibility_layer_not_ready:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_residual_bounded_policy_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_residual_bounded_policy_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_residual_bounded_policy_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_blocks_without_force_term_physics_gate(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    kpi_packet = _kpi_packet(ready=True, force_term_physics_validation_ready=False)

    payload = mod.build_payload(
        kpi_packet=kpi_packet,
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=_artifact_specs(tmp_path, kpi_packet=kpi_packet),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is False
    assert summary["product_claim_ready"] is False
    assert {"code": "kpi_claim_metadata_gates_not_validated"} in payload["blockers"]
    assert any(
        error.startswith("pm_force_term_physics_validation_gate_missing:")
        for error in summary["bundle_validation_errors"]
    )


def test_ai_md_product_evidence_bundle_rejects_build_mode_receipt_for_product_claim(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    image_packet = _image_preflight_packet(clean_ready=True)
    image_packet["summary"]["receipt_mode"] = "build"

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=image_packet,
        artifact_specs=_artifact_specs(tmp_path),
        out_tar=str(out_tar),
    )

    summary = payload["summary"]
    assert summary["bundle_export_ready"] is True
    assert summary["bundle_validation_pass"] is True
    assert summary["product_claim_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["product_image_receipt_mode"] == "build"
    assert summary["next_required_step"].startswith("Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime")
    assert {"code": "clean_container_smoke_not_ready"} in payload["blockers"]


def test_ai_md_product_evidence_bundle_blocks_missing_required_artifact(tmp_path: Path) -> None:
    out_tar = tmp_path / "bundle.tar.gz"
    specs = _artifact_specs(tmp_path)
    specs.append(
        {
            "artifact_id": "missing_required",
            "artifact_path": str(tmp_path / "missing.json"),
            "role": "required_evidence",
            "required": True,
        }
    )

    payload = mod.build_payload(
        kpi_packet=_kpi_packet(ready=True),
        rocm_manifest_packet=_rocm_packet(ready=True),
        product_image_preflight_packet=_image_preflight_packet(clean_ready=True),
        artifact_specs=specs,
        out_tar=str(out_tar),
    )

    assert payload["summary"]["status"] == "blocked_ai_md_product_evidence_bundle"
    assert payload["summary"]["bundle_export_ready"] is False
    assert payload["summary"]["required_artifact_missing_count"] == 1
    assert not out_tar.exists()


def test_ai_md_product_evidence_bundle_cli_writes_outputs(tmp_path: Path) -> None:
    kpi_json = _write(tmp_path / "kpi.json", json.dumps(_kpi_packet(ready=True)))
    kpi_md = _write(tmp_path / "kpi.md")
    rocm_json = _write(tmp_path / "rocm.json", json.dumps(_rocm_packet(ready=True)))
    image_preflight_json = _write(tmp_path / "image_preflight.json", json.dumps(_image_preflight_packet(clean_ready=True)))
    next_doc = _write(tmp_path / "next.md")
    out_tar = tmp_path / "bundle.tar.gz"
    out_json = tmp_path / "bundle.json"
    out_csv = tmp_path / "bundle.csv"
    out_md = tmp_path / "bundle.md"

    rc = mod.main(
        [
            "--kpi-json",
            str(kpi_json),
            "--kpi-md",
            str(kpi_md),
            "--rocm-manifest-json",
            str(rocm_json),
            "--product-image-preflight-json",
            str(image_preflight_json),
            "--next-steps-doc",
            str(next_doc),
            "--out-tar",
            str(out_tar),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["bundle_export_ready"] is True
    assert out_tar.exists()
    assert out_csv.read_text(encoding="utf-8").startswith("artifact_id,")
    assert out_md.read_text(encoding="utf-8").startswith("# AI-MD Product Evidence Bundle")
