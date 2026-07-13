from __future__ import annotations

from dataclasses import replace
import hashlib
from itertools import combinations
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID,
    SDF_V2000_ROUND_TRIP_REPORT_SCHEMA_ID,
    SDF_V2000_WRITER_VERSION,
    SDF_V2000_WRITE_RECEIPT_SCHEMA_ID,
    SdfV2000IngestResult,
    SdfV2000RoundTripReport,
    SdfV2000RoundTripResult,
    SdfV2000WriteError,
    SdfV2000WriteReceipt,
    SdfV2000WriteResult,
    UnitCell,
    canonical_all_atom_snapshot_digest,
    canonical_topology_sha256,
    parse_sdf_v2000,
    round_trip_sdf_v2000_source,
    sdf_v2000_representable_state_sha256,
    serialize_sdf_v2000,
    write_sdf_v2000,
)
from betelgeuze_engine_v2.molecular import sdf_v2000_writer as writer_module


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ETHANOL = FIXTURES / "tier_beta" / "ethanol.sdf"
V2_1_CORPUS = FIXTURES / "v2_1_ingest_corpus"
V2_2_ALKANES = FIXTURES / "v2_2_linear_alkane"


def _atom_line(
    element: str = "C",
    *,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    charge_code: int = 0,
    atom_map: int = 0,
) -> str:
    return (
        f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3}"
        f"{0:2d}{charge_code:3d}{0:3d}{0:3d}"
        f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{atom_map:3d}{0:3d}{0:3d}"
    )


def _bond_line(atom_i: int, atom_j: int, bond_type: int = 1) -> str:
    return f"{atom_i:3d}{atom_j:3d}{bond_type:3d}{0:3d}"


def _record(
    *,
    atoms: tuple[str, ...],
    bonds: tuple[str, ...] = (),
    properties: tuple[str, ...] = (),
    title: str = "fixture",
    program: str = "codex",
    comment: str = "writer contract",
    delimiter: bool = True,
) -> bytes:
    lines = [
        title,
        program,
        comment,
        f"{len(atoms):3d}{len(bonds):3d}  0  0  0  0  0  0  0  0999 V2000",
        *atoms,
        *bonds,
        *properties,
        "M  END",
    ]
    if delimiter:
        lines.append("$$$$")
    return ("\n".join(lines) + "\n").encode("ascii")


def _property_records(
    name: str,
    pairs: tuple[tuple[int, int], ...],
) -> tuple[str, ...]:
    return tuple(
        f"M  {name}{len(pairs[start : start + 8]):3d}"
        + "".join(
            f"{atom_index:4d}{value:4d}"
            for atom_index, value in pairs[start : start + 8]
        )
        for start in range(0, len(pairs), 8)
    )


def _assert_error(system, code: str) -> None:
    with pytest.raises(SdfV2000WriteError) as exc_info:
        write_sdf_v2000(system)
    assert exc_info.value.code == code


