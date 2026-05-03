#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
FULL_SET_IDS = {"set1_core_blind", "set2_expanded_ood"}
SMOKE_SET_ID = "set3_operational_smoke"


@dataclass(frozen=True)
class ScaleupPilotPreset:
    target_ligand_size: int
    target_scale_label: str
    target_scale_slug: str
    pilot_version_slug: str
    profile_suffix: str
    full_shape_class: str
    full_count_key: str
    full_ids_key: str

    @classmethod
    def from_target_ligand_size(cls, target_ligand_size: int) -> "ScaleupPilotPreset":
        size = int(target_ligand_size)
        if size <= 0:
            raise ValueError("target_ligand_size must be positive")
        if size % 1_000_000 == 0:
            units = size // 1_000_000
            scale_label = f"{units}M"
            scale_slug = f"{units}m"
        elif size % 1_000 == 0:
            units = size // 1_000
            scale_label = f"{units}k"
            scale_slug = f"{units}k"
        else:
            scale_label = str(size)
            scale_slug = scale_label.lower()
        return cls(
            target_ligand_size=size,
            target_scale_label=scale_label,
            target_scale_slug=scale_slug,
            pilot_version_slug=f"scaleup_{scale_slug}_pilot_v1",
            profile_suffix=f"prod{scale_slug}",
            full_shape_class=f"full_{scale_slug}",
            full_count_key=f"full_task_count_{scale_slug}",
            full_ids_key=f"full_task_ids_{scale_slug}",
        )


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def resolve_repo_path(path_str: str, *, root: Path = ROOT) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _resolve_from_base(base_spec_path: Path, path_str: str, *, root: Path = ROOT) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    for candidate in ((base_spec_path.parent / path).resolve(), (root / path).resolve()):
        if candidate.exists():
            return candidate
    return (root / path).resolve()


def _rel_or_abs(path: Path, *, root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())


def _clone_scale_profile(src: Path, dst: Path, *, preset: ScaleupPilotPreset, description_suffix: str) -> Dict[str, Any]:
    payload = _read_json(src)
    payload["traj_prod_profile_intent"] = f"scaleup_{preset.target_scale_slug}_pilot"
    payload["traj_prod_stage2_preset"] = "auto"
    payload["traj_prod_stage2_preset_strict"] = True
    payload["traj_prod_speedpack"] = True
    payload["traj_prod_early_stop_enabled"] = True
    payload["traj_prod_adaptive_frame_budget"] = True
    payload["traj_prod_light_artifacts"] = True
    payload["traj_prod_light_progress_every_jobs"] = int(max(1, int(payload.get("traj_prod_light_progress_every_jobs", 250))))
    payload["hard_decoy_synth_total_decoys"] = int(
        max(int(payload.get("hard_decoy_synth_total_decoys", 10_000)), preset.target_ligand_size)
    )
    desc = str(payload.get("description") or "").strip()
    payload["description"] = f"{desc} {description_suffix}".strip() if desc else description_suffix
    _write_json(dst, payload)
    return payload


def _build_spec(base_spec: Mapping[str, Any], full_profile_map: Mapping[str, str], *, preset: ScaleupPilotPreset) -> Dict[str, Any]:
    spec = json.loads(json.dumps(base_spec))
    spec["protocol_id"] = f"external_validation_biorxiv_{preset.pilot_version_slug}"
    spec["protocol_title"] = f"{preset.target_scale_label} Production Speedpack Pilot"
    spec["protocol_version"] = preset.pilot_version_slug
    spec["description"] = (
        f"Production-only {preset.target_scale_label} pilot built on the promoted ligand stack. "
        "This pilot enables stage2 production speedpack plus target-specific presets while preserving task identities for regression comparison."
    )
    spec["revision_note"] = (
        "This pilot is not a replacement for the accepted reviewer-facing package. "
        "It is a commercialization-oriented throughput benchmark over the same task surface."
    )
    if isinstance(spec.get("global_governance"), dict):
        claim_scope = spec["global_governance"].setdefault("claim_scope", [])
        note = "This protocol is a production speedpack pilot and does not supersede the accepted v7r1 validation package."
        if note not in claim_scope:
            claim_scope.append(note)

    for set_row in spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")) != "ligand_stress":
                continue
            profile_json = str(task.get("profile_json") or "")
            if set_id in FULL_SET_IDS:
                if profile_json in full_profile_map:
                    task["profile_json"] = full_profile_map[profile_json]
                task["ligand_sizes"] = str(preset.target_ligand_size)
                suffix = str(task.get("date_tag_suffix") or "").strip()
                if suffix:
                    task["date_tag_suffix"] = f"{suffix}-{preset.profile_suffix}"
        set_row["preregistered_claim"] = (
            f"Production-oriented {preset.target_scale_label} pilot over the accepted cross-domain task surface; "
            "results are size-shift operational benchmarks, not paper-claim replacements."
        )
    return spec


