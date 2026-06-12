#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.casp17 import validate_casp17_confidence_calibration as confidence_validator
from tools.casp17 import validate_casp17_geometry_sanity as geometry_validator
from tools import validate_casp17_ts_prediction as format_validator


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_RANKED_RAW_ROOT = "runs/casp17_prediction_jobs_top5_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_top5_current"
DEFAULT_OUT_JSON = "runs/casp17_ranked_model_depth_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_ranked_model_depth_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_ranked_model_depth_packet_current.md"


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


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
    if explicit:
        return explicit
    return _current_open_targets(_read_json(args.target_watchlist_json))


def _raw_atom_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _record(line) == "ATOM":
            lines.append(line.rstrip("\r\n"))
    return lines


def _atom_chain_id(line: str) -> str:
    if len(line) > 21:
        return line[21].strip() or "_"
    fields = line.split()
    return fields[4] if len(fields) > 4 else "_"


def _coordinate_lines(atoms: list[str], parent: str) -> tuple[list[str], int, int]:
    lines: list[str] = []
    current_chain = ""
    parent_count = 0
    ter_count = 0
    for atom in atoms:
        chain_id = _atom_chain_id(atom)
        if chain_id != current_chain:
            if current_chain:
                lines.append("TER")
                ter_count += 1
            lines.append(f"PARENT {parent}")
            parent_count += 1
            current_chain = chain_id
        lines.append(atom)
    if current_chain:
        lines.append("TER")
        ter_count += 1
    return lines, parent_count, ter_count


def _convert_one(
    *,
    target_id: str,
    model_index: int,
    input_pdb: Path,
    output_pdb: Path,
    author_code: str,
    method: str,
    parent: str,
) -> tuple[str, int, int, int]:
    atoms = _raw_atom_lines(input_pdb)
    if not atoms:
        return "atom_records_missing", 0, 0, 0
    coordinate_lines, parent_count, ter_count = _coordinate_lines(atoms, parent)
    lines = [
        "PFRMAT TS",
        f"TARGET {target_id}",
        f"AUTHOR {author_code}",
        f"METHOD {method}",
        f"MODEL {model_index}",
        *coordinate_lines,
        "END",
        "",
    ]
    output_pdb.parent.mkdir(parents=True, exist_ok=True)
    output_pdb.write_text("\n".join(lines), encoding="utf-8")
    return "pass", len(atoms), parent_count, ter_count


def _validate_candidate(target_id: str, ts_pdb: Path, sequence_path: Path) -> dict[str, Any]:
    format_payload = format_validator.validate_prediction(
        target_id=target_id,
        prediction_file=ts_pdb,
        sequence_path=sequence_path,
        allow_ranked_model_index=True,
    )
    geometry_payload = geometry_validator.validate_geometry(target_id=target_id, prediction_file=ts_pdb)
    confidence_payload = confidence_validator.validate_confidence(
        target_id=target_id,
        prediction_file=ts_pdb,
        sequence_path=sequence_path,
    )
    statuses = {
        "format_check_status": format_payload["summary"]["format_check_status"],
        "geometry_sanity_status": geometry_payload["summary"]["geometry_sanity_status"],
        "confidence_calibration_status": confidence_payload["summary"]["confidence_calibration_status"],
    }
    return {
        **statuses,
        "candidate_gate_status": "pass" if set(statuses.values()) == {"pass"} else "blocked",
        "format_blocker_count": format_payload["summary"].get("blocker_count", 0),
        "geometry_blocker_count": geometry_payload["summary"].get("blocker_count", 0),
        "confidence_blocker_count": confidence_payload["summary"].get("blocker_count", 0),
    }


