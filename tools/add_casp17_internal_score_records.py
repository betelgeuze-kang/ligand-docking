#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_recursive_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_scored_current"
DEFAULT_OUT_JSON = "runs/casp17_internal_score_record_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_internal_score_record_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_internal_score_record_packet_current.md"


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _float_slice(line: str, start: int, end: int, fallback_index: int) -> float | None:
    if len(line) >= end:
        parsed = _float_or_none(line[start:end])
        if parsed is not None:
            return parsed
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


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
    return explicit or _current_open_targets(_read_json(args.target_watchlist_json))


def _atom_name(line: str) -> str:
    return line[12:16].strip() if len(line) >= 16 else (line.split()[2] if len(line.split()) > 2 else "")


def _atom_chain_id(line: str) -> str:
    if len(line) > 21:
        return line[21].strip() or "_"
    fields = line.split()
    return fields[4] if len(fields) > 4 else "_"


def _atom_coord(line: str) -> tuple[float, float, float] | None:
    x = _float_slice(line, 30, 38, 6)
    y = _float_slice(line, 38, 46, 7)
    z = _float_slice(line, 46, 54, 8)
    if x is None or y is None or z is None:
        return None
    return x, y, z


def _atom_b_factor(line: str) -> float | None:
    return _float_slice(line, 60, 66, 10)


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2)


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _model_atom_lines(lines: list[str]) -> list[str]:
    atoms: list[str] = []
    in_first_model = False
    seen_model = False
    for line in lines:
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec == "ATOM" and (in_first_model or not seen_model):
            atoms.append(line)
    return atoms


def _global_score(atoms: list[str]) -> tuple[float, dict[str, Any]]:
    b_factors = [value for line in atoms if (value := _atom_b_factor(line)) is not None]
    if not b_factors:
        return 0.05, {"confidence_mean": 0.0, "confidence_stddev": 0.0, "basis": "missing_b_factors"}
    mean = sum(b_factors) / len(b_factors)
    variance = sum((value - mean) ** 2 for value in b_factors) / max(len(b_factors), 1)
    stddev = math.sqrt(variance)
    score = 0.10 + 0.48 * (mean / 100.0) + 0.05 * min(stddev / 20.0, 1.0)
    return round(_clamp(score, 0.05, 0.68), 3), {
        "confidence_mean": round(mean, 3),
        "confidence_stddev": round(stddev, 3),
        "basis": "internal_b_factor_confidence_conservative_uncalibrated",
    }


def _chain_ca_coords(atoms: list[str]) -> dict[str, list[tuple[float, float, float]]]:
    chains: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for line in atoms:
        if _atom_name(line) != "CA":
            continue
        coord = _atom_coord(line)
        if coord is None:
            continue
        chains[_atom_chain_id(line)].append(coord)
    return dict(chains)


def _interface_scores(atoms: list[str], global_score: float) -> tuple[list[str], dict[str, Any]]:
    chains = _chain_ca_coords(atoms)
    chain_ids = sorted(chain for chain, coords in chains.items() if coords)
    qscore_records: list[str] = []
    contact_pairs = 0
    for left_index, left_chain in enumerate(chain_ids):
        for right_chain in chain_ids[left_index + 1 :]:
            left_coords = chains[left_chain]
            right_coords = chains[right_chain]
            contacts = 0
            clashes = 0
            min_distance = float("inf")
            for left in left_coords:
                for right in right_coords:
                    distance = _distance(left, right)
                    min_distance = min(min_distance, distance)
                    contacts += int(distance <= 12.0)
                    clashes += int(distance < 3.0)
            if contacts <= 0:
                continue
            contact_pairs += 1
            contact_scale = min(contacts / max(8.0, min(len(left_coords), len(right_coords)) * 4.0), 1.0)
            qscore = 0.08 + 0.32 * contact_scale + 0.22 * global_score
            if clashes:
                qscore *= 0.45
            qscore_records.append(f"{left_chain}{right_chain}:{_clamp(qscore, 0.03, 0.62):.3f}")
    return qscore_records, {"chain_count": len(chain_ids), "interface_count": contact_pairs}