def test_writer_public_contract_and_ethanol_golden_receipt() -> None:
    source = ETHANOL.read_bytes()
    result = round_trip_sdf_v2000_source(
        source,
        source_id="tier-beta-ethanol",
    )

    assert SDF_V2000_WRITER_VERSION == "1.0.0"
    assert SDF_V2000_REPRESENTABLE_STATE_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_representable_state/1.0.0"
    )
    assert SDF_V2000_WRITE_RECEIPT_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_write_receipt/1.0.0"
    )
    assert SDF_V2000_ROUND_TRIP_REPORT_SCHEMA_ID == (
        "betelgeuze.sdf_v2000_round_trip_report/1.0.0"
    )
    assert result.write_result.payload == source
    assert result.write_result.receipt.output_source_sha256 == (
        "f4835419da95267ad2ef566a121b981011c202c882b071b86d35fc82b683563f"
    )
    assert result.write_result.receipt.output_byte_count == 313
    assert result.write_result.receipt.atom_count == 3
    assert result.write_result.receipt.bond_count == 2
    assert result.write_result.receipt.parent_source_sha256 == hashlib.sha256(
        source
    ).hexdigest()
    assert result.write_result.receipt.input_snapshot_sha256 == (
        canonical_all_atom_snapshot_digest(result.source_ingest.system)
    )
    assert result.write_result.receipt.input_snapshot_sha256 == (
        "6dd278d2c1ef4aaf4adc0237106a1fa590fad8a4301367762feab404767f55ee"
    )
    assert result.write_result.receipt.input_topology_sha256 == (
        "8002a0a206d4ec2db0bb7594e4edda900b43ecaeb9cfc6510949c389b5e3ff5e"
    )
    assert result.write_result.receipt.input_representable_state_sha256 == (
        "08bd6692ed559645fa8e6028950446dfd5cc75c15eb9e93e128f6282e090fc26"
    )
    receipt = result.write_result.receipt.to_dict()
    assert receipt["schema_id"] == SDF_V2000_WRITE_RECEIPT_SCHEMA_ID
    assert receipt["source_authentication_status"] == "not_authenticated"
    assert receipt["preparation_ready"] is False
    assert receipt["parameterability_assessed"] is False
    assert receipt["simulation_ready"] is False
    assert receipt["claim_safe"] is False
    assert receipt["receipt_sha256"] == result.write_result.receipt.receipt_sha256
    assert receipt["receipt_sha256"] == (
        "7bf0e7ee2368d700a57f82d4f2fb227a43d76155d3f43e8181d96e242f066855"
    )

    report = result.report.to_dict()
    assert report["schema_id"] == SDF_V2000_ROUND_TRIP_REPORT_SCHEMA_ID
    assert report["declared_projection_sha256_equal"] is True
    assert report["canonical_topology_sha256_equal"] is True
    assert report["coordinate_binary64_projection_equal"] is True
    assert report["declared_parser_marker_projection_equal"] is True
    assert report["emitted_source_sha256_and_bytes_stable"] is True
    assert report["full_canonical_snapshot_equality_claimed"] is False
    assert report["dynamic_source_provenance_equality_claimed"] is False
    assert report["claim_safe"] is False
    assert report["report_sha256"] == result.report.report_sha256
    assert report["report_sha256"] == (
        "4d458d0a202c1da8578ba2db8fd129aad1c0dfc4261c395862e23d7c9f59fbfa"
    )


@pytest.mark.parametrize(
    "path",
    [
        ETHANOL,
        V2_1_CORPUS / "methane_explicit_h.sdf",
        V2_1_CORPUS / "methane_c13_explicit_h.sdf",
        V2_2_ALKANES / "ethane_explicit_h.sdf",
        V2_2_ALKANES / "propane_explicit_h.sdf",
        V2_2_ALKANES / "n_butane_explicit_h.sdf",
    ],
)
def test_supported_real_sources_round_trip_without_declared_projection_loss(
    path: Path,
) -> None:
    source = path.read_bytes()
    result = round_trip_sdf_v2000_source(source, source_id=path.stem)
    before = result.source_ingest.system
    after = result.reparsed_ingest.system

    assert result.write_result.payload == source
    assert canonical_topology_sha256(before) == canonical_topology_sha256(after)
    assert sdf_v2000_representable_state_sha256(before) == (
        sdf_v2000_representable_state_sha256(after)
    )
    assert torch.equal(
        before.coordinates.view(torch.int64),
        after.coordinates.view(torch.int64),
    )
    assert serialize_sdf_v2000(after) == result.write_result.payload
    assert result.report.input_representable_state_sha256 == (
        result.report.reparsed_representable_state_sha256
    )
    assert result.report.emitted_source_sha256 == (
        result.report.reemitted_source_sha256
    )


def test_charge_isotope_map_aromaticity_and_source_bond_direction_are_preserved() -> None:
    source = _record(
        atoms=(
            _atom_line("C", atom_map=17),
            _atom_line("N", x=1.2),
            _atom_line("C", x=2.4),
        ),
        bonds=(
            _bond_line(2, 1, 1),
            _bond_line(3, 2, 4),
        ),
        properties=(
            "M  CHG  2   1  -1   2   1",
            "M  ISO  1   2  15",
        ),
    )
    result = round_trip_sdf_v2000_source(source, source_id="markers")
    emitted = result.write_result.payload.decode("ascii").splitlines()

    assert emitted[7] == "  2  1  1  0"
    assert emitted[8] == "  3  2  4  0"
    assert emitted[9] == "M  CHG  2   1  -1   2   1"
    assert emitted[10] == "M  ISO  1   2  15"
    before = result.source_ingest.system
    after = result.reparsed_ingest.system
    assert [dict(atom.metadata) for atom in before.atoms] == [
        dict(atom.metadata) for atom in after.atoms
    ]
    assert [dict(bond.metadata) for bond in before.bonds] == [
        dict(bond.metadata) for bond in after.bonds
    ]
    assert before.provenance.operations == after.provenance.operations
    assert before.metadata == after.metadata


