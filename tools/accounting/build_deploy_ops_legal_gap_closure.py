#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_product_rollout_execution_readiness import build_product_rollout_execution_readiness
from tools.product.build_third_party_license_review_gate import build_third_party_license_review_gate

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/deploy_ops_legal_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/deploy_ops_legal_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/deploy_ops_legal_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Deploy/ops/legal gap closure status only; it audits rollout execution readiness, pager/TLS operator intake, "
    "third-party license review, and LICENSE technical consistency while keeping rollout_executed=false and "
    "legal_advice_provided=false. It does not deploy services, contact pager providers, or provide legal advice."
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


def _read_text(path_like: str | Path) -> str:
    path = _resolve(path_like)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row(gap_id: str, gap: str, status: str, evidence: str, observed: str, next_action: str) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "gap": gap,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "rollout_executed": False,
        "legal_advice_provided": False,
        "external_state_mutated": False,
    }


def build_deploy_ops_legal_gap_closure(
    *,
    rollout_readiness_packet: dict[str, Any] | None = None,
    license_review_packet: dict[str, Any] | None = None,
    license_decision_packet: dict[str, Any] | None = None,
    security_contract_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    release = _read_json_if_present("runs/product_release_bundle_current.json")
    rollout_plan = _read_json_if_present("runs/product_rollout_plan_current.json")
    security = security_contract_packet or _read_json_if_present("runs/product_security_deployment_contract_current.json")
    alert = _read_json_if_present("runs/alert_delivery_smoke_current.json")
    operator_csv = "runs/product_rollout_execution_operator_intake.csv"
    operator_rows = _read_csv_rows(operator_csv)
    rollout = rollout_readiness_packet or build_product_rollout_execution_readiness(
        release_bundle_packet=release,
        rollout_plan_packet=rollout_plan,
        security_contract_packet=security,
        alert_smoke_packet=alert,
        operator_rows=operator_rows,
        operator_csv_present=_resolve(operator_csv).exists(),
        operator_csv=operator_csv,
    )
    audit = _read_json_if_present("runs/self_hosted_license_distribution_audit_current.json")
    review_csv = "runs/third_party_license_review_operator_intake.csv"
    review_rows = _read_csv_rows(review_csv)
    license_review = license_review_packet or build_third_party_license_review_gate(
        audit_packet=audit,
        review_rows=review_rows,
        review_csv_present=_resolve(review_csv).exists(),
        review_csv=review_csv,
    )
    license_decision = _summary(license_decision_packet or _read_json_if_present("runs/product_license_decision_gate_current.json"))
    security_summary = _summary(security)

    rollout_summary = _summary(rollout)
    license_review_summary = _summary(license_review)
    rollout_closed = rollout_summary.get("status") == "product_rollout_execution_readiness_ready"
    pager_closed = rollout_closed and bool(rollout_summary.get("alert_smoke_ready"))
    security_py = _read_text("api/security.py")
    config_py = _read_text("api/config.py")
    tls_guard_present = (
        "hosted_tls_termination_not_verified" in security_py
        and "product_api_tls_termination_operator_verified" in config_py
    )
    tls_closed = rollout_closed and tls_guard_present
    jszip_closed = license_review_summary.get("status") == "third_party_license_review_gate_ready"
    license_text = _read_text("LICENSE")
    approved_text = _read_text("legal/proprietary-license-betelgeuze.txt")
    license_hash_match = bool(license_text) and _sha256_text(license_text) == _sha256_text(approved_text)
    license_closed = license_decision.get("status") == "product_license_decision_gate_ready" and license_hash_match

    rows = [
        _row(
            "DEP-ROLLOUT",
            "Rollout execution smoke readiness",
            "closed" if rollout_closed else "open",
            "runs/product_rollout_execution_readiness_current.json",
            f"status={rollout_summary.get('status')}; rollout_executed=false",
            "Fill operator rollout intake CSV and run separate operator-approved rollout smoke.",
        ),
        _row(
            "DEP-PAGER",
            "Pager/webhook operator mount confirmation",
            "closed" if pager_closed else "open",
            "monitoring/alertmanager.yml; runs/alert_delivery_smoke_current.json",
            f"alert_smoke_ready={rollout_summary.get('alert_smoke_ready')}; pager_provider_contacted=false",
            "Mount /etc/alertmanager/paged-webhook-url and keep closed-loop smoke evidence current.",
        ),
        _row(
            "DEP-TLS",
            "Ingress/TLS fail-closed guard + operator verification",
            "closed" if tls_closed else "open",
            "api/security.py; deploy/docker-compose.product.yml",
            f"tls_guard_present={tls_guard_present}; ingress_certificate_verified_live=false",
            "Keep fail-closed TLS guard; operator verifies termination before hosted exposure.",
        ),
        _row(
            "DEP-JSZIP",
            "JSZip dual-license operator review",
            "closed" if jszip_closed else "open",
            "runs/third_party_license_review_gate_current.json",
            f"status={license_review_summary.get('status')}; legal_advice_provided=false",
            "Complete third-party license review operator intake for JSZip redistribution path.",
        ),
        _row(
            "DEP-LICENSE",
            "LICENSE technical consistency + legal boundary",
            "closed" if license_closed else "open",
            "LICENSE; legal/proprietary-license-betelgeuze.txt; runs/product_license_decision_gate_current.json",
            f"license_hash_match={license_hash_match}; legal_advice_provided=false",
            "Technical LICENSE/hash gates are closed; legal sufficiency remains operator/legal counsel scope.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "deploy_ops_legal_gap_closure",
        "status": "deploy_ops_legal_gap_closure_complete" if not open_rows else "blocked_deploy_ops_legal_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "closed_gap_ids": [row["gap_id"] for row in closed_rows],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap_id": first_open["gap_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All deploy/ops/legal boundary gaps are closed.",
        "rollout_executed": False,
        "pager_provider_contacted": False,
        "ingress_certificate_verified_live": False,
        "legal_advice_provided": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Deploy/Ops/Legal Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        "",
        "## Gaps",
        "",
        "| gap_id | status | gap | observed |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['gap_id']}` | `{row['status']}` | {row['gap']} | `{row['observed']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build deploy/ops/legal gap closure status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_deploy_ops_legal_gap_closure()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
