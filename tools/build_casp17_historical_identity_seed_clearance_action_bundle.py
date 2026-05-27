#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WORKORDER_JSON = "runs/casp17_historical_identity_seed_clearance_workorder_current.json"
DEFAULT_OUT_DIR = "casp17/historical_identity_seed_clearance_action_bundle"
DEFAULT_OUT_JSON = "casp17/casp17_historical_identity_seed_clearance_action_bundle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_identity_seed_clearance_action_bundle_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_IDENTITY_SEED_CLEARANCE_ACTION_BUNDLE.md"

ACTION_COLUMNS = [
    "action_rank",
    "seed_rank",
    "batch_slot",
    "target_id",
    "scope",
    "lane",
    "action_status",
    "target_bundle_folder",
    "action_folder",
    "action_md",
    "request_md",
    "operator_clearance_csv",
    "required_field",
    "blockers",
    "recommended_action",
    "unlocks",
    "verification_command",
    "prediction_pdb",
    "native_pdb",
]
PHASES = [
    ("identity", "identity_status", "target_id/benchmark_id/scope", "repair identity fields"),
    ("core_files", "core_files_status", "prediction_pdb/native_pdb", "provide distinct local prediction/native PDBs"),
    (
        "no_leak_provenance",
        "no_leak_provenance_status",
        "no_leak_evidence_ref/provenance_controls",
        "complete no-leak evidence, dates, and leakage controls",
    ),
    (
        "calibration",
        "calibration_status",
        "selected/best ranks and metric values",
        "enter model selection and native-metric calibration values",
    ),
    ("ablation", "ablation_status", "ablation_manifest_ref", "provide a local ablation manifest reference"),
]
REQUEST_FILENAMES = {
    "identity": "identity_request.md",
    "core_files": "core_file_request.md",
    "no_leak_provenance": "no_leak_evidence_request.md",
    "calibration": "calibration_request.md",
    "ablation": "ablation_request.md",
}
CLAIM_BOUNDARY = (
    "Local CASP17 historical seed-clearance action bundle only. It materializes open seed-clearance phases into "
    "per-seed request folders for operator work. Request files are templates and are intentionally not no-leak "
    "evidence. It does not fill operator clearance, certify chronology, fetch native structures, score native "
    "accuracy, mutate competitive-floor identity intake, run predictors, or submit to CASP."
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
        return int(float(str(value).strip()))
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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACTION_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _slug(value: str, fallback: str = "seed") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug or fallback


def _file_fingerprint(path_like: str) -> str:
    text = _text(path_like)
    if not text:
        return "missing"
    path = _resolve(text)
    if not path.is_file():
        return "missing"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"size={path.stat().st_size};sha256_16={digest}"


def _operator_rows_by_target(operator_csv: str) -> dict[str, dict[str, str]]:
    return {_text(row.get("target_id")).upper(): row for row in _read_csv(operator_csv)}


def _open_phase_actions(report_row: dict[str, Any]) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    for lane, status_key, required_field, recommended_action in PHASES:
        if _text(report_row.get(status_key)) != "ready":
            actions.append((lane, required_field, recommended_action))
    return actions


def _request_text(action: dict[str, Any]) -> str:
    lane = _text(action.get("lane"))
    target_id = _text(action.get("target_id"))
    prediction_pdb = _text(action.get("prediction_pdb"))
    native_pdb = _text(action.get("native_pdb"))
    common = [
        f"- target_id: `{target_id}`",
        f"- scope: `{_text(action.get('scope'))}`",
        f"- prediction_pdb: `{prediction_pdb or '-'}`",
        f"- prediction_fingerprint: `{_file_fingerprint(prediction_pdb)}`",
        f"- native_pdb: `{native_pdb or '-'}`",
        f"- native_fingerprint: `{_file_fingerprint(native_pdb)}`",
        f"- operator_clearance_csv: `{_text(action.get('operator_clearance_csv'))}`",
        f"- blockers: `{_text(action.get('blockers')) or '-'}`",
        "",
    ]
    if lane == "no_leak_provenance":
        return "\n".join(
            [
                f"# {target_id} No-Leak Provenance Request",
                "",
                "CLEARANCE_EVIDENCE_STATUS: request_template",
                "",
                "This file is an operator request template, not completed no-leak evidence.",
                *common,
                "Required operator work:",
                "- create a separate completed evidence file that names this target_id",
                "- set leakage_clearance/operator_clearance only after review is complete",
                "- fill prediction_created_at and native_release_date with ISO dates",
                "- confirm prediction_generated_before_native_release=true",
                "- confirm public_template_or_native_used_for_prediction=false",
                "- confirm other_team_model_used=false",
                "- confirm post_release_information_used=false",
                "- confirm current_casp17_target=false",
                "",
            ]
        )
    if lane == "calibration":
        return "\n".join(
            [
                f"# {target_id} Calibration Request",
                "",
                "This request keeps model1 and best-of-5 calibration explicit before promotion.",
                *common,
                "Required operator work:",
                "- fill selected_model_rank and best_model_rank with values from 1 to 5",
                "- fill selected_native_metric and best_native_metric after no-leak native scoring",
                "- fill selected_score and best_score from the internal ranking surface",
                "- keep selected_native_metric <= best_native_metric",
                "",
            ]
        )
    if lane == "ablation":
        return "\n".join(
            [
                f"# {target_id} Ablation Manifest Request",
                "",
                "This request records the ablation evidence needed before seed promotion.",
                *common,
                "Required operator work:",
                "- provide a local ablation_manifest_ref file",
                "- include which recursive/refinement/model-selection layers were present",
                "- include enough rows to reproduce selected-vs-best comparison context",
                "",
            ]
        )
    if lane == "core_files":
        return "\n".join(
            [
                f"# {target_id} Core File Request",
                "",
                "This request covers distinct local prediction/native PDB requirements.",
                *common,
                "Required operator work:",
                "- provide readable local prediction and native PDB files",
                "- ensure the files are distinct and contain valid ATOM coordinates",
                "",
            ]
        )
    return "\n".join(
        [
            f"# {target_id} Identity Request",
            "",
            "This request covers benchmark_id, target_id, and scope fields.",
            *common,
            "Required operator work:",
            "- keep benchmark_id and target_id stable",
            "- keep scope as monomer or complex",
            "- do not use current/open CASP17 target identities as historical benchmarks",
            "",
        ]
    )


def _write_action_files(out_dir: Path, action: dict[str, Any]) -> dict[str, str]:
    target = _slug(_text(action.get("target_id")), fallback=f"seed_{action.get('batch_slot')}")
    target_folder = out_dir / f"{int(action['batch_slot']):02d}_{target}"
    action_folder = target_folder / f"action_{int(action['action_rank']):03d}_{_slug(_text(action.get('lane')))}"
    action_folder.mkdir(parents=True, exist_ok=True)
    request_md = action_folder / REQUEST_FILENAMES.get(_text(action.get("lane")), "request.md")
    request_md.write_text(_request_text(action), encoding="utf-8")
    action_md = action_folder / "ACTION.md"
    action_md.write_text(
        "\n".join(
            [
                f"# {_text(action.get('target_id'))} {_text(action.get('lane'))} Action",
                "",
                f"- action_rank: `{action.get('action_rank')}`",
                f"- action_status: `{_text(action.get('action_status'))}`",
                f"- required_field: `{_text(action.get('required_field'))}`",
                f"- blockers: `{_text(action.get('blockers')) or '-'}`",
                f"- recommended_action: {_text(action.get('recommended_action'))}",
                f"- unlocks: `{_text(action.get('unlocks'))}`",
                f"- verification_command: `{_text(action.get('verification_command'))}`",
                f"- request_md: `{_artifact(request_md)}`",
                "",
                "## Claim Boundary",
                "",
                CLAIM_BOUNDARY,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "target_bundle_folder": _artifact(target_folder),
        "action_folder": _artifact(action_folder),
        "action_md": _artifact(action_md),
        "request_md": _artifact(request_md),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    workorder_summary = _summary(workorder_payload)
    operator_csv = _text(workorder_summary.get("operator_clearance_csv"))
    operator_by_target = _operator_rows_by_target(operator_csv)
    out_dir = _resolve(args.out_dir)
    actions: list[dict[str, Any]] = []
    action_rank = 1
    for report_row in _rows(workorder_payload):
        target_id = _text(report_row.get("target_id")).upper()
        operator_row = operator_by_target.get(target_id, {})
        for lane, required_field, recommended_action in _open_phase_actions(report_row):
            action = {
                "action_rank": action_rank,
                "seed_rank": _int(report_row.get("seed_rank")),
                "batch_slot": _int(report_row.get("batch_slot")),
                "target_id": target_id,
                "scope": _text(report_row.get("scope")),
                "lane": lane,
                "action_status": "open",
                "operator_clearance_csv": operator_csv,
                "required_field": required_field,
                "blockers": _text(report_row.get("blockers")),
                "recommended_action": recommended_action,
                "unlocks": "ready_for_cleared_seed_manifest",
                "verification_command": "python3 tools/build_casp17_historical_identity_seed_clearance_workorder.py",
                "prediction_pdb": _text(operator_row.get("prediction_pdb")),
                "native_pdb": _text(operator_row.get("native_pdb")),
            }
            action.update(_write_action_files(out_dir, action))
            actions.append(action)
            action_rank += 1
    lane_counts = {lane: sum(1 for action in actions if _text(action.get("lane")) == lane) for lane, *_ in PHASES}
    first_open = actions[0] if actions else {}
    open_count = sum(1 for action in actions if _text(action.get("action_status")) == "open")
    target_count = len({action["target_id"] for action in actions if action.get("target_id")})
    action_folder_count = len({action["action_folder"] for action in actions if action.get("action_folder")})
    target_folder_count = len({action["target_bundle_folder"] for action in actions if action.get("target_bundle_folder")})
    bundle_file_count = sum(1 for action in actions if action.get("action_md")) + sum(
        1 for action in actions if action.get("request_md")
    )
    status = "open_actions" if open_count else "ready"
    if not _rows(workorder_payload):
        status = "missing_workorder_rows"
    summary = {
        "packet_type": "casp17_historical_identity_seed_clearance_action_bundle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "seed_clearance_action_bundle_status": status,
        "workorder_json": _artifact(args.workorder_json),
        "out_dir": _artifact(args.out_dir),
        "operator_clearance_csv": operator_csv,
        "target_count": target_count,
        "action_count": len(actions),
        "open_action_count": open_count,
        "target_folder_count": target_folder_count,
        "action_folder_count": action_folder_count,
        "bundle_file_count": bundle_file_count,
        "identity_action_count": lane_counts["identity"],
        "core_file_action_count": lane_counts["core_files"],
        "no_leak_action_count": lane_counts["no_leak_provenance"],
        "calibration_action_count": lane_counts["calibration"],
        "ablation_action_count": lane_counts["ablation"],
        "first_open_action_md": _text(first_open.get("action_md")),
        "first_open_request_md": _text(first_open.get("request_md")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": actions}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Identity Seed Clearance Action Bundle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- seed_clearance_action_bundle_status: `{summary['seed_clearance_action_bundle_status']}`",
        f"- targets/actions/open: `{summary['target_count']}/{summary['action_count']}/{summary['open_action_count']}`",
        f"- folders/files: `{summary['action_folder_count']}/{summary['bundle_file_count']}`",
        f"- lanes identity/core/no-leak/calibration/ablation: `{summary['identity_action_count']}/{summary['core_file_action_count']}/{summary['no_leak_action_count']}/{summary['calibration_action_count']}/{summary['ablation_action_count']}`",
        f"- operator clearance csv: `{summary['operator_clearance_csv'] or '-'}`",
        f"- first action: `{summary['first_open_action_md'] or '-'}`",
        f"- first request: `{summary['first_open_request_md'] or '-'}`",
        "",
        "## Actions",
        "",
        "| rank | target | lane | status | action | request | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for action in payload["rows"]:
        lines.append(
            f"| {action['action_rank']} | `{action['target_id']}` | `{action['lane']}` | "
            f"`{action['action_status']}` | `{action['action_md']}` | `{action['request_md']}` | "
            f"`{action['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `missing_workorder_rows` | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed clearance action bundle.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