def test_atom_block_charge_origin_is_reemitted_without_m_chg() -> None:
    source = _record(atoms=(_atom_line("N", charge_code=3),))
    result = round_trip_sdf_v2000_source(source)
    emitted = result.write_result.payload.decode("ascii")
    atom_line = emitted.splitlines()[4]

    assert atom_line[36:39] == "  3"
    assert "M  CHG" not in emitted
    assert result.reparsed_ingest.system.atoms[0].formal_charge == 1
    assert result.reparsed_ingest.system.atoms[0].metadata[
        "formal_charge_source"
    ] == "sdf_v2000_atom_block"


def test_property_pairs_are_deterministically_chunked_eight_then_one() -> None:
    atoms = tuple(
        _atom_line("C", x=float(index), atom_map=index + 1)
        for index in range(9)
    )
    # Use noncanonical signs, zero padding, whitespace, and one-pair rows. The
    # writer must converge them to the deterministic 8+1 grouping.
    source = _record(
        atoms=atoms,
        properties=tuple(
            f"M  CHG +1 +{index:03d} {(-1 if index % 2 else 1):+05d}"
            for index in range(1, 10)
        )
        + tuple(f"M  ISO +1 +{index:03d} +0013" for index in range(1, 10)),
    )
    result = round_trip_sdf_v2000_source(source)
    lines = result.write_result.payload.decode("ascii").splitlines()
    chg_lines = [line for line in lines if line.startswith("M  CHG")]
    iso_lines = [line for line in lines if line.startswith("M  ISO")]

    assert [line[6:9] for line in chg_lines] == ["  8", "  1"]
    assert [line[6:9] for line in iso_lines] == ["  8", "  1"]
    assert lines.index(chg_lines[-1]) < lines.index(iso_lines[0])
    assert [atom.atom_map for atom in result.reparsed_ingest.system.atoms] == list(
        range(1, 10)
    )
    assert [atom.isotope_mass_number for atom in result.reparsed_ingest.system.atoms] == [
        13
    ] * 9


def test_missing_delimiter_is_canonicalized_and_second_emission_is_stable() -> None:
    source = _record(atoms=(_atom_line(),), title="", delimiter=False)
    result = round_trip_sdf_v2000_source(source)

    assert result.write_result.payload.endswith(b"M  END\n$$$$\n")
    assert result.write_result.payload != source
    assert serialize_sdf_v2000(result.reparsed_ingest.system) == (
        result.write_result.payload
    )
    assert result.report.input_source_sha256 != result.report.emitted_source_sha256
    assert result.report.input_snapshot_sha256 != (
        result.report.reparsed_snapshot_sha256
    )
    assert result.report.input_representable_state_sha256 == (
        result.report.reparsed_representable_state_sha256
    )
    assert result.source_ingest.system.system_id != (
        result.reparsed_ingest.system.system_id
    )
    assert "system_id_and_source_id_are_outside_declared_projection" in (
        result.report.to_dict()["blockers"]
    )
    assert result.report.to_dict()["full_canonical_snapshot_equality_claimed"] is False
    assert result.report.to_dict()[
        "dynamic_source_provenance_equality_claimed"
    ] is False


def test_write_result_is_detached_from_later_coordinate_mutation() -> None:
    parsed = parse_sdf_v2000(ETHANOL.read_bytes())
    first = write_sdf_v2000(parsed.system)
    payload = first.payload
    receipt = first.receipt.to_dict()

    parsed.system.coordinates[0, 0, 0] = -1.0
    assert first.payload == payload
    assert first.receipt.to_dict() == receipt
    assert hashlib.sha256(first.payload).hexdigest() == (
        first.receipt.output_source_sha256
    )


