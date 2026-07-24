"""Align authoritative rotor selection with canonical docking semantics.

Canonical :class:`Bond` records use ``"none"`` for an undeclared stereo state.
The initial authority implementation treated every non-empty string as a stereo
declaration, which excluded every ordinary single bond. This installer preserves
all original authority checks and reconstructs only the rotatable-child mask,
accepting canonical ``none`` and ``unspecified`` labels while continuing to
exclude unknown or explicitly stereochemical bonds.

The authenticated search wrapper also resolves the active search implementation
at call time. It therefore inherits later fail-closed search hardening rather
than retaining a function alias captured before the round-one installer ran.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
import hashlib
import json
import sys

import torch


AUTHORITY_ROTOR_STEREO_COMPAT_SCHEMA_ID = (
    "betelgeuze.engine_v2_authority_rotor_stereo_compat/1.0.0"
)
_UNDECLARED_BOND_STEREO = frozenset({"none", "unspecified"})


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def install_authority_rotor_stereo_compat() -> str:
    marker = "_betelgeuze_authority_rotor_stereo_compat_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from betelgeuze_engine_v2 import docking as docking_package
    from betelgeuze_engine_v2.docking import authority
    from betelgeuze_engine_v2.docking.proposals import TorsionSearchSpace

    original = authority.derive_authoritative_torsion_search_space
    if getattr(original, "_betelgeuze_stereo_compat", False):
        return str(getattr(sys, marker))

    def derive_authoritative_torsion_search_space(
        ligand_system,
        *,
        model_index: int = 0,
    ):
        search_space, receipt = original(
            ligand_system,
            model_index=model_index,
        )
        parent = [int(value) for value in search_space.parent.tolist()]
        atom_count = search_space.atom_count
        children: list[list[int]] = [[] for _ in range(atom_count)]
        roots: list[int] = []
        for child, ancestor in enumerate(parent):
            if ancestor < 0:
                roots.append(child)
            else:
                children[ancestor].append(child)
        order: list[int] = []
        queue: deque[int] = deque(sorted(roots))
        while queue:
            node = queue.popleft()
            order.append(node)
            queue.extend(sorted(children[node]))
        if len(order) != atom_count:
            raise authority.DockingAuthorityError(
                "derived torsion forest is incomplete"
            )
        subtree_size = [1] * atom_count
        for child in reversed(order):
            ancestor = parent[child]
            if ancestor >= 0:
                subtree_size[ancestor] += subtree_size[child]
        pair_to_bond = {
            tuple(sorted((int(bond.atom_i), int(bond.atom_j)))): bond
            for bond in ligand_system.bonds
        }
        rotatable = torch.zeros(atom_count, dtype=torch.bool)
        for child, ancestor in enumerate(parent):
            if ancestor < 0:
                continue
            bond = pair_to_bond[tuple(sorted((child, ancestor)))]
            stereo = str(bond.stereo or "none").strip().lower()
            child_side = subtree_size[child]
            parent_side = atom_count - child_side
            rotatable[child] = bool(
                float(bond.order) == 1.0
                and not bool(bond.aromatic)
                and stereo in _UNDECLARED_BOND_STEREO
                and ligand_system.atoms[child].element.upper() != "H"
                and ligand_system.atoms[ancestor].element.upper() != "H"
                and child_side > 1
                and parent_side > 1
            )
        corrected = TorsionSearchSpace(
            local_offsets=search_space.local_offsets,
            parent=search_space.parent,
            local_axes=search_space.local_axes,
            rotatable_mask=rotatable,
            root_positions=search_space.root_positions,
        )
        corrected_receipt = authority.TorsionSearchSpaceDerivationReceipt(
            ligand_chemical_graph_sha256=(
                receipt.ligand_chemical_graph_sha256
            ),
            ligand_indexed_topology_sha256=(
                receipt.ligand_indexed_topology_sha256
            ),
            ligand_source_bound_topology_sha256=(
                receipt.ligand_source_bound_topology_sha256
            ),
            ligand_coordinates_sha256=receipt.ligand_coordinates_sha256,
            selected_model_coordinate_sha256=(
                receipt.selected_model_coordinate_sha256
            ),
            model_index=receipt.model_index,
            atom_count=receipt.atom_count,
            bond_count=receipt.bond_count,
            root_atom_indices=receipt.root_atom_indices,
            rotatable_child_atom_indices=tuple(
                int(index)
                for index in torch.nonzero(
                    rotatable,
                    as_tuple=False,
                ).reshape(-1).tolist()
            ),
            search_space_fingerprint_sha256=corrected.fingerprint_sha256,
            zero_torsion_coordinate_sha256=(
                receipt.zero_torsion_coordinate_sha256
            ),
            derivation_policy_sha256=receipt.derivation_policy_sha256,
        )
        return corrected, corrected_receipt

    def run_authenticated_bounded_docking_search(
        authenticated_problem,
        budget,
        scorer,
        *,
        refiner=None,
        diversity_rmsd_angstrom: float = 0.5,
        diversity_metric: str = "direct_rmsd",
        symmetry_permutations: Sequence[
            Sequence[int] | torch.Tensor
        ] | None = None,
    ):
        if not isinstance(
            authenticated_problem,
            authority.AuthenticatedDockingProblem,
        ):
            raise TypeError(
                "authenticated_problem must be AuthenticatedDockingProblem"
            )
        authenticated_problem.input_receipt_sha256
        from betelgeuze_engine_v2.docking import search as search_module

        result = search_module.run_bounded_docking_search(
            authenticated_problem.search_space,
            budget,
            scorer,
            refiner=refiner,
            validity_context=authenticated_problem.validity_context,
            diversity_rmsd_angstrom=diversity_rmsd_angstrom,
            diversity_metric=diversity_metric,
            symmetry_permutations=symmetry_permutations,
            problem=authenticated_problem.problem,
        )
        if (
            result.problem_fingerprint_sha256
            != authenticated_problem.problem.fingerprint_sha256
        ):
            raise authority.DockingAuthorityError(
                "search result problem identity is cross-wired"
            )
        if (
            result.search_space_fingerprint_sha256
            != authenticated_problem.search_space.fingerprint_sha256
        ):
            raise authority.DockingAuthorityError(
                "search result search-space identity is cross-wired"
            )
        if (
            result.validity_context_fingerprint_sha256
            != authenticated_problem.validity_context.fingerprint_sha256
        ):
            raise authority.DockingAuthorityError(
                "search result validity identity is cross-wired"
            )
        return authority.AuthenticatedDockingSearchResult(
            authenticated_input_receipt_sha256=(
                authenticated_problem.input_receipt_sha256
            ),
            search_result=result,
        )

    derive_authoritative_torsion_search_space._betelgeuze_stereo_compat = True
    authority.derive_authoritative_torsion_search_space = (
        derive_authoritative_torsion_search_space
    )
    authority.run_authenticated_bounded_docking_search = (
        run_authenticated_bounded_docking_search
    )
    docking_package.derive_authoritative_torsion_search_space = (
        derive_authoritative_torsion_search_space
    )
    docking_package.run_authenticated_bounded_docking_search = (
        run_authenticated_bounded_docking_search
    )

    receipt = _sha256(
        {
            "schema_id": AUTHORITY_ROTOR_STEREO_COMPAT_SCHEMA_ID,
            "canonical_undeclared_stereo_labels": sorted(
                _UNDECLARED_BOND_STEREO
            ),
            "subtree_accounting_is_atom_index_independent": True,
            "authenticated_search_resolves_active_implementation": True,
            "explicit_stereo_bonds_remain_nonrotatable": True,
            "unknown_stereo_bonds_remain_nonrotatable": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "AUTHORITY_ROTOR_STEREO_COMPAT_SCHEMA_ID",
    "install_authority_rotor_stereo_compat",
]
