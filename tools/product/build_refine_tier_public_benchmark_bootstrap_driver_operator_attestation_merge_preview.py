#!/usr/bin/env python3
"""Merge-preview gate for R9 bootstrap-driver operator attestations."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template import (
    DEFAULT_OUT_CSV as DEFAULT_ATTESTATION_CSV,
    OPERATOR_ONLY_FIELDS,
)
from tools.product.build_refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template import (
    DEFAULT_PREFILL_CSV,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt import (
    APPROVAL_TOKEN,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview_current.json"
DEFAULT_OUT_CSV = "config/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview_current.csv"
DEFAULT_MERGED_CANDIDATE_CSV = (
    "config/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merged_candidate_current.csv"
)
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview_current.md"

PLACEHOLDER_PREFIXES = ("OPERATOR_FILL", "OPERATOR_CONFIRM")
ACCEPT_DECISIONS = {"accept", "accepted", "approve", "approved", "reviewed_accept"}

CLAIM_BOUNDARY = (
    "R9 bootstrap-driver operator attestation merge preview validates operator-only attestations against "
    "machine-prefill row fingerprints and builds a separate merged candidate worksheet only for passing "
    "rows. It does not edit the canonical worksheet, write metric payload JSON, copy canonical receipts, "
    "promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, "
    "commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _read_csv(path_like: str | Path, *, root: Path) -> tuple[list[dict[str, str]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _has_placeholder(value: Any) -> bool:
    return _text(value).startswith(PLACEHOLDER_PREFIXES)


def _reviewed_at_valid(value: Any) -> bool:
    text = _text(value)
    if not text or _has_placeholder(text):
        return False
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def prefill_row_fingerprint(row: dict[str, Any]) -> str:
    payload = {str(key): _text(value) for key, value in sorted(row.items())}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _attestation_blockers(attestation: dict[str, Any], prefill: dict[str, Any] | None) -> list[str]:
    blockers: list[str] = []
    if prefill is None:
        blockers.append("prefill_row_missing_for_attestation")
        return blockers
    expected_fingerprint = prefill_row_fingerprint(prefill)
    if _text(attestation.get("prefill_row_sha256")) != expected_fingerprint:
        blockers.append("prefill_row_fingerprint_missing_or_mismatch")
    if any(_has_placeholder(attestation.get(field)) for field in OPERATOR_ONLY_FIELDS):
        blockers.append("operator_only_placeholders_unfilled")
    if _text(attestation.get("operator_decision")).lower() not in ACCEPT_DECISIONS:
        blockers.append("operator_decision_missing_or_not_accept")
    if _bool(attestation.get("license_ok_reviewed")) is not True:
        blockers.append("license_review_not_true")
    if not _text(attestation.get("operator_id")) or _has_placeholder(attestation.get("operator_id")):
        blockers.append("operator_id_missing")
    if not _reviewed_at_valid(attestation.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing_or_invalid")
    if _text(attestation.get("approval_token")) != APPROVAL_TOKEN:
        blockers.append("approval_token_missing_or_invalid")
    if _text(attestation.get("approval_token_required")) != APPROVAL_TOKEN:
        blockers.append("approval_token_required_mismatch")
    return blockers


def _merge_candidate(prefill: dict[str, str], attestation: dict[str, str]) -> dict[str, str]:
    merged = dict(prefill)
    for field in OPERATOR_ONLY_FIELDS:
        merged[field] = _text(attestation.get(field))
    merged["operator_manual_pending_field_count"] = "0"
    merged["operator_manual_pending_fields"] = ""
    merged["payload_write_allowed"] = "False"
    merged["canonical_receipt_write_allowed"] = "False"
    merged["canonical_intake_promotion_allowed"] = "False"
    merged["claim_promotion_allowed"] = "False"
    merged["production_score_mutation_allowed"] = "False"
    merged["external_state_mutated"] = "False"
    return merged


def _most_common_blocker(rows: list[dict[str, Any]]) -> str:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(_split_semicolon(row.get("blockers")))
    return counter.most_common(1)[0][0] if counter else ""


def build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview(
    *,
    prefill_csv: str | Path = DEFAULT_PREFILL_CSV,
    attestation_csv: str | Path = DEFAULT_ATTESTATION_CSV,
    merged_candidate_csv: str | Path = DEFAULT_MERGED_CANDIDATE_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    prefill_rows, _, prefill_present = _read_csv(prefill_csv, root=root_path)
    attestation_rows, _, attestation_present = _read_csv(attestation_csv, root=root_path)
    prefill_by_worksheet = {_text(row.get("worksheet_id")): row for row in prefill_rows if _text(row.get("worksheet_id"))}
    attestation_by_worksheet = {
        _text(row.get("worksheet_id")): row for row in attestation_rows if _text(row.get("worksheet_id"))
    }
    missing_attestation_ids = [
        worksheet_id for worksheet_id in prefill_by_worksheet if worksheet_id not in attestation_by_worksheet
    ]
    unexpected_attestation_ids = [
        worksheet_id for worksheet_id in attestation_by_worksheet if worksheet_id not in prefill_by_worksheet
    ]

    report_rows: list[dict[str, Any]] = []
    merged_rows: list[dict[str, str]] = []
    for index, attestation in enumerate(attestation_rows, start=1):
        worksheet_id = _text(attestation.get("worksheet_id"))
        prefill = prefill_by_worksheet.get(worksheet_id)
        expected_fingerprint = prefill_row_fingerprint(prefill) if prefill is not None else ""
        blockers = _attestation_blockers(attestation, prefill)
        row_status = "pass" if not blockers else "blocked"
        if row_status == "pass" and prefill is not None:
            merged_rows.append(_merge_candidate(prefill, attestation))
        report_rows.append(
            {
                "merge_preview_id": f"r9_bootstrap_driver_operator_attestation_merge_{index:03d}",
                "attestation_id": _text(attestation.get("attestation_id")),
                "worksheet_id": worksheet_id,
                "target_id": _text(attestation.get("target_id")),
                "pose_id": _text(attestation.get("pose_id")),
                "work_order_id": _text(attestation.get("work_order_id")),
                "split": _text(attestation.get("split")),
                "metric_name": _text(attestation.get("metric_name")),
                "review_surface": _text(attestation.get("review_surface")),
                "provided_prefill_row_sha256": _text(attestation.get("prefill_row_sha256")),
                "expected_prefill_row_sha256": expected_fingerprint,
                "prefill_row_fingerprint_verified": bool(
                    expected_fingerprint and _text(attestation.get("prefill_row_sha256")) == expected_fingerprint
                ),
                "operator_decision": _text(attestation.get("operator_decision")),
                "license_ok_reviewed": _text(attestation.get("license_ok_reviewed")),
                "operator_id": _text(attestation.get("operator_id")),
                "reviewed_at_utc": _text(attestation.get("reviewed_at_utc")),
                "approval_token": _text(attestation.get("approval_token")),
                "row_status": row_status,
                "blockers": ";".join(blockers),
                "merged_candidate_row_emitted": row_status == "pass",
                "payload_write_allowed": False,
                "canonical_receipt_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "production_score_mutation_allowed": False,
                "external_state_mutated": False,
            }
        )

    pass_rows = [row for row in report_rows if row["row_status"] == "pass"]
    blocked_rows = [row for row in report_rows if row["row_status"] != "pass"]
    blockers: list[str] = []
    if not prefill_present:
        blockers.append("prefill_csv_missing")
    if not attestation_present:
        blockers.append("attestation_csv_missing")
    if not prefill_rows:
        blockers.append("prefill_rows_missing")
    if not attestation_rows:
        blockers.append("attestation_rows_missing")
    if missing_attestation_ids:
        blockers.append("attestation_rows_missing_for_prefill_rows")
    if unexpected_attestation_ids:
        blockers.append("unexpected_attestation_rows_present")
    if blocked_rows:
        blockers.append("blocked_attestation_rows_present")
    all_rows_mergeable = bool(
        prefill_present
        and attestation_present
        and prefill_rows
        and attestation_rows
        and not missing_attestation_ids
        and not unexpected_attestation_ids
        and len(pass_rows) == len(prefill_rows)
    )

    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview_ready"
            if all_rows_mergeable
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview"
        ),
        "prefill_csv": _display(prefill_csv, root=root_path),
        "prefill_csv_present": prefill_present,
        "prefill_row_count": len(prefill_rows),
        "attestation_csv": _display(attestation_csv, root=root_path),
        "attestation_csv_present": attestation_present,
        "attestation_row_count": len(attestation_rows),
        "merge_preview_row_count": len(report_rows),
        "merge_preview_pass_row_count": len(pass_rows),
        "merge_preview_blocked_row_count": len(blocked_rows),
        "prefill_row_fingerprint_verified_count": sum(
            1 for row in report_rows if row.get("prefill_row_fingerprint_verified") is True
        ),
        "prefill_row_fingerprint_mismatch_count": sum(
            1
            for row in report_rows
            if "prefill_row_fingerprint_missing_or_mismatch" in _split_semicolon(row.get("blockers"))
        ),
        "missing_attestation_row_count": len(missing_attestation_ids),
        "missing_attestation_worksheet_ids": missing_attestation_ids,
        "unexpected_attestation_row_count": len(unexpected_attestation_ids),
        "unexpected_attestation_worksheet_ids": unexpected_attestation_ids,
        "merged_candidate_csv": _display(merged_candidate_csv, root=root_path),
        "merged_candidate_row_count": len(merged_rows),
        "attestation_merge_ready": all_rows_mergeable,
        "approval_token_required": APPROVAL_TOKEN,
        "canonical_worksheet_edited": False,
        "payload_write_allowed": False,
        "canonical_receipt_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "first_blocked_merge_preview_id": _text(blocked_rows[0].get("merge_preview_id")) if blocked_rows else "",
        "first_blocked_worksheet_id": _text(blocked_rows[0].get("worksheet_id")) if blocked_rows else "",
        "most_common_row_blocker": _most_common_blocker(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Fill all operator attestation rows, verify prefill fingerprints, then use the merged candidate "
            "worksheet as the input to the staging apply preview before any payload or canonical receipt write."
            if not all_rows_mergeable
            else "Merged candidate worksheet is ready for staging apply preview; payload and canonical receipt writes remain disabled here."
        ),
    }
    return {"summary": summary, "rows": report_rows, "merged_candidate_rows": merged_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Operator Attestation Merge Preview",
        "",
        f"- status: `{s['status']}`",
        f"- attestation_merge_ready: `{s['attestation_merge_ready']}`",
        f"- rows pass/blocked/total: `{s['merge_preview_pass_row_count']}/{s['merge_preview_blocked_row_count']}/{s['merge_preview_row_count']}`",
        f"- prefill_row_fingerprint_verified_count: `{s['prefill_row_fingerprint_verified_count']}`",
        f"- prefill_row_fingerprint_mismatch_count: `{s['prefill_row_fingerprint_mismatch_count']}`",
        f"- merged_candidate_row_count: `{s['merged_candidate_row_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- payload_write_allowed: `{s['payload_write_allowed']}`",
        f"- canonical_receipt_write_allowed: `{s['canonical_receipt_write_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- most_common_row_blocker: `{s['most_common_row_blocker']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in s["blockers"])
    if not s["blockers"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| merge | target | pose | metric | fingerprint | status | blockers |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['merge_preview_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['metric_name']}` | `{row['prefill_row_fingerprint_verified']}` | "
            f"`{row['row_status']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R9 bootstrap-driver attestation merge preview.")
    parser.add_argument("--prefill-csv", default=DEFAULT_PREFILL_CSV)
    parser.add_argument("--attestation-csv", default=DEFAULT_ATTESTATION_CSV)
    parser.add_argument("--merged-candidate-csv", default=DEFAULT_MERGED_CANDIDATE_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview(
        prefill_csv=args.prefill_csv,
        attestation_csv=args.attestation_csv,
        merged_candidate_csv=args.merged_candidate_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    write_csv_rows(_resolve(args.merged_candidate_csv, root=root), payload["merged_candidate_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
