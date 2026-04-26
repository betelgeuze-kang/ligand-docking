#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_wetlab_rescue_three_bead_candidates import (
    annotate_translation_gate_row,
    summarize_translation_gate_rows,
)
from tools.native_target_registry import find_matching_target_row, resolve_repo_native_entry
from tools.wetlab_allatom_refinement_utils import resolve_optional_claim_gate_summary
from tools.wetlab_pose_validation_utils import summarize_pose_validation_rows
from tools.wetlab_target_render_utils import load_json, write_artifact
from tools.wetlab_broad_screen_watch_utils import slug

ROOT = Path(__file__).resolve().parents[1]
TARGET_ID = "T. cruzi PDE"
DEFAULT_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_allatom_rescue_current.md"
DEFAULT_TOP_K = 8
ALLATOM_COMMAND_KIND = "pseudo_allatom_backmapping_rescore"
ALLATOM_LIGAND_MODEL = "3bead_implicit_hbond"
STRICT_THRESHOLD_A = 2.5
NEAR_THRESHOLD_A = 3.0
DEFAULT_FILTER_MODE = "all"


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text



def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default



def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except Exception:
        return None


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({text for value in values if (text := _text(value))})


def _unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered



def _under_root(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_fingerprint(path: Path | str) -> dict[str, Any]:
    text_path = _text(path)
    if not text_path:
        return {"path": "", "present": False, "size": None, "sha256": ""}
    resolved = _under_root(text_path)
    present = resolved.exists() and resolved.is_file()
    return {
        "path": str(resolved),
        "present": present,
        "size": resolved.stat().st_size if present else None,
        "sha256": _sha256_file(resolved) if present else "",
    }


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_attempt_id(value: str) -> str:
    attempt_id = _text(value)
    if not attempt_id:
        return ""
    if attempt_id in {".", ".."} or "/" in attempt_id or "\\" in attempt_id:
        raise SystemExit(f"invalid PDE all-atom rescue attempt id: {value}")
    return attempt_id


def _next_attempt_identity(
    *,
    slice_dir: Path,
    input_fingerprint_sha256: str,
    execute: bool,
    override_attempt_id: str,
) -> tuple[str, str, int | None]:
    if override_attempt_id:
        attempt_dir = slice_dir / "attempts" / override_attempt_id
        if attempt_dir.exists():
            raise SystemExit(f"PDE all-atom rescue attempt already exists: {attempt_dir}")
        return override_attempt_id, "cli_override", None

    mode = "exec" if execute else "noexec"
    prefix = f"inputfp_{input_fingerprint_sha256[:12]}__{mode}__"
    attempts_dir = slice_dir / "attempts"
    used_sequences: set[int] = set()
    if attempts_dir.exists():
        for child in attempts_dir.iterdir():
            if not child.is_dir() or not child.name.startswith(prefix):
                continue
            suffix = child.name.removeprefix(prefix)
            if suffix.isdigit():
                used_sequences.add(int(suffix))
    sequence = 1
    while sequence in used_sequences:
        sequence += 1
    return f"{prefix}{sequence:04d}", "deterministic_input_fingerprint_sequence", sequence


def _selected_trajectory_fingerprints(
    *,
    stage2_subset_rows: list[dict[str, Any]],
    trajectory_root: Path,
) -> list[dict[str, Any]]:
    fingerprints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in stage2_subset_rows:
        trajectory_npz = _text(row.get("trajectory_npz"))
        if not trajectory_npz:
            continue
        trajectory_path = Path(trajectory_npz)
        resolved = trajectory_path if trajectory_path.is_absolute() else trajectory_root / trajectory_path
        key = str(resolved.resolve())
        if key in seen:
            continue
        seen.add(key)
        fingerprints.append(
            {
                "ligand_id": _text(row.get("ligand_id")),
                "trajectory_npz": trajectory_npz,
                **_file_fingerprint(resolved),
            }
        )
    return fingerprints


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.is_dir():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row or {}) for row in csv.DictReader(handle)]


def _resolve_target_native_reference(target_id: str, candidate_csv_paths: list[str]) -> dict[str, Any]:
    for csv_path in [path for path in candidate_csv_paths if _text(path)]:
        resolved_csv = _under_root(csv_path)
        rows = _read_csv_rows(resolved_csv)
        if not rows:
            continue
        selected_row = find_matching_target_row(rows, target_id)
        native_path = _text(selected_row.get("native_pdb_path"))
        if not native_path:
            continue
        resolved_native = _under_root(native_path)
        if not resolved_native.exists() or resolved_native.is_dir():
            continue
        return {
            "native_pdb_path": str(resolved_native),
            "pdb_id": _text(selected_row.get("pdb_id")),
            "notes": _text(selected_row.get("notes")),
            "source_csv": str(resolved_csv),
            "pocket_x": _text(selected_row.get("pocket_x")),
            "pocket_y": _text(selected_row.get("pocket_y")),
            "pocket_z": _text(selected_row.get("pocket_z")),
            "provenance": "target_native_csv",
        }
    registry_entry = resolve_repo_native_entry(target_id)
    if registry_entry:
        native_path = _text(registry_entry.get("native_pdb_path"))
        resolved_native = _under_root(native_path)
        if resolved_native.exists() and not resolved_native.is_dir():
            return {
                "native_pdb_path": str(resolved_native),
                "pdb_id": _text(registry_entry.get("pdb_id")),
                "notes": _text(registry_entry.get("notes")),
                "source_csv": _text(registry_entry.get("source_csv")),
                "pocket_x": _text(registry_entry.get("pocket_x")),
                "pocket_y": _text(registry_entry.get("pocket_y")),
                "pocket_z": _text(registry_entry.get("pocket_z")),
                "provenance": "repo_native_registry",
            }
    return {}



def _resolve_focus(
    lane_payload: dict[str, Any],
    *,
    target_id: str = "",
    shard_id: str = "",
) -> tuple[str, str]:
    lane_summary = dict(lane_payload.get("summary", {}) or {})
    resolved_target = _text(target_id) or _text(lane_summary.get("target_id"))
    resolved_shard = _text(shard_id) or _text(lane_summary.get("shard_id"))
    if resolved_target != TARGET_ID or not resolved_shard:
        raise SystemExit("PDE all-atom rescue lane has no resolved T. cruzi PDE target/shard")
    return resolved_target, resolved_shard


def _normalize_filter_mode(value: Any) -> str:
    raw = _text(value).lower().replace("-", "_")
    aliases = {
        "": DEFAULT_FILTER_MODE,
        "union": "all",
        "strict": "strict_only",
        "near": "near_only",
        "strict_then_near": "strict_then_near_fill",
    }
    mode = aliases.get(raw, raw)
    if mode not in {"all", "strict_only", "near_only", "strict_then_near_fill"}:
        raise SystemExit(f"unsupported PDE all-atom rescue filter mode: {value}")
    return mode


def _resolve_review_band(row: dict[str, Any]) -> tuple[str, str]:
    resolved_band = _text(row.get("resolved_rescue_review_band"))
    resolved_source = _text(row.get("resolved_rescue_review_band_source"))
    if resolved_band:
        return resolved_band, resolved_source or "resolved_rescue_review_band"
    source_band = _text(row.get("source_rescue_review_band"))
    if source_band:
        return source_band, "source_rescue_review_band"
    distance = _safe_float(row.get("source_three_bead_mean_min_distance_A"), float("nan"))
    if distance == distance:
        if distance <= STRICT_THRESHOLD_A:
            return "strict_under_2p5A", "mean_min_distance_A_fallback"
        if distance <= NEAR_THRESHOLD_A:
            return "near_under_3p0A", "mean_min_distance_A_fallback"
        return "candidate_top32", "mean_min_distance_A_fallback"
    return "candidate_top32", "fallback_default"


def _numeric_review_band(row: dict[str, Any]) -> tuple[str, str]:
    distance = _safe_optional_float(row.get("source_three_bead_mean_min_distance_A"))
    if distance is None:
        return "", ""
    if distance <= STRICT_THRESHOLD_A:
        return "strict_under_2p5A", "source_three_bead_mean_min_distance_A"
    if distance <= NEAR_THRESHOLD_A:
        return "near_under_3p0A", "source_three_bead_mean_min_distance_A"
    return "candidate_top32", "source_three_bead_mean_min_distance_A"


def _review_band_bucket(review_band: Any) -> str:
    band = _text(review_band)
    if band == "strict_under_2p5A" or band.startswith("strict"):
        return "strict"
    if band == "near_under_3p0A" or band.startswith("near"):
        return "near"
    return "other"


