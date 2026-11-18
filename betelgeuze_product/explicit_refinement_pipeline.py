"""Opt-in, typed docking consumers for retained V9 and explicit physical models.

The product layer depends on engine contracts, never the reverse. No default
V7 profile, sealed recorder, parameter perception, or scientific claim changes.
Each source retains at most its baseline and one refined candidate; both are
independently scored and validated before the stable bounded Top-K selection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking.authority import AuthenticatedDockingProblem
from betelgeuze_engine_v2.docking.guided_placement import (
    GuidedPlacementContext,
    GuidedPlacementPolicy,
)
from betelgeuze_engine_v2.docking.proposals import (
    DockingBudget,
    DockingProposal,
    generate_bounded_docking_proposals,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
from betelgeuze_engine_v2.docking.scoring import score_sort_key
from .docking_development_v1.prepared_scoring import (
    ChemistryPoseScorerV1,
    PreparedGuidedPlacementContext,
    generate_guided_docking_proposals,
)
from .docking_development_v1.refinement_work import refinement_work_records
from .docking_development_v1.torsion_refinement_v9 import (
    InteractionAwareTorsionContactEnsembleRefinerV9,
    TorsionRefinementBoundsV9,
)
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    ReferenceForceFieldV2Parameters,
)

from .cpu_refinement_fourier_v1.parameters import FourierParameters
from .cpu_refinement_fourier_v1.evaluation import FourierCrossParameters
from .cpu_refinement_v1_2.fixed_receptor import CrossParameters
from .cpu_refinement_v1_2.provenance import environment
from .fixed_receptor_structure_refinement import (
    FixedReceptorEnergyForceProvider,
    FixedReceptorStructureCoordinator,
)
from .structure_preserving import SearchConfig
from .structure_preserving_refinement import StructureRefinementError


PIPELINE_ID = "betelgeuze.explicit_retained_refinement_docking/1.0.0"
MAX_SOURCE_CANDIDATES = 64
MAX_RETAINED_CANDIDATES = 128


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _json(value):
    return json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _sha(value):
    return hashlib.sha256(_json(value).encode("ascii")).hexdigest()


def implementation_sources():
    """Extend the owning numerical inventory, including actual E/F and geometry."""
    from .cpu_refinement_fourier_v1.minimization import (
        implementation_sources as numerical_sources,
    )
    from . import (
        structure_preserving,
        structure_preserving_refinement,
        fixed_receptor_structure_refinement,
    )

    modules = (
        structure_preserving,
        structure_preserving_refinement,
        fixed_receptor_structure_refinement,
    )
    sources = numerical_sources()
    for module in modules:
        sources[module.__name__.replace(".", "/") + ".py"] = hashlib.sha256(
            Path(module.__file__).read_bytes()
        ).hexdigest()
    sources[__name__.replace(".", "/") + ".py"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    product_root = Path(__file__).resolve().parent
    for path in sorted((product_root / "docking_development_v1").rglob("*.py")):
        sources["betelgeuze_product/" + path.relative_to(product_root).as_posix()] = (
            hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return dict(sorted(sources.items()))


def implementation_source_sha256():
    return _sha(implementation_sources())


@dataclass(frozen=True)
class RetainedCandidateV1:
    role: str
    proposal: DockingProposal
    policy_admissible: bool
    policy_rejections: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            self.role not in {"baseline", "refined"}
            or type(self.proposal) is not DockingProposal
        ):
            raise StructureRefinementError("typed retained candidate required")
        self.proposal.assert_integrity()
        if type(self.policy_admissible) is not bool or self.policy_admissible != (
            not self.policy_rejections
        ):
            raise StructureRefinementError("candidate policy admission mismatch")


@dataclass(frozen=True)
class ContactRefinementProviderV9:
    """All source indices may refine because this consumer retains each baseline."""

    bounds: TorsionRefinementBoundsV9 = field(default_factory=TorsionRefinementBoundsV9)

    def __post_init__(self):
        if type(self.bounds) is not TorsionRefinementBoundsV9:
            raise TypeError("exact V9 bounds required")

    def build(self, authority, ligand, receptor, budget, source):
        return InteractionAwareTorsionContactEnsembleRefinerV9(
            authority,
            receptor,
            ligand,
            implementation_source_sha256=source,
            v3_proposal_indices=tuple(range(budget.candidate_count)),
            bounds=self.bounds,
        )


@dataclass(frozen=True)
class FixedReceptorStructureProviderV1:
    """Explicit parameter/cross-parameter authority; no automatic force field."""

    parameters: ReferenceForceFieldV2Parameters | FourierParameters
    cross_parameters: CrossParameters | FourierCrossParameters
    config: SearchConfig = field(default_factory=SearchConfig)

    def __post_init__(self):
        legacy = (
            type(self.parameters) is ReferenceForceFieldV2Parameters
            and type(self.cross_parameters) is CrossParameters
        )
        fourier = (
            type(self.parameters) is FourierParameters
            and type(self.cross_parameters) is FourierCrossParameters
        )
        if not (legacy or fourier) or type(self.config) is not SearchConfig:
            raise StructureRefinementError(
                "explicit matching parameter, cross-parameter and solver authority required"
            )

    def build(self, authority, ligand, receptor, budget, source):
        if budget.max_refinement_steps > self.config.max_steps:
            raise StructureRefinementError(
                "docking step budget exceeds explicit solver bound"
            )
        capacity = budget.candidate_count * self.config.max_evaluations
        if capacity > 100_000:
            raise StructureRefinementError(
                "aggregate physical callback capacity exceeds supported bound"
            )
        provider = FixedReceptorEnergyForceProvider(
            authority,
            ligand,
            receptor,
            self.parameters,
            self.cross_parameters,
            implementation_source_sha256=source,
            max_evaluations=capacity,
        )
        coordinator = FixedReceptorStructureCoordinator(
            authority,
            ligand,
            provider,
            implementation_source_sha256=source,
            config=self.config,
            max_attempts=budget.candidate_count,
        )
        return FixedReceptorStructureDockingRefinerV1(coordinator, provider)


class FixedReceptorStructureDockingRefinerV1:
    """A DockingPoseRefiner with typed final-admission and E/F evidence.

    Generic docking callers use refine(), which fails on rejected final admission.
    The retained consumer uses refine_candidates() to retain the evaluated baseline
    and to exclude an inadmissible endpoint independently from pose validity.
    """

    refiner_id = "betelgeuze.explicit_fixed_receptor_structure_docking_refiner"
    refiner_version = "1.0.0"

    def __init__(self, coordinator, provider):
        if (
            type(coordinator) is not FixedReceptorStructureCoordinator
            or type(provider) is not FixedReceptorEnergyForceProvider
        ):
            raise StructureRefinementError(
                "exact coordinator and physical provider required"
            )
        self._coordinator, self._provider = coordinator, provider
        self._identity = self._current_identity()
        self._receipts = {}
        self._work = {}

    def _current_identity(self):
        return {
            "refiner_id": self.refiner_id,
            "refiner_version": self.refiner_version,
            **self._coordinator.binding_identity(provider=self._provider),
        }

    def assert_ready(self):
        if self._current_identity() != self._identity:
            raise StructureRefinementError("docking adapter binding changed")

    @property
    def problem_fingerprint_sha256(self):
        self.assert_ready()
        return self._identity["problem"]

    @property
    def implementation_source_sha256(self):
        self.assert_ready()
        return self._identity["source"]

    @property
    def config_fingerprint_sha256(self):
        self.assert_ready()
        return _sha({"adapter": self.refiner_id, **self._identity})

    @property
    def receipts(self):
        return MappingProxyType(
            {key: json.loads(value) for key, value in self._receipts.items()}
        )

    @property
    def work(self):
        return MappingProxyType(
            {key: json.loads(value) for key, value in self._work.items()}
        )

    def refine_candidates(self, proposal, *, max_steps):
        self.assert_ready()
        proposal.assert_integrity()
        source = proposal.fingerprint_sha256
        if source in self._work:
            raise StructureRefinementError("physical docking source already attempted")
        before = (
            self._provider.evaluation_attempts,
            self._provider.physical_evaluation_attempts,
            self._provider.graph_build_attempts,
            self._provider.recoverable_rejections,
        )
        try:
            outcome = self._coordinator.run(proposal, max_steps=max_steps)
        finally:
            after = (
                self._provider.evaluation_attempts,
                self._provider.physical_evaluation_attempts,
                self._provider.graph_build_attempts,
                self._provider.recoverable_rejections,
            )
            names = (
                "provider_admitted_attempts",
                "physical_evaluation_attempts",
                "graph_build_attempts",
                "recoverable_rejections",
            )
            attempt = self._coordinator.attempts.get(source)
            self._work[source] = _json(
                {
                    **dict(
                        zip(
                            names,
                            (a - b for a, b in zip(after, before, strict=True)),
                            strict=True,
                        )
                    ),
                    "objective_callback_attempts": 0
                    if attempt is None
                    else attempt.result.evaluation_attempts,
                    "evaluated_accepted_steps": 0
                    if attempt is None
                    else attempt.result.accepted_steps,
                    "selected_path_steps": 0,
                }
            )
        self.assert_ready()
        attempt = outcome.optimizer_attempt
        result = attempt.result
        work = json.loads(self._work[source])
        work["selected_path_steps"] = result.accepted_steps if outcome.admissible else 0
        work["selected_path_scope"] = (
            "admissible_optimizer_endpoint_before_pipeline_ranking"
        )
        self._work[source] = _json(work)
        receipt = {
            "schema_id": "betelgeuze.fixed_receptor_structure_docking_receipt/1.0.0",
            "source_proposal_sha256": source,
            "model_fingerprint_sha256": self._identity["model"],
            "authority_input_receipt_sha256": self._identity["authority"],
            "optimizer_attempt_sha256": attempt.receipt_sha256,
            "optimizer_attempt": asdict(attempt),
            "initial_observation": asdict(outcome.initial_observation),
            "final_observation": asdict(outcome.final_observation),
            "final_admission": outcome.admission_document(),
            "final_rejection_reasons": list(outcome.rejection_reasons),
            "projected_stationary": result.projected_stationary,
            "cartesian_converged": False,
            "scientifically_validated": False,
        }
        digest = _sha(receipt)
        receipt["receipt_sha256"] = digest
        self._receipts[source] = _json(receipt)

        def bind(coordinates, torsions):
            return proposal.with_refined_coordinates(
                coordinates,
                refiner_id=self.refiner_id,
                refiner_version=self.refiner_version,
                refinement_receipt_sha256=digest,
                torsion_angles=torsions,
            )

        baseline = RetainedCandidateV1(
            "baseline", bind(proposal.coordinates, proposal.torsion_angles), True
        )
        refined = RetainedCandidateV1(
            "refined",
            bind(outcome.proposal.coordinates, outcome.proposal.torsion_angles),
            outcome.admissible,
            outcome.rejection_reasons,
        )
        return (baseline, refined)

    def refine(self, proposal, *, max_steps):
        candidate = self.refine_candidates(proposal, max_steps=max_steps)[-1]
        if not candidate.policy_admissible:
            raise StructureRefinementError(
                "physical final-admission policy rejected refinement"
            )
        return candidate.proposal


@dataclass(frozen=True)
class ExplicitRefinementResultV1:
    """Canonical immutable evidence; coordinates remain in the complete document."""

    canonical_document: str

    def __post_init__(self):
        document = json.loads(self.canonical_document)
        if (
            _json(document) != self.canonical_document
            or document.get("pipeline_id") != PIPELINE_ID
        ):
            raise StructureRefinementError(
                "canonical explicit refinement result required"
            )
        if (
            _sha(document["implementation_sources"])
            != document["implementation_source_sha256"]
        ):
            raise StructureRefinementError("implementation source inventory mismatch")
        sources = document["source_candidate_count"]
        if not 1 <= sources <= MAX_SOURCE_CANDIDATES:
            raise StructureRefinementError("source denominator exceeds pipeline bounds")
        if (
            len(document["source_outcomes"]) != sources
            or len(document["candidates"]) > 2 * sources
        ):
            raise StructureRefinementError("retained candidate denominator mismatch")
        if (
            document.get("scientifically_validated") is not False
            or document.get("accuracy_claim") is not False
            or not document.get("claim_blockers")
        ):
            raise StructureRefinementError(
                "explicit refinement result cannot carry an accuracy claim"
            )
        outcomes = document["source_outcomes"]
        if [row["source_proposal_index"] for row in outcomes] != list(range(sources)):
            raise StructureRefinementError("source outcome identities are incomplete")
        selected = [tuple(value) for value in document["selected_candidates"]]
        if len(selected) > document["budget"]["top_k"] or len(set(selected)) != len(
            selected
        ):
            raise StructureRefinementError(
                "selected retained candidate capacity mismatch"
            )
        observed, per_source = set(), [0] * sources
        for row in document["candidates"]:
            index, ordinal = row["source_proposal_index"], row["ordinal"]
            if (
                type(index) is not int
                or not 0 <= index < sources
                or type(ordinal) is not int
                or ordinal not in {0, 1}
                or (index, ordinal) in observed
                or row["role"] != ("baseline" if ordinal == 0 else "refined")
            ):
                raise StructureRefinementError("invalid retained candidate identity")
            observed.add((index, ordinal))
            per_source[index] += 1
            if (
                row["source_proposal_sha256"]
                != outcomes[index]["source_proposal_sha256"]
            ):
                raise StructureRefinementError(
                    "retained source identity is cross-wired"
                )
            identity = row["proposal_identity"]
            if (
                _sha(identity) != row["proposal_sha256"]
                or identity["parent_proposal_fingerprint_sha256"]
                != row["source_proposal_sha256"]
            ):
                raise StructureRefinementError("retained proposal identity mismatch")
            xyz = row["coordinates_binary64_hex"]
            if not 1 <= len(xyz) <= 512 or any(len(point) != 3 for point in xyz):
                raise StructureRefinementError("invalid retained coordinate shape")
            values = [value for point in xyz for value in point]
            if any(
                not isinstance(value, str)
                or not math.isfinite(float.fromhex(value))
                or float.fromhex(value).hex() != value
                for value in values
            ):
                raise StructureRefinementError("invalid retained coordinate values")
            coordinate_sha = _sha(
                {
                    "schema_id": "betelgeuze.engine_v2_pose_coordinates/1.1.0",
                    "coordinates": {"shape": [len(xyz), 3], "values_hex": values},
                }
            )
            if coordinate_sha != identity["coordinate_fingerprint_sha256"]:
                raise StructureRefinementError(
                    "retained coordinates do not match their identity"
                )
            eligible = (
                row["status"] == "success"
                and row["policy_admissible"]
                and row["pose_validity"]["complete"]
                and row["pose_validity"]["valid"]
            )
            if row["selection_eligible"] != eligible or row["selected"] != (
                (index, ordinal) in selected
            ):
                raise StructureRefinementError(
                    "retained candidate eligibility mismatch"
                )
            if row["selected"] and not eligible:
                raise StructureRefinementError(
                    "invalid retained candidate was selected"
                )
        if set(selected) - observed or any(
            row["retained_count"] != count
            for row, count in zip(outcomes, per_source, strict=True)
        ):
            raise StructureRefinementError("retained candidate denominator mismatch")

    def to_dict(self):
        return json.loads(self.canonical_document)

    @property
    def receipt_sha256(self):
        return hashlib.sha256(self.canonical_document.encode("ascii")).hexdigest()


def _failure(exc):
    receipt = failure_receipt(
        exc, public_message="explicit refinement candidate failed"
    )
    return {
        "error_code": receipt.public_error_code,
        "private_error_sha256": receipt.private_error_sha256,
        "private_error_byte_length": receipt.private_error_byte_length,
    }


def _provider_identity(provider):
    if type(provider) is ContactRefinementProviderV9:
        provider.__post_init__()
        return {
            "type": type(provider).__name__,
            "bounds": provider.bounds.fingerprint_sha256,
        }
    if type(provider) is FixedReceptorStructureProviderV1:
        # Revalidate exact parameter types even after low-level object mutation.
        provider.__post_init__()
        return {
            "type": type(provider).__name__,
            "parameters": provider.parameters.fingerprint_sha256,
            "cross_parameters": provider.cross_parameters.fingerprint_sha256,
            "config": asdict(provider.config),
        }
    raise StructureRefinementError(
        "exact supported explicit refinement provider required"
    )


class ExplicitRefinementDockingPipelineV1:
    """Bounded opt-in API: prepare authority/parameters first, then dock and rank."""

    def __init__(self, provider):
        self.provider = provider
        self._provider_snapshot = _json(_provider_identity(provider))

    def run(
        self,
        authority,
        ligand,
        receptor,
        budget,
        *,
        guided_context=None,
        guided_policy=None,
    ):
        if _json(_provider_identity(self.provider)) != self._provider_snapshot:
            raise StructureRefinementError(
                "pipeline provider changed after construction"
            )
        if (
            type(authority) is not AuthenticatedDockingProblem
            or type(budget) is not DockingBudget
        ):
            raise StructureRefinementError(
                "exact docking authority and budget required"
            )
        if (
            not 1 <= budget.candidate_count <= MAX_SOURCE_CANDIDATES
            or not 1 <= budget.max_refinement_steps <= 128
        ):
            raise StructureRefinementError(
                "explicit refinement pipeline budget exceeds supported bounds"
            )
        authority_sha = authority.input_receipt_sha256
        if (
            canonical_system_sha256(ligand) != authority.ligand_system_sha256
            or canonical_system_sha256(receptor) != authority.receptor_system_sha256
        ):
            raise StructureRefinementError("pipeline source systems are cross-wired")
        if guided_context is None and guided_policy is not None:
            raise StructureRefinementError(
                "guided policy requires a bound guided context"
            )
        source_files = implementation_sources()
        source = _sha(source_files)
        execution_environment = environment()
        refiner = self.provider.build(authority, ligand, receptor, budget, source)
        scorer = ChemistryPoseScorerV1(
            authority, receptor, ligand, implementation_source_sha256=source
        )
        if guided_context is None:
            proposals = generate_bounded_docking_proposals(
                authority.search_space,
                budget,
                problem=authority.problem,
                placement_center=authority.pocket.center,
            )
            generation = {"mode": "authenticated_uniform_bounded"}
        else:
            if type(guided_context) not in (
                GuidedPlacementContext,
                PreparedGuidedPlacementContext,
            ) or (
                guided_policy is not None
                and type(guided_policy) is not GuidedPlacementPolicy
            ):
                raise StructureRefinementError("exact guided context/policy required")
            proposals, receipt = generate_guided_docking_proposals(
                authority,
                budget,
                guided_context,
                receptor_system=receptor,
                ligand_system=ligand,
                policy=guided_policy,
            )
            generation = {
                "mode": "authenticated_guided_bounded",
                "receipt_sha256": receipt.receipt_sha256,
            }
        if len(proposals) != budget.candidate_count or tuple(
            proposal.proposal_index for proposal in proposals
        ) != tuple(range(budget.candidate_count)):
            raise StructureRefinementError(
                "proposal generation changed its declared denominator"
            )
        source_outcomes, candidates = [], []
        for proposal in proposals:
            source_sha = proposal.fingerprint_sha256
            source_rows = []
            try:
                if type(refiner) is InteractionAwareTorsionContactEnsembleRefinerV9:
                    refiner.refine(proposal, max_steps=budget.max_refinement_steps)
                    retained = tuple(
                        RetainedCandidateV1(
                            "baseline" if i == 0 else "refined", value, True
                        )
                        for i, value in enumerate(refiner.retained_candidates(proposal))
                    )
                else:
                    retained = refiner.refine_candidates(
                        proposal, max_steps=budget.max_refinement_steps
                    )
                proposal.assert_integrity()
                if (
                    proposal.fingerprint_sha256 != source_sha
                    or not 1 <= len(retained) <= 2
                ):
                    raise StructureRefinementError(
                        "refiner changed source identity or candidate capacity"
                    )
                before = tuple(value.proposal.fingerprint_sha256 for value in retained)
                identity_snapshots = tuple(
                    value.proposal.identity_payload() for value in retained
                )
                coordinate_snapshots = tuple(
                    [
                        [float(x).hex() for x in xyz]
                        for xyz in value.proposal.coordinates.tolist()
                    ]
                    for value in retained
                )
                scores = scorer.score_batch(tuple(value.proposal for value in retained))
                if len(scores) != len(retained):
                    raise StructureRefinementError(
                        "retained score denominator mismatch"
                    )
                for ordinal, (candidate, outcome, fingerprint) in enumerate(
                    zip(retained, scores, before, strict=True)
                ):
                    pose = candidate.proposal
                    row = {
                        "source_proposal_index": proposal.proposal_index,
                        "ordinal": ordinal,
                        "role": candidate.role,
                        "source_proposal_sha256": source_sha,
                        "proposal_sha256": fingerprint,
                        "policy_admissible": candidate.policy_admissible,
                        "proposal_identity": identity_snapshots[ordinal],
                        "policy_rejections": list(candidate.policy_rejections),
                        "selected": False,
                        "coordinates_binary64_hex": coordinate_snapshots[ordinal],
                    }
                    try:
                        pose.assert_integrity()
                        if (
                            pose.fingerprint_sha256 != fingerprint
                            or pose.parent_proposal_fingerprint_sha256 != source_sha
                        ):
                            raise StructureRefinementError(
                                "scorer changed retained candidate identity"
                            )
                        if outcome.error is not None:
                            raise outcome.error
                        if type(outcome.evidence) is not ScorerV1Terms:
                            raise StructureRefinementError(
                                "typed scorer term evidence required"
                            )
                        score = float(outcome.score)
                        if (
                            not math.isfinite(score)
                            or score != outcome.evidence.total_score
                        ):
                            raise StructureRefinementError(
                                "retained scorer value does not match its terms"
                            )
                        validity = authority.validity_context.evaluate(pose)
                        row.update(
                            status="success",
                            score=score,
                            score_terms=outcome.evidence.to_dict(),
                            pose_validity=validity.to_dict(),
                            selection_eligible=bool(
                                candidate.policy_admissible
                                and validity.complete
                                and validity.valid
                            ),
                            refinement_receipt_sha256=pose.refinement_receipt_sha256,
                            coordinates_binary64_hex=[
                                [float(x).hex() for x in xyz]
                                for xyz in pose.coordinates.tolist()
                            ],
                        )
                    except Exception as exc:
                        row.update(
                            status="failure",
                            score=None,
                            selection_eligible=False,
                            **_failure(exc),
                        )
                    source_rows.append(row)
                proposal.assert_integrity()
                if proposal.fingerprint_sha256 != source_sha:
                    raise StructureRefinementError(
                        "source proposal identity changed during scoring"
                    )
                candidates.extend(source_rows)
                source_outcomes.append(
                    {
                        "source_proposal_index": proposal.proposal_index,
                        "source_proposal_sha256": source_sha,
                        "status": "success",
                        "retained_count": len(retained),
                    }
                )
            except Exception as exc:
                source_outcomes.append(
                    {
                        "source_proposal_index": proposal.proposal_index,
                        "source_proposal_sha256": source_sha,
                        "status": "failure",
                        "retained_count": 0,
                        **_failure(exc),
                    }
                )
        ranked = sorted(
            (row for row in candidates if row["selection_eligible"]),
            key=lambda row: (
                score_sort_key(row["score"], scorer.score_descriptor),
                row["source_proposal_index"],
                row["ordinal"],
            ),
        )
        # Duplicate endpoints do not consume two Top-K places. Baseline wins an
        # exact tie because ordinal zero is ranked first.
        seen, selected = set(), []
        for row in ranked:
            identity = _sha(row["coordinates_binary64_hex"])
            if identity in seen:
                continue
            seen.add(identity)
            row["selected"] = True
            selected.append((row["source_proposal_index"], row["ordinal"]))
            if len(selected) == budget.top_k:
                break
        if (
            authority.input_receipt_sha256 != authority_sha
            or canonical_system_sha256(ligand) != authority.ligand_system_sha256
            or canonical_system_sha256(receptor) != authority.receptor_system_sha256
            or _json(_provider_identity(self.provider)) != self._provider_snapshot
            or implementation_source_sha256() != source
            or environment() != execution_environment
        ):
            raise StructureRefinementError(
                "pipeline authority or implementation changed during execution"
            )
        if type(refiner) is FixedReceptorStructureDockingRefinerV1:
            refiner.assert_ready()
            work = dict(refiner.work)
        else:
            work = {
                row.source_proposal_sha256: row.to_dict()
                for row in refinement_work_records(refiner)
            }
        receipts = dict(refiner.receipts)
        for source_sha, row in work.items():
            chosen = [
                candidate["role"]
                for candidate in candidates
                if candidate["source_proposal_sha256"] == source_sha
                and candidate["selected"]
            ]
            receipt = receipts.get(source_sha, {})
            if type(refiner) is FixedReceptorStructureDockingRefinerV1:
                steps = row["evaluated_accepted_steps"] if "refined" in chosen else 0
            else:
                steps = (
                    int(receipt.get("accepted_steps", 0))
                    if "refined" in chosen
                    else int(
                        receipt.get("baseline_v6_receipt_payload", {}).get(
                            "accepted_steps", 0
                        )
                    )
                    if "baseline" in chosen
                    else 0
                )
            row["pipeline_selected_roles"] = chosen
            row["pipeline_selected_path_steps"] = steps
        document = {
            "pipeline_id": PIPELINE_ID,
            "provider_type": type(self.provider).__name__,
            "authority_input_receipt_sha256": authority_sha,
            "implementation_source_sha256": source,
            "implementation_sources": source_files,
            "execution_environment": execution_environment,
            "budget": budget.to_dict(),
            "proposal_generation": generation,
            "source_candidate_count": len(proposals),
            "maximum_retained_candidates_per_source": 2,
            "source_outcomes": source_outcomes,
            "candidates": candidates,
            "selected_candidates": selected,
            "refinement_receipts": receipts,
            "work": work,
            "scorer_contract_sha256": scorer.contract_fingerprint_sha256,
            "score_descriptor": scorer.score_descriptor.to_dict(),
            "scientifically_validated": False,
            "accuracy_claim": False,
            "claim_blockers": [
                "explicit_refinement_pipeline_not_scientifically_validated",
                "retained_candidate_budget_differs_from_frozen_v7",
            ],
        }
        return ExplicitRefinementResultV1(_json(document))
