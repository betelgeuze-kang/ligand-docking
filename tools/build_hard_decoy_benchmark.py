#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import os
import re
import random
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    from rdkit import Chem, RDLogger  # type: ignore
    from rdkit.Chem import BRICS  # type: ignore
    from rdkit.Chem import AllChem  # type: ignore
    from rdkit.Chem import Crippen, Descriptors, Lipinski  # type: ignore
    from rdkit.Chem.Scaffolds import MurckoScaffold  # type: ignore
    RDLogger.DisableLog("rdApp.warning")
except Exception:  # pragma: no cover
    Chem = None
    BRICS = None
    AllChem = None
    Crippen = None
    Descriptors = None
    Lipinski = None
    MurckoScaffold = None


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _write_progress_json(path: str, payload: Dict[str, Any]) -> None:
    p = str(path or "").strip()
    if not p:
        return
    _ensure_parent(p)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _read_relax_cache(path: str) -> Dict[str, bool]:
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
    out: Dict[str, bool] = {}
    for k, v in obj.items():
        if isinstance(k, str):
            out[k] = bool(v)
    return out


def _write_relax_cache(path: str, payload: Dict[str, bool]) -> None:
    dst = str(path or "").strip()
    if not dst:
        return
    _ensure_parent(dst)
    tmp = f"{dst}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, dst)


def _parse_csv_list(spec: str) -> List[str]:
    return [x.strip() for x in str(spec or "").split(",") if x.strip()]


def _safe_slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text)).strip("_")
    return s or "x"


def _derive_scaffold(smiles: str) -> str:
    smi = str(smiles or "").strip()
    if not smi:
        return ""
    if Chem is None or MurckoScaffold is None:
        return smi
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return smi
    try:
        s = MurckoScaffold.GetScaffoldForMol(m)
        return str(Chem.MolToSmiles(s, isomericSmiles=False) or "")
    except Exception:
        return smi


def _canonicalize_smiles(smiles: str) -> str:
    smi = str(smiles or "").strip()
    if not smi:
        return ""
    if Chem is None:
        return smi
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return ""
    try:
        return str(Chem.MolToSmiles(mol, isomericSmiles=False) or "")
    except Exception:
        return ""


def _rdkit_desc(smiles: str) -> Optional[Tuple[float, float, int, int, int]]:
    smi = str(smiles or "").strip()
    if (not smi) or (Chem is None):
        return None
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    mw = float(Descriptors.MolWt(mol)) if Descriptors is not None else float("nan")
    logp = float(Crippen.MolLogP(mol)) if Crippen is not None else float("nan")
    h_don = int(Lipinski.NumHDonors(mol)) if Lipinski is not None else 0
    h_acc = int(Lipinski.NumHAcceptors(mol)) if Lipinski is not None else 0
    rot = int(Lipinski.NumRotatableBonds(mol)) if Lipinski is not None else 0
    if np.isnan(mw) or np.isnan(logp):
        return None
    return float(mw), float(logp), int(h_don), int(h_acc), int(rot)


def _template_smiles_candidates() -> Tuple[List[str], List[str]]:
    templates = [
        "c1cc({r1})ccc1{r2}",
        "c1nc({r1})ccc1{r2}",
        "c1cc({r1})nc({r2})c1",
        "c1c({r1})c({r2})c({r3})cc1",
        "c1cc2cc({r1})c({r2})cc2[nH]1",
        "C1CC({r1})CC({r2})C1",
        "c1ccc({r1})c({r2})c1{r3}",
        "c1cc({r1})c(C)c({r2})c1{r3}",
        "c1nc({r1})cc(c1){r2}",
        "c1cc({r1})cc(n1){r2}",
        "c1ccc2cc({r1})ccc2c1{r2}",
        "C1CCC({r1})CC1{r2}",
        "C1CC({r1})C({r2})C({r3})C1",
        "c1c({r1})c({r2})c({r3})c({r4})c1",
        "c1cc({r1})c({r2})c({r3})c1{r4}",
        "C1C({r1})C({r2})C({r3})C({r4})C1",
    ]
    substituents = [
        "F",
        "Cl",
        "Br",
        "C",
        "CC",
        "CCC",
        "C(C)C",
        "C#N",
        "O",
        "OC",
        "OCC",
        "OCCC",
        "N",
        "NC",
        "N(C)C",
        "NCC",
        "C(=O)O",
        "C(=O)N",
        "C(=O)NC",
        "S",
        "SC",
        "S(=O)(=O)N",
        "S(=O)(=O)C",
        "c1ccccc1",
        "c1ncccc1",
        "c1ccncc1",
        "CCN",
        "CCO",
        "COC",
        "COCC",
        "CF",
        "C(F)(F)F",
        "CN",
        "CNC",
        "CCNC",
        "OCCO",
        "OCF",
        "NCCO",
        "CCS",
        "SCC",
        "C1CC1",
        "C1CCCCC1",
        "CC(C)O",
        "CC(C)N",
        "COC(C)C",
        "CCCC",
        "CC(C)C",
        "C(C)(C)C",
        "CC#N",
        "COCC",
        "COCCC",
        "OCCN",
        "OCCCN",
        "N(C)CC",
        "N(CC)CC",
        "C(=O)OC",
        "C(=O)OCC",
        "C(=O)CC",
        "C(=O)NCC",
        "C(=O)N(C)C",
        "S(=O)C",
        "S(=O)CC",
        "S(=O)(=O)NC",
        "S(=O)(=O)N(C)C",
        "c1ccoc1",
        "c1ccsc1",
        "c1ncccn1",
        "c1ncncc1",
        "c1cn[nH]c1",
        "C1COCC1",
        "C1CCOC1",
        "C1CCNCC1",
        "C1CNCCN1",
        "CC(=O)N",
        "CC(=O)NC",
        "OC(C)C",
        "OCC(C)O",
        "CCOC",
        "CCN(C)C",
        "CN(C)C",
    ]
    return templates, substituents


