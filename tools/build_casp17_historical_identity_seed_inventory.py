#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_MONOMER_NATIVE_DIR = "data/native"
DEFAULT_MONOMER_PREDICTION_ROOT = "data/internal_structures_refined"
DEFAULT_COMPLEX_ROOT = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_current"
DEFAULT_OUT_JSON = "runs/casp17_historical_identity_seed_inventory_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_identity_seed_inventory_current.csv"
DEFAULT_OUT_MD = "runs/CASP17_HISTORICAL_IDENTITY_SEED_INVENTORY.md"
DEFAULT_OUT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"

SEED_COLUMNS = [
    "seed_rank",
    "batch_slot",
    "seed_status",
    "scope",
    "benchmark_id",
    "target_id",
    "target_label",
    "prediction_pdb",
    "native_pdb",
    "prediction_atom_count",
    "native_atom_count",
    "prediction_chain_count",
    "native_chain_count",
    "source_kind",
    "collision_status",
    "blockers",
    "next_action",
]
MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]
CLAIM_BOUNDARY = (
    "Local CASP17 historical identity seed inventory only. It discovers local non-current-looking seed "
    "identity candidates with paired local prediction/native PDB paths and prepares a blocked seed manifest "
    "for operator review. It does not clear no-leak provenance, certify prediction/native chronology, fetch "
    "native structures, score native accuracy, mutate the active competitive-floor intake, run predictors, "
    "or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return text or "unknown"


def _target_id(prefix: str, label: str) -> str:
    body = re.sub(r"[^A-Za-z0-9]+", "_", label.strip().upper()).strip("_")
    return f"{prefix}_{body}"[:80]


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    return rows, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames)
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb_stats(path_like: str | Path) -> tuple[int, int]:
    path = _resolve(path_like)
    if not path.exists():
        return 0, 0
    atom_count = 0
    chains: set[str] = set()
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("ATOM"):
                continue
            atom_count += 1
            chain_id = line[21:22].strip()
            if chain_id:
                chains.add(chain_id)
    return atom_count, len(chains)


def _current_target_tokens(path_like: str | Path) -> set[str]:
    rows, blockers = _read_csv(path_like)
    if blockers:
        return set()
    tokens: set[str] = set()
    for row in rows:
        for column in ("target_id", "protein_name", "folder_name"):
            value = _text(row.get(column))
            if value:
                tokens.add(_slug(value))
                tokens.add(value.upper())
    return tokens


def _native_lookup(native_dir: str | Path) -> dict[str, Path]:
    root = _resolve(native_dir)
    if not root.exists():
        return {}
    return {_slug(path.stem): path for path in root.rglob("*.pdb") if path.is_file()}


def _prediction_slug(path: Path) -> str:
    stem = path.stem
    prefix = "visual_post_internal_post_"
    if not stem.startswith(prefix) or "_sample" not in stem:
        return ""
    return stem[len(prefix) : stem.index("_sample")]


def _monomer_seed_rows(args: argparse.Namespace, current_tokens: set[str]) -> list[dict[str, Any]]:
    native_by_slug = _native_lookup(args.monomer_native_dir)
    prediction_root = _resolve(args.monomer_prediction_root)
    if not prediction_root.exists():
        return []
    predictions_by_slug: dict[str, Path] = {}
    for prediction in sorted(prediction_root.rglob("*.pdb")):
        slug = _prediction_slug(prediction)
        if not slug:
            continue
        current = predictions_by_slug.get(slug)
        if current is None or prediction.name > current.name:
            predictions_by_slug[slug] = prediction
    rows: list[dict[str, Any]] = []
    for label in sorted(predictions_by_slug):
        native = native_by_slug.get(_slug(label))
        if native is None:
            continue
        rows.append(
            _seed_row(
                scope="monomer",
                label=label,
                prediction=predictions_by_slug[label],
                native=native,
                source_kind="paired_native_internal_prediction",
                current_tokens=current_tokens,
            )
        )
    return rows


def _complex_seed_rows(args: argparse.Namespace, current_tokens: set[str]) -> list[dict[str, Any]]:
    root = _resolve(args.complex_root)
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        prediction = folder / "protein_ligand_complex_minimized.pdb"
        native = folder / "protein_ligand_complex.pdb"
        if not prediction.exists() or not native.exists():
            continue
        label = _slug(folder.name)
        rows.append(
            _seed_row(
                scope="complex",
                label=label,
                prediction=prediction,
                native=native,
                source_kind="paired_protein_ligand_complex_minimized",
                current_tokens=current_tokens,
            )
        )
    return rows