def test_exactly_representable_coordinate_edit_is_bound_as_current_snapshot_not_source_authentication() -> None:
    source = ETHANOL.read_bytes()
    parsed = parse_sdf_v2000(source).system
    coordinates = parsed.coordinates.clone()
    coordinates[0, 0, 0] = -1.0
    edited = replace(parsed, coordinates=coordinates)
    result = write_sdf_v2000(edited)
    reparsed = parse_sdf_v2000(result.payload).system

    assert result.receipt.parent_source_sha256 == hashlib.sha256(source).hexdigest()
    assert result.receipt.input_snapshot_sha256 == canonical_all_atom_snapshot_digest(
        edited
    )
    assert result.receipt.input_snapshot_sha256 != canonical_all_atom_snapshot_digest(
        parsed
    )
    assert result.receipt.to_dict()["source_authentication_status"] == (
        "not_authenticated"
    )
    assert sdf_v2000_representable_state_sha256(edited) == (
        sdf_v2000_representable_state_sha256(reparsed)
    )


def test_safe_header_edit_is_bound_in_current_snapshot_and_projection() -> None:
    parsed = parse_sdf_v2000(ETHANOL.read_bytes()).system
    header = dict(parsed.metadata["sdf_v2000_header"])
    header["title"] = "edited-safe-title"
    edited = replace(parsed, metadata={"sdf_v2000_header": header})
    result = write_sdf_v2000(edited)
    reparsed = parse_sdf_v2000(result.payload).system

    assert result.payload.splitlines()[0] == b"edited-safe-title"
    assert result.receipt.input_snapshot_sha256 == canonical_all_atom_snapshot_digest(
        edited
    )
    assert result.receipt.input_snapshot_sha256 != canonical_all_atom_snapshot_digest(
        parsed
    )
    assert sdf_v2000_representable_state_sha256(edited) == (
        sdf_v2000_representable_state_sha256(reparsed)
    )


def test_writer_accepts_the_v2000_atom_limit_without_exceeding_parser_limits() -> None:
    atoms = tuple(_atom_line(atom_map=index) for index in range(1, 1_000))
    bonds = tuple(_bond_line(index, index + 1) for index in range(1, 999)) + (
        _bond_line(1, 999),
    )
    pairs = tuple((index, 1) for index in range(1, 1_000))
    isotopes = tuple((index, 13) for index in range(1, 1_000))
    source = _record(
        atoms=atoms,
        bonds=bonds,
        properties=_property_records("CHG", pairs)
        + _property_records("ISO", isotopes),
    )
    result = round_trip_sdf_v2000_source(source)

    assert result.write_result.receipt.atom_count == 999
    assert result.write_result.receipt.bond_count == 999
    assert result.reparsed_ingest.coverage.formal_charge_count == 999
    assert result.reparsed_ingest.coverage.isotope_count == 999
    assert result.reparsed_ingest.coverage.atom_map_count == 999
    assert len(result.write_result.payload) < 2 * 1024 * 1024
    assert len(result.write_result.payload.splitlines()) < 4_096
    assert max(map(len, result.write_result.payload.splitlines())) <= 256


def test_writer_explicitly_rejects_v2000_atom_and_bond_count_overflow() -> None:
    base = parse_sdf_v2000(ETHANOL.read_bytes()).system

    atoms_1000 = tuple(
        replace(
            base.atoms[0],
            index=index,
            name=f"C{index + 1}",
            serial=index + 1,
            atom_map=None,
            aromatic=False,
            metadata={},
        )
        for index in range(1_000)
    )
    too_many_atoms = replace(
        base,
        atoms=atoms_1000,
        bonds=(),
        residues=(
            replace(base.residues[0], atom_indices=tuple(range(1_000))),
        ),
        coordinates=torch.zeros((1, 1_000, 3), dtype=torch.float64),
    )
    _assert_error(too_many_atoms, "unsupported_atom_count")

    atoms_46 = atoms_1000[:46]
    pairs = tuple(combinations(range(46), 2))[:1_000]
    bonds_1000 = tuple(
        replace(
            base.bonds[0],
            index=index,
            atom_i=atom_i,
            atom_j=atom_j,
            aromatic=False,
            metadata={},
        )
        for index, (atom_i, atom_j) in enumerate(pairs)
    )
    too_many_bonds = replace(
        base,
        atoms=atoms_46,
        bonds=bonds_1000,
        residues=(replace(base.residues[0], atom_indices=tuple(range(46))),),
        coordinates=torch.zeros((1, 46, 3), dtype=torch.float64),
    )
    _assert_error(too_many_bonds, "unsupported_bond_count")


