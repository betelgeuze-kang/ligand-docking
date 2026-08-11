from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib import metadata, util
import math
from types import SimpleNamespace

import numpy as np
import pytest

import betelgeuze_engine_v2.docking.search_v2 as search_v2_module
from betelgeuze_engine_v2.docking.search_v2 import (
    DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID,
    DOCKING_SEARCH_V2_CORE_SCHEMA_ID,
    DockingSearchV2Config,
    DockingSearchV2Error,
    DockingSearchV2Input,
    DockingShortRangeV2Config,
    _run_docking_search_v2_with_native_for_tests,
    _validate_composite_preflight,
    run_docking_search_v2,
)


_DIGEST = "a" * 64


def _input(
    *, numpy_arrays: bool = False, source_seed: str = "42" * 32
) -> DockingSearchV2Input:
    values: dict[str, object] = {
        "source_seed": source_seed,
        "ligand_coordinates_angstrom": [[0.0, 0.0, 0.0]],
        "ligand_vdw_radii_angstrom": [0.5],
        "ligand_epsilon_kcal_per_mol": [0.2],
        "ligand_charge_elementary": [0.1],
        "ligand_anchor_ids": [7],
        "ligand_anchor_atom_indices": [0],
        "ligand_anchor_directions": [[1.0, 0.0, 0.0]],
        "ligand_anchor_kinds": ["hydrogen_bond_donor"],
        "receptor_coordinates_angstrom": [[10.0, 0.0, 0.0]],
        "receptor_vdw_radii_angstrom": [0.5],
        "receptor_epsilon_kcal_per_mol": [0.2],
        "receptor_charge_elementary": [-0.1],
        "surface_ids": [11],
        "surface_positions_angstrom": [[4.0, 0.0, 0.0]],
        "surface_outward_normals": [[1.0, 0.0, 0.0]],
        "surface_anchor_kinds": ["hydrogen_bond_acceptor"],
    }
    if numpy_arrays:
        float_names = {
            "ligand_coordinates_angstrom",
            "ligand_vdw_radii_angstrom",
            "ligand_epsilon_kcal_per_mol",
            "ligand_charge_elementary",
            "ligand_anchor_directions",
            "receptor_coordinates_angstrom",
            "receptor_vdw_radii_angstrom",
            "receptor_epsilon_kcal_per_mol",
            "receptor_charge_elementary",
            "surface_positions_angstrom",
            "surface_outward_normals",
        }
        integer_names = {
            "ligand_anchor_ids",
            "ligand_anchor_atom_indices",
            "surface_ids",
        }
        for name in float_names:
            values[name] = np.asarray(values[name], dtype=np.float64)
        for name in integer_names:
            values[name] = np.asarray(values[name], dtype=np.int64)
        values["ligand_anchor_kinds"] = np.asarray(
            values["ligand_anchor_kinds"], dtype="U32"
        )
        values["surface_anchor_kinds"] = np.asarray(
            values["surface_anchor_kinds"], dtype="U32"
        )
    return DockingSearchV2Input(**values)


def _config() -> DockingSearchV2Config:
    return DockingSearchV2Config(
        orientation_count=4,
        generated_candidate_limit=4,
        coarse_keep=3,
        refinement_keep=2,
        top_k=1,
        refinement_steps=0,
    )


def _key(orientation_index: int) -> dict[str, int | None]:
    return {
        "orientation_index": orientation_index,
        "primary_surface_id": 11,
        "primary_ligand_anchor_id": 7,
        "secondary_surface_id": None,
        "secondary_ligand_anchor_id": None,
    }


def _candidate(
    slot_index: int,
    *,
    status: str,
    reason: str | None,
    physically_valid: bool | None,
    gap: float | None,
    cluster_id: int | None = None,
    final_rank: int | None = None,
    energy: float | None = None,
) -> dict[str, object]:
    return {
        "slot_index": slot_index,
        "key": _key(slot_index),
        "placement_mode": "single_anchor_fallback",
        "status": status,
        "reason": reason,
        "detail": None,
        "coordinates_angstrom": [[float(slot_index), 0.0, 0.0]],
        "anchor_fit_rmsd_angstrom": 0.0,
        "coarse_score": float(slot_index),
        "detailed_score": None if status == "coarse_pruned" else float(slot_index),
        "energy_kcal_per_mol": energy,
        "physically_valid": physically_valid,
        "minimum_receptor_gap_angstrom": gap,
        "cluster_id": cluster_id,
        "final_rank": final_rank,
    }


