#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/data_science_expansion_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/data_science_expansion_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/data_science_expansion_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Data/science expansion gap closure status only; audits transporter, CA2/PXR, CAMEO, IDP, GPCR, and physics/wetlab "
    "expansion lanes. It does not run docking, widen delivery claims, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _placeholder_count(path_like: str | Path) -> int:
    return sum(
        1
        for row in _read_csv_rows(path_like)
        if "template_placeholder" in str(row.get("source", "")).lower()
        or "placeholder" in str(row.get("ligand_id", "")).lower()
    )


def _row(item_id: int, gap: str, status: str, evidence: str, observed: str, next_action: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "gap": gap,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_data_science_expansion_gap_closure(
    *,
    transporter_membrane_packet: dict[str, Any] | None = None,
    ca2_readiness_packet: dict[str, Any] | None = None,
    pxr_readiness_packet: dict[str, Any] | None = None,
    cameo_architecture_packet: dict[str, Any] | None = None,
    idp_promotion_packet: dict[str, Any] | None = None,
    gpcr_breadth_packet: dict[str, Any] | None = None,
    accuracy_parity_packet: dict[str, Any] | None = None,
    aqp1_reference_csv: str = "config/ligand_binding_reference_blind_aqp1_v1.csv",
    glut1_reference_csv: str = "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
) -> dict[str, Any]:
    transporter = _summary(transporter_membrane_packet or _read_json_if_present("runs/transporter_membrane_readiness_current.json"))
    ca2 = _summary(ca2_readiness_packet or _read_json_if_present("runs/ca2_packet_replacement_readiness_current.json"))
    pxr = _summary(pxr_readiness_packet or _read_json_if_present("runs/pxr_packet_replacement_readiness_current.json"))
    cameo = _summary(cameo_architecture_packet or _read_json_if_present("runs/cameo_architecture_validation_contract_current.json"))
    idp = _summary(idp_promotion_packet or _read_json_if_present("runs/idp_broader_promotion_resolution_current.json"))
    gpcr = _summary(gpcr_breadth_packet or _read_json_if_present("runs/gpcr_residual_proof_breadth_gate_current.json"))
    accuracy = _summary(accuracy_parity_packet or _read_json_if_present("runs/accuracy_parity_scorecard_current.json"))

    aqp1_placeholders = _placeholder_count(aqp1_reference_csv)
    glut1_placeholders = _placeholder_count(glut1_reference_csv)
    transporter_ready = (
        aqp1_placeholders == 0
        and glut1_placeholders == 0
        and _resolve("config/ligand_meta_blind_aqp1_v1.csv").exists()
        and _resolve("config/ligand_meta_blind_glut1_4pyp_v1.csv").exists()
    )
    ca2_ready = int(ca2.get("ready_row_count") or 0) > 0 or int(ca2.get("blocked_row_count") or 12) == 0
    pxr_ready = int(pxr.get("ready_row_count") or 0) >= 8 or int(pxr.get("blocked_row_count") or 6) == 0
    ca2_pxr_ready = ca2_ready and pxr_ready
    cameo_ready = (
        _resolve("betelgeuze_cameo/outbound_email_send_executor.py").exists()
        and _resolve("betelgeuze_cameo/official_result_fetch_executor.py").exists()
        and cameo.get("local_validation_protocol_ready") is True
    )
    idp_ready = idp.get("wider_shadow_safe_lane_admitted") is True or idp.get("bounded_lane_closure_ready") is True
    gpcr_ready = gpcr.get("gpcr_residual_proof_breadth_gate_ready") is True
    physics_ready = accuracy.get("status") == "green" or int(accuracy.get("pass_row_count") or 0) >= 5

    rows = [
        _row(
            6,
            "GPCR CI-low / residual proof breadth",
            "closed" if gpcr_ready else "open",
            "runs/gpcr_residual_proof_breadth_gate_current.json",
            f"breadth_gate_ready={gpcr.get('gpcr_residual_proof_breadth_gate_ready')}; effective_count={gpcr.get('effective_gpcr_breadth_count')}",
            "Expand GPCR residual proof breadth gate beyond narrow slice.",
        ),
        _row(
            7,
            "Transporter AQP1/GLUT1 curated packets",
            "closed" if transporter_ready else "open",
            f"{aqp1_reference_csv}; {glut1_reference_csv}",
            f"aqp1_placeholder_rows={aqp1_placeholders}; glut1_placeholder_rows={glut1_placeholders}; membrane_status={transporter.get('status')}",
            "Replace placeholder transporter rows with curated functional/direct-binding provenance.",
        ),
        _row(
            8,
            "OpenMM / accuracy parity restricted lane",
            "closed" if physics_ready else "open",
            "runs/accuracy_parity_scorecard_current.json",
            f"status={accuracy.get('status')}; pass_row_count={accuracy.get('pass_row_count')}",
            "Maintain restricted 2-bead OpenMM parity scorecard green state.",
        ),
        _row(
            9,
            "Prospective wetlab translation scaffold",
            "closed" if physics_ready else "open",
            "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
            f"accuracy_status={accuracy.get('status')}",
            "Keep wetlab prospective translation out-of-claim while simulation packet quality stays green.",
        ),
        _row(
            10,
            "CA2/PXR packet replacement closure",
            "closed" if ca2_pxr_ready else "open",
            "runs/ca2_packet_replacement_readiness_current.json; runs/pxr_packet_replacement_readiness_current.json",
            f"ca2_ready_rows={ca2.get('ready_row_count')}; pxr_ready_rows={pxr.get('ready_row_count')}",
            "Fill and apply CA2/PXR replacement workbook rows with curated provenance.",
        ),
        _row(
            11,
            "IDP bounded shadow-safe lane",
            "closed" if idp_ready else "open",
            "runs/idp_broader_promotion_resolution_current.json",
            f"wider_lane_admitted={idp.get('wider_shadow_safe_lane_admitted')}; bounded_closure={idp.get('bounded_lane_closure_ready')}",
            "Admit bounded one-wider IDP shadow-safe lane without broader promotion.",
        ),
        _row(
            12,
            "CAMEO sender/fetch executor scaffold",
            "closed" if cameo_ready else "open",
            "betelgeuze_cameo/outbound_email_send_executor.py; betelgeuze_cameo/official_result_fetch_executor.py",
            f"receiver_ready={cameo.get('receiver_api_readiness_ready')}; local_protocol={cameo.get('local_validation_protocol_ready')}",
            "Ship fail-closed CAMEO send/fetch executors behind operator approval preflights.",
        ),
    ]
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "data_science_expansion_gap_closure",
        "status": "data_science_expansion_gap_closure_complete" if not open_rows else "blocked_data_science_expansion_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "closed_item_ids": [row["item_id"] for row in closed_rows],
        "open_item_ids": [row["item_id"] for row in open_rows],
        "current_primary_open_item": first_open["item_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All data/science expansion gaps are closed.",
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
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
        "# Data/Science Expansion Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        "",
        "## Gaps",
        "",
        "| item | status | gap | observed |",
        "| ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['item_id']}` | `{row['status']}` | {row['gap']} | `{row['observed']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build data/science expansion gap closure status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_data_science_expansion_gap_closure()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
