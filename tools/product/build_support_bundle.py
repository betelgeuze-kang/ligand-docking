#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/support_bundle_current.json"
DEFAULT_OUT_CSV = "runs/support_bundle_current.csv"
DEFAULT_OUT_MD = "runs/support_bundle_current.md"

CLAIM_BOUNDARY = (
    "Support bundle readiness only; builds a redacted local manifest of selected operator artifacts, hashes, "
    "and safe summary fields for incident handoff and recovery review. It does not include customer raw data, "
    "read .env files, run docking, start services, build images, deploy, upload, email, delete, commit, push, "
    "or mutate external state."
)

FORBIDDEN_PATH_FRAGMENTS = (".env", "/.env", "customer_raw", "raw_customer", "secrets/")

SAFE_SUMMARY_FIELDS = (
    "status",
    "packet_type",
    "blocker_count",
    "claim_boundary",
    "execution_enabled",
    "external_state_mutated",
    "next_required_step",
    "audit_log_ready",
    "audit_retention_ready",
    "metrics_endpoint_ready",
    "rollback_ready",
    "product_job_orchestration_contract_ready",
    "worker_lease_heartbeat_ready",
    "idempotency_preserved",
    "retry_child_attempt_created",
    "retryable_failure_resume_ready",
    "rollout_execution_smoke_receipt_ready",
    "rollout_executed",
    "ingress_certificate_verified_live",
    "target_environment",
    "ledger_privacy_scan_ready",
    "leak_count",
    "invalid_json_count",
    "result_manifest_signature_verified",
    "bundle_validation_ready",
    "restricted_unattended_runtime_ready",
    "tier_alpha_smoke_status",
    "third_party_license_review_gate_ready",
    "hard_blocker_count",
    "spdx_license_id",
)

