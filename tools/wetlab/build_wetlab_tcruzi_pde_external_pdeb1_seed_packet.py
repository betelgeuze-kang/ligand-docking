#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_TBRUCEI_RAW_JSONS = [
    "runs/life_science_external/chembl_tbrucei_pdeb1_activities_raw.json",
    "runs/life_science_external/chembl_tbrucei_pdeb1_activities_raw_offset100.json",
    "runs/life_science_external/chembl_tbrucei_pdeb1_activities_raw_offset200.json",
]
DEFAULT_LMAJOR_RAW_JSONS = [
    "runs/life_science_external/chembl_lmajor_pdeb1_activities_raw.json",
]
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_external_pdeb1_seed_packet_current.md"
DEFAULT_TOP_N = 48


def _text(value: Any) -> str:
    return "" if value in {"", None} else str(value).strip()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _read_activities(paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path_like in paths:
        path = Path(path_like)
        if not path.exists() or path.is_dir():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        activities = payload.get("activities", payload if isinstance(payload, list) else [])
        if not isinstance(activities, list):
            continue
        for activity in activities:
            if isinstance(activity, dict):
                row = dict(activity)
                row["_source_raw_json"] = path.as_posix()
                rows.append(row)
    return rows


def _fallback_descriptors(smiles: str) -> dict[str, Any]:
    heavyish = max(50.0, min(1200.0, len(smiles) * 7.5))
    return {
        "molecular_weight": round(heavyish, 3),
        "logp": round(min(max((len(smiles) / 20.0) - 0.5, -2.0), 8.0), 3),
        "h_donors": 0,
        "h_acceptors": 0,
        "rot_bonds": max(len(smiles) // 14, 0),
    }


def _descriptors(smiles: str) -> dict[str, Any]:
    try:
        from rdkit import Chem  # type: ignore
        from rdkit.Chem import Crippen, Descriptors, Lipinski  # type: ignore

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return _fallback_descriptors(smiles)
        return {
            "molecular_weight": round(float(Descriptors.MolWt(mol)), 3),
            "logp": round(float(Crippen.MolLogP(mol)), 3),
            "h_donors": int(Lipinski.NumHDonors(mol)),
            "h_acceptors": int(Lipinski.NumHAcceptors(mol)),
            "rot_bonds": int(Lipinski.NumRotatableBonds(mol)),
        }
    except Exception:
        return _fallback_descriptors(smiles)


def _is_quantitative_activity(row: dict[str, Any]) -> bool:
    if _text(row.get("standard_relation")) not in {"=", "<", "<="}:
        return False
    if _text(row.get("standard_units")).lower() != "nm":
        return False
    if _safe_float(row.get("standard_value")) is None:
        return False
    if _text(row.get("canonical_smiles")) == "":
        return False
    if _text(row.get("data_validity_comment")):
        return False
    return True


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not _is_quantitative_activity(row):
            continue
        molecule_id = _text(row.get("molecule_chembl_id"))
        smiles = _text(row.get("canonical_smiles"))
        if not molecule_id or not smiles:
            continue
        potency_nM = _safe_float(row.get("standard_value"))
        pchembl = _safe_float(row.get("pchembl_value"))
        if potency_nM is None:
            continue
        current = grouped.setdefault(
            molecule_id,
            {
                "molecule_chembl_id": molecule_id,
                "compound_name": _text(row.get("molecule_pref_name")) or molecule_id,
                "smiles": smiles,
                "target_chembl_ids": set(),
                "target_organisms": set(),
                "target_pref_names": set(),
                "document_chembl_ids": set(),
                "assay_chembl_ids": set(),
                "standard_types": set(),
                "activity_count": 0,
                "min_standard_value_nM": potency_nM,
                "max_pchembl_value": pchembl,
                "best_assay_description": _text(row.get("assay_description")),
                "best_document_year": row.get("document_year"),
                "best_source_raw_json": _text(row.get("_source_raw_json")),
            },
        )
        current["activity_count"] += 1
        current["target_chembl_ids"].add(_text(row.get("target_chembl_id")))
        current["target_organisms"].add(_text(row.get("target_organism")))
        current["target_pref_names"].add(_text(row.get("target_pref_name")))
        current["document_chembl_ids"].add(_text(row.get("document_chembl_id")))
        current["assay_chembl_ids"].add(_text(row.get("assay_chembl_id")))
        current["standard_types"].add(_text(row.get("standard_type")))
        if potency_nM < float(current["min_standard_value_nM"]):
            current["min_standard_value_nM"] = potency_nM
            current["best_assay_description"] = _text(row.get("assay_description"))
            current["best_document_year"] = row.get("document_year")
            current["best_source_raw_json"] = _text(row.get("_source_raw_json"))
        if pchembl is not None:
            prev = current.get("max_pchembl_value")
            current["max_pchembl_value"] = pchembl if prev is None else max(float(prev), pchembl)

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(
        sorted(
            grouped.values(),
            key=lambda row: (
                float(row["min_standard_value_nM"]),
                -float(row.get("max_pchembl_value") or 0.0),
                _text(row.get("molecule_chembl_id")),
            ),
        ),
        start=1,
    ):
        desc = _descriptors(_text(item.get("smiles")))
        out.append(
            {
                "row_kind": "tcruzi_pde_external_pdeb1_homolog_seed",
                "priority_rank": idx,
                "ligand_id": f"tcruzi_pde_external_pdeb1_{idx:03d}_{_text(item.get('molecule_chembl_id')).lower()}",
                "compound_name": _text(item.get("compound_name")),
                "smiles": _text(item.get("smiles")),
                **desc,
                "source_dataset": "ChEMBL",
                "source_anchor": "TbrPDEB1/LmjPDEB1 homolog activity",
                "source_url": "https://www.ebi.ac.uk/chembl/",
                "molecule_chembl_id": _text(item.get("molecule_chembl_id")),
                "activity_count": int(item.get("activity_count", 0)),
                "min_standard_value_nM": round(float(item["min_standard_value_nM"]), 4),
                "max_pchembl_value": (
                    None if item.get("max_pchembl_value") is None else round(float(item["max_pchembl_value"]), 4)
                ),
                "target_chembl_ids": ";".join(sorted(v for v in item["target_chembl_ids"] if v)),
                "target_organisms": ";".join(sorted(v for v in item["target_organisms"] if v)),
                "target_pref_names": ";".join(sorted(v for v in item["target_pref_names"] if v)),
                "document_chembl_ids": ";".join(sorted(v for v in item["document_chembl_ids"] if v)),
                "assay_chembl_ids": ";".join(sorted(v for v in item["assay_chembl_ids"] if v)),
                "standard_types": ";".join(sorted(v for v in item["standard_types"] if v)),
                "best_document_year": item.get("best_document_year"),
                "best_assay_description": _text(item.get("best_assay_description")),
                "best_source_raw_json": _text(item.get("best_source_raw_json")),
                "direct_tcruzi_pde_evidence": False,
                "homolog_seed_only": True,
                "claim_policy": "seed_for_candidate_pool_expansion_not_direct_tcruzi_pde_claim",
            }
        )
    return out


def build_payload(
    *,
    tbrucei_raw_jsons: list[str] | None = None,
    lmajor_raw_jsons: list[str] | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    tbrucei_rows = _read_activities(list(tbrucei_raw_jsons or DEFAULT_TBRUCEI_RAW_JSONS))
    lmajor_rows = _read_activities(list(lmajor_raw_jsons or DEFAULT_LMAJOR_RAW_JSONS))
    rows = _aggregate([*tbrucei_rows, *lmajor_rows])[: max(1, int(top_n))]
    focus = rows[0] if rows else {}
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_external_pdeb1_seed_packet_ready" if rows else "blocked_no_external_pdeb1_seeds",
            "target_id": "T. cruzi PDE",
            "evidence_scope": "homolog_pdeb1_seed_only",
            "claim_promotion_allowed": False,
            "direct_tcruzi_pde_evidence_count": 0,
            "raw_activity_count": len(tbrucei_rows) + len(lmajor_rows),
            "quantitative_seed_count": len(rows),
            "top_n": max(1, int(top_n)),
            "top_seed_ligand_id": _text(focus.get("ligand_id")),
            "top_seed_molecule_chembl_id": _text(focus.get("molecule_chembl_id")),
            "top_seed_min_standard_value_nM": focus.get("min_standard_value_nM"),
            "top_seed_max_pchembl_value": focus.get("max_pchembl_value"),
            "top_seed_target_organisms": _text(focus.get("target_organisms")),
            "ligand_csv": DEFAULT_OUT_MD.replace(".md", ".csv"),
            "next_required_step": (
                "Use this homolog PDEB1 seed CSV for a strictly labeled candidate-pool expansion run; do not treat it as direct T. cruzi PDE evidence."
                if rows
                else "Query or curate additional PDEB1/PDE inhibitor sources before attempting candidate-pool expansion."
            ),
        },
        "structured": {
            "chembl_tbrucei_raw_jsons": list(tbrucei_raw_jsons or DEFAULT_TBRUCEI_RAW_JSONS),
            "chembl_lmajor_raw_jsons": list(lmajor_raw_jsons or DEFAULT_LMAJOR_RAW_JSONS),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a claim-safe external PDEB1 homolog seed packet for T. cruzi PDE candidate expansion.")
    parser.add_argument("--tbrucei-raw-json", action="append", default=None)
    parser.add_argument("--lmajor-raw-json", action="append", default=None)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        tbrucei_raw_jsons=args.tbrucei_raw_json,
        lmajor_raw_jsons=args.lmajor_raw_json,
        top_n=max(1, int(args.top_n)),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE External PDEB1 Seed Packet", payload)


if __name__ == "__main__":
    main()
