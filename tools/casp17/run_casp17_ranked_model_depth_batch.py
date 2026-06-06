#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_JOB_ROOT = "runs/casp17_prediction_jobs_top5_current"
DEFAULT_RANKED_TS_DIR = "runs/casp17_predictions_top5_current"
DEFAULT_OUT_JSON = "runs/casp17_ranked_model_depth_batch_current.json"
DEFAULT_OUT_CSV = "runs/casp17_ranked_model_depth_batch_current.csv"
DEFAULT_OUT_MD = "runs/casp17_ranked_model_depth_batch_current.md"
DEFAULT_RANKED_DEPTH_JSON = "runs/casp17_ranked_model_depth_packet_current.json"
DEFAULT_RANKED_DEPTH_CSV = "runs/casp17_ranked_model_depth_packet_current.csv"
DEFAULT_RANKED_DEPTH_MD = "runs/casp17_ranked_model_depth_packet_current.md"


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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _current_open_targets(watchlist: dict[str, Any]) -> list[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return []
    targets: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lane = _text(row.get("lane_recommendation"))
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}:
            targets.append(target_id)
    return targets


def _target_ids(args: argparse.Namespace) -> list[str]:
    explicit = [item.strip().upper() for item in _text(args.target_ids).split(",") if item.strip()]
    targets = explicit or _current_open_targets(_read_json(args.target_watchlist_json))
    if int(args.target_limit) > 0:
        return targets[: int(args.target_limit)]
    return targets


def _has_ranked_raw(target_id: str, job_root: str | Path, model_count: int) -> bool:
    root = _resolve(job_root) / target_id
    return all((root / f"{target_id}_model_{rank}.pdb").exists() for rank in range(1, int(model_count) + 1))


def _predictor_command(target_id: str, args: argparse.Namespace) -> list[str]:
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    out_dir = _resolve(args.job_root) / target_id
    command = [
        sys.executable,
        str(ROOT / "tools/run_casp17_internal_physics_baseline_predictor.py"),
        "--target-id",
        target_id,
        "--fasta",
        str(sequence_path),
        "--out-dir",
        str(out_dir),
        "--raw-pdb",
        str(out_dir / f"{target_id}_model_1.pdb"),
        "--runtime-json",
        str(out_dir / "backend_runtime.json"),
        "--metrics-json",
        str(out_dir / "internal_physics_metrics.json"),
        "--device",
        str(args.device),
        "--quality-preset",
        str(args.quality_preset),
        "--ranked-raw-dir",
        str(out_dir),
        "--ranked-raw-count",
        str(max(1, min(5, int(args.model_count)))),
        "--out-json",
        str(out_dir / "predictor.json"),
        "--out-csv",
        str(out_dir / "predictor.csv"),
        "--out-md",
        str(out_dir / "predictor.md"),
    ]
    if int(args.ensemble_size) > 0:
        command.extend(["--ensemble-size", str(args.ensemble_size)])
    if int(args.steps) > 0:
        command.extend(["--steps", str(args.steps)])
    if int(args.docking_steps) >= 0:
        command.extend(["--docking-steps", str(args.docking_steps)])
    if int(args.seed) >= 0:
        command.extend(["--seed", str(int(args.seed) + _stable_target_offset(target_id))])
    if bool(args.allow_cpu):
        command.append("--allow-cpu")
    if bool(args.emit_backbone_atoms):
        command.append("--emit-backbone-atoms")
    return command


def _stable_target_offset(target_id: str) -> int:
    value = 0
    for char in target_id:
        value = (value * 131 + ord(char)) % 1_000_003
    return value