def _translation_gate_row_from_lane_row(row: dict[str, Any]) -> dict[str, Any]:
    annotated = annotate_translation_gate_row(
        {
            "mean_min_distance_A": row.get("source_three_bead_mean_min_distance_A"),
            "binding_energy_proxy": row.get("source_three_bead_binding_energy_proxy"),
            "stability_score": row.get("source_three_bead_stability_score"),
            "contact_fraction": row.get("source_three_bead_contact_fraction"),
            "trajectory_frames": row.get("source_three_bead_trajectory_frames"),
            "pose_preservation_rmsd_A": row.get("source_three_bead_pose_preservation_rmsd_A"),
            "backmapping_consistency_score": row.get("source_three_bead_backmapping_consistency_score"),
            "local_minimization_survival_fraction": row.get("source_three_bead_local_minimization_survival_fraction"),
            "replicate_pass_fraction": row.get("source_three_bead_replicate_pass_fraction"),
        },
        review_band=_text(row.get("resolved_rescue_review_band")) or _text(row.get("source_rescue_review_band")),
    )
    return {
        "translation_gate_version": annotated.get("translation_gate_version"),
        "translation_gate_band_bucket": annotated.get("translation_gate_band_bucket"),
        "translation_gate_score": annotated.get("translation_gate_score"),
        "translation_gate_soft_score": annotated.get("translation_gate_soft_score"),
        "translation_gate_status": annotated.get("translation_gate_status"),
        "translation_gate_hard_status": annotated.get("translation_gate_hard_status"),
        "translation_gate_soft_status": annotated.get("translation_gate_soft_status"),
        "translation_gate_pass": annotated.get("translation_gate_pass"),
        "translation_gate_required_check_count": annotated.get("translation_gate_required_check_count"),
        "translation_gate_required_pass_count": annotated.get("translation_gate_required_pass_count"),
        "translation_gate_optional_check_count": annotated.get("translation_gate_optional_check_count"),
        "translation_gate_optional_pass_count": annotated.get("translation_gate_optional_pass_count"),
        "translation_gate_hard_check_count": annotated.get("translation_gate_hard_check_count"),
        "translation_gate_hard_pass_count": annotated.get("translation_gate_hard_pass_count"),
        "translation_gate_hard_failed_checks": annotated.get("translation_gate_hard_failed_checks"),
        "translation_gate_soft_warning_checks": annotated.get("translation_gate_soft_warning_checks"),
        "translation_gate_failed_checks": annotated.get("translation_gate_failed_checks"),
        "translation_gate_warning_checks": annotated.get("translation_gate_warning_checks"),
        "translation_gate_passed_checks": annotated.get("translation_gate_passed_checks"),
        "translation_gate_requires_pose_tightening": annotated.get("translation_gate_requires_pose_tightening"),
        "translation_gate_reason": annotated.get("translation_gate_reason"),
        "translation_gate_action_codes": annotated.get("translation_gate_action_codes"),
        "translation_gate_blocker_codes": annotated.get("translation_gate_blocker_codes"),
        "pose_validation_version": annotated.get("pose_validation_version"),
        "pose_validation_reported": annotated.get("pose_validation_reported"),
        "pose_validation_score": annotated.get("pose_validation_score"),
        "pose_validation_status": annotated.get("pose_validation_status"),
        "pose_validation_soft_status": annotated.get("pose_validation_soft_status"),
        "pose_validation_pass": annotated.get("pose_validation_pass"),
        "pose_validation_metrics_reported_count": annotated.get("pose_validation_metrics_reported_count"),
        "pose_validation_metrics_required_count": annotated.get("pose_validation_metrics_required_count"),
        "pose_validation_pose_preservation_rmsd_A": annotated.get("pose_validation_pose_preservation_rmsd_A"),
        "pose_validation_backmapping_consistency_score": annotated.get(
            "pose_validation_backmapping_consistency_score"
        ),
        "pose_validation_thresholds": annotated.get("pose_validation_thresholds"),
        "pose_validation_failed_checks": annotated.get("pose_validation_failed_checks"),
        "pose_validation_missing_checks": annotated.get("pose_validation_missing_checks"),
        "pose_validation_passed_checks": annotated.get("pose_validation_passed_checks"),
        "pose_validation_action_codes": annotated.get("pose_validation_action_codes"),
        "pose_validation_blocker_codes": annotated.get("pose_validation_blocker_codes"),
        "pose_validation_reason": annotated.get("pose_validation_reason"),
        "stronger_physics_shortlist_version": annotated.get("stronger_physics_shortlist_version"),
        "shortlist_tier": annotated.get("shortlist_tier"),
        "shortlist_promising": annotated.get("shortlist_promising"),
        "recommended_next_expensive_lane": annotated.get("recommended_next_expensive_lane"),
        "recommended_next_expensive_lane_priority": annotated.get("recommended_next_expensive_lane_priority"),
        "recommended_next_expensive_lane_reason": annotated.get("recommended_next_expensive_lane_reason"),
        "recommended_next_expensive_lane_entry_status": annotated.get("recommended_next_expensive_lane_entry_status"),
        "recommended_next_expensive_lane_gate": annotated.get("recommended_next_expensive_lane_gate"),
        "recommended_next_expensive_lane_action": annotated.get("recommended_next_expensive_lane_action"),
        "recommended_next_expensive_lane_action_codes": annotated.get("recommended_next_expensive_lane_action_codes"),
        "recommended_next_expensive_lane_blocker_codes": annotated.get("recommended_next_expensive_lane_blocker_codes"),
    }


def _make_action_recipe_row(
    *,
    action_recipe_code: str,
    action_recipe_domain: str,
    action_recipe_status: str,
    action_recipe_priority: int,
    action_recipe_reason: str,
    action_recipe_next_calculation: str = "",
    source_patterns: list[str] | None = None,
) -> dict[str, Any]:
    code = _text(action_recipe_code)
    next_calculation = _text(action_recipe_next_calculation) or code
    return {
        "action_recipe_code": code,
        "action_recipe_domain": _text(action_recipe_domain),
        "action_recipe_status": _text(action_recipe_status) or "required",
        "action_recipe_priority": int(action_recipe_priority),
        "action_recipe_reason": _text(action_recipe_reason),
        "action_recipe_next_calculation": next_calculation,
        "action_recipe_source_patterns": _sorted_unique(list(source_patterns or [])),
    }


