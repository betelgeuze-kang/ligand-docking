#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUEUE_JSON = "runs/family_evidence_acquisition_queue_current.json"
DEFAULT_PXR_LITERATURE_OVERLAY_JSON = "runs/pxr_literature_candidate_overlay_current.json"
DEFAULT_OUT_JSON = "runs/family_evidence_investigator_packet_current.json"
DEFAULT_OUT_CSV = "runs/family_evidence_investigator_packet_current.csv"
DEFAULT_OUT_MD = "runs/family_evidence_investigator_packet_current.md"
DEFAULT_TOP_N = 6


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


def _overlay_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _is_actionable_focus_row(row: dict[str, Any]) -> bool:
    actionability_bucket = str(row.get("actionability_bucket", "")).strip()
    promotion_if_resolved = str(row.get("promotion_if_resolved", "")).strip().lower()
    return actionability_bucket in {"count_improving_gap", "actionable_conflict_resolution"} and promotion_if_resolved == "yes"


def _is_low_probability_conflict_focus_row(row: dict[str, Any]) -> bool:
    return str(row.get("actionability_bucket", "")).strip() == "low_probability_conflict_cleanup"


def _pubmed_url(query: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(query)}"


def _europepmc_url(query: str) -> str:
    return f"https://europepmc.org/search?query={quote_plus(query)}"


def _search_query(row: dict[str, Any]) -> str:
    ligand = str(row.get("ligand", "")).strip()
    family = str(row.get("family", "")).strip()
    blocker = str(row.get("blocking_reason", "")).strip()
    evidence_need_class = str(row.get("evidence_need_class", "")).strip()
    conflict_lane = str(row.get("conflict_lane", "")).strip()

    if family == "ca2":
        return (
            f'"{ligand}" AND ("carbonic anhydrase II" OR "CA II" OR CA2) '
            'AND (inhibition OR activity OR binding OR inactive OR "no inhibition")'
        )

    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return (
            f'"{ligand}" AND ("pregnane X receptor" OR PXR OR NR1I2) '
            'AND (agonist OR antagonist OR transactivation OR coactivator OR binding) '
            'AND (human OR "cell free" OR TR-FRET OR reporter)'
        )
    if conflict_lane in {"direct_human_qhts_active_inactive_conflict", "direct_human_qhts_proxy_conflict"}:
        return (
            f'"{ligand}" AND ("pregnane X receptor" OR PXR OR NR1I2) '
            'AND (binding OR transactivation OR reporter OR activation) '
            'AND (human OR orthogonal OR validation)'
        )
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return (
            f'"{ligand}" AND ("pregnane X receptor" OR PXR OR NR1I2 OR SXR) '
            'AND (binding OR agonist OR activation OR transactivation) '
            'AND (EC50 OR IC50 OR Ki OR Kd OR potency OR affinity)'
        )
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return (
            f'"{ligand}" AND ("pregnane X receptor" OR PXR OR NR1I2) '
            'AND (binding OR agonist OR activation OR transactivation)'
        )
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return (
            f'"{ligand}" AND ("pregnane X receptor" OR PXR OR NR1I2) '
            'AND (agonist OR antagonist OR binding OR activation OR transactivation)'
        )
    return (
        f'"{ligand}" AND ("pregnane X receptor" OR PXR OR NR1I2) '
        'AND (activity OR binding OR agonist OR antagonist OR activation)'
    )


def _primary_search_route(row: dict[str, Any]) -> tuple[str, str]:
    family = str(row.get("family", "")).strip()
    if family == "ca2":
        return "PubMed exact target query", _pubmed_url(_search_query(row))
    return "Current ChEMBL/PXR anchor", str(row.get("primary_source_url", "")).strip()


def _secondary_search_route(row: dict[str, Any]) -> tuple[str, str]:
    family = str(row.get("family", "")).strip()
    if family == "ca2":
        return "Europe PMC exact target query", _europepmc_url(_search_query(row))
    return "PubMed exact target query", _pubmed_url(_search_query(row))


def _tertiary_search_route(row: dict[str, Any]) -> tuple[str, str]:
    family = str(row.get("family", "")).strip()
    if family == "ca2":
        return "Current anchor review", str(row.get("primary_source_url", "")).strip()
    return "Europe PMC exact target query", _europepmc_url(_search_query(row))


