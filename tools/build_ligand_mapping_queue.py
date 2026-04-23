#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import math
import multiprocessing
import os
import random
import re
import tempfile
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure repo-root imports work when running `python tools/...py` directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants
from tools.pdb_loader import load_native_structure

try:
    from rdkit import Chem  # type: ignore
    from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Chem = None
    AllChem = None
    Crippen = None
    Descriptors = None
    Lipinski = None


@dataclass
class LigandRecord:
    ligand_id: str
    smiles: str
    source: str
    molecular_weight: float
    logp: float
    h_donors: int
    h_acceptors: int
    rot_bonds: int
    bead_count: int
    bead_coords: List[List[float]]


def _safe_slug_path_target(name: str) -> str:
    out: List[str] = []
    prev_us = False
    for ch in str(name).strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    s = "".join(out).strip("_")
    return s or "target"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip()).strip("_")
    return s or "ligand"


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if s in ("all", "*"):
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    if not out:
        raise ValueError(f"no targets parsed from spec: {spec}")
    seen = set()
    uniq: List[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def _parse_csv_list(text: str) -> List[str]:
    return [s.strip() for s in str(text or "").split(",") if s.strip()]


def _load_target_ligand_overrides(
    path: str,
    roles: str,
    role_col: str,
    target_col: str,
    ligand_col: str,
) -> Dict[str, List[str]]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    df = pd.read_csv(src)
    for col in (target_col, ligand_col):
        if col not in df.columns:
            raise ValueError(f"target-ligand csv missing column: {col}")
    use = df
    role_list = _parse_csv_list(roles)
    if role_list:
        if role_col not in df.columns:
            raise ValueError(f"target-ligand csv missing role column: {role_col}")
        use = df[df[role_col].astype(str).isin(role_list)].copy()
    out: Dict[str, List[str]] = {}
    seen: Dict[str, set] = {}
    for _, row in use.iterrows():
        t = str(row.get(target_col, "")).strip()
        lid = str(row.get(ligand_col, "")).strip()
        if (not t) or (not lid):
            continue
        if t not in out:
            out[t] = []
            seen[t] = set()
        if lid in seen[t]:
            continue
        seen[t].add(lid)
        out[t].append(lid)
    return out


def _load_ligand_binder_map(
    path: str,
    ligand_col: str,
    binder_col: str,
) -> Dict[str, int]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        df = pd.read_csv(src)
    except Exception:
        return {}
    lid_col = str(ligand_col).strip()
    b_col = str(binder_col).strip()
    if (not lid_col) or (not b_col):
        return {}
    if (lid_col not in df.columns) or (b_col not in df.columns):
        return {}
    out: Dict[str, int] = {}
    for _, row in df[[lid_col, b_col]].iterrows():
        lid = str(row.get(lid_col, "")).strip()
        if not lid:
            continue
        try:
            val = int(float(row.get(b_col, 0) or 0))
        except Exception:
            val = 0
        prev = int(out.get(lid, 0))
        if val > prev:
            out[lid] = val
    return out


def _pdb_centroid(path: str) -> Optional[Tuple[float, float, float]]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return None
    ca: List[List[float]] = []
    xyz: List[List[float]] = []
    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except Exception:
                continue
            atom = str(line[12:16]).strip().upper()
            xyz.append([x, y, z])
            if atom == "CA":
                ca.append([x, y, z])
    use = ca if len(ca) > 0 else xyz
    if len(use) <= 0:
        return None
    arr = np.asarray(use, dtype=np.float32)
    ctr = np.mean(arr, axis=0)
    return float(ctr[0]), float(ctr[1]), float(ctr[2])


def _default_pocket_center(target: str, native_path: str = "") -> Tuple[float, float, float]:
    c = _pdb_centroid(native_path)
    if c is not None:
        return c
    coords, _ = load_native_structure(target)
    if coords is None:
        return 0.0, 0.0, 0.0
    arr = coords.detach().cpu().numpy()
    if arr.ndim != 2 or arr.shape[1] != 3 or arr.shape[0] <= 0:
        return 0.0, 0.0, 0.0
    center = np.mean(arr, axis=0)
    return float(center[0]), float(center[1]), float(center[2])


def _load_target_native_overrides(path: str) -> Dict[str, Dict[str, Any]]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    df = pd.read_csv(src)
    if "target" not in df.columns:
        raise ValueError(f"target-native csv missing 'target' column: {src}")
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        t = str(row.get("target", "")).strip()
        if not t:
            continue
        rec: Dict[str, Any] = {
            "native_pdb_path": str(row.get("native_pdb_path", "")).strip(),
        }
        # Optional explicit pocket coordinates.
        has_xyz = all(c in df.columns for c in ("pocket_x", "pocket_y", "pocket_z"))
        if has_xyz:
            try:
                rec["pocket_xyz"] = (
                    float(row.get("pocket_x", 0.0)),
                    float(row.get("pocket_y", 0.0)),
                    float(row.get("pocket_z", 0.0)),
                )
            except Exception:
                pass
        out[t] = rec
    return out


def _read_smiles_bead_cache(path: str) -> Dict[str, List[List[float]]]:
    src = str(path or "").strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, List[List[float]]] = {}
    for k, v in obj.items():
        if (not isinstance(k, str)) or (not isinstance(v, list)):
            continue
        pts: List[List[float]] = []
        ok = True
        for p in v:
            if (not isinstance(p, (list, tuple))) or len(p) < 3:
                ok = False
                break
            try:
                pts.append([float(p[0]), float(p[1]), float(p[2])])
            except Exception:
                ok = False
                break
        if ok and pts:
            out[k] = pts
    return out


