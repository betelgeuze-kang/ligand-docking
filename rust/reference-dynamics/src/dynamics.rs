use crate::constraints::{displacement, project_positions_in_place, project_velocities_in_place};
use crate::model::{
    DynamicsError, DynamicsErrorCode, ForceProvider, IntegrationReport, LangevinConfig,
    MinimizationConfig, MinimizationReport, State, System, VerletConfig,
};
use crate::rng::normal_triplet;
use crate::{ACCELERATION_ANGSTROM_PER_FS2_PER_FORCE_PER_DALTON, GAS_CONSTANT_KCAL_PER_MOL_KELVIN};

fn evaluate<P: ForceProvider + ?Sized>(
    provider: &mut P,
    positions_angstrom: &[[f64; 3]],
    forces_kcal_per_mol_angstrom: &mut [[f64; 3]],
) -> Result<f64, DynamicsError> {
    forces_kcal_per_mol_angstrom.fill([0.0; 3]);
    let energy = provider.energy_and_forces(positions_angstrom, forces_kcal_per_mol_angstrom)?;
    if !energy.is_finite() {
        return Err(DynamicsError::new(
            DynamicsErrorCode::NonFiniteEnergy,
            "force provider returned non-finite potential energy",
        ));
    }
    for (atom, force) in forces_kcal_per_mol_angstrom.iter().enumerate() {
        for (axis, component) in force.iter().copied().enumerate() {
            if !component.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteForce,
                    format!("force[{atom}][{axis}] is non-finite"),
                ));
            }
        }
    }
    Ok(energy)
}

fn maximum_force(forces: &[[f64; 3]]) -> Result<f64, DynamicsError> {
    let mut maximum = 0.0_f64;
    for force in forces {
        let squared = force[0] * force[0] + force[1] * force[1] + force[2] * force[2];
        if !squared.is_finite() {
            return Err(DynamicsError::new(
                DynamicsErrorCode::NonFiniteForce,
                "force norm overflowed",
            ));
        }
        maximum = maximum.max(squared.sqrt());
    }
    Ok(maximum)
}

fn tangent_projected_forces(
    system: &System,
    positions: &[[f64; 3]],
    forces: &[[f64; 3]],
    max_iterations: u32,
) -> Result<Vec<[f64; 3]>, DynamicsError> {
    let mut projected = forces.to_vec();
    if system.constraints().is_empty() {
        return Ok(projected);
    }
    let scale = maximum_force(forces)?;
    let tolerance = 64.0 * f64::EPSILON * (1.0 + scale);

    for _ in 0..max_iterations {
        for constraint in system.constraints() {
            let delta = displacement(
                positions[constraint.atom_i],
                positions[constraint.atom_j],
                system.cell(),
            )?;
            let distance_squared = delta[0] * delta[0] + delta[1] * delta[1] + delta[2] * delta[2];
            if !distance_squared.is_finite() || distance_squared <= 0.0 {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::ConstraintDegenerate,
                    "cannot project force at a degenerate constraint",
                ));
            }
            let relative = [
                projected[constraint.atom_i][0] - projected[constraint.atom_j][0],
                projected[constraint.atom_i][1] - projected[constraint.atom_j][1],
                projected[constraint.atom_i][2] - projected[constraint.atom_j][2],
            ];
            let dot = delta[0] * relative[0] + delta[1] * relative[1] + delta[2] * relative[2];
            let beta = dot / (2.0 * distance_squared);
            if !beta.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteForce,
                    "constraint-tangent force correction became non-finite",
                ));
            }
            for (axis, component) in delta.iter().copied().enumerate() {
                projected[constraint.atom_i][axis] -= beta * component;
                projected[constraint.atom_j][axis] += beta * component;
            }
        }

        let mut maximum_residual = 0.0_f64;
        for constraint in system.constraints() {
            let delta = displacement(
                positions[constraint.atom_i],
                positions[constraint.atom_j],
                system.cell(),
            )?;
            let distance_squared = delta[0] * delta[0] + delta[1] * delta[1] + delta[2] * delta[2];
            if !distance_squared.is_finite() || distance_squared <= 0.0 {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::ConstraintDegenerate,
                    "cannot measure projected force at a degenerate constraint",
                ));
            }
            let relative = [
                projected[constraint.atom_i][0] - projected[constraint.atom_j][0],
                projected[constraint.atom_i][1] - projected[constraint.atom_j][1],
                projected[constraint.atom_i][2] - projected[constraint.atom_j][2],
            ];
            let dot = delta[0] * relative[0] + delta[1] * relative[1] + delta[2] * relative[2];
            maximum_residual = maximum_residual.max(dot.abs() / distance_squared.sqrt());
        }
        if maximum_residual <= tolerance {
            return Ok(projected);
        }
    }

    Err(DynamicsError::new(
        DynamicsErrorCode::ConstraintNotConverged,
        "constraint-tangent force projection did not converge",
    ))
}

