#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE_BUNDLE_JSON = "runs/product_release_bundle_current.json"
DEFAULT_ROLLOUT_PLAN_JSON = "runs/product_rollout_plan_current.json"
DEFAULT_SECURITY_CONTRACT_JSON = "runs/product_security_deployment_contract_current.json"
DEFAULT_ALERT_SMOKE_JSON = "runs/alert_delivery_smoke_current.json"
DEFAULT_OPERATOR_INTAKE_CSV = "runs/product_rollout_execution_operator_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/product_rollout_execution_operator_template_current.csv"
DEFAULT_OUT_JSON = "runs/product_rollout_execution_readiness_current.json"
DEFAULT_OUT_CSV = "runs/product_rollout_execution_readiness_current.csv"
DEFAULT_OUT_MD = "runs/product_rollout_execution_readiness_current.md"

APPROVAL_TOKEN = "APPROVE_PRODUCT_ROLLOUT"
HOSTED_EXPOSURE_TOKEN = "APPROVE_HOSTED_PRODUCT_API_EXPOSURE"
VALID_DECISIONS = {"approve", "defer"}
VALID_TARGETS = {"compose", "k8s", "systemd", "build-only", "all"}
CLAIM_BOUNDARY = (
    "Product rollout execution readiness only; it validates operator-provided rollout, TLS, pager, and registry/context "
    "metadata before a separate execution step. It does not build images, push containers, apply Kubernetes manifests, "
    "start services, contact pager providers, verify live certificates, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _is_true_text(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _write_template(path_like: str | Path) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "operator_decision",
        "rollout_approval_token",
        "hosted_exposure_approval_token",
        "target_environment",
        "image_digest_or_tag",
        "registry_context_verified",
        "k8s_or_compose_context_verified",
        "tls_termination_verified",
        "pager_webhook_secret_mounted",
        "rollback_reference_verified",
        "operator_name",
        "reviewed_at_utc",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "operator_decision": "",
                "rollout_approval_token": "",
                "hosted_exposure_approval_token": "",
                "target_environment": "",
                "image_digest_or_tag": "",
                "registry_context_verified": "",
                "k8s_or_compose_context_verified": "",
                "tls_termination_verified": "",
                "pager_webhook_secret_mounted": "",
                "rollback_reference_verified": "",
                "operator_name": "",
                "reviewed_at_utc": "",
                "operator_note": "",
            }
        )