def _write_smiles_bead_cache(path: str, payload: Dict[str, List[List[float]]]) -> None:
    dst = str(path or "").strip()
    if not dst:
        return
    dst_dir = os.path.dirname(dst) or "."
    os.makedirs(dst_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f"{os.path.basename(dst)}.", suffix=".tmp", dir=dst_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _clean_text_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _load_pocket_overrides(path: str) -> Dict[str, Tuple[float, float, float]]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    df = pd.read_csv(src)
    required = {"target", "pocket_x", "pocket_y", "pocket_z"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"pocket csv missing columns: {missing}")
    out: Dict[str, Tuple[float, float, float]] = {}
    for _, row in df.iterrows():
        t = str(row.get("target", "")).strip()
        if not t:
            continue
        out[t] = (
            float(row.get("pocket_x", 0.0)),
            float(row.get("pocket_y", 0.0)),
            float(row.get("pocket_z", 0.0)),
        )
    return out


def _kmeans_2bead(coords: np.ndarray, iters: int = 8) -> List[List[float]]:
    arr = np.asarray(coords, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3 or arr.shape[0] <= 0:
        return [[0.0, 0.0, 0.0]]
    if arr.shape[0] == 1:
        c = arr[0].tolist()
        return [[float(c[0]), float(c[1]), float(c[2])]]
    # Init: first atom + farthest atom from first.
    c0 = arr[0]
    d = np.sum((arr - c0[None, :]) ** 2, axis=1)
    c1 = arr[int(np.argmax(d))]
    cent = np.stack([c0, c1], axis=0)
    for _ in range(int(max(iters, 1))):
        dist = np.sum((arr[:, None, :] - cent[None, :, :]) ** 2, axis=2)
        assign = np.argmin(dist, axis=1)
        next_cent = cent.copy()
        for k in range(2):
            mask = assign == k
            if np.any(mask):
                next_cent[k] = np.mean(arr[mask], axis=0)
        cent = next_cent
    out = cent.astype(np.float32).tolist()
    return [[float(v[0]), float(v[1]), float(v[2])] for v in out]


def _beads_from_smiles_relaxed(
    smiles: str,
    *,
    max_iters: int,
    embed_seed: int,
) -> Optional[List[List[float]]]:
    smi = str(smiles).strip()
    if (not smi) or (Chem is None) or (AllChem is None):
        return None
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    try:
        mol_h = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = int(embed_seed)
        params.useRandomCoords = True
        emb = int(AllChem.EmbedMolecule(mol_h, params))
        if emb != 0:
            params2 = AllChem.ETKDGv2()
            params2.randomSeed = int(embed_seed)
            params2.useRandomCoords = True
            emb = int(AllChem.EmbedMolecule(mol_h, params2))
        if emb != 0:
            return None
        if bool(AllChem.MMFFHasAllMoleculeParams(mol_h)):
            AllChem.MMFFOptimizeMolecule(mol_h, maxIters=int(max(max_iters, 1)))
        else:
            AllChem.UFFOptimizeMolecule(mol_h, maxIters=int(max(max_iters, 1)))
        conf = mol_h.GetConformer()
        coords: List[List[float]] = []
        for atom in mol_h.GetAtoms():
            if int(atom.GetAtomicNum()) <= 1:
                continue
            p = conf.GetAtomPosition(atom.GetIdx())
            coords.append([float(p.x), float(p.y), float(p.z)])
        if len(coords) <= 0:
            return None
        return _kmeans_2bead(np.asarray(coords, dtype=np.float32))
    except Exception:
        return None


def _ligand_from_csv_row(
    row: Dict[str, Any],
    source: str,
    *,
    csv_relax_3d: bool,
    csv_relax_max_iters: int,
    csv_relax_embed_seed: int,
    smiles_bead_cache: Optional[Dict[str, List[List[float]]]] = None,
) -> LigandRecord:
    ligand_id = _slug(row.get("ligand_id", row.get("id", row.get("name", "ligand"))))
    smiles = _clean_text_field(row.get("smiles", ""))
    mw = float(row.get("molecular_weight", max(float(len(smiles) * 7.5), 50.0)))
    logp = float(row.get("logp", min(max((len(smiles) / 20.0) - 0.5, -2.0), 8.0)))
    h_don = int(row.get("h_donors", 0))
    h_acc = int(row.get("h_acceptors", 0))
    rot = int(row.get("rot_bonds", max(len(smiles) // 14, 0)))
    bead_raw = _clean_text_field(row.get("bead_coords_json", ""))
    bead_coords: List[List[float]]
    if bead_raw:
        try:
            payload = json.loads(bead_raw)
            if isinstance(payload, list) and payload:
                bead_coords = [
                    [float(p[0]), float(p[1]), float(p[2])]
                    for p in payload
                    if isinstance(p, (list, tuple)) and len(p) >= 3
                ]
            else:
                bead_coords = [[-0.8, 0.0, 0.0], [0.8, 0.0, 0.0]]
        except Exception:
            bead_coords = [[-0.8, 0.0, 0.0], [0.8, 0.0, 0.0]]
    else:
        bead_coords = []
        if bool(csv_relax_3d):
            smi_key = _clean_text_field(smiles)
            if smi_key and isinstance(smiles_bead_cache, dict) and (smi_key in smiles_bead_cache):
                bead_coords = smiles_bead_cache[smi_key]
            else:
                generated = _beads_from_smiles_relaxed(
                    smi_key,
                    max_iters=int(max(csv_relax_max_iters, 1)),
                    embed_seed=int(csv_relax_embed_seed),
                )
                if generated is not None:
                    bead_coords = generated
                    if smi_key and isinstance(smiles_bead_cache, dict):
                        smiles_bead_cache[smi_key] = generated
        if len(bead_coords) <= 0:
            bead_coords = [[-0.8, 0.0, 0.0], [0.8, 0.0, 0.0]]
    bead_count = int(max(len(bead_coords), 1))
    return LigandRecord(
        ligand_id=ligand_id,
        smiles=smiles,
        source=source,
        molecular_weight=float(mw),
        logp=float(logp),
        h_donors=int(h_don),
        h_acceptors=int(h_acc),
        rot_bonds=int(rot),
        bead_count=bead_count,
        bead_coords=bead_coords,
    )


def _load_ligands_from_csv(
    path: str,
    *,
    csv_relax_3d: bool,
    csv_relax_max_iters: int,
    csv_relax_embed_seed: int,
    csv_relax_workers: int = 0,
    csv_smiles_cache_json: str = "",
    csv_prioritize_binders: bool = False,
    csv_binder_col: str = "is_binder",
) -> List[LigandRecord]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return []
    df = pd.read_csv(src)
    if df.empty:
        return []
    binder_col = str(csv_binder_col).strip()
    if bool(csv_prioritize_binders) and binder_col and (binder_col in df.columns):
        # Ensure positive/binder examples are retained under max_ligands truncation.
        df = df.sort_values(by=[binder_col], ascending=False, kind="stable").reset_index(drop=True)

    normalized_rows: List[Dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        row_copy = dict(row)
        row_copy["smiles"] = _clean_text_field(row_copy.get("smiles", ""))
        row_copy["bead_coords_json"] = _clean_text_field(row_copy.get("bead_coords_json", ""))
        # Rows without a valid SMILES can still survive only if explicit bead coordinates were supplied.
        if (not row_copy["smiles"]) and (not row_copy["bead_coords_json"]):
            continue
        normalized_rows.append(row_copy)
    if not normalized_rows:
        return []

    smiles_bead_cache: Dict[str, List[List[float]]] = {}
    disk_cache_path = str(csv_smiles_cache_json or "").strip()
    if bool(csv_relax_3d) and disk_cache_path:
        smiles_bead_cache.update(_read_smiles_bead_cache(disk_cache_path))

    if bool(csv_relax_3d):
        missing_smiles: List[str] = []
        seen_missing: set[str] = set()
        for row in normalized_rows:
            bead_raw = _clean_text_field(row.get("bead_coords_json", ""))
            if bead_raw:
                continue
            smi = _clean_text_field(row.get("smiles", ""))
            if (not smi) or (smi in smiles_bead_cache) or (smi in seen_missing):
                continue
            seen_missing.add(smi)
            missing_smiles.append(smi)

        if missing_smiles:
            req_workers = int(max(0, int(csv_relax_workers)))
            auto_workers = int(max(1, min(16, (multiprocessing.cpu_count() or 4))))
            workers = int(req_workers if req_workers > 0 else auto_workers)
            if workers <= 1:
                for smi in missing_smiles:
                    beads = _beads_from_smiles_relaxed(
                        smi,
                        max_iters=int(max(csv_relax_max_iters, 1)),
                        embed_seed=int(csv_relax_embed_seed),
                    )
                    if beads is not None:
                        smiles_bead_cache[smi] = beads
            else:
                def _job(s: str) -> Tuple[str, Optional[List[List[float]]]]:
                    return (
                        s,
                        _beads_from_smiles_relaxed(
                            s,
                            max_iters=int(max(csv_relax_max_iters, 1)),
                            embed_seed=int(csv_relax_embed_seed),
                        ),
                    )

                with cf.ThreadPoolExecutor(max_workers=int(workers)) as ex:
                    for smi, beads in ex.map(_job, missing_smiles):
                        if beads is not None:
                            smiles_bead_cache[smi] = beads

    out: List[LigandRecord] = []
    for row in normalized_rows:
        out.append(
            _ligand_from_csv_row(
                row,
                source="csv",
                csv_relax_3d=bool(csv_relax_3d),
                csv_relax_max_iters=int(csv_relax_max_iters),
                csv_relax_embed_seed=int(csv_relax_embed_seed),
                smiles_bead_cache=smiles_bead_cache,
            )
        )
    if bool(csv_relax_3d) and disk_cache_path and smiles_bead_cache:
        _write_smiles_bead_cache(disk_cache_path, smiles_bead_cache)
    return out


def _smiles_descriptors(smiles: str) -> Tuple[float, float, int, int, int]:
    if Chem is None:
        mw = max(float(len(smiles) * 7.5), 50.0)
        logp = min(max((len(smiles) / 20.0) - 0.5, -2.0), 8.0)
        h_don = max(smiles.count("N") // 2 + smiles.count("O") // 3, 0)
        h_acc = max(smiles.count("N") + smiles.count("O"), 0)
        rot = max(smiles.count("-") + smiles.count("=") // 4, 0)
        return float(mw), float(logp), int(h_don), int(h_acc), int(rot)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return max(float(len(smiles) * 7.5), 50.0), 0.0, 0, 0, 0
    mw = float(Descriptors.MolWt(mol)) if Descriptors is not None else max(float(len(smiles) * 7.5), 50.0)
    logp = float(Crippen.MolLogP(mol)) if Crippen is not None else 0.0
    h_don = int(Lipinski.NumHDonors(mol)) if Lipinski is not None else 0
    h_acc = int(Lipinski.NumHAcceptors(mol)) if Lipinski is not None else 0
    rot = int(Lipinski.NumRotatableBonds(mol)) if Lipinski is not None else 0
    return mw, logp, h_don, h_acc, rot


def _ligands_from_sdf(path: str, max_ligands: int) -> List[LigandRecord]:
    if Chem is None:
        raise RuntimeError(
            "RDKit is required for --ligand-sdf parsing. Install rdkit or provide --ligand-csv fallback."
        )
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        raise FileNotFoundError(f"ligand sdf not found: {src}")
    suppl = Chem.SDMolSupplier(src, removeHs=False)
    out: List[LigandRecord] = []
    for idx, mol in enumerate(suppl):
        if mol is None:
            continue
        if 0 < int(max_ligands) <= len(out):
            break
        ligand_id = _slug(mol.GetProp("_Name")) if mol.HasProp("_Name") else f"lig_{idx:06d}"
        smiles = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)
        mw, logp, h_don, h_acc, rot = _smiles_descriptors(smiles)
        conf = mol.GetConformer() if mol.GetNumConformers() > 0 else None
        coords = []
        if conf is not None:
            for atom in mol.GetAtoms():
                if atom.GetAtomicNum() <= 1:
                    continue
                p = conf.GetAtomPosition(atom.GetIdx())
                coords.append([float(p.x), float(p.y), float(p.z)])
        if not coords:
            coords = [[-0.8, 0.0, 0.0], [0.8, 0.0, 0.0]]
        bead_coords = _kmeans_2bead(np.asarray(coords, dtype=np.float32))
        out.append(
            LigandRecord(
                ligand_id=str(ligand_id),
                smiles=str(smiles),
                source="sdf",
                molecular_weight=float(mw),
                logp=float(logp),
                h_donors=int(h_don),
                h_acceptors=int(h_acc),
                rot_bonds=int(rot),
                bead_count=int(len(bead_coords)),
                bead_coords=bead_coords,
            )
        )
    if not out:
        raise ValueError(f"no valid ligands found in sdf: {src}")
    return out


def _resolve_ligands(
    ligand_sdf: str,
    ligand_csv: str,
    max_ligands: int,
    *,
    csv_relax_3d: bool,
    csv_relax_max_iters: int,
    csv_relax_embed_seed: int,
    csv_relax_workers: int = 0,
    csv_smiles_cache_json: str = "",
    required_ligand_ids: Optional[Sequence[str]] = None,
    csv_prioritize_binders: bool = False,
    csv_binder_col: str = "is_binder",
) -> Tuple[List[LigandRecord], str]:
    csv_rows = _load_ligands_from_csv(
        ligand_csv,
        csv_relax_3d=bool(csv_relax_3d),
        csv_relax_max_iters=int(csv_relax_max_iters),
        csv_relax_embed_seed=int(csv_relax_embed_seed),
        csv_relax_workers=int(csv_relax_workers),
        csv_smiles_cache_json=str(csv_smiles_cache_json),
        csv_prioritize_binders=bool(csv_prioritize_binders),
        csv_binder_col=str(csv_binder_col),
    )
    if csv_rows:
        if int(max_ligands) > 0:
            lim = int(max_ligands)
            if len(csv_rows) > lim:
                req_ids = {str(x).strip() for x in (required_ligand_ids or []) if str(x).strip()}
                if req_ids:
                    req: List[LigandRecord] = []
                    rem: List[LigandRecord] = []
                    seen = set()
                    for lig in csv_rows:
                        lid = str(lig.ligand_id).strip()
                        if (not lid) or (lid in seen):
                            continue
                        seen.add(lid)
                        if lid in req_ids:
                            req.append(lig)
                        else:
                            rem.append(lig)
                    if len(req) >= lim:
                        csv_rows = req[:lim]
                    else:
                        csv_rows = req + rem[: (lim - len(req))]
                else:
                    csv_rows = csv_rows[:lim]
        return csv_rows, "csv"
    sdf_path = str(ligand_sdf).strip()
    if sdf_path:
        ligs = _ligands_from_sdf(sdf_path, max_ligands=max_ligands)
        return ligs, "sdf"
    raise ValueError("either --ligand-csv or --ligand-sdf must be provided")


def _build_runtime_defaults() -> Dict[str, float]:
    return {
        "ionic_strength": 0.15,
        "ptm_count": 0.0,
        "force_scale": 1.0,
        "cooling_rate": 0.0,
        "hydro_strength": 1.0,
        "k_angle": 1.0,
        "theta0": 109.5,
        "k_dihedral": 0.5,
        "phi0_alpha": -57.0,
        "ai_correction_active": 1.0,
    }


def _assignment_index(policy: str, target_idx: int, replica_idx: int, ligand_count: int, seed: int) -> int:
    if ligand_count <= 0:
        return 0
    pol = str(policy).strip().lower()
    if pol == "random":
        rnd = random.Random(int(seed) + int(target_idx) * 100000 + int(replica_idx))
        return int(rnd.randrange(0, ligand_count))
    if pol == "target_block":
        return int((target_idx + replica_idx) % ligand_count)
    # round_robin default
    return int(replica_idx % ligand_count)


def build_queue(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(str(args.targets))
    target_ligand_overrides = _load_target_ligand_overrides(
        path=str(args.target_ligand_csv),
        roles=str(args.target_ligand_roles),
        role_col=str(args.target_ligand_role_col),
        target_col=str(args.target_ligand_target_col),
        ligand_col=str(args.target_ligand_id_col),
    )
    required_override_ids: List[str] = []
    for _t, ids in target_ligand_overrides.items():
        required_override_ids.extend([str(x).strip() for x in ids if str(x).strip()])
    binder_map: Dict[str, int] = {}
    if bool(args.csv_prioritize_binders):
        binder_map = _load_ligand_binder_map(
            path=str(args.ligand_csv),
            ligand_col="ligand_id",
            binder_col=str(args.csv_binder_col),
        )
    ligands, ligand_source = _resolve_ligands(
        ligand_sdf=str(args.ligand_sdf),
        ligand_csv=str(args.ligand_csv),
        max_ligands=int(args.max_ligands),
        csv_relax_3d=bool(args.csv_relax_3d),
        csv_relax_max_iters=int(args.csv_relax_max_iters),
        csv_relax_embed_seed=int(args.csv_relax_embed_seed),
        csv_relax_workers=int(args.csv_relax_workers),
        csv_smiles_cache_json=str(args.csv_smiles_cache_json),
        required_ligand_ids=required_override_ids,
        csv_prioritize_binders=bool(args.csv_prioritize_binders),
        csv_binder_col=str(args.csv_binder_col),
    )
    if not ligands:
        raise ValueError("no ligands resolved")
    ligand_by_id: Dict[str, LigandRecord] = {}
    for lig in ligands:
        lid = str(lig.ligand_id).strip()
        if lid and (lid not in ligand_by_id):
            ligand_by_id[lid] = lig

    pocket_overrides = _load_pocket_overrides(str(args.target_pocket_csv))
    native_overrides = _load_target_native_overrides(str(args.target_native_csv))
    runtime_defaults = _build_runtime_defaults()

    max_replicas = int(max(args.replicas, 1))
    queue_rows: List[Dict[str, Any]] = []
    for ti, target in enumerate(targets):
        native_path = ""
        if target in native_overrides:
            native_path = str(native_overrides[target].get("native_pdb_path", "")).strip()
        if (not native_path) and os.path.exists(f"data/native/{target.lower()}.pdb"):
            native_path = f"data/native/{target.lower()}.pdb"
        if (not native_path):
            slug = _safe_slug_path_target(target)
            alt = f"data/native/{slug}.pdb"
            if os.path.exists(alt):
                native_path = alt
        if bool(args.require_native_path) and ((not native_path) or (not os.path.exists(native_path))):
            raise FileNotFoundError(
                f"native_pdb_path required but missing for target={target}. "
                f"provide --target-native-csv with target,native_pdb_path"
            )

        pocket = pocket_overrides.get(target)
        if pocket is None:
            rec = native_overrides.get(target, {})
            if isinstance(rec, dict) and ("pocket_xyz" in rec):
                pocket = rec["pocket_xyz"]
            else:
                pocket = _default_pocket_center(target, native_path=native_path)
        jobs_this_target = int(args.jobs_per_target) if int(args.jobs_per_target) > 0 else max_replicas
        jobs_this_target = min(jobs_this_target, max_replicas)
        target_pool = ligands
        override_ids = target_ligand_overrides.get(str(target), [])
        if override_ids:
            ordered_ids = list(override_ids)
            if binder_map:
                # Keep stable order within same binder class while moving binders first.
                ordered_ids = sorted(
                    ordered_ids,
                    key=lambda lid: int(binder_map.get(str(lid).strip(), 0)),
                    reverse=True,
                )
            picked = [ligand_by_id[lid] for lid in ordered_ids if lid in ligand_by_id]
            if picked:
                target_pool = picked
        for replica_idx in range(jobs_this_target):
            lig_idx = _assignment_index(
                policy=str(args.queue_policy),
                target_idx=ti,
                replica_idx=replica_idx,
                ligand_count=len(target_pool),
                seed=int(args.seed),
            )
            lig = target_pool[int(lig_idx)]
            queue_id = f"{_slug(target)}__rep{replica_idx:04d}__{_slug(lig.ligand_id)}"
            bead0 = lig.bead_coords[0] if lig.bead_coords else [0.0, 0.0, 0.0]
            bead1 = lig.bead_coords[1] if len(lig.bead_coords) > 1 else bead0
            row = {
                "queue_id": queue_id,
                "target": target,
                "replica_idx": int(replica_idx),
                "ligand_id": lig.ligand_id,
                "ligand_smiles": lig.smiles,
                "ligand_source": lig.source,
                "ligand_mw": float(lig.molecular_weight),
                "ligand_logp": float(lig.logp),
                "ligand_h_donors": int(lig.h_donors),
                "ligand_h_acceptors": int(lig.h_acceptors),
                "ligand_rot_bonds": int(lig.rot_bonds),
                "ligand_bead_count": int(lig.bead_count),
                "ligand_bead0_x": float(bead0[0]),
                "ligand_bead0_y": float(bead0[1]),
                "ligand_bead0_z": float(bead0[2]),
                "ligand_bead1_x": float(bead1[0]),
                "ligand_bead1_y": float(bead1[1]),
                "ligand_bead1_z": float(bead1[2]),
                "pocket_x": float(pocket[0]),
                "pocket_y": float(pocket[1]),
                "pocket_z": float(pocket[2]),
                "native_pdb_path": str(native_path),
            }
            row.update(runtime_defaults)
            queue_rows.append(row)

    queue_df = pd.DataFrame(queue_rows)
    os.makedirs(os.path.dirname(str(args.out_queue_csv)) or ".", exist_ok=True)
    queue_df.to_csv(str(args.out_queue_csv), index=False)

    ligand_payload = {
        "source": ligand_source,
        "count": int(len(ligands)),
        "rows": [
            {
                "ligand_id": lig.ligand_id,
                "smiles": lig.smiles,
                "source": lig.source,
                "molecular_weight": float(lig.molecular_weight),
                "logp": float(lig.logp),
                "h_donors": int(lig.h_donors),
                "h_acceptors": int(lig.h_acceptors),
                "rot_bonds": int(lig.rot_bonds),
                "bead_count": int(lig.bead_count),
                "bead_coords": lig.bead_coords,
            }
            for lig in ligands
        ],
    }
    os.makedirs(os.path.dirname(str(args.out_ligand_json)) or ".", exist_ok=True)
    with open(str(args.out_ligand_json), "w", encoding="utf-8") as f:
        json.dump(ligand_payload, f, indent=2, ensure_ascii=False)

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "targets": int(len(targets)),
        "target_list": targets,
        "ligand_source": ligand_source,
        "ligands": int(len(ligands)),
        "replicas_requested": int(max_replicas),
        "jobs_per_target": int(args.jobs_per_target if int(args.jobs_per_target) > 0 else max_replicas),
        "queue_rows": int(len(queue_df)),
        "queue_policy": str(args.queue_policy),
        "runtime_defaults": runtime_defaults,
        "target_native_csv": str(args.target_native_csv),
        "target_ligand_csv": str(args.target_ligand_csv),
        "target_ligand_roles": _parse_csv_list(str(args.target_ligand_roles)),
        "targets_with_ligand_overrides": sorted([k for k, v in target_ligand_overrides.items() if v]),
        "required_override_ids": int(len({x for x in required_override_ids if x})),
        "csv_prioritize_binders": bool(args.csv_prioritize_binders),
        "csv_binder_col": str(args.csv_binder_col),
        "csv_relax_3d": bool(args.csv_relax_3d),
        "csv_relax_max_iters": int(args.csv_relax_max_iters),
        "csv_relax_embed_seed": int(args.csv_relax_embed_seed),
        "csv_relax_workers": int(args.csv_relax_workers),
        "csv_smiles_cache_json": str(args.csv_smiles_cache_json),
        "artifacts": {
            "queue_csv": str(args.out_queue_csv),
            "ligand_json": str(args.out_ligand_json),
        },
    }
    os.makedirs(os.path.dirname(str(args.out_summary_json)) or ".", exist_ok=True)
    with open(str(args.out_summary_json), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Ligand Mapping Queue",
        "",
        f"- generated_at_local: {summary['generated_at_local']}",
        f"- targets: {summary['targets']}",
        f"- ligands: {summary['ligands']}",
        f"- queue_rows: {summary['queue_rows']}",
        f"- queue_policy: {summary['queue_policy']}",
        f"- queue_csv: `{args.out_queue_csv}`",
        f"- ligand_json: `{args.out_ligand_json}`",
    ]
    os.makedirs(os.path.dirname(str(args.out_summary_md)) or ".", exist_ok=True)
    with open(str(args.out_summary_md), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Build protein-ligand HTVS queue: convert ligands (SDF/CSV) into 2-bead templates and "
            "assign them to per-target replica slots."
        )
    )
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--ligand-sdf", type=str, default="")
    p.add_argument("--ligand-csv", type=str, default="")
    p.add_argument("--max-ligands", type=int, default=640)
    p.add_argument("--replicas", type=int, default=640)
    p.add_argument("--jobs-per-target", type=int, default=640)
    p.add_argument("--queue-policy", type=str, default="round_robin", choices=["round_robin", "target_block", "random"])
    p.add_argument("--csv-prioritize-binders", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--csv-binder-col", type=str, default="is_binder")
    p.add_argument("--csv-relax-3d", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--csv-relax-max-iters", type=int, default=200)
    p.add_argument("--csv-relax-embed-seed", type=int, default=13)
    p.add_argument("--csv-relax-workers", type=int, default=0)
    p.add_argument("--csv-smiles-cache-json", type=str, default="runs/ligand_smiles_bead_cache.json")
    p.add_argument("--target-pocket-csv", type=str, default="")
    p.add_argument("--target-native-csv", type=str, default="")
    p.add_argument("--target-ligand-csv", type=str, default="")
    p.add_argument("--target-ligand-roles", type=str, default="")
    p.add_argument("--target-ligand-role-col", type=str, default="role")
    p.add_argument("--target-ligand-target-col", type=str, default="target")
    p.add_argument("--target-ligand-id-col", type=str, default="ligand_id")
    p.add_argument("--require-native-path", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-queue-csv", type=str, default=f"runs/ligand_mapping_queue_{stamp}.csv")
    p.add_argument("--out-ligand-json", type=str, default=f"runs/ligand_mapping_library_{stamp}.json")
    p.add_argument("--out-summary-json", type=str, default=f"runs/ligand_mapping_queue_{stamp}_summary.json")
    p.add_argument("--out-summary-md", type=str, default=f"runs/ligand_mapping_queue_{stamp}_summary.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_queue(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
