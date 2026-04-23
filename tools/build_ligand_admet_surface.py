#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

try:
    from rdkit import Chem  # type: ignore
    from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors  # type: ignore
except Exception:  # pragma: no cover
    Chem = None
    Crippen = None
    Descriptors = None
    Lipinski = None
    QED = None
    rdMolDescriptors = None

ROOT = Path(__file__).resolve().parents[1]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _safe_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        out = float(value)
        if math.isnan(out):
            return None
        return out
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value in {"", None}:
            return None
        return int(float(value))
    except Exception:
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round_or_blank(value: float | None, digits: int = 3) -> float | str:
    return round(value, digits) if value is not None else ""


def _weighted_mean(items: list[tuple[float | None, float]], *, missing: float = 0.5) -> float:
    total = 0.0
    weight_total = 0.0
    for value, weight in items:
        total += (missing if value is None else value) * weight
        weight_total += weight
    if weight_total <= 0:
        return missing
    return total / weight_total


def _window_score(
    value: float | None,
    *,
    ideal_low: float,
    ideal_high: float,
    floor_low: float | None = None,
    ceil_high: float | None = None,
    missing: float = 0.55,
) -> float:
    if value is None:
        return missing
    low_bound = ideal_low if floor_low is None else floor_low
    high_bound = ideal_high if ceil_high is None else ceil_high
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < low_bound or value > high_bound:
        return 0.0
    if value < ideal_low:
        width = ideal_low - low_bound
        return 0.0 if width <= 0 else _clamp((value - low_bound) / width)
    width = high_bound - ideal_high
    return 0.0 if width <= 0 else _clamp((high_bound - value) / width)


def _low_good_score(
    value: float | None,
    *,
    good_max: float,
    bad_max: float,
    missing: float = 0.55,
) -> float:
    if value is None:
        return missing
    if value <= good_max:
        return 1.0
    if value >= bad_max:
        return 0.0
    width = bad_max - good_max
    return 0.0 if width <= 0 else _clamp((bad_max - value) / width)


def _high_risk_score(
    value: float | None,
    *,
    warn: float,
    high: float,
    missing: float = 0.45,
) -> float:
    if value is None:
        return missing
    if value <= warn:
        return 0.0
    if value >= high:
        return 1.0
    width = high - warn
    return 1.0 if width <= 0 else _clamp((value - warn) / width)


def _risk_bucket(score: float) -> str:
    if score >= 65.0:
        return "high"
    if score >= 35.0:
        return "moderate"
    return "low"


def _permeability_bucket(score: float) -> str:
    if score >= 70.0:
        return "favorable"
    if score >= 45.0:
        return "borderline"
    return "restricted"


def _enrich_descriptor_bundle(row: dict[str, Any]) -> dict[str, Any]:
    smiles = str(row.get("smiles", "") or "").strip()
    mw = _safe_float(row.get("molecular_weight"))
    logp = _safe_float(row.get("logp"))
    h_don = _safe_int(row.get("h_donors"))
    h_acc = _safe_int(row.get("h_acceptors"))
    rot = _safe_int(row.get("rot_bonds"))
    tpsa = _safe_float(row.get("tpsa"))
    qed = _safe_float(row.get("qed"))
    if smiles and Chem is not None:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            if mw is None and Descriptors is not None:
                mw = float(Descriptors.MolWt(mol))
            if logp is None and Crippen is not None:
                logp = float(Crippen.MolLogP(mol))
            if h_don is None and Lipinski is not None:
                h_don = int(Lipinski.NumHDonors(mol))
            if h_acc is None and Lipinski is not None:
                h_acc = int(Lipinski.NumHAcceptors(mol))
            if rot is None and Lipinski is not None:
                rot = int(Lipinski.NumRotatableBonds(mol))
            if tpsa is None and rdMolDescriptors is not None:
                tpsa = float(rdMolDescriptors.CalcTPSA(mol))
            if qed is None and QED is not None:
                qed = float(QED.qed(mol))
    row["molecular_weight"] = _round_or_blank(mw)
    row["logp"] = _round_or_blank(logp)
    row["h_donors"] = h_don if h_don is not None else ""
    row["h_acceptors"] = h_acc if h_acc is not None else ""
    row["rot_bonds"] = rot if rot is not None else ""
    row["tpsa"] = _round_or_blank(tpsa)
    row["qed"] = _round_or_blank(qed)
    return row


