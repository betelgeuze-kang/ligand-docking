#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def _default_rows() -> List[Dict[str, str]]:
    return [
        {
            "target": "KRAS_G12D",
            "pdb_id": "6OIM",
            "native_pdb_path": "data/native/kras_g12d.pdb",
            "pdb_url": "https://files.rcsb.org/download/6OIM.pdb",
            "notes": "KRAS druggable pocket benchmark",
        },
        {
            "target": "EGFR_KINASE",
            "pdb_id": "1M17",
            "native_pdb_path": "data/native/egfr_kinase.pdb",
            "pdb_url": "https://files.rcsb.org/download/1M17.pdb",
            "notes": "EGFR kinase domain benchmark",
        },
        {
            "target": "HIV1_PROTEASE",
            "pdb_id": "1HVR",
            "native_pdb_path": "data/native/hiv1_protease.pdb",
            "pdb_url": "https://files.rcsb.org/download/1HVR.pdb",
            "notes": "HIV-1 protease benchmark",
        },
    ]


def _write_atomic(path: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dl_", suffix=".tmp", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _download(url: str, timeout_sec: float) -> bytes:
    req = urllib.request.Request(str(url).strip(), headers={"User-Agent": "md-real-targets/1.0"})
    with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
        data = resp.read()
    if len(data) <= 0:
        raise RuntimeError(f"empty payload: {url}")
    return data


def run_prepare(args: argparse.Namespace) -> Dict[str, Any]:
    src = str(args.sources_csv).strip()
    if src and os.path.exists(src):
        df = pd.read_csv(src)
    else:
        df = pd.DataFrame(_default_rows())
    if "target" not in df.columns:
        raise ValueError("sources csv requires 'target' column")
    for col in ("pdb_id", "native_pdb_path"):
        if col not in df.columns:
            df[col] = ""
    if "pdb_url" not in df.columns:
        df["pdb_url"] = ""

    rows: List[Dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        target = str(row.get("target", "")).strip()
        pdb_id = str(row.get("pdb_id", "")).strip().upper()
        out_path = str(row.get("native_pdb_path", "")).strip()
        url = str(row.get("pdb_url", "")).strip() or (f"https://files.rcsb.org/download/{pdb_id}.pdb" if pdb_id else "")
        if (not target) or (not out_path) or (not url):
            rows.append(
                {
                    "target": target,
                    "pdb_id": pdb_id,
                    "native_pdb_path": out_path,
                    "status": "skipped_invalid_row",
                    "bytes": 0,
                    "error": "missing target/native_pdb_path/url",
                }
            )
            continue
        if os.path.exists(out_path) and (not bool(args.overwrite)):
            rows.append(
                {
                    "target": target,
                    "pdb_id": pdb_id,
                    "native_pdb_path": out_path,
                    "status": "exists",
                    "bytes": int(os.path.getsize(out_path)),
                    "error": "",
                }
            )
            continue
        if bool(args.dry_run):
            rows.append(
                {
                    "target": target,
                    "pdb_id": pdb_id,
                    "native_pdb_path": out_path,
                    "status": "dry_run",
                    "bytes": 0,
                    "error": "",
                }
            )
            continue
        try:
            payload = _download(url=url, timeout_sec=float(args.timeout_sec))
            _write_atomic(path=out_path, payload=payload)
            rows.append(
                {
                    "target": target,
                    "pdb_id": pdb_id,
                    "native_pdb_path": out_path,
                    "status": "downloaded",
                    "bytes": int(len(payload)),
                    "error": "",
                }
            )
        except urllib.error.HTTPError as exc:
            rows.append(
                {
                    "target": target,
                    "pdb_id": pdb_id,
                    "native_pdb_path": out_path,
                    "status": "failed",
                    "bytes": 0,
                    "error": f"http_{int(exc.code)}",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "target": target,
                    "pdb_id": pdb_id,
                    "native_pdb_path": out_path,
                    "status": "failed",
                    "bytes": 0,
                    "error": str(exc),
                }
            )

    out_csv = str(args.out_csv).strip() or f"runs/real_drug_targets_prepare_{dt.date.today().isoformat()}.csv"
    out_json = str(args.out_json).strip() or f"runs/real_drug_targets_prepare_{dt.date.today().isoformat()}.json"
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(rows)),
        "downloaded": int(sum(1 for r in rows if r.get("status") == "downloaded")),
        "exists": int(sum(1 for r in rows if r.get("status") == "exists")),
        "failed": int(sum(1 for r in rows if r.get("status") == "failed")),
        "out_csv": out_csv,
    }
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Download real drug-target PDBs and materialize to data/native/*.pdb")
    p.add_argument("--sources-csv", type=str, default="config/real_drug_targets_native_v1.csv")
    p.add_argument("--timeout-sec", type=float, default=30.0)
    p.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-csv", type=str, default=f"runs/real_drug_targets_prepare_{stamp}.csv")
    p.add_argument("--out-json", type=str, default=f"runs/real_drug_targets_prepare_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_prepare(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
