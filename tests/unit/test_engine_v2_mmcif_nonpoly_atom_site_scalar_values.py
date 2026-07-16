from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_atom_site_scalar_values as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_atom_site_scalar_values import (
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_DICTIONARY_ITEMS,
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID,
    MmcifNonpolyAtomSiteScalarValueError,
    mmcif_nonpoly_atom_site_scalar_value_document,
    mmcif_nonpoly_atom_site_scalar_value_json_bytes,
    parse_mmcif_nonpoly_atom_site_scalar_values,
    require_mmcif_nonpoly_atom_site_scalar_value_document,
    write_mmcif_nonpoly_atom_site_scalar_value_json,
)
from tests.unit.test_engine_v2_mmcif_nonpoly_atom_site_observations import (
    ATOM_SITE_ROWS,
    _source,
    _updated,
)


def _scalar_error(source: str, code: str) -> MmcifNonpolyAtomSiteScalarValueError:
    with pytest.raises(MmcifNonpolyAtomSiteScalarValueError) as exc_info:
        parse_mmcif_nonpoly_atom_site_scalar_values(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_marker_states_and_known_numeric_values_are_bound_without_defaults() -> None:
    snapshot = parse_mmcif_nonpoly_atom_site_scalar_values(_source())

    assert [row.source_atom_id for row in snapshot.scalar_observations] == [2, 3, 4]
    carbon, oxygen, water = snapshot.scalar_observations
    assert carbon.occupancy.state == "known"
    assert carbon.occupancy.numeric_value == 0.5
    assert carbon.occupancy.binary64_bits_hex == "3fe0000000000000"
    assert carbon.b_iso_or_equiv.state == "unknown"
    assert carbon.b_iso_or_equiv.numeric_value is None
    assert carbon.formal_charge.state == "known"
    assert carbon.formal_charge.integer_value == 0
    assert oxygen.occupancy.state == "not_applicable"
    assert oxygen.occupancy.numeric_value is None
    assert oxygen.b_iso_or_equiv.numeric_value == -1.0
    assert oxygen.formal_charge.state == "unknown"
    assert water.occupancy.numeric_value == 1.0
    assert len(carbon.scalar_value_identity_sha256) == 64
    assert len(carbon.scalar_source_binding_sha256) == 64

    payload = snapshot.to_dict()
    assert payload["state_counts"] == {
        "occupancy": {"known": 2, "unknown": 0, "not_applicable": 1},
        "b_iso_or_equiv": {"known": 2, "unknown": 1, "not_applicable": 0},
        "formal_charge": {"known": 1, "unknown": 2, "not_applicable": 0},
    }
    for flag in (
        "source_atom_site_scalar_tokens_preserved",
        "atom_site_identity_joined",
        "coordinate_values_interpreted",
        "occupancy_marker_state_interpreted",
        "occupancy_values_interpreted",
        "occupancy_unit_interval_verified",
        "b_factor_marker_state_interpreted",
        "b_factor_interpreted",
        "formal_charge_marker_state_interpreted",
        "formal_charge_interpreted",
        "formal_charge_dictionary_range_verified",
    ):
        assert payload[flag] is True
    for flag in (
        "source_authenticated",
        "occupancy_default_inferred",
        "occupancy_population_interpreted",
        "b_factor_quality_assessed",
        "b_factor_units_interpreted",
        "standard_uncertainty_interpreted",
        "formal_charge_chemistry_validated",
        "coordinate_units_interpreted",
        "coordinate_geometry_interpreted",
        "type_symbol_interpreted",
        "altloc_population_interpreted",
        "missingness_inferred",
        "connection_type_interpreted",
        "symmetry_interpreted",
        "bond_order_interpreted",
        "covalence_interpreted",
        "coordination_interpreted",
        "topology_interpreted",
        "chemistry_interpreted",
        "preparation_ready",
        "parameterability_assessed",
        "physics_supported",
        "runtime_eligible",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_standard_uncertainty_and_spelling_do_not_change_numeric_identity() -> None:
    canonical = parse_mmcif_nonpoly_atom_site_scalar_values(_source())
    with_uncertainty = parse_mmcif_nonpoly_atom_site_scalar_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.occupancy", "'0.50(2)'"
            )
        )
    )

    left = canonical.scalar_observations[0].occupancy
    right = with_uncertainty.scalar_observations[0].occupancy
    assert right.raw_lexeme == "'0.50(2)'"
    assert right.standard_uncertainty_digits == "2"
    assert left.numeric_value == right.numeric_value == 0.5
    assert left.value_identity_sha256 == right.value_identity_sha256
    assert left.source_value_binding_sha256 != right.source_value_binding_sha256
    assert canonical.scalar_projection_sha256 != with_uncertainty.scalar_projection_sha256


