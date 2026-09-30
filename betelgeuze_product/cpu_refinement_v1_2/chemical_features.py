"""Opt-in explicit-graph hydrogen-bond features; no pH or affinity inference.

The formal charges, hydrogens, aromatic flags and bond orders are declarations
in the input. This bounded model does not repair or choose chemical states.
RDKit BaseFeatures and Lipinski are independent comparison definitions, not an
oracle: for example BaseFeatures calls carboxylic hydroxyl O an acceptor and
omits many aliphatic amines. This model explicitly excludes acid hydroxyl O.
The historical engine scorer and its numeric weights are not modified.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import math

from betelgeuze_engine_v2.docking.scorer_v1 import (
    ChemistryPoseScorerV1, ScorerBackend, ScorerV1Context, ScorerV1Error,
    ScorerV1Terms,
)
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, ScoreDirection
from betelgeuze_engine_v2.molecular import AllAtomSystem, require_valid_all_atom_system


EXPLICIT_CHEMICAL_FEATURE_MODEL_ID = "explicit_graph_hbond_features/1.0.0"
EXPLICIT_GRAPH_SCORER_ID = "betelgeuze.cpu_explicit_graph_pose_scorer"
EXPLICIT_GRAPH_SCORE_ID = EXPLICIT_GRAPH_SCORER_ID + "/1.0.0"
EXPLICIT_GRAPH_CONTEXT_SCHEMA = "betelgeuze.cpu_explicit_graph_scorer_context/1.0.0"
EXPLICIT_GRAPH_TERMS_SCHEMA = "betelgeuze.cpu_explicit_graph_scorer_terms/1.0.0"


def feature_model_document() -> dict:
    return {
        "feature_model_id": EXPLICIT_CHEMICAL_FEATURE_MODEL_ID,
        "chemical_state": "declared_explicit_hydrogens_formal_charges_aromaticity_bond_orders",
        "state_inference": False,
        "nitrogen": "exclude_positive_pyrrolic_amide_thioamide_sulfonamide_phosphoramide_and_cationic_amidine_group",
        "neutral_amidine_guanidine": "only_declared_imine_nitrogen_accepts",
        "oxygen": "nonpositive_accepts_except_neutral_oxoacid_hydroxyl",
        "sulfur": "nonpositive_divalent_or_monovalent_anion_accepts",
        "donor": "nonnegative_N_O_S_with_explicit_bonded_H",
        "hydrophobic": "legacy_neutral_C_S_halogen_partial_charge_absolute_at_most_0.35",
        "pocket_filter": "classify_using_complete_graph_then_restrict_feature_atoms",
        "references": [
            "https://github.com/rdkit/rdkit/blob/master/Data/BaseFeatures.fdef",
            "https://github.com/rdkit/rdkit/blob/master/rdkit/Chem/Lipinski.py",
            "https://doi.org/10.1016/S0010-8545(00)00389-1",
        ],
        "scientifically_validated": False,
        "claim_safe": False,
    }


@dataclass(frozen=True)
class ChemicalFeatures:
    donors: tuple[tuple[int, int], ...]
    acceptors: tuple[int, ...]
    hydrophobic: tuple[int, ...]
    acceptor_reasons: tuple[tuple[int, str], ...]


def derive_explicit_chemical_features(
    system: AllAtomSystem, allowed: set[int] | None = None,
) -> ChemicalFeatures:
    """Classify declared atoms, rejecting incomplete common-organic valences.

    Group classification uses the full graph even at a pocket boundary. Charge
    delocalization in cationic amidines/guanidines excludes *every* group N,
    independently of which N carries the drawn C=N bond or positive charge.
    Neutral tautomers retain only the explicitly drawn imine N as acceptor.
    """
    require_valid_all_atom_system(system)
    atoms = system.atoms
    selected = set(range(system.atom_count)) if allowed is None else set(allowed)
    if any(type(i) is not int or not 0 <= i < system.atom_count for i in selected):
        raise ScorerV1Error("explicit feature atom selection is invalid")
    neighbors = [[] for _ in atoms]
    aromatic_neighbors = [[] for _ in atoms]
    orders = {}
    for bond in system.bonds:
        i, j = bond.atom_i, bond.atom_j
        order = float(bond.order)
        if order not in (1.0, 1.5, 2.0, 3.0):
            raise ScorerV1Error("explicit features require declared supported bond orders")
        if bond.aromatic:
            if not (atoms[i].aromatic and atoms[j].aromatic) or order == 3.0:
                raise ScorerV1Error("explicit aromatic bond and atom declarations disagree")
            aromatic_neighbors[i].append(j)
            aromatic_neighbors[j].append(i)
        elif order == 1.5:
            raise ScorerV1Error("fractional aromatic bond requires aromatic declarations")
        neighbors[i].append(j)
        neighbors[j].append(i)
        orders[min(i, j), max(i, j)] = order
    for row in neighbors:
        row.sort()

    def order(i, j):
        return orders[min(i, j), max(i, j)]

    hydrogen_neighbors = [tuple(j for j in row if atoms[j].element == "H") for row in neighbors]
    for i, atom in enumerate(atoms):
        valence = sum(order(i, j) for j in neighbors[i])
        if atom.aromatic:
            aromatic_orders = tuple(order(i, j) for j in aromatic_neighbors[i])
            if (atom.element not in {"C", "N", "O", "S"}
                    or len(neighbors[i]) not in {2, 3} or len(aromatic_orders) not in {2, 3}):
                raise ScorerV1Error("explicit aromatic atom graph is unsupported")
            fractional = 1.5 in aromatic_orders
            if fractional and any(o != 1.5 for o in aromatic_orders):
                raise ScorerV1Error("mixed aromatic bond encodings are unsupported")
            if fractional:
                # Two aromatic edges contribute 3; an external H/substituent
                # contributes 1. Fused C/pyrrolic N may have three 1.5 edges.
                valid = (
                    (atom.element == "C" and atom.formal_charge == 0
                     and len(neighbors[i]) == 3 and valence in {4.0, 4.5})
                    or (atom.element == "N" and atom.formal_charge == 0
                        and valence in ({3.0} if len(neighbors[i]) == 2 else {4.0, 4.5}))
                    or (atom.element == "N" and atom.formal_charge == 1
                        and len(neighbors[i]) == 3 and valence in {4.0, 4.5})
                    or (atom.element == "N" and atom.formal_charge == -1
                        and len(neighbors[i]) == 2 and valence == 3.0)
                    or (atom.element in {"O", "S"} and atom.formal_charge == 0
                        and len(neighbors[i]) == 2 and valence == 3.0)
                )
            else:
                expected = {("C", 0): 4, ("N", 0): 3, ("N", 1): 4,
                            ("N", -1): 2, ("O", 0): 2, ("S", 0): 2}
                valid = expected.get((atom.element, atom.formal_charge)) == valence
            if not valid:
                raise ScorerV1Error("explicit aromatic atom lacks complete supported valence/hydrogens")
        else:
            expected = {
                ("H", 0): (1,), ("C", 0): (4,), ("C", 1): (3,), ("C", -1): (3,),
                ("N", 0): (3,), ("N", 1): (4,), ("N", -1): (2,),
                ("O", 0): (2,), ("O", 1): (3,), ("O", -1): (1,),
                ("S", 0): (2, 4, 6), ("S", 1): (3, 5), ("S", 2): (4,), ("S", -1): (1,),
                ("P", 0): (3, 5), ("P", 1): (4,),
                ("F", 0): (1,), ("Cl", 0): (1,), ("Br", 0): (1,), ("I", 0): (1,),
                ("F", -1): (0,), ("Cl", -1): (0,), ("Br", -1): (0,), ("I", -1): (0,),
            }.get((atom.element, atom.formal_charge))
            organic = atom.element in {"H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I"}
            if organic and (expected is None or valence not in expected):
                raise ScorerV1Error(
                    f"explicit chemical graph has incomplete/unsupported valence at atom {i}"
                )
        if atom.partial_charge_e is None or not math.isfinite(float(atom.partial_charge_e)):
            raise ScorerV1Error("explicit features require finite declared partial charges")

    amidine_reasons = {}
    for center, atom in enumerate(atoms):
        if atom.element != "C" or atom.aromatic:
            continue
        nitrogens = [j for j in neighbors[center] if atoms[j].element == "N"]
        imines = [j for j in nitrogens if order(center, j) == 2.0]
        if len(nitrogens) < 2 or not (imines or atom.formal_charge > 0):
            continue
        positive = atom.formal_charge + sum(atoms[j].formal_charge for j in nitrogens) > 0
        for j in nitrogens:
            if positive:
                amidine_reasons[j] = "reject_cationic_amidine_guanidine_group"
            elif j not in imines:
                amidine_reasons[j] = "reject_neutral_amidine_guanidine_amino_nitrogen"

    def oxo_equivalents(center, excluded):
        return sum(
            atoms[j].element in {"O", "S"}
            and (order(center, j) == 2.0 or (
                atoms[center].element in {"S", "P"}
                and atoms[center].formal_charge > 0 and atoms[j].formal_charge < 0
            ))
            for j in neighbors[center] if j != excluded
        )

    def acceptor_reason(i):
        atom = atoms[i]
        if atom.formal_charge > 0:
            return "reject_positive_formal_charge"
        if atom.element == "N":
            if i in amidine_reasons:
                return amidine_reasons[i]
            if atom.aromatic and (hydrogen_neighbors[i] or len(neighbors[i]) == 3):
                return "reject_pyrrolic_aromatic_nitrogen"
            for center in neighbors[i]:
                if order(i, center) != 1.0:
                    continue
                element = atoms[center].element
                oxo = oxo_equivalents(center, i)
                if element == "C" and oxo:
                    return "reject_amide_thioamide_nitrogen"
                if element == "S" and oxo >= 2:
                    return "reject_sulfonamide_nitrogen"
                if element == "P" and oxo:
                    return "reject_phosphoramide_nitrogen"
            return "accept_available_nitrogen_lone_pair"
        if atom.element == "O":
            if atom.formal_charge == 0 and hydrogen_neighbors[i]:
                if any(atoms[j].element in {"C", "S", "P"} and oxo_equivalents(j, i)
                       for j in neighbors[i]):
                    return "reject_neutral_oxoacid_hydroxyl"
            return "accept_nonpositive_oxygen"
        valence = sum(order(i, j) for j in neighbors[i])
        if atom.formal_charge < 0 and valence == 1:
            return "accept_monovalent_sulfur_anion"
        if atom.formal_charge == 0 and valence == 2:
            return "accept_divalent_sulfur"
        return "reject_other_sulfur_valence"

    donors, acceptors, hydrophobic, reasons = [], [], [], []
    for i in sorted(selected):
        atom = atoms[i]
        if atom.element in {"N", "O", "S"}:
            if atom.formal_charge >= 0:
                donors.extend((i, h) for h in hydrogen_neighbors[i] if h in selected)
            reason = acceptor_reason(i)
            reasons.append((i, reason))
            if reason.startswith("accept_"):
                acceptors.append(i)
        if (atom.element in {"C", "S", "F", "Cl", "Br", "I"}
                and atom.formal_charge == 0 and abs(float(atom.partial_charge_e)) <= 0.35):
            hydrophobic.append(i)
    return ChemicalFeatures(tuple(donors), tuple(acceptors), tuple(hydrophobic), tuple(reasons))


class ExplicitGraphContext(ScorerV1Context):
    __slots__ = ()

    def _projection(self):
        return {**super()._projection(), "schema_id": EXPLICIT_GRAPH_CONTEXT_SCHEMA,
                "chemical_feature_model_id": EXPLICIT_CHEMICAL_FEATURE_MODEL_ID}


class ExplicitGraphTerms(ScorerV1Terms):
    __slots__ = ()

    def _projection(self):
        return {**super()._projection(), "schema_id": EXPLICIT_GRAPH_TERMS_SCHEMA,
                "score_id": EXPLICIT_GRAPH_SCORE_ID}


def explicit_graph_score_descriptor() -> DockingScoreDescriptor:
    return DockingScoreDescriptor(
        score_id=EXPLICIT_GRAPH_SCORE_ID, direction=ScoreDirection.MINIMIZE, unit=None,
        semantics="uncalibrated_dimensionless_explicit_graph_chemistry_pose_ordering_score",
        calibrated=False,
        applicability_domain_id="authenticated_known_pocket_complete_explicit_chemical_graph_partial_charge_v1",
    )


class ExplicitGraphScorer(ChemistryPoseScorerV1):
    """Separate CPU scorer identity using unchanged v1 numeric score equations."""
    scorer_id = EXPLICIT_GRAPH_SCORER_ID
    scorer_version = "1.0.0"
    chemical_feature_model_id = EXPLICIT_CHEMICAL_FEATURE_MODEL_ID

    def __init__(self, authority, receptor_system, ligand_system, **kwargs):
        if ScorerBackend(kwargs.get("backend", ScorerBackend.PYTHON_REFERENCE)) is not ScorerBackend.PYTHON_REFERENCE:
            raise ScorerV1Error("explicit graph scorer currently requires Python reference CPU backend")
        receptor = derive_explicit_chemical_features(receptor_system, set(authority.receptor_atom_indices))
        ligand = derive_explicit_chemical_features(ligand_system)
        super().__init__(authority, receptor_system, ligand_system, **kwargs)
        values = {f.name: getattr(self._context, f.name) for f in fields(ScorerV1Context) if f.init}
        position = {atom: i for i, atom in enumerate(authority.receptor_atom_indices)}
        values.update(
            receptor_donors=tuple((position[d], position[h]) for d, h in receptor.donors),
            receptor_acceptors=tuple(position[i] for i in receptor.acceptors),
            receptor_hydrophobic=tuple(position[i] for i in receptor.hydrophobic),
            ligand_donors=ligand.donors, ligand_acceptors=ligand.acceptors,
            ligand_hydrophobic=ligand.hydrophobic,
        )
        self._context = ExplicitGraphContext(**values)
        self.score_descriptor = explicit_graph_score_descriptor()
        self._receptor_hydrophobic = frozenset(self._context.receptor_hydrophobic)
        self._ligand_hydrophobic = frozenset(self._context.ligand_hydrophobic)
        self._ligand_acceptors = frozenset(self._context.ligand_acceptors)
        self._ligand_donor_heavy = frozenset(d for d, _ in self._context.ligand_donors)

    def _score_terms_python(self, proposal):
        result = super()._score_terms_python(proposal)
        return ExplicitGraphTerms(**{f.name: getattr(result, f.name) for f in fields(ScorerV1Terms) if f.init})
