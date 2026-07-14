from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import hashlib

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology as topology_module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology import (
    MmcifNonpolyComponentRow,
    MmcifNonpolyComponentTopologyError,
    MmcifNonpolyComponentTopologyIngestResult,
    MmcifNonpolyComponentTopologyRoundTripResult,
    MmcifNonpolyComponentTopologyWriteReceipt,
    mmcif_nonpoly_component_topology_projection_sha256,
    mmcif_nonpoly_component_topology_state_sha256,
    parse_mmcif_nonpoly_component_topology,
    round_trip_mmcif_nonpoly_component_topology_source,
    serialize_mmcif_nonpoly_component_topology,
    write_mmcif_nonpoly_component_topology,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MmcifNonpolyIdentityError,
    parse_mmcif_nonpoly_identity,
)
from betelgeuze_engine_v2.molecular.pdb_mmcif import (
    StructureParseError,
    parse_mmcif,
)


AtomTemplate = tuple[str, str, int, str]
BondTemplate = tuple[str, str, str]
Component = tuple[str, int, tuple[AtomTemplate, ...], tuple[BondTemplate, ...]]
Instance = tuple[str, str, str, str, tuple[str, ...]]


def _factory_artifact_for_kind(
    result: MmcifNonpolyComponentTopologyRoundTripResult, kind: str
) -> object:
    if kind == "receipt":
        return result.write_result.receipt
    if kind == "write_result":
        return result.write_result
    if kind == "report":
        return result.report
    if kind == "round_trip_result":
        return result
    raise AssertionError(f"unexpected factory artifact kind: {kind}")


def _copy_dataclass_fields(target: object, source: object) -> None:
    assert type(target) is type(source)
    for dataclass_field in fields(source):
        object.__setattr__(
            target, dataclass_field.name, getattr(source, dataclass_field.name)
        )


def _access_factory_artifact(kind: str, value: object) -> object:
    if kind == "receipt":
        return value.output_source_sha256  # type: ignore[attr-defined]
    if kind == "write_result":
        return value.payload  # type: ignore[attr-defined]
    if kind == "report":
        return value.report_sha256  # type: ignore[attr-defined]
    if kind == "round_trip_result":
        return value.report  # type: ignore[attr-defined]
    raise AssertionError(f"unexpected factory artifact kind: {kind}")


