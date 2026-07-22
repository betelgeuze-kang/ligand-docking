"""Heavy-ligand graph comparison for public-data intake audits.

This module is intentionally separate from the frozen four-case reference-pose
materializer whose exact source bytes are part of protocol v1.1.  It projects
away explicit hydrogens and reports connectivity and raw directional V2000 bond
marks separately.  It does not perceive aromaticity or atom stereochemistry.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Sequence

from betelgeuze_engine_v2.molecular import AllAtomSystem

from .public_materialization import (
    PublicReferenceMaterializationError,
    PublicReferenceMaterializationLimits,
    _LabeledGraph,
    _STEREO_CODE_BY_NAME,
    _canonical_sha256,
    _digest,
    _exact_int,
    _graph_isomorphisms,
)


PUBLIC_LIGAND_HEAVY_GRAPH_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_ligand_heavy_graph_comparison/1.0.0"
)


def _bond_directional_label(
    bond: object,
    source: int,
    *,
    include_directional_stereo: bool,
) -> tuple[str, bool, int, int]:
    order = float(getattr(bond, "order"))
    aromatic = bool(getattr(bond, "aromatic"))
    if not include_directional_stereo:
        return order.hex(), aromatic, 0, 0
    stereo_name = str(getattr(bond, "stereo", "none")).strip().lower()
    metadata = dict(getattr(bond, "metadata", {}))
    raw_code = metadata.get(
        "v2000_stereo_code",
        _STEREO_CODE_BY_NAME.get(stereo_name),
    )
    if isinstance(raw_code, bool) or not isinstance(raw_code, Integral):
        raise PublicReferenceMaterializationError(
            "V2000 stereo code is unavailable for heavy-graph comparison"
        )
    stereo_code = int(raw_code)
    if stereo_code not in {0, 1, 4, 6}:
        raise PublicReferenceMaterializationError(
            "unsupported V2000 stereo code in heavy-graph comparison"
        )
    direction = 0
    if stereo_code:
        raw_first = metadata.get("v2000_source_atom_i")
        raw_second = metadata.get("v2000_source_atom_j")
        if (
            isinstance(raw_first, bool)
            or isinstance(raw_second, bool)
            or not isinstance(raw_first, Integral)
            or not isinstance(raw_second, Integral)
        ):
            raise PublicReferenceMaterializationError(
                "directional V2000 stereo metadata is missing"
            )
        if source == int(raw_first):
            direction = 1
        elif source == int(raw_second):
            direction = -1
        else:
            raise PublicReferenceMaterializationError(
                "directional V2000 stereo metadata is inconsistent"
            )
    return order.hex(), aromatic, stereo_code, direction


def _projected_labeled_graph(
    system: AllAtomSystem,
    *,
    atom_indices: Sequence[int],
    include_directional_stereo: bool,
) -> _LabeledGraph:
    selected = tuple(int(value) for value in atom_indices)
    if (
        not selected
        or tuple(sorted(set(selected))) != selected
        or selected[0] < 0
        or selected[-1] >= system.atom_count
    ):
        raise PublicReferenceMaterializationError(
            "heavy-graph atom projection must be a sorted non-empty subset"
        )
    projected_index = {
        atom_index: position for position, atom_index in enumerate(selected)
    }
    labels = tuple(
        (
            int(atom.atomic_number),
            int(atom.formal_charge),
            0 if atom.isotope_mass_number is None else int(atom.isotope_mass_number),
            bool(atom.aromatic),
        )
        for atom in (system.atoms[index] for index in selected)
    )
    adjacency: list[dict[int, tuple[str, bool, int, int]]] = [
        {} for _ in selected
    ]
    ordered_bonds: list[dict[str, object]] = []
    for bond in system.bonds:
        source_first = int(bond.atom_i)
        source_second = int(bond.atom_j)
        if source_first not in projected_index or source_second not in projected_index:
            continue
        first = projected_index[source_first]
        second = projected_index[source_second]
        forward = _bond_directional_label(
            bond,
            source_first,
            include_directional_stereo=include_directional_stereo,
        )
        reverse = _bond_directional_label(
            bond,
            source_second,
            include_directional_stereo=include_directional_stereo,
        )
        adjacency[first][second] = forward
        adjacency[second][first] = reverse
        ordered_bonds.append(
            {
                "atom_i": first,
                "atom_j": second,
                "forward_label": list(forward),
                "reverse_label": list(reverse),
            }
        )
    payload = {
        "atom_labels": [list(label) for label in labels],
        "bonds": ordered_bonds,
        "identity_policy": (
            "heavy_atomic_number_formal_charge_isotope_aromatic_and_"
            "directional_v2000_bond_order_aromatic_stereo"
            if include_directional_stereo
            else "heavy_atomic_number_formal_charge_isotope_aromatic_and_bond_order"
        ),
    }
    return _LabeledGraph(
        atom_labels=labels,
        adjacency=tuple(adjacency),
        edge_count=len(ordered_bonds),
        ordered_sha256=_canonical_sha256(payload),
    )


@dataclass(frozen=True, slots=True)
class PublicLigandHeavyGraphComparison:
    source_heavy_atom_indices: tuple[int, ...]
    target_heavy_atom_indices: tuple[int, ...]
    source_ordered_graph_sha256: str
    target_ordered_graph_sha256: str
    connectivity_isomorphism_count: int
    directional_stereo_isomorphism_count: int
    canonical_connectivity_mapping: tuple[int, ...]
    canonical_directional_stereo_mapping: tuple[int, ...]
    status: str
    schema_id: str = PUBLIC_LIGAND_HEAVY_GRAPH_COMPARISON_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_LIGAND_HEAVY_GRAPH_COMPARISON_SCHEMA_ID:
            raise PublicReferenceMaterializationError(
                "unsupported public ligand heavy-graph comparison schema"
            )
        for name in ("source_heavy_atom_indices", "target_heavy_atom_indices"):
            values = tuple(
                _exact_int(value, name=name) for value in getattr(self, name)
            )
            if not values or values != tuple(sorted(set(values))):
                raise PublicReferenceMaterializationError(
                    "heavy-atom index projections must be sorted and unique"
                )
            object.__setattr__(self, name, values)
        for name in (
            "source_ordered_graph_sha256",
            "target_ordered_graph_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        connectivity = _exact_int(
            self.connectivity_isomorphism_count,
            name="connectivity_isomorphism_count",
        )
        stereo = _exact_int(
            self.directional_stereo_isomorphism_count,
            name="directional_stereo_isomorphism_count",
        )
        connectivity_mapping = tuple(
            _exact_int(value, name="canonical_connectivity_mapping")
            for value in self.canonical_connectivity_mapping
        )
        stereo_mapping = tuple(
            _exact_int(value, name="canonical_directional_stereo_mapping")
            for value in self.canonical_directional_stereo_mapping
        )
        expected_status = (
            "graph_mismatch"
            if connectivity == 0
            else "directional_stereo_mismatch"
            if stereo == 0
            else "directional_stereo_match"
        )
        if self.status != expected_status:
            raise PublicReferenceMaterializationError(
                "heavy-graph comparison status is inconsistent"
            )
        if stereo > connectivity:
            raise PublicReferenceMaterializationError(
                "stereo isomorphisms cannot exceed connectivity isomorphisms"
            )
        width = len(self.source_heavy_atom_indices)
        if connectivity:
            if (
                len(connectivity_mapping) != width
                or len(self.target_heavy_atom_indices) != width
                or sorted(connectivity_mapping) != list(range(width))
            ):
                raise PublicReferenceMaterializationError(
                    "canonical connectivity mapping must be a complete bijection"
                )
        elif connectivity_mapping:
            raise PublicReferenceMaterializationError(
                "a graph mismatch cannot retain a connectivity mapping"
            )
        if stereo:
            if (
                len(stereo_mapping) != width
                or len(self.target_heavy_atom_indices) != width
                or sorted(stereo_mapping) != list(range(width))
            ):
                raise PublicReferenceMaterializationError(
                    "canonical heavy-graph mapping must be a complete bijection"
                )
        elif stereo_mapping:
            raise PublicReferenceMaterializationError(
                "a failed stereo comparison cannot retain a canonical mapping"
            )
        object.__setattr__(self, "connectivity_isomorphism_count", connectivity)
        object.__setattr__(self, "directional_stereo_isomorphism_count", stereo)
        object.__setattr__(self, "canonical_connectivity_mapping", connectivity_mapping)
        object.__setattr__(
            self,
            "canonical_directional_stereo_mapping",
            stereo_mapping,
        )

    @property
    def graph_match(self) -> bool:
        return self.connectivity_isomorphism_count > 0

    @property
    def directional_stereo_match(self) -> bool:
        return self.directional_stereo_isomorphism_count > 0

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "source_heavy_atom_indices": list(self.source_heavy_atom_indices),
            "target_heavy_atom_indices": list(self.target_heavy_atom_indices),
            "source_ordered_graph_sha256": self.source_ordered_graph_sha256,
            "target_ordered_graph_sha256": self.target_ordered_graph_sha256,
            "connectivity_isomorphism_count": self.connectivity_isomorphism_count,
            "directional_stereo_isomorphism_count": (
                self.directional_stereo_isomorphism_count
            ),
            "canonical_connectivity_mapping": list(
                self.canonical_connectivity_mapping
            ),
            "canonical_directional_stereo_mapping": list(
                self.canonical_directional_stereo_mapping
            ),
            "status": self.status,
            "identity_policy": (
                "heavy_atoms_only_atomic_number_formal_charge_isotope_aromatic_"
                "bond_order_aromatic_and_directional_v2000_bond_stereo"
            ),
            "atom_stereo_parity_beyond_directional_v2000_bonds_interpreted": False,
            "claim_safe": False,
        }


def compare_public_ligand_heavy_atom_graphs(
    source: AllAtomSystem,
    target: AllAtomSystem,
    *,
    limits: PublicReferenceMaterializationLimits | None = None,
) -> PublicLigandHeavyGraphComparison:
    """Compare heavy-atom connectivity and raw directional V2000 bond marks."""

    active = PublicReferenceMaterializationLimits() if limits is None else limits
    if not isinstance(active, PublicReferenceMaterializationLimits):
        raise PublicReferenceMaterializationError(
            "limits must be PublicReferenceMaterializationLimits"
        )
    source_heavy = tuple(
        atom.index for atom in source.atoms if atom.atomic_number != 1
    )
    target_heavy = tuple(
        atom.index for atom in target.atoms if atom.atomic_number != 1
    )
    source_connectivity = _projected_labeled_graph(
        source,
        atom_indices=source_heavy,
        include_directional_stereo=False,
    )
    target_connectivity = _projected_labeled_graph(
        target,
        atom_indices=target_heavy,
        include_directional_stereo=False,
    )
    connectivity_mappings = _graph_isomorphisms(
        source_connectivity,
        target_connectivity,
        max_mappings=active.max_symmetry_permutations,
        max_search_states=active.max_graph_search_states,
    )
    source_stereo = _projected_labeled_graph(
        source,
        atom_indices=source_heavy,
        include_directional_stereo=True,
    )
    target_stereo = _projected_labeled_graph(
        target,
        atom_indices=target_heavy,
        include_directional_stereo=True,
    )
    stereo_mappings = (
        _graph_isomorphisms(
            source_stereo,
            target_stereo,
            max_mappings=active.max_symmetry_permutations,
            max_search_states=active.max_graph_search_states,
        )
        if connectivity_mappings
        else ()
    )
    status = (
        "graph_mismatch"
        if not connectivity_mappings
        else "directional_stereo_mismatch"
        if not stereo_mappings
        else "directional_stereo_match"
    )
    return PublicLigandHeavyGraphComparison(
        source_heavy_atom_indices=source_heavy,
        target_heavy_atom_indices=target_heavy,
        source_ordered_graph_sha256=source_stereo.ordered_sha256,
        target_ordered_graph_sha256=target_stereo.ordered_sha256,
        connectivity_isomorphism_count=len(connectivity_mappings),
        directional_stereo_isomorphism_count=len(stereo_mappings),
        canonical_connectivity_mapping=(
            connectivity_mappings[0] if connectivity_mappings else ()
        ),
        canonical_directional_stereo_mapping=(
            stereo_mappings[0] if stereo_mappings else ()
        ),
        status=status,
    )


__all__ = [
    "PUBLIC_LIGAND_HEAVY_GRAPH_COMPARISON_SCHEMA_ID",
    "PublicLigandHeavyGraphComparison",
    "compare_public_ligand_heavy_atom_graphs",
]
