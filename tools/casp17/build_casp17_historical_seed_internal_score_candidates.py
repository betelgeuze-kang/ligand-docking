#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.casp17 import add_casp17_internal_score_records as score_records


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CALIBRATION_LEDGER_JSON = "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.json"
DEFAULT_SCORE_DIR = "casp17/historical_seed_internal_score_candidates"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_internal_score_candidates_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_internal_score_candidates_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_INTERNAL_SCORE_CANDIDATES.md"

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "score_status",
    "score_candidate_csv",
    "candidate_count",
    "scored_candidate_count",
    "selected_score_candidate",
    "best_internal_score_candidate",
    "top5_scored_ready",
    "next_action",
    "blockers",
]

CANDIDATE_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_rank",
    "role",
    "path",
    "exists",
    "atom_count",
    "coordinate_valid",
    "sha256_16",
    "internal_score_candidate",
    "qscore_count",
    "chain_count",
    "confidence_mean",
    "confidence_stddev",
    "score_status",
    "blockers",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed internal score candidates only. Scores reuse the conservative internal "
    "SCORE/QSCORE confidence heuristic already used for local PDB review. They are not native oracle metrics, "
    "not no-leak clearance, not selected-vs-best proof, not official CASP assessment, and not a CASP submission."
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
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() == "true"


