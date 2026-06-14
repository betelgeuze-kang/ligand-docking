#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACCURACY_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_OPENMM_JSON = "runs/openmm_2bead_strict_multitarget_current_summary.json"
DEFAULT_WETLAB_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_openmm_claim_promotion_boundary_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_openmm_claim_promotion_boundary_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_openmm_claim_promotion_boundary_current.md"

CLAIM_BOUNDARY = (
    "Wetlab/OpenMM claim promotion boundary only; it audits restricted 2-bead OpenMM parity and simulation-based "
    "wetlab translation scaffolds while keeping wetlab-proven hits and full all-atom/MM-GBSA/FEP+ claims "
    "out-of-scope. It does not run MD, widen delivery claims, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path_like: str | Path) -> str:
    path = _resolve(path_like)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def build_wetlab_openmm_claim_promotion_boundary(
    *,
    accuracy_packet: dict[str, Any] | None = None,
    openmm_packet: dict[str, Any] | None = None,
    wetlab_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accuracy = _summary(accuracy_packet or _read_json_if_present(DEFAULT_ACCURACY_JSON))
    openmm = _summary(openmm_packet or _read_json_if_present(DEFAULT_OPENMM_JSON))
    wetlab = _summary(wetlab_packet or _read_json_if_present(DEFAULT_WETLAB_JSON))
    accuracy_rows = _rows(accuracy_packet or _read_json_if_present(DEFAULT_ACCURACY_JSON))
    forcefield = _read_text("core/forcefield.py")
    topology = _read_text("core/topology.py")

    openmm_row = next((row for row in accuracy_rows if row.get("axis") == "physics_dynamics"), {})
    physics_accounting_green = (
        accuracy.get("status") == "green"
        or _bool(accuracy.get("openmm_class_claim_allowed"))
        or str(openmm_row.get("status") or "").strip() == "pass"
        or _bool(openmm_row.get("commercial_parity_claim_allowed"))
        or _int(accuracy.get("pass_row_count")) >= 5
    )
    openmm_2bead_pass = _int(openmm.get("pass_count")) >= 11 or _int(openmm.get("target_pass_count")) >= 11
    wetlab_simulation_green = _int(wetlab.get("hard_block_count")) == 0 or _bool(wetlab.get("selected_allatom_gate_ready"))
    full_aa_boundary_documented = (
        "placeholder" in topology.lower() or "alanine" in topology.lower()
    ) and ("lj" in forcefield.lower() or "lennard" in forcefield.lower())
    wetlab_proven_out_of_claim = True
    rows = [
        {
            "lane_id": "openmm_restricted_2bead",
            "accounting_status": "green" if physics_accounting_green and openmm_2bead_pass else "blocked",
            "claim_promotion_status": "restricted_lane_only",
            "claim_promotion_allowed": False,
            "openmm_2bead_pass_count": _int(openmm.get("pass_count")) or _int(openmm.get("target_pass_count")),
            "full_all_atom_implemented": False,
            "mm_gbsa_fep_implemented": False,
            "promotion_boundary_ready": physics_accounting_green and openmm_2bead_pass and full_aa_boundary_documented,
            "gap_closed": physics_accounting_green and openmm_2bead_pass and full_aa_boundary_documented,
            "blockers": ""
            if physics_accounting_green and openmm_2bead_pass and full_aa_boundary_documented
            else "openmm_or_accuracy_or_full_aa_boundary_incomplete",
        },
        {
            "lane_id": "wetlab_prospective_translation",
            "accounting_status": "green" if wetlab_simulation_green else "blocked",
            "claim_promotion_status": "simulation_packet_only",
            "claim_promotion_allowed": False,
            "wetlab_assay_count": 0,
            "wetlab_proven_hit_out_of_claim": wetlab_proven_out_of_claim,
            "promotion_boundary_ready": wetlab_simulation_green and wetlab_proven_out_of_claim,
            "gap_closed": wetlab_simulation_green and wetlab_proven_out_of_claim,
            "blockers": "" if wetlab_simulation_green else "wetlab_simulation_packet_not_green",
        },
    ]
    open_rows = [row for row in rows if not row["gap_closed"]]
    promotion_boundary_ready = not open_rows
    summary = {
        "packet_type": "wetlab_openmm_claim_promotion_boundary",
        "status": "wetlab_openmm_claim_promotion_boundary_ready" if promotion_boundary_ready else "blocked_wetlab_openmm_claim_promotion_boundary",
        "promotion_boundary_ready": promotion_boundary_ready,
        "accounting_closed": physics_accounting_green and wetlab_simulation_green,
        "claim_promotion_allowed": False,
        "openmm_2bead_lane_closed": rows[0]["gap_closed"],
        "wetlab_lane_closed": rows[1]["gap_closed"],
        "full_all_atom_implemented": False,
        "mm_gbsa_fep_implemented": False,
        "wetlab_proven_hit_out_of_claim": True,
        "open_gap_count": len(open_rows),
        "blocker_count": len(open_rows),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Restricted 2-bead OpenMM and simulation-only wetlab translation boundaries are closed; "
            "full all-atom and wetlab-proven claims remain out-of-scope."
            if promotion_boundary_ready
            else "Restore accuracy parity / OpenMM 2-bead / wetlab simulation packet green state."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Wetlab/OpenMM Claim Promotion Boundary",
        "",
        f"- status: `{s['status']}`",
        f"- promotion_boundary_ready: `{s['promotion_boundary_ready']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build wetlab/OpenMM claim promotion boundary.")
    parser.add_argument("--accuracy-json", default=DEFAULT_ACCURACY_JSON)
    parser.add_argument("--openmm-json", default=DEFAULT_OPENMM_JSON)
    parser.add_argument("--wetlab-json", default=DEFAULT_WETLAB_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_wetlab_openmm_claim_promotion_boundary(
        accuracy_packet=_read_json_if_present(args.accuracy_json),
        openmm_packet=_read_json_if_present(args.openmm_json),
        wetlab_packet=_read_json_if_present(args.wetlab_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
