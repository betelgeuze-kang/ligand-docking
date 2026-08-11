use std::fmt;

use crate::Vec3;

pub const NATIVE_RIGID_REFINEMENT_MAX_LIGAND_ATOMS: usize = 512;
pub const NATIVE_RIGID_REFINEMENT_MAX_RECEPTOR_ATOMS: usize = 65_536;
pub const NATIVE_RIGID_REFINEMENT_MAX_PAIR_EVALUATIONS: usize = 250_000_000;
pub const NATIVE_RIGID_REFINEMENT_MAX_STEPS: usize = 128;
pub const NATIVE_RIGID_V6_NEAR_CLEAR_PENALTY: f64 = 0.000_244_140_625;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeRigidRefinementErrorCode {
    InvalidInput,
    NonFiniteInput,
    PairBudgetExceeded,
    NonFiniteDerivedValue,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeRigidRefinementError {
    code: NativeRigidRefinementErrorCode,
    message: &'static str,
}

impl NativeRigidRefinementError {
    const fn new(code: NativeRigidRefinementErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeRigidRefinementErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeRigidRefinementError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native rigid refinement: {}", self.message)
    }
}

impl std::error::Error for NativeRigidRefinementError {}

#[derive(Clone, Copy, Debug)]
pub struct NativeRigidRefinementContext<'a> {
    pub receptor_coordinates_angstrom: &'a [Vec3],
    pub receptor_vdw_radii_angstrom: &'a [f64],
    pub ligand_vdw_radii_angstrom: &'a [f64],
    pub pocket_center_angstrom: Vec3,
    pub pocket_radius_angstrom: f64,
}

