#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
import pandas as pd

from core.mm_gbsa import mm_gbsa_refinement_delta
from betelgeuze_engine.product.selection_score_authority import (
    load_authority_summary,
    resolve_selection_score_authority,
)
from betelgeuze_engine.product.pocketmd_admission_authority import (
    derive_pocketmd_admission_batch,
    validate_pocketmd_admission_batch,
)
from betelgeuze_engine.product.implementation_provenance import (
    build_implementation_source_manifest,
)
from betelgeuze_product.pocketmd_lite_contract import (
    PocketMdAdmissionPolicy,
)


_FIXED_REFINEMENT_OUTPUT_COLUMNS = frozenset(
    {
        "__pocketmd_source_index",
        "pocketmd_upstream_topk_selected",
        "pocketmd_authority_rank_global",
        "pocketmd_authority_rank_pct",
        "pocketmd_admitted",
        "pocketmd_admission_reason",
        "pocketmd_admission_reason_codes",
        "pocketmd_admission_estimated_cost",
        "pocketmd_admission_cumulative_cost_before",
        "pocketmd_admission_cumulative_cost_after",
        "pocketmd_admission_cost_unit",
        "pocketmd_admission_policy_sha256",
        "selection_score_authority_schema_version",
        "selection_score_policy_sha256",
        "physics_refinement_selected",
        "physics_refinement_shortlist_tier",
        "physics_refinement_lane_mode",
        "physics_refinement_backend",
        "physics_refinement_input_score_col",
        "physics_refinement_input_score",
        "physics_refinement_delta_kcal_mol",
        "physics_refinement_distance_penalty",
        "physics_refinement_contact_penalty",
        "physics_refinement_stability_penalty",
        "physics_refinement_uncertainty_penalty",
        "physics_refinement_support_bonus",
        "physics_refinement_low_frame_penalty",
        "physics_refinement_confidence",
        "physics_refinement_decision_bucket",
        "physics_refinement_shortlist_rank_global",
        "physics_refinement_shortlist_rank_target",
    }
)
_REFINEMENT_BACKEND_ALIASES = {
    "deterministic_surrogate_wrapper_v1": "deterministic_surrogate_wrapper_v1",
    "internal_gb_sa": "internal_gb_sa_v1",
    "internal_gb_sa_v1": "internal_gb_sa_v1",
    "internal_full_stack": "internal_full_stack_v1",
    "internal_full_stack_v1": "internal_full_stack_v1",
}


def normalize_refinement_backend(value: Any) -> str:
    requested = str(value or "").strip().lower()
    normalized = _REFINEMENT_BACKEND_ALIASES.get(requested)
    if normalized is None:
        raise ValueError(
            f"unsupported refinement backend: {requested or '<empty>'}"
        )
    return normalized


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_usable_numeric(df: pd.DataFrame, col: str) -> bool:
    name = str(col or "").strip()
    if (not name) or (name not in df.columns):
        return False
    vals = pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)
    return bool(np.isfinite(vals).any())


