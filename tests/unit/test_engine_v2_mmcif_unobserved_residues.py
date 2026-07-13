from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_unobserved_residues as unobserved_module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION,
    MmcifNonpolyIdentityError,
    parse_mmcif_nonpoly_identity,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    MmcifPolymerSequenceError,
    parse_mmcif_polymer_sequence,
)
from betelgeuze_engine_v2.molecular.mmcif_unobserved_residues import (
    MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES,
    MAX_MMCIF_UNOBSERVED_RESIDUE_ROWS,
    MAX_MMCIF_UNOBSERVED_RESIDUE_SOURCE_ID_BYTES,
    MMCIF_UNOBSERVED_RESIDUE_ENVELOPE_VERSION,
    MMCIF_UNOBSERVED_RESIDUE_PROJECTION_SCOPE,
    MmcifUnobservedResidueError,
    emit_mmcif_unobserved_residues,
    parse_mmcif_unobserved_residues,
    round_trip_mmcif_unobserved_residues_source,
    serialize_mmcif_unobserved_residues,
)
from betelgeuze_engine_v2.molecular.mmcif_writer import (
    MMCIF_WRITER_VERSION,
    MmcifWriteError,
    write_mmcif,
)
from betelgeuze_engine_v2.molecular.pdb_mmcif import (
    MMCIF_PARSER_VERSION,
    StructureParseError,
    parse_mmcif,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_unobserved_residues"
)
SINGLE = FIXTURES / "single_unobserved_member.cif"
MULTIPLE = FIXTURES / "multiple_ordered_claims.cif"
SHARED_ASYM = FIXTURES / "shared_entity_multiple_asym.cif"
COMPOSED = FIXTURES / "composed_nonpoly_carrier.cif"
CATEGORY_ORDER = FIXTURES / "category_order_variant.cif"
INSERTION = FIXTURES / "insertion_marker_auth_alias.cif"

_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "modeled_residue_presence_assessed",
    "modified_residue_identity_assessed",
    "polymer_chemistry_interpreted",
    "microheterogeneity_interpreted",
    "chemistry_interpreted",
    "role_assignment_interpreted",
    "bond_topology_interpreted",
    "bond_order_interpreted",
    "coordination_interpreted",
    "charge_interpreted",
    "protonation_interpreted",
    "missing_residue_fact_claimed",
    "sequence_completeness_claimed",
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


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _assert_error(source: bytes, code: str) -> MmcifUnobservedResidueError:
    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        parse_mmcif_unobserved_residues(source)
    assert exc_info.value.code == code
    return exc_info.value


def _assert_claim_boundary(document: dict[str, object]) -> None:
    assert document["source_reported_unobserved_residue_claims_preserved"] is True
    for field_name in _FALSE_GATES:
        assert document[field_name] is False


