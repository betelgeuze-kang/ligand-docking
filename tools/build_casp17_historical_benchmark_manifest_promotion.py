#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SCAFFOLD_CSV = "runs/casp17_historical_benchmark_manifest_scaffold_current.csv"
DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_OUT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_ready_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_historical_benchmark_manifest_promotion_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_benchmark_manifest_promotion_current.csv"
DEFAULT_OUT_MD = "runs/casp17_historical_benchmark_manifest_promotion_current.md"

REQUIRED_COLUMNS = ["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"]
PROVENANCE_COLUMNS = [
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
OUTPUT_COLUMNS = REQUIRED_COLUMNS + PROVENANCE_COLUMNS
OPTIONAL_ABLATION_LAYER_NAMES = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]
OPTIONAL_ABLATION_LAYER_COLUMNS = [f"{layer}_prediction_pdb" for layer in OPTIONAL_ABLATION_LAYER_NAMES]
STATUS_COLUMNS = {"manifest_ready_status", "promotion_status", "blockers"}
LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}


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


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["scaffold_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    missing = [column for column in OUTPUT_COLUMNS if column not in fieldnames]
    blockers = [f"required_columns_missing:{','.join(missing)}"] if missing else []
    if not rows:
        blockers.append("scaffold_csv_empty")
    return rows, blockers


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
    for key in OUTPUT_COLUMNS + OPTIONAL_ABLATION_LAYER_COLUMNS + ["promotion_status", "blockers"]:
        if key not in fieldnames:
            fieldnames.append(key)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(OUTPUT_COLUMNS + OPTIONAL_ABLATION_LAYER_COLUMNS)
    for row in rows:
        for key in row:
            if key not in fieldnames and key not in STATUS_COLUMNS:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _current_open_targets(watchlist: dict[str, Any]) -> set[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return set()
    current: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True:
            current.add(target_id)
    return current


def _normalized_manifest_row(row: dict[str, str]) -> dict[str, Any]:
    normalized = {key: _text(value) for key, value in row.items() if key and key not in STATUS_COLUMNS}
    normalized.update(
        {
        "benchmark_id": _text(row.get("benchmark_id")),
        "target_id": _text(row.get("target_id")).upper(),
        "scope": _text(row.get("scope")).lower(),
        "split": _text(row.get("split")) or "historical",
        "prediction_pdb": _artifact(row.get("prediction_pdb", "")) if _text(row.get("prediction_pdb")) else "",
        "native_pdb": _artifact(row.get("native_pdb", "")) if _text(row.get("native_pdb")) else "",
        "leakage_clearance": _text(row.get("leakage_clearance")),
        }
    )
    for column in PROVENANCE_COLUMNS:
        normalized[column] = _text(row.get(column))
    return normalized


def _evaluate_row(row: dict[str, str], current_targets: set[str]) -> dict[str, Any]:
    promoted = _normalized_manifest_row(row)
    blockers: list[str] = []
    scaffold_status = _text(row.get("manifest_ready_status")).lower()
    target_id = promoted["target_id"]
    scope = promoted["scope"]
    prediction = promoted["prediction_pdb"]
    native = promoted["native_pdb"]
    leakage = promoted["leakage_clearance"].lower()
    if scaffold_status and scaffold_status != "ready":
        blockers.append("scaffold_row_not_ready")
    if not promoted["benchmark_id"]:
        blockers.append("benchmark_id_missing")
    if not target_id:
        blockers.append("target_id_missing")
    if target_id.startswith("REQUIRED_"):
        blockers.append("placeholder_target_id")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed_for_historical_benchmark")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if not prediction:
        blockers.append("prediction_pdb_missing")
    elif not _resolve(prediction).exists():
        blockers.append("prediction_pdb_not_found")
    if not native:
        blockers.append("native_pdb_missing")
    elif not _resolve(native).exists():
        blockers.append("native_pdb_not_found")
    if leakage not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if not _text(promoted.get("prediction_method")):
        blockers.append("prediction_method_required")
    prediction_created_at = _date_or_none(promoted.get("prediction_created_at"))
    native_release_date = _date_or_none(promoted.get("native_release_date"))
    if prediction_created_at is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_release_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_created_at is not None and native_release_date is not None and prediction_created_at >= native_release_date:
        blockers.append("prediction_date_not_before_native_release")
    if _text(promoted.get("prediction_generated_before_native_release")).lower() not in TRUE_VALUES:
        blockers.append("prediction_generated_before_native_release_required")
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(promoted.get(column)).lower() not in FALSE_VALUES:
            blockers.append(f"{column}_must_be_false")
    if _text(promoted.get("operator_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("operator_clearance_required")
    promoted["promotion_status"] = "promoted" if not blockers else "blocked"
    promoted["blockers"] = ",".join(blockers)
    return promoted


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scaffold_rows, scaffold_blockers = _read_csv(args.scaffold_csv)
    current_targets = _current_open_targets(_read_json(args.target_watchlist_json))
    rows = [_evaluate_row(row, current_targets) for row in scaffold_rows]
    promoted_rows = [row for row in rows if row["promotion_status"] == "promoted"]
    blocked_rows = [row for row in rows if row["promotion_status"] != "promoted"]
    monomer_promoted = sum(1 for row in promoted_rows if row.get("scope") == "monomer")
    complex_promoted = sum(1 for row in promoted_rows if row.get("scope") == "complex")
    min_monomer = int(args.min_ready_monomer)
    min_complex = int(args.min_ready_complex)
    threshold_blockers: list[str] = []
    if len(promoted_rows) < int(args.min_ready_total):
        threshold_blockers.append("ready_total_below_threshold")
    if monomer_promoted < min_monomer:
        threshold_blockers.append("ready_monomer_below_threshold")
    if complex_promoted < min_complex:
        threshold_blockers.append("ready_complex_below_threshold")
    promotion_status = "ready" if promoted_rows and not blocked_rows and not scaffold_blockers and not threshold_blockers else "blocked"
    preserved_extra_columns = sorted(
        {
            key
            for row in rows
            for key in row
            if key not in set(OUTPUT_COLUMNS) | STATUS_COLUMNS
        }
    )
    summary = {
        "packet_type": "casp17_historical_benchmark_manifest_promotion",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scaffold_csv": _artifact(args.scaffold_csv),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "out_manifest_csv": _artifact(args.out_manifest_csv),
        "source_row_count": len(rows),
        "promoted_count": len(promoted_rows),
        "blocked_count": len(blocked_rows),
        "monomer_promoted_count": monomer_promoted,
        "complex_promoted_count": complex_promoted,
        "min_ready_total": int(args.min_ready_total),
        "min_ready_monomer": min_monomer,
        "min_ready_complex": min_complex,
        "current_target_exclusion_count": len(current_targets),
        "scaffold_blockers": ",".join(scaffold_blockers),
        "threshold_blockers": ",".join(threshold_blockers),
        "optional_ablation_layer_columns": ",".join(OPTIONAL_ABLATION_LAYER_COLUMNS),
        "preserved_extra_columns": ",".join(preserved_extra_columns),
        "preserved_extra_column_count": len(preserved_extra_columns),
        "promotion_status": promotion_status,
        "claim_boundary": "Local manifest promotion only; it copies ready no-leak historical rows to a candidate manifest and does not fetch data, score accuracy, or submit to CASP.",
    }
    return {"summary": summary, "rows": rows, "promoted_manifest_rows": promoted_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Benchmark Manifest Promotion",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- promotion_status: `{summary['promotion_status']}`",
        f"- scaffold_csv: `{summary['scaffold_csv']}`",
        f"- out_manifest_csv: `{summary['out_manifest_csv']}`",
        f"- source/promoted/blocked: `{summary['source_row_count']}/{summary['promoted_count']}/{summary['blocked_count']}`",
        f"- monomer/complex promoted: `{summary['monomer_promoted_count']}/{summary['complex_promoted_count']}`",
        f"- scaffold_blockers: `{summary['scaffold_blockers'] or '-'}`",
        f"- threshold_blockers: `{summary['threshold_blockers'] or '-'}`",
        f"- optional_ablation_layer_columns: `{summary['optional_ablation_layer_columns']}`",
        f"- preserved_extra_columns: `{summary['preserved_extra_columns'] or '-'}`",
        "",
        "## Rows",
        "",
        "| benchmark | target | scope | promotion | prediction_pdb | native_pdb | leakage | prediction/native dates | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id'] or '-'}` | `{row['target_id'] or '-'}` | `{row['scope'] or '-'}` | `{row['promotion_status']}` | "
            f"`{row['prediction_pdb'] or '-'}` | `{row['native_pdb'] or '-'}` | `{row['leakage_clearance'] or '-'}` | "
            f"`{row.get('prediction_created_at') or '-'}/{row.get('native_release_date') or '-'}` | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked` | - | - | - | no scaffold rows |")
    lines.extend(
        [
            "",
            "## Use",
            "",
            "Use the promoted manifest for scoring only when `promotion_status=ready` and the operator has verified the no-leak decision for every row.",
            "The default output is a candidate manifest; do not overwrite the active scoring manifest unless the promotion packet is ready.",
            "",
            "## Claim Boundary",
            "",
            str(summary["claim_boundary"]),
            "",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote ready no-leak historical benchmark scaffold rows into a scoring manifest candidate.")
    parser.add_argument("--scaffold-csv", default=DEFAULT_SCAFFOLD_CSV)
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--out-manifest-csv", default=DEFAULT_OUT_MANIFEST_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--min-ready-total", type=int, default=2)
    parser.add_argument("--min-ready-monomer", type=int, default=1)
    parser.add_argument("--min-ready-complex", type=int, default=1)
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_manifest_csv(args.out_manifest_csv, payload["promoted_manifest_rows"])
    _write_md(args.out_md, payload)
    if args.fail_on_blocked and payload["summary"]["promotion_status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
