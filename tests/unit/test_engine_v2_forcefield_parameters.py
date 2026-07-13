from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.forcefield import (
    EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
    EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    FORCE_FIELD_UNIT_SYSTEM_ID,
    SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS,
    ExactMethaneBondAngleParameterAssignmentReport,
    ExactMethaneBondAngleParameterSet,
    ForceFieldParameterContractError,
    ForceFieldParameterSerializationError,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    analyze_exact_methane_bond_angle_parameter_assignment,
    deserialize_exact_methane_bond_angle_parameter_set,
    serialize_exact_methane_bond_angle_parameter_set,
)
from betelgeuze_engine_v2.forcefield import parameters as parameter_module
from betelgeuze_engine_v2.molecular import (
    deserialize_all_atom_system,
    parse_sdf_v2000,
    serialize_all_atom_system,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_ingest_corpus"
METHANE = FIXTURES / "methane_explicit_h.sdf"
C13_METHANE = FIXTURES / "methane_c13_explicit_h.sdf"


class _FormStringSubclass(str):
    pass


class _AlwaysEqualString(str):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__


def _parameter_set(
    *,
    bond_length: float = 1.0,
    bond_force_constant: float = 1.0,
    angle_value: float = 1.0,
    angle_force_constant: float = 1.0,
    artifact_schema_version: str = (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
    ),
    functional_form_id: str | None = None,
) -> ExactMethaneBondAngleParameterSet:
    return ExactMethaneBondAngleParameterSet(
        parameter_set_id="nonphysical_exact_methane_contract_fixture",
        parameter_set_version="1.0.0",
        derivation_status="declared_contract_fixture",
        bond_parameter=HarmonicBondParameter(
            parameter_id="fixture_ch_bond",
            equilibrium_length_angstrom=bond_length,
            force_constant_kj_mol_angstrom2=bond_force_constant,
        ),
        angle_parameter=HarmonicAngleParameter(
            parameter_id="fixture_hch_angle",
            equilibrium_angle_radian=angle_value,
            force_constant_kj_mol_radian2=angle_force_constant,
        ),
        artifact_schema_version=artifact_schema_version,
        functional_form_id=functional_form_id,
    )


def _methane_system(source: bytes | None = None, *, source_id: str = "methane"):
    return parse_sdf_v2000(
        METHANE.read_bytes() if source is None else source,
        source_id=source_id,
    ).system


def _form_bound_parameter_set() -> ExactMethaneBondAngleParameterSet:
    return _parameter_set(
        artifact_schema_version=(
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
        ),
        functional_form_id=EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    )


def _canonical_json(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _atom_line(element: str) -> str:
    return (
        f"{0.0:10.4f}{0.0:10.4f}{0.0:10.4f} {element:<3}"
        f"{0:2d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
        f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
    )


def _bond_line(atom_i: int, atom_j: int) -> str:
    return f"{atom_i:3d}{atom_j:3d}{1:3d}{0:3d}"


def _sdf_record(
    elements: tuple[str, ...],
    bonds: tuple[tuple[int, int], ...],
) -> bytes:
    lines = [
        "parameter-contract-fixture",
        "betelgeuze-v2",
        "nonphysical-test-only",
        f"{len(elements):3d}{len(bonds):3d}  0  0  0  0  0  0  0  0999 V2000",
        *(_atom_line(element) for element in elements),
        *(_bond_line(atom_i, atom_j) for atom_i, atom_j in bonds),
        "M  END",
        "$$$$",
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _ethane_source() -> bytes:
    return _sdf_record(
        ("C", "C", "H", "H", "H", "H", "H", "H"),
        (
            (1, 2),
            (1, 3),
            (1, 4),
            (1, 5),
            (2, 6),
            (2, 7),
            (2, 8),
        ),
    )


def test_nonphysical_parameter_contract_has_fixed_units_and_no_authority() -> None:
    parameter_set = _parameter_set()
    payload = parameter_set.to_dict()

    assert payload["schema_id"] == EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID
    assert payload["schema_version"] == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
    )
    assert parameter_set.artifact_schema_version == "1.0.0"
    assert parameter_set.functional_form_id is None
    assert "functional_form_id" not in payload
    assert payload["parameter_scope"] == EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE
    assert payload["assignment_policy_id"] == (
        EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID
    )
    assert payload["unit_system"] == {
        "unit_system_id": FORCE_FIELD_UNIT_SYSTEM_ID,
        "coordinate_length": "angstrom",
        "bond_equilibrium_length": "angstrom",
        "angle_equilibrium_value": "radian",
        "energy": "kilojoule_per_mole",
        "bond_force_constant": "kilojoule_per_mole_per_angstrom_squared",
        "angle_force_constant": "kilojoule_per_mole_per_radian_squared",
        "numeric_encoding": "ieee754_binary64_big_endian_hex",
    }
    assert payload["bond_parameter"] == {
        "parameter_id": "fixture_ch_bond",
        "equilibrium_length_ieee754_binary64_be": "3ff0000000000000",
        "force_constant_ieee754_binary64_be": "3ff0000000000000",
    }
    assert payload["angle_parameter"] == {
        "parameter_id": "fixture_hch_angle",
        "equilibrium_angle_ieee754_binary64_be": "3ff0000000000000",
        "force_constant_ieee754_binary64_be": "3ff0000000000000",
    }
    assert parameter_set.parameter_payload_sha256 == (
        "fb28de63f3128c13daaa599ad95a2fbbda2e33847d6c42c2185e92969841af61"
    )
    assert parameter_set.parameter_set_sha256 == (
        "a3487327f2f596cf5e7a7a2f27671c1084ac074dba0e1dab63df2916fcc6a8ae"
    )
    assert parameter_set.artifact_purpose == "contract_fixture_only"
    assert parameter_set.fit_execution_status == "not_run"
    assert parameter_set.parameter_artifact_authentication_status == (
        "not_authenticated"
    )
    assert parameter_set.license_review_status == "not_reviewed"
    assert parameter_set.scientific_validation_status == "missing"
    assert parameter_set.runtime_authorization_status == "prohibited"
    assert parameter_set.parameterability_assessed is False
    assert parameter_set.parameterizable is False
    assert parameter_set.global_parameter_coverage_complete is False
    assert parameter_set.runtime_eligible is False
    assert parameter_set.execution_authorized is False
    assert parameter_set.claim_safe is False


def test_parameter_set_serialization_round_trip_and_strict_tamper_checks() -> None:
    parameter_set = _parameter_set()
    serialized = serialize_exact_methane_bond_angle_parameter_set(parameter_set)
    restored = deserialize_exact_methane_bond_angle_parameter_set(serialized)

    assert len(serialized) == 2579
    assert hashlib.sha256(serialized).hexdigest() == (
        "cc0be8bedb08f0f06b2f5b4d5255dde3991db5f5296dddf9956c191a95963ee0"
    )
    assert restored == parameter_set
    assert serialize_exact_methane_bond_angle_parameter_set(restored) == serialized
    assert json.loads(serialized) == parameter_set.to_dict()

    document = json.loads(serialized)
    document["unit_system"]["energy"] = "kilocalorie_per_mole"
    with pytest.raises(
        ForceFieldParameterSerializationError,
        match="stale or forged",
    ):
        deserialize_exact_methane_bond_angle_parameter_set(
            json.dumps(document).encode("ascii")
        )

    document = json.loads(serialized)
    document["parameter_set_sha256"] = "0" * 64
    with pytest.raises(
        ForceFieldParameterSerializationError,
        match="stale or forged",
    ):
        deserialize_exact_methane_bond_angle_parameter_set(
            json.dumps(document).encode("ascii")
        )

    document = json.loads(serialized)
    document["parameterizable"] = True
    with pytest.raises(
        ForceFieldParameterSerializationError,
        match="stale or forged",
    ):
        deserialize_exact_methane_bond_angle_parameter_set(
            json.dumps(document).encode("ascii")
        )

    document = json.loads(serialized)
    document["approved"] = True
    with pytest.raises(ForceFieldParameterSerializationError, match="keys mismatch"):
        deserialize_exact_methane_bond_angle_parameter_set(
            json.dumps(document).encode("ascii")
        )

    duplicate = b'{"schema_id":"forged",' + serialized[1:]
    with pytest.raises(ForceFieldParameterSerializationError, match="duplicate"):
        deserialize_exact_methane_bond_angle_parameter_set(duplicate)

    noncanonical = json.dumps(json.loads(serialized), indent=2).encode("ascii")
    with pytest.raises(ForceFieldParameterSerializationError, match="byte-canonical"):
        deserialize_exact_methane_bond_angle_parameter_set(noncanonical)

    false_as_integer = json.loads(serialized)
    false_as_integer["parameterizable"] = 0
    false_as_integer_payload = json.dumps(
        false_as_integer,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    with pytest.raises(ForceFieldParameterSerializationError, match="byte-canonical"):
        deserialize_exact_methane_bond_angle_parameter_set(
            false_as_integer_payload
        )


def test_form_bound_1_1_artifact_round_trip_hashes_and_assignment_binding() -> None:
    legacy = _parameter_set()
    parameter_set = _form_bound_parameter_set()
    payload = parameter_set.to_dict()
    serialized = serialize_exact_methane_bond_angle_parameter_set(parameter_set)
    restored = deserialize_exact_methane_bond_angle_parameter_set(serialized)

    assert SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS == frozenset(
        {"1.0.0", "1.1.0"}
    )
    assert parameter_set.artifact_schema_version == "1.1.0"
    assert parameter_module.EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert parameter_set.schema_id == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
    )
    assert payload["schema_version"] == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
    )
    assert payload["functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert parameter_set._payload_document()["functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert parameter_set.parameter_payload_sha256 != (
        legacy.parameter_payload_sha256
    )
    assert parameter_set.parameter_set_sha256 != legacy.parameter_set_sha256
    assert restored == parameter_set
    assert serialize_exact_methane_bond_angle_parameter_set(restored) == serialized

    system = _methane_system()
    legacy_assignment = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        legacy,
    )
    assignment = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        parameter_set,
    )
    assignment_payload = assignment.to_dict()
    assert assignment.bond_angle_assignment_complete is True
    assert len(assignment.bond_assignments) == 4
    assert len(assignment.angle_assignments) == 6
    assert assignment_payload["parameter_set_schema_id"] == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
    )
    assert assignment_payload["parameter_payload_sha256"] == (
        parameter_set.parameter_payload_sha256
    )
    assert assignment.parameter_assignment_sha256 != (
        legacy_assignment.parameter_assignment_sha256
    )
    assert parameter_set.parameterability_assessed is False
    assert parameter_set.parameterizable is False
    assert parameter_set.global_parameter_coverage_complete is False
    assert parameter_set.runtime_eligible is False
    assert parameter_set.execution_authorized is False
    assert parameter_set.claim_safe is False
    assert assignment.physics_supported is False
    assert assignment.energy_evaluation_authorized is False
    assert assignment.force_evaluation_authorized is False
    assert assignment.minimization_authorized is False
    assert assignment.simulation_ready is False
    assert assignment.claim_safe is False


