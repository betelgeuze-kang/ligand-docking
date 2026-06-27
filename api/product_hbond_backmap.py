from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-hbond-backmap"])

ROOT = Path(__file__).resolve().parents[1]
HBOND_BACKMAP_REPORT_ARTIFACT = ROOT / "runs" / "hbond_backmap_report_current.json"

_CLAIM_BOUNDARY_MISSING = (
    "H-Bond BackMap report endpoint only; the local report artifact is missing or invalid. "
    "It does not run docking or scoring, emit scientific results, or mutate external state. "
    "H-Bond BackMap is local interpretability evidence, not a docking-accuracy or binding-affinity claim."
)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@router.get("/hbond-backmap-report")
async def get_product_hbond_backmap_report() -> dict[str, Any]:
    """Return the read-only H-Bond BackMap (ONSPS-4) candidate report surface.

    Exposes the per-candidate interpretability evidence + batch claim-safe-rate
    KPI (from ``runs/hbond_backmap_report_current.json``, built by
    ``tools/product/build_hbond_backmap_report.py``) for the GUI candidate table
    and evidence bundle. Fail-closed when the artifact is missing/invalid.
    """

    artifact = _read_json_object(HBOND_BACKMAP_REPORT_ARTIFACT)
    summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_hbond_backmap_report",
            "artifact_path": str(HBOND_BACKMAP_REPORT_ARTIFACT),
            "candidate_count": 0,
            "claim_safe_count": 0,
            "evidence_only_count": 0,
            "claim_safe_rate": 0.0,
            "total_donor_sites": 0,
            "total_acceptor_sites": 0,
            "evidence_only_reason_counts": {},
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "candidates": [],
            "claim_boundary": _CLAIM_BOUNDARY_MISSING,
        }
    return {
        "status": artifact.get("status"),
        "artifact_path": str(HBOND_BACKMAP_REPORT_ARTIFACT),
        "report_version": summary.get("report_version", ""),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "claim_safe_count": int(summary.get("claim_safe_count") or 0),
        "evidence_only_count": int(summary.get("evidence_only_count") or 0),
        "claim_safe_rate": float(summary.get("claim_safe_rate") or 0.0),
        "total_donor_sites": int(summary.get("total_donor_sites") or 0),
        "total_acceptor_sites": int(summary.get("total_acceptor_sites") or 0),
        "evidence_only_reason_counts": summary.get("evidence_only_reason_counts", {}),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "candidates": rows,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
