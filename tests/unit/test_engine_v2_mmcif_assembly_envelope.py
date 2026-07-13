from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import torch

import betelgeuze_engine_v2.molecular.mmcif_assembly_envelope as assembly
from betelgeuze_engine_v2.molecular.mmcif_assembly_envelope import (
    MMCIF_ASSEMBLY_ENVELOPE_VERSION,
    MMCIF_ASSEMBLY_PROFILE_ID,
    MmcifAssemblyEnvelopeError,
    MmcifAssemblyIngestResult,
    MmcifAssemblyRoundTripReport,
    MmcifAssemblyRoundTripResult,
    MmcifAssemblyWriteReceipt,
    MmcifAssemblyWriteResult,
    emit_mmcif_assembly,
    mmcif_assembly_declaration_projection_sha256,
    mmcif_assembly_expanded_state_sha256,
    parse_mmcif_assembly,
    round_trip_mmcif_assembly_source,
    serialize_mmcif_assembly,
)
from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
from betelgeuze_engine_v2.molecular.mmcif_writer import (
    MmcifWriteError,
    write_mmcif,
)
from betelgeuze_engine_v2.molecular.models import UnitCell
from betelgeuze_engine_v2.molecular.pdb_mmcif import parse_mmcif


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_assembly"
)
FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "biological_assembly_correctness_assessed",
    "assembly_declaration_authoritative",
    "crystallographic_symmetry_expanded",
    "pbc_interpreted",
    "bond_topology_interpreted",
    "chemistry_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)


