from __future__ import annotations

# Torch is optional for collection, so imports depending on it intentionally follow
# the importorskip guard below.
# ruff: noqa: E402

import hashlib
from types import SimpleNamespace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import public_materializer as materializer_module
from betelgeuze_engine_v2.benchmark.public_evaluator import (
    PublicBenchmarkEvaluationCaseInput,
    PublicBenchmarkEvaluationError,
    _materialized_metric_mappings,
    run_offline_public_benchmark_evaluation,
)
from betelgeuze_engine_v2.benchmark.public_materializer import (
    materialize_frozen_public_benchmark_inputs,
)
from betelgeuze_engine_v2.benchmark.public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
)
from betelgeuze_engine_v2.io import parse_sdf_v2000


def _atom_line(element: str, x: float, y: float, z: float) -> str:
    return (
        f"{x:10.4f}{y:10.4f}{z:10.4f} "
        f"{element:<3}{0:2d}{0:3d}  0  0  0  0  0  0  0  0  0  0  0  0"
    )


def _sdf_record(
    title: str,
    atoms: tuple[tuple[str, float, float, float], ...],
    bonds: tuple[tuple[int, int, int], ...],
) -> bytes:
    rows = [
        title,
        "EngineV2",
        "offline evaluator fixture",
        f"{len(atoms):3d}{len(bonds):3d}  0  0  0  0            999 V2000",
        *[_atom_line(*atom) for atom in atoms],
        *[
            f"{first:3d}{second:3d}{order:3d}{0:3d}  0  0  0"
            for first, second, order in bonds
        ],
        "M  END",
        "$$$$",
    ]
    return ("\n".join(rows) + "\n").encode("ascii")


def _seed_record(*, shift: float = 0.0) -> bytes:
    return _sdf_record(
        "seed",
        (
            ("C", 0.0 + shift, 0.0, 0.0),
            ("N", 1.0 + shift, 0.0, 0.0),
            ("O", 2.0 + shift, 0.5, 0.0),
        ),
        ((1, 2, 1), (2, 3, 1)),
    )


def _reference_record() -> bytes:
    return _sdf_record(
        "reference",
        (
            ("N", 1.0, 0.0, 0.0),
            ("O", 2.0, 0.5, 0.0),
            ("C", 0.0, 0.0, 0.0),
        ),
        ((3, 1, 1), (1, 2, 1)),
    )


def _artifact(
    pdb_id: str,
    *,
    role: str,
    filename: str,
    payload: bytes,
    media_type: str,
) -> PublicBenchmarkArtifact:
    relative = f"posebusters/datasets/pdb/{pdb_id}/{filename}"
    return PublicBenchmarkArtifact(
        role=role,
        relative_path=relative,
        immutable_url=(
            "https://raw.githubusercontent.com/maabuu/posebusters/"
            f"{POSEBUSTERS_SOURCE_COMMIT_SHA}/{relative}"
        ),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        media_type=media_type,
    )


def _case(
    pdb_id: str,
) -> tuple[PublicBenchmarkCaseDefinition, dict[str, bytes]]:
    receptor = b"HEADER    SYNTHETIC RECEPTOR\nEND\n"
    reference = _reference_record()
    seed = _seed_record()
    case = PublicBenchmarkCaseDefinition(
        case_id=f"synthetic-{pdb_id}",
        pdb_id=pdb_id,
        receptor=_artifact(
            pdb_id,
            role="receptor",
            filename=f"{pdb_id}_protein_one_lig_removed.pdb",
            payload=receptor,
            media_type="chemical/x-pdb",
        ),
        reference_ligands=_artifact(
            pdb_id,
            role="reference_ligands",
            filename=f"{pdb_id}_ligands.sdf",
            payload=reference,
            media_type="chemical/x-mdl-sdfile",
        ),
        ligand_identity_seed=_artifact(
            pdb_id,
            role="ligand_identity_seed",
            filename=f"{pdb_id}_ligand.sdf",
            payload=seed,
            media_type="chemical/x-mdl-sdfile",
        ),
    )
    return case, {
        "receptor": receptor,
        "reference_ligands": reference,
        "ligand_identity_seed": seed,
    }


def _evaluation_input(
    materialization,
    *,
    candidate_shift: float = 0.0,
) -> PublicBenchmarkEvaluationCaseInput:
    reference = parse_sdf_v2000(
        _reference_record().decode("ascii"),
        source_id=(
            f"{materialization.case_id}:reference:"
            f"{materialization.selected_reference_record_index}"
        ),
    )
    seed = parse_sdf_v2000(
        _seed_record().decode("ascii"),
        source_id=f"{materialization.case_id}:ligand-identity-seed",
    )
    candidate_bytes = _seed_record(shift=candidate_shift)
    candidate = parse_sdf_v2000(
        candidate_bytes.decode("ascii"),
        source_id=f"{materialization.case_id}:candidate",
    )
    pocket_center = torch.tensor([1.0, 0.1, 0.0], dtype=torch.float64)
    return PublicBenchmarkEvaluationCaseInput(
        case_id=materialization.case_id,
        materialization=materialization,
        receptor_artifact_sha256=materialization.receptor_sha256,
        reference_artifact_sha256=materialization.reference_ligands_sha256,
        ligand_identity_seed_artifact_sha256=(
            materialization.ligand_identity_seed_sha256
        ),
        candidate_artifact_sha256=hashlib.sha256(candidate_bytes).hexdigest(),
        receptor_system_sha256="a" * 64,
        reference_system=reference,
        ligand_identity_seed_system=seed,
        candidate_system=candidate,
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]], dtype=torch.float64
        ),
        pocket_center=pocket_center,
        pocket_radius_angstrom=10.0,
        excluded_nonbonded_pairs=((0, 1), (1, 2)),
        chirality_centers=(),
    )