def _should_switch_to_brics(
    *,
    attempts: int,
    last_accept_attempt: int,
    target_count: int,
    stall_attempts: int,
) -> bool:
    threshold = int(max(stall_attempts, max(10000, target_count * 5)))
    if threshold <= 0:
        return False
    if attempts < threshold:
        return False
    return (attempts - last_accept_attempt) >= threshold


def _passes_3d_relaxation(smiles: str, max_iters: int = 200) -> bool:
    smi = str(smiles or "").strip()
    if not smi:
        return False
    if (Chem is None) or (AllChem is None):
        return True
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return False
    try:
        mol_h = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 13
        cid = int(AllChem.EmbedMolecule(mol_h, params))
        if cid < 0:
            return False
        mmff_props = AllChem.MMFFGetMoleculeProperties(mol_h, mmffVariant="MMFF94")
        if mmff_props is not None:
            rc = int(AllChem.MMFFOptimizeMolecule(mol_h, mmffVariant="MMFF94", maxIters=int(max_iters)))
            return rc in (0, 1)
        rc = int(AllChem.UFFOptimizeMolecule(mol_h, maxIters=int(max_iters)))
        return rc in (0, 1)
    except Exception:
        return False


def _generate_synthetic_unique_decoys(
    count: int,
    seed_smiles: List[str],
    rng: random.Random,
    max_attempt_mult: int,
    global_forbidden: Optional[set[str]] = None,
    require_relaxed_3d: bool = True,
    relax_max_iters: int = 200,
    relax_cache: Optional[Dict[str, bool]] = None,
    progress_cb: Optional[Callable[[int, int, int], None]] = None,
    progress_every: int = 250,
    progress_max_interval_sec: float = 30.0,
    template_stall_attempts: int = 250000,
    generation_mode: str = "random",
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    target_count = int(max(count, 0))
    if target_count <= 0:
        return []
    if Chem is None:
        raise RuntimeError("RDKit is required for synthetic unique hard-decoy generation")

    templates, substituents = _template_smiles_candidates()
    forbidden: set[str] = set(global_forbidden or set())
    for smi in seed_smiles:
        can = _canonicalize_smiles(smi)
        if can:
            forbidden.add(can)

    out: Dict[str, Dict[str, Any]] = {}
    max_attempts = int(max(target_count * max(max_attempt_mult, 20), target_count * 40))
    attempts = 0
    last_progress_at = time.monotonic()
    last_accept_attempt = 0
    template_exit_reason = "target_reached"
    brics_generated = 0
    mode = str(generation_mode or "random").strip().lower()
    if mode not in {"random", "enumerate"}:
        mode = "random"

    def _maybe_emit_progress(*, force: bool = False) -> None:
        nonlocal last_progress_at
        if progress_cb is None:
            return
        now_mono = time.monotonic()
        due_to_attempt = (attempts % max(1, int(progress_every)) == 0)
        due_to_target = len(out) >= target_count
        due_to_time = (now_mono - last_progress_at) >= float(max(progress_max_interval_sec, 1.0))
        if force or due_to_attempt or due_to_target or due_to_time:
            try:
                progress_cb(int(attempts), int(len(out)), int(max_attempts))
            except Exception:
                pass
            last_progress_at = now_mono

    def _accept_smiles(smi: str) -> bool:
        nonlocal last_accept_attempt
        can = _canonicalize_smiles(smi)
        if (not can) or (can in forbidden) or (can in out):
            return False
        desc = _rdkit_desc(can)
        if desc is None:
            return False
        if bool(require_relaxed_3d):
            ok_relax = None
            if isinstance(relax_cache, dict):
                ok_relax = relax_cache.get(can, None)
            if ok_relax is None:
                ok_relax = bool(_passes_3d_relaxation(can, max_iters=int(relax_max_iters)))
                if isinstance(relax_cache, dict):
                    relax_cache[can] = bool(ok_relax)
            if not bool(ok_relax):
                return False
        mw, logp, h_don, h_acc, rot = desc
        if not (120.0 <= mw <= 680.0):
            return False
        if not (-1.5 <= logp <= 7.5):
            return False
        if h_don > 6 or h_acc > 12 or rot > 14:
            return False
        out[can] = {
            "smiles": can,
            "molecular_weight": float(mw),
            "logp": float(logp),
            "h_donors": int(h_don),
            "h_acceptors": int(h_acc),
            "rot_bonds": int(rot),
            "scaffold": _derive_scaffold(can),
        }
        last_accept_attempt = attempts
        _maybe_emit_progress()
        return True

    placeholder_names = ("r1", "r2", "r3", "r4")

    def _placeholders_for(tpl: str) -> List[str]:
        return [name for name in placeholder_names if f"{{{name}}}" in tpl]

    def _format_template(tpl: str, values: Dict[str, str]) -> str:
        params = {name: "" for name in placeholder_names}
        params.update(values)
        return tpl.format(**params)

    if mode == "enumerate":
        tpl_order = list(templates)
        rng.shuffle(tpl_order)
        shuffled_subs: Dict[str, List[str]] = {}
        for name in placeholder_names:
            vals = list(substituents)
            rng.shuffle(vals)
            shuffled_subs[name] = vals
        template_exit_reason = "enumeration_exhausted"
        for tpl in tpl_order:
            placeholders = _placeholders_for(tpl)
            value_lists = [shuffled_subs[name] for name in placeholders]
            for combo in itertools.product(*value_lists):
                if len(out) >= target_count:
                    break
                attempts += 1
                _maybe_emit_progress()
                _accept_smiles(_format_template(tpl, dict(zip(placeholders, combo))))
            if len(out) >= target_count:
                break
    else:
        while len(out) < target_count and attempts < max_attempts:
            attempts += 1
            _maybe_emit_progress()
            if _should_switch_to_brics(
                attempts=attempts,
                last_accept_attempt=last_accept_attempt,
                target_count=target_count,
                stall_attempts=int(template_stall_attempts),
            ):
                template_exit_reason = "stall_switch_to_brics"
                break
            tpl = templates[rng.randrange(len(templates))]
            placeholders = _placeholders_for(tpl)
            values = {name: substituents[rng.randrange(len(substituents))] for name in placeholders}
            _accept_smiles(_format_template(tpl, values))

    raw_combo_upper_bound = 0
    for tpl in templates:
        placeholders = _placeholders_for(tpl)
        raw_combo_upper_bound += int(len(substituents) ** len(placeholders))

    if len(out) >= target_count:
        template_exit_reason = "target_reached"
    elif attempts >= max_attempts:
        template_exit_reason = "max_attempts"

    # BRICS fallback to fill remaining slots.
    if len(out) < target_count and BRICS is not None:
        frags: List[Any] = []
        for smi in seed_smiles:
            mol = Chem.MolFromSmiles(str(smi))
            if mol is None:
                continue
            try:
                frag_smi = BRICS.BRICSDecompose(mol)
            except Exception:
                frag_smi = set()
            for fs in frag_smi:
                fm = Chem.MolFromSmiles(str(fs))
                if fm is not None:
                    frags.append(fm)
        if len(frags) > 1:
            try:
                for mol in BRICS.BRICSBuild(frags, maxDepth=3, scrambleReagents=True):
                    _maybe_emit_progress()
                    if len(out) >= target_count:
                        break
                    if mol is None:
                        continue
                    can = _canonicalize_smiles(Chem.MolToSmiles(mol, isomericSmiles=False))
                    if (not can) or (can in forbidden) or (can in out):
                        continue
                    desc = _rdkit_desc(can)
                    if desc is None:
                        continue
                    if bool(require_relaxed_3d):
                        ok_relax = None
                        if isinstance(relax_cache, dict):
                            ok_relax = relax_cache.get(can, None)
                        if ok_relax is None:
                            ok_relax = bool(_passes_3d_relaxation(can, max_iters=int(relax_max_iters)))
                            if isinstance(relax_cache, dict):
                                relax_cache[can] = bool(ok_relax)
                        if not bool(ok_relax):
                            continue
                    mw, logp, h_don, h_acc, rot = desc
                    if not (120.0 <= mw <= 680.0):
                        continue
                    if not (-1.5 <= logp <= 7.5):
                        continue
                    if h_don > 6 or h_acc > 12 or rot > 14:
                        continue
                    out[can] = {
                        "smiles": can,
                        "molecular_weight": float(mw),
                        "logp": float(logp),
                        "h_donors": int(h_don),
                        "h_acceptors": int(h_acc),
                        "rot_bonds": int(rot),
                        "scaffold": _derive_scaffold(can),
                    }
                    brics_generated += 1
                    _maybe_emit_progress()
            except Exception:
                pass

    _maybe_emit_progress(force=True)

    if diagnostics is not None:
        diagnostics.update(
            {
                "template_count": int(len(templates)),
                "substituent_count": int(len(substituents)),
                "raw_combo_upper_bound": int(raw_combo_upper_bound),
                "generation_mode": str(mode),
                "template_attempts": int(attempts),
                "template_exit_reason": str(template_exit_reason),
                "template_generated": int(len(out) - brics_generated),
                "brics_generated": int(brics_generated),
                "used_brics_fallback": bool(brics_generated > 0 or template_exit_reason == "stall_switch_to_brics"),
                "template_stall_attempts": int(max(template_stall_attempts, 0)),
            }
        )

    return list(out.values())


def _z_norm(x: pd.Series) -> pd.Series:
    arr = x.astype(float)
    mu = float(arr.mean())
    sd = float(arr.std(ddof=0))
    if sd <= 1e-12:
        return pd.Series(np.zeros(len(arr), dtype=np.float64), index=arr.index)
    return (arr - mu) / sd


def _match_distance(dec: pd.Series, bind: pd.DataFrame, feat_cols: List[str]) -> float:
    if bind.empty or len(feat_cols) <= 0:
        return float("nan")
    best = float("inf")
    dv = dec[feat_cols].astype(float).to_numpy(dtype=np.float64)
    for _, br in bind.iterrows():
        bv = br[feat_cols].astype(float).to_numpy(dtype=np.float64)
        d = float(np.mean(np.abs(dv - bv)))
        if d < best:
            best = d
    return float(best)


def _match_distances_vectorized(dec: pd.DataFrame, bind: pd.DataFrame, feat_cols: List[str]) -> np.ndarray:
    if dec.empty or bind.empty or len(feat_cols) <= 0:
        return np.full(len(dec), np.nan, dtype=np.float64)
    dec_arr = dec[feat_cols].astype(float).to_numpy(dtype=np.float64, copy=False)
    bind_arr = bind[feat_cols].astype(float).to_numpy(dtype=np.float64, copy=False)
    if dec_arr.size <= 0 or bind_arr.size <= 0:
        return np.full(len(dec), np.nan, dtype=np.float64)
    chunk = 100_000
    out = np.empty(dec_arr.shape[0], dtype=np.float64)
    for start in range(0, dec_arr.shape[0], chunk):
        stop = min(start + chunk, dec_arr.shape[0])
        dist = np.mean(np.abs(dec_arr[start:stop, None, :] - bind_arr[None, :, :]), axis=2)
        out[start:stop] = np.min(dist, axis=1)
    return out


def _assign_fit_id_roles(group: pd.DataFrame, fit_fraction: float) -> pd.Series:
    # Preserve both classes in fit by splitting within class.
    role = pd.Series(["fit"] * len(group), index=group.index)
    frac = float(min(max(fit_fraction, 0.1), 0.95))
    for cls in [1, 0]:
        idx = group[group["is_binder"].astype(int) == cls].index.tolist()
        if len(idx) <= 0:
            continue
        n_eval = int(max(1, round((1.0 - frac) * len(idx)))) if len(idx) > 1 else 0
        for j in idx[:n_eval]:
            role.loc[j] = "id_eval"
    return role


def _enforce_role_min_counts(
    split_df: pd.DataFrame,
    *,
    target_col: str,
    ligand_col: str,
    ensure_roles: List[str],
    min_rows_per_role: int,
    donor_roles: List[str],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    out = split_df.copy()
    if out.empty:
        return out, {"applied": False, "moved_rows": 0, "before": {}, "after": {}}
    roles = [str(x).strip() for x in ensure_roles if str(x).strip()]
    min_n = int(max(0, int(min_rows_per_role)))
    donors = [str(x).strip() for x in donor_roles if str(x).strip()]
    if min_n <= 0 or (not roles):
        before = out["role"].value_counts().to_dict()
        return out, {"applied": False, "moved_rows": 0, "before": before, "after": before}

    out["_ord"] = np.arange(len(out), dtype=np.int64)
    moved = 0
    before_counts = out["role"].value_counts().to_dict()

    def _count(role: str) -> int:
        return int((out["role"].astype(str) == str(role)).sum())

    for role in roles:
        need = int(max(0, min_n - _count(role)))
        while need > 0:
            cands = out[out["role"].astype(str).isin(donors)].copy()
            if cands.empty:
                break
            # Prefer moving from donors that have the largest surplus.
            cands["__surplus"] = cands["role"].astype(str).map(lambda r: _count(r) - (min_n if r in roles else 0))
            cands = cands[cands["__surplus"] > 0]
            if cands.empty:
                break
            pick = cands.sort_values(["__surplus", "_ord"], ascending=[False, True]).iloc[0]
            idx = pick.name
            out.at[idx, "role"] = str(role)
            moved += 1
            need -= 1

    after_counts = out["role"].value_counts().to_dict()
    out = out.drop(columns=["_ord"], errors="ignore")
    return out, {
        "applied": bool(moved > 0),
        "moved_rows": int(moved),
        "before": {str(k): int(v) for k, v in before_counts.items()},
        "after": {str(k): int(v) for k, v in after_counts.items()},
        "ensure_roles": list(roles),
        "min_rows_per_role": int(min_n),
        "donor_roles": list(donors),
    }


def run_build(args: argparse.Namespace) -> Dict[str, Any]:
    ref_csv = str(args.reference_csv).strip()
    if (not ref_csv) or (not os.path.exists(ref_csv)):
        raise FileNotFoundError(f"reference csv not found: {ref_csv}")
    df = pd.read_csv(ref_csv)
    req = {args.target_col, args.ligand_col, args.binder_col, args.reference_energy_col}
    miss = [c for c in req if c not in df.columns]
    if miss:
        raise ValueError(f"reference csv missing columns: {miss}")

    out = df.copy()
    out[args.target_col] = out[args.target_col].astype(str)
    out[args.ligand_col] = out[args.ligand_col].astype(str)
    out["is_binder"] = out[args.binder_col].astype(int)
    out["reference_binding_kcal_mol"] = out[args.reference_energy_col].astype(float)
    target_filter = set(_parse_csv_list(getattr(args, "targets", "")))
    if target_filter:
        out = out[out[args.target_col].astype(str).isin(target_filter)].copy()
        if out.empty:
            raise ValueError("target filter removed all rows in reference csv")

    ligand_meta_csv = str(args.ligand_meta_csv).strip()
    if ligand_meta_csv:
        if not os.path.exists(ligand_meta_csv):
            raise FileNotFoundError(f"ligand meta csv not found: {ligand_meta_csv}")
        ldf = pd.read_csv(ligand_meta_csv)
        if args.ligand_col not in ldf.columns:
            raise ValueError(f"ligand meta csv missing key column: {args.ligand_col}")
        keep = [args.ligand_col]
        for c in [
            args.mw_col,
            args.logp_col,
            args.hd_col,
            args.ha_col,
            args.rot_col,
            args.scaffold_col,
            args.smiles_col,
        ]:
            if c in ldf.columns and c not in keep:
                keep.append(c)
        out = out.merge(ldf[keep].drop_duplicates(), on=[args.ligand_col], how="left")

    if args.scaffold_col in out.columns:
        out["_scaffold"] = out[args.scaffold_col].astype(str)
    elif args.smiles_col in out.columns:
        out["_scaffold"] = out[args.smiles_col].astype(str).apply(_derive_scaffold)
    else:
        out["_scaffold"] = ""
    out["_synthetic_decoy"] = False
    progress_json = str(getattr(args, "progress_json", "") or "").strip()

    def _emit_progress(
        *,
        status: str,
        phase: str,
        current_target: str = "",
        target_index: int = 0,
        target_total: int = 0,
        requested_total: int = 0,
        generated_total: int = 0,
        attempt: int = 0,
        max_attempts: int = 0,
    ) -> None:
        _write_progress_json(
            progress_json,
            {
                "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
                "status": str(status),
                "phase": str(phase),
                "current_target": str(current_target),
                "target_index": int(target_index),
                "target_total": int(target_total),
                "requested_total": int(requested_total),
                "generated_total": int(generated_total),
                "attempt": int(attempt),
                "max_attempts": int(max_attempts),
                "progress_ratio": float(
                    (float(generated_total) / float(max(1, requested_total)))
                    if requested_total > 0
                    else 0.0
                ),
            },
        )

    synth_requested = 0
    synth_generated = 0
    synth_shortfall = 0
    synth_targets: List[str] = []
    synthetic_target_generation_stats: List[Dict[str, Any]] = []
    relax_cache_path = str(getattr(args, "synth_relax_cache_json", "") or "").strip()
    relax_cache: Dict[str, bool] = _read_relax_cache(relax_cache_path) if relax_cache_path else {}
    relax_cache_last_flush_at = time.monotonic()
    relax_cache_last_flush_size = len(relax_cache)

    def _maybe_flush_relax_cache(*, force: bool = False) -> None:
        nonlocal relax_cache_last_flush_at, relax_cache_last_flush_size
        if (not relax_cache_path) or (not relax_cache):
            return
        now_mono = time.monotonic()
        new_entries = int(len(relax_cache) - relax_cache_last_flush_size)
        due_to_size = new_entries >= 256
        due_to_time = (now_mono - relax_cache_last_flush_at) >= 60.0
        if force or due_to_size or due_to_time:
            _write_relax_cache(relax_cache_path, relax_cache)
            relax_cache_last_flush_at = now_mono
            relax_cache_last_flush_size = len(relax_cache)
    if bool(args.synthesize_unique_decoys):
        if args.smiles_col not in out.columns:
            raise ValueError(
                f"--synthesize-unique-decoys requires smiles column '{args.smiles_col}' in reference/meta inputs"
            )
        targets_sorted = sorted([str(x) for x in out[args.target_col].astype(str).unique().tolist()])
        if len(targets_sorted) <= 0:
            raise ValueError("no targets available for synthetic decoy generation")
        synth_targets = targets_sorted
        total_req = int(max(args.synth_total_decoys, 0))
        per_target = int(max(args.synth_decoys_per_target, 0))
        if total_req <= 0 and per_target <= 0:
            total_req = 10000
        if per_target > 0:
            per_target_map = {t: int(per_target) for t in targets_sorted}
            synth_requested = int(per_target * len(targets_sorted))
        else:
            base = int(total_req // len(targets_sorted))
            rem = int(total_req % len(targets_sorted))
            per_target_map = {
                t: int(base + (1 if i < rem else 0))
                for i, t in enumerate(targets_sorted)
            }
            synth_requested = int(total_req)

        _emit_progress(
            status="running",
            phase="synthetic_decoy_generation",
            target_index=0,
            target_total=len(targets_sorted),
            requested_total=int(synth_requested),
            generated_total=int(synth_generated),
        )

        seed_smiles = [str(x) for x in out[args.smiles_col].astype(str).tolist() if str(x).strip()]
        if len(seed_smiles) <= 0:
            raise ValueError("no seed smiles available for synthetic decoy generation")
        rng = random.Random(int(args.synth_random_seed))
        global_forbidden: set[str] = set()
        synthetic_rows: List[Dict[str, Any]] = []
        for t_idx, tgt in enumerate(targets_sorted, start=1):
            n_req = int(per_target_map.get(tgt, 0))
            if n_req <= 0:
                continue
            tgt_df = out[out[args.target_col].astype(str) == str(tgt)].copy()
            bind_ref = tgt_df[tgt_df["is_binder"].astype(int) == 1]["reference_binding_kcal_mol"]
            bind_median = float(bind_ref.median()) if (not bind_ref.empty) else -6.0
            _emit_progress(
                status="running",
                phase="synthetic_decoy_generation",
                current_target=str(tgt),
                target_index=int(t_idx),
                target_total=len(targets_sorted),
                requested_total=int(synth_requested),
                generated_total=int(synth_generated),
            )

            def _target_progress_cb(attempt: int, generated_local: int, max_attempts: int) -> None:
                _emit_progress(
                    status="running",
                    phase="synthetic_decoy_generation",
                    current_target=str(tgt),
                    target_index=int(t_idx),
                    target_total=len(targets_sorted),
                    requested_total=int(synth_requested),
                    generated_total=int(synth_generated + int(generated_local)),
                    attempt=int(attempt),
                    max_attempts=int(max_attempts),
                )
                _maybe_flush_relax_cache()

            target_gen_diag: Dict[str, Any] = {"target": str(tgt), "requested": int(n_req)}
            synth = _generate_synthetic_unique_decoys(
                count=n_req,
                seed_smiles=seed_smiles,
                rng=rng,
                max_attempt_mult=int(max(args.synth_max_attempt_mult, 20)),
                global_forbidden=global_forbidden if bool(args.synth_global_unique) else set(),
                require_relaxed_3d=bool(args.synth_relax_3d),
                relax_max_iters=int(args.synth_relax_max_iters),
                relax_cache=relax_cache,
                progress_cb=_target_progress_cb,
                progress_every=int(max(args.progress_every_attempts, 200)),
                progress_max_interval_sec=float(max(args.progress_max_interval_sec, 1.0)),
                template_stall_attempts=int(max(args.synth_template_stall_attempts, 0)),
                generation_mode=str(args.synth_generation_mode),
                diagnostics=target_gen_diag,
            )
            target_gen_diag["generated"] = int(len(synth))
            synthetic_target_generation_stats.append(target_gen_diag)
            for i, rec in enumerate(synth, start=1):
                can = str(rec.get("smiles", "")).strip()
                if not can:
                    continue
                if bool(args.synth_global_unique):
                    global_forbidden.add(can)
                lid = f"decoy_{_safe_slug(tgt)}_{i:05d}"
                ref_val = float(min(-0.05, max(-2.95, bind_median + 3.6 + rng.uniform(-0.4, 0.4))))
                synthetic_rows.append(
                    {
                        args.target_col: str(tgt),
                        args.ligand_col: lid,
                        "reference_binding_kcal_mol": float(ref_val),
                        "is_binder": 0,
                        "source": "synthetic_hard_decoy",
                        args.smiles_col: can,
                        args.mw_col: float(rec.get("molecular_weight", np.nan)),
                        args.logp_col: float(rec.get("logp", np.nan)),
                        args.hd_col: int(rec.get("h_donors", 0)),
                        args.ha_col: int(rec.get("h_acceptors", 0)),
                        args.rot_col: int(rec.get("rot_bonds", 0)),
                        args.scaffold_col: str(rec.get("scaffold", "")),
                        "_scaffold": str(rec.get("scaffold", "")),
                        "_synthetic_decoy": True,
                    }
                )
            synth_generated += int(len(synth))
            _maybe_flush_relax_cache()
            _emit_progress(
                status="running",
                phase="synthetic_decoy_generation",
                current_target=str(tgt),
                target_index=int(t_idx),
                target_total=len(targets_sorted),
                requested_total=int(synth_requested),
                generated_total=int(synth_generated),
            )

        synth_shortfall = int(max(0, synth_requested - synth_generated))
        if synth_shortfall > 0 and (not bool(args.synth_allow_shortfall)):
            raise RuntimeError(
                f"synthetic decoy generation shortfall: requested={synth_requested}, generated={synth_generated}"
            )
        if synthetic_rows:
            out = pd.concat([out, pd.DataFrame(synthetic_rows)], axis=0, ignore_index=True)

    feat_cols: List[str] = []
    for c in [args.mw_col, args.logp_col, args.hd_col, args.ha_col, args.rot_col]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
            out[c] = out[c].fillna(out[c].median() if out[c].notna().any() else 0.0)
            out[f"_z_{c}"] = _z_norm(out[c])
            feat_cols.append(f"_z_{c}")

    _emit_progress(
        status="running",
        phase="postprocess_curate",
        target_index=len(synth_targets) if synth_targets else 0,
        target_total=len(synth_targets),
        requested_total=int(synth_requested),
        generated_total=int(synth_generated),
    )

    curated_rows: List[pd.DataFrame] = []
    hard_stats: List[Dict[str, Any]] = []

    curated_groups = list(out.groupby(args.target_col))
    curated_group_total = len(curated_groups)
    for c_idx, (tgt, g) in enumerate(curated_groups, start=1):
        _emit_progress(
            status="running",
            phase="postprocess_curate",
            current_target=str(tgt),
            target_index=int(c_idx),
            target_total=int(curated_group_total),
            requested_total=int(synth_requested),
            generated_total=int(synth_generated),
        )
        gg = g.copy().reset_index(drop=True)
        bind = gg[gg["is_binder"] == 1].copy()
        dec = gg[gg["is_binder"] == 0].copy()

        if bind.empty or dec.empty:
            gg["decoy_match_distance"] = np.nan
            gg["decoy_hardness_score"] = np.nan
            gg["decoy_selected"] = gg["is_binder"].astype(int) == 1
            curated_rows.append(gg)
            hard_stats.append(
                {
                    "target": str(tgt),
                    "binders": int(len(bind)),
                    "decoys": int(len(dec)),
                    "selected_decoys": int(len(dec)),
                }
            )
            continue

        dec = dec.copy()
        if "_synthetic_decoy" not in dec.columns:
            dec["_synthetic_decoy"] = False
        _emit_progress(
            status="running",
            phase="postprocess_curate",
            current_target=str(tgt),
            target_index=int(c_idx),
            target_total=int(curated_group_total),
            requested_total=int(synth_requested),
            generated_total=int(synth_generated),
        )
        dec["decoy_match_distance"] = _match_distances_vectorized(dec, bind, feat_cols)
        if dec["decoy_match_distance"].isna().all():
            bmed = float(bind["reference_binding_kcal_mol"].median())
            dec["decoy_match_distance"] = (dec["reference_binding_kcal_mol"] - bmed).abs()

        binder_scafs = {x for x in bind["_scaffold"].astype(str) if x and x != "nan"}
        dec["_scaf_match"] = dec["_scaffold"].astype(str).isin(binder_scafs).astype(float)
        dec["decoy_hardness_score"] = -dec["decoy_match_distance"].astype(float) + 0.25 * dec["_scaf_match"].astype(float)

        q = float(min(max(args.hard_decoy_quantile, 0.0), 1.0))
        thr = float(dec["decoy_hardness_score"].quantile(q))
        sel = dec[dec["decoy_hardness_score"] >= thr].copy()
        synth_only = dec[dec["_synthetic_decoy"].astype(bool)].copy()
        if bool(args.synth_keep_all_decoys) and (not synth_only.empty):
            sel = pd.concat([sel, synth_only], axis=0, ignore_index=True)
            sel = sel.drop_duplicates(subset=[args.ligand_col], keep="first")

        if (
            (not bool(args.synth_keep_all_decoys))
            and int(args.max_hard_decoys_per_target) > 0
            and len(sel) > int(args.max_hard_decoys_per_target)
        ):
            sel = sel.sort_values("decoy_hardness_score", ascending=False).head(int(args.max_hard_decoys_per_target)).copy()

        min_keep = int(max(args.min_hard_decoys_per_target, 1))
        if len(sel) < min_keep:
            sel = dec.sort_values("decoy_hardness_score", ascending=False).head(min_keep).copy()

        bind = bind.copy()
        bind["decoy_match_distance"] = np.nan
        bind["decoy_hardness_score"] = np.nan
        bind["decoy_selected"] = True
        sel["decoy_selected"] = True

        cur = pd.concat([bind, sel], axis=0, ignore_index=True)
        curated_rows.append(cur)
        hard_stats.append(
            {
                "target": str(tgt),
                "binders": int(len(bind)),
                "decoys": int(len(dec)),
                "selected_decoys": int(len(sel)),
                "hard_threshold": float(thr),
            }
        )

    curated = pd.concat(curated_rows, axis=0, ignore_index=True)
    curated["row_id"] = curated[args.target_col].astype(str) + "::" + curated[args.ligand_col].astype(str)

    # Split assignment (fit / id_eval / near_ood_eval / far_ood_eval)
    fit_targets = set(_parse_csv_list(args.fit_targets))
    if not fit_targets:
        fit_targets = {str(sorted(curated[args.target_col].astype(str).unique().tolist())[0])}

    family_map: Dict[str, str] = {}
    tmeta_csv = str(args.target_meta_csv).strip()
    if tmeta_csv:
        if not os.path.exists(tmeta_csv):
            raise FileNotFoundError(f"target meta csv not found: {tmeta_csv}")
        tdf = pd.read_csv(tmeta_csv)
        if args.target_col in tdf.columns and args.target_family_col in tdf.columns:
            family_map = {
                str(r[args.target_col]): str(r[args.target_family_col])
                for _, r in tdf[[args.target_col, args.target_family_col]].drop_duplicates().iterrows()
            }

    fit_families = {family_map.get(t, "") for t in fit_targets}
    fit_families = {x for x in fit_families if x and x != "nan"}

    split_frames: List[pd.DataFrame] = []
    _emit_progress(
        status="running",
        phase="split_assignment",
        target_index=len(synth_targets) if synth_targets else 0,
        target_total=len(synth_targets),
        requested_total=int(synth_requested),
        generated_total=int(synth_generated),
    )
    split_groups = list(curated.groupby(args.target_col))
    split_group_total = len(split_groups)
    for s_idx, (tgt, g) in enumerate(split_groups, start=1):
        _emit_progress(
            status="running",
            phase="split_assignment",
            current_target=str(tgt),
            target_index=int(s_idx),
            target_total=int(split_group_total),
            requested_total=int(synth_requested),
            generated_total=int(synth_generated),
        )
        gg = g.copy().sort_values(["is_binder", "reference_binding_kcal_mol"], ascending=[False, True])
        tgt_s = str(tgt)
        if tgt_s in fit_targets:
            roles = _assign_fit_id_roles(gg, fit_fraction=float(args.fit_fraction))
            gg["role"] = roles.values
        else:
            fam = family_map.get(tgt_s, "")
            role = "near_ood_eval" if (fam and fam in fit_families) else "far_ood_eval"
            gg["role"] = role
        split_frames.append(gg[[args.target_col, args.ligand_col, "role"]].copy())

    split_df = pd.concat(split_frames, axis=0, ignore_index=True).drop_duplicates(
        [args.target_col, args.ligand_col],
        keep="first",
    )
    split_df[args.target_col] = split_df[args.target_col].astype(str)
    split_df[args.ligand_col] = split_df[args.ligand_col].astype(str)
    split_df["role"] = split_df["role"].astype(str)
    split_df, role_rebalance = _enforce_role_min_counts(
        split_df,
        target_col=args.target_col,
        ligand_col=args.ligand_col,
        ensure_roles=_parse_csv_list(str(args.ensure_roles)),
        min_rows_per_role=int(args.min_rows_per_role),
        donor_roles=_parse_csv_list(str(args.rebalance_donor_roles)),
    )

    # Output payloads
    out_labels_csv = str(args.out_labels_csv).strip()
    out_split_csv = str(args.out_split_csv).strip()
    out_json = str(args.out_json).strip()
    out_md = str(args.out_md).strip()

    _ensure_parent(out_labels_csv)
    _ensure_parent(out_split_csv)
    _ensure_parent(out_json)
    _ensure_parent(out_md)

    _emit_progress(
        status="running",
        phase="writing_outputs",
        target_index=len(synth_targets) if synth_targets else 0,
        target_total=len(synth_targets),
        requested_total=int(synth_requested),
        generated_total=int(synth_generated),
    )

    curated_out_cols = list(df.columns)
    for c in [
        args.smiles_col,
        args.scaffold_col,
        args.mw_col,
        args.logp_col,
        args.hd_col,
        args.ha_col,
        args.rot_col,
    ]:
        if c in curated.columns and c not in curated_out_cols:
            curated_out_cols.append(c)
    for c in ["decoy_match_distance", "decoy_hardness_score", "decoy_selected", "_scaffold"]:
        if c in curated.columns and c not in curated_out_cols:
            curated_out_cols.append(c)
    curated[curated_out_cols].to_csv(out_labels_csv, index=False)
    _emit_progress(
        status="running",
        phase="writing_outputs",
        target_index=len(synth_targets) if synth_targets else 0,
        target_total=len(synth_targets),
        requested_total=int(synth_requested),
        generated_total=int(synth_generated),
    )
    split_df.to_csv(out_split_csv, index=False)

    role_counts = split_df["role"].value_counts().to_dict()

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": True,
        "reference_csv": ref_csv,
        "target_filter": sorted(list(target_filter)) if target_filter else [],
        "fit_targets": sorted(list(fit_targets)),
        "rows_reference": int(len(df)),
        "rows_curated": int(len(curated)),
        "role_counts": {str(k): int(v) for k, v in role_counts.items()},
        "role_rebalance": role_rebalance,
        "synthetic_decoys": {
            "enabled": bool(args.synthesize_unique_decoys),
            "targets": synth_targets,
            "requested": int(synth_requested),
            "generated": int(synth_generated),
            "shortfall": int(synth_shortfall),
            "allow_shortfall": bool(args.synth_allow_shortfall),
            "generation_mode": str(args.synth_generation_mode),
            "global_unique": bool(args.synth_global_unique),
            "relax_cache_json": relax_cache_path,
            "relax_cache_entries": int(len(relax_cache)),
            "template_stall_attempts": int(max(args.synth_template_stall_attempts, 0)),
            "target_generation_stats": synthetic_target_generation_stats,
        },
        "target_hard_decoy_stats": hard_stats,
        "artifacts": {
            "labels_csv": out_labels_csv,
            "split_csv": out_split_csv,
            "summary_json": out_json,
            "summary_md": out_md,
            "progress_json": progress_json,
        },
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if relax_cache_path and relax_cache:
        _maybe_flush_relax_cache(force=True)

    _emit_progress(
        status="done",
        phase="complete",
        requested_total=int(synth_requested),
        generated_total=int(synth_generated),
    )

    md_lines = [
        "# Hard-Decoy Benchmark Build",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- pass: {payload['pass']}",
        f"- rows_reference: {payload['rows_reference']}",
        f"- rows_curated: {payload['rows_curated']}",
        f"- fit_targets: {payload['fit_targets']}",
        f"- role_counts: {payload['role_counts']}",
        f"- synthetic_decoys: {payload['synthetic_decoys']}",
        f"- labels_csv: `{out_labels_csv}`",
        f"- split_csv: `{out_split_csv}`",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Build matched hard-decoy benchmark and ID/near/far OOD split.")
    p.add_argument("--reference-csv", type=str, required=True)
    p.add_argument("--target-col", type=str, default="target")
    p.add_argument("--ligand-col", type=str, default="ligand_id")
    p.add_argument("--binder-col", type=str, default="is_binder")
    p.add_argument("--reference-energy-col", type=str, default="reference_binding_kcal_mol")
    p.add_argument("--targets", type=str, default="")

    p.add_argument("--ligand-meta-csv", type=str, default="")
    p.add_argument("--smiles-col", type=str, default="smiles")
    p.add_argument("--scaffold-col", type=str, default="scaffold")
    p.add_argument("--mw-col", type=str, default="molecular_weight")
    p.add_argument("--logp-col", type=str, default="logp")
    p.add_argument("--hd-col", type=str, default="h_donors")
    p.add_argument("--ha-col", type=str, default="h_acceptors")
    p.add_argument("--rot-col", type=str, default="rot_bonds")

    p.add_argument("--target-meta-csv", type=str, default="")
    p.add_argument("--target-family-col", type=str, default="target_family")

    p.add_argument("--fit-targets", type=str, default="")
    p.add_argument("--fit-fraction", type=float, default=0.67)
    p.add_argument("--ensure-roles", type=str, default="fit,id_eval,near_ood_eval,eval,far_ood_eval,ood_eval")
    p.add_argument("--min-rows-per-role", type=int, default=0)
    p.add_argument("--rebalance-donor-roles", type=str, default="id_eval,near_ood_eval,eval,far_ood_eval,ood_eval")
    p.add_argument("--hard-decoy-quantile", type=float, default=0.50)
    p.add_argument("--min-hard-decoys-per-target", type=int, default=1)
    p.add_argument("--max-hard-decoys-per-target", type=int, default=0)
    p.add_argument("--synthesize-unique-decoys", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--synth-total-decoys", type=int, default=0)
    p.add_argument("--synth-decoys-per-target", type=int, default=0)
    p.add_argument("--synth-random-seed", type=int, default=13)
    p.add_argument("--synth-generation-mode", type=str, default="random", choices=["random", "enumerate"])
    p.add_argument("--synth-global-unique", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--synth-max-attempt-mult", type=int, default=400)
    p.add_argument("--synth-template-stall-attempts", type=int, default=250000)
    p.add_argument("--synth-relax-3d", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--synth-relax-max-iters", type=int, default=200)
    p.add_argument("--synth-relax-cache-json", type=str, default="runs/hard_decoy_relax_cache.json")
    p.add_argument("--progress-every-attempts", type=int, default=250)
    p.add_argument("--progress-max-interval-sec", type=float, default=30.0)
    p.add_argument("--progress-json", type=str, default="")
    p.add_argument("--synth-keep-all-decoys", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--synth-allow-shortfall", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--out-labels-csv", type=str, default=f"runs/ligand_hard_decoy_labels_{stamp}.csv")
    p.add_argument("--out-split-csv", type=str, default=f"runs/ligand_hard_decoy_split_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/ligand_hard_decoy_summary_{stamp}.json")
    p.add_argument("--out-md", type=str, default=f"runs/ligand_hard_decoy_summary_{stamp}.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
