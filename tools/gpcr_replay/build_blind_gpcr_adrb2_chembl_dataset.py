#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests

try:
    from rdkit import Chem  # type: ignore
    from rdkit.Chem import Crippen, Descriptors, Lipinski  # type: ignore
    from rdkit.Chem.Scaffolds import MurckoScaffold  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("RDKit is required for blind GPCR ChEMBL dataset generation") from exc


ROOT = "/home/betelgeuze/분자동역학"
BASE_META = os.path.join(ROOT, "config/ligand_meta_blind_gpcr_adrb2_v1.csv")
BASE_REF = os.path.join(ROOT, "config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv")
BASE_SPLIT = os.path.join(ROOT, "config/ligand_eval_splits_blind_gpcr_adrb2_v1.csv")
BASE_PROFILE = os.path.join(ROOT, "config/ligand_htvs_blind_gpcr_adrb2_v1.json")


@dataclass
class Candidate:
    ligand_id: str
    smiles: str
    mw: float
    logp: float
    h_donors: int
    h_acceptors: int
    rot_bonds: int
    scaffold: str
    pchembl: float
    ref_kcal_mol: float
    standard_type: str
    source: str


def _safe_slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip().lower()).strip("_")
    return s or "x"


def _read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: str, rows: Sequence[Dict[str, object]], fieldnames: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames))
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _canonicalize_smiles(smiles: str) -> str:
    mol = Chem.MolFromSmiles(str(smiles or "").strip())
    if mol is None:
        return ""
    return str(Chem.MolToSmiles(mol, isomericSmiles=False) or "")


