#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_BLOCKER_DECOMPOSITION_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_follow_on_source_confirmation_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_follow_on_source_confirmation_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_follow_on_source_confirmation_packet_current.md"

DEFAULT_FOLLOW_ON_PACKET_ARTIFACT = "runs/aqp1_first_wave_follow_on_packet_current.md"
DEFAULT_BLOCKER_DECOMPOSITION_ARTIFACT = "runs/aqp1_follow_on_blocker_decomposition_current.md"
DEFAULT_QUANTITATIVE_PROVENANCE_ARTIFACT = "runs/aqp1_quantitative_provenance_packet_current.md"

FOLLOW_ON_STEPS = ("core_binder_02", "core_binder_03")
LITERATURE_OVERRIDES: dict[str, dict[str, str]] = {
    "AqB011": {
        "source_anchor": "PMID 29755973",
        "source_title": "Identification of Loop D Domain Amino Acids in the Human Aquaporin-1 Channel Involved in Activation of the Ionic Conductance and Inhibition by AqB011.",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/29755973/",
        "evidence_signal": "Exact human AQP1 functional literature anchor with AqB011 inhibition of ionic conductance; direct binding/Ki/Kd not publicly recovered.",
        "literature_support": "supportive_pmids=26467039,31477744",
    }
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rows_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
    }


def _join_artifacts(*paths: str) -> str:
    return "; ".join(path for path in (_text(item) for item in paths) if path)


def _lane_label(packet_steps: list[str]) -> str:
    if not packet_steps:
        return ""
    if len(packet_steps) == 1:
        return packet_steps[0]
    prefix = packet_steps[0].rsplit("_", 1)[0]
    suffixes = [step.rsplit("_", 1)[-1] for step in packet_steps]
    return f"{prefix}_{'/'.join(suffixes)}"


def _confirmation_scope(public_provenance_status: str) -> str:
    if public_provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return "exact_human_activity_source_confirmation"
    if public_provenance_status == "pubchem_resolved_chembl_target_pair_absent":
        return "exact_target_pair_absence_source_confirmation"
    if public_provenance_status == "compound_publicly_resolved_target_activity_absent":
        return "compound_public_source_confirmation"
    return "follow_on_source_confirmation"


def _confirmation_checks(
    source_anchor: str,
    public_provenance_status: str,
    public_provenance_signal: str,
    state_change_potential: str,
    review_bucket: str,
    claim_safe_binding_kcal_ready: str,
) -> str:
    checks = [
        f"source_anchor={source_anchor or '-'}",
        f"public_provenance_status={public_provenance_status or '-'}",
        f"public_provenance_signal={public_provenance_signal or '-'}",
        f"state_change_potential={state_change_potential or '-'}",
        f"claim_safe_binding_kcal_ready={claim_safe_binding_kcal_ready or '-'}",
    ]
    if review_bucket:
        checks.append(f"review_bucket={review_bucket}")
    return "; ".join(checks)


def _acceptance_gate(packet_step: str, candidate_name: str, source_anchor: str, public_provenance_status: str) -> str:
    if public_provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            f"Accept only if {source_anchor or packet_step} still supports {candidate_name} as exact human AQP1 quantitative activity "
            "and replacement_reference_binding_kcal_mol remains blank."
        )
    if public_provenance_status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            f"Accept only if {source_anchor or packet_step} still maps to {candidate_name} as PubChem-resolved but exact ChEMBL target-pair absent, "
            "with replacement_reference_binding_kcal_mol left blank."
        )
    return (
        "Accept only exact source identity, follow-on packet-step mapping, and review-only continuity without filling "
        "replacement_reference_binding_kcal_mol."
    )


def _rejection_gate(packet_step: str, candidate_name: str, source_anchor: str, public_provenance_status: str) -> str:
    if public_provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            f"Reject any wording that upgrades {candidate_name} at {source_anchor or packet_step} into claim-safe binding, direct binding, "
            "or authoritative apply."
        )
    if public_provenance_status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            f"Reject any attempt to promote {candidate_name} at {source_anchor or packet_step} out of review-only, or to invent an exact "
            "ChEMBL target pair that the current lane does not support."
        )
    return "Reject non-exact identity matches, source drift, and any premature promotion out of review-only."


