"""Development-only native dimer bridge to the existing V2 cross evaluator.

Coordinates and chemistry come from the native CSV and companion MOL record.
The explicitly selected parameter profile is an approximate, graph-derived
baseline, not measured charges, OPLS, UFF energy, affinity, or a production FF.
No hydrogen coordinates, bonds, protonation states, or missing values are added.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Mapping

import numpy as np
from rdkit import Chem, rdBase
from rdkit.Chem import rdForceFieldHelpers, rdPartialCharges
import torch

from betelgeuze_engine.product.v2_cross_interaction import evaluate_prepared_cross_interaction
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_system_sha256, require_valid_all_atom_system,
)

SCHEMA_ID = "betelgeuze.des370k_v2_interaction_development/1.0.0"
PARAMETER_PROFILE = "v2_lb_lj_uff_atomic_values_gasteiger12_neutral_chno_v1"
ENERGY_COLUMN = "cbs_CCSD(T)_all"
GEOMETRY_FIELDS = ("smiles0", "smiles1", "charge0", "charge1", "natoms0", "natoms1",
                   "system_id", "group_orig", "group_id", "k_index", "geom_id", "xyz", "elements")
MODEL_CONFIG = {"cutoff_angstrom": 20.0, "switch_start_angstrom": 18.0,
                "dielectric": 1.0, "screening_kappa_per_angstrom": 0.0}


class DimerInputError(ValueError):
    """A native record or the declared approximation is unsupported."""


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _integer(value, name):
    if type(value) is int:
        return value
    if type(value) is str and re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    raise DimerInputError("invalid_integer:" + name)


def _number(value, name):
    if type(value) not in (str, float, int):
        raise DimerInputError("invalid_number:" + name)
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise DimerInputError("invalid_number:" + name) from None
    if not math.isfinite(result):
        raise DimerInputError("nonfinite_number:" + name)
    return result


def _canonical_smiles(mol):
    return Chem.MolToSmiles(Chem.RemoveHs(mol), canonical=True, isomericSmiles=True)


def validate_units(units):
    if (not isinstance(units, Mapping) or units.get("xyz") != "angstrom"
            or units.get(ENERGY_COLUMN) != "kcal/mol"
            or units.get("charge0") != "elementary charge"
            or units.get("charge1") != "elementary charge"):
        raise DimerInputError("native_units_missing_or_mismatched")


def prepare_native_dimer(row, mol_block, *, units, parameter_profile):
    """Preserve CSV atom order and verify its bond/element mapping to source MOL.

