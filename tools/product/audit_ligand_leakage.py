#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

try:
    from rdkit import Chem  # type: ignore
    from rdkit.Chem.Scaffolds import MurckoScaffold  # type: ignore
except Exception:  # pragma: no cover
    Chem = None
    MurckoScaffold = None


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _parse_roles(spec: str) -> List[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _key_set(df: pd.DataFrame, target_col: str, ligand_col: str) -> Set[Tuple[str, str]]:
    if df.empty:
        return set()
    return set(zip(df[target_col].astype(str), df[ligand_col].astype(str)))


def _tokenize_fp(fp: str) -> Set[str]:
    s = str(fp or "").strip()
    if not s:
        return set()
    toks = [t for t in re.split(r"[|,;\s]+", s) if t]
    return set(toks)


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return float(inter / max(uni, 1))


def _seq_identity(a: str, b: str) -> float:
    sa = str(a or "").strip().upper()
    sb = str(b or "").strip().upper()
    if (not sa) or (not sb):
        return float("nan")
    m = min(len(sa), len(sb))
    if m <= 0:
        return float("nan")
    same = 0
    for i in range(m):
        if sa[i] == sb[i]:
            same += 1
    return float(same / max(len(sa), len(sb), 1))


def _scaffold_from_smiles(smiles: str) -> str:
    smi = str(smiles or "").strip()
    if not smi:
        return ""
    if Chem is None or MurckoScaffold is None:
        return smi
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return smi
    try:
        scaf = MurckoScaffold.GetScaffoldForMol(mol)
        return str(Chem.MolToSmiles(scaf, isomericSmiles=False) or "")
    except Exception:
        return smi


def run_audit(args: argparse.Namespace) -> Dict[str, Any]:
    split_csv = str(args.split_csv).strip()
    if (not split_csv) or (not os.path.exists(split_csv)):
        raise FileNotFoundError(f"split csv not found: {split_csv}")

    sdf = pd.read_csv(split_csv)
    tcol = str(args.split_target_col).strip()
    lcol = str(args.split_ligand_col).strip()
    rcol = str(args.split_role_col).strip()
    req = {tcol, lcol, rcol}
    miss = [c for c in req if c not in sdf.columns]
    if miss:
        raise ValueError(f"split csv missing columns: {miss}")

    fit_roles = _parse_roles(str(args.fit_roles))
    eval_roles = _parse_roles(str(args.eval_roles))
    if not fit_roles:
        raise ValueError("fit roles are empty")
    if not eval_roles:
        raise ValueError("eval roles are empty")

    fit_df = sdf[sdf[rcol].astype(str).isin(fit_roles)].copy()
    eval_df = sdf[sdf[rcol].astype(str).isin(eval_roles)].copy()
    if fit_df.empty:
        raise ValueError("no fit rows")
    if eval_df.empty:
        raise ValueError("no eval rows")

    fit_keys = _key_set(fit_df, tcol, lcol)
    eval_keys = _key_set(eval_df, tcol, lcol)
    key_overlap = fit_keys & eval_keys

    fit_targets = set(fit_df[tcol].astype(str))
    eval_targets = set(eval_df[tcol].astype(str))
    target_overlap = fit_targets & eval_targets

    fit_ligands = set(fit_df[lcol].astype(str))
    eval_ligands = set(eval_df[lcol].astype(str))
    ligand_overlap = fit_ligands & eval_ligands

    # Optional target metadata.
    tmeta_csv = str(args.target_meta_csv).strip()
    tmeta: pd.DataFrame = pd.DataFrame(columns=["target"])  # fallback
    if tmeta_csv:
        if not os.path.exists(tmeta_csv):
            raise FileNotFoundError(f"target meta csv not found: {tmeta_csv}")
        tmeta = pd.read_csv(tmeta_csv)

    tmeta_target_col = str(args.target_meta_target_col).strip()
    fam_col = str(args.target_family_col).strip()
    seq_col = str(args.target_sequence_col).strip()
    pfp_col = str(args.target_pocket_fp_col).strip()

    if (not tmeta.empty) and (tmeta_target_col in tmeta.columns):
        fit_tmeta = tmeta[tmeta[tmeta_target_col].astype(str).isin(fit_targets)].copy()
        eval_tmeta = tmeta[tmeta[tmeta_target_col].astype(str).isin(eval_targets)].copy()
    else:
        fit_tmeta = pd.DataFrame()
        eval_tmeta = pd.DataFrame()

    fit_families: Set[str] = set()
    eval_families: Set[str] = set()
    family_overlap: Set[str] = set()
    if (not fit_tmeta.empty) and (fam_col in fit_tmeta.columns):
        fit_families = {x for x in fit_tmeta[fam_col].astype(str) if x and x != "nan"}
    if (not eval_tmeta.empty) and (fam_col in eval_tmeta.columns):
        eval_families = {x for x in eval_tmeta[fam_col].astype(str) if x and x != "nan"}
    family_overlap = fit_families & eval_families
    family_overlap_ratio = float(len(family_overlap) / max(len(eval_families), 1)) if eval_families else float("nan")

    # Sequence similarity leakage (max eval-vs-fit identity).
    seq_pairs: List[Dict[str, Any]] = []
    max_seq_identity = float("nan")
    seq_leak_count = 0
    if (
        (not fit_tmeta.empty)
        and (not eval_tmeta.empty)
        and (seq_col in fit_tmeta.columns)
        and (seq_col in eval_tmeta.columns)
    ):
        fit_seq = {
            str(r[tmeta_target_col]): str(r[seq_col])
            for _, r in fit_tmeta[[tmeta_target_col, seq_col]].drop_duplicates().iterrows()
        }
        for _, er in eval_tmeta[[tmeta_target_col, seq_col]].drop_duplicates().iterrows():
            et = str(er[tmeta_target_col])
            es = str(er[seq_col])
            best_fit = ""
            best_id = -1.0
            for ft, fs in fit_seq.items():
                sid = _seq_identity(es, fs)
                if np.isnan(sid):
                    continue
                if sid > best_id:
                    best_id = sid
                    best_fit = ft
            if best_id >= 0.0:
                seq_pairs.append({"eval_target": et, "fit_target": best_fit, "max_sequence_identity": float(best_id)})
        if seq_pairs:
            max_seq_identity = float(max(x["max_sequence_identity"] for x in seq_pairs))
            seq_leak_count = int(sum(x["max_sequence_identity"] >= float(args.max_allowed_seq_identity) for x in seq_pairs))

    # Pocket fingerprint overlap leakage.
    pocket_pairs: List[Dict[str, Any]] = []
    max_pocket_jaccard = float("nan")
    pocket_leak_count = 0
    if (
        (not fit_tmeta.empty)
        and (not eval_tmeta.empty)
        and (pfp_col in fit_tmeta.columns)
        and (pfp_col in eval_tmeta.columns)
    ):
        fit_fp = {
            str(r[tmeta_target_col]): _tokenize_fp(str(r[pfp_col]))
            for _, r in fit_tmeta[[tmeta_target_col, pfp_col]].drop_duplicates().iterrows()
        }
        for _, er in eval_tmeta[[tmeta_target_col, pfp_col]].drop_duplicates().iterrows():
            et = str(er[tmeta_target_col])
            e_fp = _tokenize_fp(str(er[pfp_col]))
            best_fit = ""
            best_j = -1.0
            for ft, f_fp in fit_fp.items():
                j = _jaccard(e_fp, f_fp)
                if j > best_j:
                    best_j = j
                    best_fit = ft
            if best_j >= 0.0:
                pocket_pairs.append({"eval_target": et, "fit_target": best_fit, "max_pocket_jaccard": float(best_j)})
        if pocket_pairs:
            max_pocket_jaccard = float(max(x["max_pocket_jaccard"] for x in pocket_pairs))
            pocket_leak_count = int(sum(x["max_pocket_jaccard"] >= float(args.max_allowed_pocket_jaccard) for x in pocket_pairs))

    # Optional ligand metadata -> scaffold overlap.
    lmeta_csv = str(args.ligand_meta_csv).strip()
    lmeta_lig_col = str(args.ligand_meta_ligand_col).strip()
    lmeta_smi_col = str(args.ligand_smiles_col).strip()
    lmeta_scaf_col = str(args.ligand_scaffold_col).strip()
    fit_scaffolds: Set[str] = set()
    eval_scaffolds: Set[str] = set()
    scaffold_overlap: Set[str] = set()
    scaffold_overlap_ratio = float("nan")
    if lmeta_csv:
        if not os.path.exists(lmeta_csv):
            raise FileNotFoundError(f"ligand meta csv not found: {lmeta_csv}")
        ldf = pd.read_csv(lmeta_csv)
        if lmeta_lig_col not in ldf.columns:
            raise ValueError(f"ligand meta missing ligand column: {lmeta_lig_col}")
        ldf = ldf.copy()
        if lmeta_scaf_col in ldf.columns:
            ldf["_scaffold"] = ldf[lmeta_scaf_col].astype(str)
        elif lmeta_smi_col in ldf.columns:
            ldf["_scaffold"] = ldf[lmeta_smi_col].astype(str).apply(_scaffold_from_smiles)
        else:
            ldf["_scaffold"] = ""
        scaf_map = {
            str(r[lmeta_lig_col]): str(r["_scaffold"]).strip()
            for _, r in ldf[[lmeta_lig_col, "_scaffold"]].drop_duplicates().iterrows()
        }
        fit_scaffolds = {scaf_map.get(x, "") for x in fit_ligands}
        eval_scaffolds = {scaf_map.get(x, "") for x in eval_ligands}
        fit_scaffolds = {x for x in fit_scaffolds if x and x != "nan"}
        eval_scaffolds = {x for x in eval_scaffolds if x and x != "nan"}
        scaffold_overlap = fit_scaffolds & eval_scaffolds
        scaffold_overlap_ratio = (
            float(len(scaffold_overlap) / max(len(eval_scaffolds), 1)) if len(eval_scaffolds) > 0 else float("nan")
        )

    failed_rules: List[Dict[str, Any]] = []

    if int(len(key_overlap)) > int(args.max_key_overlap):
        failed_rules.append(
            {
                "metric": "key_overlap_count",
                "value": int(len(key_overlap)),
                "threshold": int(args.max_key_overlap),
            }
        )
    if int(len(target_overlap)) > int(args.max_target_overlap):
        failed_rules.append(
            {
                "metric": "target_overlap_count",
                "value": int(len(target_overlap)),
                "threshold": int(args.max_target_overlap),
            }
        )
    if (not np.isnan(family_overlap_ratio)) and family_overlap_ratio > float(args.max_family_overlap_ratio):
        failed_rules.append(
            {
                "metric": "family_overlap_ratio",
                "value": float(family_overlap_ratio),
                "threshold": float(args.max_family_overlap_ratio),
            }
        )
    if (not np.isnan(scaffold_overlap_ratio)) and scaffold_overlap_ratio > float(args.max_scaffold_overlap_ratio):
        failed_rules.append(
            {
                "metric": "scaffold_overlap_ratio",
                "value": float(scaffold_overlap_ratio),
                "threshold": float(args.max_scaffold_overlap_ratio),
            }
        )
    if (not np.isnan(max_seq_identity)) and max_seq_identity > float(args.max_allowed_seq_identity):
        failed_rules.append(
            {
                "metric": "max_sequence_identity",
                "value": float(max_seq_identity),
                "threshold": float(args.max_allowed_seq_identity),
            }
        )
    if (not np.isnan(max_pocket_jaccard)) and max_pocket_jaccard > float(args.max_allowed_pocket_jaccard):
        failed_rules.append(
            {
                "metric": "max_pocket_jaccard",
                "value": float(max_pocket_jaccard),
                "threshold": float(args.max_allowed_pocket_jaccard),
            }
        )

    passed = len(failed_rules) == 0

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": bool(passed),
        "split_csv": split_csv,
        "fit_roles": fit_roles,
        "eval_roles": eval_roles,
        "fit_rows": int(len(fit_df)),
        "eval_rows": int(len(eval_df)),
        "fit_unique_keys": int(len(fit_keys)),
        "eval_unique_keys": int(len(eval_keys)),
        "key_overlap_count": int(len(key_overlap)),
        "target_overlap_count": int(len(target_overlap)),
        "ligand_overlap_count": int(len(ligand_overlap)),
        "family_overlap_count": int(len(family_overlap)),
        "family_overlap_ratio": float(family_overlap_ratio) if not np.isnan(family_overlap_ratio) else None,
        "max_sequence_identity": float(max_seq_identity) if not np.isnan(max_seq_identity) else None,
        "sequence_leak_count": int(seq_leak_count),
        "max_pocket_jaccard": float(max_pocket_jaccard) if not np.isnan(max_pocket_jaccard) else None,
        "pocket_leak_count": int(pocket_leak_count),
        "scaffold_overlap_count": int(len(scaffold_overlap)),
        "scaffold_overlap_ratio": float(scaffold_overlap_ratio) if not np.isnan(scaffold_overlap_ratio) else None,
        "failed_rules": failed_rules,
        "overlap_examples": {
            "keys": [{"target": t, "ligand_id": l} for (t, l) in sorted(key_overlap)[: int(args.max_examples)]],
            "targets": sorted(list(target_overlap))[: int(args.max_examples)],
            "ligands": sorted(list(ligand_overlap))[: int(args.max_examples)],
            "families": sorted(list(family_overlap))[: int(args.max_examples)],
            "scaffolds": sorted(list(scaffold_overlap))[: int(args.max_examples)],
            "sequence_pairs": sorted(seq_pairs, key=lambda x: -float(x.get("max_sequence_identity", -1.0)))[: int(args.max_examples)],
            "pocket_pairs": sorted(pocket_pairs, key=lambda x: -float(x.get("max_pocket_jaccard", -1.0)))[: int(args.max_examples)],
        },
        "artifacts": {},
    }

    out_json = str(args.out_json).strip()
    out_csv = str(args.out_csv).strip()
    out_md = str(args.out_md).strip()

    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    payload["artifacts"]["out_json"] = out_json

    _ensure_parent(out_csv)
    pd.DataFrame(
        [
            {
                "pass": payload["pass"],
                "fit_rows": payload["fit_rows"],
                "eval_rows": payload["eval_rows"],
                "fit_unique_keys": payload["fit_unique_keys"],
                "eval_unique_keys": payload["eval_unique_keys"],
                "key_overlap_count": payload["key_overlap_count"],
                "target_overlap_count": payload["target_overlap_count"],
                "ligand_overlap_count": payload["ligand_overlap_count"],
                "family_overlap_count": payload["family_overlap_count"],
                "family_overlap_ratio": payload["family_overlap_ratio"],
                "max_sequence_identity": payload["max_sequence_identity"],
                "max_pocket_jaccard": payload["max_pocket_jaccard"],
                "scaffold_overlap_count": payload["scaffold_overlap_count"],
                "scaffold_overlap_ratio": payload["scaffold_overlap_ratio"],
            }
        ]
    ).to_csv(out_csv, index=False)
    payload["artifacts"]["out_csv"] = out_csv

    lines = [
        "# Ligand Leakage Audit",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- pass: {payload['pass']}",
        f"- split_csv: `{split_csv}`",
        f"- fit_roles: {fit_roles}",
        f"- eval_roles: {eval_roles}",
        f"- key_overlap_count: {payload['key_overlap_count']}",
        f"- target_overlap_count: {payload['target_overlap_count']}",
        f"- family_overlap_ratio: {payload['family_overlap_ratio']}",
        f"- max_sequence_identity: {payload['max_sequence_identity']}",
        f"- max_pocket_jaccard: {payload['max_pocket_jaccard']}",
        f"- scaffold_overlap_ratio: {payload['scaffold_overlap_ratio']}",
        f"- failed_rules: {payload['failed_rules']}",
    ]
    _ensure_parent(out_md)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["artifacts"]["out_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Audit train/eval leakage for ligand screening splits.")
    p.add_argument("--split-csv", type=str, required=True)
    p.add_argument("--split-target-col", type=str, default="target")
    p.add_argument("--split-ligand-col", type=str, default="ligand_id")
    p.add_argument("--split-role-col", type=str, default="role")
    p.add_argument("--fit-roles", type=str, default="fit")
    p.add_argument("--eval-roles", type=str, default="eval,ood_eval,id_eval,near_ood_eval,far_ood_eval")

    p.add_argument("--target-meta-csv", type=str, default="")
    p.add_argument("--target-meta-target-col", type=str, default="target")
    p.add_argument("--target-family-col", type=str, default="target_family")
    p.add_argument("--target-sequence-col", type=str, default="sequence")
    p.add_argument("--target-pocket-fp-col", type=str, default="pocket_fingerprint")

    p.add_argument("--ligand-meta-csv", type=str, default="")
    p.add_argument("--ligand-meta-ligand-col", type=str, default="ligand_id")
    p.add_argument("--ligand-smiles-col", type=str, default="smiles")
    p.add_argument("--ligand-scaffold-col", type=str, default="scaffold")

    p.add_argument("--max-key-overlap", type=int, default=0)
    p.add_argument("--max-target-overlap", type=int, default=0)
    p.add_argument("--max-family-overlap-ratio", type=float, default=0.0)
    p.add_argument("--max-scaffold-overlap-ratio", type=float, default=0.0)
    p.add_argument("--max-allowed-seq-identity", type=float, default=0.30)
    p.add_argument("--max-allowed-pocket-jaccard", type=float, default=0.40)
    p.add_argument("--max-examples", type=int, default=10)

    p.add_argument("--out-json", type=str, default=f"runs/ligand_leakage_audit_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/ligand_leakage_audit_{stamp}.csv")
    p.add_argument("--out-md", type=str, default=f"runs/ligand_leakage_audit_{stamp}.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_audit(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