def _merge_action_recipe_rows(action_recipe_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in action_recipe_rows:
        code = _text(row.get("action_recipe_code"))
        domain = _text(row.get("action_recipe_domain"))
        status = _text(row.get("action_recipe_status"))
        next_calculation = _text(row.get("action_recipe_next_calculation")) or code
        key = (code, domain, status, next_calculation)
        merged_row = merged.get(key)
        if merged_row is None:
            merged_row = dict(row)
            merged_row["action_recipe_source_patterns"] = list(row.get("action_recipe_source_patterns", []) or [])
            merged[key] = merged_row
            continue
        merged_row["action_recipe_source_patterns"].extend(
            list(row.get("action_recipe_source_patterns", []) or [])
        )
        if not _text(merged_row.get("action_recipe_reason")) and _text(row.get("action_recipe_reason")):
            merged_row["action_recipe_reason"] = row.get("action_recipe_reason")
        merged_row["action_recipe_priority"] = min(
            _safe_int(merged_row.get("action_recipe_priority"), 10_000),
            _safe_int(row.get("action_recipe_priority"), 10_000),
        )
    merged_rows = list(merged.values())
    for row in merged_rows:
        row["action_recipe_source_patterns"] = _sorted_unique(list(row.get("action_recipe_source_patterns", []) or []))
    return sorted(
        merged_rows,
        key=lambda row: (
            _safe_int(row.get("action_recipe_priority"), 10_000),
            _text(row.get("action_recipe_code")),
            _text(row.get("action_recipe_domain")),
        ),
    )


def _translation_action_recipe_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    failed_checks = set(_sorted_unique(list(row.get("translation_gate_failed_checks", []) or [])))
    hard_failed_checks = set(_sorted_unique(list(row.get("translation_gate_hard_failed_checks", []) or [])))
    blocker_codes = set(_sorted_unique(list(row.get("translation_gate_blocker_codes", []) or [])))
    blocker_patterns = failed_checks | hard_failed_checks | blocker_codes
    translation_status = _text(row.get("translation_gate_status"))
    rows: list[dict[str, Any]] = []

    def _add(
        *,
        code: str,
        status: str,
        priority: int,
        reason: str,
        next_calculation: str = "",
        source_patterns: list[str] | None = None,
    ) -> None:
        rows.append(
            _make_action_recipe_row(
                action_recipe_code=code,
                action_recipe_domain="translation_gate",
                action_recipe_status=status,
                action_recipe_priority=priority,
                action_recipe_reason=reason,
                action_recipe_next_calculation=next_calculation,
                source_patterns=source_patterns,
            )
        )

    if blocker_patterns & {"distance_above_translation_near_band", "translation_geometry_outside_near_band"}:
        _add(
            code="re_minimize_short_replicated_md",
            status="required",
            priority=10,
            reason="mean_min_distance_A is outside the rescue band; re-minimize the pose and rerun short replicated MD.",
            next_calculation="re_minimize_pose_then_short_replicated_md",
            source_patterns=sorted(
                blocker_patterns & {"distance_above_translation_near_band", "translation_geometry_outside_near_band"}
            ),
        )
    if blocker_patterns & {"missing_mean_min_distance_A", "missing_translation_distance"}:
        _add(
            code="measure_mean_min_distance_A",
            status="required",
            priority=11,
            reason="mean_min_distance_A is missing; recompute the translation distance signal before expensive spend.",
            next_calculation="measure_mean_min_distance_A",
            source_patterns=sorted(blocker_patterns & {"missing_mean_min_distance_A", "missing_translation_distance"}),
        )
    if blocker_patterns & {"local_minimization_breaks_translation", "local_minimization_survival_too_low"}:
        _add(
            code="stabilize_local_minimization_then_short_replicated_md",
            status="required",
            priority=14,
            reason="local minimization survival is too low; stabilize the minimization path and rerun short replicated MD.",
            next_calculation="stabilize_local_minimization_then_short_replicated_md",
            source_patterns=sorted(
                blocker_patterns & {"local_minimization_breaks_translation", "local_minimization_survival_too_low"}
            ),
        )
    if blocker_patterns & {"replicate_consensus_breaks_translation", "replicate_pass_fraction_too_low"}:
        _add(
            code="increase_replicate_support_then_short_replicated_md",
            status="required",
            priority=15,
            reason="replicate consensus is too weak; collect more replicate support before rerunning short replicated MD.",
            next_calculation="increase_replicate_support_then_short_replicated_md",
            source_patterns=sorted(
                blocker_patterns & {"replicate_consensus_breaks_translation", "replicate_pass_fraction_too_low"}
            ),
        )
    if blocker_patterns & {"binding_energy_proxy_too_weak_for_translation", "translation_energy_too_weak"}:
        _add(
            code="recompute_binding_energy_proxy",
            status="required",
            priority=16,
            reason="binding energy support is too weak for translation; recompute the three-bead binding energy signal.",
            next_calculation="recompute_binding_energy_proxy",
            source_patterns=sorted(
                blocker_patterns & {"binding_energy_proxy_too_weak_for_translation", "translation_energy_too_weak"}
            ),
        )
    if blocker_patterns & {"missing_binding_energy_proxy", "missing_translation_energy"}:
        _add(
            code="measure_binding_energy_proxy",
            status="required",
            priority=17,
            reason="binding energy support is missing; measure the three-bead binding energy proxy before escalation.",
            next_calculation="measure_binding_energy_proxy",
            source_patterns=sorted(blocker_patterns & {"missing_binding_energy_proxy", "missing_translation_energy"}),
        )
    if blocker_patterns & {"stability_too_low_for_translation", "translation_stability_too_low"}:
        _add(
            code="raise_three_bead_stability",
            status="required",
            priority=18,
            reason="three-bead stability is too low; raise the stability signal before expensive lane spend.",
            next_calculation="raise_three_bead_stability",
            source_patterns=sorted(
                blocker_patterns & {"stability_too_low_for_translation", "translation_stability_too_low"}
            ),
        )
    if blocker_patterns & {"missing_stability_score", "missing_translation_stability"}:
        _add(
            code="measure_stability_score",
            status="required",
            priority=19,
            reason="three-bead stability is missing; measure the stability signal before escalation.",
            next_calculation="measure_stability_score",
            source_patterns=sorted(blocker_patterns & {"missing_stability_score", "missing_translation_stability"}),
        )

    if (
        not rows
        and translation_status in {"fail", "borderline"}
        and _text(row.get("pose_validation_status")) != "fail"
    ):
        _add(
            code="run_seed_replicated_short_md_consensus",
            status="required",
            priority=20,
            reason="translation is not ready and no narrower blocker pattern was available; run short replicated MD consensus next.",
            next_calculation="run_seed_replicated_short_md_consensus",
            source_patterns=["translation_gate_v2_not_ready"],
        )

    return rows


def _pose_validation_action_recipe_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    failed_checks = set(_sorted_unique(list(row.get("pose_validation_failed_checks", []) or [])))
    missing_checks = set(_sorted_unique(list(row.get("pose_validation_missing_checks", []) or [])))
    blocker_codes = set(_sorted_unique(list(row.get("pose_validation_blocker_codes", []) or [])))
    pose_status = _text(row.get("pose_validation_status"))
    rows: list[dict[str, Any]] = []

    def _add(
        *,
        code: str,
        status: str,
        priority: int,
        reason: str,
        next_calculation: str = "",
        source_patterns: list[str] | None = None,
    ) -> None:
        rows.append(
            _make_action_recipe_row(
                action_recipe_code=code,
                action_recipe_domain="pose_validation",
                action_recipe_status=status,
                action_recipe_priority=priority,
                action_recipe_reason=reason,
                action_recipe_next_calculation=next_calculation,
                source_patterns=source_patterns,
            )
        )

    pose_failure_patterns = (failed_checks | blocker_codes) & {
        "pose_preservation_rmsd_above_gate",
        "pose_validation_pose_preservation_rmsd_failed",
    }
    backmapping_failure_patterns = (failed_checks | blocker_codes) & {
        "backmapping_consistency_below_gate",
        "pose_validation_backmapping_consistency_failed",
    }

    if pose_failure_patterns:
        _add(
            code="repair_pose_preservation_then_short_replicated_md",
            status="required",
            priority=12,
            reason="Pose preservation failed the standalone pose-validation gate; repair pose preservation before more expensive spend.",
            next_calculation="repair_pose_preservation_then_short_replicated_md",
            source_patterns=sorted(pose_failure_patterns),
        )
    if backmapping_failure_patterns:
        _add(
            code="repair_backmapping_consistency_then_short_replicated_md",
            status="required",
            priority=13,
            reason="Backmapping consistency failed the standalone pose-validation gate; repair the backmapping path before more expensive spend.",
            next_calculation="repair_backmapping_consistency_then_short_replicated_md",
            source_patterns=sorted(backmapping_failure_patterns),
        )
    if "pose_preservation_rmsd_missing" in missing_checks:
        _add(
            code="measure_pose_preservation_rmsd",
            status="advisory",
            priority=32,
            reason="Pose preservation RMSD is missing; measure it to complete the pose-validation axis.",
            next_calculation="measure_pose_preservation_rmsd",
            source_patterns=["pose_preservation_rmsd_missing"],
        )
    if "backmapping_consistency_missing" in missing_checks:
        _add(
            code="measure_backmapping_consistency",
            status="advisory",
            priority=33,
            reason="Backmapping consistency is missing; measure it to complete the pose-validation axis.",
            next_calculation="measure_backmapping_consistency",
            source_patterns=["backmapping_consistency_missing"],
        )
    if not rows and pose_status == "fail":
        _add(
            code="review_pose_validation_gate",
            status="required",
            priority=34,
            reason="The pose-validation gate failed without a narrower pattern; review the pose-preservation and backmapping traces.",
            next_calculation="review_pose_validation_gate",
            source_patterns=sorted(blocker_codes) or ["pose_validation_gate_not_ready"],
        )

    return rows


def _claim_action_recipe_rows(claim_gate_summary: dict[str, Any]) -> list[dict[str, Any]]:
    claim_gate_summary = dict(claim_gate_summary or {})
    claim_status = _text(claim_gate_summary.get("claim_gate_status"))
    claim_required_for_final = bool(claim_gate_summary.get("claim_gate_required_for_final_wetlab", False))
    claim_required_for_commercial = bool(
        claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
    )
    claim_primary_action = _text(claim_gate_summary.get("claim_gate_primary_action"))
    claim_reason = _text(claim_gate_summary.get("claim_gate_status_reason"))
    missing_metrics = _sorted_unique(list(claim_gate_summary.get("claim_gate_missing_metrics_detail", []) or []))
    blocking_metrics = _sorted_unique(list(claim_gate_summary.get("claim_gate_blocking_metrics", []) or []))

    if claim_status == "claim_ready":
        return []

    if claim_status == "claim_required_unavailable" or claim_required_for_final or claim_required_for_commercial:
        return [
            _make_action_recipe_row(
                action_recipe_code="produce_claim_equivalence_packet",
                action_recipe_domain="claim_equivalence_gate",
                action_recipe_status="required",
                action_recipe_priority=50,
                action_recipe_reason=claim_reason or "produce the missing claim/equivalence packet before final wetlab release.",
                action_recipe_next_calculation="produce_claim_equivalence_packet",
                source_patterns=missing_metrics or ["claim_gate_required_unavailable"],
            )
        ]

    if claim_status == "claim_blocked":
        return [
            _make_action_recipe_row(
                action_recipe_code="resolve_claim_equivalence_gate",
                action_recipe_domain="claim_equivalence_gate",
                action_recipe_status="required",
                action_recipe_priority=50,
                action_recipe_reason=claim_reason or "resolve the claim/equivalence gate before final wetlab release.",
                action_recipe_next_calculation="resolve_claim_equivalence_gate",
                source_patterns=blocking_metrics or ["claim_ready_for_allatom"],
            )
        ]

    if claim_status == "claim_incomplete":
        return [
            _make_action_recipe_row(
                action_recipe_code="complete_claim_equivalence_metrics",
                action_recipe_domain="claim_equivalence_gate",
                action_recipe_status="required",
                action_recipe_priority=50,
                action_recipe_reason=claim_reason or "complete the claim/equivalence metrics before release.",
                action_recipe_next_calculation="complete_claim_equivalence_metrics",
                source_patterns=missing_metrics or ["claim_ready_for_allatom_missing"],
            )
        ]

    if claim_status == "claim_optional_unavailable":
        return [
            _make_action_recipe_row(
                action_recipe_code="produce_claim_equivalence_packet",
                action_recipe_domain="claim_equivalence_gate",
                action_recipe_status="advisory",
                action_recipe_priority=50,
                action_recipe_reason=claim_reason or "claim/equivalence evidence can be produced, but the target is currently optional.",
                action_recipe_next_calculation="produce_claim_equivalence_packet",
                source_patterns=["claim_gate_optional_unavailable"],
            )
        ]

    return [
        _make_action_recipe_row(
            action_recipe_code=claim_primary_action or "produce_claim_equivalence_packet",
            action_recipe_domain="claim_equivalence_gate",
            action_recipe_status="required",
            action_recipe_priority=50,
            action_recipe_reason=claim_reason or "produce the claim/equivalence packet.",
            action_recipe_next_calculation=claim_primary_action or "produce_claim_equivalence_packet",
            source_patterns=[claim_status or "claim_gate_status_unknown"],
        )
    ]


def _expensive_lane_action_recipe_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    lane = _text(row.get("recommended_next_expensive_lane"))
    lane_action = _text(row.get("recommended_next_expensive_lane_action")) or lane
    lane_reason = _text(row.get("recommended_next_expensive_lane_reason"))
    lane_entry_status = _text(row.get("recommended_next_expensive_lane_entry_status"))
    lane_gate = _text(row.get("recommended_next_expensive_lane_gate"))
    if not lane:
        return []
    if lane == "defer_expensive_lane":
        return [
            _make_action_recipe_row(
                action_recipe_code="defer_expensive_lane",
                action_recipe_domain="expensive_lane_policy",
                action_recipe_status="deferred",
                action_recipe_priority=90,
                action_recipe_reason=lane_reason or "defer expensive-lane spend until the translation gate improves.",
                action_recipe_next_calculation="defer_expensive_lane",
                source_patterns=[f"recommended_next_expensive_lane={lane}", lane_gate or "translation_v2_default"],
            )
        ]
    return [
        _make_action_recipe_row(
            action_recipe_code=lane_action or lane,
            action_recipe_domain="expensive_lane_policy",
            action_recipe_status=lane_entry_status or "open",
            action_recipe_priority=80,
            action_recipe_reason=lane_reason or "enter the recommended expensive lane next.",
            action_recipe_next_calculation=lane_action or lane,
            source_patterns=[f"recommended_next_expensive_lane={lane}", lane_gate or "translation_v2_default"],
        )
    ]


def _effective_blocking_order(
    *,
    row: dict[str, Any],
    claim_gate_summary: dict[str, Any],
) -> list[str]:
    blocking_order: list[str] = []
    if _text(row.get("pose_validation_status")) == "fail":
        blocking_order.append("pose_validation")
    translation_status = _text(row.get("translation_gate_status"))
    translation_hard_status = _text(row.get("translation_gate_hard_status"))
    if translation_status != "pass" or translation_hard_status != "pass":
        blocking_order.append("translation_gate")
    claim_required = bool(claim_gate_summary.get("claim_gate_required_for_final_wetlab", False)) or bool(
        claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
    )
    claim_status = _text(claim_gate_summary.get("claim_gate_status"))
    claim_satisfied = claim_gate_summary.get("claim_gate_satisfied")
    if claim_required and claim_satisfied is not True:
        blocking_order.append("claim_equivalence_gate")
    elif claim_status in {"claim_blocked", "claim_incomplete"} and "claim_equivalence_gate" not in blocking_order:
        blocking_order.append("claim_equivalence_gate")
    return blocking_order


def _action_recipe_bundle(
    *,
    row: dict[str, Any],
    claim_gate_summary: dict[str, Any],
) -> dict[str, Any]:
    claim_gate_summary = dict(claim_gate_summary or {})
    pose_validation_rows = _pose_validation_action_recipe_rows(row)
    translation_rows = _translation_action_recipe_rows(row)
    claim_rows = _claim_action_recipe_rows(claim_gate_summary)
    expensive_lane_rows = _expensive_lane_action_recipe_rows(row)
    action_recipe_rows = _merge_action_recipe_rows(
        [*pose_validation_rows, *translation_rows, *claim_rows, *expensive_lane_rows]
    )
    blocking_order = _effective_blocking_order(row=row, claim_gate_summary=claim_gate_summary)
    primary_blocking_domain = blocking_order[0] if blocking_order else ""
    action_recipe_codes = [str(recipe.get("action_recipe_code")) for recipe in action_recipe_rows if _text(recipe.get("action_recipe_code"))]
    required_calculations = [
        _text(recipe.get("action_recipe_next_calculation"))
        for recipe in action_recipe_rows
        if _text(recipe.get("action_recipe_domain"))
        in {"pose_validation", "translation_gate", "claim_equivalence_gate"}
        and _text(recipe.get("action_recipe_status")) in {"required"}
        and _text(recipe.get("action_recipe_next_calculation"))
    ]
    required_calculations = _sorted_unique(required_calculations)
    if blocking_order:
        effective_status = "hard_blocked"
    elif "defer_expensive_lane" in action_recipe_codes:
        effective_status = "deferred_expensive_lane"
    elif action_recipe_codes:
        effective_status = "ready_for_expensive_lane"
    else:
        effective_status = "open"
    return {
        "raw_claim_requirement_mode": _text(claim_gate_summary.get("claim_gate_requirement_mode")),
        "raw_claim_requirement_provenance": _text(claim_gate_summary.get("claim_gate_requirement_provenance")),
        "raw_claim_target_group": _text(claim_gate_summary.get("claim_gate_target_group")),
        "raw_claim_required_for_final_wetlab": bool(claim_gate_summary.get("claim_gate_required_for_final_wetlab", False)),
        "raw_claim_required_for_commercial_readiness": bool(
            claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
        ),
        "raw_claim_requirement_reason": _text(claim_gate_summary.get("claim_gate_requirement_reason")),
        "raw_claim_gate_available": bool(claim_gate_summary.get("claim_gate_available", False)),
        "raw_claim_gate_status": _text(claim_gate_summary.get("claim_gate_status")),
        "raw_claim_gate_satisfied": claim_gate_summary.get("claim_gate_satisfied"),
        "raw_claim_gate_status_reason": _text(claim_gate_summary.get("claim_gate_status_reason")),
        "raw_claim_gate_primary_action": _text(claim_gate_summary.get("claim_gate_primary_action")),
        "raw_claim_gate_action_rollup": _text(claim_gate_summary.get("claim_gate_action_rollup")),
        "raw_claim_gate_blocking_metrics": list(claim_gate_summary.get("claim_gate_blocking_metrics", []) or []),
        "raw_claim_gate_missing_metrics_detail": list(
            claim_gate_summary.get("claim_gate_missing_metrics_detail", []) or []
        ),
        "effective_actionability_status": effective_status,
        "effective_actionability_claim_requirement_mode": _text(
            claim_gate_summary.get("claim_gate_requirement_mode")
        ),
        "effective_actionability_claim_requirement_status": _text(claim_gate_summary.get("claim_gate_status")),
        "effective_actionability_claim_requirement_reason": _text(
            claim_gate_summary.get("claim_gate_status_reason")
        ),
        "effective_actionability_next_expensive_lane": _text(row.get("recommended_next_expensive_lane")),
        "effective_actionability_next_expensive_lane_reason": _text(
            row.get("recommended_next_expensive_lane_reason")
        ),
        "effective_actionability_required_calculations": required_calculations,
        "effective_actionability_action_list": action_recipe_codes,
        "effective_blocking_order": blocking_order,
        "effective_primary_blocking_domain": primary_blocking_domain,
        "action_recipe_codes": action_recipe_codes,
        "action_recipe_rows": action_recipe_rows,
        "action_recipe_rollup": "; ".join(
            f"{_text(recipe.get('action_recipe_code'))} -> {_text(recipe.get('action_recipe_next_calculation'))}"
            for recipe in action_recipe_rows
            if _text(recipe.get("action_recipe_code"))
        ),
    }


def _review_bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"strict": 0, "near": 0, "other": 0}
    for row in rows:
        bucket = _text(row.get("resolved_rescue_review_bucket")) or _review_band_bucket(
            row.get("resolved_rescue_review_band") or row.get("source_rescue_review_band")
        )
        if bucket not in counts:
            bucket = "other"
        counts[bucket] += 1
    return counts


