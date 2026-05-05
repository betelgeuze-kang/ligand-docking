#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPAIR_ROWS_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_ATOM_CACHE_CSV = "runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.csv"
DEFAULT_CATIONIC_CACHE_CSV = "runs/gpcr_drd2_cationic_center_geometry_cache_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_hard_decoy_slice_packet_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_drd2_hard_decoy_slice_packet_current.md"

DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


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
    f = _float(value)
    return int(f) if f is not None else None


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "t", "yes", "y"}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key not in out:
            out[key] = row
    return out


def _clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return float(max(0.0, min(1.0, value)))


def _slice_labels(row: dict[str, Any]) -> list[str]:
    if row["is_positive"]:
        return ["positive_repaired_anchor_window"]
    labels: list[str] = []
    basic = int(row.get("basic_amine_count") or 0)
    donors = row.get("ligand_h_donors") or 0.0
    acceptors = row.get("ligand_h_acceptors") or 0.0
    rotors = row.get("ligand_rot_bonds") or 0.0
    close = row.get("atom_contact_fraction_le_2p8A") or 0.0
    window = row.get("atom_contact_fraction_2p8_4p2A") or 0.0
    cationic_window = row.get("cationic_center_contact_fraction_2p8_4p2A") or 0.0
    cationic_close = row.get("cationic_center_contact_fraction_le_2p8A") or 0.0
    centroid_rmsd = row.get("coarse_centroid_preservation_rmsd_A_mean") or 0.0
    mean_anchor = row.get("atom_anchor_mean_distance_A")
    if close >= 0.75 and basic <= 0:
        labels.append("invalid_close_overanchor_no_basic")
    if close >= 0.75 and basic <= 0 and donors <= 1.0 and acceptors <= 3.5:
        labels.append("hydrophobic_close_overanchor")
    if basic > 0 and (donors >= 2.5 or acceptors >= 4.5 or rotors >= 6.5) and (close >= 0.35 or window >= 0.35):
        labels.append("multipolar_basic_overanchor")
    if basic > 0 and window >= 0.50 and cationic_window < 0.50:
        labels.append("atom_window_basic_cationic_mismatch")
    if basic > 0 and window >= 0.50 and cationic_window >= 0.50 and centroid_rmsd >= 2.0:
        labels.append("pose_distorted_valid_anchor")
    if (
        basic > 0
        and window >= 0.50
        and close < 0.50
        and cationic_window >= 0.50
        and cationic_close < 0.50
        and centroid_rmsd < 2.0
        and donors <= 2.5
        and acceptors <= 4.5
    ):
        labels.append("valid_anchor_challenge")
    if basic <= 0 and window >= 0.50:
        labels.append("window_like_nonbasic")
    if mean_anchor is not None and mean_anchor < 2.0:
        labels.append("sub_2A_anchor_artifact")
    if not labels:
        labels.append("uncategorized_hard_decoy")
    return labels