def test_unrepresentable_coordinate_states_fail_closed() -> None:
    system = parse_sdf_v2000(ETHANOL.read_bytes()).system

    rounded = system.coordinates.clone()
    rounded[0, 0, 0] += 0.00001
    _assert_error(replace(system, coordinates=rounded), "coordinate_rounding_required")

    overflow = system.coordinates.clone()
    overflow[0, 0, 0] = -10000.0
    _assert_error(replace(system, coordinates=overflow), "coordinate_field_overflow")

    _assert_error(
        replace(system, coordinates=system.coordinates.to(dtype=torch.float32)),
        "unsupported_coordinate_dtype",
    )
    _assert_error(
        replace(system, coordinates=system.coordinates.clone().requires_grad_(True)),
        "coordinate_gradient_state_unsupported",
    )
    _assert_error(
        replace(system, coordinates=system.coordinates.new_empty((0, 3, 3))),
        "unsupported_coordinate_model_count",
    )
    _assert_error(
        replace(system, coordinates=system.coordinates.repeat(2, 1, 1)),
        "unsupported_coordinate_model_count",
    )
    _assert_error(
        replace(
            system,
            cell=UnitCell.orthorhombic(
                (10.0, 10.0, 10.0),
                dtype=torch.float64,
            ),
        ),
        "unsupported_unit_cell",
    )


def test_signed_zero_fixed_width_extrema_and_property_extrema_round_trip_bitwise() -> None:
    first = _atom_line("C", atom_map=998)
    second = _atom_line("N", x=1.0, atom_map=999)
    first = (
        f"{-0.0:10.4f}{99999.9999:10.4f}{-9999.9999:10.4f}" + first[30:]
    )
    source = _record(
        atoms=(first, second),
        properties=(
            "M  CHG  2   1 -15   2  15",
            "M  ISO  2   1 350   2 350",
        ),
    )
    result = round_trip_sdf_v2000_source(source)

    before = result.source_ingest.system.coordinates.view(torch.int64)
    after = result.reparsed_ingest.system.coordinates.view(torch.int64)
    assert torch.equal(before, after)
    assert int(before[0, 0, 0].item()) == -(1 << 63)
    assert [atom.formal_charge for atom in result.reparsed_ingest.system.atoms] == [
        -15,
        15,
    ]
    assert [
        atom.isotope_mass_number for atom in result.reparsed_ingest.system.atoms
    ] == [350, 350]
    assert [atom.atom_map for atom in result.reparsed_ingest.system.atoms] == [
        998,
        999,
    ]