@pytest.mark.parametrize(
    ("schema_version", "functional_form_id"),
    [
        (
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
            EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
        ),
        (
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
            None,
        ),
        (
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
            "harmonic_half_k_delta_squared_bond_angle/2.0.0",
        ),
        ("1.2.0", EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID),
    ],
)
def test_parameter_schema_and_functional_form_combinations_are_exact(
    schema_version: str,
    functional_form_id: str | None,
) -> None:
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(
            artifact_schema_version=schema_version,
            functional_form_id=functional_form_id,
        )

    with pytest.raises(TypeError, match="artifact_schema_version"):
        _parameter_set(  # type: ignore[arg-type]
            artifact_schema_version=True,
            functional_form_id=None,
        )


@pytest.mark.parametrize(
    "functional_form_id",
    [
        True,
        1,
        [],
        {},
        _FormStringSubclass(EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID),
    ],
)
def test_form_bound_schema_requires_an_exact_builtin_string(
    functional_form_id: object,
) -> None:
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(
            artifact_schema_version=(
                EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
            ),
            functional_form_id=functional_form_id,  # type: ignore[arg-type]
        )


def test_parameter_serializer_and_assignment_revalidate_tampered_state() -> None:
    parameter_set = _form_bound_parameter_set()
    assert not hasattr(parameter_set, "__dict__")
    assert not hasattr(parameter_set.bond_parameter, "__dict__")
    assert not hasattr(parameter_set.angle_parameter, "__dict__")
    with pytest.raises(AttributeError):
        object.__setattr__(parameter_set, "to_dict", lambda: {"claim_safe": True})
    with pytest.raises(AttributeError):
        object.__setattr__(
            parameter_set.bond_parameter,
            "to_dict",
            lambda: {"force_constant": "forged"},
        )

    downgraded = _form_bound_parameter_set()
    object.__setattr__(
        downgraded,
        "artifact_schema_version",
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
    )
    with pytest.raises(ForceFieldParameterContractError):
        serialize_exact_methane_bond_angle_parameter_set(downgraded)
    with pytest.raises(ForceFieldParameterContractError):
        analyze_exact_methane_bond_angle_parameter_assignment(
            _methane_system(),
            downgraded,
        )

    forged_form = _form_bound_parameter_set()
    object.__setattr__(forged_form, "functional_form_id", "forged_form/9.9.9")
    with pytest.raises(ForceFieldParameterContractError):
        serialize_exact_methane_bond_angle_parameter_set(forged_form)
    with pytest.raises(ForceFieldParameterContractError):
        analyze_exact_methane_bond_angle_parameter_assignment(
            _methane_system(),
            forged_form,
        )

    forged_units = _form_bound_parameter_set()
    object.__setattr__(
        forged_units,
        "_unit_system_items",
        (("unit_system_id", "forged"),),
    )
    with pytest.raises(ForceFieldParameterContractError, match="unit-system"):
        serialize_exact_methane_bond_angle_parameter_set(forged_units)


