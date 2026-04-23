#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SUBSET_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_SCOPE_NOTE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_BLOCKER_NOTE_JSON = "runs/idp_broader_promotion_blocker_note_current.json"
DEFAULT_LITERATURE_SUMMARY_JSON = "runs/idp_feature_state_literature_anchor_summary_current.json"
DEFAULT_SUBSET_SCAFFOLD_JSON = "runs/idp_literature_anchor_subset_holdout_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_anchor_shadow_scaffold_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_anchor_shadow_scaffold_current.md"

CORE_TARGETS = {"alpha_synuclein_full", "fus_lcd", "sic1_ntd", "tardbp_ctd"}
WATCHLIST_TARGETS = {"hnrnpa1_lcd", "tau_k18", "tp53_tad"}


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


def _lane_for_target(target: str) -> str:
    if target in WATCHLIST_TARGETS:
        return "commercial_pretest_watchlist"
    return "commercial_pretest_core"


def _risk_for_target(target: str) -> str:
    if target == "tau_k18":
        return "corrected_path_fragility_anchor"
    if target in {"hnrnpa1_lcd", "tp53_tad"}:
        return "state_change_watchlist"
    return "stable_anchor_backed_core"


def _reason_for_target(target: str, literature_rows: dict[str, dict[str, Any]]) -> str:
    row = literature_rows.get(target, {})
    if target == "tau_k18":
        return "Keep on watchlist because broader promotion is explicitly blocked by corrected-path fragility centered on tau_k18."
    if target in {"hnrnpa1_lcd", "tp53_tad"}:
        return (
            f"Keep on watchlist because literature slice telemetry showed "
            f"{int(row.get('would_change_state_count', 0) or 0)} state changes even with zero gate changes."
        )
    return "Use as anchor-backed commercial-pretest core target because current subset-safe evidence does not flag corrected-path or gate instability."


