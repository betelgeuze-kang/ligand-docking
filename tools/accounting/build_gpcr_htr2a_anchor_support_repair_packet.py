#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    artifact as _artifact,
    read_csv as _read_csv,
    read_json as _read_json,
    resolve as _resolve,
    summary as _summary,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_POSE_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_SCORES_CSV = "runs/gpcr_false_support_discriminator_v16_frozen_adaptive_truebase_full_shadow_replay_scores_current.csv"
DEFAULT_TARGET = "CHEMBL224_HTR2A_HUMAN"
DEFAULT_LIGAND_ID = "CHEMBL83894"
DEFAULT_OUT_JSON = "runs/gpcr_htr2a_anchor_support_repair_packet_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_htr2a_anchor_support_repair_packet_rows_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_htr2a_anchor_support_repair_packet_current.md"

POSE_SUPPORT_GATE = 0.50


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    value_float = _float(value)
    return int(value_float) if value_float is not None else None


def _num(value: Any, default: float = 0.0) -> float:
    parsed = _float(value)
    return float(default) if parsed is None else parsed


def _rounded(value: Any, digits: int = 6) -> float:
    return round(_num(value), digits)


def _target_summaries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("target_summaries", [])
    return rows if isinstance(rows, list) else []


def _find_gap_row(payload: dict[str, Any], target: str, ligand_id: str) -> dict[str, Any]:
    for row in _target_summaries(payload):
        if _text(row.get("target")) == target and _text(row.get("ligand_id")) == ligand_id:
            return row
    return {}


def _score(row: dict[str, str], score_col: str) -> float:
    score = _float(row.get(score_col))
    if score is not None:
        return score
    return _num(row.get("base_score"), default=float("inf"))


def _anchor_mode(row: dict[str, str]) -> str:
    return (
        _text(row.get("effective_label_free_anchor_mode"))
        or _text(row.get("label_free_anchor_mode"))
        or _text(row.get("requested_label_free_anchor_mode"))
    )


def _exact_anchor_signature(row: dict[str, str]) -> dict[str, Any]:
    return {
        "anchor_mode": _anchor_mode(row),
        "basic_amine_count": _int(row.get("basic_amine_count")),
        "label_free_support_pressure": _rounded(row.get("label_free_support_pressure")),
        "label_free_penalty_pressure": _rounded(row.get("label_free_penalty_pressure")),
        "atom_contact_fraction_le_2p8A": _rounded(row.get("atom_contact_fraction_le_2p8A")),
        "atom_contact_fraction_2p8_4p2A": _rounded(row.get("atom_contact_fraction_2p8_4p2A")),
        "cationic_center_contact_fraction_le_2p8A": _rounded(row.get("cationic_center_contact_fraction_le_2p8A")),
        "cationic_center_contact_fraction_2p8_4p2A": _rounded(row.get("cationic_center_contact_fraction_2p8_4p2A")),
        "invalid_close_overanchor_pressure": _rounded(row.get("invalid_close_overanchor_pressure")),
        "hydrophobic_overcontact_pressure": _rounded(row.get("hydrophobic_overcontact_pressure")),
        "multipolar_basic_pressure": _rounded(row.get("multipolar_basic_pressure")),
        "cationic_mismatch_pressure": _rounded(row.get("cationic_mismatch_pressure")),
    }


def _generic_anchor_signature(row: dict[str, str]) -> dict[str, Any]:
    exact = _exact_anchor_signature(row)
    return {key: value for key, value in exact.items() if key not in {"basic_amine_count"}}


def _mean(rows: list[dict[str, str]], key: str) -> float | None:
    values = [_float(row.get(key)) for row in rows]
    real_values = [value for value in values if value is not None]
    if not real_values:
        return None
    return float(sum(real_values) / len(real_values))


def _shadow_delta(row: dict[str, str], score_col: str) -> float | None:
    score = _float(row.get(score_col))
    base = _float(row.get("base_score"))
    if score is None or base is None:
        return None
    return float(score - base)


def _ranked_rows(rows: list[dict[str, str]], score_col: str, target: str) -> list[dict[str, str]]:
    target_rows = [row for row in rows if _text(row.get("target")) == target]
    return sorted(target_rows, key=lambda row: (_score(row, score_col), _text(row.get("ligand_id"))))


