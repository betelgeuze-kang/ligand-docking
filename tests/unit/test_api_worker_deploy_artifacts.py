from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    EXECUTION_EVIDENCE_PURPOSE_REQUEST_KEY,
    EXECUTION_EVIDENCE_SOURCE_ACTOR_REQUEST_KEY,
    TIER_ALPHA_ADRB2_EVIDENCE_PURPOSE,
    TIER_ALPHA_ADRB2_SOURCE_ACTOR,
    tier_alpha_adrb2_execution_evidence,
)
from api.validated_runner_runtime_qualification import RECEIPT_SCHEMA_VERSION
import tools.product.run_tier_alpha_adrb2_dispatch_smoke as tier_alpha_smoke
from tools.product.run_tier_alpha_adrb2_dispatch_smoke import (
    _run_operator_qualified_profile,
    _validated_runner_runtime_manifest_binding,
)


def _run_attempt_bound_tier_alpha_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    job_id: str,
    tamper_published_manifest_path: bool = False,
) -> tuple[dict[str, Any], Path]:
    """Run the real dispatch/store/worker path with only profile execution faked."""

    workspace = tmp_path / "tier-alpha-workspace"
    signing_key = "operator-managed-signing-key-0123456789abcdef"
    key_id = "operator-key-v1"

    import api.config as config_mod
    original_settings = config_mod.settings

    with monkeypatch.context() as scoped:
        scoped.setattr(config_mod, "settings", original_settings)
        scoped.setenv("API_RESULT_MANIFEST_SIGNING_KEY", signing_key)
        scoped.setenv("API_RESULT_MANIFEST_KEY_ID", key_id)
        tier_alpha_smoke._configure_runtime(
            workspace=workspace,
            job_id=job_id,
            runner_enabled=True,
            runner_timeout_seconds=30,
        )
        importlib.reload(config_mod)

        import api.docking_dispatch as docking_dispatch
        import api.validated_runner as validated_runner
        import api.worker as worker

        # The CLI normally starts in a fresh interpreter. Keep cached modules in
        # this test process on the same freshly reloaded settings object.
        scoped.setattr(docking_dispatch, "settings", config_mod.settings)
        scoped.setattr(validated_runner, "settings", config_mod.settings)
        scoped.setattr(worker, "settings", config_mod.settings)
        scoped.setattr(tier_alpha_smoke, "_reload_settings", lambda: None)

        async def _qualified_fake_runner(
            current_job_id: str,
            request_data: dict[str, Any],
        ) -> None:
            del request_data
            attempt_dir = Path(worker.job_results_dir(current_job_id))
            result_file = attempt_dir / "htvs_summary.json"
            result_file.write_text(
                '{"status":"completed","probe":true}\n',
                encoding="utf-8",
            )
            status = worker.read_status_file(worker.job_status_path(current_job_id))
            status.update(
                {
                    "job_id": current_job_id,
                    "status": "completed",
                    "result_file": str(result_file),
                    "validated_runner_namespace_runtime_qualified": True,
                    "validated_runner_namespace_runtime_receipt_schema_version": (
                        RECEIPT_SCHEMA_VERSION
                    ),
                    "validated_runner_namespace_runtime_receipt_sha256": "a" * 64,
                    "validated_runner_namespace_runtime_receipt_issued_at_utc": (
                        "2026-07-16T00:00:00Z"
                    ),
                    "validated_runner_namespace_runtime_receipt_expires_at_utc": (
                        "2026-07-16T01:00:00Z"
                    ),
                    EXECUTION_EVIDENCE_PROVENANCE_KEY: (
                        tier_alpha_adrb2_execution_evidence(current_job_id)
                    ),
                }
            )
            worker.write_status_file(worker.job_status_path(current_job_id), status)

        scoped.setattr(
            tier_alpha_smoke,
            "_run_operator_qualified_profile",
            _qualified_fake_runner,
        )

        if tamper_published_manifest_path:
            process_next_job_once = worker.process_next_job_once

            async def _process_then_mix_published_attempt(
                *args: Any,
                **kwargs: Any,
            ) -> dict[str, Any] | None:
                completed = await process_next_job_once(*args, **kwargs)
                if completed is None or completed.get("status") != "completed":
                    return completed
                legitimate_manifest = Path(completed["result_manifest_path"])
                foreign_attempt = (
                    workspace
                    / "results"
                    / job_id
                    / ".attempts"
                    / f"attempt-999999-{'f' * 64}-{'e' * 64}"
                )
                foreign_attempt.mkdir(mode=0o700)
                foreign_manifest = foreign_attempt / "result_manifest.json"
                foreign_manifest.write_bytes(legitimate_manifest.read_bytes())
                published_status = Path(completed["published_status_path"])
                status = json.loads(published_status.read_text(encoding="utf-8"))
                status["result_manifest"] = str(foreign_manifest)
                published_status.write_text(
                    json.dumps(status),
                    encoding="utf-8",
                )
                return completed

            scoped.setattr(
                worker,
                "process_next_job_once",
                _process_then_mix_published_attempt,
            )

        packet = tier_alpha_smoke.run_tier_alpha_adrb2_dispatch_smoke(
            workspace=workspace,
            job_id=job_id,
            timeout_seconds=30,
            poll_seconds=0.01,
        )

    return packet, workspace


