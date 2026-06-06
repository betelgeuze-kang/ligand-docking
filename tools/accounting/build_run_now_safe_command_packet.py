#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PRETEST_HANDOFF_JSON = "runs/pretest_handoff_bundle_current.json"
DEFAULT_PRETEST_CHECKLIST_JSON = "runs/pretest_command_checklist_current.json"
DEFAULT_OUT_JSON = "runs/run_now_safe_command_packet_current.json"
DEFAULT_OUT_CSV = "runs/run_now_safe_command_packet_current.csv"
DEFAULT_OUT_MD = "runs/run_now_safe_command_packet_current.md"


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


def build_payload(pretest_handoff: dict[str, Any], pretest_checklist: dict[str, Any]) -> dict[str, Any]:
    handoff_rows = {
        str(row.get("family", "")).strip(): dict(row)
        for row in pretest_handoff.get("rows", []) or []
        if str(row.get("family", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    for row in pretest_checklist.get("rows", []) or []:
        if str(row.get("execution_lane", "")).strip() != "run_now":
            continue
        family = str(row.get("family", "")).strip()
        handoff = handoff_rows.get(family, {})
        rows.append(
            {
                "packet_rank": 0,
                "family": family,
                "safe_scope_now": str(row.get("safe_scope_now", handoff.get("safe_scope_now", ""))).strip(),
                "blocked_scope": str(row.get("blocked_scope", handoff.get("blocked_scope", ""))).strip(),
                "operator_status": str(handoff.get("operator_status", "")).strip(),
                "artifact_check_command": str(row.get("artifact_check_command", "")).strip(),
                "guardrail_check_command": str(row.get("guardrail_check_command", "")).strip(),
                "do_not_do": str(row.get("do_not_do", "")).strip(),
                "next_action": str(row.get("next_action", handoff.get("next_safe_experiment", ""))).strip(),
                "source_artifact": str(row.get("source_artifact", handoff.get("source_artifact", ""))).strip(),
                "primary_handoff_note": str(handoff.get("primary_handoff_note", "")).strip(),
            }
        )

    rows.sort(key=lambda row: str(row["family"]))
    family_order = {"gpcr": 1, "idp": 2}
    rows.sort(key=lambda row: family_order.get(str(row["family"]), 999))
    for idx, row in enumerate(rows, start=1):
        row["packet_rank"] = idx

    summary = {
        "run_now_family_count": len(rows),
        "bounded_family_count": len(rows),
        "guardrail_count": len(rows),
        "families": [str(row["family"]) for row in rows],
        "next_required_step": "Run only the bounded families listed here, use the artifact-check and guardrail-check commands before any test launch, and do not cross into blocked scope.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Run-Now Safe Command Packet",
        "",
        f"- run_now_family_count: `{s['run_now_family_count']}`",
        f"- bounded_family_count: `{s['bounded_family_count']}`",
        f"- guardrail_count: `{s['guardrail_count']}`",
        f"- families: `{', '.join(s['families'])}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Safe Command Packet",
        "",
        "| packet_rank | family | safe_scope_now | blocked_scope | operator_status | artifact_check_command | guardrail_check_command | do_not_do |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['packet_rank']} | `{row['family']}` | `{row['safe_scope_now']}` | `{row['blocked_scope']}` | "
            f"`{row['operator_status']}` | `{row['artifact_check_command']}` | `{row['guardrail_check_command']}` | `{row['do_not_do']}` |"
        )
    lines.extend(
        [
            "",
            "## Handoff Notes",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['family']}`: {row['primary_handoff_note']}")
        lines.append(f"- `{row['family']}` next: {row['next_action']}")
        lines.append(f"- `{row['family']}` source: `{row['source_artifact']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a run-now safe-command packet from pretest handoff and checklist artifacts.")
    parser.add_argument("--pretest-handoff-json", default=DEFAULT_PRETEST_HANDOFF_JSON)
    parser.add_argument("--pretest-checklist-json", default=DEFAULT_PRETEST_CHECKLIST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pretest_handoff_json),
        _load_json(args.pretest_checklist_json),
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
