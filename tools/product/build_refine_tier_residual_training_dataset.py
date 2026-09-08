#!/usr/bin/env python3
"""Enrich residual supervised dataset rows with refine-tier labels from stage3 scoring."""

from __future__ import annotations

import argparse
import csv
import json
import hashlib
import io
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.product.residual_evidence import (
    IDENTITY_FIELDS, PROVENANCE_FIELD, REFINE_JOIN_CONTRACT, _sha, declared_evaluation_only, merge_source_provenance,
    first_numeric_observation, require_complete_csv_row, source_provenance_json, validated_csv_fieldnames,
)

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
        number = float(value)
        return number if math.isfinite(number) else None
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
    by_target_ligand: dict[tuple[str, str], dict[str, Any] | None] = field(default_factory=dict)
    by_queue_id: dict[str, dict[str, Any] | None] = field(default_factory=dict)


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


def _meta_from_row(raw: dict[str, Any], stage3_path: Path) -> dict[str, Any]:
    base = _float(raw.get("binding_energy_mmpbsa_kcal_mol_proxy"))
    refined, refined_column, observation_status = first_numeric_observation(
        raw, ("deltaG_mm_gbsa_kcal_mol", "binding_energy_explicit_water_recheck_kcal_mol_proxy"),
    )
    value_status = "observed" if observation_status == "observed" else observation_status + "_refine_value"
    return {
        "base_proxy": base, "refined": refined, "value_status": value_status,
        "refined_column": refined_column,
        "refine_confidence": _float(raw.get("physics_refinement_confidence")),
        "ligand_model": str(raw.get("ligand_model") or ""),
        "stage3_source": str(stage3_path), "row": dict(raw),
        "queue_id": str(raw.get("queue_id") or "").strip(),
    }


def _register_key(lookup: dict, key: Any, meta: dict[str, Any]) -> None:
    if key not in lookup:
        lookup[key] = meta
    elif lookup[key] is not meta:
        # Repeated aliases for one source row are harmless. Distinct rows,
        # including an invalid/blank second row, make the join ambiguous.
        lookup[key] = None


def _register_lookup_key(lookup: dict, *, target: str, ligand_id: str, meta: dict[str, Any]) -> None:
    if target and ligand_id:
        _register_key(lookup, (target, ligand_id), meta)


def _load_stage3_refine_lookup(stage3_paths: list[Path]) -> RefineLookup:
    lookup = RefineLookup()
    for stage3_path in stage3_paths:
        if not stage3_path.exists():
            continue
        raw_bytes = stage3_path.read_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        with io.StringIO(raw_bytes.decode("utf-8"), newline="") as fh:
            reader = csv.DictReader(fh, strict=True)
            reader.fieldnames = validated_csv_fieldnames(reader.fieldnames)
            for raw in reader:
                require_complete_csv_row(raw)
                meta = _meta_from_row(raw, stage3_path)
                meta[PROVENANCE_FIELD] = source_provenance_json(
                    raw, source_csv=str(stage3_path), source_sha256=digest, source_line=reader.line_num,
                )
                target, ligand_id = str(raw.get("target") or "").strip(), str(raw.get("ligand_id") or "").strip()
                for tv in _target_variants(target):
                    for lv in _ligand_id_variants(ligand_id, tv):
                        _register_lookup_key(lookup.by_target_ligand, target=tv, ligand_id=lv, meta=meta)
                queue_id = meta["queue_id"]
                if queue_id:
                    _register_key(lookup.by_queue_id, queue_id, meta)
                    queue_match = _QUEUE_ID_RE.match(queue_id)
                    if queue_match:
                        for tv in _target_variants(queue_match.group("target").strip()):
                            for lv in _ligand_id_variants(queue_match.group("ligand").strip(), tv):
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
    lookup: RefineLookup, *, target: str, ligand_id: str, queue_id: str = "", source_csv: str = "",
) -> tuple[dict[str, Any] | None, str]:
    if queue_id and queue_id in lookup.by_queue_id:
        meta = lookup.by_queue_id[queue_id]
        return meta, "queue_id" if meta is not None else "rejected_ambiguous_queue_id"
    candidates = {}
    for tv in _target_variants(target):
        for lv in _ligand_id_variants(ligand_id, tv):
            key = (tv, lv)
            if key not in lookup.by_target_ligand:
                continue
            meta = lookup.by_target_ligand[key]
            if meta is None:
                return None, "rejected_ambiguous_target_ligand_id"
            candidates[id(meta)] = meta
    if len(candidates) > 1:
        return None, "rejected_ambiguous_target_ligand_id"
    if candidates:
        meta = next(iter(candidates.values()))
        exact = lookup.by_target_ligand.get((target, ligand_id)) is meta
        return meta, "target_ligand_id" if exact else "target_ligand_id_normalized"
    source_refine = _refine_path_from_stage5_source(source_csv) if source_csv else None
    if source_refine and source_refine.exists():
        meta, method = _resolve_refine_meta(_load_stage3_refine_lookup([source_refine]),
                                          target=target, ligand_id=ligand_id, queue_id=queue_id)
        return meta, "source_csv_" + method
    return None, "no_matching_source"