def test_product_compose_runs_api_and_worker_with_shared_queue() -> None:
    compose = Path("deploy/docker-compose.product.yml").read_text(encoding="utf-8")

    assert "api-server:" in compose
    assert "api-worker:" in compose
    assert "api-docking-dispatch:" in compose
    assert "tools/run_api_docking_dispatch_worker.py" in compose
    assert "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS" in compose
    assert 'API_INLINE_WORKER_ENABLED: "0"' in compose
    assert compose.count('API_VALIDATED_RUNNER_ENABLED: "0"') == 3
    assert "${API_VALIDATED_RUNNER_ENABLED" not in compose
    assert "API_VALIDATED_RUNNER_PROFILES_PATH" in compose
    assert 'API_JOB_STORE_PATH: "/data/api_jobs.sqlite3"' in compose
    assert compose.count('RESULTS_STORAGE_PATH: "/data/results"') == 3
    assert 'DOCKING_PRIVATE_PAYLOAD_DIR: "/data/private_payloads"' in compose
    assert 'PRODUCT_API_AUDIT_LOG_PATH: "/data/results/product_audit_log.jsonl"' in compose
    assert 'PRODUCT_API_SECURITY_LEDGER_PATH: "/data/results/product_security.sqlite3"' in compose
    assert "micf-product-results:/data" in compose
    assert "tools/run_api_simulation_worker.py" in compose
    assert "--worker-id api-worker-$${HOSTNAME}" in compose
    assert "FORCE_RUST_HIP" in compose
    assert "RUST_HIP_USE_GPU_NBLIST_BUILDER" in compose
    assert "TORCH_BLAS_PREFER_HIPBLASLT" in compose
    assert "/dev/kfd:/dev/kfd" in compose
    assert "/dev/dri:/dev/dri" in compose
    assert "API_RESULT_MANIFEST_SIGNING_KEY: \"${API_RESULT_MANIFEST_SIGNING_KEY:?set API_RESULT_MANIFEST_SIGNING_KEY}\"" in compose
    assert "PRODUCT_API_TOKEN: \"${PRODUCT_API_TOKEN:?set PRODUCT_API_TOKEN}\"" in compose
    assert compose.count(
        'DOCKING_PRIVATE_PAYLOAD_KEYS: "${DOCKING_PRIVATE_PAYLOAD_KEYS:?set DOCKING_PRIVATE_PAYLOAD_KEYS}"'
    ) == 1
    assert 'PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED: "${PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED:-0}"' in compose


