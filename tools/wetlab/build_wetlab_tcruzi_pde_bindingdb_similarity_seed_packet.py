#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_RAW_GLOB = "runs/life_science_external/bindingdb_similarity_tcruzi_pde_external_pdeb1_*_chembl*_raw.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_bindingdb_similarity_seed_packet_current.md"
DEFAULT_TOP_N = 32


def _text(value: Any) -> str:
    return "" if value in {"", None} else str(value).strip()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        text = str(value).strip()
        text = text.removeprefix("<").removeprefix(">").strip()
        return float(text)
    except Exception:
        return default


def _clean_smiles(smiles: str) -> str:
    clean = _text(smiles).split()[0] if _text(smiles) else ""
    if not clean:
        return ""
    try:
        from rdkit import Chem  # type: ignore

        mol = Chem.MolFromSmiles(clean)
        if mol is None:
            return clean
        return Chem.MolToSmiles(mol, canonical=True)
    except Exception:
        return clean


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


def _query_ligand_id_from_raw_path(path: Path) -> str:
    name = path.name.removesuffix("_raw.json")
    prefix = "bindingdb_similarity_"
    return name.removeprefix(prefix)


def _affinity_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("getLindsByUniprotResponse", {})
    if not isinstance(response, dict):
        return []
    affinities = response.get("bdb.affinities", [])
    if isinstance(affinities, dict):
        affinities = [affinities]
    if not isinstance(affinities, list):
        return []
    return [dict(item or {}) for item in affinities if isinstance(item, dict)]


