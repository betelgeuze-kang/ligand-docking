from __future__ import annotations

import ast
from collections import Counter
from dataclasses import asdict, replace
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct

import pytest

import betelgeuze_engine_v2 as package_root
from betelgeuze_engine_v2.forcefield import spice_c1c4_force_matching_targets as module
from betelgeuze_engine_v2.forcefield.spice_c1c4_force_matching_targets import (
    BOHR_TO_ANGSTROM_BINARY64_BE_HEX,
    BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL,
    HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_BINARY64_BE_HEX,
    HARTREE_TO_KJ_PER_MOL_BINARY64_BE_HEX,
    HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL,
    SPICE_C1C4_FORCE_MATCHING_TARGET_CLAIM_SCOPE,
    SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256,
    SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256,
    SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID,
    SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_BYTE_COUNT,
    SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_SHA256,
    SpiceC1C4ForceMatchingTargetReport,
    SpiceC1C4ForceMatchingTargets,
    analyze_spice_c1c4_force_matching_targets,
    derive_spice_c1c4_force_matching_targets,
    serialize_spice_c1c4_force_matching_target_report,
    serialize_spice_c1c4_force_matching_targets,
    spice_c1c4_force_matching_target_protocol_bytes,
    spice_c1c4_force_matching_target_protocol_document,
)
from betelgeuze_engine_v2.forcefield.spice_c1c4_quantum_reference import (
    SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256,
    SpiceC1C4QuantumReferenceContractError,
    load_spice_c1c4_quantum_reference_evidence,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_quantum_reference_evidence.json"
)
MODULE_PATH = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2"
    / "forcefield"
    / "spice_c1c4_force_matching_targets.py"
)
_GROUP_ORDER = ("c", "cc", "ccc", "cccc")
_PARTITIONS = ("fit", "selection", "holdout")


def _source_bytes() -> bytes:
    return SOURCE_PATH.read_bytes()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _f64_hex(value: Fraction, *, negative_zero: bool = False) -> str:
    result = float(value)
    if value == 0 and negative_zero:
        result = -0.0
    return struct.pack(">d", result).hex()


def _f32_fractions(raw_hex: str) -> list[tuple[Fraction, bool]]:
    raw = bytes.fromhex(raw_hex)
    result = []
    for index in range(0, len(raw), 4):
        chunk = raw[index : index + 4]
        (value,) = struct.unpack(">f", chunk)
        result.append(
            (Fraction.from_float(value), value == 0.0 and bool(chunk[0] & 0x80))
        )
    return result


def test_strict_source_replay_freezes_canonical_target_bytes_and_hash_dag() -> None:
    source = _source_bytes()
    targets = derive_spice_c1c4_force_matching_targets(source)
    serialized = serialize_spice_c1c4_force_matching_targets(source)
    document = json.loads(serialized)

    assert targets.schema_id == SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID
    assert targets.claim_scope == SPICE_C1C4_FORCE_MATCHING_TARGET_CLAIM_SCOPE
    assert (
        targets.source_artifact_sha256 == SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256
    )
    assert targets.protocol_sha256 == SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256
    assert SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256 == (
        "34757b44cb6ca6471ed835dce41b70bc85d4c687347fb6e598bbc7951ccd2f75"
    )
    assert targets.core_sha256 == SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256
    assert SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256 == (
        "caff216e22207a368ad640dc2fa0567dec3d3f04027b3ce2c3b8c433ee1c4c74"
    )
    assert len(serialized) == SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_BYTE_COUNT
    assert len(serialized) == 686561
    assert (
        hashlib.sha256(serialized).hexdigest()
        == SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_SHA256
    )
    assert SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_SHA256 == (
        "ff19771d03dc476dd538c99b1468bce3ada25e68623b3cb329f8e71c05fd7e13"
    )
    core = dict(document)
    supplied_core = core.pop("core_sha256")
    assert supplied_core == hashlib.sha256(_canonical_bytes(core)).hexdigest()
    assert serialize_spice_c1c4_force_matching_targets(source) == serialized


