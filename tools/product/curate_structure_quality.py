#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from glob import glob
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


TARGET_MAP = {_normalize_target_key(k): k for k in ResearchConstants.CHALLENGES.keys()}


@dataclass
class ParsedPDB:
    path: str
    total_atoms: int
    ca_atoms: int
    ca_residues: int
    bfactor_all: List[float]
    bfactor_ca: List[float]
    is_afdb_hint: bool


@dataclass
class StructureCandidate:
    path: str
    target_hint: Optional[str]
    source_kind_hint: Optional[str]


def _target_guess_from_path(path: str) -> Optional[str]:
    stem = os.path.splitext(os.path.basename(path))[0]
    norm = _normalize_target_key(stem)
    if norm in TARGET_MAP:
        return TARGET_MAP[norm]
    for k_norm, k_orig in TARGET_MAP.items():
        if k_norm in norm or norm in k_norm:
            return k_orig
    return None


def _parse_pdb(path: str) -> ParsedPDB:
    total_atoms = 0
    ca_atoms = 0
    bfactor_all: List[float] = []
    bfactor_ca: List[float] = []
    ca_res_keys: set = set()
    afdb_hint = False

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "ALPHAFOLD" in line.upper():
                afdb_hint = True
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            total_atoms += 1
            atom_name = line[12:16].strip()
            chain = line[21:22].strip()
            resseq = line[22:26].strip()
            icode = line[26:27].strip()
            try:
                bf = float(line[60:66].strip())
                if np.isfinite(bf):
                    bfactor_all.append(float(bf))
            except Exception:
                pass
            if atom_name == "CA":
                ca_atoms += 1
                ca_res_keys.add((chain, resseq, icode))
                try:
                    bf_ca = float(line[60:66].strip())
                    if np.isfinite(bf_ca):
                        bfactor_ca.append(float(bf_ca))
                except Exception:
                    pass

    name = os.path.basename(path).upper()
    if name.startswith("AF-") or ("ALPHAFOLD" in name):
        afdb_hint = True

    return ParsedPDB(
        path=os.path.abspath(path),
        total_atoms=int(total_atoms),
        ca_atoms=int(ca_atoms),
        ca_residues=int(len(ca_res_keys)),
        bfactor_all=bfactor_all,
        bfactor_ca=bfactor_ca,
        is_afdb_hint=bool(afdb_hint),
    )