def _band_consistency_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = _text(row.get("rescue_review_band_consistency_status")) or "not_checked"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _execution_status_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ["deferred_blocked", "ready_manifest_only", "execute_requested"]
    counts = {status: 0 for status in order}
    for row in rows:
        status = _text(row.get("rescue_execution_status")) or "deferred_blocked"
        counts.setdefault(status, 0)
        counts[status] += 1
    return [
        {"rescue_execution_status": status, "count": count}
        for status in order
        if (count := counts.get(status, 0)) > 0
    ] + [
        {"rescue_execution_status": status, "count": count}
        for status, count in sorted(counts.items())
        if status not in order and count > 0
    ]


def _next_action_recipe_codes(action_recipe_rows: list[dict[str, Any]]) -> list[str]:
    return _unique_in_order(
        [
            _text(recipe.get("action_recipe_code"))
            for recipe in action_recipe_rows
            if _text(recipe.get("action_recipe_status")) in {"required", "open"}
        ]
    )


def _next_required_calculations(bundle: dict[str, Any]) -> list[str]:
    required = list(bundle.get("effective_actionability_required_calculations", []) or [])
    if required:
        return [_text(value) for value in required if _text(value)]
    return _unique_in_order(
        [
            _text(recipe.get("action_recipe_next_calculation"))
            for recipe in list(bundle.get("action_recipe_rows", []) or [])
            if _text(recipe.get("action_recipe_status")) in {"required", "open"}
        ]
    )


def _row_execution_plan_fields(
    *,
    row: dict[str, Any],
    action_bundle: dict[str, Any],
    selected_rank: int,
    requested_top_k: int,
    actual_top_k: int,
    filter_meta: dict[str, Any],
    execute: bool,
) -> dict[str, Any]:
    blocking_order = list(action_bundle.get("effective_blocking_order", []) or [])
    action_recipe_rows = list(action_bundle.get("action_recipe_rows", []) or [])
    next_required_calculations = _next_required_calculations(action_bundle)
    next_action_recipe_codes = _next_action_recipe_codes(action_recipe_rows)
    if blocking_order:
        execution_status = "deferred_blocked"
        expensive_lane_status = "deferred"
        status_reason = "blocked by required pre-expensive-lane validation gates."
    elif execute:
        execution_status = "execute_requested"
        expensive_lane_status = "open"
        status_reason = "gates are satisfied and execution was requested by the controller."
    else:
        execution_status = "ready_manifest_only"
        expensive_lane_status = "open"
        status_reason = "gates are satisfied, but this run is manifest-only because execute=false."

    return {
        "rescue_execution_status": execution_status,
        "rescue_execution_status_reason": status_reason,
        "rescue_expensive_lane_status": expensive_lane_status,
        "rescue_next_required_calculations": next_required_calculations,
        "rescue_next_action_recipe_codes": next_action_recipe_codes,
        "rescue_iteration_metadata": {
            "selected_rank": selected_rank,
            "top_k_requested": requested_top_k,
            "top_k_effective": actual_top_k,
            "filter_mode_requested": _text(filter_meta.get("requested_filter_mode")),
            "filter_mode_applied": _text(filter_meta.get("applied_filter_mode")),
            "review_bucket": _text(row.get("resolved_rescue_review_bucket")) or "other",
            "execute_requested": bool(execute),
        },
    }


def _execution_plan_summary(
    *,
    payload_rows: list[dict[str, Any]],
    filtered_lane_rows: list[dict[str, Any]],
    selected_lane_rows: list[dict[str, Any]],
    requested_top_k: int,
    actual_top_k: int,
    filter_meta: dict[str, Any],
) -> dict[str, Any]:
    status_counts = _execution_status_counts(payload_rows)
    statuses = {_text(row.get("rescue_execution_status")) for row in payload_rows}
    expensive_statuses = {_text(row.get("rescue_expensive_lane_status")) for row in payload_rows}
    if "deferred_blocked" in statuses:
        plan_status = "blocked_deferred"
    elif "execute_requested" in statuses:
        plan_status = "execute_requested"
    else:
        plan_status = "ready_manifest_only"
    expensive_lane_status = "deferred" if "deferred" in expensive_statuses else "open"
    top_k_shortfall_count = max(0, requested_top_k - actual_top_k)
    top_k_shortfall_reason = ""
    if top_k_shortfall_count:
        top_k_shortfall_reason = (
            f"filtered_lane_candidate_count={len(filtered_lane_rows)} below requested_top_k={requested_top_k} "
            f"after {_text(filter_meta.get('applied_filter_mode'))}"
        )
    return {
        "top_k_requested": requested_top_k,
        "top_k_effective": actual_top_k,
        "top_k_shortfall_count": top_k_shortfall_count,
        "top_k_shortfall_reason": top_k_shortfall_reason,
        "rescue_execution_plan_version": "pde_selected_allatom_rescue_plan_v1",
        "rescue_execution_plan_status": plan_status,
        "rescue_execution_expensive_lane_status": expensive_lane_status,
        "rescue_execution_filtered_bucket_counts": _review_bucket_counts(filtered_lane_rows),
        "rescue_execution_selected_bucket_counts": _review_bucket_counts(selected_lane_rows),
        "rescue_execution_status_counts": status_counts,
        "rescue_execution_next_required_calculations": _unique_in_order(
            [
                calculation
                for row in payload_rows
                for calculation in list(row.get("rescue_next_required_calculations", []) or [])
            ]
        ),
        "rescue_execution_next_action_recipe_codes": _unique_in_order(
            [
                code
                for row in payload_rows
                for code in list(row.get("rescue_next_action_recipe_codes", []) or [])
            ]
        ),
    }


def _normalize_scoring_summary(scoring_payload: Any) -> dict[str, Any]:
    if not isinstance(scoring_payload, dict):
        return {}
    nested_summary = scoring_payload.get("summary")
    if isinstance(nested_summary, dict) and nested_summary:
        return dict(nested_summary)
    return dict(scoring_payload)


def _scoring_status_from_summary(
    *,
    returncode: int,
    summary_present: bool,
    scoring_summary: dict[str, Any],
    expected_jobs: int,
) -> tuple[str, str]:
    if returncode != 0:
        return "error", f"scoring_returncode={returncode}"
    if not summary_present:
        return "error", "scoring_summary_missing"
    processed_jobs = _safe_int(scoring_summary.get("processed_jobs"), 0)
    if processed_jobs < expected_jobs:
        return "incomplete", f"processed_jobs={processed_jobs} below expected_jobs={expected_jobs}"
    return "pass", "processed_jobs_complete"


def _band_mismatch_count(rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if _text(row.get("rescue_review_band_consistency_status")) == "mismatch_fail_closed"
    )


