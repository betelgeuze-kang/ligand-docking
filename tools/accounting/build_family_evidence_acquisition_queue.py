#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CA2_CAPTURE_SHEET_JSON = "runs/ca2_negative_evidence_capture_sheet_current.json"
DEFAULT_CA2_COMMIT_PACKET_JSON = "runs/ca2_evidence_closure_commit_packet_current.json"
DEFAULT_PXR_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_PXR_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/family_evidence_acquisition_queue_current.json"
DEFAULT_OUT_CSV = "runs/family_evidence_acquisition_queue_current.csv"
DEFAULT_OUT_MD = "runs/family_evidence_acquisition_queue_current.md"

TIER_ORDER = {
    "P0_count_improving_binder_gap": 0,
    "P1_count_improving_negative_gap": 1,
    "P2_supportive_manual_confirmation": 2,
    "P2_conflict_resolution": 3,
    "P2_low_probability_conflict_cleanup": 4,
    "P3_review_only_documentation": 5,
}

STATE_CHANGE_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2,
    "review_only": 3,
}


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


def _join_by_step(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in rows
        if str(row.get("packet_step", "")).strip()
    }


def _ca2_search_scope(blocker: str) -> str:
    if blocker == "no_direct_ca2_negative_evidence_located_after_research":
        return "human CA2 direct negative or explicit no-activity assay evidence"
    return "contradictory direct CA2-negative evidence strong enough to overturn current inhibitor/conflict literature"


def _ca2_stop_condition(blocker: str) -> str:
    if blocker == "no_direct_ca2_negative_evidence_located_after_research":
        return "Stop if search returns only general carbonic-anhydrase mechanism papers or non-CA2-specific evidence; keep review-only and leave kcal blank."
    return "Stop if evidence remains inhibitor/conflict-only or non-CA2-specific; keep review-only and leave kcal blank."


def _ca2_claim_impact(blocker: str) -> str:
    if blocker == "no_direct_ca2_negative_evidence_located_after_research":
        return "potential_count_improving_if_direct_negative_found"
    return "count_neutral_without_new_primary_contradiction"


def _ca2_actionability_bucket(blocker: str) -> str:
    if blocker == "no_direct_ca2_negative_evidence_located_after_research":
        return "count_improving_gap"
    return "review_only_documentation"


def _ca2_state_change_potential(blocker: str) -> str:
    if blocker == "no_direct_ca2_negative_evidence_located_after_research":
        return "high"
    return "review_only"


def _ca2_tier(blocker: str) -> str:
    if blocker == "no_direct_ca2_negative_evidence_located_after_research":
        return "P1_count_improving_negative_gap"
    return "P3_review_only_documentation"


def _pxr_search_scope(evidence_need_class: str, blocker: str) -> str:
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return "claim-safe quantitative human NR1I2/PXR binder value or explicit target-specific activity provenance"
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return "review-only confirmation of the current inactive-only human NR1I2/PXR qHTS record"
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return "human NR1I2/PXR target-specific binder or direct binding evidence"
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return "human NR1I2/PXR target-specific evidence capable of resolving the current proxy conflict"
    if evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution":
        return "stronger human NR1I2/PXR negative-like evidence than the current weak upper-bound proxy"
    return "human NR1I2/PXR target-specific negative or no-activity evidence"


def _pxr_conflict_lane(blocker: str, source_title: str, source_url: str, source_note: str) -> str:
    if blocker != "activity_proxy_conflicts_with_non_binder":
        return ""
    lowered_note = source_note.lower()
    lowered_title = source_title.lower()
    lowered_url = source_url.lower()
    if "antagonist activity at human nr1i2" in lowered_note and "agonist activity at human nr1i2" in lowered_note:
        return "exact_human_dual_mode_activity_conflict"
    has_pubchem = "pubchem" in lowered_title or "pubchem" in lowered_url
    has_active = "active" in lowered_note
    has_inactive = "inactive" in lowered_note
    if has_pubchem and has_active and has_inactive:
        return "direct_human_qhts_active_inactive_conflict"
    if has_pubchem:
        return "direct_human_qhts_proxy_conflict"
    return "generic_human_proxy_conflict"