def _run_predictor(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    if not sequence_path.exists():
        return {
            "target_id": target_id,
            "attempt_status": "blocked",
            "predictor_status": "not_run",
            "ranked_raw_ready": False,
            "blockers": "sequence_file_missing",
            "job_dir": _artifact(_resolve(args.job_root) / target_id),
        }
    if bool(args.skip_existing) and _has_ranked_raw(target_id, args.job_root, int(args.model_count)):
        return {
            "target_id": target_id,
            "attempt_status": "skipped_existing",
            "predictor_status": "skipped",
            "ranked_raw_ready": True,
            "blockers": "",
            "job_dir": _artifact(_resolve(args.job_root) / target_id),
        }
    if not bool(args.execute):
        return {
            "target_id": target_id,
            "attempt_status": "planned",
            "predictor_status": "not_run",
            "ranked_raw_ready": _has_ranked_raw(target_id, args.job_root, int(args.model_count)),
            "blockers": "",
            "job_dir": _artifact(_resolve(args.job_root) / target_id),
        }

    command = _predictor_command(target_id, args)
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    predictor_json = _resolve(args.job_root) / target_id / "predictor.json"
    predictor_summary = _read_json(predictor_json).get("summary", {})
    status = "completed" if completed.returncode == 0 else "failed"
    return {
        "target_id": target_id,
        "attempt_status": status,
        "predictor_status": _text(predictor_summary.get("predictor_status")) or status,
        "ranked_raw_ready": _has_ranked_raw(target_id, args.job_root, int(args.model_count)),
        "ranked_raw_count": int(predictor_summary.get("ranked_raw_count", 0) or 0),
        "return_code": completed.returncode,
        "stderr_tail": completed.stderr[-600:],
        "blockers": "" if completed.returncode == 0 else "predictor_command_failed",
        "job_dir": _artifact(_resolve(args.job_root) / target_id),
    }


def _run_ranked_depth_builder(target_ids: list[str], args: argparse.Namespace) -> dict[str, Any]:
    if not bool(args.execute) and not bool(args.build_ranked_depth_without_execute):
        return {"summary": {"ranked_depth_status": "not_run"}}
    command = [
        sys.executable,
        str(ROOT / "tools/build_casp17_ranked_model_depth_packet.py"),
        "--target-ids",
        ",".join(target_ids),
        "--ranked-raw-root",
        str(_resolve(args.job_root)),
        "--sequence-dir",
        str(_resolve(args.sequence_dir)),
        "--out-dir",
        str(_resolve(args.ranked_ts_dir)),
        "--author-code",
        str(args.author_code),
        "--model-count",
        str(max(1, min(5, int(args.model_count)))),
        "--out-json",
        str(_resolve(args.ranked_depth_json)),
        "--out-csv",
        str(_resolve(args.ranked_depth_csv)),
        "--out-md",
        str(_resolve(args.ranked_depth_md)),
    ]
    if bool(args.allow_partial):
        command.append("--allow-partial")
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    payload = _read_json(args.ranked_depth_json)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if completed.returncode != 0:
        summary = {
            **summary,
            "ranked_depth_status": _text(summary.get("ranked_depth_status")) or "blocked",
            "builder_return_code": completed.returncode,
            "builder_stderr_tail": completed.stderr[-600:],
        }
    return {"summary": summary, "rows": payload.get("rows", []) if isinstance(payload.get("rows"), list) else []}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    targets = _target_ids(args)
    rows = [_run_predictor(target_id, args) for target_id in targets]
    ranked_depth_payload = _run_ranked_depth_builder(targets, args) if targets else {"summary": {"ranked_depth_status": "no_targets"}}
    summary = {
        "packet_type": "casp17_ranked_model_depth_batch",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "execute": bool(args.execute),
        "target_count": len(targets),
        "completed_count": sum(1 for row in rows if row["attempt_status"] == "completed"),
        "skipped_existing_count": sum(1 for row in rows if row["attempt_status"] == "skipped_existing"),
        "planned_count": sum(1 for row in rows if row["attempt_status"] == "planned"),
        "failed_count": sum(1 for row in rows if row["attempt_status"] in {"failed", "blocked"}),
        "ranked_raw_ready_count": sum(1 for row in rows if row.get("ranked_raw_ready") is True),
        "model_count": max(1, min(5, int(args.model_count))),
        "ranked_depth_json": _artifact(args.ranked_depth_json),
        "ranked_depth_status": _text(ranked_depth_payload.get("summary", {}).get("ranked_depth_status")),
        "ranked_depth_pass_count": int(ranked_depth_payload.get("summary", {}).get("pass_count", 0) or 0),
        "candidate_gate_pass_count": int(ranked_depth_payload.get("summary", {}).get("candidate_gate_pass_count", 0) or 0),
        "candidate_gate_total_count": int(ranked_depth_payload.get("summary", {}).get("candidate_gate_total_count", 0) or 0),
        "claim_boundary": "Ranked model-depth batch orchestration only; not CASP portal submission or official native-accuracy evidence.",
    }
    return {"summary": summary, "rows": rows, "ranked_depth_summary": ranked_depth_payload.get("summary", {})}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Ranked Model Depth Batch",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- execute: `{summary['execute']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- completed/skipped/planned/failed: `{summary['completed_count']}/{summary['skipped_existing_count']}/{summary['planned_count']}/{summary['failed_count']}`",
        f"- ranked raw ready: `{summary['ranked_raw_ready_count']}`",
        f"- ranked depth status: `{summary['ranked_depth_status']}`",
        f"- ranked depth pass: `{summary['ranked_depth_pass_count']}`",
        f"- candidate gates: `{summary['candidate_gate_pass_count']}/{summary['candidate_gate_total_count']}`",
        "",
        "| target | attempt | predictor | ranked raw ready | ranked raw count | blockers |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['attempt_status']}` | `{row['predictor_status']}` | "
            f"`{row.get('ranked_raw_ready', False)}` | {row.get('ranked_raw_count', 0)} | {row.get('blockers') or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run internal ranked top-5 CASP17 candidate generation and validation.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--job-root", default=DEFAULT_JOB_ROOT)
    parser.add_argument("--ranked-ts-dir", default=DEFAULT_RANKED_TS_DIR)
    parser.add_argument("--author-code", required=True)
    parser.add_argument("--model-count", type=int, default=5)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--quality-preset", choices=["casp17_quality", "fast", "smoke"], default="fast")
    parser.add_argument("--ensemble-size", type=int, default=8)
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--docking-steps", type=int, default=-1)
    parser.add_argument("--seed", type=int, default=27017)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--emit-backbone-atoms", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--build-ranked-depth-without-execute", action="store_true")
    parser.add_argument("--ranked-depth-json", default=DEFAULT_RANKED_DEPTH_JSON)
    parser.add_argument("--ranked-depth-csv", default=DEFAULT_RANKED_DEPTH_CSV)
    parser.add_argument("--ranked-depth-md", default=DEFAULT_RANKED_DEPTH_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["failed_count"] and bool(args.execute):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
