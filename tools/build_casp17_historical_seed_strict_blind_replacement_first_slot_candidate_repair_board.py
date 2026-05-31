#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CANDIDATE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_REPAIR_DIR = "casp17/historical_seed_strict_blind_replacement_first_slot_candidate_repair_board"
DEFAULT_OUT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board_current.csv"
)
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_CANDIDATE_REPAIR_BOARD.md"

BLOCKER_POLICY = {
    "prediction_not_before_native": {
        "class": "chronology",
        "priority": 1,
        "field": "prediction_created_at",
        "target_dropzone_field": "prediction_pdb",
        "next_action": "attach a prediction artifact created before the authoritative native release date",
    },
    "no_leak_not_ready": {
        "class": "no_leak",
        "priority": 2,
        "field": "no_leak_evidence_ref",
        "target_dropzone_field": "no_leak_evidence_ref",
        "next_action": "complete independent no-leak evidence, negative controls, and operator clearance",
    },
    "ablation_not_ready": {
        "class": "ablation",
        "priority": 3,
        "field": "ablation_manifest_ref",
        "target_dropzone_field": "ablation_manifest_ref",
        "next_action": "attach same-run ablation layer evidence; deterministic top5 decoys remain review-only",
    },
    "calibration_not_ready": {
        "class": "calibration",
        "priority": 4,
        "field": "calibration_values_ref",
        "target_dropzone_field": "calibration_values_ref",
        "next_action": "operator-fill calibration values after no-leak provenance clearance",
    },
    "strict_blind_not_eligible": {
        "class": "eligibility",
        "priority": 5,
        "field": "target_identity_non_current_historical",
        "target_dropzone_field": "target_identity_non_current_historical",
        "next_action": "promote only after chronology, no-leak, ablation, and calibration blockers are cleared",
    },
    "native_authority_missing": {
        "class": "native_authority",
        "priority": 1,
        "field": "native_authority_ref",
        "target_dropzone_field": "native_authority_ref",
        "next_action": "attach authoritative native/source reference for the candidate native structure",
    },
    "prediction_missing": {
        "class": "prediction_file",
        "priority": 1,
        "field": "prediction_pdb",
        "target_dropzone_field": "prediction_pdb",
        "next_action": "attach local prediction PDB for this candidate",
    },
    "native_missing": {
        "class": "native_file",
        "priority": 1,
        "field": "native_pdb",
        "target_dropzone_field": "native_pdb",
        "next_action": "attach authoritative native PDB for this candidate",
    },
}
ROW_COLUMNS = [
    "action_id",
    "candidate_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "repair_class",
    "blocker",
    "priority",
    "field_name",
    "target_dropzone_field",
    "action_status",
    "candidate_status",
    "candidate_folder",
    "repair_folder",
    "evidence_pointer",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot candidate repair board only. It decomposes fail-closed local-candidate blockers into "
    "operator repair actions for chronology, provenance, ablation, calibration, and missing source files. It does "
    "not create evidence, approve candidates, mutate intake CSVs, compute CASP metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _repair_folder(repair_dir: str | Path, candidate_rank: int, target_id: str, blocker: str) -> Path:
    safe_target = target_id.lower().replace("/", "_").replace(" ", "_")
    safe_blocker = blocker.lower().replace("/", "_").replace(" ", "_")
    return _resolve(repair_dir) / f"{candidate_rank:02d}_{safe_target}" / safe_blocker


def _evidence_pointer(row: dict[str, Any], blocker: str) -> str:
    if blocker == "prediction_missing":
        return _text(row.get("prediction_pdb"))
    if blocker == "native_missing":
        return _text(row.get("native_pdb"))
    if blocker == "native_authority_missing":
        return _text(row.get("native_authority_ref"))
    if blocker == "no_leak_not_ready":
        return _text(row.get("no_leak_dossier"))
    if blocker == "ablation_not_ready":
        return _text(row.get("ablation_manifest_ref"))
    if blocker == "calibration_not_ready":
        return _text(row.get("calibration_values_ref"))
    if blocker == "prediction_not_before_native":
        return f"prediction_created_at={_text(row.get('prediction_created_at'))};native_release_date={_text(row.get('native_release_date'))}"
    return _text(row.get("candidate_folder"))


def _action_status(blocker: str) -> str:
    if blocker == "strict_blind_not_eligible":
        return "blocked_waiting_on_primary_repairs"
    return "open_repair_action"


def _repair_rows(candidate_rows: list[dict[str, Any]], repair_dir: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    action_index = 1
    for candidate in candidate_rows:
        blockers = [_text(part) for part in _text(candidate.get("blockers")).split(",") if _text(part)]
        for blocker in blockers:
            policy = BLOCKER_POLICY.get(blocker, {
                "class": "unknown",
                "priority": 9,
                "field": "",
                "target_dropzone_field": "",
                "next_action": "inspect candidate blocker and add a repair policy",
            })
            folder = _repair_folder(repair_dir, _int(candidate.get("candidate_rank")), _text(candidate.get("target_id")), blocker)
            rows.append(
                {
                    "action_id": f"first_slot_repair_{action_index:03d}",
                    "candidate_rank": _int(candidate.get("candidate_rank")),
                    "target_id": _text(candidate.get("target_id")),
                    "benchmark_id": _text(candidate.get("benchmark_id")),
                    "scope": _text(candidate.get("scope")),
                    "repair_class": policy["class"],
                    "blocker": blocker,
                    "priority": policy["priority"],
                    "field_name": policy["field"],
                    "target_dropzone_field": policy["target_dropzone_field"],
                    "action_status": _action_status(blocker),
                    "candidate_status": _text(candidate.get("candidate_status")),
                    "candidate_folder": _text(candidate.get("candidate_folder")),
                    "repair_folder": _artifact(folder),
                    "evidence_pointer": _evidence_pointer(candidate, blocker),
                    "next_action": policy["next_action"],
                }
            )
            action_index += 1
    rows.sort(key=lambda row: (int(row["priority"]), int(row["candidate_rank"]), row["blocker"]))
    for index, row in enumerate(rows, start=1):
        row["action_id"] = f"first_slot_repair_{index:03d}"
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_payload = _read_json(args.candidate_board_json)
    input_blockers = []
    if not _resolve(args.candidate_board_json).exists():
        input_blockers.append("first_slot_local_candidate_board_json_missing")
    rows = _repair_rows(_rows(candidate_payload), args.repair_dir)
    summary = _build_summary(args, rows, input_blockers, candidate_payload)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    candidate_payload: dict[str, Any],
) -> dict[str, Any]:
    open_rows = [row for row in rows if row["action_status"] == "open_repair_action"]
    blocked_rows = [row for row in rows if row["action_status"].startswith("blocked")]
    first_open = open_rows[0] if open_rows else (blocked_rows[0] if blocked_rows else {})
    classes = sorted({row["repair_class"] for row in rows if row.get("repair_class")})
    class_counts = {name: sum(1 for row in rows if row["repair_class"] == name) for name in classes}
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_first_slot_candidate_repair_board_status": _overall_status(rows, input_blockers),
        "candidate_board_json": _artifact(args.candidate_board_json),
        "candidate_board_status": _text(
            _summary(candidate_payload).get("strict_blind_replacement_first_slot_local_candidate_board_status")
        ),
        "required_benchmark_id": _text(_summary(candidate_payload).get("required_benchmark_id")),
        "candidate_count": _int(_summary(candidate_payload).get("candidate_count")),
        "action_count": len(rows),
        "open_repair_action_count": len(open_rows),
        "blocked_action_count": len(blocked_rows),
        "chronology_action_count": class_counts.get("chronology", 0),
        "no_leak_action_count": class_counts.get("no_leak", 0),
        "ablation_action_count": class_counts.get("ablation", 0),
        "calibration_action_count": class_counts.get("calibration", 0),
        "native_authority_action_count": class_counts.get("native_authority", 0),
        "prediction_file_action_count": class_counts.get("prediction_file", 0),
        "native_file_action_count": class_counts.get("native_file", 0),
        "eligibility_action_count": class_counts.get("eligibility", 0),
        "first_open_action_id": _text(first_open.get("action_id")),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_repair_class": _text(first_open.get("repair_class")),
        "first_open_blocker": _text(first_open.get("blocker")),
        "first_open_status": _text(first_open.get("action_status")),
        "first_next_action": _text(first_open.get("next_action")) or "provide first-slot candidate repair inputs",
        "repair_dir": _artifact(args.repair_dir),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "first_slot_candidate_repair_clear"
    if any(row["action_status"] == "open_repair_action" for row in rows):
        return "awaiting_first_slot_candidate_repairs"
    return "blocked_first_slot_candidate_repair_dependencies"


def _write_repair_md(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} {row['blocker']} Repair",
        "",
        f"- action: `{row['action_id']}`",
        f"- status: `{row['action_status']}`",
        f"- repair class: `{row['repair_class']}`",
        f"- candidate: `{row['target_id']}` `{row['benchmark_id']}`",
        f"- field/dropzone field: `{row['field_name'] or '-'}` `{row['target_dropzone_field'] or '-'}`",
        f"- evidence pointer: `{row['evidence_pointer'] or '-'}`",
        f"- next action: {row['next_action']}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["repair_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "REPAIR_ACTION.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "repair_action.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement First Slot Candidate Repair Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_first_slot_candidate_repair_board_status']}`",
        f"- required benchmark: `{summary['required_benchmark_id'] or '-'}`",
        f"- actions open/blocked/total: `{summary['open_repair_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}`",
        f"- repair classes chronology/no-leak/ablation/calibration: `{summary['chronology_action_count']}/{summary['no_leak_action_count']}/{summary['ablation_action_count']}/{summary['calibration_action_count']}`",
        f"- source-file/native-authority/eligibility: `{summary['prediction_file_action_count']}/{summary['native_file_action_count']}/{summary['native_authority_action_count']}/{summary['eligibility_action_count']}`",
        f"- first open: `{summary['first_open_action_id'] or '-'}` `{summary['first_open_target_id'] or '-'}` `{summary['first_open_repair_class'] or '-'}` `{summary['first_open_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Repair Actions",
        "",
        "| action | target | class | blocker | priority | status | field | next action |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"][:120]:
        lines.append(
            f"| `{row['action_id']}` | `{row['target_id']}` | `{row['repair_class']}` | "
            f"`{row['blocker']}` | {row['priority']} | `{row['action_status']}` | "
            f"`{row['field_name'] or '-'}` | {row['next_action']} |"
        )
    if len(payload["rows"]) > 120:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | `{len(payload['rows']) - 120} more actions in CSV` |")
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `clear` | - | rerun candidate board |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_repair_md(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot candidate repair action board.")
    parser.add_argument("--candidate-board-json", default=DEFAULT_CANDIDATE_BOARD_JSON)
    parser.add_argument("--repair-dir", default=DEFAULT_REPAIR_DIR)
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