def _build_task_rows(
    base_spec: Mapping[str, Any],
    pilot_spec: Mapping[str, Any],
    *,
    preset: ScaleupPilotPreset,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    base_task_index: Dict[tuple[str, str], Dict[str, Any]] = {}
    for set_row in base_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if set_id and task_id:
                base_task_index[(set_id, task_id)] = dict(task)

    task_rows: List[Dict[str, Any]] = []
    set_rows: List[Dict[str, Any]] = []
    target_size_text = str(preset.target_ligand_size)
    for set_row in pilot_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        counts = {
            "ligand_stress_task_count": 0,
            "full_task_count_target": 0,
            preset.full_count_key: 0,
            "smoke_task_count_unchanged": 0,
        }
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")) != "ligand_stress":
                continue
            task_id = str(task.get("task_id", "")).strip()
            base_task = base_task_index.get((set_id, task_id), {})
            ligand_sizes_before = str(base_task.get("ligand_sizes", "")).strip()
            ligand_sizes_after = str(task.get("ligand_sizes", "")).strip()
            profile_before = str(base_task.get("profile_json", "")).strip()
            profile_after = str(task.get("profile_json", "")).strip()
            if ligand_sizes_after == target_size_text:
                shape_class = preset.full_shape_class
            elif ligand_sizes_after == "64":
                shape_class = "smoke_baseline"
            else:
                shape_class = "unchanged_other"
            row = {
                "set_id": set_id,
                "task_id": task_id,
                "domain": str(task.get("domain", "")).strip(),
                "source_profile_json": profile_before,
                "pilot_profile_json": profile_after,
                "profile_changed": profile_before != profile_after,
                "ligand_sizes_before": ligand_sizes_before,
                "ligand_sizes_after": ligand_sizes_after,
                "scaleup_applied": ligand_sizes_before != ligand_sizes_after,
                "pilot_shape_class": shape_class,
                "date_tag_suffix_before": str(base_task.get("date_tag_suffix", "")).strip(),
                "date_tag_suffix_after": str(task.get("date_tag_suffix", "")).strip(),
            }
            task_rows.append(row)
            counts["ligand_stress_task_count"] += 1
            if ligand_sizes_after == target_size_text:
                counts["full_task_count_target"] += 1
                counts[preset.full_count_key] += 1
            elif ligand_sizes_after == "64":
                counts["smoke_task_count_unchanged"] += 1

        set_rows.append(
            {
                "set_id": set_id,
                "ligand_stress_task_count": counts["ligand_stress_task_count"],
                "full_task_count_target": counts["full_task_count_target"],
                preset.full_count_key: counts[preset.full_count_key],
                "smoke_task_count_unchanged": counts["smoke_task_count_unchanged"],
            }
        )
    return task_rows, set_rows


def build_guardrail_rows(*, preset: ScaleupPilotPreset) -> List[Dict[str, str]]:
    return [
        {
            "guardrail_id": "no_pass_to_fail",
            "metric": "set_pass_transition",
            "threshold": "0 pass->fail transitions",
            "scope": "regression slice",
            "rationale": "Keep the accepted claim set intact while measuring size-shift throughput.",
        },
        {
            "guardrail_id": "pr_auc_drop_max_0p02",
            "metric": "ranking_pr_auc_delta",
            "threshold": ">= -0.02 absolute",
            "scope": "regression slice",
            "rationale": "Permit small operational movement without accepting material ranking degradation.",
        },
        {
            "guardrail_id": "top20_hit_drop_max_1",
            "metric": "top20_hit_rate_delta",
            "threshold": ">= -0.05 absolute rate",
            "scope": "regression slice",
            "rationale": f"Preserve shortlist usefulness under the {preset.target_scale_label} pilot.",
        },
        {
            "guardrail_id": "slowest_domain_speedup_min_1p8x",
            "metric": "measured_end_to_end_speedup",
            "threshold": ">= 1.8x on slowest domain",
            "scope": "throughput benchmark",
            "rationale": "Require a meaningful operational win, not only a larger run.",
        },
    ]


def _build_scope_summary(
    task_rows: Sequence[Mapping[str, Any]],
    set_rows: Sequence[Mapping[str, Any]],
    profile_rows: Sequence[Mapping[str, Any]],
    *,
    preset: ScaleupPilotPreset,
) -> Dict[str, Any]:
    full_rows = [row for row in task_rows if row["pilot_shape_class"] == preset.full_shape_class]
    smoke_rows = [row for row in task_rows if row["pilot_shape_class"] == "smoke_baseline"]
    return {
        "set_count": len(set_rows),
        "ligand_stress_task_count": len(task_rows),
        "full_task_count_target": len(full_rows),
        preset.full_count_key: len(full_rows),
        "smoke_task_count_unchanged": len(smoke_rows),
        "profile_clone_count": len(profile_rows),
        "full_set_ids": sorted({str(row["set_id"]) for row in full_rows}),
        "smoke_set_ids": sorted({str(row["set_id"]) for row in smoke_rows}),
        "domains_touched": sorted({str(row["domain"]) for row in task_rows if str(row["domain"]).strip()}),
    }


def _build_drift_audit(
    task_rows: Sequence[Mapping[str, Any]],
    profile_rows: Sequence[Mapping[str, Any]],
    *,
    preset: ScaleupPilotPreset,
) -> Dict[str, Any]:
    target_size_text = str(preset.target_ligand_size)
    full_rows = [row for row in task_rows if row["pilot_shape_class"] == preset.full_shape_class]
    smoke_rows = [row for row in task_rows if row["pilot_shape_class"] == "smoke_baseline"]
    nonstandard_rows = [row for row in task_rows if str(row["ligand_sizes_after"]) not in {target_size_text, "64"}]
    return {
        "ok": bool(
            (len(nonstandard_rows) == 0)
            and all(str(row["ligand_sizes_after"]) == target_size_text for row in full_rows)
            and all(str(row["ligand_sizes_after"]) == "64" for row in smoke_rows)
            and all(bool(row.get("traj_prod_stage2_preset_strict", False)) for row in profile_rows)
            and all(bool(row.get("traj_prod_speedpack", False)) for row in profile_rows)
            and all(bool(row.get("traj_prod_light_artifacts", False)) for row in profile_rows)
            and all(str(row.get("traj_prod_profile_intent", "")).strip() for row in profile_rows)
        ),
        "nonstandard_ligand_size_count": len(nonstandard_rows),
        "full_task_non_target_count": sum(1 for row in full_rows if str(row["ligand_sizes_after"]) != target_size_text),
        "smoke_task_non_64_count": sum(1 for row in smoke_rows if str(row["ligand_sizes_after"]) != "64"),
        "profile_missing_strict_preset_count": sum(
            1 for row in profile_rows if not bool(row.get("traj_prod_stage2_preset_strict", False))
        ),
        "profile_missing_speedpack_count": sum(
            1 for row in profile_rows if not bool(row.get("traj_prod_speedpack", False))
        ),
        "profile_missing_light_artifacts_count": sum(
            1 for row in profile_rows if not bool(row.get("traj_prod_light_artifacts", False))
        ),
        "profile_missing_intent_count": sum(
            1 for row in profile_rows if not str(row.get("traj_prod_profile_intent", "")).strip()
        ),
    }


def build_launch_readiness(
    drift_audit: Mapping[str, Any],
    *,
    preset: ScaleupPilotPreset,
    comparison_enabled: bool | None = None,
    comparison_skip_reason: str = "",
) -> Dict[str, Any]:
    target_size_text = str(preset.target_ligand_size)
    blockers: List[str] = []
    if int(drift_audit.get("nonstandard_ligand_size_count", 0) or 0) > 0:
        blockers.append(
            f"pilot spec contains ligand_stress tasks outside the allowed {target_size_text}/64 shape"
        )
    if int(drift_audit.get("full_task_non_target_count", 0) or 0) > 0:
        blockers.append(
            f"one or more full ligand_stress tasks are not set to {target_size_text} ligands"
        )
    if int(drift_audit.get("smoke_task_non_64_count", 0) or 0) > 0:
        blockers.append("one or more smoke ligand_stress tasks are not preserved at 64 ligands")
    if int(drift_audit.get("profile_missing_strict_preset_count", 0) or 0) > 0:
        blockers.append("one or more selected full-task profiles are missing strict auto-preset governance")
    if int(drift_audit.get("profile_missing_speedpack_count", 0) or 0) > 0:
        blockers.append("one or more selected full-task profiles are missing speedpack")
    if int(drift_audit.get("profile_missing_light_artifacts_count", 0) or 0) > 0:
        blockers.append("one or more selected full-task profiles are missing light-artifact mode")
    if int(drift_audit.get("profile_missing_intent_count", 0) or 0) > 0:
        blockers.append("one or more selected full-task profiles are missing traj_prod_profile_intent")
    if comparison_enabled is not None and not bool(comparison_enabled):
        if comparison_skip_reason == "skip_compare":
            blockers.append("comparison is explicitly disabled via --skip-compare")
        elif comparison_skip_reason == "baseline_run_root_not_found":
            blockers.append("baseline run root could not be resolved from the current package metadata")
        else:
            blockers.append("comparison against the accepted current run is not enabled")
    return {
        "ready": len(blockers) == 0,
        "status": "ready" if len(blockers) == 0 else "blocked",
        "blocking_issue_count": len(blockers),
        "blocking_issues": blockers,
        "comparison_required": comparison_enabled is not None,
        "comparison_enabled": comparison_enabled if comparison_enabled is not None else None,
    }


def build_pilot_payload(
    *,
    base_spec_path: Path,
    out_config_dir: Path,
    preset: ScaleupPilotPreset,
    runner_script_name: str,
    root: Path = ROOT,
) -> Dict[str, Any]:
    base_spec = _read_json(base_spec_path)
    out_config_dir.mkdir(parents=True, exist_ok=True)
    unique_full_profiles: Dict[str, Path] = {}
    smoke_task_ids_baseline: List[str] = []
    for set_row in base_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            profile_json = str(task.get("profile_json") or "").strip()
            if not profile_json or str(task.get("kind", "")) != "ligand_stress":
                continue
            src = _resolve_from_base(base_spec_path, profile_json, root=root)
            if not src.exists():
                continue
            if set_id in FULL_SET_IDS:
                unique_full_profiles[profile_json] = src
            elif str(task.get("ligand_sizes", "")).strip() == "64":
                smoke_task_ids_baseline.append(str(task.get("task_id", "")).strip())

    profile_rows: List[Dict[str, Any]] = []
    profile_map: Dict[str, str] = {}
    for rel_src, src in sorted(unique_full_profiles.items()):
        dst = out_config_dir / f"{src.stem}_{preset.profile_suffix}.json"
        payload = _clone_scale_profile(
            src,
            dst,
            preset=preset,
            description_suffix=(
                f"Production-only {preset.target_scale_label} pilot profile with stage2 speedpack "
                "and target-specific preset auto-selection."
            ),
        )
        profile_map[rel_src] = _rel_or_abs(dst, root=root)
        profile_rows.append(
            {
                "source_profile_json": rel_src,
                "pilot_profile_json": _rel_or_abs(dst, root=root),
                "applies_to": "full",
                "hard_decoy_synth_total_decoys": int(payload.get("hard_decoy_synth_total_decoys", 0)),
                "traj_prod_profile_intent": str(payload.get("traj_prod_profile_intent", "")),
                "traj_prod_stage2_preset": str(payload.get("traj_prod_stage2_preset", "")),
                "traj_prod_stage2_preset_strict": bool(payload.get("traj_prod_stage2_preset_strict", False)),
                "traj_prod_speedpack": bool(payload.get("traj_prod_speedpack", False)),
                "traj_prod_early_stop_enabled": bool(payload.get("traj_prod_early_stop_enabled", False)),
                "traj_prod_light_artifacts": bool(payload.get("traj_prod_light_artifacts", False)),
            }
        )

    spec = _build_spec(base_spec, profile_map, preset=preset)
    task_rows, set_rows = _build_task_rows(base_spec, spec, preset=preset)
    scope_summary = _build_scope_summary(task_rows, set_rows, profile_rows, preset=preset)
    guardrail_rows = build_guardrail_rows(preset=preset)
    drift_audit = _build_drift_audit(task_rows, profile_rows, preset=preset)
    launch_readiness = build_launch_readiness(drift_audit, preset=preset)
    spec_path = out_config_dir / f"external_validation_biorxiv_{preset.pilot_version_slug}.json"
    _write_json(spec_path, spec)

    target_size_text = str(preset.target_ligand_size)
    full_task_ids_target = sorted([row["task_id"] for row in task_rows if row["ligand_sizes_after"] == target_size_text])
    default_tag = f"{dt.date.today().isoformat()}_{preset.pilot_version_slug}"
    baseline_ligand_sizes = {f"{row['set_id']}::{row['task_id']}": row["ligand_sizes_before"] for row in task_rows}
    pilot_ligand_sizes = {f"{row['set_id']}::{row['task_id']}": row["ligand_sizes_after"] for row in task_rows}
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_spec_json": _rel_or_abs(base_spec_path, root=root),
        "pilot_spec_json": _rel_or_abs(spec_path, root=root),
        "target_ligand_size": preset.target_ligand_size,
        "target_scale_label": preset.target_scale_label,
        "target_scale_slug": preset.target_scale_slug,
        "profile_count": len(profile_rows),
        "full_task_count_target": len(full_task_ids_target),
        preset.full_count_key: len(full_task_ids_target),
        "smoke_task_count_unchanged": sum(1 for row in task_rows if row["ligand_sizes_after"] == "64"),
        "full_task_ids_target": full_task_ids_target,
        preset.full_ids_key: full_task_ids_target,
        "smoke_task_ids_baseline": sorted(smoke_task_ids_baseline),
        "baseline_ligand_sizes": baseline_ligand_sizes,
        "pilot_ligand_sizes": pilot_ligand_sizes,
        "comparison_kind": "size_shift_operational_regression",
        "smoke_uses_baseline_decoys": True,
        "scope_summary": scope_summary,
        "drift_audit": drift_audit,
        "launch_readiness": launch_readiness,
        "set_rows": set_rows,
        "task_rows": task_rows,
        "profile_rows": profile_rows,
        "guardrail_rows": guardrail_rows,
        "preflight_notes": [
            f"Only full ligand_stress tasks in set1_core_blind and set2_expanded_ood are upsized to {preset.target_ligand_size}.",
            "Smoke ligand_stress tasks remain at 64 and keep the baseline-style decoy regime.",
            f"Cloned full-task {preset.profile_suffix} profiles enable strict auto-preset governance and artifact-light stage2 mode.",
            "This pilot is an operational throughput benchmark and does not replace the accepted reviewer package.",
        ],
        "comparison_label_default": f"{default_tag}_vs_current",
        "runner_command": (
            f"python3 {runner_script_name} "
            f"--set-spec-json {_rel_or_abs(spec_path, root=root)} "
            f"--tag {default_tag}"
        ),
        "runner_dry_run_command": (
            f"python3 {runner_script_name} "
            f"--set-spec-json {_rel_or_abs(spec_path, root=root)} "
            f"--tag {default_tag} "
            "--dry-run"
        ),
    }


