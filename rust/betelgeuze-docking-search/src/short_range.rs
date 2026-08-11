use crate::model::{
    EnergyForceEvaluator, LigandAtom, ReceptorAtom, SearchInput, MAX_LIGAND_ATOMS,
    MAX_RECEPTOR_ATOMS,
};
use crate::{
    EvaluationError, SearchError, SearchErrorCode, Vec3, COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
};

const TWO_TO_ONE_SIXTH: f64 = 1.122_462_048_309_373;
const MINIMUM_VECTOR_NORM: f64 = 1.0e-12;

/// Bounded product-owned scalar short-range physics used for local refinement.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ShortRangeConfig {
    pub ligand_shape_force_constant_kcal_per_mol_angstrom2: f64,
    pub cutoff_angstrom: f64,
    pub switch_start_angstrom: f64,
    pub softcore_angstrom: f64,
    pub dielectric: f64,
}

impl Default for ShortRangeConfig {
    fn default() -> Self {
        Self {
            ligand_shape_force_constant_kcal_per_mol_angstrom2: 10.0,
            cutoff_angstrom: 12.0,
            switch_start_angstrom: 10.0,
            softcore_angstrom: 0.25,
            dielectric: 4.0,
        }
    }
}

impl ShortRangeConfig {
    /// SHA-256 over the frozen canonical binary evaluator configuration.
    #[must_use]
    pub fn canonical_sha256(self) -> [u8; 32] {
        crate::identity::short_range_config_sha256(self)
    }
}

#[derive(Clone, Copy, Debug)]
struct ReferencePair {
    atom_i: usize,
    atom_j: usize,
    distance_angstrom: f64,
}

/// Independent deterministic analytic evaluator for ligand shape plus
/// ligand/receptor soft-core Lennard-Jones and Coulomb interactions.
#[derive(Clone, Debug)]
pub struct ShortRangeEvaluator {
    ligand_atoms: Vec<LigandAtom>,
    receptor_atoms: Vec<ReceptorAtom>,
    reference_pairs: Vec<ReferencePair>,
    config: ShortRangeConfig,
}

impl ShortRangeEvaluator {
    /// Freeze source-ligand pair distances and a canonical receptor row order.
    pub fn from_input(input: &SearchInput, config: ShortRangeConfig) -> Result<Self, SearchError> {
        validate_config(config)?;
        if input.ligand_atoms.is_empty() {
            return Err(SearchError::new(
                SearchErrorCode::EmptyLigand,
                "short-range evaluator requires at least one ligand atom",
            ));
        }
        if input.ligand_atoms.len() > MAX_LIGAND_ATOMS
            || input.receptor_atoms.len() > MAX_RECEPTOR_ATOMS
        {
            return Err(SearchError::new(
                SearchErrorCode::TooManyItems,
                "short-range evaluator atom count exceeds a search hard cap",
            ));
        }
        for (index, atom) in input.ligand_atoms.iter().enumerate() {
            validate_atom(atom.position_angstrom, atom, "ligand", index)?;
        }
        for (index, atom) in input.receptor_atoms.iter().enumerate() {
            validate_receptor_atom(atom, index)?;
        }
        let pair_count = input
            .ligand_atoms
            .len()
            .checked_mul(input.ligand_atoms.len().saturating_sub(1))
            .and_then(|value| value.checked_div(2))
            .ok_or_else(|| {
                SearchError::new(
                    SearchErrorCode::AllocationOverflow,
                    "ligand reference-pair count overflowed",
                )
            })?;
        let mut reference_pairs = Vec::with_capacity(pair_count);
        for atom_i in 0..input.ligand_atoms.len() {
            for atom_j in atom_i + 1..input.ligand_atoms.len() {
                reference_pairs.push(ReferencePair {
                    atom_i,
                    atom_j,
                    distance_angstrom: input.ligand_atoms[atom_i]
                        .position_angstrom
                        .minus(input.ligand_atoms[atom_j].position_angstrom)
                        .norm(),
                });
            }
        }
        let mut receptor_atoms = input.receptor_atoms.clone();
        receptor_atoms.sort_by(canonical_receptor_order);
        Ok(Self {
            ligand_atoms: input.ligand_atoms.clone(),
            receptor_atoms,
            reference_pairs,
            config,
        })
    }

    #[must_use]
    pub const fn config(&self) -> ShortRangeConfig {
        self.config
    }

    #[must_use]
    pub fn ligand_atom_count(&self) -> usize {
        self.ligand_atoms.len()
    }

    #[must_use]
    pub fn receptor_atom_count(&self) -> usize {
        self.receptor_atoms.len()
    }
}