def test_single_claim_round_trip_is_exact_and_does_not_promote_fact() -> None:
    source = SINGLE.read_bytes()
    ingest = parse_mmcif_unobserved_residues(source, source_id="single-claim")
    write_result = emit_mmcif_unobserved_residues(ingest)
    result = round_trip_mmcif_unobserved_residues_source(
        source, source_id="single-claim"
    )

    assert MMCIF_UNOBSERVED_RESIDUE_ENVELOPE_VERSION == "1.0.0"
    assert MMCIF_UNOBSERVED_RESIDUE_PROJECTION_SCOPE == (
        "source_reported_unobserved_polymer_residue_claims_only"
    )
    assert ingest.full_source_sha256 == hashlib.sha256(source).hexdigest()
    assert ingest.carrier_kind == "mmcif_polymer_sequence"
    assert len(ingest.unobserved_residue_rows) == 1
    assert serialize_mmcif_unobserved_residues(ingest) == write_result.payload
    assert result.source_ingest.unobserved_residue_rows == (
        result.reparsed_ingest.unobserved_residue_rows
    )
    assert result.source_ingest.unobserved_residue_projection_sha256 == (
        result.reparsed_ingest.unobserved_residue_projection_sha256
    )
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert result.report.second_emission_byte_stable is True
    assert result.report.unobserved_residue_projection_sha256_equal is True
    assert result.report.record_state_sha256_equal is True
    assert b"1 Y 1 1 X ALA 102 ? A ALA 2\n" in write_result.payload

    for artifact in (
        ingest.to_dict(),
        write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        _assert_claim_boundary(artifact)


def test_multiple_claims_preserve_source_order_and_exact_projection() -> None:
    result = round_trip_mmcif_unobserved_residues_source(MULTIPLE.read_bytes())
    payload = result.write_result.payload
    first = b"1 Y 1 1 X ALA 102 ? A ALA 2"
    second = b"2 Y 1 1 X SER 103 ? A SER 3"

    assert len(result.source_ingest.unobserved_residue_rows) == 2
    assert payload.index(first) < payload.index(second)
    assert result.source_ingest.unobserved_residue_rows == (
        result.reparsed_ingest.unobserved_residue_rows
    )


def test_shared_entity_multiple_asym_claims_remain_instance_specific() -> None:
    result = round_trip_mmcif_unobserved_residues_source(SHARED_ASYM.read_bytes())
    payload = result.write_result.payload

    assert len(result.source_ingest.unobserved_residue_rows) == 2
    assert b"1 Y 1 1 AX ALA 102 ? A ALA 2" in payload
    assert b"2 Y 1 1 BX SER 203 ? B SER 3" in payload
    assert result.report.unobserved_residue_projection_sha256_equal is True


def test_composed_nonpoly_carrier_is_bound_without_scope_promotion() -> None:
    result = round_trip_mmcif_unobserved_residues_source(
        COMPOSED.read_bytes(), source_id="composed"
    )
    ingest = result.source_ingest

    assert ingest.carrier_kind == "mmcif_polymer_sequence_nonpoly_identity"
    assert ingest.has_nonpoly_identity is True
    assert ingest.nonpoly_identity_projection_sha256 is not None
    assert ingest.nonpoly_identity_record_state_sha256 is not None
    assert result.report.nonpoly_identity_projection_sha256_equal is True
    assert result.report.nonpoly_identity_record_state_sha256_equal is True
    lower = ingest.polymer_sequence_ingest
    assert lower.has_nonpoly_identity is True
    assert lower.nonpoly_identity_projection_sha256 == (
        ingest.nonpoly_identity_projection_sha256
    )

    text = result.write_result.payload.decode("ascii").lower()
    categories = (
        "_entity.id",
        "_struct_asym.id",
        "_entity_poly_seq.entity_id",
        "_pdbx_entity_nonpoly.entity_id",
        "_pdbx_nonpoly_scheme.asym_id",
        "_pdbx_unobs_or_zero_occ_residues.id",
        "_atom_site.group_pdb",
    )
    offsets = [text.index(category) for category in categories]
    assert offsets == sorted(offsets)
    for artifact in (
        ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        _assert_claim_boundary(artifact)


def test_category_order_normalizes_but_source_binding_remains_distinct() -> None:
    canonical = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    reordered = round_trip_mmcif_unobserved_residues_source(CATEGORY_ORDER.read_bytes())

    assert canonical.write_result.payload == reordered.write_result.payload
    assert canonical.source_ingest.unobserved_residue_projection_sha256 == (
        reordered.source_ingest.unobserved_residue_projection_sha256
    )
    assert canonical.source_ingest.record_state_sha256 == (
        reordered.source_ingest.record_state_sha256
    )
    assert canonical.source_ingest.source_binding_sha256 != (
        reordered.source_ingest.source_binding_sha256
    )
    assert canonical.write_result.receipt.receipt_sha256 != (
        reordered.write_result.receipt.receipt_sha256
    )


def test_auth_alias_and_insertion_marker_are_preserved_as_source_identity() -> None:
    result = round_trip_mmcif_unobserved_residues_source(INSERTION.read_bytes())
    assert b"7 Y 1 1 AUTH-A ALA AUTH-42 B A ALA 2\n" in (result.write_result.payload)
    assert result.source_ingest.unobserved_residue_rows == (
        result.reparsed_ingest.unobserved_residue_rows
    )
    _assert_claim_boundary(result.to_dict())


def test_report_does_not_require_raw_missingness_report_sha_equality() -> None:
    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    source_missingness = result.source_ingest.base_ingest.missingness_evidence
    reparsed_missingness = result.reparsed_ingest.base_ingest.missingness_evidence

    assert source_missingness.report_sha256 != reparsed_missingness.report_sha256
    assert source_missingness.canonical_topology_sha256 == (
        reparsed_missingness.canonical_topology_sha256
    )
    assert result.report.unobserved_residue_projection_sha256_equal is True
    assert result.report.record_state_sha256_equal is True
    assert result.report.second_emission_byte_stable is True


def test_existing_parser_writer_and_carrier_versions_are_unchanged() -> None:
    source = SINGLE.read_bytes()
    assert MMCIF_PARSER_VERSION == "1.9.0"
    assert MMCIF_WRITER_VERSION == "1.5.0"
    assert MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION == "1.0.0"
    assert MMCIF_NONPOLY_IDENTITY_ENVELOPE_VERSION == "1.0.0"

    ingest = parse_mmcif_unobserved_residues(source)
    base = ingest.base_ingest
    assert base.missingness_evidence.source_reported_missing_residue_count == 1
    with pytest.raises(MmcifWriteError) as write_exc:
        write_mmcif(base.system)
    assert write_exc.value.code == "unsupported_missingness_evidence"

    with pytest.raises(StructureParseError) as base_exc:
        parse_mmcif(source)
    assert base_exc.value.code == "unsupported_context_category"

    with pytest.raises(MmcifPolymerSequenceError) as polymer_exc:
        parse_mmcif_polymer_sequence(source)
    assert polymer_exc.value.code == "unsupported_category_surface"
    with pytest.raises(MmcifNonpolyIdentityError):
        parse_mmcif_nonpoly_identity(source)


@pytest.mark.parametrize(
    ("source", "code"),
    (
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"_pdbx_unobs_or_zero_occ_residues.id\n_pdbx_unobs_or_zero_occ_residues.polymer_flag\n",
                b"_pdbx_unobs_or_zero_occ_residues.polymer_flag\n_pdbx_unobs_or_zero_occ_residues.id\n",
            ),
            "unsupported_category_headers",
        ),
        (
            _replace_once(
                MULTIPLE.read_bytes(),
                b"2 Y 1 1 X SER 103 ? A SER 3\n",
                b"1 Y 1 1 X SER 103 ? A SER 3\n",
            ),
            "duplicate_or_invalid_unobserved_residue_id",
        ),
        (
            _replace_once(
                MULTIPLE.read_bytes(),
                b"2 Y 1 1 X SER 103 ? A SER 3\n",
                b"2 Y 1 1 X ALA 102 ? A ALA 2\n",
            ),
            "duplicate_unobserved_residue_identity",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"1 Y 1 1 X ALA 102 ? A ALA 2\n",
                b"1 Y 1 1 X VAL 102 ? A VAL 2\n",
            ),
            "unobserved_residue_sequence_join_mismatch",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"? A ALA 2\n", b"? B ALA 2\n"),
            "unknown_unobserved_residue_asym_id",
        ),
        (
            _replace_once(COMPOSED.read_bytes(), b"? A ALA 2\n", b"? L ALA 2\n"),
            "unobserved_residue_nonpolymer_entity",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"ATOM 2 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER X OG 1\n",
                b"ATOM 2 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER X OG 1\n"
                b"ATOM 3 C CA . ALA A 1 2 ? 1 0 0 1.0 20.0 ? 102 ALA X CA 1\n",
            ),
            "unobserved_residue_present_in_coordinates",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 Y 1 1 X ALA", b"1 N 1 1 X ALA"),
            "unsupported_unobserved_residue_polymer_flag",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 Y 1 1 X ALA", b"1 Y 0 1 X ALA"),
            "unsupported_unobserved_residue_occupancy_flag",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 Y 1 1 X ALA", b"1 Y 1 2 X ALA"),
            "unsupported_unobserved_residue_model",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"loop_\n_atom_site.group_PDB\n",
                b"_pdbx_unobs_or_zero_occ_atoms.id 1\n#\nloop_\n_atom_site.group_PDB\n",
            ),
            "unsupported_category_surface",
        ),
        (
            _replace_once(
                _replace_once(
                    SINGLE.read_bytes(),
                    b"_pdbx_unobs_or_zero_occ_residues.label_seq_id\n",
                    b"_pdbx_unobs_or_zero_occ_residues.label_seq_id\n"
                    b"_pdbx_unobs_or_zero_occ_residues.local_extension\n",
                ),
                b"1 Y 1 1 X ALA 102 ? A ALA 2\n",
                b"1 Y 1 1 X ALA 102 ? A ALA 2 PRIVATE\n",
            ),
            "unsupported_category_headers",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"loop_\n_atom_site.group_PDB\n",
                b"_chem_comp.id GLY\n#\nloop_\n_atom_site.group_PDB\n",
            ),
            "unsupported_category_surface",
        ),
    ),
)
def test_selected_failure_contract_is_fail_closed(source: bytes, code: str) -> None:
    _assert_error(source, code)