def _payload(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _assert_code(payload: bytes, code: str, *, assembly_id: str = "1") -> None:
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(payload, assembly_id=assembly_id, source_id="fixture")
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    ("fixture", "atom_count", "chain_count", "operator_rows"),
    [
        ("identity_single_chain.cif", 1, 1, 1),
        ("two_copy_translation.cif", 4, 2, 2),
        ("noncommuting_composition.cif", 1, 1, 2),
    ],
)
def test_exact_assembly_envelope_round_trips_stably(
    fixture: str,
    atom_count: int,
    chain_count: int,
    operator_rows: int,
) -> None:
    result = round_trip_mmcif_assembly_source(
        _payload(fixture), assembly_id="1", source_id=fixture
    )

    assert MMCIF_ASSEMBLY_ENVELOPE_VERSION == "1.0.0"
    assert result.source_ingest.expanded_system.atom_count == atom_count
    assert len(result.source_ingest.expanded_system.chains) == chain_count
    assert result.source_ingest.assembly_operator_row_count == operator_rows
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert serialize_mmcif_assembly(result.source_ingest) == result.write_result.payload
    assert result.report.to_dict()["explicit_assembly_round_trip_preserved"] is True
    assert result.source_ingest.declaration_projection_sha256 == (
        mmcif_assembly_declaration_projection_sha256(result.source_ingest)
    )
    assert result.source_ingest.expanded_state_sha256 == (
        mmcif_assembly_expanded_state_sha256(result.source_ingest)
    )
    assert result.source_ingest.to_dict()["profile_id"] == MMCIF_ASSEMBLY_PROFILE_ID
    for document in (
        result.source_ingest.to_dict(),
        result.write_result.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        for field_name in FALSE_AUTHORITY_FIELDS:
            assert document[field_name] is False


def test_expanded_coordinates_and_noncommuting_order_are_bitwise_preserved() -> None:
    translation = round_trip_mmcif_assembly_source(
        _payload("two_copy_translation.cif"), assembly_id="1"
    )
    source = translation.source_ingest.expanded_system
    reparsed = translation.reparsed_ingest.expanded_system
    assert torch.equal(source.coordinates, reparsed.coordinates)
    assert source.coordinates[0, :, 0].tolist() == [1.0, 2.0, 11.0, 12.0]
    assert [chain.chain_id for chain in source.chains] == ["ASM000001", "ASM000002"]

    composed = round_trip_mmcif_assembly_source(
        _payload("noncommuting_composition.cif"), assembly_id="1"
    )
    assert composed.source_ingest.expanded_system.coordinates[0, 0].tolist() == [
        10.0,
        1.0,
        0.0,
    ]


def test_output_retains_asu_rows_and_does_not_flatten_expanded_atoms() -> None:
    ingest = parse_mmcif_assembly(
        _payload("two_copy_translation.cif"), assembly_id="1"
    )
    output = emit_mmcif_assembly(ingest).payload
    block = parse_cif_block(output.decode("ascii"))
    atom_loop = next(loop for loop in block.loops if "_atom_site" in loop.categories)
    assert len(atom_loop.rows) == 2
    assert ingest.expanded_system.atom_count == 4
    assert block.categories == (
        "_entity",
        "_struct_asym",
        "_pdbx_struct_assembly",
        "_pdbx_struct_assembly_gen",
        "_pdbx_struct_oper_list",
        "_atom_site",
    )
    explicit = parse_mmcif(output, assembly_id="1")
    assert explicit.system.atom_count == 4
    assert torch.equal(explicit.system.coordinates, ingest.expanded_system.coordinates)


def test_base_parser_writer_contract_remains_unchanged() -> None:
    payload = _payload("identity_single_chain.cif")
    deferred = parse_mmcif(payload)
    assert deferred.coverage.assembly_status == "present_not_requested"
    with pytest.raises(MmcifWriteError) as exc_info:
        write_mmcif(deferred.system)
    assert exc_info.value.code == "unsupported_assembly"

    expanded = parse_mmcif(payload, assembly_id="1")
    with pytest.raises(MmcifWriteError) as exc_info:
        write_mmcif(expanded.system)
    assert exc_info.value.code == "unsupported_assembly"


def test_uncertain_operator_is_an_explicit_failure_corpus_row() -> None:
    _assert_code(
        _payload("failure_numeric_uncertainty.cif"),
        "assembly_numeric_uncertainty_unsupported",
    )


def test_unknown_operator_asym_and_nonrigid_transform_fail_closed() -> None:
    payload = _payload("identity_single_chain.cif")
    _assert_code(
        payload.replace(b"1 1 A\n#", b"1 9 A\n#", 1),
        "unknown_assembly_operator_id",
    )
    _assert_code(
        payload.replace(b"1 1 A\n#", b"1 1 Z\n#", 1),
        "unknown_assembly_asym_id",
    )
    _assert_code(
        payload.replace(
            b"1 1 0 0 0 1 0 0 0 1 0 0 0",
            b"1 2 0 0 0 1 0 0 0 1 0 0 0",
        ),
        "non_rigid_assembly_operator",
    )


def test_exact_surface_rejects_extra_headers_scalars_quoting_and_wrong_id() -> None:
    payload = _payload("identity_single_chain.cif")
    extra_header = payload.replace(
        b"_pdbx_struct_assembly.id\n1\n#",
        b"_pdbx_struct_assembly.id\n_pdbx_struct_assembly.details\n1 generated\n#",
    )
    _assert_code(extra_header, "unsupported_category_headers")

    scalar = payload.replace(
        b"loop_\n_pdbx_struct_assembly.id\n1\n#",
        b"_pdbx_struct_assembly.id 1\n#",
    )
    _assert_code(scalar, "unsupported_scalar_items")

    quoted = payload.replace(b"1 1 A\n#", b"'1' 1 A\n#", 1)
    _assert_code(quoted, "unsupported_token_quoting")
    _assert_code(payload, "assembly_id_mismatch", assembly_id="2")


def test_category_order_and_multimodel_carrier_fail_closed() -> None:
    payload = _payload("identity_single_chain.cif")
    entity = (
        b"loop_\n_entity.id\n_entity.type\n1 polymer\n#\n"
    )
    struct_asym = (
        b"loop_\n_struct_asym.id\n_struct_asym.entity_id\nA 1\n#\n"
    )
    swapped = payload.replace(entity + struct_asym, struct_asym + entity)
    _assert_code(swapped, "unsupported_category_surface")

    multimodel = payload.replace(
        b"ATOM 1 C CA . GLY A 1 1 ? 1 2 3 1.0 20.0 ? 1 GLY AX CA 1\n#",
        b"ATOM 1 C CA . GLY A 1 1 ? 1 2 3 1.0 20.0 ? 1 GLY AX CA 1\n"
        b"ATOM 2 C CA . GLY A 1 1 ? 2 2 3 1.0 20.0 ? 1 GLY AX CA 2\n#",
    )
    _assert_code(multimodel, "unsupported_model_id")


def test_resource_and_source_id_caps_precede_nested_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload("identity_single_chain.cif")
    monkeypatch.setattr(assembly, "MAX_MMCIF_ASSEMBLY_ENVELOPE_GENERATOR_ROWS", 0)
    _assert_code(payload, "assembly_generator_limit_exceeded")

    monkeypatch.setattr(assembly, "MAX_MMCIF_ASSEMBLY_ENVELOPE_GENERATOR_ROWS", 256)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            payload,
            assembly_id="1",
            source_id="x" * (
                assembly.MAX_MMCIF_ASSEMBLY_ENVELOPE_SOURCE_ID_BYTES + 1
            ),
        )
    assert exc_info.value.code == "source_id_limit_exceeded"


