from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    PUBLIC_RIGID_DOCKING_DIAGNOSTIC_BLOCKERS,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
    PublicRigidDockingDiagnosticConfig,
    PublicRigidDockingDiagnosticError,
    run_public_rigid_docking_diagnostic,
    write_public_rigid_docking_diagnostic_report,
)
from betelgeuze_engine_v2.benchmark.public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
)
from betelgeuze_engine_v2.docking import (
    ElementGeometryDiagnosticScoreConfig,
    GeometricRigidBodyRefiner,
    GeometricRigidRefinementConfig,
)


_LIGAND_SDF = b"""rigid-two-carbon
unit-test

  2  1  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.4000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
$$$$
"""


def _pdb_atom(
    serial: int,
    name: str,
    element: str,
    x: float,
    y: float,
    z: float,
) -> str:
    return (
        f"{'ATOM':<6}{serial:5d} {name:<4}{'':1}{'ALA':>3} {'A':1}{1:4d}{'':1}   "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{10.0:6.2f}          {element:>2}{'':>2}"
    )


def _receptor() -> bytes:
    return (
        "\n".join(
            (
                f"CRYST1{20.0:9.3f}{21.0:9.3f}{22.0:9.3f}{80.0:7.2f}{90.0:7.2f}{90.0:7.2f} P 1           1",
                _pdb_atom(1, "C1", "C", 0.0, 3.4, 0.0),
                _pdb_atom(2, "O1", "O", 1.4, 3.2, 0.0),
                "END",
            )
        )
        + "\n"
    ).encode("ascii")


def _artifact(
    pdb_id: str,
    role: str,
    filename: str,
    source: bytes,
) -> PublicBenchmarkArtifact:
    relative_path = f"posebusters/datasets/pdb/{pdb_id}/{pdb_id}_{filename}"
    return PublicBenchmarkArtifact(
        role=role,
        relative_path=relative_path,
        immutable_url=(
            "https://raw.githubusercontent.com/maabuu/posebusters/"
            f"{POSEBUSTERS_SOURCE_COMMIT_SHA}/{relative_path}"
        ),
        sha256=hashlib.sha256(source).hexdigest(),
        size_bytes=len(source),
        media_type=("chemical/x-pdb" if role == "receptor" else "chemical/x-mdl-sdfile"),
    )


def _protocol_and_sources() -> tuple[FrozenPublicBenchmarkProtocol, dict[str, bytes]]:
    receptor = _receptor()
    cases = []
    sources: dict[str, bytes] = {}
    for pdb_id in ("1abc", "2abc", "3abc", "4abc"):
        receptor_artifact = _artifact(
            pdb_id,
            "receptor",
            "protein_one_lig_removed.pdb",
            receptor,
        )
        reference_artifact = _artifact(
            pdb_id,
            "reference_ligands",
            "ligands.sdf",
            _LIGAND_SDF,
        )
        seed_artifact = _artifact(
            pdb_id,
            "ligand_identity_seed",
            "ligand.sdf",
            _LIGAND_SDF,
        )
        cases.append(
            PublicBenchmarkCaseDefinition(
                case_id=f"posebusters-packaged-{pdb_id}",
                pdb_id=pdb_id,
                receptor=receptor_artifact,
                reference_ligands=reference_artifact,
                ligand_identity_seed=seed_artifact,
            )
        )
        sources[receptor_artifact.relative_path] = receptor
        sources[reference_artifact.relative_path] = _LIGAND_SDF
        sources[seed_artifact.relative_path] = _LIGAND_SDF
    return FrozenPublicBenchmarkProtocol(cases=tuple(cases), scorer_identities=()), sources


def _config() -> PublicRigidDockingDiagnosticConfig:
    return PublicRigidDockingDiagnosticConfig(
        candidate_count=12,
        top_k=3,
        translation_radius_angstrom=1.5,
        diversity_rmsd_angstrom=0.0,
        seed=71,
        refinement_steps=4,
        geometry_score=ElementGeometryDiagnosticScoreConfig(
            interaction_cutoff_angstrom=8.0,
            receptor_shell_radius_angstrom=10.0,
            pocket_radius_angstrom=6.0,
        ),
        rigid_refinement=GeometricRigidRefinementConfig(maximum_steps=4),
    )