def _candidate_pressures(row: dict[str, Any]) -> dict[str, float]:
    basic_count = int(row.get("basic_amine_count") or 0)
    basic = 1.0 if basic_count > 0 else 0.0
    donors = float(row.get("ligand_h_donors") or 0.0)
    acceptors = float(row.get("ligand_h_acceptors") or 0.0)
    rotors = float(row.get("ligand_rot_bonds") or 0.0)
    logp = float(row.get("ligand_logp") or 0.0)
    close = _clamp01(row.get("atom_contact_fraction_le_2p8A"))
    window = _clamp01(row.get("atom_contact_fraction_2p8_4p2A"))
    cationic_window = _clamp01(row.get("cationic_center_contact_fraction_2p8_4p2A"))
    cationic_close = _clamp01(row.get("cationic_center_contact_fraction_le_2p8A"))
    centroid_rmsd = float(row.get("coarse_centroid_preservation_rmsd_A_mean") or 0.0)
    mean_anchor = row.get("atom_anchor_mean_distance_A")
    too_close_distance = max(0.0, (2.8 - float(mean_anchor)) / 2.8) if mean_anchor is not None else 0.0
    invalid_close_overanchor_pressure = close * (1.0 - basic) + 0.50 * too_close_distance * (1.0 - basic)
    hydrophobic_overcontact_pressure = invalid_close_overanchor_pressure * max(0.0, logp - 1.5) / 4.0
    multipolar_basic_pressure = (
        basic
        * max(window, close)
        * (
            max(0.0, donors - 2.5) / 2.0
            + 0.75 * max(0.0, acceptors - 4.5) / 2.0
            + 0.35 * max(0.0, rotors - 5.5) / 3.0
        )
    )
    cationic_mismatch_pressure = basic * window * (1.0 - cationic_window) + basic * cationic_close
    pose_distortion_pressure = basic * window * cationic_window * max(0.0, (centroid_rmsd - 1.5) / 2.0)
    pose_preservation_support = max(0.0, 1.0 - max(0.0, (centroid_rmsd - 1.0) / 2.0))
    valid_anchor_support = (
        basic
        * window
        * cationic_window
        * (1.0 - min(close, 0.95))
        * (1.0 - min(cationic_close, 0.95))
        * pose_preservation_support
    )
    compact_anchor_support = valid_anchor_support * (1.0 - min(max(0.0, donors - 2.5) / 3.0, 1.0))
    label_free_penalty_pressure = (
        invalid_close_overanchor_pressure
        + hydrophobic_overcontact_pressure
        + multipolar_basic_pressure
        + cationic_mismatch_pressure
        + pose_distortion_pressure
    )
    return {
        "invalid_close_overanchor_pressure": float(invalid_close_overanchor_pressure),
        "hydrophobic_overcontact_pressure": float(hydrophobic_overcontact_pressure),
        "multipolar_basic_pressure": float(multipolar_basic_pressure),
        "cationic_mismatch_pressure": float(cationic_mismatch_pressure),
        "pose_distortion_pressure": float(pose_distortion_pressure),
        "pose_preservation_support": float(pose_preservation_support),
        "valid_anchor_support": float(valid_anchor_support),
        "compact_anchor_support": float(compact_anchor_support),
        "label_free_penalty_pressure": float(label_free_penalty_pressure),
        "label_free_support_pressure": float(compact_anchor_support),
    }


def _weak_base_rescue_support(base_score: float | None, support_pressure: float) -> tuple[float, float]:
    if base_score is None:
        return 0.0, 0.0
    # Lower scores are already strong in this ranking convention. Only let
    # motif support rescue rows whose base score is weak/borderline.
    gate = max(0.0, min(1.0, (float(base_score) + 6.0) / 6.0))
    return float(gate), float(max(0.0, support_pressure) * gate)


