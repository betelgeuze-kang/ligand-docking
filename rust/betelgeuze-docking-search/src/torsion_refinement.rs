use std::{cmp::Ordering, fmt};

use crate::Vec3;

pub const NATIVE_TORSION_V7_ALGORITHM_ID: &str =
    "betelgeuze.native_interaction_aware_torsion_contact_refinement_v7/1.0.0";
pub const NATIVE_TORSION_V7_CONFIG_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_interaction_aware_torsion_contact_config/7.0.0";
pub const NATIVE_TORSION_V7_MAX_LIGAND_ATOMS: usize = 512;
pub const NATIVE_TORSION_V7_MAX_RECEPTOR_ATOMS: usize = 65_536;
pub const NATIVE_TORSION_V7_MAX_TOTAL_PAIR_EVALUATIONS: usize = 250_000_000;
pub const NATIVE_TORSION_V7_MAX_CALLER_STEPS: usize = 10_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeTorsionV7ErrorCode {
    InvalidInput,
    NonFiniteInput,
    PairBudgetExceeded,
    DegenerateRotor,
    NonFiniteDerivedValue,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeTorsionV7Error {
    code: NativeTorsionV7ErrorCode,
    message: &'static str,
}

impl NativeTorsionV7Error {
    const fn new(code: NativeTorsionV7ErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeTorsionV7ErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeTorsionV7Error {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "native torsion-contact V7 refinement: {}",
            self.message
        )
    }
}

impl std::error::Error for NativeTorsionV7Error {}

#[derive(Clone, Copy, Debug)]
pub struct NativeTorsionV7Context<'a> {
    pub receptor_coordinates_angstrom: &'a [Vec3],
    pub receptor_vdw_radii_angstrom: &'a [f64],
    pub ligand_vdw_radii_angstrom: &'a [f64],
    pub pocket_center_angstrom: Vec3,
    pub parent_atom_indices: &'a [i32],
    pub rotatable_child_atom_indices: &'a [usize],
    pub evaluated_internal_pairs: &'a [(usize, usize)],
}

#[derive(Clone, Copy, Debug)]
pub struct NativeTorsionV7Request<'a> {
    pub context: NativeTorsionV7Context<'a>,
    pub source_coordinates_angstrom: &'a [Vec3],
    pub baseline_v6_coordinates_angstrom: &'a [Vec3],
    pub baseline_v6_torsion_angles_radians: &'a [f64],
    pub proposal_is_torsion_eligible: bool,
    pub max_steps: usize,
    pub baseline_v6_accepted_steps: usize,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeTorsionV7Config {
    pub receptor_overlap_scale: f64,
    pub internal_overlap_scale: f64,
    pub internal_overlap_weight: f64,
    pub maximum_baseline_v6_steps: usize,
    pub maximum_torsions_evaluated: usize,
    pub maximum_torsion_steps: usize,
    pub maximum_backtracking_evaluations: usize,
    pub maximum_torsion_step_radians: f64,
    pub minimum_torsion_step_radians: f64,
    pub maximum_total_torsion_path_radians: f64,
    pub maximum_centroid_offset_angstrom: f64,
    pub minimum_selected_final_receptor_penalty: f64,
    pub maximum_selected_final_receptor_penalty: f64,
    pub penalty_tolerance: f64,
    pub epsilon_angstrom: f64,
}

impl Default for NativeTorsionV7Config {
    fn default() -> Self {
        Self {
            receptor_overlap_scale: 1.0,
            internal_overlap_scale: 0.80,
            internal_overlap_weight: 1.0,
            maximum_baseline_v6_steps: 20,
            maximum_torsions_evaluated: 4,
            maximum_torsion_steps: 4,
            maximum_backtracking_evaluations: 3,
            maximum_torsion_step_radians: std::f64::consts::PI / 8.0,
            minimum_torsion_step_radians: std::f64::consts::PI / 32.0,
            maximum_total_torsion_path_radians: std::f64::consts::PI / 2.0,
            maximum_centroid_offset_angstrom: 4.0,
            minimum_selected_final_receptor_penalty: 2.0,
            maximum_selected_final_receptor_penalty: 4.0,
            penalty_tolerance: 1.0e-18,
            epsilon_angstrom: 1.0e-9,
        }
    }
}

