from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-release-evidence"])

ROOT = Path(__file__).resolve().parents[1]
RELEASE_CLAIM_EVIDENCE_LADDER_ARTIFACT = (
    ROOT / "runs" / "release_claim_evidence_ladder_gate_current.json"
)

CLAIM_BOUNDARY = (
    "Release claim evidence-ladder endpoint only reads the local ladder artifact. "
    "It separates local-observed, GitHub Actions remote-green, and ROCm runtime-green evidence. "
    "It does not run tests, dispatch workflows, deploy images, promote runtime claims, or mutate external state."
)


def _read_json_object(path: Path) -> dict[str, Any]:
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


def _missing_response() -> dict[str, Any]:
    return {
        "status": "missing_release_claim_evidence_ladder_gate",
        "artifact_path": str(RELEASE_CLAIM_EVIDENCE_LADDER_ARTIFACT),
        "highest_supported_claim": "none",
        "local_observed_green": False,
        "remote_green": False,
        "merge_commit_workflow_run_present": False,
        "remote_green_attributable_to_head": False,
        "runtime_green": False,
        "claim_promotion": {
            "tests_pass_locally": False,
            "ci_wired_and_green_on_main": False,
            "runtime_or_production_claim": False,
        },
        "runtime_claim_allowed": False,
        "production_release_claim_allowed": False,
        "blocker_count": 1,
        "blockers": [
            {
                "code": "missing_release_claim_evidence_ladder_gate",
                "detail": "Run tools/product/build_release_claim_evidence_ladder_gate.py with remote workflow-run inputs.",
            }
        ],
        "rows": [],
        "next_required_step": "Generate remote-attributed release evidence ladder artifact from GitHub Actions workflow run data.",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


@router.get("/release-claim-evidence-ladder")
async def get_release_claim_evidence_ladder() -> dict[str, Any]:
    packet = _read_json_object(RELEASE_CLAIM_EVIDENCE_LADDER_ARTIFACT)
    summary = _summary(packet)
    if not summary:
        return _missing_response()

    claim_promotion = summary.get("claim_promotion")
    if not isinstance(claim_promotion, dict):
        claim_promotion = {}
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    runtime_claim_allowed = bool(claim_promotion.get("runtime_or_production_claim") is True)
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RELEASE_CLAIM_EVIDENCE_LADDER_ARTIFACT),
        "highest_supported_claim": summary.get("highest_supported_claim", "none"),
        "local_observed_green": bool(summary.get("local_observed_green") is True),
        "remote_green": bool(summary.get("remote_green") is True),
        "merge_commit_workflow_run_present": bool(
            summary.get("merge_commit_workflow_run_present") is True
        ),
        "remote_green_attributable_to_head": bool(
            summary.get("remote_green_attributable_to_head") is True
        ),
        "runtime_green": bool(summary.get("runtime_green") is True),
        "claim_promotion": {
            "tests_pass_locally": bool(claim_promotion.get("tests_pass_locally") is True),
            "ci_wired_and_green_on_main": bool(
                claim_promotion.get("ci_wired_and_green_on_main") is True
            ),
            "runtime_or_production_claim": runtime_claim_allowed,
        },
        "runtime_claim_allowed": runtime_claim_allowed,
        "production_release_claim_allowed": runtime_claim_allowed,
        "blocker_count": int(summary.get("blocker_count") or len(blockers)),
        "blockers": blockers,
        "rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary") or CLAIM_BOUNDARY,
    }
