#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows
from tools.build_ligand_admet_surface import descriptor_based_predictive_prior, rule_based_admet_bucket

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

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKET_INDEX_JSON = "runs/wetlab_cro_delivery_packet_index_current.json"
DEFAULT_OUT_JSON = "runs/ligand_admet_module_current.json"
DEFAULT_OUT_CSV = "runs/ligand_admet_module_current.csv"
DEFAULT_OUT_MD = "runs/ligand_admet_module_current.md"

SELECTIVITY_PANEL_BY_TARGET = {
    "EGFR_KINASE": "kinase_selectivity_minipanel_required",
    "ADRB2_GPCR_BLIND": "orthogonal_gpcr_functional_panel_required",
    "HIV1_PROTEASE": "host_protease_reactivity_panel_required",
    "TRPV1_ION_CHANNEL_BLIND": "channel_counterscreen_and_procurement_gate_required",
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    return json.loads(_resolve(path_like).read_text(encoding="utf-8"))


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


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


def _iter_meta_paths() -> list[Path]:
    paths = sorted(ROOT.glob("config/ligand_meta*.csv"))
    source_csv = ROOT / "docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv"
    if source_csv.exists():
        paths.append(source_csv)
    return paths


def _build_meta_lookup() -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in _iter_meta_paths():
        try:
            frame = pd.read_csv(path).fillna("")
        except Exception:
            continue
        for row in frame.to_dict(orient="records"):
            for key_col in ("ligand_id", "compound_id", "chembl_id", "normalized_name", "name"):
                key = _stringify(row.get(key_col, "")).lower()
                if key and key not in lookup:
                    lookup[key] = dict(row)
    return lookup


def _resolve_packet_jsons(packet_index_payload: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for row in packet_index_payload.get("rows", []) or []:
        packet_md = _stringify(row.get("packet_md", ""))
        if not packet_md:
            continue
        packet_json = _resolve(packet_md).with_suffix(".json")
        if packet_json.exists():
            paths.append(packet_json)
    return paths


def _lookup_source_row(meta_lookup: dict[str, dict[str, Any]], row: dict[str, Any]) -> dict[str, Any]:
    for key in (
        _stringify(row.get("compound_id", "")).lower(),
        _stringify(row.get("compound_name", "")).lower(),
        _stringify(row.get("chembl_id", "")).lower(),
    ):
        if key and key in meta_lookup:
            return dict(meta_lookup[key])
    return {}


def _descriptor_bundle(smiles: str, source_row: dict[str, Any]) -> dict[str, Any]:
    mw = _safe_float(source_row.get("molecular_weight"))
    logp = _safe_float(source_row.get("logp"))
    h_don = _safe_int(source_row.get("h_donors"))
    h_acc = _safe_int(source_row.get("h_acceptors"))
    rot = _safe_int(source_row.get("rot_bonds"))
    tpsa = _safe_float(source_row.get("tpsa"))
    qed = None
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
            if QED is not None:
                qed = float(QED.qed(mol))
    return {
        "molecular_weight": round(mw, 3) if mw is not None else "",
        "logp": round(logp, 3) if logp is not None else "",
        "h_donors": h_don if h_don is not None else "",
        "h_acceptors": h_acc if h_acc is not None else "",
        "rot_bonds": rot if rot is not None else "",
        "tpsa": round(tpsa, 3) if tpsa is not None else "",
        "qed": round(qed, 3) if qed is not None else "",
    }


def build_payload(packet_index_payload: dict[str, Any]) -> dict[str, Any]:
    meta_lookup = _build_meta_lookup()
    rows: list[dict[str, Any]] = []
    for packet_json in _resolve_packet_jsons(packet_index_payload):
        packet_payload = _load_json(str(packet_json))
        packet_summary = dict(packet_payload.get("summary", {}) or {})
        target_id = _stringify(packet_summary.get("target_id", ""))
        for row in packet_payload.get("rows", []) or []:
            source_row = _lookup_source_row(meta_lookup, row)
            smiles = _stringify(source_row.get("smiles", ""))
            descriptors = _descriptor_bundle(smiles, source_row)
            bucket, lipinski_violations, flags = rule_based_admet_bucket(descriptors)
            predictive = descriptor_based_predictive_prior(descriptors)
            rows.append(
                {
                    "target_id": target_id,
                    "packet_label": _stringify(packet_summary.get("packet_label", "")),
                    "compound_id": _stringify(row.get("compound_id", "")),
                    "compound_name": _stringify(row.get("compound_name", "")),
                    "expected_class": _stringify(row.get("expected_class", "")),
                    "smiles": smiles,
                    **descriptors,
                    "lipinski_violation_count": lipinski_violations,
                    "admet_bucket": bucket,
                    "liability_flags": flags,
                    "selectivity_companion_panel": SELECTIVITY_PANEL_BY_TARGET.get(target_id, "manual_selectivity_context_required"),
                    "admet_note": "Rule-based ADMET sanity only. No hERG/CYP/AMES claim is made from this surface.",
                    **predictive,
                }
            )

    target_summaries: list[dict[str, Any]] = []
    for target_id in sorted({row["target_id"] for row in rows}):
        target_rows = [row for row in rows if row["target_id"] == target_id]
        target_summaries.append(
            {
                "target_id": target_id,
                "compound_count": len(target_rows),
                "green_count": sum(1 for row in target_rows if row["admet_bucket"] == "green"),
                "yellow_count": sum(1 for row in target_rows if row["admet_bucket"] == "yellow"),
                "red_count": sum(1 for row in target_rows if row["admet_bucket"] == "red"),
                "predictive_low_count": sum(1 for row in target_rows if row.get("predictive_risk_bucket") == "low"),
                "predictive_moderate_count": sum(1 for row in target_rows if row.get("predictive_risk_bucket") == "moderate"),
                "predictive_high_count": sum(1 for row in target_rows if row.get("predictive_risk_bucket") == "high"),
                "predictive_mean_risk_score": round(
                    sum(float(row.get("predictive_risk_score", 0.0) or 0.0) for row in target_rows) / len(target_rows),
                    1,
                )
                if target_rows
                else 0.0,
            }
        )

    summary = {
        "status": "ligand_admet_module_ready",
        "target_count": len(target_summaries),
        "compound_count": len(rows),
        "green_count": sum(1 for row in rows if row["admet_bucket"] == "green"),
        "yellow_count": sum(1 for row in rows if row["admet_bucket"] == "yellow"),
        "red_count": sum(1 for row in rows if row["admet_bucket"] == "red"),
        "module_scope": "rule_based_minimal_independent_admet_selectivity_surface",
        "next_required_step": "Use this surface for first-pass liability triage only; the predictive layer is a descriptor-based prior, so add trained ADMET models before making development-grade claims.",
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
        "rule_set": "Lipinski + Veber-style heuristic with explicit selectivity-companion annotations plus descriptor-based predictive prior scores.",
        "non_claim": "No trained hERG, CYP, clearance, permeability, or mutagenicity prediction is claimed; endpoint-style fields are descriptor-based predictive priors only.",
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
        "target_summaries": target_summaries,
    }
    return {"summary": summary, "structured": structured, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Ligand ADMET Module",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- compound_count: `{summary['compound_count']}`",
        f"- green_count: `{summary['green_count']}`",
        f"- yellow_count: `{summary['yellow_count']}`",
        f"- red_count: `{summary['red_count']}`",
        f"- predictive_prior_kind: `{summary.get('predictive_prior_kind', '')}`",
        f"- predictive_risk_bucket_summary: `{summary.get('predictive_low_count', 0)} low / {summary.get('predictive_moderate_count', 0)} moderate / {summary.get('predictive_high_count', 0)} high`",
        f"- predictive_mean_risk_score: `{summary.get('predictive_mean_risk_score', 0.0)}`",
        "",
        "| target_id | compound_id | admet_bucket | predictive_risk_bucket | predictive_risk_score | lipinski_violation_count | logp | molecular_weight | tpsa | liability_flags |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []) or []:
        lines.append(
            f"| `{row['target_id']}` | `{row['compound_id']}` | `{row['admet_bucket']}` | `{row.get('predictive_risk_bucket', '')}` | `{row.get('predictive_risk_score', '')}` | `{row['lipinski_violation_count']}` | `{row['logp']}` | `{row['molecular_weight']}` | `{row['tpsa']}` | `{row['liability_flags']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a minimal independent ligand ADMET/selectivity surface from current CRO packets.")
    parser.add_argument("--packet-index-json", default=DEFAULT_PACKET_INDEX_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.packet_index_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload.get("rows", []) or [])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