def test_schema_aware_deserializer_rejects_mismatch_downgrade_and_form_tamper() -> None:
    legacy = _parameter_set().to_dict()
    bound = _form_bound_parameter_set().to_dict()

    legacy_with_form = dict(legacy)
    legacy_with_form["functional_form_id"] = (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    with pytest.raises(ForceFieldParameterSerializationError, match="keys mismatch"):
        deserialize_exact_methane_bond_angle_parameter_set(
            _canonical_json(legacy_with_form)
        )

    bound_without_form = dict(bound)
    del bound_without_form["functional_form_id"]
    with pytest.raises(ForceFieldParameterSerializationError, match="keys mismatch"):
        deserialize_exact_methane_bond_angle_parameter_set(
            _canonical_json(bound_without_form)
        )

    wrong_form = dict(bound)
    wrong_form["functional_form_id"] = (
        "harmonic_half_k_delta_squared_bond_angle/2.0.0"
    )
    with pytest.raises(
        ForceFieldParameterContractError,
        match="fixed exact-methane harmonic functional form",
    ):
        deserialize_exact_methane_bond_angle_parameter_set(
            _canonical_json(wrong_form)
        )

    for schema_id, schema_version in (
        (
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID,
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
        ),
        (
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1,
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
        ),
        (
            "betelgeuze.exact_methane_bond_angle_parameter_set/1.2.0",
            "1.2.0",
        ),
    ):
        mismatch = dict(bound)
        mismatch["schema_id"] = schema_id
        mismatch["schema_version"] = schema_version
        with pytest.raises(ForceFieldParameterSerializationError):
            deserialize_exact_methane_bond_angle_parameter_set(
                _canonical_json(mismatch)
            )

    stale_downgrade = dict(bound)
    stale_downgrade["schema_id"] = (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID
    )
    stale_downgrade["schema_version"] = (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
    )
    del stale_downgrade["functional_form_id"]
    with pytest.raises(
        ForceFieldParameterSerializationError,
        match="stale or forged",
    ):
        deserialize_exact_methane_bond_angle_parameter_set(
            _canonical_json(stale_downgrade)
        )


def test_fixed_unit_contract_cannot_mutate_existing_parameter_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameter_set = _parameter_set()
    baseline = parameter_set.parameter_set_sha256

    with pytest.raises(TypeError):
        parameter_module._FORCE_FIELD_UNIT_SYSTEM["energy"] = "forged"  # type: ignore[index]
    monkeypatch.setattr(
        parameter_module,
        "_FORCE_FIELD_UNIT_SYSTEM_ITEMS",
        (("unit_system_id", "forged"),),
    )
    assert parameter_set.parameter_set_sha256 == baseline


def test_exported_schema_and_form_constants_cannot_redefine_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _parameter_set()
    form_bound = _form_bound_parameter_set()
    assignment = analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(),
        form_bound,
    )
    legacy_bytes = serialize_exact_methane_bond_angle_parameter_set(legacy)
    form_bound_bytes = serialize_exact_methane_bond_angle_parameter_set(
        form_bound
    )
    assignment_payload = assignment.to_dict()

    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION",
        "9.0.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID",
        "forged.schema/9.0.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1",
        "9.1.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1",
        "forged.schema/9.1.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS",
        frozenset({"9.0.0", "9.1.0"}),
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID",
        "forged_harmonic_form/9.0.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PROFILE_ID",
        "forged_profile_v9",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE",
        "forged_parameter_scope",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID",
        "forged_assignment_policy/9.0.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION",
        "9.0.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID",
        "forged.assignment/9.0.0",
    )
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID",
        "forged.inventory/9.0.0",
    )

    assert serialize_exact_methane_bond_angle_parameter_set(legacy) == (
        legacy_bytes
    )
    assert serialize_exact_methane_bond_angle_parameter_set(form_bound) == (
        form_bound_bytes
    )
    reconstructed = _parameter_set(
        artifact_schema_version="1.1.0",
        functional_form_id=(
            "harmonic_half_k_delta_squared_bond_angle/1.0.0"
        ),
    )
    assert serialize_exact_methane_bond_angle_parameter_set(
        reconstructed
    ) == form_bound_bytes
    assert assignment.to_dict() == assignment_payload
    assert analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(),
        form_bound,
    ).to_dict() == assignment_payload
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(
            artifact_schema_version="1.1.0",
            functional_form_id="forged_harmonic_form/9.0.0",
        )
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(artifact_schema_version="9.1.0")


