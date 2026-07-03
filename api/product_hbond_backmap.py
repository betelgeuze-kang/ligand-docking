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


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return []


def _candidate_rows(rows: list[Any], claim_boundary: str) -> list[dict[str, Any]]:
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_safe = bool(row.get("claim_safe") is True)
        candidate_rows.append(
            {
                "entry_id": str(row.get("entry_id") or ""),
                "evidence_tier": str(row.get("evidence_tier") or ""),
                "claim_safe": claim_safe,
                "evidence_only": not claim_safe,
                "mapped_site_count": _int(row.get("mapped_site_count")),
                "site_count": _int(row.get("site_count")),
                "max_onsps_sites": _int(row.get("max_onsps_sites")),
                "donor_count": _int(row.get("donor_count")),
                "acceptor_count": _int(row.get("acceptor_count")),
                "polar_site_elements": _string_list(row.get("polar_site_elements")),
                "mapping_source": str(row.get("mapping_source") or ""),
                "backmap_status": str(row.get("backmap_status") or ""),
                "reason_code": str(row.get("reason_code") or ""),
                "reason_detail": str(row.get("reason_detail") or ""),
                "two_bead_vs_four_bead_delta": _float_or_none(
                    row.get("two_bead_vs_four_bead_delta")
                ),
                "hbond_angle_score": _float_or_none(row.get("hbond_angle_score")),
                "operator_action_required": not claim_safe,
                "claim_boundary": str(row.get("claim_boundary") or claim_boundary),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return candidate_rows


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
            "candidate_table_ready": False,
            "candidate_row_count": 0,
            "claim_safe_candidate_row_count": 0,
            "evidence_only_candidate_row_count": 0,
            "candidate_rows": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "candidates": [],
            "claim_boundary": _CLAIM_BOUNDARY_MISSING,
        }
    claim_boundary = str(summary.get("claim_boundary") or "")
    candidate_rows = _candidate_rows(rows, claim_boundary)
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
        "candidate_table_ready": True,
        "candidate_row_count": len(candidate_rows),
        "claim_safe_candidate_row_count": sum(1 for row in candidate_rows if row["claim_safe"]),
        "evidence_only_candidate_row_count": sum(
            1 for row in candidate_rows if row["evidence_only"]
        ),
        "candidate_rows": candidate_rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "candidates": rows,
        "claim_boundary": claim_boundary,
    }
