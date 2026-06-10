#!/usr/bin/env python3
"""Enrich residual supervised dataset rows with refine-tier labels from stage3 scoring."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def enrich_refine_tier_labels(
    *,
    input_csv: str | Path,
    stage3_csv: str | Path,
    out_csv: str | Path,
) -> dict[str, Any]:
    stage3_path = _resolve(stage3_csv)
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if stage3_path.exists():
        with stage3_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                target = str(raw.get("target") or "").strip()
                ligand_id = str(raw.get("ligand_id") or "").strip()
                if not target or not ligand_id:
                    continue
                base = _float(raw.get("binding_energy_mmpbsa_kcal_mol_proxy"))
                refined = _float(raw.get("deltaG_mm_gbsa_kcal_mol")) or _float(
                    raw.get("binding_energy_explicit_water_recheck_kcal_mol_proxy")
                )
                lookup[(target, ligand_id)] = {
                    "base_proxy": base,
                    "refined": refined,
                    "refine_confidence": _float(raw.get("physics_refinement_confidence")),
                    "ligand_model": str(raw.get("ligand_model") or ""),
                }

    in_path = _resolve(input_csv)
    rows: list[dict[str, Any]] = []
    enriched = 0
    with in_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        for extra in (
            "refine_tier_label",
            "refine_tier_label_source",
            "refine_tier_delta",
            "mm_gbsa_delta",
            "refine_confidence",
        ):
            if extra not in fieldnames:
                fieldnames.append(extra)
        for raw in reader:
            row = dict(raw)
            target = str(row.get("target") or "").strip()
            ligand_id = str(row.get("ligand_id") or "").strip()
            meta = lookup.get((target, ligand_id))
            if meta and meta.get("refined") is not None:
                row["refine_tier_label"] = meta["refined"]
                row["refine_tier_label_source"] = "stage3_refine_tier"
                base = meta.get("base_proxy")
                if base is not None:
                    row["mm_gbsa_delta"] = float(meta["refined"]) - float(base)
                    row["refine_tier_delta"] = row["mm_gbsa_delta"]
                if meta.get("refine_confidence") is not None:
                    row["refine_confidence"] = meta["refine_confidence"]
                enriched += 1
            rows.append(row)

    out_path = _resolve(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return {
        "status": "refine_tier_enrichment_ready",
        "input_csv": str(in_path),
        "stage3_csv": str(stage3_path),
        "out_csv": str(out_path),
        "row_count": len(rows),
        "refine_tier_label_rows": enriched,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Enrich residual dataset with refine-tier labels from stage3 CSV.")
    p.add_argument("--input-csv", required=True)
    p.add_argument("--stage3-csv", required=True)
    p.add_argument("--out-csv", required=True)
    args = p.parse_args()
    summary = enrich_refine_tier_labels(
        input_csv=args.input_csv,
        stage3_csv=args.stage3_csv,
        out_csv=args.out_csv,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