def _strip_existing_score_records(lines: list[str]) -> list[str]:
    stripped: list[str] = []
    for line in lines:
        rec = _record(line)
        if rec in {"SCORE", "QSCORE"}:
            continue
        if line.startswith("REMARK INTERNAL_CASP17_SCORE_RECORD"):
            continue
        stripped.append(line)
    return stripped


def _augment_text(text: str) -> tuple[str, dict[str, Any]]:
    lines = _strip_existing_score_records(text.splitlines())
    atoms = _model_atom_lines(lines)
    score, score_metrics = _global_score(atoms)
    qscores, interface_metrics = _interface_scores(atoms, score)
    output: list[str] = []
    inserted = False
    for line in lines:
        output.append(line)
        if not inserted and _record(line) == "MODEL":
            output.append(f"SCORE {score:.3f}")
            if qscores:
                output.append(f"QSCORE {', '.join(qscores)}")
            output.append(
                "REMARK INTERNAL_CASP17_SCORE_RECORD conservative internal confidence estimate; "
                "not native-calibrated accuracy evidence"
            )
            inserted = True
    if not inserted:
        output.extend(
            [
                f"SCORE {score:.3f}",
                "REMARK INTERNAL_CASP17_SCORE_RECORD inserted without MODEL anchor; validate before use",
            ]
        )
    output.append("")
    return "\n".join(output), {**score_metrics, **interface_metrics, "score": score, "qscore_count": len(qscores)}


def _target_row(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    source_path = _resolve(args.source_dir) / f"{target_id}TS.pdb"
    out_path = _resolve(args.out_dir) / f"{target_id}TS.pdb"
    if not source_path.exists():
        return {
            "target_id": target_id,
            "score_record_status": "blocked",
            "source_pdb": _artifact(source_path),
            "out_pdb": _artifact(out_path),
            "score": 0.0,
            "qscore_count": 0,
            "chain_count": 0,
            "blockers": "source_prediction_missing",
        }
    augmented, metrics = _augment_text(source_path.read_text(encoding="utf-8", errors="replace"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(augmented, encoding="utf-8")
    qscore_expected = int(metrics["chain_count"]) > 1
    blockers: list[str] = []
    if metrics["score"] <= 0.0:
        blockers.append("score_not_available")
    if qscore_expected and int(metrics["qscore_count"]) == 0:
        blockers.append("qscore_not_available_for_multichain")
    return {
        "target_id": target_id,
        "score_record_status": "pass" if not blockers else "blocked",
        "source_pdb": _artifact(source_path),
        "out_pdb": _artifact(out_path),
        "score": metrics["score"],
        "qscore_count": metrics["qscore_count"],
        "chain_count": metrics["chain_count"],
        "confidence_mean": metrics["confidence_mean"],
        "confidence_stddev": metrics["confidence_stddev"],
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_target_row(target_id, args) for target_id in _target_ids(args)]
    multichain_count = sum(1 for row in rows if int(row.get("chain_count", 0) or 0) > 1)
    score_pass_count = sum(1 for row in rows if float(row.get("score", 0.0) or 0.0) > 0.0)
    qscore_pass_count = sum(
        1
        for row in rows
        if int(row.get("chain_count", 0) or 0) > 1 and int(row.get("qscore_count", 0) or 0) > 0
    )
    pass_count = sum(1 for row in rows if row["score_record_status"] == "pass")
    summary = {
        "packet_type": "casp17_internal_score_record_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "score_record_count": score_pass_count,
        "qscore_multichain_count": qscore_pass_count,
        "multichain_target_count": multichain_count,
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "score_record_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "claim_boundary": "Adds conservative internal SCORE/QSCORE records only; not native-calibrated CASP accuracy evidence or portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Internal SCORE/QSCORE Record Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- SCORE records: `{summary['score_record_count']}/{summary['target_count']}`",
        f"- multichain QSCORE records: `{summary['qscore_multichain_count']}/{summary['multichain_target_count']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        "",
        "| target | status | score | qscore_count | chains | output | blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['score_record_status']}` | {row['score']:.3f} | "
            f"{row['qscore_count']} | {row['chain_count']} | `{row['out_pdb']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add conservative internal SCORE/QSCORE records to CASP17 TS prediction copies.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
    if payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
