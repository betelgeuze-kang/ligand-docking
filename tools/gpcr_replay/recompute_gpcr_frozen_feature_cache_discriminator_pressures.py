#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.gpcr_replay.build_gpcr_drd2_hard_decoy_slice_packet import (
    _candidate_pressures,
    _weak_base_rescue_support,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv"
DEFAULT_OUT_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_discriminator_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_discriminator_current.json"
DEFAULT_OUT_MD = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_discriminator_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def recompute_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        pressure_input = {
            "basic_amine_count": int(_float(updated.get("basic_amine_count"), 0)),
            "cationic_center_basic_atom_count": int(_float(updated.get("cationic_center_basic_atom_count"), 0)),
            "ligand_h_donors": _float(updated.get("ligand_h_donors"), 0.0),
            "ligand_h_acceptors": _float(updated.get("ligand_h_acceptors"), 0.0),
            "ligand_rot_bonds": _float(updated.get("ligand_rot_bonds"), 0.0),
            "ligand_logp": _float(updated.get("ligand_logp"), 0.0),
            "atom_contact_fraction_le_2p8A": _float(updated.get("atom_contact_fraction_le_2p8A"), 0.0),
            "atom_contact_fraction_2p8_4p2A": _float(updated.get("atom_contact_fraction_2p8_4p2A"), 0.0),
            "cationic_center_contact_fraction_2p8_4p2A": _float(
                updated.get("cationic_center_contact_fraction_2p8_4p2A"), 0.0
            ),
            "cationic_center_contact_fraction_le_2p8A": _float(
                updated.get("cationic_center_contact_fraction_le_2p8A"), 0.0
            ),
            "cationic_center_contact_fraction_ge_4p2A": _float(
                updated.get("cationic_center_contact_fraction_ge_4p2A"), 0.0
            ),
            "coarse_centroid_preservation_rmsd_A_mean": _float(
                updated.get("coarse_centroid_preservation_rmsd_A_mean"), 0.0
            ),
            "atom_anchor_mean_distance_A": updated.get("atom_anchor_mean_distance_A"),
        }
        pressures = _candidate_pressures(pressure_input)
        base_score = _float(updated.get("base_score"))
        weak_gate, weak_support = _weak_base_rescue_support(
            base_score,
            float(pressures.get("label_free_support_pressure") or 0.0),
        )
        updated.update(pressures)
        updated["weak_base_rescue_gate"] = weak_gate
        updated["weak_base_rescue_support_pressure"] = weak_support
        updated["discriminator_pressure_refresh"] = "v11_false_valid_anchor_recompute"
        out.append(updated)
    return out


def build_payload(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    generated_at_local: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _read_csv(input_csv)
    rows = recompute_rows(source_rows)
    false_positive = sum(1 for row in rows if _float(row.get("false_valid_anchor_discriminator_pressure")) > 0.0)
    summary = {
        "packet_type": "gpcr_frozen_feature_cache_discriminator_pressure_refresh",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "discriminator_pressure_refresh_ready" if rows else "blocked_discriminator_pressure_refresh",
        "input_csv": str(_resolve(input_csv)),
        "input_row_count": len(source_rows),
        "output_row_count": len(rows),
        "false_valid_anchor_discriminator_row_count": false_positive,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "next_required_step": (
            "Replay gpcr_core_cationic_weakbase_rescue_shadow_v11 on the refreshed cache and rerun frozen "
            "shadow review. Full claim review remains blocked until stage2/stage3 regeneration completes and "
            "CI-low/top20/leakage gates are green."
            if rows
            else "Provide a non-empty frozen feature cache CSV before recomputing discriminator pressures."
        ),
    }
    return rows, summary


def _write_markdown(path_like: str | Path, summary: dict[str, Any]) -> None:
    lines = [
        "# GPCR Frozen Feature Cache Discriminator Pressure Refresh",
        "",
        f"- status: `{summary['status']}`",
        f"- input_row_count: `{summary['input_row_count']}`",
        f"- output_row_count: `{summary['output_row_count']}`",
        f"- false_valid_anchor_discriminator_row_count: `{summary['false_valid_anchor_discriminator_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute false-valid-anchor discriminator pressures on an existing frozen feature cache CSV."
    )
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, summary = build_payload(input_csv=args.input_csv)
    _write_csv(args.out_csv, rows)
    payload = {"summary": summary}
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
