#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_throughput_bridge as primary_bridge
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_PRIMARY_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_antitarget_throughput_bridge_current.md"
COMMAND_PREFERENCE = [
    "throughput_preflight_tuned_gate55",
    "throughput_preflight_tuned",
    "throughput_preflight",
]


def _select_antitarget_row(execution_queue: dict[str, Any], primary_target_id: str = "", anti_target_id: str = "", shard_id: str = "") -> dict[str, Any]:
    rows = [dict(row) for row in (execution_queue.get("rows", []) or [])]
    if primary_target_id and anti_target_id and shard_id:
        for row in rows:
            if (
                str(row.get("primary_target_id", "")).strip() == primary_target_id
                and str(row.get("anti_target_id", "")).strip() == anti_target_id
                and str(row.get("primary_shard_id", "")).strip() == shard_id
            ):
                return row
    summary = dict(execution_queue.get("summary", {}) or {})
    first_primary = str(summary.get("first_actionable_primary_target_id", "")).strip()
    first_anti = str(summary.get("first_actionable_anti_target_id", "")).strip()
    first_shard = str(summary.get("first_actionable_shard_id", "")).strip()
    for row in rows:
        if (
            str(row.get("primary_target_id", "")).strip() == first_primary
            and str(row.get("anti_target_id", "")).strip() == first_anti
            and str(row.get("primary_shard_id", "")).strip() == first_shard
        ):
            return row
    return rows[0] if rows else {}


def _primary_queue_row(primary_queue: dict[str, Any], primary_target_id: str, shard_id: str) -> dict[str, Any]:
    for row in (primary_queue.get("rows", []) or []):
        if str(row.get("target_id", "")).strip() == primary_target_id and str(row.get("shard_id", "")).strip() == shard_id:
            return dict(row)
    return {}


def _domain_family_for_target(portfolio: dict[str, Any], target_id: str) -> str:
    for row in (portfolio.get("rows", []) or []):
        if str(row.get("target_id", "")).strip() == target_id:
            return str(row.get("domain_family", "")).strip()
    return ""


def _tuning_target(primary_target_id: str, anti_target_id: str) -> str:
    if primary_target_id == "CA IX" and anti_target_id in {"CA II", "CA XII"}:
        return "CA IX"
    return anti_target_id


