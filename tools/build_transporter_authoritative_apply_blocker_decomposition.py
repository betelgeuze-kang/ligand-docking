#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_APPLY_DRAFT_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_DONOR_REOPEN_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_DONOR_POLICY_JSON = "runs/transporter_fit_donor_policy_decision_current.json"
DEFAULT_READINESS_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_AQP1_COMMIT_JSON = "runs/aqp1_manual_verdict_commit_packet_current.json"
DEFAULT_GLUT1_COMMIT_JSON = "runs/glut1_manual_verdict_commit_packet_current.json"
DEFAULT_AQP1_WORKBOOK_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_GLUT1_WORKBOOK_JSON = "runs/glut1_packet_replacement_workbook_current.json"
DEFAULT_OUT_JSON = "runs/transporter_authoritative_apply_blocker_decomposition_current.json"
DEFAULT_OUT_CSV = "runs/transporter_authoritative_apply_blocker_decomposition_current.csv"
DEFAULT_OUT_MD = "runs/transporter_authoritative_apply_blocker_decomposition_current.md"


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
    dashboard: dict[str, Any],
    apply_draft_status: dict[str, Any],
    donor_reopen: dict[str, Any],
    donor_policy: dict[str, Any],
    readiness: dict[str, Any],
    aqp1_commit: dict[str, Any],
    glut1_commit: dict[str, Any],
    aqp1_workbook: dict[str, Any],
    glut1_workbook: dict[str, Any],
) -> dict[str, Any]:
    dashboard_s = dict(dashboard.get("summary", {}) or {})
    apply_s = dict(apply_draft_status.get("summary", {}) or {})
    donor_reopen_s = dict(donor_reopen.get("summary", {}) or {})
    donor_policy_s = dict(donor_policy.get("summary", {}) or {})
    readiness_s = dict(readiness.get("summary", {}) or {})
    aqp1_commit_s = dict(aqp1_commit.get("summary", {}) or {})
    glut1_commit_s = dict(glut1_commit.get("summary", {}) or {})
    aqp1_wb_s = dict(aqp1_workbook.get("summary", {}) or {})
    glut1_wb_s = dict(glut1_workbook.get("summary", {}) or {})

    rows = [
        {
            "blocker_rank": 1,
            "blocker_id": "placeholder_packet_rows",
            "blocker_status": "blocked",
            "scope": "family",
            "current_signal": (
                f"placeholder_driven_rows={apply_s.get('placeholder_driven_rows', 0)}; "
                f"staged_non_authoritative_rows={apply_s.get('staged_non_authoritative_rows', 0)}; "
                f"ready_for_apply_rows={apply_s.get('ready_for_apply_rows', 0)}"
            ),
            "source_artifact": "runs/transporter_apply_draft_status_current.md",
            "next_action": "replace placeholder-driven transporter workbook rows with target-specific reference/split/meta evidence before any authoritative apply discussion",
        },
        {
            "blocker_rank": 2,
            "blocker_id": "target_specific_binder_evidence_uncurated",
            "blocker_status": "blocked",
            "scope": "target",
            "current_signal": (
                f"aqp1_keep_review_only={dashboard_s.get('aqp1_keep_review_only_count', 0)}; "
                f"glut1_keep_review_only={dashboard_s.get('glut1_keep_review_only_count', 0)}"
            ),
            "source_artifact": "runs/transporter_manual_review_dashboard_current.md",
            "next_action": "keep binder verdicts review-only until at least one AQP1 or GLUT1 candidate is backed by claim-safe target-specific packet evidence",
        },
        {
            "blocker_rank": 3,
            "blocker_id": "donor_policy_frozen",
            "blocker_status": "blocked",
            "scope": "family",
            "current_signal": (
                f"reopen_ready={donor_reopen_s.get('reopen_ready', False)}; "
                f"blocked_check_count={donor_reopen_s.get('blocked_check_count', 0)}; "
                f"fit_donor={donor_policy_s.get('scaffold_fit_donor_target', '')}"
            ),
            "source_artifact": "runs/transporter_donor_policy_reopen_checklist_current.md",
            "next_action": "do not reopen donor policy until at least one transporter binder row is non-placeholder and transporter P0 scaffold blockers are reduced",
        },
        {
            "blocker_rank": 4,
            "blocker_id": "p0_scaffold_gaps",
            "blocker_status": "blocked",
            "scope": "family",
            "current_signal": f"p0_open_count={readiness_s.get('p0_open_count', 0)}",
            "source_artifact": "runs/transporter_membrane_readiness_current.md",
            "next_action": "burn down remaining AQP1/GLUT1 transporter P0 gaps before treating the family as runnable beyond draft/manual-review mode",
        },
        {
            "blocker_rank": 5,
            "blocker_id": "reviewer_commit_non_authoritative",
            "blocker_status": "soft_blocked",
            "scope": "target",
            "current_signal": (
                f"aqp1_manual_fields_committed={aqp1_commit_s.get('manual_fields_committed_count', 0)}; "
                f"glut1_manual_fields_committed={glut1_commit_s.get('manual_fields_committed_count', 0)}"
            ),
            "source_artifact": "runs/transporter_manual_review_dashboard_current.md",
            "next_action": "treat completed manual verdicts as reviewer-state only; they reduce review backlog but do not authorize transporter apply on their own",
        },
        {
            "blocker_rank": 6,
            "blocker_id": "workbook_seed_rows_not_apply_ready",
            "blocker_status": "blocked",
            "scope": "target",
            "current_signal": (
                f"aqp1_ready_seed_rows={aqp1_wb_s.get('ready_seed_row_count', 0)}; "
                f"glut1_ready_seed_rows={glut1_wb_s.get('ready_seed_row_count', 0)}"
            ),
            "source_artifact": "runs/aqp1_packet_replacement_workbook_current.md + runs/glut1_packet_replacement_workbook_current.md",
            "next_action": "promote at least one transporter workbook row from staged review-only state into a synchronized reference/split/meta candidate with claim-safe quantitative binding before reopening apply discussion",
        },
    ]

    summary = {
        "blocker_count": len(rows),
        "hard_blocker_count": sum(1 for row in rows if row["blocker_status"] == "blocked"),
        "soft_blocker_count": sum(1 for row in rows if row["blocker_status"] == "soft_blocked"),
        "manual_review_backlog_cleared": int(apply_s.get("pending_manual_verdict_count", 0) or 0) == 0,
        "authoritative_apply_ready": False,
        "top_blocker_id": rows[0]["blocker_id"] if rows else "",
        "top_blocker_signal": rows[0]["current_signal"] if rows else "",
        "next_required_step": "Use this blocker board after manual verdict completion; the remaining work is packet evidence and donor-policy closure, not additional transporter reviewer phrasing.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Authoritative Apply Blocker Decomposition",
        "",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- hard_blocker_count: `{s['hard_blocker_count']}`",
        f"- soft_blocker_count: `{s['soft_blocker_count']}`",
        f"- manual_review_backlog_cleared: `{s['manual_review_backlog_cleared']}`",
        f"- authoritative_apply_ready: `{s['authoritative_apply_ready']}`",
        f"- top_blocker_id: `{s['top_blocker_id']}`",
        f"- top_blocker_signal: `{s['top_blocker_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Blockers",
        "",
        "| blocker_rank | blocker_id | blocker_status | scope | current_signal | source_artifact | next_action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['blocker_rank']} | `{row['blocker_id']}` | `{row['blocker_status']}` | `{row['scope']}` | "
            f"`{row['current_signal']}` | `{row['source_artifact']}` | {row['next_action']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decompose remaining transporter authoritative-apply blockers after reviewer manual-verdict completion.")
    parser.add_argument("--dashboard-json", default=DEFAULT_DASHBOARD_JSON)
    parser.add_argument("--apply-draft-status-json", default=DEFAULT_APPLY_DRAFT_STATUS_JSON)
    parser.add_argument("--donor-reopen-json", default=DEFAULT_DONOR_REOPEN_JSON)
    parser.add_argument("--donor-policy-json", default=DEFAULT_DONOR_POLICY_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--aqp1-commit-json", default=DEFAULT_AQP1_COMMIT_JSON)
    parser.add_argument("--glut1-commit-json", default=DEFAULT_GLUT1_COMMIT_JSON)
    parser.add_argument("--aqp1-workbook-json", default=DEFAULT_AQP1_WORKBOOK_JSON)
    parser.add_argument("--glut1-workbook-json", default=DEFAULT_GLUT1_WORKBOOK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.dashboard_json),
        _load_json(args.apply_draft_status_json),
        _load_json(args.donor_reopen_json),
        _load_json(args.donor_policy_json),
        _load_json(args.readiness_json),
        _load_json(args.aqp1_commit_json),
        _load_json(args.glut1_commit_json),
        _load_json(args.aqp1_workbook_json),
        _load_json(args.glut1_workbook_json),
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