impl EnergyForceEvaluator for ShortRangeEvaluator {
    fn energy_and_forces(
        &mut self,
        positions_angstrom: &[Vec3],
        forces_kcal_per_mol_angstrom: &mut [Vec3],
    ) -> Result<f64, EvaluationError> {
        if positions_angstrom.len() != self.ligand_atoms.len()
            || forces_kcal_per_mol_angstrom.len() != self.ligand_atoms.len()
        {
            return Err(EvaluationError::new(format!(
                "short-range evaluator expects {} ligand positions and forces",
                self.ligand_atoms.len()
            )));
        }
        for (index, position) in positions_angstrom.iter().enumerate() {
            if !position.is_finite() {
                return Err(EvaluationError::new(format!(
                    "ligand position {index} is non-finite"
                )));
            }
        }
        forces_kcal_per_mol_angstrom.fill(Vec3::default());
        let mut energy = 0.0;
        accumulate_shape(
            positions_angstrom,
            forces_kcal_per_mol_angstrom,
            &self.reference_pairs,
            self.config
                .ligand_shape_force_constant_kcal_per_mol_angstrom2,
            &mut energy,
        )?;
        accumulate_receptor(
            positions_angstrom,
            forces_kcal_per_mol_angstrom,
            &self.ligand_atoms,
            &self.receptor_atoms,
            self.config,
            &mut energy,
        )?;
        if !energy.is_finite() {
            return Err(EvaluationError::new(
                "short-range energy accumulation overflowed",
            ));
        }
        Ok(energy)
    }
}

fn accumulate_shape(
    positions: &[Vec3],
    forces: &mut [Vec3],
    pairs: &[ReferencePair],
    force_constant: f64,
    energy: &mut f64,
) -> Result<(), EvaluationError> {
    for pair in pairs {
        let delta = positions[pair.atom_i].minus(positions[pair.atom_j]);
        let distance = delta.norm();
        let displacement = distance - pair.distance_angstrom;
        *energy += 0.5 * force_constant * displacement * displacement;
        if distance <= MINIMUM_VECTOR_NORM {
            if pair.distance_angstrom > MINIMUM_VECTOR_NORM {
                return Err(EvaluationError::new(format!(
                    "ligand shape pair ({}, {}) collapsed",
                    pair.atom_i, pair.atom_j
                )));
            }
            continue;
        }
        let force_on_i = delta.scale(-force_constant * displacement / distance);
        add_pair_force(forces, pair.atom_i, pair.atom_j, force_on_i)?;
    }
    Ok(())
}

fn accumulate_receptor(
    positions: &[Vec3],
    forces: &mut [Vec3],
    ligand_atoms: &[LigandAtom],
    receptor_atoms: &[ReceptorAtom],
    config: ShortRangeConfig,
    energy: &mut f64,
) -> Result<(), EvaluationError> {
    for (ligand_index, (position, ligand_atom)) in positions.iter().zip(ligand_atoms).enumerate() {
        for receptor_atom in receptor_atoms {
            let delta = position.minus(receptor_atom.position_angstrom);
            let distance = delta.norm();
            if distance >= config.cutoff_angstrom {
                continue;
            }
            let soft_distance = libm::hypot(distance, config.softcore_angstrom);
            let contact_distance =
                ligand_atom.vdw_radius_angstrom + receptor_atom.vdw_radius_angstrom;
            let sigma = contact_distance / TWO_TO_ONE_SIXTH;
            let epsilon =
                libm::sqrt(ligand_atom.epsilon_kcal_per_mol * receptor_atom.epsilon_kcal_per_mol);
            let sigma_over_r = sigma / soft_distance;
            let sr2 = sigma_over_r * sigma_over_r;
            let sr6 = sr2 * sr2 * sr2;
            let sr12 = sr6 * sr6;
            let lennard_jones = 4.0 * epsilon * (sr12 - sr6);
            let lennard_jones_derivative = 24.0 * epsilon * (sr6 - 2.0 * sr12) / soft_distance;
            let charge_product = ligand_atom.charge_elementary * receptor_atom.charge_elementary;
            let coulomb_scale =
                COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * charge_product / config.dielectric;
            let coulomb = coulomb_scale / soft_distance;
            let coulomb_derivative = -coulomb_scale / (soft_distance * soft_distance);
            let raw_energy = lennard_jones + coulomb;
            let raw_derivative = lennard_jones_derivative + coulomb_derivative;
            let (switch, switch_derivative) = switching(distance, config);
            let switched_energy = switch * raw_energy;
            let radial_coefficient = if distance <= MINIMUM_VECTOR_NORM {
                switch * raw_derivative / soft_distance
            } else {
                switch * raw_derivative / soft_distance + raw_energy * switch_derivative / distance
            };
            let force = delta.scale(-radial_coefficient);
            if !switched_energy.is_finite() || !force.is_finite() {
                return Err(EvaluationError::new(format!(
                    "short-range pair for ligand atom {ligand_index} overflowed"
                )));
            }
            *energy += switched_energy;
            forces[ligand_index] = forces[ligand_index].plus(force);
            if !forces[ligand_index].is_finite() || !energy.is_finite() {
                return Err(EvaluationError::new(
                    "short-range force or energy accumulation overflowed",
                ));
            }
        }
    }
    Ok(())
}

