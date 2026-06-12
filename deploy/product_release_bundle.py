#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_ARTIFACTS = {
    "security_contract": "runs/product_security_deployment_contract_current.json",
    "rollout_plan": "runs/product_rollout_plan_current.json",
    "alert_delivery_smoke": "runs/alert_delivery_smoke_current.json",
    "runner_profile_work_order": "runs/api_runner_profile_enablement_work_order_current.json",
    "api_runner_profile_promotion_readiness": "runs/api_runner_profile_promotion_readiness_current.json",
    "api_runner_profile_promotion_operator_template": "runs/api_runner_profile_promotion_operator_template_current.csv",
    "api_runner_profile_promotion_operator_receipt": "runs/api_runner_profile_promotion_operator_receipt_current.json",
    "rollback_runbook": "deploy/product_rollback_runbook.md",
    "rollout_runbook": "deploy/product_rollout_runbook.md",
    "dockerfile": "Dockerfile.product",
    "compose": "deploy/docker-compose.product.yml",
    "k8s_kustomization": "deploy/k8s/kustomization.yaml",
    "systemd_api_server_unit": "deploy/systemd/micf-api-server.service",
    "systemd_api_server_env_example": "deploy/systemd/api-server.env.example",
    "systemd_api_worker_unit": "deploy/systemd/micf-api-worker.service",
    "systemd_api_worker_env_example": "deploy/systemd/api-worker.env.example",
    "viewer_vendor_manifest": "viewer/vendor/manifest.json",
    "viewer_vendor_notices": "viewer/vendor/THIRD_PARTY_NOTICES.md",
    "viewer_asset_base_url_decision": "runs/viewer_asset_base_url_decision_current.json",
    "self_hosted_license_distribution_audit": "runs/self_hosted_license_distribution_audit_current.json",
    "third_party_license_review_gate": "runs/third_party_license_review_gate_current.json",
    "product_rollout_execution_readiness": "runs/product_rollout_execution_readiness_current.json",
    "product_launch_r4_preflight": "runs/product_launch_r4_preflight_current.json",
    "engine_refinement_claim_promotion_action_board": "runs/engine_refinement_claim_promotion_action_board_current.csv",
    "engine_refinement_claim_evidence_receipt": "runs/engine_refinement_claim_evidence_receipt_current.json",
    "product_goal_completion_audit": "runs/product_goal_completion_audit_current.json",
}
APPROVAL_TOKENS = [
    "APPROVE_PRODUCT_ROLLOUT",
    "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
    "MODEL_REGISTRY_SIGNING_KEY",
    "API_RESULT_MANIFEST_SIGNING_KEY",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _artifact_row(name: str, path_text: str) -> dict[str, Any]:
    path = _resolve(path_text)
    return {
        "name": name,
        "path": path_text,
        "present": path.is_file(),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
    }


def _runner_enablement_work_order_ready(runner: dict[str, Any]) -> bool:
    if runner.get("status") != "ready":
        return False
    enabled_count = int(runner.get("enabled_profile_count") or 0)
    if enabled_count == 0:
        return True
    rows = runner.get("rows", [])
    if not isinstance(rows, list):
        return False
    enabled_rows = [row for row in rows if isinstance(row, dict) and row.get("enabled") is True]
    if len(enabled_rows) != enabled_count:
        return False
    return all(bool(row.get("runner_allowlisted")) and bool(row.get("runner_exists")) for row in enabled_rows)


def _status_checks(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    security = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["security_contract"])))
    rollout = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["rollout_plan"])))
    alert = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["alert_delivery_smoke"])))
    runner = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["runner_profile_work_order"])))
    runner_promotion = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["api_runner_profile_promotion_readiness"])))
    runner_promotion_receipt = _summary(
        _read_json(_resolve(DEFAULT_ARTIFACTS["api_runner_profile_promotion_operator_receipt"]))
    )
    viewer_asset_base = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["viewer_asset_base_url_decision"])))
    license_audit = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["self_hosted_license_distribution_audit"])))
    third_party_license_review = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["third_party_license_review_gate"])))
    rollout_execution_readiness = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["product_rollout_execution_readiness"])))
    launch_r4_preflight = _summary(_read_json(_resolve(DEFAULT_ARTIFACTS["product_launch_r4_preflight"])))
    engine_action_board_text = _read_text(_resolve(DEFAULT_ARTIFACTS["engine_refinement_claim_promotion_action_board"]))
    engine_claim_evidence_receipt = _summary(
        _read_json(_resolve(DEFAULT_ARTIFACTS["engine_refinement_claim_evidence_receipt"]))
    )
    goal_audit_payload = _read_json(_resolve(DEFAULT_ARTIFACTS["product_goal_completion_audit"]))
    goal_audit = _summary(goal_audit_payload)
    goal_audit_rows = goal_audit_payload.get("rows") if isinstance(goal_audit_payload.get("rows"), list) else []
    engine_claim_row = next(
        (
            row
            for row in goal_audit_rows
            if isinstance(row, dict)
            and row.get("requirement_id") == "R9_engine_refinement_claim_promotion"
        ),
        {},
    )
    viewer_vendor = _read_json(_resolve(DEFAULT_ARTIFACTS["viewer_vendor_manifest"]))
    systemd_api_server_unit = _read_text(_resolve(DEFAULT_ARTIFACTS["systemd_api_server_unit"]))
    systemd_api_server_env = _read_text(_resolve(DEFAULT_ARTIFACTS["systemd_api_server_env_example"]))
    systemd_api_worker_unit = _read_text(_resolve(DEFAULT_ARTIFACTS["systemd_api_worker_unit"]))
    systemd_api_worker_env = _read_text(_resolve(DEFAULT_ARTIFACTS["systemd_api_worker_env_example"]))
    runner_promotion_template = _read_text(_resolve(DEFAULT_ARTIFACTS["api_runner_profile_promotion_operator_template"]))
    viewer_assets = viewer_vendor.get("assets") if isinstance(viewer_vendor.get("assets"), list) else []
    viewer_assets_ready = bool(viewer_assets)
    viewer_notice_path_text = str(viewer_vendor.get("third_party_notice_path", ""))
    viewer_notice_path = _resolve(viewer_notice_path_text) if viewer_notice_path_text else Path("")
    viewer_notice_text = viewer_notice_path.read_text(encoding="utf-8") if viewer_notice_path.is_file() else ""
    viewer_license_ready = bool(viewer_assets) and bool(viewer_notice_text)
    for row in viewer_assets:
        if not isinstance(row, dict):
            viewer_assets_ready = False
            viewer_license_ready = False
            continue
        asset_path = _resolve(str(row.get("path", "")))
        viewer_assets_ready = (
            viewer_assets_ready
            and asset_path.is_file()
            and asset_path.stat().st_size == int(row.get("size_bytes") or -1)
            and _sha256(asset_path) == str(row.get("sha256", ""))
        )
        package = str(row.get("package", ""))
        license_id = str(row.get("license_id", ""))
        license_source_url = str(row.get("license_source_url", ""))
        viewer_license_ready = (
            viewer_license_ready
            and bool(package)
            and bool(license_id)
            and license_source_url.startswith("https://")
            and package in viewer_notice_text
            and license_id in viewer_notice_text
            and license_source_url in viewer_notice_text
        )
    checks = [
        {
            "check": "required_artifacts_present",
            "passed": all(row["present"] and row["sha256"] for row in artifacts.values()),
            "observed": ",".join(name for name, row in artifacts.items() if not row["present"]) or "all_present",
        },
        {
            "check": "security_contract_ready",
            "passed": security.get("security_deployment_ready") is True,
            "observed": str(security.get("status", "")),
        },
        {
            "check": "rollout_plan_dry_run_approval_gated",
            "passed": (
                rollout.get("status") == "planned"
                and rollout.get("dry_run") is True
                and rollout.get("approval_token_required") == "APPROVE_PRODUCT_ROLLOUT"
            ),
            "observed": f"status={rollout.get('status')};dry_run={rollout.get('dry_run')};token={rollout.get('approval_token_required')}",
        },
        {
            "check": "alert_delivery_closed_loop_smoke_pass",
            "passed": alert.get("status") == "pass" and int(alert.get("received_alert_count") or 0) == 1,
            "observed": f"status={alert.get('status')};received_alert_count={alert.get('received_alert_count')}",
        },
        {
            "check": "runner_profile_enablement_work_order_ready",
            "passed": _runner_enablement_work_order_ready(runner),
            "observed": f"status={runner.get('status')};enabled_profile_count={runner.get('enabled_profile_count')}",
        },
        {
            "check": "api_runner_profile_promotion_readiness_recorded",
            "passed": (
                runner_promotion.get("status")
                in {"blocked_api_runner_profile_promotion_readiness", "api_runner_profile_promotion_ready"}
                and runner_promotion.get("profile_enabled_by_this_tool") is False
                and runner_promotion.get("runner_executed") is False
                and runner_promotion.get("external_state_mutated") is False
            ),
            "observed": (
                f"status={runner_promotion.get('status')};"
                f"promotion_ready_count={runner_promotion.get('promotion_ready_count')};"
                f"blocked_profile_count={runner_promotion.get('blocked_profile_count')}"
            ),
        },
        {
            "check": "api_runner_profile_promotion_operator_template_recorded",
            "passed": (
                runner_promotion_template.startswith("profile_id,operator_decision,approval_token,")
                and "APPROVE_API_RUNNER_PROFILE_PROMOTION" in str(runner_promotion.get("approval_token_required"))
                and str(runner_promotion.get("operator_template_csv", ""))
                == DEFAULT_ARTIFACTS["api_runner_profile_promotion_operator_template"]
            ),
            "observed": (
                f"template_path={DEFAULT_ARTIFACTS['api_runner_profile_promotion_operator_template']};"
                f"readiness_template_path={runner_promotion.get('operator_template_csv')}"
            ),
        },
        {
            "check": "api_runner_profile_promotion_operator_receipt_recorded",
            "passed": (
                runner_promotion_receipt.get("status")
                in {
                    "blocked_api_runner_profile_promotion_operator_receipt",
                    "api_runner_profile_promotion_operator_receipt_ready",
                }
                and runner_promotion_receipt.get("profile_enabled_by_this_tool") is False
                and runner_promotion_receipt.get("runner_executed") is False
                and runner_promotion_receipt.get("external_state_mutated") is False
                and runner_promotion_receipt.get("approval_token_required") == "APPROVE_API_RUNNER_PROFILE_PROMOTION"
                and runner_promotion_receipt.get("operator_template_csv")
                == DEFAULT_ARTIFACTS["api_runner_profile_promotion_operator_template"]
                and runner_promotion_receipt.get("readiness_artifact")
                == DEFAULT_ARTIFACTS["api_runner_profile_promotion_readiness"]
                and int(runner_promotion_receipt.get("profile_count") or 0)
                == int(runner_promotion.get("profile_count") or 0)
                and int(runner_promotion_receipt.get("receipt_row_count") or 0)
                >= int(runner_promotion.get("profile_count") or 0)
                and int(runner_promotion_receipt.get("missing_profile_count") or 0) == 0
            ),
            "observed": (
                f"receipt_status={runner_promotion_receipt.get('status')};"
                f"receipt_ready={runner_promotion_receipt.get('operator_receipt_ready')};"
                f"blocked_row_count={runner_promotion_receipt.get('blocked_row_count')};"
                f"profile_count={runner_promotion_receipt.get('profile_count')};"
                f"receipt_row_count={runner_promotion_receipt.get('receipt_row_count')}"
            ),
        },
        {
            "check": "viewer_vendor_assets_pinned",
            "passed": viewer_vendor.get("manifest_version") == "viewer_vendor_assets_v1" and viewer_assets_ready,
            "observed": f"manifest={viewer_vendor.get('manifest_version')};asset_count={len(viewer_assets)}",
        },
        {
            "check": "viewer_vendor_license_notices_recorded",
            "passed": (
                viewer_vendor.get("license_review_status") == "recorded_not_legal_approved"
                and viewer_license_ready
            ),
            "observed": (
                f"notice_path={viewer_notice_path_text};"
                f"license_review_status={viewer_vendor.get('license_review_status')}"
            ),
        },
        {
            "check": "viewer_asset_base_url_decision_recorded",
            "passed": (
                viewer_asset_base.get("status") == "viewer_asset_base_url_decision_pass"
                and viewer_asset_base.get("same_directory_or_subpath_bundle_supported") is True
                and viewer_asset_base.get("asset_base_url_override_required_for_standard_bundle") is False
            ),
            "observed": (
                f"status={viewer_asset_base.get('status')};"
                f"standard_override_required={viewer_asset_base.get('asset_base_url_override_required_for_standard_bundle')}"
            ),
        },
        {
            "check": "self_hosted_license_distribution_audit_recorded",
            "passed": (
                license_audit.get("status") == "self_hosted_license_distribution_audit_recorded"
                and int(license_audit.get("hard_blocker_count") if license_audit.get("hard_blocker_count") is not None else -1) == 0
                and license_audit.get("legal_advice_provided") is False
            ),
            "observed": (
                f"status={license_audit.get('status')};"
                f"hard_blocker_count={license_audit.get('hard_blocker_count')};"
                f"operator_review_item_count={license_audit.get('operator_review_item_count')};"
                f"third_party_review_gate={license_audit.get('third_party_license_review_gate_status')};"
                f"third_party_review_gate_blockers={license_audit.get('third_party_license_review_gate_blocker_count')}"
            ),
        },
        {
            "check": "third_party_license_review_gate_recorded",
            "passed": (
                third_party_license_review.get("status")
                in {"blocked_third_party_license_review_gate", "third_party_license_review_gate_ready"}
                and third_party_license_review.get("legal_advice_provided") is False
                and third_party_license_review.get("asset_modified") is False
                and third_party_license_review.get("external_state_mutated") is False
            ),
            "observed": (
                f"status={third_party_license_review.get('status')};"
                f"expected_review_asset_count={third_party_license_review.get('expected_review_asset_count')};"
                f"blocker_count={third_party_license_review.get('blocker_count')}"
            ),
        },
        {
            "check": "systemd_api_server_worker_units_recorded",
            "passed": (
                "uvicorn api.main:app" in systemd_api_server_unit
                and "tools/run_api_simulation_worker.py" in systemd_api_worker_unit
                and "ProtectSystem=strict" in systemd_api_server_unit
                and "ProtectSystem=strict" in systemd_api_worker_unit
                and "ReadWritePaths=/var/lib/micf" in systemd_api_server_unit
                and "ReadWritePaths=/var/lib/micf" in systemd_api_worker_unit
                and "PRODUCT_API_AUTH_REQUIRED=1" in systemd_api_server_env
                and "API_INLINE_WORKER_ENABLED=0" in systemd_api_server_env
                and "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in systemd_api_server_env
                and "API_JOB_STORE_PATH=/var/lib/micf/api_jobs.sqlite3" in systemd_api_worker_env
            ),
            "observed": "api_server_unit=deploy/systemd/micf-api-server.service;api_worker_unit=deploy/systemd/micf-api-worker.service",
        },
        {
            "check": "product_rollout_execution_readiness_recorded",
            "passed": (
                rollout_execution_readiness.get("status")
                in {"blocked_product_rollout_execution_readiness", "product_rollout_execution_readiness_ready"}
                and rollout_execution_readiness.get("rollout_executed") is False
                and rollout_execution_readiness.get("pager_provider_contacted") is False
                and rollout_execution_readiness.get("external_state_mutated") is False
            ),
            "observed": (
                f"status={rollout_execution_readiness.get('status')};"
                f"blocker_count={rollout_execution_readiness.get('blocker_count')};"
                f"operator_csv_present={rollout_execution_readiness.get('operator_csv_present')}"
            ),
        },
        {
            "check": "product_launch_r4_preflight_recorded",
            "passed": (
                launch_r4_preflight.get("status")
                in {"blocked_product_launch_r4_preflight", "product_launch_r4_preflight_ready"}
                and launch_r4_preflight.get("authorized_for_external_mutation") is False
                and launch_r4_preflight.get("launch_executed") is False
                and launch_r4_preflight.get("external_state_mutated") is False
                and isinstance(launch_r4_preflight.get("required_r4_fields"), list)
                and all(
                    field in launch_r4_preflight.get("required_r4_fields")
                    for field in ("target", "action", "impact", "risk", "rollback", "verification")
                )
            ),
            "observed": (
                f"status={launch_r4_preflight.get('status')};"
                f"blocker_count={launch_r4_preflight.get('blocker_count')};"
                f"authorized_for_external_mutation={launch_r4_preflight.get('authorized_for_external_mutation')};"
                f"launch_executed={launch_r4_preflight.get('launch_executed')}"
            ),
        },
        {
            "check": "engine_refinement_claim_promotion_action_board_recorded",
            "passed": (
                engine_action_board_text.startswith("blocker_id,current_status,required_evidence,")
                and engine_action_board_text.count("\n") >= 6
                and "public_benchmark_gate_not_ready" in engine_action_board_text
                and "external_structure_quality_parity_not_ready" in engine_action_board_text
                and "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE" in engine_action_board_text
                and DEFAULT_ARTIFACTS["engine_refinement_claim_promotion_action_board"]
                == str(launch_r4_preflight.get("engine_refinement_claim_promotion_action_board_csv", ""))
            ),
            "observed": (
                f"action_board_path={DEFAULT_ARTIFACTS['engine_refinement_claim_promotion_action_board']};"
                f"launch_preflight_action_board_path="
                f"{launch_r4_preflight.get('engine_refinement_claim_promotion_action_board_csv')};"
                f"line_count={engine_action_board_text.count(chr(10))}"
            ),
        },
        {
            "check": "engine_refinement_claim_evidence_receipt_recorded",
            "passed": (
                engine_claim_evidence_receipt.get("status")
                in {"blocked_engine_refinement_claim_evidence_receipt", "engine_refinement_claim_evidence_receipt_ready"}
                and int(engine_claim_evidence_receipt.get("required_blocker_count") or 0) == 6
                and int(engine_claim_evidence_receipt.get("receipt_row_count") or 0) >= 6
                and int(engine_claim_evidence_receipt.get("missing_required_blocker_count") or 0) == 0
                and engine_claim_evidence_receipt.get("external_state_mutated") is False
                and DEFAULT_ARTIFACTS["engine_refinement_claim_evidence_receipt"]
                == str(launch_r4_preflight.get("engine_refinement_claim_evidence_receipt_artifact", ""))
            ),
            "observed": (
                f"receipt_status={engine_claim_evidence_receipt.get('status')};"
                f"receipt_ready={engine_claim_evidence_receipt.get('claim_promotion_evidence_receipt_ready')};"
                f"blocked_row_count={engine_claim_evidence_receipt.get('blocked_row_count')};"
                f"blocker_count={engine_claim_evidence_receipt.get('blocker_count')};"
                f"launch_preflight_receipt_artifact="
                f"{launch_r4_preflight.get('engine_refinement_claim_evidence_receipt_artifact')}"
            ),
        },
        {
            "check": "product_goal_completion_audit_full_claim_boundary_recorded",
            "passed": (
                goal_audit.get("status") == "blocked_product_goal_completion_audit"
                and goal_audit.get("goal_complete") is False
                and goal_audit.get("engine_refinement_claim_promotion_ready") is False
                and int(goal_audit.get("engine_refinement_claim_promotion_blocker_count") or 0) >= 6
                and engine_claim_row.get("status") == "fail"
                and engine_claim_row.get("release_blocker") is True
                and engine_claim_row.get("blocker") == "engine_refinement_claim_promotion_not_ready"
            ),
            "observed": (
                f"goal_audit_status={goal_audit.get('status')};"
                f"goal_complete={goal_audit.get('goal_complete')};"
                f"engine_refinement_claim_promotion_ready="
                f"{goal_audit.get('engine_refinement_claim_promotion_ready')};"
                f"engine_refinement_claim_promotion_blocker_count="
                f"{goal_audit.get('engine_refinement_claim_promotion_blocker_count')};"
                f"r9_status={engine_claim_row.get('status')};"
                f"r9_release_blocker={engine_claim_row.get('release_blocker')}"
            ),
        },
    ]
    return checks