fn checked_position_update(value: f64) -> Result<f64, DynamicsError> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(DynamicsError::new(
            DynamicsErrorCode::NonFiniteState,
            "position update became non-finite",
        ))
    }
}

fn checked_velocity_update(value: f64) -> Result<f64, DynamicsError> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(DynamicsError::new(
            DynamicsErrorCode::NonFiniteState,
            "velocity update became non-finite",
        ))
    }
}

fn finalize_minimized_state(
    system: &System,
    work: &mut State,
    constraint_config: crate::ConstraintConfig,
) -> Result<(), DynamicsError> {
    if !system.constraints().is_empty() {
        project_velocities_in_place(
            system,
            &work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            constraint_config,
        )?;
    }
    system.validate_state(work)
}

/// Kinetic energy in kcal/mol using the canonical dalton/angstrom/fs factor.
pub fn kinetic_energy_kcal_per_mol(system: &System, state: &State) -> Result<f64, DynamicsError> {
    system.validate_state(state)?;
    let mut mass_velocity_squared = 0.0;
    for (atom, velocity) in state.velocities_angstrom_per_fs.iter().enumerate() {
        let mass = system.masses_dalton()[atom];
        for component in velocity {
            mass_velocity_squared += mass * component * component;
            if !mass_velocity_squared.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::NonFiniteState,
                    "kinetic-energy accumulation overflowed",
                ));
            }
        }
    }
    let kinetic = 0.5 * mass_velocity_squared / ACCELERATION_ANGSTROM_PER_FS2_PER_FORCE_PER_DALTON;
    if !kinetic.is_finite() {
        return Err(DynamicsError::new(
            DynamicsErrorCode::NonFiniteState,
            "kinetic energy became non-finite",
        ));
    }
    Ok(kinetic)
}

/// Instantaneous temperature using `dof = 3*N - constraint_count`.
pub fn temperature_kelvin(system: &System, state: &State) -> Result<f64, DynamicsError> {
    let cartesian_dof = system.particle_count().checked_mul(3).ok_or_else(|| {
        DynamicsError::new(
            DynamicsErrorCode::InvalidConstraint,
            "Cartesian degree-of-freedom count overflowed",
        )
    })?;
    let degrees_of_freedom = cartesian_dof
        .checked_sub(system.constraints().len())
        .filter(|value| *value != 0)
        .ok_or_else(|| {
            DynamicsError::new(
                DynamicsErrorCode::InvalidConstraint,
                "constraints leave no positive degree-of-freedom count",
            )
        })?;
    let kinetic = kinetic_energy_kcal_per_mol(system, state)?;
    let temperature =
        2.0 * kinetic / ((degrees_of_freedom as f64) * GAS_CONSTANT_KCAL_PER_MOL_KELVIN);
    if !temperature.is_finite() {
        return Err(DynamicsError::new(
            DynamicsErrorCode::NonFiniteState,
            "temperature became non-finite",
        ));
    }
    Ok(temperature)
}

