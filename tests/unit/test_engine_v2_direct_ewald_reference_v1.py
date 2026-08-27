from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config/engine_v2_direct_ewald_reference_profile_v1.json"
CRATE = ROOT / "rust/reference-ewald"
PROFILE_SHA256 = "5d0d46f737edd30f86a20346371198d1ca158b57841416098d44caa7d593b439"


def test_profile_identity_parent_and_reference_boundary_are_frozen() -> None:
    raw = PROFILE_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PROFILE_SHA256
    profile = json.loads(raw)
    assert profile["schema_id"] == (
        "betelgeuze.engine_v2_direct_ewald_reference_profile/1.0.0"
    )
    assert profile["profile_id"] == (
        "engine_v2_four_charge_direct_ewald_reference_development_v1"
    )
    assert profile["roadmap_issue"] == 434
    assert profile["parent"] == {
        "explicit_composition_profile_sha256": (
            "a9fad385e3eaf84c673507ee513778ad05842da139c282ce9def1c712eb13079"
        ),
        "explicit_composition_merge_commit": (
            "579fe48ea1320ad6139b55118d6368553f6b895b"
        ),
        "explicit_composition_tree": (
            "feac1d09582980a8fc947f5262eec86d4466633b"
        ),
    }
    assert profile["implementation"] == {
        "crate": "rust/reference-ewald",
        "reference_schema_id": "betelgeuze.reference_direct_ewald/1.0.0",
        "arithmetic": "scalar_binary64",
        "direct_ewald_implemented": True,
        "pme_implemented": False,
        "native_runtime_integrated": False,
        "native_abi_version_allocated": False,
        "external_md_engine_dependency": False,
        "fixed64_cpu_v7_source_closure_modified": False,
        "source_sha256": (
            "b27b0c4e417ff7ce4e5d7faa6889f2d595db78c18274a500b2ff29d4632302f0"
        ),
        "frozen_fixture_sha256": (
            "4911f62b37a26d31cdc76f62775da6e284d8e83fe0b3b3d9514a8e96c4a489e2"
        ),
        "cargo_lock_sha256": (
            "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
        ),
    }
    assert "reference-ewald" not in (ROOT / "rust/Cargo.toml").read_text()


def test_fixture_settings_and_frozen_observations_are_exact() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    assert profile["fixture"] == {
        "atom_count": 4,
        "positions_angstrom": [
            [1.25, 2.5, 3.75],
            [5.1, 3.2, 8.4],
            [10.2, 12.3, 7.7],
            [15.4, 17.1, 19.3],
        ],
        "charges_elementary": [0.7, -0.4, -0.6, 0.3],
        "net_charge_elementary": 0.0,
        "orthorhombic_lengths_angstrom": [18.0, 20.0, 22.0],
        "periodic_axes": [True, True, True],
        "excluded_pairs": [[0, 1]],
        "scaled_pairs": [
            {"atom_i": 2, "atom_j": 3, "coulomb_scale": 0.5}
        ],
    }
    assert profile["settings"] == {
        "coulomb_kcal_angstrom_per_mol_e2": 332.063713299,
        "alpha_per_angstrom": 0.31,
        "real_space_cutoff_angstrom": 8.9,
        "reciprocal_max_indices": [5, 5, 5],
        "dielectric": 1.0,
        "minimum_pair_distance_angstrom": 1e-8,
        "neutrality_tolerance_elementary": 1e-12,
        "real_pair_order": "lexicographic_i_then_j",
        "reciprocal_vector_order": (
            "nx_then_ny_then_nz_ascending_inclusive_omit_zero"
        ),
        "minimum_image_interval": (
            "half_open_negative_half_length_to_positive_half_length"
        ),
        "coordinate_reduction": (
            "per_axis_rem_euclid_primary_cell_with_positive_zero"
        ),
    }
    observation = profile["frozen_observation"]
    assert observation["total_kcal_per_mol"] == -6.063080251124816
    assert observation["maximum_central_finite_difference_force_error_kcal_per_mol_angstrom"] == (
        1.1746751071850525e-8
    )
    assert observation[
        "reciprocal_bound_absolute_total_difference_from_bound_9_kcal_per_mol"
    ] == {
        "bound_3": 0.21813662961478286,
        "bound_5": 0.0011959243365424754,
        "bound_7": 1.6123660273592577e-6,
    }
    assert observation["debug_release_bitwise_identical"] is True
    assert observation["frozen_energy_and_force_component_count"] == 17


def test_validation_authority_and_standalone_crate_are_bounded() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    assert all(profile["validation"].values())
    authority = profile["authority"]
    assert authority["development_fixture_only"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key != "development_fixture_only"
    )

    manifest = (CRATE / "Cargo.toml").read_text()
    assert "[workspace]" in manifest
    assert 'libm = { version = "=0.2.16"' in manifest
    assert "betelgeuze-runtime" not in manifest
    assert "reference-physics" not in manifest
    source = (CRATE / "src/lib.rs").read_text()
    for required in (
        "pub const EWALD_SCHEMA_ID",
        "pub fn evaluate",
        "real_space_kcal_per_mol",
        "reciprocal_space_kcal_per_mol",
        "self_kcal_per_mol",
        "pair_correction_kcal_per_mol",
        "libm::erfc",
        "reciprocal_max_indices",
        "NonNeutralSystem",
        "CutoffViolatesMinimumImage",
        "ConflictingPairRule",
    ):
        assert required in source

    fixture = (CRATE / "fixtures/direct_ewald_v1.tsv").read_text()
    assert "betelgeuze.reference_direct_ewald/1.0.0" in fixture
    assert len([line for line in fixture.splitlines() if "\t" in line]) == 18

    implementation = profile["implementation"]
    assert hashlib.sha256((CRATE / "src/lib.rs").read_bytes()).hexdigest() == (
        implementation["source_sha256"]
    )
    assert hashlib.sha256(
        (CRATE / "fixtures/direct_ewald_v1.tsv").read_bytes()
    ).hexdigest() == implementation["frozen_fixture_sha256"]
    assert hashlib.sha256((CRATE / "Cargo.lock").read_bytes()).hexdigest() == (
        implementation["cargo_lock_sha256"]
    )
