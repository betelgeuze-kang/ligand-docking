#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTAKE_CSV = "config/casp17_target_intake_template.csv"
DEFAULT_OUT_JSON = "runs/casp17_submission_gate_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_submission_gate_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_submission_gate_packet_current.md"

DEFAULT_LOCAL_DELIVERY_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_PDE_LOCAL_MIN_JSON = "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json"
DEFAULT_SELECTED_ALLATOM_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"

ALLOWED_LANES = {
    "organic_ligand_protein_complexes": {
        "label": "Organic Ligand-Protein Complexes",
        "rank": 1,
        "allowed_formats": {"TS", "LG"},
        "requires_ligand_checks": True,
    },
    "difficult_protein_complexes": {
        "label": "Difficult Protein Structures and Complexes",
        "rank": 2,
        "allowed_formats": {"TS"},
        "requires_ligand_checks": False,
    },
    "accuracy_estimation": {
        "label": "Accuracy Estimation",
        "rank": 3,
        "allowed_formats": {"QA"},
        "requires_ligand_checks": False,
    },
}

PASS_VALUES = {"pass", "passed", "green", "ready", "ok", "true", "1", "complete"}
FAIL_VALUES = {"fail", "failed", "red", "blocked", "false", "0", "incomplete", "missing"}


def _resolve(path_like: str | Path, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _artifact(path_like: str | Path, root: Path) -> str:
    path = _resolve(path_like, root).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status(value: Any) -> str:
    text = _text(value).lower()
    if text in PASS_VALUES:
        return "pass"
    if text in FAIL_VALUES:
        return "fail"
    if not text:
        return "missing"
    return "unknown"


def _boolish(value: Any) -> bool | None:
    text = _text(value).lower()
    if isinstance(value, bool):
        return value
    if text in PASS_VALUES:
        return True
    if text in FAIL_VALUES:
        return False
    return None


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path, root: Path) -> dict[str, Any]:
    path = _resolve(path_like, root)
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


def _read_csv(path_like: str | Path, root: Path) -> list[dict[str, str]]:
    path = _resolve(path_like, root)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any], root: Path) -> None:
    path = _resolve(path_like, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], root: Path) -> None:
    path = _resolve(path_like, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "lane",
        "submission_format",
        "deadline_class",
        "submission_decision",
        "blocker_count",
        "blockers",
        "prediction_file_path",
        "sequence_path",
        "validation_json_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _source_artifact(label: str, path_like: str | Path, root: Path) -> dict[str, Any]:
    path = _resolve(path_like, root)
    artifact = {
        "label": label,
        "path": _artifact(path, root),
        "present": path.exists(),
        "status": "missing",
        "mtime_ns": 0,
        "json_valid": False,
    }
    if not path.exists():
        return artifact
    try:
        artifact["mtime_ns"] = path.stat().st_mtime_ns
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        artifact["status"] = "invalid_json"
        return artifact
    if not isinstance(payload, dict):
        artifact["status"] = "invalid_json"
        return artifact
    artifact["status"] = "present"
    artifact["json_valid"] = True
    return artifact


def _framework_gate(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], list[str]]:
    verdict_payload = _read_json(args.local_delivery_verdict_json, root)
    queue_payload = _read_json(args.local_engine_queue_json, root)
    accuracy_payload = _read_json(args.accuracy_scorecard_json, root)
    pde_payload = _read_json(args.pde_local_min_json, root)
    selected_payload = _read_json(args.selected_allatom_json, root)

    verdict_summary = _summary(verdict_payload)
    queue_summary = _summary(queue_payload)
    accuracy_summary = _summary(accuracy_payload)
    pde_summary = _summary(pde_payload)
    selected_summary = _summary(selected_payload)

    blockers: list[str] = []
    if _boolish(verdict_summary.get("delivery_ready")) is not True:
        blockers.append("local_delivery_verdict_not_ready")
    if _boolish(queue_summary.get("queue_clear")) is not True and _int(queue_summary.get("blocked_count")) > 0:
        blockers.append("local_engine_queue_not_clear")
    if _text(accuracy_summary.get("status")).lower() not in {"green", "pass", "ready"}:
        blockers.append("accuracy_parity_scorecard_not_green")
    if _int(pde_summary.get("parameterization_ready_count")) < 7:
        blockers.append("pde_atomized_parameterization_not_7_of_7")
    if _int(pde_summary.get("protein_local_minimization_ready_count")) < 7:
        blockers.append("pde_atomized_local_minimization_not_7_of_7")
    if _int(selected_summary.get("hard_block_count")) > 0:
        blockers.append("selected_allatom_hard_blocks_present")

    framework = {
        "framework_gate_pass": not blockers,
        "framework_blockers": blockers,
        "registration_class_recommendation": "regular_prediction_group",
        "server_registration_ready": False,
        "server_registration_reason": "CASP17 server submissions require a 72-hour fully automated path; keep server registration blocked until that path has its own green gate.",
        "primary_lane": "organic_ligand_protein_complexes",
        "secondary_lane": "difficult_protein_complexes",
        "support_lane": "accuracy_estimation",
        "submission_policy": "fail_closed_internal_gate",
        "source_metrics": {
            "local_delivery_ready": verdict_summary.get("delivery_ready"),
            "local_delivery_verdict": verdict_summary.get("verdict"),
            "local_engine_queue_clear": queue_summary.get("queue_clear"),
            "local_engine_blocked_count": queue_summary.get("blocked_count"),
            "accuracy_parity_status": accuracy_summary.get("status"),
            "accuracy_parity_pass_row_count": accuracy_summary.get("pass_row_count"),
            "pde_parameterization_ready_count": pde_summary.get("parameterization_ready_count"),
            "pde_local_minimization_ready_count": pde_summary.get("protein_local_minimization_ready_count"),
            "selected_allatom_hard_block_count": selected_summary.get("hard_block_count"),
        },
    }
    return framework, blockers


