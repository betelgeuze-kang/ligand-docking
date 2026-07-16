from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_coordinate_values as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_coordinate_values import (
    MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID,
    MmcifNonpolyCoordinateValueError,
    mmcif_nonpoly_coordinate_value_document,
    mmcif_nonpoly_coordinate_value_json_bytes,
    parse_mmcif_nonpoly_coordinate_values,
    require_mmcif_nonpoly_coordinate_value_document,
    write_mmcif_nonpoly_coordinate_value_json,
)
from tests.unit.test_engine_v2_mmcif_nonpoly_atom_site_observations import (
    ATOM_SITE_ROWS,
    _source,
    _updated,
)


def _coordinate_error(source: str, code: str) -> MmcifNonpolyCoordinateValueError:
    with pytest.raises(MmcifNonpolyCoordinateValueError) as exc_info:
        parse_mmcif_nonpoly_coordinate_values(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_selected_coordinate_tokens_bind_numeric_values_and_exact_bits() -> None:
    snapshot = parse_mmcif_nonpoly_coordinate_values(_source())

    assert [row.source_atom_id for row in snapshot.coordinates] == [2, 3, 4]
    assert snapshot.to_dict()["coordinate_count"] == 3
    assert snapshot.to_dict()["coordinate_scalar_count"] == 9

    carbon, oxygen, water = snapshot.coordinates
    assert carbon.cartn_x.raw_value == "1.000"
    assert carbon.cartn_x.raw_lexeme == "1.000"
    assert carbon.cartn_x.numeric_value == 1.0
    assert carbon.cartn_x.binary64_bits_hex == "3ff0000000000000"
    assert carbon.cartn_x.binary64_hex == "0x1.0000000000000p+0"
    assert oxygen.cartn_x.raw_value == "1.250"
    assert oxygen.cartn_x.raw_lexeme == "'1.250'"
    assert oxygen.cartn_x.quoted is True
    assert oxygen.cartn_x.numeric_value == 1.25
    assert oxygen.cartn_x.binary64_bits_hex == "3ff4000000000000"
    assert water.cartn_z.numeric_value == 6.0
    assert len(carbon.coordinate_value_identity_sha256) == 64
    assert len(carbon.coordinate_source_binding_sha256) == 64

    payload = snapshot.to_dict()
    for flag in (
        "source_coordinate_tokens_preserved",
        "atom_site_identity_joined",
        "coordinate_values_interpreted",
        "coordinate_binary64_bits_bound",
        "coordinate_value_identity_bound",
        "coordinate_source_spelling_bound",
        "coordinate_finiteness_verified",
    ):
        assert payload[flag] is True
    for flag in (
        "coordinate_observation_scientifically_assessed",
        "source_authenticated",
        "coordinate_units_interpreted",
        "coordinate_geometry_interpreted",
        "distance_or_clash_interpreted",
        "occupancy_values_interpreted",
        "b_factor_interpreted",
        "formal_charge_interpreted",
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


def test_equivalent_spellings_share_bits_but_keep_distinct_source_binding() -> None:
    canonical = parse_mmcif_nonpoly_coordinate_values(_source())
    equivalent = parse_mmcif_nonpoly_coordinate_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", "'+1e0'"
            )
        )
    )
    double_quoted = parse_mmcif_nonpoly_coordinate_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", '"+1e0"'
            )
        )
    )

    left = canonical.coordinates[0]
    right = equivalent.coordinates[0]
    assert left.cartn_x.binary64_bits_hex == right.cartn_x.binary64_bits_hex
    assert left.cartn_x.value_identity_sha256 == right.cartn_x.value_identity_sha256
    assert left.coordinate_value_identity_sha256 == right.coordinate_value_identity_sha256
    assert left.cartn_x.source_value_binding_sha256 != right.cartn_x.source_value_binding_sha256
    assert left.coordinate_source_binding_sha256 != right.coordinate_source_binding_sha256
    assert canonical.coordinate_projection_sha256 != equivalent.coordinate_projection_sha256
    assert equivalent.coordinates[0].cartn_x.raw_lexeme == "'+1e0'"
    assert double_quoted.coordinates[0].cartn_x.raw_lexeme == '"+1e0"'
    assert (
        equivalent.coordinates[0].cartn_x.value_identity_sha256
        == double_quoted.coordinates[0].cartn_x.value_identity_sha256
    )
    assert (
        equivalent.coordinates[0].cartn_x.source_value_binding_sha256
        != double_quoted.coordinates[0].cartn_x.source_value_binding_sha256
    )


