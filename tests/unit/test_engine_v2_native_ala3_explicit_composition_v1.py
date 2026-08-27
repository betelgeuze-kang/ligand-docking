from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    ROOT / "config/engine_v2_native_ala3_explicit_composition_profile_v1.json"
)
ASSET_PATH = (
    ROOT
    / "rust/betelgeuze-runtime/assets/engine_v2_native_ala3_explicit_composition_profile_v1.json"
)
RUNTIME_PATH = ROOT / "rust/betelgeuze-runtime/src/development_explicit_composition.rs"
WATER_RUNTIME_PATH = ROOT / "rust/betelgeuze-runtime/src/development_water_box.rs"
CONSTRAINTS_RUNTIME_PATH = (
    ROOT / "rust/betelgeuze-runtime/src/development_peptide_constraints.rs"
)

PROFILE_SHA256 = "a9fad385e3eaf84c673507ee513778ad05842da139c282ce9def1c712eb13079"


def test_profile_asset_identity_and_parent_chain_are_frozen() -> None:
    canonical = PROFILE_PATH.read_bytes()
    assert ASSET_PATH.read_bytes() == canonical
    assert hashlib.sha256(canonical).hexdigest() == PROFILE_SHA256
    profile = json.loads(canonical)

    assert profile["schema_id"] == (
        "betelgeuze.engine_v2_native_ala3_explicit_composition_profile/1.0.0"
    )
    assert profile["profile_id"] == (
        "engine_v2_native_ala3_tip3p_nacl_composition_development_v1"
    )
    assert profile["parents"] == {
        "ala3_profile_sha256": (
            "a7a4229cc30bb24393b06d4b19e25b917060213ca432b1263329bda6c0b49adf"
        ),
        "ala3_constraints_profile_sha256": (
            "815c9ab462aec7daa57b6cf6e42d8bba569d5891ec1e002deff6ad9e974cb692"
        ),
        "water_box_profile_sha256": (
            "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
        ),
        "water_ion_profile_sha256": (
            "409902e5f6776bd58c76f80a572c9cf978f7e2f4938003e5609036bfe91c631f"
        ),
        "periodic_neighbor_cache_profile_sha256": (
            "c9e671b925b8f5da48a43dec2abe264e695840b277cc3cf4a84aa7255b59150d"
        ),
    }


def test_composition_periodic_constraints_and_nve_contract_are_exact() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    assert profile["composition"] == {
        "atom_count": 41,
        "ala3_atom_count": 33,
        "tip3p_water_count": 2,
        "sodium_count": 1,
        "chloride_count": 1,
        "net_charge_elementary": 0.0,
        "canonical_component_order": [
            "ala3",
            "tip3p_water_0",
            "tip3p_water_1",
            "sodium",
            "chloride",
        ],
        "general_solvation_or_parameter_assignment_implemented": False,
    }
    assert profile["placement"] == {
        "ala3_translation_angstrom": [8.0, 15.0, 15.0],
        "tip3p_water_fixture_translation_angstrom": [25.0, 5.0, 10.0],
        "sodium_position_angstrom": [32.0, 10.0, 25.0],
        "chloride_position_angstrom": [34.5, 10.0, 25.0],
        "all_positions_inside_primary_cell": True,
    }
    assert profile["periodic_short_range"] == {
        "orthorhombic_lengths_angstrom": [40.0, 40.0, 40.0],
        "periodic_axes": [True, True, True],
        "cutoff_angstrom": 12.0,
        "switch_start_angstrom": 10.0,
        "pme_or_ewald_implemented": False,
    }
    assert profile["constraints"] == {
        "ala3_xh_row_count": 17,
        "rigid_water_row_count": 6,
        "total_row_count": 23,
        "position_tolerance_angstrom": 1e-10,
        "radial_velocity_tolerance_angstrom_per_femtosecond": 1e-10,
        "maximum_iterations": 100,
    }
    assert profile["nve"] == {
        "integrator": "velocity_verlet",
        "initial_velocities": "all_exact_zero",
        "timestep_femtoseconds": 0.02,
        "step_count": 128,
        "checkpoint_step": 53,
        "energy_drift_baseline": (
            "total_energy_after_first_constraint_projection_step"
        ),
        "maximum_absolute_post_projection_total_energy_drift_kcal_per_mol": 0.0005,
        "exact_same_backend_checkpoint_continuation_required": True,
        "cpu_backend_report_and_state_bitwise_parity_required": True,
    }
    assert profile["observation"] == {
        "static_energy_and_force_cpu_parity_required": True,
        "complete_final_state_digest_required": True,
        "backend_independent_receipt_rederivation_required": True,
        "backend_tagged_receipt_rederivation_required": True,
        "nonfinite_observation_allowed": False,
    }


def test_authority_is_development_only_and_runtime_contract_is_bound() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    authority = profile["authority"]
    assert authority["development_fixture_only"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key != "development_fixture_only"
    )

    runtime_source = RUNTIME_PATH.read_text()
    for required in (
        "DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_SCHEMA_ID",
        "DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_PROFILE_ID",
        "DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_ATOM_COUNT: usize = 41",
        "DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_CONSTRAINT_COUNT: usize = 23",
        "development_ala3_explicit_composition_v1_profile_sha256",
        "evaluate_development_ala3_explicit_composition_v1",
        "observe_development_ala3_explicit_composition_v1",
        "DevelopmentAla3ExplicitCompositionV1",
        "composition_system",
        "composition_forcefield",
        "composition_constraints",
        "const CELL_ANGSTROM: f64 = 40.0",
        "const CUTOFF_ANGSTROM: f64 = 12.0",
        "const SWITCH_START_ANGSTROM: f64 = 10.0",
        "const TIMESTEP_FEMTOSECONDS: f64 = 0.02",
        "const NVE_STEPS: u64 = 128",
        "const CHECKPOINT_STEP: u64 = 53",
        "const MAXIMUM_NVE_DRIFT: f64 = 5.0e-4",
        "explicit composition checkpoint load did not preserve the state bitwise",
        "rederive_observation_receipt",
        "rederive_backend_receipt",
    ):
        assert required in runtime_source

    water_source = WATER_RUNTIME_PATH.read_text()
    for shared in (
        "pub(crate) const OH_DISTANCE_ANGSTROM",
        "pub(crate) const HH_DISTANCE_ANGSTROM",
        "pub(crate) const POSITION_X",
        "pub(crate) const ATOM_NONBONDED",
        "pub(crate) const BONDS",
        "pub(crate) const ANGLES",
        "pub(crate) const EXCLUSIONS",
    ):
        assert shared in water_source

    assert (
        "pub(crate) fn frozen_xh_constraints()" in CONSTRAINTS_RUNTIME_PATH.read_text()
    )