def build_payload(
    subset_decision_payload: dict[str, Any],
    scope_note_payload: dict[str, Any],
    blocker_note_payload: dict[str, Any],
    literature_summary_payload: dict[str, Any],
    subset_scaffold_payload: dict[str, Any],
) -> dict[str, Any]:
    subset_s = dict(subset_decision_payload.get("summary", {}) or {})
    scope_s = dict(scope_note_payload.get("summary", {}) or {})
    blocker_s = dict(blocker_note_payload.get("summary", {}) or {})
    literature_s = dict(literature_summary_payload.get("summary", {}) or {})
    subset_scaffold_s = dict(subset_scaffold_payload.get("summary", {}) or {})

    literature_rows = {
        str(row.get("target_name", "")).strip(): dict(row)
        for row in literature_summary_payload.get("rows", []) or []
        if int(row.get("is_literature_anchor", 0) or 0) == 1
    }

    targets = list(subset_scaffold_s.get("subset_targets", []) or [])
    condition_counts = dict(subset_scaffold_s.get("subset_condition_counts", {}) or {})
    rows: list[dict[str, Any]] = []
    for target in targets:
        lit_row = literature_rows.get(target, {})
        lane = _lane_for_target(target)
        rows.append(
            {
                "target_name": target,
                "lane": lane,
                "condition_row_count": int(condition_counts.get(target, 0) or 0),
                "anchor_backed": True,
                "watchlist": lane == "commercial_pretest_watchlist",
                "risk_class": _risk_for_target(target),
                "state_change_count": int(lit_row.get("would_change_state_count", 0) or 0),
                "gate_change_count": int(lit_row.get("would_change_gate_count", 0) or 0),
                "anchor_source": str(lit_row.get("anchor_source", "literature_curated_partial")).strip(),
                "recommended_mask": str(scope_s.get("default_feature_mask", subset_s.get("default_feature_mask", "rg_sasa_only"))).strip(),
                "success_criteria": "would_have_changed_state=0; would_have_changed_gate=0; no_corrected_pass_regression",
                "stop_condition": "Stop if any corrected-pass regression appears or any state/gate changes become non-zero.",
                "selection_reason": _reason_for_target(target, literature_rows),
            }
        )

    rows.sort(key=lambda row: (0 if row["lane"] == "commercial_pretest_core" else 1, row["target_name"]))
    summary = {
        "status": "broader_anchor_shadow_scaffold_ready",
        "allowed_now": str(scope_s.get("allowed_now", "")).strip(),
        "broader_promotion_blocked": bool(blocker_s.get("broader_promotion_blocked", True)),
        "subset_safe_scope": str(blocker_s.get("subset_safe_scope", "literature_anchor_subset_rg_sasa_only")).strip(),
        "default_feature_mask": str(scope_s.get("default_feature_mask", subset_s.get("default_feature_mask", "rg_sasa_only"))).strip(),
        "controlled_target_count": len(rows),
        "commercial_pretest_core_count": sum(1 for row in rows if row["lane"] == "commercial_pretest_core"),
        "commercial_pretest_watchlist_count": sum(1 for row in rows if row["lane"] == "commercial_pretest_watchlist"),
        "subset_fold_count": int(subset_s.get("fold_count", 0) or 0),
        "subset_corrected_pass_folds": int(subset_s.get("corrected_pass_folds", 0) or 0),
        "subset_state_changes": int(subset_s.get("would_have_changed_state_count", 0) or 0),
        "subset_gate_changes": int(subset_s.get("would_have_changed_gate_count", 0) or 0),
        "literature_anchor_slice_count": int(literature_s.get("literature_anchor_slice_count", 0) or 0),
        "blocker_reason": str(blocker_s.get("blocker_reason", subset_s.get("blocking_reason", ""))).strip(),
        "next_required_step": "Run the next anchor-backed shadow-only commercialization pretest on this controlled 7-target scaffold, keeping rg_sasa_only and all no-override guardrails frozen.",
    }
    guardrails = [
        "no_coordinate_correction",
        "no_ranking_override",
        "no_gate_override",
        "feature_state_smoothing_only",
        f"default_mask={summary['default_feature_mask']}",
        "require_zero_state_changes",
        "require_zero_gate_changes",
        "require_no_corrected_pass_regression",
    ]
    milestone_rows = [
        {
            "milestone": "freeze_controlled_anchor_scaffold",
            "status": "ready",
            "success_signal": "7 anchor-backed targets split into core/watchlist lanes",
        },
        {
            "milestone": "run_shadow_only_pretest",
            "status": "next",
            "success_signal": "all targets keep zero state/gate changes and no corrected-pass regression",
        },
        {
            "milestone": "unlock_broader_idp_commercial_pretest_lane",
            "status": "blocked",
            "success_signal": "tau_k18-style corrected-path fragility no longer appears on the controlled scaffold",
        },
    ]
    payload = {
        "summary": summary,
        "guardrails": guardrails,
        "rows": rows,
        "milestones": milestone_rows,
        "suggested_command": [
            "python3",
            "tools/run_idp_3bead_holdout_pipeline.py",
            "--config-json",
            str(_resolve("config/idp_3bead_benchmark_v7_literature_anchor_subset.json")),
            "--device",
            "cuda",
            "--out-prefix",
            "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1",
            "--resume-existing",
            "1",
            "--kalman-shadow-enable",
            "1",
            "--kalman-shadow-mode",
            "feature_state_v1",
            "--kalman-shadow-family-token",
            "idp",
            "--kalman-shadow-feature-mask",
            summary["default_feature_mask"],
            "--kalman-shadow-obs-noise-scale",
            "0.15",
            "--kalman-shadow-process-noise-scale",
            "0.03",
            "--kalman-shadow-delta-cap-frac",
            "0.25",
        ],
    }
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Anchor Shadow Scaffold",
        "",
        f"- status: `{s['status']}`",
        f"- allowed_now: `{s['allowed_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- subset_safe_scope: `{s['subset_safe_scope']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- controlled_target_count: `{s['controlled_target_count']}`",
        f"- commercial_pretest_core_count: `{s['commercial_pretest_core_count']}`",
        f"- commercial_pretest_watchlist_count: `{s['commercial_pretest_watchlist_count']}`",
        f"- subset_corrected_pass_folds: `{s['subset_corrected_pass_folds']}`",
        f"- subset_state_changes: `{s['subset_state_changes']}`",
        f"- subset_gate_changes: `{s['subset_gate_changes']}`",
        "",
        "## Blocker",
        "",
        f"- {s['blocker_reason']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Guardrails",
        "",
    ]
    for item in payload["guardrails"]:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Controlled Targets",
            "",
            "| target | lane | rows | risk_class | state_changes | gate_changes | recommended_mask |",
            "| --- | --- | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['lane']}` | {row['condition_row_count']} | `{row['risk_class']}` | "
            f"{row['state_change_count']} | {row['gate_change_count']} | `{row['recommended_mask']}` |"
        )
    lines.extend(["", "## Selection Reasons", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['target_name']}`: {row['selection_reason']}")
    lines.extend(
        [
            "",
            "## Milestones",
            "",
            "| milestone | status | success_signal |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["milestones"]:
        lines.append(f"| `{row['milestone']}` | `{row['status']}` | {row['success_signal']} |")
    lines.extend(
        [
            "",
            "## Suggested Command",
            "",
            "```bash",
            " ".join(payload["suggested_command"]),
            "```",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build the next broader anchor-backed IDP shadow scaffold for commercialization pretest.")
    ap.add_argument("--subset-decision-json", default=DEFAULT_SUBSET_DECISION_JSON)
    ap.add_argument("--scope-note-json", default=DEFAULT_SCOPE_NOTE_JSON)
    ap.add_argument("--blocker-note-json", default=DEFAULT_BLOCKER_NOTE_JSON)
    ap.add_argument("--literature-summary-json", default=DEFAULT_LITERATURE_SUMMARY_JSON)
    ap.add_argument("--subset-scaffold-json", default=DEFAULT_SUBSET_SCAFFOLD_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.subset_decision_json),
        _load_json(args.scope_note_json),
        _load_json(args.blocker_note_json),
        _load_json(args.literature_summary_json),
        _load_json(args.subset_scaffold_json),
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
