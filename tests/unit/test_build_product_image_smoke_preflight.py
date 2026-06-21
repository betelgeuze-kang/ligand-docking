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


def test_product_image_smoke_preflight_contract_ready_with_docker_path(tmp_path: Path) -> None:
    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    summary = payload["summary"]
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert summary["status"] == "product_image_smoke_preflight_ready"
    assert summary["preflight_ready"] is True
    assert summary["docker_cli_present"] is True
    assert summary["docker_daemon_reachable"] is True
    assert summary["script_contract_ready"] is True
    assert summary["workflow_contract_ready"] is True
    assert summary["clean_container_smoke_ready"] is False
    assert summary["receipt_present"] is False
    assert summary["container_runtime_receipt_ready"] is False
    assert summary["product_runner_smoke_ready"] is False
    assert summary["product_runner_claim_metadata_ready"] is False
    assert "rocm-runtime" in summary["rocm_runtime_runner_smoke_command"]
    assert payload["blockers"] == []
    assert rows_by_id["product_rocm_requirements_no_cpu_torch_pin"]["passed"] is True
    assert rows_by_id["build_mode_receipt_not_product_claim_ready"]["passed"] is True
    assert rows_by_id["docker_cmd_override_declared"]["passed"] is True
    assert rows_by_id["docker_host_setup_script_declared"]["passed"] is True
    assert rows_by_id["workflow_pull_request_trigger_declared"]["passed"] is True
    assert rows_by_id["workflow_manual_verify_mode_choice_declared"]["passed"] is True
    assert rows_by_id["workflow_build_smoke_self_hosted_by_default"]["passed"] is True
    assert rows_by_id["workflow_rocm_runtime_self_hosted_runner_declared"]["passed"] is True
    assert rows_by_id["workflow_hosted_build_summary_not_product_claim"]["passed"] is True
    assert all(row["execution_enabled"] is False for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_product_image_smoke_preflight_blocks_without_docker_cli(tmp_path: Path) -> None:
    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="",
        receipt_json=tmp_path / "missing_receipt.json",
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["docker_cli_present"] is False
    assert summary["docker_daemon_reachable"] is False
    assert {"code": "docker_cli_missing"} in payload["blockers"]
    assert summary["clean_container_smoke_ready"] is False
    assert summary["next_required_step"].startswith("Run bash scripts/prepare_product_docker_host.sh")
    assert summary["docker_host_setup_command"] == "bash scripts/prepare_product_docker_host.sh"
    assert "DOCKER_CMD='sudo docker'" in summary["docker_cmd_override_example"]


def test_product_image_smoke_preflight_blocks_when_docker_daemon_unreachable_without_receipt(
    tmp_path: Path,
) -> None:
    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=False,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["docker_cli_present"] is True
    assert summary["docker_daemon_reachable"] is False
    assert {"code": "docker_daemon_unreachable"} in payload["blockers"]
    assert "refresh this shell's docker group access" in summary["next_required_step"]


def test_product_image_smoke_preflight_blocks_rocm_requirements_that_include_cpu_torch_graph(
    tmp_path: Path,
) -> None:
    (tmp_path / "deploy").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "deploy" / "verify_product_image.sh").write_text(
        "\n".join(
            [
                "build|rocm-runtime",
                "PRODUCT_IMAGE_VERIFY_MODE",
                "docker_cli_missing",
                "docker_daemon_unreachable",
                "DOCKER_CMD",
                "DOCKER_BIN",
                "docker_cmd",
                "DOCKER_BUILDKIT",
                "PRODUCT_IMAGE_PRUNE_BEFORE_BUILD",
                "container prune -f",
                "image prune -f",
                "build --progress=plain",
                "exit 2",
                "not mark missing Docker as green",
                "/dev/kfd",
                "/dev/dri",
                "--device=/dev/kfd",
                "torch.cuda.is_available()",
                "torch.cuda.device_count() > 0",
                "rocm_container_runtime_proof.json",
                "rocm_container_runtime_proof_v1",
                "probe_rust_hip_backend",
                "rust_hip_backend_enabled",
                "run_tier_alpha_adrb2_dispatch_smoke.py",
                "API_VALIDATED_RUNNER_ENABLED=1",
                "tier_alpha_adrb2_dispatch_smoke.json",
                "tools/run_ligand_backmapping_scoring.py",
                "backmapping_summary.json",
                "hbond_evidence_v1",
                "ligand_topology_validity_v1",
                "product_runner_claim_metadata_ready",
                "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON",
                "product_runner_smoke_ready",
                "clean_container_smoke_ready",
                "receipt_ready",
                "product_image_build_smoke_ready",
                "blocked_product_image_rocm_runtime_smoke",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "prepare_product_docker_host.sh").write_text(
        "\n".join(
            [
                "sudo apt-get install -y docker.io",
                "sudo systemctl enable --now docker",
                "/dev/kfd",
                "/dev/dri",
                "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".github" / "workflows" / "product-image-smoke.yml").write_text(
        "\n".join(
            [
                "pull_request:",
                "workflow_dispatch:",
                "verify_mode:",
                "build_runner_labels_json:",
                "- build",
                "- rocm-runtime",
                "product-image-build-smoke:",
                "fromJSON(inputs.build_runner_labels_json || '[\"self-hosted\",\"linux\"]')",
                "use [\"ubuntu-latest\"] only by explicit choice",
                "PRODUCT_IMAGE_VERIFY_MODE: build",
                'DOCKER_BUILDKIT: "1"',
                'PRODUCT_IMAGE_PRUNE_BEFORE_BUILD: "1"',
                "product runtime claim: `false`",
                "required runtime claim mode: `rocm-runtime on self-hosted ROCm runner`",
                "product-image-rocm-runtime-smoke:",
                "runs-on: [self-hosted, linux, rocm]",
                "PRODUCT_IMAGE_VERIFY_MODE: rocm-runtime",
                "deploy/verify_product_image.sh",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Dockerfile.product").write_text(
        "\n".join(
            [
                "FROM rocm/pytorch:test",
                "COPY requirements-base.txt requirements.txt requirements-rocm.txt requirements-product-rocm.txt ./",
                "RUN python tools/build_rust_hip_engine.py --output /app",
                "RUN python - <<'PY'",
                "import torch",
                "assert torch.version.hip",
                "PY",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "requirements-base.txt").write_text("numpy==1.26.4\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("-r requirements-base.txt\ntorch==2.6.0\n", encoding="utf-8")
    (tmp_path / "requirements-rocm.txt").write_text(
        "-r requirements.txt\n--extra-index-url https://download.pytorch.org/whl/rocm6.1\ntorch==2.6.0+rocm6.1\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements-product-rocm.txt").write_text("-r requirements-base.txt\n", encoding="utf-8")

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
    )
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert payload["summary"]["preflight_ready"] is False
    assert payload["summary"]["script_contract_ready"] is False
    assert rows_by_id["product_rocm_requirements_no_cpu_torch_pin"]["passed"] is False
    assert {"code": "product_rocm_requirements_no_cpu_torch_pin"} in payload["blockers"]


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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
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

    payload_without_live_docker = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=False,
        receipt_json=receipt_json,
    )
    summary_without_live_docker = payload_without_live_docker["summary"]

    assert summary_without_live_docker["status"] == "product_image_smoke_preflight_ready"
    assert summary_without_live_docker["preflight_ready"] is True
    assert summary_without_live_docker["docker_daemon_reachable"] is False
    assert summary_without_live_docker["clean_container_smoke_ready"] is True
    assert {"code": "docker_daemon_unreachable"} not in payload_without_live_docker["blockers"]
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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )

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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
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
                "status": "product_image_build_smoke_ready",
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

    payload = mod.build_product_image_smoke_preflight(
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )

    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert payload["summary"]["receipt_present"] is True
    assert payload["summary"]["receipt_mode"] == "build"


def test_product_image_smoke_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "preflight.json"
    out_md = tmp_path / "preflight.md"
    missing_receipt = tmp_path / "missing_receipt.json"

    rc = mod.main([
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
        "--receipt-json",
        str(missing_receipt),
    ])

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "product_image_smoke_preflight"
    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert "Product Image Smoke Preflight" in out_md.read_text(encoding="utf-8")