def _seed_row(
    *,
    scope: str,
    label: str,
    prediction: Path,
    native: Path,
    source_kind: str,
    current_tokens: set[str],
) -> dict[str, Any]:
    slug = _slug(label)
    prefix = "HIST_COMPLEX" if scope == "complex" else "HIST"
    target_id = _target_id(prefix, slug)
    benchmark_id = f"hist_seed_{slug}"
    prediction_atoms, prediction_chains = _pdb_stats(prediction)
    native_atoms, native_chains = _pdb_stats(native)
    collision = target_id.upper() in current_tokens or slug in current_tokens
    blockers: list[str] = []
    if prediction_atoms <= 0:
        blockers.append("prediction_pdb_has_no_protein_atoms")
    if native_atoms <= 0:
        blockers.append("native_pdb_has_no_protein_atoms")
    if collision:
        blockers.append("current_casp17_target_collision")
    blockers.extend(
        [
            "no_leak_provenance_required",
            "operator_clearance_required",
            "prediction_created_at_required_iso_date",
            "native_release_date_required_iso_date",
            "calibration_values_required",
            "ablation_layers_required",
        ]
    )
    hard_blockers = {"prediction_pdb_has_no_protein_atoms", "native_pdb_has_no_protein_atoms", "current_casp17_target_collision"}
    status = "blocked_seed_source" if hard_blockers & set(blockers) else "operator_clearance_required"
    return {
        "seed_rank": 0,
        "batch_slot": 0,
        "seed_status": status,
        "scope": scope,
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "target_label": slug,
        "prediction_pdb": _artifact(prediction),
        "native_pdb": _artifact(native),
        "prediction_atom_count": prediction_atoms,
        "native_atom_count": native_atoms,
        "prediction_chain_count": prediction_chains,
        "native_chain_count": native_chains,
        "source_kind": source_kind,
        "collision_status": "current_collision" if collision else "no_current_target_id_or_name_collision_detected",
        "blockers": ",".join(blockers),
        "next_action": "operator must verify no-leak provenance, chronology, calibration values, and ablation files before promotion",
    }


def _assign_ranks(
    monomer_rows: list[dict[str, Any]],
    complex_rows: list[dict[str, Any]],
    *,
    batch_monomer_count: int,
    batch_complex_count: int,
) -> list[dict[str, Any]]:
    selected_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    seed_rank = 0
    batch_slot = 0
    for pool, quota in ((monomer_rows, batch_monomer_count), (complex_rows, batch_complex_count)):
        selected_in_pool = 0
        for row in pool:
            seed_rank += 1
            item = dict(row)
            item["seed_rank"] = seed_rank
            if selected_in_pool < quota and row["seed_status"] == "operator_clearance_required":
                batch_slot += 1
                selected_in_pool += 1
                selected_ids.add(row["target_id"])
                item["batch_slot"] = batch_slot
            rows.append(item)
    remaining = [row for row in monomer_rows + complex_rows if row["target_id"] not in selected_ids]
    for row in remaining:
        if any(existing["target_id"] == row["target_id"] for existing in rows):
            continue
        seed_rank += 1
        item = dict(row)
        item["seed_rank"] = seed_rank
        rows.append(item)
    return rows