def _source(
    *,
    components: tuple[Component, ...],
    instances: tuple[Instance, ...],
    polymer: bool = False,
    block_name: str = "component_topology",
) -> bytes:
    entities: list[tuple[str, str]] = []
    asym_rows: list[tuple[str, str]] = []
    entity_nonpoly: list[tuple[str, str]] = []
    scheme: list[tuple[str, ...]] = []
    atom_site: list[tuple[str, ...]] = []
    next_entity = 1
    next_serial = 1
    if polymer:
        entities.append(("1", "polymer"))
        asym_rows.append(("A", "1"))
        atom_site.append(
            (
                "ATOM",
                "1",
                "C",
                "CA",
                ".",
                "GLY",
                "A",
                "1",
                "1",
                "?",
                "0.0",
                "0.0",
                "0.0",
                "1.0",
                "20.0",
                "?",
                "101",
                "GLY",
                "AX",
                "CA",
                "1",
            )
        )
        next_entity = 2
        next_serial = 2

    component_entity: dict[str, str] = {}
    component_type = {
        comp_id: "water" if comp_id == "HOH" else "non-polymer"
        for comp_id, *_ in components
    }
    for comp_id, *_ in components:
        entity_id = str(next_entity)
        next_entity += 1
        component_entity[comp_id] = entity_id
        entities.append((entity_id, component_type[comp_id]))
        entity_nonpoly.append((entity_id, comp_id))

    seen_asym: set[str] = set()
    sequence_by_asym: dict[str, int] = {}
    template_by_component = {
        comp_id: {
            atom_id: (element, charge, aromatic)
            for atom_id, element, charge, aromatic in atoms
        }
        for comp_id, _formal_charge, atoms, _bonds in components
    }
    for asym_id, _unused_entity, comp_id, auth_seq, atom_ids in instances:
        entity_id = component_entity[comp_id]
        if asym_id not in seen_asym:
            asym_rows.append((asym_id, entity_id))
            seen_asym.add(asym_id)
        sequence_by_asym[asym_id] = sequence_by_asym.get(asym_id, 0) + 1
        ndb = str(sequence_by_asym[asym_id])
        scheme.append(
            (
                asym_id,
                entity_id,
                comp_id,
                ndb,
                auth_seq,
                auth_seq,
                comp_id,
                comp_id,
                f"AUTH{asym_id}",
                ".",
            )
        )
        for atom_id in atom_ids:
            element, charge, _aromatic = template_by_component[comp_id][atom_id]
            atom_site_charge = "?" if next_serial % 2 == 0 else str(charge)
            atom_site.append(
                (
                    "HETATM",
                    str(next_serial),
                    element,
                    atom_id,
                    ".",
                    comp_id,
                    asym_id,
                    entity_id,
                    ".",
                    "?",
                    f"{float(next_serial):.1f}",
                    "0.0",
                    "0.0",
                    "1.0",
                    "20.0",
                    atom_site_charge,
                    auth_seq,
                    comp_id,
                    f"AUTH{asym_id}",
                    atom_id,
                    "1",
                )
            )
            next_serial += 1

    chem_comp_rows = [
        (comp_id, "NON-POLYMER", str(formal_charge))
        for comp_id, formal_charge, _atoms, _bonds in components
    ]
    chem_atom_rows: list[tuple[str, ...]] = []
    chem_bond_rows: list[tuple[str, ...]] = []
    for comp_id, _formal_charge, atoms, bonds in components:
        for ordinal, (atom_id, element, charge, aromatic) in enumerate(atoms, 1):
            chem_atom_rows.append(
                (
                    comp_id,
                    atom_id,
                    element,
                    str(charge),
                    aromatic,
                    "N",
                    str(ordinal),
                )
            )
        for ordinal, (atom_1, atom_2, value_order) in enumerate(bonds, 1):
            chem_bond_rows.append(
                (
                    comp_id,
                    atom_1,
                    atom_2,
                    value_order,
                    "Y" if value_order == "AROM" else "N",
                    "N",
                    str(ordinal),
                )
            )

    def loop(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
        return (
            "\n".join(("loop_", *headers, *(" ".join(row) for row in rows), "#")) + "\n"
        )

    text = f"data_{block_name}\n#\n"
    text += loop(("_entity.id", "_entity.type"), entities)
    text += loop(("_struct_asym.id", "_struct_asym.entity_id"), asym_rows)
    text += loop(
        ("_chem_comp.id", "_chem_comp.type", "_chem_comp.pdbx_formal_charge"),
        chem_comp_rows,
    )
    text += loop(
        (
            "_chem_comp_atom.comp_id",
            "_chem_comp_atom.atom_id",
            "_chem_comp_atom.type_symbol",
            "_chem_comp_atom.charge",
            "_chem_comp_atom.pdbx_aromatic_flag",
            "_chem_comp_atom.pdbx_stereo_config",
            "_chem_comp_atom.pdbx_ordinal",
        ),
        chem_atom_rows,
    )
    text += loop(
        (
            "_chem_comp_bond.comp_id",
            "_chem_comp_bond.atom_id_1",
            "_chem_comp_bond.atom_id_2",
            "_chem_comp_bond.value_order",
            "_chem_comp_bond.pdbx_aromatic_flag",
            "_chem_comp_bond.pdbx_stereo_config",
            "_chem_comp_bond.pdbx_ordinal",
        ),
        chem_bond_rows,
    )
    text += loop(
        ("_pdbx_entity_nonpoly.entity_id", "_pdbx_entity_nonpoly.comp_id"),
        entity_nonpoly,
    )
    text += loop(
        (
            "_pdbx_nonpoly_scheme.asym_id",
            "_pdbx_nonpoly_scheme.entity_id",
            "_pdbx_nonpoly_scheme.mon_id",
            "_pdbx_nonpoly_scheme.ndb_seq_num",
            "_pdbx_nonpoly_scheme.pdb_seq_num",
            "_pdbx_nonpoly_scheme.auth_seq_num",
            "_pdbx_nonpoly_scheme.pdb_mon_id",
            "_pdbx_nonpoly_scheme.auth_mon_id",
            "_pdbx_nonpoly_scheme.pdb_strand_id",
            "_pdbx_nonpoly_scheme.pdb_ins_code",
        ),
        scheme,
    )
    text += loop(
        (
            "_atom_site.group_PDB",
            "_atom_site.id",
            "_atom_site.type_symbol",
            "_atom_site.label_atom_id",
            "_atom_site.label_alt_id",
            "_atom_site.label_comp_id",
            "_atom_site.label_asym_id",
            "_atom_site.label_entity_id",
            "_atom_site.label_seq_id",
            "_atom_site.pdbx_PDB_ins_code",
            "_atom_site.Cartn_x",
            "_atom_site.Cartn_y",
            "_atom_site.Cartn_z",
            "_atom_site.occupancy",
            "_atom_site.B_iso_or_equiv",
            "_atom_site.pdbx_formal_charge",
            "_atom_site.auth_seq_id",
            "_atom_site.auth_comp_id",
            "_atom_site.auth_asym_id",
            "_atom_site.auth_atom_id",
            "_atom_site.pdbx_PDB_model_num",
        ),
        atom_site,
    )
    return text.encode("ascii")


ALIPHATIC: tuple[Component, ...] = (
    (
        "LIG",
        0,
        (("C1", "C", 0, "N"), ("O1", "O", 0, "N"), ("H1", "H", 0, "N")),
        (("C1", "O1", "DOUB"), ("C1", "H1", "SING")),
    ),
)
AROMATIC: tuple[Component, ...] = (
    (
        "RNG",
        0,
        (("C1", "C", 0, "Y"), ("C2", "C", 0, "Y")),
        (("C1", "C2", "AROM"),),
    ),
)


def _single_source() -> bytes:
    return _source(
        components=ALIPHATIC,
        instances=(("L", "", "LIG", "501", ("C1", "O1", "H1")),),
    )


def _assert_error(source: bytes, code: str) -> None:
    with pytest.raises(MmcifNonpolyComponentTopologyError) as exc_info:
        parse_mmcif_nonpoly_component_topology(source)
    assert exc_info.value.code == code


def test_single_aliphatic_materializes_full_charge_atom_and_bond_state() -> None:
    source = _single_source()
    ingest = parse_mmcif_nonpoly_component_topology(source, source_id="single")
    system = ingest.system

    assert ingest.carrier_ingest.system.bonds == ()
    assert [atom.name for atom in system.atoms] == ["C1", "O1", "H1"]
    assert all(atom.formal_charge_known for atom in system.atoms)
    assert [atom.formal_charge for atom in system.atoms] == [0, 0, 0]
    assert [atom.stereo for atom in system.atoms] == ["none", "none", "none"]
    assert [
        (bond.atom_i, bond.atom_j, bond.order, bond.aromatic, bond.stereo)
        for bond in system.bonds
    ] == [(0, 1, 2.0, False, "none"), (0, 2, 1.0, False, "none")]
    assert mmcif_nonpoly_component_topology_projection_sha256(ingest) == (
        ingest.component_projection_sha256
    )
    assert mmcif_nonpoly_component_topology_state_sha256(ingest) == (
        ingest.topology_state_sha256
    )
    assert ingest.to_dict()["preparation_ready"] is False
    assert ingest.to_dict()["parameterability_assessed"] is False
    assert ingest.to_dict()["runtime_eligible"] is False
    assert ingest.to_dict()["claim_safe"] is False
    write_result = write_mmcif_nonpoly_component_topology(ingest)
    assert system.provenance.source_sha256 == hashlib.sha256(source).hexdigest()
    assert system.provenance.source_sha256 == ingest.full_source_sha256
    assert system.provenance.source_sha256 != write_result.receipt.output_source_sha256
    assert system.provenance.metadata["mmcif_nonpoly_component_topology"] == {
        "canonical_output_sha256": write_result.receipt.output_source_sha256,
        "carrier_evidence_semantics": (
            "preserved_identity_carrier_only_not_augmented_topology_evidence"
        ),
        "source_sha256_semantics": "raw_full_source_bytes",
    }


def test_aromatic_component_materializes_aromatic_atoms_and_bond() -> None:
    source = _source(
        components=AROMATIC,
        instances=(("R", "", "RNG", "9", ("C1", "C2")),),
    )
    system = parse_mmcif_nonpoly_component_topology(source).system
    assert [atom.aromatic for atom in system.atoms] == [True, True]
    assert len(system.bonds) == 1
    assert system.bonds[0].order == 1.5
    assert system.bonds[0].aromatic is True


def test_same_component_multiple_instances_get_independent_canonical_bonds() -> None:
    source = _source(
        components=ALIPHATIC,
        instances=(
            ("L", "", "LIG", "501", ("C1", "O1", "H1")),
            ("L", "", "LIG", "502", ("C1", "O1", "H1")),
        ),
    )
    system = parse_mmcif_nonpoly_component_topology(source).system
    assert len(system.residues) == 2
    assert [(bond.atom_i, bond.atom_j) for bond in system.bonds] == [
        (0, 1),
        (0, 2),
        (3, 4),
        (3, 5),
    ]
    assert [bond.index for bond in system.bonds] == [0, 1, 2, 3]


def test_mixed_polymer_remains_unchanged_and_bondless() -> None:
    components: tuple[Component, ...] = (
        *ALIPHATIC,
        ("HOH", 0, (("O", "O", 0, "N"),), ()),
    )
    source = _source(
        components=components,
        instances=(
            ("L", "", "LIG", "501", ("C1", "O1", "H1")),
            ("W", "", "HOH", "601", ("O",)),
        ),
        polymer=True,
    )
    ingest = parse_mmcif_nonpoly_component_topology(source)
    carrier = ingest.carrier_ingest.system
    system = ingest.system
    assert system.atoms[0] == carrier.atoms[0]
    assert system.atoms[0].residue_index == 0
    assert system.atoms[0].formal_charge_known is False
    assert all(bond.atom_i != 0 and bond.atom_j != 0 for bond in system.bonds)
    assert [residue.entity_type for residue in system.residues] == [
        "polymer",
        "non_polymer",
        "water",
    ]


def test_round_trip_is_exact_and_category_order_is_canonical() -> None:
    result = round_trip_mmcif_nonpoly_component_topology_source(
        _single_source(), source_id="roundtrip"
    )
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert serialize_mmcif_nonpoly_component_topology(result.source_ingest) == (
        result.write_result.payload
    )
    assert result.report.component_projection_equal
    assert result.report.topology_state_equal
    assert result.report.topology_equal
    assert result.report.emitted_source_reparsed_exact
    assert result.report.second_emission_byte_stable
    text = result.write_result.payload.decode("ascii").lower()
    categories = [
        "_entity.id",
        "_struct_asym.id",
        "_chem_comp.id",
        "_chem_comp_atom.comp_id",
        "_chem_comp_bond.comp_id",
        "_pdbx_entity_nonpoly.entity_id",
        "_pdbx_nonpoly_scheme.asym_id",
        "_atom_site.group_pdb",
    ]
    assert [text.index(category) for category in categories] == sorted(
        text.index(category) for category in categories
    )


def test_base_and_identity_parsers_remain_rejecting() -> None:
    source = _single_source()
    with pytest.raises(StructureParseError) as base_error:
        parse_mmcif(source)
    assert base_error.value.code == "unsupported_topology_category"
    with pytest.raises(MmcifNonpolyIdentityError) as identity_error:
        parse_mmcif_nonpoly_identity(source)
    assert identity_error.value.code == "unsupported_category_surface"


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (b"LIG NON-POLYMER 0", b"LIG NON-POLYMER 1", "component_charge_sum_mismatch"),
        (b"LIG O1 O 0 N N 2", b"LIG O1 O 1 N N 2", "component_charge_sum_mismatch"),
        (
            b"LIG C1 O1 DOUB N N 1",
            b"LIG C1 O1 AROM N N 1",
            "component_bond_aromatic_mismatch",
        ),
        (b"LIG C1 H1 SING N N 2", b"LIG C1 H9 SING N N 2", "dangling_component_bond"),
        (b"LIG C1 H1 SING N N 2", b"LIG C1 C1 SING N N 2", "self_component_bond"),
        (b"LIG O1 O 0 N N 2", b"LIG O1 Si 0 N N 2", "unsupported_component_element"),
        (b"LIG O1 O 0 N N 2", b"LIG O1 O 0 N R 2", "unsupported_component_atom_stereo"),
    ],
)
def test_representative_component_definition_failures(
    old: bytes, new: bytes, code: str
) -> None:
    source = _single_source()
    assert source.count(old) == 1
    _assert_error(source.replace(old, new, 1), code)