def test_standard_container_route_keeps_validated_execution_unqualified() -> None:
    compose = Path("deploy/docker-compose.product.yml").read_text(encoding="utf-8")
    env_example = Path("deploy/docker-compose.product.env.example").read_text(
        encoding="utf-8"
    )
    stack_script = Path("deploy/run_tier_alpha_product_stack.sh").read_text(
        encoding="utf-8"
    )
    verify_script = Path("deploy/verify_product_image.sh").read_text(
        encoding="utf-8"
    )
    preflight_builder = Path(
        "tools/product/build_product_image_smoke_preflight.py"
    ).read_text(encoding="utf-8")
    runtime_verifier = Path(
        "api/validated_runner_runtime_qualification.py"
    ).read_text(encoding="utf-8")
    kubernetes_config = Path("deploy/k8s/configmap.yaml").read_text(encoding="utf-8")
    assert compose.count('API_VALIDATED_RUNNER_ENABLED: "0"') == 3
    assert 'API_VALIDATED_RUNNER_ENABLED: "0"' in kubernetes_config
    assert "API_VALIDATED_RUNNER_ENABLED=0" in env_example
    assert "namespace-capable" in env_example
    assert "Standard Docker/Compose is not validated-runner namespace-qualified" in stack_script
    assert "run_tier_alpha_adrb2_dispatch_smoke.py" not in verify_script
    assert "API_VALIDATED_RUNNER_ENABLED=1" not in verify_script
    assert '"validated_runner_namespace_runtime_qualified": False' in verify_script
    assert '"customer_execution_enabled": False' in verify_script
    assert "verify_validated_runner_namespace_runtime" in preflight_builder
    assert "validated_runner_namespace_runtime_receipt_v1" in runtime_verifier
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH" in runtime_verifier
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256" in runtime_verifier

    policy_text = "\n".join(
        (compose, env_example, stack_script, kubernetes_config)
    )
    for forbidden in (
        "privileged: true",
        "SYS_ADMIN",
        "seccomp=unconfined",
        "apparmor=unconfined",
    ):
        assert forbidden not in policy_text


def test_tier_alpha_smoke_uses_operator_only_runner_and_exact_manifest_binding() -> None:
    smoke_source = Path(
        "tools/product/run_tier_alpha_adrb2_dispatch_smoke.py"
    ).read_text(encoding="utf-8")
    assert "runner=_run_operator_qualified_profile" in smoke_source
    assert "require_customer_submission_allowed=False" in smoke_source

    qualification = {
        "validated_runner_namespace_runtime_qualified": True,
        "validated_runner_namespace_runtime_receipt_schema_version": (
            RECEIPT_SCHEMA_VERSION
        ),
        "validated_runner_namespace_runtime_receipt_sha256": "a" * 64,
        "validated_runner_namespace_runtime_receipt_issued_at_utc": (
            "2026-07-16T00:00:00Z"
        ),
        "validated_runner_namespace_runtime_receipt_expires_at_utc": (
            "2026-07-16T01:00:00Z"
        ),
    }
    manifest = {
        "worker_provenance": {
            "validated_runner_runtime_qualification": qualification
        }
    }

    verified, summary_fields = _validated_runner_runtime_manifest_binding(
        manifest,
        dict(qualification),
    )

    assert verified is True
    assert summary_fields == qualification

    mismatched_status = dict(qualification)
    mismatched_status[
        "validated_runner_namespace_runtime_receipt_sha256"
    ] = "b" * 64
    verified, summary_fields = _validated_runner_runtime_manifest_binding(
        manifest,
        mismatched_status,
    )
    assert verified is False
    assert summary_fields[
        "validated_runner_namespace_runtime_qualified"
    ] is False

    malformed_manifest = {
        "worker_provenance": {
            "validated_runner_runtime_qualification": {
                **qualification,
                "validated_runner_namespace_runtime_qualified": 1,
            }
        }
    }
    verified, _ = _validated_runner_runtime_manifest_binding(
        malformed_manifest,
        dict(qualification),
    )
    assert verified is False


def test_tier_alpha_smoke_verifies_the_completed_winner_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "tier_alpha_adrb2_smoke_attempt_winner"
    packet, workspace = _run_attempt_bound_tier_alpha_smoke(
        tmp_path,
        monkeypatch,
        job_id=job_id,
    )

    summary = packet["summary"]
    assert summary["status"] == "tier_alpha_adrb2_dispatch_smoke_pass"
    assert summary["validated_result_artifacts_verified"] is True
    assert summary["ledger_result_binding_verified"] is True
    assert (
        summary["validated_runner_namespace_runtime_manifest_binding_verified"]
        is True
    )
    assert (
        summary[
            "validated_runner_execution_evidence_manifest_binding_verified"
        ]
        is True
    )
    assert packet["sqlite_job_status"] == "completed"
    assert packet["ledger_worker_state"] == "completed_fail_closed"
    assert packet["simulation_sync_status"] == "completed"
    assert packet["result_manifest_signature_verified"] is True
    assert packet["result_manifest_status_verified"] is True
    assert len(packet["result_manifest_sha256"]) == 64

    job_root = workspace / "results" / job_id
    result_file = Path(packet["result_file"])
    result_manifest = Path(packet["result_manifest"])
    published_status = Path(packet["status_json"])
    winner_attempt = result_file.parent
    assert result_manifest.parent == winner_attempt
    assert published_status.parent == winner_attempt
    assert published_status.name == "published_status.json"
    attempt_parts = winner_attempt.relative_to(job_root).parts
    assert attempt_parts[0] == ".attempts"
    assert attempt_parts[1].startswith("attempt-000001-")
    assert not (job_root / "result_manifest.json").exists()

    ledger = json.loads(
        (workspace / "results" / "product_docking_jobs" / f"{job_id}.json").read_text(
            encoding="utf-8"
        )
    )
    terminal_event = ledger["event_history"][-1]
    assert ledger["last_event_type"] == "worker_dispatch_completed"
    assert terminal_event["event_type"] == "worker_dispatch_completed"
    assert terminal_event["actor"] == "tier-alpha-adrb2-smoke-worker"
    assert terminal_event["worker_state"] == "completed_fail_closed"
    assert terminal_event["simulation_status"] == "completed"
    assert terminal_event["simulation_result_file"] == packet["result_file"]


