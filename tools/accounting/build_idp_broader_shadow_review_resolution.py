#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVIEW_PACKET_JSON = "runs/idp_broader_shadow_review_packet_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_FULL_CONFIG_JSON = "config/idp_3bead_benchmark_v7.json"
DEFAULT_TRUE_BROADER_CONFIG_JSON = "config/idp_3bead_benchmark_v7_anchor_plus_page4.json"
DEFAULT_ANCHOR_JSON = "config/idp_observable_anchors_expanded_v5.json"
DEFAULT_OUT_JSON = "runs/idp_broader_shadow_review_resolution_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_shadow_review_resolution_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_shadow_review_resolution_current.md"


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
    validation_result: dict[str, Any],
    scaffold_payload: dict[str, Any],
    full_config: dict[str, Any],
    anchor_payload: dict[str, Any],
) -> dict[str, Any]:
    review_s = dict(review_packet.get("summary", {}) or {})
    validation_s = dict(validation_result.get("summary", {}) or {})
    scaffold_s = dict(scaffold_payload.get("summary", {}) or {})

    scaffold_rows = [dict(row) for row in scaffold_payload.get("rows", []) or []]
    current_targets = {str(row.get("target_name", "")).strip() for row in scaffold_rows}
    watchlist_targets = {
        str(row.get("target_name", "")).strip()
        for row in scaffold_rows
        if str(row.get("lane", "")).strip() == "commercial_pretest_watchlist"
    }
    anchor_targets = dict((anchor_payload.get("targets", {}) if isinstance(anchor_payload.get("targets", {}), dict) else {}) or {})

    seen: list[str] = []
    for target in full_config.get("targets", []) or []:
        name = str(target.get("name", "")).strip()
        if name and name not in seen:
            seen.append(name)

    rows: list[dict[str, Any]] = []
    additional_anchor_backed = 0
    for name in seen:
        anchor_meta = dict(anchor_targets.get(name, {}) or {})
        source_class = str(anchor_meta.get("source", "")).strip() or "unknown"
        anchor_backed = source_class != "branch_family_provisional"
        if name in current_targets:
            tier = "validated_current_watchlist" if name in watchlist_targets else "validated_current_core"
            evidence_role = "non_regression_required"
            use_in_true_broader_rerun = False
            use_in_same_scope_process_check = True
        else:
            tier = "provisional_only_expansion" if not anchor_backed else "anchor_backed_expansion"
            evidence_role = (
                "not_launch_eligible_provisional_only"
                if not anchor_backed
                else "additional_anchor_backed_candidate"
            )
            use_in_true_broader_rerun = anchor_backed
            use_in_same_scope_process_check = False
            if anchor_backed:
                additional_anchor_backed += 1
        rows.append(
            {
                "target_name": name,
                "source_class": source_class,
                "anchor_backed": anchor_backed,
                "tier": tier,
                "use_in_true_broader_rerun": use_in_true_broader_rerun,
                "use_in_same_scope_process_check": use_in_same_scope_process_check,
                "evidence_role": evidence_role,
            }
        )

    validated_count = sum(1 for row in rows if row["tier"].startswith("validated_"))
    provisional_count = sum(1 for row in rows if row["tier"] == "provisional_only_expansion")
    has_true_broader_roster = additional_anchor_backed > 0
    summary = {
        "status": (
            "broader_shadow_review_resolved_true_broader_roster_available"
            if has_true_broader_roster
            else "broader_shadow_review_resolved_no_additional_anchor_backed_targets"
        ),
        "operator_scope_now": str(review_s.get("operator_scope_now", "")).strip(),
        "broader_promotion_blocked": True,
        "shadow_safe_retained": True,
        "recommended_launch_scope": (
            "first_true_broader_shadow_only_not_promotion"
            if has_true_broader_roster
            else "same_scope_process_check_only"
        ),
        "reviewed_target_count": len(rows),
        "validated_current_target_count": validated_count,
        "additional_anchor_backed_target_count": additional_anchor_backed,
        "provisional_expansion_target_count": provisional_count,
        "true_broader_rerun_ready": has_true_broader_roster,
        "same_scope_process_check_ready": not has_true_broader_roster,
        "config_json": str(_resolve(DEFAULT_TRUE_BROADER_CONFIG_JSON if has_true_broader_roster else DEFAULT_FULL_CONFIG_JSON)),
        "same_scope_config_json": str(_resolve("config/idp_3bead_benchmark_v7_literature_anchor_subset.json")),
        "default_feature_mask": str(scaffold_s.get("default_feature_mask", "rg_sasa_only")).strip(),
        "bounded_validation_pass_folds": f"{validation_s.get('corrected_pass_folds', '')}/{validation_s.get('fold_count', '')}",
        "promotion_policy_resolution": (
            "Broader promotion remains blocked, but the first true broader shadow-only rerun can now be defined with PAGE4 as the first additional anchor-backed target beyond the validated 7-target scaffold."
            if has_true_broader_roster
            else
            "Broader promotion remains blocked because the local roster adds no extra anchor-backed targets beyond the currently validated 7-target scaffold."
        ),
        "success_criteria_resolution": (
            "Freeze the first broader anchor-backed roster to the validated 7-target scaffold plus PAGE4, preserve the same no-override guardrails, and require zero state/gate drift plus no corrected-pass regression on the validated current targets."
            if has_true_broader_roster
            else
            "Treat the current 7-target literature-anchor subset as the only launchable process-check scope, keep zero state/gate drift and no corrected-pass regression as frozen criteria, "
            "and do not treat the 13 provisional-only expansion targets as promotion evidence."
        ),
        "next_required_step": (
            "Keep broader_full_idp_promotion blocked, freeze the first broader anchor-backed roster to the validated 7-target scaffold plus PAGE4, and use that resolved roster to define one true broader full-IDP shadow-only rerun under the same no-override guardrails."
            if has_true_broader_roster
            else
            "Do not launch a true broader full-IDP rerun yet. Either run one same-scope process check on the 7-target literature-anchor subset with the same no-override guardrails, "
            "or curate at least one additional anchor-backed target before defining a broader shadow rerun."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Shadow Review Resolution",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- recommended_launch_scope: `{s['recommended_launch_scope']}`",
        f"- reviewed_target_count: `{s['reviewed_target_count']}`",
        f"- validated_current_target_count: `{s['validated_current_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- provisional_expansion_target_count: `{s['provisional_expansion_target_count']}`",
        f"- true_broader_rerun_ready: `{s['true_broader_rerun_ready']}`",
        f"- same_scope_process_check_ready: `{s['same_scope_process_check_ready']}`",
        f"- config_json: `{s['config_json']}`",
        f"- same_scope_config_json: `{s['same_scope_config_json']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- bounded_validation_pass_folds: `{s['bounded_validation_pass_folds']}`",
        "",
        "## Review Resolution",
        "",
        f"- {s['promotion_policy_resolution']}",
        f"- {s['success_criteria_resolution']}",
        "",
        "## Target Roster",
        "",
        "| target | source_class | anchor_backed | tier | use_in_true_broader_rerun | use_in_same_scope_process_check | evidence_role |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['source_class']}` | `{row['anchor_backed']}` | `{row['tier']}` | `{row['use_in_true_broader_rerun']}` | `{row['use_in_same_scope_process_check']}` | `{row['evidence_role']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a resolved broader-shadow review artifact for IDP.")
    p.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    p.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    p.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    p.add_argument("--full-config-json", default=DEFAULT_FULL_CONFIG_JSON)
    p.add_argument("--anchor-json", default=DEFAULT_ANCHOR_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.review_packet_json),
        _load_json(args.validation_result_json),
        _load_json(args.scaffold_json),
        _load_json(args.full_config_json),
        _load_json(args.anchor_json),
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
