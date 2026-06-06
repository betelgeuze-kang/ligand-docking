#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_BUNDLE_JSON = "runs/pretest_handoff_bundle_current.json"
DEFAULT_OUT_JSON = "runs/pretest_execution_sequence_note_current.json"
DEFAULT_OUT_CSV = "runs/pretest_execution_sequence_note_current.csv"
DEFAULT_OUT_MD = "runs/pretest_execution_sequence_note_current.md"


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


def _classify_row(row: dict[str, Any]) -> tuple[str, str]:
    family = str(row.get("family", "")).strip()
    status = str(row.get("operator_status", "")).strip()
    blocked = str(row.get("blocked_scope", "")).strip()

    if family == "gpcr":
        return "run_now", "Run only inside the apply-safe locked-decoy endpoint; do not touch router promotion."
    if family == "idp":
        return "run_now", "Run only the controlled shadow-only commercial-pretest path under rg_sasa_only; keep broader promotion blocked."
    if family in {"non_kinase_enzyme_ca2", "nuclear_receptor_pxr"}:
        return "partial_prep", "Do evidence closure and packet completion only; do not broaden beyond partial-authoritative rows."
    if family == "transporter":
        return "later_blocked", "Keep manual-review only; do not run authoritative apply or reopen donor policy."
    if status or blocked:
        return "later_blocked", "Stay within current safe scope until a clearer operator lane is defined."
    return "later_blocked", "No current execution lane."


def build_payload(bundle_payload: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    handoff_rows = list(bundle_payload.get("rows", []) or [])
    priority = {
        "gpcr": 1,
        "idp": 2,
        "non_kinase_enzyme_ca2": 3,
        "nuclear_receptor_pxr": 4,
        "transporter": 5,
    }

    for row in sorted(handoff_rows, key=lambda r: priority.get(str(r.get("family", "")).strip(), 999)):
        lane, guardrail = _classify_row(row)
        rows.append(
            {
                "sequence_order": priority.get(str(row.get("family", "")).strip(), 999),
                "family": str(row.get("family", "")).strip(),
                "execution_lane": lane,
                "safe_scope_now": str(row.get("safe_scope_now", "")).strip(),
                "blocked_scope": str(row.get("blocked_scope", "")).strip(),
                "guardrail": guardrail,
                "next_action": str(row.get("next_safe_experiment", "")).strip(),
                "source_artifact": str(row.get("source_artifact", "")).strip(),
            }
        )

    summary = {
        "sequence_count": len(rows),
        "run_now_count": sum(1 for row in rows if row["execution_lane"] == "run_now"),
        "partial_prep_count": sum(1 for row in rows if row["execution_lane"] == "partial_prep"),
        "later_blocked_count": sum(1 for row in rows if row["execution_lane"] == "later_blocked"),
        "next_required_step": "Execute only the run_now lanes in order, keep partial_prep lanes focused on evidence closure, and leave later_blocked lanes untouched until their blockers are cleared.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Pretest Execution Sequence Note",
        "",
        f"- sequence_count: `{s['sequence_count']}`",
        f"- run_now_count: `{s['run_now_count']}`",
        f"- partial_prep_count: `{s['partial_prep_count']}`",
        f"- later_blocked_count: `{s['later_blocked_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Ordered Sequence",
        "",
        "| sequence_order | family | execution_lane | safe_scope_now | blocked_scope | guardrail | next_action | source_artifact |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['sequence_order']} | `{row['family']}` | `{row['execution_lane']}` | "
            f"`{row['safe_scope_now']}` | `{row['blocked_scope']}` | {row['guardrail']} | {row['next_action']} | `{row['source_artifact']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an ordered, guardrailed execution sequence from the pretest handoff bundle.")
    parser.add_argument("--handoff-bundle-json", default=DEFAULT_HANDOFF_BUNDLE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.handoff_bundle_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
