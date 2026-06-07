#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_target_render_utils import resolve

DEFAULT_OUT_MD = "runs/wetlab_broad_screen_compound_universe_current.md"
TARGET_LIBRARY_SIZE = 100000
DEFAULT_SOURCE_PATHS = (
    "runs/wetlab_priority3_repurposing_fill_map_current.json",
    "runs/wetlab_next3_repurposing_fill_map_current.json",
    "runs/wetlab_stk17b_repurposing_fill_map_current.json",
    "runs/wetlab_lbdhodh_repurposing_fill_map_current.json",
    "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json",
    "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.json",
    "runs/wetlab_dpre1_repurposing_fill_map_current.json",
    "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.json",
    "runs/wetlab_lrrk2_repurposing_fill_map_current.json",
    "config/ligand_blind_gpcr_adrb2_chembl_candidates_v1.csv",
    "config/ligand_blind_trpv1_chembl_candidates_v1.csv",
    "config/ligand_meta_blind_gpcr_adrb2_chembl50_v1.csv",
    "config/ligand_meta_blind_trpv1_chembl50_v1.csv",
    "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
    "runs/ligand_smiles_bead_cache_blind_gpcr_adrb2_chembl20_v1.json",
    "runs/ligand_smiles_bead_cache_blind_gpcr_adrb2_chembl50_v1.json",
    "runs/ligand_smiles_bead_cache_blind_trpv1_chembl20_v1.json",
    "runs/ligand_smiles_bead_cache_blind_trpv1_chembl50_v1.json",
)
DEFAULT_NAME_LOOKUP_PATHS = (
    "config/ligand_meta_blind_gpcr_adrb2_chembl20_v1.csv",
    "config/ligand_meta_blind_gpcr_adrb2_chembl50_v1.csv",
    "config/ligand_meta_blind_trpv1_chembl20_v1.csv",
    "config/ligand_meta_blind_trpv1_chembl50_v1.csv",
)


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_name(text: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return " ".join(lowered.split())


def _normalize_smiles(text: str) -> str:
    return "".join(str(text).strip().split())


def _guess_approval_class(row: dict[str, Any], source_path: Path) -> str:
    seed_status = _first_text(row, "seed_status", "source_class")
    lowered = seed_status.lower()
    if "smiles_bead_cache" in source_path.name.lower():
        return "chembl_procurement_candidate"
    if "approved" in lowered or "clinical" in lowered or "benchmark" in lowered:
        return "approved_or_clinical_anchor"
    if "repurposing" in lowered or "comparator" in lowered:
        return "repurposing_anchor"
    if source_path.suffix == ".csv" and "chembl" in source_path.name.lower():
        return "chembl_procurement_candidate"
    return "local_curated_candidate"


def _guess_procurement_tier(row: dict[str, Any], source_path: Path) -> str:
    if "smiles_bead_cache" in source_path.name.lower():
        return "local_cache_expanded"
    if str(row.get("vendor_check_required", "")).strip().lower() == "true":
        return "vendor_check_required"
    if source_path.suffix == ".csv":
        return "local_library_metadata"
    return "curated_packet_seed"


def _build_smiles_name_lookup() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path_like in DEFAULT_NAME_LOOKUP_PATHS:
        path = resolve(path_like)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                smiles = _normalize_smiles(_first_text(row, "smiles", "canonical_smiles"))
                name = _first_text(row, "ligand_id", "compound_name", "name")
                if smiles and name:
                    mapping.setdefault(smiles, name)
    return mapping


def _cache_row_name(smiles: str, name_lookup: dict[str, str]) -> str:
    if smiles in name_lookup:
        return name_lookup[smiles]
    return f"chembl_cache_{hashlib.sha1(smiles.encode('utf-8')).hexdigest()[:12]}"


def _load_source_rows(path: Path, *, name_lookup: dict[str, str]) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]

    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, dict):
        if "rows" not in payload and all(isinstance(value, list) for value in payload.values()):
            return [
                {
                    "compound_name": _cache_row_name(smiles, name_lookup),
                    "canonical_smiles": smiles,
                    "source_class": "chembl_procurement_candidate",
                    "source": path.name,
                }
                for smiles in payload.keys()
            ]
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
        return [payload]
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    return []


def _normalize_row(row: dict[str, Any], source_path: Path) -> tuple[dict[str, Any] | None, str]:
    compound_name = _first_text(row, "compound_name", "preferred_name", "name", "ligand_id")
    smiles = _normalize_smiles(_first_text(row, "canonical_smiles", "smiles"))
    if not compound_name and not smiles:
        return None, "missing_compound_identity"
    if smiles.upper().startswith("TODO"):
        return None, "placeholder_smiles"
    dedupe_key = f"smiles::{smiles}" if smiles else f"name::{_normalize_name(compound_name)}"
    return (
        {
            "compound_name": compound_name or _first_text(row, "ligand_id"),
            "canonical_smiles": smiles,
            "dedupe_key": dedupe_key,
            "approval_class": _guess_approval_class(row, source_path),
            "procurement_tier": _guess_procurement_tier(row, source_path),
            "source_dataset": source_path.name,
            "source_path": str(source_path),
            "source_anchor": _first_text(row, "source_anchor", "source") or source_path.name,
            "source_url": _first_text(row, "source_url"),
            "seed_status": _first_text(row, "seed_status", "source_class"),
            "molecular_weight": _first_text(row, "molecular_weight"),
            "logp": _first_text(row, "logp"),
        },
        "",
    )