REQUIRED_ARTIFACTS = (
    {
        "artifact_id": "product_security_deployment_contract",
        "path": "runs/product_security_deployment_contract_current.json",
        "required_status": "product_security_deployment_contract_ready",
        "required_true_fields": (
            "audit_log_ready",
            "audit_retention_ready",
            "metrics_endpoint_ready",
            "rollback_ready",
        ),
        "required_zero_fields": ("blocker_count",),
    },
    {
        "artifact_id": "product_job_orchestration_contract",
        "path": "runs/product_job_orchestration_contract_current.json",
        "required_status": "product_job_orchestration_contract_ready",
        "required_true_fields": (
            "product_job_orchestration_contract_ready",
            "worker_lease_heartbeat_ready",
            "idempotency_preserved",
            "retry_child_attempt_created",
            "retryable_failure_resume_ready",
        ),
        "required_zero_fields": ("blocked_check_count",),
    },
    {
        "artifact_id": "product_rollout_execution_smoke_receipt",
        "path": "runs/product_rollout_execution_smoke_receipt_current.json",
        "required_status": "product_rollout_execution_smoke_receipt_ready",
        "required_true_fields": (
            "rollout_execution_smoke_receipt_ready",
            "rollout_executed",
            "ingress_certificate_verified_live",
        ),
        "required_zero_fields": ("blocker_count",),
    },
    {
        "artifact_id": "product_ledger_privacy_scan",
        "path": "runs/product_ledger_privacy_scan_current.json",
        "required_status": "product_ledger_privacy_scan_ready",
        "required_true_fields": ("ledger_privacy_scan_ready",),
        "required_zero_fields": ("blocker_count", "leak_count", "invalid_json_count"),
    },
    {
        "artifact_id": "api_customer_flow_release_evidence",
        "path": "runs/api_customer_flow_release_evidence_current.json",
        "required_status": "api_customer_flow_release_evidence_ready",
        "required_true_fields": (
            "result_manifest_signature_verified",
            "bundle_validation_ready",
            "restricted_unattended_runtime_ready",
        ),
        "required_zero_fields": ("blocker_count",),
    },
    {
        "artifact_id": "self_hosted_license_distribution_audit",
        "path": "runs/self_hosted_license_distribution_audit_current.json",
        "required_status": "self_hosted_license_distribution_audit_recorded",
        "required_true_fields": ("third_party_license_review_gate_ready",),
        "required_zero_fields": ("hard_blocker_count",),
    },
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _artifact(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _path_allowed(path_text: str) -> bool:
    lowered = path_text.lower()
    return not any(fragment in lowered for fragment in FORBIDDEN_PATH_FRAGMENTS)


def _safe_summary(summary: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for field in SAFE_SUMMARY_FIELDS:
        value = summary.get(field)
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[field] = value
    return safe


def _artifact_row(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    path_text = _text(spec["path"])
    path = _resolve(path_text, root=root)
    payload = _read_json(path, root=root)
    summary = _summary(payload)
    required_status = _text(spec.get("required_status"))
    missing_true_fields = [
        field for field in spec.get("required_true_fields", ()) if summary.get(field) is not True
    ]
    nonzero_fields = [
        field for field in spec.get("required_zero_fields", ()) if _int(summary.get(field)) != 0
    ]
    path_allowed = _path_allowed(path_text)
    present = path.exists() and path.is_file()
    status_matches = _text(summary.get("status")) == required_status if required_status else bool(summary)
    ready = present and path_allowed and status_matches and not missing_true_fields and not nonzero_fields
    blockers = []
    if not present:
        blockers.append("artifact_missing")
    if not path_allowed:
        blockers.append("artifact_path_not_allowlisted_for_support_bundle")
    if not status_matches:
        blockers.append("artifact_status_not_ready")
    blockers.extend(f"missing_true:{field}" for field in missing_true_fields)
    blockers.extend(f"nonzero:{field}" for field in nonzero_fields)
    return {
        "artifact_id": _text(spec["artifact_id"]),
        "artifact_path": _artifact(path_text, root=root),
        "artifact_present": present,
        "artifact_sha256": _sha256(path),
        "status": _text(summary.get("status")) or "missing",
        "ready": ready,
        "safe_summary": _safe_summary(summary),
        "blockers": blockers,
        "redacted_summary_only": True,
        "customer_raw_data_included": False,
        "secret_material_included": False,
    }


def build_support_bundle(
    *,
    root: Path = ROOT,
    artifact_specs: tuple[dict[str, Any], ...] = REQUIRED_ARTIFACTS,
) -> dict[str, Any]:
    root = Path(root)
    rows = [_artifact_row(spec, root=root) for spec in artifact_specs]
    blocked_rows = [row for row in rows if not row["ready"]]
    lookup = {row["artifact_id"]: row for row in rows}
    security = lookup.get("product_security_deployment_contract", {}).get("safe_summary", {})
    jobs = lookup.get("product_job_orchestration_contract", {}).get("safe_summary", {})
    rollout = lookup.get("product_rollout_execution_smoke_receipt", {}).get("safe_summary", {})
    privacy = lookup.get("product_ledger_privacy_scan", {}).get("safe_summary", {})
    api_flow = lookup.get("api_customer_flow_release_evidence", {}).get("safe_summary", {})
    license_audit = lookup.get("self_hosted_license_distribution_audit", {}).get("safe_summary", {})

    recovery_drill_ready = (
        _bool_true(security.get("rollback_ready"))
        and _bool_true(jobs.get("idempotency_preserved"))
        and _bool_true(jobs.get("retryable_failure_resume_ready"))
        and _bool_true(rollout.get("rollout_execution_smoke_receipt_ready"))
        and _bool_true(rollout.get("rollout_executed"))
    )
    incident_handoff_ready = (
        _bool_true(security.get("audit_log_ready"))
        and _bool_true(security.get("metrics_endpoint_ready"))
        and _bool_true(privacy.get("ledger_privacy_scan_ready"))
        and _bool_true(api_flow.get("result_manifest_signature_verified"))
        and _bool_true(license_audit.get("third_party_license_review_gate_ready"))
    )
    blocked_secret_path_count = sum(1 for row in rows if not _path_allowed(row["artifact_path"]))
    raw_customer_data_included = any(row["customer_raw_data_included"] for row in rows)
    secret_material_included = any(row["secret_material_included"] for row in rows)
    customer_safe_bundle_ready = (
        not blocked_secret_path_count
        and not raw_customer_data_included
        and not secret_material_included
        and _int(privacy.get("leak_count")) == 0
    )
    support_bundle_ready = (
        not blocked_rows
        and recovery_drill_ready
        and incident_handoff_ready
        and customer_safe_bundle_ready
    )
    primary = blocked_rows[0] if blocked_rows else {}
    primary_blocker = ""
    if primary:
        primary_blocker = _text(primary.get("blockers", ["support_bundle_artifact_blocked"])[0])
    elif not recovery_drill_ready:
        primary_blocker = "recovery_drill_evidence_incomplete"
    elif not incident_handoff_ready:
        primary_blocker = "incident_handoff_evidence_incomplete"
    elif not customer_safe_bundle_ready:
        primary_blocker = "customer_safe_redaction_evidence_incomplete"

    summary = {
        "packet_type": "support_bundle",
        "status": "support_bundle_ready" if support_bundle_ready else "blocked_support_bundle",
        "support_bundle_ready": support_bundle_ready,
        "customer_safe_bundle_ready": customer_safe_bundle_ready,
        "recovery_drill_ready": recovery_drill_ready,
        "incident_handoff_ready": incident_handoff_ready,
        "redaction_manifest_ready": True,
        "artifact_count": len(rows),
        "required_artifact_count": len(rows),
        "ready_artifact_count": sum(1 for row in rows if row["ready"]),
        "blocked_artifact_count": len(blocked_rows),
        "redacted_artifact_count": len(rows),
        "blocked_secret_path_count": blocked_secret_path_count,
        "raw_customer_data_included": raw_customer_data_included,
        "secret_material_included": secret_material_included,
        "primary_blocker_id": _text(primary.get("artifact_id")) if primary else "",
        "primary_blocker": primary_blocker,
        "included_artifact_ids": [row["artifact_id"] for row in rows],
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Support bundle is ready for operator incident handoff review."
            if support_bundle_ready
            else "Clear the primary support-bundle blocker, then rebuild this manifest."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Support Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- support_bundle_ready: `{s['support_bundle_ready']}`",
        f"- customer_safe_bundle_ready: `{s['customer_safe_bundle_ready']}`",
        f"- recovery_drill_ready: `{s['recovery_drill_ready']}`",
        f"- incident_handoff_ready: `{s['incident_handoff_ready']}`",
        f"- blocked_artifact_count: `{s['blocked_artifact_count']}`",
        "",
        "| artifact | status | ready | sha256 |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_id']}` | `{row['status']}` | `{row['ready']}` | "
            f"`{row['artifact_sha256'][:12]}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build redacted support bundle readiness manifest.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_support_bundle(root=root)
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
