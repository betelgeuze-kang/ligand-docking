"""Narrow, source-origin-bound structural bridge for native v4 development rows.

The optional origin is part of a rederived v4 metadata record. Equality with
this observation checks bytes and structure, not the truth of an assay-state
claim or the scientific suitability of a prepared receptor.
"""

from __future__ import annotations

from rdkit import Chem

from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
from betelgeuze_engine.product.prepared_rigid_poses import (
    EVALUATION_FIELDS, _inside_declared_pocket, _number,
    _rigid_pose_coordinates, _transform,
)
from betelgeuze_engine_v2.molecular import canonical_system_sha256

from . import native_v4_bound as bound
from . import native_v4_chemical_identity as chemical
from . import public_assay_components as components
from .prepared_hard_overlap_screen import (
    HARD_OVERLAP_DISTANCE_ANGSTROM, minimum_cross_distance_angstrom,
)


SCHEMA = "native_v4_candidate_prepared_structural_binding_v1"
SOURCE_FIELD = "prepared_state_origin"
PARAMETER_KEYS = (
    "protein_atomtypes", "protein_defaults", "ligand_itp", "ligand_atomtypes",
    "ligand_defaults",
)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _sha(value: object) -> str:
    return components.digest(components.canonical(value))


def _construct(receptor) -> list[dict]:
    return [
        {
            "chain_id": chain.chain_id,
            "residues": [
                {"name": receptor.residues[index].name,
                 "sequence_number": receptor.residues[index].sequence_number,
                 "insertion_code": receptor.residues[index].insertion_code}
                for index in chain.residue_indices
            ],
        }
        for chain in receptor.chains
    ]


def _geometry_isomeric_smiles(mol: Chem.Mol) -> str:
    """Derive stereo from the prepared conformer, ignoring SDF declarations."""
    _require(mol.GetNumConformers() == 1 and mol.GetConformer().Is3D(),
             "native_prepared_ligand_geometry_stereochemistry_mismatch")
    geometry = Chem.Mol(mol)
    Chem.RemoveStereochemistry(geometry)
    Chem.AssignStereochemistryFrom3D(geometry)
    return Chem.MolToSmiles(
        Chem.RemoveHs(geometry, sanitize=True), canonical=True, isomericSmiles=True)


def _ligand_identity(prepared_input: dict, ligand, identity: dict) -> dict:
    ref = prepared_input["ligand_sdf"]
    raw = bound.read_bound(ref["path"], ref["sha256"])
    text = raw.decode("utf-8")
    mol = Chem.MolFromMolBlock(text.split("M  END", 1)[0] + "M  END\n",
                               sanitize=True, removeHs=False, strictParsing=True)
    _require(mol is not None and mol.GetNumAtoms() == ligand.atom_count,
             "native_prepared_ligand_atom_graph_mismatch")
    atoms = [
        {"atomic_number": atom.GetAtomicNum(), "formal_charge": atom.GetFormalCharge(),
         "isotope": atom.GetIsotope(), "aromatic": atom.GetIsAromatic()}
        for atom in mol.GetAtoms()
    ]
    bonds = sorted([
        {"atom_i": min(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()),
         "atom_j": max(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()),
         "order": bond.GetBondTypeAsDouble(), "aromatic": bond.GetIsAromatic()}
        for bond in mol.GetBonds()
    ], key=lambda item: (item["atom_i"], item["atom_j"]))
    observed_bonds = sorted([
        {"atom_i": bond.atom_i, "atom_j": bond.atom_j,
         "order": bond.order, "aromatic": bond.aromatic}
        for bond in ligand.bonds
    ], key=lambda item: (item["atom_i"], item["atom_j"]))
    _require(all(
        atom.atomic_number == expected["atomic_number"]
        and atom.formal_charge == expected["formal_charge"]
        and (atom.isotope_mass_number or 0) == expected["isotope"]
        and atom.aromatic == expected["aromatic"]
        for atom, expected in zip(ligand.atoms, atoms)
    ) and observed_bonds == bonds, "native_prepared_ligand_atom_graph_mismatch")
    normalized = Chem.RemoveHs(mol, sanitize=True)
    canonical = Chem.MolToSmiles(normalized, canonical=True, isomericSmiles=True)
    _require(identity.get("stereo_unspecified_count") == 0
             and not identity.get("unresolved_stereochemistry")
             and not any(str(info.specified) == "Unspecified"
                         for info in Chem.FindPotentialStereo(normalized))
             and canonical == identity["canonical_isomeric_smiles"]
             and chemical.digest(canonical) == identity["canonical_isomeric_smiles_sha256"]
             and Chem.GetFormalCharge(normalized) == identity["formal_charge"],
             "native_prepared_ligand_chemical_identity_mismatch")
    # MolFromMolBlock honors wedge bonds and atom parity. Re-derive stereo from
    # coordinates alone so a 2D drawing cannot inherit a correct SMILES from
    # those declarations.
    _require(_geometry_isomeric_smiles(mol) == canonical,
             "native_prepared_ligand_geometry_stereochemistry_mismatch")
    return {
        "sdf_sha256": ref["sha256"],
        "atom_graph_sha256": _sha({"atoms": atoms, "bonds": bonds}),
        "canonical_isomeric_smiles_sha256": chemical.digest(canonical),
        "formal_charge": Chem.GetFormalCharge(normalized),
        "system_sha256": canonical_system_sha256(ligand),
    }


