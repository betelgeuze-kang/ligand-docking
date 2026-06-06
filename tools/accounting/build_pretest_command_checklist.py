#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SEQUENCE_JSON = "runs/pretest_execution_sequence_note_current.json"
DEFAULT_OUT_JSON = "runs/pretest_command_checklist_current.json"
DEFAULT_OUT_CSV = "runs/pretest_command_checklist_current.csv"
DEFAULT_OUT_MD = "runs/pretest_command_checklist_current.md"


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


def _check_row(sequence_row: dict[str, Any]) -> dict[str, Any]:
    family = str(sequence_row.get("family", "")).strip()
    source_artifact = str(sequence_row.get("source_artifact", "")).strip()
    lane = str(sequence_row.get("execution_lane", "")).strip()
    blocked_scope = str(sequence_row.get("blocked_scope", "")).strip()

    artifact_cmd = f"sed -n '1,200p' {source_artifact}"
    if family == "gpcr":
        guard_cmd = "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md"
        do_not = "Do not launch any 100k/router GPCR run."
    elif family == "idp":
        if source_artifact.endswith("runs/idp_broader_promotion_resolution_current.md"):
            guard_cmd = "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_broader_shadow_result_current.md"
            do_not = "Do not broaden beyond the admitted one-wider shadow-safe lane, change the frozen 8-target roster, enable ranking/gate override, or claim commercialization beyond that bounded lane."
        else:
            guard_cmd = "sed -n '1,220p' runs/idp_broader_shadow_decision_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_broader_shadow_result_current.md"
            do_not = "Do not broaden beyond the controlled shadow-only commercial-pretest scope or enable ranking/gate override."
    elif family == "non_kinase_enzyme_ca2":
        guard_cmd = "sed -n '1,200p' runs/ca2_packet_replacement_readiness_current.md && printf '\\n---\\n' && sed -n '1,160p' runs/ca2_next_verification_slice_current.md"
        do_not = "Do not promote beyond partial-authoritative CA2 rows."
    elif family == "nuclear_receptor_pxr":
        guard_cmd = "sed -n '1,200p' runs/pxr_pending_policy_note_current.md && printf '\\n---\\n' && sed -n '1,200p' runs/pxr_packet_fill_readiness_current.md"
        do_not = "Do not auto-promote deferred PXR rows."
    elif family == "transporter":
        guard_cmd = "sed -n '1,220p' runs/transporter_manual_review_dashboard_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/transporter_manual_verdict_packets_current.md"
        do_not = "Do not run authoritative transporter apply or reopen donor policy."
    else:
        guard_cmd = artifact_cmd
        do_not = ""

    return {
        "sequence_order": sequence_row.get("sequence_order", ""),
        "family": family,
        "execution_lane": lane,
        "artifact_check_command": artifact_cmd,
        "guardrail_check_command": guard_cmd,
        "safe_scope_now": str(sequence_row.get("safe_scope_now", "")).strip(),
        "blocked_scope": blocked_scope,
        "do_not_do": do_not,
        "next_action": str(sequence_row.get("next_action", "")).strip(),
        "source_artifact": source_artifact,
    }


def build_payload(sequence_payload: dict[str, Any]) -> dict[str, Any]:
    rows = [_check_row(row) for row in sequence_payload.get("rows", []) or []]
    summary = {
        "check_count": len(rows),
        "run_now_check_count": sum(1 for row in rows if row["execution_lane"] == "run_now"),
        "partial_prep_check_count": sum(1 for row in rows if row["execution_lane"] == "partial_prep"),
        "later_blocked_check_count": sum(1 for row in rows if row["execution_lane"] == "later_blocked"),
        "next_required_step": "Use these commands to verify the current safe scope before any new test. They are artifact-check commands only and should not launch new runs.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Pretest Command Checklist",
        "",
        f"- check_count: `{s['check_count']}`",
        f"- run_now_check_count: `{s['run_now_check_count']}`",
        f"- partial_prep_check_count: `{s['partial_prep_check_count']}`",
        f"- later_blocked_check_count: `{s['later_blocked_check_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Checklist",
        "",
        "| sequence_order | family | execution_lane | artifact_check_command | guardrail_check_command | do_not_do |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['sequence_order']} | `{row['family']}` | `{row['execution_lane']}` | "
            f"`{row['artifact_check_command']}` | `{row['guardrail_check_command']}` | {row['do_not_do']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an artifact-check command checklist from the pretest execution sequence note.")
    parser.add_argument("--sequence-json", default=DEFAULT_SEQUENCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.sequence_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
