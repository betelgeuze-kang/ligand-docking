#!/usr/bin/env python3
"""Build the PocketMD Lite remaining evidence queue.

Read-only: this tool does not run local-min, micro-MD, H-bond scoring,
docking, or external mutation. It joins the current top-k candidate CSV with
the local stage3 summary and records the exact inputs still needed to fill
PocketMD Lite's claim-grade refinement evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.pocketmd_lite_contract import TOPK_DEFAULT_THRESHOLD_PCT, is_refine_selected

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_STAGE3_JSON = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage3_summary.json"
)
DEFAULT_OUT_JSON = "runs/pocketmd_lite_remaining_evidence_queue_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_remaining_evidence_queue_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_remaining_evidence_queue_current.csv"
DEFAULT_TRAJECTORY_SEARCH_ROOTS = (
    "runs",
    "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs",
)

PACKET_TYPE = "pocketmd_lite_remaining_evidence_queue"
SCHEMA_VERSION = "pocketmd_lite_remaining_evidence_queue_v1"

REQUIRED_REFINEMENT_METRICS = (
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
)

REFRESH_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py && "
    "python3 tools/product/build_pocketmd_lite_report.py && "
    "python3 tools/product/build_pocketmd_lite_refinement_work_order.py && "
    "python3 tools/product/build_pocketmd_lite_remaining_evidence_queue.py"
)

CLAIM_BOUNDARY = (
    "PocketMD Lite remaining evidence queue only; it records missing top-k local-min, H-bond persistence, "
    "contact, and baseline/final clash-relief evidence plus available local input paths. It does not run "
    "local-min, micro-MD, H-bond scoring, docking, generate scientific results, promote a binding-affinity "
    "claim, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path: str | Path) -> str:
    text = _text(path)
    if not text:
        return ""
    path_obj = Path(text)
    if path_obj.is_absolute():
        try:
            return str(path_obj.relative_to(ROOT))
        except ValueError:
            return str(path_obj)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_present(value: Any) -> bool:
    return _text(value) != ""


def _num(value: Any) -> float | None:
    if not _is_present(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    text = _text(value).lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _path_exists(path_like: Any) -> bool:
    text = _text(path_like)
    if not text:
        return False
    try:
        path = Path(text)
        return path.exists() if path.is_absolute() else (ROOT / path).exists()
    except OSError:
        return False


def _alternate_trajectory_candidates(
    trajectory_npz: str,
    *,
    search_roots: list[str | Path],
    max_candidates: int = 5,
) -> list[str]:
    text = _text(trajectory_npz)
    if not text or _path_exists(text):
        return []
    basename = Path(text).name
    if not basename:
        return []
    found: list[str] = []
    for root_like in search_roots:
        root_text = _text(root_like)
        if not root_text:
            continue
        root = _resolve(root_text)
        if not root.exists() or not root.is_dir():
            continue
        try:
            matches = sorted(root.rglob(basename))
        except (OSError, PermissionError):
            continue
        for match in matches:
            if not match.is_file():
                continue
            display = _display(match)
            if display not in found:
                found.append(display)
            if len(found) >= max_candidates:
                return found
    return found


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _split_entry_id(entry_id: str) -> tuple[str, str]:
    target, sep, ligand = _text(entry_id).partition(":")
    return _text(target), _text(ligand) if sep else ""


def _entry_id(row: dict[str, Any]) -> str:
    entry = _text(row.get("entry_id"))
    if entry:
        return entry
    target = _text(row.get("target"))
    ligand = _text(row.get("ligand_id"))
    return f"{target}:{ligand}" if target and ligand else ""


def _stage3_row_score(row: dict[str, Any]) -> int:
    keys = (
        "trajectory_npz",
        "protein_structure_source_path",
        "ligand_smiles",
        "frame_contact_presence_fraction",
        "clash_count_mean_per_frame",
        "clash_frame_fraction",
        "backmapped_pdb",
        "score_json",
    )
    return sum(1 for key in keys if _is_present(row.get(key)))


def _stage3_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            target = _text(obj.get("target"))
            ligand = _text(obj.get("ligand_id"))
            if target and ligand:
                key = f"{target}:{ligand}"
                current = lookup.get(key)
                if current is None or _stage3_row_score(obj) >= _stage3_row_score(current):
                    lookup[key] = obj
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return lookup


def _selected_for_refine(row: dict[str, Any], *, target: str) -> bool:
    explicit = _bool(row.get("selected_for_refine"))
    if explicit is not None:
        return explicit
    return is_refine_selected(
        family=_text(row.get("family")) or target,
        rank_pct=_num(row.get("rank_pct")),
        top_k_threshold_pct=TOPK_DEFAULT_THRESHOLD_PCT,
    )


def _metric_value(candidate: dict[str, Any], stage3: dict[str, Any], metric: str) -> Any:
    if _is_present(candidate.get(metric)):
        return candidate.get(metric)
    if metric == "initial_clash_count":
        for key in (
            "pre_refine_clash_count",
            "baseline_clash_count",
            "pre_local_min_clash_count",
            "pre_refinement_clash_count",
            "clash_count_before",
        ):
            if _is_present(candidate.get(key)):
                return candidate.get(key)
            if _is_present(stage3.get(key)):
                return stage3.get(key)
    if metric == "contact_persistence":
        return stage3.get("frame_contact_presence_fraction")
    if metric == "clash_count":
        clash_mean = _num(stage3.get("clash_count_mean_per_frame"))
        clash_frame = _num(stage3.get("clash_frame_fraction"))
        if clash_mean == 0.0 and clash_frame == 0.0:
            return 0
    return stage3.get(metric)


def _missing_metrics(candidate: dict[str, Any], stage3: dict[str, Any], selected: bool) -> list[str]:
    if not selected:
        return []
    return [
        metric
        for metric in REQUIRED_REFINEMENT_METRICS
        if not _is_present(_metric_value(candidate, stage3, metric))
    ]


def build_pocketmd_lite_remaining_evidence_queue(
    *,
    candidate_csv: str | Path = DEFAULT_CANDIDATE_CSV,
    stage3_json: str | Path = DEFAULT_STAGE3_JSON,
    trajectory_search_roots: list[str | Path] | None = None,
) -> dict[str, Any]:
    candidate_path = _resolve(candidate_csv)
    stage3_path = _resolve(stage3_json)
    trajectory_roots = list(trajectory_search_roots or DEFAULT_TRAJECTORY_SEARCH_ROOTS)
    fieldnames, candidates = _read_csv(candidate_path)
    stage3_payload = _read_json(stage3_path)
    stage3_rows = _stage3_lookup(stage3_payload)
    rows: list[dict[str, Any]] = []

    materializer_status = "materialized"
    blockers: list[str] = []
    if not candidate_path.exists():
        materializer_status = "blocked_missing_candidate_csv"
        blockers.append("candidate_csv_missing")
    elif "entry_id" not in fieldnames:
        materializer_status = "blocked_candidate_csv_missing_entry_id"
        blockers.append("candidate_csv_missing_entry_id")
    if not stage3_path.exists():
        blockers.append("stage3_json_missing")

    for candidate in candidates:
        entry_id = _entry_id(candidate)
        target, ligand = _split_entry_id(entry_id)
        stage3 = stage3_rows.get(entry_id, {})
        selected = _selected_for_refine(candidate, target=target)
        missing = _missing_metrics(candidate, stage3, selected)

        trajectory_npz = _text(stage3.get("trajectory_npz"))
        trajectory_available = _path_exists(trajectory_npz)
        alternate_trajectories = _alternate_trajectory_candidates(
            trajectory_npz,
            search_roots=trajectory_roots,
        )
        protein_path = _text(stage3.get("protein_structure_source_path"))
        backmapped_pdb = _text(stage3.get("backmapped_pdb"))
        score_json = _text(stage3.get("score_json"))
        ligand_smiles = _text(stage3.get("ligand_smiles"))
        row_blockers = list(missing)
        if selected and trajectory_npz and not trajectory_available:
            row_blockers.append("trajectory_npz_unavailable")
        if selected and not trajectory_npz:
            row_blockers.append("trajectory_npz_missing")
        if selected and protein_path and not _path_exists(protein_path):
            row_blockers.append("protein_structure_source_path_unavailable")
        if selected and not protein_path:
            row_blockers.append("protein_structure_source_path_missing")
        if selected and not ligand_smiles:
            row_blockers.append("ligand_smiles_missing")

        rows.append(
            {
                "entry_id": entry_id,
                "target": target,
                "ligand_id": ligand,
                "selected_for_refine": selected,
                "stage3_row_present": bool(stage3),
                "missing_metrics": ";".join(missing),
                "remaining_metric_count": len(missing),
                "local_min_ligand_rmsd_a": _metric_value(candidate, stage3, "local_min_ligand_rmsd_a"),
                "hbond_persistence": _metric_value(candidate, stage3, "hbond_persistence"),
                "contact_persistence": _metric_value(candidate, stage3, "contact_persistence"),
                "initial_clash_count": _metric_value(candidate, stage3, "initial_clash_count"),
                "clash_count": _metric_value(candidate, stage3, "clash_count"),
                "trajectory_npz": _display(trajectory_npz),
                "trajectory_npz_available": trajectory_available,
                "alternate_trajectory_npz_candidates": ";".join(alternate_trajectories),
                "alternate_trajectory_npz_candidate_count": len(alternate_trajectories),
                "protein_structure_source_path": _display(protein_path),
                "protein_structure_source_path_available": _path_exists(protein_path),
                "backmapped_pdb": _display(backmapped_pdb),
                "backmapped_pdb_available": _path_exists(backmapped_pdb),
                "score_json": _display(score_json),
                "score_json_available": _path_exists(score_json),
                "ligand_smiles": ligand_smiles,
                "ligand_smiles_present": bool(ligand_smiles),
                "hbond_confidence_source": stage3.get("hbond_confidence"),
                "local_min_required_input": _display(trajectory_npz),
                "hbond_required_input": ";".join(
                    item
                    for item in (
                        _display(trajectory_npz),
                        _display(protein_path),
                        "ligand_smiles" if ligand_smiles else "",
                    )
                    if item
                ),
                "recommended_next_local_action": (
                    "restore_or_mount_trajectory_npz_and_collect_pocketmd_lite_top_k_local_min_hbond_clash_relief_evidence"
                    if missing
                    else "rerun_pocketmd_lite_report_and_review_band"
                ),
                "blockers": ";".join(row_blockers),
                **_READ_ONLY_FLAGS,
            }
        )

    selected_rows = [row for row in rows if row["selected_for_refine"]]
    remaining_rows = [row for row in selected_rows if row["missing_metrics"]]
    remaining_metric_count = sum(int(row["remaining_metric_count"]) for row in remaining_rows)
    missing_metric_names = sorted(
        {metric for row in remaining_rows for metric in _text(row["missing_metrics"]).split(";") if metric}
    )
    trajectory_unavailable_count = sum(
        1 for row in selected_rows if row["trajectory_npz"] and not row["trajectory_npz_available"]
    )
    alternate_trajectory_candidate_count = sum(
        int(row["alternate_trajectory_npz_candidate_count"]) for row in selected_rows
    )
    candidates_with_alternate_trajectory_count = sum(
        1 for row in selected_rows if int(row["alternate_trajectory_npz_candidate_count"]) > 0
    )
    protein_unavailable_count = sum(
        1 for row in selected_rows if row["protein_structure_source_path"] and not row["protein_structure_source_path_available"]
    )
    stage3_matched_count = sum(1 for row in rows if row["stage3_row_present"])
    contact_clash_ready_count = sum(
        1
        for row in selected_rows
        if _is_present(row["contact_persistence"]) and _is_present(row["clash_count"])
    )
    clash_relief_baseline_ready_count = sum(
        1
        for row in selected_rows
        if _is_present(row["initial_clash_count"])
    )

    if materializer_status != "materialized":
        status = "blocked_pocketmd_lite_remaining_evidence_queue_materialization"
    elif remaining_rows:
        status = "blocked_pocketmd_lite_remaining_evidence_queue"
    else:
        status = "pocketmd_lite_remaining_evidence_queue_ready"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "materializer_status": materializer_status,
        "candidate_count": len(rows),
        "selected_top_k_count": len(selected_rows),
        "stage3_matched_candidate_count": stage3_matched_count,
        "contact_clash_ready_count": contact_clash_ready_count,
        "clash_relief_baseline_ready_count": clash_relief_baseline_ready_count,
        "remaining_candidate_count": len(remaining_rows),
        "remaining_metric_count": remaining_metric_count,
        "missing_metric_names": missing_metric_names,
        "trajectory_npz_unavailable_count": trajectory_unavailable_count,
        "alternate_trajectory_npz_candidate_count": alternate_trajectory_candidate_count,
        "candidates_with_alternate_trajectory_count": candidates_with_alternate_trajectory_count,
        "protein_structure_source_path_unavailable_count": protein_unavailable_count,
        "candidate_csv": _display(candidate_path),
        "stage3_json": _display(stage3_path),
        "trajectory_search_roots": [_display(root) for root in trajectory_roots],
        "refresh_command_after_fill": REFRESH_COMMAND,
        "next_required_step": (
            "Supply PocketMD Lite top-k missing evidence: "
            + ", ".join(missing_metric_names)
            + "; restore unavailable trajectory NPZ inputs when needed; then rerun refresh_command_after_fill."
            if missing_metric_names
            else "PocketMD Lite required evidence fields are present; rerun the report and review uncertainty bands."
        ),
        "top_k_only_policy_enforced": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "blockers": blockers,
        **_READ_ONLY_FLAGS,
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
    return str(value)


_CSV_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "selected_for_refine",
    "stage3_row_present",
    "missing_metrics",
    "remaining_metric_count",
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
    "trajectory_npz",
    "trajectory_npz_available",
    "alternate_trajectory_npz_candidates",
    "alternate_trajectory_npz_candidate_count",
    "protein_structure_source_path",
    "protein_structure_source_path_available",
    "backmapped_pdb",
    "backmapped_pdb_available",
    "score_json",
    "score_json_available",
    "ligand_smiles",
    "ligand_smiles_present",
    "hbond_confidence_source",
    "local_min_required_input",
    "hbond_required_input",
    "recommended_next_local_action",
    "blockers",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Remaining Evidence Queue (current)",
        "",
        "Read-only queue for top-k PocketMD Lite evidence collection.",
        "",
        f"- status: `{summary['status']}`",
        f"- materializer_status: `{summary['materializer_status']}`",
        f"- selected_top_k_count: `{summary['selected_top_k_count']}`",
        f"- contact_clash_ready_count: `{summary['contact_clash_ready_count']}`",
        f"- clash_relief_baseline_ready_count: `{summary['clash_relief_baseline_ready_count']}`",
        f"- remaining_candidate_count: `{summary['remaining_candidate_count']}`",
        f"- remaining_metric_count: `{summary['remaining_metric_count']}`",
        f"- missing_metric_names: `{', '.join(summary['missing_metric_names'])}`",
        f"- trajectory_npz_unavailable_count: `{summary['trajectory_npz_unavailable_count']}`",
        f"- candidates_with_alternate_trajectory_count: `{summary['candidates_with_alternate_trajectory_count']}`",
        f"- alternate_trajectory_npz_candidate_count: `{summary['alternate_trajectory_npz_candidate_count']}`",
        f"- refresh_command_after_fill: `{summary['refresh_command_after_fill']}`",
        "",
        "## Rows",
        "",
        "| entry | missing metrics | trajectory | alternates | protein | action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{missing}` | `{traj}` | `{alternates}` | `{protein}` | `{action}` |".format(
                entry=row["entry_id"],
                missing=row["missing_metrics"] or "(none)",
                traj="available" if row["trajectory_npz_available"] else "missing",
                alternates=row["alternate_trajectory_npz_candidate_count"],
                protein="available" if row["protein_structure_source_path_available"] else "missing",
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PocketMD Lite remaining evidence queue.")
    parser.add_argument("--candidate-csv", default=DEFAULT_CANDIDATE_CSV)
    parser.add_argument("--stage3-json", default=DEFAULT_STAGE3_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument(
        "--trajectory-search-root",
        action="append",
        default=None,
        help="Optional local roots to scan for same-basename trajectory NPZ restore candidates.",
    )
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_remaining_evidence_queue(
        candidate_csv=args.candidate_csv,
        stage3_json=args.stage3_json,
        trajectory_search_roots=args.trajectory_search_root,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    for path in (out_json, out_md, out_csv):
        path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out_json, payload)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
