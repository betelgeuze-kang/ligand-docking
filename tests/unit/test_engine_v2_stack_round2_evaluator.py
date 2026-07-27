from __future__ import annotations

# Torch is optional for collection, so imports depending on it intentionally follow
# the importorskip guard below.
# ruff: noqa: E402

import hashlib

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import STACK_ROUND2_EVALUATOR_SHA256
from betelgeuze_engine_v2.benchmark import (
    AuthenticatedPublicBenchmarkCaseInput,
    FrozenPublicBenchmarkProtocol,
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
    materialize_frozen_public_benchmark_inputs,
    run_offline_public_benchmark_evaluation,
    run_prepared_offline_public_benchmark_evaluation,
)
from betelgeuze_engine_v2.benchmark import public_evaluator as evaluator_module
from betelgeuze_engine_v2.benchmark import public_materializer as materializer_module
from betelgeuze_engine_v2.stack_round2_evaluator import (
    AUTHENTICATED_INPUT_BINDING_MODE,
    PREPARED_INPUT_BINDING_MODE,
    PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID,
    PUBLIC_BENCHMARK_EVALUATION_SCOPE,
    PublicBenchmarkEvaluationInternalError,
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
        "round2 evaluator fixture",
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


def _seed_record() -> bytes:
    return _sdf_record(
        "symmetric-seed",
        (
            ("C", -1.0, 0.0, 0.0),
            ("N", 0.0, 0.0, 0.0),
            ("C", 1.0, 0.0, 0.0),
        ),
        ((1, 2, 1), (2, 3, 1)),
    )


def _reference_record() -> bytes:
    return _sdf_record(
        "symmetric-reference",
        (
            ("C", 1.0, 0.0, 0.0),
            ("N", 0.0, 0.0, 0.0),
            ("C", -1.0, 0.0, 0.0),
        ),
        ((1, 2, 1), (2, 3, 1)),
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
        "HEADER    ROUND2 RECEPTOR\n"
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
        case_id=f"round2-{pdb_id}",
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
        for pdb_id in ("3aaa", "3aab", "3aac", "3aad")
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
    manifest = materialize_frozen_public_benchmark_inputs(
        supplied,
        protocol=protocol,
    )
    return manifest, supplied


def _authenticated_inputs(manifest, supplied):
    rows = {}
    for row in manifest.rows:
        materialization = row.materialization
        assert materialization is not None
        payloads = supplied[row.case_id]
        rows[row.case_id] = AuthenticatedPublicBenchmarkCaseInput(
            case_id=row.case_id,
            materialization=materialization,
            receptor_bytes=payloads["receptor"],
            reference_ligands_bytes=payloads["reference_ligands"],
            ligand_identity_seed_bytes=payloads["ligand_identity_seed"],
            candidate_bytes=_seed_record(),
        )
    return rows


def test_round2_authenticated_report_retains_authoritative_input_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert len(STACK_ROUND2_EVALUATOR_SHA256) == 64
    manifest, supplied = _manifest(monkeypatch)
    inputs = _authenticated_inputs(manifest, supplied)
    report = run_offline_public_benchmark_evaluation(
        manifest,
        inputs,
        engine_commit="a" * 40,
        environment_fingerprint_sha256="b" * 64,
        command=("round2-authenticated-evaluator",),
        seed=31,
        execution_receipt_sha256="c" * 64,
    )
    document = report.to_dict()
    assert document["schema_id"] == PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID
    assert document["input_binding_mode"] == AUTHENTICATED_INPUT_BINDING_MODE
    assert document["authoritative_input_binding"] is True
    assert document["execution_identity_authoritative"] is True
    assert document["execution_receipt_sha256"] == "c" * 64
    assert document["evaluation_scope"] == PUBLIC_BENCHMARK_EVALUATION_SCOPE
    assert document["evaluator_integrity_complete"] is True
    assert document["internal_error_count"] == 0
    assert document["authenticated_case_input_sha256s"] == {
        case_id: row.input_sha256 for case_id, row in sorted(inputs.items())
    }
    assert len(document["derivation_policy_sha256"]) == 64
    assert report.success_count == 4
    for row in report.rows:
        assert row.pose_validity is not None
        assert "selected_symmetry_mapping_index" in row.pose_validity
        assert "selected_full_reference_to_seed_mapping" in row.pose_validity
        assert "selected_heavy_reference_to_candidate_mapping" in row.pose_validity
        assert len(row.pose_validity["validity_policy_sha256"]) == 64


def test_prepared_report_is_explicitly_non_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, supplied = _manifest(monkeypatch)
    authenticated = _authenticated_inputs(manifest, supplied)
    prepared = {
        case_id: row.prepared_input for case_id, row in authenticated.items()
    }
    report = run_prepared_offline_public_benchmark_evaluation(
        manifest,
        prepared,
        engine_commit="d" * 40,
        environment_fingerprint_sha256="e" * 64,
        command=("round2-prepared-evaluator",),
        seed=37,
    )
    document = report.to_dict()
    assert document["input_binding_mode"] == PREPARED_INPUT_BINDING_MODE
    assert document["authoritative_input_binding"] is False
    assert document["execution_identity_authoritative"] is False
    assert document["authenticated_case_input_sha256s"] == {}
    assert document["derivation_policy_sha256"] == ""


def test_unexpected_internal_defect_invalidates_the_whole_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, supplied = _manifest(monkeypatch)
    inputs = _authenticated_inputs(manifest, supplied)

    def broken_graph_match(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("programmer defect")

    monkeypatch.setattr(
        evaluator_module,
        "exact_graph_isomorphisms",
        broken_graph_match,
    )
    with pytest.raises(
        PublicBenchmarkEvaluationInternalError,
        match="internal invariant",
    ):
        run_offline_public_benchmark_evaluation(
            manifest,
            inputs,
            engine_commit="f" * 40,
            environment_fingerprint_sha256="1" * 64,
            command=("round2-broken-evaluator",),
            seed=41,
        )
