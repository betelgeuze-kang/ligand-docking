from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from betelgeuze_engine.backmapping.onsps import ONSPS_BACKMAP_SCHEMA_VERSION, backmap_4bead_onsps
from betelgeuze_engine.contracts.claim import default_claim_metadata
from betelgeuze_engine.interactions.hbond_evidence import (
    HBOND_CLAIM_METADATA_SCHEMA_VERSION,
    HBOND_EVIDENCE_SCHEMA_VERSION,
    evaluate_hbond_evidence,
)

HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION = "hbond_recovery_benchmark_v1"


@dataclass(frozen=True)
class HbondRecoveryFixture:
    pose_id: str
    benchmark_role: str
    smiles: str
    ligand_xyz: np.ndarray
    protein_xyz: np.ndarray
    pocket_center: np.ndarray | None = None
    expected_claim_safe: bool = False
    expected_blocked_reason: str = ""
    expected_overanchored: bool = False
    expected_unsatisfied: bool = False


@dataclass(frozen=True)
class HbondRecoveryBenchmark:
    ready: bool
    status: str
    summary: dict[str, Any]
    rows: list[dict[str, Any]]
    claim_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": bool(self.ready),
            "status": str(self.status),
            "summary": dict(self.summary),
            "rows": list(self.rows),
            "claim_metadata": dict(self.claim_metadata),
        }


def _xyz(value: np.ndarray | Iterable[Iterable[float]]) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("benchmark coordinates must have shape [N, 3]")
    return arr


def _fixture_row(fixture: HbondRecoveryFixture) -> dict[str, Any]:
    evidence = evaluate_hbond_evidence(
        smiles=fixture.smiles,
        protein_xyz=_xyz(fixture.protein_xyz),
        ligand_xyz=_xyz(fixture.ligand_xyz),
        pocket_center=None if fixture.pocket_center is None else _xyz([fixture.pocket_center])[0],
    )
    claim_metadata = evidence.to_claim_metadata(
        topology_fidelity="sequence_mapped",
        ligand_topology_valid=True,
        product_claim_promoted=False,
    )
    unsatisfied_total = int(evidence.unsatisfied_donor_count) + int(evidence.unsatisfied_acceptor_count)
    expected_reason = str(fixture.expected_blocked_reason or "")
    blocked_reason = str(evidence.blocked_reason or "")
    reason_matches = (
        blocked_reason == expected_reason
        if expected_reason
        else blocked_reason == ""
    )
    benchmark_contract_pass = bool(
        evidence.schema_ready()
        and evidence.claim_safe is bool(fixture.expected_claim_safe)
        and bool(evidence.overanchoring_flag) is bool(fixture.expected_overanchored)
        and (unsatisfied_total > 0) is bool(fixture.expected_unsatisfied)
        and reason_matches
    )
    onsps_meta = evidence.onsps_backmap_metadata if isinstance(evidence.onsps_backmap_metadata, dict) else {}
    return {
        "pose_id": str(fixture.pose_id),
        "benchmark_role": str(fixture.benchmark_role),
        "smiles": str(fixture.smiles),
        "schema_version": HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION,
        "hbond_schema_version": str(evidence.schema_version),
        "hbond_schema_ready": bool(evidence.schema_ready()),
        "hbond_threshold_schema_ready": bool(evidence.threshold_schema_ready()),
        "hbond_pair_schema_ready": bool(evidence.pair_schema_ready()),
        "hbond_geometry_flags_ready": bool(evidence.geometry_flags_ready()),
        "hbond_status": str(evidence.status),
        "hbond_claim_safe": bool(evidence.claim_safe),
        "hbond_blocked_reason": blocked_reason,
        "hbond_abstention_reason": str(evidence.abstention_reason or ""),
        "hbond_confidence": float(evidence.hbond_confidence),
        "hbond_site_count": int(evidence.site_count),
        "hbond_donor_site_count": int(evidence.donor_site_count),
        "hbond_acceptor_site_count": int(evidence.acceptor_site_count),
        "hbond_distance_pass_count": int(evidence.distance_pass_count),
        "hbond_angle_pass_count": int(evidence.angle_pass_count),
        "hbond_unsatisfied_donor_count": int(evidence.unsatisfied_donor_count),
        "hbond_unsatisfied_acceptor_count": int(evidence.unsatisfied_acceptor_count),
        "hbond_unsatisfied_total_count": int(unsatisfied_total),
        "overanchoring_flag": bool(evidence.overanchoring_flag),
        "missing_expected_anchor_flag": bool(evidence.missing_expected_anchor_flag),
        "onsps_backmap_schema_version": str(onsps_meta.get("schema_version") or ONSPS_BACKMAP_SCHEMA_VERSION),
        "onsps_backmap_metadata_schema_ready": bool(
            claim_metadata.get("onsps_backmap_metadata_schema_ready") is True
        ),
        "onsps_backmap_claim_safe": bool(claim_metadata.get("onsps_backmap_claim_safe") is True),
        "expected_claim_safe": bool(fixture.expected_claim_safe),
        "expected_blocked_reason": expected_reason,
        "expected_overanchored": bool(fixture.expected_overanchored),
        "expected_unsatisfied": bool(fixture.expected_unsatisfied),
        "benchmark_contract_pass": benchmark_contract_pass,
        "claim_metadata": claim_metadata,
    }