def _acceptance_criteria(row: dict[str, Any]) -> str:
    family = str(row.get("family", "")).strip()
    blocker = str(row.get("blocking_reason", "")).strip()
    evidence_need_class = str(row.get("evidence_need_class", "")).strip()
    conflict_lane = str(row.get("conflict_lane", "")).strip()

    if family == "ca2":
        return (
            "Accept only direct human CA2-specific assay evidence that explicitly reports inactivity, "
            "no inhibition, or a target-specific upper-bound signal for the ligand."
        )
    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return (
            "Accept only orthogonal exact human NR1I2/PXR evidence strong enough to explain or override the "
            "current antagonist-versus-agonist dual-mode anchor; otherwise preserve the defer lane."
        )
    if conflict_lane in {"direct_human_qhts_active_inactive_conflict", "direct_human_qhts_proxy_conflict"}:
        return (
            "Accept only exact non-qHTS human NR1I2/PXR evidence strong enough to dominate the current direct "
            "human qHTS disagreement or ambiguity."
        )
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return (
            "Accept only human NR1I2/PXR target-specific binder or direct-binding evidence with explicit "
            "quantitative output or claim-safe activity proxy details and unambiguous assay context."
        )
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return (
            "Accept only human NR1I2/PXR target-specific binder or direct-binding evidence with explicit "
            "target assay details and unambiguous ligand identity."
        )
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return (
            "Accept only human NR1I2/PXR evidence strong enough to dominate the current proxy conflict, "
            "and only promote if it cleanly supports a safer classification."
        )
    return (
        "Accept only human NR1I2/PXR target-specific no-activity, upper-bound, or clearly negative evidence "
        "with explicit assay target and species."
    )


def _rejection_criteria(row: dict[str, Any]) -> str:
    family = str(row.get("family", "")).strip()
    blocker = str(row.get("blocking_reason", "")).strip()
    evidence_need_class = str(row.get("evidence_need_class", "")).strip()
    conflict_lane = str(row.get("conflict_lane", "")).strip()

    if family == "ca2":
        return (
            "Reject general carbonic-anhydrase mechanism papers, non-CA2 isoform results, docking-only claims, "
            "or papers that never state a direct CA2 assay outcome."
        )
    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return (
            "Reject the current TR-FRET anchor restated in weaker form, non-human boundary papers, and generic "
            "metabolism/induction studies that do not add an orthogonal exact human NR1I2/PXR assay."
        )
    if conflict_lane in {"direct_human_qhts_active_inactive_conflict", "direct_human_qhts_proxy_conflict"}:
        return (
            "Reject additional qHTS-only restatements, proxy-only ADME responses, and non-human evidence that "
            "cannot dominate the current direct-human conflict."
        )
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return (
            "Reject qualitative-only rexinoid context, CYP3A induction without explicit quantitative NR1I2/PXR "
            "target output, and non-human-only evidence."
        )
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return (
            "Reject generic RXR/retinoid mechanism papers, CYP3A induction without explicit PXR target context, "
            "or non-human-only evidence."
        )
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return (
            "Reject proxy-only ADME responses, non-target-specific transcriptional effects, and non-human evidence "
            "that cannot resolve the current human PXR conflict."
        )
    return (
        "Reject absence-of-record arguments, generic induction papers without explicit NR1I2/PXR target context, "
        "and non-human-only evidence."
    )


def _handoff_if_resolved(row: dict[str, Any]) -> str:
    family = str(row.get("family", "")).strip()
    blocker = str(row.get("blocking_reason", "")).strip()
    evidence_need_class = str(row.get("evidence_need_class", "")).strip()
    actionability_bucket = str(row.get("actionability_bucket", "")).strip()

    if family == "ca2":
        return "Attach the exact source to the CA2 capture sheet, rerun CA2 intake/commit packet refresh, and reopen only if direct CA2-negative evidence is explicit."
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return (
            "Attach the exact quantitative source to the PXR capture sheet, rerun capture intake and commit refresh, "
            "and only fill binder-facing fields if claim-safe quantitative provenance is explicit."
        )
    if evidence_need_class == "target_specific_human_pxr_binder_evidence":
        return "Attach the source to the PXR capture sheet, rerun capture intake and commit packet refresh, and fill binder-facing fields only if the human PXR binder evidence is explicit."
    if actionability_bucket == "low_probability_conflict_cleanup":
        return "Attach the orthogonal exact-human source only if it clearly dominates the current conflict; otherwise rerun refresh only to preserve the defer lane with cleaner provenance."
    if blocker == "activity_proxy_conflicts_with_non_binder":
        return "Attach the stronger resolving source, rerun PXR capture intake and commit refresh, and only relax defer if the blocker is reduced cleanly."
    return "Attach the exact human PXR source, rerun PXR capture intake and commit refresh, and only move the row if the target-specific gap truly closes."


