#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_OUT_MD = "runs/product_image_smoke_preflight_current.md"
DEFAULT_RECEIPT_JSON = "runs/product_image_smoke_receipt_current.json"

CLAIM_BOUNDARY = (
    "Product image smoke preflight only; checks local Docker availability and verifies that the product image "
    "smoke script/workflow fail closed and expose Docker-host preparation plus ROCm-runtime runner validation "
    "commands. It does not build images, run containers, run docking, mutate Docker state, upload, deploy, "
    "submit, email, or delete files."
)


def _resolve(root: Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_text(root: Path, path_like: str | Path) -> str:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(root: Path, path_like: str | Path) -> dict[str, Any]:
    path = _resolve(root, path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _requirement_lines(text: str) -> set[str]:
    return {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _docker_daemon_reachable(docker_cli: str) -> bool:
    if not docker_cli:
        return False
    try:
        result = subprocess.run(
            [docker_cli, "info"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Product Image Smoke Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- docker_cli_present: `{s['docker_cli_present']}`",
        f"- docker_daemon_reachable: `{s['docker_daemon_reachable']}`",
        f"- script_contract_ready: `{s['script_contract_ready']}`",
        f"- workflow_contract_ready: `{s['workflow_contract_ready']}`",
        f"- clean_container_smoke_ready: `{s['clean_container_smoke_ready']}`",
        f"- receipt_present: `{s['receipt_present']}`",
        f"- receipt_mode: `{s['receipt_mode']}`",
        f"- container_runtime_receipt_ready: `{s['container_runtime_receipt_ready']}`",
        f"- container_runtime_visible_device_count: `{s['container_runtime_visible_device_count']}`",
        f"- container_runtime_rust_hip_backend_enabled: `{s['container_runtime_rust_hip_backend_enabled']}`",
        f"- docker_host_setup_command: `{s['docker_host_setup_command']}`",
        f"- docker_cmd_override_example: `{s['docker_cmd_override_example']}`",
        f"- product_runner_smoke_ready: `{s['product_runner_smoke_ready']}`",
        f"- rocm_runtime_runner_smoke_command: `{s['rocm_runtime_runner_smoke_command']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{row['code']}`" for row in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _contract_row(check_id: str, passed: bool, observed: str, required: str, source: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "source": source,
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_product_image_smoke_preflight(
    *,
    root: str | Path = ROOT,
    docker_cli_path: str | None = None,
    docker_daemon_ready: bool | None = None,
    receipt_json: str | Path = DEFAULT_RECEIPT_JSON,
) -> dict[str, Any]:
    root_path = Path(root)
    docker_cli = docker_cli_path if docker_cli_path is not None else shutil.which("docker")
    docker_cli_present = bool(docker_cli)
    if docker_daemon_ready is None:
        docker_daemon_ready = (
            docker_cli_present
            if docker_cli_path is not None
            else _docker_daemon_reachable(str(docker_cli or ""))
        )
    verify_script = _read_text(root_path, "deploy/verify_product_image.sh")
    host_setup_script = _read_text(root_path, "scripts/prepare_product_docker_host.sh")
    workflow = _read_text(root_path, ".github/workflows/product-image-smoke.yml")
    dockerfile = _read_text(root_path, "Dockerfile.product")
    base_requirements = _read_text(root_path, "requirements-base.txt")
    default_requirements = _read_text(root_path, "requirements.txt")
    rocm_requirements = _read_text(root_path, "requirements-rocm.txt")
    product_rocm_requirements = _read_text(root_path, "requirements-product-rocm.txt")
    receipt = _read_json(root_path, receipt_json)
    base_requirement_lines = _requirement_lines(base_requirements)
    default_requirement_lines = _requirement_lines(default_requirements)
    rocm_requirement_lines = _requirement_lines(rocm_requirements)
    product_rocm_requirement_lines = _requirement_lines(product_rocm_requirements)
    product_rocm_preserves_base_torch = bool(
        "-r requirements-base.txt" in product_rocm_requirement_lines
        and "-r requirements-rocm.txt" not in product_rocm_requirement_lines
        and "-r requirements.txt" not in product_rocm_requirement_lines
        and "torch==2.6.0" not in product_rocm_requirement_lines
        and "-r requirements-base.txt" in rocm_requirement_lines
        and "-r requirements.txt" not in rocm_requirement_lines
        and "torch==2.6.0+rocm6.1" in rocm_requirement_lines
        and "torch==2.6.0" not in rocm_requirement_lines
        and "-r requirements-base.txt" in default_requirement_lines
        and "torch==2.6.0" in default_requirement_lines
        and base_requirement_lines
        and "torch==2.6.0" not in base_requirement_lines
        and "requirements-base.txt" in dockerfile
    )

    rows = [
        _contract_row(
            "docker_missing_fail_closed",
            "docker_cli_missing" in verify_script
            and "docker_daemon_unreachable" in verify_script
            and "exit 2" in verify_script
            and "not mark missing Docker as green" in verify_script,
            "docker_cli_missing guarded" if "docker_cli_missing" in verify_script else "missing",
            "missing Docker or inaccessible daemon exits nonzero and is not treated as green",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "docker_cmd_override_declared",
            "DOCKER_CMD" in verify_script
            and "DOCKER_BIN" in verify_script
            and "docker_cmd" in verify_script,
            "DOCKER_CMD override present" if "DOCKER_CMD" in verify_script else "missing",
            "operator can run the smoke with a Docker-compatible command such as sudo docker",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "docker_host_setup_script_declared",
            "docker.io" in host_setup_script
            and "systemctl enable --now docker" in host_setup_script
            and "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime" in host_setup_script
            and "/dev/kfd" in host_setup_script
            and "/dev/dri" in host_setup_script,
            "Docker host setup helper present" if "docker.io" in host_setup_script else "missing",
            "host helper installs/starts Docker, checks ROCm device nodes, and prints rocm-runtime smoke command",
            "scripts/prepare_product_docker_host.sh",
        ),
        _contract_row(
            "verify_modes_declared",
            "build|rocm-runtime" in verify_script and "PRODUCT_IMAGE_VERIFY_MODE" in verify_script,
            "build|rocm-runtime" if "build|rocm-runtime" in verify_script else "missing",
            "build and rocm-runtime modes",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "rocm_device_nodes_required",
            "/dev/kfd" in verify_script and "/dev/dri" in verify_script and "--device=/dev/kfd" in verify_script,
            "device args present" if "--device=/dev/kfd" in verify_script else "missing",
            "rocm-runtime mode passes /dev/kfd and /dev/dri",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "rocm_torch_visibility_required",
            "torch.cuda.is_available()" in verify_script and "torch.cuda.device_count() > 0" in verify_script,
            "torch visibility assert present" if "torch.cuda.device_count() > 0" in verify_script else "missing",
            "container asserts torch ROCm visible device count > 0",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "container_runtime_proof_required",
            "rocm_container_runtime_proof.json" in verify_script
            and "rocm_container_runtime_proof_v1" in verify_script
            and "probe_rust_hip_backend" in verify_script
            and "rust_hip_backend_enabled" in verify_script,
            "container runtime proof writer present"
            if "rocm_container_runtime_proof.json" in verify_script
            else "missing",
            "rocm-runtime mode writes in-container ROCm/HIP/Rust proof JSON",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "real_validated_runner_smoke_required",
            "run_tier_alpha_adrb2_dispatch_smoke.py" in verify_script
            and "API_VALIDATED_RUNNER_ENABLED=1" in verify_script
            and "tier_alpha_adrb2_dispatch_smoke.json" in verify_script,
            "tier alpha runner smoke present" if "run_tier_alpha_adrb2_dispatch_smoke.py" in verify_script else "missing",
            "rocm-runtime mode runs real validated runner dispatch smoke",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "backmapping_claim_metadata_smoke_required",
            "tools/run_ligand_backmapping_scoring.py" in verify_script
            and "backmapping_summary.json" in verify_script
            and "hbond_evidence_v1" in verify_script
            and "ligand_topology_validity_v1" in verify_script
            and "product_runner_claim_metadata_ready" in verify_script,
            "backmapping claim metadata smoke present"
            if "product_runner_claim_metadata_ready" in verify_script
            else "missing",
            "rocm-runtime mode runs backmapping scoring smoke and records H-bond/ONSPS/ligand topology schema claim metadata",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "rocm_runtime_receipt_written",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON" in verify_script
            and "product_runner_smoke_ready" in verify_script
            and "clean_container_smoke_ready" in verify_script,
            "receipt writer present" if "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON" in verify_script else "missing",
            "successful smoke writes a receipt that distinguishes build from rocm-runtime",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "build_mode_receipt_not_product_claim_ready",
            "product_image_build_smoke_ready" in verify_script
            and "blocked_product_image_rocm_runtime_smoke" in verify_script
            and "receipt_ready" in verify_script,
            "mode-specific receipt status present"
            if "product_image_build_smoke_ready" in verify_script
            else "missing",
            "build-only receipt must not use product_image_smoke_ready claim status",
            "deploy/verify_product_image.sh",
        ),
        _contract_row(
            "workflow_build_mode_declared",
            "PRODUCT_IMAGE_VERIFY_MODE: build" in workflow,
            "build mode in workflow" if "PRODUCT_IMAGE_VERIFY_MODE: build" in workflow else "missing",
            "hosted CI uses build contract mode explicitly",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_pull_request_trigger_declared",
            "pull_request:" in workflow and "deploy/verify_product_image.sh" in workflow,
            "pull_request path trigger present" if "pull_request:" in workflow else "missing",
            "product image smoke runs on PRs for relevant product runtime path changes",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_manual_verify_mode_choice_declared",
            "workflow_dispatch:" in workflow
            and "verify_mode:" in workflow
            and "- build" in workflow
            and "- rocm-runtime" in workflow,
            "workflow_dispatch verify_mode choice present" if "verify_mode:" in workflow else "missing",
            "manual workflow dispatch exposes build vs rocm-runtime mode explicitly",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_rocm_runtime_self_hosted_runner_declared",
            "product-image-rocm-runtime-smoke" in workflow
            and "runs-on: [self-hosted, linux, rocm]" in workflow
            and "PRODUCT_IMAGE_VERIFY_MODE: rocm-runtime" in workflow,
            "self-hosted rocm runtime job present"
            if "product-image-rocm-runtime-smoke" in workflow
            else "missing",
            "rocm-runtime workflow path must run only on a self-hosted ROCm runner",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "workflow_hosted_build_summary_not_product_claim",
            "product runtime claim: `false`" in workflow
            and "required runtime claim mode: `rocm-runtime on self-hosted ROCm runner`" in workflow,
            "hosted build summary claim boundary present"
            if "product runtime claim: `false`" in workflow
            else "missing",
            "hosted CI summary must state build smoke is not product runtime readiness",
            ".github/workflows/product-image-smoke.yml",
        ),
        _contract_row(
            "dockerfile_rocm_hip_rust_contract",
            "rocm/pytorch" in dockerfile
            and "torch.version.hip" in dockerfile
            and "tools/build_rust_hip_engine.py --output /app" in dockerfile
            and "requirements-base.txt" in dockerfile,
            "ROCm/HIP/Rust product Dockerfile" if "rocm/pytorch" in dockerfile else "missing",
            "Dockerfile.product builds ROCm PyTorch and Rust HIP extension and copies split requirement files",
            "Dockerfile.product",
        ),
        _contract_row(
            "product_rocm_requirements_no_cpu_torch_pin",
            product_rocm_preserves_base_torch,
            (
                "product_rocm_includes_base="
                f"{'-r requirements-base.txt' in product_rocm_requirement_lines};"
                "product_rocm_includes_rocm="
                f"{'-r requirements-rocm.txt' in product_rocm_requirement_lines};"
                "product_rocm_includes_default="
                f"{'-r requirements.txt' in product_rocm_requirement_lines};"
                "product_rocm_cpu_torch_pin="
                f"{'torch==2.6.0' in product_rocm_requirement_lines};"
                "rocm_includes_base="
                f"{'-r requirements-base.txt' in rocm_requirement_lines};"
                "rocm_includes_default="
                f"{'-r requirements.txt' in rocm_requirement_lines};"
                "rocm_cpu_torch_pin="
                f"{'torch==2.6.0' in rocm_requirement_lines};"
                "rocm_torch_pin="
                f"{'torch==2.6.0+rocm6.1' in rocm_requirement_lines}"
            ),
            "product ROCm requirements must install base dependencies only and preserve Dockerfile.product's ROCm PyTorch base build",
            "requirements-product-rocm.txt",
        ),
    ]
    script_contract_ready = all(row["passed"] for row in rows if row["source"] != ".github/workflows/product-image-smoke.yml")
    workflow_contract_ready = all(row["passed"] for row in rows if row["source"] == ".github/workflows/product-image-smoke.yml")
    receipt_present = bool(receipt)
    receipt_status = str(receipt.get("status") or "")
    receipt_mode = str(receipt.get("mode") or "")
    receipt_simulate_missing_profile_http = _int_value(receipt.get("simulate_missing_profile_http"))
    container_runtime_proof_ready = bool(receipt.get("container_runtime_proof_ready") is True)
    container_runtime_proof_schema_version = str(
        receipt.get("container_runtime_proof_schema_version") or ""
    )
    container_runtime_in_container = bool(receipt.get("container_runtime_in_container") is True)
    container_runtime_device_nodes_ready = bool(receipt.get("container_runtime_device_nodes_ready") is True)
    container_runtime_torch_rocm_ready = bool(receipt.get("container_runtime_torch_rocm_ready") is True)
    container_runtime_torch_cuda_available = bool(
        receipt.get("container_runtime_torch_cuda_available") is True
    )
    container_runtime_visible_device_count = _int_value(
        receipt.get("container_runtime_visible_device_count")
    )
    container_runtime_rust_hip_backend_enabled = bool(
        receipt.get("container_runtime_rust_hip_backend_enabled") is True
    )
    container_runtime_receipt_ready = bool(
        container_runtime_proof_ready
        and container_runtime_proof_schema_version == "rocm_container_runtime_proof_v1"
        and container_runtime_in_container
        and container_runtime_device_nodes_ready
        and container_runtime_torch_rocm_ready
        and container_runtime_torch_cuda_available
        and container_runtime_visible_device_count > 0
        and container_runtime_rust_hip_backend_enabled
    )
    product_runner_smoke_ready = bool(receipt.get("product_runner_smoke_ready") is True)
    product_runner_claim_metadata_ready = bool(receipt.get("product_runner_claim_metadata_ready") is True)
    tier_alpha_manifest_signature_verified = bool(receipt.get("tier_alpha_result_manifest_signature_verified") is True)
    tier_alpha_manifest_status = str(receipt.get("tier_alpha_result_manifest_status") or "")
    backmapping_runner_claim_metadata_ready = bool(receipt.get("backmapping_runner_claim_metadata_ready") is True)
    backmapping_hbond_evidence_schema_version = str(
        receipt.get("backmapping_hbond_evidence_schema_version") or ""
    )
    backmapping_hbond_claim_metadata_schema_version = str(
        receipt.get("backmapping_hbond_claim_metadata_schema_version") or ""
    )
    backmapping_hbond_claim_metadata_schema_ready_row_count = _int_value(
        receipt.get("backmapping_hbond_claim_metadata_schema_ready_row_count")
    )
    backmapping_onsps_backmap_schema_version = str(
        receipt.get("backmapping_onsps_backmap_schema_version") or ""
    )
    backmapping_hbond_evaluated_row_count = _int_value(receipt.get("backmapping_hbond_evaluated_row_count"))
    backmapping_onsps_backmap_claim_safe_row_count = _int_value(
        receipt.get("backmapping_onsps_backmap_claim_safe_row_count")
    )
    backmapping_ligand_topology_valid = bool(receipt.get("backmapping_ligand_topology_valid") is True)
    backmapping_ligand_topology_claim_safe = bool(
        receipt.get("backmapping_ligand_topology_claim_safe") is True
    )
    backmapping_ligand_topology_schema_version = str(
        receipt.get("backmapping_ligand_topology_schema_version") or ""
    )
    backmapping_ligand_topology_schema_ready_row_count = _int_value(
        receipt.get("backmapping_ligand_topology_schema_ready_row_count")
    )
    backmapping_ligand_topology_claim_safe_row_count = _int_value(
        receipt.get("backmapping_ligand_topology_claim_safe_row_count")
    )
    backmapping_ligand_topology_invalid_row_count = _int_value(
        receipt.get("backmapping_ligand_topology_invalid_row_count")
    )
    backmapping_ligand_topology_receipt_ready = bool(
        backmapping_ligand_topology_schema_version == "ligand_topology_validity_v1"
        and backmapping_ligand_topology_schema_ready_row_count >= 1
        and (
            receipt.get("backmapping_ligand_topology_receipt_ready") is True
            or (
                backmapping_ligand_topology_valid
                and backmapping_ligand_topology_claim_safe
                and backmapping_ligand_topology_claim_safe_row_count >= 1
                and backmapping_ligand_topology_invalid_row_count == 0
            )
        )
    )
    backmapping_hbond_evidence_receipt_ready = bool(
        backmapping_hbond_evidence_schema_version == "hbond_evidence_v1"
        and backmapping_hbond_claim_metadata_schema_version == "hbond_evidence_v1"
        and backmapping_hbond_claim_metadata_schema_ready_row_count >= 1
        and backmapping_hbond_evaluated_row_count >= 1
    )
    backmapping_onsps_backmap_receipt_ready = bool(
        backmapping_onsps_backmap_schema_version == "onsps_backmap_evidence_v1"
        and backmapping_onsps_backmap_claim_safe_row_count >= 1
    )
    receipt_clean_container_smoke_ready = bool(receipt.get("clean_container_smoke_ready") is True)
    clean_container_smoke_ready = bool(
        receipt_status == "product_image_smoke_ready"
        and receipt_mode == "rocm-runtime"
        and receipt_simulate_missing_profile_http == 422
        and product_runner_smoke_ready
        and product_runner_claim_metadata_ready
        and tier_alpha_manifest_signature_verified
        and tier_alpha_manifest_status == "completed"
        and backmapping_runner_claim_metadata_ready
        and backmapping_ligand_topology_receipt_ready
        and backmapping_hbond_evidence_receipt_ready
        and backmapping_onsps_backmap_receipt_ready
        and receipt_clean_container_smoke_ready
        and container_runtime_receipt_ready
        and receipt.get("rocm_runtime_visible_device_required") is True
    )
    docker_access_ready = bool(docker_cli_present and docker_daemon_ready)
    preflight_ready = bool(
        script_contract_ready
        and workflow_contract_ready
        and (docker_access_ready or clean_container_smoke_ready)
    )
    blockers = []
    if not clean_container_smoke_ready and not docker_cli_present:
        blockers.append({"code": "docker_cli_missing"})
    elif not clean_container_smoke_ready and not docker_daemon_ready:
        blockers.append({"code": "docker_daemon_unreachable"})
    for row in rows:
        if not row["passed"]:
            blockers.append({"code": row["check_id"]})
    summary = {
        "packet_type": "product_image_smoke_preflight",
        "status": "product_image_smoke_preflight_ready" if preflight_ready else "blocked_product_image_smoke_preflight",
        "preflight_ready": preflight_ready,
        "docker_cli_present": docker_cli_present,
        "docker_cli_path": docker_cli or "",
        "docker_daemon_reachable": bool(docker_daemon_ready),
        "script_contract_ready": script_contract_ready,
        "workflow_contract_ready": workflow_contract_ready,
        "clean_container_smoke_ready": clean_container_smoke_ready,
        "receipt_json": str(receipt_json),
        "receipt_present": receipt_present,
        "receipt_status": receipt_status,
        "receipt_mode": receipt_mode,
        "receipt_simulate_missing_profile_http": receipt_simulate_missing_profile_http,
        "receipt_clean_container_smoke_ready": receipt_clean_container_smoke_ready,
        "container_runtime_proof_present": bool(receipt.get("container_runtime_proof_present") is True),
        "container_runtime_proof_schema_version": container_runtime_proof_schema_version,
        "container_runtime_proof_ready": container_runtime_proof_ready,
        "container_runtime_receipt_ready": container_runtime_receipt_ready,
        "container_runtime_in_container": container_runtime_in_container,
        "container_runtime_device_nodes_ready": container_runtime_device_nodes_ready,
        "container_runtime_torch_rocm_ready": container_runtime_torch_rocm_ready,
        "container_runtime_torch_cuda_available": container_runtime_torch_cuda_available,
        "container_runtime_visible_device_count": container_runtime_visible_device_count,
        "container_runtime_visible_device_name": str(
            receipt.get("container_runtime_visible_device_name") or ""
        ),
        "container_runtime_rust_hip_backend_enabled": container_runtime_rust_hip_backend_enabled,
        "container_runtime_rust_hip_kernel_name": str(
            receipt.get("container_runtime_rust_hip_kernel_name") or ""
        ),
        "product_runner_smoke_ready": product_runner_smoke_ready,
        "product_runner_claim_metadata_ready": product_runner_claim_metadata_ready,
        "tier_alpha_result_manifest_signature_verified": tier_alpha_manifest_signature_verified,
        "tier_alpha_result_manifest_status": tier_alpha_manifest_status,
        "backmapping_runner_claim_metadata_ready": backmapping_runner_claim_metadata_ready,
        "backmapping_hbond_evidence_schema_version": backmapping_hbond_evidence_schema_version,
        "backmapping_hbond_claim_metadata_schema_version": backmapping_hbond_claim_metadata_schema_version,
        "backmapping_hbond_claim_metadata_schema_ready_row_count": (
            backmapping_hbond_claim_metadata_schema_ready_row_count
        ),
        "backmapping_onsps_backmap_schema_version": backmapping_onsps_backmap_schema_version,
        "backmapping_hbond_evaluated_row_count": backmapping_hbond_evaluated_row_count,
        "backmapping_onsps_backmap_claim_safe_row_count": backmapping_onsps_backmap_claim_safe_row_count,
        "backmapping_ligand_topology_valid": backmapping_ligand_topology_valid,
        "backmapping_ligand_topology_claim_safe": backmapping_ligand_topology_claim_safe,
        "backmapping_ligand_topology_schema_version": backmapping_ligand_topology_schema_version,
        "backmapping_ligand_topology_schema_ready_row_count": backmapping_ligand_topology_schema_ready_row_count,
        "backmapping_ligand_topology_claim_safe_row_count": backmapping_ligand_topology_claim_safe_row_count,
        "backmapping_ligand_topology_invalid_row_count": backmapping_ligand_topology_invalid_row_count,
        "backmapping_ligand_topology_receipt_ready": backmapping_ligand_topology_receipt_ready,
        "backmapping_hbond_evidence_receipt_ready": backmapping_hbond_evidence_receipt_ready,
        "backmapping_onsps_backmap_receipt_ready": backmapping_onsps_backmap_receipt_ready,
        "build_contract_command": "PRODUCT_IMAGE_VERIFY_MODE=build bash deploy/verify_product_image.sh",
        "docker_host_setup_command": "bash scripts/prepare_product_docker_host.sh",
        "docker_cmd_override_example": (
            "DOCKER_CMD='sudo docker' PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh"
        ),
        "rocm_runtime_runner_smoke_command": "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh",
        "required_runtime_mode_for_product_claim": "rocm-runtime",
        "execution_enabled": False,
        "container_build_executed": False,
        "container_runner_smoke_executed": False,
        "container_runner_smoke_receipt_attached": receipt_present,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach clean container smoke receipt to the product evidence bundle."
            if clean_container_smoke_ready
            else (
                "Run bash scripts/prepare_product_docker_host.sh on this ROCm host, then run "
                "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh."
                if not docker_cli_present
                else (
                    "Start Docker or refresh this shell's docker group access, then rerun "
                    "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh."
                    if not docker_daemon_ready
                    else "Run PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh on a Docker-enabled ROCm host."
                )
            )
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product image smoke preflight evidence.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--receipt-json", default=DEFAULT_RECEIPT_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_product_image_smoke_preflight(receipt_json=args.receipt_json)
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps({"status": payload["summary"]["status"], "out_json": args.out_json}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