def _iter_source_paths(extra_source_globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for path_like in DEFAULT_SOURCE_PATHS:
        path = resolve(path_like)
        if path.exists() and path not in seen:
            seen.add(path)
            paths.append(path)
    for pattern in extra_source_globs:
        base = resolve(".")
        for path in sorted(base.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def build_payload(*, extra_source_globs: list[str] | None = None) -> dict[str, Any]:
    source_paths = _iter_source_paths(extra_source_globs or [])
    name_lookup = _build_smiles_name_lookup()
    deduped: dict[str, dict[str, Any]] = {}
    invalid_reason_counts: dict[str, int] = {}
    input_row_count = 0
    duplicate_row_count = 0

    for source_path in source_paths:
        for raw in _load_source_rows(source_path, name_lookup=name_lookup):
            input_row_count += 1
            normalized, invalid_reason = _normalize_row(raw, source_path)
            if normalized is None:
                invalid_reason_counts[invalid_reason] = invalid_reason_counts.get(invalid_reason, 0) + 1
                continue
            dedupe_key = normalized["dedupe_key"]
            existing = deduped.get(dedupe_key)
            if existing:
                duplicate_row_count += 1
                datasets = set(str(existing.get("source_dataset_set", "")).split(" ; ")) | {normalized["source_dataset"]}
                datasets.discard("")
                existing["source_dataset_set"] = " ; ".join(sorted(datasets))
                existing["source_dataset_count"] = len(datasets)
                if not existing.get("canonical_smiles") and normalized.get("canonical_smiles"):
                    existing["canonical_smiles"] = normalized["canonical_smiles"]
                continue
            normalized["source_dataset_set"] = normalized["source_dataset"]
            normalized["source_dataset_count"] = 1
            deduped[dedupe_key] = normalized

    rows = sorted(
        deduped.values(),
        key=lambda row: (
            0 if row["approval_class"] == "approved_or_clinical_anchor" else 1,
            0 if row["procurement_tier"] == "curated_packet_seed" else 1,
            str(row["compound_name"]).lower(),
        ),
    )
    for idx, row in enumerate(rows, start=1):
        row["compound_index"] = idx

    selected_count = min(TARGET_LIBRARY_SIZE, len(rows))
    return {
        "summary": {
            "status": "wetlab_broad_screen_compound_universe_ready",
            "target_library_size": TARGET_LIBRARY_SIZE,
            "source_file_count": len(source_paths),
            "input_row_count": input_row_count,
            "invalid_row_count": sum(invalid_reason_counts.values()),
            "duplicate_row_count": duplicate_row_count,
            "deduped_compound_count": len(rows),
            "selected_for_lane_count": selected_count,
            "coverage_gap_to_target_size": max(TARGET_LIBRARY_SIZE - len(rows), 0),
            "coverage_status": "full_target_coverage" if len(rows) >= TARGET_LIBRARY_SIZE else "partial_local_coverage",
            "next_required_step": "Add larger approved/procurement source tables if needed, then feed this deduped universe into the broad-screen execution queue and bridge autofill.",
        },
        "structured": {
            "source_files": " ; ".join(str(path) for path in source_paths),
            "invalid_reason_counts": invalid_reason_counts,
        },
        "rows": rows,
    }


def _write_markdown(md_path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("summary", {}) or {}
    structured = payload.get("structured", {}) or {}
    rows = payload.get("rows", []) or []
    sample_rows = rows[:10]
    lines = ["# Wet-Lab Broad Screen Compound Universe", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    if structured:
        lines.extend(["", "## Structured", ""])
        for key, value in structured.items():
            lines.append(f"- {key}: `{value}`")
    if sample_rows:
        headers = list(sample_rows[0].keys())
        lines.extend(
            [
                "",
                "## Sample Rows",
                "",
                f"- sample_row_count: `{len(sample_rows)}`",
                f"- total_row_count: `{len(rows)}`",
                "",
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]
        )
        for row in sample_rows:
            values = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(values) + " |")
    if summary.get("next_required_step"):
        lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the deduped compound universe for the 100k broad wet-lab screen.")
    parser.add_argument("--extra-source-glob", action="append", default=[])
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(extra_source_globs=args.extra_source_glob)
    md_path = resolve(args.out_md)
    json_path = md_path.with_suffix(".json")
    csv_path = md_path.with_suffix(".csv")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(csv_path, payload.get("rows", []) or [])
    _write_markdown(md_path, payload)