def test_derivation_and_assignment_state_require_exact_types_and_snapshots() -> None:
    with pytest.raises(ForceFieldParameterContractError):
        replace(
            _parameter_set(),
            derivation_status=_AlwaysEqualString("forged_status"),
        )

    tampered_parameter_set = _parameter_set()
    object.__setattr__(
        tampered_parameter_set,
        "derivation_status",
        _AlwaysEqualString("forged_status"),
    )
    with pytest.raises(ForceFieldParameterContractError):
        serialize_exact_methane_bond_angle_parameter_set(
            tampered_parameter_set
        )
    with pytest.raises(ForceFieldParameterContractError):
        analyze_exact_methane_bond_angle_parameter_assignment(
            _methane_system(),
            tampered_parameter_set,
        )

    report = analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(),
        _parameter_set(),
    )
    assert not hasattr(report, "__dict__")
    assert all(not hasattr(item, "__dict__") for item in report.bond_assignments)
    assert all(not hasattr(item, "__dict__") for item in report.angle_assignments)
    with pytest.raises(AttributeError):
        object.__setattr__(report, "to_dict", lambda: {"claim_safe": True})
    with pytest.raises(AttributeError):
        object.__setattr__(
            report.bond_assignments[0],
            "to_dict",
            lambda: {"parameter_id": "forged"},
        )

    assignment = report.bond_assignments[0]
    assignment_payload = assignment.to_dict()
    object.__setattr__(
        assignment.identity,
        "to_dict",
        lambda: {"atom_i": 999, "atom_j": 1000},
    )
    assert assignment.to_dict() == assignment_payload

    object.__setattr__(
        assignment,
        "parameter_id",
        _AlwaysEqualString("forged_parameter"),
    )
    with pytest.raises((TypeError, ForceFieldParameterContractError)):
        report.to_dict()

    report = analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(),
        _parameter_set(),
    )
    object.__setattr__(
        report.parameter_set.bond_parameter,
        "force_constant_kj_mol_angstrom2",
        2.0,
    )
    with pytest.raises(ForceFieldParameterContractError, match="changed"):
        report.to_dict()