def build_release_bundle(*, release_id: str, artifact_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    artifact_paths = dict(DEFAULT_ARTIFACTS)
    artifact_paths.update(artifact_overrides or {})
    artifact_rows = {name: _artifact_row(name, path) for name, path in artifact_paths.items()}
    checks = _status_checks(artifact_rows)
    blocker_checks = [row for row in checks if not row["passed"]]
    status = "release_bundle_ready_for_operator_review" if not blocker_checks else "blocked_release_bundle"
    return {
        "bundle_version": "product_release_bundle_manifest_v1",
        "release_id": release_id,
        "status": status,
        "release_bundle_ready": not blocker_checks,
        "created_at_utc": _utc_now(),
        "artifact_count": len(artifact_rows),
        "check_count": len(checks),
        "pass_count": sum(1 for row in checks if row["passed"]),
        "blocker_count": len(blocker_checks),
        "artifacts": list(artifact_rows.values()),
        "checks": checks,
        "blockers": blocker_checks,
        "operator_promotion_policy": {
            "status": "operator_approval_required",
            "external_state_mutation_allowed": False,
            "approval_tokens_required": APPROVAL_TOKENS,
            "must_review_fields": ["target", "action", "impact", "risk", "rollback", "verification"],
            "required_before_execution": [
                "Review this release bundle manifest and artifact hashes.",
                "Confirm the rollout dry-run target image, registry, namespace, and command list.",
                "Provide APPROVE_PRODUCT_ROLLOUT only in the execution environment, not in git.",
                "Mount real pager webhook and hosted TLS/secret material in operator-managed storage.",
            ],
        },
        "claim_boundary": (
            "Product release bundle manifest only; links local evidence artifacts and approval policy. It does not "
            "build images, push containers, deploy services, approve hosted exposure, or run scientific profiles."
        ),
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    lines = [
        "# Product Release Bundle",
        "",
        f"- release_id: `{payload['release_id']}`",
        f"- status: `{payload['status']}`",
        f"- pass_count: `{payload['pass_count']}` / `{payload['check_count']}`",
        f"- promotion_policy: `{payload['operator_promotion_policy']['status']}`",
        "",
        "## Artifacts",
        "",
        "| name | present | sha256 | path |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["artifacts"]:
        lines.append(f"| `{row['name']}` | `{row['present']}` | `{row['sha256']}` | `{row['path']}` |")
    lines.extend(["", "## Checks", "", "| check | passed | observed |", "| --- | --- | --- |"])
    for row in payload["checks"]:
        lines.append(f"| `{row['check']}` | `{row['passed']}` | `{row['observed']}` |")
    lines.extend(
        [
            "",
            "## Approval Tokens",
            "",
            *[f"- `{token}`" for token in payload["operator_promotion_policy"]["approval_tokens_required"]],
            "",
            "## Claim Boundary",
            "",
            payload["claim_boundary"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build product release bundle manifest from local evidence artifacts.")
    parser.add_argument("--release-id", default=datetime.now(timezone.utc).strftime("product-%Y%m%dT%H%M%SZ"))
    parser.add_argument("--out-json", default="runs/product_release_bundle_current.json")
    parser.add_argument("--out-md", default="runs/product_release_bundle_current.md")
    args = parser.parse_args(argv)

    payload = build_release_bundle(release_id=args.release_id)
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload["status"] == "release_bundle_ready_for_operator_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
