from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config/engine_v2_native_ala3_peptide_profile_v1.json"
ASSET_PATH = (
    ROOT
    / "rust/betelgeuze-runtime/assets/engine_v2_native_ala3_peptide_profile_v1.json"
)
DATA_PATH = ROOT / "rust/betelgeuze-runtime/src/development_peptide_data.rs"
RUNTIME_PATH = ROOT / "rust/betelgeuze-runtime/src/development_peptide.rs"
GENERATOR_PATH = (
    ROOT / "benchmarks/oracles/openmm/generate_native_ala3_profile_v1.py"
)

PROFILE_SHA256 = "a7a4229cc30bb24393b06d4b19e25b917060213ca432b1263329bda6c0b49adf"
DATA_SHA256 = "7a75f9ccd2d0cee99387ec2ae25c47b145a1a325bf0498b1752340c3a04b88a0"
PDB_SHA256 = "5510388d045a8f8938236f0975e4f52b81e1b8b7bf9d0c5effcf856050d6123d"
FFXML_SHA256 = "d9f9779c09d67cd5f8bc657692f174ffab14c469dfd06d560ac1899fa7e976b8"


def load_generator():
    spec = importlib.util.spec_from_file_location("ala3_generator", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_asset_and_generated_data_are_exactly_bound() -> None:
    canonical = PROFILE_PATH.read_bytes()
    assert ASSET_PATH.read_bytes() == canonical
    assert hashlib.sha256(canonical).hexdigest() == PROFILE_SHA256
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() == DATA_SHA256

    profile = json.loads(canonical)
    assert profile["schema_id"] == (
        "betelgeuze.engine_v2_native_ala3_peptide_profile/1.0.0"
    )
    assert profile["profile_id"] == "engine_v2_native_ala3_ff14sb_development_v1"
    assert profile["native_projection"]["generated_rust_data_sha256"] == DATA_SHA256
    generated_data = DATA_PATH.read_text()
    assert (
        generated_data.count(
            "lennard_jones_scale: f64::from_bits(0x3fe0000000000000)"
        )
        == 74
    )
    assert (
        generated_data.count("coulomb_scale: f64::from_bits(0x3feaaaaaaaaaaaab)")
        == 74
    )


def test_source_identity_topology_and_projection_contract_are_frozen() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    source = profile["source"]
    assert source["coordinate_artifact"]["sha256"] == PDB_SHA256
    assert source["parameter_artifact"]["sha256"] == FFXML_SHA256
    assert source["parameter_artifact"]["reference_doi"] == (
        "10.1021/acs.jctc.5b00255"
    )
    assert source["parameter_artifact"][
        "legal_compliance_determination_provided"
    ] is False
    assert source["projection_tool"] == (
        "benchmarks/oracles/openmm/generate_native_ala3_profile_v1.py"
    )

    topology = profile["topology"]
    assert topology["residue_sequence"] == ["ALA", "ALA", "ALA"]
    assert topology["atom_count"] == 33
    assert topology["bond_count"] == 32
    assert topology["angle_count"] == 57
    assert topology["periodic_torsion_term_count"] == 72
    assert topology["exclusion_count"] == 89
    assert topology["one_four_scale_count"] == 74
    assert [atom["index"] for atom in topology["atoms"]] == list(range(33))
    assert abs(topology["net_charge_elementary"]) <= 1.0e-12

    projection = profile["native_projection"]
    assert projection["one_four_lennard_jones_scale"] == 0.5
    assert projection["one_four_coulomb_scale"] == pytest.approx(5.0 / 6.0)
    assert projection[
        "proper_and_improper_terms_use_the_existing_periodic_torsion_representation"
    ] is True
    nonbonded = projection["nonbonded"]
    assert nonbonded["cell"] is None
    assert nonbonded["cutoff_angstrom"] == 20.0
    assert nonbonded["switch_start_angstrom"] == 15.0
    assert nonbonded["maximum_fixture_pair_distance_angstrom"] < 15.0
    assert nonbonded["switching_is_exactly_one_for_every_fixture_pair"] is True
    assert nonbonded["dielectric"] == 1.0
    assert nonbonded["screening_kappa_per_angstrom"] == 0.0


def test_openmm_reference_dynamics_and_authority_are_fail_closed() -> None:
    profile = json.loads(PROFILE_PATH.read_text())
    reference = profile["openmm_reference"]
    assert reference["platform"] == "Reference"
    assert reference["nonbonded_method"] == "NoCutoff"
    assert reference["constraints"] is None
    assert reference["remove_center_of_mass_motion"] is False
    assert reference["potential_energy_kcal_per_mol"] == pytest.approx(
        10.003287760014612, abs=1.0e-15
    )
    assert reference["maximum_absolute_force_kcal_per_mol_per_angstrom"] == (
        pytest.approx(28.64752676264597, abs=1.0e-14)
    )
    assert reference["comparison"] == {
        "energy_absolute_tolerance_kcal_per_mol": 2.0e-5,
        "force_absolute_tolerance_kcal_per_mol_per_angstrom": 5.0e-5,
    }

    assert profile["dynamics"] == {
        "integrator": "velocity_verlet",
        "initial_velocities": "all_exact_zero",
        "timestep_femtoseconds": 0.05,
        "step_count": 32,
        "checkpoint_step": 13,
        "cpu_backend_state_parity_required": True,
        "exact_checkpoint_continuation_required": True,
    }
    assert profile["authority"] == {
        "development_fixture_only": True,
        "general_peptide_parameter_assignment_implemented": False,
        "production_md_validated": False,
        "scientific_claim_authorized": False,
        "molecular_execution_authorized": False,
        "performance_claim_authorized": False,
        "hip_device_execution_authorized": False,
        "product_authority": False,
    }


def test_generator_and_runtime_bind_the_same_exact_contract() -> None:
    generator = load_generator()
    assert generator.SCHEMA_ID == (
        "betelgeuze.engine_v2_native_ala3_peptide_profile/1.0.0"
    )
    assert generator.PROFILE_ID == "engine_v2_native_ala3_ff14sb_development_v1"
    assert generator.EXPECTED_PDB_SHA256 == PDB_SHA256
    assert generator.EXPECTED_FFXML_SHA256 == FFXML_SHA256
    assert generator.EXPECTED_OPENMM_DISTRIBUTION_VERSION == "8.4.0.post2"
    assert generator.EXPECTED_OPENMM_RUNTIME_VERSION == "8.4.0.dev-4768436"
    assert generator.NATIVE_CUTOFF_ANGSTROM == 20.0
    assert generator.NATIVE_SWITCH_START_ANGSTROM == 15.0
    assert generator.TIMESTEP_FEMTOSECONDS == 0.05
    assert generator.NVE_STEPS == 32
    assert generator.CHECKPOINT_STEP == 13

    runtime_source = RUNTIME_PATH.read_text()
    for required in (
        "DEVELOPMENT_ALA3_V1_SCHEMA_ID",
        "DEVELOPMENT_ALA3_V1_PROFILE_ID",
        "development_ala3_v1_profile_sha256",
        "evaluate_development_ala3_v1",
        "DevelopmentAla3V1",
        "Backend::CppCpuReference | Backend::RustCpu",
        "DistanceConstraints::default()",
        "Integrator::VelocityVerlet",
        "data::PAIR_SCALES",
    ):
        assert required in runtime_source


def test_generator_rejects_unpinned_openmm_before_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = load_generator()
    fake_openmm = SimpleNamespace(
        version=SimpleNamespace(version="8.4.0.dev-4768436")
    )
    monkeypatch.setattr(
        generator.importlib.metadata, "version", lambda name: "8.4.0.post2"
    )
    assert generator.require_exact_openmm_runtime(fake_openmm) == (
        "8.4.0.post2",
        "8.4.0.dev-4768436",
    )

    monkeypatch.setattr(generator.importlib.metadata, "version", lambda name: "8.5.0")
    with pytest.raises(SystemExit, match="distribution version mismatch"):
        generator.require_exact_openmm_runtime(fake_openmm)

    monkeypatch.setattr(
        generator.importlib.metadata, "version", lambda name: "8.4.0.post2"
    )
    fake_openmm.version.version = "8.5.0.dev"
    with pytest.raises(SystemExit, match="runtime version mismatch"):
        generator.require_exact_openmm_runtime(fake_openmm)
