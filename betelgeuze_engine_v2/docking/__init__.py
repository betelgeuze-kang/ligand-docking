"""Bounded, non-claim docking proposal and search scaffolds."""

from .identity import (
    DockingIdentityError,
    DockingProblemIdentity,
    coordinate_fingerprint,
    search_space_fingerprint,
)
from .metrics import (
    MAX_SYMMETRY_PERMUTATIONS,
    PoseMetricError,
    RMSDResult,
    direct_rmsd,
    kabsch_aligned_coordinates,
    kabsch_aligned_rmsd,
    symmetry_aware_rmsd,
)
from .proposals import (
    MAX_DOCKING_CANDIDATES,
    MAX_DOCKING_REFINEMENT_STEPS,
    MAX_DOCKING_TOP_K,
    MAX_DOCKING_TORSIONS,
    DockingBudget,
    DockingProposal,
    DockingProposalError,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
)
from .scoring import (
    DockingScoreDescriptor,
    ScoreDirection,
    UNCALIBRATED_INTERNAL_DOCKING_SCORE,
    component_contract_fingerprint,
    scorer_descriptor,
)
from .search import (
    DockingPoseRefiner,
    DockingPoseScorer,
    DockingSearchError,
    DockingSearchResult,
    DockingSearchRow,
    run_bounded_docking_search,
)
from .validity import (
    PoseValidityConfig,
    PoseValidityError,
    PoseValidityResult,
    evaluate_pose_validity,
)

__all__ = [
    "MAX_DOCKING_CANDIDATES",
    "MAX_DOCKING_REFINEMENT_STEPS",
    "MAX_DOCKING_TOP_K",
    "MAX_DOCKING_TORSIONS",
    "MAX_SYMMETRY_PERMUTATIONS",
    "DockingBudget",
    "DockingIdentityError",
    "DockingPoseRefiner",
    "DockingPoseScorer",
    "DockingProblemIdentity",
    "DockingProposal",
    "DockingProposalError",
    "DockingScoreDescriptor",
    "DockingSearchError",
    "DockingSearchResult",
    "DockingSearchRow",
    "PoseMetricError",
    "PoseValidityConfig",
    "PoseValidityError",
    "PoseValidityResult",
    "RMSDResult",
    "ScoreDirection",
    "TorsionSearchSpace",
    "UNCALIBRATED_INTERNAL_DOCKING_SCORE",
    "component_contract_fingerprint",
    "coordinate_fingerprint",
    "direct_rmsd",
    "evaluate_pose_validity",
    "generate_bounded_docking_proposals",
    "kabsch_aligned_coordinates",
    "kabsch_aligned_rmsd",
    "run_bounded_docking_search",
    "scorer_descriptor",
    "search_space_fingerprint",
    "symmetry_aware_rmsd",
]
