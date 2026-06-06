#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FOLLOW_ON_PACKET_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_follow_on_blocker_decomposition_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_follow_on_blocker_decomposition_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_follow_on_blocker_decomposition_current.md"

DEFAULT_FOLLOW_ON_PACKET_ARTIFACT = "runs/aqp1_first_wave_follow_on_packet_current.md"
DEFAULT_QUANTITATIVE_PROVENANCE_ARTIFACT = "runs/aqp1_quantitative_provenance_packet_current.md"

FOLLOW_ON_STEPS = ("core_binder_02", "core_binder_03")


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


def _load_json_if_exists(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
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


def _rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
    }


def _artifact_json_path(artifact_path: str) -> Path | None:
    text = _text(artifact_path)
    if not text:
        return None
    return _resolve(str(Path(text).with_suffix(".json")))


def _lane_label(packet_steps: list[str]) -> str:
    if not packet_steps:
        return ""
    if len(packet_steps) == 1:
        return packet_steps[0]
    prefix = packet_steps[0].rsplit("_", 1)[0]
    suffixes = [step.rsplit("_", 1)[-1] for step in packet_steps]
    return f"{prefix}_{'/'.join(suffixes)}"


def _load_related_artifacts(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    seed_packet = _load_json_if_exists(_artifact_json_path(str(row.get("seed_packet_artifact", ""))))
    fill_draft = _load_json_if_exists(_artifact_json_path(str(row.get("fill_draft_artifact", ""))))
    sync_preview = _load_json_if_exists(_artifact_json_path(str(row.get("sync_preview_artifact", ""))))
    return seed_packet, fill_draft, sync_preview


def _blocker_profile(
    packet_step: str,
    candidate_name: str,
    public_provenance_status: str,
    public_provenance_signal: str,
    current_signal: str,
    unresolved_fields: str,
    claim_safe_binding_kcal_ready: str,
    next_required_action: str,
) -> tuple[str, str, str, str, str]:
    if public_provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            "no_claim_safe_aqp1_binding_kcal_curated",
            "claim_safe_quantitative_binding",
            "exact_human_activity_present;functional_not_direct_binding;claim_safe_binding_kcal_missing",
            (
                f"{candidate_name} carries exact human AQP1 activity, but it remains functional-only and "
                f"`{unresolved_fields or 'replacement_reference_binding_kcal_mol'}` is still unresolved."
            ),
            (
                "Carry exact human AQP1 quantitative-activity provenance forward, but keep "
                "`replacement_reference_binding_kcal_mol` blank until direct binding or a claim-safe kcal anchor is curated."
            ),
        )
    if public_provenance_status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            "no_local_aqp1_binder_evidence_curated",
            "local_binder_evidence",
            "pubchem_resolved_only;exact_chembl_pair_absent;claim_safe_binding_kcal_missing",
            (
                f"{candidate_name} is PubChem-resolved, but the exact ChEMBL AQP1 pair is absent and "
                f"`{unresolved_fields or 'replacement_reference_binding_kcal_mol'}` is still unresolved."
            ),
            (
                f"Keep `{candidate_name}` review-only. PubChem resolves the compound, but an exact ChEMBL molecule/target pair "
                "was not recovered from the current public lane."
                if candidate_name
                else _text(next_required_action) or "manual_curated_search_or_defer"
            ),
        )
    return (
        "follow_on_row_blocked_pending_curation",
        "follow_on_lane",
        "follow_on_row_blocked;claim_safe_binding_kcal_missing",
        (
            f"{candidate_name} remains blocked while the current follow-on lane stays non-authoritative and "
            f"`{unresolved_fields or 'replacement_reference_binding_kcal_mol'}` is unresolved."
        ),
        _text(next_required_action) or "keep_review_only_until_curation_is_complete",
    )


