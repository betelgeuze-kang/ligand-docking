#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_TRAJECTORY_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_derivation_validation_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_derivation_validation_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_derivation_validation_current.md"

FORCE_LABEL_COLUMN_TOKENS = ("force", "gradient")
COORDINATE_KEY_TOKENS = ("coord", "xyz", "position", "pos")
ENERGY_KEY_TOKENS = ("energy", "score", "potential")

CLAIM_BOUNDARY = (
    "Residual force-derivation validation only; inspects existing local stage3 score rows and referenced trajectory "
    "NPZ/PDB artifacts for delta_force label or -grad(delta_energy) derivation readiness. It does not run docking, "
    "compute force labels, derive gradients, train models, create checkpoints, promote production mode, upload, submit, "
    "email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
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
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _valid_path_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    return text


def _float_present(value: Any) -> bool:
    try:
        if value is None or str(value).strip() == "":
            return False
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _stage3_path_from_stage5(source_csv: str) -> Path:
    source = _resolve(source_csv)
    name = source.name
    if name.endswith("_stage5_ranking_rows.csv"):
        return source.with_name(name.replace("_stage5_ranking_rows.csv", "_stage3_scores.csv"))
    return source


def _trajectory_remap_from_regeneration_queue(
    packet: dict[str, Any] | None,
    *,
    queue_packet_path: str,
) -> dict[str, str]:
    payload = packet or {}
    summary = _summary(payload)
    rows = [dict(row) for row in payload.get("rows", []) or [] if isinstance(row, dict)]
    queue_csv = str(summary.get("regeneration_queue_csv") or "").strip()
    if queue_csv:
        csv_path = _resolve(queue_csv)
    else:
        csv_path = _resolve(str(queue_packet_path).replace(".json", ".csv"))
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as fh:
                rows.extend(dict(row) for row in csv.DictReader(fh))
        except OSError:
            pass
    remap: dict[str, str] = {}
    for row in rows:
        original = _valid_path_text(row.get("original_trajectory_npz"))
        expected = _valid_path_text(row.get("expected_regenerated_trajectory_npz"))
        if original and expected:
            remap.setdefault(original, expected)
    return remap


def _npz_probe(path_text: str) -> dict[str, Any]:
    path = _resolve(path_text)
    if not path.exists():
        return {
            "trajectory_npz": path_text,
            "trajectory_npz_exists": False,
            "npz_readable": False,
            "coordinate_array_present": False,
            "energy_array_present": False,
            "array_keys": "",
            "probe_status": "missing_npz",
        }
    try:
        with np.load(path, allow_pickle=False) as data:
            keys = list(data.files)
            coordinate_keys = [
                key
                for key in keys
                if any(token in key.lower() for token in COORDINATE_KEY_TOKENS)
                and getattr(data[key], "ndim", 0) >= 2
            ]
            energy_keys = [
                key
                for key in keys
                if any(token in key.lower() for token in ENERGY_KEY_TOKENS)
                and getattr(data[key], "size", 0) > 0
            ]
            return {
                "trajectory_npz": path_text,
                "trajectory_npz_exists": True,
                "npz_readable": True,
                "coordinate_array_present": bool(coordinate_keys),
                "energy_array_present": bool(energy_keys),
                "array_keys": ",".join(keys[:24]),
                "coordinate_keys": ",".join(coordinate_keys[:8]),
                "energy_keys": ",".join(energy_keys[:8]),
                "probe_status": "npz_derivation_inputs_present" if coordinate_keys and energy_keys else "npz_missing_coordinate_or_energy_arrays",
            }
    except Exception as exc:  # noqa: BLE001 - probe must report row-level parser failures.
        return {
            "trajectory_npz": path_text,
            "trajectory_npz_exists": True,
            "npz_readable": False,
            "coordinate_array_present": False,
            "energy_array_present": False,
            "array_keys": "",
            "probe_status": f"npz_read_error:{type(exc).__name__}",
        }


def _scan_stage3_sources(
    supervised_rows: list[dict[str, Any]],
    *,
    trajectory_remap: dict[str, str],
    max_sources: int,
    max_rows_per_source: int,
    max_npz_samples: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    supervised_keys = {
        (str(row.get("target") or "").strip(), str(row.get("ligand_id") or "").strip())
        for row in supervised_rows
        if str(row.get("target") or "").strip() and str(row.get("ligand_id") or "").strip()
    }
    stage5_sources = sorted({str(row.get("source_csv") or "").strip() for row in supervised_rows if row.get("source_csv")})
    source_rows: list[dict[str, Any]] = []
    npz_rows: list[dict[str, Any]] = []
    raw_trajectory_path_rows = 0
    valid_trajectory_path_rows = 0
    existing_trajectory_npz_rows = 0
    trajectory_remap_candidate_rows = 0
    existing_remapped_trajectory_npz_rows = 0
    force_label_rows = 0
    force_label_keys: set[str] = set()
    backmapped_pdb_path_rows = 0
    existing_backmapped_pdb_rows = 0
    sampled_paths: set[str] = set()

    for source in stage5_sources[: max(0, max_sources)]:
        stage3 = _stage3_path_from_stage5(source)
        scanned = 0
        joined = 0
        source_valid_trajectory_rows = 0
        source_existing_npz_rows = 0
        source_remap_candidate_rows = 0
        source_existing_remapped_npz_rows = 0
        source_force_label_rows = 0
        source_existing_pdb_rows = 0
        if not stage3.exists():
            source_rows.append(
                {
                    "source_csv": _rel(stage3),
                    "status": "missing_stage3_source",
                    "scanned_rows": 0,
                    "joined_rows": 0,
                    "valid_trajectory_path_rows": 0,
                    "existing_trajectory_npz_rows": 0,
                    "trajectory_remap_candidate_rows": 0,
                    "existing_remapped_trajectory_npz_rows": 0,
                    "force_label_rows": 0,
                    "existing_backmapped_pdb_rows": 0,
                }
            )
            continue
        with stage3.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            force_cols = [
                col
                for col in fieldnames
                if any(token in col.lower() for token in FORCE_LABEL_COLUMN_TOKENS)
                and not col.lower().startswith(("force_backend",))
            ]
            for raw in reader:
                scanned += 1
                if scanned > max_rows_per_source:
                    break
                key = (str(raw.get("target") or "").strip(), str(raw.get("ligand_id") or "").strip())
                if key not in supervised_keys:
                    continue
                joined += 1
                if any(_float_present(raw.get(col)) for col in force_cols):
                    force_label_rows += 1
                    source_force_label_rows += 1
                    force_label_keys.add(f"{key[0]}::{key[1]}")
                raw_trajectory = str(raw.get("trajectory_npz") or "").strip()
                if raw_trajectory:
                    raw_trajectory_path_rows += 1
                trajectory = _valid_path_text(raw.get("trajectory_npz"))
                if trajectory:
                    valid_trajectory_path_rows += 1
                    source_valid_trajectory_rows += 1
                    trajectory_path = _resolve(trajectory)
                    probe_trajectory = trajectory
                    remapped_trajectory = ""
                    if not trajectory_path.exists():
                        remapped_trajectory = _valid_path_text(trajectory_remap.get(trajectory))
                        if remapped_trajectory:
                            trajectory_remap_candidate_rows += 1
                            source_remap_candidate_rows += 1
                            trajectory_path = _resolve(remapped_trajectory)
                            probe_trajectory = remapped_trajectory
                    if trajectory_path.exists():
                        existing_trajectory_npz_rows += 1
                        source_existing_npz_rows += 1
                        if remapped_trajectory:
                            existing_remapped_trajectory_npz_rows += 1
                            source_existing_remapped_npz_rows += 1
                        if len(sampled_paths) < max_npz_samples and probe_trajectory not in sampled_paths:
                            sampled_paths.add(probe_trajectory)
                            probe = _npz_probe(probe_trajectory)
                            probe.update(
                                {
                                    "target": key[0],
                                    "ligand_id": key[1],
                                    "source_csv": _rel(stage3),
                                    "original_trajectory_npz": trajectory,
                                    "remapped_trajectory_npz": remapped_trajectory,
                                }
                            )
                            npz_rows.append(probe)
                backmapped_pdb = _valid_path_text(raw.get("backmapped_pdb"))
                if backmapped_pdb:
                    backmapped_pdb_path_rows += 1
                    if _resolve(backmapped_pdb).exists():
                        existing_backmapped_pdb_rows += 1
                        source_existing_pdb_rows += 1
        source_rows.append(
            {
                "source_csv": _rel(stage3),
                "status": "used" if joined else "no_joined_rows",
                "scanned_rows": min(scanned, max_rows_per_source),
                "joined_rows": joined,
                "valid_trajectory_path_rows": source_valid_trajectory_rows,
                "existing_trajectory_npz_rows": source_existing_npz_rows,
                "trajectory_remap_candidate_rows": source_remap_candidate_rows,
                "existing_remapped_trajectory_npz_rows": source_existing_remapped_npz_rows,
                "force_label_rows": source_force_label_rows,
                "existing_backmapped_pdb_rows": source_existing_pdb_rows,
            }
        )

    counts = {
        "stage3_source_count": len(stage5_sources),
        "scanned_stage3_source_count": len(source_rows),
        "joined_rows": sum(int(row.get("joined_rows") or 0) for row in source_rows),
        "raw_trajectory_path_rows": raw_trajectory_path_rows,
        "valid_trajectory_path_rows": valid_trajectory_path_rows,
        "existing_trajectory_npz_rows": existing_trajectory_npz_rows,
        "trajectory_remap_candidate_rows": trajectory_remap_candidate_rows,
        "existing_remapped_trajectory_npz_rows": existing_remapped_trajectory_npz_rows,
        "force_label_rows": force_label_rows,
        "unique_force_label_keys": len(force_label_keys),
        "backmapped_pdb_path_rows": backmapped_pdb_path_rows,
        "existing_backmapped_pdb_rows": existing_backmapped_pdb_rows,
    }
    return source_rows, npz_rows, counts


def build_residual_force_derivation_validation(
    *,
    supervised_dataset_packet: dict[str, Any],
    trajectory_regeneration_queue_packet: dict[str, Any] | None = None,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    trajectory_regeneration_queue_path: str = DEFAULT_TRAJECTORY_REGENERATION_QUEUE_JSON,
    max_sources: int = 24,
    max_rows_per_source: int = 20000,
    max_npz_samples: int = 16,
    min_existing_npz_rows: int = 1000,
    min_npz_probe_successes: int = 8,
) -> dict[str, Any]:
    supervised = _summary(supervised_dataset_packet)
    supervised_rows = [dict(row) for row in supervised_dataset_packet.get("rows", []) or [] if isinstance(row, dict)]
    trajectory_remap = _trajectory_remap_from_regeneration_queue(
        trajectory_regeneration_queue_packet,
        queue_packet_path=trajectory_regeneration_queue_path,
    )
    source_rows, npz_rows, counts = _scan_stage3_sources(
        supervised_rows,
        trajectory_remap=trajectory_remap,
        max_sources=max_sources,
        max_rows_per_source=max_rows_per_source,
        max_npz_samples=max_npz_samples,
    )
    npz_readable_count = sum(1 for row in npz_rows if row.get("npz_readable") is True)
    coordinate_array_sample_count = sum(1 for row in npz_rows if row.get("coordinate_array_present") is True)
    energy_array_sample_count = sum(1 for row in npz_rows if row.get("energy_array_present") is True)
    derivation_input_sample_count = sum(
        1
        for row in npz_rows
        if row.get("npz_readable") is True
        and row.get("coordinate_array_present") is True
        and row.get("energy_array_present") is True
    )
    effective_min_existing_npz_rows = (
        min(int(min_existing_npz_rows), int(counts["valid_trajectory_path_rows"]))
        if int(counts["valid_trajectory_path_rows"]) > 0
        else int(min_existing_npz_rows)
    )
    existing_npz_rows_ready = counts["existing_trajectory_npz_rows"] >= effective_min_existing_npz_rows
    existing_npz_floor_capped_by_available_paths = (
        int(counts["valid_trajectory_path_rows"]) > 0 and effective_min_existing_npz_rows < int(min_existing_npz_rows)
    )
    rows = [
        {
            "check_id": "force_label_columns",
            "status": "pass" if counts["force_label_rows"] > 0 else "fail",
            "observed": f"force_label_rows={counts['force_label_rows']};unique_force_label_keys={counts['unique_force_label_keys']}",
            "required": "direct force or gradient label columns exist for supervised target+ligand rows",
            "next_action": "Use direct force labels if available; otherwise validate an energy-gradient derivation path.",
            "release_blocker": counts["force_label_rows"] <= 0,
        },
        {
            "check_id": "trajectory_npz_artifacts",
            "status": "pass" if existing_npz_rows_ready else "fail",
            "observed": (
                f"raw_trajectory_path_rows={counts['raw_trajectory_path_rows']};"
                f"valid_trajectory_path_rows={counts['valid_trajectory_path_rows']};"
                f"existing_trajectory_npz_rows={counts['existing_trajectory_npz_rows']};"
                f"trajectory_remap_candidate_rows={counts['trajectory_remap_candidate_rows']};"
                f"existing_remapped_trajectory_npz_rows={counts['existing_remapped_trajectory_npz_rows']};"
                f"min_existing_npz_rows={min_existing_npz_rows};"
                f"effective_min_existing_npz_rows={effective_min_existing_npz_rows};"
                f"existing_npz_floor_capped_by_available_paths={existing_npz_floor_capped_by_available_paths}"
            ),
            "required": "existing trajectory NPZ artifacts cover all currently valid trajectory references, capped by the configured production floor",
            "next_action": "Regenerate or restore trajectory NPZ artifacts with durable paths before force derivation validation.",
            "release_blocker": not existing_npz_rows_ready,
        },
        {
            "check_id": "npz_coordinate_energy_arrays",
            "status": "pass" if derivation_input_sample_count >= min_npz_probe_successes else "fail",
            "observed": (
                f"npz_sample_count={len(npz_rows)};npz_readable_count={npz_readable_count};"
                f"coordinate_array_sample_count={coordinate_array_sample_count};"
                f"energy_array_sample_count={energy_array_sample_count};"
                f"derivation_input_sample_count={derivation_input_sample_count};"
                f"min_npz_probe_successes={min_npz_probe_successes}"
            ),
            "required": "sampled NPZ artifacts expose coordinate and energy arrays suitable for -grad(delta_energy) derivation validation",
            "next_action": "Store coordinate and energy arrays in trajectory NPZ artifacts, then validate force shape/unit/physics guards.",
            "release_blocker": derivation_input_sample_count < min_npz_probe_successes,
        },
    ]
    blockers = [row["check_id"] for row in rows if row["status"] != "pass"]
    ready = not blockers
    summary = {
        "packet_type": "residual_force_derivation_validation",
        "status": "residual_force_derivation_validation_ready" if ready else "blocked_residual_force_derivation_validation",
        "delta_force_derivation_validation_ready": ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "supervised_dataset_artifact": supervised_dataset_path,
        "trajectory_regeneration_queue_artifact": trajectory_regeneration_queue_path,
        "supervised_rows": int(supervised.get("rows_emitted") or len(supervised_rows)),
        "trajectory_remap_rows": len(trajectory_remap),
        **counts,
        "npz_sample_count": len(npz_rows),
        "npz_readable_count": npz_readable_count,
        "coordinate_array_sample_count": coordinate_array_sample_count,
        "energy_array_sample_count": energy_array_sample_count,
        "derivation_input_sample_count": derivation_input_sample_count,
        "min_existing_npz_rows": min_existing_npz_rows,
        "effective_min_existing_npz_rows": effective_min_existing_npz_rows,
        "existing_npz_floor_capped_by_available_paths": existing_npz_floor_capped_by_available_paths,
        "min_npz_probe_successes": min_npz_probe_successes,
        "execution_enabled": False,
        "validation_executed": True,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Force derivation inputs are ready; attach force label evidence to residual energy/force validation."
            if ready
            else rows[0]["next_action"]
            if rows[0]["status"] != "pass" and counts["existing_trajectory_npz_rows"] > 0
            else "Run the residual force trajectory regeneration queue command, then rerun this validation."
            if rows[1]["status"] != "pass" and counts["trajectory_remap_candidate_rows"] > 0
            else rows[1]["next_action"]
            if rows[1]["status"] != "pass"
            else rows[2]["next_action"]
        ),
    }
    return {"summary": summary, "rows": rows, "sources": source_rows, "npz_probes": npz_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "summary": payload["summary"],
        "rows": payload["rows"],
        "sources": payload["sources"][:24],
        "npz_probes": payload["npz_probes"][:24],
    }
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force Derivation Validation",
        "",
        f"- status: `{s['status']}`",
        f"- delta_force_derivation_validation_ready: `{s['delta_force_derivation_validation_ready']}`",
        f"- joined_rows: `{s['joined_rows']}`",
        f"- raw_trajectory_path_rows: `{s['raw_trajectory_path_rows']}`",
        f"- valid_trajectory_path_rows: `{s['valid_trajectory_path_rows']}`",
        f"- existing_trajectory_npz_rows: `{s['existing_trajectory_npz_rows']}`",
        f"- trajectory_remap_candidate_rows: `{s['trajectory_remap_candidate_rows']}`",
        f"- existing_remapped_trajectory_npz_rows: `{s['existing_remapped_trajectory_npz_rows']}`",
        f"- effective_min_existing_npz_rows: `{s['effective_min_existing_npz_rows']}`",
        f"- existing_npz_floor_capped_by_available_paths: `{s['existing_npz_floor_capped_by_available_paths']}`",
        f"- force_label_rows: `{s['force_label_rows']}`",
        f"- unique_force_label_keys: `{s['unique_force_label_keys']}`",
        f"- derivation_input_sample_count: `{s['derivation_input_sample_count']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['next_action']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate residual delta_force derivation readiness.")
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--trajectory-regeneration-queue-json", default=DEFAULT_TRAJECTORY_REGENERATION_QUEUE_JSON)
    parser.add_argument("--max-sources", type=int, default=24)
    parser.add_argument("--max-rows-per-source", type=int, default=20000)
    parser.add_argument("--max-npz-samples", type=int, default=16)
    parser.add_argument("--min-existing-npz-rows", type=int, default=1000)
    parser.add_argument("--min-npz-probe-successes", type=int, default=8)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_derivation_validation(
        supervised_dataset_packet=_read_json(args.supervised_dataset_json),
        trajectory_regeneration_queue_packet=_read_json(args.trajectory_regeneration_queue_json),
        supervised_dataset_path=args.supervised_dataset_json,
        trajectory_regeneration_queue_path=args.trajectory_regeneration_queue_json,
        max_sources=args.max_sources,
        max_rows_per_source=args.max_rows_per_source,
        max_npz_samples=args.max_npz_samples,
        min_existing_npz_rows=args.min_existing_npz_rows,
        min_npz_probe_successes=args.min_npz_probe_successes,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