def _investigator_note_template(row: dict[str, Any]) -> str:
    ligand = str(row.get("ligand", "")).strip()
    family = str(row.get("family", "")).strip()
    blocker = str(row.get("blocking_reason", "")).strip()
    conflict_lane = str(row.get("conflict_lane", "")).strip()
    if family == "ca2":
        return (
            f"For {ligand}, capture the exact CA2 assay language, species, and inactivity/upper-bound wording. "
            "If the paper is only mechanism-level or non-CA2-specific, leave the row review-only."
        )
    if blocker == "quantitative_binding_value_or_activity_proxy_missing":
        return (
            f"For {ligand}, capture the exact human NR1I2/PXR assay wording, quantitative value/proxy, units, and provenance. "
            "If the source is only qualitative rexinoid context, preserve the current deferred quantitative-gap bucket."
        )
    if conflict_lane == "exact_human_dual_mode_activity_conflict":
        return (
            f"For {ligand}, treat the current human dual-mode antagonist/agonist anchor as the blocker. "
            "Only capture orthogonal exact-human NR1I2/PXR assays that could explain or dominate that split."
        )
    if conflict_lane in {"direct_human_qhts_active_inactive_conflict", "direct_human_qhts_proxy_conflict"}:
        return (
            f"For {ligand}, avoid more qHTS restatements unless they add exact human assay detail. "
            "Look for orthogonal human NR1I2/PXR sources that could dominate the current qHTS conflict."
        )
    return (
        f"For {ligand}, capture the exact NR1I2/PXR target wording, assay type, species, and quantitative activity outcome. "
        "If the source is proxy-only or not target-specific, preserve the current bucket."
    )


