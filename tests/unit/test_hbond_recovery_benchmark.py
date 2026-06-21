from __future__ import annotations

import numpy as np

from betelgeuze_engine.benchmark import (
    HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION,
    HbondRecoveryFixture,
    build_hbond_recovery_benchmark,
)


def test_hbond_recovery_benchmark_tracks_active_unsatisfied_and_overanchored_fixtures() -> None:
    report = build_hbond_recovery_benchmark()

    assert report.status == "hbond_recovery_benchmark_ready"
    assert report.ready is True
    assert report.summary["schema_version"] == HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION
    assert report.summary["fixture_count"] == 3
    assert report.summary["benchmark_contract_pass_count"] == 3
    assert report.summary["hbond_evidence_schema_ready"] is True
    assert report.summary["hbond_recovery_present"] is True
    assert report.summary["hbond_recovery_pose_count"] == 1
    assert report.summary["unsatisfied_donor_acceptor_detected"] is True
    assert report.summary["unsatisfied_donor_acceptor_pose_count"] >= 1
    assert report.summary["unsatisfied_donor_count"] + report.summary["unsatisfied_acceptor_count"] >= 1
    assert report.summary["overanchored_decoys_blocked"] is True
    assert report.summary["overanchored_decoy_pose_count"] == 1

    rows = {row["pose_id"]: row for row in report.rows}
    active = rows["active_hbond_recovered_pose"]
    assert active["benchmark_role"] == "active_recovery_pose"
    assert active["hbond_claim_safe"] is True
    assert active["hbond_status"] == "pass"
    assert active["benchmark_contract_pass"] is True
    assert active["onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert active["onsps_backmap_metadata_schema_ready"] is True

    unsatisfied = rows["unsatisfied_donor_acceptor_pose"]
    assert unsatisfied["hbond_claim_safe"] is False
    assert unsatisfied["hbond_blocked_reason"] == "missing_expected_anchor"
    assert unsatisfied["expected_unsatisfied"] is True
    assert unsatisfied["hbond_unsatisfied_total_count"] >= 1
    assert unsatisfied["benchmark_contract_pass"] is True

    overanchored = rows["amide_overanchored_decoy_pose"]
    assert overanchored["hbond_claim_safe"] is False
    assert overanchored["overanchoring_flag"] is True
    assert overanchored["hbond_blocked_reason"] == "overanchored_decoy"
    assert overanchored["expected_overanchored"] is True
    assert overanchored["benchmark_contract_pass"] is True

    metadata = report.claim_metadata
    assert metadata["hbond_recovery_benchmark_schema_version"] == HBOND_RECOVERY_BENCHMARK_SCHEMA_VERSION
    assert metadata["hbond_recovery_benchmark_ready"] is True
    assert metadata["hbond_recovery_present"] is True
    assert metadata["hbond_overanchored_decoys_blocked"] is True
    assert metadata["claim_safe"] is False
    assert metadata["blocked_reason"] == "hbond_recovery_benchmark_not_product_claim_promoted"


def test_hbond_recovery_benchmark_fails_closed_on_missing_anchor_fixture() -> None:
    ligand = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    missing_anchor_fixture = HbondRecoveryFixture(
        pose_id="active_claim_missing_anchor",
        benchmark_role="active_recovery_pose",
        smiles="CCO",
        ligand_xyz=ligand,
        protein_xyz=np.asarray([[9.0, 0.0, 0.0], [10.0, 0.0, 0.0]], dtype=np.float32),
        expected_claim_safe=True,
    )

    report = build_hbond_recovery_benchmark([missing_anchor_fixture])

    assert report.ready is False
    assert report.status == "blocked_hbond_recovery_benchmark"
    assert report.summary["hbond_recovery_present"] is False
    assert report.summary["benchmark_contract_pass_count"] == 0
    assert report.rows[0]["hbond_claim_safe"] is False
    assert report.rows[0]["hbond_blocked_reason"] == "missing_expected_anchor"
    assert report.rows[0]["benchmark_contract_pass"] is False
    assert report.claim_metadata["claim_safe"] is False
    assert report.claim_metadata["blocked_reason"] == "hbond_recovery_benchmark_not_ready"