def test_parser_accepted_f10_5_coordinate_is_explicitly_outside_writer_scope() -> None:
    atom = _atom_line()
    atom = f"{1.23456:10.5f}" + atom[10:]
    system = parse_sdf_v2000(_record(atoms=(atom,))).system
    _assert_error(system, "coordinate_rounding_required")


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda system: replace(
                system,
                atoms=(replace(system.atoms[0], stereo="R"), *system.atoms[1:]),
            ),
            "unsupported_atom_stereo",
        ),
        (
            lambda system: replace(
                system,
                atoms=(
                    replace(system.atoms[0], formal_charge_known=False),
                    *system.atoms[1:],
                ),
            ),
            "unknown_formal_charge",
        ),
        (
            lambda system: replace(
                system,
                atoms=(
                    replace(
                        system.atoms[0],
                        formal_charge=16,
                        metadata={
                            **dict(system.atoms[0].metadata),
                            "formal_charge_source": "sdf_v2000_m_chg",
                        },
                    ),
                    *system.atoms[1:],
                ),
            ),
            "unsupported_formal_charge",
        ),
        (
            lambda system: replace(
                system,
                atoms=(
                    replace(system.atoms[0], partial_charge_e=0.1),
                    *system.atoms[1:],
                ),
            ),
            "unsupported_partial_charge",
        ),
        (
            lambda system: replace(
                system,
                atoms=(replace(system.atoms[0], mass_da=12.0), *system.atoms[1:]),
            ),
            "unsupported_atom_mass",
        ),
        (
            lambda system: replace(
                system,
                atoms=(replace(system.atoms[0], name="CUSTOM"), *system.atoms[1:]),
            ),
            "unsupported_atom_name",
        ),
        (
            lambda system: replace(
                system,
                atoms=(
                    replace(
                        system.atoms[0],
                        atom_map=1000,
                        metadata={
                            **dict(system.atoms[0].metadata),
                            "sdf_atom_map": 1000,
                        },
                    ),
                    *system.atoms[1:],
                ),
            ),
            "unsupported_atom_map",
        ),
        (
            lambda system: replace(
                system,
                atoms=(replace(system.atoms[0], aromatic=True), *system.atoms[1:]),
            ),
            "inconsistent_aromatic_atom_flags",
        ),
        (
            lambda system: replace(
                system,
                bonds=(replace(system.bonds[0], stereo="UP"), *system.bonds[1:]),
            ),
            "unsupported_bond_stereo",
        ),
        (
            lambda system: replace(
                system,
                bonds=(
                    replace(system.bonds[0], order=1.5, aromatic=False),
                    *system.bonds[1:],
                ),
            ),
            "unsupported_bond_state",
        ),
        (
            lambda system: replace(
                system,
                residues=(replace(system.residues[0], name="UNK"),),
            ),
            "unsupported_residue_context",
        ),
        (
            lambda system: replace(
                system,
                metadata={**dict(system.metadata), "extra": "discarded"},
            ),
            "unsupported_system_metadata",
        ),
        (
            lambda system: replace(
                system,
                atoms=(
                    replace(
                        system.atoms[0],
                        metadata={**dict(system.atoms[0].metadata), "extra": True},
                    ),
                    *system.atoms[1:],
                ),
            ),
            "unsupported_atom_metadata",
        ),
    ],
)
def test_unrepresentable_canonical_fields_are_never_silently_discarded(
    mutator,
    code: str,
) -> None:
    system = parse_sdf_v2000(ETHANOL.read_bytes()).system
    _assert_error(mutator(system), code)


def test_stale_parser_observation_and_coverage_fail_closed() -> None:
    system = parse_sdf_v2000(ETHANOL.read_bytes()).system
    metadata = dict(system.provenance.metadata)
    metadata["parser_observation_sha256"] = "0" * 64
    _assert_error(
        replace(system, provenance=replace(system.provenance, metadata=metadata)),
        "stale_parser_observation_digest",
    )

    metadata = dict(system.provenance.metadata)
    coverage = dict(metadata["coverage"])
    coverage["formal_charge_count"] = 1
    metadata["coverage"] = coverage
    _assert_error(
        replace(system, provenance=replace(system.provenance, metadata=metadata)),
        "stale_sdf_coverage",
    )

    metadata = dict(system.provenance.metadata)
    metadata["canonical_topology_sha256"] = "0" * 64
    _assert_error(
        replace(system, provenance=replace(system.provenance, metadata=metadata)),
        "stale_canonical_topology_digest",
    )


@pytest.mark.parametrize(
    ("provenance_mutator", "code"),
    [
        (
            lambda provenance: replace(provenance, source_format="pdb"),
            "unsupported_source_format",
        ),
        (
            lambda provenance: replace(provenance, parser_version="0.0.0"),
            "unsupported_parser_pedigree",
        ),
        (
            lambda provenance: replace(
                provenance,
                operations=(*provenance.operations, "unrecorded_transform"),
            ),
            "unsupported_provenance_operations",
        ),
        (
            lambda provenance: replace(provenance, parent_sha256=("0" * 64,)),
            "unsupported_parent_provenance",
        ),
        (
            lambda provenance: replace(provenance, preparation_ready=True),
            "unsupported_authority_state",
        ),
        (
            lambda provenance: replace(provenance, claim_safe=True),
            "unsupported_authority_state",
        ),
    ],
)
def test_unsupported_parser_pedigree_and_authority_state_fail_closed(
    provenance_mutator,
    code: str,
) -> None:
    system = parse_sdf_v2000(ETHANOL.read_bytes()).system
    _assert_error(
        replace(system, provenance=provenance_mutator(system.provenance)),
        code,
    )


