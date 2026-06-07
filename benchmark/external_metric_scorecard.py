from __future__ import annotations

import datetime as dt
from typing import Any

from core.claim_boundary import (
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
)

CLAIM_BOUNDARY = (
    "External metric scorecard for restricted local-delivery comparison only. "
    "Not an OpenMM/Schrödinger-grade accuracy claim."
)

METRIC_FAMILIES = ("dockq_proxy", "lddt_pli", "molprobity_clashscore")
MOLPROBITY_CLASHSCORE_MAX = 20.0


def _higher_is_better_status(*, value: float | None, threshold: float, blocked: bool, missing: bool) -> str:
    if blocked:
        return "blocked"
    if missing or value is None:
        return "missing"
    return "pass" if value >= threshold else "fail"


def _molprobity_status(*, value: float | None, blocked: bool, missing: bool) -> str:
    if blocked:
        return "blocked"
    if missing or value is None:
        return "missing"
    return "pass" if value <= MOLPROBITY_CLASHSCORE_MAX else "fail"


def build_external_metric_scorecard(
    *,
    inputs: list[dict[str, Any]],
    claim_scope: str = CLAIM_SCOPE_RESTRICTED_LOCAL,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in inputs:
        fidelity = str(item.get("topology_fidelity", TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE))
        blocked = fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        dockq = item.get("dockq_proxy")
        lddt = item.get("lddt_pli")
        clash = item.get("molprobity_clashscore")
        missing = dockq is None and lddt is None and clash is None
        rows.append(
            {
                "row_id": str(item.get("row_id", "")),
                "target_id": str(item.get("target_id", "")),
                "metric_family": "external_structure_quality_bundle",
                "claim_scope": claim_scope,
                "topology_fidelity": fidelity,
                "dockq_proxy": dockq,
                "lddt_pli": lddt,
                "molprobity_clashscore": clash,
                "dockq_status": _higher_is_better_status(
                    value=dockq, threshold=0.23, blocked=blocked, missing=dockq is None
                ),
                "lddt_pli_status": _higher_is_better_status(
                    value=lddt, threshold=0.5, blocked=blocked, missing=lddt is None
                ),
                "molprobity_status": _molprobity_status(value=clash, blocked=blocked, missing=clash is None),
                "row_status": "blocked" if blocked else ("missing" if missing else "evaluated"),
            }
        )
    blocked_count = sum(1 for r in rows if r["row_status"] == "blocked")
    evaluated_count = sum(1 for r in rows if r["row_status"] == "evaluated")
    return {
        "packet_type": "external_metric_scorecard_v1",
        "generated_at_local": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "summary": {
            "status": "external_metric_scorecard_ready",
            "claim_scope": claim_scope,
            "claim_promotion_allowed": False,
            "row_count": len(rows),
            "blocked_row_count": blocked_count,
            "evaluated_row_count": evaluated_count,
            "topology_fidelity_required": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "rows": rows,
    }


def evaluate_row_metrics(
    *,
    row_id: str,
    target_id: str,
    topology_fidelity: str,
    dockq_proxy: float | None = None,
    lddt_pli: float | None = None,
    molprobity_clashscore: float | None = None,
) -> dict[str, Any]:
    return build_external_metric_scorecard(
        inputs=[
            {
                "row_id": row_id,
                "target_id": target_id,
                "topology_fidelity": topology_fidelity,
                "dockq_proxy": dockq_proxy,
                "lddt_pli": lddt_pli,
                "molprobity_clashscore": molprobity_clashscore,
            }
        ]
    )["rows"][0]