def _row_output(
    row: dict[str, str],
    *,
    rank: int,
    row_role: str,
    score_col: str,
    positive_exact_signature: dict[str, Any],
    positive_generic_signature: dict[str, Any],
) -> dict[str, Any]:
    exact_signature = _exact_anchor_signature(row)
    generic_signature = _generic_anchor_signature(row)
    return {
        "target_rank": rank,
        "row_role": row_role,
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "base_score": _float(row.get("base_score")),
        "shadow_score": _float(row.get(score_col)),
        "shadow_delta_from_base": _shadow_delta(row, score_col),
        "anchor_mode": _anchor_mode(row),
        "basic_amine_count": _int(row.get("basic_amine_count")),
        "repaired_ligand_frame_atom_count": _int(row.get("repaired_ligand_frame_atom_count")),
        "label_free_support_pressure": _float(row.get("label_free_support_pressure")),
        "label_free_penalty_pressure": _float(row.get("label_free_penalty_pressure")),
        "pose_preservation_support": _float(row.get("pose_preservation_support")),
        "coarse_centroid_preservation_rmsd_A_mean": _float(row.get("coarse_centroid_preservation_rmsd_A_mean")),
        "atom_anchor_min_distance_A": _float(row.get("atom_anchor_min_distance_A")),
        "atom_contact_fraction_le_2p8A": _float(row.get("atom_contact_fraction_le_2p8A")),
        "atom_contact_fraction_2p8_4p2A": _float(row.get("atom_contact_fraction_2p8_4p2A")),
        "cationic_center_min_distance_A": _float(row.get("cationic_center_min_distance_A")),
        "cationic_center_contact_fraction_le_2p8A": _float(row.get("cationic_center_contact_fraction_le_2p8A")),
        "cationic_center_contact_fraction_2p8_4p2A": _float(row.get("cationic_center_contact_fraction_2p8_4p2A")),
        "invalid_close_overanchor_pressure": _float(row.get("invalid_close_overanchor_pressure")),
        "hydrophobic_overcontact_pressure": _float(row.get("hydrophobic_overcontact_pressure")),
        "multipolar_basic_pressure": _float(row.get("multipolar_basic_pressure")),
        "cationic_mismatch_pressure": _float(row.get("cationic_mismatch_pressure")),
        "exact_anchor_signature_matches_positive": exact_signature == positive_exact_signature,
        "generic_anchor_signature_matches_positive": generic_signature == positive_generic_signature,
        "adaptive_selection_reason": _text(row.get("adaptive_selection_reason")),
    }


