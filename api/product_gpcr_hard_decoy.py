from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-gpcr-hard-decoy"])

ROOT = Path(__file__).resolve().parents[1]
GPCR_HARD_DECOY_SUITE_ARTIFACT = ROOT / "runs" / "gpcr_hard_decoy_suite_current.json"

# Default required target set (matches betelgeuze_product.gpcr_hard_decoy_suite).
_DEFAULT_REQUIRED_TARGET_IDS = ["DRD2", "HTR2A", "OPRM1"]

_CLAIM_BOUNDARY_MISSING = (
    "GPCR hard-decoy endpoint only; the local report artifact is missing or invalid. "
    "It does not run scoring, generate decoys, relax thresholds, or promote broad-GPCR claims. "
    "broad GPCR/router remains locked."
)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@router.get("/gpcr-hard-decoy-suite-report")
async def get_product_gpcr_hard_decoy_suite_report() -> dict[str, Any]:
    """Return the read-only GPCR hard-decoy suite gate surface.

    Exposes the family claim decision (from ``runs/gpcr_hard_decoy_suite_current.json``,
    built by ``tools/product/build_gpcr_hard_decoy_suite_report.py``) so broad-GPCR
    readiness has one inspectable answer: whether the broad GPCR/router claim is
    still locked and which required target blocks it. Fail-closed when the
    artifact is missing/invalid. This route never promotes a broad-GPCR claim.
    """

    artifact = _read_json_object(GPCR_HARD_DECOY_SUITE_ARTIFACT)
    summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
    targets = artifact.get("targets") if isinstance(artifact.get("targets"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_gpcr_hard_decoy_suite_report",
            "artifact_path": str(GPCR_HARD_DECOY_SUITE_ARTIFACT),
            "schema_version": "",
            "family_claim_safe": False,
            "required_target_ids": list(_DEFAULT_REQUIRED_TARGET_IDS),
            "target_count": 0,
            "green_target_ids": [],
            "blocked_target_ids": [],
            "missing_required_target_ids": list(_DEFAULT_REQUIRED_TARGET_IDS),
            "first_blocked_required_target": _DEFAULT_REQUIRED_TARGET_IDS[0],
            "gate": {},
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "targets": [],
            "claim_boundary": _CLAIM_BOUNDARY_MISSING,
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(GPCR_HARD_DECOY_SUITE_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        # Fail-closed: only a true value is treated as claim-safe.
        "family_claim_safe": bool(summary.get("family_claim_safe") is True),
        "required_target_ids": summary.get("required_target_ids", []),
        "target_count": int(summary.get("target_count") or 0),
        "green_target_ids": summary.get("green_target_ids", []),
        "blocked_target_ids": summary.get("blocked_target_ids", []),
        "missing_required_target_ids": summary.get("missing_required_target_ids", []),
        "first_blocked_required_target": summary.get("first_blocked_required_target", ""),
        "gate": summary.get("gate", {}),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "targets": targets,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
