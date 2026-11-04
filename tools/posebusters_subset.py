"""Restricted exact induced-subgraph construction for pinned PB volume checks.

Retaining atoms and bonds directly avoids RDKit 2022.09.5's repeated
index/coordinate/property passes on every ``RemoveAtom``. Its batch-edit
commit still performs those same removals; changing only to batch editing
does not remove that work. No distance, cutoff, or shape arithmetic changes.

Only ordinary Mol objects without molecule-level persistent properties,
conformer properties, queries, non-tetrahedral atom chirality, bond stereo
references, or stereo/substance groups use the fast path. Everything outside
that contract is passed unchanged to the caller-supplied frozen
``volume_overlap._filter_by_mask``. RDKit's own
AddAtom and ReplaceBond operations deep-copy typed properties and atom/PDB
metadata. Original atom and bond order, atom chiral tags, bond directions and
attributes, conformer IDs/order/3D flags, and double coordinates are retained.
Clearing computed properties once reproduces the deletion helper's final
state. No sanitization, property-cache update, or coordinate conversion occurs.

The source-pinned caller owns package/source admission and input immutability.
This object has no molecule cache and must not be installed as a global patch.
Source basis: RDKit Release_2022_09_5, Code/GraphMol/{RWMol,ROMol,Atom,Bond}.cpp
and Code/GraphMol/Wrap/{Mol,Conformer}.cpp. Runtime equivalence is a separate
mandatory molecular test, not established by these source observations alone.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable


IMPLEMENTATION_ID = "betelgeuze.posebusters_induced_subset/2.0.0"
FROZEN_RDKIT_VERSION = "2022.09.5"


class SubsetOptimizationError(RuntimeError):
    """The explicitly selected subset implementation cannot be admitted."""


class ExactSubsetFilter:
    """A per-evaluator callable with bounded routing counters, not cached Mols.

    ``reference_filter`` must be the source-pinned upstream helper. Fallback is
    chosen only by explicit feature guards. An unexpected fast-path exception
    is propagated, never hidden by retrying the original algorithm.
    """

    def __init__(self, *, Chem: Any, reference_filter: Callable[[Any, Any], Any]):
        if not callable(reference_filter):
            raise TypeError("reference_filter must be callable")
        observed_version = getattr(getattr(Chem, "rdBase", None), "rdkitVersion", None)
        if observed_version != FROZEN_RDKIT_VERSION:
            raise SubsetOptimizationError(
                f"subset implementation requires RDKit {FROZEN_RDKIT_VERSION}: {observed_version!r}"
            )
        # Imports stay lazy so byte/JSON-only tools do not acquire chemistry
        # dependencies merely by importing this module.
        import numpy as np

        self._Chem = Chem
        self._np = np
        self._reference_filter = reference_filter
        self._counts: Counter[str] = Counter()
        self._fallback_reasons: Counter[str] = Counter()

    def _fallback(self, reason: str, mol: Any, mask: Any) -> Any:
        self._counts["fallback_calls"] += 1
        self._fallback_reasons[reason] += 1
        try:
            return self._reference_filter(mol, mask)
        except Exception:
            self._counts["fallback_errors"] += 1
            raise

    def _unsupported_reason(self, mol: Any) -> str | None:
        if len(mol.GetStereoGroups()) != 0:
            return "stereo_groups"
        if len(self._Chem.GetMolSubstanceGroups(mol)) != 0:
            return "substance_groups"
        # Reconstructing arbitrary typed RDProps via GetPropsAsDict can change
        # unsigned/vector property types. Do not attempt that conversion.
        if len(mol.GetPropNames(includePrivate=True, includeComputed=False)) != 0:
            return "molecule_properties"
        for atom in mol.GetAtoms():
            if atom.HasQuery():
                return "query_atom"
            if atom.GetChiralTag() not in (
                self._Chem.ChiralType.CHI_UNSPECIFIED,
                self._Chem.ChiralType.CHI_TETRAHEDRAL_CW,
                self._Chem.ChiralType.CHI_TETRAHEDRAL_CCW,
            ):
                return "atom_chirality"
        for bond in mol.GetBonds():
            if bond.HasQuery():
                return "query_bond"
            # Original deletions can clear or renumber stereo-atom references.
            # Copying those indices is not sufficient, so delegate the whole
            # molecule even when a particular mask would remove the bond.
            if bond.GetStereo() != self._Chem.BondStereo.STEREONONE:
                return "bond_stereo"
            if len(bond.GetStereoAtoms()) != 0:
                return "bond_stereo_atoms"
        for conf in mol.GetConformers():
            if conf.GetNumAtoms() != mol.GetNumAtoms():
                return "conformer_size"
            if len(conf.GetPropNames(includePrivate=True, includeComputed=True)) != 0:
                return "conformer_properties"
        return None

    def __call__(self, mol: Any, mask: Any) -> Any:
        self._counts["calls"] += 1
        # RWMol may carry an in-progress batch edit, and subclass behavior is
        # outside this narrow contract. The original helper remains available.
        if type(mol) is not self._Chem.Mol:
            return self._fallback("molecule_type", mol, mask)
        if (
            type(mask) is not self._np.ndarray
            or mask.ndim != 1
            or mask.dtype != self._np.dtype(bool)
            or len(mask) != mol.GetNumAtoms()
        ):
            return self._fallback("unsupported_mask", mol, mask)
        retained = self._np.flatnonzero(mask).tolist()
        if len(retained) == mol.GetNumAtoms():
            # Upstream returns the identical object when no atom is removed.
            self._counts["identity_calls"] += 1
            return mol
        reason = self._unsupported_reason(mol)
        if reason is not None:
            return self._fallback(reason, mol, mask)

        try:
            result = self._build_induced_subset(mol, retained)
        except Exception:
            self._counts["fast_path_errors"] += 1
            raise
        self._counts["fast_path_calls"] += 1
        self._counts["source_atoms_fast_path"] += mol.GetNumAtoms()
        self._counts["retained_atoms_fast_path"] += len(retained)
        self._counts["removed_atoms_fast_path"] += mol.GetNumAtoms() - len(retained)
        self._counts["bonded_fast_path_calls" if mol.GetNumBonds() else "bondless_fast_path_calls"] += 1
        self._counts["source_bonds_fast_path"] += mol.GetNumBonds()
        self._counts["retained_bonds_fast_path"] += result.GetNumBonds()
        self._counts["removed_bonds_fast_path"] += mol.GetNumBonds() - result.GetNumBonds()
        return result

    def _build_induced_subset(self, mol: Any, retained: list[int]) -> Any:
        Chem = self._Chem
        result = Chem.RWMol()
        new_indices = {old_index: new_index for new_index, old_index in enumerate(retained)}
        for old_index in retained:
            # The pinned Python AddAtom wrapper calls addAtom(atom, true,
            # false), which invokes the virtual Atom::copy. It deep-copies
            # RDProps, PDB/monomer info and cached atom attributes.
            result.AddAtom(mol.GetAtomWithIdx(old_index))
        for bond in mol.GetBonds():
            begin = new_indices.get(bond.GetBeginAtomIdx())
            end = new_indices.get(bond.GetEndAtomIdx())
            if begin is None or end is None:
                continue
            # Keep original edge insertion order and endpoint orientation.
            # An AROMATIC placeholder would modify copied atom flags, so use
            # UNSPECIFIED. ReplaceBond invokes virtual Bond::copy, preserving
            # every typed RDProp/attribute and replacing only endpoint/index
            # ownership with the placeholder's values. Do not copy properties
            # through Python dictionaries: that can coerce native types.
            bond_index = result.AddBond(begin, end, Chem.BondType.UNSPECIFIED) - 1
            result.ReplaceBond(bond_index, bond, preserveProps=False, keepSGroups=True)
        for original in mol.GetConformers():
            conf = Chem.Conformer(len(retained))
            conf.SetId(original.GetId())
            conf.Set3D(original.Is3D())
            for new_index, old_index in enumerate(retained):
                # Pass the Point3D directly; avoid array casts/float32 or any
                # arithmetic, including addition that could lose signed zero.
                conf.SetAtomPosition(new_index, original.GetAtomPosition(old_index))
            result.AddConformer(conf, assignId=False)
        # The reference performs this for every removed atom. Atom chirality,
        # explicit H counts, cached valences, bond direction/aromatic/conjugated
        # flags are not recalculated by that deletion path; copies retain them.
        # Admitted graphs have no stereo/group index references to rewrite.
        result.ClearComputedProps(includeRings=True)
        return Chem.Mol(result)

    def document(self) -> dict[str, Any]:
        """Return JSON-safe counters without retaining input-specific data."""
        keys = (
            "calls", "identity_calls", "fast_path_calls", "fallback_calls",
            "fast_path_errors", "fallback_errors", "source_atoms_fast_path",
            "retained_atoms_fast_path", "removed_atoms_fast_path",
            "bonded_fast_path_calls", "bondless_fast_path_calls",
            "source_bonds_fast_path", "retained_bonds_fast_path", "removed_bonds_fast_path",
        )
        return {
            "implementation_id": IMPLEMENTATION_ID,
            "rdkit_version": FROZEN_RDKIT_VERSION,
            **{key: self._counts[key] for key in keys},
            "fallback_reasons": dict(sorted(self._fallback_reasons.items())),
        }
