#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shlex
from pathlib import Path
from typing import Any

from tools import validate_casp17_backend_contract as contract_validator
from tools import validate_casp17_confidence_calibration as confidence_validator
from tools import validate_casp17_geometry_sanity as geometry_validator


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LAUNCH_PACKET_JSON = "runs/casp17_prediction_launch_packet_current.json"
DEFAULT_OUT_DIR = "runs/casp17_internal_physics_raw_validations_current"
DEFAULT_OUT_JSON = "runs/casp17_internal_physics_raw_gate_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_internal_physics_raw_gate_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_internal_physics_raw_gate_packet_current.md"


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
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


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Internal Physics Raw Gate Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- launch packet: `{summary['launch_packet_json']}`",
        f"- target count: `{summary['target_count']}`",
        f"- pass/fail/skipped: `{summary['pass_count']}/{summary['fail_count']}/{summary['skipped_count']}`",
        f"- require GPU evidence: `{summary['require_gpu']}`",
        f"- out dir: `{summary['out_dir']}`",
        "",
        "## Rows",
        "",
        "| target | kind | raw gate | contract | geometry | confidence | residues | blockers | raw PDB |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row.get('target_kind') or '-'}` | `{row['raw_gate_status']}` | "
            f"`{row['contract_status']}` | `{row['geometry_sanity_status']}` | "
            f"`{row['confidence_calibration_status']}` | `{row.get('residue_count', 0)}` | "
            f"{row.get('blockers') or '-'} | `{row.get('raw_pdb') or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `no_rows` | - | - | - | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _launch_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return rows if isinstance(rows, list) else []


def _option_value(command: str, option: str) -> str:
    if not _text(command):
        return ""
    try:
        parts = shlex.split(command)
    except ValueError:
        return ""
    for index, part in enumerate(parts):
        if part == option and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith(option + "="):
            return part.split("=", 1)[1]
    return ""


