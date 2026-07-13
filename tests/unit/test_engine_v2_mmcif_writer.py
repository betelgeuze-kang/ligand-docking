from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import math
from pathlib import Path
import struct
import sys

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    Bond,
    MMCIF_REPRESENTABLE_STATE_SCHEMA_ID,
    MMCIF_ROUND_TRIP_REPORT_SCHEMA_ID,
    MMCIF_WRITER_VERSION,
    MMCIF_WRITE_RECEIPT_SCHEMA_ID,
    MmcifRoundTripReport,
    MmcifRoundTripResult,
    MmcifWriteError,
    MmcifWriteReceipt,
    MmcifWriteResult,
    StructureParseError,
    UnitCell,
    canonical_all_atom_snapshot_digest,
    canonical_topology_sha256,
    mmcif_representable_state_sha256,
    parse_mmcif,
    parser_observation_sha256,
    round_trip_mmcif_source,
    serialize_mmcif,
    write_mmcif,
)
from betelgeuze_engine_v2.molecular import mmcif_writer as writer_module


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MINI_PROTEIN = FIXTURES / "tier_beta" / "mini_protein.cif"

CORE_HEADERS = (
    "_atom_site.group_PDB",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_seq_id",
    "_atom_site.Cartn_x",
    "_atom_site.Cartn_y",
    "_atom_site.Cartn_z",
    "_atom_site.pdbx_PDB_model_num",
)
FORMAL_CHARGE_HEADER = "_atom_site.pdbx_formal_charge"
FORMAL_CHARGE_HEADERS = (*CORE_HEADERS, FORMAL_CHARGE_HEADER)
INSERTION_CODE_HEADER = "_atom_site.pdbx_PDB_ins_code"
INSERTION_CODE_HEADERS = (*CORE_HEADERS, INSERTION_CODE_HEADER)
FORMAL_CHARGE_INSERTION_CODE_HEADERS = (
    *CORE_HEADERS,
    FORMAL_CHARGE_HEADER,
    INSERTION_CODE_HEADER,
)
OCCUPANCY_HEADER = "_atom_site.occupancy"
OCCUPANCY_HEADERS = (*CORE_HEADERS, OCCUPANCY_HEADER)
B_FACTOR_HEADER = "_atom_site.B_iso_or_equiv"
OCCUPANCY_B_FACTOR_HEADERS = (
    *CORE_HEADERS,
    OCCUPANCY_HEADER,
    B_FACTOR_HEADER,
)
COMMON_CORE21_HEADERS = (
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
)
COMMON_CORE21_PROFILE = "pdbx_common_core21_complete_label_auth_entity_identity/1.0.0"
COMMON_CATEGORY_PROFILE = (
    "exact_entity_struct_asym_atom_site_three_loop_categories/1.0.0"
)
IDENTITY_SCHEMA = "betelgeuze.mmcif_label_auth_entity_identity_projection/1.0.0"


def _row(
    atom_id: str | int = "1",
    *,
    group: str = "ATOM",
    element: str = "C",
    atom_name: str = "CA",
    residue_name: str = "GLY",
    chain_id: str = "A",
    residue_number: str | int = "1",
    x: str | float = "0.0",
    y: str | float = "0.0",
    z: str | float = "0.0",
    model_id: str | int = "1",
    extra_values: tuple[str, ...] = (),
) -> str:
    return " ".join(
        (
            group,
            str(atom_id),
            element,
            atom_name,
            residue_name,
            chain_id,
            str(residue_number),
            str(x),
            str(y),
            str(z),
            str(model_id),
            *extra_values,
        )
    )


def _loop(headers: tuple[str, ...], rows: tuple[str, ...]) -> str:
    return "\n".join(("loop_", *headers, *rows, "#"))


def _document(
    rows: tuple[str, ...] = (_row(),),
    *,
    headers: tuple[str, ...] = CORE_HEADERS,
    data_name: str = "core",
    sections: tuple[str, ...] = (),
) -> bytes:
    return (
        "\n".join(
            (
                f"data_{data_name}",
                "#",
                *sections,
                _loop(headers, rows),
            )
        )
        + "\n"
    ).encode("ascii")


def _optional_source(header: str, value: str) -> bytes:
    return _document(
        (_row(extra_values=(value,)),),
        headers=(*CORE_HEADERS, header),
    )


def _formal_charge_source(
    value: str,
    *,
    model_id: str | int = "1",
    atom_id: str | int = "1",
    atom_name: str = "CA",
    residue_number: str | int = "1",
    data_name: str = "formal-charge",
) -> bytes:
    return _document(
        (
            _row(
                atom_id,
                atom_name=atom_name,
                residue_number=residue_number,
                model_id=model_id,
                extra_values=(value,),
            ),
        ),
        headers=FORMAL_CHARGE_HEADERS,
        data_name=data_name,
    )


def _insertion_code_source(
    value: str,
    *,
    charge: str | None = None,
    atom_id: str | int = "1",
    atom_name: str = "CA",
    residue_number: str | int = "1",
    data_name: str = "insertion-code",
) -> bytes:
    headers = (
        INSERTION_CODE_HEADERS
        if charge is None
        else FORMAL_CHARGE_INSERTION_CODE_HEADERS
    )
    extra_values = (value,) if charge is None else (charge, value)
    return _document(
        (
            _row(
                atom_id,
                atom_name=atom_name,
                residue_number=residue_number,
                extra_values=extra_values,
            ),
        ),
        headers=headers,
        data_name=data_name,
    )


def _occupancy_source(
    value: str,
    *,
    atom_id: str | int = "1",
    atom_name: str = "CA",
    residue_number: str | int = "1",
    data_name: str = "occupancy",
) -> bytes:
    return _document(
        (
            _row(
                atom_id,
                atom_name=atom_name,
                residue_number=residue_number,
                extra_values=(value,),
            ),
        ),
        headers=OCCUPANCY_HEADERS,
        data_name=data_name,
    )


def _occupancy_b_factor_source(
    occupancy: str,
    b_factor: str,
    *,
    atom_id: str | int = "1",
    atom_name: str = "CA",
    residue_number: str | int = "1",
    data_name: str = "occupancy-b-factor",
) -> bytes:
    return _document(
        (
            _row(
                atom_id,
                atom_name=atom_name,
                residue_number=residue_number,
                extra_values=(occupancy, b_factor),
            ),
        ),
        headers=OCCUPANCY_B_FACTOR_HEADERS,
        data_name=data_name,
    )


def _core21_row(
    atom_id: str | int,
    atom_name: str,
    *,
    group: str = "ATOM",
    element: str = "C",
    comp_id: str = "GLY",
    label_asym_id: str = "A",
    label_entity_id: str = "1",
    label_seq_id: str = "1",
    label_alt_id: str = ".",
    insertion_code: str = "?",
    x: str = "0.0",
    y: str = "0.0",
    z: str = "0.0",
    occupancy: str = "1.0",
    b_factor: str = "20.0",
    formal_charge: str = "?",
    auth_seq_id: str = "10",
    auth_comp_id: str | None = None,
    auth_asym_id: str = "X",
    auth_atom_id: str | None = None,
    model_id: str = "1",
) -> str:
    return " ".join(
        (
            group,
            str(atom_id),
            element,
            atom_name,
            label_alt_id,
            comp_id,
            label_asym_id,
            label_entity_id,
            label_seq_id,
            insertion_code,
            x,
            y,
            z,
            occupancy,
            b_factor,
            formal_charge,
            auth_seq_id,
            comp_id if auth_comp_id is None else auth_comp_id,
            auth_asym_id,
            atom_name if auth_atom_id is None else auth_atom_id,
            model_id,
        )
    )


def _common_core21_source(
    rows: tuple[str, ...],
    *,
    entity_rows: tuple[str, ...] = ("1 polymer",),
    struct_asym_rows: tuple[str, ...] = ("A 1",),
    data_name: str = "common-core21",
    category_order: tuple[str, ...] = ("entity", "struct_asym", "atom_site"),
) -> bytes:
    sections = {
        "entity": _loop(("_entity.id", "_entity.type"), entity_rows),
        "struct_asym": _loop(
            ("_struct_asym.id", "_struct_asym.entity_id"),
            struct_asym_rows,
        ),
        "atom_site": _loop(COMMON_CORE21_HEADERS, rows),
    }
    return (
        "\n".join(
            (f"data_{data_name}", "#", *(sections[key] for key in category_order))
        )
        + "\n"
    ).encode("ascii")


def _assert_write_error(system, code: str) -> None:
    with pytest.raises(MmcifWriteError) as exc_info:
        write_mmcif(system)
    assert exc_info.value.code == code


def _assert_parse_error(source: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        round_trip_mmcif_source(source)
    assert exc_info.value.source_format == "mmcif"
    assert exc_info.value.code == code


def _replace_atom(system, **changes):
    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], **changes)
    return replace(system, atoms=tuple(atoms))


def _replace_residue(system, **changes):
    residues = list(system.residues)
    residues[0] = replace(residues[0], **changes)
    return replace(system, residues=tuple(residues))


def _replace_provenance_metadata(system, key: str, value):
    metadata = dict(system.provenance.metadata)
    metadata[key] = value
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def _replace_mmcif_metadata(system, key: str, value):
    metadata = dict(system.metadata)
    mmcif = dict(metadata["mmcif"])
    mmcif[key] = value
    metadata["mmcif"] = mmcif
    return replace(system, metadata=metadata)


def _binary64(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _public_artifact_kwargs(artifact) -> dict[str, object]:
    return {
        field.name: getattr(artifact, field.name)
        for field in fields(artifact)
        if not field.name.startswith("_")
    }


def _attached_parser_owned_digests(system) -> tuple[str, ...]:
    provenance_metadata = system.provenance.metadata
    mmcif_metadata = system.metadata["mmcif"]
    return (
        system.provenance.source_sha256,
        provenance_metadata["canonical_topology_sha256"],
        provenance_metadata["parser_observation_sha256"],
        provenance_metadata["source_missingness_evidence_sha256"],
        mmcif_metadata["source_reported_missingness"]["report_sha256"],
    )


def _replace_atom_mmcif_model_id(system, container: str, value):
    atom_metadata = dict(system.atoms[0].metadata)
    mmcif_metadata = dict(atom_metadata["mmcif"])
    entries = list(mmcif_metadata[container])
    entry = dict(entries[0])
    entry["model_id"] = value
    entries[0] = entry
    mmcif_metadata[container] = entries
    atom_metadata["mmcif"] = mmcif_metadata
    return _replace_atom(system, metadata=atom_metadata)


def _replace_mmcif_mapping_value(system, section: str, key: str, value):
    section_value = dict(system.metadata["mmcif"][section])
    section_value[key] = value
    return _replace_mmcif_metadata(system, section, section_value)


def _replace_inventory_value(system, key: str, value):
    inventory = list(system.metadata["mmcif"]["category_inventory"])
    entry = dict(inventory[0])
    entry[key] = value
    inventory[0] = entry
    return _replace_mmcif_metadata(system, "category_inventory", inventory)


def _replace_charge_payloads(
    system,
    *,
    atom_payload: dict[str, object] | None = None,
    model_payload: dict[str, object] | None = None,
    remove_atom: bool = False,
    remove_model: bool = False,
):
    atom_metadata = dict(system.atoms[0].metadata)
    mmcif = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif["atom_site"])
    if remove_atom:
        atom_site.pop(FORMAL_CHARGE_HEADER)
    elif atom_payload is not None:
        atom_site[FORMAL_CHARGE_HEADER] = atom_payload
    mmcif["atom_site"] = atom_site

    entries = list(mmcif["atom_site_by_model"])
    entry = dict(entries[0])
    values = dict(entry["values"])
    if remove_model:
        values.pop(FORMAL_CHARGE_HEADER)
    elif model_payload is not None:
        values[FORMAL_CHARGE_HEADER] = model_payload
    entry["values"] = values
    entries[0] = entry
    mmcif["atom_site_by_model"] = entries
    atom_metadata["mmcif"] = mmcif
    return _replace_atom(system, metadata=atom_metadata)


def _replace_insertion_payloads(
    system,
    *,
    atom_payload: dict[str, object] | None = None,
    model_payload: dict[str, object] | None = None,
    remove_atom: bool = False,
    remove_model: bool = False,
):
    atom_metadata = dict(system.atoms[0].metadata)
    mmcif = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif["atom_site"])
    if remove_atom:
        atom_site.pop(INSERTION_CODE_HEADER.lower())
    elif atom_payload is not None:
        atom_site[INSERTION_CODE_HEADER.lower()] = atom_payload
    mmcif["atom_site"] = atom_site

    entries = list(mmcif["atom_site_by_model"])
    entry = dict(entries[0])
    values = dict(entry["values"])
    if remove_model:
        values.pop(INSERTION_CODE_HEADER.lower())
    elif model_payload is not None:
        values[INSERTION_CODE_HEADER.lower()] = model_payload
    entry["values"] = values
    entries[0] = entry
    mmcif["atom_site_by_model"] = entries
    atom_metadata["mmcif"] = mmcif
    return _replace_atom(system, metadata=atom_metadata)


def _replace_occupancy_payloads(
    system,
    *,
    atom_payload: dict[str, object] | None = None,
    model_payload: dict[str, object] | None = None,
    remove_atom: bool = False,
    remove_model: bool = False,
):
    atom_metadata = dict(system.atoms[0].metadata)
    mmcif = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif["atom_site"])
    if remove_atom:
        atom_site.pop(OCCUPANCY_HEADER)
    elif atom_payload is not None:
        atom_site[OCCUPANCY_HEADER] = atom_payload
    mmcif["atom_site"] = atom_site

    entries = list(mmcif["atom_site_by_model"])
    entry = dict(entries[0])
    values = dict(entry["values"])
    if remove_model:
        values.pop(OCCUPANCY_HEADER)
    elif model_payload is not None:
        values[OCCUPANCY_HEADER] = model_payload
    entry["values"] = values
    entries[0] = entry
    mmcif["atom_site_by_model"] = entries
    atom_metadata["mmcif"] = mmcif
    return _replace_atom(system, metadata=atom_metadata)


def _replace_b_factor_payloads(
    system,
    *,
    atom_payload: dict[str, object] | None = None,
    model_payload: dict[str, object] | None = None,
    remove_atom: bool = False,
    remove_model: bool = False,
):
    header = B_FACTOR_HEADER.lower()
    atom_metadata = dict(system.atoms[0].metadata)
    mmcif = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif["atom_site"])
    if remove_atom:
        atom_site.pop(header)
    elif atom_payload is not None:
        atom_site[header] = atom_payload
    mmcif["atom_site"] = atom_site

    entries = list(mmcif["atom_site_by_model"])
    entry = dict(entries[0])
    values = dict(entry["values"])
    if remove_model:
        values.pop(header)
    elif model_payload is not None:
        values[header] = model_payload
    entry["values"] = values
    entries[0] = entry
    mmcif["atom_site_by_model"] = entries
    atom_metadata["mmcif"] = mmcif
    return _replace_atom(system, metadata=atom_metadata)


def _replace_core21_payload(
    system,
    header: str,
    payload: dict[str, object],
    *,
    replace_model_payload: bool = True,
):
    normalized_header = header.lower()
    atom_metadata = dict(system.atoms[0].metadata)
    mmcif = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif["atom_site"])
    atom_site[normalized_header] = payload
    mmcif["atom_site"] = atom_site
    if replace_model_payload:
        entries = list(mmcif["atom_site_by_model"])
        entry = dict(entries[0])
        values = dict(entry["values"])
        values[normalized_header] = payload
        entry["values"] = values
        entries[0] = entry
        mmcif["atom_site_by_model"] = entries
    atom_metadata["mmcif"] = mmcif
    return _replace_atom(system, metadata=atom_metadata)


