"""Bounded, non-claim docking proposal, authority, and search contracts."""

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
    component_problem_fingerprint,
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
    PoseValidityContext,
    PoseValidityError,
    PoseValidityResult,
    evaluate_pose_validity,
)
from .authority import (
    AUTHENTICATED_DOCKING_DERIVATION_ID,
    AUTHENTICATED_DOCKING_DERIVATION_POLICY_SCHEMA_ID,
    AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID,
    AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS,
    AUTHENTICATED_DOCKING_MAX_LIGAND_BONDS,
    AUTHENTICATED_DOCKING_MAX_POCKET_RADIUS_ANGSTROM,
    AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS,
    AUTHENTICATED_DOCKING_MAX_RECEPTOR_MARGIN_ANGSTROM,
    AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID,
    AuthenticatedDockingProblem,
    AuthenticatedDockingSearchResult,
    DockingAuthorityError,
    DockingScope,
    PocketDefinition,
    TorsionSearchSpaceDerivationReceipt,
    authenticated_docking_derivation_policy_document,
    build_authenticated_known_pocket_docking_problem,
    derive_authoritative_torsion_search_space,
    run_authenticated_bounded_docking_search,
)
from .authority_rotor_compat import (
    install_authority_rotor_stereo_compat as _install_authority_rotor_stereo_compat,
)

AUTHORITY_ROTOR_STEREO_COMPAT_SHA256 = (
    _install_authority_rotor_stereo_compat()
)

# Rebind the public function after the installer updates the owning module.
from .authority import derive_authoritative_torsion_search_space

__all__ = [
    "AUTHENTICATED_DOCKING_DERIVATION_ID",
    "AUTHENTICATED_DOCKING_DERIVATION_POLICY_SCHEMA_ID",
    "AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID",
    "AUTHENTICATED_DOCKING_MAX_LIGAND_ATOMS",
    "AUTHENTICATED_DOCKING_MAX_LIGAND_BONDS",
    "AUTHENTICATED_DOCKING_MAX_POCKET_RADIUS_ANGSTROM",
    "AUTHENTICATED_DOCKING_MAX_RECEPTOR_ATOMS",
    "AUTHENTICATED_DOCKING_MAX_RECEPTOR_MARGIN_ANGSTROM",
    "AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID",
    "AUTHORITY_ROTOR_STEREO_COMPAT_SHA256",
    "MAX_DOCKING_CANDIDATES",
    "MAX_DOCKING_REFINEMENT_STEPS",
    "MAX_DOCKING_TOP_K",
    "MAX_DOCKING_TORSIONS",
    "MAX_SYMMETRY_PERMUTATIONS",
    "AuthenticatedDockingProblem",
    "AuthenticatedDockingSearchResult",
    "DockingAuthorityError",
    "DockingBudget",
    "DockingIdentityError",
    "DockingPoseRefiner",
    "DockingPoseScorer",
    "DockingProblemIdentity",
    "DockingProposal",
    "DockingProposalError",
    "DockingScope",
    "DockingScoreDescriptor",
    "DockingSearchError",
    "DockingSearchResult",
    "DockingSearchRow",
    "PocketDefinition",
    "PoseMetricError",
    "PoseValidityConfig",
    "PoseValidityContext",
    "PoseValidityError",
    "PoseValidityResult",
    "RMSDResult",
    "ScoreDirection",
    "TorsionSearchSpace",
    "TorsionSearchSpaceDerivationReceipt",
    "UNCALIBRATED_INTERNAL_DOCKING_SCORE",
    "authenticated_docking_derivation_policy_document",
    "build_authenticated_known_pocket_docking_problem",
    "component_contract_fingerprint",
    "component_problem_fingerprint",
    "coordinate_fingerprint",
    "derive_authoritative_torsion_search_space",
    "direct_rmsd",
    "evaluate_pose_validity",
    "generate_bounded_docking_proposals",
    "kabsch_aligned_coordinates",
    "kabsch_aligned_rmsd",
    "run_authenticated_bounded_docking_search",
    "run_bounded_docking_search",
    "scorer_descriptor",
    "search_space_fingerprint",
    "symmetry_aware_rmsd",
]
