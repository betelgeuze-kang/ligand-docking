from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_BLOCKERS,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
    PublicFlexibleDockingDiagnosticConfig,
    PublicFlexibleDockingDiagnosticError,
    PublicRigidDockingDiagnosticConfig,
    run_public_flexible_docking_diagnostic,
    run_public_rigid_docking_diagnostic,
    write_public_flexible_docking_diagnostic_report,
)
from betelgeuze_engine_v2.benchmark.public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
)
from betelgeuze_engine_v2.docking import (
    ElementGeometryDiagnosticScoreConfig,
    GeometricRigidRefinementConfig,
    MolecularTorsionSearchConfig,
)


_LIGAND_SDF = b"""flexible-four-carbon
unit-test

  4  3  0  0  0  0            999 V2000
    0.0000    1.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.4000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.8000    1.1000    0.7000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  2  3  1  0  0  0  0
  3  4  1  0  0  0  0
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


def _base_config() -> PublicRigidDockingDiagnosticConfig:
    return PublicRigidDockingDiagnosticConfig(
        candidate_count=12,
        top_k=3,
        translation_radius_angstrom=1.5,
        diversity_rmsd_angstrom=0.0,
        seed=79,
        refinement_steps=3,
        geometry_score=ElementGeometryDiagnosticScoreConfig(
            interaction_cutoff_angstrom=8.0,
            receptor_shell_radius_angstrom=10.0,
            pocket_radius_angstrom=6.0,
        ),
        rigid_refinement=GeometricRigidRefinementConfig(maximum_steps=3),
    )


def _config(*, max_rotatable_bonds: int = 2) -> PublicFlexibleDockingDiagnosticConfig:
    return PublicFlexibleDockingDiagnosticConfig(
        search_and_refinement=_base_config(),
        torsion_search=MolecularTorsionSearchConfig(
            max_rotatable_bonds=max_rotatable_bonds
        ),
    )


def test_flexible_diagnostic_materializes_torsions_and_retains_all_rows() -> None:
    protocol, sources = _protocol_and_sources()

    report = run_public_flexible_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    )

    assert report.successful_case_count == 4
    assert report.executed_case_count == 4
    assert report.candidate_count == 48
    assert report.evaluated_candidate_count == 48
    assert report.torsion_sampling_case_count == 4
    assert report.torsion_variable_count_total == 4
    assert report.refinement_candidate_count == 12
    assert report.refinement_success_count == 12
    assert report.refinement_failure_count == 0
    for row in report.case_rows:
        assert row.status == "success"
        assert row.summary["torsion_sampling_performed"] is True
        assert row.summary["torsion_variable_count"] == 1
        assert row.summary["torsion_search_receipt"]["rotatable_bond_count"] == 1
        assert row.summary["refinement_success_count"] == 3
        assert row.summary["validity_gated_selection"] is True
        assert row.summary["invalid_candidates_excluded_from_selection"] is True
        assert len(row.candidate_rows) == 12
        assert all(
            candidate.valid
            for candidate in row.candidate_rows
            if candidate.selected_rank > 0
        )
        assert all(
            any(
                term["term_id"] == "ligand_nonbonded_self_overlap_penalty"
                for term in candidate.score_breakdown["terms"]
            )
            for candidate in row.candidate_rows
        )
    payload = report.to_dict()
    assert payload["flexible_pose_generation_performed"] is True
    assert payload["torsion_refinement_performed"] is False
    assert payload["flexible_internal_self_overlap_scored"] is True
    assert payload["force_field_internal_strain_scored"] is False
    assert payload["validity_gated_final_selection"] is True
    assert payload["public_benchmark_executed"] is False
    assert payload["public_holdout_result_established"] is False
    assert payload["claim_safe"] is False
    assert report.scientific_blockers == PUBLIC_FLEXIBLE_DOCKING_DIAGNOSTIC_BLOCKERS


def test_flexible_diagnostic_is_deterministic_and_distinct_from_rigid_search() -> None:
    protocol, sources = _protocol_and_sources()
    first = run_public_flexible_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    )
    second = run_public_flexible_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    )
    rigid = run_public_rigid_docking_diagnostic(
        protocol,
        sources,
        config=_base_config(),
    )

    assert first.to_json_bytes() == second.to_json_bytes()
    assert first.protocol_sha256 == rigid.protocol_sha256
    assert first.input_suite_receipt_sha256 == rigid.input_suite_receipt_sha256
    assert first.case_rows[0].summary["search_fingerprint_sha256"] != (
        rigid.case_rows[0].summary["search_fingerprint_sha256"]
    )


def test_torsion_capacity_failures_retain_all_four_case_rows() -> None:
    protocol, sources = _protocol_and_sources()

    report = run_public_flexible_docking_diagnostic(
        protocol,
        sources,
        config=_config(max_rotatable_bonds=0),
    )

    assert report.executed_case_count == 0
    assert report.successful_case_count == 0
    assert report.candidate_count == 0
    assert len(report.case_rows) == 4
    assert all(row.status == "failure" for row in report.case_rows)
    assert all(
        row.error_code == "MolecularTorsionSearchError" for row in report.case_rows
    )
    assert report.to_dict()["case_denominator"] == "all_four_protocol_cases"


def test_flexible_report_is_private_and_no_overwrite(tmp_path: Path) -> None:
    protocol, sources = _protocol_and_sources()
    report = run_public_flexible_docking_diagnostic(
        protocol,
        sources,
        config=_config(),
    )
    output = write_public_flexible_docking_diagnostic_report(
        report,
        tmp_path / "flexible-diagnostic.json",
    )

    assert output.read_bytes() == report.to_json_bytes()
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(PublicFlexibleDockingDiagnosticError, match="already exists"):
        write_public_flexible_docking_diagnostic_report(report, output)


def test_public_flexible_diagnostic_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import benchmark
    from betelgeuze_engine_v2.benchmark.public_flexible_diagnostic import (
        __all__ as flexible_exports,
    )

    assert set(flexible_exports) <= set(benchmark.__all__)