def _reattach_parser_observation(system):
    return _replace_provenance_metadata(
        system,
        "parser_observation_sha256",
        parser_observation_sha256(system),
    )


def _assert_typed_metadata_rejected(system, mutated) -> None:
    assert _attached_parser_owned_digests(mutated) == (
        _attached_parser_owned_digests(system)
    )
    assert canonical_topology_sha256(mutated) == canonical_topology_sha256(system)
    assert parser_observation_sha256(mutated) == parser_observation_sha256(system)
    assert canonical_all_atom_snapshot_digest(mutated) != (
        canonical_all_atom_snapshot_digest(system)
    )
    with pytest.raises(MmcifWriteError):
        write_mmcif(mutated)


def _forged_receipt_for_payload(result, payload: bytes) -> MmcifWriteReceipt:
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs.update(
        output_source_sha256=hashlib.sha256(payload).hexdigest(),
        output_byte_count=len(payload),
        output_physical_line_count=(payload.count(b"\n") + payload.count(b"\r") + 1),
    )
    return MmcifWriteReceipt(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )


def _noncanonical_payload_variant(payload: bytes, variant: str) -> bytes:
    if variant == "doubled_whitespace":
        return payload.replace(b"ATOM 1", b"ATOM  1", 1)
    if variant == "quoted_token":
        return payload.replace(b"ATOM 1", b"'ATOM' 1", 1)
    if variant == "row_comment":
        return payload.replace(b" 1\n#", b" 1 # forged comment\n#", 1)
    if variant == "crlf":
        return payload.replace(b"\n", b"\r\n")
    if variant == "blank_line":
        return payload.replace(b"\n", b"\n\n", 1)
    if variant == "uppercase_header":
        return payload.replace(
            b"_atom_site.group_pdb",
            b"_ATOM_SITE.GROUP_PDB",
            1,
        )
    if variant == "nonshortest_coordinate":
        return payload.replace(b" 0.0 ", b" 0.000 ", 1)
    raise AssertionError(f"unknown payload variant: {variant}")


def _atom_output_rows(payload: bytes) -> list[list[str]]:
    return [
        line.split()
        for line in payload.decode("ascii").splitlines()
        if line.startswith(("ATOM ", "HETATM "))
    ]


def _entity_sections() -> tuple[str, str]:
    return (
        _loop(("_entity.id", "_entity.type"), ("1 polymer",)),
        _loop(
            ("_struct_asym.id", "_struct_asym.entity_id"),
            ("A 1",),
        ),
    )


def _assembly_sections() -> tuple[str, str, str]:
    operation_headers = (
        "_pdbx_struct_oper_list.id",
        "_pdbx_struct_oper_list.matrix[1][1]",
        "_pdbx_struct_oper_list.matrix[1][2]",
        "_pdbx_struct_oper_list.matrix[1][3]",
        "_pdbx_struct_oper_list.matrix[2][1]",
        "_pdbx_struct_oper_list.matrix[2][2]",
        "_pdbx_struct_oper_list.matrix[2][3]",
        "_pdbx_struct_oper_list.matrix[3][1]",
        "_pdbx_struct_oper_list.matrix[3][2]",
        "_pdbx_struct_oper_list.matrix[3][3]",
        "_pdbx_struct_oper_list.vector[1]",
        "_pdbx_struct_oper_list.vector[2]",
        "_pdbx_struct_oper_list.vector[3]",
    )
    return (
        _loop(("_pdbx_struct_assembly.id",), ("1",)),
        _loop(
            (
                "_pdbx_struct_assembly_gen.assembly_id",
                "_pdbx_struct_assembly_gen.oper_expression",
                "_pdbx_struct_assembly_gen.asym_id_list",
            ),
            ("1 1 A",),
        ),
        _loop(
            operation_headers,
            ("1 1 0 0 0 1 0 0 0 1 0 0 0",),
        ),
    )


def _missingness_section() -> str:
    headers = (
        "_pdbx_unobs_or_zero_occ_residues.id",
        "_pdbx_unobs_or_zero_occ_residues.polymer_flag",
        "_pdbx_unobs_or_zero_occ_residues.occupancy_flag",
        "_pdbx_unobs_or_zero_occ_residues.PDB_model_num",
        "_pdbx_unobs_or_zero_occ_residues.auth_asym_id",
        "_pdbx_unobs_or_zero_occ_residues.auth_comp_id",
        "_pdbx_unobs_or_zero_occ_residues.auth_seq_id",
        "_pdbx_unobs_or_zero_occ_residues.PDB_ins_code",
        "_pdbx_unobs_or_zero_occ_residues.label_asym_id",
        "_pdbx_unobs_or_zero_occ_residues.label_comp_id",
        "_pdbx_unobs_or_zero_occ_residues.label_seq_id",
    )
    return _loop(headers, ("1 Y 1 1 X GLY 2 ? A GLY 2",))


def _cell_section() -> str:
    return "\n".join(
        (
            "_cell.length_a 10.0",
            "_cell.length_b 11.0",
            "_cell.length_c 12.0",
            "_cell.angle_alpha 90.0",
            "_cell.angle_beta 90.0",
            "_cell.angle_gamma 90.0",
            "#",
        )
    )


def test_public_contract_and_mini_protein_normalized_golden() -> None:
    source = MINI_PROTEIN.read_bytes()
    result = round_trip_mmcif_source(source, source_id="tier-beta-mini-protein")

    assert MMCIF_WRITER_VERSION == "1.5.0"
    assert MMCIF_REPRESENTABLE_STATE_SCHEMA_ID == (
        "betelgeuze.mmcif_representable_state/1.5.0"
    )
    assert MMCIF_WRITE_RECEIPT_SCHEMA_ID == ("betelgeuze.mmcif_write_receipt/1.5.0")
    assert MMCIF_ROUND_TRIP_REPORT_SCHEMA_ID == (
        "betelgeuze.mmcif_round_trip_report/1.5.0"
    )
    assert (
        writer_module.MMCIF_LABEL_AUTH_ENTITY_IDENTITY_PROJECTION_SCHEMA_ID
        == IDENTITY_SCHEMA
    )
    assert result.write_result.payload == serialize_mmcif(result.source_ingest.system)
    assert result.write_result.payload == serialize_mmcif(result.reparsed_ingest.system)
    assert hashlib.sha256(result.write_result.payload).hexdigest() == (
        result.write_result.receipt.output_source_sha256
    )
    assert (
        result.write_result.receipt.parent_source_sha256
        == hashlib.sha256(source).hexdigest()
    )
    assert result.write_result.receipt.input_snapshot_sha256 == (
        canonical_all_atom_snapshot_digest(result.source_ingest.system)
    )
    assert result.write_result.receipt.input_topology_sha256 == (
        canonical_topology_sha256(result.source_ingest.system)
    )
    assert result.write_result.receipt.input_representable_state_sha256 == (
        mmcif_representable_state_sha256(result.source_ingest.system)
    )

    receipt = result.write_result.receipt.to_dict()
    assert receipt["schema_id"] == MMCIF_WRITE_RECEIPT_SCHEMA_ID
    assert receipt["atom_site_header_profile"] == "core11"
    assert receipt["atom_site_header_count"] == 11
    assert receipt["output_token_count"] == (
        2 + 11 * (result.source_ingest.system.atom_count + 1)
    )
    assert receipt["source_authentication_status"] == "not_authenticated"
    assert receipt["preparation_ready"] is False
    assert receipt["parameterability_assessed"] is False
    assert receipt["simulation_ready"] is False
    assert receipt["claim_safe"] is False
    assert receipt["receipt_sha256"] == result.write_result.receipt.receipt_sha256

    report = result.report.to_dict()
    assert report["schema_id"] == MMCIF_ROUND_TRIP_REPORT_SCHEMA_ID
    assert report["declared_projection_sha256_equal"] is True
    assert report["canonical_topology_sha256_equal"] is True
    assert report["coordinate_binary64_projection_equal"] is True
    assert report["emitted_source_sha256_and_bytes_stable"] is True
    assert report["full_canonical_snapshot_equality_claimed"] is False
    assert report["dynamic_source_provenance_equality_claimed"] is False
    assert report["claim_safe"] is False
    assert report["report_sha256"] == result.report.report_sha256


def test_common_core21_mixed_label_auth_entity_identity_fixed_point() -> None:
    source = _common_core21_source(
        (
            _core21_row(1, "N", element="N"),
            _core21_row(2, "CA", x="1.25"),
            _core21_row(
                3,
                "SE",
                group="HETATM",
                element="Se",
                comp_id="MSE",
                label_seq_id="2",
                auth_seq_id="11",
            ),
            _core21_row(
                4,
                "C1",
                group="HETATM",
                comp_id="LIG",
                label_asym_id="B",
                label_entity_id="2",
                label_seq_id=".",
                auth_seq_id="L-7",
                auth_asym_id="X",
                formal_charge="+0",
                occupancy="01.000",
                b_factor="-0",
                x="3.0",
            ),
            _core21_row(
                5,
                "O1",
                group="HETATM",
                element="O",
                comp_id="LIG",
                label_asym_id="B",
                label_entity_id="2",
                label_seq_id=".",
                auth_seq_id="L-7",
                auth_asym_id="X",
                formal_charge="-1",
                x="4.0",
            ),
        ),
        entity_rows=("1 polymer", "2 non-polymer"),
        struct_asym_rows=("A 1", "B 2"),
    )
    result = round_trip_mmcif_source(source)
    system = result.source_ingest.system
    receipt = result.write_result.receipt

    assert [(chain.chain_id, chain.entity_id) for chain in system.chains] == [
        ("A", "1"),
        ("B", "2"),
    ]
    assert [tuple(chain.metadata["auth_asym_ids"]) for chain in system.chains] == [
        ("X",),
        ("X",),
    ]
    assert [
        (residue.name, residue.sequence_number, residue.entity_type, residue.hetero)
        for residue in system.residues
    ] == [
        ("GLY", 1, "polymer", False),
        ("MSE", 2, "polymer", True),
        ("LIG", -1, "non_polymer", True),
    ]
    assert receipt.atom_site_header_profile == COMMON_CORE21_PROFILE
    assert receipt.identity_profile == COMMON_CORE21_PROFILE
    assert receipt.category_profile == COMMON_CATEGORY_PROFILE
    assert receipt.identity_projection_schema_id == IDENTITY_SCHEMA
    assert receipt.entity_row_count == 2
    assert receipt.struct_asym_row_count == 2
    assert receipt.complete_auth_row_count == 5
    assert receipt.output_token_count == 8 + 2 * 2 + 2 * 2 + 21 * (5 + 1)
    assert result.report.input_identity_projection_sha256 == (
        result.report.reparsed_identity_projection_sha256
    )
    assert result.write_result.payload == serialize_mmcif(result.reparsed_ingest.system)
    output = result.write_result.payload.decode("ascii")
    assert output.index("_entity.id") < output.index("_struct_asym.id")
    assert output.index("_struct_asym.id") < output.index("_atom_site.group_pdb")
    assert "01.000 -0 +0 L-7 LIG X C1 1" in output


def test_common_core21_category_order_normalizes_but_category_row_order_is_bound() -> (
    None
):
    rows = (
        _core21_row(1, "N", element="N"),
        _core21_row(
            2,
            "C1",
            group="HETATM",
            comp_id="LIG",
            label_asym_id="B",
            label_entity_id="2",
            label_seq_id="?",
            auth_seq_id="A-10",
        ),
    )
    canonical_order = _common_core21_source(
        rows,
        entity_rows=("1 polymer", "2 non-polymer"),
        struct_asym_rows=("A 1", "B 2"),
        data_name="category-order",
    )
    source_order_variant = _common_core21_source(
        rows,
        entity_rows=("1 polymer", "2 non-polymer"),
        struct_asym_rows=("A 1", "B 2"),
        data_name="category-order",
        category_order=("atom_site", "struct_asym", "entity"),
    )
    first = round_trip_mmcif_source(canonical_order)
    second = round_trip_mmcif_source(source_order_variant)
    assert first.write_result.payload == second.write_result.payload
    assert first.report.input_identity_projection_sha256 == (
        second.report.input_identity_projection_sha256
    )

    row_order_variant = round_trip_mmcif_source(
        _common_core21_source(
            rows,
            entity_rows=("2 non-polymer", "1 polymer"),
            struct_asym_rows=("B 2", "A 1"),
            data_name="category-order",
        )
    )
    assert row_order_variant.write_result.payload != first.write_result.payload
    assert row_order_variant.report.input_identity_projection_sha256 != (
        first.report.input_identity_projection_sha256
    )

    declared = round_trip_mmcif_source(
        _common_core21_source(
            (_core21_row(1, "CA"),),
            entity_rows=("1 polymer", "2 non-polymer", "3 water"),
            struct_asym_rows=("A 1", "B 2", "C 3"),
            data_name="declared-crosswire",
        )
    )
    type_swap = round_trip_mmcif_source(
        _common_core21_source(
            (_core21_row(1, "CA"),),
            entity_rows=("1 polymer", "2 water", "3 non-polymer"),
            struct_asym_rows=("A 1", "B 2", "C 3"),
            data_name="declared-crosswire",
        )
    )
    asym_assignment_swap = round_trip_mmcif_source(
        _common_core21_source(
            (_core21_row(1, "CA"),),
            entity_rows=("1 polymer", "2 non-polymer", "3 water"),
            struct_asym_rows=("A 1", "B 3", "C 2"),
            data_name="declared-crosswire",
        )
    )
    assert canonical_topology_sha256(declared.source_ingest.system) == (
        canonical_topology_sha256(type_swap.source_ingest.system)
    )
    assert canonical_topology_sha256(declared.source_ingest.system) == (
        canonical_topology_sha256(asym_assignment_swap.source_ingest.system)
    )
    assert (
        len(
            {
                declared.report.input_identity_projection_sha256,
                type_swap.report.input_identity_projection_sha256,
                asym_assignment_swap.report.input_identity_projection_sha256,
            }
        )
        == 3
    )


def test_common_core21_water_and_nonpoly_synthetic_ordinals_are_exact() -> None:
    source = _common_core21_source(
        (
            _core21_row(
                1,
                "O",
                group="HETATM",
                element="O",
                comp_id="HOH",
                label_asym_id="W",
                label_entity_id="1",
                label_seq_id=".",
                auth_seq_id="W1",
            ),
            _core21_row(
                2,
                "C1",
                group="HETATM",
                comp_id="LIG",
                label_asym_id="L",
                label_entity_id="2",
                label_seq_id="?",
                auth_seq_id="first",
            ),
            _core21_row(
                3,
                "C2",
                group="HETATM",
                comp_id="DRG",
                label_asym_id="L",
                label_entity_id="2",
                label_seq_id=".",
                auth_seq_id="second",
            ),
        ),
        entity_rows=("1 water", "2 non-polymer"),
        struct_asym_rows=("W 1", "L 2"),
    )
    system = round_trip_mmcif_source(source).source_ingest.system
    assert [residue.sequence_number for residue in system.residues] == [-1, -1, -2]
    assert [residue.entity_type for residue in system.residues] == [
        "water",
        "non_polymer",
        "non_polymer",
    ]

    mixed_markers = round_trip_mmcif_source(
        _common_core21_source(
            (
                _core21_row(
                    1,
                    "C1",
                    group="HETATM",
                    comp_id="LIG",
                    label_seq_id=".",
                    auth_seq_id="same",
                ),
                _core21_row(
                    2,
                    "O1",
                    group="HETATM",
                    element="O",
                    comp_id="LIG",
                    label_seq_id="?",
                    auth_seq_id="same",
                ),
            ),
            entity_rows=("1 non-polymer",),
        )
    )
    assert len(mixed_markers.source_ingest.system.residues) == 1
    assert _atom_output_rows(mixed_markers.write_result.payload)[0][8] == "."
    assert _atom_output_rows(mixed_markers.write_result.payload)[1][8] == "?"


