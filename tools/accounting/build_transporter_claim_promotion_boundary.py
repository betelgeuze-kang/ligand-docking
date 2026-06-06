#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCAFFOLD_JSON = "runs/transporter_claim_boundary_expansion_scaffold_current.json"
DEFAULT_INTAKE_GATE_JSON = "runs/aqp1_negative_evidence_intake_gate_current.json"
DEFAULT_OUT_JSON = "runs/transporter_claim_promotion_boundary_current.json"
DEFAULT_OUT_CSV = "runs/transporter_claim_promotion_boundary_current.csv"
DEFAULT_OUT_MD = "runs/transporter_claim_promotion_boundary_current.md"

CLAIM_BOUNDARY = (
    "Transporter claim promotion boundary only; it audits functional-surrogate accounting closure and keeps direct "
    "binding kcal claims blocked until authoritative negative/positive quantitative evidence is operator-curated. "
    "It does not run docking, widen delivery claims, or mutate external state."
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


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def build_transporter_claim_promotion_boundary(
    *,
    scaffold_packet: dict[str, Any] | None = None,
    intake_gate_packet: dict[str, Any] | None = None,
    aqp1_reference_csv: str = "config/ligand_binding_reference_blind_aqp1_v1.csv",
    glut1_reference_csv: str = "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
) -> dict[str, Any]:
    scaffold = _summary(scaffold_packet or _read_json_if_present(DEFAULT_SCAFFOLD_JSON))
    intake = _summary(intake_gate_packet or _read_json_if_present(DEFAULT_INTAKE_GATE_JSON))
    aqp1_placeholders = _placeholder_count(aqp1_reference_csv)
    glut1_placeholders = _placeholder_count(glut1_reference_csv)
    accounting_closed = aqp1_placeholders == 0 and glut1_placeholders == 0
    direct_binding_blocked = scaffold.get("direct_binding_kcal_claim_allowed") is False
    functional_surrogate_ready = _bool(scaffold.get("curated_packet_ready")) or _bool(scaffold.get("binder_promotion_gate_ready"))
    intake_template_ready = _resolve("runs/aqp1_negative_evidence_intake_template_current.csv").exists()
    authoritative_negative_count = _int(intake.get("authoritative_negative_apply_allowed_count"))
    promotion_boundary_ready = accounting_closed and direct_binding_blocked and functional_surrogate_ready and intake_template_ready
    blockers: list[str] = []
    if not accounting_closed:
        blockers.append("transporter_placeholder_rows_remain")
    if not direct_binding_blocked:
        blockers.append("direct_binding_kcal_claim_not_blocked")
    if not functional_surrogate_ready:
        blockers.append("functional_surrogate_boundary_not_ready")
    if not intake_template_ready:
        blockers.append("aqp1_negative_intake_template_missing")

    row = {
        "lane_id": "transporter_aqp1_glut1",
        "accounting_status": "green" if accounting_closed else "blocked",
        "claim_promotion_status": "functional_surrogate_only",
        "claim_promotion_allowed": False,
        "direct_binding_kcal_claim_allowed": False,
        "functional_surrogate_claim_allowed": functional_surrogate_ready,
        "aqp1_placeholder_rows": aqp1_placeholders,
        "glut1_placeholder_rows": glut1_placeholders,
        "authoritative_negative_apply_allowed_count": authoritative_negative_count,
        "intake_template_ready": intake_template_ready,
        "promotion_boundary_ready": promotion_boundary_ready,
        "gap_closed": promotion_boundary_ready,
        "blockers": ",".join(blockers),
        "next_required_step": (
            "Keep direct binding kcal out-of-claim; operator-fill AQP1 negative intake template when primary "
            "quantitative evidence becomes available."
            if promotion_boundary_ready
            else "Close transporter placeholder accounting and intake template scaffolds before claim review."
        ),
    }
    summary = {
        "packet_type": "transporter_claim_promotion_boundary",
        "status": "transporter_claim_promotion_boundary_ready" if promotion_boundary_ready else "blocked_transporter_claim_promotion_boundary",
        "promotion_boundary_ready": promotion_boundary_ready,
        "accounting_closed": accounting_closed,
        "claim_promotion_allowed": False,
        "direct_binding_kcal_claim_allowed": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": row["next_required_step"],
    }
    return {"summary": summary, "rows": [row]}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Transporter Claim Promotion Boundary",
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
    parser = argparse.ArgumentParser(description="Build transporter claim promotion boundary.")
    parser.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    parser.add_argument("--intake-gate-json", default=DEFAULT_INTAKE_GATE_JSON)
    parser.add_argument("--aqp1-reference-csv", default="config/ligand_binding_reference_blind_aqp1_v1.csv")
    parser.add_argument("--glut1-reference-csv", default="config/ligand_binding_reference_blind_glut1_4pyp_v1.csv")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_transporter_claim_promotion_boundary(
        scaffold_packet=_read_json_if_present(args.scaffold_json),
        intake_gate_packet=_read_json_if_present(args.intake_gate_json),
        aqp1_reference_csv=args.aqp1_reference_csv,
        glut1_reference_csv=args.glut1_reference_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
