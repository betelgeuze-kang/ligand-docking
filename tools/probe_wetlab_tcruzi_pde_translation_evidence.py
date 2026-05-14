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
TRANSLATION_ENERGY_THRESHOLD = -0.55
TRANSLATION_DISTANCE_THRESHOLD_A = 3.10
TRANSLATION_STABILITY_THRESHOLD = 0.32


def _is_candidate_file(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    path_text = path.as_posix()
    name = path.name
    if (
        "wetlab_broad_screen_throughput/t_cruzi_pde" in path_text
        and path.suffix.lower() == ".csv"
        and ("stage3_scores" in name or "stage4_calibration_scores" in name)
    ):
        return True
    if (
        "wetlab_rescue_three_bead/t_cruzi_pde" in path_text
        and path.suffix.lower() == ".csv"
        and name == "three_bead_slice_scores.csv"
    ):
        return True
    if (
        "wetlab_tcruzi_pde_external_pdeb1_seed_screen" in path_text
        and path.suffix.lower() == ".csv"
        and name == "stage3_scores.csv"
    ):
        return True
    if (
        "wetlab_tcruzi_pde_external_geomstab_rescore" in path_text
        and path.suffix.lower() == ".csv"
        and name == "stage3_scores.csv"
    ):
        return True
    if (
        "wetlab_tcruzi_pde_external_geomstab_adress_rescue_scores" in path_text
        and path.suffix.lower() == ".csv"
        and name == "stage3_scores.csv"
    ):
        return True
    if (
        "wetlab_tcruzi_pde_external_geomstab_contact_rescue_scores" in path_text
        and path.suffix.lower() == ".csv"
        and name == "stage3_scores.csv"
    ):
        return True
    if "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" in path_text and path.suffix.lower() == ".csv":
        stage_prefix = name.removesuffix("_stage3_scores.csv")
        if name == "stage3_scores.csv" or (
            name.endswith("_stage3_scores.csv") and any(character.isdigit() for character in stage_prefix)
        ):
            return True
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


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _score_record(path: Path, row: dict[str, Any], row_number: int) -> dict[str, Any] | None:
    energy = _safe_float(row.get("binding_energy_proxy"))
    distance = _safe_float(row.get("mean_min_distance_A"))
    stability = _safe_float(row.get("stability_score"))
    if energy is None and distance is None and stability is None:
        return None
    contact = _safe_float(row.get("contact_fraction"))
    frames = _safe_float(row.get("trajectory_frames"))
    energy_pass = energy is not None and energy <= TRANSLATION_ENERGY_THRESHOLD
    distance_pass = distance is not None and distance <= TRANSLATION_DISTANCE_THRESHOLD_A
    stability_pass = stability is not None and stability >= TRANSLATION_STABILITY_THRESHOLD
    path_text = path.as_posix()
    if "wetlab_tcruzi_pde_external_geomstab_contact_rescue_scores" in path_text:
        source_pool_class = "external_homolog_pdeb1_contact_rescue"
    elif "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" in path_text:
        source_pool_class = "external_bindingdb_similarity_seed"
    elif "wetlab_tcruzi_pde_external_geomstab_adress_rescue_scores" in path_text:
        source_pool_class = "external_homolog_pdeb1_adress_rescue"
    elif "wetlab_tcruzi_pde_external_geomstab_rescore" in path_text:
        source_pool_class = "external_homolog_pdeb1_geomstab_rescore"
    elif "wetlab_tcruzi_pde_external_pdeb1_seed_screen" in path_text:
        source_pool_class = "external_homolog_pdeb1_seed"
    else:
        source_pool_class = "internal_tcruzi_pde_candidate_pool"
    return {
        "source_path": path.as_posix(),
        "source_pool_class": source_pool_class,
        "row_number": row_number,
        "target": row.get("target", ""),
        "ligand_id": row.get("ligand_id", ""),
        "binding_energy_proxy": energy,
        "mean_min_distance_A": distance,
        "stability_score": stability,
        "contact_fraction": contact,
        "trajectory_frames": frames,
        "translation_energy_pass": energy_pass,
        "translation_distance_pass": distance_pass,
        "translation_stability_pass": stability_pass,
        "translation_core_pass": energy_pass and distance_pass and stability_pass,
        "translation_core_like": distance_pass and stability_pass,
    }


def _compact_score_record(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    keys = [
        "source_path",
        "source_pool_class",
        "row_number",
        "target",
        "ligand_id",
        "binding_energy_proxy",
        "mean_min_distance_A",
        "stability_score",
        "contact_fraction",
        "trajectory_frames",
        "translation_core_pass",
        "translation_core_like",
    ]
    return {key: record.get(key) for key in keys}


def _score_scan_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    with_energy = [record for record in records if record.get("binding_energy_proxy") is not None]
    core_like = [record for record in records if record.get("translation_core_like")]
    core_pass = [record for record in records if record.get("translation_core_pass")]
    energy_pass = [record for record in records if record.get("translation_energy_pass")]
    external_homolog = [record for record in records if record.get("source_pool_class") == "external_homolog_pdeb1_seed"]
    external_geomstab_rescore = [
        record for record in records if record.get("source_pool_class") == "external_homolog_pdeb1_geomstab_rescore"
    ]
    external_adress_rescue = [
        record for record in records if record.get("source_pool_class") == "external_homolog_pdeb1_adress_rescue"
    ]
    external_contact_rescue = [
        record for record in records if record.get("source_pool_class") == "external_homolog_pdeb1_contact_rescue"
    ]
    external_bindingdb_similarity = [
        record for record in records if record.get("source_pool_class") == "external_bindingdb_similarity_seed"
    ]
    external_with_energy = [record for record in external_homolog if record.get("binding_energy_proxy") is not None]
    external_core_pass = [record for record in external_homolog if record.get("translation_core_pass")]
    external_energy_pass = [record for record in external_homolog if record.get("translation_energy_pass")]
    external_rescore_with_energy = [
        record for record in external_geomstab_rescore if record.get("binding_energy_proxy") is not None
    ]
    external_rescore_core_pass = [record for record in external_geomstab_rescore if record.get("translation_core_pass")]
    external_rescore_energy_pass = [record for record in external_geomstab_rescore if record.get("translation_energy_pass")]
    external_adress_with_energy = [
        record for record in external_adress_rescue if record.get("binding_energy_proxy") is not None
    ]
    external_adress_core_pass = [record for record in external_adress_rescue if record.get("translation_core_pass")]
    external_adress_energy_pass = [record for record in external_adress_rescue if record.get("translation_energy_pass")]
    external_contact_with_energy = [
        record for record in external_contact_rescue if record.get("binding_energy_proxy") is not None
    ]
    external_contact_core_pass = [record for record in external_contact_rescue if record.get("translation_core_pass")]
    external_contact_energy_pass = [record for record in external_contact_rescue if record.get("translation_energy_pass")]
    external_bindingdb_similarity_with_energy = [
        record for record in external_bindingdb_similarity if record.get("binding_energy_proxy") is not None
    ]
    external_bindingdb_similarity_core_pass = [
        record for record in external_bindingdb_similarity if record.get("translation_core_pass")
    ]
    external_bindingdb_similarity_energy_pass = [
        record for record in external_bindingdb_similarity if record.get("translation_energy_pass")
    ]
    best_energy = min(with_energy, key=lambda record: record["binding_energy_proxy"], default=None)
    best_core_like = min(core_like, key=lambda record: record["binding_energy_proxy"], default=None)
    best_external_energy = min(external_with_energy, key=lambda record: record["binding_energy_proxy"], default=None)
    best_external_rescore_energy = min(
        external_rescore_with_energy,
        key=lambda record: record["binding_energy_proxy"],
        default=None,
    )
    best_external_adress_energy = min(
        external_adress_with_energy,
        key=lambda record: record["binding_energy_proxy"],
        default=None,
    )
    best_external_contact_energy = min(
        external_contact_with_energy,
        key=lambda record: record["binding_energy_proxy"],
        default=None,
    )
    best_external_bindingdb_similarity_energy = min(
        external_bindingdb_similarity_with_energy,
        key=lambda record: record["binding_energy_proxy"],
        default=None,
    )
    unique_ligands = {str(record.get("ligand_id", "")).strip() for record in records if str(record.get("ligand_id", "")).strip()}
    energy_pass_unique_ligands = {
        str(record.get("ligand_id", "")).strip()
        for record in energy_pass
        if str(record.get("ligand_id", "")).strip()
    }
    core_pass_unique_ligands = {
        str(record.get("ligand_id", "")).strip()
        for record in core_pass
        if str(record.get("ligand_id", "")).strip()
    }
    return {
        "translation_score_candidate_file_count": len({record["source_path"] for record in records}),
        "translation_score_candidate_row_count": len(records),
        "translation_score_candidate_unique_ligand_count": len(unique_ligands),
        "translation_energy_pass_unique_ligand_count": len(energy_pass_unique_ligands),
        "translation_core_pass_unique_ligand_count": len(core_pass_unique_ligands),
        "external_homolog_seed_candidate_file_count": len(
            {record["source_path"] for record in external_homolog}
        ),
        "external_homolog_seed_candidate_row_count": len(external_homolog),
        "external_homolog_geomstab_rescore_candidate_file_count": len(
            {record["source_path"] for record in external_geomstab_rescore}
        ),
        "external_homolog_geomstab_rescore_candidate_row_count": len(external_geomstab_rescore),
        "external_homolog_adress_rescue_candidate_file_count": len(
            {record["source_path"] for record in external_adress_rescue}
        ),
        "external_homolog_adress_rescue_candidate_row_count": len(external_adress_rescue),
        "external_homolog_contact_rescue_candidate_file_count": len(
            {record["source_path"] for record in external_contact_rescue}
        ),
        "external_homolog_contact_rescue_candidate_row_count": len(external_contact_rescue),
        "external_bindingdb_similarity_candidate_file_count": len(
            {record["source_path"] for record in external_bindingdb_similarity}
        ),
        "external_bindingdb_similarity_candidate_row_count": len(external_bindingdb_similarity),
        "translation_energy_threshold": TRANSLATION_ENERGY_THRESHOLD,
        "translation_distance_threshold_A": TRANSLATION_DISTANCE_THRESHOLD_A,
        "translation_stability_threshold": TRANSLATION_STABILITY_THRESHOLD,
        "translation_energy_pass_count": len(energy_pass),
        "translation_distance_pass_count": sum(1 for record in records if record.get("translation_distance_pass")),
        "translation_stability_pass_count": sum(1 for record in records if record.get("translation_stability_pass")),
        "translation_core_pass_count": len(core_pass),
        "translation_core_like_count": len(core_like),
        "external_homolog_seed_energy_pass_count": len(external_energy_pass),
        "external_homolog_seed_core_pass_count": len(external_core_pass),
        "external_homolog_geomstab_rescore_energy_pass_count": len(external_rescore_energy_pass),
        "external_homolog_geomstab_rescore_core_pass_count": len(external_rescore_core_pass),
        "external_homolog_adress_rescue_energy_pass_count": len(external_adress_energy_pass),
        "external_homolog_adress_rescue_core_pass_count": len(external_adress_core_pass),
        "external_homolog_contact_rescue_energy_pass_count": len(external_contact_energy_pass),
        "external_homolog_contact_rescue_core_pass_count": len(external_contact_core_pass),
        "external_bindingdb_similarity_energy_pass_count": len(external_bindingdb_similarity_energy_pass),
        "external_bindingdb_similarity_core_pass_count": len(external_bindingdb_similarity_core_pass),
        "best_binding_energy_proxy": None if best_energy is None else best_energy.get("binding_energy_proxy"),
        "best_binding_energy_proxy_row": _compact_score_record(best_energy),
        "best_core_like_binding_energy_proxy": None if best_core_like is None else best_core_like.get("binding_energy_proxy"),
        "best_core_like_row": _compact_score_record(best_core_like),
        "external_homolog_seed_best_binding_energy_proxy": (
            None if best_external_energy is None else best_external_energy.get("binding_energy_proxy")
        ),
        "external_homolog_seed_best_binding_energy_proxy_row": _compact_score_record(best_external_energy),
        "external_homolog_geomstab_rescore_best_binding_energy_proxy": (
            None if best_external_rescore_energy is None else best_external_rescore_energy.get("binding_energy_proxy")
        ),
        "external_homolog_geomstab_rescore_best_binding_energy_proxy_row": _compact_score_record(
            best_external_rescore_energy
        ),
        "external_homolog_adress_rescue_best_binding_energy_proxy": (
            None if best_external_adress_energy is None else best_external_adress_energy.get("binding_energy_proxy")
        ),
        "external_homolog_adress_rescue_best_binding_energy_proxy_row": _compact_score_record(
            best_external_adress_energy
        ),
        "external_homolog_contact_rescue_best_binding_energy_proxy": (
            None if best_external_contact_energy is None else best_external_contact_energy.get("binding_energy_proxy")
        ),
        "external_homolog_contact_rescue_best_binding_energy_proxy_row": _compact_score_record(
            best_external_contact_energy
        ),
        "external_bindingdb_similarity_best_binding_energy_proxy": (
            None
            if best_external_bindingdb_similarity_energy is None
            else best_external_bindingdb_similarity_energy.get("binding_energy_proxy")
        ),
        "external_bindingdb_similarity_best_binding_energy_proxy_row": _compact_score_record(
            best_external_bindingdb_similarity_energy
        ),
        "candidate_pool_supports_energy_closure": bool(core_pass),
        "candidate_pool_energy_gap_closed": bool(energy_pass),
        "candidate_pool_core_gate_closed": bool(core_pass),
        "candidate_pool_claim_scope_note": (
            "external_homolog_seed_rows_are_candidate_pool_expansion_only_not_direct_tcruzi_pde_claim"
            if (
                external_homolog
                or external_geomstab_rescore
                or external_adress_rescue
                or external_contact_rescue
                or external_bindingdb_similarity
            )
            else ""
        ),
    }


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


def _scan_csv(
    path: Path,
    index: dict[str, dict[str, Any]],
    errors: list[dict[str, str]],
    score_records: list[dict[str, Any]],
) -> None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            matching = [(field, _metric_for_key(field)) for field in fieldnames]
            matching = [(field, metric) for field, metric in matching if metric is not None]
            for row_number, row in enumerate(reader, start=2):
                score_record = _score_record(path, row, row_number)
                if score_record is not None:
                    score_records.append(score_record)
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
    score_records: list[dict[str, Any]] = []
    for path in files:
        if path.suffix.lower() == ".json":
            _scan_json(path, index, errors)
        elif path.suffix.lower() == ".csv":
            _scan_csv(path, index, errors, score_records)

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
            **_score_scan_summary(score_records),
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