/// Deterministic steepest descent with bounded Armijo backtracking.
///
/// On every error, `state` remains byte-for-byte unchanged.
pub fn minimize<P: ForceProvider + ?Sized>(
    system: &System,
    state: &mut State,
    provider: &mut P,
    config: MinimizationConfig,
) -> Result<MinimizationReport, DynamicsError> {
    config.validate()?;
    system.validate_state(state)?;

    let mut work = state.clone();
    project_positions_in_place(system, &mut work.positions_angstrom, config.constraints)?;
    let mut forces = vec![[0.0; 3]; system.particle_count()];
    let mut energy = evaluate(provider, &work.positions_angstrom, &mut forces)?;
    let initial_energy = energy;
    let mut search_forces = tangent_projected_forces(
        system,
        &work.positions_angstrom,
        &forces,
        config.constraints.max_iterations,
    )?;
    let mut max_force = maximum_force(&search_forces)?;

    for iteration in 0..=config.max_iterations {
        if max_force <= config.force_tolerance_kcal_per_mol_angstrom {
            finalize_minimized_state(system, &mut work, config.constraints)?;
            *state = work;
            return Ok(MinimizationReport {
                iterations: iteration,
                converged: true,
                initial_potential_kcal_per_mol: initial_energy,
                final_potential_kcal_per_mol: energy,
                final_max_force_kcal_per_mol_angstrom: max_force,
            });
        }
        if iteration == config.max_iterations {
            finalize_minimized_state(system, &mut work, config.constraints)?;
            *state = work;
            return Ok(MinimizationReport {
                iterations: iteration,
                converged: false,
                initial_potential_kcal_per_mol: initial_energy,
                final_potential_kcal_per_mol: energy,
                final_max_force_kcal_per_mol_angstrom: max_force,
            });
        }

        let mut step = config.initial_step_angstrom2_mol_per_kcal;
        let mut accepted = None;
        for _ in 0..config.max_backtracks {
            let mut trial_positions = work.positions_angstrom.clone();
            for atom in 0..system.particle_count() {
                for axis in 0..3 {
                    trial_positions[atom][axis] = checked_position_update(
                        trial_positions[atom][axis] + step * search_forces[atom][axis],
                    )?;
                }
            }
            project_positions_in_place(system, &mut trial_positions, config.constraints)?;

            let mut directional_derivative = 0.0;
            for atom in 0..system.particle_count() {
                for axis in 0..3 {
                    let displacement =
                        trial_positions[atom][axis] - work.positions_angstrom[atom][axis];
                    directional_derivative -= forces[atom][axis] * displacement;
                    if !directional_derivative.is_finite() {
                        return Err(DynamicsError::new(
                            DynamicsErrorCode::NonFiniteEnergy,
                            "Armijo directional derivative became non-finite",
                        ));
                    }
                }
            }

            let mut trial_forces = vec![[0.0; 3]; system.particle_count()];
            let trial_energy = evaluate(provider, &trial_positions, &mut trial_forces)?;
            let bound = energy + config.armijo_c1 * directional_derivative;
            if directional_derivative < 0.0 && trial_energy <= bound {
                accepted = Some((trial_positions, trial_forces, trial_energy));
                break;
            }
            step *= config.backtrack_factor;
            if !step.is_finite() || step < config.minimum_step_angstrom2_mol_per_kcal {
                break;
            }
        }

        let Some((positions, accepted_forces, accepted_energy)) = accepted else {
            return Err(DynamicsError::new(
                DynamicsErrorCode::LineSearchFailed,
                format!(
                    "Armijo line search failed after at most {} trials",
                    config.max_backtracks
                ),
            ));
        };
        work.positions_angstrom = positions;
        forces = accepted_forces;
        let energy_change = (energy - accepted_energy).abs();
        energy = accepted_energy;
        search_forces = tangent_projected_forces(
            system,
            &work.positions_angstrom,
            &forces,
            config.constraints.max_iterations,
        )?;
        max_force = maximum_force(&search_forces)?;
        if config.energy_tolerance_kcal_per_mol > 0.0
            && energy_change <= config.energy_tolerance_kcal_per_mol
        {
            finalize_minimized_state(system, &mut work, config.constraints)?;
            *state = work;
            return Ok(MinimizationReport {
                iterations: iteration + 1,
                converged: true,
                initial_potential_kcal_per_mol: initial_energy,
                final_potential_kcal_per_mol: energy,
                final_max_force_kcal_per_mol_angstrom: max_force,
            });
        }
    }

    unreachable!("bounded minimization loop always returns")
}

fn half_kick(
    system: &System,
    velocities: &mut [[f64; 3]],
    forces: &[[f64; 3]],
    timestep_fs: f64,
) -> Result<(), DynamicsError> {
    for atom in 0..system.particle_count() {
        let scale = 0.5 * timestep_fs * ACCELERATION_ANGSTROM_PER_FS2_PER_FORCE_PER_DALTON
            / system.masses_dalton()[atom];
        for axis in 0..3 {
            velocities[atom][axis] =
                checked_velocity_update(velocities[atom][axis] + scale * forces[atom][axis])?;
        }
    }
    Ok(())
}

fn drift(
    positions: &mut [[f64; 3]],
    velocities: &[[f64; 3]],
    timestep_fs: f64,
) -> Result<(), DynamicsError> {
    for atom in 0..positions.len() {
        for axis in 0..3 {
            positions[atom][axis] = checked_position_update(
                positions[atom][axis] + timestep_fs * velocities[atom][axis],
            )?;
        }
    }
    Ok(())
}