def test_counts_splits_canonical_order_and_nonblind_scope_are_exact() -> None:
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    report = analyze_spice_c1c4_force_matching_targets(_source_bytes())

    assert targets.group_order == _GROUP_ORDER
    assert targets.partition_order == _PARTITIONS
    assert targets.role_order == ("seed", "related_nearby_lower")
    assert targets.relative_energy_target_count == 100
    assert targets.force_target_record_count == 200
    assert targets.force_target_scalar_count == 5700
    assert (
        targets.fit_relative_energy_target_count,
        targets.selection_relative_energy_target_count,
        targets.holdout_relative_energy_target_count,
    ) == (60, 20, 20)
    assert (
        targets.fit_force_target_record_count,
        targets.selection_force_target_record_count,
        targets.holdout_force_target_record_count,
    ) == (120, 40, 40)
    assert (
        targets.fit_force_target_scalar_count,
        targets.selection_force_target_scalar_count,
        targets.holdout_force_target_scalar_count,
    ) == (3420, 1140, 1140)
    assert [
        (row.group_id, row.source_pair_id) for row in targets.relative_energy_targets
    ] == [(group, pair) for group in _GROUP_ORDER for pair in range(25)]
    assert [
        (row.group_id, row.source_pair_id, row.role) for row in targets.force_targets
    ] == [
        (group, pair, role)
        for group in _GROUP_ORDER
        for pair in range(25)
        for role in ("seed", "related_nearby_lower")
    ]
    assert report.exact_record_overlap_count == 0
    assert report.geometry_overlap_count == 0
    assert report.source_pair_overlap_count == 0
    assert report.derived_target_hash_overlap_count == 0
    assert report.molecular_graph_overlap_count == 4
    assert report.molecular_graph_disjoint is False
    assert report.public_holdout_blind_to_humans is False
    assert report.generic_validation_split is False
    assert (
        report.validation_scope == "within_same_four_graphs_unseen_conformations_only"
    )


def test_every_relative_energy_uses_numeric_suffix_roles_and_exact_dyadic_delta() -> (
    None
):
    source = load_spice_c1c4_quantum_reference_evidence(_source_bytes())
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    factor = Fraction(Decimal(HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL))
    target_index = {
        (row.group_id, row.source_pair_id): row
        for row in targets.relative_energy_targets
    }

    for group in source.groups:
        by_suffix = {
            int(record.qcarchive_entry_name.rsplit("-", 1)[1]): record
            for record in group.records
        }
        for pair_id in range(25):
            row = target_index[(group.group_id, pair_id)]
            seed = by_suffix[pair_id]
            related = by_suffix[pair_id + 25]
            seed_energy = Fraction.from_float(
                struct.unpack(">d", bytes.fromhex(seed.energy_binary64_be_hex))[0]
            )
            related_energy = Fraction.from_float(
                struct.unpack(">d", bytes.fromhex(related.energy_binary64_be_hex))[0]
            )
            exact_delta = seed_energy - related_energy

            assert row.seed_qcarchive_entry_name == f"{group.group_id}-{pair_id}"
            assert row.related_qcarchive_entry_name == (
                f"{group.group_id}-{pair_id + 25}"
            )
            assert row.seed_record_id == seed.record_id
            assert row.related_record_id == related.record_id
            assert row.partition == seed.partition == related.partition
            assert row.seed_record_payload_sha256 == seed.record_payload_sha256
            assert row.related_record_payload_sha256 == related.record_payload_sha256
            assert row.seed_energy_sha256 == seed.energy_sha256
            assert row.related_energy_sha256 == related.energy_sha256
            expected_numerator = (
                f"-{abs(exact_delta.numerator):x}"
                if exact_delta.numerator < 0
                else f"{exact_delta.numerator:x}"
            )
            assert row.energy_difference_hartree_signed_numerator_hex == (
                expected_numerator
            )
            assert row.energy_difference_hartree_denominator_power_of_two == (
                exact_delta.denominator.bit_length() - 1
            )
            # The member Hartree values are subtracted exactly before the one
            # binary64 conversion; neither sorting nor abs participates.
            assert row.relative_energy_kj_per_mol_binary64_be_hex == _f64_hex(
                exact_delta * factor
            )


