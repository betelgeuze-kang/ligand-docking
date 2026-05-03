#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()


def _resolve_from_base(base_spec_path: Path, path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p.resolve()
    for candidate in [
        (base_spec_path.parent / p).resolve(),
        (ROOT / p).resolve(),
    ]:
        if candidate.exists():
            return candidate
    return (ROOT / p).resolve()


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _clone_prod100k_profile(src: Path, dst: Path, *, description_suffix: str) -> Dict[str, Any]:
    payload = _read_json(src)
    payload["traj_prod_profile_intent"] = "scaleup_100k_pilot"
    payload["traj_prod_stage2_preset"] = "auto"
    payload["traj_prod_stage2_preset_strict"] = True
    payload["traj_prod_speedpack"] = True
    payload["traj_prod_early_stop_enabled"] = True
    payload["traj_prod_adaptive_frame_budget"] = True
    payload["traj_prod_light_artifacts"] = True
    payload["traj_prod_light_progress_every_jobs"] = int(max(1, int(payload.get("traj_prod_light_progress_every_jobs", 250))))
    payload["hard_decoy_synth_total_decoys"] = int(max(int(payload.get("hard_decoy_synth_total_decoys", 10_000)), 100_000))
    desc = str(payload.get("description") or "").strip()
    payload["description"] = f"{desc} {description_suffix}".strip() if desc else description_suffix
    _write_json(dst, payload)
    return payload


def _build_spec(base_spec: Dict[str, Any], full_profile_map: Dict[str, str]) -> Dict[str, Any]:
    spec = deepcopy(base_spec)
    spec["protocol_id"] = "external_validation_biorxiv_scaleup_100k_pilot_v1"
    spec["protocol_title"] = "100k Production Speedpack Pilot"
    spec["protocol_version"] = "scaleup_100k_pilot_v1"
    spec["description"] = (
        "Production-only 100k pilot built on the promoted ligand stack. "
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
            if set_id in {"set1_core_blind", "set2_expanded_ood"}:
                if profile_json in full_profile_map:
                    task["profile_json"] = full_profile_map[profile_json]
                task["ligand_sizes"] = "100000"
                suffix = str(task.get("date_tag_suffix") or "").strip()
                if suffix:
                    task["date_tag_suffix"] = f"{suffix}-prod100k"
        set_row["preregistered_claim"] = (
            "Production-oriented 100k pilot over the accepted cross-domain task surface; results are size-shift operational benchmarks, not paper-claim replacements."
        )
    return spec


def _build_task_rows(base_spec: Dict[str, Any], pilot_spec: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    base_task_index: Dict[tuple[str, str], Dict[str, Any]] = {}
    for set_row in base_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if set_id and task_id:
                base_task_index[(set_id, task_id)] = task

    task_rows: List[Dict[str, Any]] = []
    set_rows: List[Dict[str, Any]] = []
    for set_row in pilot_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        counts = {
            "ligand_stress_task_count": 0,
            "full_task_count_100k": 0,
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
                "pilot_shape_class": (
                    "full_100k"
                    if ligand_sizes_after == "100000"
                    else ("smoke_baseline" if ligand_sizes_after == "64" else "unchanged_other")
                ),
                "date_tag_suffix_before": str(base_task.get("date_tag_suffix", "")).strip(),
                "date_tag_suffix_after": str(task.get("date_tag_suffix", "")).strip(),
            }
            task_rows.append(row)
            counts["ligand_stress_task_count"] += 1
            if ligand_sizes_after == "100000":
                counts["full_task_count_100k"] += 1
            elif ligand_sizes_after == "64":
                counts["smoke_task_count_unchanged"] += 1

        set_rows.append(
            {
                "set_id": set_id,
                "ligand_stress_task_count": counts["ligand_stress_task_count"],
                "full_task_count_100k": counts["full_task_count_100k"],
                "smoke_task_count_unchanged": counts["smoke_task_count_unchanged"],
            }
        )
    return task_rows, set_rows


def _build_guardrail_rows() -> List[Dict[str, str]]:
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
            "rationale": "Preserve shortlist usefulness under the 100k pilot.",
        },
        {
            "guardrail_id": "slowest_domain_speedup_min_1p8x",
            "metric": "measured_end_to_end_speedup",
            "threshold": ">= 1.8x on slowest domain",
            "scope": "throughput benchmark",
            "rationale": "Require a meaningful operational win, not only a larger run.",
        },
    ]


def _build_scope_summary(task_rows: List[Dict[str, Any]], set_rows: List[Dict[str, Any]], profile_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    full_rows = [row for row in task_rows if row["pilot_shape_class"] == "full_100k"]
    smoke_rows = [row for row in task_rows if row["pilot_shape_class"] == "smoke_baseline"]
    return {
        "set_count": len(set_rows),
        "ligand_stress_task_count": len(task_rows),
        "full_task_count_100k": len(full_rows),
        "smoke_task_count_unchanged": len(smoke_rows),
        "profile_clone_count": len(profile_rows),
        "full_set_ids": sorted({row["set_id"] for row in full_rows}),
        "smoke_set_ids": sorted({row["set_id"] for row in smoke_rows}),
        "domains_touched": sorted({row["domain"] for row in task_rows if str(row["domain"]).strip()}),
    }


def _build_drift_audit(task_rows: List[Dict[str, Any]], profile_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    full_rows = [row for row in task_rows if row["pilot_shape_class"] == "full_100k"]
    smoke_rows = [row for row in task_rows if row["pilot_shape_class"] == "smoke_baseline"]
    nonstandard_rows = [row for row in task_rows if row["ligand_sizes_after"] not in {"100000", "64"}]
    return {
        "ok": bool(
            (len(nonstandard_rows) == 0)
            and all(str(row["ligand_sizes_after"]) == "100000" for row in full_rows)
            and all(str(row["ligand_sizes_after"]) == "64" for row in smoke_rows)
            and all(bool(row.get("traj_prod_stage2_preset_strict", False)) for row in profile_rows)
            and all(bool(row.get("traj_prod_speedpack", False)) for row in profile_rows)
            and all(bool(row.get("traj_prod_light_artifacts", False)) for row in profile_rows)
            and all(str(row.get("traj_prod_profile_intent", "")).strip() for row in profile_rows)
        ),
        "nonstandard_ligand_size_count": len(nonstandard_rows),
        "full_task_non_100k_count": sum(1 for row in full_rows if str(row["ligand_sizes_after"]) != "100000"),
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


def _build_launch_readiness(drift_audit: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    if int(drift_audit.get("nonstandard_ligand_size_count", 0)) > 0:
        blockers.append("pilot spec contains ligand_stress tasks outside the allowed 100000/64 shape")
    if int(drift_audit.get("full_task_non_100k_count", 0)) > 0:
        blockers.append("one or more full ligand_stress tasks are not set to 100000 ligands")
    if int(drift_audit.get("smoke_task_non_64_count", 0)) > 0:
        blockers.append("one or more smoke ligand_stress tasks are not preserved at 64 ligands")
    if int(drift_audit.get("profile_missing_strict_preset_count", 0)) > 0:
        blockers.append("one or more cloned full-task profiles are missing strict auto-preset governance")
    if int(drift_audit.get("profile_missing_speedpack_count", 0)) > 0:
        blockers.append("one or more cloned full-task profiles are missing speedpack")
    if int(drift_audit.get("profile_missing_light_artifacts_count", 0)) > 0:
        blockers.append("one or more cloned full-task profiles are missing light-artifact mode")
    if int(drift_audit.get("profile_missing_intent_count", 0)) > 0:
        blockers.append("one or more cloned full-task profiles are missing traj_prod_profile_intent")
    return {
        "ready": len(blockers) == 0,
        "status": "ready" if len(blockers) == 0 else "blocked",
        "blocking_issue_count": len(blockers),
        "blocking_issues": blockers,
        "comparison_required": True,
        "next_required_step": "Run the 100k pilot runner with --dry-run and confirm comparison is enabled before launch.",
    }


def build_payload(*, base_spec_path: Path, out_config_dir: Path) -> Dict[str, Any]:
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
            src = _resolve_from_base(base_spec_path, profile_json)
            if not src.exists():
                continue
            if set_id in {"set1_core_blind", "set2_expanded_ood"}:
                unique_full_profiles[profile_json] = src
            elif str(task.get("ligand_sizes", "")).strip() == "64":
                smoke_task_ids_baseline.append(str(task.get("task_id", "")).strip())

    profile_rows: List[Dict[str, Any]] = []
    profile_map: Dict[str, str] = {}
    for rel_src, src in sorted(unique_full_profiles.items()):
        dst = out_config_dir / f"{src.stem}_prod100k.json"
        payload = _clone_prod100k_profile(
            src,
            dst,
            description_suffix="Production-only 100k pilot profile with stage2 speedpack and target-specific preset auto-selection.",
        )
        profile_map[rel_src] = _rel_or_abs(dst)
        profile_rows.append(
            {
                "source_profile_json": rel_src,
                "pilot_profile_json": _rel_or_abs(dst),
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

    spec = _build_spec(base_spec, profile_map)
    task_rows, set_rows = _build_task_rows(base_spec, spec)
    scope_summary = _build_scope_summary(task_rows, set_rows, profile_rows)
    guardrail_rows = _build_guardrail_rows()
    drift_audit = _build_drift_audit(task_rows, profile_rows)
    launch_readiness = _build_launch_readiness(drift_audit)
    spec_path = out_config_dir / "external_validation_biorxiv_scaleup_100k_pilot_v1.json"
    _write_json(spec_path, spec)

    full_task_count = 0
    smoke_task_count = 0
    for set_row in spec.get("sets", []):
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")) != "ligand_stress":
                continue
            if str(task.get("ligand_sizes", "")) == "100000":
                full_task_count += 1
            elif str(task.get("ligand_sizes", "")) == "64":
                smoke_task_count += 1

    default_tag = f"{dt.date.today().isoformat()}_scaleup_100k_pilot_v1"
    baseline_ligand_sizes = {f"{row['set_id']}::{row['task_id']}": row["ligand_sizes_before"] for row in task_rows}
    pilot_ligand_sizes = {f"{row['set_id']}::{row['task_id']}": row["ligand_sizes_after"] for row in task_rows}
    full_task_ids_100k = sorted([row["task_id"] for row in task_rows if row["ligand_sizes_after"] == "100000"])
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_spec_json": _rel_or_abs(base_spec_path),
        "pilot_spec_json": _rel_or_abs(spec_path),
        "profile_count": len(profile_rows),
        "full_task_count_100k": int(full_task_count),
        "smoke_task_count_unchanged": int(smoke_task_count),
        "full_task_ids_100k": full_task_ids_100k,
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
            "Only full ligand_stress tasks in set1_core_blind and set2_expanded_ood are upsized to 100000.",
            "Smoke ligand_stress tasks remain at 64 and keep the baseline-style decoy regime.",
            "Cloned full-task prod100k profiles enable strict auto-preset governance and artifact-light stage2 mode.",
            "This pilot is an operational throughput benchmark and does not replace the accepted reviewer package.",
        ],
        "comparison_label_default": f"{default_tag}_vs_current",
        "runner_command": (
            "python3 tools/run_ligand_scaleup_100k_pilot_current.py "
            f"--set-spec-json {_rel_or_abs(spec_path)} "
            f"--tag {default_tag}"
        ),
        "runner_dry_run_command": (
            "python3 tools/run_ligand_scaleup_100k_pilot_current.py "
            f"--set-spec-json {_rel_or_abs(spec_path)} "
            f"--tag {default_tag} "
            "--dry-run"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the production-only 100k ligand scale-up pilot spec and cloned profiles.")
    ap.add_argument("--base-spec-json", default="config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json")
    ap.add_argument("--out-config-dir", default="config")
    ap.add_argument("--out-json", default="runs/ligand_scaleup_100k_pilot_current.json")
    ap.add_argument("--out-csv", default="runs/ligand_scaleup_100k_pilot_current.csv")
    ap.add_argument("--out-task-csv", default="runs/ligand_scaleup_100k_pilot_tasks_current.csv")
    ap.add_argument("--out-md", default="runs/ligand_scaleup_100k_pilot_current.md")
    args = ap.parse_args()

    payload = build_payload(
        base_spec_path=_resolve(args.base_spec_json),
        out_config_dir=_resolve(args.out_config_dir),
    )

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_task_csv = _resolve(args.out_task_csv)
    out_md = _resolve(args.out_md)
    _write_json(out_json, payload)

    rows = payload.get("profile_rows", [])
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(rows[0].keys()) if rows else ["source_profile_json", "pilot_profile_json"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    task_rows = payload.get("task_rows", [])
    with out_task_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(task_rows[0].keys()) if task_rows else ["set_id", "task_id"],
        )
        writer.writeheader()
        for row in task_rows:
            writer.writerow(row)

    lines = [
        "# Ligand Scale-Up 100k Pilot",
        "",
        f"- generated_at_local: `{payload.get('generated_at_local')}`",
        f"- base_spec_json: `{payload.get('base_spec_json')}`",
        f"- pilot_spec_json: `{payload.get('pilot_spec_json')}`",
        f"- profile_count: `{payload.get('profile_count')}`",
        f"- full_task_count_100k: `{payload.get('full_task_count_100k')}`",
        f"- smoke_task_count_unchanged: `{payload.get('smoke_task_count_unchanged')}`",
        f"- comparison_kind: `{payload.get('comparison_kind')}`",
        f"- smoke_uses_baseline_decoys: `{payload.get('smoke_uses_baseline_decoys')}`",
        f"- comparison_label_default: `{payload.get('comparison_label_default')}`",
        "",
        "## Scope Summary",
        "",
        f"- set_count: `{payload['scope_summary']['set_count']}`",
        f"- ligand_stress_task_count: `{payload['scope_summary']['ligand_stress_task_count']}`",
        f"- full_set_ids: `{payload['scope_summary']['full_set_ids']}`",
        f"- smoke_set_ids: `{payload['scope_summary']['smoke_set_ids']}`",
        f"- domains_touched: `{payload['scope_summary']['domains_touched']}`",
        "",
        "## Drift Audit",
        "",
        f"- ok: `{payload['drift_audit']['ok']}`",
        f"- nonstandard_ligand_size_count: `{payload['drift_audit']['nonstandard_ligand_size_count']}`",
        f"- full_task_non_100k_count: `{payload['drift_audit']['full_task_non_100k_count']}`",
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
        f"- full_task_ids_100k: `{payload.get('full_task_ids_100k')}`",
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
            "| set_id | ligand_stress_tasks | 100k_full | smoke_unchanged |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload.get("set_rows", []):
        lines.append(
            f"| {row['set_id']} | {row['ligand_stress_task_count']} | {row['full_task_count_100k']} | {row['smoke_task_count_unchanged']} |"
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
    print(json.dumps({"ok": True, "pilot_spec_json": payload["pilot_spec_json"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
