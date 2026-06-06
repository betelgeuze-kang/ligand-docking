#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUICKSTART_JSON = "runs/partial_authoritative_quickstart_packet_current.json"
DEFAULT_REVIEWER_CONSOLE_JSON = "runs/partial_authoritative_reviewer_console_current.json"
DEFAULT_HANDOFF_JSON = "runs/partial_authoritative_family_handoff_current.json"
DEFAULT_CA2_DRAFT_JSON = "runs/ca2_packet_replacement_draft_apply_current.json"
DEFAULT_CA2_COMMIT_JSON = "runs/ca2_verified_binding_promotion_current.json"
DEFAULT_PXR_DRAFT_JSON = "runs/pxr_packet_replacement_draft_apply_current.json"
DEFAULT_PXR_COMMIT_JSON = "runs/pxr_verified_binding_promotion_current.json"
DEFAULT_OUT_JSON = "runs/partial_authoritative_launchboard_current.json"
DEFAULT_OUT_CSV = "runs/partial_authoritative_launchboard_current.csv"
DEFAULT_OUT_MD = "runs/partial_authoritative_launchboard_current.md"


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


def _family_lookup(rows: list[dict[str, Any]], key: str = "family") -> dict[str, dict[str, Any]]:
    return {
        str(row.get(key, "")).strip(): dict(row)
        for row in rows
        if str(row.get(key, "")).strip()
    }


def _commit_stats(commit_payload: dict[str, Any]) -> tuple[int, int]:
    summary = commit_payload.get("summary", {})
    return int(summary.get("promoted_row_count", 0)), int(summary.get("ready_row_count", 0))


def _draft_stats(draft_payload: dict[str, Any]) -> tuple[int, int]:
    summary = draft_payload.get("summary", {})
    return int(summary.get("draft_promoted_row_count", 0)), int(summary.get("replacement_row_count", 0))


