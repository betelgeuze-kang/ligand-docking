#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import MEASURED_NOOP_SAFE_SCOPE

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SEQUENCE_JSON = "runs/pretest_execution_sequence_note_current.json"
DEFAULT_CHECKLIST_JSON = "runs/pretest_command_checklist_current.json"
DEFAULT_GPCR_HANDOFF_JSON = "runs/gpcr_handoff_bundle_current.json"
DEFAULT_IDP_SCOPE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_IDP_BLOCKER_JSON = "runs/idp_broader_promotion_blocker_note_current.json"
DEFAULT_CROSS_FAMILY_DECISION_JSON = "runs/cross_family_locked_decoy_shadow_decision_current.json"
DEFAULT_CROSS_FAMILY_STATE_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_OUT_JSON = "runs/run_now_family_sanity_packet_current.json"
DEFAULT_OUT_CSV = "runs/run_now_family_sanity_packet_current.csv"
DEFAULT_OUT_MD = "runs/run_now_family_sanity_packet_current.md"


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


def _row_map(rows: list[dict[str, Any]], key: str = "family") -> dict[str, dict[str, Any]]:
    return {
        str(row.get(key, "")).strip(): dict(row)
        for row in rows
        if str(row.get(key, "")).strip()
    }


def build_payload(
    sequence_payload: dict[str, Any],
    checklist_payload: dict[str, Any],
    gpcr_handoff_payload: dict[str, Any],
    idp_scope_payload: dict[str, Any],
    idp_blocker_payload: dict[str, Any],
    cross_family_decision_payload: dict[str, Any],
    cross_family_state_payload: dict[str, Any],
) -> dict[str, Any]:
    sequence_rows = _row_map(sequence_payload.get("rows", []) or [])
    checklist_rows = _row_map(checklist_payload.get("rows", []) or [])
    decision_family_rows = _row_map(cross_family_decision_payload.get("family_rows", []) or [])
    state_rows = _row_map(cross_family_state_payload.get("rows", []) or [])

    gpcr_sequence = sequence_rows.get("gpcr", {})
    gpcr_check = checklist_rows.get("gpcr", {})
    gpcr_summary = dict(gpcr_handoff_payload.get("summary", {}) or {})

    idp_sequence = sequence_rows.get("idp", {})
    idp_check = checklist_rows.get("idp", {})
    idp_scope = dict(idp_scope_payload.get("summary", {}) or {})
    idp_blocker = dict(idp_blocker_payload.get("summary", {}) or {})

    decision_summary = dict(cross_family_decision_payload.get("summary", {}) or {})

    rows = [
        {
            "sequence_order": 1,
            "family": "gpcr",
            "sanity_lane": "run_now_endpoint",
            "safe_scope_now": str(gpcr_sequence.get("safe_scope_now", "")).strip(),
            "blocked_scope": str(gpcr_sequence.get("blocked_scope", "")).strip(),
            "artifact_check_command": str(gpcr_check.get("artifact_check_command", "")).strip(),
            "guardrail_check_command": str(gpcr_check.get("guardrail_check_command", "")).strip(),
            "do_not_do": str(gpcr_check.get("do_not_do", "")).strip(),
            "operator_note": str(gpcr_summary.get("next_required_step", "")).strip(),
            "source_artifact": "runs/gpcr_handoff_bundle_current.md",
        },
        {
            "sequence_order": 2,
            "family": "ion_channel",
            "sanity_lane": "measured_noop_shadow",
            "safe_scope_now": MEASURED_NOOP_SAFE_SCOPE,
            "blocked_scope": "non_noop_shadow_changes_or_router_like_promotion",
            "artifact_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md",
            "guardrail_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/cross_family_residual_shadow_layer_current.md",
            "do_not_do": "Do not add non-noop residual/apply/router logic to ion_channel before a new measured family decision explicitly allows it.",
            "operator_note": str(state_rows.get("ion_channel", {}).get("next_required_step", "")).strip()
            or str(decision_summary.get("next_required_step", "")).strip(),
            "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md",
        },
        {
            "sequence_order": 3,
            "family": "kinase",
            "sanity_lane": "measured_noop_shadow",
            "safe_scope_now": MEASURED_NOOP_SAFE_SCOPE,
            "blocked_scope": "non_noop_shadow_changes_or_router_like_promotion",
            "artifact_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md",
            "guardrail_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/cross_family_residual_shadow_layer_current.md",
            "do_not_do": "Do not add non-noop residual/apply/router logic to kinase before a new measured family decision explicitly allows it.",
            "operator_note": str(state_rows.get("kinase", {}).get("next_required_step", "")).strip()
            or str(decision_summary.get("next_required_step", "")).strip(),
            "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md",
        },
        {
            "sequence_order": 4,
            "family": "idp",
            "sanity_lane": "run_now_controlled_shadow_only",
            "safe_scope_now": str(idp_sequence.get("safe_scope_now", "")).strip(),
            "blocked_scope": str(idp_sequence.get("blocked_scope", "")).strip(),
            "artifact_check_command": str(idp_check.get("artifact_check_command", "")).strip(),
            "guardrail_check_command": str(idp_check.get("guardrail_check_command", "")).strip(),
            "do_not_do": str(idp_check.get("do_not_do", "")).strip(),
            "operator_note": (
                f"{str(idp_scope.get('guardrail', '')).strip()} "
                f"{str(idp_blocker.get('next_required_step', '')).strip()}"
            ).strip(),
            "source_artifact": "runs/idp_pretest_scope_note_current.md",
        },
    ]

    summary = {
        "family_count": len(rows),
        "command_row_count": len(rows),
        "run_now_family_count": sum(1 for row in rows if row["sanity_lane"].startswith("run_now")),
        "measured_noop_family_count": sum(1 for row in rows if row["sanity_lane"] == "measured_noop_shadow"),
        "direct_sequence_run_now_count": sum(
            1
            for family in ("gpcr", "idp")
            if str(sequence_rows.get(family, {}).get("execution_lane", "")).strip() == "run_now"
        ),
        "ion_kinase_decision": str(decision_summary.get("decision", "")).strip(),
        "next_required_step": (
            "Use this operator packet before any new run. GPCR and IDP are the only bounded run-now "
            "lanes here; ion_channel and kinase stay measured noop-shadow sanity lanes only."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Run-Now Family Sanity Packet",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- command_row_count: `{summary['command_row_count']}`",
        f"- run_now_family_count: `{summary['run_now_family_count']}`",
        f"- measured_noop_family_count: `{summary['measured_noop_family_count']}`",
        f"- direct_sequence_run_now_count: `{summary['direct_sequence_run_now_count']}`",
        f"- ion_kinase_decision: `{summary['ion_kinase_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Operator Packet",
        "",
        "| sequence_order | family | sanity_lane | safe_scope_now | blocked_scope | artifact_check_command | guardrail_check_command | do_not_do |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['sequence_order']} | `{row['family']}` | `{row['sanity_lane']}` | "
            f"`{row['safe_scope_now']}` | `{row['blocked_scope']}` | "
            f"`{row['artifact_check_command']}` | `{row['guardrail_check_command']}` | {row['do_not_do']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['family']}`: {row['operator_note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a run-now family sanity packet for GPCR, ion_channel, kinase, and IDP.")
    parser.add_argument("--sequence-json", default=DEFAULT_SEQUENCE_JSON)
    parser.add_argument("--checklist-json", default=DEFAULT_CHECKLIST_JSON)
    parser.add_argument("--gpcr-handoff-json", default=DEFAULT_GPCR_HANDOFF_JSON)
    parser.add_argument("--idp-scope-json", default=DEFAULT_IDP_SCOPE_JSON)
    parser.add_argument("--idp-blocker-json", default=DEFAULT_IDP_BLOCKER_JSON)
    parser.add_argument("--cross-family-decision-json", default=DEFAULT_CROSS_FAMILY_DECISION_JSON)
    parser.add_argument("--cross-family-state-json", default=DEFAULT_CROSS_FAMILY_STATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.sequence_json),
        _load_json(args.checklist_json),
        _load_json(args.gpcr_handoff_json),
        _load_json(args.idp_scope_json),
        _load_json(args.idp_blocker_json),
        _load_json(args.cross_family_decision_json),
        _load_json(args.cross_family_state_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