def test_tier_alpha_smoke_rejects_a_foreign_manifest_in_published_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet, _ = _run_attempt_bound_tier_alpha_smoke(
        tmp_path,
        monkeypatch,
        job_id="tier_alpha_adrb2_smoke_attempt_mixed",
        tamper_published_manifest_path=True,
    )

    summary = packet["summary"]
    assert summary["status"] == "tier_alpha_adrb2_dispatch_smoke_failed"
    assert summary["validated_result_artifacts_verified"] is False
    assert summary["ledger_result_binding_verified"] is False
    assert (
        summary["validated_runner_namespace_runtime_manifest_binding_verified"]
        is False
    )
    assert packet["sqlite_job_status"] == "completed"
    assert packet["ledger_worker_state"] == "completed_fail_closed"
    assert packet["simulation_sync_status"] == "completed"
    assert packet["result_manifest_signature_verified"] is False
    assert packet["result_manifest_status_verified"] is False
    assert packet["result_manifest"] == ""
    assert packet["result_file"] == ""


def test_tier_alpha_operator_wrapper_binds_exact_execution_purpose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    captured: dict[str, object] = {}

    async def _capture(
        job_id: str,
        request_data: dict[str, object],
        *,
        require_customer_submission_allowed: bool,
    ) -> dict[str, object]:
        captured.update(
            {
                "job_id": job_id,
                "request_data": request_data,
                "require_customer_submission_allowed": (
                    require_customer_submission_allowed
                ),
            }
        )
        return {}

    monkeypatch.setattr(validated_runner, "execute_validated_runner_profile", _capture)
    request = {
        "runner_profile_id": "ligand_htvs_pipeline_default",
        "target_name": "ADRB2",
        "runner_profile_params": {
            "family": "gpcr",
            "docking_job_id": "tier_alpha_adrb2_smoke_test",
        },
    }
    asyncio.run(
        _run_operator_qualified_profile(
            "tier_alpha_adrb2_smoke_test",
            request,
        )
    )
    bound_request = captured["request_data"]
    assert isinstance(bound_request, dict)
    assert bound_request[EXECUTION_EVIDENCE_PURPOSE_REQUEST_KEY] == (
        TIER_ALPHA_ADRB2_EVIDENCE_PURPOSE
    )
    assert bound_request[EXECUTION_EVIDENCE_SOURCE_ACTOR_REQUEST_KEY] == (
        TIER_ALPHA_ADRB2_SOURCE_ACTOR
    )
    assert captured["require_customer_submission_allowed"] is False

    invalid_request = dict(request)
    invalid_request["target_name"] = "FOREIGN"
    with pytest.raises(PermissionError, match="execution identity"):
        asyncio.run(
            _run_operator_qualified_profile(
                "tier_alpha_adrb2_smoke_test",
                invalid_request,
            )
        )
def test_systemd_dispatch_unit_polls_docking_ledger() -> None:
    unit = Path("deploy/systemd/micf-api-docking-dispatch.service").read_text(encoding="utf-8")
    env_example = Path("deploy/systemd/api-docking-dispatch.env.example").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/micf/api-docking-dispatch.env" in unit
    assert "tools/run_api_docking_dispatch_worker.py" in unit
    assert "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS" in unit
    assert "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in env_example
    assert "API_VALIDATED_RUNNER_ENABLED=0" in env_example
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH=" in env_example
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256=" in env_example


