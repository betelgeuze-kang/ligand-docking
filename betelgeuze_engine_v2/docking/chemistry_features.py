"""Versioned graph features shared by the explicit preparation development lane.

Chemical identity is perceived on the complete graph. Spatial filtering only
controls which interactions are usable; it cannot turn a pyrrolic N into an
acceptor. Historical systems without a policy marker keep their frozen rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from betelgeuze_engine_v2.molecular import AllAtomSystem

FULL_TOPOLOGY_FEATURE_POLICY_ID = "betelgeuze.full_topology_chemistry_features/1.0.0"
FEATURE_POLICY_METADATA_KEY = "docking_chemistry_feature_policy_id"


def uses_full_topology_features(system: AllAtomSystem) -> bool:
    marker = system.metadata.get(FEATURE_POLICY_METADATA_KEY)
    if marker is None:
        return False
    if marker != FULL_TOPOLOGY_FEATURE_POLICY_ID:
        raise ValueError("unsupported docking chemistry feature policy")
    return True


def require_matching_feature_policies(
    receptor: AllAtomSystem, ligand: AllAtomSystem
) -> None:
    if uses_full_topology_features(receptor) != uses_full_topology_features(ligand):
        raise ValueError("receptor and ligand chemistry feature policies differ")


@dataclass(frozen=True)
class ChemistryFeatures:
    donor_pairs: tuple[tuple[int, int], ...]
    acceptors: tuple[int, ...]
    positive: tuple[int, ...]
    negative: tuple[int, ...]
    hydrophobic: tuple[int, ...]
    aromatic: tuple[int, ...]

    def guidance_indices(self) -> dict[str, tuple[int, ...]]:
        return {
            "donor": tuple(sorted({donor for donor, _ in self.donor_pairs})),
            "acceptor": self.acceptors,
            "positive": self.positive,
            "negative": self.negative,
            "hydrophobic": self.hydrophobic,
            "aromatic": self.aromatic,
        }


def perceive_full_topology_features(
    system: AllAtomSystem,
    *,
    allowed_indices: set[int] | None = None,
) -> ChemistryFeatures:
    allowed = (
        set(range(system.atom_count))
        if allowed_indices is None
        else set(allowed_indices)
    )
    if not allowed.issubset(range(system.atom_count)):
        raise ValueError("feature subset references an unknown atom")
    adjacency = [set() for _ in system.atoms]
    bonds = {}
    for bond in system.bonds:
        adjacency[bond.atom_i].add(bond.atom_j)
        adjacency[bond.atom_j].add(bond.atom_i)
        bonds[tuple(sorted((bond.atom_i, bond.atom_j)))] = bond

    def multiple_bond(first: int, second: int) -> bool:
        return math.isclose(
            bonds[tuple(sorted((first, second)))].order, 2.0, abs_tol=1e-6
        )

    def restricted_nitrogen(index: int) -> bool:
        if system.atoms[index].element != "N":
            return False
        for center in adjacency[index]:
            atom = system.atoms[center]
            oxygens = [j for j in adjacency[center] if system.atoms[j].element == "O"]
            if atom.element == "C" and any(multiple_bond(center, j) for j in oxygens):
                return True
            if (
                atom.element == "S"
                and sum(
                    multiple_bond(center, j)
                    or (atom.formal_charge > 0 and system.atoms[j].formal_charge < 0)
                    for j in oxygens
                )
                >= 2
            ):
                return True
            # Amidinium/guanidinium resonance must not make the formally
            # neutral N atoms hydrogen-bond acceptors.
            nitrogens = [j for j in adjacency[center] if system.atoms[j].element == "N"]
            if (
                atom.element == "C"
                and len(nitrogens) >= 2
                and any(system.atoms[j].formal_charge > 0 for j in nitrogens)
            ):
                return True
        return False

    def restricted_sulfur(index: int) -> bool:
        atom = system.atoms[index]
        if atom.element != "S":
            return False
        # This bounded rule admits nonoxidized divalent sulfur (for example
        # thioethers) and aromatic sulfur. Oxidized/hypervalent sulfur is not
        # an acceptor; its bonded oxygen atoms are perceived independently.
        # Test the graph as well as formal charge so the neutral S=O and
        # charge-separated S+-O- representations cannot disagree here.
        if any(system.atoms[j].element == "O" for j in adjacency[index]):
            return True
        valence = math.fsum(
            bonds[tuple(sorted((index, j)))].order for j in adjacency[index]
        )
        aromatic_divalent = atom.aromatic and len(adjacency[index]) == 2
        return valence > 2.0 + 1e-6 and not aromatic_divalent

    donors, acceptors, positive, negative, hydrophobic, aromatic = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for index in sorted(allowed):
        atom = system.atoms[index]
        hydrogens = sorted(
            j for j in adjacency[index] if system.atoms[j].element == "H"
        )
        if atom.element in {"N", "O", "S"}:
            donors.extend((index, j) for j in hydrogens if j in allowed)
            pyrrolic = atom.element == "N" and atom.aromatic and bool(hydrogens)
            acid_hydroxyl = (
                atom.element == "O"
                and bool(hydrogens)
                and any(
                    system.atoms[c].element == "C"
                    and any(
                        j != index
                        and system.atoms[j].element == "O"
                        and multiple_bond(c, j)
                        for j in adjacency[c]
                    )
                    for c in adjacency[index]
                )
            )
            if (
                atom.formal_charge <= 0
                and not pyrrolic
                and not restricted_nitrogen(index)
                and not restricted_sulfur(index)
                and not acid_hydroxyl
            ):
                acceptors.append(index)
        if atom.formal_charge > 0:
            positive.append(index)
        if atom.formal_charge < 0:
            negative.append(index)
        if (
            atom.element in {"C", "S", "F", "Cl", "Br", "I"}
            and atom.formal_charge == 0
            and abs(float(atom.partial_charge_e or 0.0)) <= 0.35
        ):
            hydrophobic.append(index)
        if atom.aromatic:
            aromatic.append(index)
    return ChemistryFeatures(
        *(
            tuple(rows)
            for rows in (donors, acceptors, positive, negative, hydrophobic, aromatic)
        )
    )
