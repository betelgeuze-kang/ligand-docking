#!/usr/bin/env python3
"""Audit PocketMD Lite top-k claim-grade metric source availability.

Read-only: this packet inspects the metric collection input pack and nearby
local trajectory NPZs for exact claim-grade metric fields or atomized inputs
that could support the next local-min/H-bond/clash-relief collector. It never
computes or promotes proxy metrics.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "runs/pocketmd_lite_metric_collection_input_pack_current.csv"
DEFAULT_PROBE_JSON = "runs/pocketmd_lite_metric_collection_probe_current.json"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_claim_grade_metric_source_audit_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_claim_grade_metric_source_audit_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_claim_grade_metric_source_audit_current.csv"
DEFAULT_SEARCH_ROOTS = (
    "runs/pocketmd_lite_ligand_atom_frame_recovery_current",
    "runs/residual_force_trajectory_regeneration_current",
    "~/.local/share/Trash/files/trajectory_spill",
    "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs",
)
MAX_CANDIDATE_PATHS_PER_ROW = 12

PACKET_TYPE = "pocketmd_lite_claim_grade_metric_source_audit"
SCHEMA_VERSION = "pocketmd_lite_claim_grade_metric_source_audit_v1"

LOCAL_MIN_KEYS = (
    "local_min_ligand_rmsd_a",
    "local_min_rmsd_a",
    "local_min_survival_rmsd_a",
)
HBOND_KEYS = (
    "hbond_persistence",
    "hbond_presence_fraction",
    "hbond_frame_persistence",
)
INITIAL_CLASH_KEYS = (
    "initial_clash_count",
    "pre_refine_clash_count",
)
FINAL_CLASH_KEYS = ("clash_count", "final_clash_count")
CONTACT_KEYS = ("contact_persistence", "contact_presence_fraction")
LIGAND_ATOM_FRAME_KEYS = (
    "ligand_atom_frames",
    "ligand_heavy_atom_frames",
    "atomized_ligand_frames",
)
PROTEIN_ATOM_FRAME_KEYS = ("protein_atom_frames",)

METRIC_KEY_ALIASES = {
    "local_min_ligand_rmsd_a": LOCAL_MIN_KEYS,
    "hbond_persistence": HBOND_KEYS,
    "initial_clash_count": INITIAL_CLASH_KEYS,
    "pre_refine_clash_count": INITIAL_CLASH_KEYS,
    "clash_count": FINAL_CLASH_KEYS,
    "contact_persistence": CONTACT_KEYS,
}

CLAIM_BOUNDARY = (
    "PocketMD Lite claim-grade metric source audit only; it checks whether selected top-k inputs or nearby local "
    "NPZs already contain exact local-min/H-bond/clash metric fields, or whether they expose atomized protein and "
    "ligand frames suitable for a follow-on collector. Coarse two-bead telemetry remains diagnostic and cannot "
    "fill claim-grade fields. This tool does not run local-min, micro-MD, H-bond scoring, docking, copy files, "
    "write candidate CSVs, promote claims, or mutate external state."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "candidate_csv_update_allowed": False,
    "claim_promotion_allowed": False,
}

CSV_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "required_metrics",
    "selected_trajectory_npz",
    "selected_npz_status",
    "selected_npz_schema",
    "selected_exact_metric_ready",
    "selected_ligand_bead_count",
    "selected_protein_ca_count",
    "selected_protein_atom_frame_count",
    "selected_ligand_atom_frame_count",
    "selected_missing_exact_metric_fields",
    "searched_npz_candidate_count",
    "exact_metric_source_candidate_count",
    "atomized_protein_candidate_count",
    "ligand_atom_candidate_count",
    "claim_grade_collection_input_candidate_count",
    "best_candidate_npz",
    "best_candidate_status",
    "best_candidate_blockers",
    "recommended_next_local_action",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
    "candidate_csv_update_allowed",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if str(path).startswith("~"):
        path = path.expanduser()
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _split_semicolon(value: Any) -> list[str]:
    return [part for part in _text(value).split(";") if part]


def _read_csv(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            if value.size != 1:
                return None
            value = value.reshape(-1)[0]
        text = _text(value)
        if not text:
            return None
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metric_value(payload: Any, metric: str) -> tuple[str, float | None]:
    aliases = METRIC_KEY_ALIASES.get(metric, (metric,))
    for key in aliases:
        if key not in payload.files:
            continue
        value = _optional_float(payload[key])
        return key, value
    return "", None


def _array_shape(payload: Any, key: str) -> tuple[int, ...]:
    if key not in payload.files:
        return ()
    try:
        return tuple(int(part) for part in np.asarray(payload[key]).shape)
    except Exception:
        return ()


def _inspect_npz(path_like: str | Path, required_metrics: list[str]) -> dict[str, Any]:
    text = _text(path_like)
    path = _resolve(text) if text else Path("")
    base: dict[str, Any] = {
        "path": _display(text),
        "exists": bool(text and path.exists()),
        "readable": False,
        "status": "missing" if text else "not_requested",
        "trajectory_schema": "",
        "keys": [],
        "frame_count": 0,
        "ligand_bead_count": 0,
        "protein_ca_count": 0,
        "protein_atom_frame_count": 0,
        "ligand_atom_frame_count": 0,
        "protein_atom_frames_present": False,
        "ligand_atom_frames_present": False,
        "exact_metric_fields_present": [],
        "exact_metric_values": {},
        "missing_exact_metric_fields": list(required_metrics),
        "exact_metric_source_ready": False,
        "claim_grade_collection_input_ready": False,
        "blockers": ["npz_path_missing"] if not text else ["npz_missing"],
    }
    if not text or not path.exists():
        return base
    try:
        with np.load(str(path), allow_pickle=False) as payload:
            keys = list(payload.files)
            base["keys"] = keys
            ligand_shape = _array_shape(payload, "ligand_frames")
            protein_ca_shape = _array_shape(payload, "protein_ca")
            protein_atom_shape = _array_shape(payload, "protein_atom_frames")
            ligand_atom_shape = ()
            ligand_atom_source = ""
            for key in LIGAND_ATOM_FRAME_KEYS:
                shape = _array_shape(payload, key)
                if shape:
                    ligand_atom_shape = shape
                    ligand_atom_source = key
                    break
            if not ligand_atom_shape and len(ligand_shape) == 3 and ligand_shape[1] > 2:
                ligand_atom_shape = ligand_shape
                ligand_atom_source = "ligand_frames_gt_two_beads"

            schema_ready = (
                len(ligand_shape) == 3
                and ligand_shape[0] > 0
                and ligand_shape[1] > 0
                and ligand_shape[2] == 3
                and len(protein_ca_shape) == 2
                and protein_ca_shape[0] > 0
                and protein_ca_shape[1] == 3
            )
            exact_metric_fields: list[str] = []
            exact_metric_values: dict[str, float] = {}
            missing_exact_metrics: list[str] = []
            for metric in required_metrics:
                source_key, value = _metric_value(payload, metric)
                if source_key and value is not None:
                    exact_metric_fields.append(metric)
                    exact_metric_values[metric] = value
                else:
                    missing_exact_metrics.append(metric)

            protein_atom_present = (
                "protein_atom_frames" in keys
                and len(protein_atom_shape) == 3
                and protein_atom_shape[0] > 0
                and protein_atom_shape[1] > 0
                and protein_atom_shape[2] == 3
            )
            ligand_atom_present = bool(
                ligand_atom_shape
                and len(ligand_atom_shape) == 3
                and ligand_atom_shape[0] > 0
                and ligand_atom_shape[1] > 2
                and ligand_atom_shape[2] == 3
            )
            exact_ready = schema_ready and not missing_exact_metrics
            collection_ready = bool(schema_ready and protein_atom_present and ligand_atom_present)

            blockers: list[str] = []
            if not schema_ready:
                blockers.append("trajectory_schema_missing_or_invalid")
            if missing_exact_metrics:
                blockers.append("exact_metric_fields_missing:" + ",".join(missing_exact_metrics))
            if not protein_atom_present:
                blockers.append("protein_atom_frames_missing")
            if not ligand_atom_present:
                blockers.append("ligand_atom_frames_missing")
            if len(ligand_shape) == 3 and ligand_shape[1] <= 2:
                blockers.append("ligand_trajectory_is_two_bead_proxy")

            if exact_ready:
                status = "exact_metric_source_ready"
            elif collection_ready:
                status = "claim_grade_collection_input_ready"
            elif schema_ready and protein_atom_present:
                status = "partial_atomized_protein_only"
            elif schema_ready:
                status = "proxy_only_trajectory"
            else:
                status = "schema_incomplete"

            base.update(
                {
                    "readable": True,
                    "status": status,
                    "trajectory_schema": (
                        "atomized_collection_input"
                        if collection_ready
                        else "protein_atom_two_bead_ligand"
                        if schema_ready and protein_atom_present
                        else "coarse_two_bead_ca"
                        if schema_ready
                        else "invalid"
                    ),
                    "frame_count": int(ligand_shape[0]) if len(ligand_shape) >= 1 else 0,
                    "ligand_bead_count": int(ligand_shape[1]) if len(ligand_shape) >= 2 else 0,
                    "protein_ca_count": int(protein_ca_shape[0]) if len(protein_ca_shape) >= 1 else 0,
                    "protein_atom_frame_count": int(protein_atom_shape[1]) if len(protein_atom_shape) >= 2 else 0,
                    "ligand_atom_frame_count": int(ligand_atom_shape[1]) if len(ligand_atom_shape) >= 2 else 0,
                    "protein_atom_frames_present": protein_atom_present,
                    "ligand_atom_frames_present": ligand_atom_present,
                    "ligand_atom_frame_source": ligand_atom_source,
                    "exact_metric_fields_present": exact_metric_fields,
                    "exact_metric_values": exact_metric_values,
                    "missing_exact_metric_fields": missing_exact_metrics,
                    "exact_metric_source_ready": exact_ready,
                    "claim_grade_collection_input_ready": collection_ready,
                    "blockers": blockers,
                }
            )
            return base
    except Exception as exc:
        base.update(
            {
                "status": "unreadable",
                "blockers": [f"npz_unreadable:{type(exc).__name__}"],
            }
        )
        return base


def _search_roots(values: list[str | Path] | tuple[str | Path, ...] | None) -> list[Path]:
    roots = values if values is not None else DEFAULT_SEARCH_ROOTS
    out: list[Path] = []
    for value in roots:
        text = _text(value)
        if not text:
            continue
        path = _resolve(text)
        if path not in out:
            out.append(path)
    return out


def _candidate_path_matches(path: Path, target: str, ligand_id: str) -> bool:
    text = str(path).lower()
    target_variants = {target.lower(), target.lower().replace("-", "_")}
    ligand_variants = {ligand_id.lower(), ligand_id.lower().replace("-", "_")}
    return any(part in text for part in target_variants) and any(part in text for part in ligand_variants)


def _find_matching_npzs(row: dict[str, Any], search_roots: list[Path]) -> list[str]:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    selected = _text(row.get("selected_trajectory_npz"))
    paths: list[str] = []
    if selected:
        paths.append(_display(selected))
    if not target or not ligand_id:
        return paths
    for root in search_roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            iterator = root.rglob("*.npz")
        except OSError:
            continue
        for path in iterator:
            try:
                if not path.is_file() or not _candidate_path_matches(path, target, ligand_id):
                    continue
            except OSError:
                continue
            display = _display(path)
            if display not in paths:
                paths.append(display)
            if len(paths) >= MAX_CANDIDATE_PATHS_PER_ROW:
                return paths
    return paths


def _rank_candidate(item: dict[str, Any]) -> tuple[int, int, int]:
    if item["exact_metric_source_ready"]:
        return (4, int(item["frame_count"]), int(item["protein_atom_frame_count"]))
    if item["claim_grade_collection_input_ready"]:
        return (3, int(item["frame_count"]), int(item["protein_atom_frame_count"]))
    if item["protein_atom_frames_present"]:
        return (2, int(item["frame_count"]), int(item["protein_atom_frame_count"]))
    if item["readable"]:
        return (1, int(item["frame_count"]), int(item["protein_ca_count"]))
    return (0, 0, 0)


def _row_action(best: dict[str, Any], exact_candidates: list[dict[str, Any]]) -> str:
    if exact_candidates:
        return "extract_exact_metric_fields_into_candidate_fill_preview_then_rerun_report"
    if best.get("claim_grade_collection_input_ready"):
        return "run_claim_grade_metric_collector_for_atomized_topk_input"
    if best.get("protein_atom_frames_present"):
        return "generate_or_recover_ligand_atom_frames_then_run_claim_grade_metric_collector"
    if best.get("readable"):
        return "generate_atomized_protein_and_ligand_frames_then_run_claim_grade_metric_collector"
    return "restore_or_regenerate_topk_collection_inputs"


def build_pocketmd_lite_claim_grade_metric_source_audit(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    probe_json: str | Path = DEFAULT_PROBE_JSON,
    search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    input_path = _resolve(input_csv)
    probe_path = _resolve(probe_json)
    source_rows = [row for row in _read_csv(input_path) if _bool(row.get("collection_input_ready"))]
    probe_payload = _read_json(probe_path)
    probe_summary = probe_payload.get("summary") if isinstance(probe_payload.get("summary"), dict) else {}
    roots = _search_roots(search_roots)
    rows: list[dict[str, Any]] = []

    for source_row in source_rows:
        required_metrics = _split_semicolon(source_row.get("required_collection_metrics")) or [
            "local_min_ligand_rmsd_a",
            "hbond_persistence",
            "initial_clash_count",
        ]
        candidate_paths = _find_matching_npzs(source_row, roots)
        inspected = [_inspect_npz(path, required_metrics) for path in candidate_paths]
        selected = _inspect_npz(source_row.get("selected_trajectory_npz"), required_metrics)
        if not any(item["path"] == selected["path"] for item in inspected):
            inspected.insert(0, selected)
        exact_candidates = [item for item in inspected if item["exact_metric_source_ready"]]
        atomized_protein_candidates = [item for item in inspected if item["protein_atom_frames_present"]]
        ligand_atom_candidates = [item for item in inspected if item["ligand_atom_frames_present"]]
        collection_candidates = [item for item in inspected if item["claim_grade_collection_input_ready"]]
        best = max(inspected, key=_rank_candidate, default=selected)
        row = {
            "entry_id": _text(source_row.get("entry_id")),
            "target": _text(source_row.get("target")),
            "ligand_id": _text(source_row.get("ligand_id")),
            "required_metrics": required_metrics,
            "selected_trajectory_npz": selected["path"],
            "selected_npz_status": selected["status"],
            "selected_npz_schema": selected["trajectory_schema"],
            "selected_exact_metric_ready": selected["exact_metric_source_ready"],
            "selected_ligand_bead_count": selected["ligand_bead_count"],
            "selected_protein_ca_count": selected["protein_ca_count"],
            "selected_protein_atom_frame_count": selected["protein_atom_frame_count"],
            "selected_ligand_atom_frame_count": selected["ligand_atom_frame_count"],
            "selected_missing_exact_metric_fields": selected["missing_exact_metric_fields"],
            "searched_npz_candidate_count": len(inspected),
            "exact_metric_source_candidate_count": len(exact_candidates),
            "atomized_protein_candidate_count": len(atomized_protein_candidates),
            "ligand_atom_candidate_count": len(ligand_atom_candidates),
            "claim_grade_collection_input_candidate_count": len(collection_candidates),
            "best_candidate_npz": best["path"],
            "best_candidate_status": best["status"],
            "best_candidate_blockers": best["blockers"],
            "candidate_npz_paths": [item["path"] for item in inspected],
            "candidate_npz_statuses": [item["status"] for item in inspected],
            "recommended_next_local_action": _row_action(best, exact_candidates),
            **READ_ONLY_FLAGS,
        }
        rows.append(row)

    exact_ready_count = sum(1 for row in rows if int(row["exact_metric_source_candidate_count"]) > 0)
    collection_ready_count = sum(
        1 for row in rows if int(row["claim_grade_collection_input_candidate_count"]) > 0
    )
    atomized_protein_ready_count = sum(1 for row in rows if int(row["atomized_protein_candidate_count"]) > 0)
    ligand_atom_ready_count = sum(1 for row in rows if int(row["ligand_atom_candidate_count"]) > 0)
    selected_proxy_only_count = sum(1 for row in rows if row["selected_npz_status"] == "proxy_only_trajectory")
    partial_atomized_count = sum(
        1
        for row in rows
        if int(row["atomized_protein_candidate_count"]) > 0
        and int(row["ligand_atom_candidate_count"]) == 0
        and int(row["exact_metric_source_candidate_count"]) == 0
    )
    if rows and exact_ready_count == len(rows):
        status = "pocketmd_lite_claim_grade_metric_source_audit_ready"
    elif collection_ready_count:
        status = "blocked_pocketmd_lite_claim_grade_metric_source_collection_input_ready_metric_collection_needed"
    elif partial_atomized_count:
        status = "blocked_pocketmd_lite_claim_grade_metric_source_partial_atomized"
    elif ligand_atom_ready_count:
        status = "blocked_pocketmd_lite_claim_grade_metric_source_ligand_atom_only"
    elif rows:
        status = "blocked_pocketmd_lite_claim_grade_metric_source_proxy_only"
    else:
        status = "blocked_pocketmd_lite_claim_grade_metric_source_no_inputs"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_csv": _display(input_path),
        "probe_json": _display(probe_path),
        "probe_status": _text(probe_summary.get("status")),
        "candidate_count": len(rows),
        "searched_npz_candidate_count": sum(int(row["searched_npz_candidate_count"]) for row in rows),
        "exact_metric_source_ready_count": exact_ready_count,
        "claim_grade_collection_input_ready_count": collection_ready_count,
        "atomized_protein_source_candidate_count": atomized_protein_ready_count,
        "ligand_atom_source_candidate_count": ligand_atom_ready_count,
        "partial_atomized_protein_only_candidate_count": partial_atomized_count,
        "selected_proxy_only_count": selected_proxy_only_count,
        "missing_exact_metric_source_count": len(rows) - exact_ready_count,
        "search_roots": [_display(path) for path in roots],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Extract exact NPZ metric fields into the candidate fill preview, then rerun the PocketMD Lite report."
            if rows and exact_ready_count == len(rows)
            else "Run the claim-grade metric collector for recovered atomized top-k inputs; recover missing protein or ligand atom frames for rows not collection-ready."
            if collection_ready_count
            else "Recover ligand atom frames for partial atomized inputs and generate exact local-min/H-bond/initial-clash metrics for every selected top-k row."
            if partial_atomized_count
            else "Recover or generate protein atom frames for ligand-atom-only rows, then run the claim-grade metric collector for the selected top-k rows."
            if ligand_atom_ready_count
            else "Generate atomized protein and ligand frame inputs, then run the claim-grade metric collector for the selected top-k rows."
        ),
        **READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Claim-Grade Metric Source Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- exact_metric_source_ready_count: `{summary['exact_metric_source_ready_count']}`",
        f"- claim_grade_collection_input_ready_count: `{summary['claim_grade_collection_input_ready_count']}`",
        f"- atomized_protein_source_candidate_count: `{summary['atomized_protein_source_candidate_count']}`",
        f"- ligand_atom_source_candidate_count: `{summary['ligand_atom_source_candidate_count']}`",
        f"- selected_proxy_only_count: `{summary['selected_proxy_only_count']}`",
        "",
        "| entry | selected status | exact metric sources | atomized protein candidates | ligand atom candidates | action |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{status}` | {exact} | {protein} | {ligand} | `{action}` |".format(
                entry=row["entry_id"],
                status=row["selected_npz_status"],
                exact=row["exact_metric_source_candidate_count"],
                protein=row["atomized_protein_candidate_count"],
                ligand=row["ligand_atom_candidate_count"],
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--probe-json", default=DEFAULT_PROBE_JSON)
    parser.add_argument("--search-root", action="append", default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_claim_grade_metric_source_audit(
        input_csv=args.input_csv,
        probe_json=args.probe_json,
        search_roots=args.search_root,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