def _row_packet(
    row: dict[str, str],
    cache_row: dict[str, str],
    cationic_row: dict[str, str],
    positive_score: float | None,
) -> dict[str, Any]:
    score = _float(row.get("score"))
    is_positive = _truthy(row.get("is_positive")) or _text(row.get("ligand_id")) == DEFAULT_POSITIVE_LIGAND
    out: dict[str, Any] = {
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "is_positive": is_positive,
        "base_score": score,
        "positive_score": positive_score,
        "global_rank": _int(row.get("global_rank")),
        "within_target_rank": _int(row.get("within_target_rank")),
        "rank_pressure_to_clear_positive": (
            max(0.0, float(positive_score) - float(score) + 0.001)
            if (positive_score is not None and score is not None and not is_positive)
            else 0.0
        ),
        "ligand_smiles": _text(row.get("ligand_smiles")),
        "ligand_h_donors": _float(row.get("ligand_h_donors")) or 0.0,
        "ligand_h_acceptors": _float(row.get("ligand_h_acceptors")) or 0.0,
        "ligand_rot_bonds": _float(row.get("ligand_rot_bonds")) or 0.0,
        "ligand_logp": _float(row.get("ligand_logp")) or 0.0,
        "basic_amine_count": _int(row.get("allatom_basic_amine_atom_count")) or 0,
        "source_ligand_frame_atom_count": _int(row.get("source_ligand_frame_atom_count")),
        "repaired_ligand_frame_atom_count": _int(row.get("repaired_ligand_frame_atom_count")),
        "allatom_backmapping_coverage_ratio": _float(row.get("allatom_backmapping_coverage_ratio")),
        "target_cation_anchor_distance_A_mean": _float(row.get("target_cation_anchor_distance_A_mean")),
        "coarse_centroid_preservation_rmsd_A_mean": _float(row.get("coarse_centroid_preservation_rmsd_A_mean")),
        "atom_anchor_available": _int(cache_row.get("class_a_atom_anchor_available")) or 0,
        "atom_anchor_min_distance_A": _float(cache_row.get("class_a_atom_anchor_min_distance_A")),
        "atom_anchor_p10_distance_A": _float(cache_row.get("class_a_atom_anchor_p10_distance_A")),
        "atom_anchor_mean_distance_A": _float(cache_row.get("class_a_atom_anchor_mean_distance_A")),
        "atom_contact_fraction_le_2p8A": _float(cache_row.get("class_a_atom_anchor_contact_fraction_le_2p8A")) or 0.0,
        "atom_contact_fraction_2p8_4p2A": _float(cache_row.get("class_a_atom_anchor_contact_fraction_2p8_4p2A")) or 0.0,
        "cationic_center_available": _int(cationic_row.get("class_a_cationic_center_available")) or 0,
        "cationic_center_basic_atom_count": _int(cationic_row.get("class_a_cationic_center_basic_atom_count")) or 0,
        "cationic_center_min_distance_A": _float(cationic_row.get("class_a_cationic_center_min_distance_A")),
        "cationic_center_p10_distance_A": _float(cationic_row.get("class_a_cationic_center_p10_distance_A")),
        "cationic_center_mean_distance_A": _float(cationic_row.get("class_a_cationic_center_mean_distance_A")),
        "cationic_center_contact_fraction_le_2p8A": (
            _float(cationic_row.get("class_a_cationic_center_contact_fraction_le_2p8A")) or 0.0
        ),
        "cationic_center_contact_fraction_2p8_4p2A": (
            _float(cationic_row.get("class_a_cationic_center_contact_fraction_2p8_4p2A")) or 0.0
        ),
        "cationic_center_contact_fraction_ge_4p2A": (
            _float(cationic_row.get("class_a_cationic_center_contact_fraction_ge_4p2A")) or 0.0
        ),
    }
    out.update(_candidate_pressures(out))
    weak_gate, weak_support = _weak_base_rescue_support(score, float(out.get("label_free_support_pressure") or 0.0))
    out["weak_base_rescue_gate"] = weak_gate
    out["weak_base_rescue_support_pressure"] = weak_support
    labels = _slice_labels(out)
    out["slice_labels"] = labels
    out["slice_label_text"] = ",".join(labels)
    return out


def _slice_rollup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = sorted({label for row in rows for label in row.get("slice_labels", [])})
    out: list[dict[str, Any]] = []
    for label in labels:
        members = [row for row in rows if label in row.get("slice_labels", [])]
        decoys = [row for row in members if not row.get("is_positive")]
        out.append(
            {
                "slice_label": label,
                "row_count": len(members),
                "decoy_count": len(decoys),
                "positive_count": len(members) - len(decoys),
                "mean_rank_pressure_to_clear_positive": (
                    sum(float(row.get("rank_pressure_to_clear_positive") or 0.0) for row in decoys) / len(decoys)
                    if decoys
                    else 0.0
                ),
                "max_rank_pressure_to_clear_positive": max(
                    (float(row.get("rank_pressure_to_clear_positive") or 0.0) for row in decoys),
                    default=0.0,
                ),
                "mean_label_free_penalty_pressure": (
                    sum(float(row.get("label_free_penalty_pressure") or 0.0) for row in decoys) / len(decoys)
                    if decoys
                    else 0.0
                ),
                "mean_label_free_support_pressure": (
                    sum(float(row.get("label_free_support_pressure") or 0.0) for row in members) / len(members)
                    if members
                    else 0.0
                ),
            }
        )
    return out