def _float(value: Any) -> float:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return 0.0


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _pdb_stats(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    stats: dict[str, Any] = {
        "exists": path.is_file(),
        "atom_count": 0,
        "coordinate_valid": False,
        "sha256_16": "",
    }
    if not path.is_file():
        return stats
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    atom_count = 0
    coordinate_valid = True
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            atom_count += 1
            try:
                float(line[30:38])
                float(line[38:46])
                float(line[46:54])
            except ValueError:
                coordinate_valid = False
    stats["atom_count"] = atom_count
    stats["coordinate_valid"] = coordinate_valid and atom_count > 0
    stats["sha256_16"] = digest.hexdigest()[:16]
    return stats


def _candidate_rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = payload.get("candidate_rows_by_target")
    if not isinstance(grouped, dict):
        return {}
    return {
        _text(target).upper(): [row for row in rows if isinstance(row, dict)]
        for target, rows in grouped.items()
        if isinstance(rows, list)
    }


def _score_candidate(raw: dict[str, Any], fallback_rank: int) -> dict[str, Any]:
    target_id = _text(raw.get("target_id")).upper()
    path_text = _text(raw.get("path"))
    path = _resolve(path_text) if path_text else ROOT / "__missing_candidate_path__"
    stats = _pdb_stats(path)
    exists = bool(stats["exists"])
    coordinate_valid = bool(stats["coordinate_valid"])
    blockers: list[str] = []
    score = 0.0
    qscore_count = 0
    chain_count = 0
    confidence_mean = 0.0
    confidence_stddev = 0.0
    if not path_text:
        blockers.append("candidate_path_missing")
    if not exists:
        blockers.append("candidate_pdb_missing")
    if exists and not coordinate_valid:
        blockers.append("candidate_coordinates_invalid")
    if exists and coordinate_valid:
        text = path.read_text(encoding="utf-8", errors="replace")
        atoms = score_records._model_atom_lines(text.splitlines())
        if not atoms:
            blockers.append("model_atom_records_missing")
        else:
            score, score_metrics = score_records._global_score(atoms)
            qscores, interface_metrics = score_records._interface_scores(atoms, score)
            qscore_count = len(qscores)
            chain_count = _int(interface_metrics.get("chain_count"))
            confidence_mean = _float(score_metrics.get("confidence_mean"))
            confidence_stddev = _float(score_metrics.get("confidence_stddev"))
    status = "scored" if score > 0.0 and not blockers else "blocked"
    return {
        "target_id": target_id,
        "benchmark_id": _text(raw.get("benchmark_id")),
        "scope": _text(raw.get("scope")),
        "candidate_rank": _int(raw.get("candidate_rank")) or fallback_rank,
        "role": _text(raw.get("role")),
        "path": _artifact(path_text) if path_text else "",
        "exists": exists,
        "atom_count": _int(stats.get("atom_count")) or _int(raw.get("atom_count")),
        "coordinate_valid": coordinate_valid,
        "sha256_16": _text(stats.get("sha256_16")) or _text(raw.get("sha256_16")),
        "internal_score_candidate": f"{score:.3f}" if status == "scored" else "",
        "qscore_count": qscore_count,
        "chain_count": chain_count,
        "confidence_mean": f"{confidence_mean:.3f}" if status == "scored" else "",
        "confidence_stddev": f"{confidence_stddev:.3f}" if status == "scored" else "",
        "score_status": status,
        "blockers": ",".join(dict.fromkeys(blockers)),
        "notes": _text(raw.get("notes")) or "internal score candidate for model-selection review",
    }


def _score_input_required(raw: dict[str, Any]) -> bool:
    role = _text(raw.get("role"))
    if role != "same_run_step_candidate":
        return True
    if _bool(raw.get("exists")) and _bool(raw.get("coordinate_valid")):
        return True
    path = _text(raw.get("path"))
    if not path:
        return False
    stats = _pdb_stats(path)
    return bool(stats["exists"] and stats["coordinate_valid"])


def _build_target_scores(
    target_id: str,
    raw_rows: list[dict[str, Any]],
    row_rank: int,
    score_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    score_inputs = [raw for raw in raw_rows if _score_input_required(raw)]
    scored_rows = [_score_candidate(raw, index) for index, raw in enumerate(score_inputs, start=1)]
    scored_candidates = [row for row in scored_rows if _text(row.get("score_status")) == "scored"]
    selected_rows = [
        row
        for row in scored_candidates
        if _text(row.get("role")) in {"selected_prediction", "selected_prediction_copy"}
    ]
    selected_score = _text(selected_rows[0].get("internal_score_candidate")) if selected_rows else ""
    best_row = max(scored_candidates, key=lambda row: _float(row.get("internal_score_candidate")), default={})
    best_score = _text(best_row.get("internal_score_candidate"))
    top5_ready = len(scored_candidates) >= 5
    blockers: list[str] = []
    if not raw_rows:
        blockers.append("candidate_rows_missing")
    if not selected_score:
        blockers.append("selected_score_candidate_missing")
    if not top5_ready:
        blockers.append("top5_scored_candidates_missing")
    if len(scored_candidates) < len(scored_rows):
        blockers.append("candidate_score_inputs_blocked")
    status = (
        "internal_score_candidates_ready_for_review"
        if not blockers and top5_ready and selected_score and best_score
        else "blocked_internal_score_candidate_inputs"
    )
    score_csv = _resolve(score_dir) / f"{row_rank:02d}_{_safe_name(target_id)}" / "score_candidates.csv"
    _write_csv(score_csv, scored_rows, CANDIDATE_COLUMNS)
    first = scored_rows[0] if scored_rows else {}
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": _text(first.get("benchmark_id")),
        "scope": _text(first.get("scope")),
        "score_status": status,
        "score_candidate_csv": _artifact(score_csv),
        "candidate_count": len(scored_rows),
        "scored_candidate_count": len(scored_candidates),
        "selected_score_candidate": selected_score or "REQUIRES_INTERNAL_SCORE",
        "best_internal_score_candidate": best_score or "REQUIRES_INTERNAL_SCORE",
        "top5_scored_ready": top5_ready,
        "next_action": (
            "feed internal scores into calibration ledger, then attach native oracle metrics"
            if status == "internal_score_candidates_ready_for_review"
            else "repair candidate PDB paths before internal score review"
        ),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    return summary_row, scored_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    ledger_path = _resolve(args.calibration_ledger_json)
    ledger_payload = _read_json(ledger_path)
    grouped = _candidate_rows_by_target(ledger_payload)
    rows: list[dict[str, Any]] = []
    candidate_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, (target_id, raw_rows) in enumerate(grouped.items(), start=1):
        summary_row, scored_rows = _build_target_scores(target_id, raw_rows, index, args.score_dir)
        rows.append(summary_row)
        candidate_rows_by_target[target_id] = scored_rows
    blocked_count = sum(1 for row in rows if row.get("score_status") != "internal_score_candidates_ready_for_review")
    if not ledger_path.exists():
        status = "blocked_missing_candidate_ledger"
    elif not rows:
        status = "blocked_missing_candidate_rows"
    elif blocked_count:
        status = "blocked_internal_score_candidate_inputs"
    else:
        status = "internal_score_candidates_ready_for_review"
    first_open = next(
        (row for row in rows if row.get("score_status") != "internal_score_candidates_ready_for_review"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_historical_seed_internal_score_candidates",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "internal_score_candidate_status": status,
        "calibration_ledger_json": _artifact(args.calibration_ledger_json),
        "score_dir": _artifact(args.score_dir),
        "seed_row_count": len(rows),
        "candidate_count": sum(_int(row.get("candidate_count")) for row in rows),
        "scored_candidate_count": sum(_int(row.get("scored_candidate_count")) for row in rows),
        "top5_scored_ready_count": sum(1 for row in rows if row.get("top5_scored_ready") is True),
        "selected_score_candidate_count": sum(
            1 for row in rows if not _text(row.get("selected_score_candidate")).startswith("REQUIRES")
        ),
        "blocked_candidate_input_count": blocked_count,
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide calibration candidate ledger rows",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "candidate_rows_by_target": candidate_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Internal Score Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- internal_score_candidate_status: `{summary['internal_score_candidate_status']}`",
        f"- seed rows/candidates/scored: `{summary['seed_row_count']}/{summary['candidate_count']}/{summary['scored_candidate_count']}`",
        f"- top5 scored/selected scores/blocked inputs: `{summary['top5_scored_ready_count']}/{summary['selected_score_candidate_count']}/{summary['blocked_candidate_input_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | candidates | scored | selected | best internal | top5 scored | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['score_status']}` | "
            f"{row['candidate_count']} | {row['scored_candidate_count']} | "
            f"`{row['selected_score_candidate']}` | `{row['best_internal_score_candidate']}` | "
            f"`{row['top5_scored_ready']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_candidate_rows` | 0 | 0 | - | - | - | provide ledger rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed internal score candidates.")
    parser.add_argument("--calibration-ledger-json", default=DEFAULT_CALIBRATION_LEDGER_JSON)
    parser.add_argument("--score-dir", default=DEFAULT_SCORE_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
