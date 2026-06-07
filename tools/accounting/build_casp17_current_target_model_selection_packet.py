#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import itertools
import json
import math
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RANKED_PREDICTION_DIR = "runs/casp17_predictions_top5_current"
DEFAULT_MATERIALIZED_SELECTED_DIR = ""
DEFAULT_OUT_JSON = "runs/casp17_current_target_model_selection_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_current_target_model_selection_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_current_target_model_selection_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id", "rank"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2)


def _parse_rank(path: Path) -> int:
    match = re.search(r"_model_(\d+)TS\.pdb$", path.name)
    return int(match.group(1)) if match else 0


def _parse_candidate(path: Path) -> dict[str, Any]:
    ca: dict[tuple[str, int], tuple[float, float, float]] = {}
    chain_order: dict[str, list[tuple[int, tuple[float, float, float]]]] = {}
    b_factors: list[float] = []
    atom_count = 0
    seen_model = False
    in_first_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM":
            continue
        if seen_model and not in_first_model:
            continue
        atom_count += 1
        try:
            atom_name = line[12:16].strip()
            chain_id = line[21].strip() or "_"
            resseq = int(line[22:26])
            coord = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
            b_factor = float(line[60:66]) if len(line) >= 66 else 0.0
        except (IndexError, ValueError):
            continue
        if atom_name != "CA":
            continue
        key = (chain_id, resseq)
        ca[key] = coord
        chain_order.setdefault(chain_id, []).append((resseq, coord))
        if math.isfinite(b_factor):
            b_factors.append(b_factor)

    continuity_total = 0
    continuity_pass = 0
    max_gap = 0.0
    for values in chain_order.values():
        ordered = [coord for _resseq, coord in sorted(values)]
        for left, right in zip(ordered, ordered[1:]):
            distance = _distance(left, right)
            continuity_total += 1
            continuity_pass += int(2.0 <= distance <= 8.0)
            max_gap = max(max_gap, distance)
    confidence_mean = sum(b_factors) / len(b_factors) if b_factors else 0.0
    confidence_std = (
        math.sqrt(sum((value - confidence_mean) ** 2 for value in b_factors) / len(b_factors)) if b_factors else 0.0
    )
    ca_coords = list(ca.values())
    if ca_coords:
        center = tuple(sum(coord[index] for coord in ca_coords) / len(ca_coords) for index in range(3))
        radius_gyration = math.sqrt(sum(_distance(coord, center) ** 2 for coord in ca_coords) / len(ca_coords))
        xs = [coord[0] for coord in ca_coords]
        ys = [coord[1] for coord in ca_coords]
        zs = [coord[2] for coord in ca_coords]
        coordinate_span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    else:
        radius_gyration = 0.0
        coordinate_span = 0.0
    chain_linearity_values: list[float] = []
    for values in chain_order.values():
        ordered = [coord for _resseq, coord in sorted(values)]
        if len(ordered) < 2:
            continue
        contour_length = 3.8 * float(len(ordered) - 1)
        if contour_length > 0:
            chain_linearity_values.append(_distance(ordered[0], ordered[-1]) / contour_length)
    max_chain_linearity = max(chain_linearity_values) if chain_linearity_values else 0.0
    ca_keys = sorted(ca)
    nonlocal_ca_clash_count = 0
    nonlocal_ca_contact_count = 0
    interchain_ca_contact_count = 0
    interchain_ca_clash_count = 0
    for left_key, right_key in itertools.combinations(ca_keys, 2):
        same_chain = left_key[0] == right_key[0]
        if same_chain and abs(left_key[1] - right_key[1]) <= 2:
            continue
        ca_distance = _distance(ca[left_key], ca[right_key])
        if ca_distance < 2.0:
            nonlocal_ca_clash_count += 1
            if not same_chain:
                interchain_ca_clash_count += 1
        if ca_distance <= 12.0:
            nonlocal_ca_contact_count += 1
            if not same_chain:
                interchain_ca_contact_count += 1
    return {
        "rank": _parse_rank(path),
        "path": path,
        "ca": ca,
        "atom_count": atom_count,
        "ca_count": len(ca),
        "chain_count": len(chain_order),
        "continuity_total": continuity_total,
        "continuity_pass": continuity_pass,
        "continuity_fraction": continuity_pass / continuity_total if continuity_total else 0.0,
        "max_ca_gap_A": max_gap,
        "confidence_mean": confidence_mean,
        "confidence_stddev": confidence_std,
        "ca_radius_gyration_A": radius_gyration,
        "ca_coordinate_span_A": coordinate_span,
        "ca_span_per_residue": coordinate_span / max(1.0, float(len(ca))),
        "max_chain_linearity": max_chain_linearity,
        "nonlocal_ca_clash_count": nonlocal_ca_clash_count,
        "nonlocal_ca_contact_count": nonlocal_ca_contact_count,
        "interchain_ca_contact_count": interchain_ca_contact_count,
        "interchain_ca_clash_count": interchain_ca_clash_count,
    }


