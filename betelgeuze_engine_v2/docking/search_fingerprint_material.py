"""Complete, recomputable docking-search fingerprint material.

The historical search fingerprint bound the proposal batch, component contracts,
validity identity, diversity mode, and symmetry mappings, but omitted the numeric
diversity threshold and did not expose its input projection in the public result.
That made two searches with different top-k diversity thresholds share one search
identity and forced offline verification to cross-link rather than recompute it.

This installer wraps the already-hardened active search implementation after the
round-one compatibility layer has loaded. It emits fingerprint schema v6, binds
the threshold by its exact binary64 hexadecimal representation, stores canonical
symmetry mappings, and adds the complete projection to ``DockingSearchResult``.
The existing candidate rows, ranking, validity, and failure-complete behavior are
not reimplemented.
"""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import math
import sys

import torch


DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_search/6.0.0"
)
DOCKING_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_search_result/2.0.0"
)
SEARCH_FINGERPRINT_MATERIAL_INSTALLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_search_fingerprint_material_installer/1.0.0"
)
_SEARCH_MATERIAL_ATTRIBUTES = (
    "_search_material_atom_count",
    "_search_material_diversity_threshold",
    "_search_material_unbound_validity_compatibility",
    "_search_material_symmetry_permutations",
)


class SearchFingerprintMaterialError(RuntimeError):
    """The public search material and retained search identity disagree."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise SearchFingerprintMaterialError(
            "search fingerprint material is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _material_from_result(result: object) -> dict[str, object]:
    try:
        atom_count = int(result._search_material_atom_count)
        threshold = float(result._search_material_diversity_threshold)
        unbound_compatibility = bool(
            result._search_material_unbound_validity_compatibility
        )
        permutations = tuple(result._search_material_symmetry_permutations)
    except AttributeError as exc:
        raise SearchFingerprintMaterialError(
            "docking search result predates complete fingerprint material"
        ) from exc
    if atom_count < 1:
        raise SearchFingerprintMaterialError(
            "search fingerprint atom count must be positive"
        )
    if not math.isfinite(threshold) or threshold < 0.0:
        raise SearchFingerprintMaterialError(
            "search fingerprint diversity threshold is invalid"
        )
    canonical_permutations: tuple[tuple[int, ...], ...] = tuple(
        tuple(int(value) for value in permutation)
        for permutation in permutations
    )
    for permutation in canonical_permutations:
        if len(permutation) != atom_count:
            raise SearchFingerprintMaterialError(
                "search fingerprint symmetry mapping has the wrong atom count"
            )
    return {
        "schema_id": DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID,
        "budget": result.budget.to_dict(),
        "scorer_contract_fingerprint_sha256": (
            result.scorer_contract_fingerprint_sha256
        ),
        "refiner_contract_fingerprint_sha256": (
            result.refiner_contract_fingerprint_sha256
        ),
        "score_descriptor": result.score_descriptor.to_dict(),
        "validity_context_fingerprint_sha256": (
            result.validity_context_fingerprint_sha256
        ),
        "unbound_validity_compatibility": unbound_compatibility,
        "diversity_metric": result.diversity_metric,
        "diversity_rmsd_angstrom_binary64_hex": threshold.hex(),
        "symmetry_permutation_count": len(canonical_permutations),
        "symmetry_permutations": {
            "atom_count": atom_count,
            "mappings": [
                list(permutation) for permutation in canonical_permutations
            ],
        },
        "problem_fingerprint_sha256": result.problem_fingerprint_sha256,
        "search_space_fingerprint_sha256": (
            result.search_space_fingerprint_sha256
        ),
        "proposal_fingerprints": [
            row.proposal_fingerprint_sha256 for row in result.rows
        ],
    }


def recompute_search_fingerprint_sha256(result: object) -> str:
    """Recompute schema-v6 search identity from one retained result object."""

    material = _material_from_result(result)
    observed = _sha256(material)
    if observed != result.search_fingerprint_sha256:
        raise SearchFingerprintMaterialError(
            "retained search fingerprint does not match its public material"
        )
    return observed


def install_search_fingerprint_material() -> str:
    """Install schema-v6 material around the final active search function."""

    marker = "_betelgeuze_search_fingerprint_material_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from betelgeuze_engine_v2 import docking as docking_package
    from betelgeuze_engine_v2.docking import search as search_module

    active_run = search_module.run_bounded_docking_search
    result_class = search_module.DockingSearchResult
    original_to_dict = result_class.to_dict

    if getattr(active_run, "_betelgeuze_search_material_v6", False):
        installed = getattr(sys, marker, None)
        if isinstance(installed, str):
            return installed
        raise SearchFingerprintMaterialError(
            "search material wrapper is installed without its receipt"
        )

    def run_bounded_docking_search(
        search_space: object,
        budget: object,
        scorer: object,
        *,
        refiner: object | None = None,
        validity_context: object | None = None,
        diversity_rmsd_angstrom: float = 0.5,
        diversity_metric: str = "direct_rmsd",
        symmetry_permutations: Sequence[
            Sequence[int] | torch.Tensor
        ] | None = None,
        problem: object | None = None,
    ) -> object:
        threshold = float(diversity_rmsd_angstrom)
        problem_identity = problem or search_module.DockingProblemIdentity.unbound()
        if not isinstance(problem_identity, search_module.DockingProblemIdentity):
            raise TypeError("problem must be DockingProblemIdentity")
        canonical_permutations = (
            ()
            if symmetry_permutations is None
            else search_module._canonicalize_symmetry_permutations(
                symmetry_permutations,
                atom_count=search_space.atom_count,
            )
        )
        unbound_compatibility = bool(
            validity_context is None and not problem_identity.bound
        )
        result = active_run(
            search_space,
            budget,
            scorer,
            refiner=refiner,
            validity_context=validity_context,
            diversity_rmsd_angstrom=threshold,
            diversity_metric=diversity_metric,
            symmetry_permutations=symmetry_permutations,
            problem=problem,
        )
        object.__setattr__(
            result,
            "_search_material_atom_count",
            int(search_space.atom_count),
        )
        object.__setattr__(
            result,
            "_search_material_diversity_threshold",
            threshold,
        )
        object.__setattr__(
            result,
            "_search_material_unbound_validity_compatibility",
            unbound_compatibility,
        )
        object.__setattr__(
            result,
            "_search_material_symmetry_permutations",
            tuple(canonical_permutations),
        )
        material = _material_from_result(result)
        object.__setattr__(
            result,
            "search_fingerprint_sha256",
            _sha256(material),
        )
        recompute_search_fingerprint_sha256(result)
        return result

    run_bounded_docking_search._betelgeuze_search_material_v6 = True

    def search_fingerprint_material(self) -> dict[str, object]:
        material = _material_from_result(self)
        recompute_search_fingerprint_sha256(self)
        return material

    def result_to_dict(self) -> dict[str, object]:
        document = dict(original_to_dict(self))
        has_material = [hasattr(self, name) for name in _SEARCH_MATERIAL_ATTRIBUTES]
        if not any(has_material):
            document["schema_id"] = (
                "betelgeuze.engine_v2_docking_search_result/1.0.0"
            )
            document["search_fingerprint_fully_recomputable"] = False
            return document
        if not all(has_material):
            raise SearchFingerprintMaterialError(
                "docking search result has incomplete fingerprint material"
            )
        # Once schema-v6 material exists, every mismatch is evidence tampering or
        # corruption and must propagate. It must never silently downgrade to a
        # legacy non-recomputable document.
        material = search_fingerprint_material(self)
        document.update(
            {
                "schema_id": DOCKING_SEARCH_RESULT_SCHEMA_ID,
                "search_fingerprint_schema_id": (
                    DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID
                ),
                "search_fingerprint_material": material,
                "search_fingerprint_fully_recomputable": True,
                "selected_count": len(self.top_rows),
                "scientifically_validated": False,
                "product_qualified": False,
                "customer_execution_enabled": False,
                "claim_safe": False,
            }
        )
        return document

    result_class.search_fingerprint_material = property(
        search_fingerprint_material
    )
    result_class.to_dict = result_to_dict
    search_module.run_bounded_docking_search = run_bounded_docking_search
    docking_package.run_bounded_docking_search = run_bounded_docking_search
    for loaded in tuple(sys.modules.values()):
        if loaded is not None and getattr(
            loaded,
            "run_bounded_docking_search",
            None,
        ) is active_run:
            setattr(
                loaded,
                "run_bounded_docking_search",
                run_bounded_docking_search,
            )

    receipt = _sha256(
        {
            "schema_id": SEARCH_FINGERPRINT_MATERIAL_INSTALLER_SCHEMA_ID,
            "search_fingerprint_schema_id": (
                DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID
            ),
            "search_result_schema_id": DOCKING_SEARCH_RESULT_SCHEMA_ID,
            "diversity_threshold_exactly_bound": True,
            "canonical_symmetry_mappings_exposed": True,
            "offline_recomputation_supported": True,
            "material_mismatch_fails_closed": True,
            "candidate_execution_reimplemented": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID",
    "DOCKING_SEARCH_RESULT_SCHEMA_ID",
    "SEARCH_FINGERPRINT_MATERIAL_INSTALLER_SCHEMA_ID",
    "SearchFingerprintMaterialError",
    "install_search_fingerprint_material",
    "recompute_search_fingerprint_sha256",
]