def _derive_observation_with_systems(row: dict, request: dict) -> tuple[dict, object, object]:
    """Derive the exact observation and retain both parsed source systems."""
    _require(row["assigned_role"] == "development_test"
             and row["chemical_identity"] is not None
             and not row["prediction_issues"],
             "native_prepared_candidate_not_prediction_eligible")
    _require(type(request) is dict and set(request) == {
        "schema_version", "prepared_input", "evaluation", "execution", "poses"
    } and request["schema_version"] == "prepared_rigid_pose_cross_request_v1",
             "requires_existing_rigid_pose_request")
    prepared = request["prepared_input"]
    _require(type(prepared) is dict and prepared.get("schema_version") in {
        "prepared_gromacs_components_v1", "prepared_gromacs_components_v2",
        "prepared_gromacs_components_v3",
    }, "native_prepared_binding_requires_direct_gromacs_sources")
    _require(type(request["evaluation"]) is dict
             and set(request["evaluation"]) == EVALUATION_FIELDS
             and type(request["poses"]) is list and 1 <= len(request["poses"]) <= 32,
             "invalid_native_prepared_evaluation_or_poses")
    pose_ids = []
    for pose in request["poses"]:
        _transform(pose)
        pose_ids.append(pose["pose_id"])
    _require(len(set(pose_ids)) == len(pose_ids), "duplicate_native_prepared_pose_id")
    receptor, ligand, _, _, provenance = load_prepared_gromacs_components(prepared)
    _require(provenance["source_hashes_postflight_verified"] is True,
             "native_prepared_source_postflight_missing")
    identity = _ligand_identity(prepared, ligand, row["chemical_identity"])
    declarations = prepared["source_declarations"]
    target = row["target_annotation"]
    _require(target["chembl_target_id"] == row["native_metadata"]["target_chembl_id"]
             and row["assay_id"] == "chembl:assay:" + row["native_metadata"]["assay_chembl_id"],
             "native_prepared_assay_target_mismatch")
    observation = {
        "schema_version": SCHEMA,
        "record_id": row["record_id"],
        "assay_id": row["assay_id"],
        "metadata_origin_sha256": row["source_origins"]["metadata_origin"]["sha256"],
        "method_origin_sha256": row["source_origins"]["method_origin"]["sha256"],
        "target_annotation_sha256": row["target_annotation_sha256"],
        "target_chembl_id": target["chembl_target_id"],
        "prepared_input_sha256": _sha(prepared),
        "ligand": identity,
        "receptor_system_sha256": canonical_system_sha256(receptor),
        "receptor_construct_sha256": _sha(_construct(receptor)),
        "pocket_sha256": _sha({key: request["evaluation"][key]
                               for key in ("pocket_center_angstrom", "pocket_radius_angstrom")}),
        "evaluation_sha256": _sha(request["evaluation"]),
        "prepared_state_id": declarations["prepared_state_id"],
        "coordinate_frame_id": declarations["coordinate_frame_id"],
        "parameter_source_id": declarations["parameter_source_id"],
        "charge_source_id": declarations["charge_source_id"],
        "parameter_sources_sha256": _sha({key: prepared[key]["sha256"]
                                          for key in PARAMETER_KEYS}),
    }
    return observation, receptor, ligand


def derive_observation(row: dict, request: dict) -> dict:
    """Derive the exact structural observation an origin must have recorded."""
    observation, _, _ = _derive_observation_with_systems(row, request)
    return observation


def _pose_geometry_status(receptor, ligand, request: dict) -> dict:
    """Count in-pocket poses that also pass the ranking cross-distance rule."""
    evaluation = request["evaluation"]
    center = evaluation["pocket_center_angstrom"]
    radius = evaluation["pocket_radius_angstrom"]
    _require(type(center) is list and len(center) == 3,
             "invalid_native_prepared_pocket")
    try:
        center = [_number(value) for value in center]
        radius = _number(radius)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid_native_prepared_pocket") from exc
    _require(radius > 0, "invalid_native_prepared_pocket")
    inside = eligible = unavailable = 0
    receptor_coordinates = receptor.coordinates[0].detach().cpu().numpy()
    for pose in request["poses"]:
        rotation, translation = _transform(pose)
        coordinates, _ = _rigid_pose_coordinates(ligand.coordinates, rotation, translation)
        if not _inside_declared_pocket(coordinates, center, radius):
            continue
        inside += 1
        minimum = minimum_cross_distance_angstrom(
            receptor_coordinates, coordinates[0].detach().cpu().numpy())
        if minimum is None:
            unavailable += 1
        elif minimum >= HARD_OVERLAP_DISTANCE_ANGSTROM:
            eligible += 1
    return {"requested": len(request["poses"]), "inside_declared_pocket": inside,
            "rank_eligible_inside_pocket": eligible,
            "cross_distance_unavailable_inside_pocket": unavailable}


def check_source_binding(row: dict, request: dict, *, inspect_pose_geometry: bool = False) -> dict:
    """Require a source-record origin matching newly parsed prepared sources."""
    origin = row["source_origins"].get(SOURCE_FIELD)
    _require(type(origin) is dict and set(origin) == {"path", "sha256"},
             "native_prepared_source_link_missing")
    supplied = bound.bound_json(origin)
    expected, receptor, ligand = _derive_observation_with_systems(row, request)
    _require(type(supplied) is dict and supplied == expected,
             "native_prepared_source_link_mismatch")
    result = {
        "schema_version": SCHEMA,
        "origin_sha256": origin["sha256"],
        "observation_sha256": _sha(expected),
        "candidate_prepared_identity_bound": True,
        "same_prepared_assay_state_verified": False,
    }
    if inspect_pose_geometry:
        result["pose_geometry_status"] = _pose_geometry_status(receptor, ligand, request)
    return result