def build_payload(
    queue_payload: dict[str, Any],
    top_n: int = DEFAULT_TOP_N,
    pxr_literature_overlay_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_rows = list(queue_payload.get("rows", []) or [])
    actionable_rows = [row for row in queue_rows if _is_actionable_focus_row(row)]
    low_probability_conflict_rows = [row for row in queue_rows if _is_low_probability_conflict_focus_row(row)]
    focus_source_rows = actionable_rows or low_probability_conflict_rows or queue_rows
    focus_rows = focus_source_rows[: max(top_n, 0)]
    literature_overlay_by_step = _overlay_by_step(pxr_literature_overlay_payload)

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(focus_rows, start=1):
        primary_label, primary_url = _primary_search_route(row)
        secondary_label, secondary_url = _secondary_search_route(row)
        tertiary_label, tertiary_url = _tertiary_search_route(row)
        literature_overlay = literature_overlay_by_step.get(str(row.get("packet_step", "")).strip(), {})
        rows.append(
            {
                "focus_rank": idx,
                "queue_rank": int(row.get("queue_rank", 0) or 0),
                "family": str(row.get("family", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "priority_tier": str(row.get("priority_tier", "")).strip(),
                "phase_or_band": str(row.get("phase_or_band", "")).strip(),
                "current_policy_bucket": str(row.get("current_policy_bucket", "")).strip(),
                "claim_impact": str(row.get("claim_impact", "")).strip(),
                "actionability_bucket": str(row.get("actionability_bucket", "")).strip(),
                "state_change_potential": str(row.get("state_change_potential", "")).strip(),
                "conflict_lane": str(row.get("conflict_lane", "")).strip(),
                "search_query": _search_query(row),
                "current_anchor_title": str(row.get("primary_source_title", "")).strip(),
                "current_anchor_url": str(row.get("primary_source_url", "")).strip(),
                "primary_search_route_label": primary_label,
                "primary_search_route_url": primary_url,
                "secondary_search_route_label": secondary_label,
                "secondary_search_route_url": secondary_url,
                "tertiary_search_route_label": tertiary_label,
                "tertiary_search_route_url": tertiary_url,
                "acceptance_criteria": _acceptance_criteria(row),
                "rejection_criteria": _rejection_criteria(row),
                "stop_condition": str(row.get("stop_condition", "")).strip(),
                "promotion_if_resolved": str(row.get("promotion_if_resolved", "")).strip(),
                "handoff_if_resolved": _handoff_if_resolved(row),
                "investigator_note_template": _investigator_note_template(row),
                "literature_candidate_status": str(literature_overlay.get("candidate_status", "")).strip(),
                "literature_candidate_count": int(literature_overlay.get("candidate_count", 0) or 0),
                "literature_high_signal_candidate_count": int(literature_overlay.get("high_signal_candidate_count", 0) or 0),
                "best_candidate_pmid": str(literature_overlay.get("best_candidate_pmid", "")).strip(),
                "best_candidate_title": str(literature_overlay.get("best_candidate_title", "")).strip(),
                "best_candidate_url": str(literature_overlay.get("best_candidate_url", "")).strip(),
                "best_candidate_signal": str(literature_overlay.get("best_candidate_signal", "")).strip(),
            }
        )

    summary = {
        "focus_row_count": len(rows),
        "requested_top_n": top_n,
        "focus_mode": (
            "actionable_non_confirmation_rows"
            if actionable_rows
            else "low_probability_conflict_cleanup"
            if low_probability_conflict_rows
            else "queue_fallback"
        ),
        "included_family_count": len({str(row.get("family", "")).strip() for row in rows if str(row.get("family", "")).strip()}),
        "count_improving_focus_count": sum(
            1 for row in rows if "potential_count_improving" in str(row.get("claim_impact", ""))
        ),
        "low_probability_conflict_focus_count": sum(
            1 for row in rows if str(row.get("actionability_bucket", "")).strip() == "low_probability_conflict_cleanup"
        ),
        "rows_with_literature_candidates": sum(1 for row in rows if int(row.get("literature_candidate_count", 0) or 0) > 0),
        "rows_with_high_signal_literature_candidates": sum(
            1 for row in rows if int(row.get("literature_high_signal_candidate_count", 0) or 0) > 0
        ),
        "primary_focus_ligand": str(rows[0].get("ligand", "")).strip() if rows else "",
        "queue_span": f"{rows[0]['queue_rank']}-{rows[-1]['queue_rank']}" if rows else "",
        "next_required_step": (
            "Work the actionable count-improving/conflict-closing rows in order, capture only exact target-specific evidence, and use the separate PXR confirmation packet for supportive binder manual-confirmation rows."
            if actionable_rows
            else "No true count-improving investigator rows remain. Treat the current focus rows as low-probability conflict cleanup only, accept only orthogonal exact-human sources, and otherwise preserve the current defer lanes."
            if low_probability_conflict_rows
            else "Work the focus rows in order, capture only exact target-specific evidence, and rerun the family capture/commit refresh immediately after any row gains claim-safe support."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Evidence Investigator Packet",
        "",
        f"- focus_row_count: `{s['focus_row_count']}`",
        f"- requested_top_n: `{s['requested_top_n']}`",
        f"- focus_mode: `{s['focus_mode']}`",
        f"- included_family_count: `{s['included_family_count']}`",
        f"- count_improving_focus_count: `{s['count_improving_focus_count']}`",
        f"- low_probability_conflict_focus_count: `{s['low_probability_conflict_focus_count']}`",
        f"- rows_with_literature_candidates: `{s['rows_with_literature_candidates']}`",
        f"- rows_with_high_signal_literature_candidates: `{s['rows_with_high_signal_literature_candidates']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- queue_span: `{s['queue_span']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Focus Table",
        "",
        "| focus_rank | queue_rank | family | packet_step | ligand | tier | actionability_bucket | state_change_potential | primary_search_route |",
        "| ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['focus_rank']} | {row['queue_rank']} | `{row['family']}` | `{row['packet_step']}` | "
            f"`{row['ligand']}` | `{row['priority_tier']}` | `{row['actionability_bucket']}` | `{row['state_change_potential']}` | "
            f"[{row['primary_search_route_label']}]({row['primary_search_route_url']}) |"
        )
    lines.extend(["", "## Investigation Briefs", ""])
    for row in payload["rows"]:
        lines.append(f"### `{row['focus_rank']}. {row['ligand']} ({row['family']}:{row['packet_step']})`")
        lines.append("")
        lines.append(f"- Search query: `{row['search_query']}`")
        lines.append(f"- Current anchor: [{row['current_anchor_title']}]({row['current_anchor_url']})")
        if row["literature_candidate_status"]:
            lines.append(
                f"- Literature triage: `{row['literature_candidate_status']}`"
                + (
                    f" via PMID {row['best_candidate_pmid']} [{row['best_candidate_title']}]({row['best_candidate_url']})"
                    if row["best_candidate_pmid"] and row["best_candidate_url"]
                    else ""
                )
            )
        lines.append(f"- Primary route: [{row['primary_search_route_label']}]({row['primary_search_route_url']})")
        lines.append(f"- Secondary route: [{row['secondary_search_route_label']}]({row['secondary_search_route_url']})")
        lines.append(f"- Tertiary route: [{row['tertiary_search_route_label']}]({row['tertiary_search_route_url']})")
        lines.append(f"- Accept if: {row['acceptance_criteria']}")
        lines.append(f"- Reject if: {row['rejection_criteria']}")
        lines.append(f"- Stop condition: {row['stop_condition']}")
        lines.append(f"- Handoff if resolved: {row['handoff_if_resolved']}")
        lines.append(f"- Note template: {row['investigator_note_template']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a top-N investigator packet for the highest-value CA2/PXR evidence-acquisition rows.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--pxr-literature-overlay-json", default=DEFAULT_PXR_LITERATURE_OVERLAY_JSON)
    parser.add_argument("--top-n", default=DEFAULT_TOP_N, type=int)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.queue_json),
        top_n=args.top_n,
        pxr_literature_overlay_payload=_load_json(args.pxr_literature_overlay_json)
        if _resolve(args.pxr_literature_overlay_json).exists()
        else {},
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