def _next_required_step(
    packet_step: str,
    candidate_name: str,
    source_anchor: str,
    public_provenance_status: str,
    review_bucket: str,
) -> str:
    if public_provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            f"Confirm {packet_step} ({candidate_name}; {source_anchor}) as exact human AQP1 activity, keep replacement_reference_binding_kcal_mol blank, "
            f"and leave the row in {review_bucket or 'defer_exact_human_activity_nonbinding'}."
        )
    if public_provenance_status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            f"Confirm {packet_step} ({candidate_name}; {source_anchor}) remains PubChem-resolved but exact ChEMBL pair absent, keep replacement_reference_binding_kcal_mol blank, "
            f"and leave the row in {review_bucket or 'defer_pending_target_specific_evidence'}."
        )
    return (
        f"Confirm {packet_step} ({candidate_name}; {source_anchor}) exact-source mapping and keep the row review-only until stronger public target provenance appears."
    )


def build_payload(
    follow_on_packet: dict[str, Any],
    blocker_decomposition: dict[str, Any],
    quantitative_provenance: dict[str, Any],
) -> dict[str, Any]:
    follow_on_summary = dict(follow_on_packet.get("summary", {}) or {})
    blocker_summary = dict(blocker_decomposition.get("summary", {}) or {})
    follow_on_by_step = _rows_by_step(follow_on_packet)
    blocker_by_step = _rows_by_step(blocker_decomposition)
    provenance_by_step = _rows_by_step(quantitative_provenance)

    follow_on_packet_artifact = _text(
        follow_on_summary.get("follow_on_packet_artifact", DEFAULT_FOLLOW_ON_PACKET_ARTIFACT)
    )
    blocker_decomposition_artifact = _text(
        blocker_summary.get("blocker_decomposition_artifact", DEFAULT_BLOCKER_DECOMPOSITION_ARTIFACT)
    )
    quantitative_provenance_artifact = _text(
        blocker_summary.get(
            "quantitative_provenance_packet_artifact", DEFAULT_QUANTITATIVE_PROVENANCE_ARTIFACT
        )
    )

    rows: list[dict[str, Any]] = []
    for rank, packet_step in enumerate(FOLLOW_ON_STEPS, start=1):
        follow_on_row = follow_on_by_step.get(packet_step, {})
        blocker_row = blocker_by_step.get(packet_step, {})
        provenance_row = provenance_by_step.get(packet_step, {})
        if not any((follow_on_row, blocker_row, provenance_row)):
            continue

        candidate_name = (
            _text(follow_on_row.get("candidate_name"))
            or _text(blocker_row.get("candidate_name"))
            or _text(provenance_row.get("candidate_name"))
        )
        override = LITERATURE_OVERRIDES.get(candidate_name, {})
        source_anchor = (
            _text(override.get("source_anchor"))
            or
            _text(follow_on_row.get("source_anchor"))
            or _text(blocker_row.get("source_anchor"))
            or _text(provenance_row.get("source_anchor"))
        )
        source_title = (
            _text(override.get("source_title"))
            or _text(provenance_row.get("source_title"))
            or _text(follow_on_row.get("source_title"))
        )
        source_url = (
            _text(override.get("source_url"))
            or _text(follow_on_row.get("source_url"))
            or _text(provenance_row.get("source_url"))
        )
        evidence_signal = _text(override.get("evidence_signal")) or _text(follow_on_row.get("evidence_signal")) or _text(
            provenance_row.get("current_signal")
        )
        current_signal = _text(blocker_row.get("current_signal")) or evidence_signal
        public_provenance_status = (
            _text(blocker_row.get("public_provenance_status"))
            or _text(provenance_row.get("public_provenance_status"))
            or _text(follow_on_row.get("public_provenance_status"))
        )
        public_provenance_signal = (
            _text(blocker_row.get("public_provenance_signal"))
            or _text(provenance_row.get("public_provenance_signal"))
            or _text(follow_on_row.get("public_provenance_signal"))
        )
        state_change_potential = _text(blocker_row.get("state_change_potential")) or _text(
            provenance_row.get("state_change_potential")
        )
        review_bucket = _text(blocker_row.get("review_bucket")) or _text(follow_on_row.get("review_bucket"))
        promotion_blocker = _text(blocker_row.get("promotion_blocker")) or _text(
            follow_on_row.get("promotion_blocker")
        )
        next_required_action = _text(blocker_row.get("next_required_action")) or _text(
            follow_on_row.get("next_required_action")
        )
        claim_safe_binding_kcal_ready = _text(blocker_row.get("claim_safe_binding_kcal_ready")) or _text(
            provenance_row.get("claim_safe_binding_kcal_ready")
        )
        blocker_reason = _text(blocker_row.get("blocker_reason"))
        blocker_id = _text(blocker_row.get("blocker_id"))
        blocker_scope = _text(blocker_row.get("blocker_scope"))
        chembl_activity_record_count = _int(blocker_row.get("chembl_activity_record_count")) or _int(
            provenance_row.get("chembl_activity_record_count")
        )
        seed_packet_artifact = _text(follow_on_row.get("seed_packet_artifact"))
        fill_draft_artifact = _text(follow_on_row.get("fill_draft_artifact"))
        sync_preview_artifact = _text(follow_on_row.get("sync_preview_artifact"))
        follow_on_rank = _int(follow_on_row.get("follow_on_rank"))
        blocker_rank = _int(blocker_row.get("blocker_rank"))
        provenance_rank = _int(provenance_row.get("trace_rank")) or _int(provenance_row.get("rank"))

        confirmation_scope = _confirmation_scope(public_provenance_status)
        confirmation_checks = _confirmation_checks(
            source_anchor,
            public_provenance_status,
            public_provenance_signal,
            state_change_potential,
            review_bucket,
            claim_safe_binding_kcal_ready,
        )
        next_required_step = _next_required_step(
            packet_step,
            candidate_name,
            source_anchor,
            public_provenance_status,
            review_bucket,
        )

        rows.append(
            {
                "confirmation_rank": rank,
                "follow_on_rank": follow_on_rank or rank,
                "blocker_rank": blocker_rank or rank,
                "provenance_rank": provenance_rank or rank,
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "confirmation_scope": confirmation_scope,
                "source_anchor": source_anchor,
                "source_title": source_title,
                "source_url": source_url,
                "evidence_signal": evidence_signal,
                "current_signal": current_signal,
                "confirmation_checks": confirmation_checks,
                "literature_support": _text(override.get("literature_support")),
                "public_provenance_status": public_provenance_status,
                "public_provenance_signal": public_provenance_signal,
                "state_change_potential": state_change_potential,
                "review_bucket": review_bucket,
                "promotion_blocker": promotion_blocker,
                "next_required_action": next_required_action,
                "next_required_step": next_required_step,
                "blocker_id": blocker_id,
                "blocker_scope": blocker_scope,
                "blocker_reason": blocker_reason,
                "claim_safe_binding_kcal_ready": claim_safe_binding_kcal_ready,
                "chembl_activity_record_count": chembl_activity_record_count,
                "seed_packet_artifact": seed_packet_artifact,
                "fill_draft_artifact": fill_draft_artifact,
                "sync_preview_artifact": sync_preview_artifact,
                "follow_on_packet_artifact": follow_on_packet_artifact,
                "blocker_decomposition_artifact": blocker_decomposition_artifact,
                "quantitative_provenance_artifact": quantitative_provenance_artifact,
                "supporting_artifacts": _join_artifacts(
                    follow_on_packet_artifact,
                    seed_packet_artifact,
                    fill_draft_artifact,
                    sync_preview_artifact,
                    blocker_decomposition_artifact,
                    quantitative_provenance_artifact,
                ),
                "acceptance_gate": _acceptance_gate(
                    packet_step, candidate_name, source_anchor, public_provenance_status
                ),
                "rejection_gate": _rejection_gate(
                    packet_step, candidate_name, source_anchor, public_provenance_status
                ),
            }
        )

    exact_human_reference_ligand = next(
        (
            row["candidate_name"]
            for row in rows
            if row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
        ),
        "",
    )
    follow_on_targets = _text(follow_on_summary.get("follow_on_targets")) or ", ".join(
        row["packet_step"] for row in rows
    )
    source_anchors = _text(follow_on_summary.get("source_anchors")) or ", ".join(
        row["source_anchor"] for row in rows
    )
    candidate_names = _text(follow_on_summary.get("candidate_names")) or ", ".join(
        row["candidate_name"] for row in rows
    )
    follow_on_lane_label = _text(follow_on_summary.get("follow_on_lane_label")) or _lane_label(
        [row["packet_step"] for row in rows]
    )
    exact_human_activity_confirmation_count = sum(
        1
        for row in rows
        if row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
    )
    exact_target_pair_absent_confirmation_count = sum(
        1
        for row in rows
        if row["public_provenance_status"] == "pubchem_resolved_chembl_target_pair_absent"
    )
    claim_safe_kcal_ready_count = sum(
        1 for row in rows if _text(row.get("claim_safe_binding_kcal_ready")).lower() == "yes"
    )
    follow_on_review_only_count = sum(1 for row in rows if row["review_bucket"])
    primary_focus_row = next(
        (
            row
            for row in rows
            if row["public_provenance_status"] == "pubchem_resolved_chembl_target_pair_absent"
        ),
        rows[0] if rows else {},
    )
    primary_focus_ligand = _text(primary_focus_row.get("candidate_name"))
    primary_confirmation_target = _text(primary_focus_row.get("packet_step"))
    primary_blocker_target = _text(primary_focus_row.get("packet_step"))
    primary_blocker_id = _text(primary_focus_row.get("blocker_id"))
    primary_blocker_signal = _text(primary_focus_row.get("current_signal"))
    primary_blocker_reason = _text(primary_focus_row.get("blocker_reason"))
    exact_human_guardrail_ligand = exact_human_reference_ligand or primary_focus_ligand
    source_confirmation_packet_artifact = DEFAULT_OUT_MD
    next_required_step = (
        f"Keep {exact_human_guardrail_ligand or 'AqB013'} as the exact-human-activity guardrail with replacement_reference_binding_kcal_mol blank, "
        f"then confirm {primary_focus_row.get('packet_step', 'core_binder_03')} ({primary_focus_ligand or 'AqB011'}; {primary_focus_row.get('source_anchor', 'PMID 29755973')}) "
        "as literature-backed exact human AQP1 functional evidence with structured target-pair / claim-safe binding still absent."
        if len(rows) >= 2
        else (
            rows[0]["next_required_step"]
            if rows
            else "No AQP1 follow-on source confirmation rows are available."
        )
    )
    blocking_signal = (
        f"follow_on_targets={follow_on_targets}; "
        f"follow_on_candidates={candidate_names}; "
        f"exact_human_guardrail={exact_human_guardrail_ligand}; "
        "exact_human_activity_signal=exact_human_activity_present_leave_kcal_blank; "
        f"exact_human_activity_confirmation={exact_human_activity_confirmation_count}; "
        f"exact_target_pair_absent_confirmation={exact_target_pair_absent_confirmation_count}; "
        "authoritative_apply_allowed=False"
    )

    summary = {
        "status": "aqp1_follow_on_source_confirmation_packet_ready",
        "target_id": _text(blocker_summary.get("target_id", "AQP1")) or "AQP1",
        "row_count": len(rows),
        "follow_on_targets": follow_on_targets,
        "follow_on_lane_label": follow_on_lane_label,
        "primary_confirmation_target": primary_confirmation_target,
        "primary_focus_ligand": primary_focus_ligand,
        "source_confirmation_primary_focus_ligand": primary_focus_ligand,
        "exact_human_reference_ligand": exact_human_reference_ligand,
        "exact_human_guardrail_ligand": exact_human_guardrail_ligand,
        "candidate_names": candidate_names,
        "source_anchors": source_anchors,
        "exact_human_activity_confirmation_count": exact_human_activity_confirmation_count,
        "exact_target_pair_absent_confirmation_count": exact_target_pair_absent_confirmation_count,
        "review_only_follow_on_count": follow_on_review_only_count,
        "claim_safe_kcal_ready_count": claim_safe_kcal_ready_count,
        "primary_blocker_target": primary_blocker_target,
        "primary_blocker_id": primary_blocker_id,
        "primary_blocker_signal": primary_blocker_signal,
        "primary_blocker_reason": primary_blocker_reason,
        "follow_on_packet_artifact": follow_on_packet_artifact,
        "blocker_decomposition_artifact": blocker_decomposition_artifact,
        "quantitative_provenance_packet_artifact": quantitative_provenance_artifact,
        "source_confirmation_packet_artifact": source_confirmation_packet_artifact,
        "blocking_signal": blocking_signal,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Follow-On Source Confirmation Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- follow_on_targets: `{s['follow_on_targets']}`",
        f"- follow_on_lane_label: `{s['follow_on_lane_label']}`",
        f"- primary_confirmation_target: `{s['primary_confirmation_target']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- source_confirmation_primary_focus_ligand: `{s['source_confirmation_primary_focus_ligand']}`",
        f"- exact_human_reference_ligand: `{s['exact_human_reference_ligand']}`",
        f"- exact_human_guardrail_ligand: `{s['exact_human_guardrail_ligand']}`",
        f"- candidate_names: `{s['candidate_names']}`",
        f"- source_anchors: `{s['source_anchors']}`",
        f"- exact_human_activity_confirmation_count: `{s['exact_human_activity_confirmation_count']}`",
        f"- exact_target_pair_absent_confirmation_count: `{s['exact_target_pair_absent_confirmation_count']}`",
        f"- review_only_follow_on_count: `{s['review_only_follow_on_count']}`",
        f"- claim_safe_kcal_ready_count: `{s['claim_safe_kcal_ready_count']}`",
        f"- primary_blocker_target: `{s['primary_blocker_target']}`",
        f"- primary_blocker_id: `{s['primary_blocker_id']}`",
        f"- source_confirmation_packet_artifact: `{s['source_confirmation_packet_artifact']}`",
        f"- follow_on_packet_artifact: `{s['follow_on_packet_artifact']}`",
        f"- blocker_decomposition_artifact: `{s['blocker_decomposition_artifact']}`",
        f"- quantitative_provenance_packet_artifact: `{s['quantitative_provenance_packet_artifact']}`",
        f"- blocking_signal: `{s['blocking_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| confirmation_rank | packet_step | candidate_name | confirmation_scope | public_provenance_status | blocker_id | confirmation_checks |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['confirmation_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['confirmation_scope']}` | "
            f"`{row['public_provenance_status'] or '-'}` | `{row['blocker_id'] or '-'}` | `{row['confirmation_checks']}` |"
        )
    lines.extend(["", "## Row Actions", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['candidate_name']}`: {row['next_required_step']}")
    lines.extend(["", "## Reviewer Gates", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['candidate_name']}` accept: {row['acceptance_gate']}")
        lines.append(f"- `{row['candidate_name']}` reject: {row['rejection_gate']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an AQP1 follow-on source confirmation packet for the current core_binder_02/core_binder_03 rows."
    )
    parser.add_argument("--follow-on-packet-json", default=DEFAULT_FOLLOW_ON_PACKET_JSON)
    parser.add_argument("--blocker-decomposition-json", default=DEFAULT_BLOCKER_DECOMPOSITION_JSON)
    parser.add_argument("--quantitative-provenance-json", default=DEFAULT_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.follow_on_packet_json),
        _load_json(args.blocker_decomposition_json),
        _load_json(args.quantitative_provenance_json),
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