def _pxr_state_change_potential(evidence_need_class: str, blocker: str, conflict_lane: str) -> str:
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return "high"
    if blocker == "activity_present_manual_confirmation_required":
        return "medium"
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return "review_only"
    if conflict_lane in {
        "exact_human_dual_mode_activity_conflict",
        "direct_human_qhts_active_inactive_conflict",
        "direct_human_qhts_proxy_conflict",
    }:
        return "low"
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return "medium"
    if evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution":
        return "review_only"
    return "high"


def _pxr_actionability_bucket(evidence_need_class: str, blocker: str, conflict_lane: str) -> str:
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return "count_improving_gap"
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return "review_only_documentation"
    if blocker == "activity_present_manual_confirmation_required":
        return "supportive_manual_confirmation"
    if conflict_lane in {
        "exact_human_dual_mode_activity_conflict",
        "direct_human_qhts_active_inactive_conflict",
        "direct_human_qhts_proxy_conflict",
    }:
        return "low_probability_conflict_cleanup"
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return "actionable_conflict_resolution"
    if evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution":
        return "review_only_documentation"
    return "count_improving_gap"


def _pxr_stop_condition(evidence_need_class: str, blocker: str, ligand: str) -> str:
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return (
            f"Stop if evidence for {ligand} remains qualitative-only or lacks a quantitative human NR1I2/PXR value/proxy; "
            "keep deferred and leave binder fields blank."
        )
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return (
            f"Stop after documenting the current inactive-only human NR1I2/PXR qHTS record for {ligand}; "
            "keep review-only and do not convert it into an authoritative non-binder claim."
        )
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return f"Stop if no target-specific human PXR binder evidence is found for {ligand}; keep deferred and do not fill binder fields."
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return f"Stop if evidence remains proxy-only or conflicting for {ligand}; keep deferred and do not force a non-binder label."
    if evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution":
        return f"Stop if the source does not improve on the current weak upper-bound signal for {ligand}; keep review-only and leave quantitative binding blank."
    return f"Stop if no human NR1I2/PXR target-specific evidence is found for {ligand}; keep deferred."


def _pxr_claim_impact(evidence_need_class: str, blocker: str, actionability_bucket: str) -> str:
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return "potential_count_improving_if_quantitative_binder_provenance_found"
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return "count_neutral_review_only_confirmation"
    if blocker == "activity_present_manual_confirmation_required":
        return "manual_confirmation_needed_before_count_improving"
    if actionability_bucket == "low_probability_conflict_cleanup":
        return "low_probability_count_improving_only_if_orthogonal_human_source_found"
    if actionability_bucket == "actionable_conflict_resolution":
        return "potential_count_improving_if_conflict_resolved"
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return "potential_count_improving_if_target_specific_binder_found"
    if evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution":
        return "count_neutral_review_only_confirmation"
    return "potential_count_improving_if_target_specific_negative_found"


def _pxr_tier(evidence_need_class: str, blocker: str, actionability_bucket: str) -> str:
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return "P0_count_improving_binder_gap"
    if blocker == "inactive_only_human_pxr_qhts_review_only":
        return "P3_review_only_documentation"
    if blocker == "activity_present_manual_confirmation_required":
        return "P2_supportive_manual_confirmation"
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return "P0_count_improving_binder_gap"
    if actionability_bucket == "low_probability_conflict_cleanup":
        return "P2_low_probability_conflict_cleanup"
    if actionability_bucket == "actionable_conflict_resolution":
        return "P2_conflict_resolution"
    if evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution":
        return "P3_review_only_documentation"
    return "P1_count_improving_negative_gap"