def test_common_core21_auth_and_missing_marker_crosswires_are_distinct() -> None:
    base_kwargs = {
        "entity_rows": ("1 polymer",),
        "struct_asym_rows": ("A 1",),
        "data_name": "identity-crosswire",
    }
    auth_x = round_trip_mmcif_source(
        _common_core21_source(
            (_core21_row(1, "CA", auth_asym_id="X", auth_seq_id="10"),),
            **base_kwargs,
        )
    )
    auth_y = round_trip_mmcif_source(
        _common_core21_source(
            (_core21_row(1, "CA", auth_asym_id="Y", auth_seq_id="20"),),
            **base_kwargs,
        )
    )
    question = round_trip_mmcif_source(
        _common_core21_source(
            (
                _core21_row(
                    1,
                    "CA",
                    label_alt_id="?",
                    insertion_code=".",
                    formal_charge=".",
                ),
            ),
            **base_kwargs,
        )
    )
    assert canonical_topology_sha256(auth_x.source_ingest.system) == (
        canonical_topology_sha256(auth_y.source_ingest.system)
    )
    assert auth_x.report.input_identity_projection_sha256 != (
        auth_y.report.input_identity_projection_sha256
    )
    assert auth_x.report.input_identity_projection_sha256 != (
        question.report.input_identity_projection_sha256
    )

    report_kwargs = _public_artifact_kwargs(auth_x.report)
    report_kwargs["reparsed_identity_projection_sha256"] = (
        auth_y.report.reparsed_identity_projection_sha256
    )
    with pytest.raises(ValueError, match="identity-projection hashes"):
        MmcifRoundTripReport(
            **report_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
    with pytest.raises(ValueError, match="cross-consistent"):
        MmcifRoundTripResult(
            source_ingest=auth_x.source_ingest,
            write_result=auth_y.write_result,
            reparsed_ingest=auth_y.reparsed_ingest,
            report=auth_y.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    receipt_kwargs = _public_artifact_kwargs(auth_x.write_result.receipt)
    receipt_kwargs["input_identity_projection_sha256"] = (
        auth_y.write_result.receipt.input_identity_projection_sha256
    )
    forged_receipt = MmcifWriteReceipt(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="identity_projection"):
        MmcifWriteResult(
            payload=auth_x.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_common_core21_partial_auth_and_profile_downgrades_fail_closed() -> None:
    full_row = _core21_row(1, "CA").split()
    auth_atom_index = COMMON_CORE21_HEADERS.index("_atom_site.auth_atom_id")
    partial_headers = tuple(
        header
        for header in COMMON_CORE21_HEADERS
        if header != "_atom_site.auth_atom_id"
    )
    partial_row = " ".join(
        value for index, value in enumerate(full_row) if index != auth_atom_index
    )
    partial = _document(
        (partial_row,),
        headers=partial_headers,
        sections=_entity_sections(),
        data_name="partial-auth",
    )
    _assert_write_error(parse_mmcif(partial).system, "unsupported_atom_site_headers")

    no_categories = _document(
        (_core21_row(1, "CA"),),
        headers=COMMON_CORE21_HEADERS,
        data_name="no-identity-categories",
    )
    _assert_write_error(
        parse_mmcif(no_categories).system,
        "unsupported_preserved_category_payloads",
    )

    legacy_with_categories = _document(
        (_row(),),
        sections=_entity_sections(),
        data_name="legacy-with-identity-categories",
    )
    _assert_write_error(
        parse_mmcif(legacy_with_categories).system,
        "unsupported_category_inventory",
    )


@pytest.mark.parametrize(
    ("entity_rows", "struct_rows", "code"),
    [
        (("1 polymer", "1 polymer"), ("A 1",), "duplicate_entity_id"),
        (("1 polymer",), ("A 2",), "unknown_struct_asym_entity"),
    ],
)
def test_common_core21_duplicate_and_unknown_entity_references_fail_in_parser(
    entity_rows: tuple[str, ...],
    struct_rows: tuple[str, ...],
    code: str,
) -> None:
    _assert_parse_error(
        _common_core21_source(
            (_core21_row(1, "CA"),),
            entity_rows=entity_rows,
            struct_asym_rows=struct_rows,
        ),
        code,
    )


def test_common_core21_raw_auth_category_residue_and_chain_tamper_reject() -> None:
    source = _common_core21_source((_core21_row(1, "CA"),))
    system = parse_mmcif(source).system

    raw_auth_drift = _replace_core21_payload(
        system,
        "_atom_site.auth_asym_id",
        {"value": "Y", "quoted": False, "multiline": False},
    )
    _assert_write_error(raw_auth_drift, "unsupported_auth_identity")

    auth_metadata = dict(system.atoms[0].metadata)
    auth_mmcif = dict(auth_metadata["mmcif"])
    auth_identity = dict(auth_mmcif["auth_identity"])
    auth_identity["seq_id"] = "20"
    auth_mmcif["auth_identity"] = auth_identity
    auth_metadata["mmcif"] = auth_mmcif
    _assert_write_error(
        _replace_atom(system, metadata=auth_metadata),
        "unsupported_auth_identity",
    )

    residue_metadata = dict(system.residues[0].metadata)
    residue_metadata["mmcif_auth_seq_id"] = "20"
    _assert_write_error(
        _replace_residue(system, metadata=residue_metadata),
        "unsupported_residue_metadata",
    )

    chain_metadata = dict(system.chains[0].metadata)
    chain_metadata["auth_asym_ids"] = ["Y"]
    chains = list(system.chains)
    chains[0] = replace(chains[0], metadata=chain_metadata)
    _assert_write_error(
        replace(system, chains=tuple(chains)),
        "unsupported_chain_metadata",
    )

    payloads = list(system.metadata["mmcif"]["preserved_category_payloads"])
    entity_payload = dict(payloads[0])
    entity_loops = list(entity_payload["loops"])
    entity_loop = dict(entity_loops[0])
    entity_rows = [list(row) for row in entity_loop["rows"]]
    entity_rows[0][1] = {"value": "water", "quoted": False, "multiline": False}
    entity_loop["rows"] = entity_rows
    entity_loops[0] = entity_loop
    entity_payload["loops"] = entity_loops
    payloads[0] = entity_payload
    _assert_write_error(
        _replace_mmcif_metadata(system, "preserved_category_payloads", payloads),
        "unsupported_entity_identity",
    )


def test_common_core21_inventory_payload_index_and_header_order_tamper_reject() -> None:
    source = _common_core21_source((_core21_row(1, "CA"),))
    system = parse_mmcif(source).system

    inventory = list(system.metadata["mmcif"]["category_inventory"])
    entry = dict(inventory[0])
    entry["row_count"] = True
    inventory[0] = entry
    _assert_write_error(
        _replace_mmcif_metadata(system, "category_inventory", inventory),
        "unsupported_category_inventory",
    )

    payloads = list(system.metadata["mmcif"]["preserved_category_payloads"])
    entity_payload = dict(payloads[0])
    loops = list(entity_payload["loops"])
    loop = dict(loops[0])
    loop["source_loop_index"] = True
    loops[0] = loop
    entity_payload["loops"] = loops
    payloads[0] = entity_payload
    _assert_write_error(
        _replace_mmcif_metadata(system, "preserved_category_payloads", payloads),
        "unsupported_preserved_category_payloads",
    )

    swapped_headers = list(COMMON_CORE21_HEADERS)
    swapped_headers[16], swapped_headers[17] = swapped_headers[17], swapped_headers[16]
    row = _core21_row(1, "CA").split()
    row[16], row[17] = row[17], row[16]
    swapped = _document(
        (" ".join(row),),
        headers=tuple(swapped_headers),
        sections=_entity_sections(),
        data_name="header-order",
    )
    _assert_write_error(
        parse_mmcif(swapped).system,
        "unsupported_atom_site_headers",
    )


@pytest.mark.parametrize("forged", [True, 1.0])
@pytest.mark.parametrize(
    "field_name",
    ["entity_row_count", "struct_asym_row_count", "complete_auth_row_count"],
)
def test_common_core21_receipt_counts_reject_bool_and_float(
    field_name: str,
    forged: object,
) -> None:
    result = round_trip_mmcif_source(_common_core21_source((_core21_row(1, "CA"),)))
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs[field_name] = forged
    with pytest.raises(TypeError, match="nonnegative integer"):
        MmcifWriteReceipt(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    report_kwargs = _public_artifact_kwargs(result.report)
    report_kwargs[field_name] = forged
    with pytest.raises(TypeError, match="nonnegative integer"):
        MmcifRoundTripReport(
            **report_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("limit_name", "code"),
    [
        ("_MAX_ENTITY_ROWS", "unsupported_identity_category_profile"),
        ("_MAX_STRUCT_ASYM_ROWS", "unsupported_identity_category_profile"),
    ],
)
def test_common_core21_identity_category_row_caps_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    code: str,
) -> None:
    system = parse_mmcif(_common_core21_source((_core21_row(1, "CA"),))).system
    monkeypatch.setattr(writer_module, limit_name, 0)
    _assert_write_error(system, code)


def test_common_core21_selected_altloc_multimodel_and_auth_residue_conflict_fail() -> (
    None
):
    selected_altloc_source = _common_core21_source(
        (_core21_row(1, "CA", label_alt_id="A"),)
    )
    selected = parse_mmcif(selected_altloc_source, altloc_id="A").system
    _assert_write_error(selected, "unsupported_altloc_selection")

    multimodel = parse_mmcif(
        _common_core21_source(
            (
                _core21_row(1, "CA", model_id="1"),
                _core21_row(2, "CA", model_id="2"),
            )
        )
    ).system
    _assert_write_error(multimodel, "unsupported_model_id")

    inconsistent_auth = parse_mmcif(
        _common_core21_source(
            (
                _core21_row(1, "N", element="N", auth_seq_id="10"),
                _core21_row(2, "CA", auth_seq_id="11"),
            )
        )
    ).system
    _assert_write_error(inconsistent_auth, "inconsistent_auth_residue_identity")

    unsupported_entity_type = parse_mmcif(
        _common_core21_source(
            (_core21_row(1, "CA"),),
            entity_rows=("1 branched",),
        )
    ).system
    _assert_write_error(unsupported_entity_type, "unsupported_entity_type")


def test_whitespace_comments_header_case_and_raw_numeric_spelling_normalize() -> None:
    normalized = _document(
        (
            _row(
                atom_id="001",
                atom_name="CA",
                x="1.0",
                y="-0.0",
                z="2.5",
            ),
        ),
        data_name="normalization",
    )
    mixed_headers = tuple(
        header.replace("atom_site", "ATOM_SITE").replace("cartn", "CARTN")
        for header in CORE_HEADERS
    )
    variant = (
        "data_normalization   # data comment\n"
        "\n"
        "# before loop\n"
        "loop_\n" + "\n".join(mixed_headers) + "\n"
        "ATOM 001 C CA GLY A 1 +1.000e+0 -0.000 2.5000 1 # row comment\n"
        "#\n"
    ).encode("ascii")

    first = round_trip_mmcif_source(normalized, source_id="normalized")
    second = round_trip_mmcif_source(variant, source_id="variant")

    assert first.write_result.payload == second.write_result.payload
    assert first.write_result.payload != normalized
    assert second.write_result.payload != variant
    assert mmcif_representable_state_sha256(first.source_ingest.system) == (
        mmcif_representable_state_sha256(second.source_ingest.system)
    )
    assert canonical_topology_sha256(first.source_ingest.system) == (
        canonical_topology_sha256(second.source_ingest.system)
    )
    assert canonical_all_atom_snapshot_digest(first.source_ingest.system) != (
        canonical_all_atom_snapshot_digest(second.source_ingest.system)
    )
    assert first.report.input_parser_observation_sha256 != (
        second.report.input_parser_observation_sha256
    )
    output_row = _atom_output_rows(first.write_result.payload)[0]
    assert output_row[1] == "001"
    assert output_row[7:10] == ["1.0", "-0.0", "2.5"]


def test_shortest_exact_decimal_signed_zero_and_binary64_extrema() -> None:
    values = (
        0.0,
        -0.0,
        0.1,
        math.nextafter(1.0, 0.0),
        math.nextafter(1.0, math.inf),
        5e-324,
        sys.float_info.min,
        1e-300,
        1e300,
        sys.float_info.max,
    )
    padded = (*values, 2.0, -2.0)
    rows = tuple(
        _row(
            atom_id=f"I{index:03d}",
            atom_name=f"C{index:03d}",
            residue_number=index + 1,
            x=repr(padded[index * 3]),
            y=repr(padded[index * 3 + 1]),
            z=repr(padded[index * 3 + 2]),
        )
        for index in range(len(padded) // 3)
    )
    result = round_trip_mmcif_source(
        _document(rows, data_name="binary64"),
        source_id="binary64",
    )
    output_tokens = [
        token
        for row in _atom_output_rows(result.write_result.payload)
        for token in row[7:10]
    ]

    assert output_tokens == [repr(value) for value in padded]
    reparsed = result.reparsed_ingest.system.coordinates.reshape(-1).tolist()
    assert [_binary64(value) for value in reparsed] == [
        _binary64(value) for value in padded
    ]
    assert serialize_mmcif(result.reparsed_ingest.system) == (
        result.write_result.payload
    )


def test_raw_plus_one_and_binary64_edge_coordinates_are_a_fixed_point() -> None:
    source = _document(
        (
            _row(
                atom_id="+01",
                residue_number="+01",
                x="-0.0",
                y="5e-324",
                z=repr(sys.float_info.max),
                model_id="+01",
            ),
        ),
        headers=tuple(header.lower() for header in CORE_HEADERS),
        data_name="fixed_point",
    )
    result = round_trip_mmcif_source(source, source_id="fixed-point")

    assert result.write_result.payload == source
    assert serialize_mmcif(result.reparsed_ingest.system) == source
    assert result.write_result.receipt.atom_site_header_profile == "core11"
    assert result.write_result.receipt.atom_site_header_count == 11
    assert result.write_result.receipt.output_token_count == 24
    coordinates = result.reparsed_ingest.system.coordinates[0, 0].tolist()
    assert [_binary64(value) for value in coordinates] == [
        _binary64(-0.0),
        _binary64(5e-324),
        _binary64(sys.float_info.max),
    ]
    result.write_result.__post_init__()


@pytest.mark.parametrize(
    ("token", "formal_charge", "known"),
    [
        ("1", 1, True),
        ("+1", 1, True),
        ("-1", -1, True),
        ("0", 0, True),
        ("-0", 0, True),
        ("+0", 0, True),
        ("+01", 1, True),
        ("-32767", -32767, True),
        ("32767", 32767, True),
        (".", 0, False),
        ("?", 0, False),
    ],
)
def test_appended_formal_charge_tokens_are_exact_fixed_points(
    token: str,
    formal_charge: int,
    known: bool,
) -> None:
    source = _formal_charge_source(token, model_id="+01", data_name="charge-token")
    result = round_trip_mmcif_source(source, source_id=f"charge-{token}")
    atom = result.source_ingest.system.atoms[0]
    atom_metadata = atom.metadata

    assert atom.formal_charge == formal_charge
    assert atom.formal_charge_known is known
    assert atom_metadata["formal_charge_known"] is known
    assert atom_metadata["formal_charge_source"] == (
        FORMAL_CHARGE_HEADER if known else "missing_in_mmcif"
    )
    assert atom_metadata["formal_charge_interpretation"] == (
        "explicit" if known else "placeholder_zero_unknown"
    )
    expected_payload = _document(
        (
            _row(
                atom_name="CA",
                residue_number="1",
                model_id="+01",
                extra_values=(token,),
            ),
        ),
        headers=tuple(header.lower() for header in FORMAL_CHARGE_HEADERS),
        data_name="charge-token",
    )
    assert result.write_result.payload == expected_payload
    assert _atom_output_rows(result.write_result.payload)[0][-2:] == ["+01", token]
    assert result.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_formal_charge"
    )
    assert result.write_result.receipt.atom_site_header_count == 12
    assert result.write_result.receipt.output_token_count == 26
    assert (
        result.source_ingest.system.metadata["mmcif"]["resource_usage"]["token_count"]
        == 26
    )
    assert serialize_mmcif(result.reparsed_ingest.system) == (
        result.write_result.payload
    )
    assert mmcif_representable_state_sha256(result.source_ingest.system) == (
        mmcif_representable_state_sha256(result.reparsed_ingest.system)
    )
    result.write_result.__post_init__()


@pytest.mark.parametrize(
    ("token", "expected_occupancy"),
    [
        (".", None),
        ("?", None),
        ("+0", 0.0),
        ("-0", -0.0),
        ("01.000", 1.0),
        ("1.", 1.0),
        (".25", 0.25),
        ("1e0", 1.0),
    ],
)
def test_appended_occupancy_tokens_are_exact_fixed_points(
    token: str,
    expected_occupancy: float | None,
) -> None:
    source = _occupancy_source(token, data_name="occupancy-token")
    result = round_trip_mmcif_source(source, source_id=f"occupancy-{token}")
    atom = result.source_ingest.system.atoms[0]
    raw_payload = atom.metadata["mmcif"]["atom_site"][OCCUPANCY_HEADER]

    assert raw_payload == {"value": token, "quoted": False, "multiline": False}
    if expected_occupancy is None:
        assert atom.occupancy is None
    else:
        assert atom.occupancy is not None
        assert _binary64(atom.occupancy) == _binary64(expected_occupancy)
    expected_payload = _document(
        (_row(extra_values=(token,)),),
        headers=tuple(header.lower() for header in OCCUPANCY_HEADERS),
        data_name="occupancy-token",
    )
    assert result.write_result.payload == expected_payload
    assert _atom_output_rows(result.write_result.payload)[0][-2:] == ["1", token]
    receipt = result.write_result.receipt
    assert receipt.atom_site_header_profile == "core12_occupancy"
    assert receipt.atom_site_header_count == 12
    assert receipt.output_token_count == 26
    state = writer_module._validate_write_state(result.source_ingest.system)
    assert state.representable_state_document["occupancy_value_profile_id"] == (
        "bare_dot_question_or_uncertainty_free_finite_binary64_zero_to_one/1.0.0"
    )
    atom_document = state.representable_state_document["atoms"][0]
    assert atom_document["occupancy"] == expected_occupancy
    assert atom_document["occupancy_ieee754_binary64_be"] == (
        None
        if expected_occupancy is None
        else struct.pack(">d", expected_occupancy).hex()
    )
    assert result.write_result.payload == serialize_mmcif(result.reparsed_ingest.system)
    assert mmcif_representable_state_sha256(result.source_ingest.system) == (
        mmcif_representable_state_sha256(result.reparsed_ingest.system)
    )
    assert result.source_ingest.coverage.missingness_evidence_status == "not_present"
    assert (
        result.source_ingest.missingness_evidence.source_reported_missing_atom_count
        == 0
    )
    assert (
        result.source_ingest.missingness_evidence.source_reported_missing_residue_count
        == 0
    )
    report = result.report.to_dict()
    b_factor_nonpromotion = (
        "b_iso_or_equiv_source_notation_is_not_refinement_validity_atomic_"
        "mobility_temperature_disorder_altloc_population_occupancy_weighting_"
        "experimental_uncertainty_or_uncertainty_propagation_assessment"
    )
    assert b_factor_nonpromotion in receipt.to_dict()["blockers"]
    assert b_factor_nonpromotion in report["blockers"]
    assert report["preparation_ready"] is False
    assert report["parameterability_assessed"] is False
    assert report["simulation_ready"] is False
    assert report["claim_safe"] is False


@pytest.mark.parametrize(
    ("token", "expected_b_factor"),
    [
        (".", None),
        ("?", None),
        ("+0", 0.0),
        ("-0", -0.0),
        ("01.000", 1.0),
        ("1.", 1.0),
        (".25", 0.25),
        ("1e2", 100.0),
        ("-1.25", -1.25),
    ],
)
def test_occupancy_b_factor_tokens_are_exact_fixed_points(
    token: str,
    expected_b_factor: float | None,
) -> None:
    source = _occupancy_b_factor_source(
        "1.0",
        token,
        data_name="occupancy-b-factor-token",
    )
    result = round_trip_mmcif_source(source, source_id=f"b-factor-{token}")
    atom = result.source_ingest.system.atoms[0]
    raw_payload = atom.metadata["mmcif"]["atom_site"][B_FACTOR_HEADER.lower()]

    assert raw_payload == {"value": token, "quoted": False, "multiline": False}
    assert atom.occupancy == 1.0
    if expected_b_factor is None:
        assert atom.b_factor is None
    else:
        assert atom.b_factor is not None
        assert _binary64(atom.b_factor) == _binary64(expected_b_factor)
    expected_payload = _document(
        (_row(extra_values=("1.0", token)),),
        headers=tuple(header.lower() for header in OCCUPANCY_B_FACTOR_HEADERS),
        data_name="occupancy-b-factor-token",
    )
    assert result.write_result.payload == expected_payload
    assert _atom_output_rows(result.write_result.payload)[0][-3:] == [
        "1",
        "1.0",
        token,
    ]
    receipt = result.write_result.receipt
    assert receipt.atom_site_header_profile == "core13_occupancy_b_iso_or_equiv"
    assert receipt.atom_site_header_count == 13
    assert receipt.output_token_count == 28
    state = writer_module._validate_write_state(result.source_ingest.system)
    assert state.representable_state_document["occupancy_value_profile_id"] == (
        "bare_dot_question_or_uncertainty_free_finite_binary64_zero_to_one/1.0.0"
    )
    assert state.representable_state_document["b_factor_value_profile_id"] == (
        "bare_dot_question_or_uncertainty_free_finite_binary64/1.0.0"
    )
    atom_document = state.representable_state_document["atoms"][0]
    assert atom_document["b_factor"] == expected_b_factor
    assert atom_document["b_factor_ieee754_binary64_be"] == (
        None
        if expected_b_factor is None
        else struct.pack(">d", expected_b_factor).hex()
    )
    assert result.write_result.payload == serialize_mmcif(result.reparsed_ingest.system)
    assert mmcif_representable_state_sha256(result.source_ingest.system) == (
        mmcif_representable_state_sha256(result.reparsed_ingest.system)
    )
    report = result.report.to_dict()
    assert report["preparation_ready"] is False
    assert report["parameterability_assessed"] is False
    assert report["simulation_ready"] is False
    assert report["claim_safe"] is False


@pytest.mark.parametrize(
    ("occupancy_token", "b_factor_token"),
    [(".", "?"), ("?", "."), ("-0", "+0")],
)
def test_occupancy_b_factor_marker_combinations_preserve_field_identity(
    occupancy_token: str,
    b_factor_token: str,
) -> None:
    result = round_trip_mmcif_source(
        _occupancy_b_factor_source(
            occupancy_token,
            b_factor_token,
            data_name="occupancy-b-factor-markers",
        )
    )
    atom = result.source_ingest.system.atoms[0]

    assert _atom_output_rows(result.write_result.payload)[0][-2:] == [
        occupancy_token,
        b_factor_token,
    ]
    if occupancy_token in {".", "?"}:
        assert atom.occupancy is None
    else:
        assert atom.occupancy is not None
        assert _binary64(atom.occupancy) == _binary64(-0.0)
    if b_factor_token in {".", "?"}:
        assert atom.b_factor is None
    else:
        assert atom.b_factor is not None
        assert _binary64(atom.b_factor) == _binary64(0.0)


def test_occupancy_b_factor_all_missing_profile_does_not_collapse() -> None:
    pair = round_trip_mmcif_source(
        _occupancy_b_factor_source(".", "?", data_name="pair-all-missing")
    )
    occupancy = round_trip_mmcif_source(
        _occupancy_source(".", data_name="pair-all-missing")
    )
    core11 = round_trip_mmcif_source(_document(data_name="pair-all-missing"))

    assert pair.source_ingest.system.atoms[0].occupancy is None
    assert pair.source_ingest.system.atoms[0].b_factor is None
    assert pair.write_result.receipt.atom_site_header_profile == (
        "core13_occupancy_b_iso_or_equiv"
    )
    assert pair.write_result.receipt.atom_site_header_count == 13
    assert pair.write_result.receipt.output_token_count == 28
    assert (
        len(
            {
                mmcif_representable_state_sha256(result.source_ingest.system)
                for result in (pair, occupancy, core11)
            }
        )
        == 3
    )


@pytest.mark.parametrize(
    ("left_token", "right_token"),
    [("+0", "-0"), ("1.0", "1e0"), (".", "?")],
)
def test_same_size_b_factor_spellings_cannot_cross_wire(
    left_token: str,
    right_token: str,
) -> None:
    left = round_trip_mmcif_source(
        _occupancy_b_factor_source(
            "1.0",
            left_token,
            data_name="b-factor-crosswire",
        )
    )
    right = round_trip_mmcif_source(
        _occupancy_b_factor_source(
            "1.0",
            right_token,
            data_name="b-factor-crosswire",
        )
    )

    assert len(left.write_result.payload) == len(right.write_result.payload)
    assert left.write_result.receipt.output_token_count == (
        right.write_result.receipt.output_token_count
    )
    assert left.write_result.receipt.input_topology_sha256 == (
        right.write_result.receipt.input_topology_sha256
    )
    assert left.write_result.receipt.input_representable_state_sha256 != (
        right.write_result.receipt.input_representable_state_sha256
    )
    forged_receipt = _forged_receipt_for_payload(left, right.write_result.payload)
    with pytest.raises(ValueError, match="regenerated payload bindings"):
        MmcifWriteResult(
            payload=right.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_swapped_occupancy_and_b_factor_values_cannot_cross_wire() -> None:
    first = round_trip_mmcif_source(
        _occupancy_b_factor_source(".5", "1.0", data_name="pair-swap-wire")
    )
    second = round_trip_mmcif_source(
        _occupancy_b_factor_source("1.0", ".5", data_name="pair-swap-wire")
    )

    assert len(first.write_result.payload) == len(second.write_result.payload)
    assert first.write_result.receipt.input_topology_sha256 == (
        second.write_result.receipt.input_topology_sha256
    )
    assert first.write_result.receipt.input_representable_state_sha256 != (
        second.write_result.receipt.input_representable_state_sha256
    )
    forged_receipt = _forged_receipt_for_payload(first, second.write_result.payload)
    with pytest.raises(ValueError, match="regenerated payload bindings"):
        MmcifWriteResult(
            payload=second.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_occupancy_b_factor_and_charge_insertion_h13_profiles_cannot_cross_wire() -> (
    None
):
    measurements = round_trip_mmcif_source(
        _occupancy_b_factor_source("?", "?", data_name="h13-profile-wire")
    )
    charge_insertion = round_trip_mmcif_source(
        _insertion_code_source(
            "?",
            charge="?",
            data_name="h13-profile-wire",
        )
    )

    assert measurements.write_result.receipt.atom_site_header_count == 13
    assert charge_insertion.write_result.receipt.atom_site_header_count == 13
    assert measurements.write_result.receipt.atom_site_header_profile == (
        "core13_occupancy_b_iso_or_equiv"
    )
    assert charge_insertion.write_result.receipt.atom_site_header_profile == (
        "core13_pdbx_formal_charge_pdbx_pdb_ins_code"
    )
    assert canonical_topology_sha256(measurements.source_ingest.system) == (
        canonical_topology_sha256(charge_insertion.source_ingest.system)
    )
    forged_receipt = _forged_receipt_for_payload(
        measurements,
        charge_insertion.write_result.payload,
    )
    with pytest.raises(ValueError, match="header profile"):
        MmcifWriteResult(
            payload=charge_insertion.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_b_factor_numeric_uncertainty_is_a_typed_writer_rejection() -> None:
    system = parse_mmcif(_occupancy_b_factor_source("1.0", "20.0(5)")).system
    _assert_write_error(system, "unsupported_b_factor")


@pytest.mark.parametrize("token", ["1e9999", "'20.0'", '"20.0"'])
def test_invalid_b_factor_tokens_fail_in_the_source_parser(token: str) -> None:
    _assert_parse_error(
        _occupancy_b_factor_source("1.0", token),
        "invalid_b_factor",
    )


def test_multiline_b_factor_fails_in_the_source_parser() -> None:
    source = (
        "\n".join(
            (
                "data_multiline_b_factor",
                "#",
                "loop_",
                *OCCUPANCY_B_FACTOR_HEADERS,
                "ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1 1.0",
                ";20.0",
                ";",
                "#",
            )
        )
        + "\n"
    ).encode("ascii")
    _assert_parse_error(source, "invalid_b_factor")


def test_headerless_and_raw_canonical_b_factor_drift_precede_digest_errors() -> None:
    headerless = parse_mmcif(_occupancy_source("1.0")).system
    _assert_write_error(
        _replace_atom(headerless, b_factor=20.0),
        "unsupported_b_factor",
    )

    numeric = parse_mmcif(_occupancy_b_factor_source("1.0", "20.0")).system
    _assert_write_error(
        _replace_atom(numeric, b_factor=21.0),
        "unsupported_b_factor",
    )

    negative_zero = parse_mmcif(_occupancy_b_factor_source("1.0", "-0")).system
    _assert_write_error(
        _replace_atom(negative_zero, b_factor=0.0),
        "unsupported_b_factor",
    )


def test_b_factor_atom_and_model_raw_payload_drift_is_rejected() -> None:
    system = parse_mmcif(_occupancy_b_factor_source("1.0", "20.0")).system
    changed = {"value": "21.0", "quoted": False, "multiline": False}
    _assert_write_error(
        _replace_b_factor_payloads(
            system,
            atom_payload=changed,
            model_payload=changed,
        ),
        "unsupported_b_factor",
    )
    _assert_write_error(
        _replace_b_factor_payloads(system, model_payload=changed),
        "unsupported_atom_site_metadata",
    )

    same_binary64 = parse_mmcif(_occupancy_b_factor_source("1.0", "1.0")).system
    _assert_write_error(
        _replace_b_factor_payloads(
            same_binary64,
            model_payload={
                "value": "1e0",
                "quoted": False,
                "multiline": False,
            },
        ),
        "unsupported_atom_site_metadata",
    )


@pytest.mark.parametrize(
    ("remove_atom", "remove_model"),
    [(True, False), (False, True)],
)
def test_b_factor_atom_and_model_row_keys_must_match_the_profile(
    remove_atom: bool,
    remove_model: bool,
) -> None:
    system = parse_mmcif(_occupancy_b_factor_source("1.0", "20.0")).system
    mutated = _replace_b_factor_payloads(
        system,
        remove_atom=remove_atom,
        remove_model=remove_model,
    )
    _assert_write_error(mutated, "unsupported_atom_site_headers")


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "20.0", "quoted": 0, "multiline": False},
        {"value": "20.0", "quoted": False, "multiline": 0.0},
        {"value": 20.0, "quoted": False, "multiline": False},
    ],
)
def test_b_factor_payload_fields_require_exact_types(
    payload: dict[str, object],
) -> None:
    system = parse_mmcif(_occupancy_b_factor_source("1.0", "20.0")).system
    mutated = _replace_b_factor_payloads(
        system,
        atom_payload=payload,
        model_payload=payload,
    )
    expected_code = (
        "unsupported_b_factor"
        if type(payload["value"]) is not str
        else "unsupported_atom_site_metadata"
    )
    _assert_write_error(mutated, expected_code)


def test_occupancy_signed_zero_and_missing_markers_remain_projection_distinct() -> None:
    results = {
        token: round_trip_mmcif_source(
            _occupancy_source(token, data_name="occupancy-distinct")
        )
        for token in ("+0", "-0", ".", "?")
    }

    assert _binary64(results["+0"].source_ingest.system.atoms[0].occupancy) != (
        _binary64(results["-0"].source_ingest.system.atoms[0].occupancy)
    )
    assert results["."].source_ingest.system.atoms[0].occupancy is None
    assert results["?"].source_ingest.system.atoms[0].occupancy is None
    assert len(
        {
            mmcif_representable_state_sha256(result.source_ingest.system)
            for result in results.values()
        }
    ) == len(results)


def test_occupancy_profile_all_missing_and_dynamic_token_count() -> None:
    tokens = (".", "?", ".")
    rows = tuple(
        _row(
            index,
            atom_name=f"C{index}",
            residue_number=index,
            extra_values=(token,),
        )
        for index, token in enumerate(tokens, start=1)
    )
    occupancy = round_trip_mmcif_source(
        _document(rows, headers=OCCUPANCY_HEADERS, data_name="occupancy-missing")
    )
    core11 = round_trip_mmcif_source(
        _document(
            tuple(
                _row(index, atom_name=f"C{index}", residue_number=index)
                for index in range(1, 4)
            ),
            data_name="occupancy-missing",
        )
    )

    receipt = occupancy.write_result.receipt
    assert receipt.atom_site_header_profile == "core12_occupancy"
    assert receipt.atom_site_header_count == 12
    assert receipt.output_token_count == 2 + 12 * (len(rows) + 1)
    assert [atom.occupancy for atom in occupancy.source_ingest.system.atoms] == [
        None,
        None,
        None,
    ]
    assert canonical_topology_sha256(occupancy.source_ingest.system) == (
        canonical_topology_sha256(core11.source_ingest.system)
    )
    assert mmcif_representable_state_sha256(occupancy.source_ingest.system) != (
        mmcif_representable_state_sha256(core11.source_ingest.system)
    )


@pytest.mark.parametrize(
    ("left_token", "right_token"),
    [("+0", "-0"), ("1.0", "1e0"), (".", "?")],
)
def test_same_size_occupancy_spellings_cannot_cross_wire(
    left_token: str,
    right_token: str,
) -> None:
    left = round_trip_mmcif_source(
        _occupancy_source(left_token, data_name="occupancy-crosswire")
    )
    right = round_trip_mmcif_source(
        _occupancy_source(right_token, data_name="occupancy-crosswire")
    )

    assert len(left.write_result.payload) == len(right.write_result.payload)
    assert left.write_result.receipt.output_token_count == (
        right.write_result.receipt.output_token_count
    )
    assert left.write_result.receipt.input_topology_sha256 == (
        right.write_result.receipt.input_topology_sha256
    )
    assert left.write_result.receipt.input_representable_state_sha256 != (
        right.write_result.receipt.input_representable_state_sha256
    )
    forged_receipt = _forged_receipt_for_payload(left, right.write_result.payload)
    with pytest.raises(ValueError, match="regenerated payload bindings"):
        MmcifWriteResult(
            payload=right.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_occupancy_and_insertion_same_header_count_cannot_cross_wire() -> None:
    occupancy = round_trip_mmcif_source(
        _occupancy_source("?", data_name="optional-profile-crosswire")
    )
    insertion = round_trip_mmcif_source(
        _insertion_code_source("?", data_name="optional-profile-crosswire")
    )

    assert occupancy.write_result.receipt.atom_site_header_count == 12
    assert insertion.write_result.receipt.atom_site_header_count == 12
    assert occupancy.write_result.receipt.atom_site_header_profile == (
        "core12_occupancy"
    )
    assert insertion.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_pdb_ins_code"
    )
    assert canonical_topology_sha256(occupancy.source_ingest.system) == (
        canonical_topology_sha256(insertion.source_ingest.system)
    )
    forged_receipt = _forged_receipt_for_payload(
        occupancy,
        insertion.write_result.payload,
    )
    with pytest.raises(ValueError, match="header profile"):
        MmcifWriteResult(
            payload=insertion.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize("token", ["0.5(1)"])
def test_occupancy_numeric_uncertainty_is_a_typed_writer_rejection(
    token: str,
) -> None:
    system = parse_mmcif(_occupancy_source(token)).system
    _assert_write_error(system, "unsupported_occupancy")


@pytest.mark.parametrize("token", ["-0.001", "1.001", "1e9999", "'0.5'", '"0.5"'])
def test_invalid_occupancy_tokens_fail_in_the_source_parser(token: str) -> None:
    _assert_parse_error(_occupancy_source(token), "invalid_occupancy")


def test_multiline_occupancy_fails_in_the_source_parser() -> None:
    source = (
        "\n".join(
            (
                "data_multiline_occupancy",
                "#",
                "loop_",
                *OCCUPANCY_HEADERS,
                "ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1",
                ";0.5",
                ";",
                "#",
            )
        )
        + "\n"
    ).encode("ascii")
    _assert_parse_error(source, "invalid_occupancy")


def test_headerless_and_raw_canonical_occupancy_drift_precede_digest_errors() -> None:
    headerless = parse_mmcif(_document()).system
    _assert_write_error(
        _replace_atom(headerless, occupancy=0.5),
        "unsupported_occupancy",
    )

    numeric = parse_mmcif(_occupancy_source("0.25")).system
    _assert_write_error(
        _replace_atom(numeric, occupancy=0.5),
        "unsupported_occupancy",
    )

    negative_zero = parse_mmcif(_occupancy_source("-0")).system
    _assert_write_error(
        _replace_atom(negative_zero, occupancy=0.0),
        "unsupported_occupancy",
    )


def test_occupancy_atom_and_model_raw_payload_drift_is_rejected() -> None:
    system = parse_mmcif(_occupancy_source("0.25")).system
    changed = {"value": "0.5", "quoted": False, "multiline": False}
    _assert_write_error(
        _replace_occupancy_payloads(
            system,
            atom_payload=changed,
            model_payload=changed,
        ),
        "unsupported_occupancy",
    )
    _assert_write_error(
        _replace_occupancy_payloads(system, model_payload=changed),
        "unsupported_atom_site_metadata",
    )

    same_binary64 = parse_mmcif(_occupancy_source("1.0")).system
    _assert_write_error(
        _replace_occupancy_payloads(
            same_binary64,
            model_payload={
                "value": "1e0",
                "quoted": False,
                "multiline": False,
            },
        ),
        "unsupported_atom_site_metadata",
    )


@pytest.mark.parametrize(
    ("remove_atom", "remove_model"),
    [(True, False), (False, True)],
)
def test_occupancy_atom_and_model_row_keys_must_match_the_profile(
    remove_atom: bool,
    remove_model: bool,
) -> None:
    system = parse_mmcif(_occupancy_source("0.25")).system
    mutated = _replace_occupancy_payloads(
        system,
        remove_atom=remove_atom,
        remove_model=remove_model,
    )
    _assert_write_error(mutated, "unsupported_atom_site_headers")


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "0.25", "quoted": 0, "multiline": False},
        {"value": "0.25", "quoted": False, "multiline": 0.0},
        {"value": 0.25, "quoted": False, "multiline": False},
    ],
)
def test_occupancy_payload_fields_require_exact_types(
    payload: dict[str, object],
) -> None:
    system = parse_mmcif(_occupancy_source("0.25")).system
    mutated = _replace_occupancy_payloads(
        system,
        atom_payload=payload,
        model_payload=payload,
    )
    expected_code = (
        "unsupported_occupancy"
        if type(payload["value"]) is not str
        else "unsupported_atom_site_metadata"
    )
    _assert_write_error(mutated, expected_code)


def test_existing_six_profiles_retain_exact_emitted_bytes_and_identity_sentinel() -> (
    None
):
    cases = (
        _document(
            headers=tuple(header.lower() for header in CORE_HEADERS),
            data_name="v12-core11-bytes",
        ),
        _document(
            (_row(extra_values=("+01",)),),
            headers=tuple(header.lower() for header in FORMAL_CHARGE_HEADERS),
            data_name="v12-charge-bytes",
        ),
        _document(
            (_row(extra_values=("A",)),),
            headers=tuple(header.lower() for header in INSERTION_CODE_HEADERS),
            data_name="v12-insertion-bytes",
        ),
        _document(
            (_row(extra_values=("+01", "A")),),
            headers=tuple(
                header.lower() for header in FORMAL_CHARGE_INSERTION_CODE_HEADERS
            ),
            data_name="v12-charge-insertion-bytes",
        ),
        _document(
            (_row(extra_values=("-0",)),),
            headers=tuple(header.lower() for header in OCCUPANCY_HEADERS),
            data_name="v13-occupancy-bytes",
        ),
        _document(
            (_row(extra_values=("-0", "+0")),),
            headers=tuple(header.lower() for header in OCCUPANCY_B_FACTOR_HEADERS),
            data_name="v14-occupancy-b-factor-bytes",
        ),
    )

    for source in cases:
        result = round_trip_mmcif_source(source)
        assert result.write_result.payload == source
        assert serialize_mmcif(result.reparsed_ingest.system) == source
        receipt = result.write_result.receipt
        assert receipt.identity_profile == (
            "label_identity_without_auth_or_entity_categories/1.0.0"
        )
        assert receipt.category_profile == "atom_site_only/1.0.0"
        assert receipt.entity_row_count == 0
        assert receipt.struct_asym_row_count == 0
        assert receipt.complete_auth_row_count == 0
        assert receipt.input_identity_projection_sha256 == (
            result.report.input_identity_projection_sha256
        )


def test_mixed_known_and_unknown_formal_charge_rows_use_dynamic_token_count() -> None:
    charge_tokens = ("+1", ".", "?", "-0")
    rows = tuple(
        _row(
            index,
            atom_name=f"C{index}",
            residue_number=index,
            extra_values=(token,),
        )
        for index, token in enumerate(charge_tokens, start=1)
    )
    result = round_trip_mmcif_source(
        _document(
            rows,
            headers=FORMAL_CHARGE_HEADERS,
            data_name="mixed-charge",
        )
    )

    assert [row[-1] for row in _atom_output_rows(result.write_result.payload)] == (
        list(charge_tokens)
    )
    assert [atom.formal_charge for atom in result.source_ingest.system.atoms] == [
        1,
        0,
        0,
        0,
    ]
    assert result.source_ingest.coverage.unknown_formal_charge_count == 2
    assert result.write_result.receipt.output_token_count == 62
    assert (
        result.source_ingest.system.metadata["mmcif"]["resource_usage"]["token_count"]
        == 62
    )


def test_header_presence_and_unknown_charge_spelling_are_in_the_projection() -> None:
    core11 = round_trip_mmcif_source(_document(data_name="profile"))
    dot = round_trip_mmcif_source(_formal_charge_source(".", data_name="profile"))
    question = round_trip_mmcif_source(_formal_charge_source("?", data_name="profile"))

    assert canonical_topology_sha256(core11.source_ingest.system) == (
        canonical_topology_sha256(dot.source_ingest.system)
    )
    assert canonical_topology_sha256(dot.source_ingest.system) == (
        canonical_topology_sha256(question.source_ingest.system)
    )
    assert (
        len(
            {
                mmcif_representable_state_sha256(core11.source_ingest.system),
                mmcif_representable_state_sha256(dot.source_ingest.system),
                mmcif_representable_state_sha256(question.source_ingest.system),
            }
        )
        == 3
    )
    assert dot.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_formal_charge"
    )
    assert question.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_formal_charge"
    )


