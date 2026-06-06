#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_FORCE_VALIDATION_JSON = "runs/residual_force_derivation_validation_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_artifact_recovery_work_order_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_artifact_recovery_work_order_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_artifact_recovery_work_order_current.md"

INVALID_PATH_TEXTS = {"", "nan", "none", "null", "na", "n/a"}

CLAIM_BOUNDARY = (
    "Residual force artifact recovery work order only; inspects existing supervised rows and matching stage3 score "
    "artifacts to locate missing trajectory NPZ paths needed for delta_force derivation validation. It does not restore "
    "archives, run docking, regenerate trajectories, derive force labels, train models, create checkpoints, promote "
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
        kept = parts[: max(2, depth)]
        return str(Path(*kept))
    if len(parts) <= 1:
        return "."
    return str(Path(*parts[: min(len(parts) - 1, max(1, depth))]))


def _work_row(
    check_id: str,
    status: str,
    observed: str,
    required: str,
    source_artifact: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "source_artifact": source_artifact,
        "next_action": next_action,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "restore_executed": False,
        "trajectory_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _scan_recovery_rows(
    supervised_rows: list[dict[str, Any]],
    *,
    max_sources: int,
    max_rows_per_source: int,
    prefix_depth: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    supervised_keys = {
        (str(row.get("target") or "").strip(), str(row.get("ligand_id") or "").strip())
        for row in supervised_rows
        if str(row.get("target") or "").strip() and str(row.get("ligand_id") or "").strip()
    }
    stage5_sources = sorted({str(row.get("source_csv") or "").strip() for row in supervised_rows if row.get("source_csv")})
    stage3_paths: list[Path] = []
    seen: set[str] = set()
    for source in stage5_sources:
        stage3 = _stage3_path_from_stage5(source)
        key = str(stage3)
        if key in seen:
            continue
        seen.add(key)
        stage3_paths.append(stage3)

    source_rows: list[dict[str, Any]] = []
    prefix_counts: Counter[str] = Counter()
    prefix_parent_exists: Counter[str] = Counter()
    prefix_source_counts: Counter[tuple[str, str]] = Counter()
    prefix_examples: dict[str, str] = {}
    source_missing_counts: Counter[str] = Counter()
    source_examples: dict[str, str] = {}
    raw_trajectory_path_rows = 0
    valid_trajectory_path_rows = 0
    existing_trajectory_npz_rows = 0
    missing_trajectory_npz_rows = 0

    for stage3 in stage3_paths[: max(0, max_sources)]:
        scanned_rows = 0
        joined_rows = 0
        source_valid_rows = 0
        source_existing_rows = 0
        source_missing_rows = 0
        if not stage3.exists():
            source_rows.append(
                {
                    "source_csv": _rel(stage3),
                    "status": "missing_stage3_source",
                    "scanned_rows": 0,
                    "joined_rows": 0,
                    "valid_trajectory_path_rows": 0,
                    "existing_trajectory_npz_rows": 0,
                    "missing_trajectory_npz_rows": 0,
                    "top_missing_prefix": "",
                    "example_missing_trajectory_npz": "",
                }
            )
            continue
        with stage3.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = set(reader.fieldnames or [])
            if "target" not in fields or "ligand_id" not in fields:
                source_rows.append(
                    {
                        "source_csv": _rel(stage3),
                        "status": "skipped_missing_join_columns",
                        "scanned_rows": 0,
                        "joined_rows": 0,
                        "valid_trajectory_path_rows": 0,
                        "existing_trajectory_npz_rows": 0,
                        "missing_trajectory_npz_rows": 0,
                        "top_missing_prefix": "",
                        "example_missing_trajectory_npz": "",
                    }
                )
                continue
            local_prefix_counts: Counter[str] = Counter()
            for raw in reader:
                scanned_rows += 1
                if scanned_rows > max_rows_per_source:
                    break
                key = (str(raw.get("target") or "").strip(), str(raw.get("ligand_id") or "").strip())
                if key not in supervised_keys:
                    continue
                joined_rows += 1
                raw_trajectory = str(raw.get("trajectory_npz") or "").strip()
                if raw_trajectory:
                    raw_trajectory_path_rows += 1
                trajectory = _valid_path_text(raw_trajectory)
                if not trajectory:
                    continue
                valid_trajectory_path_rows += 1
                source_valid_rows += 1
                path = _resolve(trajectory)
                if path.exists():
                    existing_trajectory_npz_rows += 1
                    source_existing_rows += 1
                    continue
                missing_trajectory_npz_rows += 1
                source_missing_rows += 1
                prefix = _path_prefix(trajectory, depth=prefix_depth)
                prefix_counts[prefix] += 1
                local_prefix_counts[prefix] += 1
                prefix_source_counts[(prefix, _rel(stage3))] += 1
                prefix_examples.setdefault(prefix, trajectory)
                source_missing_counts[_rel(stage3)] += 1
                source_examples.setdefault(_rel(stage3), trajectory)
                if Path(trajectory).parent.exists():
                    prefix_parent_exists[prefix] += 1
        top_prefix = local_prefix_counts.most_common(1)[0][0] if local_prefix_counts else ""
        source_rows.append(
            {
                "source_csv": _rel(stage3),
                "status": "used" if joined_rows else "no_joined_rows",
                "scanned_rows": min(scanned_rows, max_rows_per_source),
                "joined_rows": joined_rows,
                "valid_trajectory_path_rows": source_valid_rows,
                "existing_trajectory_npz_rows": source_existing_rows,
                "missing_trajectory_npz_rows": source_missing_rows,
                "top_missing_prefix": top_prefix,
                "example_missing_trajectory_npz": source_examples.get(_rel(stage3), ""),
            }
        )

    missing_prefix_rows: list[dict[str, Any]] = []
    for rank, (prefix, count) in enumerate(prefix_counts.most_common(), start=1):
        top_source, top_source_count = "", 0
        for (candidate_prefix, source), source_count in prefix_source_counts.items():
            if candidate_prefix == prefix and source_count > top_source_count:
                top_source, top_source_count = source, source_count
        missing_prefix_rows.append(
            {
                "rank": rank,
                "missing_prefix": prefix,
                "missing_trajectory_npz_rows": count,
                "parent_exists_rows": prefix_parent_exists.get(prefix, 0),
                "top_source_csv": top_source,
                "top_source_missing_rows": top_source_count,
                "example_missing_trajectory_npz": prefix_examples.get(prefix, ""),
            }
        )

    counts = {
        "stage3_source_count": len(stage3_paths),
        "scanned_stage3_source_count": len(source_rows),
        "joined_rows": sum(int(row.get("joined_rows") or 0) for row in source_rows),
        "raw_trajectory_path_rows": raw_trajectory_path_rows,
        "valid_trajectory_path_rows": valid_trajectory_path_rows,
        "existing_trajectory_npz_rows": existing_trajectory_npz_rows,
        "missing_trajectory_npz_rows": missing_trajectory_npz_rows,
        "missing_path_prefix_count": len(missing_prefix_rows),
        "top_missing_prefix": missing_prefix_rows[0]["missing_prefix"] if missing_prefix_rows else "",
        "top_missing_prefix_rows": int(missing_prefix_rows[0]["missing_trajectory_npz_rows"]) if missing_prefix_rows else 0,
        "top_missing_source": source_missing_counts.most_common(1)[0][0] if source_missing_counts else "",
        "top_missing_source_rows": source_missing_counts.most_common(1)[0][1] if source_missing_counts else 0,
        "top_missing_source_example": source_examples.get(source_missing_counts.most_common(1)[0][0], "")
        if source_missing_counts
        else "",
    }
    return source_rows, missing_prefix_rows, counts


def build_residual_force_artifact_recovery_work_order(
    *,
    supervised_dataset_packet: dict[str, Any],
    force_validation_packet: dict[str, Any] | None = None,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    force_validation_path: str = DEFAULT_FORCE_VALIDATION_JSON,
    max_sources: int = 24,
    max_rows_per_source: int = 20000,
    prefix_depth: int = 5,
    max_prefix_work_items: int = 24,
) -> dict[str, Any]:
    supervised = _summary(supervised_dataset_packet)
    force_validation = _summary(force_validation_packet or {})
    supervised_rows = [dict(row) for row in supervised_dataset_packet.get("rows", []) or [] if isinstance(row, dict)]
    source_rows, missing_prefix_rows, counts = _scan_recovery_rows(
        supervised_rows,
        max_sources=max_sources,
        max_rows_per_source=max_rows_per_source,
        prefix_depth=prefix_depth,
    )
    force_validation_ready = force_validation.get("delta_force_derivation_validation_ready") is True
    recovery_required = counts["missing_trajectory_npz_rows"] > 0 and not force_validation_ready
    has_actionable_sources = counts["valid_trajectory_path_rows"] > 0 or counts["missing_path_prefix_count"] > 0

    rows: list[dict[str, Any]] = []
    if recovery_required:
        for item in missing_prefix_rows[: max(0, max_prefix_work_items)]:
            rows.append(
                _work_row(
                    f"restore_or_regenerate_missing_trajectory_npz_prefix.{item['rank']:02d}",
                    "fail",
                    (
                        f"missing_trajectory_npz_rows={item['missing_trajectory_npz_rows']};"
                        f"parent_exists_rows={item['parent_exists_rows']};"
                        f"prefix={item['missing_prefix']};"
                        f"top_source_missing_rows={item['top_source_missing_rows']};"
                        f"example={item['example_missing_trajectory_npz']}"
                    ),
                    "trajectory NPZ artifacts exist at durable paths and contain coordinate and energy arrays for force derivation validation",
                    str(item["top_source_csv"]) or supervised_dataset_path,
                    "Restore the archived trajectory shard or rerun the source pipeline with durable trajectory_npz output under runs/ or approved external storage, then rerun residual_force_derivation_validation.",
                )
            )
    rows.append(
        _work_row(
            "force_derivation_validation_rerun",
            "pass" if not recovery_required and force_validation_ready else "fail",
            (
                f"force_validation_ready={force_validation_ready};"
                f"existing_trajectory_npz_rows={counts['existing_trajectory_npz_rows']};"
                f"missing_trajectory_npz_rows={counts['missing_trajectory_npz_rows']};"
                f"validation_status={force_validation.get('status', '')}"
            ),
            "residual_force_derivation_validation_current.json is rebuilt after trajectory NPZ restoration/regeneration",
            force_validation_path,
            "Rerun tools/build_residual_force_derivation_validation.py after recovery artifacts are present.",
        )
    )

    blocker_rows = [row for row in rows if row["status"] != "pass"]
    status = (
        "residual_force_artifact_recovery_not_required"
        if not recovery_required and force_validation_ready
        else "residual_force_artifact_recovery_work_order_ready"
        if has_actionable_sources
        else "blocked_residual_force_artifact_recovery_work_order"
    )
    next_required_step = (
        "Force derivation validation is already ready; no trajectory artifact recovery is required."
        if status == "residual_force_artifact_recovery_not_required"
        else "Restore or regenerate the top missing trajectory NPZ prefix, then rerun residual_force_derivation_validation."
        if recovery_required
        else "Regenerate stage3 trajectory_npz references before artifact recovery can be scoped."
    )
    summary = {
        "packet_type": "residual_force_artifact_recovery_work_order",
        "status": status,
        "force_artifact_recovery_work_order_ready": status != "blocked_residual_force_artifact_recovery_work_order",
        "force_artifact_recovery_required": recovery_required,
        "force_derivation_validation_ready": force_validation_ready,
        "blocker_count": len(blocker_rows),
        "blockers": [row["check_id"] for row in blocker_rows],
        "supervised_dataset_artifact": supervised_dataset_path,
        "force_validation_artifact": force_validation_path,
        "supervised_rows": int(supervised.get("rows_emitted") or len(supervised_rows)),
        **counts,
        "source_artifacts": [supervised_dataset_path, force_validation_path],
        "execution_enabled": False,
        "restore_executed": False,
        "trajectory_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows, "sources": source_rows, "missing_prefixes": missing_prefix_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "summary": payload["summary"],
        "rows": payload["rows"],
        "sources": payload["sources"][:48],
        "missing_prefixes": payload["missing_prefixes"][:48],
    }
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force Artifact Recovery Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- force_artifact_recovery_required: `{s['force_artifact_recovery_required']}`",
        f"- valid_trajectory_path_rows: `{s['valid_trajectory_path_rows']}`",
        f"- existing_trajectory_npz_rows: `{s['existing_trajectory_npz_rows']}`",
        f"- missing_trajectory_npz_rows: `{s['missing_trajectory_npz_rows']}`",
        f"- missing_path_prefix_count: `{s['missing_path_prefix_count']}`",
        f"- top_missing_prefix: `{s['top_missing_prefix']}`",
        f"- top_missing_source: `{s['top_missing_source']}`",
        "",
        "## Work Items",
        "",
        "| check | status | observed | required | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Missing Prefixes", "", "| rank | missing rows | prefix | top source | example |", "| ---: | ---: | --- | --- | --- |"])
    for item in payload["missing_prefixes"][:24]:
        lines.append(
            f"| `{item['rank']}` | `{item['missing_trajectory_npz_rows']}` | `{item['missing_prefix']}` | `{item['top_source_csv']}` | `{item['example_missing_trajectory_npz']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual force trajectory artifact recovery work order.")
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--force-validation-json", default=DEFAULT_FORCE_VALIDATION_JSON)
    parser.add_argument("--max-sources", type=int, default=24)
    parser.add_argument("--max-rows-per-source", type=int, default=20000)
    parser.add_argument("--prefix-depth", type=int, default=5)
    parser.add_argument("--max-prefix-work-items", type=int, default=24)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_artifact_recovery_work_order(
        supervised_dataset_packet=_read_json_if_present(args.supervised_dataset_json),
        force_validation_packet=_read_json_if_present(args.force_validation_json),
        supervised_dataset_path=args.supervised_dataset_json,
        force_validation_path=args.force_validation_json,
        max_sources=args.max_sources,
        max_rows_per_source=args.max_rows_per_source,
        prefix_depth=args.prefix_depth,
        max_prefix_work_items=args.max_prefix_work_items,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