def _validation_overlay(row: dict[str, str], root: Path) -> dict[str, Any]:
    artifact_keys = [
        ("validation", "validation_json_path"),
        ("geometry_validation", "geometry_validation_json_path"),
        ("confidence_validation", "confidence_validation_json_path"),
        ("internal_scorecard", "internal_scorecard_json_path"),
    ]
    merged_summary: dict[str, Any] = {}
    hard_blockers: list[str] = []
    present = False
    primary_validation_path = _text(row.get("validation_json_path"))
    if not any(_text(row.get(key)) for _label, key in artifact_keys):
        return {"present": False, "summary": {}, "hard_blockers": []}
    for label, key in artifact_keys:
        path_value = _text(row.get(key))
        if not path_value:
            continue
        payload = _read_json(path_value, root)
        if not payload:
            hard_blockers.append(f"{label}_artifact_missing_or_invalid")
            continue
        present = True
        summary = _summary(payload)
        if label == "validation" or not primary_validation_path:
            merged_summary.update(summary)
        target_id = _text(row.get("target_id")).upper()
        validation_target_id = _text(summary.get("target_id")).upper()
        blockers = payload.get("blockers")
        if not isinstance(blockers, list):
            blockers = summary.get("blockers")
        if not isinstance(blockers, list):
            blockers = []
        for blocker in blockers:
            if isinstance(blocker, dict):
                severity = _text(blocker.get("severity")).lower()
                code = _text(blocker.get("code") or blocker.get("id") or blocker.get("reason"))
                if severity in {"", "hard", "blocker"}:
                    hard_blockers.append(f"{label}:{code or 'hard_blocker'}")
            elif _text(blocker):
                hard_blockers.append(f"{label}:{_text(blocker)}")
        if validation_target_id and validation_target_id != target_id:
            hard_blockers.append(f"{label}:target_id_mismatch")
    return {"present": present, "summary": merged_summary, "hard_blockers": hard_blockers}


def _merged_status(row: dict[str, str], overlay: dict[str, Any], key: str) -> str:
    row_status = _status(row.get(key))
    if row_status != "missing":
        return row_status
    summary = overlay.get("summary", {})
    if isinstance(summary, dict):
        return _status(summary.get(key))
    return "missing"