def rule_based_admet_bucket(row: dict[str, Any]) -> tuple[str, int, str]:
    mw = _safe_float(row.get("molecular_weight"))
    logp = _safe_float(row.get("logp"))
    h_don = _safe_int(row.get("h_donors"))
    h_acc = _safe_int(row.get("h_acceptors"))
    rot = _safe_int(row.get("rot_bonds"))
    tpsa = _safe_float(row.get("tpsa"))
    violations = 0
    flags: list[str] = []
    if mw is not None and mw > 500:
        violations += 1
        flags.append("high_mw")
    if logp is not None and logp > 5:
        violations += 1
        flags.append("high_logp")
    if h_don is not None and h_don > 5:
        violations += 1
        flags.append("high_h_donor_count")
    if h_acc is not None and h_acc > 10:
        violations += 1
        flags.append("high_h_acceptor_count")
    if rot is not None and rot > 10:
        flags.append("high_flexibility")
    if tpsa is not None and tpsa > 140:
        flags.append("high_polar_surface_area")
    if violations == 0 and "high_flexibility" not in flags and "high_polar_surface_area" not in flags:
        return "green", 0, "; ".join(flags)
    if violations <= 1:
        return "yellow", violations, "; ".join(flags)
    return "red", violations, "; ".join(flags)


