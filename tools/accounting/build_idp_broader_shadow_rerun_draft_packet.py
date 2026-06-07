#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVIEW_PACKET_JSON = "runs/idp_broader_shadow_review_packet_current.json"
DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_ROSTER_VIABILITY_JSON = "runs/idp_broader_anchor_roster_viability_packet_current.json"
DEFAULT_SAME_SCOPE_CONFIG_JSON = "config/idp_3bead_benchmark_v7_literature_anchor_subset.json"
DEFAULT_OUT_JSON = "runs/idp_broader_shadow_rerun_draft_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_shadow_rerun_draft_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_shadow_rerun_draft_packet_current.md"


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


def build_payload(
    review_packet: dict[str, Any],
    decision_packet: dict[str, Any],
    validation_result: dict[str, Any],
    roster_viability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_s = dict(review_packet.get("summary", {}) or {})
    review_rows = [dict(row) for row in review_packet.get("rows", []) or []]
    decision_s = dict(decision_packet.get("summary", {}) or {})
    validation_s = dict(validation_result.get("summary", {}) or {})
    roster_s = dict((roster_viability or {}).get("summary", {}) or {})
    additional_anchor_backed_target_count = int(roster_s.get("additional_anchor_backed_target_count", 0) or 0)
    provisional_only_target_count = int(roster_s.get("provisional_only_target_count", 0) or 0)
    no_true_broader_roster = additional_anchor_backed_target_count == 0

    unresolved_rows = [row for row in review_rows if str(row.get("status", "")).strip() == "review_now"]
    frozen_rows = [row for row in review_rows if str(row.get("status", "")).strip() == "keep_frozen"]
    frozen_guardrails = []
    for row in frozen_rows:
        current_signal = str(row.get("current_signal", "")).strip()
        if current_signal:
            frozen_guardrails.extend(part.strip() for part in current_signal.split(";") if part.strip())

    env_prefix = "IDP_R17_TAU_PH_SPLIT_PATCH=1 IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH=1"
    command_template = (
        f"{env_prefix} python3 tools/run_idp_3bead_holdout_pipeline.py "
        "--config-json <broader_anchor_backed_config.json> "
        "--device cuda "
        "--out-prefix runs/idp_3bead_holdout_v7_broader_shadow_r1 "
        "--resume-existing 0 "
        "--kalman-shadow-enable 1 "
        "--kalman-shadow-mode feature_state_v1 "
        "--kalman-shadow-family-token idp "
        f"--kalman-shadow-feature-mask {decision_s.get('default_feature_mask', 'rg_sasa_only')} "
        "--kalman-shadow-obs-noise-scale 0.15 "
        "--kalman-shadow-process-noise-scale 0.03 "
        "--kalman-shadow-delta-cap-frac 0.25"
    )
    same_scope_process_check_command = (
        f"{env_prefix} python3 tools/run_idp_3bead_holdout_pipeline.py "
        f"--config-json {str(_resolve(DEFAULT_SAME_SCOPE_CONFIG_JSON))} "
        "--device cuda "
        "--out-prefix runs/idp_3bead_holdout_v7_anchor_commercial_pretest_processcheck_r1 "
        "--resume-existing 0 "
        "--kalman-shadow-enable 1 "
        "--kalman-shadow-mode feature_state_v1 "
        "--kalman-shadow-family-token idp "
        f"--kalman-shadow-feature-mask {decision_s.get('default_feature_mask', 'rg_sasa_only')} "
        "--kalman-shadow-obs-noise-scale 0.15 "
        "--kalman-shadow-process-noise-scale 0.03 "
        "--kalman-shadow-delta-cap-frac 0.25"
    )

    rows = [
        {
            "draft_step": "promotion_policy",
            "status": "review_required",
            "ready_now": False,
            "current_signal": str(next((r.get("current_signal", "") for r in unresolved_rows if r.get("review_item") == "promotion_policy"), "")).strip(),
            "next_action": "Freeze whether broader promotion remains blocked until the first broader rerun completes.",
        },
        {
            "draft_step": "target_roster",
            "status": "blocked_no_true_broader_roster" if no_true_broader_roster else "review_required",
            "ready_now": False,
            "current_signal": (
                str(next((r.get("current_signal", "") for r in unresolved_rows if r.get("review_item") == "target_roster"), "")).strip()
                or f"additional_anchor_backed_target_count={additional_anchor_backed_target_count}"
            ),
            "next_action": (
                "Choose the first reviewed broader anchor-backed roster and encode it in a new config JSON."
                if additional_anchor_backed_target_count
                else "Local assets do not yet provide extra anchor-backed targets beyond the controlled scaffold, so decide whether to curate new anchors first or treat the next run as same-scope process validation only."
            ),
        },
        {
            "draft_step": "guardrails",
            "status": "frozen",
            "ready_now": True,
            "current_signal": "; ".join(frozen_guardrails),
            "next_action": "Carry these guardrails unchanged into the first broader full-IDP shadow rerun.",
        },
        {
            "draft_step": "success_criteria",
            "status": "review_required",
            "ready_now": False,
            "current_signal": str(next((r.get("current_signal", "") for r in unresolved_rows if r.get("review_item") == "success_criteria"), "")).strip(),
            "next_action": "Freeze zero state/gate drift and no corrected-pass regression against the clean bounded commercial-pretest run.",
        },
        {
            "draft_step": "execution_template",
            "status": "draft_ready",
            "ready_now": True,
            "current_signal": env_prefix,
            "next_action": (
                "Instantiate this command only after at least one additional anchor-backed target is curated and the review-required steps above are explicitly resolved."
                if no_true_broader_roster
                else "Instantiate this command only after the review-required steps above are explicitly resolved."
            ),
        },
        {
            "draft_step": "same_scope_process_check",
            "status": "ready_now" if no_true_broader_roster else "optional_fallback",
            "ready_now": True,
            "current_signal": str(_resolve(DEFAULT_SAME_SCOPE_CONFIG_JSON)),
            "next_action": "Use this only as a same-scope process check on the validated 7-target literature-anchor subset. Do not label it as a broader rerun.",
        },
    ]

    summary = {
        "status": (
            "broader_shadow_rerun_draft_blocked_no_true_broader_roster"
            if no_true_broader_roster
            else "broader_shadow_rerun_draft_blocked_pending_review"
        ),
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip(),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "bounded_validation_status": str(validation_s.get("status", "")).strip(),
        "bounded_validation_pass_folds": f"{validation_s.get('corrected_pass_folds', '')}/{validation_s.get('fold_count', '')}",
        "additional_anchor_backed_target_count": additional_anchor_backed_target_count,
        "provisional_only_target_count": provisional_only_target_count,
        "true_broader_rerun_ready": not no_true_broader_roster,
        "same_scope_process_check_ready": True,
        "review_item_count": len(review_rows),
        "unresolved_review_item_count": len(unresolved_rows),
        "frozen_guardrail_count": len(frozen_guardrails),
        "command_template_ready": True,
        "same_scope_process_check_command": same_scope_process_check_command,
        "next_required_step": (
            "Keep broader_full_idp_promotion blocked, resolve the review-required policy/roster/success items, "
            "and only instantiate this draft as a true broader rerun after at least one additional anchor-backed target is curated. "
            "Without that, the next run can only be a same-scope process check."
            if no_true_broader_roster
            else "Keep broader_full_idp_promotion blocked, resolve the review-required policy/roster/success items, instantiate this draft with the first broader anchor-backed config once those items are frozen, and use the same-scope process check only as an optional fallback rather than the primary path."
        ),
        "command_template": command_template,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Shadow Rerun Draft Packet",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- bounded_validation_status: `{s['bounded_validation_status']}`",
        f"- bounded_validation_pass_folds: `{s['bounded_validation_pass_folds']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- provisional_only_target_count: `{s['provisional_only_target_count']}`",
        f"- true_broader_rerun_ready: `{s['true_broader_rerun_ready']}`",
        f"- same_scope_process_check_ready: `{s['same_scope_process_check_ready']}`",
        f"- review_item_count: `{s['review_item_count']}`",
        f"- unresolved_review_item_count: `{s['unresolved_review_item_count']}`",
        f"- frozen_guardrail_count: `{s['frozen_guardrail_count']}`",
        f"- command_template_ready: `{s['command_template_ready']}`",
        "",
        "## Command Template",
        "",
        "```bash",
        s["command_template"],
        "```",
        "",
        "## Same-Scope Process Check",
        "",
        "```bash",
        s["same_scope_process_check_command"],
        "```",
        "",
        "## Draft Steps",
        "",
        "| draft_step | status | ready_now | current_signal | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['draft_step']}` | `{row['status']}` | `{row['ready_now']}` | `{row['current_signal']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a draft execution packet for the first broader full-IDP shadow rerun.")
    p.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    p.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    p.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    p.add_argument("--roster-viability-json", default=DEFAULT_ROSTER_VIABILITY_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.review_packet_json),
        _load_json(args.decision_json),
        _load_json(args.validation_result_json),
        _load_json(args.roster_viability_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