def build_packet(
    *,
    pose_gap_json: str | Path = DEFAULT_POSE_GAP_JSON,
    scores_csv: str | Path = DEFAULT_SCORES_CSV,
    target: str = DEFAULT_TARGET,
    ligand_id: str = DEFAULT_LIGAND_ID,
    top_n_decoys: int = 10,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pose_gap = _read_json(pose_gap_json)
    pose_gap_summary = _summary(pose_gap)
    gap_row = _find_gap_row(pose_gap, target, ligand_id)
    score_col = _text(pose_gap_summary.get("score_col")) or "binding_score_composite_v7_residual_shadow"
    ranked = _ranked_rows(_read_csv(scores_csv), score_col, target)
    positive_index = next((idx for idx, row in enumerate(ranked) if _text(row.get("ligand_id")) == ligand_id), None)
    positive_row = ranked[positive_index] if positive_index is not None else {}
    decoys_above = ranked[:positive_index] if positive_index is not None else []
    positive_rank = int(positive_index + 1) if positive_index is not None else None
    positive_exact_signature = _exact_anchor_signature(positive_row) if positive_row else {}
    positive_generic_signature = _generic_anchor_signature(positive_row) if positive_row else {}

    top_decoys = decoys_above[: max(0, int(top_n_decoys))]
    csv_rows = [
        _row_output(
            row,
            rank=idx + 1,
            row_role="decoy_above_positive",
            score_col=score_col,
            positive_exact_signature=positive_exact_signature,
            positive_generic_signature=positive_generic_signature,
        )
        for idx, row in enumerate(top_decoys)
    ]
    if positive_row:
        csv_rows.append(
            _row_output(
                positive_row,
                rank=int(positive_rank or 0),
                row_role="positive",
                score_col=score_col,
                positive_exact_signature=positive_exact_signature,
                positive_generic_signature=positive_generic_signature,
            )
        )

    positive_support = _float(positive_row.get("label_free_support_pressure")) if positive_row else None
    positive_penalty = _float(positive_row.get("label_free_penalty_pressure")) if positive_row else None
    positive_pose_support = _float(positive_row.get("pose_preservation_support")) if positive_row else None
    positive_score = _float(positive_row.get(score_col)) if positive_row else None
    positive_base = _float(positive_row.get("base_score")) if positive_row else None
    decoy_support_mean = _mean(decoys_above, "label_free_support_pressure")
    decoy_pose_mean = _mean(decoys_above, "pose_preservation_support")
    decoy_score_mean = _mean(decoys_above, score_col)
    exact_collision_count = sum(
        1 for row in decoys_above if _exact_anchor_signature(row) == positive_exact_signature
    )
    generic_collision_count = sum(
        1 for row in decoys_above if _generic_anchor_signature(row) == positive_generic_signature
    )
    support_blind_count = sum(
        1
        for row in decoys_above
        if _num(row.get("label_free_support_pressure")) <= _num(positive_support)
        and _num(row.get("label_free_penalty_pressure")) <= _num(positive_penalty)
    )
    base_score_locked_count = sum(
        1 for row in decoys_above if abs(_num(row.get(score_col)) - _num(row.get("base_score"))) <= 1e-9
    )
    pose_advantaged_count = sum(
        1 for row in decoys_above if positive_pose_support is not None and _num(row.get("pose_preservation_support")) > positive_pose_support
    )
    positive_pose_deficit = (
        max(0.0, POSE_SUPPORT_GATE - positive_pose_support) if positive_pose_support is not None else None
    )
    support_advantage_to_decoys = (
        decoy_support_mean - positive_support if decoy_support_mean is not None and positive_support is not None else None
    )
    if not positive_row:
        status = "blocked_htr2a_positive_row_missing"
        next_action = "restore_htr2a_positive_row_before_anchor_support_repair"
    elif decoys_above and generic_collision_count > 0:
        status = "blocked_htr2a_anchor_signature_nonidentifiable"
        next_action = "build_htr2a_atom_typed_anchor_probe"
    elif decoys_above:
        status = "blocked_htr2a_target_internal_decoys_above_positive"
        next_action = "build_htr2a_decoy_support_discriminator"
    elif positive_pose_deficit and positive_pose_deficit > 0.0:
        status = "blocked_htr2a_pose_preservation_below_gate"
        next_action = "repair_htr2a_positive_pose_survival"
    else:
        status = "htr2a_anchor_support_repair_candidate_ready"
        next_action = "review_htr2a_candidate_before_oprm1_repair"

    next_required_step = (
        "Build a target-portable atom-typed HTR2A anchor probe on the 6A93 positive and target-internal decoys. "
        "The current v16/adaptive feature space leaves base-score-locked decoys above the positive and contains "
        "generic anchor-signature collisions, so do not tune scalar weights or promote a scorer until the new probe "
        "separates the positive without target identity, labels, threshold relaxation, or fake pass."
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "target": target,
        "ligand_id": ligand_id,
        "score_col": score_col,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "guarded_100k_rerun_allowed": False,
        "target_row_count": len(ranked),
        "positive_target_rank": positive_rank,
        "decoys_above_positive_count": len(decoys_above),
        "pose_gap_packet_decoys_above_positive": _int(gap_row.get("decoys_above_positive")),
        "positive_shadow_score": positive_score,
        "positive_base_score": positive_base,
        "positive_shadow_delta_from_base": _shadow_delta(positive_row, score_col) if positive_row else None,
        "positive_label_free_support_pressure": positive_support,
        "positive_label_free_penalty_pressure": positive_penalty,
        "positive_pose_preservation_support": positive_pose_support,
        "positive_pose_support_gate": POSE_SUPPORT_GATE,
        "positive_pose_support_deficit_to_gate": positive_pose_deficit,
        "top_decoy_count_analyzed": len(top_decoys),
        "top_decoy_shadow_score_mean": decoy_score_mean,
        "top_decoy_label_free_support_mean": decoy_support_mean,
        "top_decoy_pose_preservation_mean": decoy_pose_mean,
        "top_decoy_support_advantage_over_positive": support_advantage_to_decoys,
        "base_score_locked_decoys_above_positive_count": base_score_locked_count,
        "support_blind_decoys_above_positive_count": support_blind_count,
        "pose_advantaged_decoys_above_positive_count": pose_advantaged_count,
        "exact_anchor_signature_decoys_above_positive_count": exact_collision_count,
        "generic_anchor_signature_decoys_above_positive_count": generic_collision_count,
        "current_blockers": [str(item) for item in gap_row.get("blockers") or []],
        "next_action": next_action,
        "next_required_step": next_required_step,
    }
    payload = {
        "packet_type": "gpcr_htr2a_anchor_support_repair_packet",
        "summary": summary,
        "source_artifacts": {
            "pose_gap_json": _artifact(pose_gap_json),
            "scores_csv": _artifact(scores_csv),
        },
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "threshold_relaxation_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "fake_pass_allowed": False,
        },
        "positive_anchor_signature": positive_exact_signature,
        "positive_generic_anchor_signature": positive_generic_signature,
        "feature_contract": {
            "required_feature_family": "target_portable_atom_typed_anchor_and_pose_support",
            "must_separate": [
                "base_score_locked_decoys_above_positive",
                "generic_anchor_signature_collisions",
                "pose_advantaged_decoys_above_positive",
            ],
            "allowed_evidence": [
                "atom-typed conserved acidic-anchor geometry",
                "orthosteric cationic-center distance and dispersion",
                "aromatic/cationic cage occupancy from structure-derived contacts",
                "pose-preservation or local-minimization survival that is computed without labels",
            ],
            "forbidden_shortcuts": [
                "target identity features",
                "ligand labels or reference affinity in scoring",
                "threshold relaxation",
                "blind scalar reweighting of the current non-identifiable feature surface",
            ],
        },
        "acceptance_checks": [
            "positive_target_rank == 1 on the HTR2A target-internal frozen replay",
            "decoys_above_positive_count == 0",
            "base_score_locked_decoys_above_positive_count == 0 after the new feature is replayed",
            "generic_anchor_signature_decoys_above_positive_count == 0 or is explicitly separated by atom-typed evidence",
            "positive_pose_preservation_support >= 0.50",
            "positive_label_free_support_pressure exceeds top_decoy_label_free_support_mean without label or target identity features",
            "claim_promotion_allowed, scorer_apply_allowed, and guarded_100k_rerun_allowed remain false until OPRM1 and guarded CI/top20 gates also clear",
        ],
        "rows": csv_rows,
    }
    return payload, csv_rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR HTR2A Anchor-Support Repair Packet",
        "",
        "## Summary",
        "",
        f"- status: `{s['status']}`",
        f"- target: `{s['target']}`",
        f"- ligand_id: `{s['ligand_id']}`",
        f"- score_col: `{s['score_col']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(s['scorer_apply_allowed']).lower()}`",
        f"- guarded_100k_rerun_allowed: `{str(s['guarded_100k_rerun_allowed']).lower()}`",
        f"- positive_target_rank: `{s['positive_target_rank']}`",
        f"- decoys_above_positive_count: `{s['decoys_above_positive_count']}`",
        f"- base_score_locked_decoys_above_positive_count: `{s['base_score_locked_decoys_above_positive_count']}`",
        f"- support_blind_decoys_above_positive_count: `{s['support_blind_decoys_above_positive_count']}`",
        f"- pose_advantaged_decoys_above_positive_count: `{s['pose_advantaged_decoys_above_positive_count']}`",
        f"- exact_anchor_signature_decoys_above_positive_count: `{s['exact_anchor_signature_decoys_above_positive_count']}`",
        f"- generic_anchor_signature_decoys_above_positive_count: `{s['generic_anchor_signature_decoys_above_positive_count']}`",
        f"- positive_pose_preservation_support: `{s['positive_pose_preservation_support']}`",
        f"- positive_pose_support_deficit_to_gate: `{s['positive_pose_support_deficit_to_gate']}`",
        f"- next_action: `{s['next_action']}`",
        "",
        "## Next Required Step",
        "",
        s["next_required_step"],
        "",
        "## Acceptance Checks",
        "",
    ]
    for check in payload["acceptance_checks"]:
        lines.append(f"- `{check}`")
    lines.extend(["", "## Feature Contract", ""])
    contract = payload["feature_contract"]
    lines.append(f"- required_feature_family: `{contract['required_feature_family']}`")
    lines.append(f"- must_separate: `{', '.join(contract['must_separate'])}`")
    lines.append(f"- forbidden_shortcuts: `{', '.join(contract['forbidden_shortcuts'])}`")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the HTR2A anchor-support repair packet.")
    parser.add_argument("--pose-gap-json", default=DEFAULT_POSE_GAP_JSON)
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--ligand-id", default=DEFAULT_LIGAND_ID)
    parser.add_argument("--top-n-decoys", type=int, default=10)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, rows = build_packet(
        pose_gap_json=args.pose_gap_json,
        scores_csv=args.scores_csv,
        target=args.target,
        ligand_id=args.ligand_id,
        top_n_decoys=args.top_n_decoys,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
