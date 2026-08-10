use crate::model::{
    validate_vectors, ConstraintConfig, DynamicsError, DynamicsErrorCode, OrthorhombicCell, System,
};

pub(crate) fn displacement(
    position_i: [f64; 3],
    position_j: [f64; 3],
    cell: Option<OrthorhombicCell>,
) -> Result<[f64; 3], DynamicsError> {
    let mut result = [0.0; 3];
    for axis in 0..3 {
        let mut component = position_i[axis] - position_j[axis];
        if !component.is_finite() {
            return Err(DynamicsError::new(
                DynamicsErrorCode::NonFiniteState,
                "constraint displacement overflowed",
            ));
        }
        if let Some(box_) = cell {
            if box_.periodic_axes[axis] {
                let length = box_.lengths_angstrom[axis];
                let image = (component / length + 0.5).floor();
                component -= length * image;
                if !component.is_finite() {
                    return Err(DynamicsError::new(
                        DynamicsErrorCode::NonFiniteState,
                        "minimum-image displacement became non-finite",
                    ));
                }
            }
        }
        result[axis] = component;
    }
    Ok(result)
}

fn squared_norm(vector: [f64; 3]) -> Result<f64, DynamicsError> {
    let value = vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2];
    if !value.is_finite() || value <= 0.0 {
        return Err(DynamicsError::new(
            DynamicsErrorCode::ConstraintDegenerate,
            "constraint displacement must have a finite nonzero norm",
        ));
    }
    Ok(value)
}

fn pair_mut<T>(values: &mut [T], atom_i: usize, atom_j: usize) -> (&mut T, &mut T) {
    debug_assert!(atom_i < atom_j);
    let (left, right) = values.split_at_mut(atom_j);
    (&mut left[atom_i], &mut right[0])
}

/// Verify that the instantaneous constraint Jacobian has one independent row
/// per declared constraint. This is the precondition behind `3*N-C` degrees of
/// freedom and catches redundant/singular rows before dynamics or checkpoint
/// operations use that count.
pub(crate) fn validate_constraint_independence(
    system: &System,
    positions_angstrom: &[[f64; 3]],
) -> Result<(), DynamicsError> {
    let row_count = system.constraints().len();
    if row_count == 0 {
        return Ok(());
    }
    let column_count = system.particle_count().checked_mul(3).ok_or_else(|| {
        DynamicsError::new(
            DynamicsErrorCode::InvalidConstraint,
            "constraint Jacobian column count overflowed",
        )
    })?;
    let mut matrix = vec![vec![0.0; column_count]; row_count];
    let mut maximum_entry = 0.0_f64;
    for (row, constraint) in system.constraints().iter().enumerate() {
        let delta = displacement(
            positions_angstrom[constraint.atom_i],
            positions_angstrom[constraint.atom_j],
            system.cell(),
        )?;
        let distance = squared_norm(delta)?.sqrt();
        let scale_i = 1.0 / system.masses_dalton()[constraint.atom_i].sqrt();
        let scale_j = 1.0 / system.masses_dalton()[constraint.atom_j].sqrt();
        for axis in 0..3 {
            let direction = delta[axis] / distance;
            matrix[row][3 * constraint.atom_i + axis] = direction * scale_i;
            matrix[row][3 * constraint.atom_j + axis] = -direction * scale_j;
            maximum_entry = maximum_entry
                .max((direction * scale_i).abs())
                .max((direction * scale_j).abs());
        }
    }
    let dimension = row_count.max(column_count) as f64;
    let tolerance = 128.0 * f64::EPSILON * dimension * maximum_entry.max(f64::MIN_POSITIVE);
    let mut rank = 0_usize;
    for column in 0..column_count {
        let mut pivot = rank;
        let mut pivot_magnitude = 0.0_f64;
        for (row, values) in matrix.iter().enumerate().skip(rank) {
            let magnitude = values[column].abs();
            if magnitude > pivot_magnitude {
                pivot = row;
                pivot_magnitude = magnitude;
            }
        }
        if pivot_magnitude <= tolerance {
            continue;
        }
        matrix.swap(rank, pivot);
        let pivot_value = matrix[rank][column];
        for entry in &mut matrix[rank][column..] {
            *entry /= pivot_value;
        }
        let normalized_pivot = matrix[rank][column..].to_vec();
        for row in matrix.iter_mut().skip(rank + 1) {
            let factor = row[column];
            if factor == 0.0 {
                continue;
            }
            for (entry, pivot_entry) in row[column..].iter_mut().zip(&normalized_pivot) {
                *entry -= factor * pivot_entry;
            }
        }
        rank += 1;
        if rank == row_count {
            return Ok(());
        }
    }
    Err(DynamicsError::new(
        DynamicsErrorCode::InvalidConstraint,
        format!(
            "constraint Jacobian has rank {rank} but {row_count} independent rows are required"
        ),
    ))
}