@pytest.mark.parametrize(
    "encoded",
    [
        "3FF0000000000000",
        "7ff0000000000000",
        "fff0000000000000",
        "7ff8000000000000",
        "8000000000000000",
    ],
)
def test_deserializer_rejects_noncanonical_or_invalid_binary64_hex(
    encoded: str,
) -> None:
    document = _parameter_set().to_dict()
    document["bond_parameter"][
        "equilibrium_length_ieee754_binary64_be"
    ] = encoded
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    with pytest.raises(
        (ForceFieldParameterContractError, ForceFieldParameterSerializationError)
    ):
        deserialize_exact_methane_bond_angle_parameter_set(payload)


def test_deserializer_rejects_nested_duplicates_unit_shape_and_resource_abuse() -> None:
    serialized = serialize_exact_methane_bond_angle_parameter_set(_parameter_set())
    nested_duplicate = serialized.replace(
        b'"parameter_id":"fixture_ch_bond"',
        b'"parameter_id":"fixture_ch_bond","parameter_id":"forged"',
        1,
    )
    with pytest.raises(ForceFieldParameterSerializationError, match="duplicate"):
        deserialize_exact_methane_bond_angle_parameter_set(nested_duplicate)

    for mutation in ("missing", "extra"):
        document = json.loads(serialized)
        if mutation == "missing":
            del document["unit_system"]["energy"]
        else:
            document["unit_system"]["distance_alias"] = "angstroms"
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        with pytest.raises(
            ForceFieldParameterSerializationError,
            match="stale or forged",
        ):
            deserialize_exact_methane_bond_angle_parameter_set(payload)

    with pytest.raises(ForceFieldParameterSerializationError, match="byte limit"):
        deserialize_exact_methane_bond_angle_parameter_set(b" " * (1024 * 1024 + 1))

    deeply_nested = (
        b'{"schema_id":' + b"[" * 1200 + b"0" + b"]" * 1200 + b"}"
    )
    with pytest.raises(ForceFieldParameterSerializationError):
        deserialize_exact_methane_bond_angle_parameter_set(deeply_nested)


