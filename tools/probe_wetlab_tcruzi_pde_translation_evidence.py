#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REQUESTED_FIELDS = (
    "pose_preservation_rmsd_A",
    "backmapping_consistency_score",
    "local_minimization_survival_fraction",
    "replicate_pass_fraction",
    "binding_energy_proxy",
)

TEXT_EXTENSIONS = {".json", ".csv"}


def _is_candidate_file(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    path_text = path.as_posix()
    name = path.name
    if path_text.startswith("runs/wetlab_tcruzi_pde_allatom_rescue"):
        return True
    lowered = name.lower()
    is_tcruzi_pde = "tcruzi_pde" in lowered or "t_cruzi_pde" in lowered
    is_current = "current" in lowered
    is_allatom_review_or_rescue = "allatom" in lowered and ("review" in lowered or "rescue" in lowered)
    return is_tcruzi_pde and is_current and is_allatom_review_or_rescue


def discover_candidate_files(root: Path) -> list[Path]:
    runs = root / "runs"
    if not runs.exists():
        return []
    return sorted(path for path in runs.rglob("*") if path.is_file() and _is_candidate_file(path.relative_to(root)))


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _metric_for_key(key: str) -> str | None:
    for field in REQUESTED_FIELDS:
        if field in key:
            return field
    return None


def _add_occurrence(
    index: dict[str, dict[str, Any]],
    *,
    metric: str,
    key: str,
    source_path: Path,
    value: Any,
    container: str,
    row_number: int | None = None,
) -> None:
    item = index[metric].setdefault(
        key,
        {
            "field": key,
            "exact_requested_field": key == metric,
            "occurrence_count": 0,
            "non_null_count": 0,
            "sample_values": [],
            "sample_sources": [],
        },
    )
    item["occurrence_count"] += 1
    if _has_value(value):
        item["non_null_count"] += 1
        if len(item["sample_values"]) < 3:
            item["sample_values"].append(value)
    if len(item["sample_sources"]) < 5:
        sample = {"path": source_path.as_posix(), "container": container}
        if row_number is not None:
            sample["row_number"] = row_number
        item["sample_sources"].append(sample)


def _walk_json(value: Any, *, path: Path, index: dict[str, dict[str, Any]], container: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            metric = _metric_for_key(str(key))
            if metric is not None:
                _add_occurrence(
                    index,
                    metric=metric,
                    key=str(key),
                    source_path=path,
                    value=child,
                    container=container,
                )
            _walk_json(child, path=path, index=index, container=f"{container}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _walk_json(child, path=path, index=index, container=f"{container}[{idx}]")


def _scan_json(path: Path, index: dict[str, dict[str, Any]], errors: list[dict[str, str]]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append({"path": path.as_posix(), "error": str(exc)})
        return
    _walk_json(payload, path=path, index=index)


def _scan_csv(path: Path, index: dict[str, dict[str, Any]], errors: list[dict[str, str]]) -> None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            matching = [(field, _metric_for_key(field)) for field in fieldnames]
            matching = [(field, metric) for field, metric in matching if metric is not None]
            if not matching:
                return
            for row_number, row in enumerate(reader, start=2):
                for field, metric in matching:
                    assert metric is not None
                    _add_occurrence(
                        index,
                        metric=metric,
                        key=field,
                        source_path=path,
                        value=row.get(field),
                        container="csv_row",
                        row_number=row_number,
                    )
    except Exception as exc:
        errors.append({"path": path.as_posix(), "error": str(exc)})


def build_probe(root: Path) -> dict[str, Any]:
    files = discover_candidate_files(root)
    index: dict[str, dict[str, Any]] = defaultdict(dict)
    errors: list[dict[str, str]] = []
    for path in files:
        if path.suffix.lower() == ".json":
            _scan_json(path, index, errors)
        elif path.suffix.lower() == ".csv":
            _scan_csv(path, index, errors)

    metrics: dict[str, Any] = {}
    for metric in REQUESTED_FIELDS:
        observed_fields = sorted(
            index.get(metric, {}).values(),
            key=lambda item: (not item["exact_requested_field"], item["field"]),
        )
        exact = [item for item in observed_fields if item["exact_requested_field"]]
        alias = [item for item in observed_fields if not item["exact_requested_field"]]
        metrics[metric] = {
            "exact_field_present": bool(exact),
            "exact_field_non_null_count": sum(item["non_null_count"] for item in exact),
            "alias_field_count": len(alias),
            "observed_fields": observed_fields,
        }

    return {
        "summary": {
            "schema_version": "wetlab_tcruzi_pde_translation_evidence_probe_v1",
            "root": root.as_posix(),
            "candidate_file_count": len(files),
            "candidate_files": [path.as_posix() for path in files],
            "requested_fields": list(REQUESTED_FIELDS),
            "parse_error_count": len(errors),
        },
        "metrics": metrics,
        "errors": errors,
    }


def _write_report(payload: dict[str, Any], out_json: Path | None) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if out_json is None:
        print(encoded)
        return
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(encoded + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-json", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = build_probe(args.root)
    _write_report(payload, args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