def test_same_size_dot_and_question_charge_payloads_cannot_cross_wire() -> None:
    dot = round_trip_mmcif_source(_formal_charge_source(".", data_name="crosswire"))
    question = round_trip_mmcif_source(
        _formal_charge_source("?", data_name="crosswire")
    )
    dot_receipt = dot.write_result.receipt
    question_receipt = question.write_result.receipt

    assert len(dot.write_result.payload) == len(question.write_result.payload)
    assert dot_receipt.output_token_count == question_receipt.output_token_count
    assert dot_receipt.output_physical_line_count == (
        question_receipt.output_physical_line_count
    )
    assert dot_receipt.input_topology_sha256 == question_receipt.input_topology_sha256
    assert dot_receipt.input_representable_state_sha256 != (
        question_receipt.input_representable_state_sha256
    )

    receipt_kwargs = _public_artifact_kwargs(dot_receipt)
    for field_name in (
        "output_source_sha256",
        "output_byte_count",
        "output_token_count",
        "output_physical_line_count",
        "atom_count",
        "bond_count",
        "model_count",
        "atom_site_row_count",
        "atom_site_header_profile",
        "atom_site_header_count",
    ):
        receipt_kwargs[field_name] = getattr(question_receipt, field_name)
    forged_receipt = MmcifWriteReceipt(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )

    with pytest.raises(ValueError, match="regenerated payload bindings"):
        MmcifWriteResult(
            payload=question.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("token", "expected_insertion_code"),
    [("A", "A"), (".", ""), ("?", "")],
)
def test_appended_insertion_code_tokens_are_exact_fixed_points(
    token: str,
    expected_insertion_code: str,
) -> None:
    source = _insertion_code_source(token, data_name="insertion-token")
    result = round_trip_mmcif_source(source, source_id=f"insertion-{token}")
    system = result.source_ingest.system
    atom = system.atoms[0]
    raw_payload = atom.metadata["mmcif"]["atom_site"][INSERTION_CODE_HEADER.lower()]

    assert system.residues[0].insertion_code == expected_insertion_code
    assert raw_payload == {"value": token, "quoted": False, "multiline": False}
    assert atom.formal_charge == 0
    assert atom.formal_charge_known is False
    assert atom.metadata["formal_charge_source"] == "missing_in_mmcif"
    assert _atom_output_rows(result.write_result.payload)[0][-2:] == ["1", token]
    assert result.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_pdb_ins_code"
    )
    assert result.write_result.receipt.atom_site_header_count == 12
    assert result.write_result.receipt.output_token_count == 26
    assert result.write_result.payload == serialize_mmcif(result.reparsed_ingest.system)
    assert mmcif_representable_state_sha256(system) == (
        mmcif_representable_state_sha256(result.reparsed_ingest.system)
    )