def _apply_refine_meta(row: dict[str, Any], meta: dict[str, Any], join_method: str) -> bool:
    row[PROVENANCE_FIELD] = merge_source_provenance(row, meta)
    row["refine_tier_join_method"] = join_method
    row["refine_tier_join_contract"] = REFINE_JOIN_CONTRACT
    source = meta["row"]
    row["refine_tier_evidence_kind"] = str(source.get("evidence_kind") or source.get("label_evidence_kind") or "unverified_computed_proxy")
    if declared_evaluation_only(row):
        row["refine_tier_join_status"] = "rejected_evaluation_only_source"
        return False
    for key in ("target", "ligand_id"):
        left, right = str(row.get(key) or "").strip(), str(source.get(key) or "").strip()
        if left and right:
            matches = (_normalize_target(left) == _normalize_target(right)) if key == "target" else bool(
                set(_ligand_id_variants(left, str(row.get("target", "")))) & set(_ligand_id_variants(right, str(source.get("target", ""))))
            )
            if not matches:
                row["refine_tier_join_status"] = "rejected_identity_mismatch:" + key
                return False
    identity_fields = ("pose_id", *IDENTITY_FIELDS)
    identity_complete = True
    for key in identity_fields:
        left, right = str(row.get(key) or ""), str(source.get(key) or "")
        if key == "pose_id":
            left, right = left.strip(), right.strip()
        identity_complete = identity_complete and bool(left and right)
        if key in IDENTITY_FIELDS:
            try:
                for value in (left, right):
                    if value:
                        _sha(value, key)
            except ValueError:
                row["refine_tier_join_status"] = "rejected_invalid_identity:" + key
                return False
        if (left or right) and left != right:
            row["refine_tier_join_status"] = "rejected_identity_mismatch:" + key
            return False
    row["refine_tier_identity_status"] = "declared_identity_matched" if identity_complete else "unverified_missing_identity"
    if row["refine_tier_evidence_kind"].casefold() in {"experimental", "experimental_label", "ai_prediction", "heuristic"}:
        row["refine_tier_join_status"] = "rejected_incompatible_refine_evidence_kind"
        return False
    if meta["value_status"] != "observed":
        row["refine_tier_join_status"] = meta["value_status"]
        return False
    row["refine_tier_label"] = meta["refined"]
    row["refine_tier_label_source"] = "stage3_refine_tier"
    row["refine_tier_value_semantics"] = "computed_proxy_not_physical_energy_residual"
    base = meta.get("base_proxy")
    if base is not None:
        delta = float(meta["refined"]) - float(base)
        if math.isfinite(delta):
            row["mm_gbsa_delta"] = row["refine_tier_delta"] = delta
    if meta.get("refine_confidence") is not None:
        row["refine_confidence"] = meta["refine_confidence"]
    row["refine_tier_join_status"] = "joined"
    return True


def enrich_refine_tier_labels(
    *, input_csv: str | Path, stage3_csv: str | Path = "", stage3_glob: str = "",
    stage3_csvs: list[str | Path] | None = None, out_csv: str | Path,
) -> dict[str, Any]:
    stage3_paths = _resolve_stage3_paths(stage3_csv=stage3_csv, stage3_glob=stage3_glob, stage3_csvs=stage3_csvs)
    lookup = _load_stage3_refine_lookup(stage3_paths)
    in_path = _resolve(input_csv)
    raw_bytes = in_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    rows = []
    enriched = 0
    join_methods: dict[str, int] = {}
    join_statuses: dict[str, int] = {}
    generated = ("refine_tier_label", "refine_tier_label_source", "refine_tier_join_method",
                 "refine_tier_delta", "mm_gbsa_delta", "refine_confidence",
                 "refine_tier_join_status", "refine_tier_evidence_kind",
                 "refine_tier_value_semantics", "refine_tier_identity_status", "refine_tier_join_contract")
    with io.StringIO(raw_bytes.decode("utf-8"), newline="") as fh:
        reader = csv.DictReader(fh, strict=True)
        reader.fieldnames = validated_csv_fieldnames(reader.fieldnames)
        fieldnames = list(dict.fromkeys([*reader.fieldnames, *generated, PROVENANCE_FIELD]))
        for raw in reader:
            require_complete_csv_row(raw)
            row = dict(raw)
            row[PROVENANCE_FIELD] = source_provenance_json(
                raw, source_csv=str(in_path), source_sha256=digest, source_line=reader.line_num,
            )
            for key in generated:
                row[key] = ""
            if row.get("delta_force_label_source") == "refine_tier_energy_derivation_proxy":
                row["delta_force"] = row["delta_force_label_source"] = ""
            meta, method = _resolve_refine_meta(
                lookup, target=str(row.get("target") or "").strip(),
                ligand_id=str(row.get("ligand_id") or "").strip(),
                queue_id=str(row.get("queue_id") or "").strip(), source_csv=str(row.get("source_csv") or "").strip(),
            )
            row["refine_tier_join_status"] = method
            if meta is not None and _apply_refine_meta(row, meta, method):
                enriched += 1
                join_methods[method] = join_methods.get(method, 0) + 1
            status = row["refine_tier_join_status"]
            join_statuses[status] = join_statuses.get(status, 0) + 1
            rows.append(row)
    out_path = _resolve(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "status": "refine_tier_enrichment_ready" if enriched else "blocked_refine_tier_enrichment",
        "input_csv": str(in_path), "stage3_csv": str(stage3_paths[-1]) if stage3_paths else "",
        "stage3_source_count": len(stage3_paths), "stage3_sources": [str(path) for path in stage3_paths],
        "stage3_lookup_keys": len(lookup.by_target_ligand), "refine_tier_join_methods": join_methods,
        "refine_tier_join_status_counts": join_statuses, "out_csv": str(out_path),
        "row_count": len(rows), "refine_tier_label_rows": enriched,
        "rejected_or_unmatched_rows": len(rows) - enriched,
        "physical_energy_residual_validated": False, "force_labels_derived": False,
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
