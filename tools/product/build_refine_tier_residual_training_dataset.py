#!/usr/bin/env python3
"""Enrich residual supervised dataset rows with refine-tier labels from stage3 scoring."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_QUEUE_ID_RE = re.compile(r"^(?P<target>.+?)__rep\d+__(?P<ligand>.+)$")
_TARGET_ALIASES = {
    "ADRB2": "ADRB2_GPCR_BLIND",
    "ADRB2_GPCR": "ADRB2_GPCR_BLIND",
}


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


def _normalize_target(target: str) -> str:
    t = str(target or "").strip().upper()
    return _TARGET_ALIASES.get(t, t)


def _ligand_id_variants(ligand_id: str, target: str = "") -> list[str]:
    ligand_id = str(ligand_id or "").strip()
    if not ligand_id:
        return []
    variants = {ligand_id, ligand_id.lower(), ligand_id.upper()}
    product_match = re.match(r"^product_gate_decoy_(\d+)$", ligand_id, re.I)
    if product_match:
        num_int = int(product_match.group(1))
        nt = _normalize_target(target)
        for suffix in (product_match.group(1), f"{num_int:04d}", f"{num_int:05d}"):
            variants.add(f"decoy_{nt}_{suffix}")
            variants.add(f"decoy_ADRB2_GPCR_BLIND_{suffix}")
    decoy_match = re.match(r"^decoy_(.+?)_(\d+)$", ligand_id, re.I)
    if decoy_match:
        num_int = int(decoy_match.group(2))
        variants.add(f"product_gate_decoy_{num_int:04d}")
        variants.add(f"product_gate_decoy_{num_int}")
    return sorted(variants)


def _target_variants(target: str) -> list[str]:
    target = str(target or "").strip()
    if not target:
        return []
    normalized = _normalize_target(target)
    variants = {target, target.upper(), normalized}
    for alias, canonical in _TARGET_ALIASES.items():
        if normalized == canonical:
            variants.add(alias)
            variants.add(canonical)
    return sorted(variants)


@dataclass
class RefineLookup:
    by_target_ligand: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    by_queue_id: dict[str, dict[str, Any]] = field(default_factory=dict)


def _refine_output_path(stage3_path: Path) -> Path:
    name = stage3_path.name
    if name.endswith("_stage3_scores.csv"):
        return stage3_path.with_name(name.replace("_stage3_scores.csv", "_stage3_refine_scores.csv"))
    return stage3_path.with_name(f"{stage3_path.stem}_refine_scores.csv")


def _refine_path_from_stage5_source(source_csv: str) -> Path | None:
    path = _resolve(source_csv)
    name = path.name
    if name.endswith("_stage5_ranking_rows.csv"):
        return path.with_name(name.replace("_stage5_ranking_rows.csv", "_stage3_refine_scores.csv"))
    return None


def _meta_from_row(raw: dict[str, Any], stage3_path: Path) -> dict[str, Any] | None:
    base = _float(raw.get("binding_energy_mmpbsa_kcal_mol_proxy"))
    refined = _float(raw.get("internal_refine_proxy_score")) or _float(
        raw.get("binding_energy_explicit_water_recheck_kcal_mol_proxy")
    )
    if refined is None:
        return None
    return {
        "base_proxy": base,
        "refined": refined,
        "refine_confidence": _float(raw.get("physics_refinement_confidence")),
        "ligand_model": str(raw.get("ligand_model") or ""),
        "stage3_source": str(stage3_path),
        "queue_id": str(raw.get("queue_id") or "").strip(),
    }


def _register_lookup_key(
    lookup: dict[tuple[str, str], dict[str, Any]],
    *,
    target: str,
    ligand_id: str,
    meta: dict[str, Any],
) -> None:
    if not target or not ligand_id:
        return
    lookup[(target, ligand_id)] = meta


def _load_stage3_refine_lookup(stage3_paths: list[Path]) -> RefineLookup:
    lookup = RefineLookup()
    for stage3_path in stage3_paths:
        if not stage3_path.exists():
            continue
        with stage3_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                target = str(raw.get("target") or "").strip()
                ligand_id = str(raw.get("ligand_id") or "").strip()
                meta = _meta_from_row(raw, stage3_path)
                if meta is None:
                    continue
                _register_lookup_key(lookup.by_target_ligand, target=target, ligand_id=ligand_id, meta=meta)
                for tv in _target_variants(target):
                    for lv in _ligand_id_variants(ligand_id, tv):
                        _register_lookup_key(lookup.by_target_ligand, target=tv, ligand_id=lv, meta=meta)
                queue_id = meta.get("queue_id") or ""
                if queue_id:
                    lookup.by_queue_id[queue_id] = meta
                    queue_match = _QUEUE_ID_RE.match(queue_id)
                    if queue_match:
                        q_target = queue_match.group("target").strip()
                        q_ligand = queue_match.group("ligand").strip()
                        _register_lookup_key(lookup.by_target_ligand, target=q_target, ligand_id=q_ligand, meta=meta)
                        for tv in _target_variants(q_target):
                            for lv in _ligand_id_variants(q_ligand, tv):
                                _register_lookup_key(lookup.by_target_ligand, target=tv, ligand_id=lv, meta=meta)
    return lookup


def _resolve_stage3_paths(
    *,
    stage3_csv: str | Path = "",
    stage3_glob: str = "",
    stage3_csvs: list[str | Path] | None = None,
) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for item in list(stage3_csvs or []):
        path = _resolve(item)
        key = str(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)
    single = _resolve(stage3_csv) if str(stage3_csv).strip() else None
    if single is not None and str(single) not in seen:
        seen.add(str(single))
        paths.append(single)
    if stage3_glob:
        glob_path = Path(stage3_glob)
        if glob_path.is_absolute():
            matches = sorted(glob_path.parent.glob(glob_path.name))
        else:
            matches = sorted(ROOT.glob(stage3_glob))
        for match in matches:
            key = str(match)
            if key not in seen:
                seen.add(key)
                paths.append(match)
    return paths


def _resolve_refine_meta(
    lookup: RefineLookup,
    *,
    target: str,
    ligand_id: str,
    queue_id: str = "",
    source_csv: str = "",
) -> tuple[dict[str, Any] | None, str]:
    if queue_id and queue_id in lookup.by_queue_id:
        return lookup.by_queue_id[queue_id], "queue_id"

    for tv in _target_variants(target):
        for lv in _ligand_id_variants(ligand_id, tv):
            meta = lookup.by_target_ligand.get((tv, lv))
            if meta and meta.get("refined") is not None:
                if (tv, lv) == (target, ligand_id):
                    return meta, "target_ligand_id"
                return meta, "target_ligand_id_normalized"

    source_refine = _refine_path_from_stage5_source(source_csv)
    if source_refine and source_refine.exists():
        source_lookup = _load_stage3_refine_lookup([source_refine])
        if queue_id and queue_id in source_lookup.by_queue_id:
            return source_lookup.by_queue_id[queue_id], "source_csv_queue_id"
        for tv in _target_variants(target):
            for lv in _ligand_id_variants(ligand_id, tv):
                meta = source_lookup.by_target_ligand.get((tv, lv))
                if meta and meta.get("refined") is not None:
                    return meta, "source_csv_target_ligand_id"

    return None, ""


def _apply_refine_meta(row: dict[str, Any], meta: dict[str, Any], join_method: str) -> None:
    row["refine_tier_label"] = meta["refined"]
    row["refine_tier_label_source"] = "stage3_refine_tier"
    row["refine_tier_join_method"] = join_method
    base = meta.get("base_proxy")
    if base is not None:
        row["mm_gbsa_delta"] = float(meta["refined"]) - float(base)
        row["refine_tier_delta"] = row["mm_gbsa_delta"]
        row["delta_force"] = -float(row["mm_gbsa_delta"])
        row["delta_force_label_source"] = "refine_tier_energy_derivation_proxy"
    if meta.get("refine_confidence") is not None:
        row["refine_confidence"] = meta["refine_confidence"]


def enrich_refine_tier_labels(
    *,
    input_csv: str | Path,
    stage3_csv: str | Path = "",
    stage3_glob: str = "",
    stage3_csvs: list[str | Path] | None = None,
    out_csv: str | Path,
) -> dict[str, Any]:
    stage3_paths = _resolve_stage3_paths(stage3_csv=stage3_csv, stage3_glob=stage3_glob, stage3_csvs=stage3_csvs)
    lookup = _load_stage3_refine_lookup(stage3_paths)
    lookup_key_count = len(lookup.by_target_ligand)
    in_path = _resolve(input_csv)
    rows: list[dict[str, Any]] = []
    enriched = 0
    join_methods: dict[str, int] = {}
    with in_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        for extra in (
            "refine_tier_label",
            "refine_tier_label_source",
            "refine_tier_join_method",
            "refine_tier_delta",
            "mm_gbsa_delta",
            "refine_confidence",
            "delta_force",
            "delta_force_label_source",
        ):
            if extra not in fieldnames:
                fieldnames.append(extra)
        for raw in reader:
            row = dict(raw)
            target = str(row.get("target") or "").strip()
            ligand_id = str(row.get("ligand_id") or "").strip()
            queue_id = str(row.get("queue_id") or "").strip()
            source_csv = str(row.get("source_csv") or "").strip()
            meta, join_method = _resolve_refine_meta(
                lookup,
                target=target,
                ligand_id=ligand_id,
                queue_id=queue_id,
                source_csv=source_csv,
            )
            if meta and meta.get("refined") is not None:
                _apply_refine_meta(row, meta, join_method)
                enriched += 1
                join_methods[join_method] = join_methods.get(join_method, 0) + 1
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
        "stage3_csv": str(stage3_paths[-1]) if stage3_paths else "",
        "stage3_source_count": len(stage3_paths),
        "stage3_sources": [str(path) for path in stage3_paths],
        "stage3_lookup_keys": lookup_key_count,
        "refine_tier_join_methods": join_methods,
        "out_csv": str(out_path),
        "row_count": len(rows),
        "refine_tier_label_rows": enriched,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Enrich residual dataset with refine-tier labels from stage3 CSV.")
    p.add_argument("--input-csv", required=True)
    p.add_argument("--stage3-csv", default="")
    p.add_argument("--stage3-glob", default="")
    p.add_argument("--out-csv", required=True)
    args = p.parse_args()
    summary = enrich_refine_tier_labels(
        input_csv=args.input_csv,
        stage3_csv=args.stage3_csv,
        stage3_glob=args.stage3_glob,
        out_csv=args.out_csv,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