impl NativeRigidRefinementContext<'_> {
    fn validate(self, ligand_atom_count: usize) -> Result<(), NativeRigidRefinementError> {
        if self.receptor_coordinates_angstrom.is_empty()
            || self.receptor_coordinates_angstrom.len() != self.receptor_vdw_radii_angstrom.len()
            || self.receptor_coordinates_angstrom.len() > NATIVE_RIGID_REFINEMENT_MAX_RECEPTOR_ATOMS
            || ligand_atom_count == 0
            || ligand_atom_count != self.ligand_vdw_radii_angstrom.len()
            || ligand_atom_count > NATIVE_RIGID_REFINEMENT_MAX_LIGAND_ATOMS
        {
            return Err(invalid("rigid-refinement context shape is invalid"));
        }
        let pair_count = ligand_atom_count
            .checked_mul(self.receptor_coordinates_angstrom.len())
            .ok_or_else(|| budget("rigid-refinement pair count overflowed"))?;
        if pair_count > NATIVE_RIGID_REFINEMENT_MAX_PAIR_EVALUATIONS {
            return Err(budget("rigid-refinement pair budget exceeded"));
        }
        if !self.pocket_center_angstrom.is_finite()
            || !self.pocket_radius_angstrom.is_finite()
            || self.pocket_radius_angstrom <= 0.0
            || self
                .receptor_coordinates_angstrom
                .iter()
                .any(|coordinate| !coordinate.is_finite())
            || self
                .receptor_vdw_radii_angstrom
                .iter()
                .chain(self.ligand_vdw_radii_angstrom)
                .any(|radius| !radius.is_finite() || *radius <= 0.0)
        {
            return Err(non_finite("rigid-refinement context is non-finite"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeRigidV2Config {
    pub overlap_scale: f64,
    pub maximum_step_angstrom: f64,
    pub minimum_step_angstrom: f64,
    pub maximum_total_translation_angstrom: f64,
    pub maximum_backtracking_evaluations: usize,
    pub penalty_tolerance: f64,
    pub epsilon_angstrom: f64,
}

impl Default for NativeRigidV2Config {
    fn default() -> Self {
        Self {
            overlap_scale: 0.75,
            maximum_step_angstrom: 0.30,
            minimum_step_angstrom: 0.009_375,
            maximum_total_translation_angstrom: 2.25,
            maximum_backtracking_evaluations: 6,
            penalty_tolerance: 1.0e-18,
            epsilon_angstrom: 1.0e-9,
        }
    }
}

impl NativeRigidV2Config {
    fn validate(self) -> Result<(), NativeRigidRefinementError> {
        let values = [
            self.overlap_scale,
            self.maximum_step_angstrom,
            self.minimum_step_angstrom,
            self.maximum_total_translation_angstrom,
            self.penalty_tolerance,
            self.epsilon_angstrom,
        ];
        if values
            .iter()
            .any(|value| !value.is_finite() || *value <= 0.0)
        {
            return Err(non_finite("V2 configuration is non-finite"));
        }
        if !(0.55..=1.0).contains(&self.overlap_scale)
            || self.minimum_step_angstrom > self.maximum_step_angstrom
            || self.maximum_step_angstrom > self.maximum_total_translation_angstrom
            || !(1..=16).contains(&self.maximum_backtracking_evaluations)
        {
            return Err(invalid("V2 configuration bounds are inconsistent"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeRigidV3Config {
    pub v2: NativeRigidV2Config,
    pub maximum_rotation_step_radians: f64,
    pub minimum_rotation_step_radians: f64,
    pub maximum_total_rotation_radians: f64,
    pub maximum_rotation_steps: usize,
    pub minimum_rotation_relative_penalty_reduction: f64,
    pub maximum_centroid_offset_angstrom: f64,
}

impl Default for NativeRigidV3Config {
    fn default() -> Self {
        Self {
            v2: NativeRigidV2Config::default(),
            maximum_rotation_step_radians: std::f64::consts::PI / 36.0,
            minimum_rotation_step_radians: std::f64::consts::PI / 1_152.0,
            maximum_total_rotation_radians: std::f64::consts::PI / 18.0,
            maximum_rotation_steps: 2,
            minimum_rotation_relative_penalty_reduction: 0.01,
            maximum_centroid_offset_angstrom: 4.0,
        }
    }
}

impl NativeRigidV3Config {
    #[must_use]
    pub fn clearance_v4() -> Self {
        Self {
            v2: NativeRigidV2Config {
                overlap_scale: 0.80,
                maximum_total_translation_angstrom: 4.0,
                ..NativeRigidV2Config::default()
            },
            maximum_total_rotation_radians: std::f64::consts::PI / 6.0,
            maximum_rotation_steps: 6,
            ..Self::default()
        }
    }

    fn validate(self) -> Result<(), NativeRigidRefinementError> {
        self.v2.validate()?;
        let values = [
            self.maximum_rotation_step_radians,
            self.minimum_rotation_step_radians,
            self.maximum_total_rotation_radians,
            self.minimum_rotation_relative_penalty_reduction,
            self.maximum_centroid_offset_angstrom,
        ];
        if values
            .iter()
            .any(|value| !value.is_finite() || *value <= 0.0)
        {
            return Err(non_finite("V3 configuration is non-finite"));
        }
        if self.minimum_rotation_step_radians > self.maximum_rotation_step_radians
            || self.maximum_rotation_step_radians > self.maximum_total_rotation_radians
            || !(1..=8).contains(&self.maximum_rotation_steps)
            || self.minimum_rotation_relative_penalty_reduction > 0.25
            || !(0.5..=8.0).contains(&self.maximum_centroid_offset_angstrom)
        {
            return Err(invalid("V3 configuration bounds are inconsistent"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeRigidRefinementProfile {
    V2Translation,
    V3TranslationRotation,
    V6BaselineV2,
    V6BaselineV3,
    V6ClearanceV4,
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeRigidRefinementOutcome {
    profile: NativeRigidRefinementProfile,
    coordinates_angstrom: Vec<Vec3>,
    initial_penalty: f64,
    final_penalty: f64,
    accepted_steps: usize,
    accepted_translation_steps: usize,
    accepted_rotation_steps: usize,
    line_search_evaluation_count: usize,
    fallback_direction_step_count: usize,
    total_translation_angstrom: Vec3,
    total_rotation_vector_radians: Vec3,
    total_rotation_path_radians: f64,
    initial_centroid_offset_angstrom: f64,
    final_centroid_offset_angstrom: f64,
    maximum_centroid_offset_angstrom: f64,
}

impl NativeRigidRefinementOutcome {
    #[must_use]
    pub const fn profile(&self) -> NativeRigidRefinementProfile {
        self.profile
    }

    #[must_use]
    pub fn coordinates_angstrom(&self) -> &[Vec3] {
        &self.coordinates_angstrom
    }

    #[must_use]
    pub const fn initial_penalty(&self) -> f64 {
        self.initial_penalty
    }

    #[must_use]
    pub const fn final_penalty(&self) -> f64 {
        self.final_penalty
    }

    #[must_use]
    pub const fn accepted_steps(&self) -> usize {
        self.accepted_steps
    }

    #[must_use]
    pub const fn accepted_translation_steps(&self) -> usize {
        self.accepted_translation_steps
    }

    #[must_use]
    pub const fn accepted_rotation_steps(&self) -> usize {
        self.accepted_rotation_steps
    }

    #[must_use]
    pub const fn line_search_evaluation_count(&self) -> usize {
        self.line_search_evaluation_count
    }

    #[must_use]
    pub const fn fallback_direction_step_count(&self) -> usize {
        self.fallback_direction_step_count
    }

    #[must_use]
    pub const fn total_translation_angstrom(&self) -> Vec3 {
        self.total_translation_angstrom
    }

    #[must_use]
    pub const fn total_rotation_vector_radians(&self) -> Vec3 {
        self.total_rotation_vector_radians
    }

    #[must_use]
    pub const fn total_rotation_path_radians(&self) -> f64 {
        self.total_rotation_path_radians
    }

    #[must_use]
    pub const fn initial_centroid_offset_angstrom(&self) -> f64 {
        self.initial_centroid_offset_angstrom
    }

    #[must_use]
    pub const fn final_centroid_offset_angstrom(&self) -> f64 {
        self.final_centroid_offset_angstrom
    }

    #[must_use]
    pub const fn maximum_centroid_offset_angstrom(&self) -> f64 {
        self.maximum_centroid_offset_angstrom
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeRigidV6Outcome {
    selected: NativeRigidRefinementOutcome,
    comparison_v2: Option<NativeRigidRefinementOutcome>,
    baseline_v3: Option<NativeRigidRefinementOutcome>,
    clearance_v4: Option<NativeRigidRefinementOutcome>,
    baseline_duplicate_of_v2: bool,
    clearance_evaluated: bool,
    clearance_selected: bool,
}

impl NativeRigidV6Outcome {
    #[must_use]
    pub const fn selected(&self) -> &NativeRigidRefinementOutcome {
        &self.selected
    }

    #[must_use]
    pub const fn comparison_v2(&self) -> Option<&NativeRigidRefinementOutcome> {
        self.comparison_v2.as_ref()
    }

    #[must_use]
    pub const fn baseline_v3(&self) -> Option<&NativeRigidRefinementOutcome> {
        self.baseline_v3.as_ref()
    }

    #[must_use]
    pub const fn clearance_v4(&self) -> Option<&NativeRigidRefinementOutcome> {
        self.clearance_v4.as_ref()
    }

    #[must_use]
    pub const fn baseline_duplicate_of_v2(&self) -> bool {
        self.baseline_duplicate_of_v2
    }

    #[must_use]
    pub const fn clearance_evaluated(&self) -> bool {
        self.clearance_evaluated
    }

    #[must_use]
    pub const fn clearance_selected(&self) -> bool {
        self.clearance_selected
    }
}

pub fn refine_interaction_aware_rigid_v2(
    context: NativeRigidRefinementContext<'_>,
    coordinates_angstrom: &[Vec3],
    max_steps: usize,
    config: NativeRigidV2Config,
) -> Result<NativeRigidRefinementOutcome, NativeRigidRefinementError> {
    validate_request(context, coordinates_angstrom, max_steps)?;
    config.validate()?;
    let mut coordinates = coordinates_angstrom.to_vec();
    let initial_penalty = penalty_and_direction(context, &coordinates, config)?.0;
    let mut total_shift = Vec3::default();
    let mut accepted_steps = 0usize;
    let mut line_search_evaluation_count = 0usize;
    let mut fallback_direction_step_count = 0usize;

    for _ in 0..max_steps {
        let (penalty, aggregate_direction) = penalty_and_direction(context, &coordinates, config)?;
        if penalty <= config.penalty_tolerance {
            break;
        }
        let remaining = config.maximum_total_translation_angstrom - norm(total_shift);
        if remaining <= config.minimum_step_angstrom {
            break;
        }
        let directions = candidate_directions(context, &coordinates, aggregate_direction, config)?;
        if directions.is_empty() {
            break;
        }
        let base_step = config.maximum_step_angstrom.min(remaining);
        let mut best: Option<TranslationTrial> = None;
        for (direction_index, direction) in directions.iter().copied().enumerate() {
            let mut step_size = base_step;
            for backtracking_index in 0..config.maximum_backtracking_evaluations {
                if step_size < config.minimum_step_angstrom {
                    break;
                }
                let step = direction.scale(step_size);
                let trial_shift = total_shift.plus(step);
                if norm(trial_shift)
                    > config.maximum_total_translation_angstrom + config.epsilon_angstrom
                {
                    step_size *= 0.5;
                    continue;
                }
                let trial = translated(&coordinates, step);
                let trial_penalty = penalty_and_direction(context, &trial, config)?.0;
                line_search_evaluation_count += 1;
                let candidate = TranslationTrial {
                    penalty: trial_penalty,
                    direction_index,
                    backtracking_index,
                    coordinates: trial,
                    total_shift: trial_shift,
                };
                if best.as_ref().is_none_or(|current| candidate.less(current)) {
                    best = Some(candidate);
                }
                step_size *= 0.5;
            }
        }
        let required_reduction = config.penalty_tolerance.max(penalty.abs() * 1.0e-12);
        let Some(best) = best.filter(|candidate| candidate.penalty <= penalty - required_reduction)
        else {
            break;
        };
        coordinates = best.coordinates;
        total_shift = best.total_shift;
        accepted_steps += 1;
        fallback_direction_step_count += usize::from(best.direction_index > 0);
    }
    let final_penalty = penalty_and_direction(context, &coordinates, config)?.0;
    Ok(NativeRigidRefinementOutcome {
        profile: NativeRigidRefinementProfile::V2Translation,
        coordinates_angstrom: coordinates,
        initial_penalty,
        final_penalty,
        accepted_steps,
        accepted_translation_steps: accepted_steps,
        accepted_rotation_steps: 0,
        line_search_evaluation_count,
        fallback_direction_step_count,
        total_translation_angstrom: canonical_vec(total_shift),
        total_rotation_vector_radians: Vec3::default(),
        total_rotation_path_radians: 0.0,
        initial_centroid_offset_angstrom: 0.0,
        final_centroid_offset_angstrom: 0.0,
        maximum_centroid_offset_angstrom: 0.0,
    })
}

pub fn refine_interaction_aware_rigid_v3(
    context: NativeRigidRefinementContext<'_>,
    coordinates_angstrom: &[Vec3],
    max_steps: usize,
    config: NativeRigidV3Config,
) -> Result<NativeRigidRefinementOutcome, NativeRigidRefinementError> {
    validate_request(context, coordinates_angstrom, max_steps)?;
    config.validate()?;
    let mut coordinates = coordinates_angstrom.to_vec();
    let initial_penalty = penalty_and_direction(context, &coordinates, config.v2)?.0;
    let initial_centroid_offset =
        norm(centroid(&coordinates).minus(context.pocket_center_angstrom));
    let maximum_centroid_offset = config
        .maximum_centroid_offset_angstrom
        .min(context.pocket_radius_angstrom);
    let mut total_shift = Vec3::default();
    let mut total_rotation_vector = Vec3::default();
    let mut total_rotation_path = 0.0;
    let mut accepted_steps = 0usize;
    let mut accepted_rotation_steps = 0usize;
    let mut line_search_evaluation_count = 0usize;
    let mut fallback_direction_step_count = 0usize;

    for _ in 0..max_steps {
        let (penalty, aggregate_direction) =
            penalty_and_direction(context, &coordinates, config.v2)?;
        if penalty <= config.v2.penalty_tolerance {
            break;
        }
        let remaining_translation =
            config.v2.maximum_total_translation_angstrom - norm(total_shift);
        let remaining_rotation = config.maximum_total_rotation_radians - total_rotation_path;
        if remaining_translation <= config.v2.minimum_step_angstrom
            && remaining_rotation <= config.minimum_rotation_step_radians
        {
            break;
        }
        let directions =
            candidate_directions(context, &coordinates, aggregate_direction, config.v2)?;
        let mut best: Option<RigidTrial> = None;
        if remaining_translation > config.v2.minimum_step_angstrom {
            let base_step = config.v2.maximum_step_angstrom.min(remaining_translation);
            for (direction_index, direction) in directions.iter().copied().enumerate() {
                let mut step_size = base_step;
                for backtracking_index in 0..config.v2.maximum_backtracking_evaluations {
                    if step_size < config.v2.minimum_step_angstrom {
                        break;
                    }
                    let step = direction.scale(step_size);
                    let trial_shift = total_shift.plus(step);
                    if norm(trial_shift)
                        > config.v2.maximum_total_translation_angstrom + config.v2.epsilon_angstrom
                    {
                        step_size *= 0.5;
                        continue;
                    }
                    let trial = translated(&coordinates, step);
                    let trial_centroid_offset =
                        norm(centroid(&trial).minus(context.pocket_center_angstrom));
                    if trial_centroid_offset > maximum_centroid_offset + config.v2.epsilon_angstrom
                    {
                        step_size *= 0.5;
                        continue;
                    }
                    let trial_penalty = penalty_and_direction(context, &trial, config.v2)?.0;
                    line_search_evaluation_count += 1;
                    let candidate = RigidTrial {
                        penalty: trial_penalty,
                        direction_index,
                        backtracking_index,
                        coordinates: trial,
                        total_shift: trial_shift,
                        total_rotation_vector,
                        total_rotation_path,
                    };
                    if best.as_ref().is_none_or(|current| candidate.less(current)) {
                        best = Some(candidate);
                    }
                    step_size *= 0.5;
                }
            }
        }

        let required_reduction = config.v2.penalty_tolerance.max(penalty.abs() * 1.0e-12);
        let translation_improves = best
            .as_ref()
            .is_some_and(|candidate| candidate.penalty <= penalty - required_reduction);
        let torque = rotation_torque(context, &coordinates, config.v2)?;
        let torque_norm = norm(torque);
        if !translation_improves
            && torque_norm > config.v2.epsilon_angstrom
            && remaining_rotation > config.minimum_rotation_step_radians
            && accepted_rotation_steps < config.maximum_rotation_steps
        {
            let axis = torque.scale(1.0 / torque_norm);
            let rotation_required_reduction = required_reduction
                .max(penalty.abs() * config.minimum_rotation_relative_penalty_reduction);
            let mut angle = config.maximum_rotation_step_radians.min(remaining_rotation);
            for backtracking_index in 0..config.v2.maximum_backtracking_evaluations {
                if angle < config.minimum_rotation_step_radians {
                    break;
                }
                let rotation_step = axis.scale(angle);
                let trial = rotate_about_centroid(&coordinates, rotation_step)?;
                let trial_penalty = penalty_and_direction(context, &trial, config.v2)?.0;
                line_search_evaluation_count += 1;
                let candidate = RigidTrial {
                    penalty: trial_penalty,
                    direction_index: 2,
                    backtracking_index,
                    coordinates: trial,
                    total_shift,
                    total_rotation_vector: total_rotation_vector.plus(rotation_step),
                    total_rotation_path: total_rotation_path + angle,
                };
                if trial_penalty <= penalty - rotation_required_reduction
                    && best.as_ref().is_none_or(|current| candidate.less(current))
                {
                    best = Some(candidate);
                }
                angle *= 0.5;
            }
        }
        let Some(best) = best.filter(|candidate| candidate.penalty <= penalty - required_reduction)
        else {
            break;
        };
        coordinates = best.coordinates;
        total_shift = best.total_shift;
        total_rotation_vector = best.total_rotation_vector;
        total_rotation_path = best.total_rotation_path;
        accepted_steps += 1;
        accepted_rotation_steps += usize::from(best.direction_index == 2);
        fallback_direction_step_count += usize::from(best.direction_index == 1);
    }
    let final_penalty = penalty_and_direction(context, &coordinates, config.v2)?.0;
    let final_centroid_offset = norm(centroid(&coordinates).minus(context.pocket_center_angstrom));
    Ok(NativeRigidRefinementOutcome {
        profile: NativeRigidRefinementProfile::V3TranslationRotation,
        coordinates_angstrom: coordinates,
        initial_penalty,
        final_penalty,
        accepted_steps,
        accepted_translation_steps: accepted_steps - accepted_rotation_steps,
        accepted_rotation_steps,
        line_search_evaluation_count,
        fallback_direction_step_count,
        total_translation_angstrom: canonical_vec(total_shift),
        total_rotation_vector_radians: canonical_vec(total_rotation_vector),
        total_rotation_path_radians: canonical_zero(total_rotation_path),
        initial_centroid_offset_angstrom: initial_centroid_offset,
        final_centroid_offset_angstrom: final_centroid_offset,
        maximum_centroid_offset_angstrom: maximum_centroid_offset,
    })
}

pub fn refine_interaction_aware_rigid_v6(
    context: NativeRigidRefinementContext<'_>,
    coordinates_angstrom: &[Vec3],
    max_steps: usize,
    v3_lane: bool,
    v2_config: NativeRigidV2Config,
    v3_config: NativeRigidV3Config,
    clearance_config: NativeRigidV3Config,
) -> Result<NativeRigidV6Outcome, NativeRigidRefinementError> {
    if !v3_lane {
        let mut selected =
            refine_interaction_aware_rigid_v2(context, coordinates_angstrom, max_steps, v2_config)?;
        selected.profile = NativeRigidRefinementProfile::V6BaselineV2;
        return Ok(NativeRigidV6Outcome {
            selected,
            comparison_v2: None,
            baseline_v3: None,
            clearance_v4: None,
            baseline_duplicate_of_v2: false,
            clearance_evaluated: false,
            clearance_selected: false,
        });
    }
    let comparison_v2 =
        refine_interaction_aware_rigid_v2(context, coordinates_angstrom, max_steps, v2_config)?;
    let mut baseline_v3 =
        refine_interaction_aware_rigid_v3(context, coordinates_angstrom, max_steps, v3_config)?;
    let duplicate = coordinates_bit_equal(
        comparison_v2.coordinates_angstrom(),
        baseline_v3.coordinates_angstrom(),
    );
    let clearance_evaluated =
        duplicate || baseline_v3.final_penalty() <= NATIVE_RIGID_V6_NEAR_CLEAR_PENALTY;
    let mut clearance_v4 = None;
    let mut clearance_selected = false;
    if clearance_evaluated {
        let mut candidate = refine_interaction_aware_rigid_v3(
            context,
            coordinates_angstrom,
            max_steps,
            clearance_config,
        )?;
        candidate.profile = NativeRigidRefinementProfile::V6ClearanceV4;
        clearance_selected = duplicate || candidate.final_penalty() < candidate.initial_penalty();
        clearance_v4 = Some(candidate);
    }
    baseline_v3.profile = NativeRigidRefinementProfile::V6BaselineV3;
    let selected = if clearance_selected {
        clearance_v4
            .as_ref()
            .expect("clearance selection requires evaluated result")
            .clone()
    } else {
        baseline_v3.clone()
    };
    Ok(NativeRigidV6Outcome {
        selected,
        comparison_v2: Some(comparison_v2),
        baseline_v3: Some(baseline_v3),
        clearance_v4,
        baseline_duplicate_of_v2: duplicate,
        clearance_evaluated,
        clearance_selected,
    })
}

#[derive(Clone, Debug)]
struct TranslationTrial {
    penalty: f64,
    direction_index: usize,
    backtracking_index: usize,
    coordinates: Vec<Vec3>,
    total_shift: Vec3,
}

impl TranslationTrial {
    fn less(&self, other: &Self) -> bool {
        (self.penalty, self.direction_index, self.backtracking_index)
            < (
                other.penalty,
                other.direction_index,
                other.backtracking_index,
            )
    }
}

#[derive(Clone, Debug)]
struct RigidTrial {
    penalty: f64,
    direction_index: usize,
    backtracking_index: usize,
    coordinates: Vec<Vec3>,
    total_shift: Vec3,
    total_rotation_vector: Vec3,
    total_rotation_path: f64,
}

impl RigidTrial {
    fn less(&self, other: &Self) -> bool {
        (self.penalty, self.direction_index, self.backtracking_index)
            < (
                other.penalty,
                other.direction_index,
                other.backtracking_index,
            )
    }
}

fn validate_request(
    context: NativeRigidRefinementContext<'_>,
    coordinates: &[Vec3],
    max_steps: usize,
) -> Result<(), NativeRigidRefinementError> {
    context.validate(coordinates.len())?;
    if !(1..=NATIVE_RIGID_REFINEMENT_MAX_STEPS).contains(&max_steps) {
        return Err(invalid("rigid-refinement step count is outside [1,128]"));
    }
    if coordinates.iter().any(|coordinate| !coordinate.is_finite()) {
        return Err(non_finite("rigid-refinement coordinates are non-finite"));
    }
    Ok(())
}

fn penalty_and_direction(
    context: NativeRigidRefinementContext<'_>,
    coordinates: &[Vec3],
    config: NativeRigidV2Config,
) -> Result<(f64, Vec3), NativeRigidRefinementError> {
    let mut penalty = 0.0;
    let mut direction = Vec3::default();
    for (ligand_index, ligand) in coordinates.iter().copied().enumerate() {
        for (receptor_index, receptor) in context
            .receptor_coordinates_angstrom
            .iter()
            .copied()
            .enumerate()
        {
            let delta = ligand.minus(receptor);
            let distance = norm(delta).max(config.epsilon_angstrom);
            let cutoff = config.overlap_scale
                * (context.ligand_vdw_radii_angstrom[ligand_index]
                    + context.receptor_vdw_radii_angstrom[receptor_index]);
            let penetration = (cutoff - distance).max(0.0);
            let squared = penetration * penetration;
            penalty += squared * squared;
            direction = direction.plus(delta.scale(squared * penetration / distance));
        }
    }
    if !penalty.is_finite() || !direction.is_finite() {
        return Err(derived("rigid-refinement objective overflowed"));
    }
    Ok((canonical_zero(penalty), canonical_vec(direction)))
}

fn maximum_penetration_direction(
    context: NativeRigidRefinementContext<'_>,
    coordinates: &[Vec3],
    config: NativeRigidV2Config,
) -> Result<Vec3, NativeRigidRefinementError> {
    let mut best_penetration = -1.0;
    let mut best_ligand_index = 0usize;
    let mut best_receptor_index = 0usize;
    let mut best_delta = Vec3::default();
    let mut best_distance = config.epsilon_angstrom;
    for (ligand_index, ligand) in coordinates.iter().copied().enumerate() {
        for (receptor_index, receptor) in context
            .receptor_coordinates_angstrom
            .iter()
            .copied()
            .enumerate()
        {
            let delta = ligand.minus(receptor);
            let distance = norm(delta).max(config.epsilon_angstrom);
            let cutoff = config.overlap_scale
                * (context.ligand_vdw_radii_angstrom[ligand_index]
                    + context.receptor_vdw_radii_angstrom[receptor_index]);
            let penetration = (cutoff - distance).max(0.0);
            if penetration > best_penetration
                || (penetration == best_penetration
                    && (ligand_index, receptor_index) < (best_ligand_index, best_receptor_index))
            {
                best_penetration = penetration;
                best_ligand_index = ligand_index;
                best_receptor_index = receptor_index;
                best_delta = delta;
                best_distance = distance;
            }
        }
    }
    if best_penetration <= 0.0 {
        return Ok(Vec3::default());
    }
    if norm(best_delta) > config.epsilon_angstrom {
        return Ok(canonical_vec(best_delta.scale(1.0 / best_distance)));
    }
    let signed_axis = (best_ligand_index * 131 + best_receptor_index) % 6;
    let sign = if signed_axis % 2 == 0 { 1.0 } else { -1.0 };
    Ok(match signed_axis / 2 {
        0 => Vec3::new(sign, 0.0, 0.0),
        1 => Vec3::new(0.0, sign, 0.0),
        _ => Vec3::new(0.0, 0.0, sign),
    })
}

fn candidate_directions(
    context: NativeRigidRefinementContext<'_>,
    coordinates: &[Vec3],
    aggregate_direction: Vec3,
    config: NativeRigidV2Config,
) -> Result<Vec<Vec3>, NativeRigidRefinementError> {
    let mut directions = Vec::with_capacity(2);
    let aggregate_norm = norm(aggregate_direction);
    if aggregate_norm > config.epsilon_angstrom {
        directions.push(canonical_vec(
            aggregate_direction.scale(1.0 / aggregate_norm),
        ));
    }
    let fallback = maximum_penetration_direction(context, coordinates, config)?;
    let fallback_norm = norm(fallback);
    if fallback_norm > config.epsilon_angstrom {
        let normalized = canonical_vec(fallback.scale(1.0 / fallback_norm));
        if directions
            .first()
            .is_none_or(|first| !vector_close(*first, normalized, 1.0e-12))
        {
            directions.push(normalized);
        }
    }
    Ok(directions)
}

fn rotation_torque(
    context: NativeRigidRefinementContext<'_>,
    coordinates: &[Vec3],
    config: NativeRigidV2Config,
) -> Result<Vec3, NativeRigidRefinementError> {
    let center = centroid(coordinates);
    let mut torque = Vec3::default();
    for (ligand_index, ligand) in coordinates.iter().copied().enumerate() {
        let lever = ligand.minus(center);
        for (receptor_index, receptor) in context
            .receptor_coordinates_angstrom
            .iter()
            .copied()
            .enumerate()
        {
            let delta = ligand.minus(receptor);
            let distance = norm(delta).max(config.epsilon_angstrom);
            let cutoff = config.overlap_scale
                * (context.ligand_vdw_radii_angstrom[ligand_index]
                    + context.receptor_vdw_radii_angstrom[receptor_index]);
            let penetration = (cutoff - distance).max(0.0);
            let force = delta.scale(penetration * penetration * penetration / distance);
            torque = torque.plus(lever.cross(force));
        }
    }
    if !torque.is_finite() {
        return Err(derived("rigid-refinement torque overflowed"));
    }
    Ok(canonical_vec(torque))
}

fn rotate_about_centroid(
    coordinates: &[Vec3],
    rotation_vector: Vec3,
) -> Result<Vec<Vec3>, NativeRigidRefinementError> {
    let angle = norm(rotation_vector);
    if !angle.is_finite() {
        return Err(derived("rigid-refinement rotation overflowed"));
    }
    if angle <= 1.0e-18 {
        return Ok(coordinates.to_vec());
    }
    let axis = rotation_vector.scale(1.0 / angle);
    let center = centroid(coordinates);
    let cosine = libm::cos(angle);
    let sine = libm::sin(angle);
    let mut output = Vec::with_capacity(coordinates.len());
    for coordinate in coordinates.iter().copied() {
        let centered = coordinate.minus(center);
        let rotated = centered
            .scale(cosine)
            .plus(axis.cross(centered).scale(sine))
            .plus(axis.scale(axis.dot(centered) * (1.0 - cosine)))
            .plus(center);
        if !rotated.is_finite() {
            return Err(derived(
                "rigid-refinement rotation produced non-finite coordinates",
            ));
        }
        output.push(canonical_vec(rotated));
    }
    Ok(output)
}

fn translated(coordinates: &[Vec3], step: Vec3) -> Vec<Vec3> {
    coordinates
        .iter()
        .copied()
        .map(|coordinate| canonical_vec(coordinate.plus(step)))
        .collect()
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

fn coordinates_bit_equal(left: &[Vec3], right: &[Vec3]) -> bool {
    left.len() == right.len()
        && left.iter().zip(right).all(|(left, right)| {
            left.x.to_bits() == right.x.to_bits()
                && left.y.to_bits() == right.y.to_bits()
                && left.z.to_bits() == right.z.to_bits()
        })
}

fn vector_close(left: Vec3, right: Vec3, tolerance: f64) -> bool {
    (left.x - right.x).abs() <= tolerance
        && (left.y - right.y).abs() <= tolerance
        && (left.z - right.z).abs() <= tolerance
}

fn norm(value: Vec3) -> f64 {
    libm::sqrt(value.x * value.x + value.y * value.y + value.z * value.z)
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

const fn invalid(message: &'static str) -> NativeRigidRefinementError {
    NativeRigidRefinementError::new(NativeRigidRefinementErrorCode::InvalidInput, message)
}

const fn non_finite(message: &'static str) -> NativeRigidRefinementError {
    NativeRigidRefinementError::new(NativeRigidRefinementErrorCode::NonFiniteInput, message)
}

const fn budget(message: &'static str) -> NativeRigidRefinementError {
    NativeRigidRefinementError::new(NativeRigidRefinementErrorCode::PairBudgetExceeded, message)
}

const fn derived(message: &'static str) -> NativeRigidRefinementError {
    NativeRigidRefinementError::new(
        NativeRigidRefinementErrorCode::NonFiniteDerivedValue,
        message,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn context<'a>(
        receptor: &'a [Vec3],
        receptor_radii: &'a [f64],
        ligand_radii: &'a [f64],
    ) -> NativeRigidRefinementContext<'a> {
        NativeRigidRefinementContext {
            receptor_coordinates_angstrom: receptor,
            receptor_vdw_radii_angstrom: receptor_radii,
            ligand_vdw_radii_angstrom: ligand_radii,
            pocket_center_angstrom: Vec3::default(),
            pocket_radius_angstrom: 8.0,
        }
    }

    #[test]
    fn v2_is_deterministic_bounded_and_reduces_penalty() {
        let receptor = [Vec3::default(), Vec3::new(0.0, 2.0, 0.0)];
        let receptor_radii = [1.7, 1.7];
        let ligand_radii = [1.7, 1.7];
        let coordinates = [Vec3::new(0.2, 0.0, 0.0), Vec3::new(0.2, 1.5, 0.0)];
        let first = refine_interaction_aware_rigid_v2(
            context(&receptor, &receptor_radii, &ligand_radii),
            &coordinates,
            12,
            NativeRigidV2Config::default(),
        )
        .unwrap();
        let second = refine_interaction_aware_rigid_v2(
            context(&receptor, &receptor_radii, &ligand_radii),
            &coordinates,
            12,
            NativeRigidV2Config::default(),
        )
        .unwrap();
        assert_eq!(first, second);
        assert!(first.final_penalty() < first.initial_penalty());
        assert!(norm(first.total_translation_angstrom()) <= 2.25 + 1.0e-9);
        assert_eq!(first.accepted_steps(), first.accepted_translation_steps());
        assert_eq!(first.accepted_rotation_steps(), 0);
        assert!(first.line_search_evaluation_count() <= 12 * 2 * 6);
    }

    #[test]
    fn v3_respects_pocket_and_rotation_budgets() {
        let receptor = [Vec3::new(0.0, 0.0, 0.0), Vec3::new(2.0, 0.0, 0.0)];
        let receptor_radii = [1.8, 1.8];
        let ligand_radii = [1.7, 1.7, 1.7];
        let coordinates = [
            Vec3::new(0.1, -0.7, 0.0),
            Vec3::new(0.1, 0.0, 0.0),
            Vec3::new(0.1, 0.7, 0.0),
        ];
        let outcome = refine_interaction_aware_rigid_v3(
            context(&receptor, &receptor_radii, &ligand_radii),
            &coordinates,
            16,
            NativeRigidV3Config::default(),
        )
        .unwrap();
        assert!(outcome.final_penalty() <= outcome.initial_penalty());
        assert!(outcome.accepted_rotation_steps() <= 2);
        assert!(outcome.total_rotation_path_radians() <= std::f64::consts::PI / 18.0 + 1.0e-12);
        assert!(outcome.final_centroid_offset_angstrom() <= 4.0 + 1.0e-9);
        assert_eq!(
            outcome.accepted_steps(),
            outcome.accepted_translation_steps() + outcome.accepted_rotation_steps()
        );
    }

    #[test]
    fn v6_lane_is_predeclared_and_clearance_decision_rederives() {
        let receptor = [Vec3::new(6.0, 0.0, 0.0)];
        let receptor_radii = [1.5];
        let ligand_radii = [1.5, 1.5];
        let coordinates = [Vec3::new(0.0, -0.5, 0.0), Vec3::new(0.0, 0.5, 0.0)];
        let v2_lane = refine_interaction_aware_rigid_v6(
            context(&receptor, &receptor_radii, &ligand_radii),
            &coordinates,
            8,
            false,
            NativeRigidV2Config::default(),
            NativeRigidV3Config::default(),
            NativeRigidV3Config::clearance_v4(),
        )
        .unwrap();
        assert_eq!(
            v2_lane.selected().profile(),
            NativeRigidRefinementProfile::V6BaselineV2
        );
        assert!(!v2_lane.clearance_evaluated());

        let v3_lane = refine_interaction_aware_rigid_v6(
            context(&receptor, &receptor_radii, &ligand_radii),
            &coordinates,
            8,
            true,
            NativeRigidV2Config::default(),
            NativeRigidV3Config::default(),
            NativeRigidV3Config::clearance_v4(),
        )
        .unwrap();
        assert!(v3_lane.baseline_duplicate_of_v2());
        assert!(v3_lane.clearance_evaluated());
        assert!(v3_lane.clearance_selected());
        assert_eq!(
            v3_lane.selected().profile(),
            NativeRigidRefinementProfile::V6ClearanceV4
        );
    }

    #[test]
    fn invalid_shapes_nonfinite_values_and_budget_fail_closed() {
        let receptor = [Vec3::default()];
        let receptor_radii = [1.0];
        let ligand_radii = [1.0];
        let bad = refine_interaction_aware_rigid_v2(
            context(&receptor, &receptor_radii, &ligand_radii),
            &[Vec3::new(f64::NAN, 0.0, 0.0)],
            1,
            NativeRigidV2Config::default(),
        )
        .unwrap_err();
        assert_eq!(bad.code(), NativeRigidRefinementErrorCode::NonFiniteInput);
        let bad_steps = refine_interaction_aware_rigid_v2(
            context(&receptor, &receptor_radii, &ligand_radii),
            &[Vec3::default()],
            0,
            NativeRigidV2Config::default(),
        )
        .unwrap_err();
        assert_eq!(
            bad_steps.code(),
            NativeRigidRefinementErrorCode::InvalidInput
        );
    }
}