def test_every_force_scalar_is_sign_bit_xor_and_exact_rational_conversion() -> None:
    source = load_spice_c1c4_quantum_reference_evidence(_source_bytes())
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    source_index = {
        (group.group_id, record.qcarchive_entry_name): record
        for group in source.groups
        for record in group.records
    }
    force_factor = Fraction(Decimal(HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL)) / Fraction(
        Decimal(BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL)
    )
    geometry_factor = Fraction(Decimal(BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL))
    scalar_count = 0

    for row in targets.force_targets:
        record = source_index[(row.group_id, row.qcarchive_entry_name)]
        gradient = bytes.fromhex(record.gradient_binary32_be_hex)
        force = bytes.fromhex(row.force_hartree_per_bohr_binary32_be_hex)
        assert len(force) == len(gradient)
        for index in range(0, len(force), 4):
            assert force[index] == gradient[index] ^ 0x80
            assert force[index + 1 : index + 4] == gradient[index + 1 : index + 4]
            scalar_count += 1

        expected_force = b"".join(
            bytes.fromhex(_f64_hex(value * force_factor, negative_zero=negative_zero))
            for value, negative_zero in _f32_fractions(force.hex())
        )
        expected_geometry = b"".join(
            bytes.fromhex(
                _f64_hex(value * geometry_factor, negative_zero=negative_zero)
            )
            for value, negative_zero in _f32_fractions(record.geometry_binary32_be_hex)
        )
        assert row.force_kj_per_mol_per_angstrom_binary64_be_hex == (
            expected_force.hex()
        )
        assert row.geometry_angstrom_binary64_be_hex == expected_geometry.hex()
        assert row.force_hartree_per_bohr_sha256 == hashlib.sha256(force).hexdigest()
        assert (
            row.force_kj_per_mol_per_angstrom_sha256
            == hashlib.sha256(expected_force).hexdigest()
        )
        assert (
            row.geometry_angstrom_sha256
            == hashlib.sha256(expected_geometry).hexdigest()
        )
    assert scalar_count == 5700


def test_signed_zero_is_flipped_and_preserved_by_converted_zero() -> None:
    raw = bytes.fromhex("00000000800000003f800000bf800000")
    negated = module._negate_binary32_sign_bits(raw)
    assert negated.hex() == "8000000000000000bf8000003f800000"
    assert (
        module._fraction_to_binary64_bytes(Fraction(), negative_zero=True).hex()
        == "8000000000000000"
    )
    assert (
        module._fraction_to_binary64_bytes(Fraction(), negative_zero=False).hex()
        == "0000000000000000"
    )
    with pytest.raises(module.SpiceC1C4ForceMatchingTargetContractError):
        module._negate_binary32_sign_bits(b"\x00")


def test_codata_protocol_constants_use_independent_decimal_fraction_oracle() -> None:
    bohr = Fraction(Decimal("0.529177210544"))
    hartree = Fraction(Decimal("2625.499639479162971656"))
    gradient = hartree / bohr

    assert _f64_hex(bohr) == BOHR_TO_ANGSTROM_BINARY64_BE_HEX
    assert _f64_hex(hartree) == HARTREE_TO_KJ_PER_MOL_BINARY64_BE_HEX
    assert _f64_hex(gradient) == (
        HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_BINARY64_BE_HEX
    )
    assert module._PROTOCOL_DOCUMENT["unit_convention"]["interpretation"] == (
        "2022_CODATA_central_values_frozen_as_exact_protocol_decimals_not_a_"
        "claim_of_physical_exactness"
    )
    assert (
        module._PROTOCOL_DOCUMENT["unit_convention"]["openmm_constants_used"] is False
    )
    protocol_bytes = spice_c1c4_force_matching_target_protocol_bytes()
    protocol_document = spice_c1c4_force_matching_target_protocol_document()
    assert protocol_document == module._PROTOCOL_DOCUMENT
    assert hashlib.sha256(protocol_bytes).hexdigest() == (
        SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256
    )
    protocol_document["protocol_id"] = "mutated"
    assert (
        spice_c1c4_force_matching_target_protocol_document()["protocol_id"]
        == module.SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_ID
    )


