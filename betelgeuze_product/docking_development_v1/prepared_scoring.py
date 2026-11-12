"""Prepared-chemistry adapters around the unchanged Engine v2 contracts.

Only complete-graph feature perception and the resulting bound contexts differ.
The engine owns scoring arithmetic, geometry, proposal generation and limits.
No process-global function or class is replaced.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json

from betelgeuze_engine_v2.docking import guided_placement as _guidance
from betelgeuze_engine_v2.docking import scorer_v1 as _scoring
from betelgeuze_engine_v2.docking.authority import DockingAuthorityError
from betelgeuze_engine_v2.molecular import AllAtomSystem

from .chemistry_features import (
    FULL_TOPOLOGY_FEATURE_POLICY_ID,
    perceive_full_topology_features,
    require_matching_feature_policies,
    uses_full_topology_features,
)


def _sha(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _init_values(value, base):
    return {
        field.name: getattr(value, field.name) for field in fields(base) if field.init
    }


def _uses_prepared_pair(receptor, ligand):
    for name, system in (("receptor_system", receptor), ("ligand_system", ligand)):
        if not isinstance(system, AllAtomSystem):
            raise TypeError(f"{name} must be AllAtomSystem")
    require_matching_feature_policies(receptor, ligand)
    return uses_full_topology_features(receptor)


def _features(system, allowed):
    if not uses_full_topology_features(system):
        return _scoring._features(system, allowed)
    features = perceive_full_topology_features(system, allowed_indices=allowed)
    return features.donor_pairs, features.acceptors, features.hydrophobic


def _feature_indices(system, *, allowed_indices=None):
    if not uses_full_topology_features(system):
        return _guidance._feature_indices(system, allowed_indices=allowed_indices)
    features = perceive_full_topology_features(
        system, allowed_indices=allowed_indices
    ).guidance_indices()
    if any(
        len(rows) > _guidance.MAX_GUIDED_FEATURE_ATOMS for rows in features.values()
    ):
        raise DockingAuthorityError("guided feature atom count exceeds its hard bound")
    return features


@dataclass(frozen=True, slots=True)
class PreparedScorerContext(_scoring.ScorerV1Context):
    feature_policy_id: str = FULL_TOPOLOGY_FEATURE_POLICY_ID

    def __post_init__(self):
        if self.feature_policy_id != FULL_TOPOLOGY_FEATURE_POLICY_ID:
            raise _scoring.ScorerV1Error("unsupported prepared scorer feature policy")
        _scoring.ScorerV1Context.__post_init__(self)

    def _projection(self):
        return {
            **_scoring.ScorerV1Context._projection(self),
            "schema_id": "betelgeuze.product_prepared_scorer_context/1.0.0",
            "feature_policy_id": self.feature_policy_id,
        }


class ChemistryPoseScorerV1(_scoring.ChemistryPoseScorerV1):
    """Legacy numerical scorer plus an opt-in Python prepared-feature adapter."""

    def __init__(
        self,
        authority,
        receptor_system,
        ligand_system,
        *,
        implementation_source_sha256,
        config=None,
        backend=_scoring.ScorerBackend.PYTHON_REFERENCE,
        backend_options=None,
        backend_receipt=None,
    ):
        prepared = _uses_prepared_pair(receptor_system, ligand_system)
        if prepared and backend != _scoring.ScorerBackend.PYTHON_REFERENCE:
            raise _scoring.ScorerV1Error(
                "prepared feature policy supports the Python reference backend only"
            )
        super().__init__(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            config=config,
            backend=backend,
            backend_options=backend_options,
            backend_receipt=backend_receipt,
        )
        if not prepared:
            return
        values = _init_values(self.context, _scoring.ScorerV1Context)
        positions = {
            index: offset
            for offset, index in enumerate(authority.receptor_atom_indices)
        }
        receptor = _features(receptor_system, set(positions))
        ligand = _features(ligand_system, set(range(ligand_system.atom_count)))
        values.update(
            receptor_donors=tuple((positions[d], positions[h]) for d, h in receptor[0]),
            ligand_donors=ligand[0],
            receptor_acceptors=tuple(positions[i] for i in receptor[1]),
            ligand_acceptors=ligand[1],
            receptor_hydrophobic=tuple(positions[i] for i in receptor[2]),
            ligand_hydrophobic=ligand[2],
        )
        self._context = PreparedScorerContext(**values)
        self._receptor_hydrophobic = frozenset(self.context.receptor_hydrophobic)
        self._ligand_hydrophobic = frozenset(self.context.ligand_hydrophobic)
        self._ligand_acceptors = frozenset(self.context.ligand_acceptors)
        self._ligand_donor_heavy = frozenset(d for d, _ in self.context.ligand_donors)
        self.scorer_id = "betelgeuze.product_prepared_chemistry_pose_scorer"
        self.scorer_version = "1.0.0"
        self._assert_bound_state()

    @property
    def config_fingerprint_sha256(self):
        if not isinstance(self.context, PreparedScorerContext):
            return super().config_fingerprint_sha256
        return _sha(
            {
                "base_config_sha256": self.config.fingerprint_sha256,
                "prepared_context_sha256": self.context.fingerprint_sha256,
                "feature_policy_id": self.context.feature_policy_id,
            }
        )

    def _assert_bound_state(self):
        super()._assert_bound_state()
        if isinstance(self.context, PreparedScorerContext) and (
            self._native_context is not None
            or self._receptor_hydrophobic
            != frozenset(self.context.receptor_hydrophobic)
            or self._ligand_hydrophobic != frozenset(self.context.ligand_hydrophobic)
            or self._ligand_acceptors != frozenset(self.context.ligand_acceptors)
            or self._ligand_donor_heavy
            != frozenset(d for d, _ in self.context.ligand_donors)
        ):
            raise _scoring.ScorerV1Error("prepared scorer feature caches changed")


@dataclass(frozen=True, slots=True)
class PreparedGuidedPlacementContext(_guidance.GuidedPlacementContext):
    feature_policy_id: str = FULL_TOPOLOGY_FEATURE_POLICY_ID

    def __post_init__(self):
        if self.feature_policy_id != FULL_TOPOLOGY_FEATURE_POLICY_ID:
            raise DockingAuthorityError("unsupported prepared guidance feature policy")
        # Reuse the sealed context's structural normalization and bounds on a
        # temporary value. It never escapes or authorizes proposal generation;
        # this subclass owns and fingerprints the explicit new feature policy.
        values = _init_values(self, _guidance.GuidedPlacementContext)
        values.pop("feature_policy_id")
        normalized = _guidance.GuidedPlacementContext(**values)
        for name, value in _init_values(
            normalized, _guidance.GuidedPlacementContext
        ).items():
            if name != "feature_policy_id":
                object.__setattr__(self, name, value)
        object.__setattr__(self, "_fingerprint_sha256", _sha(self._projection()))

    def _projection(self):
        return {
            **_guidance.GuidedPlacementContext._projection(self),
            "schema_id": "betelgeuze.product_prepared_guidance_context/1.0.0",
        }


def build_guided_placement_context(authority, receptor_system, ligand_system):
    prepared = _uses_prepared_pair(receptor_system, ligand_system)
    base = _guidance.build_guided_placement_context(
        authority, receptor_system, ligand_system
    )
    if not prepared:
        return base
    allowed = set(authority.receptor_atom_indices)
    receptor = _feature_indices(receptor_system, allowed_indices=allowed)
    ligand = _feature_indices(ligand_system)
    coordinates = receptor_system.coordinates[authority.receptor_model_index]
    values = _init_values(base, _guidance.GuidedPlacementContext)
    values.update(
        feature_policy_id=FULL_TOPOLOGY_FEATURE_POLICY_ID,
        ligand_features=ligand,
        receptor_feature_rows={
            name: tuple(
                (
                    index,
                    _guidance._coordinates_tuple(coordinates[index]),
                    receptor_system.atoms[index].formal_charge,
                )
                for index in indices
            )
            for name, indices in receptor.items()
        },
        ligand_hydrophobic_patches=_guidance._hydrophobic_patches(
            ligand_system, ligand["hydrophobic"]
        ),
        receptor_hydrophobic_patches=tuple(
            (patch, _guidance._coordinates_tuple(coordinates[list(patch)].mean(dim=0)))
            for patch in _guidance._hydrophobic_patches(
                receptor_system, receptor["hydrophobic"], allowed_indices=allowed
            )
        ),
    )
    return PreparedGuidedPlacementContext(**values)


def generate_guided_docking_proposals(
    authority, budget, context, *, receptor_system, ligand_system, policy=None
):
    if not _uses_prepared_pair(receptor_system, ligand_system):
        return _guidance.generate_guided_docking_proposals(
            authority,
            budget,
            context,
            receptor_system=receptor_system,
            ligand_system=ligand_system,
            policy=policy,
        )
    from .prepared_guidance import generate_prepared_docking_proposals

    return generate_prepared_docking_proposals(
        authority,
        budget,
        context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        policy=policy,
    )


def run_authenticated_scorer_v1_guided_search(
    authority,
    budget,
    scorer,
    context,
    *,
    receptor_system,
    ligand_system,
    refiner=None,
    guided_policy=None,
    diversity_rmsd_angstrom=0.5,
    diversity_metric="direct_rmsd",
    symmetry_permutations=None,
):
    """Own prepared context rederivation through generation, search and evidence.

    Source-paired rescue and precomputed conformer protocols are separate lanes;
    this adapter accepts the ordinary bounded guided policy only.
    """
    if not _uses_prepared_pair(receptor_system, ligand_system):
        return _scoring.run_authenticated_scorer_v1_guided_search(
            authority,
            budget,
            scorer,
            context,
            receptor_system=receptor_system,
            ligand_system=ligand_system,
            refiner=refiner,
            guided_policy=guided_policy,
            diversity_rmsd_angstrom=diversity_rmsd_angstrom,
            diversity_metric=diversity_metric,
            symmetry_permutations=symmetry_permutations,
        )
    if not isinstance(scorer, ChemistryPoseScorerV1) or not isinstance(
        scorer.context, PreparedScorerContext
    ):
        raise _scoring.ScorerV1Error("prepared scoring context is required")
    if scorer.authority_input_receipt_sha256 != authority.input_receipt_sha256:
        raise _scoring.ScorerV1Error("prepared scorer authority is cross-wired")
    proposals, receipt = generate_guided_docking_proposals(
        authority,
        budget,
        context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        policy=guided_policy,
    )
    # This is the engine's existing context-local proposal transport. No engine
    # function/global is replaced, and the override is reset even after failure.
    override = _guidance._ProposalOverride(
        search_space_fingerprint_sha256=authority.search_space.fingerprint_sha256,
        budget_sha256=_guidance._budget_sha256(budget),
        problem_fingerprint_sha256=authority.problem.fingerprint_sha256,
        proposals=proposals,
    )
    token = _guidance._PROPOSAL_OVERRIDE.set(override)
    try:
        from betelgeuze_engine_v2.docking.authority import (
            run_authenticated_bounded_docking_search,
        )

        search = run_authenticated_bounded_docking_search(
            authority,
            budget,
            scorer,
            refiner=refiner,
            diversity_rmsd_angstrom=diversity_rmsd_angstrom,
            diversity_metric=diversity_metric,
            symmetry_permutations=symmetry_permutations,
        )
    finally:
        _guidance._PROPOSAL_OVERRIDE.reset(token)
    guided = _guidance.GuidedPlacementSearchResult(
        guided_receipt=receipt, authenticated_search_result=search
    )
    retained = []
    for row in search.search_result.rows:
        terms = row.score_evidence if row.succeeded else None
        if row.succeeded and (
            row.proposal is None
            or row.score is None
            or not isinstance(terms, _scoring.ScorerV1Terms)
        ):
            raise _scoring.ScorerV1Error("prepared score row lacks typed evidence")
        retained.append(
            _scoring.ScorerV1SearchTermRow(
                candidate_id=row.candidate_id,
                proposal_index=row.proposal_index,
                search_status=row.status,
                search_row_sha256=_scoring._row_sha256(row),
                score=float(row.score) if row.succeeded else None,
                selection_eligible=row.selection_eligible,
                terms=terms,
                **({"error_code": row.error_code} if not row.succeeded else {}),
            )
        )
    return _scoring.ScorerV1GuidedSearchResult(
        guided_search_result=guided,
        scorer=scorer,
        scorer_contract_fingerprint_sha256=scorer.contract_fingerprint_sha256,
        scorer_authority_input_receipt_sha256=scorer.authority_input_receipt_sha256,
        scorer_context_fingerprint_sha256=scorer.context.fingerprint_sha256,
        scorer_config_fingerprint_sha256=scorer.config.fingerprint_sha256,
        rows=tuple(retained),
    )