def _native_orientation_material() -> list[dict[str, object]]:
    return [
        {
            "orientation_index": 0,
            "raw_sequence_index": 0,
            "quaternion": [
                -0.8595933567490339,
                0.047704628928053605,
                -0.5079653821674907,
                0.02819042268572571,
            ],
        },
        {
            "orientation_index": 1,
            "raw_sequence_index": 1,
            "quaternion": [
                0.26873799326261855,
                0.4110430166848916,
                -0.22286586526816066,
                0.8421130182523239,
            ],
        },
        {
            "orientation_index": 2,
            "raw_sequence_index": 2,
            "quaternion": [
                0.3162498092820938,
                -0.625429875139711,
                0.5994331181391611,
                0.38665678099540324,
            ],
        },
        {
            "orientation_index": 3,
            "raw_sequence_index": 3,
            "quaternion": [
                0.7260252795184639,
                -0.6812222574816325,
                -0.07281773405798704,
                0.05933891655924421,
            ],
        },
    ]


def _native_result() -> dict[str, object]:
    candidates = [
        _candidate(
            0,
            status="top_k",
            reason=None,
            physically_valid=True,
            gap=2.0,
            cluster_id=1,
            final_rank=1,
            energy=-1.25,
        ),
        _candidate(
            1,
            status="physical_rejected",
            reason="receptor_clash",
            physically_valid=False,
            gap=-0.25,
            energy=4.0,
        ),
        _candidate(
            2,
            status="detailed_pruned",
            reason="detailed_budget",
            physically_valid=None,
            gap=1.5,
        ),
        _candidate(
            3,
            status="coarse_pruned",
            reason="coarse_budget",
            physically_valid=None,
            gap=None,
        ),
    ]
    receipt: dict[str, object] = {
        "schema_id": DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID,
        "evaluator_id": "betelgeuze_short_range_analytic/1.0.0",
        "evaluator_config_sha256": _DIGEST,
        "config_sha256": "b" * 64,
        "input_sha256": "c" * 64,
        "result_independent_allocation": True,
        "placement_mode": "single_anchor_fallback",
        "requested_orientation_count": 4,
        "accepted_orientation_count": 4,
        "raw_orientation_attempt_count": 4,
        "compatible_single_anchor_pair_count": 1,
        "compatible_dual_anchor_combination_count": 0,
        "used_anchor_combination_count": 1,
        "possible_candidate_slot_count": 4,
        "generated_candidate_limit": 4,
        "allocated_candidate_slot_count": 4,
        "allocation_sha256": "d" * 64,
        "orientation_sha256": "e" * 64,
        "candidate_rows_sha256": "f" * 64,
        "poses_sha256": "1" * 64,
        "coarse_keep_budget": 3,
        "coarse_kept_count": 3,
        "refinement_keep_budget": 2,
        "refinement_selected_count": 2,
        "refinement_steps_per_candidate": 0,
        "refinement_succeeded_count": 2,
        "refinement_evaluator_failed_count": 0,
        "refinement_non_finite_failed_count": 0,
        "evaluator_call_count": 2,
        "maximum_evaluator_call_count": 2,
        "physical_valid_count": 1,
        "rejected_non_finite_coordinate_count": 0,
        "rejected_coordinate_out_of_bounds_count": 0,
        "rejected_ligand_self_overlap_count": 0,
        "rejected_receptor_clash_count": 1,
        "cluster_count": 1,
        "top_k_budget": 1,
        "returned_pose_count": 1,
        "receipt_sha256": "2" * 64,
    }
    return {
        "schema_id": DOCKING_SEARCH_V2_CORE_SCHEMA_ID,
        "orientation_material": _native_orientation_material(),
        "candidate_rows": candidates,
        "poses": [
            {
                "rank": 1,
                "key": _key(0),
                "coordinates_angstrom": [[0.0, 0.0, 0.0]],
                "energy_kcal_per_mol": -1.25,
                "cluster_size": 1,
                "minimum_receptor_gap_angstrom": 2.0,
            }
        ],
        "receipt": receipt,
    }