def _select_lane_rows(
    lane_rows: list[dict[str, Any]],
    requested_filter_mode: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mode_requested = _normalize_filter_mode(requested_filter_mode)
    annotated_rows: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    near_rows: list[dict[str, Any]] = []
    other_rows: list[dict[str, Any]] = []
    has_review_band_metadata = False
    for row in lane_rows:
        annotated = dict(row or {})
        resolved_band, band_source = _resolve_review_band(annotated)
        metadata_bucket = _review_band_bucket(resolved_band)
        numeric_band, numeric_band_source = _numeric_review_band(annotated)
        numeric_bucket = _review_band_bucket(numeric_band) if numeric_band else ""
        if numeric_bucket and metadata_bucket and metadata_bucket != numeric_bucket:
            band_bucket = "other"
            consistency_status = "mismatch_fail_closed"
        elif numeric_bucket:
            band_bucket = numeric_bucket
            consistency_status = "match" if metadata_bucket == numeric_bucket else "numeric_only"
        else:
            band_bucket = metadata_bucket
            consistency_status = "metadata_only" if band_source != "fallback_default" else "not_checked"
        annotated["resolved_rescue_review_band"] = resolved_band
        annotated["resolved_rescue_review_band_source"] = band_source
        annotated["metadata_rescue_review_bucket"] = metadata_bucket
        annotated["numeric_rescue_review_band"] = numeric_band
        annotated["numeric_rescue_review_band_source"] = numeric_band_source
        annotated["numeric_rescue_review_bucket"] = numeric_bucket
        annotated["resolved_rescue_review_bucket"] = band_bucket
        annotated["rescue_review_band_consistency_status"] = consistency_status
        annotated.update(_translation_gate_row_from_lane_row(annotated))
        annotated_rows.append(annotated)
        if band_source != "fallback_default":
            has_review_band_metadata = True
        if band_bucket == "strict":
            strict_rows.append(annotated)
        elif band_bucket == "near":
            near_rows.append(annotated)
        else:
            other_rows.append(annotated)

    applied_filter_mode = mode_requested
    fallback_reason = ""
    if mode_requested == "strict_only":
        selected_rows = strict_rows
    elif mode_requested == "near_only":
        selected_rows = near_rows
    elif mode_requested == "strict_then_near_fill":
        selected_rows = [*strict_rows, *near_rows]
    else:
        selected_rows = annotated_rows
    if mode_requested != "all" and (not has_review_band_metadata):
        applied_filter_mode = "all"
        fallback_reason = (
            f"requested {mode_requested} but no rescue review-band metadata was available; fell back to all"
        )
        selected_rows = annotated_rows

    return selected_rows, {
        "requested_filter_mode": mode_requested,
        "applied_filter_mode": applied_filter_mode,
        "fallback_reason": fallback_reason,
        "has_review_band_metadata": has_review_band_metadata,
        "strict_band_candidate_count": len(strict_rows),
        "near_band_candidate_count": len(near_rows),
        "other_band_candidate_count": len(other_rows),
        "filtered_lane_candidate_count": len(selected_rows),
        "rescue_review_band_consistency_counts": _band_consistency_counts(annotated_rows),
        "rescue_review_band_mismatch_count": _band_mismatch_count(annotated_rows),
        "source_rescue_review_band_mismatch_count": _band_mismatch_count(annotated_rows),
        "filtered_rescue_review_band_mismatch_count": _band_mismatch_count(selected_rows),
    }



def run(
    *,
    lane_json: str,
    target_id: str,
    shard_id: str,
    top_k: int,
    filter_mode: str,
    claim_readiness_json: str,
    equivalence_gate_json: str,
    python_bin: str,
    execute: bool,
    out_md: str,
    attempt_id: str = "",
) -> dict[str, Any]:
    lane_payload = load_json(lane_json)
    lane_summary = dict(lane_payload.get("summary", {}) or {})
    resolved_target, resolved_shard = _resolve_focus(lane_payload, target_id=target_id, shard_id=shard_id)

    lane_rows = [
        dict(row or {})
        for row in (lane_payload.get("rows", []) or [])
        if _text((row or {}).get("target_id")) == resolved_target
        and _text((row or {}).get("shard_id")) == resolved_shard
    ]
    lane_rows.sort(
        key=lambda row: (
            _safe_int(row.get("lane_rank"), 0),
            _text(row.get("ligand_id")),
        )
    )
    if not lane_rows:
        raise SystemExit(f"no PDE all-atom rescue lane rows found for {resolved_target} {resolved_shard}")

    requested_filter_mode = _text(filter_mode) or _text(lane_summary.get("default_filter_mode")) or DEFAULT_FILTER_MODE
    filtered_lane_rows, filter_meta = _select_lane_rows(lane_rows, requested_filter_mode)
    if not filtered_lane_rows:
        raise SystemExit(
            f"no PDE all-atom rescue lane rows matched filter mode {filter_meta.get('requested_filter_mode')} "
            f"for {resolved_target} {resolved_shard}"
        )
    requested_top_k = max(1, int(top_k))
    selected_lane_rows = filtered_lane_rows[:requested_top_k]
    filtered_translation_summary = summarize_translation_gate_rows(filtered_lane_rows)
    selected_translation_summary = summarize_translation_gate_rows(selected_lane_rows)
    filtered_pose_validation_summary = summarize_pose_validation_rows(filtered_lane_rows)
    selected_pose_validation_summary = summarize_pose_validation_rows(selected_lane_rows)
    claim_gate_summary = resolve_optional_claim_gate_summary(
        target_id=resolved_target,
        claim_readiness_json=claim_readiness_json,
        equivalence_gate_json=equivalence_gate_json,
    )
    focus_action_recipe_bundle = _action_recipe_bundle(
        row=selected_lane_rows[0],
        claim_gate_summary=claim_gate_summary,
    )
    actual_top_k = len(selected_lane_rows)
    target_slug = slug(resolved_target)
    slice_suffix = ""
    if filter_meta.get("requested_filter_mode") != "all" or filter_meta.get("applied_filter_mode") != "all":
        slice_suffix = f"_{filter_meta.get('requested_filter_mode')}"
        if filter_meta.get("applied_filter_mode") != filter_meta.get("requested_filter_mode"):
            slice_suffix += f"__applied_{filter_meta.get('applied_filter_mode')}"
    slice_dir = _under_root(
        f"runs/wetlab_tcruzi_pde_allatom_rescue/{target_slug}/{resolved_shard}/top_{requested_top_k}{slice_suffix}"
    )
    slice_dir.mkdir(parents=True, exist_ok=True)

    current_manifest_csv = slice_dir / "allatom_rescue_manifest.csv"
    current_queue_subset_csv = slice_dir / "allatom_rescue_queue.csv"
    current_stage2_subset_csv = slice_dir / "allatom_rescue_stage2_manifest.csv"
    state_json = slice_dir / "allatom_rescue_state.json"

    stage1_queue_csv = _under_root(_text(lane_summary.get("base_stage1_queue_csv")))
    stage2_manifest_csv = _under_root(_text(lane_summary.get("base_stage2_manifest_csv")))
    trajectory_root = _under_root(_text(lane_summary.get("base_trajectory_root")))
    if not stage1_queue_csv.exists():
        raise SystemExit(f"missing stage1 queue for PDE all-atom rescue: {stage1_queue_csv}")
    if not stage2_manifest_csv.exists():
        raise SystemExit(f"missing stage2 manifest for PDE all-atom rescue: {stage2_manifest_csv}")
    if not trajectory_root.exists():
        raise SystemExit(f"missing trajectory root for PDE all-atom rescue: {trajectory_root}")

    manifest_rows: list[dict[str, Any]] = []
    selected_ligand_ids: list[str] = []
    selected_ligand_id_set: set[str] = set()
    for row in selected_lane_rows:
        ligand_id = _text(row.get("ligand_id"))
        if not ligand_id or ligand_id in selected_ligand_id_set:
            continue
        selected_ligand_ids.append(ligand_id)
        selected_ligand_id_set.add(ligand_id)
        manifest_rows.append(
            {
                "target_id": resolved_target,
                "target_slug": target_slug,
                "shard_id": resolved_shard,
                "lane_rank": _safe_int(row.get("lane_rank"), 0),
                "ligand_id": ligand_id,
                "compound_name": _text(row.get("compound_name")),
                "compound_name_human_readable": _text(row.get("compound_name_human_readable")),
                "compound_name_resolution": _text(row.get("compound_name_resolution"),) or "unresolved",
                "smiles": _text(row.get("smiles")),
                "compound_source_dataset": _text(row.get("compound_source_dataset")),
                "compound_source_anchor": _text(row.get("compound_source_anchor")),
                "compound_source_url": _text(row.get("compound_source_url")),
                "source_three_bead_priority_rank": _safe_int(row.get("source_three_bead_priority_rank"), 0),
                "source_three_bead_binding_energy_proxy": _safe_float(row.get("source_three_bead_binding_energy_proxy")),
                "source_three_bead_stability_score": _safe_float(row.get("source_three_bead_stability_score")),
                "source_three_bead_mean_min_distance_A": _safe_float(row.get("source_three_bead_mean_min_distance_A")),
                "source_three_bead_contact_fraction": _safe_optional_float(row.get("source_three_bead_contact_fraction")),
                "source_three_bead_trajectory_frames": _safe_optional_float(row.get("source_three_bead_trajectory_frames")),
                "source_three_bead_pose_preservation_rmsd_A": _safe_optional_float(
                    row.get("source_three_bead_pose_preservation_rmsd_A")
                ),
                "source_three_bead_backmapping_consistency_score": _safe_optional_float(
                    row.get("source_three_bead_backmapping_consistency_score")
                ),
                "source_three_bead_local_minimization_survival_fraction": _safe_optional_float(
                    row.get("source_three_bead_local_minimization_survival_fraction")
                ),
                "source_three_bead_replicate_pass_fraction": _safe_optional_float(
                    row.get("source_three_bead_replicate_pass_fraction")
                ),
                "source_rescue_review_band": _text(row.get("source_rescue_review_band")),
                "resolved_rescue_review_band": _text(row.get("resolved_rescue_review_band")),
                "resolved_rescue_review_band_source": _text(row.get("resolved_rescue_review_band_source")),
                "metadata_rescue_review_bucket": _text(row.get("metadata_rescue_review_bucket")),
                "numeric_rescue_review_band": _text(row.get("numeric_rescue_review_band")),
                "numeric_rescue_review_band_source": _text(row.get("numeric_rescue_review_band_source")),
                "numeric_rescue_review_bucket": _text(row.get("numeric_rescue_review_bucket")),
                "resolved_rescue_review_bucket": _text(row.get("resolved_rescue_review_bucket")),
                "rescue_review_band_consistency_status": _text(row.get("rescue_review_band_consistency_status")),
                "selected_filter_mode_requested": _text(filter_meta.get("requested_filter_mode")),
                "selected_filter_mode_applied": _text(filter_meta.get("applied_filter_mode")),
                "selected_filter_mode_fallback_reason": _text(filter_meta.get("fallback_reason")),
                "translation_gate_version": _text(row.get("translation_gate_version")),
                "translation_gate_band_bucket": _text(row.get("translation_gate_band_bucket")),
                "translation_gate_score": row.get("translation_gate_score"),
                "translation_gate_soft_score": row.get("translation_gate_soft_score"),
                "translation_gate_status": _text(row.get("translation_gate_status")),
                "translation_gate_hard_status": _text(row.get("translation_gate_hard_status")),
                "translation_gate_soft_status": _text(row.get("translation_gate_soft_status")),
                "translation_gate_pass": bool(row.get("translation_gate_pass", False)),
                "translation_gate_required_check_count": _safe_int(row.get("translation_gate_required_check_count"), 0),
                "translation_gate_required_pass_count": _safe_int(row.get("translation_gate_required_pass_count"), 0),
                "translation_gate_optional_check_count": _safe_int(row.get("translation_gate_optional_check_count"), 0),
                "translation_gate_optional_pass_count": _safe_int(row.get("translation_gate_optional_pass_count"), 0),
                "translation_gate_hard_check_count": _safe_int(row.get("translation_gate_hard_check_count"), 0),
                "translation_gate_hard_pass_count": _safe_int(row.get("translation_gate_hard_pass_count"), 0),
                "translation_gate_hard_failed_checks": list(row.get("translation_gate_hard_failed_checks", []) or []),
                "translation_gate_soft_warning_checks": list(row.get("translation_gate_soft_warning_checks", []) or []),
                "translation_gate_failed_checks": list(row.get("translation_gate_failed_checks", []) or []),
                "translation_gate_warning_checks": list(row.get("translation_gate_warning_checks", []) or []),
                "translation_gate_passed_checks": list(row.get("translation_gate_passed_checks", []) or []),
                "translation_gate_requires_pose_tightening": bool(row.get("translation_gate_requires_pose_tightening", False)),
                "translation_gate_reason": _text(row.get("translation_gate_reason")),
                "translation_gate_action_codes": list(row.get("translation_gate_action_codes", []) or []),
                "translation_gate_blocker_codes": list(row.get("translation_gate_blocker_codes", []) or []),
                "pose_validation_version": _text(row.get("pose_validation_version")),
                "pose_validation_reported": bool(row.get("pose_validation_reported", False)),
                "pose_validation_score": row.get("pose_validation_score"),
                "pose_validation_status": _text(row.get("pose_validation_status")),
                "pose_validation_soft_status": _text(row.get("pose_validation_soft_status")),
                "pose_validation_pass": bool(row.get("pose_validation_pass", False)),
                "pose_validation_metrics_reported_count": _safe_int(
                    row.get("pose_validation_metrics_reported_count"),
                    0,
                ),
                "pose_validation_metrics_required_count": _safe_int(
                    row.get("pose_validation_metrics_required_count"),
                    0,
                ),
                "pose_validation_pose_preservation_rmsd_A": _safe_optional_float(
                    row.get("pose_validation_pose_preservation_rmsd_A")
                ),
                "pose_validation_backmapping_consistency_score": _safe_optional_float(
                    row.get("pose_validation_backmapping_consistency_score")
                ),
                "pose_validation_thresholds": dict(row.get("pose_validation_thresholds", {}) or {}),
                "pose_validation_failed_checks": list(row.get("pose_validation_failed_checks", []) or []),
                "pose_validation_missing_checks": list(row.get("pose_validation_missing_checks", []) or []),
                "pose_validation_passed_checks": list(row.get("pose_validation_passed_checks", []) or []),
                "pose_validation_action_codes": list(row.get("pose_validation_action_codes", []) or []),
                "pose_validation_blocker_codes": list(row.get("pose_validation_blocker_codes", []) or []),
                "pose_validation_reason": _text(row.get("pose_validation_reason")),
                "stronger_physics_shortlist_version": _text(row.get("stronger_physics_shortlist_version")),
                "shortlist_tier": _text(row.get("shortlist_tier")),
                "shortlist_promising": bool(row.get("shortlist_promising", False)),
                "recommended_next_expensive_lane": _text(row.get("recommended_next_expensive_lane")),
                "recommended_next_expensive_lane_priority": _safe_int(row.get("recommended_next_expensive_lane_priority"), 0),
                "recommended_next_expensive_lane_reason": _text(row.get("recommended_next_expensive_lane_reason")),
                "recommended_next_expensive_lane_entry_status": _text(
                    row.get("recommended_next_expensive_lane_entry_status")
                ),
                "recommended_next_expensive_lane_gate": _text(row.get("recommended_next_expensive_lane_gate")),
                "recommended_next_expensive_lane_action": _text(row.get("recommended_next_expensive_lane_action")),
                "recommended_next_expensive_lane_action_codes": list(
                    row.get("recommended_next_expensive_lane_action_codes", []) or []
                ),
                "recommended_next_expensive_lane_blocker_codes": list(
                    row.get("recommended_next_expensive_lane_blocker_codes", []) or []
                ),
                "selected_command_kind": ALLATOM_COMMAND_KIND,
                "selected_threshold_A": STRICT_THRESHOLD_A,
                "allatom_ligand_model": ALLATOM_LIGAND_MODEL,
                "rescue_target_native_csv": _text(row.get("rescue_target_native_csv")),
                "rescue_target_pocket_csv": _text(row.get("rescue_target_pocket_csv")),
                "rescue_target_ligand_csv": _text(row.get("rescue_target_ligand_csv")),
            }
        )
    if not manifest_rows:
        raise SystemExit(f"no PDE all-atom rescue manifest rows available for {resolved_target} {resolved_shard}")

    queue_subset_rows: list[dict[str, Any]] = []
    with stage1_queue_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if _text(row.get("ligand_id")) in selected_ligand_id_set:
                queue_subset_rows.append(dict(row))
    if not queue_subset_rows:
        raise SystemExit(f"no stage1 queue rows matched PDE all-atom rescue ligands for {resolved_target} {resolved_shard}")
    native_reference = _resolve_target_native_reference(
        resolved_target,
        [
            _text(lane_summary.get("rescue_target_native_csv")),
            str(stage1_queue_csv.parent / "target_native_stub.csv"),
        ],
    )
    if native_reference:
        for row in queue_subset_rows:
            if not _text(row.get("native_pdb_path")):
                row["native_pdb_path"] = _text(native_reference.get("native_pdb_path"))
            if not _text(row.get("pdb_id")):
                row["pdb_id"] = _text(native_reference.get("pdb_id"))
            if not _text(row.get("notes")):
                row["notes"] = _text(native_reference.get("notes"))
            if not _text(row.get("pocket_x")) and _text(native_reference.get("pocket_x")):
                row["pocket_x"] = _text(native_reference.get("pocket_x"))
            if not _text(row.get("pocket_y")) and _text(native_reference.get("pocket_y")):
                row["pocket_y"] = _text(native_reference.get("pocket_y"))
            if not _text(row.get("pocket_z")) and _text(native_reference.get("pocket_z")):
                row["pocket_z"] = _text(native_reference.get("pocket_z"))
            row["native_reference_provenance"] = _text(native_reference.get("provenance"))

    stage2_subset_rows: list[dict[str, Any]] = []
    with stage2_manifest_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if _text(row.get("ligand_id")) in selected_ligand_id_set:
                stage2_subset_rows.append(dict(row))
    if not stage2_subset_rows:
        raise SystemExit(f"no stage2 manifest rows matched PDE all-atom rescue ligands for {resolved_target} {resolved_shard}")

    input_fingerprint_ledger = {
        "schema_version": "pde_allatom_rescue_input_fingerprint_v1",
        "lane_json": _file_fingerprint(lane_json),
        "stage1_queue_csv": _file_fingerprint(stage1_queue_csv),
        "stage2_manifest_csv": _file_fingerprint(stage2_manifest_csv),
        "claim_readiness_json": _file_fingerprint(claim_readiness_json),
        "equivalence_gate_json": _file_fingerprint(equivalence_gate_json),
        "rescue_target_native_csv": _file_fingerprint(lane_summary.get("rescue_target_native_csv")),
        "rescue_target_pocket_csv": _file_fingerprint(lane_summary.get("rescue_target_pocket_csv")),
        "rescue_target_ligand_csv": _file_fingerprint(lane_summary.get("rescue_target_ligand_csv")),
        "resolved_native_pdb": _file_fingerprint(native_reference.get("native_pdb_path")),
        "selected_ligand_ids": list(selected_ligand_ids),
        "selected_manifest_rows_sha256": _canonical_sha256({"rows": manifest_rows}),
        "selected_queue_rows_sha256": _canonical_sha256({"rows": queue_subset_rows}),
        "selected_stage2_rows_sha256": _canonical_sha256({"rows": stage2_subset_rows}),
        "selected_stage2_trajectory_files": _selected_trajectory_fingerprints(
            stage2_subset_rows=stage2_subset_rows,
            trajectory_root=trajectory_root,
        ),
    }
    input_fingerprint_basis = {
        "schema_version": "pde_allatom_rescue_attempt_v1",
        "settings": {
            "target_id": resolved_target,
            "shard_id": resolved_shard,
            "requested_top_k": requested_top_k,
            "actual_top_k": actual_top_k,
            "filter_mode_requested": _text(filter_meta.get("requested_filter_mode")),
            "filter_mode_applied": _text(filter_meta.get("applied_filter_mode")),
            "execute": bool(execute),
            "selected_command_kind": ALLATOM_COMMAND_KIND,
            "allatom_ligand_model": ALLATOM_LIGAND_MODEL,
        },
        "inputs": input_fingerprint_ledger,
    }
    input_fingerprint_sha256 = _canonical_sha256(input_fingerprint_basis)
    override_attempt_id = _validate_attempt_id(attempt_id)
    resolved_attempt_id, attempt_id_source, attempt_sequence = _next_attempt_identity(
        slice_dir=slice_dir,
        input_fingerprint_sha256=input_fingerprint_sha256,
        execute=execute,
        override_attempt_id=override_attempt_id,
    )
    attempt_dir = slice_dir / "attempts" / resolved_attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=False)
    manifest_csv = attempt_dir / "allatom_rescue_manifest.csv"
    queue_subset_csv = attempt_dir / "allatom_rescue_queue.csv"
    stage2_subset_csv = attempt_dir / "allatom_rescue_stage2_manifest.csv"
    attempt_state_json = attempt_dir / "allatom_rescue_state.json"
    scores_csv = attempt_dir / "allatom_rescue_scores.csv"
    summary_json = attempt_dir / "allatom_rescue_summary.json"
    summary_md = attempt_dir / "allatom_rescue_summary.md"
    scoring_log = attempt_dir / "allatom_rescue_scoring.log"
    out_dir = attempt_dir / "allatom_delivery"
    attempt_artifacts = {
        "manifest_csv": str(manifest_csv),
        "queue_csv": str(queue_subset_csv),
        "stage2_manifest_csv": str(stage2_subset_csv),
        "state_json": str(attempt_state_json),
        "scores_csv": str(scores_csv),
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
        "scoring_log": str(scoring_log),
        "delivery_dir": str(out_dir),
    }
    current_artifacts = {
        "manifest_csv": str(current_manifest_csv),
        "queue_csv": str(current_queue_subset_csv),
        "stage2_manifest_csv": str(current_stage2_subset_csv),
        "state_json": str(state_json),
        "artifact_md": str(_under_root(out_md)),
        "artifact_json": str(_under_root(out_md).with_suffix(".json")),
        "artifact_csv": str(_under_root(out_md).with_suffix(".csv")),
    }
    write_csv_rows(manifest_csv, manifest_rows)
    write_csv_rows(queue_subset_csv, queue_subset_rows)
    write_csv_rows(stage2_subset_csv, stage2_subset_rows)
    write_csv_rows(current_manifest_csv, manifest_rows)
    write_csv_rows(current_queue_subset_csv, queue_subset_rows)
    write_csv_rows(current_stage2_subset_csv, stage2_subset_rows)

    payload_rows: list[dict[str, Any]] = []
    for selected_rank, row in enumerate(manifest_rows, start=1):
        action_bundle = _action_recipe_bundle(row=row, claim_gate_summary=claim_gate_summary)
        payload_rows.append(
            {
                **row,
                "attempt_id": resolved_attempt_id,
                "input_fingerprint_sha256": input_fingerprint_sha256,
                **action_bundle,
                **_row_execution_plan_fields(
                    row=row,
                    action_bundle=action_bundle,
                    selected_rank=selected_rank,
                    requested_top_k=requested_top_k,
                    actual_top_k=actual_top_k,
                    filter_meta=filter_meta,
                    execute=execute,
                ),
            }
        )
    execution_plan_summary = _execution_plan_summary(
        payload_rows=payload_rows,
        filtered_lane_rows=filtered_lane_rows,
        selected_lane_rows=selected_lane_rows,
        requested_top_k=requested_top_k,
        actual_top_k=actual_top_k,
        filter_meta=filter_meta,
    )

    execution_mode = "controller_manifest_only"
    scoring_status = "not_executed"
    scoring_status_reason = "not_executed"
    scoring_returncode: int | None = None
    scoring_summary_present = False
    scoring_summary: dict[str, Any] = {}
    scoring_expected_jobs = actual_top_k
    if execute:
        scoring_cmd = [
            python_bin,
            str(ROOT / "tools" / "run_ligand_backmapping_scoring.py"),
            "--queue-csv",
            str(queue_subset_csv),
            "--stage2-manifest-csv",
            str(stage2_subset_csv),
            "--trajectory-root",
            str(trajectory_root),
            "--min-frames",
            "100",
            "--max-jobs",
            str(actual_top_k),
            "--ligand-model",
            ALLATOM_LIGAND_MODEL,
            "--out-dir",
            str(out_dir),
            "--out-scores-csv",
            str(scores_csv),
            "--out-summary-json",
            str(summary_json),
            "--out-summary-md",
            str(summary_md),
            "--workers",
            "0",
            "--parallel-threshold",
            "2",
            "--make-bundle-zip",
            "--no-allow-missing-trajectory",
        ]
        with scoring_log.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.run(
                scoring_cmd,
                cwd=ROOT,
                text=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        scoring_returncode = int(proc.returncode)
        execution_mode = "pseudo_allatom_backmapping_scoring_executed"
        if summary_json.exists():
            scoring_payload = load_json(str(summary_json))
            scoring_summary = _normalize_scoring_summary(scoring_payload)
            scoring_summary_present = bool(scoring_summary)
            scoring_status, scoring_status_reason = _scoring_status_from_summary(
                returncode=scoring_returncode,
                summary_present=scoring_summary_present,
                scoring_summary=scoring_summary,
                expected_jobs=scoring_expected_jobs,
            )
        else:
            scoring_status = "error"
            scoring_status_reason = "scoring_summary_missing"

    payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_rescue_ready",
            "target_id": resolved_target,
            "shard_id": resolved_shard,
            "selected_command_kind": ALLATOM_COMMAND_KIND,
            "selected_threshold_A": STRICT_THRESHOLD_A,
            "allatom_ligand_model": ALLATOM_LIGAND_MODEL,
            "requested_top_k": requested_top_k,
            **execution_plan_summary,
            "slice_candidate_count": len(manifest_rows),
            "source_lane_candidate_count": len(lane_rows),
            "filtered_lane_candidate_count": _safe_int(filter_meta.get("filtered_lane_candidate_count"), len(filtered_lane_rows)),
            "selected_lane_candidate_count": len(selected_lane_rows),
            "filter_mode_requested": _text(filter_meta.get("requested_filter_mode")),
            "filter_mode_applied": _text(filter_meta.get("applied_filter_mode")),
            "filter_mode_fallback_reason": _text(filter_meta.get("fallback_reason")),
            "has_review_band_metadata": bool(filter_meta.get("has_review_band_metadata", False)),
            "strict_band_candidate_count": _safe_int(filter_meta.get("strict_band_candidate_count"), 0),
            "near_band_candidate_count": _safe_int(filter_meta.get("near_band_candidate_count"), 0),
            "other_band_candidate_count": _safe_int(filter_meta.get("other_band_candidate_count"), 0),
            "rescue_review_band_consistency_counts": dict(
                filter_meta.get("rescue_review_band_consistency_counts", {}) or {}
            ),
            "rescue_review_band_mismatch_count": _safe_int(filter_meta.get("rescue_review_band_mismatch_count"), 0),
            "source_rescue_review_band_mismatch_count": _safe_int(
                filter_meta.get("source_rescue_review_band_mismatch_count"),
                _safe_int(filter_meta.get("rescue_review_band_mismatch_count"), 0),
            ),
            "filtered_rescue_review_band_mismatch_count": _safe_int(
                filter_meta.get("filtered_rescue_review_band_mismatch_count"), 0
            ),
            "selected_rescue_review_band_mismatch_count": _band_mismatch_count(selected_lane_rows),
            "filtered_translation_gate_version": _text(filtered_translation_summary.get("translation_gate_version")),
            "filtered_translation_gate_pass_count": _safe_int(filtered_translation_summary.get("translation_gate_pass_count"), 0),
            "filtered_translation_gate_borderline_count": _safe_int(filtered_translation_summary.get("translation_gate_borderline_count"), 0),
            "filtered_translation_gate_fail_count": _safe_int(filtered_translation_summary.get("translation_gate_fail_count"), 0),
            "filtered_pose_validation_version": _text(filtered_pose_validation_summary.get("pose_validation_version")),
            "filtered_pose_validation_pass_count": _safe_int(
                filtered_pose_validation_summary.get("pose_validation_pass_count"),
                0,
            ),
            "filtered_pose_validation_watch_count": _safe_int(
                filtered_pose_validation_summary.get("pose_validation_watch_count"),
                0,
            ),
            "filtered_pose_validation_fail_count": _safe_int(
                filtered_pose_validation_summary.get("pose_validation_fail_count"),
                0,
            ),
            "filtered_shortlist_promising_count": _safe_int(filtered_translation_summary.get("shortlist_promising_count"), 0),
            "filtered_shortlist_tier1_gold_count": _safe_int(filtered_translation_summary.get("shortlist_tier1_gold_count"), 0),
            "filtered_shortlist_tier2_silver_count": _safe_int(filtered_translation_summary.get("shortlist_tier2_silver_count"), 0),
            "filtered_shortlist_tier3_bronze_count": _safe_int(filtered_translation_summary.get("shortlist_tier3_bronze_count"), 0),
            "selected_translation_gate_version": _text(selected_translation_summary.get("translation_gate_version")),
            "selected_translation_gate_pass_count": _safe_int(selected_translation_summary.get("translation_gate_pass_count"), 0),
            "selected_translation_gate_borderline_count": _safe_int(selected_translation_summary.get("translation_gate_borderline_count"), 0),
            "selected_translation_gate_fail_count": _safe_int(selected_translation_summary.get("translation_gate_fail_count"), 0),
            "selected_translation_gate_focus_status": _text(selected_translation_summary.get("translation_gate_focus_status")),
            "selected_translation_gate_focus_score": selected_translation_summary.get("translation_gate_focus_score"),
            "selected_translation_gate_focus_reason": _text(selected_translation_summary.get("translation_gate_focus_reason")),
            "selected_translation_gate_focus_hard_status": _text(
                selected_translation_summary.get("translation_gate_focus_hard_status")
            ),
            "selected_translation_gate_focus_soft_status": _text(
                selected_translation_summary.get("translation_gate_focus_soft_status")
            ),
            "selected_translation_gate_focus_hard_failed_checks": list(
                selected_translation_summary.get("translation_gate_focus_hard_failed_checks", []) or []
            ),
            "selected_translation_gate_focus_failed_checks": list(selected_translation_summary.get("translation_gate_focus_failed_checks", []) or []),
            "selected_translation_gate_focus_warning_checks": list(selected_translation_summary.get("translation_gate_focus_warning_checks", []) or []),
            "selected_translation_gate_focus_soft_warning_checks": list(
                selected_translation_summary.get("translation_gate_focus_soft_warning_checks", []) or []
            ),
            "selected_translation_gate_focus_action_codes": list(
                selected_translation_summary.get("translation_gate_focus_action_codes", []) or []
            ),
            "selected_translation_gate_focus_blocker_codes": list(
                selected_translation_summary.get("translation_gate_focus_blocker_codes", []) or []
            ),
            "selected_pose_validation_version": _text(selected_pose_validation_summary.get("pose_validation_version")),
            "selected_pose_validation_pass_count": _safe_int(
                selected_pose_validation_summary.get("pose_validation_pass_count"),
                0,
            ),
            "selected_pose_validation_watch_count": _safe_int(
                selected_pose_validation_summary.get("pose_validation_watch_count"),
                0,
            ),
            "selected_pose_validation_fail_count": _safe_int(
                selected_pose_validation_summary.get("pose_validation_fail_count"),
                0,
            ),
            "selected_pose_validation_focus_reported": bool(
                selected_pose_validation_summary.get("pose_validation_focus_reported", False)
            ),
            "selected_pose_validation_focus_status": _text(
                selected_pose_validation_summary.get("pose_validation_focus_status")
            ),
            "selected_pose_validation_focus_soft_status": _text(
                selected_pose_validation_summary.get("pose_validation_focus_soft_status")
            ),
            "selected_pose_validation_focus_score": selected_pose_validation_summary.get(
                "pose_validation_focus_score"
            ),
            "selected_pose_validation_focus_pose_preservation_rmsd_A": _safe_optional_float(
                selected_pose_validation_summary.get("pose_validation_focus_pose_preservation_rmsd_A")
            ),
            "selected_pose_validation_focus_backmapping_consistency_score": _safe_optional_float(
                selected_pose_validation_summary.get(
                    "pose_validation_focus_backmapping_consistency_score"
                )
            ),
            "selected_pose_validation_focus_thresholds": dict(
                selected_pose_validation_summary.get("pose_validation_focus_thresholds", {}) or {}
            ),
            "selected_pose_validation_focus_failed_checks": list(
                selected_pose_validation_summary.get("pose_validation_focus_failed_checks", []) or []
            ),
            "selected_pose_validation_focus_missing_checks": list(
                selected_pose_validation_summary.get("pose_validation_focus_missing_checks", []) or []
            ),
            "selected_pose_validation_focus_passed_checks": list(
                selected_pose_validation_summary.get("pose_validation_focus_passed_checks", []) or []
            ),
            "selected_pose_validation_focus_action_codes": list(
                selected_pose_validation_summary.get("pose_validation_focus_action_codes", []) or []
            ),
            "selected_pose_validation_focus_blocker_codes": list(
                selected_pose_validation_summary.get("pose_validation_focus_blocker_codes", []) or []
            ),
            "selected_pose_validation_focus_reason": _text(
                selected_pose_validation_summary.get("pose_validation_focus_reason")
            ),
            "selected_stronger_physics_shortlist_version": _text(selected_translation_summary.get("stronger_physics_shortlist_version")),
            "selected_shortlist_promising_count": _safe_int(selected_translation_summary.get("shortlist_promising_count"), 0),
            "selected_shortlist_tier1_gold_count": _safe_int(selected_translation_summary.get("shortlist_tier1_gold_count"), 0),
            "selected_shortlist_tier2_silver_count": _safe_int(selected_translation_summary.get("shortlist_tier2_silver_count"), 0),
            "selected_shortlist_tier3_bronze_count": _safe_int(selected_translation_summary.get("shortlist_tier3_bronze_count"), 0),
            "focus_shortlist_tier": _text(selected_translation_summary.get("focus_shortlist_tier")),
            "recommended_next_expensive_lane": _text(selected_translation_summary.get("focus_recommended_next_expensive_lane")),
            "recommended_next_expensive_lane_reason": _text(selected_translation_summary.get("focus_recommended_next_expensive_lane_reason")),
            "recommended_next_expensive_lane_entry_status": _text(
                selected_translation_summary.get("focus_recommended_next_expensive_lane_entry_status")
            ),
            "recommended_next_expensive_lane_gate": _text(
                selected_translation_summary.get("focus_recommended_next_expensive_lane_gate")
            ),
            "recommended_next_expensive_lane_action": _text(
                selected_translation_summary.get("focus_recommended_next_expensive_lane_action")
            ),
            "recommended_next_expensive_lane_action_codes": list(
                selected_translation_summary.get("focus_recommended_next_expensive_lane_action_codes", []) or []
            ),
            "recommended_next_expensive_lane_blocker_codes": list(
                selected_translation_summary.get("focus_recommended_next_expensive_lane_blocker_codes", []) or []
            ),
            "recommended_next_expensive_lane_counts": list(selected_translation_summary.get("recommended_next_expensive_lane_counts", []) or []),
            "recommended_next_expensive_lane_entry_status_counts": list(
                selected_translation_summary.get("recommended_next_expensive_lane_entry_status_counts", []) or []
            ),
            "raw_claim_requirement_mode": focus_action_recipe_bundle["raw_claim_requirement_mode"],
            "raw_claim_requirement_provenance": focus_action_recipe_bundle["raw_claim_requirement_provenance"],
            "raw_claim_target_group": focus_action_recipe_bundle["raw_claim_target_group"],
            "raw_claim_required_for_final_wetlab": focus_action_recipe_bundle["raw_claim_required_for_final_wetlab"],
            "raw_claim_required_for_commercial_readiness": focus_action_recipe_bundle[
                "raw_claim_required_for_commercial_readiness"
            ],
            "raw_claim_requirement_reason": focus_action_recipe_bundle["raw_claim_requirement_reason"],
            "raw_claim_gate_available": focus_action_recipe_bundle["raw_claim_gate_available"],
            "raw_claim_gate_status": focus_action_recipe_bundle["raw_claim_gate_status"],
            "raw_claim_gate_satisfied": focus_action_recipe_bundle["raw_claim_gate_satisfied"],
            "raw_claim_gate_status_reason": focus_action_recipe_bundle["raw_claim_gate_status_reason"],
            "raw_claim_gate_primary_action": focus_action_recipe_bundle["raw_claim_gate_primary_action"],
            "raw_claim_gate_action_rollup": focus_action_recipe_bundle["raw_claim_gate_action_rollup"],
            "raw_claim_gate_blocking_metrics": list(focus_action_recipe_bundle["raw_claim_gate_blocking_metrics"]),
            "raw_claim_gate_missing_metrics_detail": list(
                focus_action_recipe_bundle["raw_claim_gate_missing_metrics_detail"]
            ),
            "effective_actionability_status": focus_action_recipe_bundle["effective_actionability_status"],
            "effective_actionability_claim_requirement_mode": focus_action_recipe_bundle[
                "effective_actionability_claim_requirement_mode"
            ],
            "effective_actionability_claim_requirement_status": focus_action_recipe_bundle[
                "effective_actionability_claim_requirement_status"
            ],
            "effective_actionability_claim_requirement_reason": focus_action_recipe_bundle[
                "effective_actionability_claim_requirement_reason"
            ],
            "effective_actionability_next_expensive_lane": focus_action_recipe_bundle[
                "effective_actionability_next_expensive_lane"
            ],
            "effective_actionability_next_expensive_lane_reason": focus_action_recipe_bundle[
                "effective_actionability_next_expensive_lane_reason"
            ],
            "effective_actionability_required_calculations": list(
                focus_action_recipe_bundle["effective_actionability_required_calculations"]
            ),
            "effective_actionability_action_list": list(focus_action_recipe_bundle["effective_actionability_action_list"]),
            "effective_blocking_order": list(focus_action_recipe_bundle["effective_blocking_order"]),
            "effective_primary_blocking_domain": focus_action_recipe_bundle["effective_primary_blocking_domain"],
            "action_recipe_codes": list(focus_action_recipe_bundle["action_recipe_codes"]),
            "action_recipe_rows": list(focus_action_recipe_bundle["action_recipe_rows"]),
            "action_recipe_rollup": focus_action_recipe_bundle["action_recipe_rollup"],
            "allatom_claim_readiness_json": _text(claim_readiness_json),
            "allatom_equivalence_gate_json": _text(equivalence_gate_json),
            "attempt_id": resolved_attempt_id,
            "attempt_id_source": attempt_id_source,
            "attempt_sequence": attempt_sequence,
            "input_fingerprint_sha256": input_fingerprint_sha256,
            "input_fingerprint_schema_version": _text(input_fingerprint_ledger.get("schema_version")),
            "focus_ligand_id": _text(manifest_rows[0].get("ligand_id")),
            "allatom_manifest_csv": str(manifest_csv),
            "allatom_queue_csv": str(queue_subset_csv),
            "allatom_stage2_manifest_csv": str(stage2_subset_csv),
            "allatom_state_json": str(state_json),
            "attempt_dir": str(attempt_dir),
            "attempt_state_json": str(attempt_state_json),
            "current_pointer_json": str(state_json),
            "current_artifact_is_pointer": True,
            "attempt_artifacts": attempt_artifacts,
            "current_artifacts": current_artifacts,
            "trajectory_root": str(trajectory_root),
            "allatom_scores_csv": str(scores_csv),
            "allatom_summary_json": str(summary_json),
            "allatom_summary_md": str(summary_md),
            "allatom_scoring_log": str(scoring_log),
            "rescue_target_native_csv": _text(lane_summary.get("rescue_target_native_csv")),
            "target_native_pdb_path": _text(native_reference.get("native_pdb_path")),
            "target_native_pdb_id": _text(native_reference.get("pdb_id")),
            "target_native_provenance": _text(native_reference.get("provenance")),
            "rescue_target_pocket_csv": _text(lane_summary.get("rescue_target_pocket_csv")),
            "rescue_target_ligand_csv": _text(lane_summary.get("rescue_target_ligand_csv")),
            "execution_mode": execution_mode,
            "scoring_status": scoring_status,
            "scoring_status_reason": scoring_status_reason,
            "scoring_returncode": scoring_returncode,
            "scoring_summary_present": scoring_summary_present,
            "scoring_expected_jobs": scoring_expected_jobs,
            "queue_rows": _safe_int(scoring_summary.get("queue_rows"), len(queue_subset_rows)),
            "processed_jobs": _safe_int(scoring_summary.get("processed_jobs"), 0),
            "avg_binding_energy_proxy": scoring_summary.get("avg_binding_energy_proxy"),
            "avg_stability_score": scoring_summary.get("avg_stability_score"),
            "next_required_step": (
                f"Review the PDE pseudo-all-atom rescue slice for {resolved_shard} using the {filter_meta.get('applied_filter_mode')} "
                f"filter mode and promote only rescue-lane ligands that remain within the 3.0A review band. Focus next spend on "
                f"`{_text(selected_translation_summary.get('focus_recommended_next_expensive_lane')) or 'seed_replicated_short_md_consensus'}` "
                f"under `{_text(selected_translation_summary.get('focus_recommended_next_expensive_lane_gate')) or 'translation_v2_default'}` "
                f"with action codes {list(selected_translation_summary.get('focus_recommended_next_expensive_lane_action_codes', []) or []) or ['collect_replicate_translation_support']}."
            ),
        },
        "structured": {
            "allatom_rescue_lane_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md",
            "rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "rescue_three_bead_slice_artifact": "runs/wetlab_rescue_three_bead_slice_current.md",
            "allatom_claim_readiness_json": _text(claim_readiness_json),
            "allatom_equivalence_gate_json": _text(equivalence_gate_json),
        },
        "input_fingerprints": input_fingerprint_ledger,
        "input_fingerprint_ledger": input_fingerprint_ledger,
        "rows": payload_rows,
    }
    state_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    attempt_state_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_artifact(out_md, "Wet-Lab T. cruzi PDE All-Atom Rescue", payload)
    return payload



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the T. cruzi PDE pseudo-all-atom rescue slice from the PDE-specific rescue lane."
    )
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--filter-mode", default="")
    parser.add_argument("--claim-readiness-json", default="")
    parser.add_argument("--equivalence-gate-json", default="")
    parser.add_argument("--python-bin", default=sys.executable or "python3")
    parser.add_argument("--execute", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--attempt-id", default="")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    run(
        lane_json=args.lane_json,
        target_id=args.target_id,
        shard_id=args.shard_id,
        top_k=max(1, int(args.top_k)),
        filter_mode=args.filter_mode,
        claim_readiness_json=str(args.claim_readiness_json),
        equivalence_gate_json=str(args.equivalence_gate_json),
        python_bin=str(args.python_bin),
        execute=bool(args.execute),
        out_md=args.out_md,
        attempt_id=str(args.attempt_id),
    )


if __name__ == "__main__":
    main()