def _derive_scaffold(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    try:
        scaf = MurckoScaffold.GetScaffoldForMol(mol)
        return str(Chem.MolToSmiles(scaf, isomericSmiles=False) or "")
    except Exception:
        return ""


def _rdkit_desc(smiles: str) -> Optional[Tuple[float, float, int, int, int]]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return (
        float(Descriptors.MolWt(mol)),
        float(Crippen.MolLogP(mol)),
        int(Lipinski.NumHDonors(mol)),
        int(Lipinski.NumHAcceptors(mol)),
        int(Lipinski.NumRotatableBonds(mol)),
    )


def _fetch_chembl_activities(target_chembl_id: str, limit: int = 1000) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    offset = 0
    session = requests.Session()
    while True:
        url = (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json"
            f"?target_chembl_id={target_chembl_id}"
            "&assay_type=B"
            "&standard_relation=%3D"
            f"&limit={int(limit)}&offset={int(offset)}"
        )
        r = session.get(url, timeout=60)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("activities", []) or []
        if not rows:
            break
        out.extend(rows)
        if len(rows) < limit:
            break
        offset += limit
    return out


def _activity_to_candidate(activity: Dict[str, object]) -> Optional[Candidate]:
    smiles = _canonicalize_smiles(str(activity.get("canonical_smiles", "") or ""))
    if not smiles:
        return None
    desc = _rdkit_desc(smiles)
    if desc is None:
        return None
    mw, logp, h_don, h_acc, rot = desc
    if not (120.0 <= mw <= 700.0):
        return None
    if not (-2.0 <= logp <= 8.0):
        return None
    pchembl_raw = activity.get("pchembl_value", None)
    try:
        pchembl = float(pchembl_raw)
    except Exception:
        return None
    if not math.isfinite(pchembl) or pchembl < 6.5:
        return None
    std_type = str(activity.get("standard_type", "") or "").strip()
    mol_id = str(activity.get("molecule_chembl_id", "") or "").strip()
    if not mol_id:
        return None
    # DeltaG ≈ -RT ln(10) * pK  at 298K.
    ref_kcal = -1.364 * pchembl
    lig_id = f"{_safe_slug(mol_id)}"
    return Candidate(
        ligand_id=lig_id,
        smiles=smiles,
        mw=mw,
        logp=logp,
        h_donors=h_don,
        h_acceptors=h_acc,
        rot_bonds=rot,
        scaffold=_derive_scaffold(smiles),
        pchembl=pchembl,
        ref_kcal_mol=ref_kcal,
        standard_type=std_type,
        source="chembl_blind_adrb2_v1",
    )


def _select_diverse_candidates(
    activities: Iterable[Dict[str, object]],
    need: int,
    existing_ids: set[str],
    existing_smiles: set[str],
) -> List[Candidate]:
    dedup: Dict[str, Candidate] = {}
    for act in activities:
        cand = _activity_to_candidate(act)
        if cand is None:
            continue
        if cand.ligand_id in existing_ids or cand.smiles in existing_smiles:
            continue
        prev = dedup.get(cand.smiles)
        if prev is None or cand.pchembl > prev.pchembl:
            dedup[cand.smiles] = cand

    cands = sorted(dedup.values(), key=lambda c: (-c.pchembl, c.ligand_id))
    selected: List[Candidate] = []
    scaffold_counts: Dict[str, int] = {}
    for cap in (1, 2, 3, 99):
        for cand in cands:
            if cand in selected:
                continue
            scaf = cand.scaffold or cand.smiles
            if scaffold_counts.get(scaf, 0) >= cap:
                continue
            selected.append(cand)
            scaffold_counts[scaf] = scaffold_counts.get(scaf, 0) + 1
            if len(selected) >= need:
                return selected
    return selected[:need]


def _load_base_rows(meta_csv: str, ref_csv: str, split_csv: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    return _read_csv(meta_csv), _read_csv(ref_csv), _read_csv(split_csv)


def _base_existing_sets(meta_rows: Sequence[Dict[str, str]]) -> Tuple[set[str], set[str]]:
    ids = set()
    smiles = set()
    for row in meta_rows:
        lid = str(row.get("ligand_id", "") or "").strip()
        smi = _canonicalize_smiles(str(row.get("smiles", "") or ""))
        if lid:
            ids.add(lid)
        if smi:
            smiles.add(smi)
    return ids, smiles


def _generate_variant(
    count: int,
    candidates: Sequence[Candidate],
    base_meta: Sequence[Dict[str, str]],
    base_ref: Sequence[Dict[str, str]],
    base_split: Sequence[Dict[str, str]],
    *,
    target_name: str,
    target_slug: str,
    base_profile_path: str,
) -> Dict[str, str]:
    chosen = list(candidates[:count])
    suffix = f"chembl{int(count)}_v1"

    meta_rows = [dict(r) for r in base_meta]
    ref_rows = [dict(r) for r in base_ref]
    split_rows = [dict(r) for r in base_split]

    for cand in chosen:
        meta_rows.append(
            {
                "ligand_id": cand.ligand_id,
                "smiles": cand.smiles,
                "molecular_weight": f"{cand.mw:.2f}",
                "logp": f"{cand.logp:.3f}",
                "h_donors": str(cand.h_donors),
                "h_acceptors": str(cand.h_acceptors),
                "rot_bonds": str(cand.rot_bonds),
                "scaffold": cand.scaffold,
            }
        )
        ref_rows.append(
            {
                "target": str(target_name),
                "ligand_id": cand.ligand_id,
                "reference_binding_kcal_mol": f"{cand.ref_kcal_mol:.3f}",
                "is_binder": "1",
                "source": f"{cand.source}:{cand.standard_type}:pchembl={cand.pchembl:.2f}",
            }
        )
        split_rows.append(
            {
                "target": str(target_name),
                "ligand_id": cand.ligand_id,
                "role": "far_ood_eval",
            }
        )

    # Deduplicate by ligand_id, preserving first occurrence for base rows.
    def dedup(rows: Sequence[Dict[str, str]], key_cols: Sequence[str]) -> List[Dict[str, str]]:
        seen = set()
        out = []
        for row in rows:
            key = tuple(str(row.get(c, "") or "") for c in key_cols)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    meta_rows = dedup(meta_rows, ["ligand_id"])
    ref_rows = dedup(ref_rows, ["target", "ligand_id"])
    split_rows = dedup(split_rows, ["target", "ligand_id", "role"])

    meta_path = os.path.join(ROOT, f"config/ligand_meta_{target_slug}_{suffix}.csv")
    ref_path = os.path.join(ROOT, f"config/ligand_binding_reference_{target_slug}_{suffix}.csv")
    split_path = os.path.join(ROOT, f"config/ligand_eval_splits_{target_slug}_{suffix}.csv")
    profile_path = os.path.join(ROOT, f"config/ligand_htvs_{target_slug}_{suffix}.json")

    _write_csv(meta_path, meta_rows, ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"])
    _write_csv(ref_path, ref_rows, ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"])
    _write_csv(split_path, split_rows, ["target", "ligand_id", "role"])

    with open(base_profile_path, "r", encoding="utf-8") as f:
        prof = json.load(f)
    prof = copy.deepcopy(prof)
    prof["version"] = f"ligand_htvs_{target_slug}_{suffix}"
    prof["description"] = (
        f"Frozen-v8 blind {target_name} profile expanded with {int(count)} ChEMBL-derived public actives; "
        f"fit target retained, {target_name} evaluated as far-OOD with 10k hard decoys."
    )
    prof["ligand_csv"] = os.path.relpath(ref_path, ROOT)
    prof["calibration_reference_csv"] = os.path.relpath(ref_path, ROOT)
    prof["ranking_labels_csv"] = os.path.relpath(ref_path, ROOT)
    prof["eval_split_csv"] = os.path.relpath(split_path, ROOT)
    prof["leakage_ligand_meta_csv"] = os.path.relpath(meta_path, ROOT)
    prof["hard_decoy_reference_csv"] = os.path.relpath(ref_path, ROOT)
    prof["hard_decoy_ligand_meta_csv"] = os.path.relpath(meta_path, ROOT)
    prof["csv_smiles_cache_json"] = f"runs/ligand_smiles_bead_cache_{target_slug}_{suffix}.json"
    prof["ranking_score_col"] = "binding_score_composite_v5"
    prof["ranking_probability_score_col"] = "binding_score_composite_v5"
    prof["hard_decoy_min_rows_per_role"] = int(max(count, 6))
    prof["traj_auto_fast_output"] = True
    prof["traj_frame_output_format"] = "npz_bundle"
    prof["traj_writer_mode"] = "process"
    prof["traj_writer_workers"] = 4
    prof["traj_npz_layout"] = "flat_shard"
    prof["traj_npz_shard_size"] = 512

    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=2, ensure_ascii=False)

    return {
        "count": str(count),
        "meta_csv": meta_path,
        "reference_csv": ref_path,
        "split_csv": split_path,
        "profile_json": profile_path,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-chembl-id", default="CHEMBL210")
    ap.add_argument("--target-name", default="ADRB2_GPCR_BLIND")
    ap.add_argument("--target-slug", default="blind_gpcr_adrb2")
    ap.add_argument("--base-meta-csv", default=BASE_META)
    ap.add_argument("--base-ref-csv", default=BASE_REF)
    ap.add_argument("--base-split-csv", default=BASE_SPLIT)
    ap.add_argument("--base-profile-json", default=BASE_PROFILE)
    ap.add_argument("--counts", default="20,50")
    ap.add_argument("--out-candidates-csv", default=os.path.join(ROOT, "config/ligand_blind_gpcr_adrb2_chembl_candidates_v1.csv"))
    ap.add_argument("--out-summary-json", default=os.path.join(ROOT, "config/ligand_blind_gpcr_adrb2_chembl_build_summary_v1.json"))
    args = ap.parse_args()

    counts = sorted({int(x.strip()) for x in str(args.counts).split(",") if str(x).strip()})
    base_meta, base_ref, base_split = _load_base_rows(str(args.base_meta_csv), str(args.base_ref_csv), str(args.base_split_csv))
    existing_ids, existing_smiles = _base_existing_sets(base_meta)
    acts = _fetch_chembl_activities(str(args.target_chembl_id).strip())
    max_need = max(counts or [0])
    candidates = _select_diverse_candidates(acts, max_need, existing_ids, existing_smiles)

    os.makedirs(os.path.dirname(args.out_candidates_csv) or ".", exist_ok=True)
    _write_csv(
        args.out_candidates_csv,
        [
            {
                "ligand_id": c.ligand_id,
                "smiles": c.smiles,
                "molecular_weight": f"{c.mw:.2f}",
                "logp": f"{c.logp:.3f}",
                "h_donors": c.h_donors,
                "h_acceptors": c.h_acceptors,
                "rot_bonds": c.rot_bonds,
                "scaffold": c.scaffold,
                "pchembl": f"{c.pchembl:.3f}",
                "reference_binding_kcal_mol": f"{c.ref_kcal_mol:.3f}",
                "source": c.source,
                "standard_type": c.standard_type,
            }
            for c in candidates
        ],
        [
            "ligand_id",
            "smiles",
            "molecular_weight",
            "logp",
            "h_donors",
            "h_acceptors",
            "rot_bonds",
            "scaffold",
            "pchembl",
            "reference_binding_kcal_mol",
            "source",
            "standard_type",
        ],
    )

    variants: List[Dict[str, str]] = []
    for count in counts:
        if len(candidates) < count:
            raise RuntimeError(f"Only {len(candidates)} candidates available, need {count}")
        variants.append(
            _generate_variant(
                count,
                candidates,
                base_meta,
                base_ref,
                base_split,
                target_name=str(args.target_name),
                target_slug=str(args.target_slug),
                base_profile_path=str(args.base_profile_json),
            )
        )

    summary = {
        "target_chembl_id": args.target_chembl_id,
        "activities_fetched": len(acts),
        "candidate_count": len(candidates),
        "candidate_csv": args.out_candidates_csv,
        "variants": variants,
    }
    with open(args.out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
