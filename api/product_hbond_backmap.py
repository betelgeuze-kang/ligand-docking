from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-hbond-backmap"])

_CLAIM_BOUNDARY_JOB_SCOPED = (
    "Global H-Bond candidate rows are not a customer evidence surface. H-Bond evidence is "
    "available only inside the owning job's verified EvidenceBundle, bound to the job, both "
    "request fingerprints, and the exact result file. It remains local interpretability "
    "evidence, not a docking-accuracy or binding-affinity claim."
)


@router.get("/hbond-backmap-report")
async def get_product_hbond_backmap_report() -> dict[str, Any]:
    """Return only the fail-closed migration receipt for the legacy global route.

    A fixed ``runs/*_current`` artifact is not tenant- or job-bound and therefore
    must never expose candidate rows.  Verified per-job EvidenceBundles are the
    sole H-bond evidence source.
    """

    return {
        "status": "job_scoped_hbond_evidence_required",
        "artifact_path": "",
        "report_version": "job_scoped_hbond_evidence_v1",
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
        "legacy_global_artifact_accepted": False,
        "candidates": [],
        "claim_boundary": _CLAIM_BOUNDARY_JOB_SCOPED,
    }