def test_core13_charge_and_insertion_tokens_are_preserved_together() -> None:
    charge_tokens = ("+01", "-0", ".", "?")
    insertion_tokens = ("A", ".", "?", "B")
    rows = tuple(
        _row(
            index,
            atom_name=f"C{index}",
            residue_number=index,
            extra_values=(charge, insertion),
        )
        for index, (charge, insertion) in enumerate(
            zip(charge_tokens, insertion_tokens, strict=True),
            start=1,
        )
    )
    result = round_trip_mmcif_source(
        _document(
            rows,
            headers=FORMAL_CHARGE_INSERTION_CODE_HEADERS,
            data_name="charge-insertion",
        )
    )

    assert [row[-2:] for row in _atom_output_rows(result.write_result.payload)] == [
        [charge, insertion]
        for charge, insertion in zip(
            charge_tokens,
            insertion_tokens,
            strict=True,
        )
    ]
    assert [atom.formal_charge for atom in result.source_ingest.system.atoms] == [
        1,
        0,
        0,
        0,
    ]
    assert [
        residue.insertion_code for residue in result.source_ingest.system.residues
    ] == ["A", "", "", "B"]
    receipt = result.write_result.receipt
    assert receipt.atom_site_header_profile == (
        "core13_pdbx_formal_charge_pdbx_pdb_ins_code"
    )
    assert receipt.atom_site_header_count == 13
    assert receipt.output_token_count == 2 + 13 * (4 + 1)
    report = result.report.to_dict()
    assert report["preparation_ready"] is False
    assert report["parameterability_assessed"] is False
    assert report["simulation_ready"] is False
    assert report["claim_safe"] is False