def default_hbond_recovery_fixtures() -> list[HbondRecoveryFixture]:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    active_mapped, _active_meta = backmap_4bead_onsps(two_bead, "CCO")
    active_protein = active_mapped + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
    active_center = active_mapped.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)

    unsatisfied_protein = active_mapped + np.asarray([[8.0, 0.0, 0.0]], dtype=np.float32)

    over_mapped, _over_meta = backmap_4bead_onsps(two_bead, "CC(=O)N")

    return [
        HbondRecoveryFixture(
            pose_id="active_hbond_recovered_pose",
            benchmark_role="active_recovery_pose",
            smiles="CCO",
            ligand_xyz=two_bead,
            protein_xyz=active_protein,
            pocket_center=active_center,
            expected_claim_safe=True,
        ),
        HbondRecoveryFixture(
            pose_id="unsatisfied_donor_acceptor_pose",
            benchmark_role="unsatisfied_donor_pose",
            smiles="CCO",
            ligand_xyz=two_bead,
            protein_xyz=unsatisfied_protein,
            expected_claim_safe=False,
            expected_blocked_reason="missing_expected_anchor",
            expected_unsatisfied=True,
        ),
        HbondRecoveryFixture(
            pose_id="amide_overanchored_decoy_pose",
            benchmark_role="overanchored_decoy_pose",
            smiles="CC(=O)N",
            ligand_xyz=two_bead,
            protein_xyz=over_mapped,
            expected_claim_safe=False,
            expected_blocked_reason="overanchored_decoy",
            expected_overanchored=True,
            expected_unsatisfied=True,
        ),
    ]


def build_hbond_recovery_benchmark(
    fixtures: Iterable[HbondRecoveryFixture] | None = None,
) -> HbondRecoveryBenchmark:
    rows = [_fixture_row(fixture) for fixture in (fixtures or default_hbond_recovery_fixtures())]
    contract_pass_count = sum(1 for row in rows if row["benchmark_contract_pass"])
    schema_ready_count = sum(1 for row in rows if row["hbond_schema_ready"])
    onsps_schema_ready_count = sum(1 for row in rows if row["onsps_backmap_metadata_schema_ready"])
    active_rows = [row for row in rows if row["benchmark_role"] == "active_recovery_pose"]
    active_claim_safe_rows = [row for row in active_rows if row["hbond_claim_safe"] is True]
    unsatisfied_rows = [row for row in rows if int(row["hbond_unsatisfied_total_count"]) > 0]
    overanchored_rows = [
        row
        for row in rows
        if row["expected_overanchored"] is True
        and row["overanchoring_flag"] is True
        and row["hbond_claim_safe"] is False
        and row["hbond_blocked_reason"] == "overanchored_decoy"
    ]
    ready = bool(
        rows
        and contract_pass_count == len(rows)
        and schema_ready_count == len(rows)
        and onsps_schema_ready_count == len(rows)
        and active_claim_safe_rows
        and unsatisfied_rows
        and overanchored_rows
    )
    summary = {
        "schema_version": HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION,
        "status": "hbond_recovery_benchmark_ready" if ready else "blocked_hbond_recovery_benchmark",
        "ready": ready,
        "fixture_count": len(rows),
        "benchmark_contract_pass_count": int(contract_pass_count),
        "hbond_evidence_schema_ready": bool(schema_ready_count == len(rows) and rows),
        "hbond_evidence_schema_ready_count": int(schema_ready_count),
        "onsps_backmap_metadata_schema_ready_count": int(onsps_schema_ready_count),
        "hbond_recovery_present": bool(active_claim_safe_rows),
        "hbond_recovery_pose_count": int(len(active_claim_safe_rows)),
        "unsatisfied_donor_acceptor_detected": bool(unsatisfied_rows),
        "unsatisfied_donor_acceptor_pose_count": int(len(unsatisfied_rows)),
        "unsatisfied_donor_count": int(sum(int(row["hbond_unsatisfied_donor_count"]) for row in rows)),
        "unsatisfied_acceptor_count": int(sum(int(row["hbond_unsatisfied_acceptor_count"]) for row in rows)),
        "overanchored_decoys_blocked": bool(overanchored_rows),
        "overanchored_decoy_pose_count": int(len(overanchored_rows)),
        "claim_boundary": (
            "H-bond recovery benchmark evidence only; it evaluates local synthetic active, unsatisfied, "
            "and overanchored decoy fixtures with ONSPS metadata. It does not promote a product claim by itself."
        ),
    }
    claim_metadata = default_claim_metadata(
        topology_fidelity="sequence_mapped",
        ligand_topology_valid=ready,
        hbond_evidence_status="pass" if ready else "review",
        force_residual_applied=False,
        claim_safe=False,
        blocked_reason=(
            "hbond_recovery_benchmark_not_product_claim_promoted"
            if ready
            else "hbond_recovery_benchmark_not_ready"
        ),
        hbond_claim_metadata_schema_version=HBOND_CLAIM_METADATA_SCHEMA_VERSION,
        hbond_evidence_schema_version=HBOND_EVIDENCE_SCHEMA_VERSION,
        hbond_recovery_benchmark_schema_version=HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION,
        hbond_recovery_benchmark_ready=ready,
        hbond_recovery_present=summary["hbond_recovery_present"],
        hbond_recovery_pose_count=summary["hbond_recovery_pose_count"],
        hbond_unsatisfied_donor_count=summary["unsatisfied_donor_count"],
        hbond_unsatisfied_acceptor_count=summary["unsatisfied_acceptor_count"],
        hbond_overanchored_decoys_blocked=summary["overanchored_decoys_blocked"],
    )
    return HbondRecoveryBenchmark(
        ready=ready,
        status=str(summary["status"]),
        summary=summary,
        rows=rows,
        claim_metadata=claim_metadata,
    )