fn switching(distance: f64, config: ShortRangeConfig) -> (f64, f64) {
    if distance <= config.switch_start_angstrom {
        return (1.0, 0.0);
    }
    if distance >= config.cutoff_angstrom {
        return (0.0, 0.0);
    }
    let width = config.cutoff_angstrom - config.switch_start_angstrom;
    let t = (distance - config.switch_start_angstrom) / width;
    let t2 = t * t;
    let t3 = t2 * t;
    let t4 = t3 * t;
    let t5 = t4 * t;
    let value = 1.0 - 10.0 * t3 + 15.0 * t4 - 6.0 * t5;
    let derivative = (-30.0 * t2 + 60.0 * t3 - 30.0 * t4) / width;
    (value, derivative)
}

fn add_pair_force(
    forces: &mut [Vec3],
    atom_i: usize,
    atom_j: usize,
    force_on_i: Vec3,
) -> Result<(), EvaluationError> {
    forces[atom_i] = forces[atom_i].plus(force_on_i);
    forces[atom_j] = forces[atom_j].minus(force_on_i);
    if forces[atom_i].is_finite() && forces[atom_j].is_finite() {
        Ok(())
    } else {
        Err(EvaluationError::new(
            "ligand shape force accumulation overflowed",
        ))
    }
}

fn validate_config(config: ShortRangeConfig) -> Result<(), SearchError> {
    let values = [
        config.ligand_shape_force_constant_kcal_per_mol_angstrom2,
        config.cutoff_angstrom,
        config.switch_start_angstrom,
        config.softcore_angstrom,
        config.dielectric,
    ];
    if values.iter().any(|value| !value.is_finite())
        || !(0.0..=1.0e6).contains(&config.ligand_shape_force_constant_kcal_per_mol_angstrom2)
        || !(f64::EPSILON..=1_000.0).contains(&config.cutoff_angstrom)
        || !(0.0..config.cutoff_angstrom).contains(&config.switch_start_angstrom)
        || config.switch_start_angstrom >= config.cutoff_angstrom
        || !(f64::EPSILON..=10.0).contains(&config.softcore_angstrom)
        || !(1.0..=1.0e6).contains(&config.dielectric)
    {
        return Err(SearchError::new(
            SearchErrorCode::InvalidConfiguration,
            "short-range configuration is non-finite, unordered, or outside hard bounds",
        ));
    }
    Ok(())
}

fn validate_atom(
    position: Vec3,
    atom: &LigandAtom,
    label: &str,
    index: usize,
) -> Result<(), SearchError> {
    validate_parameters(
        position,
        atom.vdw_radius_angstrom,
        atom.epsilon_kcal_per_mol,
        atom.charge_elementary,
        label,
        index,
    )
}

fn validate_receptor_atom(atom: &ReceptorAtom, index: usize) -> Result<(), SearchError> {
    validate_parameters(
        atom.position_angstrom,
        atom.vdw_radius_angstrom,
        atom.epsilon_kcal_per_mol,
        atom.charge_elementary,
        "receptor",
        index,
    )
}

fn validate_parameters(
    position: Vec3,
    radius: f64,
    epsilon: f64,
    charge: f64,
    label: &str,
    index: usize,
) -> Result<(), SearchError> {
    if !position.is_finite()
        || position.x.abs() > 1.0e9
        || position.y.abs() > 1.0e9
        || position.z.abs() > 1.0e9
    {
        return Err(SearchError::new(
            SearchErrorCode::NonFiniteInput,
            format!("{label} atom {index} position is non-finite"),
        ));
    }
    if !radius.is_finite() || !(f64::EPSILON..=100.0).contains(&radius) {
        return Err(SearchError::new(
            SearchErrorCode::InvalidRadius,
            format!("{label} atom {index} radius is outside (0, 100] angstrom"),
        ));
    }
    if !epsilon.is_finite()
        || !(0.0..=1_000.0).contains(&epsilon)
        || !charge.is_finite()
        || !(-16.0..=16.0).contains(&charge)
    {
        return Err(SearchError::new(
            SearchErrorCode::InvalidAtomParameter,
            format!("{label} atom {index} epsilon or charge is outside hard bounds"),
        ));
    }
    Ok(())
}

fn canonical_receptor_order(left: &ReceptorAtom, right: &ReceptorAtom) -> core::cmp::Ordering {
    left.position_angstrom
        .x
        .total_cmp(&right.position_angstrom.x)
        .then_with(|| {
            left.position_angstrom
                .y
                .total_cmp(&right.position_angstrom.y)
        })
        .then_with(|| {
            left.position_angstrom
                .z
                .total_cmp(&right.position_angstrom.z)
        })
        .then_with(|| {
            left.vdw_radius_angstrom
                .total_cmp(&right.vdw_radius_angstrom)
        })
        .then_with(|| {
            left.epsilon_kcal_per_mol
                .total_cmp(&right.epsilon_kcal_per_mol)
        })
        .then_with(|| left.charge_elementary.total_cmp(&right.charge_elementary))
}