def test_absent_dot_question_and_same_count_optional_profiles_are_distinct() -> None:
    core11 = round_trip_mmcif_source(_document(data_name="insertion-profile"))
    insertion_dot = round_trip_mmcif_source(
        _insertion_code_source(".", data_name="insertion-profile")
    )
    insertion_question = round_trip_mmcif_source(
        _insertion_code_source("?", data_name="insertion-profile")
    )
    charge_dot = round_trip_mmcif_source(
        _formal_charge_source(".", data_name="insertion-profile")
    )
    results = (core11, insertion_dot, insertion_question, charge_dot)

    assert (
        len(
            {
                canonical_topology_sha256(result.source_ingest.system)
                for result in results
            }
        )
        == 1
    )
    assert (
        len(
            {
                mmcif_representable_state_sha256(result.source_ingest.system)
                for result in results
            }
        )
        == 4
    )
    assert (
        insertion_dot.write_result.receipt.atom_site_header_count
        == (charge_dot.write_result.receipt.atom_site_header_count)
        == 12
    )
    assert insertion_dot.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_pdb_ins_code"
    )
    assert charge_dot.write_result.receipt.atom_site_header_profile == (
        "core12_pdbx_formal_charge"
    )


def test_per_row_dot_and_question_in_one_blank_residue_are_preserved() -> None:
    source = _document(
        (
            _row(1, atom_name="CA", extra_values=(".",)),
            _row(2, atom_name="CB", x="1.0", extra_values=("?",)),
        ),
        headers=INSERTION_CODE_HEADERS,
        data_name="mixed-missing-insertion",
    )
    result = round_trip_mmcif_source(source)

    assert len(result.source_ingest.system.residues) == 1
    assert result.source_ingest.system.residues[0].insertion_code == ""
    assert [row[-1] for row in _atom_output_rows(result.write_result.payload)] == [
        ".",
        "?",
    ]
    assert result.write_result.payload == serialize_mmcif(result.reparsed_ingest.system)


def test_same_sequence_blank_a_and_b_insertion_residues_remain_distinct() -> None:
    source = _document(
        (
            _row(1, atom_name="CA", residue_number=1, extra_values=(".",)),
            _row(2, atom_name="CA", residue_number=1, x="1.0", extra_values=("A",)),
            _row(3, atom_name="CA", residue_number=1, x="2.0", extra_values=("B",)),
        ),
        headers=INSERTION_CODE_HEADERS,
        data_name="three-insertions",
    )
    result = round_trip_mmcif_source(source)

    before = result.source_ingest.system
    after = result.reparsed_ingest.system
    assert [
        (residue.sequence_number, residue.insertion_code) for residue in before.residues
    ] == [
        (1, ""),
        (1, "A"),
        (1, "B"),
    ]
    assert [
        (residue.sequence_number, residue.insertion_code) for residue in after.residues
    ] == [
        (1, ""),
        (1, "A"),
        (1, "B"),
    ]
    assert canonical_topology_sha256(before) == canonical_topology_sha256(after)
    assert mmcif_representable_state_sha256(before) == (
        mmcif_representable_state_sha256(after)
    )
    assert result.write_result.payload == serialize_mmcif(after)


def test_token_count_is_profile_dynamic_for_eleven_twelve_and_thirteen_headers() -> (
    None
):
    row_count = 3
    core_rows = tuple(
        _row(index, atom_name=f"C{index}", residue_number=index)
        for index in range(1, row_count + 1)
    )
    cases = (
        (_document(core_rows, data_name="h11"), 11, "core11"),
        (
            _document(
                tuple(f"{row} ." for row in core_rows),
                headers=FORMAL_CHARGE_HEADERS,
                data_name="h12-charge",
            ),
            12,
            "core12_pdbx_formal_charge",
        ),
        (
            _document(
                tuple(f"{row} ?" for row in core_rows),
                headers=INSERTION_CODE_HEADERS,
                data_name="h12-insertion",
            ),
            12,
            "core12_pdbx_pdb_ins_code",
        ),
        (
            _document(
                tuple(f"{row} . ?" for row in core_rows),
                headers=FORMAL_CHARGE_INSERTION_CODE_HEADERS,
                data_name="h13",
            ),
            13,
            "core13_pdbx_formal_charge_pdbx_pdb_ins_code",
        ),
    )

    for source, header_count, profile in cases:
        receipt = round_trip_mmcif_source(source).write_result.receipt
        assert receipt.atom_site_header_profile == profile
        assert receipt.atom_site_header_count == header_count
        assert receipt.output_token_count == 2 + header_count * (row_count + 1)


@pytest.mark.parametrize("quote", ["'", '"'])
def test_quoted_core_identity_is_a_typed_writer_rejection(quote: str) -> None:
    source = _document(
        (_row(atom_name=f"{quote}CA{quote}"),),
        data_name="quoted",
    )
    system = parse_mmcif(source).system
    _assert_write_error(system, "unsupported_atom_site_metadata")


def test_semicolon_multiline_core_identity_is_a_typed_writer_rejection() -> None:
    source = (
        "\n".join(
            (
                "data_multiline",
                "#",
                "loop_",
                *CORE_HEADERS,
                "ATOM 1 C",
                ";CA",
                ";",
                "GLY A 1 0.0 0.0 0.0 1",
                "#",
            )
        )
        + "\n"
    ).encode("ascii")
    system = parse_mmcif(source).system
    _assert_write_error(system, "unsupported_atom_site_metadata")


@pytest.mark.parametrize("atom_name", ["CA#x", "O5'", "CA;X"])
def test_unsafe_bare_core_identity_is_rejected(atom_name: str) -> None:
    system = parse_mmcif(_document((_row(atom_name=atom_name),))).system
    _assert_write_error(system, "unsafe_cif_token")


@pytest.mark.parametrize(
    ("atom_name", "code"),
    [
        ("loop_", "malformed_loop_rows"),
        ("stop_", "malformed_loop_rows"),
        ("global_", "malformed_loop_rows"),
        ("data_x", "malformed_loop_rows"),
        ("save_x", "malformed_loop_rows"),
        ("_x.id", "malformed_loop_rows"),
        ("#comment", "malformed_loop_rows"),
        ("$frame", "invalid_unquoted_value"),
        ("[reserved]", "invalid_unquoted_value"),
    ],
)
def test_bare_structural_or_reserved_tokens_fail_in_the_source_parser(
    atom_name: str,
    code: str,
) -> None:
    _assert_parse_error(_document((_row(atom_name=atom_name),)), code)


def test_source_atom_site_and_label_identity_are_not_numeric_normalizations() -> None:
    source = _document(
        (
            _row(
                atom_id="Ca3g28",
                group="HETATM",
                element="Zn",
                atom_name="ZN1",
                residue_name="ZN",
                chain_id="Z1",
                residue_number="7",
                x="-1.25",
            ),
        ),
        data_name="identity-1",
    )
    result = round_trip_mmcif_source(source)
    output = _atom_output_rows(result.write_result.payload)[0]

    assert output[:7] == ["HETATM", "Ca3g28", "Zn", "ZN1", "ZN", "Z1", "7"]
    before = result.source_ingest.system
    after = result.reparsed_ingest.system
    assert before.atoms[0].name == after.atoms[0].name == "ZN1"
    assert before.chains[0].chain_id == after.chains[0].chain_id == "Z1"


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        (
            (
                _row("1", atom_name="CA", residue_number=1),
                _row("1", atom_name="CB", residue_number=1),
            ),
            "duplicate_atom_site_id",
        ),
        (
            (
                _row("1", atom_name="CA", residue_number=1),
                _row("2", atom_name="CA", residue_number=1),
            ),
            "duplicate_altloc_atom_identity",
        ),
    ],
)
def test_duplicate_source_identity_fails_before_writing(
    rows: tuple[str, ...],
    code: str,
) -> None:
    _assert_parse_error(_document(rows), code)


def test_chain_and_atom_order_follow_first_source_occurrence() -> None:
    source = _document(
        (
            _row("B1", atom_name="CB", chain_id="B", residue_number=1),
            _row("A1", atom_name="CA", chain_id="A", residue_number=1),
        ),
        data_name="first-occurrence",
    )
    result = round_trip_mmcif_source(source)

    assert [chain.chain_id for chain in result.source_ingest.system.chains] == [
        "B",
        "A",
    ]
    assert [row[1] for row in _atom_output_rows(result.write_result.payload)] == [
        "B1",
        "A1",
    ]


@pytest.mark.parametrize(
    ("header", "value", "code"),
    [
        ("_atom_site.B_iso_or_equiv", "20.0", "unsupported_atom_site_headers"),
        ("_atom_site.B_iso_or_equiv_esd", "0.5", "unsupported_atom_site_headers"),
        ("_atom_site.auth_atom_id", "CA", "unsupported_atom_site_headers"),
        ("_atom_site.auth_comp_id", "GLY", "unsupported_atom_site_headers"),
        ("_atom_site.auth_asym_id", "X", "unsupported_atom_site_headers"),
        ("_atom_site.auth_seq_id", "10", "unsupported_atom_site_headers"),
        ("_atom_site.label_entity_id", "1", "unsupported_atom_site_headers"),
        ("_atom_site.Cartn_x_esd", "0.01", "unsupported_atom_site_headers"),
    ],
)
def test_optional_atom_site_surface_is_rejected(
    header: str,
    value: str,
    code: str,
) -> None:
    system = parse_mmcif(_optional_source(header, value)).system
    _assert_write_error(system, code)


def test_selected_optional_headers_require_exact_append_order_and_position() -> None:
    inserted_headers = (*CORE_HEADERS[:-1], FORMAL_CHARGE_HEADER, CORE_HEADERS[-1])
    inserted = _document(
        ("ATOM 1 C CA GLY A 1 0.0 0.0 0.0 +1 1",),
        headers=inserted_headers,
        data_name="inserted-charge",
    )
    _assert_write_error(parse_mmcif(inserted).system, "unsupported_atom_site_headers")

    extra = _document(
        (_row(extra_values=("+1", "1.0")),),
        headers=(*FORMAL_CHARGE_HEADERS, "_atom_site.occupancy"),
        data_name="charge-plus-extra",
    )
    _assert_write_error(parse_mmcif(extra).system, "unsupported_atom_site_headers")

    inserted_insertion_headers = (
        *CORE_HEADERS[:-1],
        INSERTION_CODE_HEADER,
        CORE_HEADERS[-1],
    )
    inserted_insertion = _document(
        ("ATOM 1 C CA GLY A 1 0.0 0.0 0.0 A 1",),
        headers=inserted_insertion_headers,
        data_name="inserted-insertion",
    )
    _assert_write_error(
        parse_mmcif(inserted_insertion).system,
        "unsupported_atom_site_headers",
    )

    wrong_optional_order = _document(
        (_row(extra_values=("A", "+1")),),
        headers=(*CORE_HEADERS, INSERTION_CODE_HEADER, FORMAL_CHARGE_HEADER),
        data_name="wrong-optional-order",
    )
    _assert_write_error(
        parse_mmcif(wrong_optional_order).system,
        "unsupported_atom_site_headers",
    )

    inserted_occupancy_headers = (
        *CORE_HEADERS[:-1],
        OCCUPANCY_HEADER,
        CORE_HEADERS[-1],
    )
    inserted_occupancy = _document(
        ("ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1.0 1",),
        headers=inserted_occupancy_headers,
        data_name="inserted-occupancy",
    )
    _assert_write_error(
        parse_mmcif(inserted_occupancy).system,
        "unsupported_atom_site_headers",
    )

    occupancy_plus_insertion = _document(
        (_row(extra_values=("1.0", "A")),),
        headers=(*OCCUPANCY_HEADERS, INSERTION_CODE_HEADER),
        data_name="occupancy-plus-insertion",
    )
    _assert_write_error(
        parse_mmcif(occupancy_plus_insertion).system,
        "unsupported_atom_site_headers",
    )

    reverse_measurements = _document(
        (_row(extra_values=("20.0", "1.0")),),
        headers=(*CORE_HEADERS, B_FACTOR_HEADER, OCCUPANCY_HEADER),
        data_name="b-factor-before-occupancy",
    )
    _assert_write_error(
        parse_mmcif(reverse_measurements).system,
        "unsupported_atom_site_headers",
    )

    dictionary_native_measurements = _document(
        ("ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1.0 20.0 1",),
        headers=(
            *CORE_HEADERS[:-1],
            OCCUPANCY_HEADER,
            B_FACTOR_HEADER,
            CORE_HEADERS[-1],
        ),
        data_name="middle-occupancy-b-factor",
    )
    _assert_write_error(
        parse_mmcif(dictionary_native_measurements).system,
        "unsupported_atom_site_headers",
    )

    occupancy_b_factor_plus_charge = _document(
        (_row(extra_values=("1.0", "20.0", "+1")),),
        headers=(*OCCUPANCY_B_FACTOR_HEADERS, FORMAL_CHARGE_HEADER),
        data_name="measurements-plus-charge",
    )
    _assert_write_error(
        parse_mmcif(occupancy_b_factor_plus_charge).system,
        "unsupported_atom_site_headers",
    )

    occupancy_b_factor_plus_insertion = _document(
        (_row(extra_values=("1.0", "20.0", "A")),),
        headers=(*OCCUPANCY_B_FACTOR_HEADERS, INSERTION_CODE_HEADER),
        data_name="measurements-plus-insertion",
    )
    _assert_write_error(
        parse_mmcif(occupancy_b_factor_plus_insertion).system,
        "unsupported_atom_site_headers",
    )

    core14 = _document(
        (_row(extra_values=("+1", "A", "1.0")),),
        headers=(
            *FORMAL_CHARGE_INSERTION_CODE_HEADERS,
            "_atom_site.occupancy",
        ),
        data_name="core14",
    )
    _assert_write_error(parse_mmcif(core14).system, "unsupported_atom_site_headers")


@pytest.mark.parametrize("quoted", ["'+1'", '"+1"'])
def test_quoted_formal_charge_is_rejected_by_the_source_parser(quoted: str) -> None:
    _assert_parse_error(
        _formal_charge_source(quoted, data_name="quoted-charge"),
        "invalid_formal_charge",
    )


def test_multiline_formal_charge_is_rejected_by_the_source_parser() -> None:
    source = (
        "\n".join(
            (
                "data_multiline_charge",
                "#",
                "loop_",
                *FORMAL_CHARGE_HEADERS,
                "ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1",
                ";+1",
                ";",
                "#",
            )
        )
        + "\n"
    ).encode("ascii")
    _assert_parse_error(source, "invalid_formal_charge")