def test_same_id_content_changes_and_manifest_evidence_do_not_alias_hashes() -> None:
    baseline = _parameter_set()
    changed = _parameter_set(bond_force_constant=2.0)
    assert baseline.parameter_set_id == changed.parameter_set_id
    assert baseline.parameter_payload_sha256 != changed.parameter_payload_sha256
    assert baseline.parameter_set_sha256 != changed.parameter_set_sha256

    common = {
        "parameter_set_id": "declared_fit_candidate",
        "parameter_set_version": "1.0.0",
        "derivation_status": "declared_fit_candidate_unverified",
        "bond_parameter": HarmonicBondParameter("candidate_ch_bond", 1.0, 2.0),
        "angle_parameter": HarmonicAngleParameter("candidate_hch_angle", 1.0, 4.0),
        "dataset_manifest_sha256": "1" * 64,
        "split_manifest_sha256": "2" * 64,
        "fit_protocol_id": "synthetic_fit_protocol_v1",
    }
    first = ExactMethaneBondAngleParameterSet(
        **common,
        fit_receipt_sha256="3" * 64,
    )
    second = ExactMethaneBondAngleParameterSet(
        **common,
        fit_receipt_sha256="4" * 64,
    )
    assert first.parameter_payload_sha256 == second.parameter_payload_sha256
    assert first.parameter_set_sha256 != second.parameter_set_sha256
    assert first.fit_execution_status == second.fit_execution_status == "unverified"
    assert first.runtime_eligible is second.runtime_eligible is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -0.0])
def test_parameter_scalars_reject_nonfinite_and_negative_zero(value: float) -> None:
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(bond_length=value)
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(bond_force_constant=value)
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(angle_value=value)
    with pytest.raises(ForceFieldParameterContractError):
        _parameter_set(angle_force_constant=value)


@pytest.mark.parametrize("value", [True, 1, "1", None])
def test_parameter_scalars_require_exact_float_type(value: object) -> None:
    with pytest.raises(TypeError):
        _parameter_set(bond_length=value)  # type: ignore[arg-type]


