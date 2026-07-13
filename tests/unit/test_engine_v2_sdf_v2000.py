from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    SDF_V2000_PARSER_VERSION,
    SdfV2000ParseError,
    analyze_molecular_preparation,
    attached_canonical_topology_sha256_matches,
    attached_parser_observation_sha256_matches,
    canonical_all_atom_systems_equal,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    parse_sdf_v2000,
    serialize_all_atom_system,
    validate_all_atom_system,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tier_beta"


def _atom_line(
    element: str = "C",
    *,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    mass_difference: int = 0,
    charge_code: int = 0,
    parity: int = 0,
    hydrogen_count: int = 0,
    atom_map: int = 0,
) -> str:
    return (
        f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3}"
        f"{mass_difference:2d}{charge_code:3d}{parity:3d}{hydrogen_count:3d}"
        f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{atom_map:3d}{0:3d}{0:3d}"
    )


def _bond_line(atom_i: int, atom_j: int, bond_type: int = 1, *, stereo: int = 0) -> str:
    return f"{atom_i:3d}{atom_j:3d}{bond_type:3d}{stereo:3d}"


def _record(
    *,
    atoms: tuple[str, ...] | None = None,
    bonds: tuple[str, ...] = (),
    properties: tuple[str, ...] = (),
    after_m_end: tuple[str, ...] = (),
    include_m_end: bool = True,
    include_delimiter: bool = True,
    counts_line: str | None = None,
) -> bytes:
    atom_lines = atoms or (_atom_line(),)
    counts = counts_line or (
        f"{len(atom_lines):3d}{len(bonds):3d}  0  0  0  0  0  0  0  0999 V2000"
    )
    lines = ["fixture", "codex", "strict subset", counts, *atom_lines, *bonds, *properties]
    if include_m_end:
        lines.append("M  END")
    lines.extend(after_m_end)
    if include_delimiter:
        lines.append("$$$$")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_parse_existing_ethanol_fixture_and_canonical_round_trip() -> None:
    source = (FIXTURES / "ethanol.sdf").read_bytes()
    result = parse_sdf_v2000(source, source_id="tier-beta-ethanol")
    system = result.system

    assert SDF_V2000_PARSER_VERSION == "1.5.0"
    assert system.system_id == "tier-beta-ethanol"
    assert [atom.element for atom in system.atoms] == ["C", "C", "O"]
    assert [atom.index for atom in system.atoms] == [0, 1, 2]
    assert [atom.name for atom in system.atoms] == ["C1", "C2", "O3"]
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in system.bonds] == [
        (0, 1, 1.0),
        (1, 2, 1.0),
    ]
    assert system.coordinates.dtype == torch.float64
    assert system.coordinates.shape == (1, 3, 3)
    assert torch.allclose(
        system.coordinates[0],
        torch.tensor([[-1.299, -0.25, 0.0], [0.0, 0.5, 0.0], [1.299, -0.25, 0.0]], dtype=torch.float64),
    )
    assert system.provenance.source_sha256 == hashlib.sha256(source).hexdigest()
    assert system.provenance.parser_version == SDF_V2000_PARSER_VERSION
    assert system.provenance.claim_safe is False
    assert validate_all_atom_system(system).valid
    assert result.coverage.atom_count == 3
    assert result.coverage.bond_count == 2
    assert result.coverage.claim_safe is False
    assert "protonation_not_assessed" in result.coverage.blockers
    topology_digest = canonical_topology_sha256(system)
    assert result.coverage.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert result.coverage.canonical_topology_sha256 == topology_digest
    assert system.provenance.metadata["canonical_topology_schema_id"] == (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    assert system.provenance.metadata["canonical_topology_sha256"] == topology_digest
    assert attached_canonical_topology_sha256_matches(system)
    repeated = parse_sdf_v2000(source, source_id="tier-beta-ethanol")
    assert repeated.coverage.canonical_topology_sha256 == topology_digest

    restored = deserialize_all_atom_system(serialize_all_atom_system(system))
    assert canonical_all_atom_systems_equal(system, restored)
    assert canonical_topology_sha256(restored) == topology_digest
    assert attached_canonical_topology_sha256_matches(restored)


def test_parse_charge_isotope_atom_map_and_aromatic_bond() -> None:
    charged = _record(
        atoms=(
            _atom_line("C", atom_map=17),
            _atom_line("N", x=1.2),
        ),
        bonds=(_bond_line(1, 2, 1),),
        properties=("M  CHG  1   1  -1", "M  ISO  1   2  15"),
    )
    result = parse_sdf_v2000(charged)
    assert result.system.atoms[0].formal_charge == -1
    assert result.system.atoms[0].atom_map == 17
    assert result.system.atoms[0].metadata["sdf_atom_map"] == 17
    assert result.system.atoms[0].metadata["formal_charge_source"] == (
        "sdf_v2000_m_chg"
    )
    assert result.system.atoms[1].metadata["formal_charge_source"] == (
        "sdf_v2000_atom_block"
    )
    assert result.system.atoms[1].atom_map is None
    assert result.system.atoms[1].isotope_mass_number == 15
    assert result.coverage.formal_charge_count == 1
    assert result.coverage.isotope_count == 1
    assert result.coverage.atom_map_count == 1

    aromatic = parse_sdf_v2000(
        _record(
            atoms=(_atom_line("C"), _atom_line("C", x=1.4)),
            bonds=(_bond_line(1, 2, 4),),
        )
    )
    assert aromatic.system.bonds[0].aromatic is True
    assert aromatic.system.bonds[0].order == 1.5
    assert [atom.aromatic for atom in aromatic.system.atoms] == [True, True]
    assert aromatic.coverage.aromatic_bond_count == 1
    aromatic_report = analyze_molecular_preparation(aromatic.system)
    assert aromatic_report.aromatic_annotation_origin == (
        "metadata_observed_sdf_v2000_bond_type_4_projection"
    )
    assert aromatic_report.aromaticity_perception_assessed is False

    hydrogen = parse_sdf_v2000(_record(atoms=(_atom_line("H"),)))
    assert hydrogen.system.atoms[0].metadata["hydrogen_origin"] == "source"


def test_sdf_charge_origin_marker_swap_invalidates_parser_observation() -> None:
    source = parse_sdf_v2000(
        _record(
            atoms=(_atom_line("C"), _atom_line("N", x=1.2)),
            bonds=(_bond_line(1, 2),),
            properties=("M  CHG  1   1  -1",),
        )
    ).system
    first, second = source.atoms
    forged = replace(
        source,
        atoms=(
            replace(
                first,
                metadata={
                    **dict(first.metadata),
                    "formal_charge_source": "sdf_v2000_atom_block",
                },
            ),
            replace(
                second,
                metadata={
                    **dict(second.metadata),
                    "formal_charge_source": "sdf_v2000_m_chg",
                },
            ),
        ),
    )
    assert attached_parser_observation_sha256_matches(forged) is False
    report = analyze_molecular_preparation(forged)
    assert report.parser_observation_self_consistent is False
    assert report.formal_charge_origin_counts == (
        ("unclassified_known", 2),
    )


def test_unexpected_numeric_marker_values_have_distinct_observation_digests() -> None:
    source = parse_sdf_v2000((FIXTURES / "ethanol.sdf").read_bytes()).system
    metadata = dict(source.atoms[0].metadata)
    metadata["sdf_source_atom_index"] = 2.0
    sealed = attach_parser_observation_digest(
        replace(
            source,
            atoms=(replace(source.atoms[0], metadata=metadata), *source.atoms[1:]),
        )
    )
    changed_metadata = dict(sealed.atoms[0].metadata)
    changed_metadata["sdf_source_atom_index"] = 1.0
    changed = replace(
        sealed,
        atoms=(
            replace(sealed.atoms[0], metadata=changed_metadata),
            *sealed.atoms[1:],
        ),
    )
    assert attached_parser_observation_sha256_matches(changed) is False
    report = analyze_molecular_preparation(changed)
    assert report.parser_observation_self_consistent is False
    assert report.formal_charge_origin_counts == (
        ("unclassified_known", report.atom_count),
    )


def test_parse_allows_single_mol_block_without_sdf_delimiter() -> None:
    result = parse_sdf_v2000(_record(include_delimiter=False))
    assert result.coverage.atom_count == 1


def test_property_integer_digit_bomb_fails_with_stable_parser_error() -> None:
    payload = _record().replace(
        b"M  END",
        b"M  CHG " + b"9" * 5000 + b"\nM  END",
        1,
    )
    with pytest.raises(SdfV2000ParseError) as exc_info:
        parse_sdf_v2000(payload)
    assert exc_info.value.code == "line_too_long"


def test_sdf_input_and_line_resource_caps_fail_before_parsing() -> None:
    with pytest.raises(SdfV2000ParseError) as exc_info:
        parse_sdf_v2000(b"x" * (2 * 1024 * 1024 + 1))
    assert exc_info.value.code == "input_too_large"

    source = _record()
    long_header = b"x" * 257 + source[source.index(b"\n") :]
    with pytest.raises(SdfV2000ParseError) as exc_info:
        parse_sdf_v2000(long_header)
    assert exc_info.value.code == "line_too_long"


def test_parse_preserves_source_bond_order_while_canonicalizing_endpoints() -> None:
    result = parse_sdf_v2000(
        _record(
            atoms=(_atom_line("C"), _atom_line("O", x=1.2)),
            bonds=(_bond_line(2, 1),),
        )
    )
    bond = result.system.bonds[0]
    assert (bond.atom_i, bond.atom_j) == (0, 1)
    assert bond.metadata["sdf_source_atom_i"] == 2
    assert bond.metadata["sdf_source_atom_j"] == 1
    assert "canonicalize_bond_endpoint_order" in result.system.provenance.operations


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff\xfe", "invalid_ascii"),
        (_record().replace(b"fixture", "fíxture".encode("utf-8")), "invalid_ascii"),
        (_record(counts_line="  1  0  0  0  0  0  0  0  0  0999 V3000"), "unsupported_v3000"),
        (_record(include_m_end=False, include_delimiter=False), "missing_m_end"),
        (_record(after_m_end=(">  <ID>", "value")), "unsupported_data_fields"),
        (_record(properties=("M  RAD  1   1   2",)), "unsupported_property_record"),
        (_record(atoms=(_atom_line(parity=1),)), "unsupported_atom_stereo"),
        (_record(atoms=(_atom_line(charge_code=4),)), "unsupported_radical"),
        (_record(atoms=(_atom_line(hydrogen_count=1),)), "unsupported_atom_feature"),
        (
            _record(atoms=(_atom_line(atom_map=7), _atom_line("N", x=1.0, atom_map=7))),
            "duplicate_atom_map",
        ),
        (_record(atoms=(_atom_line("Xx"),)), "unknown_element"),
        (_record(atoms=(_atom_line(x=float("nan")),)), "invalid_atom_coordinate"),
        (
            _record(atoms=(_atom_line(), _atom_line(x=1.0)), bonds=(_bond_line(1, 2, 5),)),
            "unsupported_bond_type",
        ),
        (
            _record(atoms=(_atom_line(), _atom_line(x=1.0)), bonds=(_bond_line(1, 2, stereo=1),)),
            "unsupported_bond_stereo",
        ),
        (
            _record(atoms=(_atom_line(), _atom_line(x=1.0)), bonds=(_bond_line(1, 3),)),
            "bond_atom_out_of_range",
        ),
        (
            _record(
                atoms=(_atom_line(), _atom_line(x=1.0)),
                bonds=(_bond_line(1, 2), _bond_line(2, 1)),
            ),
            "duplicate_bond",
        ),
        (
            _record(atoms=(_atom_line(charge_code=3),), properties=("M  CHG  1   1   1",)),
            "conflicting_charge_sources",
        ),
        (
            _record(
                atoms=(_atom_line(charge_code=3), _atom_line("N", x=1.0)),
                properties=("M  CHG  1   2  -1",),
            ),
            "conflicting_charge_sources",
        ),
        (
            _record(properties=("M  ISO  1   1  13", "M  ISO  1   1  13")),
            "duplicate_isotope_property",
        ),
        (_record(properties=("M  CHG  1   2  -1",)), "property_atom_out_of_range"),
        (_record(properties=("M  ISO  1   1   5",)), "invalid_isotope_mass_number"),
        (
            _record(counts_line="  1  0  0  0  1  0  0  0  0  0999 V2000"),
            "unsupported_counts_feature",
        ),
        (
            _record(counts_line="1_0  0  0  0  0  0  0  0  0  0999 V2000"),
            "invalid_counts_line",
        ),
        (
            _record(atoms=(f"{'1_0.0':>10}" + _atom_line()[10:],)),
            "invalid_atom_coordinate",
        ),
        (
            _record(
                atoms=(_atom_line(), _atom_line(x=1.0)),
                bonds=(_bond_line(1, 2) + "  0  0  0  0",),
            ),
            "invalid_bond_line",
        ),
        (_record(properties=("M  CHG  1_   1  -1",)), "invalid_property_line"),
    ],
)
def test_sdf_v2000_unsupported_or_malformed_features_fail_closed(payload: bytes, code: str) -> None:
    with pytest.raises(SdfV2000ParseError) as exc_info:
        parse_sdf_v2000(payload)
    assert exc_info.value.code == code


def test_sdf_v2000_rejects_multiple_records() -> None:
    with pytest.raises(SdfV2000ParseError) as exc_info:
        parse_sdf_v2000(_record() + _record())
    assert exc_info.value.code == "multiple_records"


def test_sdf_v2000_rejects_non_bytes_and_non_string_source_id() -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        parse_sdf_v2000("not-bytes")
    with pytest.raises(TypeError, match="source_id must be a string"):
        parse_sdf_v2000(_record(), source_id=7)
