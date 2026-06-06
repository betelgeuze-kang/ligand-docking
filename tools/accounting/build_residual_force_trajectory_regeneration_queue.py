#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_RECOVERY_WORK_ORDER_JSON = "runs/residual_force_artifact_recovery_work_order_current.json"
DEFAULT_OUT_QUEUE_CSV = "runs/residual_force_trajectory_regeneration_queue_current.csv"
DEFAULT_OUT_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_OUT_MD = "runs/residual_force_trajectory_regeneration_queue_current.md"
DEFAULT_REGENERATION_OUT_ROOT = "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames"
DEFAULT_ENGINE_MANIFEST_CSV = "runs/residual_force_trajectory_regeneration_current_manifest.csv"
DEFAULT_ENGINE_SUMMARY_JSON = "runs/residual_force_trajectory_regeneration_current_summary.json"
DEFAULT_ENGINE_SUMMARY_MD = "runs/residual_force_trajectory_regeneration_current_summary.md"
DEFAULT_ENGINE_PROGRESS_JSON = "runs/residual_force_trajectory_regeneration_current_progress.json"

INVALID_PATH_TEXTS = {"", "nan", "none", "null", "na", "n/a"}

QUEUE_COLUMNS = [
    "queue_id",
    "original_queue_id",
    "target",
    "ligand_id",
    "ligand_smiles",
    "replica_idx",
    "simulation_seed",
    "native_pdb_path",
    "pocket_x",
    "pocket_y",
    "pocket_z",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "original_trajectory_npz",
    "expected_regenerated_trajectory_npz",
    "recovery_prefix",
    "source_stage3_csv",
    "regeneration_lane",
]