def build_packet(
    *,
    repair_rows_csv: str | Path = DEFAULT_REPAIR_ROWS_CSV,
    atom_cache_csv: str | Path = DEFAULT_ATOM_CACHE_CSV,
    cationic_cache_csv: str | Path = DEFAULT_CATIONIC_CACHE_CSV,
    positive_ligand: str = DEFAULT_POSITIVE_LIGAND,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repair_rows = _read_csv(repair_rows_csv)
    cache = _lookup(_read_csv(atom_cache_csv))
    cationic_cache = _lookup(_read_csv(cationic_cache_csv))
    positive_row = next(
        (
            row
            for row in repair_rows
            if _text(row.get("ligand_id")) == positive_ligand or _truthy(row.get("is_positive"))
        ),
        {},
    )
    positive_score = _float(positive_row.get("score"))
    rows = [
        _row_packet(
            row,
            cache.get((_text(row.get("target")), _text(row.get("ligand_id"))), {}),
            cationic_cache.get((_text(row.get("target")), _text(row.get("ligand_id"))), {}),
            positive_score,
        )
        for row in repair_rows
    ]
    decoys = [row for row in rows if not row.get("is_positive")]
    rollup = _slice_rollup(rows)
    overanchor_count = sum(1 for row in decoys if "invalid_close_overanchor_no_basic" in row.get("slice_labels", []))
    hydrophobic_count = sum(1 for row in decoys if "hydrophobic_close_overanchor" in row.get("slice_labels", []))
    multipolar_count = sum(1 for row in decoys if "multipolar_basic_overanchor" in row.get("slice_labels", []))
    cationic_mismatch_count = sum(
        1 for row in decoys if "atom_window_basic_cationic_mismatch" in row.get("slice_labels", [])
    )
    pose_distorted_count = sum(1 for row in decoys if "pose_distorted_valid_anchor" in row.get("slice_labels", []))
    valid_anchor_count = sum(1 for row in decoys if "valid_anchor_challenge" in row.get("slice_labels", []))
    max_required_pressure = max(
        (float(row.get("rank_pressure_to_clear_positive") or 0.0) for row in decoys),
        default=0.0,
    )
    mean_required_pressure = (
        sum(float(row.get("rank_pressure_to_clear_positive") or 0.0) for row in decoys) / len(decoys)
        if decoys
        else 0.0
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "hard_decoy_slice_packet_ready",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "repair_rows_csv": str(_resolve(repair_rows_csv)),
        "atom_cache_csv": str(_resolve(atom_cache_csv)),
        "cationic_cache_csv": str(_resolve(cationic_cache_csv)),
        "row_count": len(rows),
        "decoy_count": len(decoys),
        "positive_ligand_id": positive_ligand,
        "positive_score": positive_score,
        "positive_repaired_atom_count": next(
            (row.get("repaired_ligand_frame_atom_count") for row in rows if row.get("is_positive")),
            None,
        ),
        "positive_atom_window_fraction_2p8_4p2A": next(
            (row.get("atom_contact_fraction_2p8_4p2A") for row in rows if row.get("is_positive")),
            None,
        ),
        "positive_atom_anchor_mean_distance_A": next(
            (row.get("atom_anchor_mean_distance_A") for row in rows if row.get("is_positive")),
            None,
        ),
        "invalid_close_overanchor_no_basic_count": overanchor_count,
        "hydrophobic_close_overanchor_count": hydrophobic_count,
        "multipolar_basic_overanchor_count": multipolar_count,
        "atom_window_basic_cationic_mismatch_count": cationic_mismatch_count,
        "pose_distorted_valid_anchor_count": pose_distorted_count,
        "valid_anchor_challenge_count": valid_anchor_count,
        "mean_rank_pressure_to_clear_positive": mean_required_pressure,
        "max_rank_pressure_to_clear_positive": max_required_pressure,
        "next_action": "design_label_free_overanchor_multipolar_penalty_then_replay_on_repaired_slice",
        "next_required_step": (
            "Use this packet to design a label-free penalty/support candidate. Required separation should first reduce "
            "invalid close-overanchor/no-basic and multipolar-basic decoy pressure on the repaired selected slice; only "
            "after slice separation should a full frozen 100k replay or guarded apply be considered."
        ),
    }
    payload = {
        "packet_type": "gpcr_drd2_hard_decoy_slice_packet",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "threshold_relaxation_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
        },
        "slice_rollup": rollup,
        "candidate_feature_contract": [
            "invalid_close_overanchor_pressure = close acidic-anchor contact without basic amine support",
            "hydrophobic_overcontact_pressure = invalid close overanchor plus high hydrophobicity context",
            "multipolar_basic_pressure = basic-amine atom-window rows with excess donor/acceptor/rotor burden",
            "valid_anchor_support = basic-amine row in 2.8-4.2A atom-window with low too-close contact",
        ],
        "rows": rows,
    }
    return payload, rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR DRD2 Hard-Decoy Slice Packet",
        "",
        "## Summary",
        "",
        f"- status: `{s['status']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- row_count: `{s['row_count']}`",
        f"- decoy_count: `{s['decoy_count']}`",
        f"- positive_ligand_id: `{s['positive_ligand_id']}`",
        f"- positive_score: `{s['positive_score']}`",
        f"- positive_repaired_atom_count: `{s['positive_repaired_atom_count']}`",
        f"- positive_atom_anchor_mean_distance_A: `{s['positive_atom_anchor_mean_distance_A']}`",
        f"- positive_atom_window_fraction_2p8_4p2A: `{s['positive_atom_window_fraction_2p8_4p2A']}`",
        f"- invalid_close_overanchor_no_basic_count: `{s['invalid_close_overanchor_no_basic_count']}`",
        f"- hydrophobic_close_overanchor_count: `{s['hydrophobic_close_overanchor_count']}`",
        f"- multipolar_basic_overanchor_count: `{s['multipolar_basic_overanchor_count']}`",
        f"- atom_window_basic_cationic_mismatch_count: `{s['atom_window_basic_cationic_mismatch_count']}`",
        f"- pose_distorted_valid_anchor_count: `{s['pose_distorted_valid_anchor_count']}`",
        f"- valid_anchor_challenge_count: `{s['valid_anchor_challenge_count']}`",
        f"- mean_rank_pressure_to_clear_positive: `{s['mean_rank_pressure_to_clear_positive']}`",
        f"- max_rank_pressure_to_clear_positive: `{s['max_rank_pressure_to_clear_positive']}`",
        f"- next_action: `{s['next_action']}`",
        "",
        "## Slice Rollup",
        "",
        "| slice | rows | decoys | positives | mean required pressure | max required pressure |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload.get("slice_rollup", []):
        lines.append(
            f"| `{row['slice_label']}` | {row['row_count']} | {row['decoy_count']} | {row['positive_count']} | "
            f"{row['mean_rank_pressure_to_clear_positive']} | {row['max_rank_pressure_to_clear_positive']} |"
        )
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a hard-decoy slice packet for repaired DRD2 GPCR rows.")
    parser.add_argument("--repair-rows-csv", default=DEFAULT_REPAIR_ROWS_CSV)
    parser.add_argument("--atom-cache-csv", default=DEFAULT_ATOM_CACHE_CSV)
    parser.add_argument("--cationic-cache-csv", default=DEFAULT_CATIONIC_CACHE_CSV)
    parser.add_argument("--positive-ligand", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, rows = build_packet(
        repair_rows_csv=args.repair_rows_csv,
        atom_cache_csv=args.atom_cache_csv,
        cationic_cache_csv=args.cationic_cache_csv,
        positive_ligand=args.positive_ligand,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