class _FakeNative:
    def __init__(self, mutate=None, *, build_overrides=None) -> None:
        self._mutate = mutate
        self._build_overrides = dict(build_overrides or {})
        self.calls = 0

    def docking_search_build_info(self) -> dict[str, str]:
        result = {
            "backend_id": "rust_cpu_required",
            "backend_version": "0.2.0-rc.6",
            "crate_name": "betelgeuze-engine-v2-native",
            "cargo_lock_sha256": "3" * 64,
            "native_source_closure_sha256": "4" * 64,
            "native_source_closure_file_count": "24",
            "rustc_version": "rustc 1.93.0 (254b59607 2026-01-19)",
            "target_triple": "x86_64-unknown-linux-gnu",
            "build_profile": "release",
            "opt_level": "3",
            "debug": "false",
            "panic_strategy": "abort",
            "build_flags": (
                "profile=release,codegen-units=1,debug=false,lto=fat,"
                "opt-level=3,panic=abort,strip=symbols"
            ),
            "cargo_features": "extension-module",
            "implicit_fallback_allowed": "false",
            "docking_search_schema_id": DOCKING_SEARCH_V2_CORE_SCHEMA_ID,
            "docking_search_receipt_schema_id": (
                DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID
            ),
            "docking_search_evaluator_id": ("betelgeuze_short_range_analytic/1.0.0"),
        }
        result.update(self._build_overrides)
        return result

    def docking_search_v2(self, **arguments):
        self.calls += 1
        assert arguments["ligand_anchor_kinds"] == (0,)
        assert arguments["surface_anchor_kinds"] == (1,)
        result = deepcopy(_native_result())
        _seal_native_result(result)
        if self._mutate is not None:
            self._mutate(result)
        return result


def _seal_native_result(value: dict[str, object]) -> None:
    search_input = _input()
    config = _config()
    short_range_config = DockingShortRangeV2Config()
    candidate_rows = tuple(
        search_v2_module.DockingSearchV2CandidateRow._from_native(
            row,
            ligand_count=len(search_input.ligand_coordinates_angstrom),
        )
        for row in value["candidate_rows"]
    )
    poses = tuple(
        search_v2_module.DockingSearchV2Pose._from_native(
            row,
            ligand_count=len(search_input.ligand_coordinates_angstrom),
        )
        for row in value["poses"]
    )
    receipt = value["receipt"]
    orientation_material = search_v2_module._orientation_material(
        value["orientation_material"],
        expected_count=config.orientation_count,
        source_seed=str(search_input.source_seed),
    )
    receipt.update(
        evaluator_config_sha256=search_v2_module._short_range_config_sha256(
            short_range_config
        ),
        config_sha256=search_v2_module._search_config_sha256(config),
        input_sha256=search_v2_module._search_input_sha256(search_input),
        orientation_sha256=search_v2_module._orientation_sha256(orientation_material),
        allocation_sha256=search_v2_module._allocation_sha256(candidate_rows),
        candidate_rows_sha256=search_v2_module._candidate_rows_sha256(candidate_rows),
        poses_sha256=search_v2_module._poses_sha256(poses),
    )
    receipt["receipt_sha256"] = search_v2_module._search_receipt_sha256(receipt)


def _run(fake: _FakeNative | None = None):
    return _run_docking_search_v2_with_native_for_tests(
        _input(),
        _config(),
        DockingShortRangeV2Config(),
        _FakeNative() if fake is None else fake,
    )


def _negate_orientation_quaternion(value: dict[str, object]) -> None:
    quaternion = value["orientation_material"][0]["quaternion"]
    value["orientation_material"][0]["quaternion"] = [
        -component for component in quaternion
    ]


def _duplicate_orientation_quaternion(value: dict[str, object]) -> None:
    value["orientation_material"][1]["quaternion"] = list(
        value["orientation_material"][0]["quaternion"]
    )


def _swap_orientation_quaternions(value: dict[str, object]) -> None:
    first = value["orientation_material"][0]["quaternion"]
    second = value["orientation_material"][1]["quaternion"]
    value["orientation_material"][0]["quaternion"] = second
    value["orientation_material"][1]["quaternion"] = first


