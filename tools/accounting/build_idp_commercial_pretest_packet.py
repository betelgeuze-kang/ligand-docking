#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_OUT_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_commercial_pretest_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_commercial_pretest_packet_current.md"


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


def _watchlist_interpretation(row: dict[str, Any]) -> str:
    target = str(row.get("target_name", "")).strip()
    risk = str(row.get("risk_class", "")).strip()
    if target == "tau_k18" or risk == "corrected_path_fragility_anchor":
        return "Do not use as promotion evidence; use only to detect corrected-path regression."
    if risk == "state_change_watchlist":
        return "Use as stability watchlist target; any non-zero state change blocks broader promotion."
    return "Treat as steady anchor-backed comparator only."


def build_payload(scaffold_payload: dict[str, Any]) -> dict[str, Any]:
    scaffold_s = dict(scaffold_payload.get("summary", {}) or {})
    rows = [dict(row) for row in scaffold_payload.get("rows", []) or []]
    core_rows = [row for row in rows if str(row.get("lane", "")).strip() == "commercial_pretest_core"]
    watchlist_rows = [row for row in rows if str(row.get("lane", "")).strip() == "commercial_pretest_watchlist"]

    packet_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(core_rows + watchlist_rows, start=1):
        packet_rows.append(
            {
                "packet_rank": idx,
                "target_name": str(row.get("target_name", "")).strip(),
                "lane": str(row.get("lane", "")).strip(),
                "risk_class": str(row.get("risk_class", "")).strip(),
                "condition_row_count": int(row.get("condition_row_count", 0) or 0),
                "recommended_mask": str(row.get("recommended_mask", "")).strip(),
                "success_criteria": str(row.get("success_criteria", "")).strip(),
                "stop_condition": str(row.get("stop_condition", "")).strip(),
                "watchlist_interpretation": _watchlist_interpretation(row),
                "selection_reason": str(row.get("selection_reason", "")).strip(),
            }
        )

    success_gates = [
        "all targets keep would_have_changed_state = 0",
        "all targets keep would_have_changed_gate = 0",
        "no corrected-pass regression on any controlled target",
        "tau_k18 does not reproduce corrected-path fragility on the shadow-only pretest slice",
    ]
    failure_gates = [
        "any target shows non-zero would_have_changed_state",
        "any target shows non-zero would_have_changed_gate",
        "any corrected-pass regression appears on the controlled slice",
        "tau_k18 or another watchlist target reintroduces corrected-path fragility",
    ]
    next_step_guidance = [
        "Run this packet only as shadow-only commercialization pretest.",
        "Review core targets first for clean zero-change confirmation.",
        "Use watchlist targets only as blocker detectors, not promotion evidence.",
        "If all success gates hold, propose the next IDP commercial-pretest promotion note; otherwise keep broader promotion blocked.",
    ]

    summary = {
        "status": "operator_packet_ready",
        "packet_scope": "idp_anchor_backed_shadow_only_commercial_pretest",
        "broader_promotion_blocked": bool(scaffold_s.get("broader_promotion_blocked", True)),
        "default_feature_mask": str(scaffold_s.get("default_feature_mask", "rg_sasa_only")).strip(),
        "core_target_count": len(core_rows),
        "watchlist_target_count": len(watchlist_rows),
        "row_count": len(packet_rows),
        "blocker_reason": str(scaffold_s.get("blocker_reason", "")).strip(),
        "recommended_command": " ".join(scaffold_payload.get("suggested_command", []) or []),
        "next_required_step": "Execute the shadow-only commercial-pretest command, check success/failure gates, and keep broader promotion blocked unless every gate stays green.",
    }
    return {
        "summary": summary,
        "success_gates": success_gates,
        "failure_gates": failure_gates,
        "next_step_guidance": next_step_guidance,
        "rows": packet_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Commercial Pretest Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- core_target_count: `{s['core_target_count']}`",
        f"- watchlist_target_count: `{s['watchlist_target_count']}`",
        f"- row_count: `{s['row_count']}`",
        "",
        "## Blocker",
        "",
        f"- {s['blocker_reason']}",
        "",
        "## Recommended Command",
        "",
        "```bash",
        s["recommended_command"],
        "```",
        "",
        "## Success Gates",
        "",
    ]
    for item in payload["success_gates"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Failure Gates", ""])
    for item in payload["failure_gates"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Targets",
            "",
            "| packet_rank | target | lane | risk_class | rows | recommended_mask | watchlist_interpretation |",
            "| ---: | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['packet_rank']} | `{row['target_name']}` | `{row['lane']}` | `{row['risk_class']}` | "
            f"{row['condition_row_count']} | `{row['recommended_mask']}` | {row['watchlist_interpretation']} |"
        )
    lines.extend(["", "## Next-Step Guidance", ""])
    for item in payload["next_step_guidance"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Per-Target Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['target_name']}`: {row['selection_reason']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build an operator-facing IDP commercial pretest packet from the broader anchor shadow scaffold.")
    ap.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.scaffold_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