fn drift_and_constrain(
    system: &System,
    positions: &mut [[f64; 3]],
    velocities: &mut [[f64; 3]],
    duration_fs: f64,
    constraint_config: crate::ConstraintConfig,
) -> Result<(), DynamicsError> {
    drift(positions, velocities, duration_fs)?;
    if system.constraints().is_empty() {
        return Ok(());
    }
    let unconstrained_positions = positions.to_vec();
    project_positions_in_place(system, positions, constraint_config)?;
    // SHAKE changes the realized drift. Reconstruct that position correction
    // into velocity before the final RATTLE tangent projection.
    for atom in 0..system.particle_count() {
        for axis in 0..3 {
            let correction = positions[atom][axis] - unconstrained_positions[atom][axis];
            velocities[atom][axis] =
                checked_velocity_update(velocities[atom][axis] + correction / duration_fs)?;
        }
    }
    project_velocities_in_place(system, positions, velocities, constraint_config)
}

struct PreparedIntegration {
    state: State,
    forces: Vec<[f64; 3]>,
    potential_kcal_per_mol: f64,
    kinetic_kcal_per_mol: f64,
}

fn prepare_integration<P: ForceProvider + ?Sized>(
    system: &System,
    state: &State,
    provider: &mut P,
    constraint_config: crate::ConstraintConfig,
    steps: u64,
) -> Result<PreparedIntegration, DynamicsError> {
    system.validate_state(state)?;
    state.absolute_step.checked_add(steps).ok_or_else(|| {
        DynamicsError::new(
            DynamicsErrorCode::StepOverflow,
            "absolute integration step would overflow u64",
        )
    })?;
    let mut work = state.clone();
    project_positions_in_place(system, &mut work.positions_angstrom, constraint_config)?;
    project_velocities_in_place(
        system,
        &work.positions_angstrom,
        &mut work.velocities_angstrom_per_fs,
        constraint_config,
    )?;
    let mut forces = vec![[0.0; 3]; system.particle_count()];
    let potential = evaluate(provider, &work.positions_angstrom, &mut forces)?;
    let kinetic = kinetic_energy_kcal_per_mol(system, &work)?;
    Ok(PreparedIntegration {
        state: work,
        forces,
        potential_kcal_per_mol: potential,
        kinetic_kcal_per_mol: kinetic,
    })
}

fn zero_step_report<P: ForceProvider + ?Sized>(
    system: &System,
    state: &State,
    provider: &mut P,
) -> Result<IntegrationReport, DynamicsError> {
    system.validate_state(state)?;
    let mut forces = vec![[0.0; 3]; system.particle_count()];
    let potential = evaluate(provider, &state.positions_angstrom, &mut forces)?;
    let kinetic = kinetic_energy_kcal_per_mol(system, state)?;
    Ok(IntegrationReport {
        steps: 0,
        absolute_step: state.absolute_step,
        initial_potential_kcal_per_mol: potential,
        final_potential_kcal_per_mol: potential,
        initial_kinetic_kcal_per_mol: kinetic,
        final_kinetic_kcal_per_mol: kinetic,
    })
}

/// Integrate using deterministic velocity Verlet and SHAKE/RATTLE.
///
/// On every error, `state` remains byte-for-byte unchanged.
pub fn integrate_velocity_verlet<P: ForceProvider + ?Sized>(
    system: &System,
    state: &mut State,
    provider: &mut P,
    config: VerletConfig,
) -> Result<IntegrationReport, DynamicsError> {
    config.validate()?;
    if config.steps == 0 {
        return zero_step_report(system, state, provider);
    }
    let prepared = prepare_integration(system, state, provider, config.constraints, config.steps)?;
    let mut work = prepared.state;
    let mut forces = prepared.forces;
    let initial_potential = prepared.potential_kcal_per_mol;
    let initial_kinetic = prepared.kinetic_kcal_per_mol;
    let mut final_potential = initial_potential;

    for _ in 0..config.steps {
        half_kick(
            system,
            &mut work.velocities_angstrom_per_fs,
            &forces,
            config.timestep_fs,
        )?;
        drift_and_constrain(
            system,
            &mut work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            config.timestep_fs,
            config.constraints,
        )?;
        final_potential = evaluate(provider, &work.positions_angstrom, &mut forces)?;
        half_kick(
            system,
            &mut work.velocities_angstrom_per_fs,
            &forces,
            config.timestep_fs,
        )?;
        project_velocities_in_place(
            system,
            &work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            config.constraints,
        )?;
        work.absolute_step += 1;
    }

    let final_kinetic = kinetic_energy_kcal_per_mol(system, &work)?;
    let report = IntegrationReport {
        steps: config.steps,
        absolute_step: work.absolute_step,
        initial_potential_kcal_per_mol: initial_potential,
        final_potential_kcal_per_mol: final_potential,
        initial_kinetic_kcal_per_mol: initial_kinetic,
        final_kinetic_kcal_per_mol: final_kinetic,
    };
    *state = work;
    Ok(report)
}