def test_plain_and_numpy_inputs_are_canonical_and_mutation_sensitive() -> None:
    plain = _input()
    numpy_input = _input(numpy_arrays=True)
    assert plain.fingerprint_sha256 == numpy_input.fingerprint_sha256
    changed_values = plain._projection()
    changed_values["source_seed_hex"] = "43" * 32
    assert (
        plain.fingerprint_sha256
        != __import__("hashlib")
        .sha256(
            __import__("json")
            .dumps(
                changed_values,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            .encode("ascii")
        )
        .hexdigest()
    )
    with pytest.raises(TypeError):
        plain.ligand_coordinates_angstrom[0][0] = 9.0


def test_rust_compatible_identity_normalizes_directions_and_signed_zero() -> None:
    base_values = _input()._projection()
    base_values.pop("source_seed_hex")
    base_values["source_seed"] = "42" * 32
    base_values["ligand_anchor_directions"] = ((0.25, -0.5, 1.0),)
    base_values["ligand_charge_elementary"] = (0.0,)
    base_values["surface_outward_normals"] = ((0.5, 1.0, -0.25),)
    base = DockingSearchV2Input(**base_values)

    equivalent_values = base._projection()
    equivalent_values.pop("source_seed_hex")
    equivalent_values["source_seed"] = "42" * 32
    equivalent_values["ligand_coordinates_angstrom"] = ((-0.0, 0.0, -0.0),)
    equivalent_values["ligand_charge_elementary"] = (-0.0,)
    equivalent_values["ligand_anchor_directions"] = (
        tuple(component * 8.0 for component in (0.25, -0.5, 1.0)),
    )
    equivalent_values["surface_positions_angstrom"] = ((4.0, -0.0, 0.0),)
    equivalent_values["surface_outward_normals"] = (
        tuple(component * 0.25 for component in (0.5, 1.0, -0.25)),
    )
    equivalent = DockingSearchV2Input(**equivalent_values)
    assert search_v2_module._search_input_sha256(
        base
    ) == search_v2_module._search_input_sha256(equivalent)

    config = DockingSearchV2Config(
        placement_clearance_angstrom=0.0,
        coarse_clash_weight=0.0,
        translation_step_angstrom2_per_kcal=0.0,
        rotation_step_per_torque=0.0,
    )
    equivalent_config = DockingSearchV2Config(
        placement_clearance_angstrom=-0.0,
        coarse_clash_weight=-0.0,
        translation_step_angstrom2_per_kcal=-0.0,
        rotation_step_per_torque=-0.0,
    )
    assert search_v2_module._search_config_sha256(
        config
    ) == search_v2_module._search_config_sha256(equivalent_config)


def test_public_5sd5_direction_rows_have_frozen_cross_language_identity() -> None:
    # Rows copied from the real 5SD5_HWI request that exposed the Rust/libc
    # versus CPython math.hypot ULP difference in canonical direction hashes.
    search_input = DockingSearchV2Input(
        source_seed=(
            "f8a739361654dd792b28eea723802ccbfb973efebd4c171e529a47c2dd3087d8"
        ),
        ligand_coordinates_angstrom=[[-3.2869, -3.5712, 2.4783]],
        ligand_vdw_radii_angstrom=[1.55],
        ligand_epsilon_kcal_per_mol=[0.17],
        ligand_charge_elementary=[-0.3677192090241967],
        ligand_anchor_ids=[22],
        ligand_anchor_atom_indices=[0],
        ligand_anchor_directions=[
            [-0.6409734436307287, -0.5960894010357192, 0.4835602036282995]
        ],
        ligand_anchor_kinds=["hydrogen_bond_donor"],
        receptor_coordinates_angstrom=[[15.522, 10.752, 8.664]],
        receptor_vdw_radii_angstrom=[1.7],
        receptor_epsilon_kcal_per_mol=[0.12],
        receptor_charge_elementary=[0.0],
        surface_ids=[8],
        surface_positions_angstrom=[
            [3.856288487549871, 6.613194919700477, 12.322604421462243]
        ],
        surface_outward_normals=[
            [0.411799024225723, -0.8437452130964667, 0.3442609170724153]
        ],
        surface_anchor_kinds=["hydrogen_bond_acceptor"],
    )
    assert search_v2_module._search_input_sha256(search_input) == (
        "8c6d123661e7b1bd404f6ebb92d20f5a07ff58afbbac421e010545b9cde5ea4d"
    )


def test_orientation_prefix_has_frozen_cross_language_identity() -> None:
    material = search_v2_module._orientation_material(
        _native_orientation_material(), expected_count=4, source_seed="42" * 32
    )
    assert search_v2_module._orientation_sha256(material) == (
        "b89a2491012b94007ad278434ee72d51dff986d98a706efdf16fc9684180b298"
    )


def test_orientation_semantics_allow_cross_libm_last_bit_drift() -> None:
    rows = deepcopy(_native_orientation_material())
    component = rows[0]["quaternion"][0]
    rows[0]["quaternion"][0] = math.nextafter(component, math.inf)
    material = search_v2_module._orientation_material(
        rows, expected_count=4, source_seed="42" * 32
    )
    assert search_v2_module._orientation_sha256(material) != (
        "b89a2491012b94007ad278434ee72d51dff986d98a706efdf16fc9684180b298"
    )


@pytest.mark.parametrize(
    "mutation,match",
    [
        (
            lambda value: value["orientation_material"][0].__setitem__("extra", 1),
            "key schema",
        ),
        (lambda value: value["orientation_material"].pop(), "count disagrees"),
        (
            lambda value: value["orientation_material"][0].__setitem__(
                "orientation_index", 1
            ),
            "canonical index order",
        ),
        (
            lambda value: value["orientation_material"][1].__setitem__(
                "raw_sequence_index", 0
            ),
            "strictly increasing",
        ),
        (
            lambda value: value["orientation_material"][3].__setitem__(
                "raw_sequence_index", 4_096
            ),
            "raw_sequence_index",
        ),
        (
            lambda value: value["orientation_material"][0]["quaternion"].__setitem__(
                0, float("inf")
            ),
            "must be finite",
        ),
        (
            lambda value: value["orientation_material"][0]["quaternion"].__setitem__(
                0, -0.0
            ),
            "signed zero",
        ),
        (
            lambda value: value["orientation_material"][0]["quaternion"].__setitem__(
                0, -0.4
            ),
            "unit length",
        ),
        (_negate_orientation_quaternion, "sign is not canonical"),
        (_duplicate_orientation_quaternion, "duplicate quaternion"),
    ],
)
def test_native_orientation_material_mutations_fail_closed(
    mutation, match: str
) -> None:
    with pytest.raises(DockingSearchV2Error, match=match):
        _run(_FakeNative(mutation))


def test_valid_native_ledger_preserves_all_rows_and_is_never_claim_safe() -> None:
    result = _run()
    assert len(result.candidate_rows) == 4
    assert result.candidate_rows[1].minimum_receptor_gap_angstrom == -0.25
    assert result.candidate_rows[2].minimum_receptor_gap_angstrom == 1.5
    assert result.poses[0].minimum_receptor_gap_angstrom == 2.0
    payload = result.to_dict()
    assert payload["claim_safe"] is False
    assert payload["claim_blockers"] == ["public_development_cohort_gate_not_passed"]
    assert payload["search_receipt"][
        "input_sha256"
    ] == search_v2_module._search_input_sha256(_input())
    assert payload["search_receipt"]["poses_sha256"] == search_v2_module._poses_sha256(
        result.poses
    )


def test_installed_rc6_native_executes_full_search_when_available() -> None:
    if util.find_spec("betelgeuze_engine_v2_native") is None:
        pytest.skip("rc6 native extension is not installed in this test environment")
    try:
        version = metadata.version("betelgeuze-engine-v2-native")
    except metadata.PackageNotFoundError:
        pytest.skip("rc6 native distribution metadata is not installed")
    if version != "0.2.0rc6":
        pytest.skip("a non-rc6 developer extension is installed")
    result = run_docking_search_v2(_input(numpy_arrays=True), _config())
    assert len(result.candidate_rows) == 4
    assert result.search_receipt["evaluator_id"] == (
        "betelgeuze_short_range_analytic/1.0.0"
    )
    assert result.native_backend_receipt["test_double"] is False
    release_5sis = run_docking_search_v2(
        _input(
            source_seed=(
                "5b5c5f696e68d7d3794897d7829958e3adab3e5faab386418a01496009543edd"
            )
        ),
        DockingSearchV2Config(
            orientation_count=64,
            generated_candidate_limit=64,
            coarse_keep=64,
            refinement_keep=64,
            top_k=1,
            refinement_steps=0,
        ),
    )
    assert release_5sis.search_receipt["orientation_sha256"] == (
        "006ee393989d4c99fed886492e640cd1c58c1e37f525c2cb61f52bbd64108e02"
    )


def test_huge_numpy_shape_is_rejected_before_tolist() -> None:
    class _NoToList(np.ndarray):
        def tolist(self):
            pytest.fail("tolist called before shape cap")

    huge = np.lib.stride_tricks.as_strided(
        np.zeros((1,), dtype=np.float64),
        shape=(513, 3),
        strides=(0, 0),
    ).view(_NoToList)
    values = _input()._projection()
    values.pop("source_seed_hex")
    values["source_seed"] = "42" * 32
    values["ligand_coordinates_angstrom"] = huge
    with pytest.raises(DockingSearchV2Error, match="row count"):
        DockingSearchV2Input(**values)


def test_composite_work_is_rejected_before_native_call() -> None:
    base = _input()._projection()
    base.pop("source_seed_hex")
    base["source_seed"] = "42" * 32
    ligand_count = 50
    receptor_count = 1_000
    base.update(
        ligand_coordinates_angstrom=[
            [float(index), 0.0, 0.0] for index in range(ligand_count)
        ],
        ligand_vdw_radii_angstrom=[0.5] * ligand_count,
        ligand_epsilon_kcal_per_mol=[0.2] * ligand_count,
        ligand_charge_elementary=[0.0] * ligand_count,
        receptor_coordinates_angstrom=[
            [100.0 + index, 0.0, 0.0] for index in range(receptor_count)
        ],
        receptor_vdw_radii_angstrom=[0.5] * receptor_count,
        receptor_epsilon_kcal_per_mol=[0.2] * receptor_count,
        receptor_charge_elementary=[0.0] * receptor_count,
    )
    search_input = DockingSearchV2Input(**base)
    fake = _FakeNative()
    with pytest.raises(DockingSearchV2Error, match="pair-evaluation"):
        _run_docking_search_v2_with_native_for_tests(
            search_input,
            DockingSearchV2Config(
                orientation_count=64,
                generated_candidate_limit=64,
                coarse_keep=64,
                refinement_keep=64,
                top_k=1,
                refinement_steps=128,
            ),
            DockingShortRangeV2Config(),
            fake,
        )
    assert fake.calls == 0


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda value: value.__setitem__("extra", 1), "result.*key schema"),
        (
            lambda value: value["candidate_rows"][0].__setitem__("extra", 1),
            "key schema",
        ),
        (
            lambda value: value["candidate_rows"][0].__setitem__("final_rank", 0),
            "final_rank",
        ),
        (
            lambda value: value["candidate_rows"][0]["key"].__setitem__(
                "primary_surface_id", 99
            ),
            "invented surface",
        ),
        (
            lambda value: value["candidate_rows"][0]["key"].__setitem__(
                "orientation_index", 4
            ),
            "orientation",
        ),
        (
            lambda value: value["candidate_rows"][0].__setitem__(
                "reason", "top_k_budget"
            ),
            "terminal status",
        ),
        (
            lambda value: value["poses"][0].__setitem__("energy_kcal_per_mol", -2.0),
            "ledger-bound",
        ),
        (
            lambda value: value["poses"][0].__setitem__(
                "minimum_receptor_gap_angstrom", 3.0
            ),
            "ledger-bound",
        ),
        (
            lambda value: value["poses"][0].__setitem__("cluster_size", 2),
            "cluster size",
        ),
        (
            lambda value: value["candidate_rows"][3]["coordinates_angstrom"][
                0
            ].__setitem__(0, 999.0),
            "candidate_rows_sha256",
        ),
        (_swap_orientation_quaternions, "Halton/Shoemake"),
        (
            lambda value: value["receipt"].__setitem__(
                "allocated_candidate_slot_count", 3
            ),
            "allocated candidate",
        ),
        (
            lambda value: value["orientation_material"][3].__setitem__(
                "raw_sequence_index", 4
            ),
            "canonical accepted prefix",
        ),
        (
            lambda value: value["receipt"].__setitem__(
                "used_anchor_combination_count", 2
            ),
            "anchor-combination",
        ),
        (
            lambda value: value["receipt"].__setitem__(
                "possible_candidate_slot_count", 3
            ),
            "allocated candidate",
        ),
        (
            lambda value: value["receipt"].__setitem__("poses_sha256", "A" * 64),
            "lowercase SHA-256",
        ),
        (
            lambda value: value["receipt"].__setitem__("poses_sha256", "9" * 64),
            "poses_sha256",
        ),
        (
            lambda value: value["receipt"].__setitem__("receipt_sha256", "8" * 64),
            "does not seal",
        ),
    ],
)
def test_native_result_mutations_fail_closed(mutation, match: str) -> None:
    with pytest.raises(DockingSearchV2Error, match=match):
        _run(_FakeNative(mutation))