def test_unsafe_header_text_fails_closed() -> None:
    system = parse_sdf_v2000(ETHANOL.read_bytes()).system
    header = dict(system.metadata["sdf_v2000_header"])
    header["comment"] = "unsafe\theader"
    _assert_error(
        replace(system, metadata={"sdf_v2000_header": header}),
        "unsupported_sdf_header",
    )


def test_success_artifacts_are_factory_only_and_cross_wiring_is_rejected() -> None:
    ethanol = round_trip_sdf_v2000_source(
        ETHANOL.read_bytes(),
        source_id="ethanol",
    )
    methane = round_trip_sdf_v2000_source(
        (V2_1_CORPUS / "methane_explicit_h.sdf").read_bytes(),
        source_id="methane",
    )
    zero = "0" * 64

    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000WriteReceipt(
            input_system_schema_id=ethanol.source_ingest.system.schema_id,
            parent_source_sha256=zero,
            input_snapshot_sha256=zero,
            input_topology_sha256=zero,
            input_representable_state_sha256=zero,
            output_source_sha256=zero,
            output_byte_count=1,
            atom_count=1,
            bond_count=0,
        )
    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000WriteResult(
            payload=ethanol.write_result.payload,
            receipt=ethanol.write_result.receipt,
        )
    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000RoundTripReport(
            input_source_sha256=zero,
            input_snapshot_sha256=zero,
            input_topology_sha256=zero,
            input_representable_state_sha256=zero,
            writer_receipt_sha256=zero,
            emitted_source_sha256=zero,
            reparsed_snapshot_sha256=zero,
            reparsed_topology_sha256=zero,
            reparsed_representable_state_sha256=zero,
            reemitted_source_sha256=zero,
        )
    with pytest.raises(TypeError, match="factory-only"):
        SdfV2000RoundTripResult(
            source_ingest=ethanol.source_ingest,
            write_result=ethanol.write_result,
            reparsed_ingest=ethanol.reparsed_ingest,
            report=ethanol.report,
        )
    with pytest.raises(TypeError):
        replace(ethanol, source_ingest=methane.source_ingest)

    with pytest.raises(ValueError, match="cross-consistent"):
        SdfV2000RoundTripResult(
            source_ingest=methane.source_ingest,
            write_result=ethanol.write_result,
            reparsed_ingest=ethanol.reparsed_ingest,
            report=ethanol.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    mismatched_coverage = SdfV2000IngestResult(
        system=ethanol.source_ingest.system,
        coverage=methane.source_ingest.coverage,
    )
    with pytest.raises(ValueError, match="source ingest coverage"):
        SdfV2000RoundTripResult(
            source_ingest=mismatched_coverage,
            write_result=ethanol.write_result,
            reparsed_ingest=ethanol.reparsed_ingest,
            report=ethanol.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_round_trip_result_accessors_return_fresh_detached_system_copies() -> None:
    result = round_trip_sdf_v2000_source(ETHANOL.read_bytes())
    original_source = result.source_ingest.system.coordinates.clone()
    original_reparsed = result.reparsed_ingest.system.coordinates.clone()

    exposed_source = result.source_ingest
    exposed_reparsed = result.reparsed_ingest
    exposed_source.system.coordinates[0, 0, 0] = 123.0
    exposed_reparsed.system.coordinates[0, 0, 0] = -456.0

    assert torch.equal(result.source_ingest.system.coordinates, original_source)
    assert torch.equal(result.reparsed_ingest.system.coordinates, original_reparsed)
    result.__post_init__()


def test_success_artifact_repr_is_bounded_and_does_not_expose_source_payloads() -> None:
    result = round_trip_sdf_v2000_source(ETHANOL.read_bytes())
    result_repr = repr(result)
    write_repr = repr(result.write_result)

    assert len(result_repr) < 4_000
    assert len(write_repr) < 2_000
    assert "M  END" not in result_repr
    assert "M  END" not in write_repr
    assert "RDKit" not in result_repr
    assert "RDKit" not in write_repr
    assert "coordinates_ieee754" not in result_repr


def test_writer_rejects_non_system_input_without_partial_output() -> None:
    with pytest.raises(TypeError, match="exact AllAtomSystem"):
        serialize_sdf_v2000(b"not-a-system")