def test_systemd_worker_unit_is_fail_closed_and_writes_only_data_dir() -> None:
    unit = Path("deploy/systemd/micf-api-worker.service").read_text(encoding="utf-8")
    env_example = Path("deploy/systemd/api-worker.env.example").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/micf/api-worker.env" in unit
    assert "tools/run_api_simulation_worker.py" in unit
    assert "--heartbeat-interval-seconds ${API_WORKER_HEARTBEAT_INTERVAL_SECONDS}" in unit
    assert "Restart=always" in unit
    assert "ProtectSystem=strict" in unit
    assert "ReadWritePaths=/var/lib/micf" in unit

    assert "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in env_example
    assert "API_VALIDATED_RUNNER_ENABLED=0" in env_example
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH=" in env_example
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256=" in env_example
    assert "API_VALIDATED_RUNNER_PROFILES_PATH=/opt/micf/config/api_validated_runner_profiles" in env_example
    assert "API_RESULT_MANIFEST_SIGNING_KEY=replace-with-operator-managed-secret" in env_example
    assert "PRODUCT_API_HOSTED_EXPOSURE_APPROVED=0" in env_example
    assert "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=0" in env_example
    assert "DOCKING_PRIVATE_PAYLOAD_KEYS" not in env_example


def test_systemd_api_server_unit_is_fail_closed_and_matches_product_env_contract() -> None:
    unit = Path("deploy/systemd/micf-api-server.service").read_text(encoding="utf-8")
    env_example = Path("deploy/systemd/api-server.env.example").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/micf/api-server.env" in unit
    assert "-m uvicorn api.main:app --host ${API_HOST} --port ${API_PORT}" in unit
    assert "Restart=always" in unit
    assert "ProtectSystem=strict" in unit
    assert "ReadWritePaths=/var/lib/micf" in unit
    assert "NoNewPrivileges=true" in unit

    assert "PRODUCT_API_AUTH_REQUIRED=1" in env_example
    assert "PRODUCT_API_TOKEN=replace-with-operator-managed-token" in env_example
    assert "PRODUCT_API_AUDIT_LOG_PATH=/var/lib/micf/product_audit_log.jsonl" in env_example
    assert "PRODUCT_API_HOSTED_EXPOSURE_APPROVED=0" in env_example
    assert "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=0" in env_example
    assert "DOCKING_PRIVATE_PAYLOAD_KEYS=replace-with-operator-managed-private-payload-keyring" in env_example
    assert "DOCKING_PRIVATE_PAYLOAD_DIR=/var/lib/micf/private_payloads" in env_example
    assert "API_INLINE_WORKER_ENABLED=0" in env_example
    assert "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in env_example
    assert "API_VALIDATED_RUNNER_ENABLED=0" in env_example
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH=" in env_example
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256=" in env_example
    assert "API_RESULT_MANIFEST_SIGNING_KEY=replace-with-operator-managed-secret" in env_example
    assert "RESULTS_STORAGE_PATH=/var/lib/micf/results" in env_example


def test_product_dockerfile_contains_worker_entrypoint_assets() -> None:
    dockerfile = Path("Dockerfile.product").read_text(encoding="utf-8")

    assert "COPY api ./api" in dockerfile
    assert "COPY tools ./tools" in dockerfile
    assert "COPY config ./config" in dockerfile
    assert "COPY rust_engine ./rust_engine" in dockerfile
    assert "requirements-product-rocm.txt" in dockerfile
    assert "tools/build_rust_hip_engine.py --output /app" in dockerfile
    assert "chmod -R a+rwX logs runs" in dockerfile
    assert "FORCE_RUST_HIP=1" in dockerfile
    assert "API_VALIDATED_RUNNER_ENABLED=0" in dockerfile
    assert 'CMD ["uvicorn", "api.main:app"' in dockerfile


def test_model_registry_scripts_are_signed_artifact_based() -> None:
    upload = Path("deploy/upload_model.py").read_text(encoding="utf-8")
    download = Path("deploy/download_model.py").read_text(encoding="utf-8")
    rollback = Path("deploy/rollback_model.py").read_text(encoding="utf-8")
    pipeline = Path("deploy/deploy_pipeline.sh").read_text(encoding="utf-8")
    runbook = Path("deploy/product_rollback_runbook.md").read_text(encoding="utf-8")

    assert "publish_model_artifact" in upload
    assert "MODEL_REGISTRY_SIGNING_KEY" in upload
    assert "download_model_artifact" in download
    assert "rollback_model_version" in rollback
    assert "python3 deploy/upload_model.py" in pipeline
    assert "python3 deploy/download_model.py" in pipeline
    assert "--version_or_stage current" in pipeline
    assert "deploy/rollback_model.py" in runbook