def build_payload(
    *,
    quickstart_payload: dict[str, Any],
    reviewer_console_payload: dict[str, Any],
    handoff_payload: dict[str, Any],
    ca2_draft_payload: dict[str, Any],
    ca2_commit_payload: dict[str, Any],
    pxr_draft_payload: dict[str, Any],
    pxr_commit_payload: dict[str, Any],
) -> dict[str, Any]:
    quickstart = _family_lookup(quickstart_payload.get("family_rows", []))
    reviewer = _family_lookup(reviewer_console_payload.get("family_rows", []))
    handoff = _family_lookup(handoff_payload.get("families", []))

    ca2_commit_promoted, ca2_commit_ready = _commit_stats(ca2_commit_payload)
    pxr_commit_promoted, pxr_commit_ready = _commit_stats(pxr_commit_payload)
    ca2_draft_promoted, ca2_draft_rows = _draft_stats(ca2_draft_payload)
    pxr_draft_promoted, pxr_draft_rows = _draft_stats(pxr_draft_payload)

    family_rows = [
        {
            "launch_rank": 1,
            "family": "ca2",
            "safe_scope_now": str(quickstart["ca2"]["safe_scope_now"]),
            "ready_rows": int(quickstart["ca2"]["ready_rows"]),
            "blocked_rows": int(quickstart["ca2"]["blocked_rows"]),
            "review_focus": str(reviewer["ca2"]["review_focus"]),
            "draft_promoted_rows": ca2_draft_promoted,
            "draft_total_rows": ca2_draft_rows,
            "commit_promoted_rows": ca2_commit_promoted,
            "commit_ready_rows": ca2_commit_ready,
            "next_gate": str(handoff["ca2"]["next_gate"]),
            "open_first_command": str(quickstart["ca2"]["artifact_check_command"]),
            "guardrail_command": str(quickstart["ca2"]["guardrail_check_command"]),
            "source_artifact": str(quickstart["ca2"]["source_artifact"]),
            "launch_note": str(quickstart["ca2"]["operator_note"]),
        },
        {
            "launch_rank": 2,
            "family": "pxr",
            "safe_scope_now": str(quickstart["pxr"]["safe_scope_now"]),
            "ready_rows": int(quickstart["pxr"]["ready_rows"]),
            "blocked_rows": int(quickstart["pxr"]["blocked_rows"]),
            "review_focus": str(reviewer["pxr"]["review_focus"]),
            "draft_promoted_rows": pxr_draft_promoted,
            "draft_total_rows": pxr_draft_rows,
            "commit_promoted_rows": pxr_commit_promoted,
            "commit_ready_rows": pxr_commit_ready,
            "next_gate": str(handoff["pxr"]["next_gate"]),
            "open_first_command": str(quickstart["pxr"]["artifact_check_command"]),
            "guardrail_command": str(quickstart["pxr"]["guardrail_check_command"]),
            "source_artifact": str(quickstart["pxr"]["source_artifact"]),
            "launch_note": str(quickstart["pxr"]["operator_note"]),
        },
    ]

    launch_rows: list[dict[str, Any]] = []
    for row in quickstart_payload.get("quick_rows", []):
        family = str(row.get("family", "")).strip()
        if family not in {"ca2", "pxr"}:
            continue
        launch_rows.append(
            {
                "family": family,
                "console_rank": int(row.get("console_rank", 999)),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "handoff_bucket": str(row.get("handoff_bucket", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
            }
        )
    launch_rows.sort(key=lambda item: (0 if item["family"] == "ca2" else 1, item["console_rank"]))

    summary = {
        "family_count": 2,
        "launchable_family_count": 2,
        "total_ready_rows": sum(row["ready_rows"] for row in family_rows),
        "total_blocked_rows": sum(row["blocked_rows"] for row in family_rows),
        "total_commit_promoted_rows": sum(row["commit_promoted_rows"] for row in family_rows),
        "total_draft_promoted_rows": sum(row["draft_promoted_rows"] for row in family_rows),
        "launch_row_count": len(launch_rows),
        "next_required_step": "Open the family launch row first, then use the paired guardrail command and commit/draft packet counts to stay inside partial-authoritative scope only.",
    }
    return {"summary": summary, "family_rows": family_rows, "launch_rows": launch_rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Partial-Authoritative Launchboard",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- launchable_family_count: `{summary['launchable_family_count']}`",
        f"- total_ready_rows: `{summary['total_ready_rows']}`",
        f"- total_blocked_rows: `{summary['total_blocked_rows']}`",
        f"- total_commit_promoted_rows: `{summary['total_commit_promoted_rows']}`",
        f"- total_draft_promoted_rows: `{summary['total_draft_promoted_rows']}`",
        f"- launch_row_count: `{summary['launch_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Family Launch Rows",
        "",
        "| launch_rank | family | safe_scope_now | ready_rows | blocked_rows | draft_promoted_rows | commit_promoted_rows | next_gate |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["family_rows"]:
        lines.append(
            f"| {row['launch_rank']} | `{row['family']}` | `{row['safe_scope_now']}` | {row['ready_rows']} | {row['blocked_rows']} | "
            f"{row['draft_promoted_rows']} | {row['commit_promoted_rows']} | `{row['next_gate']}` |"
        )
    lines.extend(
        [
            "",
            "## Immediate Launch Queue",
            "",
            "| family | console_rank | packet_step | ligand | handoff_bucket | next_required_action | recommended_resolution | assay_type_honesty |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["launch_rows"]:
        lines.append(
            f"| `{row['family']}` | {row['console_rank']} | `{row['packet_step']}` | `{row['ligand']}` | `{row['handoff_bucket']}` | "
            f"`{row['next_required_action']}` | `{row['recommended_resolution']}` | `{row['assay_type_honesty']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2/PXR partial-authoritative launchboard.")
    parser.add_argument("--quickstart-json", default=DEFAULT_QUICKSTART_JSON)
    parser.add_argument("--reviewer-console-json", default=DEFAULT_REVIEWER_CONSOLE_JSON)
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--ca2-draft-json", default=DEFAULT_CA2_DRAFT_JSON)
    parser.add_argument("--ca2-commit-json", default=DEFAULT_CA2_COMMIT_JSON)
    parser.add_argument("--pxr-draft-json", default=DEFAULT_PXR_DRAFT_JSON)
    parser.add_argument("--pxr-commit-json", default=DEFAULT_PXR_COMMIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        quickstart_payload=_load_json(args.quickstart_json),
        reviewer_console_payload=_load_json(args.reviewer_console_json),
        handoff_payload=_load_json(args.handoff_json),
        ca2_draft_payload=_load_json(args.ca2_draft_json),
        ca2_commit_payload=_load_json(args.ca2_commit_json),
        pxr_draft_payload=_load_json(args.pxr_draft_json),
        pxr_commit_payload=_load_json(args.pxr_commit_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["launch_rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
