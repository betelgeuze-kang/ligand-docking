#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SEED_INVENTORY_JSON = "runs/casp17_historical_identity_seed_inventory_current.json"
DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_historical_identity_seed_clearance_workorder_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_identity_seed_clearance_workorder_current.csv"
DEFAULT_OUT_MD = "runs/CASP17_HISTORICAL_IDENTITY_SEED_CLEARANCE_WORKORDER.md"
DEFAULT_OUT_CLEARED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_cleared_current.csv"

CLEAR_VALUES = {"no_leak", "cleared", "ready_for_row_fill", "internal_no_leak", "true", "yes"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
URL_PREFIXES = ("http://", "https://")
BLOCKED_EVIDENCE_MARKERS = (
    "clearance_evidence_status: request_template",
    "evidence request template",
    "not a completed no-leak clearance",
)
OPERATOR_COLUMNS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
    "ablation_manifest_ref",
    "notes",
]
REPORT_COLUMNS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "clearance_status",
    "identity_status",
    "core_files_status",
    "no_leak_provenance_status",
    "calibration_status",
    "ablation_status",
    "blocking_field_count",
    "blockers",
    "next_action",
]
MANIFEST_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
]
CLAIM_BOUNDARY = (
    "Local CASP17 historical identity seed clearance workorder only. It creates and validates operator "
    "clearance rows for seed historical benchmark candidates, and emits a cleared manifest only for rows "
    "whose local files, no-leak provenance, chronology, calibration values, and ablation manifest reference "
    "are already complete. It does not clear no-leak provenance itself, fetch native structures, score native "
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


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(_text(value))
    except ValueError:
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames)
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _seed_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in _rows(payload) if _int(row.get("batch_slot")) > 0]


def _operator_template_row(seed: dict[str, Any]) -> dict[str, str]:
    return {
        "seed_rank": _text(seed.get("seed_rank")),
        "batch_slot": _text(seed.get("batch_slot")),
        "benchmark_id": _text(seed.get("benchmark_id")),
        "target_id": _text(seed.get("target_id")),
        "scope": _text(seed.get("scope")),
        "prediction_pdb": _text(seed.get("prediction_pdb")),
        "native_pdb": _text(seed.get("native_pdb")),
        "no_leak_evidence_ref": "",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "operator": "REQUIRED_OPERATOR_ID",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
        "ablation_manifest_ref": "REQUIRED_ABLATION_MANIFEST_REF",
        "notes": "operator must verify no-leak provenance before promotion",
    }


def _ensure_operator_clearance_csv(path_like: str | Path, seeds: list[dict[str, Any]], *, refresh: bool) -> str:
    path = _resolve(path_like)
    if path.exists() and not refresh:
        return "preserved"
    rows = [_operator_template_row(seed) for seed in seeds]
    _write_csv(path, rows, OPERATOR_COLUMNS)
    return "refreshed" if path.exists() and refresh else "created"


def _pdb_blockers(path_like: Any, *, role: str) -> list[str]:
    text = _text(path_like)
    if _contains_placeholder(text):
        return [f"{role}_pdb_required"]
    path = _resolve(text)
    if not path.exists():
        return [f"{role}_pdb_missing"]
    if not path.is_file():
        return [f"{role}_pdb_not_file"]
    try:
        atom_count = 0
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.startswith("ATOM"):
                    continue
                atom_count += 1
                try:
                    float(line[30:38])
                    float(line[38:46])
                    float(line[46:54])
                except ValueError:
                    parts = line.split()
                    float(parts[6])
                    float(parts[7])
                    float(parts[8])
    except (OSError, ValueError):
        return [f"{role}_pdb_invalid_or_unreadable"]
    if atom_count <= 0:
        return [f"{role}_pdb_has_no_protein_atoms"]
    return []


def _sha256(path_like: str | Path) -> str:
    return hashlib.sha256(_resolve(path_like).read_bytes()).hexdigest()


