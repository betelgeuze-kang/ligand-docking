#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_INVESTIGATOR_PACKET_JSON = "runs/family_evidence_investigator_packet_current.json"
DEFAULT_LITERATURE_OVERLAY_JSON = "runs/pxr_literature_candidate_overlay_current.json"
DEFAULT_OUT_JSON = "runs/pxr_conflict_resolver_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_conflict_resolver_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_conflict_resolver_packet_current.md"


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


def _by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _recommended_resolution(capture_row: dict[str, Any], literature_row: dict[str, Any]) -> str:
    lane = _conflict_lane(capture_row, literature_row)
    if lane == "exact_human_dual_mode_activity_conflict":
        return "keep_deferred_exact_human_dual_mode_conflict"
    if lane == "weak_human_proxy_plus_nonhuman_boundary_conflict":
        return "keep_deferred_nonhuman_boundary_review"
    if lane == "direct_human_qhts_active_inactive_conflict":
        return "keep_deferred_direct_human_qhts_conflict"
    if lane == "direct_human_qhts_proxy_conflict":
        return "keep_deferred_pubchem_proxy_conflict"
    return "keep_deferred_until_exact_human_target_source_appears"


def _has_exact_human_dual_mode_conflict(capture_row: dict[str, Any]) -> bool:
    source_note = str(capture_row.get("source_note", "")).strip().lower()
    return (
        "antagonist activity at human nr1i2" in source_note
        and "agonist activity at human nr1i2" in source_note
    )


def _has_nonhuman_boundary_context(literature_row: dict[str, Any]) -> bool:
    candidate_status = str(literature_row.get("candidate_status", "")).strip()
    return candidate_status == "title_direct_nonhuman_candidates_present"


def _conflict_lane(capture_row: dict[str, Any], literature_row: dict[str, Any]) -> str:
    if _has_exact_human_dual_mode_conflict(capture_row):
        return "exact_human_dual_mode_activity_conflict"
    candidate_status = str(literature_row.get("candidate_status", "")).strip()
    source_title = str(capture_row.get("source_title", "")).strip().lower()
    source_url = str(capture_row.get("source_url", "")).strip().lower()
    source_note = str(capture_row.get("source_note", "")).strip().lower()
    has_pubchem = "pubchem" in source_title or "pubchem" in source_url
    has_active = "active" in source_note
    has_inactive = "inactive" in source_note

    if has_pubchem and has_active and has_inactive:
        return "direct_human_qhts_active_inactive_conflict"
    if candidate_status == "title_direct_nonhuman_candidates_present":
        return "weak_human_proxy_plus_nonhuman_boundary_conflict"
    if has_pubchem:
        return "direct_human_qhts_proxy_conflict"
    return "generic_human_proxy_conflict"


def _state_change_potential(conflict_lane: str) -> str:
    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return "low"
    if conflict_lane == "weak_human_proxy_plus_nonhuman_boundary_conflict":
        return "medium"
    if conflict_lane in {"direct_human_qhts_active_inactive_conflict", "direct_human_qhts_proxy_conflict"}:
        return "low"
    return "medium"


def _resolver_goal(conflict_lane: str, ligand: str) -> str:
    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return (
            f"For {ligand}, preserve the exact human NR1I2/PXR antagonist-versus-agonist dual-mode conflict "
            "as the primary blocker and keep any nonhuman literature only as boundary context."
        )
    if conflict_lane == "weak_human_proxy_plus_nonhuman_boundary_conflict":
        return (
            f"For {ligand}, confirm whether the current blocker should remain a deferred weak-human-proxy lane "
            "with an explicit nonhuman literature boundary note."
        )
    if conflict_lane == "direct_human_qhts_active_inactive_conflict":
        return (
            f"For {ligand}, confirm that direct human PXR qHTS active/inactive disagreement remains unresolved "
            "and blocks any cleaner non-binder label."
        )
    if conflict_lane == "direct_human_qhts_proxy_conflict":
        return (
            f"For {ligand}, confirm whether the current direct human PXR qHTS proxy stays too ambiguous to relax the defer bucket."
        )
    return f"For {ligand}, resolve whether the current human PXR proxy conflict can be reduced by an exact target-specific source."


