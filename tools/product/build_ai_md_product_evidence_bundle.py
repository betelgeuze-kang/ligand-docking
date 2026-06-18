#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KPI_JSON = "runs/ai_md_engine_kpi_report_current.json"
DEFAULT_KPI_MD = "runs/ai_md_engine_kpi_report_current.md"
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_PRODUCT_IMAGE_RECEIPT_JSON = "runs/product_image_smoke_receipt_current.json"
DEFAULT_NEXT_STEPS_DOC = "docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md"
DEFAULT_OUT_TAR = "runs/ai_md_product_evidence_bundle_current.tar.gz"
DEFAULT_OUT_JSON = "runs/ai_md_product_evidence_bundle_current.json"
DEFAULT_OUT_CSV = "runs/ai_md_product_evidence_bundle_current.csv"
DEFAULT_OUT_MD = "runs/ai_md_product_evidence_bundle_current.md"

CLAIM_BOUNDARY = (
    "AI-MD product evidence bundle export only; packages local ROCm/HIP/Rust runtime contracts, KPI reports, "
    "runner profile evidence, and implementation documents. It does not run docking, run GPU jobs, train models, "
    "promote claims, upload, submit, email, delete files, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _arcname(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return f"external_inputs/{_sha256_file(path)[:12]}_{path.name}"


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bool_nested(payload: dict[str, Any], *keys: str) -> bool:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return False
        current = current.get(key)
    return current is True


def _validate_kpi_claim_metadata_gates(
    *,
    artifact_id: str,
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("packet_type") != "ai_md_engine_kpi_report":
        errors.append(f"kpi_json_packet_type_invalid:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "runner_claim_metadata_signed"):
        errors.append(f"kpi_runner_claim_metadata_not_signed:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "force_term_claim_metadata_ready"):
        errors.append(f"kpi_force_term_claim_metadata_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_forcefield_bridge_ready"):
        errors.append(f"kpi_core_forcefield_bridge_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_compatibility_layer_ready"):
        errors.append(f"kpi_core_compatibility_layer_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "runner_claim_metadata_manifest_smoke", "ready"):
        errors.append(f"kpi_runner_claim_metadata_manifest_smoke_not_ready:{artifact_id}")
    manifest_smoke = (
        payload.get("product_kpi", {}).get("runner_claim_metadata_manifest_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(manifest_smoke, dict):
        manifest_smoke = {}
    if manifest_smoke.get("manifest_ligand_topology_valid") is not True:
        errors.append(f"kpi_manifest_ligand_topology_valid_missing:{artifact_id}")
    if manifest_smoke.get("manifest_ligand_topology_claim_safe") is not True:
        errors.append(f"kpi_manifest_ligand_topology_claim_safe_missing:{artifact_id}")
    if _int_value(manifest_smoke.get("manifest_ligand_topology_claim_safe_row_count")) < 1:
        errors.append(f"kpi_manifest_ligand_topology_claim_safe_rows_missing:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "force_term_claim_metadata_smoke", "ready"):
        errors.append(f"kpi_force_term_claim_metadata_smoke_not_ready:{artifact_id}")
    force_term_smoke = (
        payload.get("product_kpi", {}).get("force_term_claim_metadata_smoke", {})
        if isinstance(payload.get("product_kpi"), dict)
        else {}
    )
    if not isinstance(force_term_smoke, dict):
        force_term_smoke = {}
    forcefield_claim_rows = force_term_smoke.get("forcefield_claim_rows")
    if not isinstance(forcefield_claim_rows, list):
        forcefield_claim_rows = []
    if force_term_smoke.get("forcefield_claim_metadata_schema_version") != "force_term_claim_metadata_v1":
        errors.append(f"kpi_force_term_claim_metadata_schema_missing:{artifact_id}")
    if _int_value(force_term_smoke.get("forcefield_claim_safe_count")) < 1:
        errors.append(f"kpi_force_term_claim_safe_rows_missing:{artifact_id}")
    if _int_value(force_term_smoke.get("forcefield_blocked_count")) != 0:
        errors.append(f"kpi_force_term_blocked_rows_present:{artifact_id}")
    if not forcefield_claim_rows:
        errors.append(f"kpi_force_term_claim_rows_missing:{artifact_id}")
    elif not all(
        isinstance(row, dict)
        and row.get("claim_safe") is True
        and str(row.get("force_term_name") or "")
        and str(row.get("force_term_status") or "") == "pass"
        for row in forcefield_claim_rows
    ):
        errors.append(f"kpi_force_term_claim_rows_not_safe:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_forcefield_bridge_smoke", "ready"):
        errors.append(f"kpi_core_forcefield_bridge_smoke_not_ready:{artifact_id}")
    if not _bool_nested(payload, "product_kpi", "core_compatibility_layer_smoke", "ready"):
        errors.append(f"kpi_core_compatibility_layer_smoke_not_ready:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "runner_claim_metadata_signed"):
        errors.append(f"pm_runner_claim_metadata_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "force_term_claim_metadata_ready"):
        errors.append(f"pm_force_term_claim_metadata_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "core_forcefield_bridge_ready"):
        errors.append(f"pm_core_forcefield_bridge_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "product", "core_compatibility_layer_ready"):
        errors.append(f"pm_core_compatibility_layer_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_bounded_policy_ready"):
        errors.append(f"pm_force_residual_bounded_policy_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "runtime", "force_residual_confidence_abstention_ready"):
        errors.append(f"pm_force_residual_confidence_abstention_gate_missing:{artifact_id}")
    if not _bool_nested(payload, "pm_kpi_summary", "physics", "force_term_physics_validation_ready"):
        errors.append(f"pm_force_term_physics_validation_gate_missing:{artifact_id}")
    return errors


def _rocm_product_runtime_ready(rocm_summary: dict[str, Any]) -> bool:
    visible_device_count = int(rocm_summary.get("visible_device_count") or 0)
    production_execution_ready = rocm_summary.get("production_execution_ready")
    production_ready = bool(production_execution_ready) if production_execution_ready is not None else visible_device_count > 0
    return bool(
        rocm_summary.get("commercial_compute_default") == "rocm_hip"
        and rocm_summary.get("torch_rocm_ready") is True
        and visible_device_count > 0
        and rocm_summary.get("device_nodes_ready", True) is True
        and production_ready
        and rocm_summary.get("cpu_fallback_allowed_for_product", False) is False
    )


def _default_artifacts(
    *,
    kpi_json: str,
    kpi_md: str,
    rocm_manifest_json: str,
    product_image_preflight_json: str,
    product_image_receipt_json: str,
    next_steps_doc: str,
) -> list[dict[str, Any]]:
    return [
        {
            "artifact_id": "ai_md_engine_kpi_report_json",
            "artifact_path": kpi_json,
            "role": "local_pc_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "ai_md_engine_kpi_report_md",
            "artifact_path": kpi_md,
            "role": "human_readable_runtime_report",
            "required": True,
        },
        {
            "artifact_id": "rocm_environment_manifest_json",
            "artifact_path": rocm_manifest_json,
            "role": "gpu_rocm_hip_runtime_gate",
            "required": True,
        },
        {
            "artifact_id": "product_image_smoke_preflight_json",
            "artifact_path": product_image_preflight_json,
            "role": "clean_container_smoke_gate",
            "required": True,
        },
        {
            "artifact_id": "product_image_smoke_receipt_json",
            "artifact_path": product_image_receipt_json,
            "role": "clean_container_rocm_runtime_receipt",
            "required": False,
        },
        {
            "artifact_id": "next_steps_doc",
            "artifact_path": next_steps_doc,
            "role": "engineering_plan",
            "required": True,
        },
        {
            "artifact_id": "product_dockerfile",
            "artifact_path": "Dockerfile.product",
            "role": "rocm_hip_rust_container_contract",
            "required": True,
        },
        {
            "artifact_id": "product_rocm_requirements",
            "artifact_path": "requirements-product-rocm.txt",
            "role": "torch_rocm_dependency_contract",
            "required": True,
        },
        {
            "artifact_id": "backmapping_runner_profile",
            "artifact_path": "config/api_validated_runner_profiles/backmapping_scoring.production.json",
            "role": "allowlisted_runner_profile",
            "required": True,
        },
        {
            "artifact_id": "product_end_to_end_rocm_benchmark_json",
            "artifact_path": "runs/product_end_to_end_rocm_benchmark_current.json",
            "role": "optional_end_to_end_rocm_benchmark",
            "required": False,
        },
    ]


def _artifact_rows(artifact_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in artifact_specs:
        artifact_path = str(spec.get("artifact_path") or "")
        path = _resolve(artifact_path)
        key = f"{spec.get('artifact_id')}::{path}"
        if key in seen:
            continue
        seen.add(key)
        exists = path.exists() and path.is_file()
        rows.append(
            {
                "artifact_id": str(spec.get("artifact_id") or path.name),
                "artifact_path": artifact_path,
                "role": str(spec.get("role") or "evidence"),
                "required": bool(spec.get("required", True)),
                "exists": exists,
                "missing": not exists,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size if exists else 0,
                "bundle_arcname": _arcname(path) if exists else "",
                "included_in_bundle": exists,
                "release_blocker": bool(spec.get("required", True) and not exists),
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return rows


def _write_tar(path_like: str | Path, rows: list[dict[str, Any]]) -> tuple[bool, int, int, str]:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    included = [row for row in rows if row["included_in_bundle"] is True]
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for row in included:
            tar.add(_resolve(str(row["artifact_path"])), arcname=str(row["bundle_arcname"]), recursive=False)
    return path.exists(), path.stat().st_size if path.exists() else 0, len(included), _sha256_file(path)


def validate_product_evidence_bundle(
    *,
    bundle_packet: dict[str, Any],
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    summary = _summary(bundle_packet)
    rows = [dict(row) for row in bundle_packet.get("rows") or [] if isinstance(row, dict)]
    included_rows = [row for row in rows if row.get("included_in_bundle") is True]
    errors: list[str] = []
    kpi_rows = [
        row
        for row in included_rows
        if str(row.get("role") or "") == "local_pc_runtime_report"
        and str(row.get("bundle_arcname") or "")
    ]
    kpi_claim_metadata_gate_count = 0
    kpi_claim_metadata_gate_validated_count = 0

    tar_path_text = str(summary.get("bundle_tar_path") or "")
    tar_path = Path(tar_path_text)
    if tar_path_text:
        tar_path = tar_path if tar_path.is_absolute() else root_path / tar_path
    tar_member_sha256: dict[str, str] = {}
    if not tar_path_text or not tar_path.exists() or not tar_path.is_file():
        errors.append("bundle_tar_missing")
        tar_names: set[str] = set()
        tar_sha = ""
    else:
        tar_sha = _sha256_file(tar_path)
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                members = [member for member in tar.getmembers() if member.isfile()]
                tar_names = {member.name for member in members}
                kpi_arcnames = {str(row.get("bundle_arcname") or "") for row in kpi_rows}
                for member in members:
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        errors.append(f"bundle_tar_member_unreadable:{member.name}")
                        continue
                    h = hashlib.sha256()
                    member_chunks: list[bytes] = []
                    collect_json = member.name in kpi_arcnames
                    for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                        h.update(chunk)
                        if collect_json:
                            member_chunks.append(chunk)
                    tar_member_sha256[member.name] = h.hexdigest()
                    if collect_json:
                        artifact_id = next(
                            str(row.get("artifact_id") or member.name)
                            for row in kpi_rows
                            if str(row.get("bundle_arcname") or "") == member.name
                        )
                        kpi_claim_metadata_gate_count += 1
                        try:
                            payload = json.loads(b"".join(member_chunks).decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            errors.append(f"kpi_json_unreadable:{artifact_id}")
                            continue
                        if not isinstance(payload, dict):
                            errors.append(f"kpi_json_not_object:{artifact_id}")
                            continue
                        kpi_errors = _validate_kpi_claim_metadata_gates(
                            artifact_id=artifact_id,
                            payload=payload,
                        )
                        errors.extend(kpi_errors)
                        if not kpi_errors:
                            kpi_claim_metadata_gate_validated_count += 1
        except tarfile.TarError:
            tar_names = set()
            errors.append("bundle_tar_unreadable")

    expected_names = {str(row.get("bundle_arcname") or "") for row in included_rows if row.get("bundle_arcname")}
    if tar_names != expected_names:
        errors.append("bundle_tar_members_mismatch")
    if int(summary.get("bundle_tar_member_count") or 0) != len(included_rows):
        errors.append("bundle_tar_member_count_mismatch")
    if tar_sha and str(summary.get("bundle_tar_sha256") or "") != tar_sha:
        errors.append("bundle_tar_sha256_mismatch")

    for row in rows:
        artifact_path = str(row.get("artifact_path") or "")
        path = Path(artifact_path)
        resolved = path if path.is_absolute() else root_path / path
        if row.get("included_in_bundle") is True:
            arcname = str(row.get("bundle_arcname") or "")
            member_sha = tar_member_sha256.get(arcname)
            if not member_sha:
                errors.append(f"bundle_tar_member_missing:{row.get('artifact_id')}")
                continue
            if str(row.get("sha256") or "") != member_sha:
                errors.append(f"artifact_sha256_mismatch:{row.get('artifact_id')}")
            continue
        if row.get("required") is True and not resolved.exists():
            errors.append(f"required_artifact_missing:{row.get('artifact_id')}")
            continue
        if row.get("exists") is True:
            actual_sha = _sha256_file(resolved)
            if actual_sha and str(row.get("sha256") or "") != actual_sha:
                errors.append(f"artifact_sha256_mismatch:{row.get('artifact_id')}")

    pass_ready = bool(summary.get("bundle_export_ready") is True and included_rows and not errors)
    return {
        "bundle_validation_pass": pass_ready,
        "bundle_validation_checked": True,
        "bundle_validation_error_count": len(errors),
        "bundle_validation_errors": errors,
        "bundle_validation_tar_member_count": len(tar_names),
        "bundle_validation_expected_member_count": len(expected_names),
        "kpi_claim_metadata_gate_count": kpi_claim_metadata_gate_count,
        "kpi_claim_metadata_gate_validated_count": kpi_claim_metadata_gate_validated_count,
        "kpi_claim_metadata_gates_validated": bool(
            kpi_claim_metadata_gate_count > 0
            and kpi_claim_metadata_gate_validated_count == kpi_claim_metadata_gate_count
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_payload(
    *,
    kpi_packet: dict[str, Any],
    rocm_manifest_packet: dict[str, Any],
    product_image_preflight_packet: dict[str, Any],
    artifact_specs: list[dict[str, Any]],
    out_tar: str = DEFAULT_OUT_TAR,
) -> dict[str, Any]:
    rows = _artifact_rows(artifact_specs)
    missing_required = [row for row in rows if row["required"] is True and row["exists"] is not True]
    kpi_summary = _summary(kpi_packet)
    rocm_summary = _summary(rocm_manifest_packet)
    image_summary = _summary(product_image_preflight_packet)
    kpi_ready = bool(kpi_summary.get("status") == "ai_md_engine_kpi_report_ready" and kpi_summary.get("report_ready") is True)
    product_kpi = kpi_summary.get("product_kpi") if isinstance(kpi_summary.get("product_kpi"), dict) else {}
    runner_claim_metadata_signed = bool(product_kpi.get("runner_claim_metadata_signed") is True)
    force_term_claim_metadata_ready = bool(product_kpi.get("force_term_claim_metadata_ready") is True)
    core_forcefield_bridge_ready = bool(product_kpi.get("core_forcefield_bridge_ready") is True)
    core_compatibility_layer_ready = bool(product_kpi.get("core_compatibility_layer_ready") is True)
    rocm_ready = _rocm_product_runtime_ready(rocm_summary)
    image_hbond_evidence_receipt_ready = bool(
        image_summary.get("backmapping_hbond_evidence_receipt_ready") is True
        or (
            image_summary.get("backmapping_hbond_evidence_schema_version") == "hbond_evidence_v1"
            and _int_value(image_summary.get("backmapping_hbond_evaluated_row_count")) >= 1
        )
    )
    image_onsps_backmap_receipt_ready = bool(
        image_summary.get("backmapping_onsps_backmap_receipt_ready") is True
        or (
            image_summary.get("backmapping_onsps_backmap_schema_version") == "onsps_backmap_evidence_v1"
            and _int_value(image_summary.get("backmapping_onsps_backmap_claim_safe_row_count")) >= 1
        )
    )
    image_ligand_topology_receipt_ready = bool(
        image_summary.get("backmapping_ligand_topology_receipt_ready") is True
        or (
            image_summary.get("backmapping_ligand_topology_valid") is True
            and image_summary.get("backmapping_ligand_topology_claim_safe") is True
            and _int_value(image_summary.get("backmapping_ligand_topology_claim_safe_row_count")) >= 1
            and _int_value(image_summary.get("backmapping_ligand_topology_invalid_row_count")) == 0
        )
    )
    image_container_runtime_receipt_ready = bool(
        image_summary.get("container_runtime_receipt_ready") is True
        and image_summary.get("container_runtime_proof_schema_version") == "rocm_container_runtime_proof_v1"
        and image_summary.get("container_runtime_in_container") is True
        and image_summary.get("container_runtime_device_nodes_ready") is True
        and image_summary.get("container_runtime_torch_rocm_ready") is True
        and image_summary.get("container_runtime_torch_cuda_available") is True
        and _int_value(image_summary.get("container_runtime_visible_device_count")) > 0
        and image_summary.get("container_runtime_rust_hip_backend_enabled") is True
    )
    clean_container_smoke_ready = bool(
        image_summary.get("clean_container_smoke_ready") is True
        and image_summary.get("receipt_status") == "product_image_smoke_ready"
        and image_summary.get("receipt_mode") == "rocm-runtime"
        and image_container_runtime_receipt_ready
        and image_summary.get("product_runner_smoke_ready") is True
        and image_summary.get("product_runner_claim_metadata_ready") is True
        and image_summary.get("tier_alpha_result_manifest_signature_verified") is True
        and image_summary.get("tier_alpha_result_manifest_status") == "completed"
        and image_summary.get("backmapping_runner_claim_metadata_ready") is True
        and image_ligand_topology_receipt_ready
        and image_hbond_evidence_receipt_ready
        and image_onsps_backmap_receipt_ready
        and _int_value(image_summary.get("receipt_simulate_missing_profile_http")) == 422
    )
    bundle_input_ready = not missing_required and bool(rows)
    tar_exists = False
    tar_size = 0
    tar_member_count = 0
    tar_sha = ""
    if bundle_input_ready:
        tar_exists, tar_size, tar_member_count, tar_sha = _write_tar(out_tar, rows)
    bundle_ready = bool(bundle_input_ready and tar_exists and tar_sha)
    provisional_packet = {
        "summary": {
            "bundle_export_ready": bundle_ready,
            "bundle_tar_path": out_tar,
            "bundle_tar_sha256": tar_sha,
            "bundle_tar_member_count": tar_member_count,
        },
        "rows": rows,
    }
    validation = validate_product_evidence_bundle(bundle_packet=provisional_packet)
    product_claim_ready = bool(
        bundle_ready
        and kpi_ready
        and rocm_ready
        and clean_container_smoke_ready
        and runner_claim_metadata_signed
        and force_term_claim_metadata_ready
        and core_forcefield_bridge_ready
        and core_compatibility_layer_ready
        and validation["kpi_claim_metadata_gates_validated"] is True
    )
    if product_claim_ready:
        next_required_step = "Use this local evidence bundle as the AI-MD product runtime handoff packet."
    elif not bundle_ready:
        next_required_step = "Generate all required local AI-MD evidence artifacts before bundle export."
    elif rocm_ready and not clean_container_smoke_ready:
        next_required_step = (
            "Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh and attach the clean "
            "container smoke receipt before product claim promotion."
        )
    else:
        next_required_step = "Expose ROCm/HIP GPU visibility to PyTorch and regenerate the KPI report before product claim promotion."
    summary = {
        "packet_type": "ai_md_product_evidence_bundle",
        "status": "ai_md_product_evidence_bundle_ready" if bundle_ready else "blocked_ai_md_product_evidence_bundle",
        "bundle_export_ready": bundle_ready,
        "product_claim_ready": product_claim_ready,
        "kpi_report_ready": kpi_ready,
        "runner_claim_metadata_signed": runner_claim_metadata_signed,
        "force_term_claim_metadata_ready": force_term_claim_metadata_ready,
        "core_forcefield_bridge_ready": core_forcefield_bridge_ready,
        "core_compatibility_layer_ready": core_compatibility_layer_ready,
        "kpi_claim_metadata_gates_validated": bool(validation["kpi_claim_metadata_gates_validated"]),
        "kpi_claim_metadata_gate_count": int(validation["kpi_claim_metadata_gate_count"]),
        "kpi_claim_metadata_gate_validated_count": int(validation["kpi_claim_metadata_gate_validated_count"]),
        "rocm_hip_rust_runtime_ready": rocm_ready,
        "clean_container_smoke_ready": clean_container_smoke_ready,
        "product_image_receipt_present": bool(image_summary.get("receipt_present") is True),
        "container_runtime_receipt_ready": image_container_runtime_receipt_ready,
        "container_runtime_proof_schema_version": str(
            image_summary.get("container_runtime_proof_schema_version") or ""
        ),
        "container_runtime_in_container": bool(image_summary.get("container_runtime_in_container") is True),
        "container_runtime_device_nodes_ready": bool(
            image_summary.get("container_runtime_device_nodes_ready") is True
        ),
        "container_runtime_torch_rocm_ready": bool(
            image_summary.get("container_runtime_torch_rocm_ready") is True
        ),
        "container_runtime_torch_cuda_available": bool(
            image_summary.get("container_runtime_torch_cuda_available") is True
        ),
        "container_runtime_visible_device_count": _int_value(
            image_summary.get("container_runtime_visible_device_count")
        ),
        "container_runtime_rust_hip_backend_enabled": bool(
            image_summary.get("container_runtime_rust_hip_backend_enabled") is True
        ),
        "product_runner_smoke_ready": bool(image_summary.get("product_runner_smoke_ready") is True),
        "product_runner_claim_metadata_ready": bool(image_summary.get("product_runner_claim_metadata_ready") is True),
        "product_image_receipt_mode": str(image_summary.get("receipt_mode") or ""),
        "tier_alpha_result_manifest_signature_verified": bool(
            image_summary.get("tier_alpha_result_manifest_signature_verified") is True
        ),
        "tier_alpha_result_manifest_status": str(image_summary.get("tier_alpha_result_manifest_status") or ""),
        "backmapping_runner_claim_metadata_ready": bool(
            image_summary.get("backmapping_runner_claim_metadata_ready") is True
        ),
        "backmapping_ligand_topology_receipt_ready": image_ligand_topology_receipt_ready,
        "backmapping_ligand_topology_valid": bool(
            image_summary.get("backmapping_ligand_topology_valid") is True
        ),
        "backmapping_ligand_topology_claim_safe": bool(
            image_summary.get("backmapping_ligand_topology_claim_safe") is True
        ),
        "backmapping_ligand_topology_claim_safe_row_count": _int_value(
            image_summary.get("backmapping_ligand_topology_claim_safe_row_count")
        ),
        "backmapping_ligand_topology_invalid_row_count": _int_value(
            image_summary.get("backmapping_ligand_topology_invalid_row_count")
        ),
        "backmapping_hbond_evidence_receipt_ready": image_hbond_evidence_receipt_ready,
        "backmapping_onsps_backmap_receipt_ready": image_onsps_backmap_receipt_ready,
        "backmapping_hbond_evidence_schema_version": str(
            image_summary.get("backmapping_hbond_evidence_schema_version") or ""
        ),
        "backmapping_onsps_backmap_schema_version": str(
            image_summary.get("backmapping_onsps_backmap_schema_version") or ""
        ),
        "backmapping_hbond_evaluated_row_count": _int_value(
            image_summary.get("backmapping_hbond_evaluated_row_count")
        ),
        "backmapping_onsps_backmap_claim_safe_row_count": _int_value(
            image_summary.get("backmapping_onsps_backmap_claim_safe_row_count")
        ),
        "cpu_fallback_allowed_for_product": False,
        "required_artifact_count": sum(1 for row in rows if row["required"] is True),
        "required_artifact_missing_count": len(missing_required),
        "source_artifact_count": len(rows),
        "included_artifact_count": sum(1 for row in rows if row["included_in_bundle"] is True),
        "bundle_tar_path": out_tar,
        "bundle_tar_exists": tar_exists,
        "bundle_tar_size_bytes": tar_size,
        "bundle_tar_member_count": tar_member_count,
        "bundle_tar_sha256": tar_sha,
        "bundle_validation_pass": bool(validation["bundle_validation_pass"]),
        "bundle_validation_checked": bool(validation["bundle_validation_checked"]),
        "bundle_validation_error_count": int(validation["bundle_validation_error_count"]),
        "bundle_validation_errors": list(validation["bundle_validation_errors"]),
        "product_runtime_completion_rule": (
            "commercial_compute_default=rocm_hip; torch_rocm_ready=true; visible_device_count>0; "
            "device_nodes_ready=true; cpu_fallback_allowed_for_product=false"
        ),
        "next_required_step": next_required_step,
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    blockers = []
    if missing_required:
        blockers.append(
            {
                "code": "required_artifacts_missing",
                "count": len(missing_required),
                "artifact_ids": [row["artifact_id"] for row in missing_required],
            }
        )
    if bundle_ready and not rocm_ready:
        blockers.append({"code": "rocm_hip_rust_runtime_not_ready"})
    if bundle_ready and not kpi_ready:
        blockers.append({"code": "kpi_report_not_ready"})
    if bundle_ready and not runner_claim_metadata_signed:
        blockers.append({"code": "runner_claim_metadata_not_signed"})
    if bundle_ready and not force_term_claim_metadata_ready:
        blockers.append({"code": "force_term_claim_metadata_not_ready"})
    if bundle_ready and not core_forcefield_bridge_ready:
        blockers.append({"code": "core_forcefield_bridge_not_ready"})
    if bundle_ready and not core_compatibility_layer_ready:
        blockers.append({"code": "core_compatibility_layer_not_ready"})
    if bundle_ready and validation["kpi_claim_metadata_gates_validated"] is not True:
        blockers.append({"code": "kpi_claim_metadata_gates_not_validated"})
    if bundle_ready and not clean_container_smoke_ready:
        blockers.append({"code": "clean_container_smoke_not_ready"})
    if bundle_ready and validation["bundle_validation_pass"] is not True:
        blockers.append({"code": "bundle_validation_failed", "errors": list(validation["bundle_validation_errors"])})
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# AI-MD Product Evidence Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- bundle_export_ready: `{s['bundle_export_ready']}`",
        f"- product_claim_ready: `{s['product_claim_ready']}`",
        f"- kpi_report_ready: `{s['kpi_report_ready']}`",
        f"- rocm_hip_rust_runtime_ready: `{s['rocm_hip_rust_runtime_ready']}`",
        f"- clean_container_smoke_ready: `{s['clean_container_smoke_ready']}`",
        f"- bundle_tar_path: `{s['bundle_tar_path']}`",
        f"- bundle_tar_sha256: `{s['bundle_tar_sha256']}`",
        f"- required_artifact_missing_count: `{s['required_artifact_missing_count']}`",
        "",
        "## Artifacts",
        "",
        "| artifact | required | exists | role | sha256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['required']}` | `{row['exists']}` | "
            f"`{row['role']}` | `{row['sha256']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local AI-MD product evidence bundle export.")
    parser.add_argument("--kpi-json", default=DEFAULT_KPI_JSON)
    parser.add_argument("--kpi-md", default=DEFAULT_KPI_MD)
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--product-image-preflight-json", default=DEFAULT_PRODUCT_IMAGE_PREFLIGHT_JSON)
    parser.add_argument("--product-image-receipt-json", default=DEFAULT_PRODUCT_IMAGE_RECEIPT_JSON)
    parser.add_argument("--next-steps-doc", default=DEFAULT_NEXT_STEPS_DOC)
    parser.add_argument("--out-tar", default=DEFAULT_OUT_TAR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_specs = _default_artifacts(
        kpi_json=args.kpi_json,
        kpi_md=args.kpi_md,
        rocm_manifest_json=args.rocm_manifest_json,
        product_image_preflight_json=args.product_image_preflight_json,
        product_image_receipt_json=args.product_image_receipt_json,
        next_steps_doc=args.next_steps_doc,
    )
    payload = build_payload(
        kpi_packet=_read_json_if_present(args.kpi_json),
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        product_image_preflight_packet=_read_json_if_present(args.product_image_preflight_json),
        artifact_specs=artifact_specs,
        out_tar=args.out_tar,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps({"status": payload["summary"]["status"], "out_tar": args.out_tar}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
