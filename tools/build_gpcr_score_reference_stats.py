#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EXCLUDED_ROLES = ["far_ood_eval", "near_ood_eval", "id_eval", "ood_eval", "eval", "test", "holdout"]
DEFAULT_FEATURE_COLS = [
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "mean_min_distance_A",
    "contact_fraction",
    "stability_score",
    "binding_energy_mmpbsa_std",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "ligand_affinity_hint",
    "ligand_onsps_norm",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _parse_csv_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.split(",")
    else:
        raw = list(value)
    return [str(item).strip() for item in raw if str(item).strip()]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _feature_stats(df: pd.DataFrame, feature_cols: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    features: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for col in feature_cols:
        if col not in df.columns:
            missing.append(col)
            continue
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if values.empty:
            missing.append(col)
            continue
        std = float(values.std())
        features[col] = {
            "count": int(values.shape[0]),
            "mean": float(values.mean()),
            "std": std if pd.notna(std) else None,
            "min": float(values.min()),
            "max": float(values.max()),
        }
    return features, missing


def build_payload(
    *,
    scores_csv: str | Path,
    split_csv: str | Path,
    feature_cols: str | Iterable[str] | None = None,
    include_roles: str | Iterable[str] | None = None,
    excluded_roles: str | Iterable[str] | None = None,
    family: str = "gpcr",
    target_col: str = "target",
    ligand_col: str = "ligand_id",
    role_col: str = "role",
) -> dict[str, Any]:
    scores_path = _resolve(scores_csv)
    split_path = _resolve(split_csv)
    include = _parse_csv_list(include_roles) or ["fit"]
    excluded = _parse_csv_list(excluded_roles) or list(DEFAULT_EXCLUDED_ROLES)
    features_requested = _parse_csv_list(feature_cols) or list(DEFAULT_FEATURE_COLS)

    scores = pd.read_csv(scores_path)
    split = pd.read_csv(split_path)
    required_score_cols = {target_col, ligand_col}
    required_split_cols = {target_col, ligand_col, role_col}
    missing_score_cols = sorted(required_score_cols.difference(scores.columns))
    missing_split_cols = sorted(required_split_cols.difference(split.columns))
    if missing_score_cols:
        raise ValueError(f"scores_csv missing required columns: {missing_score_cols}")
    if missing_split_cols:
        raise ValueError(f"split_csv missing required columns: {missing_split_cols}")

    split_roles = split[[target_col, ligand_col, role_col]].drop_duplicates()
    merged = scores.merge(split_roles, on=[target_col, ligand_col], how="inner")
    merged[role_col] = merged[role_col].astype(str)
    reference_df = merged[merged[role_col].isin(include)].copy()
    eval_role_used = int(reference_df[role_col].isin(excluded).sum())
    excluded_available = int(merged[merged[role_col].isin(excluded)].shape[0])
    features, missing_features = _feature_stats(reference_df, features_requested)
    invalid_std_features = [
        name for name, stats in features.items() if stats.get("std") is None or float(stats.get("std") or 0.0) <= 1e-12
    ]

    status = "pass"
    if reference_df.empty:
        status = "blocked_no_reference_rows"
    elif eval_role_used > 0:
        status = "blocked_eval_role_in_reference"
    elif missing_features:
        status = "blocked_missing_feature_stats"
    elif invalid_std_features:
        status = "blocked_invalid_feature_std"
    claim_safe = status == "pass"

    payload: dict[str, Any] = {
        "schema_version": "gpcr_score_reference_stats.v1",
        "reference_scope": {
            "family": str(family or "gpcr"),
            "scores_csv": _rel_or_abs(scores_path),
            "split_csv": _rel_or_abs(split_path),
            "include_roles": include,
            "excluded_roles": excluded,
            "target_col": target_col,
            "ligand_col": ligand_col,
            "role_col": role_col,
            "policy": "fit-role reference only; evaluation roles are audited but not used",
        },
        "summary": {
            "status": status,
            "claim_safe_reference": bool(claim_safe),
            "scaling_mode": "fixed_family_reference",
            "reference_row_count": int(reference_df.shape[0]),
            "merged_scored_split_row_count": int(merged.shape[0]),
            "excluded_role_available_row_count": excluded_available,
            "eval_role_used_in_reference_count": eval_role_used,
            "feature_count": int(len(features)),
            "requested_feature_count": int(len(features_requested)),
            "missing_feature_cols": missing_features,
            "invalid_std_feature_cols": invalid_std_features,
            "scores_sha256": _file_sha256(scores_path),
            "split_sha256": _file_sha256(split_path),
        },
        "features": features,
    }
    payload["summary"]["payload_sha256"] = _canonical_json_hash(payload)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("summary", {})
    scope = payload.get("reference_scope", {})
    rows = [
        "# GPCR Score Reference Stats",
        "",
        f"- status: `{summary.get('status')}`",
        f"- claim_safe_reference: `{summary.get('claim_safe_reference')}`",
        f"- scaling_mode: `{summary.get('scaling_mode')}`",
        f"- reference_row_count: `{summary.get('reference_row_count')}`",
        f"- eval_role_used_in_reference_count: `{summary.get('eval_role_used_in_reference_count')}`",
        f"- scores_csv: `{scope.get('scores_csv')}`",
        f"- split_csv: `{scope.get('split_csv')}`",
        "",
        "| feature | count | mean | std | min | max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for feature, stats in sorted((payload.get("features") or {}).items()):
        rows.append(
            f"| `{feature}` | {stats.get('count')} | {stats.get('mean')} | {stats.get('std')} | "
            f"{stats.get('min')} | {stats.get('max')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-leak GPCR fixed score reference scaling stats.")
    parser.add_argument("--scores-csv", required=True)
    parser.add_argument("--split-csv", required=True)
    parser.add_argument("--feature-cols", default=",".join(DEFAULT_FEATURE_COLS))
    parser.add_argument("--include-roles", default="fit")
    parser.add_argument("--excluded-roles", default=",".join(DEFAULT_EXCLUDED_ROLES))
    parser.add_argument("--family", default="gpcr")
    parser.add_argument("--target-col", default="target")
    parser.add_argument("--ligand-col", default="ligand_id")
    parser.add_argument("--role-col", default="role")
    parser.add_argument("--out-json", default="runs/gpcr_score_reference_stats_current.json")
    parser.add_argument("--out-md", default="runs/gpcr_score_reference_stats_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        scores_csv=args.scores_csv,
        split_csv=args.split_csv,
        feature_cols=args.feature_cols,
        include_roles=args.include_roles,
        excluded_roles=args.excluded_roles,
        family=args.family,
        target_col=args.target_col,
        ligand_col=args.ligand_col,
        role_col=args.role_col,
    )
    _write_json(_resolve(args.out_json), payload)
    _write_md(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
