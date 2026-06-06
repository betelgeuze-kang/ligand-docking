#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import torch

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_FORCE_DERIVATION_JSON = "runs/residual_force_derivation_validation_current.json"
DEFAULT_OUT_JSON = "runs/residual_energy_force_label_validation_current.json"
DEFAULT_OUT_CSV = "runs/residual_energy_force_label_validation_current.csv"
DEFAULT_OUT_MD = "runs/residual_energy_force_label_validation_current.md"

ENERGY_PROXY_COLUMNS = (
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
    "physics_favorable_energy_proxy",
)
CALIBRATION_FEATURE_COLUMNS = (
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
    "physics_favorable_energy_proxy",
    "binding_score_composite_v7",
    "mean_e_vdw",
    "mean_e_polar",
    "mean_e_nonpolar",
    "mean_e_solvation",
    "stability_score",
    "contact_fraction",
    "mean_min_distance_A",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "physics_net_support_proxy",
    "physics_contact_stability_proxy",
    "vdw_nonpolar_support_proxy",
    "polar_support_proxy",
    "solvation_penalty_proxy",
    "replicate_mean_binding_energy_mmpbsa_kcal_mol_proxy",
    "replicate_mean_mean_min_distance_A",
    "replicate_mean_active_score",
)

CLAIM_BOUNDARY = (
    "Residual energy/force label validation only; joins existing supervised production residual rows to local stage3 "
    "energy-proxy score artifacts, optionally fits a local hash-holdout ridge calibrator, and evaluates proxy quality "
    "against reference_binding_kcal_mol labels. It does not run docking, create new labels, derive forces, train "
    "production models, create checkpoints, promote production mode, upload, submit, email, delete, or mutate external "
    "state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _stage3_path_from_stage5(source_csv: str) -> Path:
    source = _resolve(source_csv)
    name = source.name
    if name.endswith("_stage5_ranking_rows.csv"):
        return source.with_name(name.replace("_stage5_ranking_rows.csv", "_stage3_scores.csv"))
    return source


def _pearson(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(a) != len(b):
        return 0.0
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    den_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    if den_a == 0.0 or den_b == 0.0:
        return 0.0
    return num / (den_a * den_b)


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(a: list[float], b: list[float]) -> float:
    return _pearson(_ranks(a), _ranks(b))


def _metric_row(metric: str, value: float, threshold: float, operator: str) -> dict[str, Any]:
    if operator == ">=":
        passed = value >= threshold
    elif operator == "<=":
        passed = value <= threshold
    else:
        raise ValueError(f"unsupported operator: {operator}")
    return {
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "operator": operator,
        "status": "pass" if passed else "fail",
        "release_blocker": not passed,
    }


def _split_bucket(target: str, ligand_id: str, holdout_percent: int) -> str:
    digest = hashlib.sha256(f"{target}::{ligand_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return "eval" if bucket < holdout_percent else "train"


def _with_calibration_predictions(
    detail_rows: list[dict[str, Any]],
    *,
    calibration_enabled: bool,
    holdout_percent: int,
    ridge_lambda: float,
) -> dict[str, Any]:
    if not calibration_enabled or len(detail_rows) < 4:
        for row in detail_rows:
            row["calibration_split"] = "disabled"
            row["calibrated_delta_energy_proxy_kcal_mol"] = row["delta_energy_proxy_kcal_mol"]
            row["calibrated_abs_error_kcal_mol"] = row["abs_error_kcal_mol"]
        return {
            "calibration_enabled": calibration_enabled,
            "calibration_ready": False,
            "calibration_blockers": ["calibration_disabled_or_too_few_rows"],
            "calibration_train_rows": 0,
            "calibration_eval_rows": 0,
            "calibration_ridge_lambda": ridge_lambda,
            "calibration_feature_count": len(CALIBRATION_FEATURE_COLUMNS),
        }

    train_indices: list[int] = []
    eval_indices: list[int] = []
    xs: list[list[float]] = []
    ys: list[float] = []
    for idx, row in enumerate(detail_rows):
        split = _split_bucket(str(row["target"]), str(row["ligand_id"]), holdout_percent)
        row["calibration_split"] = split
        if split == "eval":
            eval_indices.append(idx)
        else:
            train_indices.append(idx)
        xs.append([float(row.get(f"feature_{col}") or 0.0) for col in CALIBRATION_FEATURE_COLUMNS])
        ys.append(float(row["reference_binding_kcal_mol"]))

    if not train_indices or not eval_indices:
        for row in detail_rows:
            row["calibrated_delta_energy_proxy_kcal_mol"] = row["delta_energy_proxy_kcal_mol"]
            row["calibrated_abs_error_kcal_mol"] = row["abs_error_kcal_mol"]
        return {
            "calibration_enabled": calibration_enabled,
            "calibration_ready": False,
            "calibration_blockers": ["calibration_split_missing_train_or_eval"],
            "calibration_train_rows": len(train_indices),
            "calibration_eval_rows": len(eval_indices),
            "calibration_ridge_lambda": ridge_lambda,
            "calibration_feature_count": len(CALIBRATION_FEATURE_COLUMNS),
        }

    x = torch.tensor(xs, dtype=torch.float64)
    y = torch.tensor(ys, dtype=torch.float64)
    x_train = x[train_indices]
    y_train = y[train_indices]
    x_mean = x_train.mean(dim=0)
    x_std = x_train.std(dim=0, unbiased=False).clamp_min(1e-9)
    x_norm = (x - x_mean) / x_std
    design = torch.cat([torch.ones((len(train_indices), 1), dtype=torch.float64), x_norm[train_indices]], dim=1)
    penalty = torch.eye(design.shape[1], dtype=torch.float64)
    penalty[0, 0] = 0.0
    weights = torch.linalg.solve(design.T @ design + float(ridge_lambda) * penalty, design.T @ y_train)
    all_design = torch.cat([torch.ones((x_norm.shape[0], 1), dtype=torch.float64), x_norm], dim=1)
    predictions = (all_design @ weights).tolist()
    for row, prediction in zip(detail_rows, predictions):
        row["calibrated_delta_energy_proxy_kcal_mol"] = float(prediction)
        row["calibrated_abs_error_kcal_mol"] = abs(float(prediction) - float(row["reference_binding_kcal_mol"]))
    return {
        "calibration_enabled": calibration_enabled,
        "calibration_ready": True,
        "calibration_blockers": [],
        "calibration_train_rows": len(train_indices),
        "calibration_eval_rows": len(eval_indices),
        "calibration_ridge_lambda": ridge_lambda,
        "calibration_feature_count": len(CALIBRATION_FEATURE_COLUMNS),
        "calibration_feature_fields": list(CALIBRATION_FEATURE_COLUMNS),
    }


def _join_energy_proxy_rows(
    supervised_rows: list[dict[str, Any]],
    *,
    max_sources: int,
    max_rows_per_source: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    references: dict[tuple[str, str], dict[str, Any]] = {}
    for row in supervised_rows:
        target = str(row.get("target") or "").strip()
        ligand_id = str(row.get("ligand_id") or "").strip()
        reference = _float(row.get("reference_binding_kcal_mol"))
        if not target or not ligand_id or reference is None:
            continue
        references[(target, ligand_id)] = {
            "target": target,
            "ligand_id": ligand_id,
            "family": str(row.get("family") or "unknown"),
            "reference_binding_kcal_mol": reference,
            "source_csv": str(row.get("source_csv") or ""),
        }

    stage5_sources = sorted({item["source_csv"] for item in references.values() if item.get("source_csv")})
    proxy_values: dict[tuple[str, str], list[float]] = {}
    proxy_columns: dict[tuple[str, str], str] = {}
    feature_values: dict[tuple[str, str], dict[str, list[float]]] = {}
    source_rows: list[dict[str, Any]] = []
    for source in stage5_sources[: max(0, max_sources)]:
        path = _stage3_path_from_stage5(source)
        scanned = 0
        joined = 0
        proxy_rows = 0
        if not path.exists():
            source_rows.append(
                {
                    "source_csv": _rel(path),
                    "status": "missing_stage3_source",
                    "scanned_rows": 0,
                    "joined_rows": 0,
                    "proxy_rows": 0,
                    "energy_proxy_columns": "",
                }
            )
            continue
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            energy_cols = [col for col in ENERGY_PROXY_COLUMNS if col in set(fieldnames)]
            if "target" not in fieldnames or "ligand_id" not in fieldnames or not energy_cols:
                source_rows.append(
                    {
                        "source_csv": _rel(path),
                        "status": "skipped_missing_required_columns",
                        "scanned_rows": 0,
                        "joined_rows": 0,
                        "proxy_rows": 0,
                        "energy_proxy_columns": ",".join(energy_cols),
                    }
                )
                continue
            for raw in reader:
                scanned += 1
                if scanned > max_rows_per_source:
                    break
                key = (str(raw.get("target") or "").strip(), str(raw.get("ligand_id") or "").strip())
                if key not in references:
                    continue
                joined += 1
                for col in energy_cols:
                    value = _float(raw.get(col))
                    if value is None:
                        continue
                    proxy_values.setdefault(key, []).append(value)
                    proxy_columns.setdefault(key, col)
                    proxy_rows += 1
                    break
                bucket = feature_values.setdefault(key, {col: [] for col in CALIBRATION_FEATURE_COLUMNS})
                for col in CALIBRATION_FEATURE_COLUMNS:
                    value = _float(raw.get(col))
                    bucket[col].append(0.0 if value is None else value)
        source_rows.append(
            {
                "source_csv": _rel(path),
                "status": "used" if joined else "no_joined_rows",
                "scanned_rows": min(scanned, max_rows_per_source),
                "joined_rows": joined,
                "proxy_rows": proxy_rows,
                "energy_proxy_columns": ",".join(energy_cols),
            }
        )

    detail_rows = []
    for key, values in sorted(proxy_values.items()):
        ref = references[key]
        proxy = sum(values) / len(values)
        detail_rows.append(
            {
                "target": ref["target"],
                "ligand_id": ref["ligand_id"],
                "family": ref["family"],
                "reference_binding_kcal_mol": ref["reference_binding_kcal_mol"],
                "delta_energy_proxy_kcal_mol": proxy,
                "proxy_sample_count": len(values),
                "energy_proxy_column": proxy_columns.get(key, ""),
                "abs_error_kcal_mol": abs(proxy - float(ref["reference_binding_kcal_mol"])),
                "label_source": "joined_stage3_energy_proxy_vs_supervised_reference_binding",
            }
        )
        feature_bucket = feature_values.get(key, {})
        for col in CALIBRATION_FEATURE_COLUMNS:
            values = feature_bucket.get(col) or []
            detail_rows[-1][f"feature_{col}"] = sum(values) / len(values) if values else 0.0
    return detail_rows, source_rows


def build_residual_energy_force_label_validation(
    *,
    supervised_dataset_packet: dict[str, Any],
    force_derivation_packet: dict[str, Any] | None = None,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    force_derivation_path: str = DEFAULT_FORCE_DERIVATION_JSON,
    max_sources: int = 24,
    max_rows_per_source: int = 20000,
    min_pairs: int = 1000,
    min_targets: int = 3,
    min_pearson: float = 0.25,
    min_spearman: float = 0.25,
    max_rmse: float = 3.0,
    calibration_enabled: bool = True,
    calibration_holdout_percent: int = 20,
    calibration_ridge_lambda: float = 1.0,
) -> dict[str, Any]:
    supervised = _summary(supervised_dataset_packet)
    force_derivation = _summary(force_derivation_packet or {})
    supervised_rows = [dict(row) for row in supervised_dataset_packet.get("rows", []) or [] if isinstance(row, dict)]
    detail_rows, source_rows = _join_energy_proxy_rows(
        supervised_rows,
        max_sources=max_sources,
        max_rows_per_source=max_rows_per_source,
    )
    refs = [float(row["reference_binding_kcal_mol"]) for row in detail_rows]
    proxies = [float(row["delta_energy_proxy_kcal_mol"]) for row in detail_rows]
    targets = {str(row["target"]) for row in detail_rows}
    families = {str(row["family"]) for row in detail_rows}
    pair_count = len(detail_rows)
    raw_pearson = _pearson(refs, proxies) if detail_rows else 0.0
    raw_spearman = _spearman(refs, proxies) if detail_rows else 0.0
    raw_mae = sum(abs(a - b) for a, b in zip(refs, proxies)) / pair_count if pair_count else 0.0
    raw_rmse = math.sqrt(sum((a - b) ** 2 for a, b in zip(refs, proxies)) / pair_count) if pair_count else 0.0
    calibration = _with_calibration_predictions(
        detail_rows,
        calibration_enabled=calibration_enabled,
        holdout_percent=calibration_holdout_percent,
        ridge_lambda=calibration_ridge_lambda,
    )
    eval_rows = [row for row in detail_rows if row.get("calibration_split") == "eval"]
    metric_rows_for_energy = eval_rows if calibration.get("calibration_ready") else detail_rows
    metric_refs = [float(row["reference_binding_kcal_mol"]) for row in metric_rows_for_energy]
    metric_preds = [float(row["calibrated_delta_energy_proxy_kcal_mol"]) for row in metric_rows_for_energy]
    pearson = _pearson(metric_refs, metric_preds) if metric_rows_for_energy else 0.0
    spearman = _spearman(metric_refs, metric_preds) if metric_rows_for_energy else 0.0
    mae = sum(abs(a - b) for a, b in zip(metric_refs, metric_preds)) / len(metric_refs) if metric_refs else 0.0
    rmse = math.sqrt(sum((a - b) ** 2 for a, b in zip(metric_refs, metric_preds)) / len(metric_refs)) if metric_refs else 0.0

    metric_rows = [
        _metric_row("joined_energy_proxy_pair_count", float(pair_count), float(min_pairs), ">="),
        _metric_row("target_count", float(len(targets)), float(min_targets), ">="),
        _metric_row("pearson_reference_vs_energy_proxy", pearson, min_pearson, ">="),
        _metric_row("spearman_reference_vs_energy_proxy", spearman, min_spearman, ">="),
        _metric_row("rmse_reference_vs_energy_proxy_kcal_mol", rmse, max_rmse, "<="),
    ]
    blockers = [row["metric"] for row in metric_rows if row["status"] != "pass"]
    delta_energy_ready = not blockers
    delta_force_ready = force_derivation.get("delta_force_derivation_validation_ready") is True
    rows = metric_rows + [
        {
            "metric": "delta_force_derivation_validation",
            "value": 1.0 if delta_force_ready else 0.0,
            "threshold": 1.0,
            "operator": ">=",
            "status": "pass" if delta_force_ready else "fail",
            "release_blocker": not delta_force_ready,
        }
    ]
    force_blockers = [] if delta_force_ready else ["delta_force_derivation_validation"]
    summary = {
        "packet_type": "residual_energy_force_label_validation",
        "status": "residual_energy_force_label_validation_ready" if delta_energy_ready and delta_force_ready else "blocked_residual_energy_force_label_validation",
        "delta_energy_proxy_validation_ready": delta_energy_ready,
        "delta_force_derivation_validation_ready": delta_force_ready,
        "blocker_count": len(blockers) + len(force_blockers),
        "blockers": blockers + force_blockers,
        "joined_energy_proxy_pair_count": pair_count,
        "target_count": len(targets),
        "families": sorted(families),
        "energy_proxy_metric_mode": "hash_holdout_ridge_calibrated" if calibration.get("calibration_ready") else "raw_proxy",
        "pearson_reference_vs_energy_proxy": pearson,
        "spearman_reference_vs_energy_proxy": spearman,
        "mae_reference_vs_energy_proxy_kcal_mol": mae,
        "rmse_reference_vs_energy_proxy_kcal_mol": rmse,
        "raw_pearson_reference_vs_energy_proxy": raw_pearson,
        "raw_spearman_reference_vs_energy_proxy": raw_spearman,
        "raw_mae_reference_vs_energy_proxy_kcal_mol": raw_mae,
        "raw_rmse_reference_vs_energy_proxy_kcal_mol": raw_rmse,
        **calibration,
        "force_derivation_artifact": force_derivation_path,
        "force_derivation_status": force_derivation.get("status", ""),
        "force_derivation_blockers": [str(item) for item in force_derivation.get("blockers") or []],
        "force_derivation_next_required_step": str(force_derivation.get("next_required_step") or ""),
        "force_derivation_valid_trajectory_path_rows": int(force_derivation.get("valid_trajectory_path_rows") or 0),
        "force_derivation_existing_trajectory_npz_rows": int(force_derivation.get("existing_trajectory_npz_rows") or 0),
        "force_derivation_trajectory_remap_rows": int(force_derivation.get("trajectory_remap_rows") or 0),
        "force_derivation_trajectory_remap_candidate_rows": int(
            force_derivation.get("trajectory_remap_candidate_rows") or 0
        ),
        "force_derivation_existing_remapped_trajectory_npz_rows": int(
            force_derivation.get("existing_remapped_trajectory_npz_rows") or 0
        ),
        "force_derivation_effective_min_existing_npz_rows": int(
            force_derivation.get("effective_min_existing_npz_rows") or 0
        ),
        "force_derivation_existing_npz_floor_capped_by_available_paths": (
            force_derivation.get("existing_npz_floor_capped_by_available_paths") is True
        ),
        "force_derivation_input_sample_count": int(force_derivation.get("derivation_input_sample_count") or 0),
        "force_derivation_npz_readable_count": int(force_derivation.get("npz_readable_count") or 0),
        "force_derivation_coordinate_array_sample_count": int(force_derivation.get("coordinate_array_sample_count") or 0),
        "force_derivation_energy_array_sample_count": int(force_derivation.get("energy_array_sample_count") or 0),
        "min_pairs": min_pairs,
        "min_targets": min_targets,
        "min_pearson": min_pearson,
        "min_spearman": min_spearman,
        "max_rmse": max_rmse,
        "supervised_dataset_artifact": supervised_dataset_path,
        "supervised_rows": int(supervised.get("rows_emitted") or len(supervised_rows)),
        "execution_enabled": False,
        "validation_executed": True,
        "label_materialized": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Energy/force label validation is green; rebuild the training-data contract."
            if delta_energy_ready and delta_force_ready
            else "Energy proxy validation is green; create force derivation validation evidence."
            if delta_energy_ready
            else "Calibrate or replace the stage3 energy proxy until correlation/RMSE gates pass against reference binding labels."
        ),
    }
    if delta_energy_ready and not delta_force_ready and force_derivation.get("next_required_step"):
        summary["next_required_step"] = str(force_derivation.get("next_required_step"))
    return {"summary": summary, "rows": rows, "detail_rows": detail_rows, "sources": source_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"summary": payload["summary"], "rows": payload["rows"], "sources": payload["sources"][:24]}
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], detail_csv: str) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Energy/Force Label Validation",
        "",
        f"- status: `{s['status']}`",
        f"- delta_energy_proxy_validation_ready: `{s['delta_energy_proxy_validation_ready']}`",
        f"- delta_force_derivation_validation_ready: `{s['delta_force_derivation_validation_ready']}`",
        f"- joined_energy_proxy_pair_count: `{s['joined_energy_proxy_pair_count']}`",
        f"- target_count: `{s['target_count']}`",
        f"- energy_proxy_metric_mode: `{s['energy_proxy_metric_mode']}`",
        f"- calibration_train_rows: `{s['calibration_train_rows']}`",
        f"- calibration_eval_rows: `{s['calibration_eval_rows']}`",
        f"- pearson_reference_vs_energy_proxy: `{s['pearson_reference_vs_energy_proxy']}`",
        f"- spearman_reference_vs_energy_proxy: `{s['spearman_reference_vs_energy_proxy']}`",
        f"- rmse_reference_vs_energy_proxy_kcal_mol: `{s['rmse_reference_vs_energy_proxy_kcal_mol']}`",
        f"- raw_pearson_reference_vs_energy_proxy: `{s['raw_pearson_reference_vs_energy_proxy']}`",
        f"- raw_rmse_reference_vs_energy_proxy_kcal_mol: `{s['raw_rmse_reference_vs_energy_proxy_kcal_mol']}`",
        f"- detail_csv: `{detail_csv}`",
        "",
        "## Metrics",
        "",
        "| metric | status | value | threshold | operator |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['metric']}` | `{row['status']}` | `{row['value']}` | `{row['threshold']}` | `{row['operator']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate residual delta_energy/delta_force label evidence.")
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--force-derivation-json", default=DEFAULT_FORCE_DERIVATION_JSON)
    parser.add_argument("--max-sources", type=int, default=24)
    parser.add_argument("--max-rows-per-source", type=int, default=20000)
    parser.add_argument("--min-pairs", type=int, default=1000)
    parser.add_argument("--min-targets", type=int, default=3)
    parser.add_argument("--min-pearson", type=float, default=0.25)
    parser.add_argument("--min-spearman", type=float, default=0.25)
    parser.add_argument("--max-rmse", type=float, default=3.0)
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument("--calibration-holdout-percent", type=int, default=20)
    parser.add_argument("--calibration-ridge-lambda", type=float, default=1.0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_energy_force_label_validation(
        supervised_dataset_packet=_read_json(args.supervised_dataset_json),
        force_derivation_packet=_read_json(args.force_derivation_json),
        supervised_dataset_path=args.supervised_dataset_json,
        force_derivation_path=args.force_derivation_json,
        max_sources=args.max_sources,
        max_rows_per_source=args.max_rows_per_source,
        min_pairs=args.min_pairs,
        min_targets=args.min_targets,
        min_pearson=args.min_pearson,
        min_spearman=args.min_spearman,
        max_rmse=args.max_rmse,
        calibration_enabled=not args.no_calibration,
        calibration_holdout_percent=args.calibration_holdout_percent,
        calibration_ridge_lambda=args.calibration_ridge_lambda,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["detail_rows"])
    _write_markdown(args.out_md, payload, args.out_csv)


if __name__ == "__main__":
    main()
