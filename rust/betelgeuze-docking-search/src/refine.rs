use crate::geometry::{centroid, clamp_norm};
use crate::model::{EnergyForceEvaluator, SearchConfig};
use crate::surface::Candidate;
use crate::{Quaternion, SearchError, SearchErrorCode, Vec3};

#[derive(Clone, Debug)]
pub(crate) struct RefinementOutcome {
    pub evaluator_calls: usize,
    pub error: Option<SearchError>,
}

pub(crate) fn refine_candidate<E: EnergyForceEvaluator>(
    candidate: &mut Candidate,
    config: &SearchConfig,
    evaluator: &mut E,
) -> RefinementOutcome {
    let mut evaluator_calls = 0usize;
    let mut forces = vec![Vec3::default(); candidate.coordinates_angstrom.len()];
    for _ in 0..config.refinement_steps {
        evaluator_calls += 1;
        if let Err(error) = evaluate(evaluator, &candidate.coordinates_angstrom, &mut forces) {
            return RefinementOutcome {
                evaluator_calls,
                error: Some(error),
            };
        }
        if let Err(error) = rigid_step(&mut candidate.coordinates_angstrom, &forces, config) {
            return RefinementOutcome {
                evaluator_calls,
                error: Some(error),
            };
        }
    }
    evaluator_calls += 1;
    match evaluate(evaluator, &candidate.coordinates_angstrom, &mut forces) {
        Ok(energy) => {
            candidate.energy_kcal_per_mol = energy;
            RefinementOutcome {
                evaluator_calls,
                error: None,
            }
        }
        Err(error) => RefinementOutcome {
            evaluator_calls,
            error: Some(error),
        },
    }
}

fn evaluate<E: EnergyForceEvaluator>(
    evaluator: &mut E,
    coordinates: &[Vec3],
    forces: &mut [Vec3],
) -> Result<f64, SearchError> {
    forces.fill(Vec3::default());
    let energy = evaluator
        .energy_and_forces(coordinates, forces)
        .map_err(|error| SearchError::new(SearchErrorCode::Evaluator, error.to_string()))?;
    if !energy.is_finite() {
        return Err(SearchError::new(
            SearchErrorCode::NonFiniteEvaluation,
            "energy evaluator returned a non-finite energy",
        ));
    }
    for (atom_index, force) in forces.iter().enumerate() {
        if !force.is_finite() {
            return Err(SearchError::new(
                SearchErrorCode::NonFiniteEvaluation,
                format!("energy evaluator returned a non-finite force at atom {atom_index}"),
            ));
        }
    }
    Ok(energy)
}

fn rigid_step(
    coordinates: &mut [Vec3],
    forces: &[Vec3],
    config: &SearchConfig,
) -> Result<(), SearchError> {
    let center = centroid(coordinates);
    let inverse_count = 1.0 / coordinates.len() as f64;
    let force_mean = forces
        .iter()
        .copied()
        .fold(Vec3::default(), Vec3::plus)
        .scale(inverse_count);
    let torque_mean = coordinates
        .iter()
        .zip(forces)
        .map(|(position, force)| position.minus(center).cross(*force))
        .fold(Vec3::default(), Vec3::plus)
        .scale(inverse_count);
    if !force_mean.is_finite() || !torque_mean.is_finite() {
        return Err(SearchError::new(
            SearchErrorCode::NonFiniteEvaluation,
            "rigid force or torque accumulation overflowed",
        ));
    }
    let translation = clamp_norm(
        force_mean.scale(config.translation_step_angstrom2_per_kcal),
        config.maximum_translation_step_angstrom,
    );
    let rotation_vector = clamp_norm(
        torque_mean.scale(config.rotation_step_per_torque),
        config.maximum_rotation_step_radians,
    );
    if !translation.is_finite() || !rotation_vector.is_finite() {
        return Err(SearchError::new(
            SearchErrorCode::NonFiniteEvaluation,
            "rigid refinement step overflowed",
        ));
    }
    let rotation = Quaternion::from_rotation_vector(rotation_vector).map_err(|error| {
        SearchError::new(SearchErrorCode::NonFiniteEvaluation, error.to_string())
    })?;
    for coordinate in coordinates {
        *coordinate = rotation
            .rotate(coordinate.minus(center))
            .plus(center)
            .plus(translation);
        if !coordinate.is_finite() {
            return Err(SearchError::new(
                SearchErrorCode::NonFiniteEvaluation,
                "local rigid refinement produced a non-finite coordinate",
            ));
        }
    }
    Ok(())
}