def _str_or_empty(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def _normalize_source_kind_hint(raw: str) -> Optional[str]:
    s = _str_or_empty(raw).lower()
    if not s:
        return None
    if s.startswith("afdb_proxy") or s in {"proxy_afdb", "af_proxy"}:
        return "afdb_proxy"
    if s.startswith("afdb") or s in {"alphafold", "af"}:
        return "afdb"
    if s in {"pdb", "pdb_or_other", "experimental", "native"}:
        return "pdb_or_other"
    return None


def _build_candidates(args: argparse.Namespace) -> Tuple[List[StructureCandidate], Dict[str, Any]]:
    if args.manifest_csv:
        manifest_csv = str(args.manifest_csv)
        if not os.path.exists(manifest_csv):
            raise FileNotFoundError(f"manifest not found: {manifest_csv}")
        df = pd.read_csv(manifest_csv)
        path_col = str(args.manifest_path_col)
        target_col = str(args.manifest_target_col)
        source_kind_col = str(args.manifest_source_kind_col)
        if path_col not in df.columns:
            raise ValueError(f"manifest missing required path column '{path_col}': {manifest_csv}")

        candidates: List[StructureCandidate] = []
        missing_paths: List[str] = []
        for row in df.to_dict(orient="records"):
            raw_path = _str_or_empty(row.get(path_col, ""))
            if not raw_path:
                continue
            abs_path = os.path.abspath(raw_path)
            if not os.path.isfile(abs_path):
                missing_paths.append(abs_path)
                continue
            target_hint = _str_or_empty(row.get(target_col, "")) if target_col in df.columns else ""
            source_kind_raw = _str_or_empty(row.get(source_kind_col, "")) if source_kind_col in df.columns else ""
            candidates.append(
                StructureCandidate(
                    path=abs_path,
                    target_hint=(target_hint or None),
                    source_kind_hint=_normalize_source_kind_hint(source_kind_raw),
                )
            )

        meta = {
            "input_mode": "manifest",
            "manifest_csv": manifest_csv,
            "manifest_rows": int(len(df)),
            "missing_files_from_manifest": int(len(missing_paths)),
            "missing_file_examples": missing_paths[:10],
        }
        return candidates, meta

    files: List[str] = []
    if args.pdb_glob:
        patterns = args.pdb_glob
    elif args.pdb_file:
        patterns = []
    else:
        patterns = ["data/native/*.pdb"]
    for pattern in patterns:
        files.extend(glob(pattern))
    files.extend(args.pdb_file or [])
    files = sorted({os.path.abspath(x) for x in files if os.path.isfile(x)})
    candidates = [StructureCandidate(path=fp, target_hint=None, source_kind_hint=None) for fp in files]
    return candidates, {"input_mode": "files", "manifest_csv": None, "manifest_rows": 0, "missing_files_from_manifest": 0, "missing_file_examples": []}


def _plddt_stats(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "mean": None,
            "min": None,
            "max": None,
            "p10": None,
            "p50": None,
            "p90": None,
        }
    arr = np.asarray(values, dtype=np.float32)
    return {
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p10": float(np.quantile(arr, 0.10)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
    }


def _quality_tier(
    mean_v: Optional[float],
    p10_v: Optional[float],
    high_threshold: float,
    medium_threshold: float,
    min_threshold: float,
) -> str:
    if mean_v is None or p10_v is None:
        return "unknown"
    if mean_v >= high_threshold and p10_v >= medium_threshold:
        return "high"
    if mean_v >= medium_threshold and p10_v >= min_threshold:
        return "medium"
    return "low"


def _resolve_weight(
    tier: str,
    has_plddt: bool,
    include: bool,
    args: argparse.Namespace,
) -> float:
    if not include:
        return 0.0
    if not has_plddt:
        return float(args.experimental_weight)
    if tier == "high":
        return float(args.weight_high)
    if tier == "medium":
        return float(args.weight_medium)
    return float(args.weight_low)


def curate_structure_rows(args: argparse.Namespace) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    candidates, input_meta = _build_candidates(args)

    target_filter: Optional[set] = None
    if args.targets:
        target_filter = {t.strip() for t in str(args.targets).split(",") if t.strip()}

    rows: List[Dict[str, Any]] = []
    for cand in candidates:
        fp = cand.path
        parsed = _parse_pdb(fp)
        target_guess = cand.target_hint or _target_guess_from_path(fp)
        if target_filter is not None and target_guess not in target_filter:
            continue

        expected_n_res = None
        if target_guess and target_guess in ResearchConstants.CHALLENGES:
            expected_n_res = int(ResearchConstants.CHALLENGES[target_guess]["n_res"])

        source_kind = "afdb" if parsed.is_afdb_hint else "pdb_or_other"
        if cand.source_kind_hint in {"afdb", "afdb_proxy", "pdb_or_other"}:
            source_kind = str(cand.source_kind_hint)
        bvals = parsed.bfactor_ca
        has_plddt = bool(source_kind == "afdb" and len(bvals) > 0)
        if not has_plddt and bool(args.allow_bfactor_as_plddt):
            if len(bvals) > 0:
                # Conservative heuristic: use only if values are in the expected pLDDT range.
                bmin = float(np.min(np.asarray(bvals, dtype=np.float32)))
                bmax = float(np.max(np.asarray(bvals, dtype=np.float32)))
                if bmin >= 0.0 and bmax <= 100.0:
                    has_plddt = True
                    source_kind = "afdb_like_bfactor"

        pstats = _plddt_stats(bvals if has_plddt else [])
        tier = _quality_tier(
            mean_v=pstats["mean"],
            p10_v=pstats["p10"],
            high_threshold=float(args.plddt_high_threshold),
            medium_threshold=float(args.plddt_medium_threshold),
            min_threshold=float(args.plddt_min_threshold),
        )

        include = True
        reasons: List[str] = []
        if parsed.ca_residues < int(args.min_ca_residues):
            include = False
            reasons.append("low_ca_residue_count")
        if expected_n_res is not None and expected_n_res > 0:
            cov = float(parsed.ca_residues) / float(expected_n_res)
            if cov < float(args.min_ca_coverage):
                include = False
                reasons.append("low_ca_coverage")
        if has_plddt:
            if pstats["mean"] is None or pstats["p10"] is None:
                include = False
                reasons.append("missing_plddt")
            else:
                if pstats["mean"] < float(args.plddt_medium_threshold):
                    include = False
                    reasons.append("low_plddt_mean")
                if pstats["p10"] < float(args.plddt_min_threshold):
                    include = False
                    reasons.append("low_plddt_p10")

        weight = _resolve_weight(tier=tier, has_plddt=has_plddt, include=include, args=args)
        row = {
            "target": target_guess,
            "source_file": parsed.path,
            "source_kind": source_kind,
            "total_atoms": int(parsed.total_atoms),
            "ca_atoms": int(parsed.ca_atoms),
            "ca_residues": int(parsed.ca_residues),
            "expected_n_res": int(expected_n_res) if expected_n_res is not None else None,
            "ca_coverage": (
                float(parsed.ca_residues) / float(expected_n_res)
                if expected_n_res not in (None, 0)
                else None
            ),
            "has_plddt": int(has_plddt),
            "plddt_mean": pstats["mean"],
            "plddt_p10": pstats["p10"],
            "plddt_min": pstats["min"],
            "plddt_max": pstats["max"],
            "quality_tier": tier if has_plddt else "experimental_or_unknown",
            "include": int(include),
            "sample_weight": float(weight),
            "exclude_reason": "|".join(reasons) if reasons else "ok",
        }
        rows.append(row)

    summary = {
        "total_files_scanned": int(len(candidates)),
        "rows": int(len(rows)),
        "included": int(sum(int(r["include"]) for r in rows)),
        "excluded": int(sum(1 - int(r["include"]) for r in rows)),
        "afdb_like_rows": int(sum(1 for r in rows if str(r["source_kind"]).startswith("afdb"))),
        "experimental_rows": int(sum(1 for r in rows if r["source_kind"] == "pdb_or_other")),
        "mean_weight_included": (
            float(np.mean([r["sample_weight"] for r in rows if int(r["include"]) == 1]))
            if any(int(r["include"]) == 1 for r in rows)
            else 0.0
        ),
        "thresholds": {
            "min_ca_residues": int(args.min_ca_residues),
            "min_ca_coverage": float(args.min_ca_coverage),
            "plddt_medium_threshold": float(args.plddt_medium_threshold),
            "plddt_high_threshold": float(args.plddt_high_threshold),
            "plddt_min_threshold": float(args.plddt_min_threshold),
        },
        "input_mode": input_meta["input_mode"],
        "manifest_csv": input_meta["manifest_csv"],
        "manifest_rows": int(input_meta["manifest_rows"]),
        "missing_files_from_manifest": int(input_meta["missing_files_from_manifest"]),
        "missing_file_examples": list(input_meta["missing_file_examples"]),
    }
    return rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Curate PDB/AFDB structures with conservative pLDDT-based filtering and sample weighting."
        )
    )
    parser.add_argument(
        "--pdb-glob",
        action="append",
        default=None,
        help="Glob pattern for candidate PDB files. Repeatable. Ignored when --manifest-csv is set.",
    )
    parser.add_argument(
        "--pdb-file",
        action="append",
        default=[],
        help="Explicit PDB file path. Repeatable. Ignored when --manifest-csv is set.",
    )
    parser.add_argument(
        "--manifest-csv",
        type=str,
        default=None,
        help="Optional manifest CSV containing explicit structure paths (default path column: path).",
    )
    parser.add_argument("--manifest-path-col", type=str, default="path")
    parser.add_argument("--manifest-target-col", type=str, default="target")
    parser.add_argument("--manifest-source-kind-col", type=str, default="source_kind")
    parser.add_argument(
        "--targets",
        type=str,
        default=None,
        help="Optional target CSV filter (e.g. Chignolin,Trp_Cage).",
    )
    parser.add_argument("--min-ca-residues", type=int, default=8)
    parser.add_argument("--min-ca-coverage", type=float, default=0.90)
    parser.add_argument("--plddt-medium-threshold", type=float, default=70.0)
    parser.add_argument("--plddt-high-threshold", type=float, default=90.0)
    parser.add_argument("--plddt-min-threshold", type=float, default=50.0)
    parser.add_argument(
        "--allow-bfactor-as-plddt",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="If true, non-AFDB files with B-factor in [0,100] are treated as pLDDT-like.",
    )
    parser.add_argument("--weight-high", type=float, default=1.0)
    parser.add_argument("--weight-medium", type=float, default=0.6)
    parser.add_argument("--weight-low", type=float, default=0.2)
    parser.add_argument("--experimental-weight", type=float, default=1.0)
    parser.add_argument("--out-csv", type=str, default="runs/structure_quality_curated.csv")
    parser.add_argument("--out-json", type=str, default="runs/structure_quality_curated.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    rows, summary = curate_structure_rows(args)

    out_csv = str(args.out_csv)
    out_json = str(args.out_json)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    payload = {"summary": summary, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"Wrote CSV: {out_csv}")
    print(f"Wrote JSON: {out_json}")


if __name__ == "__main__":
    main()