pub(crate) fn project_positions_in_place(
    system: &System,
    positions_angstrom: &mut [[f64; 3]],
    config: ConstraintConfig,
) -> Result<(), DynamicsError> {
    if system.constraints().is_empty() {
        return Ok(());
    }

    for _ in 0..config.max_iterations {
        for constraint in system.constraints() {
            let delta = displacement(
                positions_angstrom[constraint.atom_i],
                positions_angstrom[constraint.atom_j],
                system.cell(),
            )?;
            let distance = squared_norm(delta)?.sqrt();
            if (distance - constraint.distance_angstrom).abs() <= config.position_tolerance_angstrom
            {
                continue;
            }

            let inverse_mass_i = 1.0 / system.masses_dalton()[constraint.atom_i];
            let inverse_mass_j = 1.0 / system.masses_dalton()[constraint.atom_j];
            // beta is positive when an overlong pair must shrink. The stored
            // coordinates remain unwrapped; only `delta` is minimum-imaged.
            let beta =
                (1.0 - constraint.distance_angstrom / distance) / (inverse_mass_i + inverse_mass_j);
            if !beta.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteState,
                    "SHAKE correction became non-finite",
                ));
            }
            let (position_i, position_j) =
                pair_mut(positions_angstrom, constraint.atom_i, constraint.atom_j);
            for axis in 0..3 {
                position_i[axis] -= inverse_mass_i * beta * delta[axis];
                position_j[axis] += inverse_mass_j * beta * delta[axis];
                if !position_i[axis].is_finite() || !position_j[axis].is_finite() {
                    return Err(DynamicsError::new(
                        DynamicsErrorCode::NonFiniteState,
                        "SHAKE position update became non-finite",
                    ));
                }
            }
        }

        let mut maximum_residual = 0.0_f64;
        for constraint in system.constraints() {
            let delta = displacement(
                positions_angstrom[constraint.atom_i],
                positions_angstrom[constraint.atom_j],
                system.cell(),
            )?;
            let residual = (squared_norm(delta)?.sqrt() - constraint.distance_angstrom).abs();
            maximum_residual = maximum_residual.max(residual);
        }
        if maximum_residual <= config.position_tolerance_angstrom {
            return Ok(());
        }
    }

    Err(DynamicsError::new(
        DynamicsErrorCode::ConstraintNotConverged,
        format!(
            "SHAKE did not reach {:.17e} angstrom in {} iterations",
            config.position_tolerance_angstrom, config.max_iterations
        ),
    ))
}

