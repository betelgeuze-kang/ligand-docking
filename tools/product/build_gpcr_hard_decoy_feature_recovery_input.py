#!/usr/bin/env python3
"""Build a focused GPCR hard-decoy feature recovery input.

This bridges the current DRD2 closure blocker from "missing feature-cache rows"
to a concrete, reproducible input CSV for the existing label-free feature-cache
builder. It only joins local evidence: readiness rows, regenerated hard-decoy
labels/splits, local trajectory NPZs, and local native PDB paths.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_READINESS_CSV = "runs/gpcr_hard_decoy_replay_materialization_readiness_current.csv"
DEFAULT_LABELS_CSV = "runs/gpcr_hard_decoy_feature_recovery_labels_current.csv"
DEFAULT_SPLIT_CSV = "runs/gpcr_hard_decoy_feature_recovery_split_current.csv"
DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV = "config/gpcr_non_adrb2_native_sources_v1.csv"
DEFAULT_ADRB2_NATIVE_SOURCE_CSV = "config/real_drug_targets_blind_gpcr_adrb2_v1.csv"
DEFAULT_TRAJECTORY_ROOTS = (
    str(Path.home() / ".local/share/Trash/files/trajectory_spill/gpcr_a1_coverage_v2_beta_rescue"),
    str(Path.home() / "trajectory_spill/gpcr_a1_coverage_v2_beta_rescue"),
)
DEFAULT_OUT_INPUT_CSV = "runs/gpcr_hard_decoy_feature_recovery_input_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_feature_recovery_input_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_feature_recovery_input_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_feature_recovery_input_manifest_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_feature_recovery_input"
SCHEMA_VERSION = "gpcr_hard_decoy_feature_recovery_input_v1"

CLAIM_BOUNDARY = (
    "GPCR hard-decoy feature recovery input only; it joins local regenerated labels, local split roles, "
    "local trajectory NPZs, and local native PDB paths for the existing feature-cache builder. It does not "
    "run scoring, regenerate rankings, relax thresholds, fetch external data, mutate external state, or "
    "promote a broad-GPCR claim."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "external_fetch_enabled": False,
    "claim_promotion_allowed": False,
}

_MANIFEST_COLUMNS = [
    "target",
    "ligand_id",
    "status",
    "blockers",
    "label_ready",
    "split_ready",
    "trajectory_ready",
    "native_ready",
    "smiles_ready",
    "feature_input_ready",
    "trajectory_npz",
    "protein_structure_source_path",
    "role",
    "retained_rank",
    "retained_score",
    "score_source",
    "claim_promotion_allowed",
]

_INPUT_COLUMNS = [
    "target",
    "ligand_id",
    "is_binder",
    "reference_binding_kcal_mol",
    "binding_score_composite_v7",
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7_coverage_v2_adaptive_rank_rescue_shadow",
    "score_value",
    "retained_rank",
    "retained_score",
    "mean_min_distance_A",
    "role",
    "ligand_smiles",
    "smiles",
    "scaffold",
    "ligand_molecular_weight",
    "ligand_logp",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "ligand_rot_bonds",
    "trajectory_npz",
    "protein_structure_source_path",
    "recovery_label_source_csv",
    "recovery_split_source_csv",
    "recovery_readiness_source_csv",
    "score_source",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path | None) -> str:
    if path_like is None:
        return ""
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path_like: str | Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _index_rows(rows: Iterable[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key[0] and key[1] and key not in out:
            out[key] = row
    return out


def _missing_feature_rows(readiness_rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for row in readiness_rows:
        if _bool(row.get("scoring_feature_cache_ready")):
            continue
        ligand_id = _text(row.get("ligand_id"))
        target = _text(row.get("target_source_id")) or _text(row.get("target"))
        if not ligand_id or not target:
            continue
        blockers = _text(row.get("blockers"))
        if "scoring_feature_cache_missing" not in blockers and _text(row.get("materialization_role")) != "decoy_above_positive":
            continue
        out.append(row)
    return out


def _native_from_pdb_id(pdb_id: str) -> str:
    pdb = _text(pdb_id).lower()
    if not pdb:
        return ""
    for root in (
        ROOT / "runs/gpcr_frozen_candidate_profile_support_current/native_pdb",
        ROOT / "runs/gpcr_frozen_candidate_profile_support_coverage_v1_current/native_pdb",
    ):
        candidate = root / f"{pdb}.pdb"
        if candidate.exists():
            return str(candidate)
    return ""


def _native_lookup(paths: Sequence[str | Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in paths:
        for row in _read_csv(path):
            target = _text(row.get("target"))
            native = _text(row.get("native_pdb_path")) or _native_from_pdb_id(_text(row.get("pdb_id")))
            if target and native and target not in out:
                out[target] = str(_resolve(native))
    return out


def _trajectory_candidates(trajectory_roots: Sequence[str | Path], ligand_id: str) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for root_like in trajectory_roots:
        root = _resolve(root_like)
        if not root.exists():
            continue
        for path in sorted(root.rglob(f"*{ligand_id}.npz")):
            resolved = path.resolve()
            if path.is_file() and resolved not in seen:
                seen.add(resolved)
                candidates.append(path)
    return candidates


def _pick_trajectory(candidates: Sequence[Path]) -> str:
    if not candidates:
        return ""
    preferred = sorted(
        candidates,
        key=lambda path: (
            0 if "2026-05-17_gpcr_a1_coverage_v2_beta_rescue_fast_r1" in str(path) else 1,
            str(path),
        ),
    )
    return str(preferred[0])


def _score_value(label: dict[str, str], readiness: dict[str, str]) -> tuple[str, str]:
    # Feature-cache geometry pressures should not treat the retained rank-rescue
    # shadow score as the immutable v7 base score. The regenerated label's
    # reference binding value is the strongest recovered local base proxy.
    reference = _text(label.get("reference_binding_kcal_mol"))
    if reference:
        return reference, "reference_binding_kcal_mol_recovered_label"
    retained = _text(readiness.get("retained_score"))
    if retained:
        return retained, "retained_score_fallback"
    return "", "missing"


def _build_input_row(
    *,
    readiness_row: dict[str, str],
    label_row: dict[str, str],
    split_row: dict[str, str],
    trajectory_npz: str,
    native_pdb: str,
    labels_csv: str | Path,
    split_csv: str | Path,
    readiness_csv: str | Path,
) -> dict[str, Any]:
    score, score_source = _score_value(label_row, readiness_row)
    retained_score = _text(readiness_row.get("retained_score"))
    return {
        "target": _text(readiness_row.get("target_source_id")) or _text(label_row.get("target")),
        "ligand_id": _text(readiness_row.get("ligand_id")) or _text(label_row.get("ligand_id")),
        "is_binder": _text(label_row.get("is_binder")) or _text(readiness_row.get("is_binder")),
        "reference_binding_kcal_mol": _text(label_row.get("reference_binding_kcal_mol")),
        "binding_score_composite_v7": score,
        "binding_score_composite_v7_residual_active": score,
        "binding_score_composite_v7_coverage_v2_adaptive_rank_rescue_shadow": retained_score,
        "score_value": retained_score,
        "retained_rank": _text(readiness_row.get("retained_rank")),
        "retained_score": retained_score,
        "mean_min_distance_A": _text(readiness_row.get("anchor_distance_a")),
        "role": _text(split_row.get("role")),
        "ligand_smiles": _text(label_row.get("smiles")),
        "smiles": _text(label_row.get("smiles")),
        "scaffold": _text(label_row.get("scaffold")) or _text(label_row.get("_scaffold")),
        "ligand_molecular_weight": _text(label_row.get("molecular_weight")),
        "ligand_logp": _text(label_row.get("logp")),
        "ligand_h_donors": _text(label_row.get("h_donors")),
        "ligand_h_acceptors": _text(label_row.get("h_acceptors")),
        "ligand_rot_bonds": _text(label_row.get("rot_bonds")),
        "trajectory_npz": trajectory_npz,
        "protein_structure_source_path": native_pdb,
        "recovery_label_source_csv": _display(labels_csv),
        "recovery_split_source_csv": _display(split_csv),
        "recovery_readiness_source_csv": _display(readiness_csv),
        "score_source": score_source,
    }


def build_gpcr_hard_decoy_feature_recovery_input(
    *,
    readiness_csv: str | Path = DEFAULT_READINESS_CSV,
    labels_csv: str | Path = DEFAULT_LABELS_CSV,
    split_csv: str | Path = DEFAULT_SPLIT_CSV,
    trajectory_roots: Sequence[str | Path] = DEFAULT_TRAJECTORY_ROOTS,
    native_source_csvs: Sequence[str | Path] = (
        DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV,
        DEFAULT_ADRB2_NATIVE_SOURCE_CSV,
    ),
) -> dict[str, Any]:
    readiness_rows = _read_csv(readiness_csv)
    label_index = _index_rows(_read_csv(labels_csv))
    split_index = _index_rows(_read_csv(split_csv))
    native_by_target = _native_lookup(native_source_csvs)
    target_rows = _missing_feature_rows(readiness_rows)

    rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, Any]] = []
    for readiness_row in target_rows:
        target = _text(readiness_row.get("target_source_id")) or _text(readiness_row.get("target"))
        ligand_id = _text(readiness_row.get("ligand_id"))
        key = (target, ligand_id)
        label_row = label_index.get(key, {})
        split_row = split_index.get(key, {})
        trajectory_npz = _pick_trajectory(_trajectory_candidates(trajectory_roots, ligand_id))
        native_pdb = native_by_target.get(target, "")
        blockers: list[str] = []
        if not label_row:
            blockers.append("label_row_missing")
        if label_row and not _text(label_row.get("smiles")):
            blockers.append("smiles_missing")
        if not split_row:
            blockers.append("split_role_missing")
        if not trajectory_npz:
            blockers.append("trajectory_npz_missing")
        if not native_pdb:
            blockers.append("native_pdb_missing")
        ready = not blockers
        status = "feature_recovery_input_ready" if ready else "blocked_feature_recovery_input_incomplete"
        manifest_row = {
            "target": target,
            "ligand_id": ligand_id,
            "status": status,
            "blockers": ";".join(blockers),
            "label_ready": bool(label_row),
            "split_ready": bool(split_row),
            "trajectory_ready": bool(trajectory_npz),
            "native_ready": bool(native_pdb),
            "smiles_ready": bool(_text(label_row.get("smiles"))),
            "feature_input_ready": ready,
            "trajectory_npz": trajectory_npz,
            "protein_structure_source_path": native_pdb,
            "role": _text(split_row.get("role")),
            "retained_rank": _text(readiness_row.get("retained_rank")),
            "retained_score": _text(readiness_row.get("retained_score")),
            "score_source": "",
            "claim_promotion_allowed": False,
        }
        if ready:
            input_row = _build_input_row(
                readiness_row=readiness_row,
                label_row=label_row,
                split_row=split_row,
                trajectory_npz=trajectory_npz,
                native_pdb=native_pdb,
                labels_csv=labels_csv,
                split_csv=split_csv,
                readiness_csv=readiness_csv,
            )
            manifest_row["score_source"] = input_row["score_source"]
            input_rows.append(input_row)
        rows.append(manifest_row)

    ready_count = sum(1 for row in rows if row["feature_input_ready"])
    missing_counts = {
        "label_missing": sum(1 for row in rows if not row["label_ready"]),
        "split_missing": sum(1 for row in rows if not row["split_ready"]),
        "trajectory_missing": sum(1 for row in rows if not row["trajectory_ready"]),
        "native_missing": sum(1 for row in rows if not row["native_ready"]),
        "smiles_missing": sum(1 for row in rows if not row["smiles_ready"]),
    }
    status = (
        "gpcr_hard_decoy_feature_recovery_input_ready"
        if rows and ready_count == len(rows)
        else "blocked_gpcr_hard_decoy_feature_recovery_input_incomplete"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "readiness_csv": str(_resolve(readiness_csv)),
        "labels_csv": str(_resolve(labels_csv)),
        "split_csv": str(_resolve(split_csv)),
        "trajectory_roots": [str(_resolve(path)) for path in trajectory_roots],
        "native_source_csvs": [str(_resolve(path)) for path in native_source_csvs],
        "target_row_count": len(rows),
        "feature_input_ready_row_count": ready_count,
        "feature_input_blocked_row_count": len(rows) - ready_count,
        "input_csv_write_allowed": True,
        "feature_cache_execution_ready": bool(rows and ready_count == len(rows)),
        "missing_counts": missing_counts,
        **_READ_ONLY_FLAGS,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the existing GPCR cationic pose-distortion feature-cache builder on the generated input CSV, "
            "then rerun replay materialization readiness with the recovered feature cache included."
        ),
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "input_rows": input_rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Feature Recovery Input",
        "",
        f"- status: `{summary['status']}`",
        f"- target_row_count: `{summary['target_row_count']}`",
        f"- feature_input_ready_row_count: `{summary['feature_input_ready_row_count']}`",
        f"- feature_cache_execution_ready: `{str(summary['feature_cache_execution_ready']).lower()}`",
        "- claim_promotion_allowed: `false`",
        "- external_fetch_enabled: `false`",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        blocker_text = row["blockers"] or "none"
        lines.append(
            f"- `{row['target']}::{row['ligand_id']}` status=`{row['status']}` blockers=`{blocker_text}`"
        )
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a focused GPCR hard-decoy feature recovery input CSV.")
    parser.add_argument("--readiness-csv", default=DEFAULT_READINESS_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--split-csv", default=DEFAULT_SPLIT_CSV)
    parser.add_argument("--trajectory-root", action="append", default=[])
    parser.add_argument("--native-source-csv", action="append", default=[])
    parser.add_argument("--out-input-csv", default=DEFAULT_OUT_INPUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    trajectory_roots = args.trajectory_root or list(DEFAULT_TRAJECTORY_ROOTS)
    native_source_csvs = args.native_source_csv or [
        DEFAULT_NON_ADRB2_NATIVE_SOURCE_CSV,
        DEFAULT_ADRB2_NATIVE_SOURCE_CSV,
    ]
    payload = build_gpcr_hard_decoy_feature_recovery_input(
        readiness_csv=args.readiness_csv,
        labels_csv=args.labels_csv,
        split_csv=args.split_csv,
        trajectory_roots=trajectory_roots,
        native_source_csvs=native_source_csvs,
    )
    _write_csv(args.out_input_csv, payload["input_rows"], _INPUT_COLUMNS)
    payload["summary"]["out_input_csv"] = str(_resolve(args.out_input_csv))
    payload["summary"]["out_manifest_csv"] = str(_resolve(args.out_csv))
    _write_csv(args.out_csv, payload["rows"], _MANIFEST_COLUMNS)
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