def _target_blockers(row: dict[str, str], framework_gate_pass: bool, root: Path) -> tuple[str, list[str]]:
    blockers: list[str] = []
    overlay = _validation_overlay(row, root)

    target_id = _text(row.get("target_id"))
    lane = _text(row.get("lane"))
    submission_format = _text(row.get("submission_format")).upper()
    deadline_class = _text(row.get("deadline_class")).lower()
    prediction_path = _text(row.get("prediction_file_path"))
    sequence_path = _text(row.get("sequence_path"))

    if not framework_gate_pass:
        blockers.append("framework_gate_not_green")
    if not target_id:
        blockers.append("missing_target_id")
    if lane not in ALLOWED_LANES:
        blockers.append("unsupported_lane")
    else:
        allowed_formats = ALLOWED_LANES[lane]["allowed_formats"]
        if submission_format not in allowed_formats:
            blockers.append("submission_format_not_allowed_for_lane")
    if deadline_class != "regular":
        blockers.append("deadline_class_not_regular")
    if not prediction_path:
        blockers.append("missing_prediction_file_path")
    elif not _resolve(prediction_path, root).exists():
        blockers.append("prediction_file_missing")
    if not sequence_path:
        blockers.append("missing_sequence_path")
    elif not _resolve(sequence_path, root).exists():
        blockers.append("sequence_file_missing")

    for key in (
        "format_check_status",
        "model_generation_status",
        "geometry_sanity_status",
        "confidence_calibration_status",
        "internal_scorecard_status",
    ):
        if _merged_status(row, overlay, key) != "pass":
            blockers.append(f"{key}_not_pass")

    if lane in ALLOWED_LANES and ALLOWED_LANES[lane]["requires_ligand_checks"]:
        for key in ("parameterization_status", "protein_local_minimization_status"):
            if _merged_status(row, overlay, key) != "pass":
                blockers.append(f"{key}_not_pass")
        if not _text(row.get("ligand_info_path")):
            blockers.append("missing_ligand_info_path")
        elif not _resolve(_text(row.get("ligand_info_path")), root).exists():
            blockers.append("ligand_info_file_missing")

    blockers.extend(f"validation:{blocker}" for blocker in overlay["hard_blockers"])
    unique_blockers = list(dict.fromkeys(blockers))
    decision = "submission_go" if not unique_blockers else "submission_no_go"
    return decision, unique_blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    rows = [row for row in _read_csv(args.intake_csv, root) if any(_text(value) for value in row.values())]
    framework, framework_blockers = _framework_gate(args, root)

    target_rows: list[dict[str, Any]] = []
    for row in rows:
        decision, blockers = _target_blockers(row, bool(framework["framework_gate_pass"]), root)
        target_rows.append(
            {
                "target_id": _text(row.get("target_id")),
                "target_name": _text(row.get("target_name")),
                "lane": _text(row.get("lane")),
                "submission_format": _text(row.get("submission_format")).upper(),
                "deadline_class": _text(row.get("deadline_class")).lower(),
                "prediction_file_path": _text(row.get("prediction_file_path")),
                "sequence_path": _text(row.get("sequence_path")),
                "validation_json_path": _text(row.get("validation_json_path")),
                "submission_decision": decision,
                "blocker_count": len(blockers),
                "blockers": ";".join(blockers),
                "notes": _text(row.get("notes")),
            }
        )

    source_artifacts = [
        _source_artifact("local_delivery_verdict", args.local_delivery_verdict_json, root),
        _source_artifact("local_engine_queue", args.local_engine_queue_json, root),
        _source_artifact("accuracy_parity_scorecard", args.accuracy_scorecard_json, root),
        _source_artifact("pde_atomized_parameterization_minimization", args.pde_local_min_json, root),
        _source_artifact("selected_allatom_gate_burndown", args.selected_allatom_json, root),
    ]
    target_go_count = sum(row["submission_decision"] == "submission_go" for row in target_rows)
    lane_counts = {lane: 0 for lane in ALLOWED_LANES}
    for row in target_rows:
        lane = row["lane"]
        if lane in lane_counts:
            lane_counts[lane] += 1

    summary = {
        "packet_type": "casp17_submission_gate_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        **framework,
        "intake_csv": _artifact(args.intake_csv, root),
        "target_row_count": len(target_rows),
        "submission_go_count": target_go_count,
        "submission_no_go_count": len(target_rows) - target_go_count,
        "lane_target_counts": lane_counts,
        "registration_action": (
            "user_register_regular_group_now_submission_gated"
            if not framework_blockers
            else "hold_registration_until_framework_blockers_reviewed"
        ),
        "claim_boundary": "CASP17 participation readiness only; no CASP17 performance, ranking, or commercial-parity claim before official assessment.",
    }
    return {"summary": summary, "target_rows": target_rows, "source_artifacts": source_artifacts}


def _write_md(path_like: str | Path, payload: dict[str, Any], root: Path) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Submission Gate Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- framework gate: `{summary['framework_gate_pass']}`",
        f"- registration action: `{summary['registration_action']}`",
        f"- recommended class: `{summary['registration_class_recommendation']}`",
        f"- server registration ready: `{summary['server_registration_ready']}`",
        f"- primary lane: `{summary['primary_lane']}`",
        f"- submission policy: `{summary['submission_policy']}`",
        f"- target rows: `{summary['target_row_count']}`",
        f"- submission go/no-go: `{summary['submission_go_count']}/{summary['submission_no_go_count']}`",
        "",
        "## Framework Blockers",
        "",
    ]
    if summary["framework_blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in summary["framework_blockers"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Source Metrics",
            "",
            "| metric | value |",
            "| --- | --- |",
        ]
    )
    for key, value in summary["source_metrics"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Target Decisions",
            "",
            "| target | lane | format | deadline | decision | blockers |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["target_rows"]:
        blockers = row["blockers"] or "-"
        lines.append(
            f"| `{row['target_id']}` | `{row['lane']}` | `{row['submission_format']}` | "
            f"`{row['deadline_class']}` | `{row['submission_decision']}` | {blockers} |"
        )
    if not payload["target_rows"]:
        lines.append("| - | - | - | - | `no_target_rows_loaded` | intake template only |")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 regular-group submission go/no-go gate packet.")
    parser.add_argument("--root", default=str(ROOT), help="Repository root.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV, help="CASP17 target intake CSV.")
    parser.add_argument("--local-delivery-verdict-json", default=DEFAULT_LOCAL_DELIVERY_VERDICT_JSON)
    parser.add_argument("--local-engine-queue-json", default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON)
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--pde-local-min-json", default=DEFAULT_PDE_LOCAL_MIN_JSON)
    parser.add_argument("--selected-allatom-json", default=DEFAULT_SELECTED_ALLATOM_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    payload = build_payload(args)
    _write_json(args.out_json, payload, root)
    _write_csv(args.out_csv, payload["target_rows"], root)
    _write_md(args.out_md, payload, root)


if __name__ == "__main__":
    main()