The profile is mandatory: it must never silently replace supplied receptor
charges in another product route. RDKit is used only for graph typing and
explicit charge assignment, never to evaluate or minimize an energy.
"""
    validate_units(units)
    if parameter_profile != PARAMETER_PROFILE:
        raise DimerInputError("explicit_development_parameter_profile_required")
    count0, count1 = (_integer(row[f"natoms{i}"], f"natoms{i}") for i in (0, 1))
    if not (1 <= count0 <= 64 and 1 <= count1 <= 64):
        raise DimerInputError("monomer_atom_count_outside_1_to_64")
    charges = [_integer(row[f"charge{i}"], f"charge{i}") for i in (0, 1)]
    if charges != [0, 0]:
        raise DimerInputError("charged_monomer_outside_declared_profile")
    for key in ("system_id", "group_id", "geom_id", "k_index"):
        _integer(row[key], key)
    count = count0 + count1
    if type(row["xyz"]) is not str or type(row["elements"]) is not str:
        raise DimerInputError("native_coordinates_or_elements_not_text")
    values = [_number(v, "xyz") for v in row["xyz"].split()]
    elements = row["elements"].split()
    if len(values) != 3 * count or len(elements) != count:
        raise DimerInputError("native_atom_coordinate_count_mismatch")
    if any(element not in {"H", "C", "N", "O"} for element in elements):
        raise DimerInputError("element_outside_neutral_chno_profile")
    xyz = np.asarray(values, dtype=np.float64).reshape(count, 3)
    mol = Chem.MolFromMolBlock(mol_block, sanitize=True, removeHs=False, strictParsing=True)
    if mol is None or mol.GetNumAtoms() != count or mol.GetNumConformers() != 1:
        raise DimerInputError("source_mol_parse_or_atom_count_failure")
    if [atom.GetSymbol() for atom in mol.GetAtoms()] != elements:
        raise DimerInputError("source_mol_element_order_mismatch")
    # V2000 companion files have four-decimal coordinates. CSV remains the
    # evaluated coordinate authority; the tolerance only verifies their mapping.
    if not np.allclose(mol.GetConformer().GetPositions(), xyz, rtol=0, atol=0.000051):
        raise DimerInputError("source_mol_coordinate_mapping_mismatch")
    atom_maps = []
    fragments = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True, fragsMolAtomMapping=atom_maps)
    expected_maps = [tuple(range(count0)), tuple(range(count0, count))]
    if len(fragments) != 2 or atom_maps != expected_maps:
        raise DimerInputError("source_mol_monomer_or_cross_bond_mismatch")
    source_mol_sha = hashlib.sha256(mol_block.encode()).hexdigest()
    parameter_source = {
        "profile": PARAMETER_PROFILE, "rdkit_version": rdBase.rdkitVersion,
        "charge_assignment": "Gasteiger-Marsili, nIter=12, throwOnParamFailure=True",
        "charge_evidence_kind": "heuristic_graph_derived_parameter_not_experimental_charge",
        "lj_atomic_values": "RDKit GetUFFVdWParams(i,i); sigma=x_ii/2**(1/6); epsilon=D_ii",
        "mixing": "Lorentz-Berthelot from unchanged V2; not UFF geometric-radius mixing",
        "missing_parameter_policy": "reject; no zero fill or fallback",
        "hydrogen_coordinates_generated": False,
        "native_partial_charges_supplied": False,
        "energy_evaluator": "existing_v2_switched_cross_lj_screened_coulomb_v1",
        "scientific_parameter_applicability_validated": False,
    }
    systems, parameter_rows, monomer_smiles = [], [], []
    for side, (fragment, indices) in enumerate(zip(fragments, atom_maps)):
        source_smiles = Chem.MolFromSmiles(row[f"smiles{side}"])
        if source_smiles is None or _canonical_smiles(fragment) != _canonical_smiles(source_smiles):
            raise DimerInputError("source_mol_smiles_chemistry_mismatch")
        if any(atom.GetNumImplicitHs() or atom.GetNumExplicitHs() for atom in fragment.GetAtoms()):
            raise DimerInputError("source_hydrogen_coordinates_incomplete")
        if any(atom.GetFormalCharge() or atom.GetNumRadicalElectrons() or atom.GetIsotope()
               for atom in fragment.GetAtoms()):
            raise DimerInputError("formal_charge_radical_or_isotope_outside_profile")
        canonical = _canonical_smiles(fragment)
        monomer_smiles.append(canonical)
        try:
            rdPartialCharges.ComputeGasteigerCharges(fragment, nIter=12, throwOnParamFailure=True)
        except (RuntimeError, ValueError) as exc:
            raise DimerInputError("charge_assignment_failed:" + str(exc)) from exc
        parameters, atoms, raw_lj = [], [], []
        for atom in fragment.GetAtoms():
            index = atom.GetIdx()
            charge = _number(atom.GetProp("_GasteigerCharge"), "computed_charge")
            if abs(_number(atom.GetProp("_GasteigerHCharge"), "implicit_hydrogen_charge")) > 1e-12:
                raise DimerInputError("unmaterialized_hydrogen_charge")
            pair = rdForceFieldHelpers.GetUFFVdWParams(fragment, index, index)
            if pair is None or len(pair) != 2:
                raise DimerInputError("lj_atomic_parameter_missing")
            x, epsilon = (_number(v, "uff_atomic_value") for v in pair)
            if x <= 0 or epsilon <= 0:
                raise DimerInputError("lj_atomic_parameter_outside_profile")
            parameters.append({"atom_index": index, "charge_e": charge,
                               "sigma_angstrom": x / 2 ** (1 / 6), "epsilon_kcal_per_mol": epsilon})
            raw_lj.append({"atom_index": index, "x_ii_angstrom": x, "D_ii_kcal_per_mol": epsilon})
            atoms.append(Atom(index, f"{atom.GetSymbol()}{indices[index]}", atom.GetSymbol(),
                              atom.GetAtomicNum(), 0, formal_charge=atom.GetFormalCharge(),
                              partial_charge_e=charge, aromatic=atom.GetIsAromatic(),
                              stereo=atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else "unspecified",
                              metadata={"native_atom_index": indices[index], "charge_origin": parameter_source["charge_evidence_kind"]}))
        if abs(math.fsum(p["charge_e"] for p in parameters)) > 1e-8:
            raise DimerInputError("computed_charge_sum_mismatch")
        bonds = []
        for bond in fragment.GetBonds():
            first, second = sorted((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()))
            stereo = str(bond.GetStereo())
            if stereo not in {"STEREONONE", "STEREOE", "STEREOZ"}:
                raise DimerInputError("unresolved_bond_stereochemistry")
            bonds.append(Bond(len(bonds), first, second, bond.GetBondTypeAsDouble(),
                              aromatic=bond.GetIsAromatic(), stereo={"STEREONONE": "none", "STEREOE": "E", "STEREOZ": "Z"}[stereo],
                              source="published_companion_mol"))
        system = AllAtomSystem(
            system_id=f"DES370K:{row['geom_id']}:monomer{side}", atoms=tuple(atoms), bonds=tuple(bonds),
            residues=(Residue(0, "FRG", 0, 1, tuple(range(len(atoms))), entity_type="non_polymer", hetero=True),),
            chains=(Chain(0, str(side), (0,)),),
            coordinates=torch.tensor(xyz[list(indices)][None], dtype=torch.float64, device="cpu"),
            provenance=StructureProvenance(source_format="des370k_csv_and_companion_mol",
                source_id=f"DES370K:{row['geom_id']}", source_sha256=source_mol_sha,
                parser_name=SCHEMA_ID, parser_version="1"),
            metadata={"native_csv_geometry_sha256": sha({"xyz": row["xyz"], "elements": row["elements"]}),
                      "source_monomer_smiles": row[f"smiles{side}"], "canonical_isomeric_smiles": canonical,
                      "source_atom_indices": list(indices), "parameter_assignment": parameter_source,
                      "raw_uff_atomic_values": raw_lj, "original_quantum_molecular_charge": charges[side],
                      "is_protein_receptor": False, "geometry_optimized_or_changed": False},
        )
        require_valid_all_atom_system(system)
        systems.append(system)
        parameter_rows.append(parameters)
    return systems, parameter_rows, {"parameter_source": parameter_source,
                                    "monomer_smiles": monomer_smiles,
                                    "native_row_geometry_sha256": sha({key: row[key] for key in (
                                        "xyz", "elements", "smiles0", "smiles1", "natoms0", "natoms1", "charge0", "charge1")}),
                                    "source_mol_sha256": source_mol_sha}


def score_native_dimer(row, mol_block, *, units, parameter_profile):
    """Evaluate a geometry without reading or propagating any energy label.

    Only a fixed whitelist of geometry fields is accessed, even when a caller
    supplies a full native record. Reference attachment is a separate operation.
    """
    row = {key: row[key] for key in GEOMETRY_FIELDS}
    wall, cpu = time.perf_counter(), time.process_time()
    systems, parameters, provenance = prepare_native_dimer(
        row, mol_block, units=units, parameter_profile=parameter_profile)
    center = systems[1].coordinates[0].mean(dim=0)
    radius = float(torch.linalg.vector_norm(systems[1].coordinates[0] - center, dim=-1).max()) + 1.0
    baseline = evaluate_prepared_cross_interaction(
        *systems, *parameters,
        source_declarations={"coordinate_frame_id": provenance["native_row_geometry_sha256"],
                             "prepared_state_id": sha([canonical_system_sha256(s) for s in systems]),
                             "parameter_source_id": sha(provenance["parameter_source"]),
                             "charge_source_id": sha(provenance["parameter_source"])},
        pocket_center_angstrom=center.tolist(), pocket_radius_angstrom=radius, **MODEL_CONFIG)
    return {"schema_id": SCHEMA_ID, "native_record": dict(row), "provenance": provenance,
            "baseline": baseline,
            "scope": "neutral_CHNO_fragment_dimer_development_only_not_protein_ligand_affinity",
            "pocket_meaning": "explicit_fragment_bounding_envelope_not_a_protein_pocket",
            "cost": {"wall_seconds": time.perf_counter() - wall,
                     "cpu_seconds": time.process_time() - cpu,
                     "scope": "native validation, explicit parameter assignment, canonical construction and V2 evaluation; import, file IO and serialization excluded"},
            "experimental_label_used": False, "customer_execution": False,
            "external_solver_called": False, "scientifically_validated": False}


def evaluate_native_dimer(row, mol_block, *, units, parameter_profile):
    """Explicitly attach a computed reference after scoring the same geometry."""
    result = score_native_dimer(row, mol_block, units=units, parameter_profile=parameter_profile)
    reference = _number(row[ENERGY_COLUMN], ENERGY_COLUMN)
    result["native_record"] = dict(row)
    result["reference"] = {
        "evidence_kind": "external_computed_reference", "column": ENERGY_COLUMN,
        "quantity": "counterpoise_corrected_gas_phase_dimer_interaction_energy",
        "method": "DES370K composite CCSD(T)/CBS", "units": "kcal/mol",
        "value": reference, "atom_forces": None,
        "force_unavailable_reason": "native_reference_has_no_per_atom_force_labels",
    }
    result["residual_target"] = {
        "quantity": "interaction_energy_reference_minus_declared_v2_baseline",
        "value_kcal_per_mol": reference - result["baseline"]["quantities"]["cross_total_kcal_per_mol"],
        "force_labels": None,
    }
    return result