def _claim_move_if_resolved(conflict_lane: str) -> str:
    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return "unlikely_count_improving_without_new_orthogonal_human_source_overriding_exact_dual_mode_conflict"
    if conflict_lane == "weak_human_proxy_plus_nonhuman_boundary_conflict":
        return "possible_boundary_note_tightening_but_not_authoritative_claim_promotion"
    if conflict_lane in {"direct_human_qhts_active_inactive_conflict", "direct_human_qhts_proxy_conflict"}:
        return "likely_keep_deferred_unless_exact_human_target_source_dominates_current_conflict"
    return "possible_defer_lane_reduction_if_exact_human_target_source_dominates"


def build_payload(
    capture_sheet_payload: dict[str, Any],
    investigator_packet_payload: dict[str, Any],
    literature_overlay_payload: dict[str, Any],
) -> dict[str, Any]:
    investigator_by_step = _by_step(investigator_packet_payload)
    literature_by_step = _by_step(literature_overlay_payload)

    rows: list[dict[str, Any]] = []
    for capture_row in capture_sheet_payload.get("rows", []) or []:
        blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
        if blocker != "activity_proxy_conflicts_with_non_binder":
            continue
        packet_step = str(capture_row.get("packet_step", "")).strip()
        investigator_row = investigator_by_step.get(packet_step, {})
        literature_row = literature_by_step.get(packet_step, {})
        conflict_lane = _conflict_lane(capture_row, literature_row)
        state_change_potential = _state_change_potential(conflict_lane)
        nonhuman_boundary_context = _has_nonhuman_boundary_context(literature_row)
        rows.append(
            {
                "resolver_rank": 0,
                "priority_rank": int(capture_row.get("priority_rank", 999) or 999),
                "packet_step": packet_step,
                "ligand": str(capture_row.get("replacement_ligand_id", "")).strip(),
                "policy_bucket": str(capture_row.get("policy_bucket", "")).strip(),
                "capture_status": str(capture_row.get("capture_status", "")).strip(),
                "blocking_reason": blocker,
                "conflict_lane": conflict_lane,
                "state_change_potential": state_change_potential,
                "nonhuman_boundary_context": "yes" if nonhuman_boundary_context else "no",
                "conflict_source_title": str(capture_row.get("source_title", "")).strip(),
                "conflict_source_url": str(capture_row.get("source_url", "")).strip(),
                "conflict_source_note": str(capture_row.get("source_note", "")).strip(),
                "search_query": str(investigator_row.get("search_query", "")).strip(),
                "primary_search_route_label": str(investigator_row.get("primary_search_route_label", "")).strip(),
                "primary_search_route_url": str(investigator_row.get("primary_search_route_url", "")).strip(),
                "secondary_search_route_label": str(investigator_row.get("secondary_search_route_label", "")).strip(),
                "secondary_search_route_url": str(investigator_row.get("secondary_search_route_url", "")).strip(),
                "acceptance_criteria": str(investigator_row.get("acceptance_criteria", "")).strip()
                or "Accept only exact human NR1I2/PXR evidence that cleanly reduces the current conflict.",
                "rejection_criteria": str(investigator_row.get("rejection_criteria", "")).strip()
                or "Reject proxy-only, non-target-specific, or non-human evidence that does not reduce the current conflict.",
                "stop_condition": str(investigator_row.get("stop_condition", "")).strip()
                or "Keep deferred unless exact human NR1I2/PXR evidence clearly reduces the current blocker.",
                "literature_candidate_status": str(literature_row.get("candidate_status", "")).strip(),
                "best_candidate_pmid": str(literature_row.get("best_candidate_pmid", "")).strip(),
                "best_candidate_title": str(literature_row.get("best_candidate_title", "")).strip(),
                "best_candidate_url": str(literature_row.get("best_candidate_url", "")).strip(),
                "best_candidate_signal": str(literature_row.get("best_candidate_signal", "")).strip(),
                "resolver_goal": _resolver_goal(conflict_lane, str(capture_row.get("replacement_ligand_id", "")).strip()),
                "claim_move_if_resolved": _claim_move_if_resolved(conflict_lane),
                "recommended_resolution": _recommended_resolution(capture_row, literature_row),
            }
        )

    rows.sort(key=lambda row: (int(row.get("priority_rank", 999) or 999), str(row.get("packet_step", ""))))
    for idx, row in enumerate(rows, start=1):
        row["resolver_rank"] = idx

    summary = {
        "row_count": len(rows),
        "primary_focus_ligand": str(rows[0].get("ligand", "")).strip() if rows else "",
        "pubchem_conflict_count": sum(
            1
            for row in rows
            if "pubchem" in str(row.get("conflict_source_title", "")).lower()
            or "pubchem" in str(row.get("conflict_source_url", "")).lower()
        ),
        "title_direct_nonhuman_conflict_count": sum(
            1
            for row in rows
            if str(row.get("literature_candidate_status", "")).strip() == "title_direct_nonhuman_candidates_present"
        ),
        "exact_human_dual_mode_conflict_count": sum(
            1
            for row in rows
            if str(row.get("conflict_lane", "")).strip() == "exact_human_dual_mode_activity_conflict"
        ),
        "direct_human_qhts_conflict_count": sum(
            1
            for row in rows
            if str(row.get("conflict_lane", "")).strip() in {
                "direct_human_qhts_active_inactive_conflict",
                "direct_human_qhts_proxy_conflict",
            }
        ),
        "weak_human_nonhuman_boundary_conflict_count": sum(
            1
            for row in rows
            if str(row.get("conflict_lane", "")).strip() == "weak_human_proxy_plus_nonhuman_boundary_conflict"
        ),
        "nonhuman_boundary_context_count": sum(
            1 for row in rows if str(row.get("nonhuman_boundary_context", "")).strip() == "yes"
        ),
        "medium_state_change_potential_count": sum(
            1 for row in rows if str(row.get("state_change_potential", "")).strip() == "medium"
        ),
        "low_state_change_potential_count": sum(
            1 for row in rows if str(row.get("state_change_potential", "")).strip() == "low"
        ),
        "search_ready_count": sum(1 for row in rows if str(row.get("search_query", "")).strip()),
        "next_required_step": (
            "Treat exact-human dual-mode conflicts as source-fidelity closure lanes, keep nonhuman-boundary literature contextual, "
            "and work direct-human-qHTS conflicts only when an exact orthogonal human source could change the picture. "
            "Accept only exact human NR1I2/PXR evidence that reduces the blocker cleanly; otherwise keep the row deferred."
            if rows
            else "No active PXR conflict rows currently require a dedicated resolver packet."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Conflict Resolver Packet",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- pubchem_conflict_count: `{s['pubchem_conflict_count']}`",
        f"- title_direct_nonhuman_conflict_count: `{s['title_direct_nonhuman_conflict_count']}`",
        f"- exact_human_dual_mode_conflict_count: `{s['exact_human_dual_mode_conflict_count']}`",
        f"- direct_human_qhts_conflict_count: `{s['direct_human_qhts_conflict_count']}`",
        f"- weak_human_nonhuman_boundary_conflict_count: `{s['weak_human_nonhuman_boundary_conflict_count']}`",
        f"- nonhuman_boundary_context_count: `{s['nonhuman_boundary_context_count']}`",
        f"- medium_state_change_potential_count: `{s['medium_state_change_potential_count']}`",
        f"- low_state_change_potential_count: `{s['low_state_change_potential_count']}`",
        f"- search_ready_count: `{s['search_ready_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Conflict Rows",
        "",
        "| resolver_rank | ligand | conflict_lane | state_change_potential | nonhuman_boundary_context | packet_step | recommended_resolution | best_candidate_pmid |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['resolver_rank']} | `{row['ligand']}` | `{row['conflict_lane']}` | "
            f"`{row['state_change_potential']}` | `{row['nonhuman_boundary_context']}` | `{row['packet_step']}` | "
            f"`{row['recommended_resolution']}` | `{row['best_candidate_pmid'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a resolver packet for active PXR conflict rows.")
    parser.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    parser.add_argument("--investigator-packet-json", default=DEFAULT_INVESTIGATOR_PACKET_JSON)
    parser.add_argument("--literature-overlay-json", default=DEFAULT_LITERATURE_OVERLAY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.capture_sheet_json),
        _load_json(args.investigator_packet_json),
        _load_json(args.literature_overlay_json),
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