def test_blank_altloc_header_and_selected_altloc_are_both_rejected() -> None:
    blank = parse_mmcif(_optional_source("_atom_site.label_alt_id", ".")).system
    _assert_write_error(blank, "unsupported_atom_site_headers")

    selected_source = _optional_source("_atom_site.label_alt_id", "A")
    selected = parse_mmcif(selected_source, altloc_id="A").system
    _assert_write_error(selected, "unsupported_altloc_selection")


def test_entity_categories_are_rejected_even_when_self_consistent() -> None:
    system = parse_mmcif(
        _document(sections=_entity_sections(), data_name="entity")
    ).system
    _assert_write_error(system, "unsupported_category_inventory")


def test_assembly_present_and_applied_states_are_rejected() -> None:
    source = _document(sections=_assembly_sections(), data_name="assembly")
    deposited = parse_mmcif(source).system
    applied = parse_mmcif(source, assembly_id="1").system

    _assert_write_error(deposited, "unsupported_assembly")
    _assert_write_error(applied, "unsupported_assembly")


def test_missingness_cell_and_other_category_states_are_rejected() -> None:
    missingness = parse_mmcif(
        _document(sections=(_missingness_section(),), data_name="missingness")
    ).system
    _assert_write_error(missingness, "unsupported_missingness_evidence")

    cell = parse_mmcif(_document(sections=(_cell_section(),), data_name="cell")).system
    _assert_write_error(cell, "unsupported_unit_cell")

    other = parse_mmcif(
        _document(sections=("_entry.id core\n#",), data_name="entry")
    ).system
    _assert_write_error(other, "unsupported_category_inventory")


@pytest.mark.parametrize(
    ("section", "code"),
    [
        ("_struct_conn.id 1\n#", "unsupported_topology_category"),
        ("_chem_comp.id LIG\n#", "unsupported_context_category"),
        ("_future_unknown.id 1\n#", "unsupported_uninterpreted_category"),
    ],
)
def test_default_deny_categories_fail_before_writer_admission(
    section: str,
    code: str,
) -> None:
    _assert_parse_error(_document(sections=(section,)), code)


def test_single_model_id_one_and_core_headers_are_exact_admission_rules() -> None:
    model_two = parse_mmcif(
        _document((_row(model_id=2),), data_name="model-two")
    ).system
    _assert_write_error(model_two, "unsupported_model_id")

    multi_model = parse_mmcif(
        _document(
            (
                _row("1", model_id=1, x=0.0),
                _row("2", model_id=2, x=1.0),
            ),
            data_name="multi-model",
        )
    ).system
    _assert_write_error(multi_model, "unsupported_model_id")

    no_model_header = CORE_HEADERS[:-1]
    no_model = parse_mmcif(
        _document(
            (" ".join(_row().split()[:-1]),),
            headers=no_model_header,
            data_name="implicit-model",
        )
    ).system
    _assert_write_error(no_model, "unsupported_atom_site_headers")


def test_bonds_cell_and_unrepresentable_atom_state_never_silently_drop() -> None:
    system = parse_mmcif(_document()).system
    second_atom = replace(
        system.atoms[0],
        index=1,
        name="CB",
        serial=2,
    )
    second_residue = replace(
        system.residues[0],
        atom_indices=(0, 1),
    )
    two_atom = replace(
        system,
        atoms=(system.atoms[0], second_atom),
        residues=(second_residue,),
        coordinates=torch.zeros((1, 2, 3), dtype=torch.float64),
    )
    bond = Bond(index=0, atom_i=0, atom_j=1, order=1.0, source="test")
    _assert_write_error(replace(two_atom, bonds=(bond,)), "unsupported_bonds")
    _assert_write_error(
        replace(
            system,
            cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
        ),
        "unsupported_unit_cell",
    )


def test_coordinate_tensor_contract_and_nonfinite_state_fail_closed() -> None:
    system = parse_mmcif(_document()).system
    _assert_write_error(
        replace(system, coordinates=system.coordinates.to(torch.float32)),
        "unsupported_coordinate_dtype",
    )
    _assert_write_error(
        replace(system, coordinates=system.coordinates.clone().requires_grad_(True)),
        "coordinate_gradient_state_unsupported",
    )
    _assert_write_error(
        replace(system, coordinate_unit="nanometer"),
        "unsupported_coordinate_unit",
    )
    coordinates = system.coordinates.clone()
    coordinates[0, 0, 0] = float("inf")
    _assert_write_error(
        replace(system, coordinates=coordinates),
        "canonical_validation_failed",
    )


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"partial_charge_e": 0.1}, "unsupported_partial_charge"),
        ({"mass_da": 12.0}, "unsupported_atom_mass"),
        ({"isotope_mass_number": 13}, "unsupported_isotope"),
        ({"atom_map": 1}, "unsupported_atom_map"),
        ({"aromatic": True}, "unsupported_aromatic_atom"),
        ({"stereo": "R"}, "unsupported_atom_stereo"),
    ],
)
def test_unsupported_canonical_atom_fields_are_rejected(
    changes: dict[str, object],
    code: str,
) -> None:
    system = parse_mmcif(_document()).system
    _assert_write_error(_replace_atom(system, **changes), code)


def test_topology_observation_coverage_missingness_and_resource_tamper() -> None:
    system = parse_mmcif(_document()).system
    _assert_write_error(
        _replace_provenance_metadata(
            system,
            "canonical_topology_sha256",
            "0" * 64,
        ),
        "stale_canonical_topology_digest",
    )
    _assert_write_error(
        _replace_provenance_metadata(
            system,
            "parser_observation_sha256",
            "0" * 64,
        ),
        "stale_parser_observation_digest",
    )

    coverage = dict(system.provenance.metadata["coverage"])
    coverage["atom_count"] += 1
    _assert_write_error(
        _replace_provenance_metadata(system, "coverage", coverage),
        "stale_mmcif_coverage",
    )

    mmcif = system.metadata["mmcif"]
    missingness = dict(mmcif["source_reported_missingness"])
    missingness["source_reported_missing_residue_count"] = 1
    _assert_write_error(
        _replace_mmcif_metadata(system, "source_reported_missingness", missingness),
        "stale_missingness_digest",
    )

    resource_usage = dict(mmcif["resource_usage"])
    resource_usage["atom_site_rows"] += 1
    _assert_write_error(
        _replace_mmcif_metadata(system, "resource_usage", resource_usage),
        "unsupported_resource_metadata",
    )


@pytest.mark.parametrize("forged_model_id", [True, 1.0])
@pytest.mark.parametrize(
    "location",
    ["provenance", "atom_site_id_by_model", "atom_site_by_model"],
)
def test_model_id_bool_and_float_equivalents_are_typed_rejections(
    location: str,
    forged_model_id,
) -> None:
    system = parse_mmcif(_document()).system
    if location == "provenance":
        mutated = _replace_provenance_metadata(
            system,
            "model_ids",
            [forged_model_id],
        )
    else:
        mutated = _replace_atom_mmcif_model_id(
            system,
            location,
            forged_model_id,
        )
    _assert_typed_metadata_rejected(system, mutated)


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [
        ("supported", 1),
        ("syntax_ingest_supported", 1.0),
        ("preparation_ready", 0),
        ("claim_safe", 0.0),
        ("cell_present", 0),
        ("atom_count", 1.0),
        ("bond_count", False),
        ("model_count", True),
        ("altloc_affected_residue_count", 0.0),
        ("altloc_kept_row_count", 1.0),
        ("assembly_operation_sequence_count", False),
        ("assembly_output_atom_count", 0.0),
        ("source_reported_missing_residue_claim_count", False),
        ("source_reported_missing_atom_claim_count", 0.0),
    ],
)
def test_coverage_numeric_and_bool_equivalents_are_typed_rejections(
    field_name: str,
    forged_value,
) -> None:
    system = parse_mmcif(_document()).system
    coverage = dict(system.provenance.metadata["coverage"])
    coverage[field_name] = forged_value
    mutated = _replace_provenance_metadata(system, "coverage", coverage)
    _assert_typed_metadata_rejected(system, mutated)


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [
        ("scalar_item_count", False),
        ("loop_count", True),
        ("row_count", 1.0),
    ],
)
def test_category_inventory_counts_require_exact_integer_types(
    field_name: str,
    forged_value,
) -> None:
    system = parse_mmcif(_document()).system
    mutated = _replace_inventory_value(system, field_name, forged_value)
    _assert_typed_metadata_rejected(system, mutated)


@pytest.mark.parametrize(
    ("section", "field_name", "forged_value"),
    [
        ("source_missingness", "residue_row_count", False),
        ("source_missingness", "atom_row_count", 0.0),
        ("source_missingness", "unobserved_residue_claim_count", False),
        ("source_missingness", "zero_occupancy_atom_row_count", 0.0),
        ("source_reported_missingness", "claim_safe", 0),
        ("source_reported_missingness", "completion_applied", 0.0),
        ("source_reported_missingness", "completion_attempted", 0),
        ("source_reported_missingness", "preparation_ready", 0.0),
        ("source_reported_missingness", "source_reported_missing_atom_count", False),
        (
            "source_reported_missingness",
            "source_reported_missing_residue_count",
            0.0,
        ),
        ("resource_usage", "input_bytes", float(len(_document()))),
        ("resource_usage", "token_count", 24.0),
        ("resource_usage", "atom_site_rows", True),
        ("resource_usage", "missing_atom_evidence_rows", False),
        ("resource_usage", "total_missingness_evidence_rows", 0.0),
        ("resource_limits", "atom_site_rows", 80_000.0),
        ("resource_limits", "missing_residue_evidence_rows", 20_000.0),
        ("resource_limits", "assembly_definition_rows", 1_024.0),
    ],
)
def test_missingness_and_resource_numbers_and_bools_are_typed_rejections(
    section: str,
    field_name: str,
    forged_value,
) -> None:
    system = parse_mmcif(_document()).system
    mutated = _replace_mmcif_mapping_value(
        system,
        section,
        field_name,
        forged_value,
    )
    _assert_typed_metadata_rejected(system, mutated)


def test_bool_model_marker_cannot_collapse_to_the_integer_projection() -> None:
    system = parse_mmcif(_document()).system
    baseline_projection = mmcif_representable_state_sha256(system)
    mutated = _replace_atom_mmcif_model_id(
        system,
        "atom_site_by_model",
        True,
    )

    assert baseline_projection == mmcif_representable_state_sha256(system)
    assert _attached_parser_owned_digests(mutated) == (
        _attached_parser_owned_digests(system)
    )
    assert canonical_all_atom_snapshot_digest(mutated) != (
        canonical_all_atom_snapshot_digest(system)
    )
    with pytest.raises(MmcifWriteError):
        mmcif_representable_state_sha256(mutated)


def test_atom_site_category_and_preserved_payload_metadata_tamper() -> None:
    system = parse_mmcif(_document()).system
    headers = list(system.metadata["mmcif"]["atom_site_headers"])
    headers.reverse()
    _assert_write_error(
        _replace_mmcif_metadata(system, "atom_site_headers", headers),
        "unsupported_atom_site_headers",
    )
    _assert_write_error(
        _replace_mmcif_metadata(
            system,
            "preserved_category_payloads",
            [
                {
                    "category": "_entry",
                    "policy": "uninterpreted_metadata",
                    "scalar_items": [],
                    "loops": [],
                }
            ],
        ),
        "unsupported_preserved_category_payloads",
    )

    atom_metadata = dict(system.atoms[0].metadata)
    mmcif_atom = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif_atom["atom_site"])
    x_token = dict(atom_site["_atom_site.cartn_x"])
    x_token["value"] = "2.0"
    atom_site["_atom_site.cartn_x"] = x_token
    mmcif_atom["atom_site"] = atom_site
    atom_metadata["mmcif"] = mmcif_atom
    _assert_write_error(
        _replace_atom(system, metadata=atom_metadata),
        "coordinate_metadata_mismatch",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "+1", "quoted": True, "multiline": False},
        {"value": "+1", "quoted": False, "multiline": True},
    ],
)
def test_quoted_or_multiline_formal_charge_payload_tamper_is_rejected(
    payload: dict[str, object],
) -> None:
    system = parse_mmcif(_formal_charge_source("+1")).system
    mutated = _replace_charge_payloads(
        system,
        atom_payload=payload,
        model_payload=payload,
    )
    mutated = _reattach_parser_observation(mutated)
    _assert_write_error(mutated, "unsupported_atom_site_metadata")


def test_raw_charge_and_canonical_charge_mismatch_is_rejected() -> None:
    system = parse_mmcif(_formal_charge_source("+1")).system
    payload = {"value": "-1", "quoted": False, "multiline": False}
    mutated = _replace_charge_payloads(
        system,
        atom_payload=payload,
        model_payload=payload,
    )
    mutated = _reattach_parser_observation(mutated)
    _assert_write_error(mutated, "unsupported_formal_charge")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("formal_charge_known", False),
        ("formal_charge_source", "missing_in_mmcif"),
        ("formal_charge_interpretation", "placeholder_zero_unknown"),
    ],
)
def test_formal_charge_metadata_tamper_is_rejected(
    field_name: str,
    value: object,
) -> None:
    system = parse_mmcif(_formal_charge_source("+1")).system
    atom_metadata = dict(system.atoms[0].metadata)
    atom_metadata[field_name] = value
    mutated = _replace_atom(system, metadata=atom_metadata)
    mutated = _reattach_parser_observation(mutated)
    _assert_write_error(mutated, "unsupported_formal_charge")


@pytest.mark.parametrize(
    ("remove_atom", "remove_model"),
    [(True, False), (False, True)],
)
def test_atom_and_model_formal_charge_row_keys_must_match_the_profile(
    remove_atom: bool,
    remove_model: bool,
) -> None:
    system = parse_mmcif(_formal_charge_source("+1")).system
    mutated = _replace_charge_payloads(
        system,
        remove_atom=remove_atom,
        remove_model=remove_model,
    )
    if remove_atom:
        mutated = _reattach_parser_observation(mutated)
    _assert_write_error(mutated, "unsupported_atom_site_headers")


def test_atom_and_model_charge_raw_spelling_must_match_exactly() -> None:
    system = parse_mmcif(_formal_charge_source("+01")).system
    mutated = _replace_charge_payloads(
        system,
        model_payload={"value": "1", "quoted": False, "multiline": False},
    )
    _assert_write_error(mutated, "unsupported_atom_site_metadata")


@pytest.mark.parametrize(
    ("source", "canonical_insertion"),
    [
        (_insertion_code_source("A"), "B"),
        (_insertion_code_source("."), "A"),
        (_document(), "A"),
    ],
)
def test_raw_and_canonical_insertion_mismatch_precedes_stale_digest(
    source: bytes,
    canonical_insertion: str,
) -> None:
    system = parse_mmcif(source).system
    mutated = _replace_residue(system, insertion_code=canonical_insertion)

    assert canonical_topology_sha256(mutated) != canonical_topology_sha256(system)
    _assert_write_error(mutated, "unsupported_insertion_code")


@pytest.mark.parametrize(
    ("remove_atom", "remove_model"),
    [(True, False), (False, True)],
)
def test_atom_and_model_insertion_row_keys_must_match_the_profile(
    remove_atom: bool,
    remove_model: bool,
) -> None:
    system = parse_mmcif(_insertion_code_source("A")).system
    mutated = _replace_insertion_payloads(
        system,
        remove_atom=remove_atom,
        remove_model=remove_model,
    )
    _assert_write_error(mutated, "unsupported_atom_site_headers")


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {"value": "A", "quoted": True, "multiline": False},
            "unsupported_atom_site_metadata",
        ),
        (
            {"value": "A", "quoted": False, "multiline": True},
            "unsupported_atom_site_metadata",
        ),
        (
            {"value": "A#", "quoted": False, "multiline": False},
            "unsafe_cif_token",
        ),
        (
            {"value": "Å", "quoted": False, "multiline": False},
            "unsupported_atom_site_metadata",
        ),
    ],
)
def test_quoted_multiline_unsafe_or_nonascii_insertion_payload_is_rejected(
    payload: dict[str, object],
    code: str,
) -> None:
    system = parse_mmcif(_insertion_code_source("A")).system
    mutated = _replace_insertion_payloads(
        system,
        atom_payload=payload,
        model_payload=payload,
    )
    mutated = _reattach_parser_observation(mutated)
    _assert_write_error(mutated, code)


