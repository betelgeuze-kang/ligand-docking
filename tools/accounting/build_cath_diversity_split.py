#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import urllib.request
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd


DEFAULT_CATH_DOMAIN_LIST_URL = (
    "https://download.cathdb.info/cath/releases/latest-release/"
    "cath-classification-data/cath-domain-list.txt"
)
DEFAULT_CATH_S40_URL = (
    "https://download.cathdb.info/cath/releases/latest-release/"
    "non-redundant-data-sets/cath-dataset-nonredundant-S40.list"
)


def _download_text(url: str, timeout_sec: float) -> str:
    with urllib.request.urlopen(str(url), timeout=float(timeout_sec)) as resp:
        payload = resp.read()
    if len(payload) == 0:
        raise RuntimeError(f"empty payload: {url}")
    return payload.decode("utf-8", errors="ignore")


def _to_int(raw: str, default: int = 0) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _to_float(raw: str, default: float = 999.0) -> float:
    try:
        return float(raw)
    except Exception:
        return float(default)


def _parse_domain_list(text: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        ln = str(line).strip()
        if not ln or ln.startswith("#"):
            continue
        toks = ln.split()
        if len(toks) < 12:
            continue
        domain_id = str(toks[0]).strip()
        if len(domain_id) < 4:
            continue
        pdb_id = domain_id[:4].upper()
        rows.append(
            {
                "domain_id": domain_id,
                "pdb_id": pdb_id,
                "class_id": _to_int(toks[1], 0),
                "architecture_id": _to_int(toks[2], 0),
                "topology_id": _to_int(toks[3], 0),
                "homology_id": _to_int(toks[4], 0),
                "residues": _to_int(toks[10], 0),
                "resolution": _to_float(toks[11], 999.0),
            }
        )
    if len(rows) == 0:
        raise RuntimeError("no parsable rows from CATH domain list")
    return rows


def _parse_domain_set(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        ln = str(line).strip()
        if ln and not ln.startswith("#"):
            out.add(ln)
    return out


def _quality_key(row: Dict[str, Any]) -> Tuple[int, float, int, str]:
    resolution = float(row.get("resolution", 999.0))
    residues = int(row.get("residues", 0) or 0)
    has_valid_resolution = 1 if resolution < 50.0 else 0
    return (
        -has_valid_resolution,  # valid resolution first
        resolution,             # smaller better
        -residues,              # longer domain first when comparable
        str(row.get("domain_id", "")),
    )


def _cat_key(row: Dict[str, Any]) -> Tuple[int, int, int]:
    return (
        int(row.get("class_id", 0) or 0),
        int(row.get("architecture_id", 0) or 0),
        int(row.get("topology_id", 0) or 0),
    )


def _pick_representatives_per_cat(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_cat: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cat[_cat_key(row)].append(dict(row))
    reps: List[Dict[str, Any]] = []
    for key, grp in by_cat.items():
        rep = sorted(grp, key=_quality_key)[0]
        rep = dict(rep)
        rep["cat_key"] = f"{key[0]}.{key[1]}.{key[2]}"
        reps.append(rep)
    return reps


def _select_balanced(
    rows: Sequence[Dict[str, Any]],
    total: int,
    allow_duplicate_pdb: bool,
) -> List[Dict[str, Any]]:
    by_class: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_class[int(row.get("class_id", 0) or 0)].append(dict(row))
    for cls, grp in by_class.items():
        by_class[cls] = sorted(grp, key=_quality_key)

    classes = sorted(by_class.keys())
    if len(classes) == 0:
        return []

    quotas: Dict[int, int] = {c: 0 for c in classes}
    base = int(total) // int(len(classes))
    for c in classes:
        quotas[c] = min(base, len(by_class[c]))
    remaining = int(total) - int(sum(quotas.values()))

    while remaining > 0:
        progressed = False
        for c in classes:
            if quotas[c] < len(by_class[c]):
                quotas[c] += 1
                remaining -= 1
                progressed = True
                if remaining <= 0:
                    break
        if not progressed:
            break

    selected: List[Dict[str, Any]] = []
    for c in classes:
        selected.extend(by_class[c][: quotas[c]])
    selected = sorted(selected, key=_quality_key)

    if not allow_duplicate_pdb:
        unique_selected: List[Dict[str, Any]] = []
        used_pdb: set[str] = set()
        for row in selected:
            pdb_id = str(row.get("pdb_id", "")).upper()
            if not pdb_id or pdb_id in used_pdb:
                continue
            used_pdb.add(pdb_id)
            unique_selected.append(row)
        selected = unique_selected

        if len(selected) < total:
            extras = sorted(rows, key=_quality_key)
            for row in extras:
                if len(selected) >= total:
                    break
                pdb_id = str(row.get("pdb_id", "")).upper()
                if not pdb_id or pdb_id in used_pdb:
                    continue
                used_pdb.add(pdb_id)
                selected.append(dict(row))

    if len(selected) > total:
        selected = selected[:total]
    return selected


def _split_counts(n: int, train_ratio: float, val_ratio: float) -> Tuple[int, int, int]:
    n = int(max(0, n))
    if n <= 0:
        return 0, 0, 0
    if n == 1:
        return 1, 0, 0
    if n == 2:
        return 1, 0, 1

    n_train = int(round(n * float(train_ratio)))
    n_val = int(round(n * float(val_ratio)))
    n_train = max(1, min(n - 2, n_train))
    n_val = max(1, min(n - n_train - 1, n_val))
    n_hold = n - n_train - n_val
    if n_hold < 1:
        n_train = max(1, n_train - 1)
        n_hold = n - n_train - n_val
    if n_hold < 1:
        n_val = max(1, n_val - 1)
        n_hold = n - n_train - n_val
    return int(n_train), int(n_val), int(max(0, n_hold))


def _assign_splits(
    rows: Sequence[Dict[str, Any]],
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> List[Dict[str, Any]]:
    rng = random.Random(int(seed))
    by_class: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_class[int(row.get("class_id", 0) or 0)].append(dict(row))

    out: List[Dict[str, Any]] = []
    for cls in sorted(by_class.keys()):
        grp = by_class[cls]
        rng.shuffle(grp)
        n_train, n_val, _n_hold = _split_counts(
            n=len(grp),
            train_ratio=float(train_ratio),
            val_ratio=float(val_ratio),
        )
        for idx, row in enumerate(grp):
            if idx < n_train:
                split = "train"
            elif idx < (n_train + n_val):
                split = "val"
            else:
                split = "holdout"
            x = dict(row)
            x["split"] = split
            out.append(x)
    return out


def _to_target_name(domain_id: str) -> str:
    return f"CATH_{str(domain_id)}"


def build_cath_diversity_split(
    out_sources_csv: str,
    out_split_csv: str,
    out_summary_json: str,
    target_count: int = 100,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 20260219,
    cath_domain_list_url: str = DEFAULT_CATH_DOMAIN_LIST_URL,
    cath_s40_url: str = DEFAULT_CATH_S40_URL,
    timeout_sec: float = 45.0,
    use_s40_filter: bool = True,
    allow_duplicate_pdb: bool = False,
) -> Dict[str, Any]:
    domain_text = _download_text(str(cath_domain_list_url), timeout_sec=float(timeout_sec))
    raw_rows = _parse_domain_list(domain_text)

    filtered_rows = list(raw_rows)
    s40_count = 0
    if bool(use_s40_filter):
        s40_text = _download_text(str(cath_s40_url), timeout_sec=float(timeout_sec))
        s40_set = _parse_domain_set(s40_text)
        s40_count = int(len(s40_set))
        filtered_rows = [row for row in filtered_rows if str(row.get("domain_id", "")) in s40_set]

    reps = _pick_representatives_per_cat(filtered_rows)
    selected = _select_balanced(
        rows=reps,
        total=int(target_count),
        allow_duplicate_pdb=bool(allow_duplicate_pdb),
    )
    split_rows = _assign_splits(
        rows=selected,
        train_ratio=float(train_ratio),
        val_ratio=float(val_ratio),
        seed=int(seed),
    )

    if len(split_rows) == 0:
        raise RuntimeError("failed to build any CATH selection rows")

    os.makedirs(os.path.dirname(out_sources_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_split_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_summary_json) or ".", exist_ok=True)

    source_rows: List[Dict[str, Any]] = []
    split_csv_rows: List[Dict[str, Any]] = []
    for row in split_rows:
        domain_id = str(row.get("domain_id", ""))
        target = _to_target_name(domain_id)
        source_rows.append(
            {
                "target": target,
                "pdb_id": str(row.get("pdb_id", "")).upper(),
                "uniprot_id": "",
                "notes": "cath_diversity_representative",
                "cath_domain_id": domain_id,
                "cath_class": int(row.get("class_id", 0) or 0),
                "cath_architecture": int(row.get("architecture_id", 0) or 0),
                "cath_topology": int(row.get("topology_id", 0) or 0),
                "cath_homology": int(row.get("homology_id", 0) or 0),
                "cath_residues": int(row.get("residues", 0) or 0),
                "cath_resolution": float(row.get("resolution", 999.0) or 999.0),
            }
        )
        split_csv_rows.append(
            {
                "target": target,
                "split": str(row.get("split", "")),
                "pdb_id": str(row.get("pdb_id", "")).upper(),
                "cath_domain_id": domain_id,
                "cath_class": int(row.get("class_id", 0) or 0),
                "cath_architecture": int(row.get("architecture_id", 0) or 0),
                "cath_topology": int(row.get("topology_id", 0) or 0),
                "cath_homology": int(row.get("homology_id", 0) or 0),
                "cath_residues": int(row.get("residues", 0) or 0),
                "cath_resolution": float(row.get("resolution", 999.0) or 999.0),
            }
        )

    source_df = pd.DataFrame(source_rows).sort_values(
        by=["cath_class", "cath_architecture", "cath_topology", "cath_domain_id"]
    )
    split_df = pd.DataFrame(split_csv_rows).sort_values(
        by=["split", "cath_class", "cath_architecture", "cath_topology", "cath_domain_id"]
    )
    source_df.to_csv(out_sources_csv, index=False)
    split_df.to_csv(out_split_csv, index=False)

    split_counts = (
        split_df.groupby("split")["target"].count().to_dict()
        if len(split_df)
        else {}
    )
    class_counts = (
        split_df.groupby("cath_class")["target"].count().to_dict()
        if len(split_df)
        else {}
    )
    summary: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "cath_domain_list_url": str(cath_domain_list_url),
            "cath_s40_url": str(cath_s40_url),
            "use_s40_filter": bool(use_s40_filter),
            "allow_duplicate_pdb": bool(allow_duplicate_pdb),
            "target_count": int(target_count),
            "train_ratio": float(train_ratio),
            "val_ratio": float(val_ratio),
            "holdout_ratio": float(max(0.0, 1.0 - float(train_ratio) - float(val_ratio))),
            "seed": int(seed),
            "timeout_sec": float(timeout_sec),
        },
        "counts": {
            "raw_domain_rows": int(len(raw_rows)),
            "s40_domain_rows": int(s40_count),
            "filtered_rows": int(len(filtered_rows)),
            "cat_representatives": int(len(reps)),
            "selected_rows": int(len(split_df)),
            "unique_pdb_ids": int(split_df["pdb_id"].nunique()) if len(split_df) else 0,
            "split_counts": {str(k): int(v) for k, v in split_counts.items()},
            "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        },
        "outputs": {
            "sources_csv": out_sources_csv,
            "split_csv": out_split_csv,
            "summary_json": out_summary_json,
        },
    }
    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Build a CATH-diverse representative set and stratified split "
            "(train/val/holdout) for overfitting/OOD validation."
        )
    )
    p.add_argument("--out-sources-csv", type=str, default="config/cath_sources_100.csv")
    p.add_argument("--out-split-csv", type=str, default="runs/cath_diversity_100_split.csv")
    p.add_argument("--out-summary-json", type=str, default="runs/cath_diversity_100_summary.json")
    p.add_argument("--target-count", type=int, default=100)
    p.add_argument("--train-ratio", type=float, default=0.7)
    p.add_argument("--val-ratio", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=20260219)
    p.add_argument("--cath-domain-list-url", type=str, default=DEFAULT_CATH_DOMAIN_LIST_URL)
    p.add_argument("--cath-s40-url", type=str, default=DEFAULT_CATH_S40_URL)
    p.add_argument("--timeout-sec", type=float, default=45.0)
    p.add_argument("--use-s40-filter", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--allow-duplicate-pdb", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    summary = build_cath_diversity_split(
        out_sources_csv=str(args.out_sources_csv),
        out_split_csv=str(args.out_split_csv),
        out_summary_json=str(args.out_summary_json),
        target_count=int(args.target_count),
        train_ratio=float(args.train_ratio),
        val_ratio=float(args.val_ratio),
        seed=int(args.seed),
        cath_domain_list_url=str(args.cath_domain_list_url),
        cath_s40_url=str(args.cath_s40_url),
        timeout_sec=float(args.timeout_sec),
        use_s40_filter=bool(args.use_s40_filter),
        allow_duplicate_pdb=bool(args.allow_duplicate_pdb),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