def _read_raw_rows(paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path_like in paths:
        path = Path(path_like)
        if not path.exists() or path.is_dir():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        query_ligand_id = _query_ligand_id_from_raw_path(path)
        for row in _affinity_rows(payload):
            row["_source_raw_json"] = path.as_posix()
            row["_query_ligand_id"] = query_ligand_id
            rows.append(row)
    return rows


def _is_tbrucei_pde(row: dict[str, Any]) -> bool:
    species = _text(row.get("bdb.species")).lower()
    target = _text(row.get("bdb.target")).lower()
    return "trypanosoma brucei" in species and "phosphodiesterase" in target


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        monomer_id = _text(row.get("bdb.monomerid"))
        smiles = _clean_smiles(_text(row.get("bdb.smiles")))
        if not monomer_id or not smiles:
            continue
        potency = _safe_float(row.get("bdb.affinity"))
        current = grouped.setdefault(
            monomer_id,
            {
                "bindingdb_monomer_id": monomer_id,
                "smiles": smiles,
                "activity_count": 0,
                "best_affinity_nM": potency,
                "best_affinity_type": _text(row.get("bdb.affinity_type")),
                "query_ligand_ids": set(),
                "source_raw_jsons": set(),
                "species": set(),
                "targets": set(),
                "affinity_types": set(),
                "tbrucei_pde_activity_count": 0,
            },
        )
        current["activity_count"] += 1
        current["query_ligand_ids"].add(_text(row.get("_query_ligand_id")))
        current["source_raw_jsons"].add(_text(row.get("_source_raw_json")))
        current["species"].add(_text(row.get("bdb.species")))
        current["targets"].add(_text(row.get("bdb.target")))
        current["affinity_types"].add(_text(row.get("bdb.affinity_type")))
        if _is_tbrucei_pde(row):
            current["tbrucei_pde_activity_count"] += 1
        if potency is not None:
            prev = current.get("best_affinity_nM")
            if prev is None or potency < float(prev):
                current["best_affinity_nM"] = potency
                current["best_affinity_type"] = _text(row.get("bdb.affinity_type"))

    ranked = sorted(
        grouped.values(),
        key=lambda item: (
            -int(item.get("tbrucei_pde_activity_count", 0) or 0),
            float(item.get("best_affinity_nM") if item.get("best_affinity_nM") is not None else 999999.0),
            _text(item.get("bindingdb_monomer_id")),
        ),
    )
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(ranked, start=1):
        smiles = _text(item.get("smiles"))
        desc = _descriptors(smiles)
        monomer_id = _text(item.get("bindingdb_monomer_id"))
        out.append(
            {
                "row_kind": "tcruzi_pde_bindingdb_similarity_homolog_seed",
                "priority_rank": idx,
                "ligand_id": f"tcruzi_pde_bindingdb_pdeb1_{idx:03d}_bdb{monomer_id}",
                "compound_name": f"BindingDB monomer {monomer_id}",
                "smiles": smiles,
                **desc,
                "source_dataset": "BindingDB",
                "source_anchor": "SMILES similarity to ChEMBL homolog PDEB1 energy-hit candidates",
                "source_url": "https://bindingdb.org",
                "bindingdb_monomer_id": monomer_id,
                "activity_count": int(item.get("activity_count", 0) or 0),
                "tbrucei_pde_activity_count": int(item.get("tbrucei_pde_activity_count", 0) or 0),
                "best_affinity_nM": item.get("best_affinity_nM"),
                "best_affinity_type": _text(item.get("best_affinity_type")),
                "target_species": ";".join(sorted(v for v in item["species"] if v)),
                "target_names": ";".join(sorted(v for v in item["targets"] if v)),
                "affinity_types": ";".join(sorted(v for v in item["affinity_types"] if v)),
                "query_ligand_ids": ";".join(sorted(v for v in item["query_ligand_ids"] if v)),
                "source_raw_jsons": ";".join(sorted(v for v in item["source_raw_jsons"] if v)),
                "direct_tcruzi_pde_evidence": False,
                "homolog_seed_only": True,
                "claim_policy": "bindingdb_similarity_seed_for_candidate_pool_expansion_not_direct_tcruzi_pde_claim",
            }
        )
    return out


def build_payload(raw_glob: str = DEFAULT_RAW_GLOB, *, top_n: int = DEFAULT_TOP_N) -> dict[str, Any]:
    raw_paths = sorted(glob.glob(raw_glob))
    raw_rows = _read_raw_rows(raw_paths)
    rows = _aggregate(raw_rows)[: max(1, int(top_n))]
    focus = rows[0] if rows else {}
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_bindingdb_similarity_seed_packet_ready" if rows else "blocked_no_bindingdb_similarity_seeds",
            "target_id": "T. cruzi PDE",
            "evidence_scope": "bindingdb_similarity_homolog_seed_only",
            "claim_promotion_allowed": False,
            "direct_tcruzi_pde_evidence_count": 0,
            "raw_json_count": len(raw_paths),
            "raw_affinity_row_count": len(raw_rows),
            "quantitative_seed_count": len(rows),
            "tbrucei_pde_seed_count": sum(1 for row in rows if int(row.get("tbrucei_pde_activity_count", 0) or 0) > 0),
            "top_n": max(1, int(top_n)),
            "top_seed_ligand_id": _text(focus.get("ligand_id")),
            "top_seed_bindingdb_monomer_id": _text(focus.get("bindingdb_monomer_id")),
            "top_seed_best_affinity_nM": focus.get("best_affinity_nM"),
            "top_seed_best_affinity_type": _text(focus.get("best_affinity_type")),
            "ligand_csv": DEFAULT_OUT_MD.replace(".md", ".csv"),
            "next_required_step": (
                "Run a strictly labeled candidate-pool expansion screen on these BindingDB similarity seeds; do not treat them as direct T. cruzi PDE evidence."
                if rows
                else "Re-query BindingDB similarity with valid PDEB1 energy-hit SMILES before attempting another candidate-pool expansion."
            ),
        },
        "structured": {
            "raw_glob": raw_glob,
            "raw_paths": raw_paths,
            "source_api": "BindingDB getTargetByCompound",
            "bindingdb_similarity_cutoff": 0.85,
            "query_ligand_id_pattern": "ChEMBL homolog PDEB1 energy-pass seed ligand IDs",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a claim-safe BindingDB similarity seed packet for T. cruzi PDE candidate expansion.")
    parser.add_argument("--raw-glob", default=DEFAULT_RAW_GLOB)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(str(args.raw_glob), top_n=max(1, int(args.top_n)))
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE BindingDB Similarity Seed Packet", payload)


if __name__ == "__main__":
    main()
