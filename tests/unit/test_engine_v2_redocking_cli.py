from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.redocking_cli import (  # noqa: E402
    REDOCKING_DIAGNOSTIC_BLOCKERS,
    REDOCKING_DIAGNOSTIC_SCHEMA_ID,
    RedockingDiagnosticConfig,
    RedockingDiagnosticError,
    main,
    run_prepared_redocking_diagnostic,
    verify_redocking_diagnostic_report,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_json_bytes,
    canonical_system_json_bytes,
    sha256_canonical,
)


def _system(
    system_id: str,
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    bonds: tuple[tuple[int, int], ...] = (),
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id=system_id,
        atoms=atoms,
        bonds=tuple(
            Bond(index=index, atom_i=first, atom_j=second)
            for index, (first, second) in enumerate(bonds)
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _receptor() -> AllAtomSystem:
    return _system(
        "receptor",
        (
            (13.0, 10.0, 10.0),
            (7.0, 10.0, 10.0),
            (10.0, 13.0, 10.0),
            (10.0, 7.0, 10.0),
            (10.0, 10.0, 13.0),
        ),
    )


def _ligand() -> AllAtomSystem:
    return _system(
        "ligand",
        (
            (20.0, 20.0, 20.0),
            (21.4, 20.0, 20.0),
            (22.7, 20.5, 20.0),
        ),
        bonds=((0, 1), (1, 2)),
    )


def _run() -> dict[str, object]:
    receptor = _receptor()
    ligand = _ligand()
    receptor_source = canonical_system_json_bytes(receptor)
    ligand_source = canonical_system_json_bytes(ligand)
    return run_prepared_redocking_diagnostic(
        receptor,
        ligand,
        receptor_artifact_sha256=hashlib.sha256(receptor_source).hexdigest(),
        ligand_artifact_sha256=hashlib.sha256(ligand_source).hexdigest(),
        pocket_center_angstrom=(10.0, 10.0, 10.0),
        pocket_radius_angstrom=6.0,
        config=RedockingDiagnosticConfig(
            candidate_count=6,
            top_k=2,
            translation_radius_angstrom=2.0,
            diversity_rmsd_angstrom=0.25,
            seed=41,
        ),
    )


def test_redocking_diagnostic_is_authenticated_deterministic_and_claim_closed() -> None:
    report = _run()
    repeated = _run()

    assert report["schema_id"] == REDOCKING_DIAGNOSTIC_SCHEMA_ID
    assert report["status"] == "diagnostic_complete"
    assert report["receipt_sha256"] == repeated["receipt_sha256"]
    assert canonical_json_bytes(report) == canonical_json_bytes(repeated)
    assert report["claims"] == {
        "benchmark_validated": False,
        "calibrated_docking_engine": False,
        "claim_safe": False,
        "customer_execution_enabled": False,
        "scientifically_validated": False,
        "supported_chemistry_validated": False,
    }
    assert set(REDOCKING_DIAGNOSTIC_BLOCKERS).issubset(report["scientific_blockers"])
    assert (
        report["authenticated_problem_input"][
            "authenticated_to_concrete_molecular_state"
        ]
        is True
    )
    assert report["search"]["candidate_count"] == 6
    assert report["search"]["scorer_id"] == "element-geometry-diagnostic"
    assert report["config"]["proposal_generation"]["mode"] == "rigid_haar"
    assert report["config"]["proposal_generation"]["requested_max_torsions"] == 32
    assert report["config"]["proposal_generation"]["effective_max_torsions"] == 0
    assert report["config"]["proposal_generation"][
        "global_torsion_sampling_enabled"
    ] is False
    assert report["config"]["proposal_generation"][
        "haar_rotation_sampling_enabled"
    ] is True
    assert report["config"]["proposal_generation"][
        "steric_field_guidance_enabled"
    ] is False
    assert report["config"]["proposal_generation"]["steric_field_plan"] is None
    assert report["search"]["translation_placement_plan_sha256"] == ""
    assert report["search"]["budget"]["max_torsions"] == 0
    assert report["config"]["pose_score"]["preparation_gate_satisfied"] is False
    assert report["config"]["pose_score"]["feature_binding_sha256"] is None
    assert report["config"]["pose_refinement"]["preparation_gate_satisfied"] is False
    assert report["config"]["pose_refinement"]["requested_max_refinement_steps"] == 6
    assert report["config"]["pose_refinement"]["effective_max_refinement_steps"] == 0
    assert report["config"]["pose_refinement"]["performed"] is False
    assert report["config"]["pose_refinement"]["refiner_id"] is None
    assert report["search"]["budget"]["max_refinement_steps"] == 0
    assert report["search"]["refiner_id"] == ""
    assert report["config"]["pose_validity"]["preparation_gate_satisfied"] is False
    assert report["config"]["pose_validity"]["result_schema_id"] is None
    assert report["config"]["pose_score"]["scorer_id"] == report["search"]["scorer_id"]
    assert (
        "interpretable_pose_scorer_v0_requires_verified_ligand_preparation"
        in report["scientific_blockers"]
    )
    assert (
        "chemistry_aware_pose_validity_v2_requires_verified_ligand_preparation"
        in report["scientific_blockers"]
    )
    assert (
        "interpretable_local_refiner_v0_requires_verified_ligand_preparation"
        in report["scientific_blockers"]
    )
    assert (
        "global_torsion_pose_generation_requires_verified_preparation_and_positive_budget"
        in report["scientific_blockers"]
    )
    assert (
        "steric_field_guided_proposals_require_verified_preparation"
        in report["scientific_blockers"]
    )
    assert len(report["search"]["rows"]) == 6
    assert all(
        row["proposal_sampling_state"]["torsion_variable_count"] == 0
        for row in report["search"]["rows"]
    )
    assert all(
        row["proposal_sampling_state"]["translation_placement_receipt"][
            "placement_plan_sha256"
        ]
        == ""
        for row in report["search"]["rows"]
    )
    assert all(
        row["refined"] is False
        and row["refinement_receipt_sha256"] == ""
        and row["refinement_receipt"] is None
        for row in report["search"]["rows"]
    )
    assert report["search"]["diversity_metric"] == ("symmetry_aware_direct_rmsd")
    assert report["search"]["claim_safe"] is False
    assert report["summary"]["all_candidate_rows_retained"] is True
    assert report["summary"]["top_pose_count"] >= 1
    assert len(report["top_poses"]) == report["summary"]["top_pose_count"]
    assert all(
        row["coordinate_frame_id"] == "canonical_receptor_input_frame"
        for row in report["top_poses"]
    )
    assert (
        verify_redocking_diagnostic_report(canonical_json_bytes(report))[
            "receipt_sha256"
        ]
        == report["receipt_sha256"]
    )


def test_redocking_cli_writes_private_receipt_and_refuses_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    output = tmp_path / "redocking-receipt.json"
    receptor_path.write_bytes(canonical_system_json_bytes(_receptor()))
    ligand_path.write_bytes(canonical_system_json_bytes(_ligand()))
    arguments = [
        "--receptor-canonical-json",
        str(receptor_path),
        "--ligand-canonical-json",
        str(ligand_path),
        "--pocket-center",
        "10",
        "10",
        "10",
        "--pocket-radius",
        "6",
        "--candidate-count",
        "4",
        "--top-k",
        "2",
        "--translation-radius",
        "2",
        "--seed",
        "43",
        "--output",
        str(output),
    ]

    assert main(arguments) == 0
    captured = capsys.readouterr()
    assert '"status":"diagnostic_complete"' in captured.out
    original = output.read_bytes()
    receipt = verify_redocking_diagnostic_report(original)
    assert receipt["summary"]["candidate_count"] == 4
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    assert main(arguments) == 1
    captured = capsys.readouterr()
    assert "no output path was replaced" in captured.err
    assert output.read_bytes() == original


def test_redocking_cli_preserves_a_sanitized_failure_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receptor_path = tmp_path / "invalid-receptor.json"
    ligand_path = tmp_path / "ligand.json"
    output = tmp_path / "failure.json"
    receptor_path.write_bytes(b"{}\n")
    ligand_path.write_bytes(canonical_system_json_bytes(_ligand()))

    assert (
        main(
            [
                "--receptor-canonical-json",
                str(receptor_path),
                "--ligand-canonical-json",
                str(ligand_path),
                "--pocket-center",
                "10",
                "10",
                "10",
                "--pocket-radius",
                "6",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    receipt = verify_redocking_diagnostic_report(output.read_bytes())
    assert receipt["status"] == "failure"
    assert receipt["claims"]["claim_safe"] is False
    assert receipt["failure"]["public_message"] == (
        "prepared redocking diagnostic failed"
    )
    assert "canonical system document" not in captured.err
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


@pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="symlink-open rejection requires O_NOFOLLOW",
)
def test_redocking_cli_rejects_symlink_inputs(
    tmp_path: Path,
) -> None:
    real_receptor = tmp_path / "real-receptor.json"
    receptor_link = tmp_path / "receptor-link.json"
    ligand_path = tmp_path / "ligand.json"
    output = tmp_path / "symlink-failure.json"
    real_receptor.write_bytes(canonical_system_json_bytes(_receptor()))
    receptor_link.symlink_to(real_receptor)
    ligand_path.write_bytes(canonical_system_json_bytes(_ligand()))

    assert (
        main(
            [
                "--receptor-canonical-json",
                str(receptor_link),
                "--ligand-canonical-json",
                str(ligand_path),
                "--pocket-center",
                "10",
                "10",
                "10",
                "--pocket-radius",
                "6",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert (
        verify_redocking_diagnostic_report(output.read_bytes())["status"] == "failure"
    )


def test_redocking_receipt_verifier_rejects_claim_promotion() -> None:
    document = json.loads(canonical_json_bytes(_run()))
    document["claims"]["scientifically_validated"] = True

    with pytest.raises(
        RedockingDiagnosticError,
        match="claim flags cannot be promoted",
    ):
        verify_redocking_diagnostic_report(canonical_json_bytes(document))


def test_redocking_receipt_verifier_rejects_cross_wired_pose_scorer() -> None:
    document = json.loads(canonical_json_bytes(_run()))
    document["config"]["pose_score"]["scorer_id"] = "interpretable-pose-scorer-v0"
    document.pop("receipt_sha256")
    document["receipt_sha256"] = sha256_canonical(document)

    with pytest.raises(
        RedockingDiagnosticError,
        match="pose-score binding",
    ):
        verify_redocking_diagnostic_report(canonical_json_bytes(document))


def test_redocking_receipt_verifier_rejects_malformed_blocker_rows() -> None:
    document = json.loads(canonical_json_bytes(_run()))
    document["scientific_blockers"].append({"not": "a blocker"})
    document.pop("receipt_sha256")
    document["receipt_sha256"] = sha256_canonical(document)

    with pytest.raises(
        RedockingDiagnosticError,
        match="scientific blockers",
    ):
        verify_redocking_diagnostic_report(canonical_json_bytes(document))


def test_redocking_receipt_verifier_rejects_cross_wired_pose_validity() -> None:
    document = json.loads(canonical_json_bytes(_run()))
    document["config"]["pose_validity"]["context_fingerprint_sha256"] = "f" * 64
    document.pop("receipt_sha256")
    document["receipt_sha256"] = sha256_canonical(document)

    with pytest.raises(
        RedockingDiagnosticError,
        match="pose-validity binding",
    ):
        verify_redocking_diagnostic_report(canonical_json_bytes(document))


def test_redocking_config_fails_closed_on_unbounded_candidate_count() -> None:
    with pytest.raises(
        RedockingDiagnosticError,
        match="candidate_count",
    ):
        RedockingDiagnosticConfig(candidate_count=1_025)

    with pytest.raises(
        RedockingDiagnosticError,
        match="max_refinement_steps",
    ):
        RedockingDiagnosticConfig(max_refinement_steps=33)

    with pytest.raises(
        RedockingDiagnosticError,
        match="max_torsions",
    ):
        RedockingDiagnosticConfig(max_torsions=65)
