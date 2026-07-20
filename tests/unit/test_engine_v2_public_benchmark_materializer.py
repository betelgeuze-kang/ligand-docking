from __future__ import annotations

import hashlib

import pytest

from betelgeuze_engine_v2.benchmark import (
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
    PublicBenchmarkMaterializerError,
    exact_graph_isomorphisms,
    materialize_frozen_public_benchmark_inputs,
    materialize_public_benchmark_case,
    split_sdf_v2000_records,
)
from betelgeuze_engine_v2.benchmark import public_materializer as materializer
from betelgeuze_engine_v2.benchmark.public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    FrozenPublicBenchmarkProtocol,
)
from betelgeuze_engine_v2.io import parse_sdf_v2000


def _atom_line(
    element: str,
    x: float,
    y: float,
    z: float,
) -> str:
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
        "public materializer fixture",
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


def _seed_record(*, coordinate_shift: float = 0.0) -> bytes:
    return _sdf_record(
        "symmetric-seed",
        (
            ("C", 0.0 + coordinate_shift, 0.0, 0.0),
            ("O", 1.2 + coordinate_shift, 0.0, 0.0),
            ("O", -1.2 + coordinate_shift, 0.0, 0.0),
        ),
        ((1, 2, 1), (1, 3, 1)),
    )


def _matching_reference_record() -> bytes:
    return _sdf_record(
        "reordered-reference",
        (
            ("O", 3.0, 0.0, 0.0),
            ("C", 2.0, 0.0, 0.0),
            ("O", 1.0, 0.0, 0.0),
        ),
        ((2, 1, 1), (2, 3, 1)),
    )


def _nonmatching_record() -> bytes:
    return _sdf_record(
        "nonmatching-reference",
        (
            ("C", 0.0, 0.0, 0.0),
            ("N", 1.0, 0.0, 0.0),
            ("O", -1.0, 0.0, 0.0),
        ),
        ((1, 2, 1), (1, 3, 1)),
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
    *,
    references: bytes | None = None,
    seed: bytes | None = None,
) -> tuple[PublicBenchmarkCaseDefinition, dict[str, bytes]]:
    receptor = b"HEADER    SYNTHETIC RECEPTOR\nEND\n"
    reference_bytes = (
        _nonmatching_record() + _matching_reference_record()
        if references is None
        else references
    )
    seed_bytes = _seed_record() if seed is None else seed
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
            payload=reference_bytes,
            media_type="chemical/x-mdl-sdfile",
        ),
        ligand_identity_seed=_artifact(
            pdb_id,
            role="ligand_identity_seed",
            filename=f"{pdb_id}_ligand.sdf",
            payload=seed_bytes,
            media_type="chemical/x-mdl-sdfile",
        ),
    )
    return case, {
        "receptor": receptor,
        "reference_ligands": reference_bytes,
        "ligand_identity_seed": seed_bytes,
    }


def test_sdf_multi_record_split_is_byte_exact_and_bounded() -> None:
    first = _nonmatching_record()
    second = _matching_reference_record()
    source = first + second

    assert split_sdf_v2000_records(source) == (first, second)
    with pytest.raises(PublicBenchmarkMaterializerError, match="record bound"):
        split_sdf_v2000_records(source, max_records=1)
    with pytest.raises(PublicBenchmarkMaterializerError, match="unterminated"):
        split_sdf_v2000_records(source[:-5])


def test_exact_graph_isomorphism_ignores_coordinates_and_retains_symmetry() -> None:
    seed = parse_sdf_v2000(_seed_record().decode("ascii"))
    shifted_seed = parse_sdf_v2000(
        _seed_record(coordinate_shift=100.0).decode("ascii")
    )
    reference = parse_sdf_v2000(_matching_reference_record().decode("ascii"))

    assert exact_graph_isomorphisms(seed, shifted_seed)
    mappings = exact_graph_isomorphisms(seed, reference)
    assert len(mappings) == 2
    assert all(sorted(mapping) == [0, 1, 2] for mapping in mappings)


def test_case_materialization_selects_exactly_one_reference_and_emits_symmetry() -> None:
    case, payloads = _case("1aaa")

    result = materialize_public_benchmark_case(
        case,
        receptor_bytes=payloads["receptor"],
        reference_ligands_bytes=payloads["reference_ligands"],
        ligand_identity_seed_bytes=payloads["ligand_identity_seed"],
    )
    document = result.to_dict()

    assert result.source_commit_sha == POSEBUSTERS_SOURCE_COMMIT_SHA
    assert result.selected_reference_record_index == 1
    assert result.heavy_atom_count == 3
    assert len(result.symmetry_permutations) == 2
    assert document["ligand_identity_seed_coordinates_used"] is False
    assert document["receptor_coordinates_interpreted"] is False
    assert document["docking_executed"] is False
    assert document["metric_values_collected"] is False
    assert document["claim_safe"] is False
    assert len(result.materialization_sha256) == 64


def test_case_materialization_fails_on_zero_or_multiple_reference_matches() -> None:
    no_match_case, no_match_payloads = _case(
        "1aab",
        references=_nonmatching_record(),
    )
    with pytest.raises(PublicBenchmarkMaterializerError, match="exactly one"):
        materialize_public_benchmark_case(
            no_match_case,
            receptor_bytes=no_match_payloads["receptor"],
            reference_ligands_bytes=no_match_payloads["reference_ligands"],
            ligand_identity_seed_bytes=no_match_payloads["ligand_identity_seed"],
        )

    multiple_case, multiple_payloads = _case(
        "1aac",
        references=_matching_reference_record() + _matching_reference_record(),
    )
    with pytest.raises(PublicBenchmarkMaterializerError, match="exactly one"):
        materialize_public_benchmark_case(
            multiple_case,
            receptor_bytes=multiple_payloads["receptor"],
            reference_ligands_bytes=multiple_payloads["reference_ligands"],
            ligand_identity_seed_bytes=multiple_payloads["ligand_identity_seed"],
        )


def test_four_case_manifest_retains_missing_and_failed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_case(pdb_id) for pdb_id in ("1aad", "1aae", "1aaf", "1aag")]
    protocol = FrozenPublicBenchmarkProtocol(
        cases=tuple(case for case, _payloads in rows),
        scorer_identities=(),
    )
    monkeypatch.setattr(
        materializer,
        "FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256",
        protocol.protocol_sha256,
    )
    supplied = {
        case.case_id: payloads
        for case, payloads in rows[:3]
    }
    supplied[rows[1][0].case_id] = {
        **supplied[rows[1][0].case_id],
        "receptor": b"tampered receptor\n",
    }

    manifest = materialize_frozen_public_benchmark_inputs(
        supplied,
        protocol=protocol,
    )
    document = manifest.to_dict()

    assert len(manifest.rows) == 4
    assert manifest.success_count == 2
    assert manifest.failure_count == 2
    assert [row.ordinal for row in manifest.rows] == [0, 1, 2, 3]
    assert all(
        row.case_id == protocol.cases[row.ordinal].case_id
        for row in manifest.rows
    )
    assert document["all_cases_observed"] is True
    assert document["failure_rows_retained"] is True
    assert document["network_fetch_performed"] is False
    assert document["raw_artifact_bytes_embedded"] is False
    assert document["benchmark_execution_performed"] is False
    assert document["metric_values_collected"] is False
    assert document["claim_safe"] is False
    failures = [row for row in manifest.rows if not row.succeeded]
    assert all(
        row.error_message == "public benchmark case materialization failed"
        for row in failures
    )
    assert all(len(row.private_error_sha256) == 64 for row in failures)
    assert all(row.private_error_byte_length > 0 for row in failures)