def test_rigid_diagnostic_generates_scores_validity_rmsd_and_all_rows() -> None:
    protocol, sources = _protocol_and_sources()

    report = run_public_rigid_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    )

    assert report.successful_case_count == 4
    assert report.executed_case_count == 4
    assert report.candidate_count == 48
    assert report.evaluated_candidate_count == 48
    assert len(report.case_rows) == 4
    for row in report.case_rows:
        assert row.status == "success"
        assert row.discarded_cryst1_record_count == 1
        assert row.receptor_atom_count == 2
        assert row.ligand_atom_count == 2
        assert len(row.candidate_rows) == 12
        assert row.summary["selected_pose_count"] == 3
        assert row.summary["metric_available"] is True
        assert row.summary["oracle_best_all_rmsd_angstrom"] is not None
        assert row.summary["oracle_best_all_score_rank"] >= 1
        assert row.summary["generated_primary_hit_count"] >= 0
        assert row.summary["refinement_attempted"] is True
        assert row.summary["refinement_performed"] is True
        assert row.summary["refinement_candidate_count"] == 3
        assert row.summary["refinement_success_count"] == 3
        assert row.summary["refinement_failure_count"] == 0
        assert row.summary["refinement_executed_step_count"] >= 3
        assert len(row.summary["refinement_receipt_sha256s"]) == 3
        assert row.summary["torsion_sampling_performed"] is False
        assert all(candidate.score_breakdown is not None for candidate in row.candidate_rows)
        assert all(candidate.validity is not None for candidate in row.candidate_rows)
        assert all(candidate.rmsd is not None for candidate in row.candidate_rows)
        refined = [candidate for candidate in row.candidate_rows if candidate.refined]
        assert len(refined) == 3
        assert all(candidate.refinement_receipt is not None for candidate in refined)
        assert all(candidate.refinement_receipt_sha256 for candidate in refined)
    payload = report.to_dict()
    assert payload["diagnostic_execution_performed"] is True
    assert payload["docking_predictions_present"] is True
    assert payload["pose_validity_evaluated"] is True
    assert payload["refinement_candidate_count"] == 12
    assert payload["refinement_success_count"] == 12
    assert payload["refinement_failure_count"] == 0
    assert payload["rigid_refinement_performed"] is True
    assert payload["rigid_refinement_failure_rows_retained"] is True
    assert payload["public_benchmark_executed"] is False
    assert payload["public_holdout_result_established"] is False
    assert payload["claim_safe"] is False
    assert report.scientific_blockers == PUBLIC_RIGID_DOCKING_DIAGNOSTIC_BLOCKERS


def test_rigid_diagnostic_is_deterministic_and_missing_input_stays_in_denominator() -> None:
    protocol, sources = _protocol_and_sources()
    first = run_public_rigid_docking_diagnostic(protocol, sources, config=_config())
    second = run_public_rigid_docking_diagnostic(protocol, sources, config=_config())
    assert first.to_json_bytes() == second.to_json_bytes()

    missing = dict(sources)
    del missing[protocol.cases[0].receptor.relative_path]
    failed = run_public_rigid_docking_diagnostic(protocol, missing, config=_config())

    assert len(failed.case_rows) == 4
    assert failed.case_rows[0].status == "failure"
    assert failed.case_rows[0].summary["top1_success"] is False
    assert failed.successful_case_count == 3
    assert failed.candidate_count == 36
    assert failed.to_dict()["case_denominator"] == "all_four_protocol_cases"


def test_report_is_protocol_bound_private_and_no_overwrite(
    tmp_path: Path,
) -> None:
    protocol, sources = _protocol_and_sources()
    report = run_public_rigid_docking_diagnostic(protocol, sources, config=_config())
    output = write_public_rigid_docking_diagnostic_report(
        report,
        tmp_path / "rigid-diagnostic.json",
    )

    assert output.read_bytes() == report.to_json_bytes()
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(PublicRigidDockingDiagnosticError, match="already exists"):
        write_public_rigid_docking_diagnostic_report(report, output)


def test_refinement_failures_are_retained_without_dropping_case_denominators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol, sources = _protocol_and_sources()

    def fail_refinement(self, proposal, *, max_steps):
        raise RuntimeError("private refinement detail")

    monkeypatch.setattr(
        GeometricRigidBodyRefiner,
        "refine_with_receipt",
        fail_refinement,
    )
    report = run_public_rigid_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    )

    assert report.executed_case_count == 4
    assert report.successful_case_count == 0
    assert report.candidate_count == 48
    assert report.evaluated_candidate_count == 36
    assert report.refinement_candidate_count == 12
    assert report.refinement_success_count == 0
    assert report.refinement_failure_count == 12
    for row in report.case_rows:
        assert row.status == "partial_failure"
        failures = [
            candidate
            for candidate in row.candidate_rows
            if candidate.status == "refinement_failure"
        ]
        assert len(failures) == 3
        assert all(candidate.error_code == "RuntimeError" for candidate in failures)
        assert all(candidate.private_error_sha256 for candidate in failures)
        assert all(not candidate.refined for candidate in failures)


def test_report_serializes_explicit_nonclaim_and_reference_leakage_boundaries() -> None:
    protocol, sources = _protocol_and_sources()
    payload = run_public_rigid_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    ).to_dict()

    assert payload["config"]["max_torsions"] == 0
    assert payload["config"]["max_refinement_steps"] == 4
    assert payload["config"]["refinement_candidate_policy"] == (
        "initial_diverse_score_top_k_only"
    )
    assert payload["config"]["pocket_center_policy"].startswith(
        "centroid_of_lowest_record_index"
    )
    assert "native_reference_coordinates_used_to_define_redocking_pocket" in (
        payload["scientific_blockers"]
    )
    assert "same_input_vina_gnina_smina_receipts_missing" in (
        payload["scientific_blockers"]
    )
    assert payload["probability_calibrated"] is False
    assert payload["benchmark_validated"] is False


def test_public_rigid_diagnostic_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import benchmark
    from betelgeuze_engine_v2.benchmark.public_rigid_diagnostic import (
        __all__ as diagnostic_exports,
    )

    assert set(diagnostic_exports) <= set(benchmark.__all__)
