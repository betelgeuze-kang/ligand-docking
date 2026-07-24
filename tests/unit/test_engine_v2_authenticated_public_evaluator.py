from __future__ import annotations

import hashlib

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    AuthenticatedPublicBenchmarkCaseInput,
    AuthenticatedPublicBenchmarkInputError,
    FrozenPublicBenchmarkProtocol,
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
    authenticated_public_benchmark_derivation_policy_document,
    materialize_frozen_public_benchmark_inputs,
    run_offline_public_benchmark_evaluation,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_materializer as materializer_module,
)


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
        "authenticated evaluator fixture",
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


def _pdb_atom(
    serial: int,
    name: str,
    x: float,
    y: float,
    z: float,
    element: str,
) -> str:
    return (
        f"ATOM  {serial:5d} {name:<4s} ALA A{1:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{20.0:6.2f}          "
        f"{element:>2s}  "
    )


def _receptor_bytes() -> bytes:
    return (
        "HEADER    AUTHENTICATED RECEPTOR\n"
        + _pdb_atom(1, "CA", 100.0, 100.0, 100.0, "C")
        + "\nEND\n"
    ).encode("ascii")


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


def _case(pdb_id: str):
    receptor = _receptor_bytes()
    reference = _reference_record()
    seed = _seed_record()
    case = PublicBenchmarkCaseDefinition(
        case_id=f"authenticated-{pdb_id}",
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


def _manifest(monkeypatch: pytest.MonkeyPatch):
    case_rows = [
        _case(pdb_id)
        for pdb_id in ("2aaa", "2aab", "2aac", "2aad")
    ]
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
    return materialize_frozen_public_benchmark_inputs(
        supplied,
        protocol=protocol,
    ), supplied


def _authenticated_input(materialization, payloads, *, shift: float = 0.0):
    return AuthenticatedPublicBenchmarkCaseInput(
        case_id=materialization.case_id,
        materialization=materialization,
        receptor_bytes=payloads["receptor"],
        reference_ligands_bytes=payloads["reference_ligands"],
        ligand_identity_seed_bytes=payloads["ligand_identity_seed"],
        candidate_bytes=_seed_record(shift=shift),
    )


def test_authenticated_boundary_derives_every_validity_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, supplied = _manifest(monkeypatch)
    first = manifest.rows[0].materialization
    second = manifest.rows[1].materialization
    assert first is not None and second is not None
    inputs = {
        first.case_id: _authenticated_input(first, supplied[first.case_id]),
        second.case_id: _authenticated_input(
            second,
            supplied[second.case_id],
            shift=50.0,
        ),
    }
    report = run_offline_public_benchmark_evaluation(
        manifest,
        inputs,
        engine_commit="a" * 40,
        environment_fingerprint_sha256="b" * 64,
        command=("authenticated-offline-evaluator",),
        seed=21,
    )
    assert len(report.rows) == 4
    assert report.success_count == 2
    assert report.failure_count == 2
    assert report.primary_success_count == 1
    assert report.rows[0].primary_pose_success is True
    assert report.rows[1].primary_pose_success is False
    assert report.rows[1].bounded_pose_valid is False
    assert report.rows[2].status == "failure"
    assert report.rows[3].status == "failure"
    document = report.to_dict()
    assert document["schema_id"].endswith("/2.0.0")
    assert document["authenticated_input_count"] == 2
    assert document["all_supplied_case_inputs_authenticated"] is True
    assert len(document["authenticated_input_manifest_sha256"]) == 64
    assert len(document["evaluator_source_sha256"]) == 64
    assert len(document["authentication_boundary_source_sha256"]) == 64
    assert len(document["evaluation_policy_sha256"]) == 64
    assert report.rows[0].authenticated_input_sha256 == (
        inputs[first.case_id].input_sha256
    )
    assert report.rows[0].mapping_applied_to_rmsd_and_validity is True
    policy = authenticated_public_benchmark_derivation_policy_document()
    assert policy["ligand_identity_seed_coordinates_used"] is False
    assert policy["caller_supplied_receptor_coordinates_allowed"] is False
    assert policy["caller_supplied_pocket_allowed"] is False
    assert policy["caller_supplied_exclusions_allowed"] is False
    assert policy["caller_supplied_chirality_allowed"] is False
    assert policy["claim_safe"] is False


def test_authenticated_boundary_recomputes_raw_artifact_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, supplied = _manifest(monkeypatch)
    materialization = manifest.rows[0].materialization
    assert materialization is not None
    tampered = {
        **supplied[materialization.case_id],
        "receptor": supplied[materialization.case_id]["receptor"]
        + b"REMARK tampered\n",
    }
    with pytest.raises(
        AuthenticatedPublicBenchmarkInputError,
        match="receptor artifact SHA-256",
    ):
        _authenticated_input(materialization, tampered)


def test_candidate_identity_is_computed_from_candidate_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, supplied = _manifest(monkeypatch)
    materialization = manifest.rows[0].materialization
    assert materialization is not None
    row = _authenticated_input(materialization, supplied[materialization.case_id])
    expected = hashlib.sha256(_seed_record()).hexdigest()
    assert row.to_dict()["candidate_sha256"] == expected
    assert row.prepared_input.candidate_artifact_sha256 == expected
    assert row.to_dict()["caller_controlled_validity_inputs"] is False