def test_resealed_forged_orientation_digest_fails_closed() -> None:
    def forge_orientation_and_reseal(value: dict[str, object]) -> None:
        receipt = value["receipt"]
        receipt["orientation_sha256"] = "9" * 64
        receipt["receipt_sha256"] = search_v2_module._search_receipt_sha256(receipt)

    with pytest.raises(DockingSearchV2Error, match="orientation_sha256"):
        _run(_FakeNative(forge_orientation_and_reseal))


def test_resealed_forged_orientation_material_fails_seed_binding() -> None:
    def forge_material_and_reseal(value: dict[str, object]) -> None:
        _swap_orientation_quaternions(value)
        material = tuple(
            (
                row["orientation_index"],
                row["raw_sequence_index"],
                tuple(row["quaternion"]),
            )
            for row in value["orientation_material"]
        )
        receipt = value["receipt"]
        receipt["orientation_sha256"] = search_v2_module._orientation_sha256(material)
        receipt["receipt_sha256"] = search_v2_module._search_receipt_sha256(receipt)

    with pytest.raises(DockingSearchV2Error, match="Halton/Shoemake"):
        _run(_FakeNative(forge_material_and_reseal))


def test_wrong_native_build_identity_fails_closed() -> None:
    with pytest.raises(DockingSearchV2Error, match="identity is invalid"):
        _run(
            _FakeNative(
                build_overrides={"docking_search_evaluator_id": "external_solver"}
            )
        )
    for overrides in (
        {"cargo_features": "none"},
        {"rustc_version": "rustc 0.0.0"},
        {"target_triple": "unknown-target"},
        {"build_profile": "debug"},
        {"opt_level": "0"},
        {"debug": "true"},
        {"panic_strategy": "unwind"},
        {"build_flags": "profile=release"},
    ):
        with pytest.raises(DockingSearchV2Error, match="identity is invalid"):
            _run(_FakeNative(build_overrides=overrides))


