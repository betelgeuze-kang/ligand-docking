"""Explicit, bounded peptide preparation for a new development profile.

RDKit's amino-acid templates supply named heavy-atom graphs, never a native
ligand pose. Heavy coordinates are retained. The selected microstate is fixed
and declared; it is not pKa prediction or a calibrated protein force field.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Mapping

import torch

from betelgeuze_engine_v2.io import parse_pdb, parse_sdf_v2000
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    canonical_system_sha256,
    require_valid_all_atom_system,
)
from .chemistry_features import (
    FEATURE_POLICY_METADATA_KEY,
    FULL_TOPOLOGY_FEATURE_POLICY_ID,
    perceive_full_topology_features,
)

RECEPTOR_PREPARATION_PROFILE_ID = "betelgeuze.named_peptide_receptor_preparation/1.0.0"
LIGAND_PREPARATION_PROFILE_ID = "betelgeuze.explicit_ligand_gasteiger_preparation/1.0.0"
PROTONATION_POLICY_ID = (
    "zwitterionic_termini_asp_glu_negative_lys_arg_positive_explicit_histidine_v1"
)
_AA = dict(
    zip(
        "ALA ARG ASN ASP CYS GLN GLU GLY ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL".split(),
        "ARNDCQEGILKMFPSTWYV",
        strict=True,
    )
)
_AA.update({"HID": "H", "HIE": "H", "HIP": "H"})
MAX_PREPARATION_ATOMS = 32_768
MAX_PREPARATION_RESIDUES = 2_048


class ChemistryPreparationError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class PreparedChemistry:
    system: AllAtomSystem
    receipt: Mapping[str, object]


def _rdkit():
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import AllChem
    except ImportError as exc:
        raise ChemistryPreparationError(
            "rdkit_unavailable", "RDKit preparation dependency is required"
        ) from exc
    return Chem, AllChem, rdBase.rdkitVersion


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _gasteiger(molecule, AllChem) -> list[float]:
    try:
        AllChem.ComputeGasteigerCharges(molecule, nIter=12, throwOnParamFailure=True)
        charges = [float(a.GetProp("_GasteigerCharge")) for a in molecule.GetAtoms()]
    except (RuntimeError, ValueError, KeyError) as exc:
        raise ChemistryPreparationError(
            "charge_assignment_failed", "Gasteiger atom typing failed"
        ) from exc
    if any(not math.isfinite(x) for x in charges):
        raise ChemistryPreparationError(
            "charge_assignment_failed", "nonfinite Gasteiger charge"
        )
    residual = sum(a.GetFormalCharge() for a in molecule.GetAtoms()) - math.fsum(
        charges
    )
    if abs(residual) > 1e-6:
        raise ChemistryPreparationError(
            "charge_conservation_failed", "charge residual exceeds numerical tolerance"
        )
    # No distinguished first/largest atom: permutation cannot move a correction.
    return [q + residual / len(charges) for q in charges]


def _hydrogen_positions(template, parent: int, count: int, Chem) -> list[list[float]]:
    """Use a named two-hop heavy frame, never the input world's axes.

    RDKit's one-neighbour fallback may choose fixed axes. Executing it on a
    small graph in this intrinsic frame makes that declared torsion choice
    rigid-transform equivariant. No frame is invented for collinear geometry.
    """
    neighbors = sorted(
        a.GetIdx() for a in template.GetAtomWithIdx(parent).GetNeighbors()
    )
    local = {parent, *neighbors}
    for index in neighbors:
        local.update(a.GetIdx() for a in template.GetAtomWithIdx(index).GetNeighbors())
    conformer = template.GetConformer()

    def position(i):
        return torch.tensor(list(conformer.GetAtomPosition(i)), dtype=torch.float64)

    origin = position(parent)
    if not neighbors:
        raise ChemistryPreparationError(
            "hydrogen_local_frame_underdetermined", "H parent has no heavy anchor"
        )
    first = position(neighbors[0]) - origin
    norm = float(torch.linalg.vector_norm(first))
    if norm < 1e-6:
        raise ChemistryPreparationError(
            "hydrogen_local_frame_degenerate", "coincident heavy anchor"
        )
    first /= norm
    second = None
    for index in sorted(local - {parent, neighbors[0]}):
        vector = position(index) - origin
        vector_norm = float(torch.linalg.vector_norm(vector))
        orthogonal = vector - torch.dot(vector, first) * first
        orthogonal_norm = float(torch.linalg.vector_norm(orthogonal))
        if vector_norm > 1e-6 and orthogonal_norm > 0.1 * vector_norm:
            second = orthogonal / orthogonal_norm
            break
    if second is None:
        raise ChemistryPreparationError(
            "hydrogen_local_frame_underdetermined",
            "two-hop heavy anchors are collinear or ill-conditioned",
        )
    frame = torch.stack((first, second, torch.linalg.cross(first, second)), dim=1)
    builder = Chem.RWMol()
    local_indices = {}
    for index in sorted(local):
        atom = Chem.Atom(template.GetAtomWithIdx(index))
        atom.SetNoImplicit(True)
        atom.SetNumExplicitHs(count if index == parent else 0)
        local_indices[index] = builder.AddAtom(atom)
    for first_index in sorted(local):
        for neighbor in template.GetAtomWithIdx(first_index).GetNeighbors():
            second_index = neighbor.GetIdx()
            if second_index in local and first_index < second_index:
                bond = template.GetBondBetweenAtoms(first_index, second_index)
                builder.AddBond(
                    local_indices[first_index],
                    local_indices[second_index],
                    bond.GetBondType(),
                )
    molecule = builder.GetMol()
    molecule.UpdatePropertyCache(strict=False)
    local_conformer = Chem.Conformer(len(local))
    for index, local_index in local_indices.items():
        local_conformer.SetAtomPosition(
            local_index, ((position(index) - origin) @ frame).tolist()
        )
    molecule.AddConformer(local_conformer)
    expanded = Chem.AddHs(molecule, addCoords=True, onlyOnAtoms=[local_indices[parent]])
    positions = [
        (
            torch.tensor(
                list(expanded.GetConformer().GetAtomPosition(i)), dtype=torch.float64
            )
            @ frame.T
            + origin
        ).tolist()
        for i in range(len(local), expanded.GetNumAtoms())
    ]
    if len(positions) != count or any(
        not math.isfinite(value) for row in positions for value in row
    ):
        raise ChemistryPreparationError(
            "hydrogen_geometry_failed", "bounded local H construction failed"
        )
    return positions


def _finish(
    source: AllAtomSystem,
    atoms,
    bonds,
    coordinates,
    *,
    profile: str,
    version: str,
    added_hydrogens: int,
) -> PreparedChemistry:
    residue_indices = defaultdict(list)
    for atom in atoms:
        residue_indices[atom.residue_index].append(atom.index)
    metadata = {
        "preparation_profile_id": profile,
        FEATURE_POLICY_METADATA_KEY: FULL_TOPOLOGY_FEATURE_POLICY_ID,
        "rdkit_version": version,
        "charge_method": "rdkit_gasteiger_12_iterations_explicit_atoms",
        "charge_calibrated": False,
        "hydrogen_geometry_policy": (
            "named_two_hop_heavy_frame_rdkit_v1"
            if added_hydrogens
            else "source_explicit_hydrogens_preserved"
        ),
        "protonation_policy_id": PROTONATION_POLICY_ID
        if profile == RECEPTOR_PREPARATION_PROFILE_ID
        else "source_declared",
        "chemistry_feature_readiness": "explicit_graph_and_hydrogens_development_only",
    }
    system = replace(
        source,
        atoms=tuple(atoms),
        bonds=tuple(bonds),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        residues=tuple(
            replace(r, atom_indices=tuple(residue_indices[r.index]))
            for r in source.residues
        ),
        metadata={**dict(source.metadata), **metadata},
        provenance=replace(
            source.provenance,
            operations=(*source.provenance.operations, profile),
            parent_sha256=(canonical_system_sha256(source),),
            transformation_chain_verified=False,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata={**dict(source.provenance.metadata), **metadata},
        ),
    )
    require_valid_all_atom_system(system)
    features = perceive_full_topology_features(system)
    receipt = {
        "schema_id": "betelgeuze.explicit_chemistry_preparation_receipt/1.0.0",
        **metadata,
        "source_system_sha256": canonical_system_sha256(source),
        "prepared_system_sha256": canonical_system_sha256(system),
        "heavy_coordinates_preserved": True,
        "source_atom_count": source.atom_count,
        "prepared_atom_count": system.atom_count,
        "added_hydrogen_count": added_hydrogens,
        "bond_count": len(system.bonds),
        "donor_pair_count": len(features.donor_pairs),
        "acceptor_count": len(features.acceptors),
        "formal_charge_total": sum(a.formal_charge for a in atoms),
        "partial_charge_total": math.fsum(a.partial_charge_e for a in atoms),
        "chemistry_validated": False,
        "scientifically_validated": False,
        "product_qualified": False,
    }
    receipt["receipt_sha256"] = _digest(receipt)
    return PreparedChemistry(system, receipt)


def prepare_receptor_v1(
    pdb_payload: str | bytes, *, source_id: str = "prepared-receptor"
) -> PreparedChemistry:
    """Prepare complete standard peptides under the explicitly declared policy.

    Requires continuous numbered chains and terminal OXT. HIS must be renamed
    HID/HIE/HIP deliberately. Waters, ions, cofactors, modified residues,
    disulfides/crosslinks, missing heavy atoms and partial H sets are rejected.
    Either zero H atoms or a complete H set for this microstate is supported.
    """
    Chem, AllChem, version = _rdkit()
    try:
        source = parse_pdb(
            pdb_payload,
            source_id=source_id,
            dtype=torch.float64,
            connectivity_policy="reject_unrepresented",
            unit_cell_policy="ignore",
        )
    except ValueError as exc:
        raise ChemistryPreparationError("receptor_parse_unsupported", str(exc)) from exc
    if (
        source.atom_count > MAX_PREPARATION_ATOMS
        or len(source.residues) > MAX_PREPARATION_RESIDUES
    ):
        raise ChemistryPreparationError(
            "preparation_capacity_exceeded", "peptide preparation bound exceeded"
        )
    for residue in source.residues:
        if residue.hetero or residue.entity_type != "polymer":
            raise ChemistryPreparationError(
                "unsupported_nonpolymer",
                f"water/ion/cofactor {residue.name} requires another preparation profile",
            )
        if residue.name == "HIS":
            raise ChemistryPreparationError(
                "histidine_microstate_required", "declare HID, HIE or HIP explicitly"
            )
        if residue.name not in _AA or residue.insertion_code:
            raise ChemistryPreparationError(
                "unsupported_residue",
                f"residue {residue.name} or insertion code outside profile",
            )
    coords = source.coordinates[0].tolist()
    atoms = list(source.atoms)
    bonds_by_pair = {}
    has_source_hydrogens = any(a.element == "H" for a in source.atoms)
    for chain in source.chains:
        residues = sorted(
            (source.residues[i] for i in chain.residue_indices),
            key=lambda r: r.sequence_number,
        )
        if any(
            b.sequence_number != a.sequence_number + 1
            for a, b in zip(residues, residues[1:])
        ):
            raise ChemistryPreparationError(
                "chain_gap_unsupported", "continuous residue numbering is required"
            )
        template = Chem.MolFromSequence("".join(_AA[r.name] for r in residues))
        if template is None:
            raise ChemistryPreparationError(
                "residue_template_unavailable", "RDKit peptide template creation failed"
            )
        named = {}
        for atom in template.GetAtoms():
            info = atom.GetPDBResidueInfo()
            named[(info.GetResidueNumber() - 1, info.GetName().strip())] = atom.GetIdx()
        # Formal states are chemically named template states, never index[0]
        # projections of a proxy charge array.
        template.GetAtomWithIdx(named[(0, "N")]).SetFormalCharge(1)
        template.GetAtomWithIdx(named[(len(residues) - 1, "OXT")]).SetFormalCharge(-1)
        for ri, residue in enumerate(residues):
            charged_name = {
                "ASP": ("OD2", -1),
                "GLU": ("OE2", -1),
                "LYS": ("NZ", 1),
                "ARG": ("NH1", 1),
            }.get(residue.name)
            if charged_name:
                name, charge = charged_name
                template.GetAtomWithIdx(named[(ri, name)]).SetFormalCharge(charge)
            if residue.name in {"HID", "HIE", "HIP"}:
                for name in ("ND1", "NE2"):
                    atom = template.GetAtomWithIdx(named[(ri, name)])
                    protonated = residue.name == "HIP" or (name == "ND1") == (
                        residue.name == "HID"
                    )
                    atom.SetNumExplicitHs(int(protonated))
                    atom.SetNoImplicit(True)
                    atom.SetFormalCharge(int(residue.name == "HIP" and name == "ND1"))
        try:
            Chem.SanitizeMol(template)
        except ValueError as exc:
            raise ChemistryPreparationError(
                "template_microstate_unsupported", str(exc)
            ) from exc
        mapping = {}
        for ri, residue in enumerate(residues):
            heavy = {}
            for index in residue.atom_indices:
                atom = source.atoms[index]
                if atom.element != "H":
                    if atom.name in heavy:
                        raise ChemistryPreparationError(
                            "duplicate_atom_name", f"{residue.name}:{atom.name}"
                        )
                    heavy[atom.name] = index
            expected = {name for (row, name) in named if row == ri}
            if set(heavy) != expected:
                raise ChemistryPreparationError(
                    "incomplete_heavy_atoms",
                    f"{residue.name} {residue.sequence_number}: missing={sorted(expected - set(heavy))}; extra={sorted(set(heavy) - expected)}",
                )
            for name, index in heavy.items():
                ti = named[(ri, name)]
                atom = template.GetAtomWithIdx(ti)
                original = source.atoms[index]
                if original.element != atom.GetSymbol():
                    raise ChemistryPreparationError(
                        "atom_element_mismatch", f"{residue.name}:{name}"
                    )
                if (
                    original.formal_charge
                    and original.formal_charge != atom.GetFormalCharge()
                ):
                    raise ChemistryPreparationError(
                        "source_microstate_conflict",
                        f"declared charge of {residue.name}:{name} conflicts with profile",
                    )
                mapping[ti] = index
        conformer = Chem.Conformer(template.GetNumAtoms())
        for ti, si in mapping.items():
            conformer.SetAtomPosition(ti, coords[si])
        template.AddConformer(conformer)
        for bond in template.GetBonds():
            first, second = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            distance = math.dist(coords[mapping[first]], coords[mapping[second]])
            if not 0.9 <= distance <= 2.2:
                raise ChemistryPreparationError(
                    "template_bond_geometry_invalid",
                    "declared peptide graph is incompatible with heavy coordinates",
                )
        observed_stereo = Chem.Mol(template)
        Chem.AssignAtomChiralTagsFromStructure(
            observed_stereo, replaceExistingTags=True
        )
        for atom in template.GetAtoms():
            if (
                atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED
                and observed_stereo.GetAtomWithIdx(atom.GetIdx()).GetChiralTag()
                != atom.GetChiralTag()
            ):
                raise ChemistryPreparationError(
                    "unsupported_residue_stereochemistry",
                    "coordinates do not match the L-amino-acid template",
                )
        expanded = Chem.AddHs(template, addCoords=False, addResidueInfo=True)
        hydrogen_slots = defaultdict(list)
        for atom in expanded.GetAtoms():
            if atom.GetAtomicNum() == 1:
                hydrogen_slots[atom.GetNeighbors()[0].GetIdx()].append(atom.GetIdx())
        assigned = Counter()
        for ri, residue in enumerate(residues):
            source_hs = sorted(
                (i for i in residue.atom_indices if source.atoms[i].element == "H"),
                key=lambda i: source.atoms[i].name,
            )
            if len({source.atoms[i].name for i in source_hs}) != len(source_hs):
                raise ChemistryPreparationError(
                    "duplicate_atom_name",
                    "hydrogen names must be unique within a residue",
                )
            parents = [
                ti for (row, _), ti in named.items() if row == ri and hydrogen_slots[ti]
            ]
            for hi in source_hs:
                candidates = [
                    ti
                    for ti in parents
                    if 0.6
                    <= math.dist(coords[hi], coords[mapping[ti]])
                    <= (1.6 if expanded.GetAtomWithIdx(ti).GetSymbol() == "S" else 1.25)
                ]
                if len(candidates) != 1:
                    raise ChemistryPreparationError(
                        "hydrogen_parent_ambiguous",
                        f"{residue.name}:{source.atoms[hi].name}",
                    )
                ti = candidates[0]
                if assigned[ti] >= len(hydrogen_slots[ti]):
                    raise ChemistryPreparationError(
                        "hydrogen_microstate_conflict",
                        "too many H atoms for the declared microstate",
                    )
                expanded_index = hydrogen_slots[ti][assigned[ti]]
                mapping[expanded_index] = hi
                expanded.GetConformer().SetAtomPosition(expanded_index, coords[hi])
                assigned[ti] += 1
        if has_source_hydrogens and any(
            assigned[ti] != len(slots) for ti, slots in hydrogen_slots.items()
        ):
            raise ChemistryPreparationError(
                "partial_hydrogen_set_unsupported",
                "supply zero H atoms or a complete H set for the declared microstate",
            )
        if not has_source_hydrogens:
            for parent, slots in hydrogen_slots.items():
                for hi, position in zip(
                    slots,
                    _hydrogen_positions(template, parent, len(slots), Chem),
                    strict=True,
                ):
                    expanded.GetConformer().SetAtomPosition(hi, position)
        charges = _gasteiger(expanded, AllChem)
        for atom in expanded.GetAtoms():
            ti = atom.GetIdx()
            if ti not in mapping:
                parent = atom.GetNeighbors()[0].GetIdx()
                original_parent = source.atoms[mapping[parent]]
                index = len(atoms)
                mapping[ti] = index
                parent_suffix = original_parent.name[1:] or original_parent.name
                name = f"H{parent_suffix}{hydrogen_slots[parent].index(ti) + 1}"
                atoms.append(
                    Atom(
                        index=index,
                        name=name,
                        element="H",
                        atomic_number=1,
                        residue_index=original_parent.residue_index,
                    )
                )
                point = expanded.GetConformer().GetAtomPosition(ti)
                coords.append([point.x, point.y, point.z])
            index = mapping[ti]
            atoms[index] = replace(
                atoms[index],
                formal_charge=atom.GetFormalCharge(),
                aromatic=atom.GetIsAromatic(),
                partial_charge_e=charges[ti],
            )
        for bond in expanded.GetBonds():
            pair = tuple(
                sorted((mapping[bond.GetBeginAtomIdx()], mapping[bond.GetEndAtomIdx()]))
            )
            bonds_by_pair[pair] = (bond.GetBondTypeAsDouble(), bond.GetIsAromatic())
    if len(atoms) > MAX_PREPARATION_ATOMS:
        raise ChemistryPreparationError(
            "preparation_capacity_exceeded", "hydrogen addition exceeds atom bound"
        )
    if any((b.atom_i, b.atom_j) not in bonds_by_pair for b in source.bonds):
        raise ChemistryPreparationError(
            "unsupported_crosslink",
            "source CONECT conflicts with named peptide topology",
        )
    bonds = [
        Bond(
            index=i,
            atom_i=pair[0],
            atom_j=pair[1],
            order=order,
            aromatic=aromatic,
            source=RECEPTOR_PREPARATION_PROFILE_ID,
        )
        for i, (pair, (order, aromatic)) in enumerate(sorted(bonds_by_pair.items()))
    ]
    return _finish(
        source,
        atoms,
        bonds,
        coords,
        profile=RECEPTOR_PREPARATION_PROFILE_ID,
        version=version,
        added_hydrogens=len(atoms) - source.atom_count,
    )


def prepare_ligand_v1(
    sdf_payload: str | bytes, *, source_id: str = "prepared-ligand"
) -> PreparedChemistry:
    """Retain a fully explicit ligand graph/microstate and assign finite charges."""
    Chem, AllChem, version = _rdkit()
    try:
        text = (
            sdf_payload.decode("ascii")
            if isinstance(sdf_payload, bytes)
            else sdf_payload
        )
        source = parse_sdf_v2000(text, source_id=source_id, dtype=torch.float64)
        molecule = Chem.MolFromMolBlock(
            text.split("$$$$", 1)[0], removeHs=False, sanitize=True
        )
    except ValueError as exc:
        raise ChemistryPreparationError("ligand_parse_unsupported", str(exc)) from exc
    if molecule is None or molecule.GetNumAtoms() != source.atom_count:
        raise ChemistryPreparationError(
            "ligand_parse_unsupported", "RDKit/canonical atom mapping differs"
        )
    if source.atom_count > 512:
        raise ChemistryPreparationError(
            "preparation_capacity_exceeded", "ligand atom bound exceeded"
        )
    if any(a.GetNumImplicitHs() or a.GetNumExplicitHs() for a in molecule.GetAtoms()):
        raise ChemistryPreparationError(
            "ligand_explicit_hydrogens_required",
            "materialize all ligand H atoms before this profile",
        )
    if any(
        a.GetAtomicNum() not in {1, 6, 7, 8, 9, 15, 16, 17, 35, 53}
        for a in molecule.GetAtoms()
    ):
        raise ChemistryPreparationError(
            "unsupported_ligand_element",
            "metal/cofactor chemistry is outside the profile",
        )
    if any(
        (a.GetAtomicNum(), a.GetFormalCharge()) != (s.atomic_number, s.formal_charge)
        for a, s in zip(molecule.GetAtoms(), source.atoms, strict=True)
    ):
        raise ChemistryPreparationError(
            "ligand_atom_mapping_mismatch", "source atom identities/microstate differ"
        )
    charges = _gasteiger(molecule, AllChem)
    atoms = [
        replace(
            atom,
            partial_charge_e=charges[i],
            aromatic=molecule.GetAtomWithIdx(i).GetIsAromatic(),
        )
        for i, atom in enumerate(source.atoms)
    ]
    return _finish(
        source,
        atoms,
        source.bonds,
        source.coordinates[0].tolist(),
        profile=LIGAND_PREPARATION_PROFILE_ID,
        version=version,
        added_hydrogens=0,
    )
