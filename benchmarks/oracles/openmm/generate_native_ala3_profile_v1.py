#!/usr/bin/env python3
"""Generate the frozen native Ala3 development profile and Rust data module.

This external-oracle development tool deliberately lives below the repository's
only OpenMM import boundary. The checked-in runtime has no OpenMM or nglview
dependency: callers provide an exact Ala3 PDB and an exact OpenMM ff14SB XML,
and this tool projects the resulting four-force OpenMM System into the existing
native System/ForceField representation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import struct
from pathlib import Path
from typing import Any, Iterable


SCHEMA_ID = "betelgeuze.engine_v2_native_ala3_peptide_profile/1.0.0"
PROFILE_ID = "engine_v2_native_ala3_ff14sb_development_v1"
EXPECTED_PDB_SHA256 = "5510388d045a8f8938236f0975e4f52b81e1b8b7bf9d0c5effcf856050d6123d"
EXPECTED_FFXML_SHA256 = "d9f9779c09d67cd5f8bc657692f174ffab14c469dfd06d560ac1899fa7e976b8"
EXPECTED_OPENMM_DISTRIBUTION_VERSION = "8.4.0.post2"
EXPECTED_OPENMM_RUNTIME_VERSION = "8.4.0.dev-4768436"
FF14SB_REFERENCE_DOI = "10.1021/acs.jctc.5b00255"
NATIVE_CUTOFF_ANGSTROM = 20.0
NATIVE_SWITCH_START_ANGSTROM = 15.0
NATIVE_MINIMUM_PAIR_DISTANCE_ANGSTROM = 1.0e-6
TIMESTEP_FEMTOSECONDS = 0.05
NVE_STEPS = 32
CHECKPOINT_STEP = 13
ENERGY_ABSOLUTE_TOLERANCE_KCAL_PER_MOL = 2.0e-5
FORCE_ABSOLUTE_TOLERANCE_KCAL_PER_MOL_ANGSTROM = 5.0e-5


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def f64_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def rust_f64(value: float) -> str:
    return f"f64::from_bits(0x{f64_bits(value):016x})"


def rust_array(
    name: str, type_name: str, values: Iterable[str], *, test_only: bool = False
) -> str:
    rows = list(values)
    body = "\n".join(f"    {row}," for row in rows)
    attributes = "#[cfg(test)]\n" if test_only else ""
    return (
        attributes
        + "#[rustfmt::skip]\n"
        f"pub(super) const {name}: [{type_name}; {len(rows)}] = [\n{body}\n];\n"
    )


def canonical_f64_digest(channels: Iterable[Iterable[float]]) -> str:
    digest = hashlib.sha256()
    for channel in channels:
        values = list(channel)
        digest.update(struct.pack("<Q", len(values)))
        for value in values:
            digest.update(struct.pack("<d", value))
    return digest.hexdigest()


def require_exact_source(path: Path, expected_sha256: str, name: str) -> bytes:
    payload = path.read_bytes()
    observed = sha256_bytes(payload)
    if observed != expected_sha256:
        raise SystemExit(
            f"{name} SHA-256 mismatch: expected {expected_sha256}, observed {observed}"
        )
    return payload


def require_exact_openmm_runtime(openmm: Any) -> tuple[str, str]:
    distribution_version = importlib.metadata.version("OpenMM")
    runtime_version = str(openmm.version.version)
    if distribution_version != EXPECTED_OPENMM_DISTRIBUTION_VERSION:
        raise SystemExit(
            "OpenMM distribution version mismatch: expected "
            f"{EXPECTED_OPENMM_DISTRIBUTION_VERSION}, observed {distribution_version}"
        )
    if runtime_version != EXPECTED_OPENMM_RUNTIME_VERSION:
        raise SystemExit(
            "OpenMM runtime version mismatch: expected "
            f"{EXPECTED_OPENMM_RUNTIME_VERSION}, observed {runtime_version}"
        )
    return distribution_version, runtime_version


def build_projection(pdb_path: Path, ffxml_path: Path) -> dict[str, Any]:
    import openmm
    from openmm import Platform, app, unit

    openmm_distribution_version, openmm_runtime_version = require_exact_openmm_runtime(
        openmm
    )

    pdb = app.PDBFile(str(pdb_path))
    forcefield = app.ForceField(str(ffxml_path))
    system = forcefield.createSystem(
        pdb.topology,
        nonbondedMethod=app.NoCutoff,
        constraints=None,
        rigidWater=False,
        removeCMMotion=False,
    )
    if system.getNumConstraints() != 0:
        raise SystemExit("Ala3 projection unexpectedly contains constraints")

    expected_force_types = {
        "HarmonicBondForce",
        "HarmonicAngleForce",
        "PeriodicTorsionForce",
        "NonbondedForce",
    }
    forces = list(system.getForces())
    observed_force_types = [type(force).__name__ for force in forces]
    if len(forces) != 4 or set(observed_force_types) != expected_force_types:
        raise SystemExit(
            f"unexpected OpenMM force classes: {sorted(observed_force_types)}"
        )

    bond_force = next(
        force for force in system.getForces() if isinstance(force, openmm.HarmonicBondForce)
    )
    angle_force = next(
        force for force in system.getForces() if isinstance(force, openmm.HarmonicAngleForce)
    )
    torsion_force = next(
        force for force in system.getForces() if isinstance(force, openmm.PeriodicTorsionForce)
    )
    nonbonded_force = next(
        force for force in system.getForces() if isinstance(force, openmm.NonbondedForce)
    )

    positions = pdb.positions.value_in_unit(unit.angstrom)
    position_x = [float(row[0]) for row in positions]
    position_y = [float(row[1]) for row in positions]
    position_z = [float(row[2]) for row in positions]
    maximum_pair_distance = max(
        math.dist(positions[left], positions[right])
        for left in range(len(positions))
        for right in range(left + 1, len(positions))
    )
    if maximum_pair_distance >= NATIVE_SWITCH_START_ANGSTROM:
        raise SystemExit("native switch start does not strictly enclose the Ala3 fixture")

    masses = [
        system.getParticleMass(index).value_in_unit(unit.dalton)
        for index in range(system.getNumParticles())
    ]
    particles: list[tuple[float, float, float]] = []
    for index in range(nonbonded_force.getNumParticles()):
        charge, sigma, epsilon = nonbonded_force.getParticleParameters(index)
        particles.append(
            (
                charge.value_in_unit(unit.elementary_charge),
                sigma.value_in_unit(unit.angstrom),
                epsilon.value_in_unit(unit.kilocalorie_per_mole),
            )
        )
    charges = [row[0] for row in particles]
    sigma = [row[1] for row in particles]
    epsilon = [row[2] for row in particles]
    if len(positions) != 33 or len(masses) != 33 or len(particles) != 33:
        raise SystemExit("Ala3 projection does not contain exactly 33 particles")
    if abs(sum(charges)) > 1.0e-12:
        raise SystemExit("Ala3 projection is not neutral within 1e-12 elementary charge")
    if nonbonded_force.getNonbondedMethod() != openmm.NonbondedForce.NoCutoff:
        raise SystemExit("Ala3 reference unexpectedly uses a cutoff")

    bonds: list[tuple[int, int, float, float]] = []
    for row in range(bond_force.getNumBonds()):
        atom_i, atom_j, equilibrium, force_constant = bond_force.getBondParameters(row)
        bonds.append(
            (
                int(atom_i),
                int(atom_j),
                equilibrium.value_in_unit(unit.angstrom),
                force_constant.value_in_unit(
                    unit.kilocalorie_per_mole / unit.angstrom**2
                ),
            )
        )

    angles: list[tuple[int, int, int, float, float]] = []
    for row in range(angle_force.getNumAngles()):
        atom_i, atom_j, atom_k, equilibrium, force_constant = (
            angle_force.getAngleParameters(row)
        )
        angles.append(
            (
                int(atom_i),
                int(atom_j),
                int(atom_k),
                equilibrium.value_in_unit(unit.radian),
                force_constant.value_in_unit(
                    unit.kilocalorie_per_mole / unit.radian**2
                ),
            )
        )

    torsions: list[tuple[int, int, int, int, int, float, float]] = []
    for row in range(torsion_force.getNumTorsions()):
        atom_i, atom_j, atom_k, atom_l, periodicity, phase, amplitude = (
            torsion_force.getTorsionParameters(row)
        )
        torsions.append(
            (
                int(atom_i),
                int(atom_j),
                int(atom_k),
                int(atom_l),
                int(periodicity),
                phase.value_in_unit(unit.radian),
                amplitude.value_in_unit(unit.kilocalorie_per_mole),
            )
        )

    exclusions: list[tuple[int, int]] = []
    pair_scales: list[tuple[int, int, float, float]] = []
    for row in range(nonbonded_force.getNumExceptions()):
        atom_i, atom_j, charge_product, exception_sigma, exception_epsilon = (
            nonbonded_force.getExceptionParameters(row)
        )
        atom_i = int(atom_i)
        atom_j = int(atom_j)
        pair = (min(atom_i, atom_j), max(atom_i, atom_j))
        charge_product_value = charge_product.value_in_unit(unit.elementary_charge**2)
        exception_sigma_value = exception_sigma.value_in_unit(unit.angstrom)
        exception_epsilon_value = exception_epsilon.value_in_unit(
            unit.kilocalorie_per_mole
        )
        if charge_product_value == 0.0 and exception_epsilon_value == 0.0:
            exclusions.append(pair)
            continue
        base_charge_product = charges[atom_i] * charges[atom_j]
        base_sigma = 0.5 * (sigma[atom_i] + sigma[atom_j])
        base_epsilon = math.sqrt(epsilon[atom_i] * epsilon[atom_j])
        if base_charge_product == 0.0 or base_epsilon == 0.0:
            raise SystemExit("nonzero exception cannot be represented as a native scale")
        if abs(exception_sigma_value - base_sigma) > 1.0e-12:
            raise SystemExit("exception sigma does not use the native Lorentz rule")
        lennard_jones_scale = exception_epsilon_value / base_epsilon
        coulomb_scale = charge_product_value / base_charge_product
        if abs(lennard_jones_scale - 0.5) > 1.0e-12:
            raise SystemExit("exception does not use the ff14SB 1-4 LJ scale")
        if abs(coulomb_scale - 5.0 / 6.0) > 1.0e-12:
            raise SystemExit("exception does not use the ff14SB 1-4 Coulomb scale")
        pair_scales.append((pair[0], pair[1], 0.5, 5.0 / 6.0))
    exclusions.sort()
    pair_scales.sort()
    if len(set(exclusions)) != len(exclusions) or len(set(row[:2] for row in pair_scales)) != len(
        pair_scales
    ):
        raise SystemExit("duplicate nonbonded exception pair")
    if set(exclusions) & set(row[:2] for row in pair_scales):
        raise SystemExit("pair is both excluded and scaled")

    integrator = openmm.VerletIntegrator(0.001 * unit.picoseconds)
    context = openmm.Context(system, integrator, Platform.getPlatformByName("Reference"))
    context.setPositions(pdb.positions)
    state = context.getState(getEnergy=True, getForces=True)
    reference_energy = state.getPotentialEnergy().value_in_unit(unit.kilocalorie_per_mole)
    reference_forces_array = state.getForces(asNumpy=True).value_in_unit(
        unit.kilocalorie_per_mole / unit.angstrom
    )
    reference_force_x = [float(row[0]) for row in reference_forces_array]
    reference_force_y = [float(row[1]) for row in reference_forces_array]
    reference_force_z = [float(row[2]) for row in reference_forces_array]

    atoms = []
    for atom in pdb.topology.atoms():
        atoms.append(
            {
                "index": atom.index,
                "residue_index": atom.residue.index,
                "residue_name": atom.residue.name,
                "residue_id": atom.residue.id,
                "atom_name": atom.name,
                "element": atom.element.symbol if atom.element is not None else None,
            }
        )

    return {
        "atoms": atoms,
        "position_x": position_x,
        "position_y": position_y,
        "position_z": position_z,
        "mass": masses,
        "charge": charges,
        "sigma": sigma,
        "epsilon": epsilon,
        "bonds": bonds,
        "angles": angles,
        "torsions": torsions,
        "exclusions": exclusions,
        "pair_scales": pair_scales,
        "maximum_pair_distance": maximum_pair_distance,
        "reference_energy": reference_energy,
        "reference_force_x": reference_force_x,
        "reference_force_y": reference_force_y,
        "reference_force_z": reference_force_z,
        "openmm_runtime_version": openmm_runtime_version,
        "openmm_distribution_version": openmm_distribution_version,
    }


def render_rust_data(projection: dict[str, Any]) -> bytes:
    sections = [
        "// Generated by benchmarks/oracles/openmm/generate_native_ala3_profile_v1.py.\n",
        "// Do not edit by hand.\n\n",
        "use crate::{\n",
        "    AtomNonbonded, HarmonicAngle, HarmonicBond, PairExclusion, PairScale, PeriodicTorsion,\n",
        "};\n\n",
        f"pub(super) const ATOM_COUNT: usize = {len(projection['mass'])};\n",
        f"pub(super) const TIMESTEP_FEMTOSECONDS: f64 = {rust_f64(TIMESTEP_FEMTOSECONDS)};\n",
        "#[cfg(test)]\n",
        f"pub(super) const NVE_STEPS: u64 = {NVE_STEPS};\n",
        "#[cfg(test)]\n",
        f"pub(super) const CHECKPOINT_STEP: u64 = {CHECKPOINT_STEP};\n",
        "#[cfg(test)]\n",
        f"pub(super) const REFERENCE_ENERGY_KCAL_PER_MOL: f64 = {rust_f64(projection['reference_energy'])};\n",
        "#[cfg(test)]\n",
        f"pub(super) const ENERGY_ABSOLUTE_TOLERANCE_KCAL_PER_MOL: f64 = {rust_f64(ENERGY_ABSOLUTE_TOLERANCE_KCAL_PER_MOL)};\n",
        "#[cfg(test)]\n",
        "pub(super) const FORCE_ABSOLUTE_TOLERANCE_KCAL_PER_MOL_ANGSTROM: f64 =\n",
        f"    {rust_f64(FORCE_ABSOLUTE_TOLERANCE_KCAL_PER_MOL_ANGSTROM)};\n\n",
    ]
    for name, values in (
        ("POSITION_X", projection["position_x"]),
        ("POSITION_Y", projection["position_y"]),
        ("POSITION_Z", projection["position_z"]),
        ("MASS_DALTON", projection["mass"]),
        ("CHARGE_ELEMENTARY", projection["charge"]),
        ("REFERENCE_FORCE_X", projection["reference_force_x"]),
        ("REFERENCE_FORCE_Y", projection["reference_force_y"]),
        ("REFERENCE_FORCE_Z", projection["reference_force_z"]),
    ):
        sections.append(
            rust_array(
                name,
                "f64",
                (rust_f64(value) for value in values),
                test_only=name.startswith("REFERENCE_FORCE_"),
            )
        )
        sections.append("\n")
    sections.append(
        rust_array(
            "ATOM_NONBONDED",
            "AtomNonbonded",
            (
                "AtomNonbonded { sigma_angstrom: %s, epsilon_kcal_per_mol: %s }"
                % (rust_f64(sigma), rust_f64(epsilon))
                for sigma, epsilon in zip(projection["sigma"], projection["epsilon"])
            ),
        )
    )
    sections.append("\n")
    sections.append(
        rust_array(
            "BONDS",
            "HarmonicBond",
            (
                "HarmonicBond { atom_i: %d, atom_j: %d, equilibrium_angstrom: %s, force_constant_kcal_per_mol_angstrom2: %s }"
                % (atom_i, atom_j, rust_f64(equilibrium), rust_f64(force_constant))
                for atom_i, atom_j, equilibrium, force_constant in projection["bonds"]
            ),
        )
    )
    sections.append("\n")
    sections.append(
        rust_array(
            "ANGLES",
            "HarmonicAngle",
            (
                "HarmonicAngle { atom_i: %d, atom_j: %d, atom_k: %d, equilibrium_radians: %s, force_constant_kcal_per_mol_radian2: %s }"
                % (
                    atom_i,
                    atom_j,
                    atom_k,
                    rust_f64(equilibrium),
                    rust_f64(force_constant),
                )
                for atom_i, atom_j, atom_k, equilibrium, force_constant in projection["angles"]
            ),
        )
    )
    sections.append("\n")
    sections.append(
        rust_array(
            "TORSIONS",
            "PeriodicTorsion",
            (
                "PeriodicTorsion { atom_i: %d, atom_j: %d, atom_k: %d, atom_l: %d, periodicity: %d, phase_radians: %s, amplitude_kcal_per_mol: %s }"
                % (
                    atom_i,
                    atom_j,
                    atom_k,
                    atom_l,
                    periodicity,
                    rust_f64(phase),
                    rust_f64(amplitude),
                )
                for atom_i, atom_j, atom_k, atom_l, periodicity, phase, amplitude in projection[
                    "torsions"
                ]
            ),
        )
    )
    sections.append("\n")
    sections.append(
        rust_array(
            "EXCLUSIONS",
            "PairExclusion",
            (
                f"PairExclusion {{ atom_i: {atom_i}, atom_j: {atom_j} }}"
                for atom_i, atom_j in projection["exclusions"]
            ),
        )
    )
    sections.append("\n")
    sections.append(
        rust_array(
            "PAIR_SCALES",
            "PairScale",
            (
                "PairScale { atom_i: %d, atom_j: %d, lennard_jones_scale: %s, coulomb_scale: %s }"
                % (atom_i, atom_j, rust_f64(lj_scale), rust_f64(coulomb_scale))
                for atom_i, atom_j, lj_scale, coulomb_scale in projection["pair_scales"]
            ),
        )
    )
    return "".join(sections).encode()


def build_profile(
    projection: dict[str, Any],
    pdb_path: Path,
    ffxml_path: Path,
    rust_data_bytes: bytes,
) -> dict[str, Any]:
    force_digest = canonical_f64_digest(
        (
            projection["reference_force_x"],
            projection["reference_force_y"],
            projection["reference_force_z"],
        )
    )
    return {
        "schema_id": SCHEMA_ID,
        "profile_id": PROFILE_ID,
        "source": {
            "coordinate_artifact": {
                "identity": "nglview-3.1.2/datafiles/ala3.pdb",
                "sha256": sha256_bytes(pdb_path.read_bytes()),
                "license_record": "nglview distribution declares MIT; legal compliance determination remains external",
            },
            "parameter_artifact": {
                "identity": "OpenMM amber14/protein.ff14SB.xml",
                "sha256": sha256_bytes(ffxml_path.read_bytes()),
                "upstream_source": "AmberTools 17.6 leaprc.protein.ff14SB",
                "reference_doi": FF14SB_REFERENCE_DOI,
                "openmm_distribution_version": projection["openmm_distribution_version"],
                "openmm_runtime_version": projection["openmm_runtime_version"],
                "legal_compliance_determination_provided": False,
            },
            "projection_tool": "benchmarks/oracles/openmm/generate_native_ala3_profile_v1.py",
        },
        "units": {
            "length": "angstrom",
            "energy": "kcal_per_mol",
            "force": "kcal_per_mol_per_angstrom",
            "mass": "dalton",
            "charge": "elementary_charge",
            "time": "femtosecond",
        },
        "topology": {
            "residue_sequence": ["ALA", "ALA", "ALA"],
            "atom_count": len(projection["atoms"]),
            "atoms": projection["atoms"],
            "bond_count": len(projection["bonds"]),
            "angle_count": len(projection["angles"]),
            "periodic_torsion_term_count": len(projection["torsions"]),
            "exclusion_count": len(projection["exclusions"]),
            "one_four_scale_count": len(projection["pair_scales"]),
            "net_charge_elementary": sum(projection["charge"]),
        },
        "native_projection": {
            "generated_rust_data_sha256": sha256_bytes(rust_data_bytes),
            "nonbonded": {
                "cell": None,
                "cutoff_angstrom": NATIVE_CUTOFF_ANGSTROM,
                "switch_start_angstrom": NATIVE_SWITCH_START_ANGSTROM,
                "maximum_fixture_pair_distance_angstrom": projection[
                    "maximum_pair_distance"
                ],
                "switching_is_exactly_one_for_every_fixture_pair": True,
                "dielectric": 1.0,
                "screening_kappa_per_angstrom": 0.0,
                "minimum_pair_distance_angstrom": NATIVE_MINIMUM_PAIR_DISTANCE_ANGSTROM,
            },
            "one_four_lennard_jones_scale": 0.5,
            "one_four_coulomb_scale": 5.0 / 6.0,
            "proper_and_improper_terms_use_the_existing_periodic_torsion_representation": True,
        },
        "openmm_reference": {
            "platform": "Reference",
            "nonbonded_method": "NoCutoff",
            "constraints": None,
            "remove_center_of_mass_motion": False,
            "potential_energy_kcal_per_mol": projection["reference_energy"],
            "force_channels_sha256": force_digest,
            "maximum_absolute_force_kcal_per_mol_per_angstrom": max(
                abs(value)
                for channel in (
                    projection["reference_force_x"],
                    projection["reference_force_y"],
                    projection["reference_force_z"],
                )
                for value in channel
            ),
            "comparison": {
                "energy_absolute_tolerance_kcal_per_mol": ENERGY_ABSOLUTE_TOLERANCE_KCAL_PER_MOL,
                "force_absolute_tolerance_kcal_per_mol_per_angstrom": FORCE_ABSOLUTE_TOLERANCE_KCAL_PER_MOL_ANGSTROM,
            },
        },
        "dynamics": {
            "integrator": "velocity_verlet",
            "initial_velocities": "all_exact_zero",
            "timestep_femtoseconds": TIMESTEP_FEMTOSECONDS,
            "step_count": NVE_STEPS,
            "checkpoint_step": CHECKPOINT_STEP,
            "cpu_backend_state_parity_required": True,
            "exact_checkpoint_continuation_required": True,
        },
        "authority": {
            "development_fixture_only": True,
            "general_peptide_parameter_assignment_implemented": False,
            "production_md_validated": False,
            "scientific_claim_authorized": False,
            "molecular_execution_authorized": False,
            "performance_claim_authorized": False,
            "hip_device_execution_authorized": False,
            "product_authority": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdb", required=True, type=Path)
    parser.add_argument("--ffxml", required=True, type=Path)
    parser.add_argument("--profile-out", required=True, type=Path)
    parser.add_argument("--rust-out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_exact_source(args.pdb, EXPECTED_PDB_SHA256, "Ala3 PDB")
    require_exact_source(args.ffxml, EXPECTED_FFXML_SHA256, "ff14SB XML")
    projection = build_projection(args.pdb, args.ffxml)
    rust_data = render_rust_data(projection)
    profile = build_profile(projection, args.pdb, args.ffxml, rust_data)
    args.rust_out.parent.mkdir(parents=True, exist_ok=True)
    args.profile_out.parent.mkdir(parents=True, exist_ok=True)
    args.rust_out.write_bytes(rust_data)
    args.profile_out.write_text(json.dumps(profile, indent=2) + "\n")
    print(f"rust_data_sha256={sha256_bytes(rust_data)}")
    print(f"profile_sha256={sha256_bytes(args.profile_out.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