def test_native_backend_receipt_is_install_path_independent(tmp_path) -> None:
    first_path = tmp_path / "first" / "betelgeuze_engine_v2_native.so"
    second_path = tmp_path / "second" / "renamed-native-extension.so"
    first_path.parent.mkdir()
    second_path.parent.mkdir()
    extension_bytes = b"same native extension bytes"
    first_path.write_bytes(extension_bytes)
    second_path.write_bytes(extension_bytes)

    first = search_v2_module._native_build_receipt(
        _FakeNative(),
        extension_path=first_path,
        distribution_version="0.2.0rc6",
        test_double=False,
    )
    second = search_v2_module._native_build_receipt(
        _FakeNative(),
        extension_path=second_path,
        distribution_version="0.2.0rc6",
        test_double=False,
    )
    assert search_v2_module._canonical_bytes(dict(first)) == (
        search_v2_module._canonical_bytes(dict(second))
    )
    assert first["extension_sha256"] == hashlib.sha256(extension_bytes).hexdigest()
    assert "extension_path" not in first

    test_double = search_v2_module._native_build_receipt(
        _FakeNative(),
        extension_path=None,
        distribution_version="0.2.0rc6",
        test_double=True,
    )
    assert set(test_double) == set(first)
    assert "extension_path" not in test_double