def build_payload(
    antitarget_execution_queue: dict[str, Any],
    primary_queue: dict[str, Any],
    compound_universe: dict[str, Any],
    portfolio: dict[str, Any],
    *,
    target_native_csv: str = DEFAULT_TARGET_NATIVE_CSV,
    primary_target_id: str = "",
    anti_target_id: str = "",
    shard_id: str = "",
) -> dict[str, Any]:
    selected = _select_antitarget_row(
        antitarget_execution_queue,
        primary_target_id=primary_target_id,
        anti_target_id=anti_target_id,
        shard_id=shard_id,
    )
    primary_target_id = str(selected.get("primary_target_id", "")).strip()
    anti_target_id = str(selected.get("anti_target_id", "")).strip()
    shard_id = str(selected.get("primary_shard_id", "")).strip()
    queue_status = str(selected.get("queue_status", "")).strip()
    panel_rank = int(selected.get("anti_target_panel_rank", 0) or 0)
    runner_kind = str(selected.get("runner_kind", "")).strip()

    primary_row = _primary_queue_row(primary_queue, primary_target_id, shard_id)
    compound_index_start = int(primary_row.get("compound_index_start", 0) or 0)
    compound_index_end = int(primary_row.get("compound_index_end", 0) or 0)
    shard_size = int(primary_row.get("shard_size", 0) or 0)

    target_slug = primary_bridge._slug(primary_target_id)
    anti_slug = primary_bridge._slug(anti_target_id)
    shard_slug = str(shard_id).replace("/", "_")
    tuning_target_id = _tuning_target(primary_target_id, anti_target_id)
    domain_family = _domain_family_for_target(portfolio, primary_target_id) or _domain_family_for_target(portfolio, anti_target_id)
    stage2_preset = primary_bridge._domain_to_stage2_preset(domain_family)
    slow_shard_profile_id, slow_shard_extra_args = primary_bridge._slow_shard_extra_args(tuning_target_id)
    gate_relax_profile_id, gate_relax_extra_args = primary_bridge._gate_relax_extra_args(tuning_target_id)

    shard_rows = primary_bridge._slice_universe(compound_universe, compound_index_start, compound_index_end)
    manifest_rows = primary_bridge._manifest_rows(shard_rows, anti_slug, shard_slug)

    artifact_dir = ROOT / "runs" / "wetlab_broad_screen_antitarget_throughput" / target_slug / anti_slug / shard_slug
    ligand_csv = artifact_dir / "ligand_manifest.csv"
    target_csv = artifact_dir / "target_native_stub.csv"
    out_prefix = artifact_dir / "throughput_run"
    primary_bridge._write_csv(ligand_csv, manifest_rows)
    native_mapping_present, native_mapping_note = primary_bridge._write_target_native_stub(target_csv, anti_target_id, ROOT / target_native_csv)

    manifest_row_count = len(manifest_rows)
    smiles_ready_row_count = sum(1 for row in manifest_rows if str(row.get("smiles", "")).strip())
    smiles_coverage_pct = round((100.0 * smiles_ready_row_count / manifest_row_count), 1) if manifest_row_count else 0.0
    throughput_execute_ready = manifest_row_count > 0 and smiles_ready_row_count > 0

    base_kwargs = {
        "target_id": anti_target_id,
        "ligand_csv": ligand_csv,
        "target_native_csv": target_csv,
        "stage2_preset": stage2_preset,
    }
    preflight_command = primary_bridge._build_command(out_prefix=out_prefix, dry_run=True, extra_args=None, **base_kwargs)
    execute_command = primary_bridge._build_command(out_prefix=out_prefix, dry_run=False, extra_args=None, **base_kwargs)
    tuned_preflight_command = primary_bridge._build_command(out_prefix=out_prefix, dry_run=True, extra_args=slow_shard_extra_args, **base_kwargs)
    tuned_execute_command = primary_bridge._build_command(out_prefix=out_prefix, dry_run=False, extra_args=slow_shard_extra_args, **base_kwargs)
    tuned_gate55_out_prefix = artifact_dir / "throughput_run_gate55"
    tuned_gate55_preflight_command = primary_bridge._build_command(
        out_prefix=tuned_gate55_out_prefix,
        dry_run=True,
        extra_args=[*slow_shard_extra_args, *gate_relax_extra_args],
        **base_kwargs,
    )
    tuned_gate55_execute_command = primary_bridge._build_command(
        out_prefix=tuned_gate55_out_prefix,
        dry_run=False,
        extra_args=[*slow_shard_extra_args, *gate_relax_extra_args],
        **base_kwargs,
    )
    preferred_command_kind = primary_bridge._preferred_command_kind(slow_shard_profile_id, gate_relax_profile_id, "", "")
    preferred_out_prefix = artifact_dir / ("throughput_run_gate55" if preferred_command_kind.endswith("gate55") else "throughput_run")
    preferred_summary_json = preferred_out_prefix.with_name(preferred_out_prefix.name + "_summary.json")
    preferred_summary_md = preferred_out_prefix.with_name(preferred_out_prefix.name + "_summary.md")
    preferred_log_path = artifact_dir / (preferred_command_kind + ".log")
    preferred_pid_path = artifact_dir / (preferred_command_kind + ".pid")

    return {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_throughput_bridge_ready",
            "primary_target_id": primary_target_id,
            "anti_target_id": anti_target_id,
            "shard_id": shard_id,
            "queue_status": queue_status,
            "runner_kind": runner_kind,
            "anti_target_panel_rank": panel_rank,
            "domain_family": domain_family,
            "traj_prod_stage2_preset": stage2_preset,
            "manifest_row_count": manifest_row_count,
            "smiles_ready_row_count": smiles_ready_row_count,
            "smiles_coverage_pct": smiles_coverage_pct,
            "native_mapping_present": native_mapping_present,
            "native_mapping_note": native_mapping_note,
            "slow_shard_profile_id": slow_shard_profile_id,
            "slow_shard_profile_ready": bool(slow_shard_profile_id),
            "gate_relax_profile_id": gate_relax_profile_id,
            "gate_relax_profile_ready": bool(gate_relax_profile_id),
            "preferred_command_kind": preferred_command_kind,
            "throughput_preflight_ready": bool(primary_target_id and anti_target_id and shard_id and manifest_row_count > 0),
            "throughput_execute_ready": throughput_execute_ready,
            "throughput_launch_mode": "preflight_plus_execute" if throughput_execute_ready else "preflight_only_missing_smiles_or_target_rows",
            "next_required_step": (
                f"Use the preferred counterscreen throughput preflight command for {primary_target_id} -> {anti_target_id} {shard_id}; switch to execute after preflight passes."
                if primary_target_id and anti_target_id and shard_id
                else "No actionable anti-target counterscreen shard is available for throughput bridging yet."
            ),
        },
        "structured": {
            "artifact_dir": str(artifact_dir),
            "ligand_manifest_csv": str(ligand_csv),
            "target_native_stub_csv": str(target_csv),
            "out_prefix": str(out_prefix),
            "preferred_out_prefix": str(preferred_out_prefix),
            "preferred_summary_json": str(preferred_summary_json),
            "preferred_summary_md": str(preferred_summary_md),
            "preferred_log_path": str(preferred_log_path),
            "preferred_pid_path": str(preferred_pid_path),
            "target_native_source_csv": str((ROOT / target_native_csv).resolve()),
            "antitarget_execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
            "primary_queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "compound_universe_artifact": "runs/wetlab_broad_screen_compound_universe_current.md",
            "portfolio_artifact": "runs/wetlab_partner_target_portfolio_current.md",
            "slow_shard_profile_artifact": "runs/caix_slow_shard_preset_current.md" if slow_shard_profile_id else "",
            "gate_tuning_surface_artifact": "runs/caix_stage6_gate_tuning_surface_current.md" if gate_relax_profile_id else "",
        },
        "rows": [
            {"command_kind": "throughput_preflight", "enabled": True, "dry_run": True, "command": preflight_command},
            {"command_kind": "throughput_execute", "enabled": throughput_execute_ready, "dry_run": False, "command": execute_command},
            {"command_kind": "throughput_preflight_tuned", "enabled": bool(slow_shard_profile_id), "dry_run": True, "command": tuned_preflight_command},
            {"command_kind": "throughput_execute_tuned", "enabled": bool(slow_shard_profile_id) and throughput_execute_ready, "dry_run": False, "command": tuned_execute_command},
            {"command_kind": "throughput_preflight_tuned_gate55", "enabled": bool(slow_shard_profile_id) and bool(gate_relax_profile_id), "dry_run": True, "command": tuned_gate55_preflight_command},
            {"command_kind": "throughput_execute_tuned_gate55", "enabled": bool(slow_shard_profile_id) and bool(gate_relax_profile_id) and throughput_execute_ready, "dry_run": False, "command": tuned_gate55_execute_command},
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge the current anti-target counterscreen shard into the HTVS throughput runner shape.")
    parser.add_argument("--antitarget-execution-queue-json", default=DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--primary-queue-json", default=DEFAULT_PRIMARY_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--primary-target-id", default="")
    parser.add_argument("--anti-target-id", default="")
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Anti-Target Throughput Bridge",
        build_payload(
            antitarget_execution_queue=load_json(args.antitarget_execution_queue_json),
            primary_queue=load_json(args.primary_queue_json),
            compound_universe=load_json(args.compound_universe_json),
            portfolio=load_json(args.portfolio_json),
            target_native_csv=args.target_native_csv,
            primary_target_id=args.primary_target_id,
            anti_target_id=args.anti_target_id,
            shard_id=args.shard_id,
        ),
    )
