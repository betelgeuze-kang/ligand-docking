#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import math
import hashlib
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.residual_evidence import IDENTITY_FIELDS, declared_evaluation_only, paired_energy_fields

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE5_GLOB = "runs/*stage5_ranking_rows.csv"
DEFAULT_OUT_CSV = "runs/residual_production_supervised_dataset_current.csv"
DEFAULT_OUT_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_OUT_MD = "runs/residual_production_supervised_dataset_current.md"

SCORE_COLUMNS = (
    "binding_score_composite_v7",
    "binding_score_composite_v6",
    "binding_score_composite_v5",
    "binding_score_composite_v4",
)
ENERGY_PROXY_COLUMNS = (
    "deltaG_mm_gbsa_kcal_mol",
    "binding_energy_explicit_water_recheck_kcal_mol_proxy",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
    "physics_favorable_energy_proxy",
    "mean_e_vdw",
    "mean_e_polar",
    "mean_e_nonpolar",
    "mean_e_solvation",
)
REFINE_FEATURE_COLUMNS = (
    "refine_tier_delta",
    "mm_gbsa_delta",
    "refine_confidence",
    "physics_refinement_confidence",
    "physics_refinement_delta_kcal_mol",
)

CLAIM_BOUNDARY = (
    "Residual production supervised dataset materializer only; normalizes existing local stage5 ranking rows with "
    "binder/reference labels into a supervised dataset for residual-checkpoint preparation. It does not run docking, "
    "train models, create checkpoints, change rankings, promote production mode, upload, submit, email, delete, or "
    "mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    if isinstance(value, bool) or number is None or not number.is_integer():
        return None
    return int(number)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _score_col(fieldnames: list[str]) -> str:
    fields = set(fieldnames)
    for col in SCORE_COLUMNS:
        if col in fields:
            return col
    return ""


def _stage3_path_from_stage5(path: Path) -> Path:
    name = path.name
    if name.endswith("_stage5_ranking_rows.csv"):
        return path.with_name(name.replace("_stage5_ranking_rows.csv", "_stage3_scores.csv"))
    return path


def _load_energy_proxy_map(stage3_path: Path) -> tuple[dict[tuple[str, str], tuple[float, str]], dict[str, Any]]:
    proxies: dict[tuple[str, str], tuple[float, str]] = {}
    seen: set[tuple[str, str]] = set()
    ambiguous: set[tuple[str, str]] = set()
    if not stage3_path.exists():
        return proxies, {
            "stage3_csv": _rel(stage3_path),
            "stage3_energy_proxy_status": "missing_stage3_source",
            "stage3_energy_proxy_rows": 0,
            "stage3_energy_proxy_column": "",
        }
    try:
        with stage3_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            fields = set(fieldnames)
            if "target" not in fields or "ligand_id" not in fields:
                return proxies, {
                    "stage3_csv": _rel(stage3_path),
                    "stage3_energy_proxy_status": "skipped_missing_join_columns",
                    "stage3_energy_proxy_rows": 0,
                    "stage3_energy_proxy_column": "",
                }
            energy_cols = [col for col in ENERGY_PROXY_COLUMNS if col in fields]
            for raw in reader:
                target = str(raw.get("target") or "").strip()
                ligand_id = str(raw.get("ligand_id") or "").strip()
                if not target or not ligand_id:
                    continue
                key = (target, ligand_id)
                if key in seen:
                    ambiguous.add(key)
                    proxies.pop(key, None)
                    continue
                seen.add(key)
                for col in energy_cols:
                    value = _float(raw.get(col))
                    if value is None:
                        continue
                    proxies[(target, ligand_id)] = (value, col)
                    break
    except (OSError, UnicodeError, csv.Error) as exc:
        return {}, {
            "stage3_csv": _rel(stage3_path),
            "stage3_energy_proxy_status": f"read_error:{exc}",
            "stage3_energy_proxy_rows": 0,
            "stage3_energy_proxy_column": "",
        }
    used_cols = sorted({col for _, col in proxies.values()})
    return proxies, {
        "stage3_csv": _rel(stage3_path),
        "stage3_energy_proxy_status": "used" if proxies else "no_energy_proxy_rows",
        "stage3_ambiguous_join_keys": len(ambiguous),
        "stage3_energy_proxy_rows": len(proxies),
        "stage3_energy_proxy_column": ",".join(used_cols),
    }


def _family_from_target(target: str) -> str:
    target_l = target.lower()
    if "gpcr" in target_l or "adrb" in target_l or "drd" in target_l:
        return "gpcr"
    if "trpv" in target_l or "ion" in target_l:
        return "ion_channel"
    if "kinase" in target_l or "egfr" in target_l or "kras" in target_l:
        return "kinase"
    if "carbonic_anhydrase" in target_l or "ca2" in target_l:
        return "ca2"
    if "pxr" in target_l or "nr1i2" in target_l:
        return "pxr"
    if "aqp" in target_l or "glut" in target_l:
        return "transporter"
    return "unknown"


def _iter_source_rows(path: Path, *, max_rows_per_source: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scanned = 0
    skipped = 0
    energy_joined = 0
    pair_rejected = 0
    stopped_at_limit = False
    rejections: list[dict[str, Any]] = []
    energy_proxy_map, energy_source = _load_energy_proxy_map(_stage3_path_from_stage5(path))
    try:
        source_bytes = path.read_bytes()
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        with io.StringIO(source_bytes.decode("utf-8"), newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            score_col = _score_col(fieldnames)
            required = {"target", "ligand_id", "is_binder", "reference_binding_kcal_mol"}
            if not required.issubset(set(fieldnames)) or not score_col:
                return [], {
                    "source_csv": _rel(path),
                    "scanned_rows": 0,
                    "emitted_rows": 0,
                    "skipped_rows": 0,
                    "status": "skipped_missing_required_columns",
                    "score_col": score_col,
                }
            for raw in reader:
                if len(rows) >= max_rows_per_source:
                    stopped_at_limit = True
                    break
                scanned += 1
                if declared_evaluation_only(raw):
                    skipped += 1
                    rejections.append({"source_line": reader.line_num, "reason": "evaluation_only_row"})
                    continue
                target = str(raw.get("target") or "").strip()
                ligand_id = str(raw.get("ligand_id") or "").strip()
                is_binder = _int(raw.get("is_binder"))
                reference = _float(raw.get("reference_binding_kcal_mol"))
                score = _float(raw.get(score_col))
                if not target or not ligand_id or is_binder not in {0, 1} or reference is None or score is None:
                    skipped += 1
                    rejections.append({"source_line": reader.line_num, "reason": "invalid_identity_or_label"})
                    continue
                mean_min_distance = _float(raw.get("mean_min_distance_A"))
                delta_score = reference - score
                if not math.isfinite(delta_score):
                    skipped += 1
                    rejections.append({"source_line": reader.line_num, "reason": "nonfinite_score_proxy_difference"})
                    continue
                row = {
                    "target": target,
                    "family": _family_from_target(target),
                    "ligand_id": ligand_id,
                    "is_binder": is_binder,
                    "role": str(raw.get("role") or "unknown").strip() or "unknown",
                    "reference_binding_kcal_mol": reference,
                    "raw_score": score,
                    "score_col": score_col,
                    "delta_score": delta_score,
                    "corrected_score": reference,
                    "mean_min_distance_A": mean_min_distance if mean_min_distance is not None else "",
                    "source_csv": _rel(path),
                    "label_source": "local_stage5_ranking_rows",
                    "label_evidence_kind": "unverified_local_label",
                    "score_residual_semantics": "legacy_reference_minus_composite_proxy_not_physical_energy",
                    "source_line": reader.line_num,
                    "source_sha256": source_digest,
                    "pose_id": str(raw.get("pose_id") or ""),
                    **{key: str(raw.get(key) or "") for key in IDENTITY_FIELDS},
                }
                # A target/ligand join does not identify a pose. Keep a loose
                # proxy association as diagnostics only, never a residual label.
                energy_proxy = energy_proxy_map.get((target, ligand_id))
                row.update(
                    stage3_energy_proxy_value=energy_proxy[0] if energy_proxy else "",
                    stage3_energy_proxy_column=energy_proxy[1] if energy_proxy else "",
                    stage3_proxy_association="target_ligand_only_not_pose_verified" if energy_proxy else "unavailable",
                    refine_tier_label="", refine_tier_label_source="",
                )
                row.update(paired_energy_fields(raw))
                if row["energy_pair_status"] == "declared_identity_matched":
                    energy_joined += 1
                elif row["energy_pair_status"] == "rejected":
                    pair_rejected += 1
                for col in REFINE_FEATURE_COLUMNS:
                    val = _float(raw.get(col))
                    row[col] = val if val is not None else ""
                rows.append(row)
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], {
            "source_csv": _rel(path),
            "scanned_rows": scanned,
            "emitted_rows": 0,
            "skipped_rows": skipped,
            "status": f"read_error:{exc}",
            "score_col": "",
            **energy_source,
        }
    return rows, {
        "source_csv": _rel(path),
        "source_sha256": source_digest,
        "scanned_rows": scanned,
        "emitted_rows": len(rows),
        "skipped_rows": skipped,
        "status": "used" if rows else "no_usable_rows",
        "score_col": rows[0]["score_col"] if rows else "",
        "delta_energy_label_rows": energy_joined,
        "energy_pair_rejected_rows": pair_rejected,
        "rejections": rejections,
        "stopped_at_row_limit": stopped_at_limit,
        **energy_source,
    }


def build_residual_production_supervised_dataset(
    *,
    stage5_glob: str = DEFAULT_STAGE5_GLOB,
    max_sources: int = 24,
    max_rows_per_source: int = 500,
    min_rows: int = 1000,
    min_targets: int = 3,
) -> dict[str, Any]:
    for name, value in (("max_sources", max_sources), ("max_rows_per_source", max_rows_per_source),
                        ("min_rows", min_rows), ("min_targets", min_targets)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    paths = [Path(path) for path in sorted(glob.glob(str(_resolve(stage5_glob))))]
    rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    target_counts: dict[str, int] = {}
    binder_count = 0
    negative_count = 0
    delta_energy_label_count = 0
    for path in paths[: max(0, max_sources)]:
        emitted, source = _iter_source_rows(path, max_rows_per_source=max_rows_per_source)
        source_rows.append(source)
        for row in emitted:
            rows.append(row)
            target = str(row["target"])
            target_counts[target] = target_counts.get(target, 0) + 1
            if int(row["is_binder"]) == 1:
                binder_count += 1
            else:
                negative_count += 1
            if _float(row.get("delta_energy")) is not None:
                delta_energy_label_count += 1

    ready = bool(len(rows) >= min_rows and len(target_counts) >= min_targets and binder_count > 0 and negative_count > 0)
    label_fields = ["is_binder", "reference_binding_kcal_mol", "delta_score", "corrected_score"]
    missing_production_output_labels = ["delta_energy", "delta_force", "uncertainty", "abstention_reason", "stage2_route_decision"]
    if delta_energy_label_count:
        label_fields.append("delta_energy")
        missing_production_output_labels = [field for field in missing_production_output_labels if field != "delta_energy"]
    summary = {
        "packet_type": "residual_production_supervised_dataset",
        "status": "residual_score_candidate_dataset_ready" if ready else "blocked_residual_score_candidate_dataset",
        "score_candidate_dataset_ready": ready,
        "production_supervised_dataset_ready": False,
        "physical_energy_residual_validated": False,
        "evidence_validation_scope": "declared_identity_and_value_checks_not_source_authentication",
        "rows_emitted": len(rows),
        "binder_rows": binder_count,
        "negative_rows": negative_count,
        "unknown_label_rows": 0,
        "targets": len(target_counts),
        "families": sorted({str(row["family"]) for row in rows}),
        "feature_dim": 3,
        "label_fields": label_fields,
        "delta_energy_label_rows": delta_energy_label_count,
        "delta_energy_label_source": "declared_matched_potential_energy_pair" if delta_energy_label_count else "",
        "energy_pair_rejected_rows": sum(int(source.get("energy_pair_rejected_rows", 0)) for source in source_rows),
        "feature_fields": ["raw_score", "mean_min_distance_A", "family"],
        "missing_production_output_labels": missing_production_output_labels,
        "stage5_source_count": len(paths),
        "used_source_count": sum(1 for row in source_rows if row.get("status") == "used"),
        "source_glob": stage5_glob,
        "min_rows": min_rows,
        "min_targets": min_targets,
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use only for diagnostic score-candidate training; validate measured-label provenance and task units before production use."
            if ready
            else "Collect documented development-only labels; do not use protected evaluation data for training."
        ),
    }
    return {"summary": summary, "rows": rows, "sources": source_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], csv_path: str) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Production Supervised Dataset",
        "",
        f"- status: `{s['status']}`",
        f"- production_supervised_dataset_ready: `{s['production_supervised_dataset_ready']}`",
        f"- rows_emitted: `{s['rows_emitted']}`",
        f"- binder_rows: `{s['binder_rows']}`",
        f"- negative_rows: `{s['negative_rows']}`",
        f"- unknown_label_rows: `{s['unknown_label_rows']}`",
        f"- targets: `{s['targets']}`",
        f"- families: `{','.join(s['families'])}`",
        f"- dataset_csv: `{csv_path}`",
        "",
        "## Source Files",
        "",
        "| source | status | emitted | score col |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["sources"][:24]:
        lines.append(f"| `{row['source_csv']}` | `{row['status']}` | `{row['emitted_rows']}` | `{row['score_col']}` |")
    lines.extend(
        [
            "",
            "## Label Boundary",
            "",
            "- Score residual labels are present: `delta_score`, `corrected_score`.",
            f"- Declared-identity-matched potential-energy residuals: `{s['delta_energy_label_rows']}`.",
            "- Legacy reference-minus-composite score labels are diagnostic proxies, not physical energy differences.",
            "- Source authenticity and scientific usefulness are not validated by matching declared hashes.",
            f"- Production output labels still missing here: `{','.join(s['missing_production_output_labels'])}`.",
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize a supervised protein-ligand residual dataset from local stage5 ranking rows.")
    parser.add_argument("--stage5-glob", default=DEFAULT_STAGE5_GLOB)
    parser.add_argument("--max-sources", type=int, default=24)
    parser.add_argument("--max-rows-per-source", type=int, default=500)
    parser.add_argument("--min-rows", type=int, default=1000)
    parser.add_argument("--min-targets", type=int, default=3)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_production_supervised_dataset(
        stage5_glob=args.stage5_glob,
        max_sources=args.max_sources,
        max_rows_per_source=args.max_rows_per_source,
        min_rows=args.min_rows,
        min_targets=args.min_targets,
    )
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload, args.out_csv)


if __name__ == "__main__":
    main()
