#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _safe_get_profile_refs(profile_path: Path) -> dict[str, str]:
    obj = _read_json(profile_path)
    refs: dict[str, str] = {}
    for key in (
        "ligand_csv",
        "eval_split_csv",
        "calibration_reference_csv",
        "ranking_labels_csv",
        "leakage_ligand_meta_csv",
        "hard_decoy_reference_csv",
    ):
        value = obj.get(key)
        if isinstance(value, str):
            refs[key] = value
    return refs


def _build_ligand_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for set_obj in spec.get("sets", []):
        set_id = set_obj.get("set_id", "")
        for task in set_obj.get("tasks", []):
            profile_rel = task.get("profile_json")
            if not isinstance(profile_rel, str):
                continue
            profile_path = (ROOT / profile_rel).resolve()
            refs = _safe_get_profile_refs(profile_path)
            ligand_csv = (ROOT / refs["ligand_csv"]).resolve()
            split_csv = (ROOT / refs["eval_split_csv"]).resolve()
            split_rows = _read_csv(split_csv) if split_csv.exists() else []
            roles = {
                (row.get("target", ""), row.get("ligand_id", "")): row.get("role", "")
                for row in split_rows
            }
            for row in _read_csv(ligand_csv):
                rows.append(
                    {
                        "set_id": set_id,
                        "task_id": task.get("task_id", ""),
                        "domain": task.get("domain", ""),
                        "profile_json": _rel(profile_path),
                        "ligand_csv": _rel(ligand_csv),
                        "eval_split_csv": _rel(split_csv),
                        "target": row.get("target", ""),
                        "ligand_id": row.get("ligand_id", ""),
                        "role": roles.get((row.get("target", ""), row.get("ligand_id", "")), ""),
                        "is_binder": row.get("is_binder", ""),
                        "source_label": row.get("source", ""),
                        "source_release": "",
                        "provenance_date": "",
                        "publication_year": "",
                        "release_date": "",
                        "provenance_granularity": "",
                        "provenance_url": "",
                        "curation_status": "pending",
                        "notes": "",
                    }
                )
    return rows


def _build_idp_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    ref_manifest_rel = spec.get("frozen_references", {}).get("idp_release_manifest_current")
    if not isinstance(ref_manifest_rel, str):
        return []
    manifest_path = (ROOT / ref_manifest_rel).resolve()
    manifest = _read_json(manifest_path)
    config_rel = manifest.get("config_json")
    if not isinstance(config_rel, str):
        return []
    config_path = (ROOT / config_rel).resolve()
    config = _read_json(config_path)

    set_ids = sorted(
        set(
            set_obj.get("set_id", "")
            for set_obj in spec.get("sets", [])
            for task in set_obj.get("tasks", [])
            if task.get("kind") == "idp_reference_current_full"
        )
    )

    by_holdout: dict[str, dict[str, Any]] = {}
    for target in config.get("targets", []):
        holdout = target.get("split_group") or target.get("name", "")
        if holdout in by_holdout:
            continue
        by_holdout[holdout] = {
            "referenced_by_sets": ",".join(set_ids),
            "task_id": "idp_release_current",
            "release_manifest_json": _rel(manifest_path),
            "config_json": _rel(config_path),
            "holdout_name": holdout,
            "representative_target_name": target.get("name", ""),
            "source_kind": target.get("source", ""),
            "pdb_path": target.get("pdb_path", ""),
            "publication_year": "",
            "benchmark_inclusion_date": "",
            "corrected_label_freeze_date": "",
            "provenance_granularity": "",
            "provenance_source": "",
            "curation_status": "pending",
            "notes": "",
        }
    return [by_holdout[key] for key in sorted(by_holdout)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Build editable provenance mapping templates for the provisional temporal validation spec.")
    ap.add_argument("--set-spec-json", default="config/external_validation_biorxiv_temporal_sets_v1_provisional.json")
    ap.add_argument("--ligand-out-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--idp-out-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    args = ap.parse_args()

    spec = _read_json((ROOT / args.set_spec_json).resolve())
    ligand_rows = _build_ligand_rows(spec)
    idp_rows = _build_idp_rows(spec)

    _write_csv(
        (ROOT / args.ligand_out_csv).resolve(),
        ligand_rows,
        [
            "set_id",
            "task_id",
            "domain",
            "profile_json",
            "ligand_csv",
            "eval_split_csv",
            "target",
            "ligand_id",
            "role",
            "is_binder",
            "source_label",
            "source_release",
            "provenance_date",
            "publication_year",
            "release_date",
            "provenance_granularity",
            "provenance_url",
            "curation_status",
            "notes",
        ],
    )
    _write_csv(
        (ROOT / args.idp_out_csv).resolve(),
        idp_rows,
        [
            "referenced_by_sets",
            "task_id",
            "release_manifest_json",
            "config_json",
            "holdout_name",
            "representative_target_name",
            "source_kind",
            "pdb_path",
            "publication_year",
            "benchmark_inclusion_date",
            "corrected_label_freeze_date",
            "provenance_granularity",
            "provenance_source",
            "curation_status",
            "notes",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