def _target_row(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    model_count = max(1, min(5, int(args.model_count)))
    raw_root = _resolve(args.ranked_raw_root)
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    target_raw_dir = raw_root / target_id
    if not target_raw_dir.exists():
        fallback = raw_root
        if (fallback / f"{target_id}_model_1.pdb").exists():
            target_raw_dir = fallback
    out_target_dir = _resolve(args.out_dir) / target_id
    global_blockers: list[str] = []
    blockers: list[str] = []
    converted_models: list[dict[str, Any]] = []

    if not _text(args.author_code):
        global_blockers.append("missing_author_code")
    if not sequence_path.exists():
        global_blockers.append("sequence_file_missing")
    blockers.extend(global_blockers)
    for model_index in range(1, model_count + 1):
        raw_pdb = target_raw_dir / f"{target_id}_model_{model_index}.pdb"
        out_pdb = out_target_dir / f"{target_id}_model_{model_index}TS.pdb"
        if global_blockers:
            status, atom_count, parent_count, ter_count = "blocked", 0, 0, 0
        elif not raw_pdb.exists():
            status, atom_count, parent_count, ter_count = "raw_model_missing", 0, 0, 0
        else:
            status, atom_count, parent_count, ter_count = _convert_one(
                target_id=target_id,
                model_index=model_index,
                input_pdb=raw_pdb,
                output_pdb=out_pdb,
                author_code=_text(args.author_code),
                method=_text(args.method)
                or "Internal CASP17 ranked physics baseline candidate; repo-local torch/coarse-grain ensemble, no external predictor or template structure.",
                parent=_text(args.parent) or "N/A",
            )
        validation: dict[str, Any] = {
            "candidate_gate_status": "not_run",
            "format_check_status": "",
            "geometry_sanity_status": "",
            "confidence_calibration_status": "",
            "format_blocker_count": 0,
            "geometry_blocker_count": 0,
            "confidence_blocker_count": 0,
        }
        if status == "pass" and bool(args.validate_candidates):
            validation = _validate_candidate(target_id, out_pdb, sequence_path)
        if status != "pass":
            blockers.append(f"model_{model_index}_{status}")
        elif bool(args.validate_candidates) and validation["candidate_gate_status"] != "pass":
            blockers.append(f"model_{model_index}_candidate_gate_{validation['candidate_gate_status']}")
        converted_models.append(
            {
                "rank": model_index,
                "raw_pdb": _artifact(raw_pdb),
                "ts_pdb": _artifact(out_pdb),
                "conversion_status": status,
                **validation,
                "atom_count": atom_count,
                "parent_record_count": parent_count,
                "ter_record_count": ter_count,
            }
        )

    converted_count = sum(1 for item in converted_models if item["conversion_status"] == "pass")
    candidate_gate_pass_count = sum(1 for item in converted_models if item["candidate_gate_status"] == "pass")
    unique_blockers = sorted(set(blockers))
    ranked_depth_status = "pass" if converted_count >= model_count and candidate_gate_pass_count >= model_count and not unique_blockers else "blocked"
    return {
        "target_id": target_id,
        "ranked_depth_status": ranked_depth_status,
        "model_count_requested": model_count,
        "converted_count": converted_count,
        "candidate_gate_pass_count": candidate_gate_pass_count,
        "ranked_raw_dir": _artifact(target_raw_dir),
        "ranked_ts_dir": _artifact(out_target_dir),
        "sequence_path": _artifact(sequence_path),
        "blockers": ",".join(unique_blockers),
        "_models": converted_models,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_target_row(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["ranked_depth_status"] == "pass")
    partial_count = sum(1 for row in rows if 0 < int(row["converted_count"]) < int(row["model_count_requested"]))
    candidate_gate_pass_count = sum(int(row["candidate_gate_pass_count"]) for row in rows)
    candidate_gate_total_count = sum(int(row["model_count_requested"]) for row in rows)
    summary = {
        "packet_type": "casp17_ranked_model_depth_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "partial_count": partial_count,
        "blocked_count": len(rows) - pass_count,
        "model_count_requested": max(1, min(5, int(args.model_count))),
        "candidate_gate_pass_count": candidate_gate_pass_count,
        "candidate_gate_total_count": candidate_gate_total_count,
        "validate_candidates": bool(args.validate_candidates),
        "ranked_depth_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "ranked_raw_root": _artifact(args.ranked_raw_root),
        "ranked_ts_out_dir": _artifact(args.out_dir),
        "claim_boundary": "Ranked model-depth packet only; not CASP portal submission or official native-accuracy evidence.",
    }
    public_rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]
    return {"summary": summary, "rows": public_rows, "models": {row["target_id"]: row["_models"] for row in rows}}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Ranked Model Depth Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- model_count_requested: `{summary['model_count_requested']}`",
        f"- pass/partial/blocked: `{summary['pass_count']}/{summary['partial_count']}/{summary['blocked_count']}`",
        f"- ranked_depth_status: `{summary['ranked_depth_status']}`",
        "",
        "| target | status | converted | candidate gates | ranked TS dir | blockers |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['ranked_depth_status']}` | {row['converted_count']}/{row['model_count_requested']} | "
            f"{row['candidate_gate_pass_count']}/{row['model_count_requested']} | "
            f"`{row['ranked_ts_dir']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TS files for ranked CASP17 internal model-depth candidates.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--ranked-raw-root", default=DEFAULT_RANKED_RAW_ROOT)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--author-code", required=True)
    parser.add_argument("--model-count", type=int, default=5)
    parser.add_argument("--method", default="")
    parser.add_argument("--parent", default="N/A")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--validate-candidates", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["blocked_count"] and not args.allow_partial:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
