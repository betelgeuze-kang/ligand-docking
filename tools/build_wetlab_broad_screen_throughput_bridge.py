#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import shlex
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_throughput_bridge_current.md"

MANIFEST_HEADERS = [
    "ligand_id",
    "smiles",
    "molecular_weight",
    "logp",
    "h_donors",
    "h_acceptors",
    "rot_bonds",
    "compound_name",
    "compound_index",
    "approval_class",
    "procurement_tier",
    "source_dataset",
    "source_anchor",
    "source_url",
]


def _slug(text: str) -> str:
    return (
        str(text or "")
        .lower()
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )


def _target_rows_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in (payload.get("rows", []) or [])
        if str(row.get("target_id", "")).strip()
    }


def _select_queue_row(execution_queue: dict[str, Any], target_id: str = "", shard_id: str = "") -> dict[str, Any]:
    rows = [dict(row) for row in (execution_queue.get("rows", []) or [])]
    if target_id and shard_id:
        for row in rows:
            if str(row.get("target_id", "")).strip() == target_id and str(row.get("shard_id", "")).strip() == shard_id:
                return row
    summary = dict(execution_queue.get("summary", {}) or {})
    first_target = str(summary.get("first_actionable_target_id", "")).strip()
    first_shard = str(summary.get("first_actionable_shard_id", "")).strip()
    for row in rows:
        if str(row.get("target_id", "")).strip() == first_target and str(row.get("shard_id", "")).strip() == first_shard:
            return row
    return rows[0] if rows else {}


def _slice_universe(compound_universe: dict[str, Any], start_idx: int, end_idx: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (compound_universe.get("rows", []) or []):
        idx = int(row.get("compound_index", 0) or 0)
        if start_idx <= idx <= end_idx:
            rows.append(dict(row))
    return rows


def _domain_to_stage2_preset(domain_family: str) -> str:
    text = str(domain_family or "").strip().lower()
    tokens = {token for token in text.replace("/", "_").replace("-", "_").split("_") if token}
    if "gpcr" in text:
        return "gpcr"
    if "trpv1" in text or "ion_channel" in text or {"ion", "channel"} <= tokens:
        return "ion_trpv1"
    if "kinase" in text or "protease" in text:
        return "kinase_protease"
    return "default"


def _slow_shard_extra_args(target_id: str) -> tuple[str, list[str]]:
    if str(target_id).strip() != "CA IX":
        return "", []
    profile_id = "caix_slow_shard_v1"
    return profile_id, [
        "--traj-prod-profile-intent",
        profile_id,
        "--traj-prod-early-stop-enabled",
        "--traj-prod-min-frames-full",
        "128",
        "--traj-prod-early-stop-min-frames-full",
        "112",
        "--traj-prod-early-stop-window",
        "10",
        "--traj-prod-early-stop-max-mean-min-distance-A",
        "5.0",
        "--traj-job-batch-autotune-candidates",
        "4,8,16",
        "--traj-writer-workers",
        "2",
        "--traj-dynamic-adress-max-protein-residues",
        "170",
        "--traj-dynamic-adress-fraction",
        "0.12",
    ]


def _gate_relax_extra_args(target_id: str) -> tuple[str, list[str]]:
    target = str(target_id).strip()
    if target == "CA IX":
        profile_id = "caix_slow_shard_v1_gate55"
    elif target == "SARS-CoV-2 PLpro":
        profile_id = "plpro_manual_retry_gate55"
    elif target == "LRRK2":
        profile_id = "lrrk2_panel_first_gate55"
    else:
        return "", []
    return profile_id, [
        "--gate-max-mean-min-distance-A",
        "5.5",
        "--strict-gate-max-mean-min-distance-A",
        "5.5",
    ]


def _observed_band_gate_relax_extra_args(target_id: str) -> tuple[str, list[str]]:
    target = str(target_id).strip()
    if target == "Leishmania braziliensis DHODH":
        profile_id = "lbdhodh_exploratory_gate51"
    elif target == "T. cruzi PDE":
        profile_id = "tcruzi_pde_stage6_gate51"
    elif target == "T. cruzi KRS1":
        profile_id = "tcruzi_krs1_stage6_gate51"
    elif target == "DprE1":
        profile_id = "dpre1_stage6_gate51"
    else:
        return "", []
    return profile_id, [
        "--gate-max-mean-min-distance-A",
        "5.1",
        "--strict-gate-max-mean-min-distance-A",
        "5.1",
    ]


def _exploratory_gate_relax_extra_args(target_id: str) -> tuple[str, list[str]]:
    target = str(target_id).strip()
    if target == "STK17B (DRAK2)":
        profile_id = "stk17b_exploratory_gate45"
    elif target == "Cathepsin K":
        profile_id = "cathepsin_k_stage6_gate45"
    elif target == "SARS-CoV-2 Mpro":
        profile_id = "sarscov2_mpro_stage6_gate45"
    elif target == "Dengue NS2B-NS3 protease":
        profile_id = "dengue_ns2b_ns3_stage6_gate45"
    else:
        return "", []
    return profile_id, [
        "--gate-max-mean-min-distance-A",
        "4.5",
        "--strict-gate-max-mean-min-distance-A",
        "4.5",
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in MANIFEST_HEADERS})