def build_payload(
    follow_on_packet: dict[str, Any],
    quantitative_provenance: dict[str, Any],
) -> dict[str, Any]:
    follow_on_summary = dict(follow_on_packet.get("summary", {}) or {})
    follow_on_by_step = _rows_by_step(follow_on_packet)
    provenance_by_step = _rows_by_step(quantitative_provenance)

    follow_on_packet_artifact = _text(
        follow_on_summary.get("follow_on_packet_artifact", DEFAULT_FOLLOW_ON_PACKET_ARTIFACT)
    )
    quantitative_provenance_artifact = _text(
        quantitative_provenance.get("summary", {}).get("quantitative_provenance_packet_artifact", DEFAULT_QUANTITATIVE_PROVENANCE_ARTIFACT)
    )

    rows: list[dict[str, Any]] = []
    for rank, packet_step in enumerate(FOLLOW_ON_STEPS, start=1):
        follow_on_row = follow_on_by_step.get(packet_step, {})
        if not follow_on_row:
            continue

        provenance_row = provenance_by_step.get(packet_step, {})
        seed_packet, fill_draft, sync_preview = _load_related_artifacts(follow_on_row)
        seed_summary = dict(seed_packet.get("summary", {}) or {})
        fill_summary = dict(fill_draft.get("summary", {}) or {})
        sync_summary = dict(sync_preview.get("summary", {}) or {})
        sync_row = dict(sync_preview.get("row", {}) or {})

        candidate_name = _text(follow_on_row.get("candidate_name")) or _text(provenance_row.get("candidate_name"))
        public_provenance_status = _text(provenance_row.get("public_provenance_status")) or _text(
            follow_on_row.get("public_provenance_status")
        )
        public_provenance_signal = _text(provenance_row.get("public_provenance_signal")) or _text(
            follow_on_row.get("public_provenance_signal")
        )
        current_signal_text = _text(provenance_row.get("current_signal")) or _text(follow_on_row.get("evidence_signal"))
        unresolved_fields = _text(seed_summary.get("remaining_unresolved_fields")) or _text(sync_row.get("unresolved_fields"))
        claim_safe_binding_kcal_ready = _text(provenance_row.get("claim_safe_binding_kcal_ready")) or _text(
            seed_summary.get("claim_safe_binding_kcal_ready")
        )
        next_required_action = _text(follow_on_row.get("next_required_action"))

        blocker_id, blocker_scope, reason_components, blocker_reason, next_required_step = _blocker_profile(
            packet_step,
            candidate_name,
            public_provenance_status,
            public_provenance_signal,
            current_signal_text,
            unresolved_fields,
            claim_safe_binding_kcal_ready,
            next_required_action,
        )

        blocker_artifacts = [
            follow_on_packet_artifact,
            _text(follow_on_row.get("seed_packet_artifact")),
            _text(follow_on_row.get("fill_draft_artifact")),
            _text(follow_on_row.get("sync_preview_artifact")),
            quantitative_provenance_artifact,
        ]
        supporting_artifacts = "; ".join(artifact for artifact in blocker_artifacts if artifact)
        current_signal = "; ".join(
            token
            for token in [
                current_signal_text,
                f"public_provenance_status={public_provenance_status}" if public_provenance_status else "",
                f"public_provenance_signal={public_provenance_signal}" if public_provenance_signal else "",
                f"claim_safe_binding_kcal_ready={claim_safe_binding_kcal_ready}" if claim_safe_binding_kcal_ready else "",
                f"seed_remaining_unresolved_fields={_text(seed_summary.get('remaining_unresolved_fields'))}" if _text(seed_summary.get("remaining_unresolved_fields")) else "",
                f"sync_unresolved_fields={_text(sync_row.get('unresolved_fields'))}" if _text(sync_row.get("unresolved_fields")) else "",
                f"state_change_potential={_text(provenance_row.get('state_change_potential')) or _text(follow_on_row.get('state_change_potential'))}" if (_text(provenance_row.get("state_change_potential")) or _text(follow_on_row.get("state_change_potential"))) else "",
            ]
            if token
        )

        rows.append(
            {
                "blocker_rank": rank,
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "focus_scope": _text(follow_on_row.get("focus_scope")),
                "source_anchor": _text(follow_on_row.get("source_anchor")),
                "source_url": _text(follow_on_row.get("source_url")),
                "evidence_signal": _text(follow_on_row.get("evidence_signal")),
                "blocker_id": blocker_id,
                "blocker_scope": blocker_scope,
                "blocker_status": "blocked",
                "review_bucket": _text(follow_on_row.get("review_bucket")),
                "promotion_blocker": _text(follow_on_row.get("promotion_blocker")),
                "reason_components": reason_components,
                "blocker_reason": blocker_reason,
                "current_signal": current_signal,
                "public_provenance_status": public_provenance_status,
                "public_provenance_signal": public_provenance_signal,
                "state_change_potential": _text(provenance_row.get("state_change_potential"))
                or _text(follow_on_row.get("state_change_potential")),
                "claim_safe_binding_kcal_ready": claim_safe_binding_kcal_ready,
                "chembl_activity_record_count": _int(provenance_row.get("chembl_activity_record_count")),
                "seed_packet_artifact": _text(follow_on_row.get("seed_packet_artifact")),
                "fill_draft_artifact": _text(follow_on_row.get("fill_draft_artifact")),
                "sync_preview_artifact": _text(follow_on_row.get("sync_preview_artifact")),
                "quantitative_provenance_artifact": quantitative_provenance_artifact,
                "supporting_artifacts": supporting_artifacts,
                "seed_remaining_unresolved_fields": _text(seed_summary.get("remaining_unresolved_fields")),
                "seed_blocked_field_count": _int(seed_summary.get("blocked_field_count")),
                "fill_blocked_field_count": _int(fill_summary.get("blocked_field_count")),
                "sync_unresolved_field_count": _int(sync_summary.get("unresolved_field_count")),
                "next_required_action": next_required_action,
                "next_required_step": next_required_step,
            }
        )

    primary_row = rows[0] if rows else {}
    exact_human_activity_blocker_count = sum(
        1 for row in rows if row["blocker_id"] == "no_claim_safe_aqp1_binding_kcal_curated"
    )
    local_binder_evidence_blocker_count = sum(
        1 for row in rows if row["blocker_id"] == "no_local_aqp1_binder_evidence_curated"
    )
    summary = {
        "status": "aqp1_follow_on_blocker_decomposition_ready",
        "target_id": _text(follow_on_summary.get("target_id", "AQP1")) or "AQP1",
        "follow_on_blocker_packet_ready": bool(rows),
        "row_count": len(rows),
        "blocker_count": len(rows),
        "blocker_row_count": len(rows),
        "hard_blocker_count": sum(1 for row in rows if row["blocker_status"] == "blocked"),
        "soft_blocker_count": sum(1 for row in rows if row["blocker_status"] == "soft_blocked"),
        "exact_human_activity_blocker_count": exact_human_activity_blocker_count,
        "local_binder_evidence_blocker_count": local_binder_evidence_blocker_count,
        "exact_human_nonbinding_count": exact_human_activity_blocker_count,
        "exact_target_pair_absent_count": local_binder_evidence_blocker_count,
        "high_or_medium_potential_count": sum(
            1 for row in rows if _text(row.get("state_change_potential")) in {"high", "medium"}
        ),
        "claim_safe_kcal_ready_count": sum(
            1 for row in rows if _text(row.get("claim_safe_binding_kcal_ready")) == "yes"
        ),
        "claim_safe_binding_kcal_missing_row_count": sum(
            1 for row in rows if "claim_safe_binding_kcal_missing" in row["reason_components"]
        ),
        "follow_on_targets": _text(follow_on_summary.get("follow_on_targets")) or ", ".join(
            row["packet_step"] for row in rows
        ),
        "follow_on_lane_label": _lane_label([row["packet_step"] for row in rows]),
        "primary_blocker_target": _text(primary_row.get("packet_step")),
        "primary_blocker_id": _text(primary_row.get("blocker_id")),
        "primary_blocker_signal": _text(primary_row.get("current_signal")),
        "primary_blocker_reason": _text(primary_row.get("blocker_reason")),
        "follow_on_packet_artifact": follow_on_packet_artifact,
        "quantitative_provenance_packet_artifact": quantitative_provenance_artifact,
        "blocker_decomposition_artifact": DEFAULT_OUT_MD,
        "packet_artifact": DEFAULT_OUT_MD,
        "candidate_names": _text(follow_on_summary.get("candidate_names")),
        "source_anchors": _text(follow_on_summary.get("source_anchors")),
        "exact_human_reference_ligand": _text(follow_on_summary.get("exact_human_guardrail_ligand")),
        "exact_human_guardrail_ligand": _text(
            follow_on_summary.get("exact_human_guardrail_ligand")
        ) or _text(primary_row.get("candidate_name")),
        "primary_focus_ligand": _text(primary_row.get("candidate_name"))
        or _text(follow_on_summary.get("primary_focus_ligand")),
        "source_confirmation_primary_focus_ligand": _text(
            follow_on_summary.get("source_confirmation_primary_focus_ligand")
        ),
        "blocking_signal": _text(primary_row.get("current_signal")),
        "next_required_step": (
            "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, "
            "keep core_binder_03 (AqB011) review-only until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked."
            if rows
            else "No follow-on blocker rows are available."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Follow-On Blocker Decomposition",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- follow_on_blocker_packet_ready: `{s['follow_on_blocker_packet_ready']}`",
        f"- row_count: `{s['row_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blocker_row_count: `{s['blocker_row_count']}`",
        f"- hard_blocker_count: `{s['hard_blocker_count']}`",
        f"- soft_blocker_count: `{s['soft_blocker_count']}`",
        f"- exact_human_activity_blocker_count: `{s['exact_human_activity_blocker_count']}`",
        f"- local_binder_evidence_blocker_count: `{s['local_binder_evidence_blocker_count']}`",
        f"- exact_human_nonbinding_count: `{s['exact_human_nonbinding_count']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        f"- high_or_medium_potential_count: `{s['high_or_medium_potential_count']}`",
        f"- claim_safe_kcal_ready_count: `{s['claim_safe_kcal_ready_count']}`",
        f"- claim_safe_binding_kcal_missing_row_count: `{s['claim_safe_binding_kcal_missing_row_count']}`",
        f"- follow_on_targets: `{s['follow_on_targets']}`",
        f"- follow_on_lane_label: `{s['follow_on_lane_label']}`",
        f"- primary_blocker_target: `{s['primary_blocker_target']}`",
        f"- primary_blocker_id: `{s['primary_blocker_id']}`",
        f"- primary_blocker_signal: `{s['primary_blocker_signal']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- exact_human_guardrail_ligand: `{s['exact_human_guardrail_ligand']}`",
        f"- blocker_decomposition_artifact: `{s['blocker_decomposition_artifact']}`",
        f"- blocking_signal: `{s['blocking_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Blocker Rows",
        "",
        "| blocker_rank | packet_step | candidate_name | blocker_id | blocker_scope | blocker_reason | current_signal |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['blocker_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['blocker_id']}` | "
            f"`{row['blocker_scope']}` | {row['blocker_reason']} | `{row['current_signal']}` |"
        )
    lines.extend(
        [
            "",
            "## Supporting Artifacts",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['packet_step']}`: {row['supporting_artifacts']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 follow-on blocker decomposition packet for core_binder_02/core_binder_03.")
    parser.add_argument("--follow-on-packet-json", default=DEFAULT_FOLLOW_ON_PACKET_JSON)
    parser.add_argument("--quantitative-provenance-json", default=DEFAULT_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.follow_on_packet_json),
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