def test_instance_missing_extra_element_and_known_charge_mismatches_fail() -> None:
    source = _single_source()
    missing = source.replace(
        b"HETATM 3 H H1 . LIG L 1 . ? 3.0 0.0 0.0 1.0 20.0 0 501 LIG AUTHL H1 1\n",
        b"",
    )
    _assert_error(missing, "component_instance_atom_coverage_mismatch")

    extra = source.replace(b"HETATM 3 H H1", b"HETATM 3 H HX")
    _assert_error(extra, "component_instance_atom_coverage_mismatch")

    element = source.replace(b"HETATM 2 O O1", b"HETATM 2 N O1")
    _assert_error(element, "component_atom_element_mismatch")

    known_charge = source.replace(
        b"HETATM 1 C C1 . LIG L 1 . ? 1.0 0.0 0.0 1.0 20.0 0",
        b"HETATM 1 C C1 . LIG L 1 . ? 1.0 0.0 0.0 1.0 20.0 1",
    )
    _assert_error(known_charge, "component_atom_charge_mismatch")


def test_factory_only_frozen_tamper_crosswire_and_whole_state_replacement() -> None:
    source = _single_source()
    result = round_trip_mmcif_nonpoly_component_topology_source(source)
    row = result.source_ingest.component_rows[0]
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyComponentRow(comp_id="X", component_type="X", formal_charge=0)
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyComponentTopologyIngestResult(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyComponentTopologyWriteReceipt(None, b"", {})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="factory-only"):
        MmcifNonpolyComponentTopologyRoundTripResult(None, None, None, None, None)  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        row.comp_id = "X"  # type: ignore[misc]

    tampered = parse_mmcif_nonpoly_component_topology(source)
    object.__setattr__(tampered, "_projection_bytes", b"{}")
    with pytest.raises(MmcifNonpolyComponentTopologyError) as stale:
        write_mmcif_nonpoly_component_topology(tampered)
    assert stale.value.code == "stale_ingest_binding"

    first = parse_mmcif_nonpoly_component_topology(source)
    second = parse_mmcif_nonpoly_component_topology(source)
    for name in (
        "_full_source",
        "_source_id",
        "_carrier_source",
        "_carrier_ingest",
        "_carrier_object_id",
        "_component_rows",
        "_component_atom_rows",
        "_component_bond_rows",
        "_projection_bytes",
        "_system_snapshot",
        "_canonical_output",
        "_topology_state_bytes",
        "_source_binding_bytes",
        "_access_binding_bytes",
    ):
        object.__setattr__(first, name, getattr(second, name))
    with pytest.raises(MmcifNonpolyComponentTopologyError) as replacement:
        _ = first.system
    assert replacement.value.code == "stale_ingest_binding"

    other = round_trip_mmcif_nonpoly_component_topology_source(source)
    object.__setattr__(result, "_write_result", other.write_result)
    with pytest.raises(MmcifNonpolyComponentTopologyError) as crosswire:
        _ = result.report
    assert crosswire.value.code == "crosswired_round_trip_artifacts"


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("receipt", "stale_write_receipt_binding"),
        ("write_result", "stale_write_result_binding"),
        ("report", "crosswired_round_trip_artifacts"),
        ("round_trip_result", "crosswired_round_trip_artifacts"),
    ],
)
def test_factory_artifact_anchor_rejects_field_complete_clone(
    kind: str, expected_code: str
) -> None:
    result = round_trip_mmcif_nonpoly_component_topology_source(_single_source())
    original = _factory_artifact_for_kind(result, kind)
    clone = object.__new__(type(original))
    _copy_dataclass_fields(clone, original)

    with pytest.raises(MmcifNonpolyComponentTopologyError) as stale:
        _access_factory_artifact(kind, clone)
    assert stale.value.code == expected_code


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("receipt", "stale_write_receipt_binding"),
        ("write_result", "stale_write_result_binding"),
        ("report", "crosswired_round_trip_artifacts"),
        ("round_trip_result", "crosswired_round_trip_artifacts"),
    ],
)
def test_factory_artifact_anchor_rejects_coherent_whole_artifact_replacement(
    kind: str, expected_code: str
) -> None:
    source = _single_source()
    first = round_trip_mmcif_nonpoly_component_topology_source(source)
    second = round_trip_mmcif_nonpoly_component_topology_source(source)
    target = _factory_artifact_for_kind(first, kind)
    replacement = _factory_artifact_for_kind(second, kind)
    _copy_dataclass_fields(target, replacement)

    with pytest.raises(MmcifNonpolyComponentTopologyError) as stale:
        _access_factory_artifact(kind, target)
    assert stale.value.code == expected_code