def _target_candidates(root: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    if not root.exists():
        return result
    for path in sorted(root.glob("*/*_model_*TS.pdb")):
        target_id = path.parent.name.upper()
        result.setdefault(target_id, []).append(path)
    for path in sorted(root.glob("*_model_*TS.pdb")):
        target_id = path.name.split("_model_", 1)[0].upper()
        result.setdefault(target_id, []).append(path)
    return {target_id: sorted(paths, key=_parse_rank) for target_id, paths in result.items()}


def _sample_residue_pairs(keys: list[tuple[str, int]], limit: int) -> list[tuple[tuple[str, int], tuple[str, int]]]:
    pairs = [
        (left, right)
        for left, right in itertools.combinations(keys, 2)
        if left[0] != right[0] or abs(left[1] - right[1]) >= 3
    ]
    if len(pairs) <= limit:
        return pairs
    stride = max(1, len(pairs) // limit)
    sampled = pairs[::stride][:limit]
    return sampled


def _distance_map_agreement(
    left: dict[tuple[str, int], tuple[float, float, float]],
    right: dict[tuple[str, int], tuple[float, float, float]],
    pairs: list[tuple[tuple[str, int], tuple[str, int]]],
) -> tuple[float, float]:
    if not pairs:
        return 0.0, 0.0
    agreement = 0.0
    left_contacts: set[int] = set()
    right_contacts: set[int] = set()
    for index, (first, second) in enumerate(pairs):
        left_distance = _distance(left[first], left[second])
        right_distance = _distance(right[first], right[second])
        agreement += math.exp(-abs(left_distance - right_distance) / 4.0)
        if left_distance <= 12.0:
            left_contacts.add(index)
        if right_distance <= 12.0:
            right_contacts.add(index)
    union = left_contacts | right_contacts
    contact_jaccard = len(left_contacts & right_contacts) / len(union) if union else 1.0
    return agreement / len(pairs), contact_jaccard


def _score_target(target_id: str, paths: list[Path], args: argparse.Namespace) -> list[dict[str, Any]]:
    candidates = [_parse_candidate(path) for path in paths]
    candidates = [candidate for candidate in candidates if int(candidate["rank"]) > 0 and candidate["ca_count"] > 0]
    if not candidates:
        return []
    common_keys = sorted(set.intersection(*(set(candidate["ca"]) for candidate in candidates))) if len(candidates) > 1 else sorted(candidates[0]["ca"])
    residue_pairs = _sample_residue_pairs(common_keys, int(args.max_distance_pairs))

    pairwise: dict[int, list[tuple[float, float]]] = {int(candidate["rank"]): [] for candidate in candidates}
    for left, right in itertools.combinations(candidates, 2):
        distance_agreement, contact_jaccard = _distance_map_agreement(left["ca"], right["ca"], residue_pairs)
        pairwise[int(left["rank"])].append((distance_agreement, contact_jaccard))
        pairwise[int(right["rank"])].append((distance_agreement, contact_jaccard))

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rank = int(candidate["rank"])
        pair_scores = pairwise.get(rank, [])
        consensus_distance = sum(item[0] for item in pair_scores) / len(pair_scores) if pair_scores else 1.0
        consensus_contacts = sum(item[1] for item in pair_scores) / len(pair_scores) if pair_scores else 1.0
        consensus_score = 0.70 * consensus_distance + 0.30 * consensus_contacts
        confidence_score = max(0.0, min(1.0, float(candidate["confidence_mean"]) / 100.0))
        continuity_score = max(0.0, min(1.0, float(candidate["continuity_fraction"])))
        gap_penalty = min(max(float(candidate["max_ca_gap_A"]) - 8.0, 0.0) / 20.0, 0.35)
        clash_score = max(
            0.0,
            min(1.0, 1.0 - (float(candidate["nonlocal_ca_clash_count"]) / max(1.0, float(candidate["ca_count"]) * 0.05))),
        )
        if int(candidate["chain_count"]) > 1:
            interface_score = 0.70 * max(
                0.0,
                min(1.0, 1.0 - (float(candidate["interchain_ca_clash_count"]) / max(1.0, float(candidate["chain_count"]) - 1.0))),
            ) + 0.30 * max(0.0, min(1.0, float(candidate["interchain_ca_contact_count"]) / 20.0))
        else:
            interface_score = 1.0
        span_per_residue = float(candidate["ca_span_per_residue"])
        radius_per_residue = float(candidate["ca_radius_gyration_A"]) / max(1.0, float(candidate["ca_count"]))
        max_chain_linearity = float(candidate["max_chain_linearity"])
        span_penalty = min(max(span_per_residue - float(args.max_span_per_residue), 0.0) / 0.65, 0.45)
        radius_penalty = min(max(radius_per_residue - float(args.max_radius_gyration_per_residue), 0.0) / 0.20, 0.35)
        linearity_penalty = min(max(max_chain_linearity - float(args.max_chain_linearity), 0.0) / 0.35, 0.30)
        shape_penalty = min(0.65, span_penalty + radius_penalty + linearity_penalty)
        shape_plausibility_score = max(0.0, 1.0 - shape_penalty)
        shape_status = "pass" if shape_penalty <= float(args.max_shape_penalty_for_recommendation) else "blocked_linear_or_overextended"
        selection_score = max(
            0.0,
            min(
                1.0,
                0.49 * consensus_score
                + 0.20 * confidence_score
                + 0.15 * continuity_score
                + 0.08 * clash_score
                + 0.05 * interface_score
                + 0.08 * shape_plausibility_score
                - gap_penalty
                - shape_penalty
                + (0.03 if rank == 1 else 0.0),
            ),
        )
        rows.append(
            {
                "target_id": target_id,
                "rank": rank,
                "candidate_pdb": _artifact(candidate["path"]),
                "selection_status": "candidate",
                "selection_score": round(selection_score, 6),
                "consensus_score": round(consensus_score, 6),
                "distance_map_agreement": round(consensus_distance, 6),
                "contact_map_jaccard": round(consensus_contacts, 6),
                "confidence_mean": round(float(candidate["confidence_mean"]), 3),
                "confidence_stddev": round(float(candidate["confidence_stddev"]), 3),
                "continuity_fraction": round(float(candidate["continuity_fraction"]), 6),
                "max_ca_gap_A": round(float(candidate["max_ca_gap_A"]), 3),
                "clash_score": round(clash_score, 6),
                "interface_score": round(interface_score, 6),
                "shape_plausibility_score": round(shape_plausibility_score, 6),
                "shape_penalty": round(shape_penalty, 6),
                "shape_status": shape_status,
                "ca_radius_gyration_A": round(float(candidate["ca_radius_gyration_A"]), 3),
                "ca_coordinate_span_A": round(float(candidate["ca_coordinate_span_A"]), 3),
                "ca_span_per_residue": round(span_per_residue, 6),
                "ca_radius_gyration_per_residue": round(radius_per_residue, 6),
                "max_chain_linearity": round(max_chain_linearity, 6),
                "nonlocal_ca_clash_count": int(candidate["nonlocal_ca_clash_count"]),
                "nonlocal_ca_contact_count": int(candidate["nonlocal_ca_contact_count"]),
                "interchain_ca_clash_count": int(candidate["interchain_ca_clash_count"]),
                "interchain_ca_contact_count": int(candidate["interchain_ca_contact_count"]),
                "ca_count": int(candidate["ca_count"]),
                "common_ca_count": len(common_keys),
                "distance_pair_count": len(residue_pairs),
                "materialization_status": "not_requested",
                "materialized_selected_pdb": "",
                "materialized_model_index": "",
                "claim_boundary": "Current-target internal consensus ranker only; no native/public/template/current-target structure lookup.",
            }
        )
    rows.sort(key=lambda row: (-float(row["selection_score"]), int(row["rank"])))
    pass_rows = [row for row in rows if row["shape_status"] == "pass"]
    if pass_rows:
        pass_rows[0]["selection_status"] = "recommended_model_1"
    elif rows:
        rows[0]["selection_status"] = "recommended_model_1_shape_blocked_fallback"
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = _resolve(args.ranked_prediction_dir)
    by_target = _target_candidates(root)
    target_ids = sorted(by_target)
    if _text(args.target_ids):
        allowed = {item.strip().upper() for item in _text(args.target_ids).split(",") if item.strip()}
        target_ids = [target_id for target_id in target_ids if target_id in allowed]
    if int(args.target_limit) > 0:
        target_ids = target_ids[: int(args.target_limit)]
    rows: list[dict[str, Any]] = []
    for target_id in target_ids:
        rows.extend(_score_target(target_id, by_target[target_id], args))
    recommended = [row for row in rows if row["selection_status"] == "recommended_model_1"]
    changed = [row for row in recommended if int(row["rank"]) != 1]
    summary = {
        "packet_type": "casp17_current_target_model_selection_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "ranked_prediction_dir": _artifact(root),
        "target_count": len(target_ids),
        "candidate_count": len(rows),
        "recommended_count": len(recommended),
        "recommended_rank1_count": sum(1 for row in recommended if int(row["rank"]) == 1),
        "recommended_non_rank1_count": len(changed),
        "selection_status": "pass" if target_ids and len(recommended) == len(target_ids) else "blocked",
        "mean_recommended_selection_score": round(
            sum(float(row["selection_score"]) for row in recommended) / len(recommended), 6
        )
        if recommended
        else 0.0,
        "mean_recommended_consensus_score": round(
            sum(float(row["consensus_score"]) for row in recommended) / len(recommended), 6
        )
        if recommended
        else 0.0,
        "materialized_selected_dir": "",
        "materialized_count": 0,
        "materialized_non_rank1_count": 0,
        "materialization_status": "not_requested",
        "ranker": "distance_map_consensus_plus_confidence_ca_continuity_clash_and_interface_proxy",
        "shape_guard": {
            "max_span_per_residue": float(args.max_span_per_residue),
            "max_radius_gyration_per_residue": float(args.max_radius_gyration_per_residue),
            "max_chain_linearity": float(args.max_chain_linearity),
            "max_shape_penalty_for_recommendation": float(args.max_shape_penalty_for_recommendation),
        },
        "claim_boundary": (
            "Current-target internal model-selection support only. It may help avoid top-5 outliers, but it is not "
            "native-calibrated accuracy evidence, official CASP assessment, or a substitute for no-leak historical calibration."
        ),
    }
    return {"summary": summary, "rows": sorted(rows, key=lambda row: (row["target_id"], row["rank"]))}


def _rewrite_selected_model(source: Path, target_id: str, source_rank: int, out_path: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    rewritten: list[str] = []
    model_seen = False
    inserted_selection_remark = False
    for line in lines:
        rec = _record(line)
        if rec == "MODEL" and not model_seen:
            rewritten.append("MODEL 1")
            rewritten.append(f"REMARK INTERNAL_SELECTION_SOURCE_RANK {source_rank}")
            rewritten.append("REMARK INTERNAL_SELECTION_SCOPE current-target top5 internal consensus only")
            model_seen = True
            inserted_selection_remark = True
            continue
        rewritten.append(line)
    if not model_seen:
        rewritten.insert(0, "MODEL 1")
    if not inserted_selection_remark:
        insert_at = 0
        for index, line in enumerate(rewritten):
            if _record(line) in {"PFRMAT", "TARGET", "AUTHOR", "METHOD"}:
                insert_at = index + 1
        rewritten.insert(insert_at, f"REMARK INTERNAL_SELECTION_SOURCE_RANK {source_rank}")
        rewritten.insert(insert_at + 1, "REMARK INTERNAL_SELECTION_SCOPE current-target top5 internal consensus only")
    if not any(_record(line) == "TARGET" for line in rewritten):
        rewritten.insert(0, f"TARGET {target_id}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(rewritten).rstrip() + "\n", encoding="utf-8")


def _materialize_selected(payload: dict[str, Any], selected_dir_like: str | Path, require_materialized: bool) -> None:
    selected_dir_text = _text(selected_dir_like)
    summary = payload["summary"]
    if not selected_dir_text:
        summary["materialization_status"] = "not_requested"
        return
    selected_dir = _resolve(selected_dir_text)
    selected_dir.mkdir(parents=True, exist_ok=True)
    materialized_count = 0
    blocked_count = 0
    for row in payload["rows"]:
        if not str(row.get("selection_status")).startswith("recommended_model_1"):
            continue
        target_id = _text(row.get("target_id")).upper()
        source = _resolve(_text(row.get("candidate_pdb")))
        out_path = selected_dir / f"{target_id}TS.pdb"
        if not source.exists():
            row["materialization_status"] = "blocked_missing_candidate"
            blocked_count += 1
            continue
        try:
            _rewrite_selected_model(source, target_id, int(row["rank"]), out_path)
        except OSError:
            row["materialization_status"] = "blocked_write_failed"
            blocked_count += 1
            continue
        row["materialization_status"] = "materialized_selected_model_1"
        row["materialized_selected_pdb"] = _artifact(out_path)
        row["materialized_model_index"] = 1
        materialized_count += 1
    summary["materialized_selected_dir"] = _artifact(selected_dir)
    summary["materialized_count"] = materialized_count
    summary["materialized_non_rank1_count"] = sum(
        1
        for row in payload["rows"]
        if row.get("materialization_status") == "materialized_selected_model_1" and int(row.get("rank") or 0) != 1
    )
    if blocked_count:
        summary["materialization_status"] = "blocked"
    elif materialized_count == int(summary.get("recommended_count") or 0) and materialized_count:
        summary["materialization_status"] = "pass"
    else:
        summary["materialization_status"] = "blocked" if require_materialized else "partial"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current-Target Model Selection Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- selection_status: `{summary['selection_status']}`",
        f"- targets: `{summary['target_count']}`",
        f"- candidates: `{summary['candidate_count']}`",
        f"- recommended non-rank1: `{summary['recommended_non_rank1_count']}`",
        f"- mean recommended score: `{summary['mean_recommended_selection_score']}`",
        f"- materialization: `{summary['materialization_status']}`",
        f"- materialized selected dir: `{summary['materialized_selected_dir']}`",
        f"- materialized selected models: `{summary['materialized_count']}`",
        f"- ranker: `{summary['ranker']}`",
        "",
        "## Candidates",
        "",
        "| target | rank | status | score | consensus | confidence | continuity | clash | interface | shape | materialized | candidate |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['rank']} | `{row['selection_status']}` | {row['selection_score']} | "
            f"{row['consensus_score']} | {row['confidence_mean']} | {row['continuity_fraction']} | "
            f"{row['clash_score']} | {row['interface_score']} | {row['shape_plausibility_score']} | "
            f"`{row['materialization_status']}` | `{row['candidate_pdb']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | 0 | `blocked` | 0 | 0 | 0 | 0 | 0 | 0 | `blocked` | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank current CASP17 top-5 candidates with internal consensus evidence.")
    parser.add_argument("--ranked-prediction-dir", default=DEFAULT_RANKED_PREDICTION_DIR)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--max-distance-pairs", type=int, default=8000)
    parser.add_argument("--max-span-per-residue", type=float, default=0.35)
    parser.add_argument("--max-radius-gyration-per-residue", type=float, default=0.18)
    parser.add_argument("--max-chain-linearity", type=float, default=0.24)
    parser.add_argument("--max-shape-penalty-for-recommendation", type=float, default=0.05)
    parser.add_argument("--materialize-selected-dir", default=DEFAULT_MATERIALIZED_SELECTED_DIR)
    parser.add_argument("--require-materialized", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _materialize_selected(payload, args.materialize_selected_dir, bool(args.require_materialized))
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["selection_status"] != "pass":
        raise SystemExit(2)
    if args.require_materialized and payload["summary"]["materialization_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
