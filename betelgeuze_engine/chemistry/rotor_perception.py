"""Chemistry-aware ligand rotor and ring-rigid-component perception (P1-2, P1-3).

A plain rotatable-bond count treats every acyclic single bond as a free torsion.
That is wrong in two directions at once:

- ring bonds are not independent torsions, so a ring-containing ligand sampled
  bond-by-bond produces broken geometry;
- amide/urea/carbamate/sulfonamide bonds and conjugated single bonds are not
  free either. They are restrained to a small number of near-planar states.

This module produces the perception layer the docking search needs before any
ring-closure sampling exists:

- each ring system becomes one **rigid component** (fused rings stay together);
- each acyclic single bond is classified into a chemistry-aware rotor class
  with a torsion periodicity and a discrete preferred-state count;
- macrocycles are routed to a separate **unsupported** lane instead of being
  silently sampled as if they were rigid.

RDKit is required for real perception. Without it the result is explicitly
``unsupported`` rather than a fabricated rotor list.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    Chem = None

ROTOR_PERCEPTION_SCHEMA_VERSION = "ligand_rotor_perception_v1"

#: A ring of this size or larger is treated as a macrocycle and routed out of
#: the supported lane: its conformation needs ring-closure sampling, which this
#: perception layer deliberately does not attempt.
MACROCYCLE_MIN_RING_SIZE = 8

STATUS_SUPPORTED = "rotor_perception_supported"
STATUS_UNSUPPORTED_MACROCYCLE = "unsupported_macrocycle_lane"
STATUS_UNSUPPORTED_NO_RDKIT = "unsupported_rdkit_unavailable"
STATUS_UNSUPPORTED_INVALID = "unsupported_invalid_smiles"

#: Rotor classes, ordered from most free to fully locked.
ROTOR_CLASS_FREE = "free_rotor"
ROTOR_CLASS_SP3_SP3 = "sp3_sp3_rotor"
ROTOR_CLASS_EXOCYCLIC_RING = "exocyclic_ring_rotor"
ROTOR_CLASS_CONJUGATED = "conjugated_hindered_rotor"
ROTOR_CLASS_RING_RING = "ring_ring_rotor"
ROTOR_CLASS_AMIDE = "amide_restrained_rotor"
ROTOR_CLASS_UREA = "urea_restrained_rotor"
ROTOR_CLASS_CARBAMATE = "carbamate_restrained_rotor"
ROTOR_CLASS_SULFONAMIDE = "sulfonamide_restrained_rotor"
ROTOR_CLASS_STEREO_LOCKED = "stereo_locked_bond"
ROTOR_CLASS_RING_BOND = "ring_rigid_bond"
ROTOR_CLASS_TERMINAL = "terminal_no_torsion"

RESTRAINED_ROTOR_CLASSES = (
    ROTOR_CLASS_AMIDE,
    ROTOR_CLASS_UREA,
    ROTOR_CLASS_CARBAMATE,
    ROTOR_CLASS_SULFONAMIDE,
)

#: SMARTS for the restrained linkages, most specific first. Urea and carbamate
#: both contain an amide substructure, so ordering decides the reported class.
_RESTRAINED_SMARTS: tuple[tuple[str, str], ...] = (
    (ROTOR_CLASS_UREA, "[NX3][CX3](=[OX1])[NX3]"),
    (ROTOR_CLASS_CARBAMATE, "[OX2][CX3](=[OX1])[NX3]"),
    (ROTOR_CLASS_SULFONAMIDE, "[NX3][SX4](=[OX1])(=[OX1])"),
    (ROTOR_CLASS_AMIDE, "[NX3][CX3](=[OX1])"),
)

#: Discrete preferred torsion states per class. A restrained linkage is not a
#: free torsion: it is a small set of near-planar states.
_PREFERRED_STATE_COUNT = {
    ROTOR_CLASS_FREE: 6,
    ROTOR_CLASS_SP3_SP3: 3,
    ROTOR_CLASS_EXOCYCLIC_RING: 3,
    ROTOR_CLASS_RING_RING: 2,
    ROTOR_CLASS_CONJUGATED: 2,
    ROTOR_CLASS_AMIDE: 2,
    ROTOR_CLASS_UREA: 2,
    ROTOR_CLASS_CARBAMATE: 2,
    ROTOR_CLASS_SULFONAMIDE: 3,
}

#: Torsion periodicity used by the sampler for each class.
_PERIODICITY = {
    ROTOR_CLASS_FREE: 6,
    ROTOR_CLASS_SP3_SP3: 3,
    ROTOR_CLASS_EXOCYCLIC_RING: 3,
    ROTOR_CLASS_RING_RING: 2,
    ROTOR_CLASS_CONJUGATED: 2,
    ROTOR_CLASS_AMIDE: 2,
    ROTOR_CLASS_UREA: 2,
    ROTOR_CLASS_CARBAMATE: 2,
    ROTOR_CLASS_SULFONAMIDE: 3,
}

CLAIM_BOUNDARY = (
    "Chemistry-aware rotor and ring-rigid-component perception only. Ring systems are treated as rigid "
    "components and macrocycles are routed to an unsupported lane; this is not ring-closure sampling, a "
    "calibrated torsion force field, or a benchmarked conformer-accuracy claim."
)


@dataclass(frozen=True)
class PerceivedRotor:
    """One acyclic single bond classified with chemistry-aware restraints."""

    bond_idx: int
    begin_atom_idx: int
    end_atom_idx: int
    rotor_class: str
    periodicity: int
    preferred_state_count: int
    conjugated: bool
    exocyclic_ring_bond: bool
    ring_ring_bond: bool
    restrained: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RigidComponent:
    """One ring system treated as a single rigid body."""

    component_index: int
    atom_indices: tuple[int, ...]
    ring_count: int
    ring_sizes: tuple[int, ...]
    aromatic: bool
    macrocyclic: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RotorPerception:
    """Perception result for one ligand."""

    smiles: str
    status: str
    source: str
    rotors: tuple[PerceivedRotor, ...] = ()
    rigid_components: tuple[RigidComponent, ...] = ()
    macrocycle_ring_sizes: tuple[int, ...] = ()
    stereo_locked_bond_count: int = 0
    unsupported_reason: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def supported(self) -> bool:
        return self.status == STATUS_SUPPORTED

    @property
    def rotor_count(self) -> int:
        return len(self.rotors)

    @property
    def restrained_rotor_count(self) -> int:
        return sum(1 for rotor in self.rotors if rotor.restrained)

    @property
    def free_rotor_count(self) -> int:
        return sum(1 for rotor in self.rotors if not rotor.restrained and not rotor.conjugated)

    @property
    def effective_torsion_state_count(self) -> int:
        """Product of per-rotor preferred states, i.e. the discrete search size."""

        total = 1
        for rotor in self.rotors:
            total *= max(int(rotor.preferred_state_count), 1)
        return int(total)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ROTOR_PERCEPTION_SCHEMA_VERSION,
            "smiles": self.smiles,
            "status": self.status,
            "source": self.source,
            "supported": self.supported,
            "rotor_count": self.rotor_count,
            "restrained_rotor_count": self.restrained_rotor_count,
            "free_rotor_count": self.free_rotor_count,
            "conjugated_rotor_count": sum(1 for rotor in self.rotors if rotor.conjugated),
            "exocyclic_ring_rotor_count": sum(1 for rotor in self.rotors if rotor.exocyclic_ring_bond),
            "ring_ring_rotor_count": sum(1 for rotor in self.rotors if rotor.ring_ring_bond),
            "stereo_locked_bond_count": int(self.stereo_locked_bond_count),
            "rigid_component_count": len(self.rigid_components),
            "ring_atom_count": sum(len(component.atom_indices) for component in self.rigid_components),
            "macrocycle_ring_sizes": list(self.macrocycle_ring_sizes),
            "macrocycle_present": bool(self.macrocycle_ring_sizes),
            "effective_torsion_state_count": self.effective_torsion_state_count,
            "rotors": [rotor.to_dict() for rotor in self.rotors],
            "rigid_components": [component.to_dict() for component in self.rigid_components],
            "unsupported_reason": self.unsupported_reason,
            "blockers": list(self.blockers),
            "macrocycle_min_ring_size": int(MACROCYCLE_MIN_RING_SIZE),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def _unsupported(
    smiles: str,
    *,
    status: str,
    source: str,
    reason: str,
    macrocycle_ring_sizes: tuple[int, ...] = (),
    rigid_components: tuple[RigidComponent, ...] = (),
) -> RotorPerception:
    return RotorPerception(
        smiles=smiles,
        status=status,
        source=source,
        rigid_components=rigid_components,
        macrocycle_ring_sizes=macrocycle_ring_sizes,
        unsupported_reason=reason,
        blockers=(reason,),
    )


def _fused_ring_components(mol: Any) -> tuple[RigidComponent, ...]:
    """Group rings that share atoms into single rigid components.

    Fused and spiro systems must move as one body; treating each SSSR ring as an
    independent unit would let a fused bicyclic hinge at the fusion bond.
    """

    rings = [tuple(int(idx) for idx in ring) for ring in mol.GetRingInfo().AtomRings()]
    if not rings:
        return ()
    groups: list[dict[str, Any]] = []
    for ring in rings:
        ring_atoms = set(ring)
        merged: dict[str, Any] = {"atoms": ring_atoms, "rings": [ring]}
        remaining: list[dict[str, Any]] = []
        for group in groups:
            if group["atoms"] & merged["atoms"]:
                merged["atoms"] = merged["atoms"] | group["atoms"]
                merged["rings"] = merged["rings"] + group["rings"]
            else:
                remaining.append(group)
        remaining.append(merged)
        groups = remaining
    components: list[RigidComponent] = []
    for index, group in enumerate(sorted(groups, key=lambda item: min(item["atoms"]))):
        atoms = tuple(sorted(int(idx) for idx in group["atoms"]))
        ring_sizes = tuple(sorted(len(ring) for ring in group["rings"]))
        aromatic = all(mol.GetAtomWithIdx(int(idx)).GetIsAromatic() for idx in atoms)
        components.append(
            RigidComponent(
                component_index=index,
                atom_indices=atoms,
                ring_count=len(group["rings"]),
                ring_sizes=ring_sizes,
                aromatic=bool(aromatic),
                macrocyclic=any(size >= MACROCYCLE_MIN_RING_SIZE for size in ring_sizes),
            )
        )
    return tuple(components)


def _restrained_bond_classes(mol: Any) -> dict[int, str]:
    """Map bond index -> restrained rotor class for amide-like linkages."""

    classes: dict[int, str] = {}
    for rotor_class, smarts in _RESTRAINED_SMARTS:
        pattern = Chem.MolFromSmarts(smarts)
        if pattern is None:
            continue
        for match in mol.GetSubstructMatches(pattern):
            for i in range(len(match)):
                for j in range(i + 1, len(match)):
                    bond = mol.GetBondBetweenAtoms(int(match[i]), int(match[j]))
                    if bond is None or bond.IsInRing():
                        continue
                    if bond.GetBondType() != Chem.BondType.SINGLE:
                        continue
                    # Most specific pattern wins: do not downgrade urea to amide.
                    classes.setdefault(int(bond.GetIdx()), rotor_class)
    return classes


def _has_torsion_partners(mol: Any, atom_idx: int, other_idx: int) -> bool:
    """A torsion needs a heavy neighbour on each side beyond the bond itself."""

    atom = mol.GetAtomWithIdx(int(atom_idx))
    for neighbour in atom.GetNeighbors():
        if int(neighbour.GetIdx()) == int(other_idx):
            continue
        if neighbour.GetAtomicNum() > 1:
            return True
    return False


def _stereo_locked(bond: Any) -> bool:
    if bond.GetBondType() == Chem.BondType.DOUBLE:
        return True
    return bool(bond.GetStereo() != Chem.BondStereo.STEREONONE)


def perceive_ligand_rotors(smiles: str) -> RotorPerception:
    """Classify ring rigid components and chemistry-aware rotors for a ligand."""

    smi = str(smiles or "").strip()
    if not smi:
        return _unsupported(
            "", status=STATUS_UNSUPPORTED_INVALID, source="none", reason="empty_smiles"
        )
    if Chem is None:
        return _unsupported(
            smi,
            status=STATUS_UNSUPPORTED_NO_RDKIT,
            source="fallback",
            reason="rdkit_unavailable_rotor_perception",
        )
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return _unsupported(
            smi, status=STATUS_UNSUPPORTED_INVALID, source="rdkit", reason="invalid_smiles"
        )

    rigid_components = _fused_ring_components(mol)
    macrocycle_ring_sizes = tuple(
        sorted(
            size
            for component in rigid_components
            for size in component.ring_sizes
            if size >= MACROCYCLE_MIN_RING_SIZE
        )
    )
    if macrocycle_ring_sizes:
        # Route out instead of pretending a macrocycle is a rigid scaffold.
        return _unsupported(
            smi,
            status=STATUS_UNSUPPORTED_MACROCYCLE,
            source="rdkit",
            reason="macrocycle_requires_ring_closure_sampling",
            macrocycle_ring_sizes=macrocycle_ring_sizes,
            rigid_components=rigid_components,
        )

    restrained_classes = _restrained_bond_classes(mol)
    rotors: list[PerceivedRotor] = []
    stereo_locked_count = 0
    for bond in mol.GetBonds():
        if bond.IsInRing():
            # Ring bonds belong to a rigid component, never to the rotor set.
            continue
        if _stereo_locked(bond):
            stereo_locked_count += 1
            continue
        if bond.GetBondType() != Chem.BondType.SINGLE:
            continue
        begin = int(bond.GetBeginAtomIdx())
        end = int(bond.GetEndAtomIdx())
        if not (_has_torsion_partners(mol, begin, end) and _has_torsion_partners(mol, end, begin)):
            continue
        conjugated = bool(bond.GetIsConjugated())
        begin_in_ring = bool(mol.GetAtomWithIdx(begin).IsInRing())
        end_in_ring = bool(mol.GetAtomWithIdx(end).IsInRing())
        # An exocyclic ring bond has exactly one ring atom; a bond joining two
        # ring systems is a distinct, more hindered case.
        exocyclic = begin_in_ring != end_in_ring
        ring_ring = begin_in_ring and end_in_ring
        restrained_class = restrained_classes.get(int(bond.GetIdx()))
        if restrained_class is not None:
            rotor_class = restrained_class
        elif conjugated:
            rotor_class = ROTOR_CLASS_CONJUGATED
        elif ring_ring:
            rotor_class = ROTOR_CLASS_RING_RING
        elif exocyclic:
            rotor_class = ROTOR_CLASS_EXOCYCLIC_RING
        elif (
            mol.GetAtomWithIdx(begin).GetHybridization() == Chem.HybridizationType.SP3
            and mol.GetAtomWithIdx(end).GetHybridization() == Chem.HybridizationType.SP3
        ):
            rotor_class = ROTOR_CLASS_SP3_SP3
        else:
            rotor_class = ROTOR_CLASS_FREE
        rotors.append(
            PerceivedRotor(
                bond_idx=int(bond.GetIdx()),
                begin_atom_idx=begin,
                end_atom_idx=end,
                rotor_class=rotor_class,
                periodicity=int(_PERIODICITY.get(rotor_class, 3)),
                preferred_state_count=int(_PREFERRED_STATE_COUNT.get(rotor_class, 3)),
                conjugated=conjugated,
                exocyclic_ring_bond=bool(exocyclic),
                ring_ring_bond=bool(ring_ring),
                restrained=rotor_class in RESTRAINED_ROTOR_CLASSES,
            )
        )

    return RotorPerception(
        smiles=smi,
        status=STATUS_SUPPORTED,
        source="rdkit",
        rotors=tuple(rotors),
        rigid_components=rigid_components,
        macrocycle_ring_sizes=(),
        stereo_locked_bond_count=int(stereo_locked_count),
    )


__all__ = [
    "CLAIM_BOUNDARY",
    "MACROCYCLE_MIN_RING_SIZE",
    "PerceivedRotor",
    "RESTRAINED_ROTOR_CLASSES",
    "ROTOR_CLASS_AMIDE",
    "ROTOR_CLASS_CARBAMATE",
    "ROTOR_CLASS_CONJUGATED",
    "ROTOR_CLASS_EXOCYCLIC_RING",
    "ROTOR_CLASS_FREE",
    "ROTOR_CLASS_RING_BOND",
    "ROTOR_CLASS_RING_RING",
    "ROTOR_CLASS_SP3_SP3",
    "ROTOR_CLASS_STEREO_LOCKED",
    "ROTOR_CLASS_SULFONAMIDE",
    "ROTOR_CLASS_TERMINAL",
    "ROTOR_CLASS_UREA",
    "ROTOR_PERCEPTION_SCHEMA_VERSION",
    "RigidComponent",
    "RotorPerception",
    "STATUS_SUPPORTED",
    "STATUS_UNSUPPORTED_INVALID",
    "STATUS_UNSUPPORTED_MACROCYCLE",
    "STATUS_UNSUPPORTED_NO_RDKIT",
    "perceive_ligand_rotors",
]
