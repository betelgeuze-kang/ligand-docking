#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCAFFOLD_CSV = "runs/casp17_historical_benchmark_manifest_scaffold_current.csv"
DEFAULT_READY_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_ready_current.csv"
DEFAULT_ACTIVE_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_current.csv"
DEFAULT_TARGET_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_PREDICTION_DIR = "runs/casp17_historical_benchmark_predictions_current"
DEFAULT_NATIVE_DIR = "runs/casp17_historical_benchmark_natives_current"
DEFAULT_OUT_JSON = "runs/casp17_historical_input_preflight_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_input_preflight_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_historical_input_preflight_packet_current.md"

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
DEFAULT_LAYERS = [
    "recursive=runs/casp17_historical_ablation_predictions_current/recursive",
    "scored=runs/casp17_historical_ablation_predictions_current/scored",
    "sidechain_scaffold=runs/casp17_historical_ablation_predictions_current/sidechain_scaffold",
    "sidechain_repacked=runs/casp17_historical_ablation_predictions_current/sidechain_repacked",
    "sidechain_completed=runs/casp17_historical_ablation_predictions_current/sidechain_completed",
    "steric_relaxed=runs/casp17_historical_ablation_predictions_current/steric_relaxed",
    "rotamer_minimized=runs/casp17_historical_ablation_predictions_current/rotamer_minimized",
    "polar_refined=runs/casp17_historical_ablation_predictions_current/polar_refined",
    "forcefield_minimized=runs/casp17_historical_ablation_predictions_current/forcefield_minimized",
    "statistical_rotamer=runs/casp17_historical_ablation_predictions_current/statistical_rotamer",
]

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
TARGET_PATTERN = re.compile(r"([A-Z][0-9]{4})")


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
        return [], ["csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    missing = [column for column in REQUIRED_COLUMNS + PROVENANCE_COLUMNS if column not in fieldnames]
    blockers = [f"required_columns_missing:{','.join(missing)}"] if missing else []
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
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["benchmark_id", "target_id", "row_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _target_id_from_path(path: Path) -> str:
    match = TARGET_PATTERN.search(path.stem.upper())
    return match.group(1) if match else path.stem.upper()


def _scope_for_target(target_id: str, fallback: str = "") -> str:
    fallback = fallback.lower()
    if fallback in {"monomer", "complex"}:
        return fallback
    return "complex" if target_id.upper().startswith("H") else "monomer"


def _scan_pdbs(path_like: str | Path) -> dict[str, Path]:
    root = _resolve(path_like)
    if not root.exists():
        return {}
    paths: dict[str, Path] = {}
    for path in sorted(root.glob("*.pdb")):
        paths.setdefault(_target_id_from_path(path), path)
    return paths


def _current_open_targets(watchlist: dict[str, Any]) -> set[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return set()
    result: set[str] = set()
    for row in rows:
        if isinstance(row, dict) and row.get("human_open") is True:
            target_id = _text(row.get("target_id")).upper()
            if target_id:
                result.add(target_id)
    return result


def _parse_layer_specs(specs: list[str] | None) -> list[tuple[str, str]]:
    layers: list[tuple[str, str]] = []
    seen: set[str] = set()
    for spec in specs or DEFAULT_LAYERS:
        if "=" not in spec:
            raise SystemExit(f"invalid layer spec {spec!r}; expected name=prediction_dir")
        name, path = spec.split("=", 1)
        name = _text(name)
        path = _text(path)
        if not name or not path:
            raise SystemExit(f"invalid layer spec {spec!r}; expected nonempty name and path")
        if name in seen:
            raise SystemExit(f"duplicate layer name {name!r}")
        seen.add(name)
        layers.append((name, path))
    return layers


def _select_rows(args: argparse.Namespace) -> tuple[str, str, list[dict[str, str]], list[str]]:
    candidates = [
        ("active_manifest", args.active_manifest_csv),
        ("ready_manifest", args.ready_manifest_csv),
        ("scaffold", args.scaffold_csv),
    ]
    csv_blockers: list[str] = []
    for source_mode, csv_path in candidates:
        rows, blockers = _read_csv(csv_path)
        if rows:
            return source_mode, _artifact(csv_path), rows, blockers
        if source_mode == "scaffold":
            csv_blockers = blockers
    predictions = _scan_pdbs(args.prediction_dir)
    natives = _scan_pdbs(args.native_dir)
    target_ids = sorted(set(predictions) | set(natives))
    rows = [
        {
            "benchmark_id": f"hist_{target_id}",
            "target_id": target_id,
            "scope": _scope_for_target(target_id),
            "split": "historical",
            "prediction_pdb": _artifact(predictions[target_id]) if target_id in predictions else "",
            "native_pdb": _artifact(natives[target_id]) if target_id in natives else "",
            "leakage_clearance": "",
        }
        for target_id in target_ids
    ]
    return "scanned_local_dirs", f"{_artifact(args.prediction_dir)};{_artifact(args.native_dir)}", rows, csv_blockers


def _path_exists(path_text: str) -> bool:
    return bool(path_text and _resolve(path_text).exists())


def _layer_prediction_path(row: dict[str, str], layer_name: str, layer_dir: str) -> tuple[str, bool, str]:
    explicit = _text(row.get(f"{layer_name}_prediction_pdb")) or _text(row.get(f"prediction_pdb_{layer_name}"))
    if explicit:
        return _artifact(explicit), _path_exists(explicit), "explicit"
    target_id = _text(row.get("target_id")) or _text(row.get("benchmark_id"))
    if not target_id:
        return "", False, "missing_target_id"
    for name in (f"{target_id}TS.pdb", f"{target_id}.pdb"):
        candidate = _resolve(layer_dir) / name
        if candidate.exists():
            return _artifact(candidate), True, "default_dir"
    return _artifact(_resolve(layer_dir) / f"{target_id}TS.pdb"), False, "default_dir_missing"


def _evaluate_row(
    row: dict[str, str],
    *,
    source_mode: str,
    current_targets: set[str],
    layers: list[tuple[str, str]],
) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id")) or f"hist_{_text(row.get('target_id')) or 'unknown'}"
    target_id = _text(row.get("target_id")).upper()
    scope = _scope_for_target(target_id, _text(row.get("scope")))
    prediction_pdb = _artifact(row.get("prediction_pdb", "")) if _text(row.get("prediction_pdb")) else ""
    native_pdb = _artifact(row.get("native_pdb", "")) if _text(row.get("native_pdb")) else ""
    blockers: list[str] = []
    if not benchmark_id:
        blockers.append("benchmark_id_missing")
    if not target_id:
        blockers.append("target_id_missing")
    if target_id.startswith("REQUIRED_"):
        blockers.append("placeholder_target_id")
    if target_id in current_targets:
        blockers.append("current_casp17_target_not_allowed")
    if scope not in {"monomer", "complex"}:
        blockers.append("scope_not_monomer_or_complex")
    if not prediction_pdb:
        blockers.append("prediction_pdb_missing")
    elif not _resolve(prediction_pdb).exists():
        blockers.append("prediction_pdb_not_found")
    if not native_pdb:
        blockers.append("native_pdb_missing")
    elif not _resolve(native_pdb).exists():
        blockers.append("native_pdb_not_found")
    if _text(row.get("leakage_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_required")
    if not _text(row.get("prediction_method")):
        blockers.append("prediction_method_required")
    prediction_created_at = _date_or_none(row.get("prediction_created_at"))
    native_release_date = _date_or_none(row.get("native_release_date"))
    if prediction_created_at is None:
        blockers.append("prediction_created_at_required_iso_date")
    if native_release_date is None:
        blockers.append("native_release_date_required_iso_date")
    if prediction_created_at is not None and native_release_date is not None and prediction_created_at >= native_release_date:
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
    if _text(row.get("operator_clearance")).lower() not in LEAKAGE_CLEAR_VALUES:
        blockers.append("operator_clearance_required")

    layer_paths: dict[str, str] = {}
    layer_sources: dict[str, str] = {}
    missing_layers: list[str] = []
    for layer_name, layer_dir in layers:
        layer_path, exists, source = _layer_prediction_path(row, layer_name, layer_dir)
        layer_paths[layer_name] = layer_path
        layer_sources[layer_name] = source
        if not exists:
            missing_layers.append(layer_name)
    historical_ready = not blockers
    ablation_ready = historical_ready and not missing_layers
    if ablation_ready:
        row_status = "historical_and_ablation_ready"
    elif historical_ready:
        row_status = "historical_ready_ablation_incomplete"
    else:
        row_status = "blocked"
    return {
        "row_source": source_mode,
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "scope": scope,
        "prediction_pdb": prediction_pdb,
        "native_pdb": native_pdb,
        "historical_ready": historical_ready,
        "ablation_ready": ablation_ready,
        "ablation_layer_present_count": len(layers) - len(missing_layers),
        "ablation_layer_required_count": len(layers),
        "missing_ablation_layers": ",".join(missing_layers),
        "row_status": row_status,
        "blockers": ",".join(sorted(set(blockers))),
        "layer_prediction_paths_json": json.dumps(layer_paths, sort_keys=True),
        "layer_prediction_sources_json": json.dumps(layer_sources, sort_keys=True),
    }


def _threshold_status(source_mode: str, threshold_ready: bool) -> str:
    if not threshold_ready:
        return "blocked"
    if source_mode == "active_manifest":
        return "pass"
    if source_mode == "ready_manifest":
        return "ready_to_activate"
    if source_mode == "scaffold":
        return "ready_to_promote"
    return "blocked"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_mode, source_artifact, source_rows, source_blockers = _select_rows(args)
    layers = _parse_layer_specs(args.layer)
    current_targets = _current_open_targets(_read_json(args.target_watchlist_json))
    rows = [_evaluate_row(row, source_mode=source_mode, current_targets=current_targets, layers=layers) for row in source_rows]
    historical_ready_rows = [row for row in rows if row["historical_ready"] is True]
    ablation_ready_rows = [row for row in rows if row["ablation_ready"] is True]
    min_total = int(args.min_ready_total)
    min_monomer = int(args.min_ready_monomer)
    min_complex = int(args.min_ready_complex)
    historical_threshold_ready = (
        len(historical_ready_rows) >= min_total
        and sum(1 for row in historical_ready_rows if row["scope"] == "monomer") >= min_monomer
        and sum(1 for row in historical_ready_rows if row["scope"] == "complex") >= min_complex
    )
    ablation_threshold_ready = (
        len(ablation_ready_rows) >= min_total
        and sum(1 for row in ablation_ready_rows if row["scope"] == "monomer") >= min_monomer
        and sum(1 for row in ablation_ready_rows if row["scope"] == "complex") >= min_complex
    )
    historical_status = _threshold_status(source_mode, historical_threshold_ready)
    ablation_status = _threshold_status(source_mode, ablation_threshold_ready)
    if historical_status == "pass" and ablation_status == "pass":
        preflight_status = "pass"
    elif historical_status.startswith("ready") and ablation_status.startswith("ready"):
        preflight_status = historical_status
    else:
        preflight_status = "blocked"
    first_blocked = next((row for row in rows if row["row_status"] != "historical_and_ablation_ready"), None)
    summary = {
        "packet_type": "casp17_historical_input_preflight_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_mode": source_mode,
        "source_artifact": source_artifact,
        "scaffold_csv": _artifact(args.scaffold_csv),
        "ready_manifest_csv": _artifact(args.ready_manifest_csv),
        "active_manifest_csv": _artifact(args.active_manifest_csv),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "candidate_count": len(rows),
        "historical_ready_count": len(historical_ready_rows),
        "ablation_ready_count": len(ablation_ready_rows),
        "historical_ready_monomer_count": sum(1 for row in historical_ready_rows if row["scope"] == "monomer"),
        "historical_ready_complex_count": sum(1 for row in historical_ready_rows if row["scope"] == "complex"),
        "ablation_ready_monomer_count": sum(1 for row in ablation_ready_rows if row["scope"] == "monomer"),
        "ablation_ready_complex_count": sum(1 for row in ablation_ready_rows if row["scope"] == "complex"),
        "min_ready_total": min_total,
        "min_ready_monomer": min_monomer,
        "min_ready_complex": min_complex,
        "missing_prediction_count": sum(1 for row in rows if "prediction_pdb_not_found" in row["blockers"] or "prediction_pdb_missing" in row["blockers"]),
        "missing_native_count": sum(1 for row in rows if "native_pdb_not_found" in row["blockers"] or "native_pdb_missing" in row["blockers"]),
        "provenance_blocked_count": sum(
            1
            for row in rows
            if any(
                token in row["blockers"]
                for token in [
                    "leakage_clearance_required",
                    "prediction_method_required",
                    "prediction_created_at_required_iso_date",
                    "native_release_date_required_iso_date",
                    "operator_clearance_required",
                ]
            )
        ),
        "missing_ablation_layer_file_count": sum(len([layer for layer in row["missing_ablation_layers"].split(",") if layer]) for row in rows),
        "historical_input_preflight_status": historical_status,
        "ablation_input_preflight_status": ablation_status,
        "preflight_status": preflight_status,
        "source_blockers": ",".join(source_blockers),
        "first_blocked_benchmark_id": first_blocked["benchmark_id"] if first_blocked else "",
        "first_blocked_blockers": first_blocked["blockers"] if first_blocked else "",
        "first_blocked_missing_ablation_layers": first_blocked["missing_ablation_layers"] if first_blocked else "",
        "layers": [{"name": name, "prediction_dir": _artifact(path)} for name, path in layers],
        "claim_boundary": "Local no-leak historical input preflight only; it does not fetch native structures, clear provenance, score accuracy, or submit to CASP.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Input Preflight Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- preflight_status: `{summary['preflight_status']}`",
        f"- source_mode: `{summary['source_mode']}`",
        f"- source_artifact: `{summary['source_artifact']}`",
        f"- candidates/historical_ready/ablation_ready: `{summary['candidate_count']}/{summary['historical_ready_count']}/{summary['ablation_ready_count']}`",
        f"- historical_status: `{summary['historical_input_preflight_status']}`",
        f"- ablation_status: `{summary['ablation_input_preflight_status']}`",
        f"- missing prediction/native/layer files: `{summary['missing_prediction_count']}/{summary['missing_native_count']}/{summary['missing_ablation_layer_file_count']}`",
        f"- provenance_blocked_count: `{summary['provenance_blocked_count']}`",
        f"- first_blocked: `{summary['first_blocked_benchmark_id'] or '-'}`",
        "",
        "## Rows",
        "",
        "| source | benchmark | target | scope | status | historical ready | ablation ready | layers | blockers | missing layers |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['row_source']}` | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['row_status']}` | `{row['historical_ready']}` | `{row['ablation_ready']}` | "
            f"{row['ablation_layer_present_count']}/{row['ablation_layer_required_count']} | "
            f"{row['blockers'] or '-'} | {row['missing_ablation_layers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked` | `False` | `False` | 0/0 | no candidate rows | - |")
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            "If this packet is `blocked`, fill the scaffold or ready manifest with local no-leak historical prediction/native pairs and optional per-layer prediction paths.",
            "If it is `ready_to_promote` or `ready_to_activate`, make the operator-owned manifest promotion/copy decision before scoring.",
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
    parser = argparse.ArgumentParser(description="Preflight local no-leak historical benchmark and ablation inputs for CASP17 win-tier evidence.")
    parser.add_argument("--scaffold-csv", default=DEFAULT_SCAFFOLD_CSV)
    parser.add_argument("--ready-manifest-csv", default=DEFAULT_READY_MANIFEST_CSV)
    parser.add_argument("--active-manifest-csv", default=DEFAULT_ACTIVE_MANIFEST_CSV)
    parser.add_argument("--target-watchlist-json", default=DEFAULT_TARGET_WATCHLIST_JSON)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--native-dir", default=DEFAULT_NATIVE_DIR)
    parser.add_argument("--layer", action="append", help="Layer spec as name=prediction_dir. Defaults to historical ablation layer dirs.")
    parser.add_argument("--min-ready-total", type=int, default=2)
    parser.add_argument("--min-ready-monomer", type=int, default=1)
    parser.add_argument("--min-ready-complex", type=int, default=1)
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


if __name__ == "__main__":
    main()
