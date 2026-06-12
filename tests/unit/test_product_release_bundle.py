from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from deploy import product_release_bundle as mod


def test_release_bundle_links_required_artifacts_and_policy() -> None:
    payload = mod.build_release_bundle(release_id="unit-release")

    assert payload["bundle_version"] == "product_release_bundle_manifest_v1"
    assert payload["status"] == "release_bundle_ready_for_operator_review"
    assert payload["release_bundle_ready"] is True
    assert payload["blocker_count"] == 0
    assert payload["operator_promotion_policy"]["status"] == "operator_approval_required"
    assert payload["operator_promotion_policy"]["external_state_mutation_allowed"] is False
    assert "APPROVE_PRODUCT_ROLLOUT" in payload["operator_promotion_policy"]["approval_tokens_required"]
    assert "APPROVE_HOSTED_PRODUCT_API_EXPOSURE" in payload["operator_promotion_policy"]["approval_tokens_required"]
    assert "target" in payload["operator_promotion_policy"]["must_review_fields"]

    artifacts = {row["name"]: row for row in payload["artifacts"]}
    assert artifacts["security_contract"]["present"] is True
    assert artifacts["rollout_plan"]["sha256"]
    assert artifacts["alert_delivery_smoke"]["sha256"]
    assert artifacts["runner_profile_work_order"]["sha256"]
    assert artifacts["api_runner_profile_promotion_readiness"]["sha256"]
    assert artifacts["api_runner_profile_promotion_operator_template"]["sha256"]
    assert artifacts["systemd_api_server_unit"]["sha256"]
    assert artifacts["systemd_api_server_env_example"]["sha256"]
    assert artifacts["systemd_api_worker_unit"]["sha256"]
    assert artifacts["systemd_api_worker_env_example"]["sha256"]
    assert artifacts["viewer_vendor_manifest"]["sha256"]
    assert artifacts["viewer_vendor_notices"]["sha256"]
    assert artifacts["viewer_asset_base_url_decision"]["sha256"]
    assert artifacts["self_hosted_license_distribution_audit"]["sha256"]
    assert artifacts["third_party_license_review_gate"]["sha256"]
    assert artifacts["product_rollout_execution_readiness"]["sha256"]
    assert artifacts["product_launch_r4_preflight"]["sha256"]
    assert artifacts["engine_refinement_claim_promotion_action_board"]["sha256"]
    assert artifacts["product_goal_completion_audit"]["sha256"]

    checks = {row["check"]: row for row in payload["checks"]}
    assert checks["security_contract_ready"]["passed"] is True
    assert checks["rollout_plan_dry_run_approval_gated"]["passed"] is True
    assert checks["alert_delivery_closed_loop_smoke_pass"]["passed"] is True
    assert checks["runner_profile_enablement_work_order_ready"]["passed"] is True
    assert checks["api_runner_profile_promotion_readiness_recorded"]["passed"] is True
    assert checks["api_runner_profile_promotion_operator_template_recorded"]["passed"] is True
    assert checks["viewer_vendor_assets_pinned"]["passed"] is True
    assert checks["viewer_vendor_license_notices_recorded"]["passed"] is True
    assert checks["viewer_asset_base_url_decision_recorded"]["passed"] is True
    assert checks["self_hosted_license_distribution_audit_recorded"]["passed"] is True
    assert checks["third_party_license_review_gate_recorded"]["passed"] is True
    assert checks["systemd_api_server_worker_units_recorded"]["passed"] is True
    assert checks["product_rollout_execution_readiness_recorded"]["passed"] is True
    assert checks["product_launch_r4_preflight_recorded"]["passed"] is True
    assert checks["engine_refinement_claim_promotion_action_board_recorded"]["passed"] is True
    assert checks["product_goal_completion_audit_full_claim_boundary_recorded"]["passed"] is True
    assert "r9_status=fail" in checks[
        "product_goal_completion_audit_full_claim_boundary_recorded"
    ]["observed"]


def test_release_bundle_blocks_missing_required_artifact() -> None:
    payload = mod.build_release_bundle(
        release_id="missing-artifact",
        artifact_overrides={"alert_delivery_smoke": "runs/does-not-exist-alert.json"},
    )

    assert payload["status"] == "blocked_release_bundle"
    assert payload["release_bundle_ready"] is False
    assert payload["blocker_count"] >= 1
    blockers = {row["check"]: row for row in payload["blockers"]}
    assert blockers["required_artifacts_present"]["passed"] is False
    assert "alert_delivery_smoke" in blockers["required_artifacts_present"]["observed"]


def test_release_bundle_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    out_json = tmp_path / "bundle.json"
    out_md = tmp_path / "bundle.md"

    result = subprocess.run(
        [
            sys.executable,
            "deploy/product_release_bundle.py",
            "--release-id",
            "cli-release",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["release_id"] == "cli-release"
    assert saved["status"] == "release_bundle_ready_for_operator_review"
    assert "# Product Release Bundle" in out_md.read_text(encoding="utf-8")