def descriptor_based_predictive_prior(descriptors: dict[str, Any]) -> dict[str, Any]:
    mw = _safe_float(descriptors.get("molecular_weight"))
    logp = _safe_float(descriptors.get("logp"))
    h_don = _safe_float(descriptors.get("h_donors"))
    h_acc = _safe_float(descriptors.get("h_acceptors"))
    rot = _safe_float(descriptors.get("rot_bonds"))
    tpsa = _safe_float(descriptors.get("tpsa"))
    raw_qed = _safe_float(descriptors.get("qed"))

    mw_drug = _window_score(mw, ideal_low=180.0, ideal_high=450.0, floor_low=120.0, ceil_high=650.0)
    logp_drug = _window_score(logp, ideal_low=1.0, ideal_high=3.5, floor_low=-0.5, ceil_high=5.5)
    tpsa_drug = _window_score(tpsa, ideal_low=20.0, ideal_high=90.0, floor_low=0.0, ceil_high=150.0)
    hbd_drug = _low_good_score(h_don, good_max=3.0, bad_max=6.0, missing=0.6)
    hba_drug = _window_score(h_acc, ideal_low=1.0, ideal_high=8.0, floor_low=0.0, ceil_high=12.0, missing=0.6)
    rot_drug = _low_good_score(rot, good_max=6.0, bad_max=12.0)
    qed_prior = _clamp(raw_qed) if raw_qed is not None else _weighted_mean(
        [
            (mw_drug, 0.2),
            (logp_drug, 0.2),
            (tpsa_drug, 0.2),
            (hbd_drug, 0.15),
            (hba_drug, 0.15),
            (rot_drug, 0.1),
        ],
        missing=0.55,
    )

    permeability_score = 100.0 * _weighted_mean(
        [
            (logp_drug, 0.25),
            (mw_drug, 0.2),
            (tpsa_drug, 0.25),
            (hbd_drug, 0.1),
            (rot_drug, 0.1),
            (qed_prior, 0.1),
        ]
    )
    clearance_score = 100.0 * _weighted_mean(
        [
            (_high_risk_score(logp, warn=3.0, high=5.5), 0.35),
            (_high_risk_score(rot, warn=6.0, high=12.0), 0.25),
            (_high_risk_score(mw, warn=420.0, high=650.0), 0.15),
            (1.0 - qed_prior, 0.15),
            (_high_risk_score(h_acc, warn=6.0, high=11.0, missing=0.4), 0.1),
        ]
    )
    herg_score = 100.0 * _weighted_mean(
        [
            (_high_risk_score(logp, warn=2.8, high=5.5), 0.4),
            (_high_risk_score(mw, warn=320.0, high=600.0), 0.15),
            (_window_score(tpsa, ideal_low=15.0, ideal_high=85.0, floor_low=0.0, ceil_high=140.0, missing=0.5), 0.15),
            (_window_score(h_acc, ideal_low=2.0, ideal_high=8.0, floor_low=0.0, ceil_high=12.0, missing=0.5), 0.1),
            (permeability_score / 100.0, 0.2),
        ]
    )
    cyp3a4_score = 100.0 * _weighted_mean(
        [
            (_high_risk_score(logp, warn=2.8, high=5.5), 0.3),
            (_high_risk_score(mw, warn=350.0, high=650.0), 0.2),
            (_high_risk_score(rot, warn=6.0, high=12.0), 0.2),
            (_high_risk_score(h_acc, warn=5.0, high=10.0, missing=0.4), 0.1),
            (permeability_score / 100.0, 0.1),
            (1.0 - qed_prior, 0.1),
        ]
    )
    ames_score = 100.0 * _weighted_mean(
        [
            (1.0 - qed_prior, 0.4),
            (_high_risk_score(logp, warn=2.5, high=5.5), 0.25),
            (_high_risk_score(h_acc, warn=7.0, high=12.0, missing=0.4), 0.15),
            (_high_risk_score(h_don, warn=2.0, high=5.0, missing=0.35), 0.1),
            (_high_risk_score(rot, warn=8.0, high=14.0, missing=0.4), 0.1),
        ]
    )
    predictive_risk_score = 100.0 * _weighted_mean(
        [
            ((100.0 - permeability_score) / 100.0, 0.25),
            (clearance_score / 100.0, 0.2),
            (herg_score / 100.0, 0.2),
            (cyp3a4_score / 100.0, 0.2),
            (ames_score / 100.0, 0.15),
        ]
    )

    flags: list[str] = []
    permeability_bucket = _permeability_bucket(permeability_score)
    clearance_bucket = _risk_bucket(clearance_score)
    herg_bucket = _risk_bucket(herg_score)
    cyp3a4_bucket = _risk_bucket(cyp3a4_score)
    ames_bucket = _risk_bucket(ames_score)
    overall_bucket = _risk_bucket(predictive_risk_score)
    if permeability_bucket == "restricted":
        flags.append("restricted_permeability_prior")
    elif permeability_bucket == "borderline":
        flags.append("borderline_permeability_prior")
    if clearance_bucket == "high":
        flags.append("high_clearance_liability_prior")
    if herg_bucket == "high":
        flags.append("high_herg_like_prior")
    if cyp3a4_bucket == "high":
        flags.append("high_cyp3a4_like_prior")
    if ames_bucket == "high":
        flags.append("high_ames_like_prior")

    return {
        "predictive_prior_label": "descriptor_based_predictive_prior",
        "predictive_prior_method": "descriptor_based_predictive_prior_v1",
        "predictive_prior_note": "Descriptor-based predictive prior only. Not a trained model or validated endpoint predictor.",
        "predictive_qed_mode": "observed_qed" if raw_qed is not None else "descriptor_proxy",
        "predictive_qed_prior": _round_or_blank(qed_prior),
        "permeability": permeability_bucket,
        "permeability_score": round(permeability_score, 1),
        "clearance_liability": clearance_bucket,
        "clearance_liability_score": round(clearance_score, 1),
        "hERG_like_risk": herg_bucket,
        "hERG_like_risk_score": round(herg_score, 1),
        "CYP3A4_like_risk": cyp3a4_bucket,
        "CYP3A4_like_risk_score": round(cyp3a4_score, 1),
        "AMES_like_risk": ames_bucket,
        "AMES_like_risk_score": round(ames_score, 1),
        "predictive_risk_bucket": overall_bucket,
        "predictive_risk_score": round(predictive_risk_score, 1),
        "predictive_risk_signal": {"low": "green", "moderate": "yellow", "high": "red"}[overall_bucket],
        "predictive_liability_flags": "; ".join(flags),
    }