def test_topology_source_and_row_hashes_bind_every_derived_target() -> None:
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    topology_hashes = {
        topology.group_id: topology.topology_sha256 for topology in targets.topologies
    }
    assert len(topology_hashes) == 4
    for topology in targets.topologies:
        body = asdict(topology)
        supplied = body.pop("topology_sha256")
        assert (
            supplied
            == hashlib.sha256(
                b"spice-c1c4-target-topology-v1\0" + _canonical_bytes(body)
            ).hexdigest()
        )
    for row in targets.relative_energy_targets:
        body = asdict(row)
        supplied = body.pop("target_sha256")
        assert row.topology_sha256 == topology_hashes[row.group_id]
        assert (
            supplied
            == hashlib.sha256(
                b"spice-c1c4-relative-energy-target-v1\0" + _canonical_bytes(body)
            ).hexdigest()
        )
    for row in targets.force_targets:
        body = asdict(row)
        supplied = body.pop("target_sha256")
        assert row.topology_sha256 == topology_hashes[row.group_id]
        assert (
            supplied
            == hashlib.sha256(
                b"spice-c1c4-force-target-v1\0" + _canonical_bytes(body)
            ).hexdigest()
        )


def test_raw_net_force_and_centroid_torque_diagnostics_replay_exactly() -> None:
    source = load_spice_c1c4_quantum_reference_evidence(_source_bytes())
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    group_by_id = {group.group_id: group for group in source.groups}
    bohr = Fraction(Decimal(BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL))
    force_factor = Fraction(Decimal(HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL)) / bohr
    observed_max_force = 0.0
    observed_max_torque = 0.0

    for row in targets.force_targets:
        group = group_by_id[row.group_id]
        geometry = [
            value * bohr
            for value, _ in _f32_fractions(
                next(
                    record.geometry_binary32_be_hex
                    for record in group.records
                    if record.qcarchive_entry_name == row.qcarchive_entry_name
                )
            )
        ]
        forces = [
            value * force_factor
            for value, _ in _f32_fractions(row.force_hartree_per_bohr_binary32_be_hex)
        ]
        centroid = tuple(
            sum(
                (geometry[atom * 3 + axis] for atom in range(group.atom_count)),
                Fraction(),
            )
            / group.atom_count
            for axis in range(3)
        )
        net = tuple(
            sum(
                (forces[atom * 3 + axis] for atom in range(group.atom_count)),
                Fraction(),
            )
            for axis in range(3)
        )
        torque = [Fraction(), Fraction(), Fraction()]
        for atom in range(group.atom_count):
            rx, ry, rz = (
                geometry[atom * 3 + axis] - centroid[axis] for axis in range(3)
            )
            fx, fy, fz = (forces[atom * 3 + axis] for axis in range(3))
            torque[0] += ry * fz - rz * fy
            torque[1] += rz * fx - rx * fz
            torque[2] += rx * fy - ry * fx

        net_raw = b"".join(bytes.fromhex(_f64_hex(value)) for value in net)
        torque_raw = b"".join(bytes.fromhex(_f64_hex(value)) for value in torque)
        net_norm = math.sqrt(float(sum((value * value for value in net), Fraction())))
        torque_norm = math.sqrt(
            float(sum((value * value for value in torque), Fraction()))
        )
        assert row.net_force_kj_per_mol_per_angstrom_binary64_be_hex == net_raw.hex()
        assert row.net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex == (
            struct.pack(">d", net_norm).hex()
        )
        assert row.torque_about_coordinate_centroid_kj_per_mol_binary64_be_hex == (
            torque_raw.hex()
        )
        assert (
            row.torque_norm_kj_per_mol_binary64_be_hex
            == struct.pack(">d", torque_norm).hex()
        )
        observed_max_force = max(observed_max_force, net_norm)
        observed_max_torque = max(observed_max_torque, torque_norm)

    report = analyze_spice_c1c4_force_matching_targets(_source_bytes())
    assert report.max_net_force_norm_kj_per_mol_per_angstrom == observed_max_force
    assert report.max_torque_norm_kj_per_mol == observed_max_torque
    assert struct.pack(">d", observed_max_force).hex() == "3fc1ae32cb6de50c"
    assert struct.pack(">d", observed_max_torque).hex() == "3fc759704f02a8db"
    assert observed_max_force == pytest.approx(0.13812861378736618)
    assert observed_max_torque == pytest.approx(0.18241695268563415)
    assert report.projection_applied is False


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("qcarchive_entry_name", "c-25"),
        ("partition", "holdout"),
        ("record_payload_sha256", "0" * 64),
        ("gradient_binary32_be_hex", "00000000"),
    ],
)
def test_source_role_split_hash_and_width_tampering_is_rejected(
    field: str, replacement: object
) -> None:
    document = json.loads(_source_bytes())
    document["groups"][0]["records"][0][field] = replacement
    core = dict(document)
    core.pop("core_sha256")
    document["core_sha256"] = hashlib.sha256(_canonical_bytes(core)).hexdigest()
    with pytest.raises(SpiceC1C4QuantumReferenceContractError):
        derive_spice_c1c4_force_matching_targets(_canonical_bytes(document))