def _identity_blockers(row: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if _contains_placeholder(row.get("benchmark_id")):
        blockers.append("benchmark_id_required")
    if _contains_placeholder(row.get("target_id")):
        blockers.append("target_id_required")
    if _text(row.get("scope")).lower() not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    return blockers


def _core_file_blockers(row: dict[str, str]) -> list[str]:
    blockers = _pdb_blockers(row.get("prediction_pdb"), role="prediction")
    blockers.extend(_pdb_blockers(row.get("native_pdb"), role="native"))
    if not blockers:
        try:
            if _resolve(row["prediction_pdb"]).samefile(_resolve(row["native_pdb"])):
                blockers.append("prediction_native_same_path")
            elif _sha256(row["prediction_pdb"]) == _sha256(row["native_pdb"]):
                blockers.append("prediction_native_identical_file")
        except OSError:
            blockers.append("prediction_native_identity_check_failed")
    return blockers


def _evidence_blockers(row: dict[str, str]) -> list[str]:
    ref = _text(row.get("no_leak_evidence_ref"))
    target_id = _text(row.get("target_id"))
    if _contains_placeholder(ref):
        return ["no_leak_evidence_ref_required"]
    if ref.lower().startswith(URL_PREFIXES):
        return ["no_leak_evidence_ref_must_be_local_file"]
    path = _resolve(ref)
    if not path.exists():
        return ["no_leak_evidence_ref_missing"]
    if not path.is_file():
        return ["no_leak_evidence_ref_not_file"]
    try:
        content = path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return ["no_leak_evidence_ref_unreadable"]
    if any(marker in content for marker in BLOCKED_EVIDENCE_MARKERS):
        return ["no_leak_evidence_is_request_template"]
    if target_id and target_id.lower() not in content:
        return ["no_leak_evidence_ref_missing_target_id"]
    return []


def _provenance_blockers(row: dict[str, str]) -> list[str]:
    blockers = _evidence_blockers(row)
    if _text(row.get("leakage_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if _text(row.get("operator_clearance")).lower() not in CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    if _contains_placeholder(row.get("operator")):
        blockers.append("operator_required")
    prediction_created = _date_or_none(row.get("prediction_created_at"))
    native_release = _date_or_none(row.get("native_release_date"))
    if prediction_created is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_release is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_created is not None and native_release is not None and prediction_created >= native_release:
        blockers.append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    return blockers


def _rank_blocker(value: Any, column: str) -> str | None:
    rank = _int(value)
    if rank < 1 or rank > 5:
        return f"{column}_required_1_to_5"
    return None


def _calibration_blockers(row: dict[str, str]) -> list[str]:
    blockers = [
        blocker
        for blocker in (
            _rank_blocker(row.get("selected_model_rank"), "selected_model_rank"),
            _rank_blocker(row.get("best_model_rank"), "best_model_rank"),
        )
        if blocker
    ]
    selected_native = _float_or_none(row.get("selected_native_metric"))
    best_native = _float_or_none(row.get("best_native_metric"))
    selected_score = _float_or_none(row.get("selected_score"))
    best_score = _float_or_none(row.get("best_score"))
    if selected_native is None:
        blockers.append("selected_native_metric_required_numeric")
    if best_native is None:
        blockers.append("best_native_metric_required_numeric")
    if selected_native is not None and best_native is not None and selected_native > best_native:
        blockers.append("selected_native_metric_exceeds_oracle_metric")
    if selected_score is None:
        blockers.append("selected_score_required_numeric")
    if best_score is None:
        blockers.append("best_score_required_numeric")
    return blockers


def _ablation_blockers(row: dict[str, str]) -> list[str]:
    ref = _text(row.get("ablation_manifest_ref"))
    if _contains_placeholder(ref):
        return ["ablation_manifest_ref_required"]
    path = _resolve(ref)
    if not path.exists():
        return ["ablation_manifest_ref_missing"]
    if not path.is_file():
        return ["ablation_manifest_ref_not_file"]
    return []


def _phase_status(blockers: list[str], ready: str, blocked: str) -> str:
    return ready if not blockers else blocked


def _next_action(report_row: dict[str, Any]) -> str:
    if report_row["clearance_status"] == "ready_for_cleared_seed_manifest":
        return "review cleared seed manifest before feeding identity candidate intake"
    phase_actions = [
        ("identity_status", "repair benchmark/target identity fields"),
        ("core_files_status", "provide distinct local prediction/native PDB files"),
        ("no_leak_provenance_status", "fill operator no-leak evidence, chronology, and leakage controls"),
        ("calibration_status", "enter selected/best model ranks, native metrics, and internal scores"),
        ("ablation_status", "provide a local ablation manifest reference"),
    ]
    for key, action in phase_actions:
        if str(report_row.get(key, "")).startswith("awaiting"):
            return action
    return "review seed clearance row"


def _report_row(row: dict[str, str]) -> dict[str, Any]:
    identity = _identity_blockers(row)
    core = _core_file_blockers(row)
    provenance = _provenance_blockers(row)
    calibration = _calibration_blockers(row)
    ablation = _ablation_blockers(row)
    blockers = identity + core + provenance + calibration + ablation
    clearance_status = "ready_for_cleared_seed_manifest" if not blockers else "awaiting_seed_clearance"
    report = {
        "seed_rank": _int(row.get("seed_rank")),
        "batch_slot": _int(row.get("batch_slot")),
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")).upper(),
        "scope": _text(row.get("scope")).lower(),
        "clearance_status": clearance_status,
        "identity_status": _phase_status(identity, "ready", "awaiting_identity_fields"),
        "core_files_status": _phase_status(core, "ready", "awaiting_core_files"),
        "no_leak_provenance_status": _phase_status(provenance, "ready", "awaiting_no_leak_provenance"),
        "calibration_status": _phase_status(calibration, "ready", "awaiting_calibration_values"),
        "ablation_status": _phase_status(ablation, "ready", "awaiting_ablation_manifest"),
        "blocking_field_count": len(blockers),
        "blockers": ",".join(blockers),
        "next_action": "",
    }
    report["next_action"] = _next_action(report)
    return report


def _cleared_manifest_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")).upper(),
        "scope": _text(row.get("scope")).lower(),
        "split": "historical_seed_cleared",
        "prediction_pdb": _artifact(row.get("prediction_pdb", "")),
        "native_pdb": _artifact(row.get("native_pdb", "")),
        "leakage_clearance": _text(row.get("leakage_clearance")).lower(),
        "prediction_method": "internal_physics_seed_inventory",
        "prediction_created_at": _text(row.get("prediction_created_at")),
        "native_release_date": _text(row.get("native_release_date")),
        "prediction_generated_before_native_release": _text(
            row.get("prediction_generated_before_native_release")
        ).lower(),
        "public_template_or_native_used_for_prediction": _text(
            row.get("public_template_or_native_used_for_prediction")
        ).lower(),
        "other_team_model_used": _text(row.get("other_team_model_used")).lower(),
        "post_release_information_used": _text(row.get("post_release_information_used")).lower(),
        "current_casp17_target": _text(row.get("current_casp17_target")).lower(),
        "operator_clearance": _text(row.get("operator_clearance")).lower(),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    seed_payload = _read_json(args.seed_inventory_json)
    seed_summary = _summary(seed_payload)
    seeds = _seed_rows(seed_payload)
    template_status = _ensure_operator_clearance_csv(
        args.operator_clearance_csv,
        seeds,
        refresh=args.refresh_template,
    )
    operator_rows, _fieldnames = _read_csv(args.operator_clearance_csv)
    by_target = {_text(row.get("target_id")).upper(): row for row in operator_rows}
    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, str]] = []
    for seed in seeds:
        row = dict(_operator_template_row(seed))
        row.update(by_target.get(_text(seed.get("target_id")).upper(), {}))
        report = _report_row(row)
        rows.append(report)
        if report["clearance_status"] == "ready_for_cleared_seed_manifest":
            manifest_rows.append(_cleared_manifest_row(row))
    by_status = Counter(str(row.get("clearance_status")) for row in rows)
    phase_open_counts = {
        "identity": sum(1 for row in rows if row["identity_status"] != "ready"),
        "core_files": sum(1 for row in rows if row["core_files_status"] != "ready"),
        "no_leak_provenance": sum(1 for row in rows if row["no_leak_provenance_status"] != "ready"),
        "calibration": sum(1 for row in rows if row["calibration_status"] != "ready"),
        "ablation": sum(1 for row in rows if row["ablation_status"] != "ready"),
    }
    first_open = next(
        (row for row in rows if row["clearance_status"] != "ready_for_cleared_seed_manifest"),
        rows[0] if rows else {},
    )
    if rows and by_status["ready_for_cleared_seed_manifest"] == len(rows):
        status = "ready_for_cleared_seed_manifest"
    elif by_status["ready_for_cleared_seed_manifest"]:
        status = "partial_seed_clearance_ready"
    elif rows:
        status = "awaiting_seed_clearance"
    else:
        status = "missing_seed_rows"
    summary = {
        "packet_type": "casp17_historical_identity_seed_clearance_workorder",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "seed_clearance_status": status,
        "template_status": template_status,
        "seed_inventory_status": _text(seed_summary.get("seed_inventory_status")),
        "seed_inventory_json": _artifact(args.seed_inventory_json),
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "cleared_manifest_csv": _artifact(args.out_cleared_manifest_csv),
        "seed_row_count": len(rows),
        "ready_seed_count": by_status["ready_for_cleared_seed_manifest"],
        "awaiting_seed_count": by_status["awaiting_seed_clearance"],
        "cleared_manifest_row_count": len(manifest_rows),
        "blocking_field_count": sum(_int(row.get("blocking_field_count")) for row in rows),
        "phase_open_counts": phase_open_counts,
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "cleared_manifest_rows": manifest_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    phase_open = summary["phase_open_counts"]
    lines = [
        "# CASP17 Historical Identity Seed Clearance Workorder",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- seed_clearance_status: `{summary['seed_clearance_status']}`",
        f"- template_status: `{summary['template_status']}`",
        f"- seed rows ready/awaiting/total: `{summary['ready_seed_count']}/{summary['awaiting_seed_count']}/{summary['seed_row_count']}`",
        f"- cleared manifest rows: `{summary['cleared_manifest_row_count']}`",
        f"- open phases identity/core/provenance/calibration/ablation: `{phase_open['identity']}/{phase_open['core_files']}/{phase_open['no_leak_provenance']}/{phase_open['calibration']}/{phase_open['ablation']}`",
        f"- blocking fields: `{summary['blocking_field_count']}`",
        f"- operator clearance csv: `{summary['operator_clearance_csv']}`",
        f"- cleared manifest csv: `{summary['cleared_manifest_csv']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| slot | target | scope | status | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['batch_slot']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['clearance_status']}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `missing_seed_rows` | - | build seed inventory first |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], REPORT_COLUMNS)
    _write_csv(args.out_cleared_manifest_csv, payload["cleared_manifest_rows"], MANIFEST_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed clearance workorder.")
    parser.add_argument("--seed-inventory-json", default=DEFAULT_SEED_INVENTORY_JSON)
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-cleared-manifest-csv", default=DEFAULT_OUT_CLEARED_MANIFEST_CSV)
    parser.add_argument("--refresh-template", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