def test_canonical_output_byte_cap_is_preflighted_during_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload("identity_single_chain.cif")
    monkeypatch.setattr(
        assembly, "MAX_MMCIF_ASSEMBLY_ENVELOPE_INPUT_BYTES", len(payload)
    )
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(payload, assembly_id="1", source_id="output-cap")
    assert exc_info.value.code == "assembly_output_byte_limit_exceeded"


def test_ingest_is_factory_only_and_stale_hidden_state_is_rejected() -> None:
    with pytest.raises(TypeError):
        MmcifAssemblyIngestResult(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MmcifAssemblyWriteReceipt({})
    with pytest.raises(TypeError):
        MmcifAssemblyWriteResult(b"", None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MmcifAssemblyRoundTripReport({})
    with pytest.raises(TypeError):
        MmcifAssemblyRoundTripResult(None, None, None, None, None)  # type: ignore[arg-type]

    ingest = parse_mmcif_assembly(
        _payload("identity_single_chain.cif"), assembly_id="1"
    )
    object.__setattr__(
        ingest,
        "_components",
        replace(ingest._components, assembly_id="forged"),
    )
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        emit_mmcif_assembly(ingest)
    assert exc_info.value.code in {"assembly_id_mismatch", "stale_or_crosswired_ingest"}


def test_distinct_assembly_declarations_have_distinct_bound_projections() -> None:
    identity = parse_mmcif_assembly(
        _payload("identity_single_chain.cif"), assembly_id="1"
    )
    translated = parse_mmcif_assembly(
        _payload("two_copy_translation.cif"), assembly_id="1"
    )
    assert (
        identity.declaration_projection_sha256
        != translated.declaration_projection_sha256
    )
    assert identity.expanded_state_sha256 != translated.expanded_state_sha256
    assert identity.expanded_topology_sha256 != translated.expanded_topology_sha256


def test_public_argument_types_are_strict() -> None:
    payload = _payload("identity_single_chain.cif")
    with pytest.raises(TypeError):
        parse_mmcif_assembly(payload, assembly_id=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_assembly("not-bytes", assembly_id="1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_assembly(payload, assembly_id="1", source_id=1)  # type: ignore[arg-type]


def test_base_parser_pedigree_and_negative_authority_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        provenance = replace(
            result.system.provenance,
            parser_version="9.9.9",
            preparation_ready=True,
            claim_safe=True,
        )
        return replace(
            result,
            system=replace(result.system, provenance=provenance),
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="pedigree",
        )
    assert exc_info.value.code == "base_mmcif_pedigree_mismatch"


def test_nested_base_coverage_authority_mirror_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        metadata = assembly._plain(result.system.provenance.metadata)
        metadata["coverage"]["preparation_ready"] = True
        metadata["coverage"]["claim_safe"] = True
        provenance = replace(result.system.provenance, metadata=metadata)
        return replace(
            result,
            system=replace(result.system, provenance=provenance),
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="nested-coverage",
        )
    assert exc_info.value.code == "base_mmcif_pedigree_mismatch"


def test_single_model_id1_provenance_is_bound_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        metadata = assembly._plain(result.system.provenance.metadata)
        metadata["model_ids"] = [2]
        provenance = replace(result.system.provenance, metadata=metadata)
        return replace(result, system=replace(result.system, provenance=provenance))

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="model-id",
        )
    assert exc_info.value.code == "base_mmcif_pedigree_mismatch"


def test_base_assembly_semantic_mirror_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        metadata = assembly._plain(result.system.metadata)
        metadata["mmcif"]["coordinate_scope"] = "deposited_asymmetric_unit"
        metadata["mmcif"]["assembly"]["status"] = "present_not_requested"
        return replace(
            result,
            system=replace(result.system, metadata=metadata),
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="semantic-mirror",
        )
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_atom_assembly_instance_full_mapping_is_bound_and_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif
    payload = _payload("identity_single_chain.cif")
    normal = real_parse(payload, assembly_id="1")
    atoms = []
    for atom in normal.system.atoms:
        metadata = assembly._plain(atom.metadata)
        metadata["assembly_instance"]["assembly_id"] = "FORGED"
        metadata["assembly_instance"]["output_chain_id"] = "FORGED"
        atoms.append(replace(atom, metadata=metadata))
    forged_system = replace(normal.system, atoms=tuple(atoms))
    assert assembly._sha256_document(
        assembly._expanded_state_document(normal.system, assembly_id="1")
    ) != assembly._sha256_document(
        assembly._expanded_state_document(forged_system, assembly_id="1")
    )

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        return replace(result, system=replace(result.system, atoms=tuple(atoms)))

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(payload, assembly_id="1", source_id="atom-pointer")
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_periodic_cell_and_coordinate_unit_are_bound_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif
    payload = _payload("identity_single_chain.cif")
    normal = real_parse(payload, assembly_id="1")
    forged_system = replace(
        normal.system,
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    with pytest.raises(MmcifAssemblyEnvelopeError) as projection_exc:
        assembly._expanded_state_document(forged_system, assembly_id="1")
    assert projection_exc.value.code == "unsupported_periodic_state"

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        return replace(result, system=replace(result.system, cell=forged_system.cell))

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(payload, assembly_id="1", source_id="periodic-cell")
    assert exc_info.value.code == "base_mmcif_pedigree_mismatch"


def test_raw_plan_is_cross_checked_against_full_instance_transforms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        metadata = assembly._plain(result.system.metadata)
        ledger = metadata["mmcif"]["assembly"]
        ledger["generators"][0]["operation_sequences"] = [["2"], ["1"]]
        ledger["instances"][1]["operation_sequence"] = ["1"]
        ledger["instances"][1]["rotation"] = [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        ledger["instances"][1]["translation"] = [999.0, 0.0, 0.0]
        ledger["instances"][1]["source_atom_count"] = 999
        return replace(result, system=replace(result.system, metadata=metadata))

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("two_copy_translation.cif"),
            assembly_id="1",
            source_id="forged-plan",
        )
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_source_atom_site_id_is_cross_checked_against_carrier_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        atoms = []
        for atom in result.system.atoms:
            metadata = assembly._plain(atom.metadata)
            metadata["mmcif"]["source_atom_site_id"] = "FORGED"
            atoms.append(replace(atom, metadata=metadata))
        return replace(result, system=replace(result.system, atoms=tuple(atoms)))

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="forged-source-atom",
        )
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_coverage_and_provenance_mirrors_are_bound_to_live_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        coverage = replace(
            result.coverage,
            atom_count=999,
            chain_count=999,
            canonical_topology_sha256="0" * 64,
        )
        metadata = assembly._plain(result.system.provenance.metadata)
        metadata["coverage"] = coverage.to_dict()
        metadata["canonical_topology_sha256"] = "0" * 64
        provenance = replace(result.system.provenance, metadata=metadata)
        return replace(
            result,
            system=replace(result.system, provenance=provenance),
            coverage=coverage,
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="forged-coverage",
        )
    assert exc_info.value.code == "base_mmcif_pedigree_mismatch"


def test_source_asym_pointer_mirror_is_bound_to_raw_generator_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        system_metadata = assembly._plain(result.system.metadata)
        system_metadata["mmcif"]["assembly"]["instances"][0][
            "source_label_asym_id"
        ] = "Z"
        chains = []
        for chain in result.system.chains:
            metadata = assembly._plain(chain.metadata)
            metadata["assembly_instance"]["source_label_asym_id"] = "Z"
            chains.append(replace(chain, metadata=metadata))
        atoms = []
        for atom in result.system.atoms:
            metadata = assembly._plain(atom.metadata)
            metadata["assembly_instance"]["source_label_asym_id"] = "Z"
            atoms.append(replace(atom, metadata=metadata))
        return replace(
            result,
            system=replace(
                result.system,
                metadata=system_metadata,
                chains=tuple(chains),
                atoms=tuple(atoms),
            ),
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="forged-source-asym",
        )
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_expanded_atom_topology_is_exactly_copied_from_carrier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        atoms = tuple(
            replace(
                atom,
                altloc="X",
                isotope_mass_number=13,
                atom_map=7,
                stereo="R",
            )
            for atom in result.system.atoms
        )
        system = replace(result.system, atoms=atoms)
        topology_sha256 = assembly.canonical_topology_sha256(system)
        coverage = replace(
            result.coverage,
            canonical_topology_sha256=topology_sha256,
        )
        provenance_metadata = assembly._plain(system.provenance.metadata)
        provenance_metadata["coverage"] = coverage.to_dict()
        provenance_metadata["canonical_topology_sha256"] = topology_sha256
        provenance = replace(system.provenance, metadata=provenance_metadata)
        return replace(
            result,
            system=replace(system, provenance=provenance),
            coverage=coverage,
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="forged-atom-topology",
        )
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_expanded_residue_and_chain_topology_is_exactly_copied_from_carrier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = assembly.parse_mmcif

    def forged_parse(*args: object, **kwargs: object) -> object:
        result = real_parse(*args, **kwargs)
        residues = tuple(
            replace(residue, sequence_number=999, insertion_code="X")
            for residue in result.system.residues
        )
        chains = tuple(
            replace(chain, entity_id="FORGED") for chain in result.system.chains
        )
        system = replace(result.system, residues=residues, chains=chains)
        topology_sha256 = assembly.canonical_topology_sha256(system)
        coverage = replace(
            result.coverage,
            canonical_topology_sha256=topology_sha256,
        )
        provenance_metadata = assembly._plain(system.provenance.metadata)
        provenance_metadata["coverage"] = coverage.to_dict()
        provenance_metadata["canonical_topology_sha256"] = topology_sha256
        provenance = replace(system.provenance, metadata=provenance_metadata)
        return replace(
            result,
            system=replace(system, provenance=provenance),
            coverage=coverage,
        )

    monkeypatch.setattr(assembly, "parse_mmcif", forged_parse)
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        parse_mmcif_assembly(
            _payload("identity_single_chain.cif"),
            assembly_id="1",
            source_id="forged-residue-chain-topology",
        )
    assert exc_info.value.code == "base_mmcif_assembly_semantic_mismatch"


def test_nested_evidence_views_are_detached_from_stored_components() -> None:
    ingest = parse_mmcif_assembly(
        _payload("identity_single_chain.cif"), assembly_id="1"
    )
    before = ingest.to_dict()

    expanded = ingest._components.expanded_document
    expanded["canonical_topology_sha256"] = "0" * 64
    expanded["preparation_ready"] = True
    declaration = ingest._components.declaration_document
    declaration["categories"][0]["rows"][0][0] = "forged"
    rows = ingest._components.rows_by_category
    rows["_pdbx_struct_assembly"] = (("forged",),)

    assert ingest.to_dict() == before
    assert ingest.expanded_topology_sha256 != "0" * 64
    assert ingest.to_dict()["preparation_ready"] is False


def test_receipt_and_report_reject_forged_claim_documents() -> None:
    result = round_trip_mmcif_assembly_source(
        _payload("identity_single_chain.cif"),
        assembly_id="1",
        source_id="forgery",
    )
    empty_payload = b""
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        MmcifAssemblyWriteReceipt(
            assembly._receipt_document(
                result.source_ingest._components,
                empty_payload,
            ),
            components=result.source_ingest._components,
            payload=empty_payload,
            _factory_token=assembly._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "invalid_write_payload"

    receipt_document = result.write_result.receipt.to_dict()
    receipt_document.pop("receipt_sha256")
    receipt_document["claim_safe"] = True
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        MmcifAssemblyWriteReceipt(
            receipt_document,
            components=result.source_ingest._components,
            payload=result.write_result.payload,
            _factory_token=assembly._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "invalid_write_receipt"

    report_document = result.report.to_dict()
    report_document.pop("report_sha256")
    report_document["claim_safe"] = True
    with pytest.raises(MmcifAssemblyEnvelopeError) as exc_info:
        MmcifAssemblyRoundTripReport(
            report_document,
            source=result.source_ingest,
            reparsed=result.reparsed_ingest,
            write_result=result.write_result,
            reemitted_write_result=result.reemitted_write_result,
            _factory_token=assembly._FACTORY_TOKEN,
        )
    assert exc_info.value.code == "crosswired_round_trip_artifacts"


def test_report_rejects_receipt_source_and_reparse_crosswires() -> None:
    payload = _payload("identity_single_chain.cif")
    source = parse_mmcif_assembly(payload, assembly_id="1", source_id="same")
    commented = payload.replace(
        b"data_identity_single_chain\n",
        b"data_identity_single_chain\n# alternate source comment\n",
        1,
    )
    other = parse_mmcif_assembly(commented, assembly_id="1", source_id="same")
    source_write = emit_mmcif_assembly(source)
    other_write = emit_mmcif_assembly(other)
    assert source_write.payload == other_write.payload

    reparsed = parse_mmcif_assembly(
        source_write.payload,
        assembly_id="1",
        source_id="same",
    )
    second = emit_mmcif_assembly(reparsed)
    receipt_crosswire = assembly._report_document(
        source,
        reparsed,
        other_write,
        second,
    )
    assert receipt_crosswire["write_receipt_source_bound"] is False
    assert receipt_crosswire["explicit_assembly_round_trip_preserved"] is False
    with pytest.raises(MmcifAssemblyEnvelopeError):
        MmcifAssemblyRoundTripReport(
            receipt_crosswire,
            source=source,
            reparsed=reparsed,
            write_result=other_write,
            reemitted_write_result=second,
            _factory_token=assembly._FACTORY_TOKEN,
        )

    comment_reparsed = parse_mmcif_assembly(
        commented,
        assembly_id="1",
        source_id="same",
    )
    comment_second = emit_mmcif_assembly(comment_reparsed)
    source_crosswire = assembly._report_document(
        source,
        comment_reparsed,
        source_write,
        comment_second,
    )
    assert source_crosswire["emitted_source_reparsed_exact"] is False
    assert source_crosswire["explicit_assembly_round_trip_preserved"] is False

    different_id = parse_mmcif_assembly(
        source_write.payload,
        assembly_id="1",
        source_id="different",
    )
    different_second = emit_mmcif_assembly(different_id)
    identity_crosswire = assembly._report_document(
        source,
        different_id,
        source_write,
        different_second,
    )
    assert identity_crosswire["source_id_equal"] is False
    assert identity_crosswire["record_state_equal"] is False
    assert identity_crosswire["explicit_assembly_round_trip_preserved"] is False


def test_canonical_assembly_row_line_boundary_is_checked_at_parse() -> None:
    payload = _payload("identity_single_chain.cif")
    original = b"1 1 0 0 0 1 0 0 0 1 0 0 0"

    exact_numeric = b"1." + (b"0" * 2022)
    exact_row = b"\n".join(
        (b"1", exact_numeric, b"0", b"0", b"0", b"1", b"0", b"0", b"0", b"1", b"0", b"0", b"0")
    )
    exact = payload.replace(original, exact_row, 1)
    exact_ingest = parse_mmcif_assembly(exact, assembly_id="1")
    emitted = emit_mmcif_assembly(exact_ingest).payload
    assert max(map(len, emitted.decode("ascii").splitlines())) == 2048

    too_long_numeric = b"1." + (b"0" * 2023)
    too_long_row = exact_row.replace(exact_numeric, too_long_numeric, 1)
    _assert_code(
        payload.replace(original, too_long_row, 1),
        "assembly_output_line_limit_exceeded",
    )
