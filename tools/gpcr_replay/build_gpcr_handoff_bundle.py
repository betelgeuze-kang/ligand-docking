#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PRETEST_JSON = "runs/gpcr_pretest_handoff_packet_current.json"
DEFAULT_ENDPOINT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_ROUTER_PAUSE_JSON = "runs/gpcr_router_pause_note_current.json"
DEFAULT_PROGRESSION_JSON = "runs/gpcr_residual_progression_comparison_current.json"
DEFAULT_ENDPOINT_NOTE_JSON = "runs/gpcr_residual_chembl50_v4_endpoint_note_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_handoff_bundle_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_handoff_checklist_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_handoff_bundle_current.md"


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


def build_payload(
    pretest_payload: dict[str, Any],
    endpoint_payload: dict[str, Any],
    router_pause_payload: dict[str, Any],
    progression_payload: dict[str, Any],
    endpoint_note_payload: dict[str, Any],
) -> dict[str, Any]:
    pretest = dict(pretest_payload.get("summary", {}) or {})
    endpoint = dict(endpoint_payload.get("summary", {}) or {})
    router = dict(router_pause_payload.get("summary", {}) or {})
    progression = dict(progression_payload.get("summary", {}) or {})
    endpoint_note = dict(endpoint_note_payload.get("summary", {}) or {})

    checklist_rows = [
        {
            "order": 1,
            "check_id": "safe_scope_now",
            "status": "ready",
            "operator_action": "Only run GPCR within the locked-decoy apply-safe endpoint scope.",
            "expected_state": str(pretest.get("safe_now", "") or "chembl50_v4_locked_decoy_apply_safe_endpoint"),
        },
        {
            "order": 2,
            "check_id": "router_block",
            "status": "blocked",
            "operator_action": "Do not run or advertise GPCR 100k router promotion.",
            "expected_state": str(pretest.get("blocked_now", "") or "100k_router_promotion"),
        },
        {
            "order": 3,
            "check_id": "core_parity",
            "status": "ready" if progression.get("core_v4_apply_preserves_baseline", False) else "watch",
            "operator_action": "Preserve gpcr_core_full baseline parity in any follow-up locked-decoy variant.",
            "expected_state": f"core_v4_apply_preserves_baseline={progression.get('core_v4_apply_preserves_baseline', False)}",
        },
        {
            "order": 4,
            "check_id": "chembl50_signal",
            "status": "ready" if progression.get("chembl50_v4_apply_has_ef1_gain", False) else "watch",
            "operator_action": "Keep the chembl50 EF1 gain while trying to remove the remaining PR regression.",
            "expected_state": f"chembl50_v4_apply_has_ef1_gain={progression.get('chembl50_v4_apply_has_ef1_gain', False)}",
        },
        {
            "order": 5,
            "check_id": "next_safe_experiment",
            "status": "queued",
            "operator_action": str(pretest.get("next_safe_experiment", "") or "Run another locked-decoy GPCR variant only."),
            "expected_state": str(endpoint_note.get("decision", "") or endpoint.get("next_required_step", "")),
        },
    ]

    summary = {
        "safe_now": str(pretest.get("safe_now", "") or "chembl50_v4_locked_decoy_apply_safe_endpoint"),
        "blocked_now": str(pretest.get("blocked_now", "") or "100k_router_promotion"),
        "endpoint_status": str(endpoint.get("endpoint_status", "") or ""),
        "router_status": str(router.get("router_status", "") or ""),
        "core_v4_apply_preserves_baseline": bool(progression.get("core_v4_apply_preserves_baseline", False)),
        "chembl50_v4_apply_has_ef1_gain": bool(progression.get("chembl50_v4_apply_has_ef1_gain", False)),
        "check_count": len(checklist_rows),
        "ready_check_count": sum(1 for row in checklist_rows if row["status"] == "ready"),
        "blocked_check_count": sum(1 for row in checklist_rows if row["status"] == "blocked"),
        "next_required_step": "Use this bundle as the GPCR operator handoff surface before any new test. Stay inside the apply-safe endpoint scope and keep router promotion blocked.",
    }
    references = [
        "runs/gpcr_pretest_handoff_packet_current.md",
        "runs/gpcr_apply_safe_endpoint_current.md",
        "runs/gpcr_router_pause_note_current.md",
        "runs/gpcr_residual_progression_comparison_current.md",
        "runs/gpcr_residual_chembl50_v4_endpoint_note_current.md",
    ]
    return {"summary": summary, "checklist_rows": checklist_rows, "references": references}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Handoff Bundle",
        "",
        f"- safe_now: `{s['safe_now']}`",
        f"- blocked_now: `{s['blocked_now']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- router_status: `{s['router_status']}`",
        f"- core_v4_apply_preserves_baseline: `{s['core_v4_apply_preserves_baseline']}`",
        f"- chembl50_v4_apply_has_ef1_gain: `{s['chembl50_v4_apply_has_ef1_gain']}`",
        f"- check_count: `{s['check_count']}`",
        f"- ready_check_count: `{s['ready_check_count']}`",
        f"- blocked_check_count: `{s['blocked_check_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Checklist",
        "",
        "| order | check_id | status | operator_action | expected_state |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["checklist_rows"]:
        lines.append(
            f"| {row['order']} | `{row['check_id']}` | `{row['status']}` | {row['operator_action']} | `{row['expected_state']}` |"
        )
    lines.extend(["", "## References", ""])
    for ref in payload["references"]:
        lines.append(f"- `{ref}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GPCR-only operator-facing handoff bundle and checklist.")
    parser.add_argument("--pretest-json", default=DEFAULT_PRETEST_JSON)
    parser.add_argument("--endpoint-json", default=DEFAULT_ENDPOINT_JSON)
    parser.add_argument("--router-pause-json", default=DEFAULT_ROUTER_PAUSE_JSON)
    parser.add_argument("--progression-json", default=DEFAULT_PROGRESSION_JSON)
    parser.add_argument("--endpoint-note-json", default=DEFAULT_ENDPOINT_NOTE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pretest_json),
        _load_json(args.endpoint_json),
        _load_json(args.router_pause_json),
        _load_json(args.progression_json),
        _load_json(args.endpoint_note_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["checklist_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