def _target_paths(row: dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    command = _text(row.get("command"))
    raw_pdb = _option_value(command, "--raw-pdb")
    runtime_json = _option_value(command, "--runtime-json")
    target_id = _text(row.get("target_id")).upper()
    if not raw_pdb:
        raw_pdb = str(_resolve(args.job_dir) / target_id / f"{target_id}_model_1.pdb")
    if not runtime_json:
        runtime_json = str(_resolve(args.job_dir) / target_id / "backend_runtime.json")
    return raw_pdb, runtime_json


def _contract_args(
    *,
    target_id: str,
    sequence_path: str,
    raw_pdb: str,
    runtime_json: str,
    require_gpu: bool,
) -> Any:
    return type(
        "Args",
        (),
        {
            "target_id": target_id,
            "sequence_path": sequence_path,
            "raw_pdb": raw_pdb,
            "runtime_json": runtime_json,
            "backend_kind": "internal_physics",
            "require_gpu": require_gpu,
        },
    )()


def _codes(payload: dict[str, Any]) -> list[str]:
    blockers = payload.get("blockers")
    if not isinstance(blockers, list):
        return []
    return [_text(blocker.get("code")) for blocker in blockers if isinstance(blocker, dict) and _text(blocker.get("code"))]


def _target_out_paths(out_dir: Path, target_id: str) -> dict[str, Path]:
    return {
        "contract_json": out_dir / f"{target_id}_backend_contract.json",
        "contract_csv": out_dir / f"{target_id}_backend_contract.csv",
        "contract_md": out_dir / f"{target_id}_backend_contract.md",
        "geometry_json": out_dir / f"{target_id}_raw_geometry_sanity.json",
        "geometry_csv": out_dir / f"{target_id}_raw_geometry_sanity.csv",
        "geometry_md": out_dir / f"{target_id}_raw_geometry_sanity.md",
        "confidence_json": out_dir / f"{target_id}_raw_confidence_calibration.json",
        "confidence_csv": out_dir / f"{target_id}_raw_confidence_calibration.csv",
        "confidence_md": out_dir / f"{target_id}_raw_confidence_calibration.md",
    }


def _validate_row(row: dict[str, Any], args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper()
    target_kind = _text(row.get("target_kind"))
    sequence_path = _text(row.get("sequence_path"))
    raw_pdb, runtime_json = _target_paths(row, args)
    paths = _target_out_paths(out_dir, target_id)
    blockers: list[str] = []

    if _text(row.get("recommended_backend")) != "internal_physics":
        blockers.append("not_internal_physics_backend")
    if _text(row.get("launch_status")) != "ready_to_launch":
        blockers.append(_text(row.get("blockers")) or f"launch_status:{_text(row.get('launch_status'))}")
    if not target_id:
        blockers.append("missing_target_id")
    if not sequence_path:
        blockers.append("missing_sequence_path")

    contract_payload: dict[str, Any] = {"summary": {"contract_status": "blocked", "residue_count": 0}, "blockers": []}
    geometry_payload: dict[str, Any] = {"summary": {"geometry_sanity_status": "blocked"}, "blockers": []}
    confidence_payload: dict[str, Any] = {"summary": {"confidence_calibration_status": "blocked"}, "blockers": []}
    if not blockers:
        contract_payload = contract_validator.validate_contract(
            _contract_args(
                target_id=target_id,
                sequence_path=sequence_path,
                raw_pdb=raw_pdb,
                runtime_json=runtime_json,
                require_gpu=bool(args.require_gpu),
            )
        )
        contract_validator._write_json(paths["contract_json"], contract_payload)
        contract_validator._write_csv(paths["contract_csv"], [contract_payload["summary"]])
        contract_validator._write_md(paths["contract_md"], contract_payload)
        blockers.extend(f"contract:{code}" for code in _codes(contract_payload))

        geometry_payload = geometry_validator.validate_geometry(target_id=target_id, prediction_file=raw_pdb)
        geometry_validator._write_json(paths["geometry_json"], geometry_payload)
        geometry_validator._write_csv(paths["geometry_csv"], [geometry_payload["summary"]])
        geometry_validator._write_md(paths["geometry_md"], geometry_payload)
        blockers.extend(f"geometry:{code}" for code in _codes(geometry_payload))

        confidence_payload = confidence_validator.validate_confidence(
            target_id=target_id,
            prediction_file=raw_pdb,
            sequence_path=sequence_path,
        )
        confidence_validator._write_json(paths["confidence_json"], confidence_payload)
        confidence_validator._write_csv(paths["confidence_csv"], [confidence_payload["summary"]])
        confidence_validator._write_md(paths["confidence_md"], confidence_payload)
        blockers.extend(f"confidence:{code}" for code in _codes(confidence_payload))

    raw_gate_status = "pass" if not blockers else "fail"
    return {
        "target_id": target_id,
        "target_kind": target_kind,
        "raw_gate_status": raw_gate_status,
        "contract_status": contract_payload["summary"].get("contract_status", "blocked"),
        "geometry_sanity_status": geometry_payload["summary"].get("geometry_sanity_status", "blocked"),
        "confidence_calibration_status": confidence_payload["summary"].get("confidence_calibration_status", "blocked"),
        "residue_count": contract_payload["summary"].get("residue_count", 0),
        "fasta_residue_count": contract_payload["summary"].get("fasta_residue_count", 0),
        "gpu_evidence_detected": contract_payload["summary"].get("gpu_evidence_detected", False),
        "raw_pdb": _artifact(raw_pdb),
        "runtime_json": _artifact(runtime_json),
        "contract_json": _artifact(paths["contract_json"]) if paths["contract_json"].exists() else "",
        "geometry_json": _artifact(paths["geometry_json"]) if paths["geometry_json"].exists() else "",
        "confidence_json": _artifact(paths["confidence_json"]) if paths["confidence_json"].exists() else "",
        "blockers": ";".join(dict.fromkeys(blockers)),
        "next_required_step": (
            "Convert raw PDB to CASP TS with the real CASP author code, then run import/validation/scorecard/submission gate."
            if raw_gate_status == "pass"
            else "Fix internal physics raw generation before TS conversion."
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    launch_packet = _read_json(args.launch_packet_json)
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_validate_row(row, args, out_dir) for row in _launch_rows(launch_packet)]
    pass_count = sum(1 for row in rows if row["raw_gate_status"] == "pass")
    fail_count = sum(1 for row in rows if row["raw_gate_status"] == "fail")
    skipped_count = sum(1 for row in rows if row["raw_gate_status"] == "skipped")
    summary = {
        "packet_type": "casp17_internal_physics_raw_gate_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "launch_packet_json": _artifact(args.launch_packet_json),
        "out_dir": _artifact(args.out_dir),
        "job_dir": _artifact(args.job_dir),
        "require_gpu": bool(args.require_gpu),
        "target_count": len(rows),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "skipped_count": skipped_count,
        "raw_gate_status": "pass" if rows and fail_count == 0 else "fail",
        "claim_boundary": "Internal physics raw artifact gate only; not CASP17 TS validation, public submission, or official accuracy evidence.",
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate internal-physics raw PDB artifacts before CASP17 TS conversion.")
    parser.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    parser.add_argument("--job-dir", default="runs/casp17_prediction_jobs_current")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--require-gpu", action=argparse.BooleanOptionalAction, default=True)
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
    if payload["summary"]["raw_gate_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
