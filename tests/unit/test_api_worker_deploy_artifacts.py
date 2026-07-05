from __future__ import annotations

from pathlib import Path


def test_product_compose_runs_api_and_worker_with_shared_queue() -> None:
    compose = Path("deploy/docker-compose.product.yml").read_text(encoding="utf-8")

    assert "api-server:" in compose
    assert "api-worker:" in compose
    assert "api-docking-dispatch:" in compose
    assert "tools/run_api_docking_dispatch_worker.py" in compose
    assert "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS" in compose
    assert 'API_INLINE_WORKER_ENABLED: "0"' in compose
    assert 'API_VALIDATED_RUNNER_ENABLED: "${API_VALIDATED_RUNNER_ENABLED:-0}"' in compose
    assert "API_VALIDATED_RUNNER_PROFILES_PATH" in compose
    assert 'API_JOB_STORE_PATH: "/data/api_jobs.sqlite3"' in compose
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
    assert 'PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED: "${PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED:-1}"' in compose


def test_systemd_dispatch_unit_polls_docking_ledger() -> None:
    unit = Path("deploy/systemd/micf-api-docking-dispatch.service").read_text(encoding="utf-8")
    env_example = Path("deploy/systemd/api-docking-dispatch.env.example").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/micf/api-docking-dispatch.env" in unit
    assert "tools/run_api_docking_dispatch_worker.py" in unit
    assert "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS" in unit
    assert "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in env_example
    assert "API_VALIDATED_RUNNER_ENABLED=0" in env_example


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
    assert "API_VALIDATED_RUNNER_PROFILES_PATH=/opt/micf/config/api_validated_runner_profiles" in env_example
    assert "API_RESULT_MANIFEST_SIGNING_KEY=replace-with-operator-managed-secret" in env_example
    assert "PRODUCT_API_HOSTED_EXPOSURE_APPROVED=0" in env_example
    assert "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1" in env_example


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
    assert "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1" in env_example
    assert "API_INLINE_WORKER_ENABLED=0" in env_example
    assert "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in env_example
    assert "API_VALIDATED_RUNNER_ENABLED=0" in env_example
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
        "secret.example.yaml",
        "api-deployment.yaml",
        "worker-deployment.yaml",
        "service.yaml",
    ):
        assert f"- {resource}" in kustomization

    assert 'API_INLINE_WORKER_ENABLED: "0"' in configmap
    assert 'API_VALIDATED_RUNNER_ENABLED: "0"' in configmap
    assert 'API_VALIDATED_RUNNER_PROFILES_PATH: "/app/config/api_validated_runner_profiles"' in configmap
    assert 'API_JOB_STORE_PATH: "/data/api_jobs.sqlite3"' in configmap
    assert "PRODUCT_API_HOSTED_EXPOSURE_APPROVED: \"0\"" in configmap
    assert "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED: \"1\"" in configmap
    assert "API_RESULT_MANIFEST_SIGNING_KEY" in secret_example
    assert "PRODUCT_API_TOKEN" in secret_example

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


def test_product_api_worker_ci_workflow_runs_contract_checks() -> None:
    workflow = Path(".github/workflows/product-api-worker.yml").read_text(encoding="utf-8")

    assert "api-worker-contract:" in workflow
    assert "runner_labels_json:" in workflow
    assert "self-hosted" in workflow
    assert "Default self-hosted avoids GitHub-hosted minutes" in workflow
    assert "fromJSON(inputs.runner_labels_json || '[\"self-hosted\",\"linux\"]')" in workflow
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
    assert "production_readiness" in readme
    assert "runner_script_sha256" in readme
    assert "fake_result_emission_forbidden" in readme
    assert "product/validate_api_runner_profiles.py" in readme
    assert '"enabled": false' in example
    assert "tools/run_ligand_backmapping_scoring.py" in example