def _manifest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for row in rows:
        if _int(row.get("batch_slot")) <= 0:
            continue
        manifest.append(
            {
                "benchmark_id": row["benchmark_id"],
                "target_id": row["target_id"],
                "scope": row["scope"],
                "split": "historical_seed",
                "prediction_pdb": row["prediction_pdb"],
                "native_pdb": row["native_pdb"],
                "leakage_clearance": "",
                "prediction_method": "internal_physics_seed_inventory",
                "prediction_created_at": "",
                "native_release_date": "",
                "prediction_generated_before_native_release": "",
                "public_template_or_native_used_for_prediction": "",
                "other_team_model_used": "",
                "post_release_information_used": "",
                "current_casp17_target": "false",
                "operator_clearance": "",
            }
        )
    return manifest


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    current_tokens = _current_target_tokens(args.current_target_csv)
    monomer_rows = _monomer_seed_rows(args, current_tokens)
    complex_rows = _complex_seed_rows(args, current_tokens)
    rows = _assign_ranks(
        monomer_rows,
        complex_rows,
        batch_monomer_count=args.batch_monomer_count,
        batch_complex_count=args.batch_complex_count,
    )
    manifest_rows = _manifest_rows(rows)
    selected_rows = [row for row in rows if _int(row.get("batch_slot")) > 0]
    eligible_monomer_count = sum(
        1 for row in rows if row["scope"] == "monomer" and row["seed_status"] == "operator_clearance_required"
    )
    eligible_complex_count = sum(
        1 for row in rows if row["scope"] == "complex" and row["seed_status"] == "operator_clearance_required"
    )
    required_total = args.batch_monomer_count + args.batch_complex_count
    if len(selected_rows) >= required_total:
        status = "batch_seed_shape_ready_operator_clearance_required"
    elif rows:
        status = "insufficient_seed_shape"
    else:
        status = "missing_local_seed_sources"
    first = selected_rows[0] if selected_rows else rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_historical_identity_seed_inventory",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "seed_inventory_status": status,
        "current_target_csv": _artifact(args.current_target_csv),
        "monomer_native_dir": _artifact(args.monomer_native_dir),
        "monomer_prediction_root": _artifact(args.monomer_prediction_root),
        "complex_root": _artifact(args.complex_root),
        "seed_candidate_count": len(rows),
        "monomer_seed_candidate_count": sum(1 for row in rows if row["scope"] == "monomer"),
        "complex_seed_candidate_count": sum(1 for row in rows if row["scope"] == "complex"),
        "eligible_monomer_seed_count": eligible_monomer_count,
        "eligible_complex_seed_count": eligible_complex_count,
        "batch_monomer_required_count": args.batch_monomer_count,
        "batch_complex_required_count": args.batch_complex_count,
        "batch_seed_slot_count": len(selected_rows),
        "candidate_manifest_row_count": len(manifest_rows),
        "candidate_manifest_csv": _artifact(args.out_manifest_csv),
        "operator_clearance_required_count": sum(1 for row in selected_rows if row["seed_status"] == "operator_clearance_required"),
        "blocked_seed_source_count": sum(1 for row in rows if row["seed_status"] == "blocked_seed_source"),
        "first_seed_benchmark_id": _text(first.get("benchmark_id")),
        "first_seed_target_id": _text(first.get("target_id")),
        "first_next_action": _text(first.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "manifest_rows": manifest_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Identity Seed Inventory",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- seed_inventory_status: `{summary['seed_inventory_status']}`",
        f"- seed candidates monomer/complex/total: `{summary['monomer_seed_candidate_count']}/{summary['complex_seed_candidate_count']}/{summary['seed_candidate_count']}`",
        f"- eligible monomer/complex: `{summary['eligible_monomer_seed_count']}/{summary['eligible_complex_seed_count']}`",
        f"- batch required monomer/complex: `{summary['batch_monomer_required_count']}/{summary['batch_complex_required_count']}`",
        f"- batch seed slots / manifest rows: `{summary['batch_seed_slot_count']}/{summary['candidate_manifest_row_count']}`",
        f"- candidate manifest: `{summary['candidate_manifest_csv']}`",
        f"- first seed: `{summary['first_seed_benchmark_id'] or '-'}` `{summary['first_seed_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Batch Seeds",
        "",
        "| slot | scope | benchmark | target | prediction atoms | native atoms | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        if _int(row.get("batch_slot")) <= 0:
            continue
        lines.append(
            f"| {row['batch_slot']} | `{row['scope']}` | `{row['benchmark_id']}` | `{row['target_id']}` | "
            f"{row['prediction_atom_count']} | {row['native_atom_count']} | `{row['blockers']}` |"
        )
    if not payload["manifest_rows"]:
        lines.append("| - | - | - | - | 0 | 0 | `missing_local_seed_sources` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], SEED_COLUMNS)
    _write_csv(args.out_manifest_csv, payload["manifest_rows"], MANIFEST_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical identity seed inventory.")
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--monomer-native-dir", default=DEFAULT_MONOMER_NATIVE_DIR)
    parser.add_argument("--monomer-prediction-root", default=DEFAULT_MONOMER_PREDICTION_ROOT)
    parser.add_argument("--complex-root", default=DEFAULT_COMPLEX_ROOT)
    parser.add_argument("--batch-monomer-count", type=int, default=10)
    parser.add_argument("--batch-complex-count", type=int, default=5)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-manifest-csv", default=DEFAULT_OUT_MANIFEST_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
