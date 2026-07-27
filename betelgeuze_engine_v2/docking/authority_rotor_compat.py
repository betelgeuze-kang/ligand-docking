"""Align authoritative rotor selection with canonical docking semantics.

Canonical :class:`Bond` records use ``"none"`` for an undeclared stereo state.
The authority implementation now owns canonical stereo handling and rigid-ring
selection directly. This installer retains the public compatibility surface
without rebuilding the mask, so it cannot discard ring topology recorded by the
authoritative derivation receipt.

The authenticated search wrapper also resolves the active search implementation
at call time. It therefore inherits later fail-closed search hardening rather
than retaining a function alias captured before the round-one installer ran.
"""

from __future__ import annotations

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
    original = authority.derive_authoritative_torsion_search_space
    if getattr(original, "_betelgeuze_stereo_compat", False):
        return str(getattr(sys, marker))

    def derive_authoritative_torsion_search_space(
        ligand_system,
        *,
        model_index: int = 0,
    ):
        return original(
            ligand_system,
            model_index=model_index,
        )

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
            placement_center=authenticated_problem.pocket.center,
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
            "authoritative_mask_reused_without_compat_reconstruction": True,
            "rigid_ring_topology_preserved": True,
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
