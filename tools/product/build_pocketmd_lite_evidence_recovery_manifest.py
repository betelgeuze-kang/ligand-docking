#!/usr/bin/env python3
"""Build the PocketMD Lite evidence recovery manifest.

This is a read-only schema/evidence inspection layer over the remaining
evidence queue. It can identify exact trajectory NPZs that already contain
claim-grade local-min/H-bond metric fields, and it can distinguish readable
alternate trajectory bundles from claim-grade refinement evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REMAINING_QUEUE_JSON = "runs/pocketmd_lite_remaining_evidence_queue_current.json"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_evidence_recovery_manifest_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_evidence_recovery_manifest_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_evidence_recovery_manifest_current.csv"
DEFAULT_RESTORE_SEARCH_ROOTS = ("~/.local/share/Trash/files",)
MAX_RESTORE_CANDIDATES_PER_ROW = 8

PACKET_TYPE = "pocketmd_lite_evidence_recovery_manifest"
SCHEMA_VERSION = "pocketmd_lite_evidence_recovery_manifest_v1"

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
HBOND_FRAME_KEYS = (
    "hbond_frame_mask",
    "hbond_presence_by_frame",
)
TRAJECTORY_SCHEMA_KEYS = ("protein_ca", "ligand_frames", "frame_indices")

CLAIM_BOUNDARY = (
    "PocketMD Lite evidence recovery manifest only; it inspects local remaining-evidence queue paths and NPZ "
    "schemas for exact claim-grade local-min/H-bond metric fields. Readable trajectory bundles without those "
    "fields are recorded as proxy-only restore candidates. It does not run local-min, micro-MD, H-bond scoring, "
    "docking, generate new scientific metrics, promote claims, copy files, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "entry_id",
    "missing_metrics",
    "trajectory_npz",
    "exact_npz_status",
    "exact_npz_schema_ready",
    "exact_npz_claim_grade_metric_source_ready",
    "exact_local_min_ligand_rmsd_a",
    "exact_hbond_persistence",
    "exact_npz_reason",
    "alternate_npz_candidate_count",
    "alternate_npz_readable_count",
    "alternate_npz_schema_ready_count",
    "alternate_npz_proxy_only_count",
    "alternate_npz_claim_grade_metric_field_count",
    "first_alternate_npz",
    "first_alternate_npz_status",
    "first_alternate_npz_reason",
    "exact_basename_restore_candidate_count",
    "exact_basename_restore_readable_count",
    "exact_basename_restore_proxy_only_count",
    "exact_basename_restore_claim_grade_metric_field_count",
    "first_exact_basename_restore_npz",
    "first_exact_basename_restore_npz_status",
    "first_exact_basename_restore_npz_reason",
    "recommended_next_local_action",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _split_semicolon(value: Any) -> list[str]:
    return [item for item in (_text(value).split(";")) if item]


def _restore_search_roots(values: list[str | Path] | tuple[str | Path, ...] | None) -> list[Path]:
    roots = values if values is not None else DEFAULT_RESTORE_SEARCH_ROOTS
    deduped: list[Path] = []
    for value in roots:
        text = _text(value)
        if not text:
            continue
        path = _resolve(text)
        if path not in deduped:
            deduped.append(path)
    return deduped


def _find_exact_basename_restore_candidates(
    trajectory_npz: Any,
    *,
    restore_search_roots: list[Path],
) -> list[str]:
    text = _text(trajectory_npz)
    if not text:
        return []
    basename = Path(text).name
    if not basename:
        return []
    candidates: list[str] = []
    for root in restore_search_roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            matches = root.rglob(basename)
        except OSError:
            continue
        for match in matches:
            try:
                if not match.is_file():
                    continue
            except OSError:
                continue
            display = _display(match)
            if display not in candidates:
                candidates.append(display)
            if len(candidates) >= MAX_RESTORE_CANDIDATES_PER_ROW:
                return candidates
    return candidates


def _scalar_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _npz_scalar(data: Any, keys: tuple[str, ...]) -> tuple[str, float | None]:
    for key in keys:
        if key not in data.files:
            continue
        try:
            arr = data[key]
            value = arr.item() if getattr(arr, "shape", ()) == () else arr.reshape(-1)[0]
        except Exception:
            return key, None
        return key, _scalar_float(value)
    return "", None


def _hbond_from_frames(data: Any) -> tuple[str, float | None]:
    for key in HBOND_FRAME_KEYS:
        if key not in data.files:
            continue
        try:
            import numpy as np

            arr = np.asarray(data[key], dtype=float)
            if arr.size == 0:
                return key, None
            finite = arr[np.isfinite(arr)]
            if finite.size == 0:
                return key, None
            return key, float(np.mean(finite > 0.0))
        except Exception:
            return key, None
    return "", None


def _inspect_npz(path_like: Any) -> dict[str, Any]:
    text = _text(path_like)
    path = _resolve(text) if text else Path("")
    base: dict[str, Any] = {
        "path": _display(text),
        "exists": bool(text and path.exists()),
        "readable": False,
        "schema_ready": False,
        "claim_grade_metric_source_ready": False,
        "local_min_metric_present": False,
        "hbond_metric_present": False,
        "local_min_ligand_rmsd_a": None,
        "hbond_persistence": None,
        "local_min_source_key": "",
        "hbond_source_key": "",
        "frame_count": 0,
        "ligand_bead_count": 0,
        "protein_ca_count": 0,
        "keys": [],
        "status": "missing" if text else "not_requested",
        "reason": "npz_path_missing" if not text else "npz_missing",
    }
    if not text or not path.exists():
        return base
    try:
        import numpy as np

        with np.load(str(path), allow_pickle=False) as data:
            keys = list(data.files)
            base["keys"] = keys
            ligand_frames = np.asarray(data["ligand_frames"]) if "ligand_frames" in keys else None
            protein_ca = np.asarray(data["protein_ca"]) if "protein_ca" in keys else None
            schema_ready = (
                all(key in keys for key in TRAJECTORY_SCHEMA_KEYS)
                and ligand_frames is not None
                and protein_ca is not None
                and ligand_frames.ndim == 3
                and ligand_frames.shape[0] > 0
                and ligand_frames.shape[1] > 0
                and ligand_frames.shape[2] == 3
                and protein_ca.ndim == 2
                and protein_ca.shape[0] > 0
                and protein_ca.shape[1] == 3
            )
            local_key, local_value = _npz_scalar(data, LOCAL_MIN_KEYS)
            hbond_key, hbond_value = _npz_scalar(data, HBOND_KEYS)
            if hbond_value is None:
                hbond_key, hbond_value = _hbond_from_frames(data)
            local_present = local_value is not None
            hbond_present = hbond_value is not None
            base.update(
                {
                    "readable": True,
                    "schema_ready": bool(schema_ready),
                    "local_min_metric_present": local_present,
                    "hbond_metric_present": hbond_present,
                    "local_min_ligand_rmsd_a": local_value,
                    "hbond_persistence": hbond_value,
                    "local_min_source_key": local_key,
                    "hbond_source_key": hbond_key,
                    "frame_count": int(ligand_frames.shape[0]) if ligand_frames is not None and ligand_frames.ndim >= 1 else 0,
                    "ligand_bead_count": (
                        int(ligand_frames.shape[1]) if ligand_frames is not None and ligand_frames.ndim >= 2 else 0
                    ),
                    "protein_ca_count": int(protein_ca.shape[0]) if protein_ca is not None and protein_ca.ndim >= 1 else 0,
                }
            )
    except Exception as exc:
        base.update(
            {
                "status": "unreadable",
                "reason": f"npz_unreadable:{type(exc).__name__}",
            }
        )
        return base

    base["claim_grade_metric_source_ready"] = bool(
        base["schema_ready"] and base["local_min_metric_present"] and base["hbond_metric_present"]
    )
    if base["claim_grade_metric_source_ready"]:
        base["status"] = "claim_grade_metric_source_ready"
        base["reason"] = "exact_metric_fields_present"
    elif base["schema_ready"]:
        base["status"] = "proxy_only_trajectory_schema"
        base["reason"] = "trajectory_schema_readable_but_missing_claim_grade_local_min_hbond_fields"
    else:
        base["status"] = "schema_incomplete"
        base["reason"] = "trajectory_schema_missing_required_fields"
    return base


def _row_action(
    exact: dict[str, Any],
    alternate_summaries: list[dict[str, Any]],
    restore_summaries: list[dict[str, Any]],
) -> str:
    if exact["claim_grade_metric_source_ready"]:
        return "extract_claim_grade_metrics_from_exact_trajectory_npz_then_rerun_pocketmd_lite_report"
    if exact["exists"] and exact["readable"]:
        return "run_pocketmd_lite_local_min_hbond_collection_for_exact_trajectory_npz"
    if any(item["claim_grade_metric_source_ready"] for item in restore_summaries):
        return "restore_exact_basename_claim_grade_metric_npz_then_extract_metrics"
    if restore_summaries:
        return "restore_exact_basename_trajectory_candidate_then_collect_local_min_hbond"
    if alternate_summaries:
        return "restore_exact_current_trajectory_or_rerun_pocketmd_lite_local_min_hbond_collection"
    return "restore_or_regenerate_missing_current_trajectory_npz_then_collect_local_min_hbond"


def build_pocketmd_lite_evidence_recovery_manifest(
    *,
    remaining_queue_json: str | Path = DEFAULT_REMAINING_QUEUE_JSON,
    restore_search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    queue_path = _resolve(remaining_queue_json)
    queue_payload = _read_json(queue_path)
    queue_summary = queue_payload.get("summary") if isinstance(queue_payload.get("summary"), dict) else {}
    queue_rows = [row for row in queue_payload.get("rows", []) or [] if isinstance(row, dict)]
    restore_roots = _restore_search_roots(restore_search_roots)
    rows: list[dict[str, Any]] = []

    for queue_row in queue_rows:
        exact = _inspect_npz(queue_row.get("trajectory_npz"))
        alternate_paths = _split_semicolon(queue_row.get("alternate_trajectory_npz_candidates"))
        alternates = [_inspect_npz(path) for path in alternate_paths]
        restore_paths = _find_exact_basename_restore_candidates(
            queue_row.get("trajectory_npz"),
            restore_search_roots=restore_roots,
        )
        restore_candidates = [_inspect_npz(path) for path in restore_paths]
        readable_alternates = [item for item in alternates if item["readable"]]
        schema_ready_alternates = [item for item in alternates if item["schema_ready"]]
        proxy_only_alternates = [
            item
            for item in alternates
            if item["schema_ready"] and not item["claim_grade_metric_source_ready"]
        ]
        metric_field_alternates = [item for item in alternates if item["claim_grade_metric_source_ready"]]
        readable_restores = [item for item in restore_candidates if item["readable"]]
        proxy_only_restores = [
            item
            for item in restore_candidates
            if item["schema_ready"] and not item["claim_grade_metric_source_ready"]
        ]
        metric_field_restores = [item for item in restore_candidates if item["claim_grade_metric_source_ready"]]
        first_alt = alternates[0] if alternates else {}
        first_restore = restore_candidates[0] if restore_candidates else {}
        row = {
            "entry_id": _text(queue_row.get("entry_id")),
            "missing_metrics": _text(queue_row.get("missing_metrics")),
            "trajectory_npz": exact["path"],
            "exact_npz_status": exact["status"],
            "exact_npz_schema_ready": exact["schema_ready"],
            "exact_npz_claim_grade_metric_source_ready": exact["claim_grade_metric_source_ready"],
            "exact_local_min_ligand_rmsd_a": exact["local_min_ligand_rmsd_a"],
            "exact_hbond_persistence": exact["hbond_persistence"],
            "exact_npz_reason": exact["reason"],
            "alternate_npz_candidate_count": len(alternates),
            "alternate_npz_readable_count": len(readable_alternates),
            "alternate_npz_schema_ready_count": len(schema_ready_alternates),
            "alternate_npz_proxy_only_count": len(proxy_only_alternates),
            "alternate_npz_claim_grade_metric_field_count": len(metric_field_alternates),
            "first_alternate_npz": first_alt.get("path", ""),
            "first_alternate_npz_status": first_alt.get("status", ""),
            "first_alternate_npz_reason": first_alt.get("reason", ""),
            "exact_basename_restore_candidate_count": len(restore_candidates),
            "exact_basename_restore_readable_count": len(readable_restores),
            "exact_basename_restore_proxy_only_count": len(proxy_only_restores),
            "exact_basename_restore_claim_grade_metric_field_count": len(metric_field_restores),
            "first_exact_basename_restore_npz": first_restore.get("path", ""),
            "first_exact_basename_restore_npz_status": first_restore.get("status", ""),
            "first_exact_basename_restore_npz_reason": first_restore.get("reason", ""),
            "recommended_next_local_action": _row_action(exact, alternates, restore_candidates),
            "exact_npz_keys": ";".join(exact["keys"]),
            "alternate_npz_paths": ";".join(item["path"] for item in alternates),
            "exact_basename_restore_npz_paths": ";".join(item["path"] for item in restore_candidates),
            **_READ_ONLY_FLAGS,
        }
        rows.append(row)

    remaining_rows = [row for row in rows if row["missing_metrics"]]
    exact_ready_rows = [row for row in remaining_rows if row["exact_npz_claim_grade_metric_source_ready"]]
    alternate_candidate_count = sum(int(row["alternate_npz_candidate_count"]) for row in rows)
    alternate_readable_count = sum(int(row["alternate_npz_readable_count"]) for row in rows)
    alternate_proxy_only_count = sum(int(row["alternate_npz_proxy_only_count"]) for row in rows)
    restore_candidate_count = sum(int(row["exact_basename_restore_candidate_count"]) for row in rows)
    restore_readable_count = sum(int(row["exact_basename_restore_readable_count"]) for row in rows)
    restore_proxy_only_count = sum(int(row["exact_basename_restore_proxy_only_count"]) for row in rows)
    restore_metric_field_count = sum(int(row["exact_basename_restore_claim_grade_metric_field_count"]) for row in rows)
    exact_available_count = sum(1 for row in rows if row["exact_npz_status"] != "missing")
    exact_missing_count = sum(1 for row in rows if row["exact_npz_status"] == "missing")
    ready = bool(remaining_rows) and len(exact_ready_rows) == len(remaining_rows)
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "pocketmd_lite_evidence_recovery_manifest_ready"
            if ready
            else "blocked_pocketmd_lite_evidence_recovery_manifest"
        ),
        "materializer_status": "materialized" if queue_path.exists() else "blocked_missing_remaining_queue_json",
        "remaining_queue_json": _display(queue_path),
        "queue_status": _text(queue_summary.get("status")),
        "candidate_count": len(rows),
        "remaining_candidate_count": len(remaining_rows),
        "remaining_metric_count": sum(len(_split_semicolon(row["missing_metrics"])) for row in remaining_rows),
        "exact_trajectory_available_count": exact_available_count,
        "exact_trajectory_missing_count": exact_missing_count,
        "exact_claim_grade_metric_source_ready_count": len(exact_ready_rows),
        "alternate_npz_candidate_count": alternate_candidate_count,
        "alternate_npz_readable_count": alternate_readable_count,
        "alternate_npz_proxy_only_count": alternate_proxy_only_count,
        "exact_basename_restore_candidate_count": restore_candidate_count,
        "exact_basename_restore_readable_count": restore_readable_count,
        "exact_basename_restore_proxy_only_count": restore_proxy_only_count,
        "exact_basename_restore_claim_grade_metric_field_count": restore_metric_field_count,
        "restore_search_roots": [_display(path) for path in restore_roots],
        "candidates_with_readable_alternate_count": sum(
            1 for row in rows if int(row["alternate_npz_readable_count"]) > 0
        ),
        "candidates_with_readable_exact_basename_restore_count": sum(
            1 for row in rows if int(row["exact_basename_restore_readable_count"]) > 0
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Extract exact NPZ metric fields into the PocketMD Lite candidate CSV, then rerun the report."
            if ready
            else "Restore the exact current top-k trajectory NPZs or rerun PocketMD Lite local-min/H-bond collection; readable alternates/restores are proxy-only unless they contain exact claim-grade metric fields."
        ),
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Evidence Recovery Manifest",
        "",
        "Read-only inspection of exact and alternate PocketMD Lite trajectory evidence.",
        "",
        f"- status: `{summary['status']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- remaining_candidate_count: `{summary['remaining_candidate_count']}`",
        f"- remaining_metric_count: `{summary['remaining_metric_count']}`",
        f"- exact_trajectory_missing_count: `{summary['exact_trajectory_missing_count']}`",
        f"- exact_claim_grade_metric_source_ready_count: `{summary['exact_claim_grade_metric_source_ready_count']}`",
        f"- alternate_npz_readable_count: `{summary['alternate_npz_readable_count']}`",
        f"- alternate_npz_proxy_only_count: `{summary['alternate_npz_proxy_only_count']}`",
        f"- exact_basename_restore_readable_count: `{summary['exact_basename_restore_readable_count']}`",
        f"- exact_basename_restore_proxy_only_count: `{summary['exact_basename_restore_proxy_only_count']}`",
        "",
        "| entry | exact status | exact metric source | readable alternates | readable restores | action |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{exact_status}` | `{exact_metric}` | {alt_readable} | {restore_readable} | `{action}` |".format(
                entry=row["entry_id"],
                exact_status=row["exact_npz_status"],
                exact_metric=str(row["exact_npz_claim_grade_metric_source_ready"]).lower(),
                alt_readable=row["alternate_npz_readable_count"],
                restore_readable=row["exact_basename_restore_readable_count"],
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PocketMD Lite evidence recovery manifest.")
    parser.add_argument("--remaining-queue-json", default=DEFAULT_REMAINING_QUEUE_JSON)
    parser.add_argument(
        "--restore-search-root",
        action="append",
        default=None,
        help="Optional read-only root to search for missing exact trajectory basenames.",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_evidence_recovery_manifest(
        remaining_queue_json=args.remaining_queue_json,
        restore_search_roots=args.restore_search_root,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