def _safe_optional_float(value: Any) -> Optional[float]:
    try:
        if value in {None, ""}:
            return None
        out = float(value)
        return float(out) if np.isfinite(out) else None
    except Exception:
        return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _identity_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, (str, int, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _row_identity_sha256(row: Mapping[str, Any]) -> str:
    payload = {
        "columns": [str(column) for column in row],
        "values": [_identity_scalar(value) for value in row.values()],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _numeric_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if str(col or "").strip() and col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
    else:
        vals = pd.Series(np.nan, index=df.index, dtype=float)
    if vals.notna().any():
        fill = float(vals.median())
        if not np.isfinite(fill):
            fill = float(default)
    else:
        fill = float(default)
    return vals.fillna(fill).astype(float)


def _parse_families(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").split(",")
    return tuple(sorted({item.strip().lower().replace("-", "_") for item in raw if item.strip()}))


def _decision_bucket(delta: pd.Series, confidence: pd.Series) -> pd.Series:
    bucket = np.full((len(delta),), "watch", dtype=object)
    bucket[(delta <= 0.75) & (confidence >= 0.70)] = "advance"
    bucket[(delta > 2.50) | (confidence < 0.35)] = "hold"
    return pd.Series(bucket, index=delta.index, dtype=object)


def run_refinement(args: argparse.Namespace) -> Dict[str, Any]:
    scores_csv = str(args.scores_csv).strip()
    if (not scores_csv) or (not os.path.exists(scores_csv)):
        raise FileNotFoundError(f"scores csv not found: {scores_csv}")
    df = pd.read_csv(scores_csv)
    if df.empty:
        raise ValueError(f"scores csv is empty: {scores_csv}")

    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    warnings: List[str] = []
    backend_requested = str(getattr(args, "backend", "") or "").strip()
    backend = normalize_refinement_backend(backend_requested)
    implementation_manifest = build_implementation_source_manifest()
    implementation_fingerprint = str(
        implementation_manifest["manifest_sha256"]
    )
    selection_mode = str(getattr(args, "selection_mode", "union") or "union").strip().lower()
    if selection_mode not in {"union", "intersection"}:
        raise ValueError("--selection-mode must be union|intersection")

    authority_summary_json = str(
        getattr(args, "selection_authority_summary_json", "") or ""
    ).strip()
    if not authority_summary_json:
        raise ValueError("--selection-authority-summary-json is required")
    declared_authority = load_authority_summary(authority_summary_json)
    selection_score_authority = resolve_selection_score_authority(
        df,
        declared_authority=declared_authority,
        requested_score_column=str(getattr(args, "score_col", "") or ""),
    )
    score_col = selection_score_authority.score_column
    lower_better = selection_score_authority.score_direction == "ascending"
    target_col = str(getattr(args, "target_col", "target") or "target")
    ligand_col = str(getattr(args, "ligand_col", "ligand_id") or "ligand_id")
    family_col = str(getattr(args, "family_col", "family") or "family")
    cost_col = str(getattr(args, "admission_cost_col", "") or "").strip()
    if target_col not in df.columns:
        raise ValueError(f"PocketMD admission requires target column: {target_col}")
    if cost_col and cost_col not in df.columns:
        raise ValueError(f"PocketMD admission cost column missing: {cost_col}")
    if family_col not in df.columns:
        warnings.append(
            f"PocketMD family column missing: {family_col}; all admissions fail closed."
        )
    base_proxy_col = str(
        getattr(
            args,
            "base_proxy_col",
            "binding_energy_mmpbsa_kcal_mol_proxy",
        )
        or ""
    )

    admission_policy = PocketMdAdmissionPolicy.create(
        eligible_families=_parse_families(
            getattr(args, "admission_eligible_families", "gpcr,kinase,ion_channel")
        ),
        rank_threshold_pct=float(getattr(args, "admission_rank_threshold_pct", 0.05)),
        max_per_target=int(getattr(args, "admission_max_per_target", 8)),
        max_per_job=int(getattr(args, "admission_max_per_job", 32)),
        cost_budget=float(getattr(args, "admission_cost_budget", 32.0)),
        unit_cost=float(getattr(args, "admission_unit_cost", 1.0)),
        cost_unit=str(
            getattr(args, "admission_cost_unit", "normalized_refinement_unit")
            or "normalized_refinement_unit"
        ),
        selection_policy_sha256=selection_score_authority.policy_sha256,
        selection_authority_schema_version=selection_score_authority.schema_version,
        topk_global=int(getattr(args, "topk_global", 0)),
        topk_per_target=int(getattr(args, "topk_per_target", 0)),
        selection_mode=selection_mode,
        target_column=target_col,
        family_column=family_col,
        cost_column=cost_col,
        base_proxy_column=base_proxy_col,
    )

    if not _has_usable_numeric(df, base_proxy_col):
        raise ValueError(f"base proxy column is missing or non-numeric: {base_proxy_col}")
    base_proxy_numeric = pd.to_numeric(df[base_proxy_col], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    refined_energy_col = str(getattr(args, "refined_energy_col", "binding_energy_explicit_water_recheck_kcal_mol_proxy") or "binding_energy_explicit_water_recheck_kcal_mol_proxy")
    refined_rank_col = str(getattr(args, "refined_rank_col", "binding_score_stronger_physics_v1") or "binding_score_stronger_physics_v1")
    existing_reserved = sorted(_FIXED_REFINEMENT_OUTPUT_COLUMNS & set(df.columns))
    if existing_reserved:
        raise ValueError(
            f"input contains reserved refinement output columns: {existing_reserved}"
        )
    if refined_energy_col == refined_rank_col:
        raise ValueError("refined energy and rank columns must be distinct")
    for output_column in (refined_energy_col, refined_rank_col):
        if not output_column or output_column.startswith("__"):
            raise ValueError(f"invalid refinement output column: {output_column!r}")
        if output_column in _FIXED_REFINEMENT_OUTPUT_COLUMNS:
            raise ValueError(
                f"refinement output column conflicts with reserved output: {output_column}"
            )
        if output_column in df.columns:
            raise ValueError(
                f"refinement output column would overwrite input evidence: {output_column}"
            )

    admission_entry_id_col = "__pocketmd_admission_entry_id"
    if admission_entry_id_col in df.columns:
        raise ValueError(
            f"reserved PocketMD admission entry column already exists: {admission_entry_id_col}"
        )
    admission_population = df.assign(
        **{
            admission_entry_id_col: [
                f"{index}:{_text(row.get(target_col))}:{_row_identity_sha256(row)}"
                for index, row in enumerate(df.to_dict(orient="records"))
            ]
        }
    )
    admission_batch = derive_pocketmd_admission_batch(
        admission_population,
        authority=selection_score_authority,
        policy=admission_policy,
        entry_id_column=admission_entry_id_col,
    )
    validated_admission = validate_pocketmd_admission_batch(
        admission_batch,
        admission_population,
    )
    admission_decisions: Dict[int, Dict[str, Any]] = {
        int(record["source_index"]): dict(record["decision"])
        for record in validated_admission["records"]
    }
    selected_idx = sorted(
        source_index
        for source_index, decision in admission_decisions.items()
        if decision["admitted"]
    )
    admitted_count = len(selected_idx)
    cumulative_admitted_cost = max(
        (
            float(decision.get("cumulative_cost_after") or 0.0)
            for decision in admission_decisions.values()
        ),
        default=0.0,
    )
    upstream_selected_indices = {
        source_index
        for source_index, decision in admission_decisions.items()
        if decision.get("upstream_topk_selected") is True
    }
    target_admitted_counts: Dict[str, int] = {}
    for decision in admission_decisions.values():
        if decision["admitted"]:
            target_id = str(decision.get("target") or "")
            target_admitted_counts[target_id] = (
                target_admitted_counts.get(target_id, 0) + 1
            )

    selected_mask = pd.Series(False, index=df.index, dtype=bool)
    if selected_idx:
        selected_mask.loc[selected_idx] = True
    else:
        warnings.append(
            "PocketMD admission selected no rows; refinement columns are carry-through aliases."
        )

    out = df.copy()
    proxy_energy_export = base_proxy_numeric.astype(float)
    proxy_energy = _numeric_series(out, base_proxy_col, default=0.0)
    input_score_export = pd.to_numeric(out[score_col], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    input_score = _numeric_series(out, score_col, default=float(proxy_energy.median()))
    mean_min_distance = _numeric_series(out, "mean_min_distance_A", default=4.0)
    contact_fraction = _numeric_series(out, "contact_fraction", default=0.10).clip(lower=0.0, upper=1.0)
    stability_score = _numeric_series(out, "stability_score", default=0.10).clip(lower=0.0)
    frame_contact_std = _numeric_series(out, "frame_contact_fraction_std", default=0.0).clip(lower=0.0)
    dist_std = _numeric_series(out, "replicate_std_mean_min_distance_A", default=0.0).clip(lower=0.0)
    energy_std = _numeric_series(out, "replicate_std_binding_energy_mmpbsa_kcal_mol_proxy", default=0.0).clip(lower=0.0)
    stability_std = _numeric_series(out, "replicate_std_stability_score", default=0.0).clip(lower=0.0)
    traj_frames = _numeric_series(out, "trajectory_frames", default=0.0).clip(lower=0.0)

    distance_penalty = (mean_min_distance - 2.60).clip(lower=0.0) * 0.90
    contact_penalty = (0.32 - contact_fraction).clip(lower=0.0) * 8.00
    stability_penalty = (0.24 - stability_score).clip(lower=0.0) * 5.50
    uncertainty_penalty = (
        frame_contact_std * 4.00
        + dist_std * 0.60
        + energy_std * 0.22
        + stability_std * 2.50
    )
    low_frame_penalty = (60.0 - traj_frames).clip(lower=0.0) / 60.0
    support_bonus = (
        (contact_fraction - 0.45).clip(lower=0.0) * 1.20
        + (stability_score - 0.30).clip(lower=0.0) * 0.80
    )
    recheck_delta = (
        0.25
        + distance_penalty
        + contact_penalty
        + stability_penalty
        + uncertainty_penalty
        + low_frame_penalty
        - support_bonus
    ).clip(lower=0.05, upper=8.0)
    confidence = (
        1.0
        / (
            1.0
            + 0.40 * recheck_delta
            + 0.15 * uncertainty_penalty
            + 0.08 * distance_penalty
            + 0.08 * contact_penalty
        )
    ).clip(lower=0.05, upper=0.99)
    if backend in {"internal_gb_sa_v1", "internal_full_stack_v1"}:
        full_stack = backend == "internal_full_stack_v1"
        gb_rows: list[float] = []
        gb_conf: list[float] = []
        for idx in out.index:
            if not bool(selected_mask.loc[idx]):
                gb_rows.append(0.0)
                gb_conf.append(0.0)
                continue
            row_proxy = float(proxy_energy.loc[idx])
            adj = mm_gbsa_refinement_delta(
                base_proxy_kcal=row_proxy,
                mean_min_distance_a=float(mean_min_distance.loc[idx]),
                contact_fraction=float(contact_fraction.loc[idx]),
                stability_score=float(stability_score.loc[idx]),
            )
            delta_val = float(adj["refinement_delta_kcal_mol"])
            conf_val = float(adj["confidence"])
            if full_stack:
                # Tighten confidence and apply an explicit/FEP-style escalation factor on
                # shortlisted rows so the stronger-physics tier separates from GB/SA alone.
                escalation = 1.0 + 0.25 * max(0.0, float(mean_min_distance.loc[idx]) - 2.6)
                delta_val *= escalation
                conf_val = float(min(0.99, conf_val * 1.05))
            gb_rows.append(delta_val)
            gb_conf.append(conf_val)
        recheck_delta = pd.Series(gb_rows, index=out.index, dtype=float)
        confidence = pd.Series(gb_conf, index=out.index, dtype=float)
    refined_energy = proxy_energy_export.copy()
    refined_energy.loc[selected_mask] = (proxy_energy + recheck_delta).loc[selected_mask]

    refined_rank = proxy_energy_export.copy()
    refined_rank.loc[selected_mask] = (
        refined_energy
        + 0.20 * uncertainty_penalty
        + 0.10 * distance_penalty
        - 0.20 * contact_fraction
        - 0.15 * stability_score
    ).loc[selected_mask]

    selected_global_rank = pd.Series(np.nan, index=out.index, dtype=float)
    selected_target_rank = pd.Series(np.nan, index=out.index, dtype=float)
    if selected_idx:
        selected_order = (
            out.loc[selected_mask]
            .assign(_rank_score=refined_rank.loc[selected_mask], _input_score=input_score.loc[selected_mask])
            .sort_values(["_rank_score", "_input_score"], ascending=[True, bool(lower_better)], na_position="last")
        )
        selected_global_rank.loc[selected_order.index] = np.arange(1, len(selected_order) + 1, dtype=float)
        if target_col in out.columns:
            for _, part in selected_order.groupby(target_col, sort=False, dropna=False):
                selected_target_rank.loc[part.index] = np.arange(1, len(part) + 1, dtype=float)

    decision_bucket = pd.Series("carrythrough", index=out.index, dtype=object)
    if bool(selected_mask.any()):
        decision_bucket.loc[selected_mask] = _decision_bucket(
            recheck_delta.loc[selected_mask],
            confidence.loc[selected_mask],
        )

    decision_rows = [admission_decisions[int(index)] for index in out.index]
    out["pocketmd_upstream_topk_selected"] = [
        int(bool(row["upstream_topk_selected"])) for row in decision_rows
    ]
    out["pocketmd_authority_rank_global"] = [
        row.get("authority_rank_global") for row in decision_rows
    ]
    out["pocketmd_authority_rank_pct"] = [row.get("rank_pct") for row in decision_rows]
    out["pocketmd_admitted"] = [int(bool(row["admitted"])) for row in decision_rows]
    out["pocketmd_admission_reason"] = [str(row["primary_reason"]) for row in decision_rows]
    out["pocketmd_admission_reason_codes"] = [
        json.dumps(row["reason_codes"], separators=(",", ":"), ensure_ascii=False)
        for row in decision_rows
    ]
    out["pocketmd_admission_estimated_cost"] = [row.get("estimated_cost") for row in decision_rows]
    out["pocketmd_admission_cumulative_cost_before"] = [
        row.get("cumulative_cost_before") for row in decision_rows
    ]
    out["pocketmd_admission_cumulative_cost_after"] = [
        row.get("cumulative_cost_after") for row in decision_rows
    ]
    out["pocketmd_admission_cost_unit"] = admission_policy.cost_unit
    out["pocketmd_admission_policy_sha256"] = admission_policy.policy_sha256
    out["selection_score_authority_schema_version"] = (
        selection_score_authority.schema_version
    )
    out["selection_score_policy_sha256"] = selection_score_authority.policy_sha256
    out["physics_refinement_selected"] = selected_mask.astype(int)
    out["physics_refinement_shortlist_tier"] = np.where(selected_mask, "selected", "carrythrough")
    out["physics_refinement_lane_mode"] = str(args.refinement_mode)
    out["physics_refinement_backend"] = backend
    out["physics_refinement_input_score_col"] = score_col
    out["physics_refinement_input_score"] = input_score_export
    out[refined_energy_col] = refined_energy
    out[refined_rank_col] = refined_rank
    out["physics_refinement_delta_kcal_mol"] = np.where(selected_mask, recheck_delta, 0.0)
    out["physics_refinement_distance_penalty"] = np.where(selected_mask, distance_penalty, 0.0)
    out["physics_refinement_contact_penalty"] = np.where(selected_mask, contact_penalty, 0.0)
    out["physics_refinement_stability_penalty"] = np.where(selected_mask, stability_penalty, 0.0)
    out["physics_refinement_uncertainty_penalty"] = np.where(selected_mask, uncertainty_penalty, 0.0)
    out["physics_refinement_support_bonus"] = np.where(selected_mask, support_bonus, 0.0)
    out["physics_refinement_low_frame_penalty"] = np.where(selected_mask, low_frame_penalty, 0.0)
    out["physics_refinement_confidence"] = np.where(selected_mask, confidence, 0.0)
    out["physics_refinement_decision_bucket"] = decision_bucket
    out["physics_refinement_shortlist_rank_global"] = selected_global_rank
    out["physics_refinement_shortlist_rank_target"] = selected_target_rank

    shortlist_df = out.loc[selected_mask].copy()
    if not shortlist_df.empty:
        shortlist_df = shortlist_df.sort_values(
            [refined_rank_col, refined_energy_col, "physics_refinement_shortlist_rank_global"],
            ascending=[True, True, True],
            na_position="last",
        ).reset_index(drop=True)

    out_csv = str(args.out_csv).strip() or f"{os.path.splitext(scores_csv)[0]}_physics_refinement.csv"
    out_json = str(args.out_json).strip() or f"{os.path.splitext(out_csv)[0]}_summary.json"
    out_md = str(args.out_md).strip() or f"{os.path.splitext(out_csv)[0]}_summary.md"
    out_shortlist_csv = str(args.out_shortlist_csv).strip() or f"{os.path.splitext(out_csv)[0]}_shortlist.csv"
    out_shortlist_json = str(args.out_shortlist_json).strip() or f"{os.path.splitext(out_csv)[0]}_shortlist.json"

    _ensure_parent(out_csv)
    out.to_csv(out_csv, index=False)
    _ensure_parent(out_shortlist_csv)
    shortlist_df.to_csv(out_shortlist_csv, index=False)

    selected_target_counts: Dict[str, int] = {}
    if (target_col in shortlist_df.columns) and (not shortlist_df.empty):
        selected_target_counts = {
            _text(k): int(v)
            for k, v in shortlist_df[target_col].fillna("").astype(str).value_counts().sort_index().items()
        }

    selected_preview: List[Dict[str, Any]] = []
    preview_cols = [
        c
        for c in [
            target_col,
            ligand_col,
            refined_rank_col,
            refined_energy_col,
            "physics_refinement_delta_kcal_mol",
            "physics_refinement_confidence",
            "physics_refinement_decision_bucket",
            "pocketmd_authority_rank_global",
            "pocketmd_authority_rank_pct",
            "pocketmd_admission_estimated_cost",
            "pocketmd_admission_reason",
        ]
        if c in shortlist_df.columns
    ]
    if preview_cols:
        selected_preview = shortlist_df[preview_cols].head(20).to_dict(orient="records")

    selected_count = int(selected_mask.sum())
    if selected_count != admitted_count:
        raise RuntimeError("PocketMD admission count mismatch")
    admission_reason_counts: Dict[str, int] = {}
    for decision in admission_decisions.values():
        if not decision["admitted"]:
            for reason in decision["reason_codes"]:
                admission_reason_counts[reason] = admission_reason_counts.get(reason, 0) + 1
    summary = {
        "generated_at_local": generated_at,
        "pass": True,
        "refinement_enabled": True,
        "refinement_schema_version": "ligand_physics_refinement_v2",
        "refinement_mode": str(args.refinement_mode),
        "refinement_backend": backend,
        "refinement_backend_requested": backend_requested,
        "scores_csv_in": scores_csv,
        "scores_csv_in_sha256": _sha256_file(scores_csv),
        "scores_csv_out": out_csv,
        "scores_csv_out_sha256": _sha256_file(out_csv),
        "selection_authority_summary_json": authority_summary_json,
        "selection_authority_summary_sha256": _sha256_file(
            authority_summary_json
        ),
        "selection_score_authority": selection_score_authority.to_dict(),
        "pocketmd_admission_policy": admission_policy.to_dict(),
        "implementation_source_manifest": implementation_manifest,
        "implementation_fingerprint_sha256": implementation_fingerprint,
        "score_col_used": score_col,
        "base_proxy_col_used": base_proxy_col,
        "refined_energy_col": refined_energy_col,
        "refined_rank_col": refined_rank_col,
        "lower_better": bool(lower_better),
        "selection_mode": selection_mode,
        "topk_global_requested": int(max(0, int(args.topk_global))),
        "topk_per_target_requested": int(max(0, int(args.topk_per_target))),
        "row_count": int(len(out)),
        "selected_count": selected_count,
        "selected_fraction": float(selected_count / max(len(out), 1)),
        "selected_target_count": int(len(selected_target_counts)),
        "selected_target_counts": selected_target_counts,
        "upstream_topk_selected_count": int(len(upstream_selected_indices)),
        "authority_score_eligible_count": int(
            validated_admission["authority_eligible_count"]
        ),
        "authority_score_ineligible_count": int(
            len(df) - validated_admission["authority_eligible_count"]
        ),
        "admission_population_sha256": validated_admission[
            "population_sha256"
        ],
        "admission_cost_used": float(cumulative_admitted_cost),
        "admission_cost_remaining": float(
            admission_policy.cost_budget - cumulative_admitted_cost
        ),
        "admission_reason_counts": admission_reason_counts,
        "selected_decision_bucket_counts": (
            {
                _text(k): int(v)
                for k, v in shortlist_df["physics_refinement_decision_bucket"].value_counts().sort_index().items()
            }
            if (not shortlist_df.empty)
            else {}
        ),
        "selected_preview": selected_preview,
        "selected_metrics": {
            "mean_refined_energy_kcal_mol": _safe_optional_float(shortlist_df[refined_energy_col].mean()) if not shortlist_df.empty else None,
            "mean_rank_score": _safe_optional_float(shortlist_df[refined_rank_col].mean()) if not shortlist_df.empty else None,
            "mean_delta_kcal_mol": _safe_optional_float(shortlist_df["physics_refinement_delta_kcal_mol"].mean()) if not shortlist_df.empty else None,
            "mean_confidence": _safe_optional_float(shortlist_df["physics_refinement_confidence"].mean()) if not shortlist_df.empty else None,
            "max_delta_kcal_mol": _safe_optional_float(shortlist_df["physics_refinement_delta_kcal_mol"].max()) if not shortlist_df.empty else None,
        },
        "artifacts": {
            "out_csv": out_csv,
            "out_json": out_json,
            "out_md": out_md,
            "shortlist_csv": out_shortlist_csv,
            "shortlist_csv_sha256": _sha256_file(out_shortlist_csv),
            "shortlist_json": out_shortlist_json,
        },
        "warnings": warnings,
    }

    shortlist_payload = {
        "generated_at_local": generated_at,
        "refinement_mode": summary["refinement_mode"],
        "refinement_backend": summary["refinement_backend"],
        "score_col_used": score_col,
        "selection_score_authority": selection_score_authority.to_dict(),
        "pocketmd_admission_policy": admission_policy.to_dict(),
        "implementation_source_manifest": implementation_manifest,
        "implementation_fingerprint_sha256": implementation_fingerprint,
        "refined_energy_col": refined_energy_col,
        "refined_rank_col": refined_rank_col,
        "selected_count": selected_count,
        "selected_preview": selected_preview,
        "rows": shortlist_df.to_dict(orient="records"),
    }

    _ensure_parent(out_shortlist_json)
    with open(out_shortlist_json, "w", encoding="utf-8") as f:
        json.dump(shortlist_payload, f, indent=2, ensure_ascii=False)
    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Ligand Physics Refinement",
        "",
        f"- generated_at_local: {generated_at}",
        f"- pass: {summary['pass']}",
        f"- refinement_schema_version: `{summary['refinement_schema_version']}`",
        f"- refinement_mode: `{summary['refinement_mode']}`",
        f"- refinement_backend: `{summary['refinement_backend']}`",
        f"- score_col_used: `{summary['score_col_used']}`",
        f"- selection_score_policy_sha256: `{selection_score_authority.policy_sha256}`",
        f"- pocketmd_admission_policy_sha256: `{admission_policy.policy_sha256}`",
        f"- implementation_fingerprint_sha256: `{implementation_fingerprint}`",
        f"- base_proxy_col_used: `{summary['base_proxy_col_used']}`",
        f"- refined_energy_col: `{summary['refined_energy_col']}`",
        f"- refined_rank_col: `{summary['refined_rank_col']}`",
        f"- row_count: {summary['row_count']}",
        f"- selected_count: {summary['selected_count']}",
        f"- selected_fraction: {summary['selected_fraction']}",
        f"- topk_global_requested: {summary['topk_global_requested']}",
        f"- topk_per_target_requested: {summary['topk_per_target_requested']}",
        f"- selection_mode: `{summary['selection_mode']}`",
        f"- admission_cost_used: {summary['admission_cost_used']} {admission_policy.cost_unit}",
        f"- admission_cost_remaining: {summary['admission_cost_remaining']} {admission_policy.cost_unit}",
        f"- shortlist_csv: `{out_shortlist_csv}`",
        f"- shortlist_json: `{out_shortlist_json}`",
    ]
    if summary["selected_target_counts"]:
        md_lines.extend(["", "## Selected Targets"])
        for target_id, count in summary["selected_target_counts"].items():
            md_lines.append(f"- {target_id or '(blank_target)'}: {count}")
    if selected_preview:
        md_lines.extend(["", "## Selected Preview"])
        for row in selected_preview[:10]:
            md_lines.append(
                "- "
                + ", ".join(
                    f"{key}={row.get(key)}"
                    for key in row.keys()
                )
            )
    if warnings:
        md_lines.extend(["", "## Warnings"])
        for warning in warnings:
            md_lines.append(f"- {warning}")
    _ensure_parent(out_md)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run a lightweight post-stage3 ligand physics refinement lane that annotates shortlisted "
            "candidates with explicit-water or stronger-physics recheck proxy metrics."
        )
    )
    p.add_argument("--scores-csv", type=str, required=True)
    p.add_argument("--selection-authority-summary-json", type=str, required=True)
    p.add_argument("--score-col", type=str, default="")
    p.add_argument("--base-proxy-col", type=str, default="binding_energy_mmpbsa_kcal_mol_proxy")
    p.add_argument("--target-col", type=str, default="target")
    p.add_argument("--ligand-col", type=str, default="ligand_id")
    p.add_argument("--family-col", type=str, default="family")
    p.add_argument("--topk-global", type=int, default=32)
    p.add_argument("--topk-per-target", type=int, default=8)
    p.add_argument("--selection-mode", type=str, default="union", choices=["union", "intersection"])
    p.add_argument("--admission-eligible-families", type=str, default="gpcr,kinase,ion_channel")
    p.add_argument("--admission-rank-threshold-pct", type=float, default=0.05)
    p.add_argument("--admission-max-per-target", type=int, default=8)
    p.add_argument("--admission-max-per-job", type=int, default=32)
    p.add_argument("--admission-cost-budget", type=float, default=32.0)
    p.add_argument("--admission-unit-cost", type=float, default=1.0)
    p.add_argument("--admission-cost-unit", type=str, default="normalized_refinement_unit")
    p.add_argument("--admission-cost-col", type=str, default="")
    p.add_argument("--refinement-mode", type=str, default="explicit_water_surrogate")
    p.add_argument("--backend", type=str, default="deterministic_surrogate_wrapper_v1",
                   choices=sorted(_REFINEMENT_BACKEND_ALIASES),
                   help="Refinement backend: deterministic_surrogate_wrapper_v1 | internal_gb_sa_v1 | internal_full_stack_v1")
    p.add_argument(
        "--refined-energy-col",
        type=str,
        default="binding_energy_explicit_water_recheck_kcal_mol_proxy",
    )
    p.add_argument("--refined-rank-col", type=str, default="binding_score_stronger_physics_v1")
    p.add_argument("--out-csv", type=str, default="")
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    p.add_argument("--out-shortlist-csv", type=str, default="")
    p.add_argument("--out-shortlist-json", type=str, default="")
    return p


def main() -> None:
    args = build_parser().parse_args()
    summary = run_refinement(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