@pytest.mark.parametrize("token", ("-0.01", "1.01", "2", "1e309"))
def test_occupancy_domain_and_finiteness_fail_closed(token: str) -> None:
    expected = "nonfinite_scalar_value" if token == "1e309" else "occupancy_out_of_bounds"
    _scalar_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.occupancy", token
            )
        ),
        expected,
    )


@pytest.mark.parametrize("token", ("NaN", "+1.0", "0x1p0", "PRIVATE-SCALAR"))
def test_non_dictionary_float_tokens_fail_without_echo(token: str) -> None:
    error = _scalar_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.b_iso_or_equiv", token
            )
        ),
        "invalid_scalar_float",
    )

    assert token not in str(error)
    assert token not in error.detail


def test_quoted_markers_are_known_values_and_do_not_become_missing() -> None:
    _scalar_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.occupancy", "'.'"
            )
        ),
        "invalid_scalar_float",
    )


def test_formal_charge_integer_spelling_range_and_identity() -> None:
    canonical = parse_mmcif_nonpoly_atom_site_scalar_values(_source())
    equivalent = parse_mmcif_nonpoly_atom_site_scalar_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.pdbx_formal_charge", "'+00'"
            )
        )
    )
    minimum = parse_mmcif_nonpoly_atom_site_scalar_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.pdbx_formal_charge", "-8"
            )
        )
    )

    left = canonical.scalar_observations[0].formal_charge
    right = equivalent.scalar_observations[0].formal_charge
    assert left.integer_value == right.integer_value == 0
    assert left.value_identity_sha256 == right.value_identity_sha256
    assert left.source_value_binding_sha256 != right.source_value_binding_sha256
    assert minimum.scalar_observations[0].formal_charge.integer_value == -8

    _scalar_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.pdbx_formal_charge", "9"
            )
        ),
        "formal_charge_out_of_bounds",
    )
    _scalar_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.pdbx_formal_charge", "1.0"
            )
        ),
        "invalid_formal_charge_integer",
    )


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_atom_site_scalar_values(_source())
    document = mmcif_nonpoly_atom_site_scalar_value_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_NONPOLY_ATOM_SITE_SCALAR_DICTIONARY_ITEMS
    )
    assert require_mmcif_nonpoly_atom_site_scalar_value_document(document) == document
    encoded = mmcif_nonpoly_atom_site_scalar_value_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_atom_site_scalar_value_json(
        tmp_path / "scalar-values.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".scalar-values.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["scalar_projection"]["scalar_observations"][0]["occupancy"][
        "numeric_value"
    ] = 0.75
    projection_digest = module._sha256(tampered["scalar_projection"])
    tampered["scalar_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID,
            "scalar_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="numeric value mismatch"):
        require_mmcif_nonpoly_atom_site_scalar_value_document(tampered)


def test_selected_row_order_and_scalar_changes_are_bound() -> None:
    canonical = parse_mmcif_nonpoly_atom_site_scalar_values(_source())
    reordered_rows = (
        ATOM_SITE_ROWS[0],
        ATOM_SITE_ROWS[3],
        ATOM_SITE_ROWS[1],
        ATOM_SITE_ROWS[2],
    )
    reordered = parse_mmcif_nonpoly_atom_site_scalar_values(
        _source(atom_site_rows=reordered_rows)
    )
    changed = parse_mmcif_nonpoly_atom_site_scalar_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 3, "_atom_site.b_iso_or_equiv", "11.0"
            )
        )
    )

    assert [row.source_atom_id for row in reordered.scalar_observations] == [4, 2, 3]
    assert canonical.scalar_projection_sha256 != reordered.scalar_projection_sha256
    assert canonical.scalar_projection_sha256 != changed.scalar_projection_sha256


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_atom_site_scalar_values(b"data_x")  # type: ignore[arg-type]
