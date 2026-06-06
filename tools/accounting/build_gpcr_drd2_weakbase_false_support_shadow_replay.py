#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

try:
    from rdkit import Chem
except Exception:  # pragma: no cover
    Chem = None  # type: ignore[assignment]

from tools.lib.artifacts import artifact as _artifact
from tools.lib.artifacts import read_csv as _read_csv
from tools.lib.artifacts import resolve as _resolve
from tools.lib.artifacts import write_csv as _write_csv
from tools.lib.artifacts import write_json as _write_json

DEFAULT_SCORES_CSV = "runs/gpcr_oprm1_topology_pose_shadow_replay_scores_current.csv"
DEFAULT_SMILES_CSV = "runs/gpcr_family_anchor_v2_shadow_replay_scores_current.csv"
DEFAULT_SCORE_COL = "binding_score_composite_v7_htr2a_oprm1_topology_pose_shadow"
DEFAULT_OUT_SCORE_COL = "binding_score_composite_v7_htr2a_oprm1_drd2_weakbase_false_support_shadow"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_summary_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_summary_current.md"
DEFAULT_OUT_GRID_CSV = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_grid_current.csv"
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_scores_current.csv"
DEFAULT_GRID = "0,0.5,1,1.5,2,2.5,3,4,5,6"

POSITIVE_PAIRS = {
    "CHEMBL217_DRD2_HUMAN": "CHEMBL301265",
    "CHEMBL224_HTR2A_HUMAN": "CHEMBL83894",
    "CHEMBL233_OPRM1_HUMAN": "CHEMBL331883",
}
DRD2_TARGET = "CHEMBL217_DRD2_HUMAN"
DRD2_POSITIVE = "CHEMBL301265"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return float(default)
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return out if math.isfinite(out) else float(default)


def _int_value(value: Any, default: int = 10**9) -> int:
    try:
        if value is None or str(value).strip() == "":
            return int(default)
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _parse_grid(spec: str) -> list[float]:
    values: list[float] = []
    for item in str(spec or "").split(","):
        item = item.strip()
        if item:
            values.append(float(item))
    return sorted(set(values)) or [0.0]


def _smiles_lookup(smiles_csv: str | Path) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for row in _read_csv(smiles_csv):
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        smiles = _text(row.get("ligand_smiles"))
        if target and ligand_id and smiles and (target, ligand_id) not in out:
            out[(target, ligand_id)] = smiles
    return out


def _is_carbonyl_carbon(atom: Any) -> bool:
    if atom.GetAtomicNum() != 6:
        return False
    for bond in atom.GetBonds():
        other = bond.GetOtherAtom(atom)
        if other.GetAtomicNum() == 8 and str(bond.GetBondType()) == "DOUBLE":
            return True
    return False


def _has_double_bond_oxygen(atom: Any) -> bool:
    for bond in atom.GetBonds():
        other = bond.GetOtherAtom(atom)
        if other.GetAtomicNum() == 8 and str(bond.GetBondType()) == "DOUBLE":
            return True
    return False


def _nitrogen_features(smiles: str) -> dict[str, Any]:
    if Chem is None:
        return {
            "smiles_present": bool(smiles),
            "rdkit_parse_ok": False,
            "protonatable_aliphatic_amine_count": 0,
            "weak_nonprotonatable_n_count": 0,
            "total_n_count": 0,
        }
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return {
            "smiles_present": bool(smiles),
            "rdkit_parse_ok": False,
            "protonatable_aliphatic_amine_count": 0,
            "weak_nonprotonatable_n_count": 0,
            "total_n_count": 0,
        }
    protonatable = 0
    weak = 0
    total_n = 0
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() != 7:
            continue
        total_n += 1
        if atom.GetIsAromatic() or atom.GetFormalCharge() < 0:
            weak += 1
            continue
        neighbors = list(atom.GetNeighbors())
        amide_like = any(_is_carbonyl_carbon(nb) for nb in neighbors)
        sulfonamide_like = any(nb.GetAtomicNum() == 16 and _has_double_bond_oxygen(nb) for nb in neighbors)
        if amide_like or sulfonamide_like:
            weak += 1
            continue
        has_aliphatic_carbon_neighbor = any(nb.GetAtomicNum() == 6 and not nb.GetIsAromatic() for nb in neighbors)
        in_nonaromatic_ring = atom.IsInRing() and not atom.GetIsAromatic()
        if has_aliphatic_carbon_neighbor or in_nonaromatic_ring or atom.GetFormalCharge() > 0:
            protonatable += 1
        else:
            weak += 1
    return {
        "smiles_present": bool(smiles),
        "rdkit_parse_ok": True,
        "protonatable_aliphatic_amine_count": int(protonatable),
        "weak_nonprotonatable_n_count": int(weak),
        "total_n_count": int(total_n),
    }