def _manifest(monkeypatch: pytest.MonkeyPatch):
    case_rows = [_case(pdb_id) for pdb_id in ("1aaa", "1aab", "1aac", "1aad")]
    protocol = FrozenPublicBenchmarkProtocol(
        cases=tuple(case for case, _ in case_rows),
        scorer_identities=(),
    )
    monkeypatch.setattr(
        materializer_module,
        "FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256",
        protocol.protocol_sha256,
    )
    supplied = {case.case_id: payloads for case, payloads in case_rows}
    supplied[case_rows[3][0].case_id] = {
        **supplied[case_rows[3][0].case_id],
        "receptor": b"tampered receptor\n",
    }
    manifest = materialize_frozen_public_benchmark_inputs(
        supplied,
        protocol=protocol,
    )
    return manifest


def test_legacy_materialization_permutations_are_inverted_explicitly() -> None:
    legacy = SimpleNamespace(
        symmetry_permutations=((2, 0, 1),),
        to_dict=lambda: {},
    )
    assert _materialized_metric_mappings(legacy) == ((1, 2, 0),)


def test_offline_evaluator_retains_all_rows_and_uses_all_case_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(monkeypatch)
    first = manifest.rows[0].materialization
    second = manifest.rows[1].materialization
    assert first is not None and second is not None
    inputs = {
        first.case_id: _evaluation_input(first),
        second.case_id: _evaluation_input(second, candidate_shift=50.0),
        # Third successful materialization is intentionally missing.
        # Fourth materialization failed before evaluation.
    }
    report = run_offline_public_benchmark_evaluation(
        manifest,
        inputs,
        engine_commit="b" * 40,
        environment_fingerprint_sha256="c" * 64,
        command=("offline-public-evaluator", "--frozen"),
        seed=17,
    )

    assert len(report.rows) == 4
    assert report.success_count == 2
    assert report.failure_count == 2
    assert report.primary_success_count == 1
    assert report.primary_success_rate_all_cases == pytest.approx(0.25)
    assert report.rows[0].rmsd_angstrom == pytest.approx(0.0, abs=1.0e-12)
    assert report.rows[0].bounded_pose_valid is True
    assert report.rows[0].primary_pose_success is True
    assert report.rows[1].bounded_pose_valid is False
    assert report.rows[1].primary_pose_success is False
    assert report.rows[2].error_message == "public benchmark case evaluation failed"
    assert report.rows[3].error_message == "public benchmark case evaluation failed"
    assert report.legacy_materialization_direction_present is False
    document = report.to_dict()
    assert document["network_fetch_performed"] is False
    assert document["ligand_only_alignment_performed"] is False
    assert document["scientifically_validated"] is False
    assert document["benchmark_validated"] is False
    assert document["product_qualified"] is False
    assert document["customer_execution_enabled"] is False
    assert document["claim_safe"] is False
    assert len(document["report_sha256"]) == 64


def test_offline_evaluator_is_deterministic_for_same_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(monkeypatch)
    inputs = {
        row.case_id: _evaluation_input(row.materialization)
        for row in manifest.rows
        if row.materialization is not None
    }
    first = run_offline_public_benchmark_evaluation(
        manifest,
        inputs,
        engine_commit="d" * 40,
        environment_fingerprint_sha256="e" * 64,
        command=("offline-public-evaluator",),
        seed=19,
    )
    second = run_offline_public_benchmark_evaluation(
        manifest,
        inputs,
        engine_commit="d" * 40,
        environment_fingerprint_sha256="e" * 64,
        command=("offline-public-evaluator",),
        seed=19,
    )
    assert first.to_dict() == second.to_dict()


def test_evaluation_input_rejects_candidate_atom_order_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(monkeypatch)
    materialization = manifest.rows[0].materialization
    assert materialization is not None
    reference = parse_sdf_v2000(
        _reference_record().decode("ascii"),
        source_id=(
            f"{materialization.case_id}:reference:"
            f"{materialization.selected_reference_record_index}"
        ),
    )
    seed = parse_sdf_v2000(
        _seed_record().decode("ascii"),
        source_id=f"{materialization.case_id}:ligand-identity-seed",
    )
    with pytest.raises(PublicBenchmarkEvaluationError, match="topology/order"):
        PublicBenchmarkEvaluationCaseInput(
            case_id=materialization.case_id,
            materialization=materialization,
            receptor_artifact_sha256=materialization.receptor_sha256,
            reference_artifact_sha256=materialization.reference_ligands_sha256,
            ligand_identity_seed_artifact_sha256=(
                materialization.ligand_identity_seed_sha256
            ),
            candidate_artifact_sha256="f" * 64,
            receptor_system_sha256="a" * 64,
            reference_system=reference,
            ligand_identity_seed_system=seed,
            candidate_system=reference,
            receptor_coordinates=torch.tensor(
                [[100.0, 100.0, 100.0]], dtype=torch.float64
            ),
            pocket_center=torch.tensor([1.0, 0.1, 0.0], dtype=torch.float64),
            pocket_radius_angstrom=10.0,
            excluded_nonbonded_pairs=((0, 1), (1, 2)),
        )
