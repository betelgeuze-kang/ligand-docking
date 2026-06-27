#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DATE_KEYWORDS = (
    "date",
    "year",
    "publication",
    "published",
    "release",
    "timestamp",
    "created",
    "generated",
    "added",
    "included",
    "provenance",
)
WEAK_ONLY_KEYWORDS = ("source",)
PROFILE_REF_KEYS = {
    "target_native_csv",
    "ligand_csv",
    "calibration_reference_csv",
    "ranking_labels_csv",
    "eval_split_csv",
    "leakage_target_meta_csv",
    "leakage_ligand_meta_csv",
    "hard_decoy_reference_csv",
    "hard_decoy_ligand_meta_csv",
    "hard_decoy_target_meta_csv",
    "data_contract_json",
    "config_json",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _keyword_columns(columns: list[str], keywords: tuple[str, ...]) -> list[str]:
    found = []
    for column in columns:
        lower = column.lower()
        if any(keyword in lower for keyword in keywords):
            found.append(column)
    return found


def _classify_csv(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        row_count = sum(1 for _ in reader)

    strong_cols = _keyword_columns(header, DATE_KEYWORDS)
    weak_cols = _keyword_columns(header, WEAK_ONLY_KEYWORDS)
    if strong_cols:
        readiness = "item_level_ready"
        note = "Contains explicit date-like provenance columns."
    elif weak_cols:
        readiness = "dataset_level_only"
        note = "Contains only source-style provenance labels; no explicit per-item date/year field."
    else:
        readiness = "missing_item_provenance"
        note = "No provenance-like columns detected in the item table."
    return {
        "path": _rel(path),
        "kind": "csv",
        "row_count": row_count,
        "columns": header,
        "strong_provenance_columns": strong_cols,
        "weak_provenance_columns": weak_cols,
        "readiness": readiness,
        "notes": note,
    }


def _top_level_scalar_keys(obj: dict[str, Any]) -> list[str]:
    return [key for key, value in obj.items() if not isinstance(value, (dict, list))]


def _first_record_keys(obj: dict[str, Any]) -> list[str]:
    for value in obj.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return list(value[0].keys())
    return []


def _classify_json(path: Path) -> dict[str, Any]:
    obj = _read_json(path)
    top_level_keys = _top_level_scalar_keys(obj)
    record_keys = _first_record_keys(obj)
    top_level_strong = _keyword_columns(top_level_keys, DATE_KEYWORDS)
    record_strong = _keyword_columns(record_keys, DATE_KEYWORDS)

    if record_strong:
        readiness = "item_level_ready"
        note = "Contains date-like provenance fields on per-record JSON entries."
    elif top_level_strong:
        readiness = "dataset_level_only"
        note = "Contains only dataset/profile-level timestamps or release labels."
    else:
        readiness = "missing_item_provenance"
        note = "No date-like provenance fields detected."

    return {
        "path": _rel(path),
        "kind": "json",
        "row_count": None,
        "columns": top_level_keys,
        "strong_provenance_columns": top_level_strong,
        "weak_provenance_columns": [],
        "record_level_candidate_columns": record_keys,
        "record_level_strong_provenance_columns": record_strong,
        "readiness": readiness,
        "notes": note,
    }


def _classify_path(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        return _classify_csv(path)
    if path.suffix.lower() == ".json":
        return _classify_json(path)
    return {
        "path": _rel(path),
        "kind": path.suffix.lower().lstrip(".") or "unknown",
        "row_count": None,
        "columns": [],
        "strong_provenance_columns": [],
        "weak_provenance_columns": [],
        "readiness": "unsupported",
        "notes": "Unsupported file type for provenance inspection.",
    }


def _profile_references(profile_path: Path) -> dict[str, str]:
    obj = _read_json(profile_path)
    refs: dict[str, str] = {}
    for key in PROFILE_REF_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and (value.endswith(".csv") or value.endswith(".json")):
            refs[key] = value
    return refs


def _collect_inventory(set_spec: dict[str, Any]) -> list[dict[str, Any]]:
    referrers: dict[str, set[str]] = defaultdict(set)
    source_roles: dict[str, set[str]] = defaultdict(set)
    temporal = set_spec.get("temporal_governance", {})
    freeze_sources = temporal.get("dataset_level_freeze_sources", {})

    for dataset_id, rel_path in freeze_sources.items():
        referrers[rel_path].add(dataset_id)
        source_roles[rel_path].add("dataset_level_freeze_source")
        abs_path = (ROOT / rel_path).resolve()
        if abs_path.suffix.lower() != ".json" or not abs_path.exists():
            continue
        if abs_path.name.endswith("_manifest_current.json"):
            config_json = _read_json(abs_path).get("config_json")
            if isinstance(config_json, str):
                referrers[config_json].add(dataset_id)
                source_roles[config_json].add("manifest_config_json")
        else:
            for key, child_rel in _profile_references(abs_path).items():
                referrers[child_rel].add(dataset_id)
                source_roles[child_rel].add(key)

    rows: list[dict[str, Any]] = []
    for rel_path in sorted(referrers):
        abs_path = (ROOT / rel_path).resolve()
        entry = _classify_path(abs_path)
        entry["exists"] = abs_path.exists()
        entry["referrers"] = sorted(referrers[rel_path])
        entry["source_roles"] = sorted(source_roles[rel_path])
        if not abs_path.exists():
            entry["readiness"] = "missing_file"
            entry["notes"] = "Referenced by the temporal spec but missing on disk."
        rows.append(entry)
    return rows


def _build_summary(rows: list[dict[str, Any]], spec_path: Path) -> dict[str, Any]:
    readiness = Counter(row["readiness"] for row in rows)
    return {
        "spec_json": _rel(spec_path),
        "inspected_file_count": len(rows),
        "readiness_counts": dict(readiness),
        "item_level_ready_count": readiness.get("item_level_ready", 0),
        "dataset_level_only_count": readiness.get("dataset_level_only", 0),
        "missing_item_provenance_count": readiness.get("missing_item_provenance", 0),
        "missing_file_count": readiness.get("missing_file", 0),
        "key_findings": [
            "Ligand reference CSVs currently expose `source` labels but not explicit per-item publication/release dates.",
            "Ligand split, target metadata, and ligand metadata CSVs do not currently provide item-level provenance dates.",
            "The current IDP release manifest provides release-level timestamps and holdout artifact paths, but not per-holdout publication or inclusion dates.",
        ],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "kind",
        "readiness",
        "exists",
        "referrers",
        "source_roles",
        "strong_provenance_columns",
        "weak_provenance_columns",
        "record_level_strong_provenance_columns",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: ";".join(row.get(key, [])) if isinstance(row.get(key), list) else row.get(key, "")
                    for key in fieldnames
                }
            )


def _write_md(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Temporal Provenance Inventory",
        "",
        f"- spec_json: `{summary['spec_json']}`",
        f"- inspected_file_count: `{summary['inspected_file_count']}`",
        f"- item_level_ready_count: `{summary['item_level_ready_count']}`",
        f"- dataset_level_only_count: `{summary['dataset_level_only_count']}`",
        f"- missing_item_provenance_count: `{summary['missing_item_provenance_count']}`",
        f"- missing_file_count: `{summary['missing_file_count']}`",
        "",
        "## Key Findings",
        "",
    ]
    for finding in summary["key_findings"]:
        lines.append(f"- {finding}")

    lines.extend(
        [
            "",
            "## Inventory",
            "",
            "| Path | Kind | Readiness | Referrers | Provenance Columns | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        cols = row.get("strong_provenance_columns") or row.get("weak_provenance_columns") or row.get("record_level_strong_provenance_columns") or []
        col_text = ", ".join(cols) if cols else "none"
        ref_text = ", ".join(row.get("referrers", [])) or "none"
        lines.append(
            f"| `{row['path']}` | `{row['kind']}` | `{row['readiness']}` | `{ref_text}` | `{col_text}` | {row['notes']} |"
        )
    _write_text(path, "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build an inventory of temporal provenance coverage for the provisional bioRxiv temporal spec.")
    ap.add_argument("--set-spec-json", default="config/external_validation_biorxiv_temporal_sets_v1_provisional.json")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_provenance_inventory_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_provenance_inventory_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_provenance_inventory_current.md")
    args = ap.parse_args(argv)

    spec_path = (ROOT / args.set_spec_json).resolve()
    spec = _read_json(spec_path)
    rows = _collect_inventory(spec)
    summary = _build_summary(rows, spec_path)
    payload = {
        "summary": summary,
        "rows": rows,
    }

    _write_json((ROOT / args.out_json).resolve(), payload)
    _write_csv((ROOT / args.out_csv).resolve(), rows)
    _write_md((ROOT / args.out_md).resolve(), summary, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