CLAIM_BOUNDARY = (
    "Residual force trajectory regeneration queue only; converts missing stage3 trajectory NPZ references into a "
    "durable local queue and engine command for later operator-approved regeneration. It does not run docking, "
    "regenerate trajectories, restore archives, derive force labels, train models, create checkpoints, promote "
    "production mode, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _valid_path_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in INVALID_PATH_TEXTS else text


def _stage3_path_from_stage5(source_csv: str) -> Path:
    source = _resolve(source_csv)
    name = source.name
    if name.endswith("_stage5_ranking_rows.csv"):
        return source.with_name(name.replace("_stage5_ranking_rows.csv", "_stage3_scores.csv"))
    return source


def _path_prefix(path_text: str, *, depth: int) -> str:
    path = Path(path_text)
    parts = path.parts
    if path.is_absolute():
        return str(Path(*parts[: min(len(parts) - 1, max(2, depth))]))
    if len(parts) <= 1:
        return "."
    return str(Path(*parts[: min(len(parts) - 1, max(1, depth))]))


def _slug(text: str) -> str:
    out = []
    for ch in str(text):
        if ch.isalnum():
            out.append(ch.lower())
        else:
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "item"


def _expected_npz_path(out_root: str, queue_id: str, *, row_index: int, shard_size: int) -> str:
    shard_index = max(0, int(row_index)) // max(1, int(shard_size))
    # Regeneration queue preserves engine flat_shard layout; rank-order drives shard placement.
    return str(Path(out_root) / f"shard_{shard_index:05d}" / f"{queue_id}.npz")


def _engine_command(
    *,
    queue_csv: str,
    out_root: str,
    manifest_csv: str,
    summary_json: str,
    summary_md: str,
    progress_json: str,
    frames: int,
    write_every: int,
    npz_shard_size: int,
) -> str:
    return (
        "python3 tools/generate_ligand_trajectory_engine.py "
        f"--queue-csv {queue_csv} "
        f"--out-root {out_root} "
        f"--frames {frames} "
        f"--write-every {write_every} "
        "--frame-output-format npz_bundle "
        "--npz-layout flat_shard "
        f"--npz-shard-size {npz_shard_size} "
        "--native-path-col native_pdb_path "
        f"--out-manifest-csv {manifest_csv} "
        f"--out-summary-json {summary_json} "
        f"--out-summary-md {summary_md} "
        f"--out-progress-json {progress_json} "
        "--prod-mode "
        "--prod-adaptive-frame-budget "
        "--prod-early-stop"
    )


def _source_stage3_paths(supervised_dataset_packet: dict[str, Any]) -> list[Path]:
    supervised_rows = [dict(row) for row in supervised_dataset_packet.get("rows", []) or [] if isinstance(row, dict)]
    paths: list[Path] = []
    seen: set[str] = set()
    for source in sorted({str(row.get("source_csv") or "").strip() for row in supervised_rows if row.get("source_csv")}):
        stage3 = _stage3_path_from_stage5(source)
        key = str(stage3)
        if key in seen:
            continue
        seen.add(key)
        paths.append(stage3)
    return paths


def build_residual_force_trajectory_regeneration_queue(
    *,
    supervised_dataset_packet: dict[str, Any],
    recovery_work_order_packet: dict[str, Any] | None = None,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    recovery_work_order_path: str = DEFAULT_RECOVERY_WORK_ORDER_JSON,
    regeneration_out_root: str = DEFAULT_REGENERATION_OUT_ROOT,
    queue_csv_path: str = DEFAULT_OUT_QUEUE_CSV,
    engine_manifest_csv: str = DEFAULT_ENGINE_MANIFEST_CSV,
    engine_summary_json: str = DEFAULT_ENGINE_SUMMARY_JSON,
    engine_summary_md: str = DEFAULT_ENGINE_SUMMARY_MD,
    engine_progress_json: str = DEFAULT_ENGINE_PROGRESS_JSON,
    max_sources: int = 24,
    max_rows_per_source: int = 20000,
    prefix_depth: int = 5,
    npz_shard_size: int = 512,
    frames: int = 120,
    write_every: int = 1,
) -> dict[str, Any]:
    recovery = _summary(recovery_work_order_packet or {})
    recovery_prefixes = {
        str(item.get("missing_prefix") or "").strip()
        for item in (recovery_work_order_packet or {}).get("missing_prefixes", []) or []
        if isinstance(item, dict) and str(item.get("missing_prefix") or "").strip()
    }
    stage3_paths = _source_stage3_paths(supervised_dataset_packet)
    supervised_rows = [dict(row) for row in supervised_dataset_packet.get("rows", []) or [] if isinstance(row, dict)]
    supervised_keys = {
        (str(row.get("target") or "").strip(), str(row.get("ligand_id") or "").strip())
        for row in supervised_rows
        if str(row.get("target") or "").strip() and str(row.get("ligand_id") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    raw_trajectory_path_rows = 0
    valid_trajectory_path_rows = 0
    existing_trajectory_npz_rows = 0
    missing_trajectory_npz_rows = 0
    missing_native_path_rows = 0
    missing_ligand_smiles_rows = 0
    stage3_missing_source_count = 0

    for stage3 in stage3_paths[: max(0, max_sources)]:
        if not stage3.exists():
            stage3_missing_source_count += 1
            continue
        with stage3.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for index, raw in enumerate(reader, start=1):
                if index > max_rows_per_source:
                    break
                key = (str(raw.get("target") or "").strip(), str(raw.get("ligand_id") or "").strip())
                if key not in supervised_keys:
                    continue
                raw_trajectory = str(raw.get("trajectory_npz") or "").strip()
                if raw_trajectory:
                    raw_trajectory_path_rows += 1
                trajectory = _valid_path_text(raw_trajectory)
                if not trajectory:
                    continue
                valid_trajectory_path_rows += 1
                if _resolve(trajectory).exists():
                    existing_trajectory_npz_rows += 1
                    continue
                missing_trajectory_npz_rows += 1
                prefix = _path_prefix(trajectory, depth=prefix_depth)
                if recovery_prefixes and prefix not in recovery_prefixes:
                    continue
                original_queue_id = str(raw.get("queue_id") or "").strip()
                if not original_queue_id:
                    original_queue_id = f"{str(raw.get('target') or 'target').strip()}__{str(raw.get('ligand_id') or 'ligand').strip()}__row{index:05d}"
                source_slug = _slug(stage3.name.replace("_stage3_scores.csv", ""))
                queue_id = f"{source_slug}__{_slug(original_queue_id)}"
                native_pdb_path = (
                    _valid_path_text(raw.get("native_pdb_path"))
                    or _valid_path_text(raw.get("protein_structure_source_explicit_native_path"))
                    or _valid_path_text(raw.get("protein_structure_source_path"))
                )
                ligand_smiles = str(raw.get("ligand_smiles") or "").strip()
                if not native_pdb_path:
                    missing_native_path_rows += 1
                if not ligand_smiles:
                    missing_ligand_smiles_rows += 1
                out_row = {column: "" for column in QUEUE_COLUMNS}
                for column in QUEUE_COLUMNS:
                    if column in raw:
                        out_row[column] = str(raw.get(column) or "").strip()
                out_row.update(
                    {
                        "queue_id": queue_id,
                        "original_queue_id": original_queue_id,
                        "target": str(raw.get("target") or "").strip(),
                        "ligand_id": str(raw.get("ligand_id") or "").strip(),
                        "ligand_smiles": ligand_smiles,
                        "native_pdb_path": native_pdb_path,
                        "original_trajectory_npz": trajectory,
                        "expected_regenerated_trajectory_npz": _expected_npz_path(
                            regeneration_out_root,
                            queue_id,
                            row_index=len(rows),
                            shard_size=npz_shard_size,
                        ),
                        "recovery_prefix": prefix,
                        "source_stage3_csv": _rel(stage3),
                        "regeneration_lane": "residual_delta_force_npz_regeneration",
                    }
                )
                rows.append(out_row)

    command = _engine_command(
        queue_csv=queue_csv_path,
        out_root=regeneration_out_root,
        manifest_csv=engine_manifest_csv,
        summary_json=engine_summary_json,
        summary_md=engine_summary_md,
        progress_json=engine_progress_json,
        frames=frames,
        write_every=write_every,
        npz_shard_size=npz_shard_size,
    )
    queue_ready = bool(rows)
    queue_execution_ready = queue_ready and missing_native_path_rows == 0
    blockers: list[str] = []
    if not queue_ready:
        blockers.append("regeneration_queue_rows")
    if missing_native_path_rows:
        blockers.append("native_pdb_path")
    status = (
        "residual_force_trajectory_regeneration_queue_ready"
        if queue_execution_ready
        else "blocked_residual_force_trajectory_regeneration_queue"
    )
    summary = {
        "packet_type": "residual_force_trajectory_regeneration_queue",
        "status": status,
        "regeneration_queue_ready": queue_ready,
        "regeneration_queue_execution_ready": queue_execution_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "supervised_dataset_artifact": supervised_dataset_path,
        "recovery_work_order_artifact": recovery_work_order_path,
        "recovery_work_order_status": recovery.get("status", ""),
        "source_stage3_count": len(stage3_paths),
        "scanned_stage3_count": min(len(stage3_paths), max_sources),
        "stage3_missing_source_count": stage3_missing_source_count,
        "raw_trajectory_path_rows": raw_trajectory_path_rows,
        "valid_trajectory_path_rows": valid_trajectory_path_rows,
        "existing_trajectory_npz_rows": existing_trajectory_npz_rows,
        "missing_trajectory_npz_rows": missing_trajectory_npz_rows,
        "queue_rows": len(rows),
        "native_pdb_path_present_rows": len(rows) - missing_native_path_rows,
        "missing_native_pdb_path_rows": missing_native_path_rows,
        "ligand_smiles_present_rows": len(rows) - missing_ligand_smiles_rows,
        "missing_ligand_smiles_rows": missing_ligand_smiles_rows,
        "regeneration_queue_csv": queue_csv_path,
        "regeneration_out_root": regeneration_out_root,
        "engine_manifest_csv": engine_manifest_csv,
        "engine_summary_json": engine_summary_json,
        "engine_summary_md": engine_summary_md,
        "engine_progress_json": engine_progress_json,
        "engine_command": command,
        "execution_enabled": False,
        "trajectory_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the residual force trajectory regeneration engine command, then rerun residual_force_derivation_validation."
            if queue_execution_ready
            else "Fill native_pdb_path for every regeneration row before running the trajectory engine."
            if missing_native_path_rows
            else "Rebuild recovery work order and stage3 trajectory references before queue generation."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"summary": payload["summary"], "rows": payload["rows"][:48]}
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force Trajectory Regeneration Queue",
        "",
        f"- status: `{s['status']}`",
        f"- regeneration_queue_execution_ready: `{s['regeneration_queue_execution_ready']}`",
        f"- queue_rows: `{s['queue_rows']}`",
        f"- missing_trajectory_npz_rows: `{s['missing_trajectory_npz_rows']}`",
        f"- native_pdb_path_present_rows: `{s['native_pdb_path_present_rows']}`",
        f"- missing_native_pdb_path_rows: `{s['missing_native_pdb_path_rows']}`",
        f"- regeneration_queue_csv: `{s['regeneration_queue_csv']}`",
        f"- regeneration_out_root: `{s['regeneration_out_root']}`",
        "",
        "## Engine Command",
        "",
        "```bash",
        s["engine_command"],
        "```",
        "",
        "## Queue Preview",
        "",
        "| queue_id | target | ligand_id | native_pdb_path | expected NPZ | source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:24]:
        lines.append(
            f"| `{row['queue_id']}` | `{row['target']}` | `{row['ligand_id']}` | `{row['native_pdb_path']}` | `{row['expected_regenerated_trajectory_npz']}` | `{row['source_stage3_csv']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual force trajectory regeneration queue.")
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--recovery-work-order-json", default=DEFAULT_RECOVERY_WORK_ORDER_JSON)
    parser.add_argument("--regeneration-out-root", default=DEFAULT_REGENERATION_OUT_ROOT)
    parser.add_argument("--engine-manifest-csv", default=DEFAULT_ENGINE_MANIFEST_CSV)
    parser.add_argument("--engine-summary-json", default=DEFAULT_ENGINE_SUMMARY_JSON)
    parser.add_argument("--engine-summary-md", default=DEFAULT_ENGINE_SUMMARY_MD)
    parser.add_argument("--engine-progress-json", default=DEFAULT_ENGINE_PROGRESS_JSON)
    parser.add_argument("--max-sources", type=int, default=24)
    parser.add_argument("--max-rows-per-source", type=int, default=20000)
    parser.add_argument("--prefix-depth", type=int, default=5)
    parser.add_argument("--npz-shard-size", type=int, default=512)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--write-every", type=int, default=1)
    parser.add_argument("--out-queue-csv", default=DEFAULT_OUT_QUEUE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_trajectory_regeneration_queue(
        supervised_dataset_packet=_read_json_if_present(args.supervised_dataset_json),
        recovery_work_order_packet=_read_json_if_present(args.recovery_work_order_json),
        supervised_dataset_path=args.supervised_dataset_json,
        recovery_work_order_path=args.recovery_work_order_json,
        regeneration_out_root=args.regeneration_out_root,
        queue_csv_path=args.out_queue_csv,
        engine_manifest_csv=args.engine_manifest_csv,
        engine_summary_json=args.engine_summary_json,
        engine_summary_md=args.engine_summary_md,
        engine_progress_json=args.engine_progress_json,
        max_sources=args.max_sources,
        max_rows_per_source=args.max_rows_per_source,
        prefix_depth=args.prefix_depth,
        npz_shard_size=args.npz_shard_size,
        frames=args.frames,
        write_every=args.write_every,
    )
    write_csv_rows(_resolve(args.out_queue_csv), payload["rows"])
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
