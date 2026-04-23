#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


DOMAIN_SOURCE_MAP: Dict[str, str] = {
    "metal": "config/structure_sources_special_metal.csv",
    "dna": "config/structure_sources_special_dna.csv",
    "membrane": "config/structure_sources_special_membrane.csv",
}


def _normalize_domain(raw: str) -> str:
    d = str(raw).strip().lower()
    if d not in DOMAIN_SOURCE_MAP:
        raise ValueError(f"unsupported domain: {raw} (allowed: {sorted(DOMAIN_SOURCE_MAP.keys())})")
    return d


def _parse_targets(spec: str) -> Optional[List[str]]:
    s = str(spec).strip()
    if (not s) or (s.lower() == "all"):
        return None
    out: List[str] = []
    seen = set()
    for token in s.split(","):
        t = str(token).strip()
        if (not t) or (t in seen):
            continue
        seen.add(t)
        out.append(t)
    return out


def run_build(args: argparse.Namespace) -> Dict[str, Any]:
    domain = _normalize_domain(str(args.domain))
    source_csv = str(args.source_csv).strip() or DOMAIN_SOURCE_MAP[domain]
    if not os.path.exists(source_csv):
        raise FileNotFoundError(f"source csv not found: {source_csv}")

    df = pd.read_csv(source_csv)
    required = ["target", "pdb_id", "uniprot_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"source csv missing required columns: {missing}")

    selected = _parse_targets(str(args.targets))
    work = df.copy()
    if selected is not None:
        work = work[work["target"].astype(str).isin(selected)].copy()

    if "notes" not in work.columns:
        work["notes"] = ""
    work["domain"] = domain

    out_manifest = str(args.out_manifest)
    out_json = str(args.out_json)
    os.makedirs(os.path.dirname(out_manifest) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)

    cols = ["domain", "target", "pdb_id", "uniprot_id", "notes"]
    out_df = work.reindex(columns=cols).copy()
    out_df.to_csv(out_manifest, index=False)

    rows_emitted = int(out_df.shape[0])
    if bool(args.strict_fail) and rows_emitted <= 0:
        raise RuntimeError(f"no rows emitted for domain={domain} targets={args.targets}")

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "domain": domain,
            "targets": str(args.targets),
            "source_csv": source_csv,
        },
        "summary": {
            "domain": domain,
            "rows_source": int(df.shape[0]),
            "rows_emitted": rows_emitted,
            "targets_emitted": sorted(out_df["target"].astype(str).unique().tolist()),
        },
        "artifacts": {
            "manifest_csv": out_manifest,
            "summary_json": out_json,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description="Build special-case source manifest for domain-specific pipelines."
    )
    p.add_argument("--domain", type=str, required=True, choices=sorted(DOMAIN_SOURCE_MAP.keys()))
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--source-csv", type=str, default="")
    p.add_argument(
        "--out-manifest",
        type=str,
        default=f"runs/special_case_manifest_{stamp}.csv",
    )
    p.add_argument(
        "--out-json",
        type=str,
        default=f"runs/special_case_manifest_{stamp}.json",
    )
    p.add_argument("--strict-fail", action=argparse.BooleanOptionalAction, default=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote manifest: {payload['artifacts']['manifest_csv']}")
    print(f"Wrote summary: {payload['artifacts']['summary_json']}")


if __name__ == "__main__":
    main()
