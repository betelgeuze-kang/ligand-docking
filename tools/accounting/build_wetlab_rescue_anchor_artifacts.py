#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_STAGE6_FAILURE_SURFACE_JSON = "runs/wetlab_primary_stage6_failure_surface_current.json"
DEFAULT_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_OUT_MD = "runs/wetlab_rescue_anchor_artifacts_current.md"
DEFAULT_TOP_N = 32


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
    except Exception:
        return default


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if (not str(path).strip()) or (not path.exists()) or path.is_dir():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _ligand_centroid(row: dict[str, Any]) -> tuple[float, float, float] | None:
    coords = []
    for prefix in ("ligand_bead0", "ligand_bead1", "ligand_bead2"):
        x = _safe_float(row.get(f"{prefix}_x"))
        y = _safe_float(row.get(f"{prefix}_y"))
        z = _safe_float(row.get(f"{prefix}_z"))
        if any(abs(v) > 1e-12 for v in (x, y, z)):
            coords.append((x, y, z))
    if not coords:
        return None
    return (
        round(sum(v[0] for v in coords) / len(coords), 6),
        round(sum(v[1] for v in coords) / len(coords), 6),
        round(sum(v[2] for v in coords) / len(coords), 6),
    )


def _target_specific_pocket_override(
    target_id: str,
    queue_rows: list[dict[str, Any]],
    stage3_rows: list[dict[str, Any]],
    *,
    top_n: int,
) -> tuple[float, float, float, str] | None:
    if "T. cruzi PDE" not in target_id:
        return None
    queue_by_ligand = {
        _text(row.get("ligand_id")): row
        for row in queue_rows
        if _text(row.get("ligand_id"))
    }
    ranked_stage3 = sorted(
        stage3_rows,
        key=lambda row: (
            _safe_float(row.get("binding_energy_proxy"), 0.0),
            -_safe_float(row.get("stability_score"), 0.0),
            _text(row.get("ligand_id")),
        ),
    )
    centroids: list[tuple[float, float, float]] = []
    for row in ranked_stage3[: max(1, min(int(top_n), 8))]:
        ligand_id = _text(row.get("ligand_id"))
        queue_row = queue_by_ligand.get(ligand_id)
        if not queue_row:
            continue
        centroid = _ligand_centroid(queue_row)
        if centroid is None:
            continue
        centroids.append(centroid)
    if not centroids:
        return None
    pocket_x = round(sum(v[0] for v in centroids) / len(centroids), 6)
    pocket_y = round(sum(v[1] for v in centroids) / len(centroids), 6)
    pocket_z = round(sum(v[2] for v in centroids) / len(centroids), 6)
    return pocket_x, pocket_y, pocket_z, "stage3_top_ligand_centroid_proxy"


def _summary_payload(summary_json: str) -> dict[str, Any]:
    path = Path(summary_json)
    if (not str(path).strip()) or (not path.exists()) or path.is_dir():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _artifact_path(summary_payload: dict[str, Any], summary_json: str, artifact_key: str, fallback_name: str) -> Path:
    artifacts = dict(summary_payload.get("artifacts", {}) or {})
    artifact_text = _text(artifacts.get(artifact_key))
    if artifact_text:
        return Path(artifact_text)
    shard_dir = Path(summary_json).parent
    candidate = shard_dir / fallback_name
    if candidate.exists():
        return candidate
    return candidate


def _resolve_stage3_scores_csv(summary_json: str, summary_payload: dict[str, Any]) -> Path:
    for candidate in [
        _artifact_path(summary_payload, summary_json, "stage3_scores_csv", "throughput_run_stage3_scores.csv"),
        Path(summary_json).parent / "throughput_run_gate45_stage3_scores.csv",
        Path(summary_json).parent / "throughput_run_gate51_stage3_scores.csv",
        Path(summary_json).parent / "throughput_run_gate55_stage3_scores.csv",
    ]:
        if candidate.exists():
            return candidate
    return Path("/__missing_stage3_scores_csv__")


def _resolve_rescue_lane_payload(
    rescue_lane_payload: dict[str, Any],
    *,
    rescue_lane_json: str = DEFAULT_RESCUE_LANE_JSON,
    stage6_failure_surface_json: str = DEFAULT_STAGE6_FAILURE_SURFACE_JSON,
    retry_policy_templates_json: str = DEFAULT_RETRY_POLICY_TEMPLATES_JSON,
) -> dict[str, Any]:
    if rescue_lane_payload.get("rows", []) or []:
        return rescue_lane_payload
    lane_payload = load_json(rescue_lane_json)
    if lane_payload.get("rows", []) or []:
        return lane_payload
    from tools import build_wetlab_hard_target_rescue_lane as rescue_lane_mod

    return rescue_lane_mod.build_payload(
        load_json(stage6_failure_surface_json),
        load_json(retry_policy_templates_json),
    )


