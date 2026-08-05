from __future__ import annotations

from dataclasses import replace

import pytest

from betelgeuze_engine_v2.benchmark.oracle_selection_evidence import (
    OracleSelectionEvidence,
    build_oracle_selection_evidence,
)
from betelgeuze_engine_v2.benchmark.oracle_selection_metrics import (
    CandidateObservation,
    OracleSelectionError,
)


def _rows() -> tuple[CandidateObservation, ...]:
    return (
        CandidateObservation(
            proposal_index=0,
            score=-8.0,
            rmsd_angstrom=5.0,
            valid=True,
        ),
        CandidateObservation(
            proposal_index=1,
            score=-4.0,
            rmsd_angstrom=1.0,
            valid=True,
        ),
        CandidateObservation(
            proposal_index=2,
            score=-2.0,
            rmsd_angstrom=1.5,
            valid=False,
        ),
    )


def test_full_observations_rederive_ranking_failure_report() -> None:
    evidence = build_oracle_selection_evidence(
        _rows(),
        rmsd_threshold_angstrom=2.0,
        top_ks=(1, 2, 3),
    )

    assert evidence.report.failure_class == "ranking_failure"
    assert evidence.to_dict()["full_observation_rederivation_verified"] is True
    assert evidence.receipt_sha256 == build_oracle_selection_evidence(
        _rows(),
        rmsd_threshold_angstrom=2.0,
        top_ks=(1, 2, 3),
    ).receipt_sha256


def test_resealed_report_failure_class_is_rejected() -> None:
    evidence = build_oracle_selection_evidence(
        _rows(),
        rmsd_threshold_angstrom=2.0,
        top_ks=(1, 2, 3),
    )
    forged_report = replace(evidence.report, failure_class="success")

    with pytest.raises(OracleSelectionError, match="observation rederivation"):
        replace(evidence, report=forged_report)


def test_resealed_observation_score_is_rejected() -> None:
    evidence = build_oracle_selection_evidence(
        _rows(),
        rmsd_threshold_angstrom=2.0,
        top_ks=(1, 2, 3),
    )
    changed_rows = (
        replace(evidence.observations[0], score=-1.0),
        *evidence.observations[1:],
    )

    with pytest.raises(OracleSelectionError, match="observation rederivation"):
        OracleSelectionEvidence(
            observations=changed_rows,
            rmsd_threshold_angstrom=evidence.rmsd_threshold_angstrom,
            top_ks=evidence.top_ks,
            report=evidence.report,
        )


def test_resealed_threshold_is_rejected() -> None:
    evidence = build_oracle_selection_evidence(
        _rows(),
        rmsd_threshold_angstrom=2.0,
        top_ks=(1, 2, 3),
    )

    with pytest.raises(OracleSelectionError, match="observation rederivation"):
        replace(evidence, rmsd_threshold_angstrom=4.0)