def test_signed_zero_and_subnormal_bits_are_not_silently_collapsed() -> None:
    positive_zero = parse_mmcif_nonpoly_coordinate_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", "0.0"
            )
        )
    )
    negative_zero = parse_mmcif_nonpoly_coordinate_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", "-0.0"
            )
        )
    )
    subnormal = parse_mmcif_nonpoly_coordinate_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", "5e-324"
            )
        )
    )

    assert positive_zero.coordinates[0].cartn_x.binary64_bits_hex == "0000000000000000"
    assert negative_zero.coordinates[0].cartn_x.binary64_bits_hex == "8000000000000000"
    assert subnormal.coordinates[0].cartn_x.binary64_bits_hex == "0000000000000001"
    assert (
        positive_zero.coordinates[0].coordinate_value_identity_sha256
        != negative_zero.coordinates[0].coordinate_value_identity_sha256
    )


@pytest.mark.parametrize(
    "token",
    (
        "NaN",
        "+Inf",
        "-Infinity",
        "0x1.0p0",
        "1_000.0",
        "PRIVATE-COORDINATE",
    ),
)
def test_nondecimal_coordinate_spellings_fail_closed_without_echo(token: str) -> None:
    error = _coordinate_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", token
            )
        ),
        "invalid_coordinate_decimal",
    )

    assert token not in str(error)
    assert token not in error.detail


@pytest.mark.parametrize("token", ("1e309", "-1e999"))
def test_decimal_overflow_to_infinity_fails_closed(token: str) -> None:
    _coordinate_error(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", token
            )
        ),
        "nonfinite_coordinate_value",
    )


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_coordinate_values(_source())
    document = mmcif_nonpoly_coordinate_value_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID
    assert require_mmcif_nonpoly_coordinate_value_document(document) == document
    encoded = mmcif_nonpoly_coordinate_value_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_coordinate_value_json(
        tmp_path / "coordinate-values.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".coordinate-values.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["coordinate_projection"]["coordinates"][0]["cartn_x"][
        "numeric_value"
    ] = 2.0
    projection_digest = module._sha256(tampered["coordinate_projection"])
    tampered["coordinate_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID,
            "coordinate_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="numeric value does not match raw token"):
        require_mmcif_nonpoly_coordinate_value_document(tampered)


def test_selected_row_order_and_value_changes_are_bound() -> None:
    canonical = parse_mmcif_nonpoly_coordinate_values(_source())
    reordered_rows = (
        ATOM_SITE_ROWS[0],
        ATOM_SITE_ROWS[3],
        ATOM_SITE_ROWS[1],
        ATOM_SITE_ROWS[2],
    )
    reordered = parse_mmcif_nonpoly_coordinate_values(
        _source(atom_site_rows=reordered_rows)
    )
    changed = parse_mmcif_nonpoly_coordinate_values(
        _source(
            atom_site_rows=_updated(
                ATOM_SITE_ROWS, 1, "_atom_site.cartn_z", "3.5"
            )
        )
    )

    assert [row.source_atom_id for row in reordered.coordinates] == [4, 2, 3]
    assert canonical.coordinate_projection_sha256 != reordered.coordinate_projection_sha256
    assert canonical.coordinate_projection_sha256 != changed.coordinate_projection_sha256


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_coordinate_values(b"data_x")  # type: ignore[arg-type]
