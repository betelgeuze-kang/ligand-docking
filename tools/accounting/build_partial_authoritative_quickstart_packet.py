#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import PARTIAL_AUTHORITATIVE_SAFE_SCOPE

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_CONSOLE_JSON = "runs/partial_authoritative_operator_console_current.json"
DEFAULT_FAMILY_HANDOFF_JSON = "runs/partial_authoritative_family_handoff_current.json"
DEFAULT_CA2_WORKBENCH_JSON = "runs/ca2_reviewer_workbench_current.json"
DEFAULT_PXR_WORKBENCH_JSON = "runs/pxr_reviewer_workbench_current.json"
DEFAULT_CA2_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_PXR_DAY_PLAN_JSON = "runs/pxr_evidence_closure_day_plan_current.json"
DEFAULT_CA2_NEXT_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_PXR_NEXT_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PXR_CONFIRMATION_JSON = "runs/pxr_exact_source_confirmation_packet_current.json"
DEFAULT_PXR_CONFLICT_RESOLVER_JSON = "runs/pxr_conflict_resolver_packet_current.json"
DEFAULT_PXR_QUANTITATIVE_PROVENANCE_JSON = "runs/pxr_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/partial_authoritative_quickstart_packet_current.json"
DEFAULT_OUT_CSV = "runs/partial_authoritative_quickstart_packet_current.csv"
DEFAULT_OUT_MD = "runs/partial_authoritative_quickstart_packet_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
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


def _family_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("family", "")).strip().lower(): dict(row)
        for row in rows
        if str(row.get("family", "")).strip()
    }


def _top_items(rows: list[dict[str, Any]], limit: int = 2) -> str:
    bits = []
    for row in rows[:limit]:
        ligand = str(row.get("ligand") or row.get("replacement_ligand_id") or "").strip()
        step = str(row.get("packet_step", "")).strip()
        action = str(row.get("next_required_action", "")).strip()
        if ligand and step:
            bits.append(f"{step}:{ligand}:{action}")
    return "; ".join(bits)