def test_atom_and_model_insertion_raw_spelling_must_match_exactly() -> None:
    system = parse_mmcif(_insertion_code_source(".")).system
    mutated = _replace_insertion_payloads(
        system,
        model_payload={"value": "?", "quoted": False, "multiline": False},
    )
    _assert_write_error(mutated, "unsupported_atom_site_metadata")


def test_same_size_dot_and_question_insertion_payloads_cannot_cross_wire() -> None:
    dot = round_trip_mmcif_source(
        _insertion_code_source(".", data_name="insertion-wire")
    )
    question = round_trip_mmcif_source(
        _insertion_code_source("?", data_name="insertion-wire")
    )
    dot_receipt = dot.write_result.receipt
    question_receipt = question.write_result.receipt

    assert len(dot.write_result.payload) == len(question.write_result.payload)
    assert dot_receipt.input_topology_sha256 == question_receipt.input_topology_sha256
    assert dot_receipt.input_representable_state_sha256 != (
        question_receipt.input_representable_state_sha256
    )

    receipt_kwargs = _public_artifact_kwargs(dot_receipt)
    for field_name in (
        "output_source_sha256",
        "output_byte_count",
        "output_token_count",
        "output_physical_line_count",
        "atom_count",
        "bond_count",
        "model_count",
        "atom_site_row_count",
        "atom_site_header_profile",
        "atom_site_header_count",
    ):
        receipt_kwargs[field_name] = getattr(question_receipt, field_name)
    forged_receipt = MmcifWriteReceipt(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )
    with pytest.raises(ValueError, match="regenerated payload bindings"):
        MmcifWriteResult(
            payload=question.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda provenance: replace(provenance, source_format="pdb"),
            "unsupported_source_format",
        ),
        (
            lambda provenance: replace(provenance, parser_name="other"),
            "unsupported_parser_pedigree",
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
def test_parser_pedigree_and_authority_drift_fail_closed(mutator, code: str) -> None:
    system = parse_mmcif(_document()).system
    _assert_write_error(
        replace(system, provenance=mutator(system.provenance)),
        code,
    )


def test_writer_output_resource_caps_fail_before_partial_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = parse_mmcif(
        _document(
            (
                _row("1", atom_name="CA", residue_number=1),
                _row("2", atom_name="CB", residue_number=2),
            ),
            data_name="caps",
        )
    ).system

    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_ATOM_ROWS", 1)
        _assert_write_error(system, "too_many_atom_rows")
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_TOKEN_COUNT", 1)
        _assert_write_error(system, "output_token_limit_exceeded")
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_OUTPUT_LINES", 1)
        _assert_write_error(system, "output_line_limit_exceeded")
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_LINE_CHARS", 8)
        _assert_write_error(system, "output_line_too_long")
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_OUTPUT_BYTES", 1)
        _assert_write_error(system, "output_too_large")


def test_data_block_resource_cap_is_separate_from_token_safety(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = parse_mmcif(_document(data_name="core-name")).system
    with monkeypatch.context() as scoped:
        scoped.setattr(writer_module, "_MAX_DATA_BLOCK_CHARS", 4)
        _assert_write_error(system, "unsupported_data_block")


def test_bounded_single_model_workload_has_one_output_row_per_input_atom() -> None:
    row_count = 1_000
    rows = tuple(
        _row(
            atom_id=f"I{index:05d}",
            atom_name=f"C{index:05d}",
            residue_number=index + 1,
            x=repr(float(index)),
        )
        for index in range(row_count)
    )
    result = round_trip_mmcif_source(
        _document(rows, data_name="bounded-1000"),
        source_id="bounded-1000",
    )

    assert len(_atom_output_rows(result.write_result.payload)) == row_count
    assert result.write_result.receipt.atom_count == row_count
    assert result.write_result.receipt.model_count == 1
    assert result.write_result.receipt.bond_count == 0
    assert result.write_result.receipt.output_token_count == 11_013
    assert serialize_mmcif(result.reparsed_ingest.system) == (
        result.write_result.payload
    )


def test_success_artifacts_are_factory_only_and_cross_wiring_is_rejected() -> None:
    mini = round_trip_mmcif_source(MINI_PROTEIN.read_bytes(), source_id="mini")
    other = round_trip_mmcif_source(
        _document((_row("A2", atom_name="CB", x=2.0),), data_name="other"),
        source_id="other",
    )

    with pytest.raises(TypeError, match="factory-only"):
        MmcifWriteReceipt(**_public_artifact_kwargs(mini.write_result.receipt))
    with pytest.raises(TypeError, match="factory-only"):
        MmcifWriteResult(
            payload=mini.write_result.payload,
            receipt=mini.write_result.receipt,
        )
    with pytest.raises(TypeError, match="factory-only"):
        MmcifRoundTripReport(**_public_artifact_kwargs(mini.report))
    with pytest.raises(TypeError, match="factory-only"):
        MmcifRoundTripResult(
            source_ingest=mini.source_ingest,
            write_result=mini.write_result,
            reparsed_ingest=mini.reparsed_ingest,
            report=mini.report,
        )

    with pytest.raises(ValueError, match="cross-consistent"):
        MmcifRoundTripResult(
            source_ingest=other.source_ingest,
            write_result=mini.write_result,
            reparsed_ingest=mini.reparsed_ingest,
            report=mini.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_receipt_count_forgery_cannot_form_a_successful_write_result() -> None:
    result = round_trip_mmcif_source(MINI_PROTEIN.read_bytes())
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    forged_values = {
        "atom_count": result.write_result.receipt.atom_count + 1,
        "bond_count": 1,
        "model_count": 2,
        "output_byte_count": len(result.write_result.payload) + 1,
    }
    for optional_count in (
        "output_token_count",
        "output_physical_line_count",
        "atom_site_row_count",
        "atom_site_header_count",
    ):
        if optional_count in receipt_kwargs:
            forged_values[optional_count] = int(receipt_kwargs[optional_count]) + 1

    for field_name, forged_value in forged_values.items():
        forged_kwargs = dict(receipt_kwargs)
        forged_kwargs[field_name] = forged_value
        with pytest.raises((TypeError, ValueError)):
            forged_receipt = MmcifWriteReceipt(
                **forged_kwargs,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )
            MmcifWriteResult(
                payload=result.write_result.payload,
                receipt=forged_receipt,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )


@pytest.mark.parametrize("forged_value", [True, 1.0])
@pytest.mark.parametrize(
    "field_name",
    [
        "output_byte_count",
        "output_token_count",
        "output_physical_line_count",
        "atom_count",
        "atom_site_row_count",
        "atom_site_header_count",
    ],
)
def test_occupancy_receipt_counts_reject_bool_and_float_equivalents(
    field_name: str,
    forged_value: object,
) -> None:
    result = round_trip_mmcif_source(_occupancy_source("-0"))
    receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
    receipt_kwargs[field_name] = forged_value
    with pytest.raises(TypeError, match="nonnegative integer"):
        MmcifWriteReceipt(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_occupancy_round_trip_report_and_aggregate_cannot_cross_wire_signed_zero() -> (
    None
):
    positive = round_trip_mmcif_source(
        _occupancy_source("+0", data_name="occupancy-aggregate-wire")
    )
    negative = round_trip_mmcif_source(
        _occupancy_source("-0", data_name="occupancy-aggregate-wire")
    )

    report_kwargs = _public_artifact_kwargs(positive.report)
    report_kwargs["reparsed_representable_state_sha256"] = (
        negative.report.reparsed_representable_state_sha256
    )
    with pytest.raises(ValueError, match="representable-state hashes"):
        MmcifRoundTripReport(
            **report_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    with pytest.raises(ValueError, match="cross-consistent"):
        MmcifRoundTripResult(
            source_ingest=positive.source_ingest,
            write_result=negative.write_result,
            reparsed_ingest=negative.reparsed_ingest,
            report=negative.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_b_factor_round_trip_report_and_aggregate_cannot_cross_wire_signed_zero() -> (
    None
):
    positive = round_trip_mmcif_source(
        _occupancy_b_factor_source(
            "1.0",
            "+0",
            data_name="b-factor-aggregate-wire",
        )
    )
    negative = round_trip_mmcif_source(
        _occupancy_b_factor_source(
            "1.0",
            "-0",
            data_name="b-factor-aggregate-wire",
        )
    )

    report_kwargs = _public_artifact_kwargs(positive.report)
    report_kwargs["reparsed_representable_state_sha256"] = (
        negative.report.reparsed_representable_state_sha256
    )
    with pytest.raises(ValueError, match="representable-state hashes"):
        MmcifRoundTripReport(
            **report_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )

    with pytest.raises(ValueError, match="cross-consistent"):
        MmcifRoundTripResult(
            source_ingest=positive.source_ingest,
            write_result=negative.write_result,
            reparsed_ingest=negative.reparsed_ingest,
            report=negative.report,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_receipt_profile_count_and_payload_headers_cannot_cross_wire() -> None:
    core11 = round_trip_mmcif_source(_document(data_name="receipt-profile"))
    core12_charge = round_trip_mmcif_source(
        _formal_charge_source("+1", data_name="receipt-profile")
    )
    core12_insertion = round_trip_mmcif_source(
        _insertion_code_source("A", data_name="receipt-profile")
    )
    core12_occupancy = round_trip_mmcif_source(
        _occupancy_source("1.0", data_name="receipt-profile")
    )
    core13 = round_trip_mmcif_source(
        _insertion_code_source(
            "A",
            charge="+1",
            data_name="receipt-profile",
        )
    )
    core13_measurements = round_trip_mmcif_source(
        _occupancy_b_factor_source("1.0", "20.0", data_name="receipt-profile")
    )

    for result, forged_profile, forged_count in (
        (core11, "core12_pdbx_formal_charge", 12),
        (core12_charge, "core11", 11),
        (core12_insertion, "core12_pdbx_formal_charge", 12),
        (core12_charge, "core12_pdbx_pdb_ins_code", 12),
        (core12_occupancy, "core12_pdbx_formal_charge", 12),
        (core12_charge, "core12_occupancy", 12),
        (
            core13_measurements,
            "core13_pdbx_formal_charge_pdbx_pdb_ins_code",
            13,
        ),
        (core13, "core13_occupancy_b_iso_or_equiv", 13),
        (
            core13,
            "core12_pdbx_pdb_ins_code",
            12,
        ),
    ):
        receipt_kwargs = _public_artifact_kwargs(result.write_result.receipt)
        receipt_kwargs["atom_site_header_profile"] = forged_profile
        receipt_kwargs["atom_site_header_count"] = forged_count
        forged_receipt = MmcifWriteReceipt(
            **receipt_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )
        with pytest.raises(ValueError, match="header profile"):
            MmcifWriteResult(
                payload=result.write_result.payload,
                receipt=forged_receipt,
                _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
            )

    core11_kwargs = _public_artifact_kwargs(core11.write_result.receipt)
    core11_kwargs["atom_site_header_count"] = 12
    with pytest.raises(ValueError, match="header count"):
        MmcifWriteReceipt(
            **core11_kwargs,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


@pytest.mark.parametrize(
    "variant",
    [
        "doubled_whitespace",
        "quoted_token",
        "row_comment",
        "crlf",
        "blank_line",
        "uppercase_header",
        "nonshortest_coordinate",
    ],
)
def test_forged_receipt_cannot_admit_parse_equivalent_noncanonical_payload(
    variant: str,
) -> None:
    result = round_trip_mmcif_source(_document(), source_id="forged-payload")
    payload = _noncanonical_payload_variant(result.write_result.payload, variant)
    assert payload != result.write_result.payload
    forged_receipt = _forged_receipt_for_payload(result, payload)

    with pytest.raises(ValueError):
        MmcifWriteResult(
            payload=payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_forged_receipt_cannot_cross_wire_distinct_canonical_payloads() -> None:
    first = round_trip_mmcif_source(
        _document(
            (_row(atom_name="CA", x="0.0"),),
            data_name="wire_a",
        ),
        source_id="wire-a",
    )
    second = round_trip_mmcif_source(
        _document(
            (_row(atom_name="CB", x="1.0"),),
            data_name="wire_b",
        ),
        source_id="wire-b",
    )
    first_receipt = first.write_result.receipt
    second_receipt = second.write_result.receipt

    assert first.write_result.payload != second.write_result.payload
    assert first_receipt.input_topology_sha256 != (second_receipt.input_topology_sha256)
    assert first_receipt.input_representable_state_sha256 != (
        second_receipt.input_representable_state_sha256
    )
    assert (
        first_receipt.output_byte_count,
        first_receipt.output_token_count,
        first_receipt.output_physical_line_count,
        first_receipt.atom_count,
        first_receipt.atom_site_row_count,
    ) == (
        second_receipt.output_byte_count,
        second_receipt.output_token_count,
        second_receipt.output_physical_line_count,
        second_receipt.atom_count,
        second_receipt.atom_site_row_count,
    )

    receipt_kwargs = _public_artifact_kwargs(first_receipt)
    for field_name in (
        "output_source_sha256",
        "output_byte_count",
        "output_token_count",
        "output_physical_line_count",
        "atom_count",
        "bond_count",
        "model_count",
        "atom_site_row_count",
        "atom_site_header_profile",
        "atom_site_header_count",
    ):
        receipt_kwargs[field_name] = getattr(second_receipt, field_name)
    forged_receipt = MmcifWriteReceipt(
        **receipt_kwargs,
        _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
    )

    with pytest.raises(ValueError, match="regenerated payload bindings"):
        MmcifWriteResult(
            payload=second.write_result.payload,
            receipt=forged_receipt,
            _factory_token=writer_module._ARTIFACT_FACTORY_TOKEN,
        )


def test_round_trip_accessors_are_fresh_detached_snapshots() -> None:
    result = round_trip_mmcif_source(MINI_PROTEIN.read_bytes())
    source_coordinates = result.source_ingest.system.coordinates.clone()
    reparsed_coordinates = result.reparsed_ingest.system.coordinates.clone()

    exposed_source = result.source_ingest
    exposed_reparsed = result.reparsed_ingest
    exposed_source.system.coordinates[0, 0, 0] = 123.0
    exposed_reparsed.system.coordinates[0, 0, 0] = -456.0

    assert torch.equal(result.source_ingest.system.coordinates, source_coordinates)
    assert torch.equal(result.reparsed_ingest.system.coordinates, reparsed_coordinates)
    result.__post_init__()


def test_success_repr_is_bounded_and_does_not_expose_payloads() -> None:
    result = round_trip_mmcif_source(MINI_PROTEIN.read_bytes())
    result_repr = repr(result)
    write_repr = repr(result.write_result)

    assert len(result_repr) < 5_000
    assert len(write_repr) < 2_000
    assert "_atom_site.group_pdb" not in result_repr.lower()
    assert "ATOM 1 C CA" not in result_repr
    assert "coordinates_ieee754" not in result_repr
    assert "tier_beta_mini_protein" not in result_repr


def test_writer_rejects_wrong_input_type_without_partial_output() -> None:
    with pytest.raises(TypeError, match="exact AllAtomSystem"):
        serialize_mmcif(b"not-a-system")
