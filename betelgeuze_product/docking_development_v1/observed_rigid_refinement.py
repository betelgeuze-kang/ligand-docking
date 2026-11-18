"""Product-owned observation of the existing bounded rigid numerical methods.

Only these new subclasses are instrumented. The original engine classes and
module globals remain untouched. Each actual objective/direction call is
observed through ordinary method dispatch. Completed leaf receipts supply exact
step/trial counts; interrupted leaves explicitly retain unknown partial counts.
"""

from betelgeuze_engine_v2.docking.interaction_refinement import (
    InteractionAwareRigidClearanceConfigV4,
    InteractionAwareRigidHybridClearanceEnsembleRefinerV6,
    InteractionAwareRigidRefinerV2,
    InteractionAwareRigidRefinerV3,
)

from .refinement_work import (
    completed_leaf_steps,
    count_direction,
    count_objective,
    failed_leaf_steps_unknown,
    track_refinement,
)


class _ObservedRigidLeaf:
    @count_objective
    def _penalty_and_direction(self, coordinates):
        return super()._penalty_and_direction(coordinates)

    @count_direction
    def _maximum_penetration_direction(self, coordinates):
        return super()._maximum_penetration_direction(coordinates)

    @count_direction
    def _rotation_torque(self, coordinates):
        return super()._rotation_torque(coordinates)

    @track_refinement
    def refine(self, proposal, *, max_steps):
        source = proposal.fingerprint_sha256
        try:
            result = super().refine(proposal, max_steps=max_steps)
            completed_leaf_steps(self.receipts[source])
            return result
        except BaseException:
            failed_leaf_steps_unknown()
            raise


class ObservedRigidRefinerV2(_ObservedRigidLeaf, InteractionAwareRigidRefinerV2):
    refiner_id = "betelgeuze.product_observed_rigid_translation"
    refiner_version = "1.0.0"


class ObservedRigidRefinerV3(_ObservedRigidLeaf, InteractionAwareRigidRefinerV3):
    refiner_id = "betelgeuze.product_observed_rigid_translation_rotation"
    refiner_version = "1.0.0"


class ObservedRigidEnsembleV6(InteractionAwareRigidHybridClearanceEnsembleRefinerV6):
    """The bounded V6 composition with separately observed product-owned arms."""

    refiner_id = "betelgeuze.product_observed_rigid_hybrid_ensemble"
    refiner_version = "1.0.0"

    def __init__(
        self,
        authority,
        receptor_system,
        ligand_system,
        *,
        implementation_source_sha256,
        v3_proposal_indices,
        v2_config=None,
        v3_config=None,
        clearance_config=None,
        radii_policy=None,
    ):
        options = dict(
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            v2_config=v2_config,
            v3_config=v3_config,
            clearance_config=clearance_config,
            radii_policy=radii_policy,
        )
        super().__init__(authority, receptor_system, ligand_system, **options)
        arm_options = dict(
            implementation_source_sha256=implementation_source_sha256,
            radii_policy=radii_policy,
        )
        v2 = ObservedRigidRefinerV2(
            authority, receptor_system, ligand_system, config=v2_config, **arm_options
        )
        v3 = ObservedRigidRefinerV3(
            authority, receptor_system, ligand_system, config=v3_config, **arm_options
        )
        clearance = ObservedRigidRefinerV3(
            authority,
            receptor_system,
            ligand_system,
            config=clearance_config or InteractionAwareRigidClearanceConfigV4(),
            **arm_options,
        )
        for original, observed in zip(
            (self._v2, self._v3, self._clearance_v3), (v2, v3, clearance), strict=True
        ):
            if original.config_fingerprint_sha256 != observed.config_fingerprint_sha256:
                raise ValueError(
                    "observed rigid arm changed its numerical configuration"
                )
        self._v2, self._v3, self._clearance_v3 = v2, v3, clearance

    @track_refinement
    def refine(self, proposal, *, max_steps):
        return super().refine(proposal, max_steps=max_steps)