def write_builder_outputs(
    *,
    payload: Mapping[str, Any],
    out_json: Path,
    out_csv: Path,
    out_task_csv: Path,
    out_md: Path,
    preset: ScaleupPilotPreset,
) -> None:
    _write_json(out_json, payload)

    rows = list(payload.get("profile_rows", []))
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(rows[0].keys()) if rows else ["source_profile_json", "pilot_profile_json"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    task_rows = list(payload.get("task_rows", []))
    with out_task_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(task_rows[0].keys()) if task_rows else ["set_id", "task_id"],
        )
        writer.writeheader()
        for row in task_rows:
            writer.writerow(row)

    lines = [
        f"# Ligand Scale-Up {preset.target_scale_label} Pilot",
        "",
        f"- generated_at_local: `{payload.get('generated_at_local')}`",
        f"- base_spec_json: `{payload.get('base_spec_json')}`",
        f"- pilot_spec_json: `{payload.get('pilot_spec_json')}`",
        f"- target_ligand_size: `{payload.get('target_ligand_size')}`",
        f"- target_scale_label: `{payload.get('target_scale_label')}`",
        f"- profile_count: `{payload.get('profile_count')}`",
        f"- full_task_count_target: `{payload.get('full_task_count_target')}`",
        f"- {preset.full_count_key}: `{payload.get(preset.full_count_key)}`",
        f"- smoke_task_count_unchanged: `{payload.get('smoke_task_count_unchanged')}`",
        f"- comparison_kind: `{payload.get('comparison_kind')}`",
        f"- smoke_uses_baseline_decoys: `{payload.get('smoke_uses_baseline_decoys')}`",
        f"- comparison_label_default: `{payload.get('comparison_label_default')}`",
        "",
        "## Scope Summary",
        "",
        f"- set_count: `{payload['scope_summary']['set_count']}`",
        f"- ligand_stress_task_count: `{payload['scope_summary']['ligand_stress_task_count']}`",
        f"- full_task_count_target: `{payload['scope_summary']['full_task_count_target']}`",
        f"- {preset.full_count_key}: `{payload['scope_summary'][preset.full_count_key]}`",
        f"- full_set_ids: `{payload['scope_summary']['full_set_ids']}`",
        f"- smoke_set_ids: `{payload['scope_summary']['smoke_set_ids']}`",
        f"- domains_touched: `{payload['scope_summary']['domains_touched']}`",
        "",
        "## Drift Audit",
        "",
        f"- ok: `{payload['drift_audit']['ok']}`",
        f"- nonstandard_ligand_size_count: `{payload['drift_audit']['nonstandard_ligand_size_count']}`",
        f"- full_task_non_target_count: `{payload['drift_audit']['full_task_non_target_count']}`",
        f"- smoke_task_non_64_count: `{payload['drift_audit']['smoke_task_non_64_count']}`",
        f"- profile_missing_strict_preset_count: `{payload['drift_audit']['profile_missing_strict_preset_count']}`",
        f"- profile_missing_speedpack_count: `{payload['drift_audit']['profile_missing_speedpack_count']}`",
        f"- profile_missing_light_artifacts_count: `{payload['drift_audit']['profile_missing_light_artifacts_count']}`",
        f"- profile_missing_intent_count: `{payload['drift_audit']['profile_missing_intent_count']}`",
        "",
        "## Launch Readiness",
        "",
        f"- ready: `{payload['launch_readiness']['ready']}`",
        f"- status: `{payload['launch_readiness']['status']}`",
        f"- blocking_issue_count: `{payload['launch_readiness']['blocking_issue_count']}`",
        f"- comparison_required: `{payload['launch_readiness']['comparison_required']}`",
        "",
        "## Task Shape",
        "",
        f"- full_task_ids_target: `{payload.get('full_task_ids_target')}`",
        f"- {preset.full_ids_key}: `{payload.get(preset.full_ids_key)}`",
        f"- smoke_task_ids_baseline: `{payload.get('smoke_task_ids_baseline')}`",
        "",
        "## Preflight Notes",
        "",
    ]
    for blocker in payload.get("launch_readiness", {}).get("blocking_issues", []):
        lines.append(f"- blocker: {blocker}")
    if "comparison_enabled" in payload.get("launch_readiness", {}):
        lines.append(
            f"- comparison_enabled: `{payload['launch_readiness'].get('comparison_enabled')}`"
        )
    if str(payload.get("launch_readiness", {}).get("next_required_step", "")).strip():
        lines.append(
            f"- next_required_step: {payload['launch_readiness'].get('next_required_step')}"
        )
    if payload.get("launch_readiness", {}).get("blocking_issues"):
        lines.append("")
    for note in payload.get("preflight_notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Profiles",
            "",
            "| source_profile_json | pilot_profile_json | applies_to | intent | hard_decoy_synth_total_decoys | traj_prod_stage2_preset | strict | speedpack | early_stop | light_artifacts |",
            "| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['source_profile_json']}` | `{row['pilot_profile_json']}` | {row['applies_to']} | {row['traj_prod_profile_intent']} | "
            f"{row['hard_decoy_synth_total_decoys']} | {row['traj_prod_stage2_preset']} | "
            f"{row['traj_prod_stage2_preset_strict']} | {row['traj_prod_speedpack']} | "
            f"{row['traj_prod_early_stop_enabled']} | {row['traj_prod_light_artifacts']} |"
        )
    lines.extend(
        [
            "",
            "## Sets",
            "",
            f"| set_id | ligand_stress_tasks | full_target | {preset.full_count_key} | smoke_unchanged |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload.get("set_rows", []):
        lines.append(
            f"| {row['set_id']} | {row['ligand_stress_task_count']} | {row['full_task_count_target']} | {row[preset.full_count_key]} | {row['smoke_task_count_unchanged']} |"
        )
    lines.extend(
        [
            "",
            "## Tasks",
            "",
            "| set_id | task_id | domain | shape | ligand_sizes_before | ligand_sizes_after | profile_changed |",
            "| --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload.get("task_rows", []):
        lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['domain']} | {row['pilot_shape_class']} | "
            f"{row['ligand_sizes_before']} | {row['ligand_sizes_after']} | {row['profile_changed']} |"
        )
    lines.extend(
        [
            "",
            "## Operational Guardrails",
            "",
            "| guardrail_id | metric | threshold | scope | rationale |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("guardrail_rows", []):
        lines.append(
            f"| {row['guardrail_id']} | {row['metric']} | {row['threshold']} | {row['scope']} | {row['rationale']} |"
        )
    lines.extend(
        [
            "",
            "## Runner",
            "",
            f"- launch: `{payload.get('runner_command')}`",
            f"- dry-run: `{payload.get('runner_dry_run_command')}`",
        ]
    )
    _write_text(out_md, "\n".join(lines) + "\n")


def parse_csv_list(spec: str) -> List[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def resolve_baseline_run_root(explicit: str, package_meta_json: str, *, root: Path = ROOT) -> str:
    if str(explicit).strip():
        return str(resolve_repo_path(explicit, root=root))
    meta_path = resolve_repo_path(package_meta_json, root=root)
    if not meta_path.exists():
        return ""
    meta = _read_json(meta_path)
    run_root = str(meta.get("run_root") or "").strip()
    return str(Path(run_root).resolve()) if run_root else ""


def selected_task_rows(set_spec_json: str, selected_sets: Sequence[str], *, root: Path = ROOT) -> List[Dict[str, Any]]:
    spec = _read_json(resolve_repo_path(set_spec_json, root=root))
    selected = set(selected_sets)
    rows: List[Dict[str, Any]] = []
    for set_row in spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        if selected and set_id not in selected:
            continue
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")) != "ligand_stress":
                continue
            rows.append(
                {
                    "set_id": set_id,
                    "task_id": str(task.get("task_id", "")).strip(),
                    "domain": str(task.get("domain", "")).strip(),
                    "ligand_sizes": str(task.get("ligand_sizes", "")).strip(),
                    "profile_json": str(task.get("profile_json", "")).strip(),
                    "date_tag_suffix": str(task.get("date_tag_suffix", "")).strip(),
                }
            )
    return rows


def selected_scope_summary(task_rows: Sequence[Mapping[str, Any]], *, preset: ScaleupPilotPreset) -> Dict[str, Any]:
    target_size_text = str(preset.target_ligand_size)
    full_rows = [row for row in task_rows if str(row["ligand_sizes"]) == target_size_text]
    smoke_rows = [row for row in task_rows if str(row["ligand_sizes"]) == "64"]
    return {
        "ligand_stress_task_count": len(task_rows),
        "full_task_count_target": len(full_rows),
        preset.full_count_key: len(full_rows),
        "smoke_task_count_unchanged": len(smoke_rows),
        "full_set_ids": sorted({str(row["set_id"]) for row in full_rows}),
        "smoke_set_ids": sorted({str(row["set_id"]) for row in smoke_rows}),
        "domains_touched": sorted({str(row["domain"]) for row in task_rows if str(row["domain"]).strip()}),
    }


def selected_drift_audit(task_rows: Sequence[Mapping[str, Any]], *, preset: ScaleupPilotPreset) -> Dict[str, Any]:
    target_size_text = str(preset.target_ligand_size)
    nonstandard_rows = [row for row in task_rows if str(row["ligand_sizes"]) not in {target_size_text, "64"}]
    full_rows = [row for row in task_rows if str(row["set_id"]) in FULL_SET_IDS]
    smoke_rows = [row for row in task_rows if str(row["set_id"]) == SMOKE_SET_ID]
    return {
        "ok": bool(
            len(nonstandard_rows) == 0
            and all(str(row["ligand_sizes"]) == target_size_text for row in full_rows)
            and all(str(row["ligand_sizes"]) == "64" for row in smoke_rows)
        ),
        "nonstandard_ligand_size_count": len(nonstandard_rows),
        "full_task_non_target_count": sum(1 for row in full_rows if str(row["ligand_sizes"]) != target_size_text),
        "smoke_task_non_64_count": sum(1 for row in smoke_rows if str(row["ligand_sizes"]) != "64"),
    }


def build_run_current_payload(
    *,
    tag: str,
    selected_sets: Sequence[str],
    set_spec_json: str,
    baseline_run_root: str,
    out_root: str,
    comparison_out_root: str,
    compare_label: str,
    skip_compare: bool,
    preset: ScaleupPilotPreset,
    root: Path = ROOT,
) -> Dict[str, Any]:
    task_rows = selected_task_rows(set_spec_json, selected_sets, root=root)
    scope_summary = selected_scope_summary(task_rows, preset=preset)
    drift_audit = selected_drift_audit(task_rows, preset=preset)
    candidate_run_root = root / out_root / f"external_validation_blind_runs_{tag}"
    comparison_enabled = bool(baseline_run_root) and (not bool(skip_compare))
    comparison_skip_reason = "skip_compare" if bool(skip_compare) else ("baseline_run_root_not_found" if not baseline_run_root else "")
    launch_readiness = build_launch_readiness(
        drift_audit,
        preset=preset,
        comparison_enabled=comparison_enabled,
        comparison_skip_reason=comparison_skip_reason,
    )
    run_cmd = [
        sys.executable,
        str(root / "tools/run_external_validation_blind_sets.py"),
        "--tag",
        str(tag),
        "--sets",
        ",".join(selected_sets),
        "--set-spec-json",
        str(set_spec_json),
        "--out-root",
        str(out_root),
    ]
    compare_cmd = [
        sys.executable,
        str(root / "tools/compare_biorxiv_external_validation_runs.py"),
        "--baseline-run-root",
        str(baseline_run_root),
        "--candidate-run-root",
        str(candidate_run_root.resolve()),
        "--out-root",
        str(comparison_out_root),
        "--label",
        str(compare_label),
    ]
    return {
        "ok": True,
        "tag": tag,
        "set_spec_json": str(resolve_repo_path(set_spec_json, root=root)),
        "target_ligand_size": preset.target_ligand_size,
        "target_scale_label": preset.target_scale_label,
        "target_scale_slug": preset.target_scale_slug,
        "selected_sets": list(selected_sets),
        "selected_ligand_stress_task_count": len(task_rows),
        "selected_full_task_count_target": scope_summary["full_task_count_target"],
        f"selected_{preset.full_count_key}": scope_summary[preset.full_count_key],
        "selected_smoke_task_count": scope_summary["smoke_task_count_unchanged"],
        "selected_scope_summary": scope_summary,
        "selected_drift_audit": drift_audit,
        "launch_readiness": launch_readiness,
        "task_rows": task_rows,
        "guardrail_summary": build_guardrail_rows(preset=preset),
        "baseline_run_root": str(baseline_run_root),
        "baseline_run_root_found": bool(baseline_run_root),
        "candidate_run_root": str(candidate_run_root.resolve()),
        "compare_label": compare_label,
        "comparison_root": str((root / comparison_out_root / f"biorxiv_run_comparison_{compare_label}").resolve()),
        "comparison_kind": "size_shift_operational_regression",
        "run_cmd": run_cmd,
        "compare_cmd": compare_cmd if comparison_enabled else [],
        "comparison_enabled": comparison_enabled,
        "comparison_skipped": not comparison_enabled,
        "comparison_skip_reason": comparison_skip_reason,
    }


def run_current_main(
    argv: Sequence[str] | None,
    *,
    preset: ScaleupPilotPreset,
    default_set_spec_json: str,
    current_package_meta_json_default: str = "runs/biorxiv_external_validation_package_current.json",
    out_root_default: str = "runs/external_validation_blind_runs",
    comparison_out_root_default: str = "runs",
    root: Path = ROOT,
) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            f"Run the production-only {preset.target_scale_label} ligand scale-up pilot and compare it with the current accepted run."
        )
    )
    parser.add_argument("--tag", default=f"{dt.date.today().isoformat()}_{preset.pilot_version_slug}")
    parser.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    parser.add_argument("--set-spec-json", default=default_set_spec_json)
    parser.add_argument("--baseline-run-root", default="")
    parser.add_argument("--current-package-meta-json", default=current_package_meta_json_default)
    parser.add_argument("--out-root", default=out_root_default)
    parser.add_argument("--comparison-out-root", default=comparison_out_root_default)
    parser.add_argument("--compare-label", default="")
    parser.add_argument("--skip-compare", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(list(argv) if argv is not None else None)

    selected_sets = parse_csv_list(args.sets)
    baseline_run_root = resolve_baseline_run_root(
        args.baseline_run_root,
        args.current_package_meta_json,
        root=root,
    )
    compare_label = str(args.compare_label).strip() or f"{args.tag}_vs_current"
    payload = build_run_current_payload(
        tag=str(args.tag),
        selected_sets=selected_sets,
        set_spec_json=str(args.set_spec_json),
        baseline_run_root=baseline_run_root,
        out_root=str(args.out_root),
        comparison_out_root=str(args.comparison_out_root),
        compare_label=compare_label,
        skip_compare=bool(args.skip_compare),
        preset=preset,
        root=root,
    )

    if args.dry_run:
        payload["dry_run"] = True
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    run_rc = subprocess.run(payload["run_cmd"], cwd=str(root)).returncode
    if run_rc != 0:
        return int(run_rc)

    if bool(args.skip_compare):
        print(
            json.dumps(
                {
                    "ok": True,
                    "tag": args.tag,
                    "target_ligand_size": preset.target_ligand_size,
                    "target_scale_label": preset.target_scale_label,
                    "candidate_run_root": payload["candidate_run_root"],
                    "comparison_skipped": True,
                    "reason": "skip_compare",
                    "comparison_kind": payload["comparison_kind"],
                    "selected_scope_summary": payload["selected_scope_summary"],
                    "selected_drift_audit": payload["selected_drift_audit"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if not baseline_run_root:
        print(
            json.dumps(
                {
                    "ok": True,
                    "tag": args.tag,
                    "target_ligand_size": preset.target_ligand_size,
                    "target_scale_label": preset.target_scale_label,
                    "candidate_run_root": payload["candidate_run_root"],
                    "comparison_skipped": True,
                    "reason": "baseline run root not found",
                    "comparison_kind": payload["comparison_kind"],
                    "selected_scope_summary": payload["selected_scope_summary"],
                    "selected_drift_audit": payload["selected_drift_audit"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    compare_rc = subprocess.run(payload["compare_cmd"], cwd=str(root)).returncode
    if compare_rc != 0:
        return int(compare_rc)

    print(
        json.dumps(
            {
                "ok": True,
                "tag": args.tag,
                "target_ligand_size": preset.target_ligand_size,
                "target_scale_label": preset.target_scale_label,
                "baseline_run_root": baseline_run_root,
                "candidate_run_root": payload["candidate_run_root"],
                "comparison_root": payload["comparison_root"],
                "set_spec_json": payload["set_spec_json"],
                "comparison_kind": payload["comparison_kind"],
                "selected_scope_summary": payload["selected_scope_summary"],
                "selected_drift_audit": payload["selected_drift_audit"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0