def test_parameter_scalar_domains_and_fit_evidence_combinations_fail_closed() -> None:
    with pytest.raises(ForceFieldParameterContractError, match="positive"):
        _parameter_set(bond_length=0.0)
    with pytest.raises(ForceFieldParameterContractError, match="positive"):
        _parameter_set(bond_force_constant=0.0)
    with pytest.raises(ForceFieldParameterContractError, match="between"):
        _parameter_set(angle_value=math.pi)
    with pytest.raises(ForceFieldParameterContractError, match="between"):
        _parameter_set(angle_value=0.0)
    with pytest.raises(ForceFieldParameterContractError, match="fit evidence"):
        replace(_parameter_set(), dataset_manifest_sha256="1" * 64)
    with pytest.raises(ForceFieldParameterContractError, match="require"):
        replace(
            _parameter_set(),
            derivation_status="declared_fit_candidate_unverified",
        )

    fitted = ExactMethaneBondAngleParameterSet(
        parameter_set_id="unreviewed_fitted_candidate",
        parameter_set_version="1.0.0",
        derivation_status="declared_fit_candidate_unverified",
        bond_parameter=HarmonicBondParameter("fitted_ch_bond", 1.0, 1.0),
        angle_parameter=HarmonicAngleParameter("fitted_hch_angle", 1.0, 1.0),
        dataset_manifest_sha256="1" * 64,
        split_manifest_sha256="2" * 64,
        fit_protocol_id="synthetic_fit_protocol_v1",
        fit_receipt_sha256="3" * 64,
    )
    assert fitted.fit_execution_status == "unverified"
    assert fitted.artifact_purpose == "declared_fit_candidate_unverified"
    assert fitted.fit_evidence_review_status == "unreviewed"
    assert fitted.scientific_validation_status == "missing"
    assert fitted.runtime_eligible is False
    assert fitted.execution_authorized is False


def test_exact_methane_assignment_resolves_exact_sets_but_never_global_support() -> None:
    parameter_set = _parameter_set()
    report = analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(),
        parameter_set,
    )
    payload = report.to_dict()

    assert payload["schema_id"] == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID
    )
    assert report.assignment_status == "contract_fixture_mapped"
    assert report.bond_angle_assignment_complete is True
    assert len(report.bond_assignments) == 4
    assert len(report.angle_assignments) == 6
    assert tuple(item.identity for item in report.bond_assignments) == (
        report.inventory_report.bond_identities
    )
    assert tuple(item.identity for item in report.angle_assignments) == (
        report.inventory_report.angle_identities
    )
    assert {item.parameter_id for item in report.bond_assignments} == {
        "fixture_ch_bond"
    }
    assert {item.parameter_id for item in report.angle_assignments} == {
        "fixture_hch_angle"
    }
    assert report.parameter_assignment_sha256 == (
        "9bee7230a4a6a576eec667838507d26b8321c51dc6e8089bba7b487fcdada2ac"
    )
    assert report.report_sha256 == (
        "96bebb13307c35222b351f592c611de0e63d0173a2199abce1b673a10bf2d284"
    )
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.global_parameter_coverage_complete is False
    assert report.preparation_ready is False
    assert report.physics_supported is False
    assert report.energy_evaluation_authorized is False
    assert report.force_evaluation_authorized is False
    assert report.minimization_authorized is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert payload["atom_typing_status"] == "not_assessed"
    assert payload["partial_charge_parameter_status"] == "not_assessed"
    assert payload["vdw_parameter_status"] == "not_assessed"
    assert payload["proper_torsion_parameter_status"] == "not_assessed"
    assert payload["improper_parameter_status"] == "not_assessed"
    assert payload["constraint_parameter_status"] == "not_assessed"


def test_assignment_is_deterministic_across_snapshot_and_parameter_round_trips() -> None:
    system = _methane_system()
    parameter_set = _parameter_set()
    restored_system = deserialize_all_atom_system(serialize_all_atom_system(system))
    restored_parameters = deserialize_exact_methane_bond_angle_parameter_set(
        serialize_exact_methane_bond_angle_parameter_set(parameter_set)
    )
    baseline = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        parameter_set,
    )
    restored = analyze_exact_methane_bond_angle_parameter_assignment(
        restored_system,
        restored_parameters,
    )

    assert restored.to_dict() == baseline.to_dict()
    assert baseline.matches(system, parameter_set) is True
    changed = _parameter_set(bond_force_constant=2.0)
    changed_report = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        changed,
    )
    assert changed.parameter_payload_sha256 != parameter_set.parameter_payload_sha256
    assert changed.parameter_set_sha256 != parameter_set.parameter_set_sha256
    assert changed_report.parameter_assignment_sha256 != (
        baseline.parameter_assignment_sha256
    )
    assert changed_report.physics_supported is False


