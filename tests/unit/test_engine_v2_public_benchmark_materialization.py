from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_materialization import (  # noqa: E402
    PUBLIC_REFERENCE_MATERIALIZATION_SCIENTIFIC_BLOCKERS,
    PublicBenchmarkCaseMaterialization,
    PublicReferenceMaterializationError,
    PublicReferenceMaterializationLimits,
    materialize_public_benchmark_case,
    minimum_public_reference_rmsd,
)
from betelgeuze_engine_v2.benchmark.public_protocol import (  # noqa: E402
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
)
from betelgeuze_engine_v2.io import sdf_v2000_string  # noqa: E402
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    atomic_number_for_element,
)


def _system(
    system_id: str,
    elements: tuple[str, ...],
    coordinates: tuple[tuple[float, float, float], ...],
    bonds: tuple[tuple[int, int, str], ...],
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_number_for_element(element),
            residue_index=0,
        )
        for index, element in enumerate(elements)
    )
    bond_rows = tuple(
        Bond(
            index=index,
            atom_i=min(first, second),
            atom_j=max(first, second),
            order=1.0,
            stereo=stereo,
        )
        for index, (first, second, stereo) in enumerate(bonds)
    )
    return AllAtomSystem(
        system_id=system_id,
        atoms=atoms,
        bonds=bond_rows,
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
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _sdf(system: AllAtomSystem) -> bytes:
    text, _receipt = sdf_v2000_string(system, title=system.system_id)
    return text.encode("utf-8")


def _artifact(
    role: str,
    relative_name: str,
    source: bytes,
) -> PublicBenchmarkArtifact:
    relative_path = f"posebusters/datasets/pdb/1abc/1abc_{relative_name}"
    return PublicBenchmarkArtifact(
        role=role,
        relative_path=relative_path,
        immutable_url=(
            "https://raw.githubusercontent.com/maabuu/posebusters/"
            f"{POSEBUSTERS_SOURCE_COMMIT_SHA}/{relative_path}"
        ),
        sha256=hashlib.sha256(source).hexdigest(),
        size_bytes=len(source),
        media_type="chemical/x-mdl-sdfile",
    )


def _case(seed: bytes, references: bytes) -> PublicBenchmarkCaseDefinition:
    receptor = b"synthetic receptor identity only\n"
    return PublicBenchmarkCaseDefinition(
        case_id="posebusters-packaged-1abc",
        pdb_id="1abc",
        receptor=_artifact("receptor", "protein_one_lig_removed.pdb", receptor),
        reference_ligands=_artifact("reference_ligands", "ligands.sdf", references),
        ligand_identity_seed=_artifact("ligand_identity_seed", "ligand.sdf", seed),
    )


def _fixture(*, stereo: str = "none"):
    seed_system = _system(
        "seed",
        ("C", "O", "C"),
        ((100.0, 100.0, 100.0), (101.0, 100.0, 100.0), (102.0, 100.0, 100.0)),
        ((0, 1, stereo), (1, 2, "none")),
    )
    far_reference = _system(
        "far-reference",
        ("C", "O", "C"),
        ((20.0, 0.0, 0.0), (21.0, 0.0, 0.0), (22.0, 0.0, 0.0)),
        ((0, 1, stereo), (1, 2, "none")),
    )
    reordered_reference = _system(
        "reordered-reference",
        ("O", "C", "C"),
        ((3.0, 0.0, 0.0), (4.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((0, 1, stereo), (0, 2, "none")),
    )
    mismatch = _system(
        "graph-mismatch",
        ("N", "O", "N"),
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((0, 1, "none"), (1, 2, "none")),
    )
    seed = _sdf(seed_system)
    references = _sdf(far_reference) + _sdf(reordered_reference) + _sdf(mismatch)
    return seed, references, _case(seed, references)


def test_all_graph_matched_records_and_symmetry_are_materialized_without_seed_coordinates() -> None:
    seed, references, case = _fixture()
    result = materialize_public_benchmark_case(
        case,
        seed,
        references,
        protocol_sha256="a" * 64,
    )

    assert result.ready_for_rmsd
    assert [row.status for row in result.record_rows] == [
        "selected_graph_match",
        "selected_graph_match",
        "rejected_graph_mismatch",
    ]
    assert len(result.reference_poses) == 2
    assert result.symmetry_permutations_seed_heavy_order == (
        (0, 1, 2),
        (2, 1, 0),
    )
    assert result.scientific_blockers == (
        PUBLIC_REFERENCE_MATERIALIZATION_SCIENTIFIC_BLOCKERS
    )
    payload = result.to_dict()
    assert payload["ligand_identity_seed_coordinates_used"] is False
    assert payload["reference_selection_policy"].startswith("all_reference_records")
    assert "100.0" not in result.to_json_bytes().decode("ascii")
    assert result.claim_safe is False


def test_direct_receptor_frame_rmsd_uses_record_and_symmetry_minimum_without_alignment() -> None:
    seed, references, case = _fixture()
    result = materialize_public_benchmark_case(
        case,
        seed,
        references,
        protocol_sha256="b" * 64,
    )
    candidate = torch.tensor(
        ((2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (4.0, 0.0, 0.0)),
        dtype=torch.float64,
    )

    rmsd = minimum_public_reference_rmsd(result, candidate)

    assert rmsd.rmsd_angstrom == pytest.approx(0.0, abs=1.0e-15)
    assert rmsd.reference_record_index == 1
    assert rmsd.symmetry_permutation_index == 1
    assert len(rmsd.candidate_coordinates_seed_order_sha256) == 64
    translated = minimum_public_reference_rmsd(result, candidate + 8.0)
    assert translated.rmsd_angstrom > 5.0
    assert translated.candidate_coordinates_seed_order_sha256 != (
        rmsd.candidate_coordinates_seed_order_sha256
    )
    assert translated.to_dict()["alignment_policy"] == (
        "direct_receptor_frame_no_ligand_alignment"
    )


def test_directional_v2000_stereo_prevents_false_graph_automorphism() -> None:
    seed, references, case = _fixture(stereo="up")
    result = materialize_public_benchmark_case(
        case,
        seed,
        references,
        protocol_sha256="c" * 64,
    )

    assert result.symmetry_permutations_seed_heavy_order == ((0, 1, 2),)
    assert [row.status for row in result.record_rows] == [
        "selected_graph_match",
        "rejected_graph_mismatch",
        "rejected_graph_mismatch",
    ]


def test_receipt_round_trip_is_canonical_and_tamper_evident() -> None:
    seed, references, case = _fixture()
    result = materialize_public_benchmark_case(
        case,
        seed,
        references,
        protocol_sha256="d" * 64,
    )
    raw = result.to_json_bytes()
    restored = PublicBenchmarkCaseMaterialization.from_json_bytes(raw)

    assert restored.to_json_bytes() == raw
    assert restored.fingerprint_sha256 == result.fingerprint_sha256
    tampered = raw.replace(b'"ready_for_rmsd":true', b'"ready_for_rmsd":false')
    with pytest.raises(
        PublicReferenceMaterializationError,
        match="not canonical or is inconsistent",
    ):
        PublicBenchmarkCaseMaterialization.from_json_bytes(tampered)
    cross_wired_pose = replace(
        result.reference_poses[0],
        record_sha256="f" * 64,
    )
    with pytest.raises(PublicReferenceMaterializationError, match="cross-wired"):
        replace(
            result,
            reference_poses=(cross_wired_pose, *result.reference_poses[1:]),
        )
    with pytest.raises(PublicReferenceMaterializationError, match="record order"):
        replace(result, reference_poses=tuple(reversed(result.reference_poses)))


def test_parse_failures_are_retained_and_block_rmsd() -> None:
    seed, references, _case_definition = _fixture()
    malformed = (
        b"malformed\nunit\nrecord\n  1  0  0  0  0  0            999 V2000\n"
        b"not-an-atom-line\nM  END\n$$$$\n"
    )
    missing_end = (
        b"missing-end\nunit\nrecord\n  1  0  0  0  0  0            999 V2000\n"
        b"    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        b"$$$$\n"
    )
    references_with_failure = references + malformed + missing_end
    case = _case(seed, references_with_failure)
    result = materialize_public_benchmark_case(
        case,
        seed,
        references_with_failure,
        protocol_sha256="e" * 64,
    )

    assert result.failed_record_indices == (3, 4)
    assert result.record_rows[-1].status == "failure_parse"
    assert result.record_rows[-1].error_code == "SDFParseError"
    assert result.ready_for_rmsd is False
    with pytest.raises(PublicReferenceMaterializationError, match="not ready"):
        minimum_public_reference_rmsd(
            result,
            torch.zeros((3, 3), dtype=torch.float64),
        )


def test_artifact_identity_and_mapping_capacity_fail_closed() -> None:
    seed, references, case = _fixture()
    with pytest.raises(PublicReferenceMaterializationError, match="identity verification"):
        materialize_public_benchmark_case(
            case,
            seed + b"tamper",
            references,
            protocol_sha256="f" * 64,
        )

    with pytest.raises(PublicReferenceMaterializationError, match="mapping capacity"):
        materialize_public_benchmark_case(
            case,
            seed,
            references,
            protocol_sha256="f" * 64,
            limits=replace(
                PublicReferenceMaterializationLimits(),
                max_symmetry_permutations=1,
            ),
        )


def test_public_materialization_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import benchmark
    from betelgeuze_engine_v2.benchmark.public_materialization import (
        __all__ as materialization_exports,
    )

    assert set(materialization_exports) <= set(benchmark.__all__)