def test_product_rollout_plan_is_approval_gated_and_documented() -> None:
    rollout = Path("deploy/product_rollout.py").read_text(encoding="utf-8")
    runbook = Path("deploy/product_rollout_runbook.md").read_text(encoding="utf-8")

    assert "APPROVE_PRODUCT_ROLLOUT" in rollout
    assert "blocked_approval_required" in rollout
    assert '"docker", "build"' in rollout
    assert "kubectl" in rollout
    assert '"rollout"' in rollout and '"status"' in rollout
    assert "mutates_external_state" in rollout

    assert "deploy/product_rollout.py" in runbook
    assert "--execute" in runbook
    assert "previous image digest" in runbook


def test_product_release_bundle_links_operator_policy_and_evidence() -> None:
    bundle = Path("deploy/product_release_bundle.py").read_text(encoding="utf-8")

    assert "product_release_bundle_manifest_v1" in bundle
    assert "release_bundle_ready_for_operator_review" in bundle
    assert "APPROVE_PRODUCT_ROLLOUT" in bundle
    assert "APPROVE_HOSTED_PRODUCT_API_EXPOSURE" in bundle
    assert "runs/product_rollout_plan_current.json" in bundle
    assert "runs/alert_delivery_smoke_current.json" in bundle
    assert "runs/product_security_deployment_contract_current.json" in bundle
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in bundle
    assert "product_full_commercial_blocker_evidence_matrix_recorded" in bundle
    assert "external_state_mutation_allowed" in bundle


def test_k8s_manifests_define_api_worker_shared_queue_rollout() -> None:
    k8s_dir = Path("deploy/k8s")
    kustomization = (k8s_dir / "kustomization.yaml").read_text(encoding="utf-8")
    configmap = (k8s_dir / "configmap.yaml").read_text(encoding="utf-8")
    api_deployment = (k8s_dir / "api-deployment.yaml").read_text(encoding="utf-8")
    worker_deployment = (k8s_dir / "worker-deployment.yaml").read_text(encoding="utf-8")
    pvc = (k8s_dir / "pvc.yaml").read_text(encoding="utf-8")
    secret_example = (k8s_dir / "secret.example.yaml").read_text(encoding="utf-8")

    for resource in (
        "namespace.yaml",
        "pvc.yaml",
        "configmap.yaml",
        "api-deployment.yaml",
        "worker-deployment.yaml",
        "service.yaml",
    ):
        assert f"- {resource}" in kustomization
    assert "- secret.example.yaml" not in kustomization
    assert "secret.example.yaml is a template" in kustomization

    assert 'API_INLINE_WORKER_ENABLED: "0"' in configmap
    assert 'API_VALIDATED_RUNNER_ENABLED: "0"' in configmap
    assert 'API_VALIDATED_RUNNER_PROFILES_PATH: "/app/config/api_validated_runner_profiles"' in configmap
    assert 'API_JOB_STORE_PATH: "/data/api_jobs.sqlite3"' in configmap
    assert 'RESULTS_STORAGE_PATH: "/data/results"' in configmap
    assert 'DOCKING_PRIVATE_PAYLOAD_DIR: "/data/private_payloads"' in configmap
    assert 'PRODUCT_API_AUDIT_LOG_PATH: "/data/results/product_audit_log.jsonl"' in configmap
    assert 'PRODUCT_API_SECURITY_LEDGER_PATH: "/data/results/product_security.sqlite3"' in configmap
    assert "PRODUCT_API_HOSTED_EXPOSURE_APPROVED: \"0\"" in configmap
    assert "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED: \"0\"" in configmap
    assert "API_RESULT_MANIFEST_SIGNING_KEY" in secret_example
    assert "PRODUCT_API_TOKEN" in secret_example
    assert "DOCKING_PRIVATE_PAYLOAD_KEYS" in secret_example

    assert "name: micf-api-server" in api_deployment
    assert "uvicorn" in api_deployment
    assert "mountPath: /data" in api_deployment
    assert "claimName: micf-product-results" in api_deployment
    assert "path: /metrics" in api_deployment

    dispatch_deployment = (k8s_dir / "dispatch-deployment.yaml").read_text(encoding="utf-8")

    assert "name: micf-api-worker" in worker_deployment
    assert "python3 tools/run_api_simulation_worker.py" in worker_deployment
    assert "name: micf-api-docking-dispatch" in dispatch_deployment
    assert "run_api_docking_dispatch_worker.py" in dispatch_deployment
    assert "dispatch-deployment.yaml" in kustomization
    assert "--heartbeat-interval-seconds ${API_WORKER_HEARTBEAT_INTERVAL_SECONDS}" in worker_deployment
    assert "mountPath: /data" in worker_deployment
    assert "claimName: micf-product-results" in worker_deployment

    assert "ReadWriteOnce" in pvc
    assert "storage: 20Gi" in pvc