def build_product_rollout_execution_readiness(
    *,
    release_bundle_packet: dict[str, Any],
    rollout_plan_packet: dict[str, Any],
    security_contract_packet: dict[str, Any],
    alert_smoke_packet: dict[str, Any],
    operator_rows: list[dict[str, Any]],
    operator_csv_present: bool,
    operator_csv: str = DEFAULT_OPERATOR_INTAKE_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
) -> dict[str, Any]:
    release = _summary(release_bundle_packet)
    rollout = _summary(rollout_plan_packet)
    security = _summary(security_contract_packet)
    alert = _summary(alert_smoke_packet)
    blockers: list[str] = []
    release_ready = _text(release.get("status")) == "release_bundle_ready_for_operator_review" and _int(release.get("blocker_count")) == 0
    rollout_ready = (
        _text(rollout.get("status")) == "planned"
        and rollout.get("dry_run") is True
        and _text(rollout.get("approval_token_required")) == APPROVAL_TOKEN
    )
    security_ready = _text(security.get("status")) == "product_security_deployment_contract_ready" and _bool(
        security.get("security_deployment_ready")
    )
    alert_ready = _text(alert.get("status")) == "pass" and _int(alert.get("received_alert_count")) >= 1
    if not release_ready:
        blockers.append("release_bundle_not_ready")
    if not rollout_ready:
        blockers.append("rollout_plan_not_dry_run_ready")
    if not security_ready:
        blockers.append("security_contract_not_ready")
    if not alert_ready:
        blockers.append("alert_smoke_not_ready")
    if not operator_csv_present:
        blockers.append("operator_rollout_execution_csv_missing")
    if len(operator_rows) > 1:
        blockers.append("duplicate_operator_rollout_execution_rows")

    row_input = operator_rows[0] if operator_rows else {}
    decision = _text(row_input.get("operator_decision")).lower()
    rollout_token = _text(row_input.get("rollout_approval_token"))
    hosted_token = _text(row_input.get("hosted_exposure_approval_token"))
    target_environment = _text(row_input.get("target_environment")).lower()
    image_digest_or_tag = _text(row_input.get("image_digest_or_tag"))
    operator_name = _text(row_input.get("operator_name"))
    reviewed_at_utc = _text(row_input.get("reviewed_at_utc"))
    row_blockers: list[str] = []
    if not row_input:
        row_status = "awaiting_operator_rollout_execution_approval"
        row_blockers.append("operator_decision_missing")
    elif decision not in VALID_DECISIONS:
        row_status = "blocked_before_rollout_execution"
        row_blockers.append("operator_decision_invalid")
    elif decision == "defer":
        row_status = "deferred_by_operator"
    else:
        row_status = "approved_for_separate_operator_execution"
        if rollout_token != APPROVAL_TOKEN:
            row_blockers.append("rollout_approval_token_mismatch")
        if hosted_token != HOSTED_EXPOSURE_TOKEN:
            row_blockers.append("hosted_exposure_approval_token_mismatch")
        if target_environment not in VALID_TARGETS:
            row_blockers.append("target_environment_invalid")
        if not image_digest_or_tag:
            row_blockers.append("image_digest_or_tag_missing")
        for key in (
            "registry_context_verified",
            "k8s_or_compose_context_verified",
            "tls_termination_verified",
            "pager_webhook_secret_mounted",
            "rollback_reference_verified",
        ):
            if not _is_true_text(row_input.get(key)):
                row_blockers.append(f"{key}_not_confirmed")
        if not operator_name:
            row_blockers.append("operator_name_missing")
        if not reviewed_at_utc:
            row_blockers.append("reviewed_at_utc_missing")
        if row_blockers:
            row_status = "blocked_before_rollout_execution"
    blockers.extend(row_blockers)

    ready = row_status == "approved_for_separate_operator_execution" and not blockers
    row = {
        "rollout_execution_readiness_status": row_status,
        "operator_decision": decision,
        "target_environment": target_environment,
        "image_digest_or_tag_present": bool(image_digest_or_tag),
        "rollout_approval_token_required": APPROVAL_TOKEN,
        "rollout_approval_token_present": bool(rollout_token),
        "hosted_exposure_approval_token_required": HOSTED_EXPOSURE_TOKEN,
        "hosted_exposure_approval_token_present": bool(hosted_token),
        "registry_context_verified": _is_true_text(row_input.get("registry_context_verified")),
        "k8s_or_compose_context_verified": _is_true_text(row_input.get("k8s_or_compose_context_verified")),
        "tls_termination_verified": _is_true_text(row_input.get("tls_termination_verified")),
        "pager_webhook_secret_mounted": _is_true_text(row_input.get("pager_webhook_secret_mounted")),
        "rollback_reference_verified": _is_true_text(row_input.get("rollback_reference_verified")),
        "operator_name_present": bool(operator_name),
        "reviewed_at_utc_present": bool(reviewed_at_utc),
        "blockers": ",".join(row_blockers),
        "rollout_executed": False,
        "pager_provider_contacted": False,
        "ingress_certificate_verified_live": False,
        "external_state_mutated": False,
    }
    summary = {
        "packet_type": "product_rollout_execution_readiness",
        "status": "product_rollout_execution_readiness_ready" if ready else "blocked_product_rollout_execution_readiness",
        "source_release_bundle_status": _text(release.get("status")),
        "source_release_bundle_blocker_count": _int(release.get("blocker_count")),
        "source_rollout_plan_status": _text(rollout.get("status")),
        "source_rollout_plan_dry_run": rollout.get("dry_run"),
        "source_security_contract_status": _text(security.get("status")),
        "source_alert_smoke_status": _text(alert.get("status")),
        "operator_csv": operator_csv,
        "operator_csv_present": bool(operator_csv_present),
        "operator_template_csv": template_csv,
        "release_bundle_ready": release_ready,
        "rollout_plan_ready": rollout_ready,
        "security_contract_ready": security_ready,
        "alert_smoke_ready": alert_ready,
        "authorized_for_separate_operator_execution": ready,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "approval_tokens_required": [APPROVAL_TOKEN, HOSTED_EXPOSURE_TOKEN],
        "rollout_executed": False,
        "image_built": False,
        "image_pushed": False,
        "service_restarted": False,
        "pager_provider_contacted": False,
        "ingress_certificate_verified_live": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the separate operator-approved rollout execution smoke outside this read-only preflight."
            if ready
            else f"Fill `{template_csv}` into `{operator_csv}` after confirming registry/context/TLS/pager/rollback details."
        ),
    }
    return {"summary": summary, "rows": [row]}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Rollout Execution Readiness",
        "",
        f"- status: `{s['status']}`",
        f"- release_bundle_ready: `{s['release_bundle_ready']}`",
        f"- rollout_plan_ready: `{s['rollout_plan_ready']}`",
        f"- security_contract_ready: `{s['security_contract_ready']}`",
        f"- alert_smoke_ready: `{s['alert_smoke_ready']}`",
        f"- operator_csv_present: `{s['operator_csv_present']}`",
        f"- authorized_for_separate_operator_execution: `{s['authorized_for_separate_operator_execution']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- rollout_executed: `{s['rollout_executed']}`",
        f"- pager_provider_contacted: `{s['pager_provider_contacted']}`",
        f"- ingress_certificate_verified_live: `{s['ingress_certificate_verified_live']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| status | decision | target | registry | context | tls | pager | rollback | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['rollout_execution_readiness_status']}` | `{row['operator_decision']}` | `{row['target_environment']}` | "
            f"`{row['registry_context_verified']}` | `{row['k8s_or_compose_context_verified']}` | "
            f"`{row['tls_termination_verified']}` | `{row['pager_webhook_secret_mounted']}` | "
            f"`{row['rollback_reference_verified']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only product rollout execution readiness preflight.")
    parser.add_argument("--release-bundle-json", default=DEFAULT_RELEASE_BUNDLE_JSON)
    parser.add_argument("--rollout-plan-json", default=DEFAULT_ROLLOUT_PLAN_JSON)
    parser.add_argument("--security-contract-json", default=DEFAULT_SECURITY_CONTRACT_JSON)
    parser.add_argument("--alert-smoke-json", default=DEFAULT_ALERT_SMOKE_JSON)
    parser.add_argument("--operator-intake-csv", default=DEFAULT_OPERATOR_INTAKE_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_rollout_execution_readiness(
        release_bundle_packet=_read_json_if_present(args.release_bundle_json),
        rollout_plan_packet=_read_json_if_present(args.rollout_plan_json),
        security_contract_packet=_read_json_if_present(args.security_contract_json),
        alert_smoke_packet=_read_json_if_present(args.alert_smoke_json),
        operator_rows=_read_csv_rows(args.operator_intake_csv),
        operator_csv_present=_resolve(args.operator_intake_csv).exists(),
        operator_csv=args.operator_intake_csv,
        template_csv=args.template_csv,
    )
    _write_template(args.template_csv)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
