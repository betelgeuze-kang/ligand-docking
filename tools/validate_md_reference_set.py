#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _target_map() -> Dict[str, str]:
    return {_normalize_target_key(k): k for k in ResearchConstants.CHALLENGES.keys()}


def _matches_md_engine(engine: str, pattern: str) -> bool:
    if engine is None:
        return False
    return re.search(pattern, str(engine), flags=re.IGNORECASE) is not None


def _normalize_representation(raw: Any) -> str:
    s = str(raw).strip().lower()
    if not s:
        return "ca"
    if s in ("ca", "ca_only", "ca_bead"):
        return "ca"
    if s in ("ca_sc_2bead", "ca_sc", "2bead", "two_bead", "ca_sc_explicit"):
        return "ca_sc_2bead"
    return "ca"


def _coerce_coords_array(arr: np.ndarray, frame: int = -1) -> np.ndarray:
    a = np.asarray(arr)
    if a.ndim == 3:
        idx = int(frame)
        if idx < 0:
            idx = a.shape[0] - 1
        if idx >= a.shape[0]:
            raise ValueError(f"Requested frame index {idx} out of range for shape {a.shape}")
        a = a[idx]
    if a.ndim != 2:
        raise ValueError(f"Coordinate array must be [N,3] or [T,N,3], got shape {a.shape}")
    if a.shape[1] != 3 and a.shape[0] == 3:
        a = a.T
    if a.shape[1] != 3:
        raise ValueError(f"Coordinate array must have 3 columns, got shape {a.shape}")
    return a


def _load_coords_csv(path: str, frame: int = -1) -> np.ndarray:
    df = pd.read_csv(path)
    cols = set(df.columns)
    xyz_sets = [
        ("x", "y", "z"),
        ("coord_x", "coord_y", "coord_z"),
        ("X", "Y", "Z"),
    ]
    xyz = None
    for cset in xyz_sets:
        if set(cset).issubset(cols):
            xyz = cset
            break
    if xyz is None:
        raise ValueError(f"CSV reference {path} must include xyz columns (x/y/z or coord_x/y/z)")

    use_df = df
    if "frame" in use_df.columns:
        if int(frame) < 0:
            selected = int(use_df["frame"].max())
        else:
            selected = int(frame)
        use_df = use_df[use_df["frame"] == selected]
        if use_df.empty:
            raise ValueError(f"CSV reference {path} has no rows for frame={selected}")
    arr = use_df.loc[:, list(xyz)].to_numpy(dtype=np.float32)
    return _coerce_coords_array(arr, frame=-1)


def _load_coords(path: str, key: Optional[str] = None, frame: int = -1) -> np.ndarray:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npy":
        arr = np.load(path, mmap_mode="r")
        return _coerce_coords_array(arr, frame=frame)
    if ext == ".npz":
        z = np.load(path)
        if key:
            if key not in z:
                raise KeyError(f"Key '{key}' not found in {path}. Available: {list(z.keys())}")
            arr = z[key]
        else:
            if len(z.files) == 0:
                raise ValueError(f"NPZ file {path} has no arrays.")
            arr = z[z.files[0]]
        return _coerce_coords_array(arr, frame=frame)
    if ext == ".csv":
        return _load_coords_csv(path, frame=frame)
    raise ValueError(f"Unsupported coordinate file extension: {ext} (path={path})")


def _validate_row(row: Dict[str, Any], md_engine_regex: str, key_col: str = "key") -> Dict[str, Any]:
    target_raw = str(row.get("target", "")).strip()
    path_raw = str(row.get("path", "")).strip()
    engine_raw = str(row.get("engine", "")).strip()
    label_raw = str(row.get("label", "")).strip()
    representation_raw = row.get("representation", "")
    representation = _normalize_representation(representation_raw)
    frame_raw = row.get("frame", -1)
    key_raw = row.get(key_col, None)

    reasons: List[str] = []
    exists = bool(path_raw) and os.path.exists(path_raw)
    engine_ok = _matches_md_engine(engine_raw, md_engine_regex)
    if not target_raw:
        reasons.append("missing_target")
    if not path_raw:
        reasons.append("missing_path")
    if not engine_ok:
        reasons.append("engine_not_md")
    if path_raw and not exists:
        reasons.append("missing_file")

    expected_n_res = None
    n_res_ok = False
    shape_ok = False
    n_atoms = None
    load_ok = False
    expected_beads_per_residue = 2 if representation == "ca_sc_2bead" else 1
    expected_n_atoms = None

    if target_raw:
        tmap = _target_map()
        mapped = tmap.get(_normalize_target_key(target_raw), None)
        if mapped is None:
            reasons.append("unknown_target")
        else:
            expected_n_res = int(ResearchConstants.CHALLENGES[mapped]["n_res"])
            expected_n_atoms = int(expected_n_res) * int(expected_beads_per_residue)

    if exists and path_raw:
        try:
            frame_i = int(frame_raw) if frame_raw is not None else -1
            key_i = str(key_raw) if key_raw is not None and str(key_raw).strip() else None
            coords = _load_coords(path_raw, key=key_i, frame=frame_i)
            load_ok = True
            shape_ok = True
            n_atoms = int(coords.shape[0])
            if expected_n_res is None:
                reasons.append("expected_n_res_unknown")
            else:
                n_res_ok = int(n_atoms) == int(expected_n_atoms)
                if not n_res_ok:
                    reasons.append("n_res_mismatch")
        except Exception as exc:
            reasons.append(f"load_error:{type(exc).__name__}")
            load_ok = False
            shape_ok = False

    row_ok = (
        len(reasons) == 0
        and exists
        and load_ok
        and shape_ok
        and n_res_ok
        and engine_ok
    )
    return {
        "target": target_raw,
        "path": path_raw,
        "engine": engine_raw,
        "label": label_raw,
        "representation": representation,
        "frame": frame_raw,
        "exists": bool(exists),
        "engine_is_md": bool(engine_ok),
        "load_ok": bool(load_ok),
        "shape_ok": bool(shape_ok),
        "n_atoms": n_atoms,
        "expected_n_res": expected_n_res,
        "expected_beads_per_residue": int(expected_beads_per_residue),
        "expected_n_atoms": expected_n_atoms,
        "n_res_ok": bool(n_res_ok),
        "row_ok": bool(row_ok),
        "reasons": reasons,
    }