def _build_ca2_rows(capture_payload: dict[str, Any], commit_payload: dict[str, Any]) -> list[dict[str, Any]]:
    commit_rows = _join_by_step(commit_payload.get("rows", []) or [])
    rows: list[dict[str, Any]] = []
    for row in capture_payload.get("rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        blocker = str(row.get("manual_promotion_blocker", "")).strip()
        review_phase = str(row.get("review_phase", "")).strip() or str(commit_rows.get(packet_step, {}).get("review_phase", "")).strip()
        ligand = str(row.get("ligand", "")).strip()
        actionability_bucket = _ca2_actionability_bucket(blocker)
        rows.append(
            {
                "queue_rank": 0,
                "family": "ca2",
                "priority_tier": _ca2_tier(blocker),
                "phase_or_band": review_phase,
                "priority_rank": int(str(row.get("capture_rank", "999")).strip() or 999),
                "packet_step": packet_step,
                "ligand": ligand,
                "current_policy_bucket": "review_only",
                "evidence_need_class": (
                    "direct_ca2_negative_evidence"
                    if blocker == "no_direct_ca2_negative_evidence_located_after_research"
                    else "ca2_conflict_reassessment"
                ),
                "claim_impact": _ca2_claim_impact(blocker),
                "actionability_bucket": actionability_bucket,
                "state_change_potential": _ca2_state_change_potential(blocker),
                "conflict_lane": "",
                "search_scope": _ca2_search_scope(blocker),
                "source_status": str(row.get("capture_status", "")).strip(),
                "blocking_reason": blocker,
                "next_required_action": str(row.get("manual_next_required_action", "")).strip(),
                "primary_source_title": str(row.get("source_title", "")).strip(),
                "primary_source_url": str(row.get("source_url", "")).strip(),
                "source_note": str(row.get("manual_decision_note", "")).strip(),
                "stop_condition": _ca2_stop_condition(blocker),
                "promotion_if_resolved": "yes" if blocker == "no_direct_ca2_negative_evidence_located_after_research" else "no",
                "source_artifact": DEFAULT_CA2_CAPTURE_SHEET_JSON,
            }
        )
    return rows


def _build_pxr_rows(capture_payload: dict[str, Any], commit_payload: dict[str, Any]) -> list[dict[str, Any]]:
    commit_rows = _join_by_step(commit_payload.get("rows", []) or [])
    rows: list[dict[str, Any]] = []
    for row in capture_payload.get("rows", []) or []:
        packet_step = str(row.get("packet_step", "")).strip()
        commit_row = commit_rows.get(packet_step, {})
        blocker = str(row.get("manual_promotion_blocker", "")).strip()
        evidence_need_class = str(row.get("evidence_need_class", "")).strip()
        ligand = str(row.get("replacement_ligand_id", "")).strip()
        source_title = str(row.get("source_title", "")).strip()
        source_url = str(row.get("source_url", "")).strip()
        source_note = str(row.get("source_note", "")).strip()
        conflict_lane = _pxr_conflict_lane(blocker, source_title, source_url, source_note)
        state_change_potential = _pxr_state_change_potential(evidence_need_class, blocker, conflict_lane)
        actionability_bucket = _pxr_actionability_bucket(evidence_need_class, blocker, conflict_lane)
        rows.append(
            {
                "queue_rank": 0,
                "family": "pxr",
                "priority_tier": _pxr_tier(evidence_need_class, blocker, actionability_bucket),
                "phase_or_band": str(commit_row.get("plan_phase", "")).strip(),
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "packet_step": packet_step,
                "ligand": ligand,
                "current_policy_bucket": str(row.get("commit_status", "")).strip() or str(commit_row.get("commit_status", "")).strip(),
                "evidence_need_class": evidence_need_class,
                "claim_impact": _pxr_claim_impact(evidence_need_class, blocker, actionability_bucket),
                "actionability_bucket": actionability_bucket,
                "state_change_potential": state_change_potential,
                "conflict_lane": conflict_lane,
                "search_scope": _pxr_search_scope(evidence_need_class, blocker),
                "source_status": str(row.get("capture_status", "")).strip(),
                "blocking_reason": blocker,
                "next_required_action": str(row.get("manual_next_required_action", "")).strip(),
                "primary_source_title": source_title,
                "primary_source_url": source_url,
                "source_note": source_note,
                "stop_condition": _pxr_stop_condition(evidence_need_class, blocker, ligand),
                "promotion_if_resolved": (
                    "no"
                    if blocker == "inactive_only_human_pxr_qhts_review_only"
                    or evidence_need_class == "target_specific_human_pxr_negative_like_conflict_resolution"
                    else "yes"
                ),
                "source_artifact": DEFAULT_PXR_CAPTURE_SHEET_JSON,
            }
        )
    return rows


def build_payload(
    ca2_capture_payload: dict[str, Any],
    ca2_commit_payload: dict[str, Any],
    pxr_capture_payload: dict[str, Any],
    pxr_commit_payload: dict[str, Any],
) -> dict[str, Any]:
    rows = _build_ca2_rows(ca2_capture_payload, ca2_commit_payload) + _build_pxr_rows(pxr_capture_payload, pxr_commit_payload)
    rows.sort(
        key=lambda row: (
            TIER_ORDER.get(str(row.get("priority_tier", "")), 9),
            STATE_CHANGE_ORDER.get(str(row.get("state_change_potential", "")), 9),
            int(row.get("priority_rank", 999) or 999),
            str(row.get("family", "")),
            str(row.get("packet_step", "")),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["queue_rank"] = idx

    summary = {
        "queue_row_count": len(rows),
        "family_count": len({str(row.get("family", "")) for row in rows}),
        "high_priority_count": sum(
            1 for row in rows if str(row.get("priority_tier", "")).startswith(("P0_", "P1_"))
        ),
        "count_improving_candidate_count": sum(
            1 for row in rows if "potential_count_improving" in str(row.get("claim_impact", ""))
        ),
        "supportive_manual_confirmation_count": sum(
            1 for row in rows if str(row.get("actionability_bucket", "")).strip() == "supportive_manual_confirmation"
        ),
        "actionable_conflict_resolution_count": sum(
            1 for row in rows if str(row.get("actionability_bucket", "")).strip() == "actionable_conflict_resolution"
        ),
        "low_probability_conflict_count": sum(
            1 for row in rows if str(row.get("actionability_bucket", "")).strip() == "low_probability_conflict_cleanup"
        ),
        "review_only_documentation_count": sum(
            1 for row in rows if str(row.get("priority_tier", "")) == "P3_review_only_documentation"
        ),
        "next_required_step": (
            "Work the true count-improving binder/negative gaps first, keep supportive manual-confirmation rows on their own lane, and only touch low-probability conflict cleanup rows when an orthogonal exact human source could realistically change the blocker."
            if any("potential_count_improving" in str(row.get("claim_impact", "")) for row in rows)
            else "No strong CA2/PXR count-improving queue rows remain. Keep supportive-manual-confirmation and low-probability conflict cleanup on exact-source-only lanes, and preserve review-only freezes unless a clearly stronger human target-specific source appears."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Evidence Acquisition Queue",
        "",
        f"- queue_row_count: `{s['queue_row_count']}`",
        f"- family_count: `{s['family_count']}`",
        f"- high_priority_count: `{s['high_priority_count']}`",
        f"- count_improving_candidate_count: `{s['count_improving_candidate_count']}`",
        f"- supportive_manual_confirmation_count: `{s['supportive_manual_confirmation_count']}`",
        f"- actionable_conflict_resolution_count: `{s['actionable_conflict_resolution_count']}`",
        f"- low_probability_conflict_count: `{s['low_probability_conflict_count']}`",
        f"- review_only_documentation_count: `{s['review_only_documentation_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Queue",
        "",
        "| queue_rank | family | tier | phase | priority_rank | packet_step | ligand | claim_impact | actionability_bucket | state_change_potential |",
        "| ---: | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['family']}` | `{row['priority_tier']}` | `{row['phase_or_band']}` | "
            f"{row['priority_rank']} | `{row['packet_step']}` | `{row['ligand']}` | `{row['claim_impact']}` | "
            f"`{row.get('actionability_bucket', '')}` | `{row.get('state_change_potential', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Search Briefs",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"- `{row['family']}:{row['packet_step']}` search `{row['search_scope']}`. Stop condition: {row['stop_condition']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2/PXR evidence acquisition queue focused on true claim-readiness blockers.")
    parser.add_argument("--ca2-capture-sheet-json", default=DEFAULT_CA2_CAPTURE_SHEET_JSON)
    parser.add_argument("--ca2-commit-packet-json", default=DEFAULT_CA2_COMMIT_PACKET_JSON)
    parser.add_argument("--pxr-capture-sheet-json", default=DEFAULT_PXR_CAPTURE_SHEET_JSON)
    parser.add_argument("--pxr-commit-packet-json", default=DEFAULT_PXR_COMMIT_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_capture_sheet_json),
        _load_json(args.ca2_commit_packet_json),
        _load_json(args.pxr_capture_sheet_json),
        _load_json(args.pxr_commit_packet_json),
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