def _probe(row: dict[str, Any], smiles_features: dict[str, Any]) -> float:
    if not smiles_features.get("rdkit_parse_ok"):
        return 0.0
    if int(smiles_features.get("protonatable_aliphatic_amine_count") or 0) > 0:
        return 0.0
    if int(smiles_features.get("weak_nonprotonatable_n_count") or 0) <= 0:
        return 0.0
    basic_count = _float(row.get("basic_amine_count"))
    cationic_window = _float(row.get("cationic_center_contact_fraction_2p8_4p2A"))
    valid_anchor = _float(row.get("valid_anchor_support"))
    weak_rescue = _float(row.get("weak_base_rescue_support_pressure"))
    if basic_count <= 0:
        return 0.0
    support = max(cationic_window, valid_anchor, weak_rescue)
    if support < 0.45:
        return 0.0
    return float(min(1.0, support))


def _is_positive(row: dict[str, Any]) -> bool:
    return POSITIVE_PAIRS.get(_text(row.get("target"))) == _text(row.get("ligand_id"))


def _rankings(rows: list[dict[str, Any]], score_col: str) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int]]:
    ranked = sorted(rows, key=lambda row: (_float(row.get(score_col)), _text(row.get("target")), _text(row.get("ligand_id"))))
    target_rows: dict[str, list[dict[str, Any]]] = {}
    for row in ranked:
        target_rows.setdefault(_text(row.get("target")), []).append(row)
    target_rank: dict[tuple[str, str], int] = {}
    for grouped in target_rows.values():
        grouped.sort(key=lambda row: (_float(row.get(score_col)), _text(row.get("ligand_id"))))
        for rank, row in enumerate(grouped, start=1):
            target_rank[(_text(row.get("target")), _text(row.get("ligand_id")))] = rank
    return ranked, target_rank


def _top20_positive_count(rows: list[dict[str, Any]], score_col: str) -> int:
    ranked, _ = _rankings(rows, score_col)
    return int(sum(1 for row in ranked[:20] if _is_positive(row)))


def _average_precision(rows: list[dict[str, Any]], score_col: str) -> float:
    ranked, _ = _rankings(rows, score_col)
    positives = int(sum(1 for row in ranked if _is_positive(row)))
    if positives <= 0:
        return float("nan")
    hit = 0
    precision_sum = 0.0
    for idx, row in enumerate(ranked, start=1):
        if _is_positive(row):
            hit += 1
            precision_sum += hit / float(idx)
    return float(precision_sum / positives)


def _evaluate(rows: list[dict[str, Any]], score_col: str) -> dict[str, Any]:
    ranked, target_ranks = _rankings(rows, score_col)
    before_or_after = {
        target: {
            "target": target,
            "ligand_id": ligand,
            "target_rank": target_ranks.get((target, ligand)),
            "decoys_above_positive": (
                int(target_ranks[(target, ligand)] - 1) if (target, ligand) in target_ranks else None
            ),
            "global_rank": next(
                (idx for idx, row in enumerate(ranked, start=1) if _text(row.get("target")) == target and _text(row.get("ligand_id")) == ligand),
                None,
            ),
        }
        for target, ligand in POSITIVE_PAIRS.items()
    }
    return {
        "ranking_pr_auc": _average_precision(rows, score_col),
        "top20_positive_count": _top20_positive_count(rows, score_col),
        "positive_summaries": list(before_or_after.values()),
        "drd2_target_rank": before_or_after[DRD2_TARGET]["target_rank"],
        "drd2_decoys_above_positive": before_or_after[DRD2_TARGET]["decoys_above_positive"],
    }