def test_non_ascii_error_does_not_echo_opaque_input() -> None:
    source = _replace_once(
        SINGLE.read_bytes(),
        b"1 Y 1 1 X ALA 102 ? A ALA 2\n",
        b"1 Y 1 1 X PRIVATE-\xff 102 ? A ALA 2\n",
    )
    error = _assert_error(source, "non_ascii_input")
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "PRIVATE" not in str(error)
    assert "PRIVATE" not in repr(error)


def test_input_types_and_resource_caps_are_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SINGLE.read_bytes()
    for value in (bytearray(source), memoryview(source), source.decode("ascii")):
        with pytest.raises(TypeError):
            parse_mmcif_unobserved_residues(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_unobserved_residues(source, source_id=1)  # type: ignore[arg-type]

    monkeypatch.setattr(unobserved_module, "MAX_MMCIF_UNOBSERVED_RESIDUE_ROWS", 0)
    _assert_error(source, "too_many_unobserved_residue_rows")
    monkeypatch.setattr(
        unobserved_module,
        "MAX_MMCIF_UNOBSERVED_RESIDUE_ROWS",
        MAX_MMCIF_UNOBSERVED_RESIDUE_ROWS,
    )
    monkeypatch.setattr(
        unobserved_module, "MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES", len(source) - 1
    )
    _assert_error(source, "input_too_large")
    assert MAX_MMCIF_UNOBSERVED_RESIDUE_INPUT_BYTES == 64 * 1024 * 1024


def test_public_artifacts_are_frozen_factory_only_repr_hidden_and_detached() -> None:
    result = round_trip_mmcif_unobserved_residues_source(INSERTION.read_bytes())
    ingest = result.source_ingest
    row = ingest.unobserved_residue_rows[0]

    for artifact in (
        row,
        ingest,
        result.write_result.receipt,
        result.write_result,
        result.report,
        result,
    ):
        assert "AUTH-42" not in repr(artifact)
        assert "AUTH-A" not in repr(artifact)
    with pytest.raises(TypeError, match="factory-only"):
        type(row)()
    with pytest.raises(TypeError, match="factory-only"):
        type(result.report)()
    with pytest.raises(FrozenInstanceError):
        row.auth_seq_id = "CHANGED"  # type: ignore[misc]

    system = ingest.system
    original = float(ingest.system.coordinates[0, 0, 0])
    system.coordinates[0, 0, 0] = original + 100.0
    assert float(ingest.system.coordinates[0, 0, 0]) == original


@pytest.mark.parametrize(
    "binding_field",
    (
        "unobserved_residue_projection_sha256",
        "record_state_sha256",
        "source_binding_sha256",
    ),
)
def test_stale_ingest_bindings_are_rejected(binding_field: str) -> None:
    ingest = parse_mmcif_unobserved_residues(SINGLE.read_bytes())
    object.__setattr__(ingest, binding_field, "0" * 64)
    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        emit_mmcif_unobserved_residues(ingest)
    assert exc_info.value.code == "stale_ingest_binding"


def test_crosswired_carrier_system_and_rows_are_rejected() -> None:
    ingest = parse_mmcif_unobserved_residues(SINGLE.read_bytes())
    foreign = parse_mmcif_unobserved_residues(SHARED_ASYM.read_bytes())

    object.__setattr__(
        ingest, "unobserved_residue_rows", foreign.unobserved_residue_rows
    )
    with pytest.raises(MmcifUnobservedResidueError) as row_exc:
        emit_mmcif_unobserved_residues(ingest)
    assert row_exc.value.code == "stale_ingest_binding"

    ingest = parse_mmcif_unobserved_residues(SINGLE.read_bytes())
    object.__setattr__(ingest, "_carrier_source_bytes", foreign._carrier_source_bytes)
    with pytest.raises(MmcifUnobservedResidueError) as carrier_exc:
        emit_mmcif_unobserved_residues(ingest)
    assert carrier_exc.value.code == "stale_ingest_binding"

    ingest = parse_mmcif_unobserved_residues(SINGLE.read_bytes())
    object.__setattr__(
        ingest, "_system_snapshot_payload", foreign._system_snapshot_payload
    )
    with pytest.raises(MmcifUnobservedResidueError) as system_exc:
        emit_mmcif_unobserved_residues(ingest)
    assert system_exc.value.code == "stale_ingest_binding"


def test_crosswired_receipt_report_and_same_output_aggregate_are_rejected() -> None:
    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    receipt_document = json.loads(
        result.write_result.receipt._document_bytes.decode("ascii")
    )
    receipt_document["receipt_sha256"] = "0" * 64
    object.__setattr__(
        result.write_result.receipt,
        "_document_bytes",
        json.dumps(
            receipt_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii"),
    )
    with pytest.raises(MmcifUnobservedResidueError):
        result.to_dict()

    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    report_document = json.loads(result.report._document_bytes.decode("ascii"))
    report_document["round_trip_report_sha256"] = "0" * 64
    object.__setattr__(
        result.report,
        "_document_bytes",
        json.dumps(
            report_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii"),
    )
    with pytest.raises(MmcifUnobservedResidueError):
        result.to_dict()

    canonical = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    reordered = round_trip_mmcif_unobserved_residues_source(CATEGORY_ORDER.read_bytes())
    assert canonical.write_result.payload == reordered.write_result.payload
    object.__setattr__(canonical, "write_result", reordered.write_result)
    with pytest.raises(MmcifUnobservedResidueError):
        canonical.to_dict()


def test_coherently_rewritten_receipt_and_payload_cannot_replace_canonical_output() -> (
    None
):
    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    write_result = result.write_result
    receipt = write_result.receipt
    evil_payload = b"data_evil\n#\n"
    evil_document = unobserved_module._receipt_document(receipt._ingest, evil_payload)
    object.__setattr__(receipt, "_payload", evil_payload)
    object.__setattr__(
        receipt,
        "_document_bytes",
        unobserved_module._canonical_json_bytes(evil_document),
    )
    object.__setattr__(write_result, "payload", evil_payload)

    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        write_result.to_dict()
    assert exc_info.value.code == "stale_write_receipt"


def test_same_payload_different_source_id_artifacts_cannot_be_crosswired() -> None:
    source = SINGLE.read_bytes()
    left = round_trip_mmcif_unobserved_residues_source(source, source_id="left")
    right = round_trip_mmcif_unobserved_residues_source(source, source_id="right")
    assert left.write_result.payload == right.write_result.payload

    object.__setattr__(left, "reparsed_ingest", right.reparsed_ingest)
    object.__setattr__(left, "reemitted_write_result", right.reemitted_write_result)
    with pytest.raises(MmcifUnobservedResidueError) as aggregate_exc:
        left.to_dict()
    assert aggregate_exc.value.code == "crosswired_round_trip_artifacts"

    left = round_trip_mmcif_unobserved_residues_source(source, source_id="left")
    right = round_trip_mmcif_unobserved_residues_source(source, source_id="right")
    object.__setattr__(right, "report", left.report)
    with pytest.raises(MmcifUnobservedResidueError) as report_exc:
        right.to_dict()
    assert report_exc.value.code == "crosswired_round_trip_artifacts"


def test_nested_aggregate_type_tamper_is_a_typed_failure() -> None:
    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    object.__setattr__(result, "write_result", None)
    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        result.to_dict()
    assert exc_info.value.code == "crosswired_round_trip_artifacts"


@pytest.mark.parametrize(
    ("target", "field_name", "code"),
    (
        ("write_result", "receipt", "stale_write_result"),
        ("receipt", "_ingest", "stale_write_receipt"),
        ("report", "_source", "stale_round_trip_report"),
        ("report", "_write_result", "stale_round_trip_report"),
    ),
)
def test_standalone_nested_type_tamper_is_a_typed_failure(
    target: str, field_name: str, code: str
) -> None:
    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    artifact = {
        "write_result": result.write_result,
        "receipt": result.write_result.receipt,
        "report": result.report,
    }[target]
    object.__setattr__(artifact, field_name, None)
    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        artifact.to_dict()
    assert exc_info.value.code == code


def test_receipt_and_report_properties_reject_noncanonical_or_nonfinite_json() -> None:
    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    receipt = result.write_result.receipt
    object.__setattr__(receipt, "_document_bytes", b" " + receipt._document_bytes)
    with pytest.raises(MmcifUnobservedResidueError) as receipt_exc:
        _ = receipt.receipt_sha256
    assert receipt_exc.value.code == "invalid_write_receipt"

    result = round_trip_mmcif_unobserved_residues_source(SINGLE.read_bytes())
    object.__setattr__(
        result.report,
        "_document_bytes",
        b'{"round_trip_report_sha256":NaN}',
    )
    with pytest.raises(MmcifUnobservedResidueError) as report_exc:
        _ = result.report.round_trip_report_sha256
    assert report_exc.value.code == "invalid_round_trip_report"


@pytest.mark.parametrize(
    ("source_id", "code"),
    (
        (
            "x" * (MAX_MMCIF_UNOBSERVED_RESIDUE_SOURCE_ID_BYTES + 1),
            "source_id_too_large",
        ),
        ("\ud800", "invalid_source_id"),
    ),
)
def test_source_id_is_resource_bounded_and_unicode_scalar_safe(
    source_id: str, code: str
) -> None:
    with pytest.raises(MmcifUnobservedResidueError) as exc_info:
        parse_mmcif_unobserved_residues(SINGLE.read_bytes(), source_id=source_id)
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    "path",
    sorted(FIXTURES.glob("*.cif")),
    ids=lambda path: path.stem,
)
def test_every_positive_fixture_has_stable_second_emission(path: Path) -> None:
    result = round_trip_mmcif_unobserved_residues_source(
        path.read_bytes(), source_id=path.stem
    )
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert result.report.second_emission_byte_stable is True
    assert result.report.unobserved_residue_projection_sha256_equal is True
    assert result.report.record_state_sha256_equal is True
