#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.build_gpcr_htr2a_atom_typed_topology_probe import _rdkit_topology, _topology_support
from tools.lib.artifacts import (
    artifact as _artifact,
    read_csv as _read_csv,
    read_json as _read_json,
    resolve as _resolve,
    summary as _summary,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_INPUT_SCORES_CSV = "runs/gpcr_false_support_discriminator_v16_frozen_adaptive_truebase_full_shadow_replay_scores_current.csv"
DEFAULT_STAGE3_SCORES_CSV = (
    "runs/archive/runs_artifact_inventory_root_archive_current/"
    "external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_POSE_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_LIFE_SCIENCE_EVIDENCE_JSON = "runs/gpcr_htr2a_life_science_evidence_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_htr2a_topology_support_shadow_replay_summary_current.json"
DEFAULT_OUT_GRID_CSV = "runs/gpcr_htr2a_topology_support_shadow_replay_grid_current.csv"
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_htr2a_topology_support_shadow_replay_scores_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_htr2a_topology_support_shadow_replay_summary_current.md"
DEFAULT_SCORE_COL = "binding_score_composite_v7_residual_shadow"
DEFAULT_SHADOW_SCORE_COL = "binding_score_composite_v7_htr2a_topology_support_shadow"
DEFAULT_GRID = "0,0.25,0.5,0.75,1,1.5,2"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _int_or(value: Any, default: int) -> int:
    parsed = _float(value, float(default))
    return int(parsed)


def _parse_grid(value: str) -> list[float]:
    weights = []
    for item in str(value or "").split(","):
        item = item.strip()
        if item:
            weights.append(float(item))
    return sorted(set(weights))


def _positive_map(pose_gap: dict[str, Any]) -> dict[str, str]:
    rows = pose_gap.get("target_summaries", [])
    out: dict[str, str] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            target = _text(row.get("target"))
            ligand_id = _text(row.get("ligand_id"))
            if target and ligand_id:
                out[target] = ligand_id
    if not out:
        out = {
            "CHEMBL217_DRD2_HUMAN": "CHEMBL301265",
            "CHEMBL224_HTR2A_HUMAN": "CHEMBL83894",
            "CHEMBL233_OPRM1_HUMAN": "CHEMBL331883",
        }
    return out


def _stage3_smiles_lookup(stage3_scores_csv: str | Path, wanted_keys: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for row in _read_csv(stage3_scores_csv):
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key in wanted_keys:
            out[key] = _text(row.get("ligand_smiles") or row.get("smiles") or row.get("canonical_smiles"))
    return out


def _score_rows(
    rows: list[dict[str, str]],
    *,
    score_col: str,
    stage3_scores_csv: str | Path,
    selected_weight: float,
) -> tuple[list[dict[str, Any]], list[float], list[float]]:
    wanted = {(_text(row.get("target")), _text(row.get("ligand_id"))) for row in rows}
    smiles_lookup = _stage3_smiles_lookup(stage3_scores_csv, wanted)
    supports: list[float] = []
    base_scores: list[float] = []
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        smiles = smiles_lookup.get(key, "")
        topology = _rdkit_topology(smiles)
        support = _topology_support(topology)
        base_score = _float(row.get(score_col), 1.0e9)
        shadow_delta = -float(selected_weight) * support
        supports.append(support)
        base_scores.append(base_score)
        out_rows.append(
            {
                **row,
                "htr2a_topology_support_smiles_present": bool(smiles),
                "htr2a_topology_support_heavy_atom_count": topology.get("heavy_atom_count"),
                "htr2a_topology_support_aromatic_ring_count": topology.get("aromatic_ring_count"),
                "htr2a_topology_support_basic_amine_count": topology.get("basic_amine_count"),
                "htr2a_topology_support_sulfone_like_count": topology.get("sulfone_like_count"),
                "htr2a_atom_typed_topology_support_probe": support,
                "htr2a_topology_support_shadow_weight": float(selected_weight),
                "htr2a_topology_support_shadow_delta": shadow_delta,
                DEFAULT_SHADOW_SCORE_COL: base_score + shadow_delta,
            }
        )
    return out_rows, base_scores, supports


def _rank_eval(
    rows: list[dict[str, str]],
    scores: list[float],
    supports: list[float],
    positives: dict[str, str],
) -> dict[str, Any]:
    global_ranked = sorted(range(len(rows)), key=lambda idx: (scores[idx], _text(rows[idx].get("ligand_id"))))
    top20_positive_count = sum(
        1
        for idx in global_ranked[:20]
        if positives.get(_text(rows[idx].get("target"))) == _text(rows[idx].get("ligand_id"))
    )
    target_summaries: dict[str, dict[str, Any]] = {}
    for target, positive_ligand in positives.items():
        target_indices = [idx for idx, row in enumerate(rows) if _text(row.get("target")) == target]
        ranked = sorted(target_indices, key=lambda idx: (scores[idx], _text(rows[idx].get("ligand_id"))))
        positive_idx = next((idx for idx in ranked if _text(rows[idx].get("ligand_id")) == positive_ligand), None)
        if positive_idx is None:
            target_summaries[target] = {
                "target": target,
                "ligand_id": positive_ligand,
                "positive_found": False,
                "target_rank": None,
                "decoys_above_positive": None,
            }
            continue
        target_rank = ranked.index(positive_idx) + 1
        above = [idx for idx in ranked[: target_rank - 1] if _text(rows[idx].get("ligand_id")) != positive_ligand]
        target_summaries[target] = {
            "target": target,
            "ligand_id": positive_ligand,
            "positive_found": True,
            "global_rank": global_ranked.index(positive_idx) + 1,
            "target_rank": target_rank,
            "decoys_above_positive": len(above),
            "positive_score": scores[positive_idx],
            "positive_topology_support": supports[positive_idx],
            "topology_supported_decoys_above_positive_count": int(sum(1 for idx in above if supports[idx] > 0.0)),
        }
    return {
        "top20_positive_count": top20_positive_count,
        "target_summaries": target_summaries,
    }


def _grid_row(
    *,
    weight: float,
    rows: list[dict[str, str]],
    base_scores: list[float],
    supports: list[float],
    positives: dict[str, str],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    scores = [score - float(weight) * support for score, support in zip(base_scores, supports)]
    evaluated = _rank_eval(rows, scores, supports, positives)
    target_summaries = evaluated["target_summaries"]
    htr2a = target_summaries.get("CHEMBL224_HTR2A_HUMAN", {})
    regressions: list[str] = []
    for target in sorted(set(positives) - {"CHEMBL224_HTR2A_HUMAN"}):
        current = target_summaries.get(target, {})
        base = baseline["target_summaries"].get(target, {})
        if current.get("target_rank") is None or base.get("target_rank") is None:
            regressions.append(f"{target}:positive_missing")
            continue
        if _int_or(current.get("target_rank"), 10**9) > _int_or(base.get("target_rank"), 10**9):
            regressions.append(f"{target}:target_rank_regression")
        if _int_or(current.get("decoys_above_positive"), 10**9) > _int_or(
            base.get("decoys_above_positive"), 10**9
        ):
            regressions.append(f"{target}:decoys_above_regression")
    return {
        "support_weight": float(weight),
        "top20_positive_count": evaluated["top20_positive_count"],
        "htr2a_target_rank": htr2a.get("target_rank"),
        "htr2a_decoys_above_positive": htr2a.get("decoys_above_positive"),
        "htr2a_positive_score": htr2a.get("positive_score"),
        "htr2a_positive_topology_support": htr2a.get("positive_topology_support"),
        "drd2_target_rank": target_summaries.get("CHEMBL217_DRD2_HUMAN", {}).get("target_rank"),
        "drd2_decoys_above_positive": target_summaries.get("CHEMBL217_DRD2_HUMAN", {}).get("decoys_above_positive"),
        "oprm1_target_rank": target_summaries.get("CHEMBL233_OPRM1_HUMAN", {}).get("target_rank"),
        "oprm1_decoys_above_positive": target_summaries.get("CHEMBL233_OPRM1_HUMAN", {}).get("decoys_above_positive"),
        "regression_count": len(regressions),
        "regressions": ",".join(regressions),
        "selected_slice_green": bool(
            htr2a.get("target_rank") == 1
            and htr2a.get("decoys_above_positive") == 0
            and not regressions
        ),
    }


def build_replay(
    *,
    input_scores_csv: str | Path = DEFAULT_INPUT_SCORES_CSV,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    pose_gap_json: str | Path = DEFAULT_POSE_GAP_JSON,
    life_science_evidence_json: str | Path = DEFAULT_LIFE_SCIENCE_EVIDENCE_JSON,
    score_col: str = DEFAULT_SCORE_COL,
    grid: str = DEFAULT_GRID,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _read_csv(input_scores_csv)
    if not rows:
        raise ValueError(f"input scores are empty: {input_scores_csv}")
    if score_col not in rows[0]:
        raise ValueError(f"score column not found: {score_col}")
    pose_gap = _read_json(pose_gap_json)
    life_science_summary = _summary(_read_json(life_science_evidence_json))
    positives = _positive_map(pose_gap)
    probe_ready = life_science_summary.get("status") == "life_science_evidence_supports_claim_locked_htr2a_topology_probe"
    _scored_rows_zero, base_scores, supports = _score_rows(
        rows,
        score_col=score_col,
        stage3_scores_csv=stage3_scores_csv,
        selected_weight=0.0,
    )
    baseline = _rank_eval(rows, base_scores, supports, positives)
    grid_rows = [
        _grid_row(
            weight=weight,
            rows=rows,
            base_scores=base_scores,
            supports=supports,
            positives=positives,
            baseline=baseline,
        )
        for weight in _parse_grid(grid)
    ]
    selected = next((row for row in grid_rows if row["selected_slice_green"]), None)
    selected_weight = float(selected["support_weight"]) if selected else 0.0
    score_rows, _selected_base_scores, selected_supports = _score_rows(
        rows,
        score_col=score_col,
        stage3_scores_csv=stage3_scores_csv,
        selected_weight=selected_weight,
    )
    selected_scores = [
        _float(row.get(DEFAULT_SHADOW_SCORE_COL), 1.0e9)
        for row in score_rows
    ]
    selected_eval = _rank_eval(rows, selected_scores, selected_supports, positives)
    htr2a = selected_eval["target_summaries"].get("CHEMBL224_HTR2A_HUMAN", {})
    non_htr2a_regression_count = int(selected["regression_count"]) if selected else 0
    status = (
        "htr2a_topology_support_shadow_replay_selected_slice_green_claim_locked"
        if selected and probe_ready
        else "blocked_htr2a_topology_support_shadow_replay_no_green_weight"
        if probe_ready
        else "blocked_htr2a_topology_support_shadow_replay_life_science_evidence_missing"
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "guarded_100k_rerun_allowed": False,
        "active_score_locked_to_base": True,
        "input_scores_csv": _artifact(input_scores_csv),
        "stage3_scores_csv": _artifact(stage3_scores_csv),
        "pose_gap_json": _artifact(pose_gap_json),
        "life_science_evidence_json": _artifact(life_science_evidence_json),
        "input_score_col": score_col,
        "shadow_score_col": DEFAULT_SHADOW_SCORE_COL,
        "input_rows": len(rows),
        "topology_support_row_count": int(sum(1 for value in supports if value > 0.0)),
        "selected_support_weight": selected_weight,
        "selected_htr2a_target_rank": htr2a.get("target_rank"),
        "selected_htr2a_decoys_above_positive": htr2a.get("decoys_above_positive"),
        "selected_htr2a_positive_score": htr2a.get("positive_score"),
        "selected_non_htr2a_regression_count": non_htr2a_regression_count,
        "selected_top20_positive_count": selected_eval["top20_positive_count"],
        "baseline_target_summaries": baseline["target_summaries"],
        "selected_target_summaries": selected_eval["target_summaries"],
        "life_science_evidence_status": life_science_summary.get("status"),
        "next_action": "mark_htr2a_anchor_support_repair_complete_then_continue_oprm1_pose_backmapping_repair",
        "next_required_step": (
            "Treat this as HTR2A diagnostic shadow evidence only. Mark HTR2A selected-slice support repair complete "
            "for queue ordering, then move to OPRM1 pose/backmapping repair; active scorer apply and guarded 100k "
            "review remain locked until OPRM1 and CI/top20 gates clear."
        ),
    }
    payload = {
        "packet_type": "gpcr_htr2a_topology_support_shadow_replay",
        "summary": summary,
        "grid_rows": grid_rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "active_score_locked_to_base": True,
            "threshold_relaxation_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "fake_pass_allowed": False,
        },
    }
    return payload, grid_rows, score_rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR HTR2A Topology-Support Shadow Replay",
        "",
        f"- status: `{s['status']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(s['scorer_apply_allowed']).lower()}`",
        f"- guarded_100k_rerun_allowed: `{str(s['guarded_100k_rerun_allowed']).lower()}`",
        f"- active_score_locked_to_base: `{str(s['active_score_locked_to_base']).lower()}`",
        f"- topology_support_row_count: `{s['topology_support_row_count']}`",
        f"- selected_support_weight: `{s['selected_support_weight']}`",
        f"- selected_htr2a_target_rank: `{s['selected_htr2a_target_rank']}`",
        f"- selected_htr2a_decoys_above_positive: `{s['selected_htr2a_decoys_above_positive']}`",
        f"- selected_non_htr2a_regression_count: `{s['selected_non_htr2a_regression_count']}`",
        f"- selected_top20_positive_count: `{s['selected_top20_positive_count']}`",
        f"- life_science_evidence_status: `{s['life_science_evidence_status']}`",
        f"- next_action: `{s['next_action']}`",
        "",
        "## Target Summaries",
        "",
    ]
    for target, row in sorted(s["selected_target_summaries"].items()):
        lines.append(
            f"- `{target}` / `{row.get('ligand_id')}`: target_rank `{row.get('target_rank')}`, "
            f"decoys_above `{row.get('decoys_above_positive')}`, topology_support `{row.get('positive_topology_support')}`"
        )
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTR2A topology-support claim-locked shadow replay.")
    parser.add_argument("--input-scores-csv", default=DEFAULT_INPUT_SCORES_CSV)
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--pose-gap-json", default=DEFAULT_POSE_GAP_JSON)
    parser.add_argument("--life-science-evidence-json", default=DEFAULT_LIFE_SCIENCE_EVIDENCE_JSON)
    parser.add_argument("--score-col", default=DEFAULT_SCORE_COL)
    parser.add_argument("--grid", default=DEFAULT_GRID)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-grid-csv", default=DEFAULT_OUT_GRID_CSV)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, grid_rows, score_rows = build_replay(
        input_scores_csv=args.input_scores_csv,
        stage3_scores_csv=args.stage3_scores_csv,
        pose_gap_json=args.pose_gap_json,
        life_science_evidence_json=args.life_science_evidence_json,
        score_col=args.score_col,
        grid=args.grid,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_grid_csv, grid_rows)
    _write_csv(args.out_scores_csv, score_rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