def test_native_receipt_and_orientation_are_bound_to_every_request_configuration() -> (
    None
):
    changed_input_values = _input()._projection()
    changed_input_values.pop("source_seed_hex")
    changed_input_values["source_seed"] = "43" * 32
    with pytest.raises(DockingSearchV2Error, match="Halton/Shoemake"):
        _run_docking_search_v2_with_native_for_tests(
            DockingSearchV2Input(**changed_input_values),
            _config(),
            DockingShortRangeV2Config(),
            _FakeNative(),
        )
    with pytest.raises(DockingSearchV2Error, match="config_sha256"):
        _run_docking_search_v2_with_native_for_tests(
            _input(),
            DockingSearchV2Config(
                orientation_count=4,
                generated_candidate_limit=4,
                coarse_keep=3,
                refinement_keep=2,
                top_k=1,
                refinement_steps=0,
                placement_clearance_angstrom=2.0,
            ),
            DockingShortRangeV2Config(),
            _FakeNative(),
        )
    with pytest.raises(DockingSearchV2Error, match="evaluator_config_sha256"):
        _run_docking_search_v2_with_native_for_tests(
            _input(),
            _config(),
            DockingShortRangeV2Config(dielectric=8.0),
            _FakeNative(),
        )


def test_public_path_rejects_missing_or_non_extension_native(monkeypatch) -> None:
    import betelgeuze_engine_v2.docking.search_v2 as module

    def missing(_name: str):
        raise ImportError("missing")

    monkeypatch.setattr(module, "import_module", missing)
    with pytest.raises(DockingSearchV2Error, match="extension is unavailable"):
        run_docking_search_v2(_input(), _config())

    monkeypatch.setattr(
        module,
        "import_module",
        lambda _name: SimpleNamespace(__file__=__file__),
    )
    with pytest.raises(DockingSearchV2Error, match="not a native extension"):
        run_docking_search_v2(_input(), _config())


def test_config_and_utf8_detail_bounds_are_fail_closed() -> None:
    with pytest.raises(DockingSearchV2Error, match="dual_anchor"):
        DockingSearchV2Config(dual_anchor_distance_tolerance_angstrom=0.0)

    def oversized_detail(value) -> None:
        row = value["candidate_rows"][1]
        row["status"] = "refinement_failed"
        row["reason"] = "evaluator_failure"
        row["physically_valid"] = None
        row["detail"] = "가" * 1_366
        value["receipt"]["refinement_evaluator_failed_count"] = 1
        value["receipt"]["rejected_receptor_clash_count"] = 0
        value["receipt"]["refinement_succeeded_count"] = 1

    with pytest.raises(DockingSearchV2Error, match="detail exceeds"):
        _run(_FakeNative(oversized_detail))


