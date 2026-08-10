use crate::identity::receipt_sha256;
use crate::{PlacementMode, SearchError, SearchErrorCode, SEARCH_RECEIPT_SCHEMA_ID};

/// Auditable stage denominators, fixed budgets, evaluator identity, and SHA-256
/// identities over canonical binary encodings.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SearchReceipt {
    pub schema_id: &'static str,
    pub evaluator_id: &'static str,
    pub evaluator_config_sha256: [u8; 32],
    pub config_sha256: [u8; 32],
    pub input_sha256: [u8; 32],
    pub result_independent_allocation: bool,
    pub placement_mode: PlacementMode,
    pub requested_orientation_count: usize,
    pub accepted_orientation_count: usize,
    pub raw_orientation_attempt_count: u64,
    pub compatible_single_anchor_pair_count: usize,
    pub compatible_dual_anchor_combination_count: usize,
    pub used_anchor_combination_count: usize,
    pub possible_candidate_slot_count: u64,
    pub generated_candidate_limit: usize,
    pub allocated_candidate_slot_count: usize,
    pub allocation_sha256: [u8; 32],
    pub orientation_sha256: [u8; 32],
    pub candidate_rows_sha256: [u8; 32],
    pub poses_sha256: [u8; 32],
    pub coarse_keep_budget: usize,
    pub coarse_kept_count: usize,
    pub refinement_keep_budget: usize,
    pub refinement_selected_count: usize,
    pub refinement_steps_per_candidate: usize,
    pub refinement_succeeded_count: usize,
    pub refinement_evaluator_failed_count: usize,
    pub refinement_non_finite_failed_count: usize,
    pub evaluator_call_count: usize,
    pub maximum_evaluator_call_count: usize,
    pub physical_valid_count: usize,
    pub rejected_non_finite_coordinate_count: usize,
    pub rejected_coordinate_out_of_bounds_count: usize,
    pub rejected_ligand_self_overlap_count: usize,
    pub rejected_receptor_clash_count: usize,
    pub cluster_count: usize,
    pub top_k_budget: usize,
    pub returned_pose_count: usize,
    pub receipt_sha256: [u8; 32],
}

impl SearchReceipt {
    #[must_use]
    pub fn has_valid_sha256(&self) -> bool {
        receipt_sha256(self) == self.receipt_sha256
    }

    pub(crate) fn seal(&mut self) {
        self.receipt_sha256 = receipt_sha256(self);
    }

    pub(crate) fn validate(&self) -> Result<(), SearchError> {
        let rejected = self
            .rejected_non_finite_coordinate_count
            .checked_add(self.rejected_coordinate_out_of_bounds_count)
            .and_then(|value| value.checked_add(self.rejected_ligand_self_overlap_count))
            .and_then(|value| value.checked_add(self.rejected_receptor_clash_count))
            .ok_or_else(|| {
                SearchError::new(
                    SearchErrorCode::AllocationOverflow,
                    "physical rejection count overflowed",
                )
            })?;
        let refinement_failed = self
            .refinement_evaluator_failed_count
            .checked_add(self.refinement_non_finite_failed_count)
            .ok_or_else(|| {
                SearchError::new(
                    SearchErrorCode::AllocationOverflow,
                    "refinement failure count overflowed",
                )
            })?;
        let expected_maximum_calls = self
            .refinement_selected_count
            .checked_mul(self.refinement_steps_per_candidate + 1)
            .ok_or_else(|| {
                SearchError::new(
                    SearchErrorCode::AllocationOverflow,
                    "maximum evaluator call count overflowed",
                )
            })?;
        let placement_counts_valid = match self.placement_mode {
            PlacementMode::DualAnchor => {
                self.compatible_dual_anchor_combination_count > 0
                    && (1..=self.compatible_dual_anchor_combination_count)
                        .contains(&self.used_anchor_combination_count)
            }
            PlacementMode::SingleAnchorFallback => {
                self.compatible_dual_anchor_combination_count == 0
                    && (1..=self.compatible_single_anchor_pair_count)
                        .contains(&self.used_anchor_combination_count)
            }
        };
        let valid = self.schema_id == SEARCH_RECEIPT_SCHEMA_ID
            && !self.evaluator_id.is_empty()
            && self.result_independent_allocation
            && placement_counts_valid
            && self.accepted_orientation_count == self.requested_orientation_count
            && self.allocated_candidate_slot_count
                == self
                    .generated_candidate_limit
                    .min(self.possible_candidate_slot_count as usize)
            && self.coarse_kept_count
                == self
                    .coarse_keep_budget
                    .min(self.allocated_candidate_slot_count)
            && self.refinement_selected_count
                == self.refinement_keep_budget.min(self.coarse_kept_count)
            && self.refinement_succeeded_count + refinement_failed
                == self.refinement_selected_count
            && self.maximum_evaluator_call_count == expected_maximum_calls
            && self.evaluator_call_count >= self.refinement_selected_count
            && self.evaluator_call_count <= self.maximum_evaluator_call_count
            && self.physical_valid_count + rejected == self.refinement_succeeded_count
            && self.cluster_count <= self.physical_valid_count
            && self.returned_pose_count == self.top_k_budget.min(self.cluster_count)
            && self.has_valid_sha256();
        if valid {
            Ok(())
        } else {
            Err(SearchError::new(
                SearchErrorCode::InternalInvariant,
                "search receipt stage counts, identities, or fixed-budget denominators are inconsistent",
            ))
        }
    }
}