/// Integrate using BAOAB Langevin, exact OU variance, and SHAKE/RATTLE.
///
/// The transition from completed step `s` to `s+1` uses counter step `s`.
/// On every error, `state` remains byte-for-byte unchanged.
pub fn integrate_baoab<P: ForceProvider + ?Sized>(
    system: &System,
    state: &mut State,
    provider: &mut P,
    config: LangevinConfig,
) -> Result<IntegrationReport, DynamicsError> {
    config.validate()?;
    if config.steps == 0 {
        return zero_step_report(system, state, provider);
    }
    let prepared = prepare_integration(system, state, provider, config.constraints, config.steps)?;
    let mut work = prepared.state;
    let mut forces = prepared.forces;
    let initial_potential = prepared.potential_kcal_per_mol;
    let initial_kinetic = prepared.kinetic_kcal_per_mol;
    let decay = (-config.friction_per_fs * config.timestep_fs).exp();
    // exp_m1 retains relative accuracy when gamma*dt is near zero.
    let variance_fraction = -(-2.0 * config.friction_per_fs * config.timestep_fs).exp_m1();
    if !decay.is_finite()
        || !variance_fraction.is_finite()
        || !(0.0..=1.0).contains(&variance_fraction)
    {
        return Err(DynamicsError::new(
            DynamicsErrorCode::InvalidConfiguration,
            "BAOAB Ornstein-Uhlenbeck coefficients are invalid",
        ));
    }
    let mut final_potential = initial_potential;

    for _ in 0..config.steps {
        half_kick(
            system,
            &mut work.velocities_angstrom_per_fs,
            &forces,
            config.timestep_fs,
        )?;
        drift_and_constrain(
            system,
            &mut work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            0.5 * config.timestep_fs,
            config.constraints,
        )?;

        for atom in 0..system.particle_count() {
            let atom_index = u64::try_from(atom).map_err(|_| {
                DynamicsError::new(
                    DynamicsErrorCode::InvalidConfiguration,
                    "atom index cannot be represented by the Philox counter",
                )
            })?;
            let normal = normal_triplet(config.seed, work.absolute_step, atom_index);
            let sigma = (ACCELERATION_ANGSTROM_PER_FS2_PER_FORCE_PER_DALTON
                * GAS_CONSTANT_KCAL_PER_MOL_KELVIN
                * config.temperature_kelvin
                * variance_fraction
                / system.masses_dalton()[atom])
                .sqrt();
            if !sigma.is_finite() {
                return Err(DynamicsError::new(
                    DynamicsErrorCode::InvalidConfiguration,
                    "BAOAB thermal velocity scale is non-finite",
                ));
            }
            for (axis, normal_component) in normal.iter().copied().enumerate() {
                work.velocities_angstrom_per_fs[atom][axis] = checked_velocity_update(
                    decay * work.velocities_angstrom_per_fs[atom][axis] + sigma * normal_component,
                )?;
            }
        }
        // The stochastic impulse generally violates velocity constraints.
        project_velocities_in_place(
            system,
            &work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            config.constraints,
        )?;

        drift_and_constrain(
            system,
            &mut work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            0.5 * config.timestep_fs,
            config.constraints,
        )?;

        final_potential = evaluate(provider, &work.positions_angstrom, &mut forces)?;
        half_kick(
            system,
            &mut work.velocities_angstrom_per_fs,
            &forces,
            config.timestep_fs,
        )?;
        project_velocities_in_place(
            system,
            &work.positions_angstrom,
            &mut work.velocities_angstrom_per_fs,
            config.constraints,
        )?;
        work.absolute_step += 1;
    }

    let final_kinetic = kinetic_energy_kcal_per_mol(system, &work)?;
    let report = IntegrationReport {
        steps: config.steps,
        absolute_step: work.absolute_step,
        initial_potential_kcal_per_mol: initial_potential,
        final_potential_kcal_per_mol: final_potential,
        initial_kinetic_kcal_per_mol: initial_kinetic,
        final_kinetic_kcal_per_mol: final_kinetic,
    };
    *state = work;
    Ok(report)
}
