from __future__ import annotations

from typing import Any


def infer_transporter_phase(transporter_summary: dict[str, Any]) -> str:
    pending_manual = int(transporter_summary.get("binder_pending_manual_verdict_count", 0) or 0)
    seed_rows = int(
        transporter_summary.get("binder_seed_row_count", transporter_summary.get("binder_slot_count", 0)) or 0
    )
    return "seed_row_blocker_closure" if pending_manual == 0 and seed_rows > 0 else "manual_review_only"


def aqp1_follow_on_seed_steps(seed_row_board: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    for row in seed_row_board.get("rows", []) or []:
        if str(row.get("target_id", "")).strip() != "AQP1":
            continue
        packet_step = str(row.get("packet_step", "")).strip()
        if packet_step and packet_step != "core_binder_01" and packet_step.startswith("core_binder_"):
            steps.append(packet_step)
    return steps
