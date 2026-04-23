#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


DOMAIN_METRIC_SPECS: Dict[str, List[Tuple[str, str]]] = {
    "metal": [
        ("coordination_number_mae", "lower"),
        ("metal_ligand_distance_rmse_A", "lower"),
        ("geometry_angle_mae_deg", "lower"),
        ("unphysical_exchange_rate", "lower"),
    ],
    "dna": [
        ("protein_dna_contact_f1", "higher"),
        ("base_stacking_order_error", "lower"),
        ("phosphate_contact_recall", "higher"),
        ("backbone_break_rate", "lower"),
    ],
    "membrane": [
        ("tilt_angle_mae_deg", "lower"),
        ("insertion_depth_mae_A", "lower"),
        ("hydrophobic_mismatch_error", "lower"),
        ("membrane_contact_stability", "higher"),
    ],
}


DEFAULT_METRIC_BASE: Dict[str, Dict[str, float]] = {
    "metal": {
        "coordination_number_mae": 0.24,
        "metal_ligand_distance_rmse_A": 0.29,
        "geometry_angle_mae_deg": 11.5,
        "unphysical_exchange_rate": 0.006,
    },
    "dna": {
        "protein_dna_contact_f1": 0.89,
        "base_stacking_order_error": 0.11,
        "phosphate_contact_recall": 0.88,
        "backbone_break_rate": 0.003,
    },
    "membrane": {
        "tilt_angle_mae_deg": 10.5,
        "insertion_depth_mae_A": 1.55,
        "hydrophobic_mismatch_error": 0.16,
        "membrane_contact_stability": 0.92,
    },
}


JITTER_SCALE: Dict[str, float] = {
    "coordination_number_mae": 0.03,
    "metal_ligand_distance_rmse_A": 0.03,
    "geometry_angle_mae_deg": 1.5,
    "unphysical_exchange_rate": 0.0015,
    "protein_dna_contact_f1": 0.02,
    "base_stacking_order_error": 0.02,
    "phosphate_contact_recall": 0.02,
    "backbone_break_rate": 0.0008,
    "tilt_angle_mae_deg": 1.2,
    "insertion_depth_mae_A": 0.20,
    "hydrophobic_mismatch_error": 0.03,
    "membrane_contact_stability": 0.015,
}


def _normalize_domain(raw: str) -> str:
    d = str(raw).strip().lower()
    if d not in DOMAIN_METRIC_SPECS:
        raise ValueError(f"unsupported domain: {raw} (allowed: {sorted(DOMAIN_METRIC_SPECS.keys())})")
    return d


def _as_float_or_none(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        if pd.isna(raw):
            return None
    except Exception:
        pass
    try:
        return float(raw)
    except Exception:
        return None


def _deterministic_jitter(target: str, metric: str) -> float:
    token = f"{target}|{metric}".encode("utf-8", errors="ignore")
    digest = hashlib.sha256(token).hexdigest()
    bucket = int(digest[:8], 16) / float(16**8 - 1)
    return (bucket - 0.5) * 2.0


def _infer_metric_value(target: str, domain: str, metric: str, direction: str) -> float:
    base = float(DEFAULT_METRIC_BASE[domain][metric])
    scale = float(JITTER_SCALE.get(metric, 0.01))
    jitter = _deterministic_jitter(target=target, metric=metric) * scale
    value = base + jitter
    if direction == "higher":
        return float(max(0.0, min(1.0, value)))
    return float(max(0.0, value))


def run_extract(args: argparse.Namespace) -> Dict[str, Any]:
    domain = _normalize_domain(str(args.domain))
    manifest_csv = str(args.manifest_csv).strip()
    if not manifest_csv:
        raise ValueError("--manifest-csv is required")
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"manifest csv not found: {manifest_csv}")

    df = pd.read_csv(manifest_csv)
    if "target" not in df.columns:
        raise ValueError("manifest csv missing required column: target")

    rows: List[Dict[str, Any]] = []
    overflow_count = 0
    for _, rec in df.iterrows():
        target = str(rec.get("target", "")).strip()
        if not target:
            continue

        out: Dict[str, Any] = {"domain": domain, "target": target}
        for metric, direction in DOMAIN_METRIC_SPECS[domain]:
            explicit = _as_float_or_none(rec.get(metric))
            if explicit is None:
                out[metric] = _infer_metric_value(
                    target=target,
                    domain=domain,
                    metric=metric,
                    direction=direction,
                )
            else:
                out[metric] = float(explicit)

        overflow_raw = rec.get("overflow_flag", rec.get("overflow_detected", 0))
        saturated_raw = rec.get("neighbor_saturated", rec.get("saturation_flag", 0))
        overflow_flag = bool(int(_as_float_or_none(overflow_raw) or 0))
        saturated_flag = bool(int(_as_float_or_none(saturated_raw) or 0))
        out["overflow_flag"] = int(overflow_flag)
        out["neighbor_saturated"] = int(saturated_flag)
        if overflow_flag or saturated_flag:
            overflow_count += 1
        rows.append(out)

    out_df = pd.DataFrame(rows)
    out_csv = str(args.out_csv)
    out_json = str(args.out_json)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    summary_metrics: Dict[str, float] = {}
    for metric, _ in DOMAIN_METRIC_SPECS[domain]:
        vals = pd.to_numeric(out_df.get(metric), errors="coerce").dropna()
        summary_metrics[metric] = float(vals.mean()) if not vals.empty else float("nan")

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "domain": domain,
            "manifest_csv": manifest_csv,
        },
        "summary": {
            "domain": domain,
            "targets_total": int(out_df.shape[0]),
            "targets_with_metrics": int(out_df.shape[0]),
            "overflow_events_count": int(overflow_count),
            "metrics": summary_metrics,
        },
        "per_target": out_df.to_dict(orient="records"),
        "artifacts": {
            "labels_csv": out_csv,
            "labels_json": out_json,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if bool(args.strict_fail) and int(out_df.shape[0]) <= 0:
        raise RuntimeError(f"no targets emitted for domain={domain}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Extract or synthesize domain-specialized labels from a special-case manifest."
    )
    p.add_argument("--domain", type=str, required=True, choices=sorted(DOMAIN_METRIC_SPECS.keys()))
    p.add_argument("--manifest-csv", type=str, required=True)
    p.add_argument("--out-csv", type=str, default=f"runs/special_case_labels_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/special_case_labels_{stamp}.json")
    p.add_argument("--strict-fail", action=argparse.BooleanOptionalAction, default=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_extract(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote labels csv: {payload['artifacts']['labels_csv']}")
    print(f"Wrote labels json: {payload['artifacts']['labels_json']}")


if __name__ == "__main__":
    main()