def _write_target_native_stub(path: Path, target_id: str, native_csv: Path) -> tuple[bool, str]:
    native_mapping_present = False
    mapping_note = "generated_stub_no_native_mapping"
    rows = []
    if native_csv.exists():
        with native_csv.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                candidate = str(row.get("target", "")).strip()
                if candidate == target_id:
                    rows.append(dict(row))
                    native_mapping_present = True
                    mapping_note = "repo_native_mapping_present"
                    break
    if not rows:
        rows = [
            {
                "target": target_id,
                "native_pdb_path": "",
                "pdb_id": "",
                "notes": "wetlab_broad_screen_throughput_stub_no_native_path",
            }
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["target", "native_pdb_path", "pdb_id", "notes"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return native_mapping_present, mapping_note


def _manifest_rows(raw_rows: list[dict[str, Any]], target_slug: str, shard_id: str) -> list[dict[str, Any]]:
    def _clean_float(value: Any, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return float(default)
        if math.isnan(numeric) or math.isinf(numeric):
            return float(default)
        return float(numeric)

    def _clean_int(value: Any, default: int) -> int:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return int(default)
        if math.isnan(numeric) or math.isinf(numeric):
            return int(default)
        return int(numeric)

    out: list[dict[str, Any]] = []
    for row in raw_rows:
        idx = int(row.get("compound_index", 0) or 0)
        smiles = str(row.get("canonical_smiles", "") or "").strip()
        out.append(
            {
                "ligand_id": f"{target_slug}_{shard_id}_{idx:06d}",
                "smiles": smiles,
                "molecular_weight": _clean_float(row.get("molecular_weight", ""), max(float(len(smiles) * 7.5), 50.0)),
                "logp": _clean_float(row.get("logp", ""), min(max((len(smiles) / 20.0) - 0.5, -2.0), 8.0)),
                "h_donors": _clean_int(row.get("h_donors", ""), 0),
                "h_acceptors": _clean_int(row.get("h_acceptors", ""), 0),
                "rot_bonds": _clean_int(row.get("rot_bonds", ""), max(len(smiles) // 14, 0)),
                "compound_name": str(row.get("compound_name", "") or "").strip(),
                "compound_index": idx,
                "approval_class": row.get("approval_class", ""),
                "procurement_tier": row.get("procurement_tier", ""),
                "source_dataset": row.get("source_dataset", ""),
                "source_anchor": row.get("source_anchor", ""),
                "source_url": row.get("source_url", ""),
            }
        )
    return out


def _build_command(
    *,
    target_id: str,
    ligand_csv: Path,
    target_native_csv: Path,
    out_prefix: Path,
    stage2_preset: str,
    dry_run: bool,
    extra_args: list[str] | None = None,
) -> str:
    parts = [
        "python3",
        "tools/run_ligand_htvs_pipeline.py",
        "--run-scope",
        "full",
        "--targets",
        target_id,
        "--out-prefix",
        str(out_prefix),
        "--ligand-csv",
        str(ligand_csv),
        "--target-native-csv",
        str(target_native_csv),
        "--no-require-native-path",
        "--traj-prod-speedpack",
        "--traj-prod-light-artifacts",
        "--traj-prod-stage2-preset",
        stage2_preset,
        "--stage3-score-only",
        "--no-run-ranking-eval",
        "--reuse-stage1-if-exists",
        "--no-single-instance",
        "--dry-run" if dry_run else "--no-dry-run",
    ]
    parts.extend(list(extra_args or []))
    return shlex.join(parts)


def _preferred_command_kind(slow_profile: str, gate_profile: str, observed_band_profile: str, exploratory_profile: str) -> str:
    if exploratory_profile:
        return "throughput_preflight_tuned_gate45"
    if observed_band_profile:
        return "throughput_preflight_tuned_gate51"
    if gate_profile:
        return "throughput_preflight_tuned_gate55"
    if slow_profile:
        return "throughput_preflight_tuned"
    return "throughput_preflight"


def _prefer_exploratory_followup_command(target_id: str, shard_id: str) -> bool:
    if str(target_id).strip() != "STK17B (DRAK2)":
        return False
    lane_payload = maybe_load_json(DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON) or {}
    summary = dict(lane_payload.get("summary", {}) or {})
    status = str(summary.get("status", "")).strip()
    if not status.startswith("wetlab_stk17b_exploratory_followup_lane_"):
        return False
    if "gate45" not in str(summary.get("selected_command_kind", "")).strip():
        return False
    shard_ids = {
        shard.strip()
        for shard in str(summary.get("followup_shard_ids", "")).split(";")
        if shard.strip()
    }
    return str(shard_id).strip() in shard_ids


def build_payload(
    execution_queue: dict[str, Any],
    compound_universe: dict[str, Any],
    portfolio: dict[str, Any],
    *,
    target_native_csv: str = DEFAULT_TARGET_NATIVE_CSV,
    target_id: str = "",
    shard_id: str = "",
) -> dict[str, Any]:
    selected = _select_queue_row(execution_queue, target_id=target_id, shard_id=shard_id)
    target_id = str(selected.get("target_id", "")).strip()
    shard_id = str(selected.get("shard_id", "")).strip()
    queue_status = str(selected.get("queue_status", "")).strip()
    target_slug = _slug(target_id)
    shard_slug = str(shard_id).replace("/", "_")
    stage2_preset = _domain_to_stage2_preset(_target_rows_by_id(portfolio).get(target_id, {}).get("domain_family", ""))
    slow_shard_profile_id, slow_shard_extra_args = _slow_shard_extra_args(target_id)
    gate_relax_profile_id, gate_relax_extra_args = _gate_relax_extra_args(target_id)
    observed_band_gate_relax_profile_id, observed_band_gate_relax_extra_args = _observed_band_gate_relax_extra_args(target_id)
    exploratory_gate_relax_profile_id, exploratory_gate_relax_extra_args = _exploratory_gate_relax_extra_args(target_id)

    start_idx = int(selected.get("compound_index_start", 0) or 0)
    end_idx = int(selected.get("compound_index_end", 0) or 0)
    shard_rows = _slice_universe(compound_universe, start_idx, end_idx)
    manifest_rows = _manifest_rows(shard_rows, target_slug, shard_slug)

    artifact_dir = ROOT / "runs" / "wetlab_broad_screen_throughput" / target_slug / shard_slug
    ligand_csv = artifact_dir / "ligand_manifest.csv"
    target_csv = artifact_dir / "target_native_stub.csv"
    out_prefix = artifact_dir / "throughput_run"

    _write_csv(ligand_csv, manifest_rows)
    native_mapping_present, native_mapping_note = _write_target_native_stub(target_csv, target_id, ROOT / target_native_csv)

    smiles_ready_row_count = sum(1 for row in manifest_rows if str(row.get("smiles", "")).strip())
    manifest_row_count = len(manifest_rows)
    smiles_coverage_pct = round((100.0 * smiles_ready_row_count / manifest_row_count), 1) if manifest_row_count else 0.0
    throughput_execute_ready = manifest_row_count > 0 and smiles_ready_row_count > 0

    preflight_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=out_prefix,
        stage2_preset=stage2_preset,
        dry_run=True,
    )
    execute_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=out_prefix,
        stage2_preset=stage2_preset,
        dry_run=False,
    )
    tuned_preflight_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=out_prefix,
        stage2_preset=stage2_preset,
        dry_run=True,
        extra_args=slow_shard_extra_args,
    )
    tuned_execute_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=out_prefix,
        stage2_preset=stage2_preset,
        dry_run=False,
        extra_args=slow_shard_extra_args,
    )
    tuned_gate55_preflight_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=artifact_dir / "throughput_run_gate55",
        stage2_preset=stage2_preset,
        dry_run=True,
        extra_args=[*slow_shard_extra_args, *gate_relax_extra_args],
    )
    tuned_gate55_execute_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=artifact_dir / "throughput_run_gate55",
        stage2_preset=stage2_preset,
        dry_run=False,
        extra_args=[*slow_shard_extra_args, *gate_relax_extra_args],
    )
    tuned_gate51_preflight_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=artifact_dir / "throughput_run_gate51",
        stage2_preset=stage2_preset,
        dry_run=True,
        extra_args=[*slow_shard_extra_args, *observed_band_gate_relax_extra_args],
    )
    tuned_gate51_execute_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=artifact_dir / "throughput_run_gate51",
        stage2_preset=stage2_preset,
        dry_run=False,
        extra_args=[*slow_shard_extra_args, *observed_band_gate_relax_extra_args],
    )
    tuned_gate45_preflight_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=artifact_dir / "throughput_run_gate45",
        stage2_preset=stage2_preset,
        dry_run=True,
        extra_args=[*slow_shard_extra_args, *exploratory_gate_relax_extra_args],
    )
    tuned_gate45_execute_command = _build_command(
        target_id=target_id,
        ligand_csv=ligand_csv,
        target_native_csv=target_csv,
        out_prefix=artifact_dir / "throughput_run_gate45",
        stage2_preset=stage2_preset,
        dry_run=False,
        extra_args=[*slow_shard_extra_args, *exploratory_gate_relax_extra_args],
    )
    preferred_command_kind = (
        "throughput_preflight_tuned_gate45"
        if _prefer_exploratory_followup_command(target_id, shard_id)
        else _preferred_command_kind(
            slow_shard_profile_id,
            gate_relax_profile_id,
            observed_band_gate_relax_profile_id,
            exploratory_gate_relax_profile_id,
        )
    )
    preferred_out_prefix = artifact_dir / (
        "throughput_run_gate45"
        if preferred_command_kind.endswith("gate45")
        else "throughput_run_gate51"
        if preferred_command_kind.endswith("gate51")
        else "throughput_run_gate55"
        if preferred_command_kind.endswith("gate55")
        else "throughput_run"
    )
    preferred_summary_json = preferred_out_prefix.with_name(preferred_out_prefix.name + "_summary.json")
    preferred_summary_md = preferred_out_prefix.with_name(preferred_out_prefix.name + "_summary.md")
    preferred_log_path = artifact_dir / (preferred_command_kind + ".log")
    preferred_pid_path = artifact_dir / (preferred_command_kind + ".pid")

    return {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "queue_status": queue_status,
            "domain_family": str(_target_rows_by_id(portfolio).get(target_id, {}).get("domain_family", "")).strip(),
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
            "observed_band_gate_relax_profile_id": observed_band_gate_relax_profile_id,
            "observed_band_gate_relax_profile_ready": bool(observed_band_gate_relax_profile_id),
            "exploratory_gate_relax_profile_id": exploratory_gate_relax_profile_id,
            "exploratory_gate_relax_profile_ready": bool(exploratory_gate_relax_profile_id),
            "preferred_command_kind": preferred_command_kind,
            "throughput_preflight_ready": bool(target_id and shard_id and manifest_row_count > 0),
            "throughput_execute_ready": throughput_execute_ready,
            "throughput_launch_mode": "preflight_plus_execute" if throughput_execute_ready else "preflight_only_missing_smiles_or_target_rows",
            "next_required_step": (
                (
                    f"Use the exploratory gate4.5 throughput preflight command for {target_id} {shard_id}; switch to the matching execute command after preflight passes."
                    if preferred_command_kind.endswith("gate45")
                    else
                    f"Use the exploratory gate5.1 throughput preflight command for {target_id} {shard_id}; switch to the matching execute command after preflight passes."
                    if preferred_command_kind.endswith("gate51")
                    else
                    f"Use the tuned gate-relaxed throughput preflight command for {target_id} {shard_id}; switch to the matching execute command after preflight passes."
                    if preferred_command_kind.endswith("gate55")
                    else (
                        f"Use the tuned throughput preflight command for {target_id} {shard_id}; switch to the matching execute command after preflight passes."
                        if preferred_command_kind.endswith("tuned")
                        else f"Use the standard throughput preflight command for {target_id} {shard_id}; switch to the matching execute command after preflight passes."
                    )
                )
                if target_id and shard_id
                else "No actionable broad-screen shard is available for throughput bridging yet."
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
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "compound_universe_artifact": "runs/wetlab_broad_screen_compound_universe_current.md",
            "portfolio_artifact": "runs/wetlab_partner_target_portfolio_current.md",
            "slow_shard_profile_artifact": "runs/caix_slow_shard_preset_current.md" if slow_shard_profile_id else "",
            "gate_tuning_surface_artifact": "runs/caix_stage6_gate_tuning_surface_current.md" if slow_shard_profile_id else "",
        },
        "rows": [
            {
                "command_kind": "throughput_preflight",
                "enabled": True,
                "dry_run": True,
                "command": preflight_command,
            },
            {
                "command_kind": "throughput_execute",
                "enabled": throughput_execute_ready,
                "dry_run": False,
                "command": execute_command,
            },
            {
                "command_kind": "throughput_preflight_tuned",
                "enabled": bool(slow_shard_profile_id),
                "dry_run": True,
                "command": tuned_preflight_command,
            },
            {
                "command_kind": "throughput_execute_tuned",
                "enabled": bool(slow_shard_profile_id) and throughput_execute_ready,
                "dry_run": False,
                "command": tuned_execute_command,
            },
            {
                "command_kind": "throughput_preflight_tuned_gate55",
                "enabled": bool(gate_relax_profile_id),
                "dry_run": True,
                "command": tuned_gate55_preflight_command,
            },
            {
                "command_kind": "throughput_execute_tuned_gate55",
                "enabled": bool(gate_relax_profile_id) and throughput_execute_ready,
                "dry_run": False,
                "command": tuned_gate55_execute_command,
            },
            {
                "command_kind": "throughput_preflight_tuned_gate51",
                "enabled": bool(observed_band_gate_relax_profile_id),
                "dry_run": True,
                "command": tuned_gate51_preflight_command,
            },
            {
                "command_kind": "throughput_execute_tuned_gate51",
                "enabled": bool(observed_band_gate_relax_profile_id) and throughput_execute_ready,
                "dry_run": False,
                "command": tuned_gate51_execute_command,
            },
            {
                "command_kind": "throughput_preflight_tuned_gate45",
                "enabled": bool(exploratory_gate_relax_profile_id),
                "dry_run": True,
                "command": tuned_gate45_preflight_command,
            },
            {
                "command_kind": "throughput_execute_tuned_gate45",
                "enabled": bool(exploratory_gate_relax_profile_id) and throughput_execute_ready,
                "dry_run": False,
                "command": tuned_gate45_execute_command,
            },
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bridge the current wet-lab broad-screen shard into the existing HTVS throughput runner shape.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Throughput Bridge",
        build_payload(
            execution_queue=load_json(args.execution_queue_json),
            compound_universe=load_json(args.compound_universe_json),
            portfolio=load_json(args.portfolio_json),
            target_native_csv=args.target_native_csv,
            target_id=args.target_id,
            shard_id=args.shard_id,
        ),
    )
