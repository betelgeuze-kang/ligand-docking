from __future__ import annotations

import json
import os
import subprocess
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


def _runner_hygiene_fields() -> dict[str, object]:
    return {
        "runner_hygiene_schema_version": "product_image_runner_hygiene_v1",
        "runner_smoke_dir": "/tmp/product_image_smoke_runner_artifacts",
        "workspace_runner_smoke_dir": "runs/product_image_smoke_runner_artifacts",
        "runner_smoke_dir_outside_workspace": True,
        "host_uid_gid": "1000:1000",
        "container_uid_gid": "1000:1000",
        "container_output_uid_gid_pinned": True,
        "container_output_uid_gid_matches_host": True,
        "container_output_uid_gid_non_root": True,
        "workspace_runner_smoke_dir_cleanup_ready": True,
        "workspace_runner_smoke_dir_exists_after_cleanup": False,
    }


def _copy_product_image_preflight_fixture(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for rel_path in (
        "deploy/verify_product_image.sh",
        "scripts/normalize_product_image_smoke_artifact_ownership.sh",
        "scripts/prepare_product_docker_host.sh",
        ".github/workflows/product-image-smoke.yml",
        ".github/workflows/product-image-smoke-trusted.yml",
        ".github/workflows/product-api-worker.yml",
        ".github/workflows/product-api-worker-trusted.yml",
        "Dockerfile.product",
        "requirements-base.txt",
        "requirements.txt",
        "requirements-rocm.txt",
        "requirements-product-rocm.txt",
    ):
        destination = root / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((repo_root / rel_path).read_text(encoding="utf-8"), encoding="utf-8")


def test_product_image_smoke_preflight_contract_ready_with_docker_path(tmp_path: Path) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    assert summary["runner_smoke_dir_contract_ready"] is True
    assert summary["workflow_workspace_artifact_recovery_ready"] is True
    assert summary["pre_checkout_cleanup_ready"] is True
    assert summary["receipt_runner_hygiene_ready"] is True
    assert summary["receipt_runner_hygiene_refresh_required"] is False
    assert summary["receipt_runner_hygiene_blocker_count"] == 0
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
    assert rows_by_id["smoke_containers_disable_auth_preflight"]["passed"] is True
    assert rows_by_id["fail_closed_receipt_written_on_early_exit"]["passed"] is True
    assert (
        rows_by_id[
            "exit_trap_runner_artifact_ownership_normalization_declared"
        ]["passed"]
        is True
    )
    assert rows_by_id["runner_smoke_dir_ownership_guard_declared"]["passed"] is True
    assert rows_by_id["runner_smoke_dir_workspace_fail_closed_declared"]["passed"] is True
    assert rows_by_id["post_smoke_ownership_script_declared"]["passed"] is True
    assert rows_by_id["docker_host_setup_script_declared"]["passed"] is True
    assert rows_by_id["workflow_pull_request_trigger_declared"]["passed"] is True
    assert rows_by_id["workflow_manual_verify_mode_choice_declared"]["passed"] is True
    assert rows_by_id["workflow_build_smoke_self_hosted_by_default"]["passed"] is True
    assert rows_by_id["workflow_pre_checkout_workspace_artifact_recovery_declared"]["passed"] is True
    assert rows_by_id["api_worker_pre_checkout_workspace_artifact_recovery_declared"]["passed"] is True
    assert (
        rows_by_id["workflow_checkout_subdir_isolated_from_stale_workspace_runs"][
            "passed"
        ]
        is True
    )
    assert (
        rows_by_id["api_worker_checkout_subdir_isolated_from_stale_workspace_runs"][
            "passed"
        ]
        is True
    )
    assert rows_by_id["workflow_runner_temp_artifact_root_declared"]["passed"] is True
    assert rows_by_id["workflow_container_uid_gid_export_declared"]["passed"] is True
    assert rows_by_id["workflow_post_smoke_ownership_normalization_declared"]["passed"] is True
    assert rows_by_id["workflow_rocm_runtime_self_hosted_runner_declared"]["passed"] is True
    assert rows_by_id["workflow_hosted_build_summary_not_product_claim"]["passed"] is True
    assert rows_by_id["workflow_artifact_retention_declared"]["passed"] is True
    product_pr_workflow = Path(".github/workflows/product-image-smoke.yml").read_text(
        encoding="utf-8"
    )
    product_trusted_workflow = Path(
        ".github/workflows/product-image-smoke-trusted.yml"
    ).read_text(encoding="utf-8")
    workflow = "\n".join((product_pr_workflow, product_trusted_workflow))
    verify_script = Path("deploy/verify_product_image.sh").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile.product").read_text(encoding="utf-8")
    ownership_script = Path("scripts/normalize_product_image_smoke_artifact_ownership.sh").read_text(
        encoding="utf-8"
    )
    pull_request_block = mod._workflow_event_block(workflow, "pull_request")
    for trigger_path in mod.PRODUCT_IMAGE_SMOKE_PR_TRIGGER_REQUIRED_PATHS:
        assert f"- {trigger_path}" in pull_request_block
    assert "Recover stale product image smoke workspace artifacts" not in workflow
    assert "sudo" not in workflow
    assert "clean: false" not in workflow
    assert mod._workflow_checkout_secure_ready(workflow, minimum_count=3)
    assert mod._workflow_checkout_subdir_ready(
        workflow,
        checkout_path="product-ci-checkout",
        minimum_count=2,
    )
    assert workflow.count("working-directory: product-ci-checkout") >= 4
    assert workflow.count('ln -s "${artifact_root}" product-ci-checkout/runs') >= 2
    assert workflow.count("${{ runner.temp }}/product-image-") >= 2
    assert workflow.count("persist-credentials: false") == 3
    assert workflow.count("clean: true") == 3
    assert workflow.count('export PRODUCT_IMAGE_CONTAINER_UID_GID="$(id -u):$(id -g)"') >= 2
    assert "repair_receipt_path" in verify_script
    assert "clear_stale_receipt" in verify_script
    assert "receipt_path_cleanup_failed" in verify_script
    assert 'repair_path_ownership "${RECEIPT_JSON}"' in verify_script
    assert "normalize_runner_artifacts_on_exit" in verify_script
    assert 'repair_path_ownership "${RUNNER_SMOKE_DIR}"' in verify_script
    assert 'repair_path_ownership "${WORKSPACE_RUNNER_SMOKE_DIR}"' in verify_script
    assert "PRODUCT_IMAGE_OWNERSHIP_REPAIR_IMAGE" in verify_script
    assert "busybox:1.36.1" in verify_script
    assert "needs_ownership_repair" in verify_script
    assert "docker_repair_ownership" in verify_script
    assert "run --rm" in verify_script
    assert "/repair-root" in verify_script
    assert "chmod -R u+rwX" in verify_script
    assert "chmod -R a+rwX logs runs" in dockerfile
    assert "WORKSPACE_SMOKE_DIR" in ownership_script
    assert "verify_ownership" in ownership_script
    assert "product_image_smoke_artifact_ownership_not_normalized" in ownership_script
    assert "product_image_smoke_artifact_not_writable" in ownership_script
    assert "PRODUCT_IMAGE_OWNERSHIP_REPAIR_DOCKER_CMD" in ownership_script
    assert "PRODUCT_IMAGE_OWNERSHIP_REPAIR_IMAGE" in ownership_script
    assert "busybox:1.36.1" in ownership_script
    assert "needs_ownership_repair" in ownership_script
    assert "docker_repair_ownership" in ownership_script
    assert "run --rm" in ownership_script
    assert "/repair-root" in ownership_script
    assert "chmod -R u+rwX" in ownership_script
    api_worker_workflow = "\n".join(
        (
            Path(".github/workflows/product-api-worker.yml").read_text(encoding="utf-8"),
            Path(".github/workflows/product-api-worker-trusted.yml").read_text(
                encoding="utf-8"
            ),
        )
    )
    assert "Recover stale product image smoke workspace artifacts" not in api_worker_workflow
    assert "sudo" not in api_worker_workflow
    assert "clean: false" not in api_worker_workflow
    assert mod._workflow_checkout_secure_ready(api_worker_workflow, minimum_count=2)
    assert mod._workflow_checkout_subdir_ready(
        api_worker_workflow,
        checkout_path="product-ci-checkout",
        minimum_count=1,
    )
    assert api_worker_workflow.count("working-directory: product-ci-checkout") >= 7
    assert "Prepare ephemeral API artifact root" in api_worker_workflow
    assert 'ln -s "${artifact_root}" product-ci-checkout/runs' in api_worker_workflow
    assert all(row["execution_enabled"] is False for row in payload["rows"])
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_product_image_smoke_preflight_blocks_pre_checkout_workspace_mutation(tmp_path: Path) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    workflow_path = (
        tmp_path / ".github" / "workflows" / "product-image-smoke-trusted.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow_path.write_text(
        workflow.replace(
            "      - name: Check out trusted source",
            (
                "      - name: Recover stale product image smoke workspace artifacts\n"
                "        run: sudo chown -R runner:runner \"${GITHUB_WORKSPACE}\"\n"
                "      - name: Check out trusted source"
            ),
            1,
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert payload["summary"]["preflight_ready"] is False
    assert payload["summary"]["workflow_workspace_artifact_recovery_ready"] is False
    assert payload["summary"]["pre_checkout_cleanup_ready"] is False
    assert rows_by_id["workflow_pre_checkout_workspace_artifact_recovery_declared"]["passed"] is False
    assert {"code": "workflow_pre_checkout_workspace_artifact_recovery_declared"} in payload["blockers"]


def test_product_image_smoke_preflight_blocks_checkout_without_subdir_isolation(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    workflow_path = (
        tmp_path / ".github" / "workflows" / "product-image-smoke-trusted.yml"
    )
    workflow_path.write_text(
        workflow_path.read_text(encoding="utf-8").replace(
            "          path: product-ci-checkout\n",
            "",
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert payload["summary"]["preflight_ready"] is False
    assert payload["summary"]["workflow_contract_ready"] is False
    assert payload["summary"]["pre_checkout_cleanup_ready"] is False
    assert (
        rows_by_id["workflow_checkout_subdir_isolated_from_stale_workspace_runs"][
            "passed"
        ]
        is False
    )
    assert {"code": "workflow_checkout_subdir_isolated_from_stale_workspace_runs"} in payload[
        "blockers"
    ]


def test_product_image_smoke_preflight_blocks_insecure_checkout_cleanup(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    workflow_path = tmp_path / ".github" / "workflows" / "product-image-smoke.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow_path.write_text(
        workflow.replace(
            "          clean: true\n",
            "          clean: false\n",
            1,
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert payload["summary"]["preflight_ready"] is False
    assert payload["summary"]["workflow_workspace_artifact_recovery_ready"] is False
    assert payload["summary"]["pre_checkout_cleanup_ready"] is False
    assert rows_by_id["workflow_pre_checkout_workspace_artifact_recovery_declared"]["passed"] is False
    assert {"code": "workflow_pre_checkout_workspace_artifact_recovery_declared"} in payload["blockers"]


def test_product_image_smoke_preflight_blocks_api_worker_pre_checkout_mutation(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    workflow_path = (
        tmp_path / ".github" / "workflows" / "product-api-worker-trusted.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow_path.write_text(
        workflow.replace(
            "      - name: Check out trusted source",
            (
                "      - name: Recover stale product image smoke workspace artifacts\n"
                "        run: sudo chmod -R u+rwX \"${GITHUB_WORKSPACE}\"\n"
                "      - name: Check out trusted source"
            ),
            1,
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert payload["summary"]["preflight_ready"] is False
    assert payload["summary"]["workflow_workspace_artifact_recovery_ready"] is False
    assert payload["summary"]["pre_checkout_cleanup_ready"] is False
    assert rows_by_id["api_worker_pre_checkout_workspace_artifact_recovery_declared"]["passed"] is False
    assert {"code": "api_worker_pre_checkout_workspace_artifact_recovery_declared"} in payload["blockers"]


def test_product_image_smoke_preflight_blocks_api_worker_persisted_credentials(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    workflow_path = tmp_path / ".github" / "workflows" / "product-api-worker.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow_path.write_text(
        workflow.replace(
            "          persist-credentials: false\n",
            "          persist-credentials: true\n",
            1,
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    rows_by_id = {row["check_id"]: row for row in payload["rows"]}

    assert payload["summary"]["preflight_ready"] is False
    assert payload["summary"]["workflow_workspace_artifact_recovery_ready"] is False
    assert payload["summary"]["pre_checkout_cleanup_ready"] is False
    assert rows_by_id["api_worker_pre_checkout_workspace_artifact_recovery_declared"]["passed"] is False
    assert {"code": "api_worker_pre_checkout_workspace_artifact_recovery_declared"} in payload["blockers"]


def test_post_smoke_ownership_script_normalizes_existing_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    runner_temp = tmp_path / "runner-temp"
    runs = workspace / "runs"
    workspace_smoke_dir = runs / "product_image_smoke_runner_artifacts"
    smoke_dir = runner_temp / "product-image-build-smoke-1-1"
    runs.mkdir(parents=True)
    workspace_smoke_dir.mkdir(parents=True)
    smoke_dir.mkdir(parents=True)
    receipt = runs / "product_image_smoke_receipt_current.json"
    log = runs / "product_image_build_smoke.log"
    workspace_smoke_artifact = workspace_smoke_dir / "stale-artifact.txt"
    smoke_artifact = smoke_dir / "artifact.txt"
    receipt.write_text("{}", encoding="utf-8")
    log.write_text("log", encoding="utf-8")
    workspace_smoke_artifact.write_text("stale", encoding="utf-8")
    smoke_artifact.write_text("artifact", encoding="utf-8")
    smoke_artifact.chmod(0o400)

    result = subprocess.run(
        [
            "bash",
            "scripts/normalize_product_image_smoke_artifact_ownership.sh",
            "--log-path",
            str(log),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": "/usr/bin:/bin",
            "GITHUB_WORKSPACE": str(workspace),
            "RUNNER_TEMP": str(runner_temp),
            "PRODUCT_IMAGE_RUNNER_SMOKE_DIR": str(smoke_dir),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert receipt.is_file()
    assert log.is_file()
    assert workspace_smoke_artifact.is_file()
    assert smoke_artifact.is_file()
    assert smoke_artifact.stat().st_mode & 0o200


def test_product_image_smoke_preflight_reports_current_workspace_artifact_cleanup_state(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    workspace_smoke_dir = tmp_path / "runs" / "product_image_smoke_runner_artifacts"
    workspace_smoke_dir.mkdir(parents=True)
    stale_artifact = workspace_smoke_dir / "stale-artifact.txt"
    stale_artifact.write_text("stale", encoding="utf-8")
    stale_artifact.chmod(0o400)

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=tmp_path / "missing_receipt.json",
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["workspace_smoke_artifact_current_present"] is True
    assert summary["workspace_smoke_artifact_current_owner_ready"] is True
    assert summary["workspace_smoke_artifact_current_writable_ready"] is False
    assert summary["workspace_smoke_artifact_current_cleanup_ready"] is False
    assert summary["workspace_smoke_artifact_current_blockers"] == [
        "workspace_smoke_artifact_current_cleanup_not_ready",
        "workspace_smoke_artifact_current_not_writable",
    ]
    assert summary["workspace_smoke_artifact_current_blocker_count"] == 2
    assert summary["workspace_smoke_artifact_current_bad_owner_path"] == ""
    assert summary["workspace_smoke_artifact_current_not_writable_path"] == (
        "runs/product_image_smoke_runner_artifacts/stale-artifact.txt"
    )
    assert "normalize_product_image_smoke_artifact_ownership.sh" in summary[
        "workspace_smoke_artifact_current_required_action"
    ]
    assert {"code": "workspace_smoke_artifact_current_cleanup_not_ready"} in payload[
        "blockers"
    ]
    assert {"code": "workspace_smoke_artifact_current_not_writable"} in payload[
        "blockers"
    ]

    work_order = mod.build_product_image_smoke_runner_hygiene_work_order(payload)
    work_order_summary = work_order["summary"]
    work_order_rows = {row["blocker_id"]: row for row in work_order["rows"]}

    assert work_order_summary["workspace_cleanup_required"] is True
    assert work_order_summary["workspace_blocker_count"] == 2
    assert work_order_summary["primary_blocker"] == (
        "workspace_smoke_artifact_current_cleanup_not_ready"
    )
    assert work_order_rows["workspace_smoke_artifact_current_not_writable"][
        "expected_receipt_field"
    ] == "workspace_smoke_artifact_current_writable_ready"
    assert "normalize_product_image_smoke_artifact_ownership.sh" in work_order_rows[
        "workspace_smoke_artifact_current_not_writable"
    ]["verification_command"]


def test_product_image_smoke_preflight_blocks_without_docker_cli(tmp_path: Path) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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


def test_verify_product_image_writes_blocked_receipt_when_docker_cli_missing(tmp_path: Path) -> None:
    receipt = tmp_path / "blocked_receipt.json"
    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": "/usr/bin:/bin",
            "DOCKER_CMD": str(tmp_path / "missing-docker"),
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
            "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR": str(
                tmp_path / "workspace-smoke"
            ),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "docker_cli_missing"
    assert payload["runner_hygiene_schema_version"] == "product_image_runner_hygiene_v1"
    assert payload["receipt_ready"] is False
    assert payload["receipt_failure_stage"] == "early_or_error_exit"
    assert payload["external_state_mutated"] is False
    assert payload["container_output_uid_gid_pinned"] is True


def test_verify_product_image_blocks_invalid_container_uid_gid_before_docker(tmp_path: Path) -> None:
    receipt = tmp_path / "blocked_receipt.json"
    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": "/usr/bin:/bin",
            "DOCKER_CMD": str(tmp_path / "missing-docker"),
            "PRODUCT_IMAGE_CONTAINER_UID_GID": "root:root",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "container_uid_gid_invalid"
    assert payload["container_uid_gid"] == "root:root"
    assert payload["container_output_uid_gid_pinned"] is False


def test_verify_product_image_blocks_root_container_uid_gid_before_docker(tmp_path: Path) -> None:
    receipt = tmp_path / "blocked_receipt.json"
    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": "/usr/bin:/bin",
            "DOCKER_CMD": str(tmp_path / "missing-docker"),
            "PRODUCT_IMAGE_CONTAINER_UID_GID": "0:0",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "container_uid_gid_root"
    assert payload["container_uid_gid"] == "0:0"
    assert payload["container_output_uid_gid_pinned"] is True
    assert payload["container_output_uid_gid_non_root"] is False


def test_verify_product_image_blocks_other_user_container_uid_gid_before_docker(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "blocked_receipt.json"
    other_uid = os.getuid() + 1
    other_gid = os.getgid() + 1
    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": "/usr/bin:/bin",
            "DOCKER_CMD": str(tmp_path / "missing-docker"),
            "PRODUCT_IMAGE_CONTAINER_UID_GID": f"{other_uid}:{other_gid}",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "container_uid_gid_not_host"
    assert payload["container_uid_gid"] == f"{other_uid}:{other_gid}"
    assert payload["container_output_uid_gid_pinned"] is True
    assert payload["container_output_uid_gid_matches_host"] is False


def test_verify_product_image_blocks_github_actions_workspace_smoke_dir(tmp_path: Path) -> None:
    receipt = tmp_path / "blocked_receipt.json"
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": "/usr/bin:/bin",
            "DOCKER_CMD": str(tmp_path / "missing-docker"),
            "GITHUB_ACTIONS": "true",
            "RUNNER_TEMP": str(runner_temp),
            "PRODUCT_IMAGE_RUNNER_SMOKE_DIR": "runs/product_image_smoke_runner_artifacts",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "runner_smoke_dir_inside_workspace"
    assert payload["runner_hygiene_schema_version"] == "product_image_runner_hygiene_v1"
    assert payload["runner_smoke_dir"].endswith("runs/product_image_smoke_runner_artifacts")
    assert payload["workspace_runner_smoke_dir"].endswith("runs/product_image_smoke_runner_artifacts")
    assert payload["runner_smoke_dir_outside_workspace"] is False
    assert payload["workspace_runner_smoke_dir_cleanup_ready"] is False


def test_verify_product_image_blocks_when_local_workspace_cleanup_fails(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "blocked_receipt.json"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_rm = fake_bin / "rm"
    fake_rm.write_text(
        """#!/usr/bin/env bash
if [[ "$*" == *"product_image_smoke_runner_artifacts"* ]]; then
  exit 1
fi
exec /usr/bin/rm "$@"
""",
        encoding="utf-8",
    )
    fake_rm.chmod(0o755)
    workspace_smoke = tmp_path / "workspace" / "product_image_smoke_runner_artifacts"
    workspace_smoke.mkdir(parents=True)
    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "DOCKER_CMD": str(tmp_path / "missing-docker"),
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
            "PRODUCT_IMAGE_RUNNER_SMOKE_DIR": str(
                tmp_path / "runner-smoke"
            ),
            "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR": str(
                workspace_smoke
            ),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "workspace_smoke_dir_cleanup_failed"
    assert payload["runner_smoke_dir_outside_workspace"] is True
    assert payload["workspace_runner_smoke_dir_cleanup_ready"] is False
    assert payload["workspace_runner_smoke_dir_cleanup_blockers"] == [
        "workspace_runner_smoke_dir_cleanup_not_ready"
    ]
    assert "sudo chown -R" in payload["next_required_step"]
    assert str(workspace_smoke) in payload["workspace_runner_smoke_dir_cleanup_required_action"]


def test_verify_product_image_writes_blocked_receipt_after_container_start_failure(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
cmd="${1:-}"
shift || true
case "${cmd}" in
  info) exit 0 ;;
  buildx) exit 0 ;;
  build) exit 0 ;;
  run)
    if [[ "${1:-}" == "-d" ]]; then
      echo fake-container-id
    fi
    exit 0
    ;;
  port) echo "127.0.0.1:49152"; exit 0 ;;
  rm) exit 0 ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
if [[ "$*" == *"%{http_code}"* ]]; then
  printf '500'
fi
exit 0
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    receipt = tmp_path / "post_container_blocked_receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "blocked_product_image_smoke",
                "reason": "workspace_smoke_dir_cleanup_failed",
                "receipt_failure_stage": "stale_previous_run",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "deploy/verify_product_image.sh"],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        env={
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "DOCKER_CMD": "docker",
            "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON": str(receipt),
            "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR": str(
                tmp_path / "workspace-smoke"
            ),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_product_image_smoke"
    assert payload["reason"] == "script_error_exit_1"
    assert payload["receipt_ready"] is False
    assert payload["receipt_failure_stage"] == "early_or_error_exit"
    assert payload["external_state_mutated"] is False


def test_product_image_smoke_preflight_blocks_when_docker_daemon_unreachable_without_receipt(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
                "PRODUCT_IMAGE_REQUIRE_BUILDX",
                "docker_buildx_missing",
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
                "DEFAULT_RUNNER_SMOKE_DIR",
                "${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts",
                "RUNNER_TEMP",
                "PRODUCT_IMAGE_RUNNER_SMOKE_DIR",
                "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR",
                "PRODUCT_IMAGE_CONTAINER_UID_GID",
                "HOST_UID_GID",
                "CONTAINER_UID_GID",
                "CONTAINER_OUTPUT_UID_GID_PINNED",
                "CONTAINER_OUTPUT_UID_GID_MATCHES_HOST",
                "CONTAINER_OUTPUT_UID_GID_NON_ROOT",
                "container_uid_gid_invalid",
                "container_uid_gid_not_host",
                "container_uid_gid_root",
                "DOCKER_SMOKE_RUN_ARGS",
                "--user",
                "reset_runner_smoke_dir",
                "runner_smoke_dir_cleanup_failed",
                "normalize_runner_artifacts_on_exit",
                'repair_path_ownership "${RUNNER_SMOKE_DIR}"',
                'repair_path_ownership "${WORKSPACE_RUNNER_SMOKE_DIR}"',
                "WORKSPACE_RUNNER_SMOKE_DIR",
                "RUNNER_SMOKE_DIR_OUTSIDE_WORKSPACE",
                "recover_workspace_smoke_dir",
                "workspace_smoke_dir_cleanup_failed",
                "runner_smoke_dir_inside_workspace",
                "runner_smoke_dir_outside_workspace",
                "workspace_runner_smoke_dir_cleanup_ready",
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
                "docker/setup-buildx-action@v3",
                'DOCKER_BUILDKIT: "1"',
                'PRODUCT_IMAGE_REQUIRE_BUILDX: "1"',
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
    _copy_product_image_preflight_fixture(tmp_path)
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
                "runtime_neighbor_release_scaling_present": True,
                "runtime_neighbor_release_scaling_ready": True,
                "runtime_neighbor_release_scaling_status": "runtime_neighbor_release_scaling_ready",
                "runtime_neighbor_release_atom_counts_ready": True,
                "runtime_neighbor_release_atom_counts": [1000, 2000, 4000, 8000],
                "runtime_neighbor_release_pair_count_slope": 1.0,
                "runtime_neighbor_release_pair_count_r2": 1.0,
                "runtime_neighbor_release_nxn_allocation_observed": False,
                "runtime_neighbor_release_max_memory_peak_mb_per_atom": 1.25,
                **_runner_hygiene_fields(),
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    assert summary["receipt_runner_hygiene_schema_version"] == "product_image_runner_hygiene_v1"
    assert summary["receipt_runner_hygiene_schema_ready"] is True
    assert summary["receipt_runner_smoke_dir_outside_workspace"] is True
    assert summary["receipt_container_uid_gid"] == "1000:1000"
    assert summary["receipt_container_output_uid_gid_pinned"] is True
    assert summary["container_output_uid_gid_fixed"] is True
    assert summary["pre_checkout_cleanup_ready"] is True
    assert summary["receipt_workspace_runner_smoke_dir_cleanup_ready"] is True
    assert summary["receipt_workspace_runner_smoke_dir_exists_after_cleanup"] is False
    assert summary["receipt_runner_hygiene_ready"] is True
    assert summary["receipt_runner_hygiene_refresh_required"] is False
    assert summary["receipt_runner_hygiene_blocker_count"] == 0
    assert summary["receipt_simulate_missing_profile_http"] == 422
    assert summary["container_runtime_proof_schema_version"] == "rocm_container_runtime_proof_v1"
    assert summary["container_runtime_receipt_ready"] is True
    assert summary["container_runtime_in_container"] is True
    assert summary["container_runtime_device_nodes_ready"] is True
    assert summary["container_runtime_torch_rocm_ready"] is True
    assert summary["container_runtime_visible_device_count"] == 1
    assert summary["container_runtime_rust_hip_backend_enabled"] is True
    assert summary["runtime_neighbor_release_scaling_present"] is True
    assert summary["runtime_neighbor_release_scaling_ready"] is True
    assert summary["runtime_neighbor_release_scaling_status"] == "runtime_neighbor_release_scaling_ready"
    assert summary["runtime_neighbor_release_atom_counts_ready"] is True
    assert summary["runtime_neighbor_release_atom_counts"] == [1000, 2000, 4000, 8000]
    assert summary["runtime_neighbor_release_pair_count_slope"] == 1.0
    assert summary["runtime_neighbor_release_pair_count_r2"] == 1.0
    assert summary["runtime_neighbor_release_nxn_allocation_observed"] is False
    assert summary["product_runner_smoke_ready"] is True
    assert summary["product_runner_claim_metadata_ready"] is True
    assert summary["tier_alpha_result_manifest_signature_verified"] is True
    assert summary["backmapping_runner_claim_metadata_ready"] is True

    payload_without_live_docker = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    _copy_product_image_preflight_fixture(tmp_path)
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
                **_runner_hygiene_fields(),
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    _copy_product_image_preflight_fixture(tmp_path)
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
                **_runner_hygiene_fields(),
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    _copy_product_image_preflight_fixture(tmp_path)
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
                **_runner_hygiene_fields(),
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    _copy_product_image_preflight_fixture(tmp_path)
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
                **_runner_hygiene_fields(),
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    _copy_product_image_preflight_fixture(tmp_path)
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
                **_runner_hygiene_fields(),
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
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
    _copy_product_image_preflight_fixture(tmp_path)
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
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )

    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert payload["summary"]["receipt_present"] is True
    assert payload["summary"]["receipt_mode"] == "build"


def test_product_image_smoke_preflight_rejects_rocm_receipt_with_workspace_artifact_root(tmp_path: Path) -> None:
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
                "runtime_neighbor_release_scaling_present": True,
                "runtime_neighbor_release_scaling_ready": True,
                "runtime_neighbor_release_scaling_status": "runtime_neighbor_release_scaling_ready",
                "runtime_neighbor_release_atom_counts_ready": True,
                "runtime_neighbor_release_atom_counts": [1000, 2000, 4000, 8000],
                "runtime_neighbor_release_pair_count_slope": 1.0,
                "runtime_neighbor_release_pair_count_r2": 1.0,
                "runtime_neighbor_release_nxn_allocation_observed": False,
                "runtime_neighbor_release_max_memory_peak_mb_per_atom": 1.25,
                "runner_hygiene_schema_version": "product_image_runner_hygiene_v1",
                "runner_smoke_dir": "runs/product_image_smoke_runner_artifacts",
                "workspace_runner_smoke_dir": "runs/product_image_smoke_runner_artifacts",
                "runner_smoke_dir_outside_workspace": False,
                "host_uid_gid": "1000:1000",
                "container_uid_gid": "1000:1000",
                "container_output_uid_gid_pinned": True,
                "container_output_uid_gid_matches_host": True,
                "container_output_uid_gid_non_root": True,
                "workspace_runner_smoke_dir_cleanup_ready": True,
                "workspace_runner_smoke_dir_exists_after_cleanup": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["receipt_runner_smoke_dir_outside_workspace"] is False
    assert summary["receipt_container_output_uid_gid_pinned"] is True
    assert summary["receipt_container_output_uid_gid_matches_host"] is True
    assert summary["receipt_container_output_uid_gid_non_root"] is True
    assert summary["container_output_uid_gid_fixed"] is True
    assert summary["receipt_runner_hygiene_ready"] is False
    assert summary["receipt_runner_hygiene_refresh_required"] is True
    assert summary["receipt_runner_hygiene_blockers"] == [
        "receipt_runner_smoke_dir_inside_workspace"
    ]
    assert "Refresh the ROCm product image smoke receipt" in summary[
        "receipt_runner_hygiene_required_action"
    ]
    assert {"code": "receipt_runner_smoke_dir_inside_workspace"} in payload["blockers"]


def test_product_image_smoke_preflight_rejects_rocm_receipt_without_uid_pinning(
    tmp_path: Path,
) -> None:
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
                "backmapping_ligand_topology_schema_version": "ligand_topology_validity_v1",
                "backmapping_ligand_topology_schema_ready_row_count": 2,
                "backmapping_ligand_topology_receipt_ready": True,
                "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1",
                **_hbond_claim_metadata_schema_fields(),
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 2,
                "backmapping_onsps_backmap_claim_safe_row_count": 1,
                "rocm_runtime_visible_device_required": True,
                "runtime_neighbor_release_scaling_present": True,
                "runtime_neighbor_release_scaling_ready": True,
                "runtime_neighbor_release_scaling_status": "runtime_neighbor_release_scaling_ready",
                "runtime_neighbor_release_atom_counts_ready": True,
                "runtime_neighbor_release_nxn_allocation_observed": False,
                "runner_hygiene_schema_version": "product_image_runner_hygiene_v1",
                "runner_smoke_dir": "/tmp/product_image_smoke_runner_artifacts",
                "workspace_runner_smoke_dir": "runs/product_image_smoke_runner_artifacts",
                "runner_smoke_dir_outside_workspace": True,
                "container_uid_gid": "",
                "container_output_uid_gid_pinned": False,
                "container_output_uid_gid_matches_host": False,
                "container_output_uid_gid_non_root": False,
                "workspace_runner_smoke_dir_cleanup_ready": True,
                "workspace_runner_smoke_dir_exists_after_cleanup": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["receipt_runner_hygiene_ready"] is False
    assert summary["container_output_uid_gid_fixed"] is False
    assert summary["receipt_runner_hygiene_blockers"] == [
        "receipt_container_output_uid_gid_not_pinned",
        "receipt_container_output_uid_gid_not_host",
        "receipt_container_output_uid_gid_root",
    ]
    assert {"code": "receipt_container_output_uid_gid_not_pinned"} in payload["blockers"]


def test_product_image_smoke_preflight_marks_legacy_rocm_receipt_for_runner_hygiene_refresh(
    tmp_path: Path,
) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    receipt_json = tmp_path / "legacy_receipt.json"
    runner_hygiene = _runner_hygiene_fields()
    runner_hygiene.pop("runner_hygiene_schema_version")
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
                "backmapping_ligand_topology_schema_version": "ligand_topology_validity_v1",
                "backmapping_ligand_topology_schema_ready_row_count": 2,
                "backmapping_ligand_topology_receipt_ready": True,
                "backmapping_hbond_evidence_schema_version": "hbond_evidence_v1",
                **_hbond_claim_metadata_schema_fields(),
                "backmapping_onsps_backmap_schema_version": "onsps_backmap_evidence_v1",
                "backmapping_hbond_evaluated_row_count": 2,
                "backmapping_onsps_backmap_claim_safe_row_count": 1,
                "rocm_runtime_visible_device_required": True,
                "runtime_neighbor_release_scaling_present": True,
                "runtime_neighbor_release_scaling_ready": True,
                "runtime_neighbor_release_scaling_status": "runtime_neighbor_release_scaling_ready",
                "runtime_neighbor_release_atom_counts_ready": True,
                "runtime_neighbor_release_nxn_allocation_observed": False,
                **runner_hygiene,
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_product_image_smoke_preflight(
        root=tmp_path,
        docker_cli_path="/usr/bin/docker",
        docker_daemon_ready=True,
        receipt_json=receipt_json,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_image_smoke_preflight"
    assert summary["preflight_ready"] is False
    assert summary["clean_container_smoke_ready"] is False
    assert summary["receipt_runner_hygiene_schema_ready"] is False
    assert summary["receipt_runner_hygiene_refresh_required"] is True
    assert summary["receipt_runner_hygiene_blockers"] == [
        "receipt_runner_hygiene_schema_missing"
    ]
    assert "runner-temp smoke artifact directory" in summary[
        "receipt_runner_hygiene_required_action"
    ]
    assert "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime" in summary[
        "receipt_runner_hygiene_verification_command"
    ]
    assert 'PRODUCT_IMAGE_CONTAINER_UID_GID="$(id -u):$(id -g)"' in summary[
        "receipt_runner_hygiene_verification_command"
    ]
    assert {"code": "receipt_runner_hygiene_schema_missing"} in payload["blockers"]
    work_order = mod.build_product_image_smoke_runner_hygiene_work_order(payload)
    work_order_summary = work_order["summary"]

    assert work_order_summary["status"] == "product_image_smoke_runner_hygiene_work_order_ready"
    assert work_order_summary["work_order_ready"] is True
    assert work_order_summary["runner_hygiene_ready"] is False
    assert work_order_summary["refresh_required"] is True
    assert work_order_summary["blocker_count"] == 1
    assert work_order_summary["primary_blocker"] == "receipt_runner_hygiene_schema_missing"
    assert work_order_summary["required_runner_hygiene_schema_version"] == (
        "product_image_runner_hygiene_v1"
    )
    assert work_order_summary["receipt_runner_hygiene_schema_version"] == ""
    assert work_order_summary["execution_enabled"] is False
    assert work_order_summary["external_state_mutated"] is False
    assert work_order["rows"] == [
        {
            "blocker_id": "receipt_runner_hygiene_schema_missing",
            "status": "operator_action_required",
            "expected_receipt_field": "receipt_runner_hygiene_schema_version",
            "expected_value": "product_image_runner_hygiene_v1",
            "observed_value": "",
            "required_action": summary["receipt_runner_hygiene_required_action"],
            "verification_command": summary["receipt_runner_hygiene_verification_command"],
            "receipt_json": str(receipt_json),
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    ]
    command_pack = mod.build_product_image_smoke_runner_hygiene_command_pack(
        payload,
        work_order,
    )
    command_pack_summary = command_pack["summary"]
    command_pack_rows = {row["target"]: row for row in command_pack["rows"]}

    assert command_pack_summary["status"] == (
        "product_image_smoke_runner_hygiene_command_pack_ready"
    )
    assert command_pack_summary["refresh_required"] is True
    assert command_pack_summary["runner_hygiene_ready"] is False
    assert command_pack_summary["target_count"] == 3
    assert command_pack_summary["targets"] == [
        "normalize-artifacts",
        "rocm-runtime-refresh",
        "preflight-rebuild",
    ]
    assert "PRODUCT_IMAGE_CONTAINER_UID_GID" in "\n".join(
        command_pack_rows["rocm-runtime-refresh"]["commands"]
    )
    assert command_pack_rows["normalize-artifacts"]["platform_guard"] == "linux"
    assert command_pack_rows["rocm-runtime-refresh"]["platform_guard"] == "linux"
    assert "--log-path runs/product_image_build_smoke.log" in "\n".join(
        command_pack_rows["normalize-artifacts"]["commands"]
    )
    assert "--log-path runs/product_image_rocm_runtime_smoke.log" in "\n".join(
        command_pack_rows["normalize-artifacts"]["commands"]
    )
    assert "tee runs/product_image_rocm_runtime_smoke.log" in "\n".join(
        command_pack_rows["rocm-runtime-refresh"]["commands"]
    )
    assert "rc=\"${PIPESTATUS[0]}\"" in "\n".join(
        command_pack_rows["rocm-runtime-refresh"]["commands"]
    )
    assert "tools/build_product_image_smoke_preflight.py" in "\n".join(
        command_pack_rows["preflight-rebuild"]["commands"]
    )
    assert all(row["execution_enabled"] is False for row in command_pack["rows"])
    assert all(row["external_state_mutated"] is False for row in command_pack["rows"])


def test_product_image_smoke_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    _copy_product_image_preflight_fixture(tmp_path)
    out_json = tmp_path / "preflight.json"
    out_md = tmp_path / "preflight.md"
    out_work_order_json = tmp_path / "runner_hygiene_work_order.json"
    out_work_order_csv = tmp_path / "runner_hygiene_work_order.csv"
    out_work_order_md = tmp_path / "runner_hygiene_work_order.md"
    out_command_pack_json = tmp_path / "runner_hygiene_command_pack.json"
    out_command_pack_sh = tmp_path / "runner_hygiene_command_pack.sh"
    out_command_pack_md = tmp_path / "runner_hygiene_command_pack.md"
    missing_receipt = tmp_path / "missing_receipt.json"

    rc = mod.main([
        "--root",
        str(tmp_path),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
        "--out-runner-hygiene-work-order-json",
        str(out_work_order_json),
        "--out-runner-hygiene-work-order-csv",
        str(out_work_order_csv),
        "--out-runner-hygiene-work-order-md",
        str(out_work_order_md),
        "--out-runner-hygiene-command-pack-json",
        str(out_command_pack_json),
        "--out-runner-hygiene-command-pack-sh",
        str(out_command_pack_sh),
        "--out-runner-hygiene-command-pack-md",
        str(out_command_pack_md),
        "--receipt-json",
        str(missing_receipt),
    ])

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "product_image_smoke_preflight"
    assert payload["summary"]["clean_container_smoke_ready"] is False
    assert "Product Image Smoke Preflight" in out_md.read_text(encoding="utf-8")
    work_order = json.loads(out_work_order_json.read_text(encoding="utf-8"))
    assert work_order["summary"]["packet_type"] == (
        "product_image_smoke_runner_hygiene_work_order"
    )
    assert work_order["summary"]["status"] == (
        "product_image_smoke_runner_hygiene_work_order_ready"
    )
    assert work_order["summary"]["work_order_ready"] is True
    assert work_order["summary"]["refresh_required"] is False
    assert out_work_order_csv.read_text(encoding="utf-8").startswith(
        "blocker_id,status,expected_receipt_field,"
    )
    assert "Product Image Smoke Runner Hygiene Work Order" in out_work_order_md.read_text(
        encoding="utf-8"
    )
    command_pack = json.loads(out_command_pack_json.read_text(encoding="utf-8"))
    assert command_pack["summary"]["packet_type"] == (
        "product_image_smoke_runner_hygiene_command_pack"
    )
    assert command_pack["summary"]["target_count"] == 3
    command_pack_sh = out_command_pack_sh.read_text(encoding="utf-8")
    assert command_pack_sh.startswith("#!/usr/bin/env bash")
    assert "case \"$target\" in" in command_pack_sh
    assert "require_platform linux" in command_pack_sh
    assert "--log-path runs/product_image_rocm_runtime_smoke.log" in command_pack_sh
    assert "rc=\"${PIPESTATUS[0]}\"" in command_pack_sh
    assert "rocm-runtime-refresh)" in command_pack_sh
    assert "preflight-rebuild)" in command_pack_sh
    assert "Product Image Smoke Runner Hygiene Command Pack" in out_command_pack_md.read_text(
        encoding="utf-8"
    )
