#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from tools.ligand_scaleup_pilot_helper import (
    ScaleupPilotPreset,
    build_pilot_payload as _base_build_pilot_payload,
    resolve_repo_path,
    write_builder_outputs,
)


PRESET = ScaleupPilotPreset.from_target_ligand_size(1_000_000)


def _build_launch_readiness(drift_audit: dict[str, object]) -> dict[str, object]:
    blockers: list[str] = []
    if int(drift_audit.get("nonstandard_ligand_size_count", 0) or 0) > 0:
        blockers.append("pilot spec contains ligand_stress tasks outside the allowed 1000000/64 shape")
    if int(drift_audit.get("full_task_non_target_count", 0) or 0) > 0:
        blockers.append("one or more full ligand_stress tasks are not set to 1000000 ligands")
    if int(drift_audit.get("smoke_task_non_64_count", 0) or 0) > 0:
        blockers.append("one or more smoke ligand_stress tasks are not preserved at 64 ligands")
    if int(drift_audit.get("profile_missing_strict_preset_count", 0) or 0) > 0:
        blockers.append("one or more cloned full-task profiles are missing strict auto-preset governance")
    if int(drift_audit.get("profile_missing_speedpack_count", 0) or 0) > 0:
        blockers.append("one or more cloned full-task profiles are missing speedpack")
    if int(drift_audit.get("profile_missing_light_artifacts_count", 0) or 0) > 0:
        blockers.append("one or more cloned full-task profiles are missing light-artifact mode")
    if int(drift_audit.get("profile_missing_intent_count", 0) or 0) > 0:
        blockers.append("one or more cloned full-task profiles are missing traj_prod_profile_intent")
    return {
        "ready": len(blockers) == 0,
        "status": "ready" if len(blockers) == 0 else "blocked",
        "blocking_issue_count": len(blockers),
        "blocking_issues": blockers,
        "comparison_required": True,
        "next_required_step": "Run the 1M pilot runner with --dry-run and confirm comparison is enabled before launch.",
    }


def build_pilot_payload(*args, **kwargs):
    payload = _base_build_pilot_payload(*args, **kwargs)
    payload["launch_readiness"] = _build_launch_readiness(dict(payload.get("drift_audit", {})))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Build the production-only {PRESET.target_scale_label} ligand scale-up pilot spec and cloned profiles."
    )
    parser.add_argument("--base-spec-json", default="config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json")
    parser.add_argument("--out-config-dir", default="config")
    parser.add_argument("--out-json", default="runs/ligand_scaleup_1m_pilot_current.json")
    parser.add_argument("--out-csv", default="runs/ligand_scaleup_1m_pilot_current.csv")
    parser.add_argument("--out-task-csv", default="runs/ligand_scaleup_1m_pilot_tasks_current.csv")
    parser.add_argument("--out-md", default="runs/ligand_scaleup_1m_pilot_current.md")
    args = parser.parse_args()

    payload = build_pilot_payload(
        base_spec_path=resolve_repo_path(args.base_spec_json),
        out_config_dir=resolve_repo_path(args.out_config_dir),
        preset=PRESET,
        runner_script_name="tools/run_ligand_scaleup_1m_pilot_current.py",
    )
    write_builder_outputs(
        payload=payload,
        out_json=resolve_repo_path(args.out_json),
        out_csv=resolve_repo_path(args.out_csv),
        out_task_csv=resolve_repo_path(args.out_task_csv),
        out_md=resolve_repo_path(args.out_md),
        preset=PRESET,
    )
    print(json.dumps({"ok": True, "pilot_spec_json": payload["pilot_spec_json"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