impl NativeTorsionV7Config {
    fn validate(self) -> Result<(), NativeTorsionV7Error> {
        let finite_positive = [
            self.receptor_overlap_scale,
            self.internal_overlap_scale,
            self.internal_overlap_weight,
            self.maximum_torsion_step_radians,
            self.minimum_torsion_step_radians,
            self.maximum_total_torsion_path_radians,
            self.maximum_centroid_offset_angstrom,
            self.penalty_tolerance,
            self.epsilon_angstrom,
        ];
        if finite_positive
            .iter()
            .any(|value| !value.is_finite() || *value <= 0.0)
        {
            return Err(non_finite("V7 configuration is non-finite"));
        }
        if !(0.55..=1.0).contains(&self.receptor_overlap_scale)
            || !(0.55..=1.0).contains(&self.internal_overlap_scale)
            || self.minimum_torsion_step_radians > self.maximum_torsion_step_radians
            || self.maximum_torsion_step_radians > self.maximum_total_torsion_path_radians
            || self.maximum_total_torsion_path_radians > std::f64::consts::PI
            || !(1..=64).contains(&self.maximum_baseline_v6_steps)
            || !(1..=32).contains(&self.maximum_torsions_evaluated)
            || !(1..=8).contains(&self.maximum_torsion_steps)
            || !(1..=8).contains(&self.maximum_backtracking_evaluations)
            || !(0.5..=8.0).contains(&self.maximum_centroid_offset_angstrom)
        {
            return Err(invalid("V7 configuration bounds are inconsistent"));
        }
        if !self.minimum_selected_final_receptor_penalty.is_finite()
            || !self.maximum_selected_final_receptor_penalty.is_finite()
            || self.minimum_selected_final_receptor_penalty < 0.0
            || self.minimum_selected_final_receptor_penalty
                >= self.maximum_selected_final_receptor_penalty
        {
            return Err(invalid("V7 selection window is invalid"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct NativeTorsionV7Objective {
    receptor: f64,
    internal: f64,
    combined: f64,
}

impl NativeTorsionV7Objective {
    #[must_use]
    pub const fn receptor(self) -> f64 {
        self.receptor
    }

    #[must_use]
    pub const fn internal(self) -> f64 {
        self.internal
    }

    #[must_use]
    pub const fn combined(self) -> f64 {
        self.combined
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeTorsionV7Move {
    rotatable_child_atom_index: usize,
    delta_radians: f64,
    objective: NativeTorsionV7Objective,
}

impl NativeTorsionV7Move {
    #[must_use]
    pub const fn rotatable_child_atom_index(self) -> usize {
        self.rotatable_child_atom_index
    }

    #[must_use]
    pub const fn delta_radians(self) -> f64 {
        self.delta_radians
    }

    #[must_use]
    pub const fn objective(self) -> NativeTorsionV7Objective {
        self.objective
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeTorsionV7SkipReason {
    NoSkip,
    NotEligible,
    NoAuthorityRotor,
    NoRemainingTorsionStepBudget,
    ObjectiveAtOrBelowTolerance,
    SelectionWindowUnreachable,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeTorsionV7SelectionReason {
    FinalReceptorPenaltyWindowSelected,
    V6RetainedOutsideFinalReceptorPenaltyWindow,
    V6BaselineRetainedNoTorsionObjectiveReduction,
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeTorsionV7Outcome {
    baseline_coordinates_angstrom: Vec<Vec3>,
    optimized_coordinates_angstrom: Vec<Vec3>,
    final_coordinates_angstrom: Vec<Vec3>,
    baseline_torsion_angles_radians: Vec<f64>,
    optimized_torsion_angles_radians: Vec<f64>,
    final_torsion_angles_radians: Vec<f64>,
    source_objective: NativeTorsionV7Objective,
    baseline_objective: NativeTorsionV7Objective,
    optimized_objective: NativeTorsionV7Objective,
    final_objective: NativeTorsionV7Objective,
    skip_reason: NativeTorsionV7SkipReason,
    selection_reason: NativeTorsionV7SelectionReason,
    torsion_step_budget: usize,
    selection_window_reachable: bool,
    evaluation_stopped_after_selection_window_became_unreachable: bool,
    torsion_evaluated: bool,
    torsion_variant_available: bool,
    torsion_selected: bool,
    evaluated_moves: Vec<NativeTorsionV7Move>,
    accepted_moves: Vec<NativeTorsionV7Move>,
    evaluated_total_torsion_path_radians: f64,
    accepted_total_torsion_path_radians: f64,
    fixed_objective_evaluation_count: usize,
    torsion_trial_objective_evaluation_count: usize,
    baseline_accepted_steps: usize,
}

impl NativeTorsionV7Outcome {
    #[must_use]
    pub fn baseline_coordinates_angstrom(&self) -> &[Vec3] {
        &self.baseline_coordinates_angstrom
    }

    #[must_use]
    pub fn optimized_coordinates_angstrom(&self) -> &[Vec3] {
        &self.optimized_coordinates_angstrom
    }

    #[must_use]
    pub fn final_coordinates_angstrom(&self) -> &[Vec3] {
        &self.final_coordinates_angstrom
    }

    #[must_use]
    pub fn baseline_torsion_angles_radians(&self) -> &[f64] {
        &self.baseline_torsion_angles_radians
    }

    #[must_use]
    pub fn optimized_torsion_angles_radians(&self) -> &[f64] {
        &self.optimized_torsion_angles_radians
    }

    #[must_use]
    pub fn final_torsion_angles_radians(&self) -> &[f64] {
        &self.final_torsion_angles_radians
    }

    #[must_use]
    pub const fn source_objective(&self) -> NativeTorsionV7Objective {
        self.source_objective
    }

    #[must_use]
    pub const fn baseline_objective(&self) -> NativeTorsionV7Objective {
        self.baseline_objective
    }

    #[must_use]
    pub const fn optimized_objective(&self) -> NativeTorsionV7Objective {
        self.optimized_objective
    }

    #[must_use]
    pub const fn final_objective(&self) -> NativeTorsionV7Objective {
        self.final_objective
    }

    #[must_use]
    pub const fn skip_reason(&self) -> NativeTorsionV7SkipReason {
        self.skip_reason
    }

    #[must_use]
    pub const fn selection_reason(&self) -> NativeTorsionV7SelectionReason {
        self.selection_reason
    }

    #[must_use]
    pub const fn torsion_step_budget(&self) -> usize {
        self.torsion_step_budget
    }

    #[must_use]
    pub const fn selection_window_reachable(&self) -> bool {
        self.selection_window_reachable
    }

    #[must_use]
    pub const fn evaluation_stopped_after_selection_window_became_unreachable(&self) -> bool {
        self.evaluation_stopped_after_selection_window_became_unreachable
    }

    #[must_use]
    pub const fn torsion_evaluated(&self) -> bool {
        self.torsion_evaluated
    }

    #[must_use]
    pub const fn torsion_variant_available(&self) -> bool {
        self.torsion_variant_available
    }

    #[must_use]
    pub const fn torsion_selected(&self) -> bool {
        self.torsion_selected
    }

    #[must_use]
    pub fn evaluated_moves(&self) -> &[NativeTorsionV7Move] {
        &self.evaluated_moves
    }

    #[must_use]
    pub fn accepted_moves(&self) -> &[NativeTorsionV7Move] {
        &self.accepted_moves
    }

    #[must_use]
    pub const fn evaluated_total_torsion_path_radians(&self) -> f64 {
        self.evaluated_total_torsion_path_radians
    }

    #[must_use]
    pub const fn accepted_total_torsion_path_radians(&self) -> f64 {
        self.accepted_total_torsion_path_radians
    }

    #[must_use]
    pub const fn fixed_objective_evaluation_count(&self) -> usize {
        self.fixed_objective_evaluation_count
    }

    #[must_use]
    pub const fn torsion_trial_objective_evaluation_count(&self) -> usize {
        self.torsion_trial_objective_evaluation_count
    }

    #[must_use]
    pub const fn objective_evaluation_count(&self) -> usize {
        self.fixed_objective_evaluation_count + self.torsion_trial_objective_evaluation_count
    }

    #[must_use]
    pub fn evaluated_torsion_steps(&self) -> usize {
        self.evaluated_moves.len()
    }

    #[must_use]
    pub fn accepted_torsion_steps(&self) -> usize {
        self.accepted_moves.len()
    }

    #[must_use]
    pub fn accepted_steps(&self) -> usize {
        self.baseline_accepted_steps + self.accepted_moves.len()
    }
}

#[derive(Clone, Debug)]
struct PreparedContext<'a> {
    raw: NativeTorsionV7Context<'a>,
    descendants: Vec<Vec<usize>>,
    cross_internal_pair_indices: Vec<Vec<usize>>,
}

#[derive(Clone, Debug)]
struct ObjectiveState {
    total: NativeTorsionV7Objective,
    receptor_by_atom: Vec<f64>,
    internal_by_pair: Vec<f64>,
}

#[derive(Clone, Debug)]
struct Trial {
    objective: NativeTorsionV7Objective,
    rotor_atom_index: usize,
    sign_order: usize,
    delta_radians: f64,
    coordinates_angstrom: Vec<Vec3>,
    torsion_angles_radians: Vec<f64>,
    receptor_by_atom: Vec<f64>,
    internal_by_pair: Vec<f64>,
}

impl Trial {
    fn compare_key(&self, other: &Self) -> Ordering {
        compare_f64(self.objective.combined, other.objective.combined)
            .then_with(|| compare_f64(self.objective.receptor, other.objective.receptor))
            .then_with(|| compare_f64(self.objective.internal, other.objective.internal))
            .then_with(|| self.rotor_atom_index.cmp(&other.rotor_atom_index))
            .then_with(|| self.sign_order.cmp(&other.sign_order))
    }
}

pub fn refine_interaction_aware_torsion_contact_v7(
    request: NativeTorsionV7Request<'_>,
    config: NativeTorsionV7Config,
) -> Result<NativeTorsionV7Outcome, NativeTorsionV7Error> {
    let NativeTorsionV7Request {
        context,
        source_coordinates_angstrom,
        baseline_v6_coordinates_angstrom,
        baseline_v6_torsion_angles_radians,
        proposal_is_torsion_eligible,
        max_steps,
        baseline_v6_accepted_steps,
    } = request;
    config.validate()?;
    let prepared = prepare_context(
        context,
        source_coordinates_angstrom,
        baseline_v6_coordinates_angstrom,
        baseline_v6_torsion_angles_radians,
        max_steps,
        baseline_v6_accepted_steps,
        config,
    )?;
    let source_state = objective(&prepared, source_coordinates_angstrom, config)?;
    let baseline_state = objective(&prepared, baseline_v6_coordinates_angstrom, config)?;
    let mut coordinates = baseline_v6_coordinates_angstrom.to_vec();
    let mut torsion_angles = baseline_v6_torsion_angles_radians.to_vec();
    let mut current_state = baseline_state.clone();
    let mut total_torsion_path = 0.0;
    let mut evaluated_moves = Vec::with_capacity(config.maximum_torsion_steps);
    let mut trial_evaluation_count = 0usize;
    let remaining_steps = max_steps.saturating_sub(baseline_v6_accepted_steps);
    let torsion_step_budget = config.maximum_torsion_steps.min(remaining_steps);
    let reachable_bound =
        baseline_state.total.receptor + torsion_step_budget as f64 * config.penalty_tolerance;
    if !reachable_bound.is_finite() {
        return Err(derived("V7 selection reachability overflowed"));
    }
    let selection_window_reachable =
        reachable_bound >= config.minimum_selected_final_receptor_penalty;
    let skip_reason = if !proposal_is_torsion_eligible {
        NativeTorsionV7SkipReason::NotEligible
    } else if context.rotatable_child_atom_indices.is_empty() {
        NativeTorsionV7SkipReason::NoAuthorityRotor
    } else if torsion_step_budget == 0 {
        NativeTorsionV7SkipReason::NoRemainingTorsionStepBudget
    } else if current_state.total.combined <= config.penalty_tolerance {
        NativeTorsionV7SkipReason::ObjectiveAtOrBelowTolerance
    } else if !selection_window_reachable {
        NativeTorsionV7SkipReason::SelectionWindowUnreachable
    } else {
        NativeTorsionV7SkipReason::NoSkip
    };
    let torsion_evaluated = skip_reason == NativeTorsionV7SkipReason::NoSkip;
    let mut stopped_after_window_unreachable = false;

    for _ in 0..if torsion_evaluated {
        torsion_step_budget
    } else {
        0
    } {
        let mut priorities = context
            .rotatable_child_atom_indices
            .iter()
            .copied()
            .enumerate()
            .map(|(rotor_position, rotor_atom_index)| {
                let priority = rotor_priority(
                    &prepared,
                    rotor_position,
                    &current_state,
                    config.internal_overlap_weight,
                );
                (priority, rotor_position, rotor_atom_index)
            })
            .collect::<Vec<_>>();
        priorities
            .sort_by(|left, right| compare_f64(right.0, left.0).then_with(|| left.2.cmp(&right.2)));
        priorities.truncate(config.maximum_torsions_evaluated);

        let mut best: Option<Trial> = None;
        let mut step = config.maximum_torsion_step_radians;
        for _ in 0..config.maximum_backtracking_evaluations {
            if step + config.penalty_tolerance < config.minimum_torsion_step_radians {
                break;
            }
            if total_torsion_path + step
                > config.maximum_total_torsion_path_radians + config.penalty_tolerance
            {
                step *= 0.5;
                continue;
            }
            for (_, rotor_position, rotor_atom_index) in priorities.iter().copied() {
                for (sign_order, sign) in [(0usize, -1.0f64), (1usize, 1.0f64)] {
                    let delta_radians = sign * step;
                    let candidate_coordinates = rotate_subtree(
                        &prepared,
                        &coordinates,
                        rotor_position,
                        delta_radians,
                        config.epsilon_angstrom,
                    )?;
                    let centroid_offset = norm(
                        centroid(&candidate_coordinates).minus(context.pocket_center_angstrom),
                    );
                    if !centroid_offset.is_finite() {
                        return Err(derived("V7 centroid calculation overflowed"));
                    }
                    if centroid_offset
                        > config.maximum_centroid_offset_angstrom + config.penalty_tolerance
                    {
                        continue;
                    }
                    let candidate_state = objective(&prepared, &candidate_coordinates, config)?;
                    trial_evaluation_count = trial_evaluation_count
                        .checked_add(1)
                        .ok_or_else(|| budget("V7 objective evaluation count overflowed"))?;
                    if candidate_state.total.receptor
                        > current_state.total.receptor + config.penalty_tolerance
                        || candidate_state.total.combined
                            >= current_state.total.combined - config.penalty_tolerance
                    {
                        continue;
                    }
                    let mut candidate_angles = torsion_angles.clone();
                    candidate_angles[rotor_atom_index] =
                        normalized_angle(candidate_angles[rotor_atom_index] + delta_radians);
                    let candidate = Trial {
                        objective: candidate_state.total,
                        rotor_atom_index,
                        sign_order,
                        delta_radians,
                        coordinates_angstrom: candidate_coordinates,
                        torsion_angles_radians: candidate_angles,
                        receptor_by_atom: candidate_state.receptor_by_atom,
                        internal_by_pair: candidate_state.internal_by_pair,
                    };
                    if best
                        .as_ref()
                        .is_none_or(|current| candidate.compare_key(current).is_lt())
                    {
                        best = Some(candidate);
                    }
                }
            }
            if best.is_some() {
                break;
            }
            step *= 0.5;
        }
        let Some(best) = best else {
            break;
        };
        total_torsion_path += best.delta_radians.abs();
        if !total_torsion_path.is_finite() {
            return Err(derived("V7 torsion path overflowed"));
        }
        evaluated_moves.push(NativeTorsionV7Move {
            rotatable_child_atom_index: best.rotor_atom_index,
            delta_radians: canonical_zero(best.delta_radians),
            objective: best.objective,
        });
        coordinates = best.coordinates_angstrom;
        torsion_angles = best.torsion_angles_radians;
        current_state = ObjectiveState {
            total: best.objective,
            receptor_by_atom: best.receptor_by_atom,
            internal_by_pair: best.internal_by_pair,
        };
        let remaining_torsion_steps = torsion_step_budget - evaluated_moves.len();
        let remaining_reachable_bound = current_state.total.receptor
            + remaining_torsion_steps as f64 * config.penalty_tolerance;
        if !remaining_reachable_bound.is_finite() {
            return Err(derived("V7 remaining reachability overflowed"));
        }
        if remaining_reachable_bound < config.minimum_selected_final_receptor_penalty {
            stopped_after_window_unreachable = true;
            break;
        }
    }

    let torsion_variant_available = !evaluated_moves.is_empty();
    let optimized_coordinates = coordinates;
    let optimized_torsion_angles = torsion_angles;
    let optimized_objective = current_state.total;
    let evaluated_total_torsion_path = canonical_zero(total_torsion_path);
    let torsion_selected = torsion_variant_available
        && config.minimum_selected_final_receptor_penalty <= optimized_objective.receptor
        && optimized_objective.receptor < config.maximum_selected_final_receptor_penalty;
    let (final_coordinates, final_torsion_angles, final_objective, accepted_moves, accepted_path) =
        if torsion_selected {
            (
                optimized_coordinates.clone(),
                optimized_torsion_angles.clone(),
                optimized_objective,
                evaluated_moves.clone(),
                evaluated_total_torsion_path,
            )
        } else {
            (
                baseline_v6_coordinates_angstrom.to_vec(),
                baseline_v6_torsion_angles_radians.to_vec(),
                baseline_state.total,
                Vec::new(),
                0.0,
            )
        };
    let selection_reason = if torsion_selected {
        NativeTorsionV7SelectionReason::FinalReceptorPenaltyWindowSelected
    } else if torsion_variant_available {
        NativeTorsionV7SelectionReason::V6RetainedOutsideFinalReceptorPenaltyWindow
    } else {
        NativeTorsionV7SelectionReason::V6BaselineRetainedNoTorsionObjectiveReduction
    };

    Ok(NativeTorsionV7Outcome {
        baseline_coordinates_angstrom: baseline_v6_coordinates_angstrom.to_vec(),
        optimized_coordinates_angstrom: optimized_coordinates,
        final_coordinates_angstrom: final_coordinates,
        baseline_torsion_angles_radians: baseline_v6_torsion_angles_radians.to_vec(),
        optimized_torsion_angles_radians: optimized_torsion_angles,
        final_torsion_angles_radians: final_torsion_angles,
        source_objective: source_state.total,
        baseline_objective: baseline_state.total,
        optimized_objective,
        final_objective,
        skip_reason,
        selection_reason,
        torsion_step_budget,
        selection_window_reachable,
        evaluation_stopped_after_selection_window_became_unreachable:
            stopped_after_window_unreachable,
        torsion_evaluated,
        torsion_variant_available,
        torsion_selected,
        evaluated_moves,
        accepted_moves,
        evaluated_total_torsion_path_radians: evaluated_total_torsion_path,
        accepted_total_torsion_path_radians: accepted_path,
        fixed_objective_evaluation_count: 2,
        torsion_trial_objective_evaluation_count: trial_evaluation_count,
        baseline_accepted_steps: baseline_v6_accepted_steps,
    })
}

/// Validates a persistent V7 context without inventing candidate coordinates
/// or evaluating a scientific objective.
pub fn validate_interaction_aware_torsion_contact_v7_context(
    context: NativeTorsionV7Context<'_>,
    config: NativeTorsionV7Config,
) -> Result<(), NativeTorsionV7Error> {
    config.validate()?;
    prepare_persistent_context(context, config).map(drop)
}

fn prepare_context<'a>(
    context: NativeTorsionV7Context<'a>,
    source_coordinates: &[Vec3],
    baseline_coordinates: &[Vec3],
    baseline_torsion_angles: &[f64],
    max_steps: usize,
    baseline_accepted_steps: usize,
    config: NativeTorsionV7Config,
) -> Result<PreparedContext<'a>, NativeTorsionV7Error> {
    let atom_count = context.ligand_vdw_radii_angstrom.len();
    if source_coordinates.len() != atom_count
        || baseline_coordinates.len() != atom_count
        || baseline_torsion_angles.len() != atom_count
        || max_steps > NATIVE_TORSION_V7_MAX_CALLER_STEPS
        || baseline_accepted_steps > max_steps
        || baseline_accepted_steps > config.maximum_baseline_v6_steps
    {
        return Err(invalid("V7 request shape or step bound is invalid"));
    }
    if source_coordinates
        .iter()
        .chain(baseline_coordinates)
        .any(|coordinate| !coordinate.is_finite())
        || baseline_torsion_angles
            .iter()
            .any(|angle| !angle.is_finite())
    {
        return Err(non_finite("V7 request contains non-finite values"));
    }
    prepare_persistent_context(context, config)
}

fn prepare_persistent_context<'a>(
    context: NativeTorsionV7Context<'a>,
    config: NativeTorsionV7Config,
) -> Result<PreparedContext<'a>, NativeTorsionV7Error> {
    let atom_count = context.ligand_vdw_radii_angstrom.len();
    let maximum_internal_pairs = atom_count
        .checked_mul(atom_count.saturating_sub(1))
        .map(|value| value / 2)
        .ok_or_else(|| budget("V7 internal pair bound overflowed"))?;
    if atom_count == 0
        || atom_count > NATIVE_TORSION_V7_MAX_LIGAND_ATOMS
        || context.parent_atom_indices.len() != atom_count
        || context.receptor_coordinates_angstrom.is_empty()
        || context.receptor_coordinates_angstrom.len() != context.receptor_vdw_radii_angstrom.len()
        || context.receptor_coordinates_angstrom.len() > NATIVE_TORSION_V7_MAX_RECEPTOR_ATOMS
        || context.evaluated_internal_pairs.len() > maximum_internal_pairs
    {
        return Err(invalid("V7 persistent context shape is invalid"));
    }
    if !context.pocket_center_angstrom.is_finite()
        || context
            .receptor_coordinates_angstrom
            .iter()
            .any(|coordinate| !coordinate.is_finite())
        || context
            .receptor_vdw_radii_angstrom
            .iter()
            .chain(context.ligand_vdw_radii_angstrom)
            .any(|radius| !radius.is_finite() || *radius <= 0.0)
    {
        return Err(non_finite(
            "V7 persistent context contains non-finite values",
        ));
    }
    validate_parent_tree(context.parent_atom_indices)?;
    let mut previous_rotor = None;
    for rotor in context.rotatable_child_atom_indices.iter().copied() {
        if rotor >= atom_count
            || context.parent_atom_indices[rotor] < 0
            || previous_rotor.is_some_and(|previous| previous >= rotor)
        {
            return Err(invalid("V7 authority rotor indices are not canonical"));
        }
        previous_rotor = Some(rotor);
    }
    let mut previous_pair = None;
    for pair in context.evaluated_internal_pairs.iter().copied() {
        if pair.0 >= pair.1
            || pair.1 >= atom_count
            || previous_pair.is_some_and(|previous| previous >= pair)
        {
            return Err(invalid("V7 internal pairs are not canonical"));
        }
        previous_pair = Some(pair);
    }
    let maximum_trial_evaluations = config
        .maximum_torsion_steps
        .checked_mul(
            config
                .maximum_torsions_evaluated
                .min(context.rotatable_child_atom_indices.len()),
        )
        .and_then(|value| value.checked_mul(config.maximum_backtracking_evaluations))
        .and_then(|value| value.checked_mul(2))
        .ok_or_else(|| budget("V7 trial count overflowed"))?;
    let pairs_per_objective = atom_count
        .checked_mul(context.receptor_coordinates_angstrom.len())
        .and_then(|value| value.checked_add(context.evaluated_internal_pairs.len()))
        .ok_or_else(|| budget("V7 pair count overflowed"))?;
    let maximum_total_pairs = pairs_per_objective
        .checked_mul(
            maximum_trial_evaluations
                .checked_add(2)
                .ok_or_else(|| budget("V7 objective count overflowed"))?,
        )
        .ok_or_else(|| budget("V7 total pair count overflowed"))?;
    if maximum_total_pairs > NATIVE_TORSION_V7_MAX_TOTAL_PAIR_EVALUATIONS {
        return Err(budget("V7 total pair budget exceeded"));
    }

    let mut descendants = Vec::with_capacity(context.rotatable_child_atom_indices.len());
    let mut cross_internal_pair_indices =
        Vec::with_capacity(context.rotatable_child_atom_indices.len());
    for rotor in context.rotatable_child_atom_indices.iter().copied() {
        let descendant_indices = (0..atom_count)
            .filter(|candidate| is_descendant(*candidate, rotor, context.parent_atom_indices))
            .collect::<Vec<_>>();
        let mut membership = vec![false; atom_count];
        for index in descendant_indices.iter().copied() {
            membership[index] = true;
        }
        let cross_pairs = context
            .evaluated_internal_pairs
            .iter()
            .copied()
            .enumerate()
            .filter_map(|(pair_index, (first, second))| {
                (membership[first] != membership[second]).then_some(pair_index)
            })
            .collect::<Vec<_>>();
        descendants.push(descendant_indices);
        cross_internal_pair_indices.push(cross_pairs);
    }
    Ok(PreparedContext {
        raw: context,
        descendants,
        cross_internal_pair_indices,
    })
}

fn validate_parent_tree(parents: &[i32]) -> Result<(), NativeTorsionV7Error> {
    let atom_count = parents.len();
    let mut root_count = 0usize;
    for (atom_index, parent) in parents.iter().copied().enumerate() {
        if parent < -1 || parent >= atom_count as i32 || parent == atom_index as i32 {
            return Err(invalid("V7 authority parent tree is invalid"));
        }
        root_count += usize::from(parent == -1);
    }
    if root_count != 1 {
        return Err(invalid(
            "V7 authority parent tree must have exactly one root",
        ));
    }
    for atom_index in 0..atom_count {
        let mut current = atom_index;
        for depth in 0..=atom_count {
            let parent = parents[current];
            if parent < 0 {
                break;
            }
            if depth == atom_count {
                return Err(invalid("V7 authority parent tree contains a cycle"));
            }
            current = parent as usize;
        }
    }
    Ok(())
}

fn is_descendant(candidate: usize, rotor: usize, parents: &[i32]) -> bool {
    let mut current = candidate;
    loop {
        if current == rotor {
            return true;
        }
        let parent = parents[current];
        if parent < 0 {
            return false;
        }
        current = parent as usize;
    }
}

fn objective(
    context: &PreparedContext<'_>,
    coordinates: &[Vec3],
    config: NativeTorsionV7Config,
) -> Result<ObjectiveState, NativeTorsionV7Error> {
    let mut receptor_by_atom = Vec::with_capacity(coordinates.len());
    for (ligand_index, ligand_coordinate) in coordinates.iter().copied().enumerate() {
        let mut atom_penalty = 0.0;
        for (receptor_index, receptor_coordinate) in context
            .raw
            .receptor_coordinates_angstrom
            .iter()
            .copied()
            .enumerate()
        {
            let raw_distance = norm(ligand_coordinate.minus(receptor_coordinate));
            if !raw_distance.is_finite() {
                return Err(derived("V7 receptor distance overflowed"));
            }
            let distance = raw_distance.max(config.epsilon_angstrom);
            let cutoff = config.receptor_overlap_scale
                * (context.raw.ligand_vdw_radii_angstrom[ligand_index]
                    + context.raw.receptor_vdw_radii_angstrom[receptor_index]);
            let overlap = (cutoff - distance).max(0.0);
            let squared = overlap * overlap;
            atom_penalty += squared * squared;
        }
        if !atom_penalty.is_finite() {
            return Err(derived("V7 receptor objective overflowed"));
        }
        receptor_by_atom.push(canonical_zero(atom_penalty));
    }
    let mut internal_by_pair = Vec::with_capacity(context.raw.evaluated_internal_pairs.len());
    for (first, second) in context.raw.evaluated_internal_pairs.iter().copied() {
        let raw_distance = norm(coordinates[first].minus(coordinates[second]));
        if !raw_distance.is_finite() {
            return Err(derived("V7 internal distance overflowed"));
        }
        let distance = raw_distance.max(config.epsilon_angstrom);
        let cutoff = config.internal_overlap_scale
            * (context.raw.ligand_vdw_radii_angstrom[first]
                + context.raw.ligand_vdw_radii_angstrom[second]);
        let overlap = (cutoff - distance).max(0.0);
        let squared = overlap * overlap;
        let penalty = squared * squared;
        if !penalty.is_finite() {
            return Err(derived("V7 internal objective overflowed"));
        }
        internal_by_pair.push(canonical_zero(penalty));
    }
    let receptor = receptor_by_atom.iter().copied().sum::<f64>();
    let internal = internal_by_pair.iter().copied().sum::<f64>();
    let combined = receptor + config.internal_overlap_weight * internal;
    if !receptor.is_finite() || !internal.is_finite() || !combined.is_finite() {
        return Err(derived("V7 combined objective overflowed"));
    }
    Ok(ObjectiveState {
        total: NativeTorsionV7Objective {
            receptor: canonical_zero(receptor),
            internal: canonical_zero(internal),
            combined: canonical_zero(combined),
        },
        receptor_by_atom,
        internal_by_pair,
    })
}

fn rotor_priority(
    context: &PreparedContext<'_>,
    rotor_position: usize,
    state: &ObjectiveState,
    internal_overlap_weight: f64,
) -> f64 {
    let receptor = context.descendants[rotor_position]
        .iter()
        .map(|index| state.receptor_by_atom[*index])
        .sum::<f64>();
    let internal = context.cross_internal_pair_indices[rotor_position]
        .iter()
        .map(|index| state.internal_by_pair[*index])
        .sum::<f64>();
    canonical_zero(receptor + internal_overlap_weight * internal)
}

fn rotate_subtree(
    context: &PreparedContext<'_>,
    coordinates: &[Vec3],
    rotor_position: usize,
    delta_radians: f64,
    epsilon_angstrom: f64,
) -> Result<Vec<Vec3>, NativeTorsionV7Error> {
    let rotor = context.raw.rotatable_child_atom_indices[rotor_position];
    let parent = context.raw.parent_atom_indices[rotor];
    if parent < 0 {
        return Err(invalid("V7 authority marked a root atom as rotatable"));
    }
    let origin = coordinates[parent as usize];
    let axis_vector = coordinates[rotor].minus(origin);
    let axis_norm = norm(axis_vector);
    if !axis_norm.is_finite() || axis_norm <= epsilon_angstrom {
        return Err(NativeTorsionV7Error::new(
            NativeTorsionV7ErrorCode::DegenerateRotor,
            "V7 torsion central bond is degenerate",
        ));
    }
    let axis = axis_vector.scale(1.0 / axis_norm);
    let cosine = libm::cos(delta_radians);
    let sine = libm::sin(delta_radians);
    let mut output = coordinates.to_vec();
    for index in context.descendants[rotor_position].iter().copied() {
        let vector = coordinates[index].minus(origin);
        let rotated = vector
            .scale(cosine)
            .plus(axis.cross(vector).scale(sine))
            .plus(axis.scale(axis.dot(vector) * (1.0 - cosine)))
            .plus(origin);
        if !rotated.is_finite() {
            return Err(derived("V7 torsion rotation overflowed"));
        }
        output[index] = canonical_vec(rotated);
    }
    Ok(output)
}

fn centroid(coordinates: &[Vec3]) -> Vec3 {
    canonical_vec(
        coordinates
            .iter()
            .copied()
            .fold(Vec3::default(), Vec3::plus)
            .scale(1.0 / coordinates.len() as f64),
    )
}

fn normalized_angle(value: f64) -> f64 {
    canonical_zero(libm::atan2(libm::sin(value), libm::cos(value)))
}

fn norm(value: Vec3) -> f64 {
    libm::sqrt(value.x * value.x + value.y * value.y + value.z * value.z)
}

fn compare_f64(left: f64, right: f64) -> Ordering {
    left.partial_cmp(&right)
        .expect("validated V7 objective values must be finite")
}

fn canonical_zero(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

fn canonical_vec(value: Vec3) -> Vec3 {
    Vec3::new(
        canonical_zero(value.x),
        canonical_zero(value.y),
        canonical_zero(value.z),
    )
}

const fn invalid(message: &'static str) -> NativeTorsionV7Error {
    NativeTorsionV7Error::new(NativeTorsionV7ErrorCode::InvalidInput, message)
}

const fn non_finite(message: &'static str) -> NativeTorsionV7Error {
    NativeTorsionV7Error::new(NativeTorsionV7ErrorCode::NonFiniteInput, message)
}

const fn budget(message: &'static str) -> NativeTorsionV7Error {
    NativeTorsionV7Error::new(NativeTorsionV7ErrorCode::PairBudgetExceeded, message)
}

const fn derived(message: &'static str) -> NativeTorsionV7Error {
    NativeTorsionV7Error::new(NativeTorsionV7ErrorCode::NonFiniteDerivedValue, message)
}

#[cfg(test)]
mod tests {
    use super::*;

    type Fixture = (
        Vec<Vec3>,
        Vec<Vec3>,
        Vec<f64>,
        Vec<Vec3>,
        Vec<f64>,
        Vec<f64>,
        Vec<i32>,
        Vec<usize>,
        Vec<(usize, usize)>,
    );

    fn context<'a>(
        receptor: &'a [Vec3],
        receptor_radii: &'a [f64],
        ligand_radii: &'a [f64],
        parents: &'a [i32],
        rotors: &'a [usize],
        internal_pairs: &'a [(usize, usize)],
    ) -> NativeTorsionV7Context<'a> {
        NativeTorsionV7Context {
            receptor_coordinates_angstrom: receptor,
            receptor_vdw_radii_angstrom: receptor_radii,
            ligand_vdw_radii_angstrom: ligand_radii,
            pocket_center_angstrom: Vec3::new(1.5, 0.0, 0.0),
            parent_atom_indices: parents,
            rotatable_child_atom_indices: rotors,
            evaluated_internal_pairs: internal_pairs,
        }
    }

    fn v7_request<'a>(
        context: NativeTorsionV7Context<'a>,
        source: &'a [Vec3],
        baseline: &'a [Vec3],
        angles: &'a [f64],
        proposal_is_torsion_eligible: bool,
    ) -> NativeTorsionV7Request<'a> {
        NativeTorsionV7Request {
            context,
            source_coordinates_angstrom: source,
            baseline_v6_coordinates_angstrom: baseline,
            baseline_v6_torsion_angles_radians: angles,
            proposal_is_torsion_eligible,
            max_steps: 4,
            baseline_v6_accepted_steps: 0,
        }
    }

    fn fixture() -> Fixture {
        let source = vec![
            Vec3::new(0.0, 0.0, 0.0),
            Vec3::new(1.0, 0.0, 0.0),
            Vec3::new(2.0, 0.0, 0.0),
            Vec3::new(2.0, 1.0, 0.0),
        ];
        (
            source.clone(),
            source,
            vec![0.0; 4],
            vec![Vec3::new(2.0, 1.0, 0.0), Vec3::new(20.0, 20.0, 20.0)],
            vec![1.0, 1.0],
            vec![1.0; 4],
            vec![-1, 0, 1, 2],
            vec![2],
            vec![(0, 2), (0, 3), (1, 3)],
        )
    }

    fn accepting_config() -> NativeTorsionV7Config {
        NativeTorsionV7Config {
            minimum_selected_final_receptor_penalty: 0.0,
            maximum_selected_final_receptor_penalty: 1_000_000.0,
            ..NativeTorsionV7Config::default()
        }
    }

    #[test]
    fn authority_rotor_is_deterministic_bounded_and_selected() {
        let (
            source,
            baseline,
            angles,
            receptor,
            receptor_radii,
            ligand_radii,
            parents,
            rotors,
            pairs,
        ) = fixture();
        let request = context(
            &receptor,
            &receptor_radii,
            &ligand_radii,
            &parents,
            &rotors,
            &pairs,
        );
        let outcome = refine_interaction_aware_torsion_contact_v7(
            v7_request(request, &source, &baseline, &angles, true),
            accepting_config(),
        )
        .unwrap();
        let second = refine_interaction_aware_torsion_contact_v7(
            v7_request(request, &source, &baseline, &angles, true),
            accepting_config(),
        )
        .unwrap();
        assert_eq!(outcome, second);
        assert!(outcome.torsion_evaluated());
        assert!(outcome.torsion_variant_available());
        assert!(outcome.torsion_selected());
        assert_eq!(outcome.evaluated_torsion_steps(), 4);
        assert_eq!(outcome.accepted_torsion_steps(), 4);
        assert_eq!(outcome.accepted_steps(), 4);
        assert!(outcome.optimized_objective().combined() < outcome.baseline_objective().combined());
        assert!(
            outcome.optimized_objective().receptor() <= outcome.baseline_objective().receptor()
        );
        assert!(outcome
            .evaluated_moves()
            .iter()
            .all(|movement| movement.rotatable_child_atom_index() == 2));
        assert!(
            outcome.evaluated_total_torsion_path_radians()
                <= accepting_config().maximum_total_torsion_path_radians + 1.0e-18
        );
        for (atom_i, atom_j) in [(0usize, 1usize), (1, 2), (2, 3)] {
            let before = norm(baseline[atom_i].minus(baseline[atom_j]));
            let actual = norm(
                outcome.final_coordinates_angstrom()[atom_i]
                    .minus(outcome.final_coordinates_angstrom()[atom_j]),
            );
            assert!((actual - before).abs() <= 1.0e-12);
        }
    }

    #[test]
    fn unavailable_or_outside_window_retains_v6_but_preserves_optimized_state() {
        let (
            source,
            baseline,
            angles,
            receptor,
            receptor_radii,
            ligand_radii,
            parents,
            rotors,
            pairs,
        ) = fixture();
        let request = context(
            &receptor,
            &receptor_radii,
            &ligand_radii,
            &parents,
            &rotors,
            &pairs,
        );
        let ineligible = refine_interaction_aware_torsion_contact_v7(
            v7_request(request, &source, &baseline, &angles, false),
            accepting_config(),
        )
        .unwrap();
        assert_eq!(
            ineligible.skip_reason(),
            NativeTorsionV7SkipReason::NotEligible
        );
        assert!(!ineligible.torsion_evaluated());
        assert_eq!(ineligible.objective_evaluation_count(), 2);
        assert_eq!(ineligible.final_coordinates_angstrom(), baseline);

        let rejecting = NativeTorsionV7Config {
            minimum_selected_final_receptor_penalty: 0.0,
            maximum_selected_final_receptor_penalty: 1.0e-12,
            ..NativeTorsionV7Config::default()
        };
        let rejected = refine_interaction_aware_torsion_contact_v7(
            v7_request(request, &source, &baseline, &angles, true),
            rejecting,
        )
        .unwrap();
        assert!(rejected.torsion_variant_available());
        assert!(!rejected.torsion_selected());
        assert!(rejected.accepted_moves().is_empty());
        assert_ne!(rejected.optimized_coordinates_angstrom(), baseline);
        assert_eq!(rejected.final_coordinates_angstrom(), baseline);
        assert_eq!(
            rejected.selection_reason(),
            NativeTorsionV7SelectionReason::V6RetainedOutsideFinalReceptorPenaltyWindow
        );
    }

    #[test]
    fn unreachable_window_prunes_without_trials() {
        let (
            source,
            baseline,
            angles,
            receptor,
            receptor_radii,
            ligand_radii,
            parents,
            rotors,
            pairs,
        ) = fixture();
        let pruned = refine_interaction_aware_torsion_contact_v7(
            v7_request(
                context(
                    &receptor,
                    &receptor_radii,
                    &ligand_radii,
                    &parents,
                    &rotors,
                    &pairs,
                ),
                &source,
                &baseline,
                &angles,
                true,
            ),
            NativeTorsionV7Config {
                minimum_selected_final_receptor_penalty: 1_000_000.0,
                maximum_selected_final_receptor_penalty: 1_000_001.0,
                ..NativeTorsionV7Config::default()
            },
        )
        .unwrap();
        assert_eq!(
            pruned.skip_reason(),
            NativeTorsionV7SkipReason::SelectionWindowUnreachable
        );
        assert!(!pruned.selection_window_reachable());
        assert_eq!(pruned.torsion_trial_objective_evaluation_count(), 0);
        assert_eq!(pruned.objective_evaluation_count(), 2);
    }

    #[test]
    fn malformed_authority_degenerate_bond_and_nonfinite_inputs_fail_closed() {
        let (
            source,
            baseline,
            angles,
            receptor,
            receptor_radii,
            ligand_radii,
            _parents,
            rotors,
            pairs,
        ) = fixture();
        let cycle = vec![1, 0, 1, 2];
        let error = refine_interaction_aware_torsion_contact_v7(
            v7_request(
                context(
                    &receptor,
                    &receptor_radii,
                    &ligand_radii,
                    &cycle,
                    &rotors,
                    &pairs,
                ),
                &source,
                &baseline,
                &angles,
                true,
            ),
            accepting_config(),
        )
        .unwrap_err();
        assert_eq!(error.code(), NativeTorsionV7ErrorCode::InvalidInput);

        let parents = vec![-1, 0, 1, 2];
        let mut degenerate = baseline.clone();
        degenerate[2] = degenerate[1];
        let error = refine_interaction_aware_torsion_contact_v7(
            v7_request(
                context(
                    &receptor,
                    &receptor_radii,
                    &ligand_radii,
                    &parents,
                    &rotors,
                    &pairs,
                ),
                &source,
                &degenerate,
                &angles,
                true,
            ),
            accepting_config(),
        )
        .unwrap_err();
        assert_eq!(error.code(), NativeTorsionV7ErrorCode::DegenerateRotor);

        let mut nonfinite = source.clone();
        nonfinite[0].x = f64::NAN;
        let error = refine_interaction_aware_torsion_contact_v7(
            v7_request(
                context(
                    &receptor,
                    &receptor_radii,
                    &ligand_radii,
                    &parents,
                    &rotors,
                    &pairs,
                ),
                &nonfinite,
                &baseline,
                &angles,
                true,
            ),
            accepting_config(),
        )
        .unwrap_err();
        assert_eq!(error.code(), NativeTorsionV7ErrorCode::NonFiniteInput);

        let mut overflowing = source;
        overflowing[0].x = 1.0e308;
        let error = refine_interaction_aware_torsion_contact_v7(
            v7_request(
                context(
                    &receptor,
                    &receptor_radii,
                    &ligand_radii,
                    &parents,
                    &rotors,
                    &pairs,
                ),
                &overflowing,
                &baseline,
                &angles,
                true,
            ),
            accepting_config(),
        )
        .unwrap_err();
        assert_eq!(
            error.code(),
            NativeTorsionV7ErrorCode::NonFiniteDerivedValue
        );
    }

    #[test]
    fn total_pair_work_is_bounded_before_objective_evaluation() {
        let ligand_atom_count = NATIVE_TORSION_V7_MAX_LIGAND_ATOMS;
        let receptor_atom_count = 20_000usize;
        let source = vec![Vec3::default(); ligand_atom_count];
        let angles = vec![0.0; ligand_atom_count];
        let receptor = vec![Vec3::new(20.0, 20.0, 20.0); receptor_atom_count];
        let receptor_radii = vec![1.0; receptor_atom_count];
        let ligand_radii = vec![1.0; ligand_atom_count];
        let mut parents = vec![0; ligand_atom_count];
        parents[0] = -1;
        let rotors = vec![1];
        let error = refine_interaction_aware_torsion_contact_v7(
            v7_request(
                context(
                    &receptor,
                    &receptor_radii,
                    &ligand_radii,
                    &parents,
                    &rotors,
                    &[],
                ),
                &source,
                &source,
                &angles,
                true,
            ),
            accepting_config(),
        )
        .unwrap_err();
        assert_eq!(error.code(), NativeTorsionV7ErrorCode::PairBudgetExceeded);
    }
}