def _sized_input(*, ligand_count: int, surface_count: int) -> DockingSearchV2Input:
    values = _input()._projection()
    values.pop("source_seed_hex")
    values["source_seed"] = "42" * 32
    values.update(
        ligand_coordinates_angstrom=[
            [float(index) * 0.1, 0.0, 0.0] for index in range(ligand_count)
        ],
        ligand_vdw_radii_angstrom=[0.5] * ligand_count,
        ligand_epsilon_kcal_per_mol=[0.2] * ligand_count,
        ligand_charge_elementary=[0.0] * ligand_count,
        ligand_anchor_ids=[7],
        ligand_anchor_atom_indices=[0],
        ligand_anchor_directions=[[1.0, 0.0, 0.0]],
        ligand_anchor_kinds=["hydrogen_bond_donor"],
        receptor_coordinates_angstrom=[],
        receptor_vdw_radii_angstrom=[],
        receptor_epsilon_kcal_per_mol=[],
        receptor_charge_elementary=[],
        surface_ids=list(range(surface_count)),
        surface_positions_angstrom=[
            [10_000.0 + float(index) * 10.0, 0.0, 0.0] for index in range(surface_count)
        ],
        surface_outward_normals=[[1.0, 0.0, 0.0]] * surface_count,
        surface_anchor_kinds=["hydrogen_bond_acceptor"] * surface_count,
    )
    return DockingSearchV2Input(**values)


def test_valid_numpy_rows_are_parsed_without_tolist_object_expansion() -> None:
    class _NoToList(np.ndarray):
        def tolist(self):
            pytest.fail("bounded float64 rows must not be expanded with tolist")

    coordinates = np.asarray([[0.0, 0.0, 0.0]], dtype=np.float64).view(_NoToList)
    values = _input()._projection()
    values.pop("source_seed_hex")
    values["source_seed"] = "42" * 32
    values["ligand_coordinates_angstrom"] = coordinates
    parsed = DockingSearchV2Input(**values)
    assert parsed.ligand_coordinates_angstrom == ((0.0, 0.0, 0.0),)


def test_nested_numpy_row_shape_is_checked_before_element_conversion() -> None:
    class _NoToList(np.ndarray):
        def tolist(self):
            pytest.fail("malformed row must not be expanded with tolist")

    wide_row = np.zeros((4,), dtype=np.float64).view(_NoToList)
    values = _input()._projection()
    values.pop("source_seed_hex")
    values["source_seed"] = "42" * 32
    values["ligand_coordinates_angstrom"] = [wide_row]
    with pytest.raises(DockingSearchV2Error, match=r"shape \[N,3\]"):
        DockingSearchV2Input(**values)


def test_packed_native_coordinate_arrays_are_accepted_without_schema_drift() -> None:
    def pack_coordinates(value: dict[str, object]) -> None:
        for row in value["candidate_rows"]:
            row["coordinates_angstrom"] = np.asarray(
                row["coordinates_angstrom"], dtype=np.float64
            )
        for pose in value["poses"]:
            pose["coordinates_angstrom"] = np.asarray(
                pose["coordinates_angstrom"], dtype=np.float64
            )

    result = _run(_FakeNative(pack_coordinates))
    assert result.candidate_rows[3].coordinates_angstrom == ((3.0, 0.0, 0.0),)
    assert result.poses[0].coordinates_angstrom == ((0.0, 0.0, 0.0),)


def test_python_bridge_expansion_cap_rejects_before_native_call() -> None:
    search_input = _sized_input(ligand_count=512, surface_count=1)
    fake = _FakeNative()
    with pytest.raises(DockingSearchV2Error, match="Python bridge output"):
        _run_docking_search_v2_with_native_for_tests(
            search_input,
            DockingSearchV2Config(
                orientation_count=512,
                generated_candidate_limit=512,
                coarse_keep=512,
                refinement_keep=512,
                top_k=512,
                refinement_steps=0,
            ),
            DockingShortRangeV2Config(),
            fake,
        )
    assert fake.calls == 0


def test_preflight_uses_exact_dual_geometry_instead_of_n_choose_two_bound() -> None:
    search_input = _sized_input(ligand_count=512, surface_count=129)
    config = DockingSearchV2Config(
        orientation_count=1,
        generated_candidate_limit=8_192,
        coarse_keep=1,
        refinement_keep=1,
        top_k=1,
        refinement_steps=0,
    )
    # All compatible pairs share one ligand anchor, so no dual is valid and
    # the core uses 129 single-anchor fallback combinations.  The former nC2
    # upper bound invented 8,192 candidates and rejected >4M coordinates.
    _validate_composite_preflight(search_input, config)
