#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import PARTIAL_AUTHORITATIVE_SAFE_SCOPE

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_CA2_POLICY_JSON = "runs/ca2_pending_row_disposition_current.json"
DEFAULT_CA2_NEXT_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_CA2_PACKET_JSON = "runs/ca2_packet_replacement_workbook_current.json"
DEFAULT_CA2_COMMIT_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"

DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PXR_POLICY_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_PXR_NEXT_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_PXR_PACKET_JSON = "runs/pxr_packet_replacement_workbook_current.json"

DEFAULT_OUT_JSON = "runs/partial_authoritative_family_handoff_current.json"
DEFAULT_OUT_CSV = "runs/partial_authoritative_family_handoff_current.csv"
DEFAULT_OUT_MD = "runs/partial_authoritative_family_handoff_current.md"

DEFAULT_FAMILY_TARGETS = {
    "ca2": "CARBONIC_ANHYDRASE_2_ZN_BLIND",
    "pxr": "PXR_NR1I2_BLIND",
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    return dict(summary or {}) if isinstance(summary, dict) else {}


def _target_from_payload(family: str, *payloads: dict[str, Any]) -> str:
    for payload in payloads:
        summary = _summary(payload)
        for key in ("target", "target_id", "target_name"):
            value = str(summary.get(key, "")).strip()
            if value:
                return value
    return DEFAULT_FAMILY_TARGETS.get(family, family.upper())


def _row_count_field(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    text = str(value or "").strip()
    if not text:
        return 0
    return len([part for part in text.split(",") if part.strip()])


def _build_family_row(
    *,
    family: str,
    readiness_payload: dict[str, Any],
    policy_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
    packet_payload: dict[str, Any],
    commit_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness_summary = _summary(readiness_payload)
    policy_summary = _summary(policy_payload)
    next_slice_summary = _summary(next_slice_payload)
    packet_summary = _summary(packet_payload)
    if family == "ca2":
        ready_rows = int(readiness_summary["ready_row_count"])
        blocked_rows = int(readiness_summary["blocked_row_count"])
        review_only_rows = int(policy_summary["review_only_rows"])
        defer_rows = int(policy_summary["defer_rows"])
        policy_line = str(policy_summary["next_required_step"]).strip()
        packet_row_count = int(packet_summary["workbook_row_count"])
        target = _target_from_payload(family, packet_payload, readiness_payload, next_slice_payload)
        next_slice_count = int(next_slice_summary["row_count"])
        partial_mode = PARTIAL_AUTHORITATIVE_SAFE_SCOPE
        next_gate = "review_only_negative_closure"
        commit_summary = dict((commit_payload or {}).get("summary", {}) or {})
        direct_conflict_rows = int(commit_summary.get("conflict_review_row_count", 0) or 0)
        no_direct_negative_source_rows = int(commit_summary.get("no_direct_negative_source_row_count", 0) or 0)
        authoritative_negative_ready_rows = int(commit_summary.get("authoritative_apply_allowed_count", 0) or 0)
        closure_scope = "review_only_conflict_or_gap_only"
    else:
        ready_rows = int(readiness_summary["ready_for_apply_row_count"])
        blocked_rows = int(readiness_summary["blocked_row_count"])
        review_only_rows = _row_count_field(policy_summary["review_only_rows"])
        defer_rows = _row_count_field(policy_summary["defer_rows"])
        policy_line = str(policy_summary["policy_line"]).strip()
        packet_row_count = int(packet_summary["workbook_row_count"])
        target = _target_from_payload(family, packet_payload, readiness_payload, next_slice_payload)
        next_slice_count = int(next_slice_summary["row_count"])
        partial_mode = PARTIAL_AUTHORITATIVE_SAFE_SCOPE
        next_gate = "review_only_and_defer_policy_lock"
        direct_conflict_rows = 0
        no_direct_negative_source_rows = 0
        authoritative_negative_ready_rows = 0
        closure_scope = "mixed_review_only_and_defer"
    return {
        "family": family,
        "target": target,
        "partial_mode": partial_mode,
        "ready_rows": ready_rows,
        "blocked_rows": blocked_rows,
        "review_only_rows": review_only_rows,
        "defer_rows": defer_rows,
        "packet_row_count": packet_row_count,
        "next_slice_count": next_slice_count,
        "policy_line": policy_line,
        "next_gate": next_gate,
        "closure_scope": closure_scope,
        "direct_conflict_rows": direct_conflict_rows,
        "no_direct_negative_source_rows": no_direct_negative_source_rows,
        "authoritative_negative_ready_rows": authoritative_negative_ready_rows,
    }


def _build_handoff_rows(family: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    handoff_rows: list[dict[str, Any]] = []
    for row in rows:
        handoff_rows.append(
            {
                "family": family,
                "priority_rank": int(str(row.get("priority_rank", "999"))),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("replacement_ligand_id", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "ready_for_authoritative_apply": str(row.get("ready_for_authoritative_apply", "")).strip() or "no",
                "handoff_bucket": (
                    "review_only_negative"
                    if str(row.get("replacement_is_binder", "")).strip() == "0"
                    else "defer_or_gap"
                ),
            }
        )
    handoff_rows.sort(key=lambda item: (item["family"], int(item["priority_rank"])))
    return handoff_rows


def build_payload(
    *,
    ca2_readiness_payload: dict[str, Any],
    ca2_policy_payload: dict[str, Any],
    ca2_next_slice_payload: dict[str, Any],
    ca2_packet_payload: dict[str, Any],
    ca2_commit_payload: dict[str, Any],
    pxr_readiness_payload: dict[str, Any],
    pxr_policy_payload: dict[str, Any],
    pxr_next_slice_payload: dict[str, Any],
    pxr_packet_payload: dict[str, Any],
) -> dict[str, Any]:
    family_rows = [
        _build_family_row(
            family="ca2",
            readiness_payload=ca2_readiness_payload,
            policy_payload=ca2_policy_payload,
            next_slice_payload=ca2_next_slice_payload,
            packet_payload=ca2_packet_payload,
            commit_payload=ca2_commit_payload,
        ),
        _build_family_row(
            family="pxr",
            readiness_payload=pxr_readiness_payload,
            policy_payload=pxr_policy_payload,
            next_slice_payload=pxr_next_slice_payload,
            packet_payload=pxr_packet_payload,
        ),
    ]
    handoff_rows = _build_handoff_rows("ca2", ca2_next_slice_payload.get("rows", [])) + _build_handoff_rows(
        "pxr", pxr_next_slice_payload.get("rows", [])
    )
    summary = {
        "family_count": 2,
        "partial_authoritative_family_count": 2,
        "ready_row_total": sum(row["ready_rows"] for row in family_rows),
        "blocked_row_total": sum(row["blocked_rows"] for row in family_rows),
        "review_only_row_total": sum(row["review_only_rows"] for row in family_rows),
        "defer_row_total": sum(row["defer_rows"] for row in family_rows),
        "handoff_row_count": len(handoff_rows),
        "ca2_closure_mode": family_rows[0]["closure_scope"] if family_rows and family_rows[0]["family"] == "ca2" else "",
        "ca2_direct_conflict_rows": family_rows[0]["direct_conflict_rows"] if family_rows and family_rows[0]["family"] == "ca2" else 0,
        "ca2_no_direct_negative_source_rows": family_rows[0]["no_direct_negative_source_rows"] if family_rows and family_rows[0]["family"] == "ca2" else 0,
        "ca2_authoritative_negative_ready_rows": family_rows[0]["authoritative_negative_ready_rows"] if family_rows and family_rows[0]["family"] == "ca2" else 0,
        "ca2_authoritative_negative_closure_allowed": False,
        "ca2_remaining_blank_field": "replacement_reference_binding_kcal_mol",
        "next_required_step": "Use this board as the operator-facing handoff for CA2/PXR partial-authoritative expansion work; CA2 is fully closed only at review-only level because five rows have direct conflict and one row still lacks a direct CA2-specific negative source, so keep both families out of full promotion until the listed policy-locked rows are resolved.",
    }
    return {
        "summary": summary,
        "families": family_rows,
        "handoff_rows": handoff_rows,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Partial Authoritative Family Handoff",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- partial_authoritative_family_count: `{summary['partial_authoritative_family_count']}`",
        f"- ready_row_total: `{summary['ready_row_total']}`",
        f"- blocked_row_total: `{summary['blocked_row_total']}`",
        f"- review_only_row_total: `{summary['review_only_row_total']}`",
        f"- defer_row_total: `{summary['defer_row_total']}`",
        f"- handoff_row_count: `{summary['handoff_row_count']}`",
        f"- ca2_closure_mode: `{summary['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_rows: `{summary['ca2_direct_conflict_rows']}`",
        f"- ca2_no_direct_negative_source_rows: `{summary['ca2_no_direct_negative_source_rows']}`",
        f"- ca2_authoritative_negative_ready_rows: `{summary['ca2_authoritative_negative_ready_rows']}`",
        f"- ca2_authoritative_negative_closure_allowed: `{summary['ca2_authoritative_negative_closure_allowed']}`",
        f"- ca2_remaining_blank_field: `{summary['ca2_remaining_blank_field']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Family Board",
        "",
        "| family | target | partial_mode | closure_scope | ready_rows | blocked_rows | review_only_rows | defer_rows | direct_conflict_rows | no_direct_negative_source_rows | authoritative_negative_ready_rows | next_slice_count | next_gate |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["families"]:
        lines.append(
            f"| `{row['family']}` | `{row['target']}` | `{row['partial_mode']}` | `{row['closure_scope']}` | {row['ready_rows']} | {row['blocked_rows']} | "
            f"{row['review_only_rows']} | {row['defer_rows']} | {row['direct_conflict_rows']} | {row['no_direct_negative_source_rows']} | "
            f"{row['authoritative_negative_ready_rows']} | {row['next_slice_count']} | `{row['next_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Handoff Rows",
            "",
            "| family | priority_rank | packet_step | ligand | binder | assay_type_honesty | next_required_action | ready_for_authoritative_apply |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["handoff_rows"]:
        lines.append(
            f"| `{row['family']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['ligand']}` | {row['replacement_is_binder']} | "
            f"`{row['assay_type_honesty']}` | `{row['next_required_action']}` | `{row['ready_for_authoritative_apply']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2/PXR partial-authoritative handoff board.")
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--ca2-policy-json", default=DEFAULT_CA2_POLICY_JSON)
    parser.add_argument("--ca2-next-slice-json", default=DEFAULT_CA2_NEXT_SLICE_JSON)
    parser.add_argument("--ca2-packet-json", default=DEFAULT_CA2_PACKET_JSON)
    parser.add_argument("--ca2-commit-json", default=DEFAULT_CA2_COMMIT_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--pxr-policy-json", default=DEFAULT_PXR_POLICY_JSON)
    parser.add_argument("--pxr-next-slice-json", default=DEFAULT_PXR_NEXT_SLICE_JSON)
    parser.add_argument("--pxr-packet-json", default=DEFAULT_PXR_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        ca2_readiness_payload=_load_json(args.ca2_readiness_json),
        ca2_policy_payload=_load_json(args.ca2_policy_json),
        ca2_next_slice_payload=_load_json(args.ca2_next_slice_json),
        ca2_packet_payload=_load_json(args.ca2_packet_json),
        ca2_commit_payload=_load_json(args.ca2_commit_json),
        pxr_readiness_payload=_load_json(args.pxr_readiness_json),
        pxr_policy_payload=_load_json(args.pxr_policy_json),
        pxr_next_slice_payload=_load_json(args.pxr_next_slice_json),
        pxr_packet_payload=_load_json(args.pxr_packet_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["handoff_rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