def test_k8s_explicit_runner_disable_and_role_scoped_secrets() -> None:
    config = yaml.safe_load(Path("deploy/k8s/configmap.yaml").read_text(encoding="utf-8"))
    assert config["data"]["API_VALIDATED_RUNNER_ENABLED"] == "0"

    for manifest_path in (
        "deploy/k8s/api-deployment.yaml",
        "deploy/k8s/worker-deployment.yaml",
        "deploy/k8s/dispatch-deployment.yaml",
    ):
        deployment = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
        pod_spec = deployment["spec"]["template"]["spec"]
        container = pod_spec["containers"][0]
        env_from = container["envFrom"]
        assert [next(iter(source)) for source in env_from] == ["configMapRef"]

        explicit_env = {
            entry["name"]: entry
            for entry in container.get("env", [])
        }
        assert explicit_env["API_VALIDATED_RUNNER_ENABLED"]["value"] == "0"

        secret_names = {
            name
            for name, entry in explicit_env.items()
            if "secretKeyRef" in (entry.get("valueFrom") or {})
        }
        expected_secrets = {
            "deploy/k8s/api-deployment.yaml": {
                "PRODUCT_API_TOKEN",
                "API_RESULT_MANIFEST_SIGNING_KEY",
                "DOCKING_PRIVATE_PAYLOAD_KEYS",
            },
            "deploy/k8s/worker-deployment.yaml": {
                "API_RESULT_MANIFEST_SIGNING_KEY",
            },
            "deploy/k8s/dispatch-deployment.yaml": set(),
        }
        assert secret_names == expected_secrets[manifest_path]
        assert "DOCKING_PRIVATE_PAYLOAD_KEYS" not in secret_names or (
            manifest_path == "deploy/k8s/api-deployment.yaml"
        )

        assert pod_spec["securityContext"]["seccompProfile"]["type"] == (
            "RuntimeDefault"
        )
        security_context = container["securityContext"]
        assert security_context["allowPrivilegeEscalation"] is False
        assert security_context["capabilities"]["drop"] == ["ALL"]
        assert security_context.get("privileged") is not True
        assert "SYS_ADMIN" not in security_context["capabilities"].get("add", [])