def validate_md_reference_set(
    manifest_csv: str,
    out_json: str,
    out_csv: str,
    md_engine_regex: str,
    expected_target_count: int,
    strict: bool,
) -> Dict[str, Any]:
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"manifest not found: {manifest_csv}")
    df = pd.read_csv(manifest_csv)
    if "target" not in df.columns or "path" not in df.columns:
        raise ValueError("manifest must include columns: target, path")
    if "engine" not in df.columns:
        df["engine"] = ""

    results = [_validate_row(dict(row), md_engine_regex=md_engine_regex) for row in df.to_dict(orient="records")]
    res_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    res_df.to_csv(out_csv, index=False)

    target_ok: Dict[str, bool] = {}
    for _, r in res_df.iterrows():
        target = str(r.get("target", "")).strip()
        if not target:
            continue
        current = bool(r.get("row_ok", False))
        target_ok[target] = bool(target_ok.get(target, True) and current)

    failed_rows = []
    for _, r in res_df.iterrows():
        if bool(r.get("row_ok", False)):
            continue
        reasons_val = r.get("reasons")
        if isinstance(reasons_val, list):
            reasons = [str(x) for x in reasons_val]
        elif reasons_val is None:
            reasons = []
        else:
            reasons = [str(reasons_val)]
        failed_rows.append(
            {
                "target": str(r.get("target", "")).strip(),
                "path": str(r.get("path", "")).strip(),
                "reasons": reasons,
            }
        )

    md_rows = res_df[res_df["engine_is_md"] == True] if not res_df.empty else pd.DataFrame()
    md_ok_rows = md_rows[md_rows["row_ok"] == True] if not md_rows.empty else pd.DataFrame()
    md_targets = set(md_rows["target"].astype(str).tolist()) if not md_rows.empty else set()
    md_ok_targets = set(md_ok_rows["target"].astype(str).tolist()) if not md_ok_rows.empty else set()

    summary: Dict[str, Any] = {
        "manifest_csv": manifest_csv,
        "out_csv": out_csv,
        "row_count": int(len(res_df)),
        "target_count": int(len(set(res_df["target"].astype(str).tolist()))) if not res_df.empty else 0,
        "existing_rows": int(res_df["exists"].sum()) if not res_df.empty else 0,
        "load_ok_rows": int(res_df["load_ok"].sum()) if not res_df.empty else 0,
        "shape_ok_rows": int(res_df["shape_ok"].sum()) if not res_df.empty else 0,
        "n_res_ok_rows": int(res_df["n_res_ok"].sum()) if not res_df.empty else 0,
        "row_ok_rows": int(res_df["row_ok"].sum()) if not res_df.empty else 0,
        "md_engine_regex": md_engine_regex,
        "md_rows": int(len(md_rows)),
        "md_ok_rows": int(len(md_ok_rows)),
        "md_targets": int(len(md_targets)),
        "md_ok_targets": int(len(md_ok_targets)),
        "expected_target_count": int(expected_target_count),
        "failed_targets": sorted([k for k, v in target_ok.items() if not v]),
        "failed_rows": failed_rows,
    }
    summary["ready"] = bool(summary["md_ok_targets"] >= int(expected_target_count) and len(summary["failed_targets"]) == 0)

    payload = {"summary": summary}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if strict and not bool(summary["ready"]):
        raise RuntimeError(
            f"MD reference validation failed: md_ok_targets={summary['md_ok_targets']} "
            f"expected={summary['expected_target_count']} failed_targets={summary['failed_targets']}"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate MD reference manifest paths, coordinate shape, and residue-count compatibility."
    )
    parser.add_argument("--manifest-csv", type=str, default="runs/external_ref_manifest_md_template.csv")
    parser.add_argument("--out-json", type=str, default="runs/md_reference_validation.json")
    parser.add_argument("--out-csv", type=str, default="runs/md_reference_validation.csv")
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = validate_md_reference_set(
            manifest_csv=str(args.manifest_csv),
            out_json=str(args.out_json),
            out_csv=str(args.out_csv),
            md_engine_regex=str(args.md_engine_regex),
            expected_target_count=int(args.expected_target_count),
            strict=bool(args.strict),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