pub(crate) fn project_velocities_in_place(
    system: &System,
    positions_angstrom: &[[f64; 3]],
    velocities_angstrom_per_fs: &mut [[f64; 3]],
    config: ConstraintConfig,
) -> Result<(), DynamicsError> {
    if system.constraints().is_empty() {
        return Ok(());
    }

    for _ in 0..config.max_iterations {
        for constraint in system.constraints() {
            let delta = displacement(
                positions_angstrom[constraint.atom_i],
                positions_angstrom[constraint.atom_j],
                system.cell(),
            )?;
            let distance_squared = squared_norm(delta)?;
            let relative_velocity = [
                velocities_angstrom_per_fs[constraint.atom_i][0]
                    - velocities_angstrom_per_fs[constraint.atom_j][0],
                velocities_angstrom_per_fs[constraint.atom_i][1]
                    - velocities_angstrom_per_fs[constraint.atom_j][1],
                velocities_angstrom_per_fs[constraint.atom_i][2]
                    - velocities_angstrom_per_fs[constraint.atom_j][2],
            ];
            let dot = delta[0] * relative_velocity[0]
                + delta[1] * relative_velocity[1]
                + delta[2] * relative_velocity[2];
            let radial_speed = dot.abs() / distance_squared.sqrt();
            if !radial_speed.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteState,
                    "RATTLE residual became non-finite",
                ));
            }
            if radial_speed <= config.velocity_tolerance_angstrom_per_fs {
                continue;
            }

            let inverse_mass_i = 1.0 / system.masses_dalton()[constraint.atom_i];
            let inverse_mass_j = 1.0 / system.masses_dalton()[constraint.atom_j];
            let beta = dot / ((inverse_mass_i + inverse_mass_j) * distance_squared);
            if !beta.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteState,
                    "RATTLE correction became non-finite",
                ));
            }
            let (velocity_i, velocity_j) = pair_mut(
                velocities_angstrom_per_fs,
                constraint.atom_i,
                constraint.atom_j,
            );
            for axis in 0..3 {
                velocity_i[axis] -= inverse_mass_i * beta * delta[axis];
                velocity_j[axis] += inverse_mass_j * beta * delta[axis];
                if !velocity_i[axis].is_finite() || !velocity_j[axis].is_finite() {
                    return Err(DynamicsError::new(
                        DynamicsErrorCode::NonFiniteState,
                        "RATTLE velocity update became non-finite",
                    ));
                }
            }
        }

        let mut maximum_residual = 0.0_f64;
        for constraint in system.constraints() {
            let delta = displacement(
                positions_angstrom[constraint.atom_i],
                positions_angstrom[constraint.atom_j],
                system.cell(),
            )?;
            let distance_squared = squared_norm(delta)?;
            let relative_velocity = [
                velocities_angstrom_per_fs[constraint.atom_i][0]
                    - velocities_angstrom_per_fs[constraint.atom_j][0],
                velocities_angstrom_per_fs[constraint.atom_i][1]
                    - velocities_angstrom_per_fs[constraint.atom_j][1],
                velocities_angstrom_per_fs[constraint.atom_i][2]
                    - velocities_angstrom_per_fs[constraint.atom_j][2],
            ];
            let dot = delta[0] * relative_velocity[0]
                + delta[1] * relative_velocity[1]
                + delta[2] * relative_velocity[2];
            let residual = dot.abs() / distance_squared.sqrt();
            if !residual.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteState,
                    "RATTLE residual became non-finite",
                ));
            }
            maximum_residual = maximum_residual.max(residual);
        }
        if maximum_residual <= config.velocity_tolerance_angstrom_per_fs {
            return Ok(());
        }
    }

    Err(DynamicsError::new(
        DynamicsErrorCode::ConstraintNotConverged,
        format!(
            "RATTLE did not reach {:.17e} angstrom/fs in {} iterations",
            config.velocity_tolerance_angstrom_per_fs, config.max_iterations
        ),
    ))
}

/// Apply canonical-order mass-weighted SHAKE transactionally.
pub fn project_positions(
    system: &System,
    positions_angstrom: &mut [[f64; 3]],
    config: ConstraintConfig,
) -> Result<(), DynamicsError> {
    config.validate()?;
    if positions_angstrom.len() != system.particle_count() {
        return Err(DynamicsError::new(
            DynamicsErrorCode::ParticleCountMismatch,
            "position count does not match the system",
        ));
    }
    validate_vectors(positions_angstrom, "position")?;
    validate_constraint_independence(system, positions_angstrom)?;
    let mut work = positions_angstrom.to_vec();
    project_positions_in_place(system, &mut work, config)?;
    positions_angstrom.copy_from_slice(&work);
    Ok(())
}

/// Apply canonical-order mass-weighted RATTLE transactionally.
pub fn project_velocities(
    system: &System,
    positions_angstrom: &[[f64; 3]],
    velocities_angstrom_per_fs: &mut [[f64; 3]],
    config: ConstraintConfig,
) -> Result<(), DynamicsError> {
    config.validate()?;
    if positions_angstrom.len() != system.particle_count()
        || velocities_angstrom_per_fs.len() != system.particle_count()
    {
        return Err(DynamicsError::new(
            DynamicsErrorCode::ParticleCountMismatch,
            "position or velocity count does not match the system",
        ));
    }
    validate_vectors(positions_angstrom, "position")?;
    validate_vectors(velocities_angstrom_per_fs, "velocity")?;
    validate_constraint_independence(system, positions_angstrom)?;
    let mut work = velocities_angstrom_per_fs.to_vec();
    project_velocities_in_place(system, positions_angstrom, &mut work, config)?;
    velocities_angstrom_per_fs.copy_from_slice(&work);
    Ok(())
}