def test_source_bond_order_is_term_equivalent_and_atom_order_remains_bound() -> None:
    lines = METHANE.read_text(encoding="ascii").splitlines()
    shuffled_source = ("\n".join((*lines[:9], *reversed(lines[9:13]), *lines[13:])) + "\n").encode(
        "ascii"
    )
    parameter_set = _parameter_set()
    baseline = analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(),
        parameter_set,
    )
    shuffled = analyze_exact_methane_bond_angle_parameter_assignment(
        _methane_system(shuffled_source, source_id="shuffled-bonds"),
        parameter_set,
    )
    assert shuffled.bond_assignments == baseline.bond_assignments
    assert shuffled.angle_assignments == baseline.angle_assignments
    assert shuffled.inventory_report.canonical_topology_sha256 == (
        baseline.inventory_report.canonical_topology_sha256
    )
    assert shuffled.report_sha256 != baseline.report_sha256

    carbon_second = _methane_system(
        _sdf_record(
            ("H", "C", "H", "H", "H"),
            ((2, 1), (2, 3), (2, 4), (2, 5)),
        ),
        source_id="carbon-second",
    )
    reordered = analyze_exact_methane_bond_angle_parameter_assignment(
        carbon_second,
        parameter_set,
    )
    assert reordered.assignment_status == "contract_fixture_mapped"
    assert len(reordered.bond_assignments) == 4
    assert len(reordered.angle_assignments) == 6
    assert reordered.parameter_assignment_sha256 != baseline.parameter_assignment_sha256


@pytest.mark.parametrize(
    "source",
    [
        C13_METHANE.read_bytes(),
        METHANE.read_bytes().replace(
            b"M  END\n",
            b"M  CHG  1   1   1\nM  END\n",
            1,
        ),
        _ethane_source(),
    ],
)
def test_out_of_scope_systems_never_expose_parameter_assignments(source: bytes) -> None:
    system = _methane_system(source, source_id="out-of-scope")
    report = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        _parameter_set(),
    )

    assert report.assignment_status == "unsupported_system"
    assert report.bond_angle_assignment_complete is False
    assert report.bond_assignments == ()
    assert report.angle_assignments == ()
    assert report.parameter_assignment_sha256 is None
    assert "bond_angle_parameters_not_assigned" in report.blockers
    assert report.runtime_eligible is False
    assert report.execution_authorized is False


def test_coordinate_only_and_foreign_partial_charge_state_never_gain_authority() -> None:
    system = _methane_system()
    parameter_set = _parameter_set()
    baseline = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        parameter_set,
    )
    moved = system.with_coordinates(system.coordinates + 0.25)
    moved_report = analyze_exact_methane_bond_angle_parameter_assignment(
        moved,
        parameter_set,
    )
    assert moved_report.to_dict() == baseline.to_dict()

    charged_atom = replace(system.atoms[0], partial_charge_e=0.5)
    foreign_partial_charge = replace(
        system,
        atoms=(charged_atom, *system.atoms[1:]),
    )
    charge_report = analyze_exact_methane_bond_angle_parameter_assignment(
        foreign_partial_charge,
        parameter_set,
    )
    assert charge_report.assignment_status == "contract_fixture_mapped"
    assert charge_report.to_dict()["partial_charge_parameter_status"] == (
        "not_assessed"
    )
    assert charge_report.energy_evaluation_authorized is False

    nonfinite = system.with_coordinates(
        torch.full_like(system.coordinates, float("nan"))
    )
    invalid_report = analyze_exact_methane_bond_angle_parameter_assignment(
        nonfinite,
        parameter_set,
    )
    assert invalid_report.assignment_status == "invalid_system"
    assert invalid_report.bond_assignments == ()


def test_assignment_and_parameter_contracts_reject_constructor_promotion() -> None:
    system = _methane_system()
    parameter_set = _parameter_set()
    report = ExactMethaneBondAngleParameterAssignmentReport(system, parameter_set)

    with pytest.raises(TypeError):
        ExactMethaneBondAngleParameterAssignmentReport(  # type: ignore[call-arg]
            system,
            parameter_set,
            assignment_status="contract_fixture_mapped",
        )
    with pytest.raises(TypeError):
        replace(report, assignment_status="contract_fixture_mapped")
    with pytest.raises(TypeError):
        replace(parameter_set, parameterizable=True)  # type: ignore[call-arg]
    with pytest.raises(ForceFieldParameterContractError):
        replace(parameter_set, parameter_set_id="FORGED")