def build_payload(
    operator_console: dict[str, Any],
    family_handoff: dict[str, Any],
    ca2_workbench: dict[str, Any],
    pxr_workbench: dict[str, Any],
    ca2_day_plan: dict[str, Any],
    pxr_day_plan: dict[str, Any],
    ca2_next_slice: dict[str, Any],
    pxr_next_slice: dict[str, Any],
    ca2_readiness: dict[str, Any],
    pxr_readiness: dict[str, Any],
    pxr_confirmation_packet: dict[str, Any] | None = None,
    pxr_quantitative_provenance_packet: dict[str, Any] | None = None,
    pxr_conflict_resolver_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    family_rows = _family_map(family_handoff.get("families", []) or [])
    console_rows = operator_console.get("console_rows", []) or []

    ca2_family = family_rows.get("ca2", {})
    pxr_family = family_rows.get("pxr", {})
    ca2_workbench_summary = dict(ca2_workbench.get("summary", {}) or {})
    pxr_workbench_summary = dict(pxr_workbench.get("summary", {}) or {})
    ca2_day_summary = dict(ca2_day_plan.get("summary", {}) or {})
    pxr_day_summary = dict(pxr_day_plan.get("summary", {}) or {})
    ca2_readiness_summary = dict(ca2_readiness.get("summary", {}) or {})
    pxr_readiness_summary = dict(pxr_readiness.get("summary", {}) or {}).get("summary", dict(pxr_readiness.get("summary", {}) or {}))
    pxr_confirmation_summary = dict((pxr_confirmation_packet or {}).get("summary", {}) or {})
    pxr_quantitative_summary = dict((pxr_quantitative_provenance_packet or {}).get("summary", {}) or {})
    pxr_conflict_summary = dict((pxr_conflict_resolver_packet or {}).get("summary", {}) or {})
    if not pxr_readiness_summary:
        pxr_readiness_summary = dict(pxr_readiness.get("summary", {}) or {})

    pxr_artifact_check_command = (
        "sed -n '1,220p' runs/pxr_packet_fill_readiness_current.md && printf '\\n---\\n' "
        "&& sed -n '1,220p' runs/pxr_reviewer_workbench_current.md"
    )
    if pxr_confirmation_summary:
        pxr_artifact_check_command += (
            " && printf '\\n---\\n' && sed -n '1,220p' runs/pxr_exact_source_confirmation_packet_current.md"
        )
    if pxr_conflict_summary:
        pxr_artifact_check_command += (
            " && printf '\\n---\\n' && sed -n '1,220p' runs/pxr_conflict_resolver_packet_current.md"
        )
    if pxr_quantitative_summary:
        pxr_artifact_check_command += (
            " && printf '\\n---\\n' && sed -n '1,220p' runs/pxr_quantitative_provenance_packet_current.md"
        )

    family_quick_rows = [
        {
            "family_rank": 1,
            "family": "ca2",
            "lane": "partial_authoritative",
            "safe_scope_now": str(ca2_family.get("partial_mode", PARTIAL_AUTHORITATIVE_SAFE_SCOPE)),
            "ready_rows": int(ca2_family.get("ready_rows", ca2_readiness_summary.get("ready_row_count", 0)) or 0),
            "blocked_rows": int(ca2_family.get("blocked_rows", ca2_readiness_summary.get("blocked_row_count", 0)) or 0),
            "day_scope": str(ca2_family.get("next_gate", "review_only_negative_closure")),
            "artifact_check_command": "sed -n '1,200p' runs/ca2_packet_replacement_readiness_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/ca2_reviewer_workbench_current.md",
            "guardrail_check_command": "sed -n '1,220p' runs/ca2_evidence_closure_day_plan_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/ca2_next_verification_slice_current.md",
            "no_go_rule": "Do not promote beyond the ready CA2 binder tranche or inject quantitative non-binder values automatically.",
            "operator_note": str(ca2_family.get("policy_line", "")) or str(ca2_workbench_summary.get("next_required_step", "")),
            "closure_mode": str(ca2_workbench_summary.get("closure_mode", "review_only_conflict_closure")).strip(),
            "direct_conflict_row_count": int(ca2_workbench_summary.get("direct_conflict_row_count", 0) or 0),
            "no_direct_negative_found_count": int(ca2_workbench_summary.get("no_direct_negative_found_count", 0) or 0),
            "authoritative_negative_closure_allowed": bool(ca2_workbench_summary.get("authoritative_negative_closure_allowed", False)),
            "top_today_items": _top_items(ca2_day_plan.get("today_focus_rows", []) or ca2_next_slice.get("rows", []) or [], limit=3),
            "source_artifact": "runs/partial_authoritative_operator_console_current.md",
        },
        {
            "family_rank": 2,
            "family": "pxr",
            "lane": "partial_authoritative",
            "safe_scope_now": str(pxr_family.get("partial_mode", PARTIAL_AUTHORITATIVE_SAFE_SCOPE)),
            "ready_rows": int(pxr_family.get("ready_rows", pxr_readiness_summary.get("ready_for_apply_row_count", 0)) or 0),
            "blocked_rows": int(pxr_family.get("blocked_rows", pxr_readiness_summary.get("blocked_row_count", 0)) or 0),
            "day_scope": str(pxr_family.get("next_gate", "review_only_and_defer_policy_lock")),
            "artifact_check_command": pxr_artifact_check_command,
            "guardrail_check_command": "sed -n '1,220p' runs/pxr_evidence_closure_day_plan_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/pxr_next_verification_slice_current.md",
            "no_go_rule": "Do not auto-promote deferred PXR rows or fill unresolved target-specific evidence gaps with proxy values.",
            "operator_note": str(pxr_family.get("policy_line", "")) or str(pxr_workbench_summary.get("next_required_step", "")),
            "top_today_items": _top_items(pxr_day_plan.get("rows", []) or pxr_next_slice.get("rows", []) or [], limit=3),
            "source_artifact": "runs/partial_authoritative_operator_console_current.md",
        },
    ]

    quick_rows = []
    for row in console_rows:
        fam = str(row.get("family", "")).strip().lower()
        if fam not in {"ca2", "pxr"}:
            continue
        quick_rows.append(
            {
                "family": fam,
                "console_rank": row.get("console_rank", ""),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "handoff_bucket": str(row.get("handoff_bucket", row.get("band", ""))).strip(),
            }
        )

    payload = {
        "summary": {
            "family_count": 2,
            "quickstart_family_count": 2,
            "console_row_count": len(quick_rows),
            "ca2_ready_rows": int(ca2_family.get("ready_rows", ca2_readiness_summary.get("ready_row_count", 0)) or 0),
            "pxr_ready_rows": int(pxr_family.get("ready_rows", pxr_readiness_summary.get("ready_for_apply_row_count", 0)) or 0),
            "ca2_today_focus_count": int(ca2_day_summary.get("today_focus_count", 0) or 0),
            "ca2_closure_mode": str(ca2_workbench_summary.get("closure_mode", "review_only_conflict_closure")).strip(),
            "ca2_direct_conflict_row_count": int(ca2_workbench_summary.get("direct_conflict_row_count", 0) or 0),
            "ca2_no_direct_negative_found_count": int(ca2_workbench_summary.get("no_direct_negative_found_count", 0) or 0),
            "ca2_authoritative_negative_closure_allowed": bool(ca2_workbench_summary.get("authoritative_negative_closure_allowed", False)),
            "pxr_first_hour_count": int(pxr_day_summary.get("first_hour_count", 0) or 0),
            "pxr_confirmation_focus_count": int(pxr_confirmation_summary.get("row_count", 0) or 0),
            "pxr_supportive_binder_confirmation_count": int(
                pxr_confirmation_summary.get("supportive_binder_confirmation_count", 0) or 0
            ),
            "pxr_conflict_resolver_focus_count": int(pxr_conflict_summary.get("row_count", 0) or 0),
            "pxr_quantitative_provenance_focus_count": int(pxr_quantitative_summary.get("row_count", 0) or 0),
            "next_required_step": "Use CA2 for review-only negative closure and PXR for pending-policy triage; keep both families inside partial-authoritative scope only.",
        },
        "family_rows": family_quick_rows,
        "quick_rows": quick_rows,
    }
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Partial-Authoritative Quickstart Packet",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- quickstart_family_count: `{s['quickstart_family_count']}`",
        f"- console_row_count: `{s['console_row_count']}`",
        f"- ca2_ready_rows: `{s['ca2_ready_rows']}`",
        f"- pxr_ready_rows: `{s['pxr_ready_rows']}`",
        f"- ca2_today_focus_count: `{s['ca2_today_focus_count']}`",
        f"- ca2_closure_mode: `{s['ca2_closure_mode']}`",
        f"- ca2_direct_conflict_row_count: `{s['ca2_direct_conflict_row_count']}`",
        f"- ca2_no_direct_negative_found_count: `{s['ca2_no_direct_negative_found_count']}`",
        f"- ca2_authoritative_negative_closure_allowed: `{s['ca2_authoritative_negative_closure_allowed']}`",
        f"- pxr_first_hour_count: `{s['pxr_first_hour_count']}`",
        f"- pxr_confirmation_focus_count: `{s['pxr_confirmation_focus_count']}`",
        f"- pxr_supportive_binder_confirmation_count: `{s['pxr_supportive_binder_confirmation_count']}`",
        f"- pxr_conflict_resolver_focus_count: `{s['pxr_conflict_resolver_focus_count']}`",
        f"- pxr_quantitative_provenance_focus_count: `{s['pxr_quantitative_provenance_focus_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Family Quickstart",
        "",
        "| family | safe_scope_now | ready_rows | blocked_rows | closure_mode | artifact_check_command | guardrail_check_command | no_go_rule |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["family_rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['safe_scope_now']}` | {row['ready_rows']} | {row['blocked_rows']} | "
            f"`{row.get('closure_mode','')}` | `{row['artifact_check_command']}` | `{row['guardrail_check_command']}` | {row['no_go_rule']} |"
        )
    lines.extend(["", "## Today / Immediate Work Items", "", "| family | rank | packet_step | ligand | next_required_action | recommended_resolution | assay_type_honesty |", "| --- | ---: | --- | --- | --- | --- | --- |"])
    for row in payload["quick_rows"]:
        lines.append(
            f"| `{row['family']}` | {row['console_rank']} | `{row['packet_step']}` | `{row['ligand']}` | "
            f"`{row['next_required_action']}` | `{row['recommended_resolution']}` | `{row['assay_type_honesty']}` |"
        )
    lines.extend(["", "## Operator Notes", ""])
    for row in payload["family_rows"]:
        lines.append(f"- `{row['family']}`: {row['operator_note']}")
        lines.append(f"  top_today_items: `{row['top_today_items']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2/PXR partial-authoritative quickstart packet.")
    parser.add_argument("--operator-console-json", default=DEFAULT_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--family-handoff-json", default=DEFAULT_FAMILY_HANDOFF_JSON)
    parser.add_argument("--ca2-workbench-json", default=DEFAULT_CA2_WORKBENCH_JSON)
    parser.add_argument("--pxr-workbench-json", default=DEFAULT_PXR_WORKBENCH_JSON)
    parser.add_argument("--ca2-day-plan-json", default=DEFAULT_CA2_DAY_PLAN_JSON)
    parser.add_argument("--pxr-day-plan-json", default=DEFAULT_PXR_DAY_PLAN_JSON)
    parser.add_argument("--ca2-next-slice-json", default=DEFAULT_CA2_NEXT_SLICE_JSON)
    parser.add_argument("--pxr-next-slice-json", default=DEFAULT_PXR_NEXT_SLICE_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--pxr-confirmation-json", default=DEFAULT_PXR_CONFIRMATION_JSON)
    parser.add_argument("--pxr-conflict-resolver-json", default=DEFAULT_PXR_CONFLICT_RESOLVER_JSON)
    parser.add_argument("--pxr-quantitative-provenance-json", default=DEFAULT_PXR_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.operator_console_json),
        _load_json(args.family_handoff_json),
        _load_json(args.ca2_workbench_json),
        _load_json(args.pxr_workbench_json),
        _load_json(args.ca2_day_plan_json),
        _load_json(args.pxr_day_plan_json),
        _load_json(args.ca2_next_slice_json),
        _load_json(args.pxr_next_slice_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.pxr_confirmation_json),
        _maybe_load_json(args.pxr_quantitative_provenance_json),
        _maybe_load_json(args.pxr_conflict_resolver_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["quick_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
