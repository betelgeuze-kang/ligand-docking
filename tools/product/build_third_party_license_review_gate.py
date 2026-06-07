#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LICENSE_AUDIT_JSON = "runs/self_hosted_license_distribution_audit_current.json"
DEFAULT_REVIEW_CSV = "runs/third_party_license_review_operator_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/third_party_license_review_operator_template_current.csv"
DEFAULT_OUT_JSON = "runs/third_party_license_review_gate_current.json"
DEFAULT_OUT_CSV = "runs/third_party_license_review_gate_current.csv"
DEFAULT_OUT_MD = "runs/third_party_license_review_gate_current.md"

APPROVAL_TOKEN = "APPROVE_THIRD_PARTY_LICENSE_REVIEW"
APPROVE_DECISION = "approve"
DEFER_DECISION = "defer"
VALID_DECISIONS = {APPROVE_DECISION, DEFER_DECISION}
ALLOWED_LICENSE_PATHS = {"MIT", "GPL-3.0-or-later", "remove_or_replace_asset"}
CLAIM_BOUNDARY = (
    "Third-party license review gate only; it validates operator/legal-review intake for recorded dual-license "
    "third-party assets. It does not provide legal advice, choose a license automatically, modify vendor assets, "
    "remove files, upload, publish, or mutate external state."
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
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _review_assets(audit_packet: dict[str, Any]) -> list[str]:
    summary = _summary(audit_packet)
    assets = summary.get("third_party_dual_license_assets")
    if isinstance(assets, list):
        return sorted({_text(asset).lower() for asset in assets if _text(asset)})
    return []


def _write_template(path_like: str | Path, assets: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "package",
        "operator_decision",
        "approval_token",
        "chosen_license_path",
        "reviewer_name",
        "reviewed_at_utc",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for package in assets or ["OPERATOR_FILL_PACKAGE"]:
            writer.writerow(
                {
                    "package": package,
                    "operator_decision": "",
                    "approval_token": "",
                    "chosen_license_path": "",
                    "reviewer_name": "",
                    "reviewed_at_utc": "",
                    "operator_note": "",
                }
            )


def build_third_party_license_review_gate(
    *,
    audit_packet: dict[str, Any],
    review_rows: list[dict[str, Any]],
    review_csv_present: bool,
    review_csv: str = DEFAULT_REVIEW_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
) -> dict[str, Any]:
    audit = _summary(audit_packet)
    review_assets = _review_assets(audit_packet)
    expected_assets = set(review_assets)
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    audit_ready = (
        _text(audit.get("status")) == "self_hosted_license_distribution_audit_recorded"
        and int(audit.get("hard_blocker_count") or 0) == 0
        and not _bool(audit.get("external_state_mutated"))
    )
    if not audit_ready:
        blockers.append("license_distribution_audit_not_ready")
    if expected_assets and not review_csv_present:
        blockers.append("operator_review_csv_missing")

    seen: set[str] = set()
    for index, row_in in enumerate(review_rows, start=1):
        package = _text(row_in.get("package")).lower()
        decision = _text(row_in.get("operator_decision")).lower()
        token = _text(row_in.get("approval_token"))
        chosen_license_path = _text(row_in.get("chosen_license_path"))
        reviewer_name = _text(row_in.get("reviewer_name"))
        reviewed_at_utc = _text(row_in.get("reviewed_at_utc"))
        row_blockers: list[str] = []
        if not package:
            row_blockers.append("package_missing")
        elif package in seen:
            row_blockers.append("duplicate_package_review_row")
        elif package not in expected_assets:
            row_blockers.append("package_not_in_review_assets")
        seen.add(package)
        if decision not in VALID_DECISIONS:
            row_blockers.append("operator_decision_invalid")
        elif decision == APPROVE_DECISION:
            if token != APPROVAL_TOKEN:
                row_blockers.append("approval_token_mismatch")
            if chosen_license_path not in ALLOWED_LICENSE_PATHS:
                row_blockers.append("chosen_license_path_invalid")
            if not reviewer_name:
                row_blockers.append("reviewer_name_missing")
            if not reviewed_at_utc:
                row_blockers.append("reviewed_at_utc_missing")
        status = "approved_for_operator_record" if decision == APPROVE_DECISION and not row_blockers else (
            "deferred_by_operator" if decision == DEFER_DECISION and not row_blockers else "blocked_review_row"
        )
        blockers.extend(row_blockers)
        rows.append(
            {
                "row_number": index,
                "package": package,
                "review_status": status,
                "operator_decision": decision,
                "chosen_license_path": chosen_license_path,
                "approval_token_required": APPROVAL_TOKEN,
                "approval_token_present": bool(token),
                "reviewer_name_present": bool(reviewer_name),
                "reviewed_at_utc_present": bool(reviewed_at_utc),
                "blockers": ",".join(row_blockers),
                "legal_advice_provided": False,
                "asset_modified": False,
                "external_state_mutated": False,
            }
        )

    missing_assets = sorted(expected_assets - seen)
    blockers.extend(f"missing_review_row:{asset}" for asset in missing_assets)
    approved_assets = sorted(row["package"] for row in rows if row["review_status"] == "approved_for_operator_record")
    deferred_assets = sorted(row["package"] for row in rows if row["review_status"] == "deferred_by_operator")
    ready = audit_ready and expected_assets and not blockers and set(approved_assets) == expected_assets
    status = "third_party_license_review_gate_ready" if ready else "blocked_third_party_license_review_gate"
    summary = {
        "packet_type": "third_party_license_review_gate",
        "status": status,
        "source_license_audit_status": _text(audit.get("status")),
        "source_hard_blocker_count": int(audit.get("hard_blocker_count") or 0),
        "source_operator_review_item_count": int(audit.get("operator_review_item_count") or 0),
        "review_csv": review_csv,
        "review_csv_present": bool(review_csv_present),
        "operator_template_csv": template_csv,
        "expected_review_asset_count": len(expected_assets),
        "review_row_count": len(rows),
        "approved_review_asset_count": len(approved_assets),
        "deferred_review_asset_count": len(deferred_assets),
        "missing_review_asset_count": len(missing_assets),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "approved_assets": approved_assets,
        "deferred_assets": deferred_assets,
        "missing_review_assets": missing_assets,
        "approval_token_required": APPROVAL_TOKEN,
        "allowed_license_paths": sorted(ALLOWED_LICENSE_PATHS),
        "legal_advice_provided": False,
        "asset_modified": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Record the approved third-party redistribution path in release/legal evidence; this gate still provides no legal advice."
            if ready
            else f"Fill `{template_csv}` into `{review_csv}` for every recorded dual-license asset."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Third-Party License Review Gate",
        "",
        f"- status: `{s['status']}`",
        f"- source_license_audit_status: `{s['source_license_audit_status']}`",
        f"- expected_review_asset_count: `{s['expected_review_asset_count']}`",
        f"- review_csv_present: `{s['review_csv_present']}`",
        f"- approved_review_asset_count: `{s['approved_review_asset_count']}`",
        f"- missing_review_asset_count: `{s['missing_review_asset_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- legal_advice_provided: `{s['legal_advice_provided']}`",
        f"- asset_modified: `{s['asset_modified']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| package | status | decision | chosen path | reviewer | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['package']}` | `{row['review_status']}` | `{row['operator_decision']}` | "
            f"`{row['chosen_license_path']}` | `{row['reviewer_name_present']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate third-party dual-license operator review intake.")
    parser.add_argument("--license-audit-json", default=DEFAULT_LICENSE_AUDIT_JSON)
    parser.add_argument("--review-csv", default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    audit = _read_json_if_present(args.license_audit_json)
    payload = build_third_party_license_review_gate(
        audit_packet=audit,
        review_rows=_read_csv_rows(args.review_csv),
        review_csv_present=_resolve(args.review_csv).exists(),
        review_csv=args.review_csv,
        template_csv=args.template_csv,
    )
    _write_template(args.template_csv, _review_assets(audit))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