def test_product_api_worker_ci_workflow_runs_contract_checks() -> None:
    pull_request_workflow = Path(".github/workflows/product-api-worker.yml").read_text(
        encoding="utf-8"
    )
    trusted_workflow = Path(
        ".github/workflows/product-api-worker-trusted.yml"
    ).read_text(encoding="utf-8")
    workflow = "\n".join((pull_request_workflow, trusted_workflow))

    assert "api-worker-contract:" in pull_request_workflow
    assert "api-worker-contract-trusted:" not in pull_request_workflow
    assert "if: ${{ github.event_name == 'pull_request' }}" in pull_request_workflow
    assert "runs-on: ubuntu-latest" in pull_request_workflow
    assert "self-hosted" not in pull_request_workflow
    assert "python -m pytest --confcutdir=tests/unit -q" in pull_request_workflow
    assert "python -m pytest --confcutdir=tests/mobile -c pytest-mobile.ini -q" in pull_request_workflow
    assert "pull_request:" not in trusted_workflow
    assert "api-worker-contract-trusted:" in trusted_workflow
    assert "runs-on: [self-hosted, linux]" in trusted_workflow
    assert "runner_labels_json" not in trusted_workflow
    assert "github.ref == 'refs/heads/main'" in trusted_workflow
    assert "Recover stale product image smoke workspace artifacts" not in workflow
    assert "sudo" not in workflow
    assert "clean: false" not in workflow
    assert workflow.count("persist-credentials: false") == 2
    assert workflow.count("clean: true") == 2
    assert "Prepare ephemeral API artifact root" in trusted_workflow
    assert "monitoring/**" in workflow
    assert "viewer/**" in workflow
    assert "tests/unit/test_deploy_model_registry.py" in workflow
    assert "tests/unit/test_product_release_bundle.py" in workflow
    assert "tests/unit/test_product_rollout.py" in workflow
    assert "tests/unit/test_smoke_alert_delivery.py" in workflow
    assert "tests/unit/test_viewer_self_hosted_assets.py" in workflow
    assert "python3 -m py_compile" in workflow
    assert "api/security.py" in workflow
    assert "api/validated_runner.py" in workflow
    assert "tools/product/validate_api_runner_profiles.py" in workflow
    assert "Validate API runner profiles" in workflow
    assert "tests/unit/test_api_job_store.py" in workflow
    assert "tests/unit/test_api_validated_runner_adapter.py" in workflow
    assert "tests/unit/test_api_worker_deploy_artifacts.py" in workflow
    assert "tests/unit/test_api_security_middleware.py" in workflow
    assert "tools/run_api_simulation_worker.py" in workflow
    assert "tools/smoke_alert_delivery.py" in workflow
    assert "deploy/product_release_bundle.py" in workflow
    assert "deploy/product_rollout.py" in workflow
    assert "tools/build_viewer_asset_base_url_decision.py" in workflow
    assert "tools/product/build_self_hosted_license_distribution_audit.py" in workflow
    assert "tests/unit/test_build_viewer_asset_base_url_decision.py" in workflow
    assert "tests/unit/test_build_self_hosted_license_distribution_audit.py" in workflow
    assert "Refresh release bundle local decision artifacts" in workflow
    assert "Smoke alert delivery CLI with localhost receiver" in workflow
    assert "--once" in workflow


def test_monitoring_alerts_are_wired_to_runtime_metrics_and_paged_webhook() -> None:
    prometheus = Path("monitoring/prometheus.yml").read_text(encoding="utf-8")
    alertmanager = Path("monitoring/alertmanager.yml").read_text(encoding="utf-8")
    alerts = Path("monitoring/product_api_alerts.yml").read_text(encoding="utf-8")
    readme = Path("monitoring/README.md").read_text(encoding="utf-8")

    assert "product_api_alerts.yml" in prometheus
    assert "job_name: 'micf-api'" in prometheus
    assert "metrics_path: '/metrics'" in prometheus

    assert "YOUR_SLACK_WEBHOOK_URL_FOR_ALERTMANAGER" not in alertmanager
    assert "operator-paged-webhook" in alertmanager
    assert "url_file: '/etc/alertmanager/paged-webhook-url'" in alertmanager
    assert "send_resolved: true" in alertmanager

    for alert_name in (
        "MicfApiMetricsTargetDown",
        "MicfApiAuditWriteFailures",
        "MicfApiHighServerErrorRate",
        "MicfApiAuthFailureSpike",
        "MicfApiRateLimitSpike",
    ):
        assert f"alert: {alert_name}" in alerts

    assert "betelgeuze_product_http_requests_total" in alerts
    assert "betelgeuze_product_blocked_requests_total" in alerts
    assert "betelgeuze_product_audit_write_failures_total" in alerts
    assert "/etc/alertmanager/paged-webhook-url" in readme
    assert "Keep the webhook URL out of git" in readme
    assert "tools/smoke_alert_delivery.py" in readme
    assert "--local-receiver-smoke" in readme


def test_validated_runner_profile_examples_are_disabled_by_default() -> None:
    readme = Path("config/api_validated_runner_profiles/README.md").read_text(encoding="utf-8")
    example = Path("config/api_validated_runner_profiles/backmapping_scoring.example.json").read_text(
        encoding="utf-8"
    )

    assert "API_VALIDATED_RUNNER_ENABLED=1" in readme
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH" in readme
    assert "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256" in readme
    assert "independently from the receipt" in readme
    assert "longer than 24 hours" in readme
    assert "production_readiness" in readme
    assert "runner_script_sha256" in readme
    assert "fake_result_emission_forbidden" in readme
    assert "product/validate_api_runner_profiles.py" in readme
    assert '"enabled": false' in example
    assert "tools/run_ligand_backmapping_scoring.py" in example