def test_dataset_and_report_are_immutable_factory_only_and_report_is_canonical() -> (
    None
):
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    report = analyze_spice_c1c4_force_matching_targets(_source_bytes())
    assert isinstance(targets, SpiceC1C4ForceMatchingTargets)
    assert isinstance(report, SpiceC1C4ForceMatchingTargetReport)
    with pytest.raises(TypeError, match="factory-only"):
        replace(targets, _factory_token=object())
    with pytest.raises(TypeError, match="factory-only"):
        replace(report, _factory_token=object())
    with pytest.raises((AttributeError, TypeError)):
        targets.force_targets = ()  # type: ignore[misc]
    report_bytes = serialize_spice_c1c4_force_matching_target_report(_source_bytes())
    assert report_bytes == _canonical_bytes(asdict(report))


def test_all_promotion_fields_remain_false_and_no_projection_is_hidden() -> None:
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    report = analyze_spice_c1c4_force_matching_targets(_source_bytes())
    promotion_fields = (
        "license_human_reviewed",
        "source_whole_file_authenticated",
        "energy_gradient_finite_difference_consistency_established",
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "parameter_identifiability_established",
        "parameter_family_sufficiency_assessed",
        "reference_validation_performed",
        "production_parameters_available",
        "parameterability_assessed",
        "parameterizable",
        "physics_ready",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
    )
    assert all(getattr(targets, field) is False for field in promotion_fields)
    assert all(getattr(report, field) is False for field in promotion_fields)
    assert targets.projection_applied is False
    assert targets.mean_removal_applied is False
    assert targets.clipping_applied is False
    assert targets.denoising_applied is False
    assert targets.target_view_only is True


def test_module_is_isolated_from_fitting_parameters_kernels_fixtures_and_runtime() -> (
    None
):
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    prohibited_fragments = (
        "fitting",
        "fixture",
        "parameter",
        "kernel",
        "runtime",
        "openmm",
        "numpy",
    )
    assert not [
        name
        for name in imports
        if any(fragment in name.lower() for fragment in prohibited_fragments)
    ]
    assert not hasattr(package_root, "derive_spice_c1c4_force_matching_targets")
    assert not list((REPOSITORY_ROOT / "config").glob("*force_matching_target*.json"))


def test_target_hashes_are_unique_by_partition_and_role_counts_are_balanced() -> None:
    targets = derive_spice_c1c4_force_matching_targets(_source_bytes())
    energy_sets = {
        partition: {
            row.target_sha256
            for row in targets.relative_energy_targets
            if row.partition == partition
        }
        for partition in _PARTITIONS
    }
    force_sets = {
        partition: {
            row.target_sha256
            for row in targets.force_targets
            if row.partition == partition
        }
        for partition in _PARTITIONS
    }
    assert all(
        not (energy_sets[left] & energy_sets[right])
        for index, left in enumerate(_PARTITIONS)
        for right in _PARTITIONS[index + 1 :]
    )
    assert all(
        not (force_sets[left] & force_sets[right])
        for index, left in enumerate(_PARTITIONS)
        for right in _PARTITIONS[index + 1 :]
    )
    assert Counter(row.role for row in targets.force_targets) == {
        "seed": 100,
        "related_nearby_lower": 100,
    }