def _apply_weight(rows: list[dict[str, Any]], base_score_col: str, out_score_col: str, weight: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        new = dict(row)
        probe = _float(new.get("drd2_weakbase_false_support_probe"))
        delta = float(weight) * probe
        new["drd2_weakbase_false_support_weight"] = float(weight)
        new["drd2_weakbase_false_support_delta"] = delta
        new[out_score_col] = _float(new.get(base_score_col)) + delta
        out.append(new)
    return out


def build_replay(
    *,
    scores_csv: str | Path = DEFAULT_SCORES_CSV,
    smiles_csv: str | Path = DEFAULT_SMILES_CSV,
    score_col: str = DEFAULT_SCORE_COL,
    out_score_col: str = DEFAULT_OUT_SCORE_COL,
    grid: str = DEFAULT_GRID,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    smiles_by_pair = _smiles_lookup(smiles_csv)
    input_rows = _read_csv(scores_csv)
    rows: list[dict[str, Any]] = []
    for row in input_rows:
        enriched: dict[str, Any] = dict(row)
        smiles = smiles_by_pair.get((_text(row.get("target")), _text(row.get("ligand_id"))), "")
        features = _nitrogen_features(smiles)
        probe = _probe(enriched, features)
        enriched["drd2_weakbase_false_support_smiles_present"] = bool(features["smiles_present"])
        enriched["drd2_weakbase_false_support_rdkit_parse_ok"] = bool(features["rdkit_parse_ok"])
        enriched["drd2_weakbase_false_support_protonatable_aliphatic_amine_count"] = int(
            features["protonatable_aliphatic_amine_count"]
        )
        enriched["drd2_weakbase_false_support_weak_nonprotonatable_n_count"] = int(
            features["weak_nonprotonatable_n_count"]
        )
        enriched["drd2_weakbase_false_support_total_n_count"] = int(features["total_n_count"])
        enriched["drd2_weakbase_false_support_probe"] = probe
        rows.append(enriched)

    before = _evaluate(rows, score_col)
    grid_rows: list[dict[str, Any]] = []
    for weight in _parse_grid(grid):
        scored = _apply_weight(rows, score_col, out_score_col, weight)
        metrics = _evaluate(scored, out_score_col)
        before_by_target = {row["target"]: row for row in before["positive_summaries"]}
        after_by_target = {row["target"]: row for row in metrics["positive_summaries"]}
        non_drd2_regressions = [
            target
            for target in POSITIVE_PAIRS
            if target != DRD2_TARGET
            and after_by_target[target]["target_rank"] is not None
            and before_by_target[target]["target_rank"] is not None
            and int(after_by_target[target]["target_rank"]) > int(before_by_target[target]["target_rank"])
        ]
        grid_rows.append(
            {
                "weight": float(weight),
                "ranking_pr_auc": metrics["ranking_pr_auc"],
                "top20_positive_count": metrics["top20_positive_count"],
                "drd2_target_rank": metrics["drd2_target_rank"],
                "drd2_decoys_above_positive": metrics["drd2_decoys_above_positive"],
                "non_drd2_positive_regression_count": len(non_drd2_regressions),
                "non_drd2_positive_regression_targets": ",".join(non_drd2_regressions),
            }
        )

    candidates = [
        row
        for row in grid_rows
        if _int_value(row.get("drd2_target_rank")) == 1
        and _int_value(row.get("drd2_decoys_above_positive")) == 0
        and _int_value(row.get("non_drd2_positive_regression_count"), default=0) == 0
    ]
    selected_grid = min(
        candidates or grid_rows,
        key=lambda row: (
            _int_value(row.get("drd2_target_rank")),
            _int_value(row.get("drd2_decoys_above_positive")),
            _int_value(row.get("non_drd2_positive_regression_count")),
            float(row.get("weight") or 0.0),
        ),
    )
    selected_weight = float(selected_grid.get("weight") or 0.0)
    selected_rows = _apply_weight(rows, score_col, out_score_col, selected_weight)
    after = _evaluate(selected_rows, out_score_col)
    top_decoy = next(
        (
            row
            for row in selected_rows
            if _text(row.get("target")) == DRD2_TARGET
            and _text(row.get("ligand_id")) == "decoy_CHEMBL217_DRD2_HUMAN_07800"
        ),
        {},
    )
    status = (
        "drd2_weakbase_false_support_shadow_replay_selected_slice_green_claim_locked"
        if _int_value(after["drd2_target_rank"]) == 1
        and _int_value(after["drd2_decoys_above_positive"]) == 0
        and _int_value(selected_grid.get("non_drd2_positive_regression_count"), default=0) == 0
        else "blocked_drd2_weakbase_false_support_shadow_replay"
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_rows": len(selected_rows),
        "score_col": score_col,
        "out_score_col": out_score_col,
        "selected_weight": selected_weight,
        "weakbase_false_support_probe_count": int(
            sum(1 for row in selected_rows if _float(row.get("drd2_weakbase_false_support_probe")) > 0)
        ),
        "drd2_weakbase_false_support_probe_count": int(
            sum(
                1
                for row in selected_rows
                if _text(row.get("target")) == DRD2_TARGET
                and _float(row.get("drd2_weakbase_false_support_probe")) > 0
            )
        ),
        "top_decoy_probe": _float(top_decoy.get("drd2_weakbase_false_support_probe")),
        "top_decoy_protonatable_aliphatic_amine_count": int(
            _float(top_decoy.get("drd2_weakbase_false_support_protonatable_aliphatic_amine_count"))
        ),
        "top_decoy_weak_nonprotonatable_n_count": int(
            _float(top_decoy.get("drd2_weakbase_false_support_weak_nonprotonatable_n_count"))
        ),
        "before_ranking_pr_auc": before["ranking_pr_auc"],
        "selected_ranking_pr_auc": after["ranking_pr_auc"],
        "before_top20_positive_count": before["top20_positive_count"],
        "selected_top20_positive_count": after["top20_positive_count"],
        "before_drd2_target_rank": before["drd2_target_rank"],
        "before_drd2_decoys_above_positive": before["drd2_decoys_above_positive"],
        "selected_drd2_target_rank": after["drd2_target_rank"],
        "selected_drd2_decoys_above_positive": after["drd2_decoys_above_positive"],
        "selected_non_drd2_positive_regression_count": int(
            selected_grid.get("non_drd2_positive_regression_count") or 0
        ),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "guarded_100k_rerun_allowed": False,
        "next_required_step": (
            "Use this as claim-locked chemistry evidence only, then rerun guarded shadow/full 100k claim review; "
            "do not promote active scorer until PR-AUC CI-low and leakage gates pass."
            if status.endswith("_green_claim_locked")
            else "The weak-base false-support replay did not clear DRD2 target-internal decoy intrusion; inspect the grid."
        ),
    }
    payload = {
        "packet_type": "gpcr_drd2_weakbase_false_support_shadow_replay",
        "summary": summary,
        "before_positive_summaries": before["positive_summaries"],
        "selected_positive_summaries": after["positive_summaries"],
        "selected_grid_row": selected_grid,
        "source_artifacts": {
            "scores_csv": _artifact(scores_csv),
            "smiles_csv": _artifact(smiles_csv),
        },
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "target_identity_feature_allowed": False,
            "threshold_relaxation_allowed": False,
            "shadow_review_only": True,
        },
    }
    return payload, grid_rows, selected_rows


def _render_md(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR DRD2 Weak-Base False-Support Shadow Replay",
        "",
        f"- status: `{s['status']}`",
        f"- input_rows: `{s['input_rows']}`",
        f"- selected_weight: `{s['selected_weight']}`",
        f"- weakbase_false_support_probe_count: `{s['weakbase_false_support_probe_count']}`",
        f"- drd2_weakbase_false_support_probe_count: `{s['drd2_weakbase_false_support_probe_count']}`",
        f"- top_decoy_probe: `{s['top_decoy_probe']}`",
        f"- before_drd2_target_rank: `{s['before_drd2_target_rank']}`",
        f"- selected_drd2_target_rank: `{s['selected_drd2_target_rank']}`",
        f"- before_drd2_decoys_above_positive: `{s['before_drd2_decoys_above_positive']}`",
        f"- selected_drd2_decoys_above_positive: `{s['selected_drd2_decoys_above_positive']}`",
        f"- before_ranking_pr_auc: `{s['before_ranking_pr_auc']}`",
        f"- selected_ranking_pr_auc: `{s['selected_ranking_pr_auc']}`",
        f"- selected_top20_positive_count: `{s['selected_top20_positive_count']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        "",
        "## Selected Positives",
        "",
        "| Target | Ligand | Global rank | Target rank | Decoys above |",
        "|---|---|---:|---:|---:|",
    ]
    for row in payload["selected_positive_summaries"]:
        lines.append(
            f"| `{row['target']}` | `{row['ligand_id']}` | {row['global_rank']} | "
            f"{row['target_rank']} | {row['decoys_above_positive']} |"
        )
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay DRD2 weak-base false-support penalty on frozen GPCR rows.")
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--smiles-csv", default=DEFAULT_SMILES_CSV)
    parser.add_argument("--score-col", default=DEFAULT_SCORE_COL)
    parser.add_argument("--out-score-col", default=DEFAULT_OUT_SCORE_COL)
    parser.add_argument("--grid", default=DEFAULT_GRID)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-grid-csv", default=DEFAULT_OUT_GRID_CSV)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, grid_rows, score_rows = build_replay(
        scores_csv=args.scores_csv,
        smiles_csv=args.smiles_csv,
        score_col=args.score_col,
        out_score_col=args.out_score_col,
        grid=args.grid,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_grid_csv, grid_rows)
    _write_csv(args.out_scores_csv, score_rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
