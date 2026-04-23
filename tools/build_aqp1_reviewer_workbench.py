#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANUAL_VERDICT_HANDOFF_JSON = "runs/aqp1_manual_verdict_handoff_packet_current.json"
DEFAULT_NEGATIVE_REVIEW_HANDOFF_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_BINDER_REVIEW_BRIEF_JSON = "runs/aqp1_binder_review_brief_current.json"
DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_FIRST_SEED_ROW_PACKET_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_SEED_SYNC_PREVIEW_JSON = "runs/aqp1_seed_row_sync_apply_preview_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_reviewer_workbench_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_reviewer_workbench_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_reviewer_workbench_current.md"


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
    manual_verdict_handoff_payload: dict[str, Any],
    negative_review_handoff_payload: dict[str, Any],
    apply_draft_payload: dict[str, Any],
    binder_review_brief_payload: dict[str, Any],
    external_seed_payload: dict[str, Any],
    first_seed_row_packet_payload: dict[str, Any],
    seed_sync_preview_payload: dict[str, Any],
) -> dict[str, Any]:
    binder_brief_by_step = {
        str(row.get("packet_step", "")).strip(): row
        for row in (binder_review_brief_payload.get("rows", []) or [])
    }
    apply_draft_by_step = {
        str(row.get("packet_step", "")).strip(): row
        for row in (apply_draft_payload.get("rows", []) or [])
    }

    rows: list[dict[str, Any]] = []
    exact_human_provenance_count = 0
    for row in manual_verdict_handoff_payload.get("rows", []) or []:
        if str(row.get("section", "")).strip() != "binder_first_wave":
            continue
        packet_step = str(row.get("packet_step", "")).strip()
        brief = binder_brief_by_step.get(packet_step, {})
        draft = apply_draft_by_step.get(packet_step, {})
        provenance_status = str(
            draft.get("public_provenance_status", "") or brief.get("public_provenance_status", "")
        ).strip()
        provenance_signal = str(
            draft.get("public_provenance_signal", "") or brief.get("public_provenance_signal", "")
        ).strip()
        if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
            exact_human_provenance_count += 1
        focus_suffix = ""
        if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
            focus_suffix = " Exact human AQP1 target-activity provenance is present; keep replacement_reference_binding_kcal_mol blank."
        elif provenance_status == "compound_publicly_resolved_target_activity_absent":
            focus_suffix = " Public compound resolution exists, but exact human AQP1 target activity is absent in the current lane."
        elif provenance_status == "pubchem_resolved_chembl_target_pair_absent":
            focus_suffix = " PubChem resolves the compound, but the exact ChEMBL AQP1 pair is still absent."
        rows.append(
            {
                "workbench_section": "binder_first_wave",
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "label": str(row.get("candidate_name", "")).strip(),
                "current_focus": (
                    str(brief.get("review_focus", "Confirm review-only hold.")).strip()
                    + " Treat current evidence as functional potency only and leave claim-safe quantitative binding blank."
                    + focus_suffix
                ),
                "recommended_verdict": str(row.get("recommended_verdict", "")).strip(),
                "draft_manual_verdict_update": str(draft.get("draft_manual_verdict_update", row.get("draft_manual_verdict_update", ""))).strip(),
                "draft_manual_confidence_update": str(draft.get("draft_manual_confidence_update", row.get("draft_manual_confidence_update", ""))).strip(),
                "anchor": str(row.get("anchor", "")).strip(),
                "assay_surface": str(row.get("assay_surface", "")).strip(),
                "next_action": str(row.get("next_action", "")).strip(),
                "blocker_or_constraint": str(row.get("promotion_blocker", "")).strip(),
                "public_provenance_status": provenance_status,
                "public_provenance_signal": provenance_signal,
            }
        )

    for row in negative_review_handoff_payload.get("rows", []) or []:
        section = str(row.get("section", "")).strip()
        if section not in {"negative_slot_policy", "caution_or_defer_signal"}:
            continue
        rows.append(
            {
                "workbench_section": section,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "label": str(row.get("label", "")).strip(),
                "current_focus": (
                    "Keep review-only negative slot blocked."
                    if section == "negative_slot_policy"
                    else "Keep caution/defer reference out of packet rows."
                ),
                "recommended_verdict": str(row.get("recommended_resolution", "")).strip(),
                "draft_manual_verdict_update": "",
                "draft_manual_confidence_update": "",
                "anchor": "",
                "assay_surface": "",
                "next_action": str(row.get("next_action", "")).strip(),
                "blocker_or_constraint": str(row.get("promotion_blocker", "")).strip(),
            }
        )

    summary = {
        "target_id": str(manual_verdict_handoff_payload.get("summary", {}).get("target_id", "AQP1")).strip(),
        "endpoint_status": str(manual_verdict_handoff_payload.get("summary", {}).get("endpoint_status", "")).strip(),
        "authoritative_apply_allowed": False,
        "binder_first_wave_count": int(manual_verdict_handoff_payload.get("summary", {}).get("binder_first_wave_count", 0) or 0),
        "pending_manual_verdict_count": int(manual_verdict_handoff_payload.get("summary", {}).get("pending_manual_verdict_count", 0) or 0),
        "negative_slot_count": int(negative_review_handoff_payload.get("summary", {}).get("negative_slot_count", 0) or 0),
        "caution_or_defer_reference_count": int(negative_review_handoff_payload.get("summary", {}).get("caution_or_defer_reference_count", 0) or 0),
        "draft_prefill_count": int(apply_draft_payload.get("summary", {}).get("draft_prefill_count", 0) or 0),
        "ready_for_reviewer_fill_count": int(binder_review_brief_payload.get("summary", {}).get("ready_for_reviewer_fill_count", 0) or 0),
        "exact_human_provenance_count": exact_human_provenance_count,
        "evidence_mode": str(first_seed_row_packet_payload.get("summary", {}).get("evidence_mode", "functional_potency_staged_review_only")).strip(),
        "quantitative_binding_status": str(first_seed_row_packet_payload.get("summary", {}).get("quantitative_binding_status", "quantitative_binding_absent_claim_safe_kcal_missing")).strip(),
        "direct_quantitative_binding_candidate_count": int(external_seed_payload.get("summary", {}).get("direct_quantitative_binding_candidate_count", 0) or 0),
        "remaining_seed_unresolved_fields": str(
            first_seed_row_packet_payload.get("summary", {}).get("remaining_unresolved_fields", "replacement_reference_binding_kcal_mol")
        ).strip(),
        "remaining_seed_unresolved_field_count": int(first_seed_row_packet_payload.get("summary", {}).get("remaining_unresolved_field_count", 0) or 0),
        "today_focus": (
            "Finish the three first-wave binder manual verdicts, then confirm the three negative slots stay review-only, and keep caution/defer references out of packet rows."
            if int(manual_verdict_handoff_payload.get("summary", {}).get("pending_manual_verdict_count", 0) or 0) > 0
            else "Manual verdicts are already recorded. Use core_binder_01 as the first seed-row promotion target, keep the negative slots review-only, and treat current AQP1 evidence as functional potency staged only while quantitative binding stays absent."
        ),
        "next_required_step": (
            "Work top-down from binder_first_wave to negative_slot_policy. Keep all AQP1 work in draft/manual-review territory and do not reopen donor policy or authoritative apply."
            if int(manual_verdict_handoff_payload.get("summary", {}).get("pending_manual_verdict_count", 0) or 0) > 0
            else "Use core_binder_01 as the first seed-row promotion target, then return to negative_slot_policy. Keep all AQP1 work non-authoritative, carry only functional potency today, and leave replacement_reference_binding_kcal_mol blank until claim-safe quantitative binding is curated."
        ),
    }
    if summary["pending_manual_verdict_count"] > 0:
        checklist = [
            "Binder first: confirm bacopaside II, AqB013, and AqB011 stay keep_review_only with explicit manual notes.",
            "Negative second: confirm all three non-binder slots stay review-only and receive no proxy quantitative fill.",
            "Caution references last: keep tetraethylammonium and acetazolamide out of authoritative packet rows.",
            "Stop if any step would require reopening donor policy or authoritative apply; that is out of scope for this workbench.",
        ]
    else:
        checklist = [
            "Seed-row first: use bacopaside II core_binder_01 as the first non-authoritative promotion target.",
            "Treat the first-wave AQP1 binders as functional potency anchors only; do not reinterpret them as claim-safe quantitative binding.",
            "If a row carries exact human AQP1 target-activity provenance, confirm it stays nonbinding and does not fill replacement_reference_binding_kcal_mol.",
            "Leave only replacement_reference_binding_kcal_mol unresolved on the first staged row until curated quantitative binding exists.",
            "Negative second: confirm all three non-binder slots stay review-only and receive no proxy quantitative fill.",
            "Caution references last: keep tetraethylammonium and acetazolamide out of authoritative packet rows.",
            "Stop if any step would require reopening donor policy or authoritative apply; that is out of scope for this workbench.",
        ]
    return {"summary": summary, "checklist": checklist, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Reviewer Workbench",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        f"- binder_first_wave_count: `{s['binder_first_wave_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- caution_or_defer_reference_count: `{s['caution_or_defer_reference_count']}`",
        f"- draft_prefill_count: `{s['draft_prefill_count']}`",
        f"- ready_for_reviewer_fill_count: `{s['ready_for_reviewer_fill_count']}`",
        f"- exact_human_provenance_count: `{s['exact_human_provenance_count']}`",
        f"- evidence_mode: `{s['evidence_mode']}`",
        f"- quantitative_binding_status: `{s['quantitative_binding_status']}`",
        f"- direct_quantitative_binding_candidate_count: `{s['direct_quantitative_binding_candidate_count']}`",
        f"- remaining_seed_unresolved_fields: `{s['remaining_seed_unresolved_fields']}`",
        "",
        "## Today Focus",
        "",
        f"- {s['today_focus']}",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Workbench Rows",
            "",
            "| workbench_section | priority_rank | packet_step | label | recommended_verdict | draft_manual_verdict_update | next_action |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['workbench_section']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['label']}` | "
            f"`{row['recommended_verdict']}` | `{row['draft_manual_verdict_update']}` | `{row['next_action']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-facing AQP1 reviewer workbench from existing AQP1 review artifacts.")
    parser.add_argument("--manual-verdict-handoff-json", default=DEFAULT_MANUAL_VERDICT_HANDOFF_JSON)
    parser.add_argument("--negative-review-handoff-json", default=DEFAULT_NEGATIVE_REVIEW_HANDOFF_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
    parser.add_argument("--binder-review-brief-json", default=DEFAULT_BINDER_REVIEW_BRIEF_JSON)
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--first-seed-row-packet-json", default=DEFAULT_FIRST_SEED_ROW_PACKET_JSON)
    parser.add_argument("--seed-sync-preview-json", default=DEFAULT_SEED_SYNC_PREVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.manual_verdict_handoff_json),
        _load_json(args.negative_review_handoff_json),
        _load_json(args.apply_draft_json),
        _load_json(args.binder_review_brief_json),
        _load_json(args.external_seed_json),
        _load_json(args.first_seed_row_packet_json),
        _load_json(args.seed_sync_preview_json),
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