def test_generated_linear_component_has_linear_number_of_atoms_and_bonds() -> None:
    atom_count = 256
    atoms: tuple[AtomTemplate, ...] = tuple(
        (f"C{index}", "C", 0, "N") for index in range(1, atom_count + 1)
    )
    bonds: tuple[BondTemplate, ...] = tuple(
        (f"C{index}", f"C{index + 1}", "SING") for index in range(1, atom_count)
    )
    source = _source(
        components=(("LIN", 0, atoms, bonds),),
        instances=(("L", "", "LIN", "1", tuple(atom[0] for atom in atoms)),),
    )
    ingest = parse_mmcif_nonpoly_component_topology(source)
    assert ingest.system.atom_count == atom_count
    assert len(ingest.system.bonds) == atom_count - 1
    assert len(ingest.component_atom_rows) == atom_count
    assert len(ingest.component_bond_rows) == atom_count - 1


def test_repeated_instances_cannot_amplify_bonds_past_materialized_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(topology_module, "MAX_MMCIF_NONPOLY_COMPONENT_BOND_ROWS", 3)
    source = _source(
        components=ALIPHATIC,
        instances=(
            ("L", "", "LIG", "501", ("C1", "O1", "H1")),
            ("L", "", "LIG", "502", ("C1", "O1", "H1")),
        ),
    )
    _assert_error(source, "too_many_materialized_bonds")


def test_source_id_token_and_block_name_limits_fail_closed() -> None:
    source = _single_source()
    with pytest.raises(MmcifNonpolyComponentTopologyError) as source_id_error:
        parse_mmcif_nonpoly_component_topology(source, source_id="x" * 4097)
    assert source_id_error.value.code == "source_id_too_large"

    long_token = source.replace(b"LIG NON-POLYMER 0", b"LIG " + b"X" * 2049 + b" 0", 1)
    _assert_error(long_token, "line_too_long")

    long_block_name = source.replace(
        b"data_component_topology", b"data_" + b"x" * 2044, 1
    )
    _assert_error(long_block_name, "line_too_long")


def test_input_requires_exact_bytes() -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        parse_mmcif_nonpoly_component_topology("not bytes")  # type: ignore[arg-type]