def build_payload(
    rescue_lane_payload: dict[str, Any],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    summary = dict(rescue_lane_payload.get("summary", {}) or {})
    focus_target_id = _text(summary.get("target_id")) or _text(summary.get("focus_target_id"))
    focus_shard_id = _text(summary.get("shard_id")) or _text(summary.get("focus_shard_id"))
    focus_row = {}
    for row in rescue_lane_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) == focus_target_id and _text(candidate.get("shard_id")) == focus_shard_id:
            focus_row = candidate
            break

    if not focus_row:
        return {
            "summary": {
                "status": "wetlab_rescue_anchor_artifacts_ready",
                "focus_target_id": "",
                "focus_shard_id": "",
                "ready_for_rescue": False,
                "next_required_step": "No hard-target rescue candidate is currently selected, so rescue anchor artifacts were not materialized.",
            },
            "rows": [],
        }

    target_id = _text(focus_row.get("target_id"))
    shard_id = _text(focus_row.get("shard_id"))
    target_slug = _text(focus_row.get("target_slug")) or slug(target_id)
    summary_json = _text(focus_row.get("summary_json"))
    summary_payload = _summary_payload(summary_json)
    queue_csv = _artifact_path(summary_payload, summary_json, "queue_csv", "throughput_run_stage1_queue.csv")
    stage3_scores_csv = _resolve_stage3_scores_csv(summary_json, summary_payload)
    queue_rows = _read_csv_rows(queue_csv)
    stage3_rows = _read_csv_rows(stage3_scores_csv)

    pocket_x = round(sum(_safe_float(row.get("pocket_x")) for row in queue_rows) / max(len(queue_rows), 1), 6) if queue_rows else 0.0
    pocket_y = round(sum(_safe_float(row.get("pocket_y")) for row in queue_rows) / max(len(queue_rows), 1), 6) if queue_rows else 0.0
    pocket_z = round(sum(_safe_float(row.get("pocket_z")) for row in queue_rows) / max(len(queue_rows), 1), 6) if queue_rows else 0.0
    pocket_zeroed = pocket_x == 0.0 and pocket_y == 0.0 and pocket_z == 0.0
    pocket_source = "stage1_queue_mean_pocket_xyz"
    pocket_override = _target_specific_pocket_override(target_id, queue_rows, stage3_rows, top_n=top_n)
    if pocket_zeroed and pocket_override is not None:
        pocket_x, pocket_y, pocket_z, pocket_source = pocket_override
        pocket_zeroed = pocket_x == 0.0 and pocket_y == 0.0 and pocket_z == 0.0

    rescue_dir = ROOT / "runs" / "wetlab_hard_target_rescue" / target_slug / shard_id
    rescue_dir.mkdir(parents=True, exist_ok=True)
    pocket_csv = rescue_dir / "rescue_target_pocket.csv"
    native_csv = rescue_dir / "rescue_target_native.csv"
    ligand_csv = rescue_dir / "rescue_target_ligand.csv"

    pocket_rows = [
        {
            "target": target_id,
            "pocket_x": pocket_x,
            "pocket_y": pocket_y,
            "pocket_z": pocket_z,
            "pocket_radius_A": 10.0 if "PDE" in target_id else 8.0,
            "source": pocket_source,
        }
    ]
    with pocket_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pocket_rows[0].keys()))
        writer.writeheader()
        writer.writerows(pocket_rows)

    shard_dir = queue_csv.parent if queue_csv.exists() else ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_id
    source_native_stub = shard_dir / "target_native_stub.csv"
    native_rows = _read_csv_rows(source_native_stub)
    if not native_rows:
        native_rows = [{"target": target_id, "native_pdb_path": "", "pdb_id": "", "notes": "rescue_lane_stub_no_native_mapping"}]
    native_anchor_quality = "stub_no_native_path"
    for row in native_rows:
        row.setdefault("target", target_id)
        row["pocket_x"] = pocket_x
        row["pocket_y"] = pocket_y
        row["pocket_z"] = pocket_z
        row["notes"] = _text(row.get("notes")) or "rescue_lane_native_anchor"
        native_path = _text(row.get("native_pdb_path"))
        if native_path and native_path.lower() != "nan":
            native_anchor_quality = "native_pdb_path_present"
        elif pocket_source != "stage1_queue_mean_pocket_xyz" and not pocket_zeroed:
            native_anchor_quality = "stub_with_target_specific_centroid_proxy"
    with native_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(native_rows[0].keys()))
        writer.writeheader()
        writer.writerows(native_rows)

    ranked_stage3 = sorted(
        stage3_rows,
        key=lambda row: (
            _safe_float(row.get("binding_energy_proxy"), 0.0),
            -_safe_float(row.get("stability_score"), 0.0),
            _text(row.get("ligand_id")),
        ),
    )
    ligand_rows = []
    if ranked_stage3:
        for idx, row in enumerate(ranked_stage3[: max(1, int(top_n))], start=1):
            ligand_rows.append(
                {
                    "target": target_id,
                    "ligand_id": _text(row.get("ligand_id")),
                    "role": "fit",
                    "priority_rank": idx,
                    "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                    "stability_score": _safe_float(row.get("stability_score")),
                    "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                    "source": "stage3_scores_topn_rescue_anchor",
                }
            )
    else:
        seen_ids: set[str] = set()
        for row in queue_rows:
            ligand_id = _text(row.get("ligand_id"))
            if not ligand_id or ligand_id in seen_ids:
                continue
            seen_ids.add(ligand_id)
            ligand_rows.append(
                {
                    "target": target_id,
                    "ligand_id": ligand_id,
                    "role": "fit",
                    "priority_rank": len(ligand_rows) + 1,
                    "binding_energy_proxy": "",
                    "stability_score": "",
                    "mean_min_distance_A": "",
                    "source": "stage1_queue_fallback_rescue_anchor",
                }
            )
            if len(ligand_rows) >= max(1, int(top_n)):
                break
    with ligand_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ligand_rows[0].keys()) if ligand_rows else ["target", "ligand_id", "role", "priority_rank", "source"])
        writer.writeheader()
        if ligand_rows:
            writer.writerows(ligand_rows)

    rows = [
        {
            "row_kind": "rescue_anchor_artifact",
            "target_id": target_id,
            "shard_id": shard_id,
            "rescue_target_pocket_csv": str(pocket_csv),
            "rescue_target_native_csv": str(native_csv),
            "rescue_target_ligand_csv": str(ligand_csv),
            "top_n_anchor_ligands": len(ligand_rows),
            "attach_rescue_target_pocket_csv": not pocket_zeroed,
            "attach_rescue_target_native_csv": True,
            "attach_rescue_target_ligand_csv": bool(ligand_rows),
            "rescue_pocket_anchor_quality": "queue_mean_zero_stub" if pocket_zeroed else pocket_source,
            "rescue_native_anchor_quality": native_anchor_quality,
            "pocket_anchor_zeroed": pocket_zeroed,
        }
    ]
    return {
        "summary": {
            "status": "wetlab_rescue_anchor_artifacts_ready",
            "focus_target_id": target_id,
            "focus_shard_id": shard_id,
            "target_id": target_id,
            "shard_id": shard_id,
            "ready_for_rescue": True,
            "rescue_only": True,
            "anchor_artifact_count": 3,
            "native_anchor_artifact": str(native_csv),
            "pocket_anchor_artifact": str(pocket_csv),
            "ligand_anchor_artifact": str(ligand_csv),
            "rescue_target_pocket_csv": str(pocket_csv),
            "rescue_target_native_csv": str(native_csv),
            "rescue_target_ligand_csv": str(ligand_csv),
            "attach_rescue_target_pocket_csv": not pocket_zeroed,
            "attach_rescue_target_native_csv": True,
            "attach_rescue_target_ligand_csv": bool(ligand_rows),
            "rescue_pocket_anchor_quality": "queue_mean_zero_stub" if pocket_zeroed else pocket_source,
            "rescue_native_anchor_quality": native_anchor_quality,
            "top_n_anchor_ligands": len(ligand_rows),
            "next_required_step": f"Use these rescue-only pocket/native/ligand anchor artifacts when launching the hard-target rescue lane for {target_id} {shard_id}.",
        },
        "structured": {
            "rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize rescue-only pocket/native anchor artifacts for the focused hard-target rescue candidate.")
    parser.add_argument("--rescue-lane-json", default=DEFAULT_RESCUE_LANE_JSON)
    parser.add_argument("--stage6-failure-surface-json", default=DEFAULT_STAGE6_FAILURE_SURFACE_JSON)
    parser.add_argument("--retry-policy-templates-json", default=DEFAULT_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _resolve_rescue_lane_payload(
            load_json(args.rescue_lane_json),
            rescue_lane_json=args.rescue_lane_json,
            stage6_failure_surface_json=args.stage6_failure_surface_json,
            retry_policy_templates_json=args.retry_policy_templates_json,
        ),
        top_n=max(1, int(args.top_n)),
    )
    write_artifact(args.out_md, "Wet-Lab Rescue Anchor Artifacts", payload)


if __name__ == "__main__":
    main()