def build_payload(scores_csv: str) -> dict[str, Any]:
    frame = pd.read_csv(_resolve(scores_csv)).fillna("")
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        base = {
            "target_id": record.get("target", ""),
            "compound_id": record.get("ligand_id", ""),
            "compound_name": record.get("ligand_id", ""),
            "smiles": record.get("smiles", ""),
            "molecular_weight": record.get("ligand_mw", record.get("molecular_weight", "")),
            "logp": record.get("ligand_logp", record.get("logp", "")),
            "h_donors": record.get("ligand_h_donors", record.get("h_donors", "")),
            "h_acceptors": record.get("ligand_h_acceptors", record.get("h_acceptors", "")),
            "rot_bonds": record.get("ligand_rot_bonds", record.get("rot_bonds", "")),
            "tpsa": record.get("ligand_tpsa", record.get("tpsa", "")),
            "qed": record.get("ligand_qed", record.get("qed", "")),
            "onsps_norm": record.get("ligand_onsps_norm", record.get("onsps_norm", "")),
        }
        base = _enrich_descriptor_bundle(base)
        bucket, violations, flags = rule_based_admet_bucket(base)
        predictive = descriptor_based_predictive_prior(base)
        base["admet_bucket"] = bucket
        base["lipinski_violation_count"] = violations
        base["liability_flags"] = flags
        base["admet_note"] = "Rule-based ADMET sanity only. No hERG/CYP/AMES claim is made from this surface."
        base.update(predictive)
        rows.append(base)

    summary = {
        "status": "ligand_admet_surface_ready",
        "source_scores_csv": str(_resolve(scores_csv)),
        "compound_count": len(rows),
        "green_count": sum(1 for row in rows if row["admet_bucket"] == "green"),
        "yellow_count": sum(1 for row in rows if row["admet_bucket"] == "yellow"),
        "red_count": sum(1 for row in rows if row["admet_bucket"] == "red"),
        "predictive_prior_kind": "descriptor_based_predictive_prior",
        "predictive_low_count": sum(1 for row in rows if row.get("predictive_risk_bucket") == "low"),
        "predictive_moderate_count": sum(1 for row in rows if row.get("predictive_risk_bucket") == "moderate"),
        "predictive_high_count": sum(1 for row in rows if row.get("predictive_risk_bucket") == "high"),
        "predictive_mean_risk_score": round(
            sum(float(row.get("predictive_risk_score", 0.0) or 0.0) for row in rows) / len(rows),
            1,
        )
        if rows
        else 0.0,
    }
    structured = {
        "rule_set": "stage3/stage4 ligand priors with Lipinski/Veber-style heuristic buckets plus descriptor-based predictive prior scores.",
        "non_claim": "No trained ADMET endpoint prediction is claimed; endpoint-style fields are descriptor-based predictive priors only.",
        "predictive_prior": {
            "kind": "descriptor_based_predictive_prior",
            "formula_version": "descriptor_based_predictive_prior_v1",
            "score_scale": "0_to_100",
            "score_direction": {
                "permeability_score": "higher is more favorable",
                "clearance_liability_score": "higher is higher liability",
                "hERG_like_risk_score": "higher is higher descriptor-based prior risk",
                "CYP3A4_like_risk_score": "higher is higher descriptor-based prior risk",
                "AMES_like_risk_score": "higher is higher descriptor-based prior risk",
                "predictive_risk_score": "higher is higher aggregated descriptor-based prior risk",
            },
        },
    }
    return {"summary": summary, "structured": structured, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a rule-based ADMET surface directly from a scored CSV.")
    parser.add_argument("--scores-csv", required=True)
    parser.add_argument("--out-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.scores_csv)
    out_json = _resolve(args.out_json)
    out_csv = out_json.with_suffix(".csv")
    out_md = out_json.with_suffix(".md")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload.get("rows", []) or [])
    lines = [
        "# Ligand ADMET Surface",
        "",
        f"- status: `{payload['summary'].get('status', '')}`",
        f"- source_scores_csv: `{payload['summary'].get('source_scores_csv', '')}`",
        f"- compound_count: `{payload['summary'].get('compound_count', 0)}`",
        f"- green_count: `{payload['summary'].get('green_count', 0)}`",
        f"- yellow_count: `{payload['summary'].get('yellow_count', 0)}`",
        f"- red_count: `{payload['summary'].get('red_count', 0)}`",
        f"- predictive_prior_kind: `{payload['summary'].get('predictive_prior_kind', '')}`",
        f"- predictive_risk_bucket_summary: `{payload['summary'].get('predictive_low_count', 0)} low / {payload['summary'].get('predictive_moderate_count', 0)} moderate / {payload['summary'].get('predictive_high_count', 0)} high`",
        f"- predictive_mean_risk_score: `{payload['summary'].get('predictive_mean_risk_score', 0.0)}`",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
