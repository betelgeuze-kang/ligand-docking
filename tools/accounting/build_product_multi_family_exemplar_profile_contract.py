#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.htvs_command import build_htvs_command_from_profile_json
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_multi_family_exemplar_profile_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_multi_family_exemplar_profile_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_multi_family_exemplar_profile_contract_current.md"

EXEMPLARS = [
    {
        "family": "gpcr",
        "target_id": "ADRB2",
        "profile_json": "config/ligand_htvs_blind_gpcr_adrb2_chembl20_product_gate_repair_v1.json",
        "bundle_tag": "product_gpcr_adrb2",
        "profile_out_prefix": "runs/product_gpcr_adrb2_after_approval",
        "planned_artifact_path": "runs/product_gpcr_adrb2_after_approval_summary.json",
    },
    {
        "family": "kinase",
        "target_id": "EGFR",
        "profile_json": "config/ligand_htvs_blind_kinase_egfr_product_exemplar_v1.json",
        "bundle_tag": "product_kinase_egfr",
        "profile_out_prefix": "runs/product_kinase_egfr_after_approval",
        "planned_artifact_path": "runs/product_kinase_egfr_after_approval_summary.json",
    },
    {
        "family": "ion_channel",
        "target_id": "TRPV1",
        "profile_json": "config/ligand_htvs_blind_ion_channel_trpv1_product_exemplar_v1.json",
        "bundle_tag": "product_ion_channel_trpv1",
        "profile_out_prefix": "runs/product_ion_channel_trpv1_after_approval",
        "planned_artifact_path": "runs/product_ion_channel_trpv1_after_approval_summary.json",
    },
]

CLAIM_BOUNDARY = (
    "Product multi-family exemplar profile contract only; it validates restricted local-delivery HTVS profile "
    "templates for gpcr, kinase, and ion_channel families and emits bundle/work-order command templates. "
    "It does not run docking, assemble bundles, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _profile_paths(profile: dict[str, Any]) -> list[str]:
    keys = (
        "target_native_csv",
        "ligand_csv",
        "eval_split_csv",
        "calibration_reference_csv",
        "ranking_labels_csv",
        "hard_decoy_reference_csv",
        "hard_decoy_ligand_meta_csv",
        "hard_decoy_target_meta_csv",
        "leakage_ligand_meta_csv",
        "leakage_target_meta_csv",
    )
    paths: list[str] = []
    for key in keys:
        value = _text(profile.get(key))
        if value and value not in paths:
            paths.append(value)
    return paths


def build_contract() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for item in EXEMPLARS:
        profile_path = item["profile_json"]
        profile = _read_json(profile_path)
        profile_abs = _resolve(profile_path)
        missing_paths = [rel for rel in _profile_paths(profile) if not _resolve(rel).exists()]
        product_exemplar = profile.get("product_exemplar") if isinstance(profile.get("product_exemplar"), dict) else {}
        bundle_tag = _text(product_exemplar.get("bundle_tag")) or item["bundle_tag"]
        out_prefix = _text(product_exemplar.get("profile_out_prefix")) or item["profile_out_prefix"]
        planned_artifact = _text(product_exemplar.get("planned_artifact_path")) or item["planned_artifact_path"]
        command_generation = (
            build_htvs_command_from_profile_json(profile_abs, out_prefix=out_prefix)
            if profile_abs.exists()
            else {}
        )
        execution_command = _text(command_generation.get("execution_command")) or _text(
            command_generation.get("command")
        )
        ready = profile_abs.exists() and not missing_paths and bool(execution_command)
        if not profile_abs.exists():
            blockers.append(f"multi_family:{item['family']}:profile_missing")
        if missing_paths:
            blockers.append(f"multi_family:{item['family']}:config_paths_missing")
        if not execution_command:
            blockers.append(f"multi_family:{item['family']}:execution_command_missing")
        rows.append(
            {
                "family": item["family"],
                "target_id": item["target_id"],
                "profile_json": profile_path,
                "profile_present": profile_abs.exists(),
                "bundle_tag": bundle_tag,
                "profile_out_prefix": out_prefix,
                "planned_artifact_path": planned_artifact,
                "execution_command": execution_command,
                "missing_config_paths": ";".join(missing_paths),
                "claim_scope": _text(product_exemplar.get("claim_scope")) or "restricted_local_delivery_only",
                "status": "ready" if ready else "blocked",
                "release_blocker": False,
            }
        )
    ready_count = sum(1 for row in rows if row["status"] == "ready")
    summary = {
        "packet_type": "product_multi_family_exemplar_profile_contract",
        "status": (
            "product_multi_family_exemplar_profile_contract_ready"
            if ready_count == len(rows)
            else "blocked_product_multi_family_exemplar_profile_contract"
        ),
        "exemplar_count": len(rows),
        "ready_exemplar_count": ready_count,
        "allowed_scope_families": [row["family"] for row in rows],
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "All restricted local-delivery family exemplar profiles are ready for work-order and bundle templating."
            if ready_count == len(rows)
            else "Repair missing profile/config paths for blocked family exemplars before repeating bundle templating."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# Product Multi-Family Exemplar Profile Contract",
        "",
        f"- status: `{summary['status']}`",
        f"- exemplar_count: `{summary['exemplar_count']}`",
        f"- ready_exemplar_count: `{summary['ready_exemplar_count']}`",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            f"- `{row['family']}` / `{row['target_id']}`: `{row['status']}` bundle=`{row['bundle_tag']}`"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate gpcr/kinase/ion_channel product exemplar HTVS profiles.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_contract()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
