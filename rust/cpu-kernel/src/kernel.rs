const STATUS_INVALID_ARGUMENT: i32 = 1;
const STATUS_OUT_OF_MEMORY: i32 = 5;
const STATUS_INTERNAL_ERROR: i32 = 9;
const STATUS_NUMERICAL_ERROR: i32 = 10;

const COULOMB_CONSTANT: f64 = 332.063_713_299;
const DEGENERATE_SQUARED_ANGSTROM2: f64 = 1.0e-24;
const ANGLE_COSINE_MARGIN: f64 = 1.0e-12;

#[derive(Clone, Copy, Default)]
struct Vector3 {
    x: f64,
    y: f64,
    z: f64,
}

impl Vector3 {
    fn dot(self, other: Self) -> f64 {
        self.x * other.x + self.y * other.y + self.z * other.z
    }

    fn cross(self, other: Self) -> Self {
        Self {
            x: self.y * other.z - self.z * other.y,
            y: self.z * other.x - self.x * other.z,
            z: self.x * other.y - self.y * other.x,
        }
    }

    fn squared_norm(self) -> f64 {
        self.dot(self)
    }

    fn scaled(self, factor: f64) -> Self {
        Self {
            x: self.x * factor,
            y: self.y * factor,
            z: self.z * factor,
        }
    }

    fn plus(self, other: Self) -> Self {
        Self {
            x: self.x + other.x,
            y: self.y + other.y,
            z: self.z + other.z,
        }
    }

    fn minus(self, other: Self) -> Self {
        Self {
            x: self.x - other.x,
            y: self.y - other.y,
            z: self.z - other.z,
        }
    }

    fn is_finite(self) -> bool {
        self.x.is_finite() && self.y.is_finite() && self.z.is_finite()
    }
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Pair {
    pub atom_i: usize,
    pub atom_j: usize,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct PairScale {
    pub atom_i: usize,
    pub atom_j: usize,
    pub lennard_jones: f64,
    pub coulomb: f64,
}

pub(crate) struct System<'a> {
    pub position_x: &'a [f64],
    pub position_y: &'a [f64],
    pub position_z: &'a [f64],
    pub charge: &'a [f64],
}

pub(crate) struct BondSoa<'a> {
    pub atom_i: &'a [usize],
    pub atom_j: &'a [usize],
    pub equilibrium: &'a [f64],
    pub force_constant: &'a [f64],
}

pub(crate) struct AngleSoa<'a> {
    pub atom_i: &'a [usize],
    pub atom_j: &'a [usize],
    pub atom_k: &'a [usize],
    pub equilibrium: &'a [f64],
    pub force_constant: &'a [f64],
}

pub(crate) struct TorsionSoa<'a> {
    pub atom_i: &'a [usize],
    pub atom_j: &'a [usize],
    pub atom_k: &'a [usize],
    pub atom_l: &'a [usize],
    pub periodicity: &'a [u32],
    pub phase: &'a [f64],
    pub amplitude: &'a [f64],
}

pub(crate) struct ForceField<'a> {
    pub atom_count: usize,
    pub sigma: &'a [f64],
    pub epsilon: &'a [f64],
    pub bonds: BondSoa<'a>,
    pub angles: AngleSoa<'a>,
    pub torsions: TorsionSoa<'a>,
    pub exclusions: &'a [Pair],
    pub pair_scales: &'a [PairScale],
    pub periodic_axes_mask: u32,
    pub cell_lengths: [f64; 3],
    pub cutoff: f64,
    pub switch_start: f64,
    pub dielectric: f64,
    pub screening_kappa: f64,
    pub minimum_pair_distance: f64,
}

#[derive(Clone, Copy, Default)]
pub(crate) struct Energy {
    pub harmonic_bond: f64,
    pub harmonic_angle: f64,
    pub periodic_torsion: f64,
    pub lennard_jones: f64,
    pub coulomb: f64,
    pub total: f64,
}

pub(crate) struct Evaluation {
    pub energy: Energy,
    pub force_x: Vec<f64>,
    pub force_y: Vec<f64>,
    pub force_z: Vec<f64>,
}

struct EvaluationView<'a> {
    energy: Energy,
    force_x: &'a mut [f64],
    force_y: &'a mut [f64],
    force_z: &'a mut [f64],
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct KernelError {
    pub status: i32,
    pub message: &'static str,
}

impl KernelError {
    const fn invalid(message: &'static str) -> Self {
        Self {
            status: STATUS_INVALID_ARGUMENT,
            message,
        }
    }

    const fn internal(message: &'static str) -> Self {
        Self {
            status: STATUS_INTERNAL_ERROR,
            message,
        }
    }

    const fn out_of_memory(message: &'static str) -> Self {
        Self {
            status: STATUS_OUT_OF_MEMORY,
            message,
        }
    }

    const fn numerical(message: &'static str) -> Self {
        Self {
            status: STATUS_NUMERICAL_ERROR,
            message,
        }
    }
}

struct SwitchValue {
    value: f64,
    derivative: f64,
}

#[derive(Default)]
struct PairRuleCursor {
    exclusion: usize,
    scale: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
struct CellAssignment {
    key: [usize; 3],
    atom: usize,
}

fn inclusive_squared_radius(radius: f64) -> f64 {
    let squared = radius * radius;
    if squared.is_finite() {
        f64::from_bits(squared.to_bits() + 1)
    } else {
        squared
    }
}

fn displacement(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    atom_i: usize,
    atom_j: usize,
) -> Result<Vector3, KernelError> {
    if atom_i >= forcefield.atom_count || atom_j >= forcefield.atom_count {
        return Err(KernelError::internal(
            "force-field atom index is out of range",
        ));
    }
    let mut result = Vector3 {
        x: system.position_x[atom_i] - system.position_x[atom_j],
        y: system.position_y[atom_i] - system.position_y[atom_j],
        z: system.position_z[atom_i] - system.position_z[atom_j],
    };
    let bits = [1_u32, 2_u32, 4_u32];
    let mut components = [&mut result.x, &mut result.y, &mut result.z];
    for axis in 0..3 {
        if forcefield.periodic_axes_mask & bits[axis] != 0 {
            let length = forcefield.cell_lengths[axis];
            let component = &mut components[axis];
            **component -= length * (**component / length + 0.5).floor();
        }
    }
    let squared = result.squared_norm();
    if !result.is_finite() || !squared.is_finite() {
        return Err(KernelError::numerical("displacement is not finite"));
    }
    Ok(result)
}

fn checked_accumulate(
    target: &mut f64,
    value: f64,
    message: &'static str,
) -> Result<(), KernelError> {
    let updated = *target + value;
    if !value.is_finite() || !updated.is_finite() {
        return Err(KernelError::numerical(message));
    }
    *target = updated;
    Ok(())
}

fn checked_accumulate_force(
    evaluation: &mut EvaluationView<'_>,
    atom: usize,
    value: Vector3,
    message: &'static str,
) -> Result<(), KernelError> {
    let updated_x = evaluation.force_x[atom] + value.x;
    let updated_y = evaluation.force_y[atom] + value.y;
    let updated_z = evaluation.force_z[atom] + value.z;
    if !value.is_finite()
        || !updated_x.is_finite()
        || !updated_y.is_finite()
        || !updated_z.is_finite()
    {
        return Err(KernelError::numerical(message));
    }
    evaluation.force_x[atom] = updated_x;
    evaluation.force_y[atom] = updated_y;
    evaluation.force_z[atom] = updated_z;
    Ok(())
}

fn pair_is_excluded(
    forcefield: &ForceField<'_>,
    atom_i: usize,
    atom_j: usize,
    cursor: &mut PairRuleCursor,
) -> bool {
    let target = (atom_i, atom_j);
    while cursor.exclusion < forcefield.exclusions.len() {
        let pair = forcefield.exclusions[cursor.exclusion];
        if (pair.atom_i, pair.atom_j) >= target {
            break;
        }
        cursor.exclusion += 1;
    }
    forcefield
        .exclusions
        .get(cursor.exclusion)
        .is_some_and(|pair| (pair.atom_i, pair.atom_j) == target)
}

fn pair_scales(
    forcefield: &ForceField<'_>,
    atom_i: usize,
    atom_j: usize,
    cursor: &mut PairRuleCursor,
) -> (f64, f64) {
    let target = (atom_i, atom_j);
    while cursor.scale < forcefield.pair_scales.len() {
        let scale = forcefield.pair_scales[cursor.scale];
        if (scale.atom_i, scale.atom_j) >= target {
            break;
        }
        cursor.scale += 1;
    }
    forcefield
        .pair_scales
        .get(cursor.scale)
        .filter(|scale| (scale.atom_i, scale.atom_j) == target)
        .map(|scale| (scale.lennard_jones, scale.coulomb))
        .unwrap_or((1.0, 1.0))
}

fn switching_value(distance: f64, start: f64, cutoff: f64) -> SwitchValue {
    if distance <= start {
        return SwitchValue {
            value: 1.0,
            derivative: 0.0,
        };
    }
    if distance >= cutoff {
        return SwitchValue {
            value: 0.0,
            derivative: 0.0,
        };
    }
    let width = cutoff - start;
    let x = (distance - start) / width;
    let x2 = x * x;
    let x3 = x2 * x;
    let x4 = x3 * x;
    let x5 = x4 * x;
    SwitchValue {
        value: 1.0 - 10.0 * x3 + 15.0 * x4 - 6.0 * x5,
        derivative: (-30.0 * x2 + 60.0 * x3 - 30.0 * x4) / width,
    }
}

fn evaluate_bonds(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    compute_forces: bool,
    evaluation: &mut EvaluationView<'_>,
) -> Result<(), KernelError> {
    for row in 0..forcefield.bonds.atom_i.len() {
        let atom_i = forcefield.bonds.atom_i[row];
        let atom_j = forcefield.bonds.atom_j[row];
        let delta = displacement(system, forcefield, atom_i, atom_j)?;
        let squared_distance = delta.squared_norm();
        if compute_forces && squared_distance <= 0.0 {
            return Err(KernelError::numerical("bond has zero-length geometry"));
        }
        let distance = squared_distance.sqrt();
        let difference = distance - forcefield.bonds.equilibrium[row];
        let force_constant = forcefield.bonds.force_constant[row];
        let energy = 0.5 * force_constant * difference * difference;
        checked_accumulate(
            &mut evaluation.energy.harmonic_bond,
            energy,
            "bond produced a non-finite energy",
        )?;
        if compute_forces {
            let force = delta.scaled(-force_constant * difference / distance);
            checked_accumulate_force(
                evaluation,
                atom_i,
                force,
                "bond produced a non-finite force",
            )?;
            checked_accumulate_force(
                evaluation,
                atom_j,
                force.scaled(-1.0),
                "bond produced a non-finite force",
            )?;
        }
    }
    Ok(())
}

fn evaluate_angles(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    compute_forces: bool,
    evaluation: &mut EvaluationView<'_>,
) -> Result<(), KernelError> {
    for row in 0..forcefield.angles.atom_i.len() {
        let atom_i = forcefield.angles.atom_i[row];
        let atom_j = forcefield.angles.atom_j[row];
        let atom_k = forcefield.angles.atom_k[row];
        let first = displacement(system, forcefield, atom_i, atom_j)?;
        let second = displacement(system, forcefield, atom_k, atom_j)?;
        let first_squared = first.squared_norm();
        let second_squared = second.squared_norm();
        if first_squared <= DEGENERATE_SQUARED_ANGSTROM2
            || second_squared <= DEGENERATE_SQUARED_ANGSTROM2
        {
            return Err(KernelError::numerical("angle has a zero-length arm"));
        }
        let first_length = first_squared.sqrt();
        let second_length = second_squared.sqrt();
        let raw_cosine = first.dot(second) / (first_length * second_length);
        if !raw_cosine.is_finite() {
            return Err(KernelError::numerical("angle cosine is not finite"));
        }
        let lower = -1.0 + ANGLE_COSINE_MARGIN;
        let upper = 1.0 - ANGLE_COSINE_MARGIN;
        let cosine = raw_cosine.clamp(lower, upper);
        let angle = cosine.acos();
        let difference = angle - forcefield.angles.equilibrium[row];
        let force_constant = forcefield.angles.force_constant[row];
        let energy = 0.5 * force_constant * difference * difference;
        checked_accumulate(
            &mut evaluation.energy.harmonic_angle,
            energy,
            "angle produced a non-finite energy",
        )?;
        if !compute_forces || raw_cosine <= lower || raw_cosine >= upper {
            continue;
        }
        let sine = (1.0 - cosine * cosine).sqrt();
        let first_unit = first.scaled(1.0 / first_length);
        let second_unit = second.scaled(1.0 / second_length);
        let derivative = force_constant * difference;
        let force_i = second_unit
            .minus(first_unit.scaled(cosine))
            .scaled(derivative / (first_length * sine));
        let force_k = first_unit
            .minus(second_unit.scaled(cosine))
            .scaled(derivative / (second_length * sine));
        let force_j = force_i.plus(force_k).scaled(-1.0);
        checked_accumulate_force(
            evaluation,
            atom_i,
            force_i,
            "angle produced a non-finite force",
        )?;
        checked_accumulate_force(
            evaluation,
            atom_j,
            force_j,
            "angle produced a non-finite force",
        )?;
        checked_accumulate_force(
            evaluation,
            atom_k,
            force_k,
            "angle produced a non-finite force",
        )?;
    }
    Ok(())
}

fn evaluate_torsions(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    compute_forces: bool,
    evaluation: &mut EvaluationView<'_>,
) -> Result<(), KernelError> {
    for row in 0..forcefield.torsions.atom_i.len() {
        let atom_i = forcefield.torsions.atom_i[row];
        let atom_j = forcefield.torsions.atom_j[row];
        let atom_k = forcefield.torsions.atom_k[row];
        let atom_l = forcefield.torsions.atom_l[row];
        let b0 = displacement(system, forcefield, atom_i, atom_j)?;
        let b1 = displacement(system, forcefield, atom_k, atom_j)?;
        let b2 = displacement(system, forcefield, atom_l, atom_k)?;
        let central_squared = b1.squared_norm();
        if central_squared <= DEGENERATE_SQUARED_ANGSTROM2 {
            return Err(KernelError::numerical(
                "torsion central bond has zero length",
            ));
        }
        let central_length = central_squared.sqrt();
        let axis = b1.scaled(1.0 / central_length);
        let v = b0.minus(axis.scaled(b0.dot(axis)));
        let w = b2.minus(axis.scaled(b2.dot(axis)));
        let v_squared = v.squared_norm();
        let w_squared = w.squared_norm();
        if !axis.is_finite()
            || !v.is_finite()
            || !w.is_finite()
            || !v_squared.is_finite()
            || !w_squared.is_finite()
            || v_squared <= DEGENERATE_SQUARED_ANGSTROM2
            || w_squared <= DEGENERATE_SQUARED_ANGSTROM2
        {
            return Err(KernelError::numerical(
                "torsion is undefined for collinear adjacent atoms",
            ));
        }
        let sine_numerator = axis.cross(v).dot(w);
        let cosine_numerator = v.dot(w);
        let phi = sine_numerator.atan2(cosine_numerator);
        let periodicity = f64::from(forcefield.torsions.periodicity[row]);
        let argument = periodicity * phi - forcefield.torsions.phase[row];
        let amplitude = forcefield.torsions.amplitude[row];
        let energy = amplitude * (1.0 + argument.cos());
        checked_accumulate(
            &mut evaluation.energy.periodic_torsion,
            energy,
            "torsion produced a non-finite energy",
        )?;
        if !compute_forces {
            continue;
        }
        let gradient_b0 = axis.cross(v).scaled(-1.0 / v_squared);
        let gradient_b2 = axis.cross(w).scaled(1.0 / w_squared);
        let gradient_b1 = gradient_b0
            .scaled(-b0.dot(b1) / central_squared)
            .plus(gradient_b2.scaled(-b2.dot(b1) / central_squared));
        let gradient_i = gradient_b0;
        let gradient_j = gradient_b0.plus(gradient_b1).scaled(-1.0);
        let gradient_k = gradient_b1.minus(gradient_b2);
        let gradient_l = gradient_b2;
        let force_factor = amplitude * periodicity * argument.sin();
        for (atom, gradient) in [
            (atom_i, gradient_i),
            (atom_j, gradient_j),
            (atom_k, gradient_k),
            (atom_l, gradient_l),
        ] {
            checked_accumulate_force(
                evaluation,
                atom,
                gradient.scaled(force_factor),
                "torsion produced a non-finite force",
            )?;
        }
    }
    Ok(())
}

fn evaluate_nonbonded(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    neighbor_pairs: Option<&[Pair]>,
    compute_forces: bool,
    evaluation: &mut EvaluationView<'_>,
) -> Result<(), KernelError> {
    // Both traversal forms below are canonical pair order, so each sorted
    // force-field rule stream only needs to move forward once per evaluation.
    let mut pair_rules = PairRuleCursor::default();
    if forcefield.periodic_axes_mask == 0b111 {
        let built_pairs;
        let pairs = if let Some(pairs) = neighbor_pairs {
            validate_neighbor_pairs(pairs, forcefield.atom_count)?;
            pairs
        } else {
            built_pairs = periodic_neighbor_pairs(system, forcefield)?;
            &built_pairs
        };
        for pair in pairs {
            evaluate_nonbonded_pair(
                system,
                forcefield,
                pair.atom_i,
                pair.atom_j,
                compute_forces,
                &mut pair_rules,
                evaluation,
            )?;
        }
    } else {
        if neighbor_pairs.is_some() {
            return Err(KernelError::invalid(
                "neighbor pairs require a fully periodic orthorhombic system",
            ));
        }
        for atom_i in 0..forcefield.atom_count {
            for atom_j in (atom_i + 1)..forcefield.atom_count {
                evaluate_nonbonded_pair(
                    system,
                    forcefield,
                    atom_i,
                    atom_j,
                    compute_forces,
                    &mut pair_rules,
                    evaluation,
                )?;
            }
        }
    }
    Ok(())
}

fn validate_neighbor_pairs(pairs: &[Pair], atom_count: usize) -> Result<(), KernelError> {
    let mut previous = None;
    for pair in pairs {
        let key = (pair.atom_i, pair.atom_j);
        if pair.atom_i >= pair.atom_j || pair.atom_j >= atom_count || previous >= Some(key) {
            return Err(KernelError::invalid(
                "neighbor pairs must be unique sorted in-range canonical pairs",
            ));
        }
        previous = Some(key);
    }
    Ok(())
}

fn evaluate_nonbonded_pair(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    atom_i: usize,
    atom_j: usize,
    compute_forces: bool,
    pair_rules: &mut PairRuleCursor,
    evaluation: &mut EvaluationView<'_>,
) -> Result<(), KernelError> {
    if pair_is_excluded(forcefield, atom_i, atom_j, pair_rules) {
        return Ok(());
    }
    let delta = displacement(system, forcefield, atom_i, atom_j)?;
    let distance = delta.squared_norm().sqrt();
    if distance < forcefield.minimum_pair_distance {
        return Err(KernelError::numerical(
            "nonbonded pair is below minimum_pair_distance",
        ));
    }
    if distance > forcefield.cutoff {
        return Ok(());
    }
    let (lj_scale, coulomb_scale) = pair_scales(forcefield, atom_i, atom_j, pair_rules);
    let sigma = 0.5 * (forcefield.sigma[atom_i] + forcefield.sigma[atom_j]);
    let epsilon = (forcefield.epsilon[atom_i] * forcefield.epsilon[atom_j]).sqrt();
    let ratio = sigma / distance;
    let ratio2 = ratio * ratio;
    let ratio6 = ratio2 * ratio2 * ratio2;
    let ratio12 = ratio6 * ratio6;
    let lennard_jones = 4.0 * epsilon * (ratio12 - ratio6) * lj_scale;
    let screening = if forcefield.screening_kappa == 0.0 {
        1.0
    } else {
        (-forcefield.screening_kappa * distance).exp()
    };
    let screened_charge = system.charge[atom_i] * system.charge[atom_j] * screening;
    let coulomb =
        COULOMB_CONSTANT * screened_charge / (forcefield.dielectric * distance) * coulomb_scale;
    let switching = switching_value(distance, forcefield.switch_start, forcefield.cutoff);
    checked_accumulate(
        &mut evaluation.energy.lennard_jones,
        lennard_jones * switching.value,
        "Lennard-Jones pair produced a non-finite energy",
    )?;
    checked_accumulate(
        &mut evaluation.energy.coulomb,
        coulomb * switching.value,
        "Coulomb pair produced a non-finite energy",
    )?;
    if !compute_forces {
        return Ok(());
    }
    let lennard_jones_derivative = 24.0 * epsilon * lj_scale * (ratio6 - 2.0 * ratio12) / distance;
    let coulomb_derivative = coulomb * (-forcefield.screening_kappa - 1.0 / distance);
    let radial_derivative = lennard_jones_derivative * switching.value
        + lennard_jones * switching.derivative
        + coulomb_derivative * switching.value
        + coulomb * switching.derivative;
    let force = delta.scaled(-radial_derivative / distance);
    checked_accumulate_force(
        evaluation,
        atom_i,
        force,
        "nonbonded pair produced a non-finite force",
    )?;
    checked_accumulate_force(
        evaluation,
        atom_j,
        force.scaled(-1.0),
        "nonbonded pair produced a non-finite force",
    )
}

fn fallible_push<T>(
    values: &mut Vec<T>,
    value: T,
    message: &'static str,
) -> Result<(), KernelError> {
    values
        .try_reserve(1)
        .map_err(|_| KernelError::out_of_memory(message))?;
    values.push(value);
    Ok(())
}

fn periodic_cell_counts(forcefield: &ForceField<'_>) -> [usize; 3] {
    let search_radius = forcefield.cutoff.max(forcefield.minimum_pair_distance);
    forcefield.cell_lengths.map(|length| {
        let count = (length / search_radius).floor();
        if count >= forcefield.atom_count as f64 {
            forcefield.atom_count
        } else {
            (count as usize).max(1)
        }
    })
}

fn periodic_cell_key(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    cell_counts: [usize; 3],
    cell_widths: [f64; 3],
    atom: usize,
) -> Result<[usize; 3], KernelError> {
    let coordinates = [
        system.position_x[atom],
        system.position_y[atom],
        system.position_z[atom],
    ];
    let mut key = [0; 3];
    for axis in 0..3 {
        let coordinate = coordinates[axis];
        if !coordinate.is_finite() {
            return Err(KernelError::numerical(
                "periodic neighbor-list coordinate is not finite",
            ));
        }
        let length = forcefield.cell_lengths[axis];
        let wrapped = coordinate.rem_euclid(length);
        let index = (wrapped / cell_widths[axis]).floor() as usize;
        key[axis] = index.min(cell_counts[axis] - 1);
    }
    Ok(key)
}

fn offset_periodic_cell(index: usize, offset: i8, count: usize) -> usize {
    match offset {
        -1 => {
            if index == 0 {
                count - 1
            } else {
                index - 1
            }
        }
        0 => index,
        1 => {
            if index + 1 == count {
                0
            } else {
                index + 1
            }
        }
        _ => unreachable!("cell-list offsets are frozen to -1, 0, and 1"),
    }
}

fn periodic_neighbor_pairs(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
) -> Result<Vec<Pair>, KernelError> {
    let cell_counts = periodic_cell_counts(forcefield);
    let cell_widths =
        std::array::from_fn(|axis| forcefield.cell_lengths[axis] / cell_counts[axis] as f64);
    let search_radius = forcefield.cutoff.max(forcefield.minimum_pair_distance);
    let search_radius_squared = inclusive_squared_radius(search_radius);
    let mut assignments = Vec::new();
    assignments
        .try_reserve_exact(forcefield.atom_count)
        .map_err(|_| KernelError::out_of_memory("periodic neighbor-list allocation failed"))?;
    let mut atom_keys = Vec::new();
    atom_keys
        .try_reserve_exact(forcefield.atom_count)
        .map_err(|_| KernelError::out_of_memory("periodic neighbor-list allocation failed"))?;
    for atom in 0..forcefield.atom_count {
        let key = periodic_cell_key(system, forcefield, cell_counts, cell_widths, atom)?;
        atom_keys.push(key);
        assignments.push(CellAssignment { key, atom });
    }
    assignments.sort_unstable();

    let mut cell_starts = Vec::new();
    cell_starts
        .try_reserve_exact(assignments.len())
        .map_err(|_| KernelError::out_of_memory("periodic neighbor-list allocation failed"))?;
    // Index each occupied cell once so atom traversal performs one lookup per
    // neighbor cell instead of two searches over every atom assignment.
    for index in 0..assignments.len() {
        if index == 0 || assignments[index - 1].key != assignments[index].key {
            cell_starts.push(index);
        }
    }

    let mut candidates = Vec::new();
    candidates
        .try_reserve_exact(forcefield.atom_count)
        .map_err(|_| KernelError::out_of_memory("periodic neighbor-list allocation failed"))?;
    let mut pairs = Vec::new();
    for (atom_i, center) in atom_keys.iter().copied().enumerate() {
        candidates.clear();
        let mut neighbor_keys = [[0; 3]; 27];
        let mut neighbor_key_count = 0;
        for dx in [-1_i8, 0, 1] {
            for dy in [-1_i8, 0, 1] {
                for dz in [-1_i8, 0, 1] {
                    let key = [
                        offset_periodic_cell(center[0], dx, cell_counts[0]),
                        offset_periodic_cell(center[1], dy, cell_counts[1]),
                        offset_periodic_cell(center[2], dz, cell_counts[2]),
                    ];
                    if !neighbor_keys[..neighbor_key_count].contains(&key) {
                        neighbor_keys[neighbor_key_count] = key;
                        neighbor_key_count += 1;
                    }
                }
            }
        }
        neighbor_keys[..neighbor_key_count].sort_unstable();
        for key in &neighbor_keys[..neighbor_key_count] {
            let Ok(cell_index) =
                cell_starts.binary_search_by_key(key, |begin| assignments[*begin].key)
            else {
                continue;
            };
            let begin = cell_starts[cell_index];
            let end = cell_starts
                .get(cell_index + 1)
                .copied()
                .unwrap_or(assignments.len());
            candidates.extend(
                assignments[begin..end]
                    .iter()
                    .map(|row| row.atom)
                    .filter(|atom_j| *atom_j > atom_i),
            );
        }
        // Every atom has exactly one assignment and neighbor_keys is unique,
        // so candidates is already duplicate-free. Sort only for pair order.
        candidates.sort_unstable();
        for atom_j in candidates.iter().copied() {
            let squared_distance = displacement(system, forcefield, atom_i, atom_j)?.squared_norm();
            if squared_distance <= search_radius_squared {
                fallible_push(
                    &mut pairs,
                    Pair { atom_i, atom_j },
                    "periodic neighbor-list pair capacity failed",
                )?;
            }
        }
    }
    Ok(pairs)
}

fn storage_is_consistent(system: &System<'_>, forcefield: &ForceField<'_>) -> bool {
    let atom_count = system.position_x.len();
    atom_count > 0
        && system.position_y.len() == atom_count
        && system.position_z.len() == atom_count
        && system.charge.len() == atom_count
        && forcefield.atom_count == atom_count
        && forcefield.sigma.len() == atom_count
        && forcefield.epsilon.len() == atom_count
        && forcefield.bonds.atom_i.len() == forcefield.bonds.atom_j.len()
        && forcefield.bonds.atom_i.len() == forcefield.bonds.equilibrium.len()
        && forcefield.bonds.atom_i.len() == forcefield.bonds.force_constant.len()
        && forcefield.angles.atom_i.len() == forcefield.angles.atom_j.len()
        && forcefield.angles.atom_i.len() == forcefield.angles.atom_k.len()
        && forcefield.angles.atom_i.len() == forcefield.angles.equilibrium.len()
        && forcefield.angles.atom_i.len() == forcefield.angles.force_constant.len()
        && forcefield.torsions.atom_i.len() == forcefield.torsions.atom_j.len()
        && forcefield.torsions.atom_i.len() == forcefield.torsions.atom_k.len()
        && forcefield.torsions.atom_i.len() == forcefield.torsions.atom_l.len()
        && forcefield.torsions.atom_i.len() == forcefield.torsions.periodicity.len()
        && forcefield.torsions.atom_i.len() == forcefield.torsions.phase.len()
        && forcefield.torsions.atom_i.len() == forcefield.torsions.amplitude.len()
}

fn zeroed_force_channel(atom_count: usize) -> Result<Vec<f64>, KernelError> {
    let mut values = Vec::new();
    values
        .try_reserve_exact(atom_count)
        .map_err(|_| KernelError::out_of_memory("rust_cpu force allocation failed"))?;
    values.resize(atom_count, 0.0);
    Ok(values)
}

fn evaluate_into_impl(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    neighbor_pairs: Option<&[Pair]>,
    compute_forces: bool,
    force_x: &mut [f64],
    force_y: &mut [f64],
    force_z: &mut [f64],
) -> Result<Energy, KernelError> {
    if !storage_is_consistent(system, forcefield) {
        return Err(KernelError::invalid(
            "system and force-field atom storage do not match",
        ));
    }
    let atom_count = forcefield.atom_count;
    if compute_forces
        && (force_x.len() != atom_count
            || force_y.len() != atom_count
            || force_z.len() != atom_count)
    {
        return Err(KernelError::internal(
            "rust_cpu force output length changed internally",
        ));
    }
    let mut evaluation = EvaluationView {
        energy: Energy::default(),
        force_x,
        force_y,
        force_z,
    };
    evaluate_bonds(system, forcefield, compute_forces, &mut evaluation)?;
    evaluate_angles(system, forcefield, compute_forces, &mut evaluation)?;
    evaluate_torsions(system, forcefield, compute_forces, &mut evaluation)?;
    evaluate_nonbonded(
        system,
        forcefield,
        neighbor_pairs,
        compute_forces,
        &mut evaluation,
    )?;
    evaluation.energy.total = evaluation.energy.harmonic_bond
        + evaluation.energy.harmonic_angle
        + evaluation.energy.periodic_torsion
        + evaluation.energy.lennard_jones
        + evaluation.energy.coulomb;
    if !evaluation.energy.total.is_finite() {
        return Err(KernelError::numerical("total energy is not finite"));
    }
    if compute_forces
        && evaluation
            .force_x
            .iter()
            .chain(evaluation.force_y.iter())
            .chain(evaluation.force_z.iter())
            .any(|value| !value.is_finite())
    {
        return Err(KernelError::numerical("force output is not finite"));
    }
    Ok(evaluation.energy)
}

fn evaluate_impl(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    neighbor_pairs: Option<&[Pair]>,
    compute_forces: bool,
) -> Result<Evaluation, KernelError> {
    if !storage_is_consistent(system, forcefield) {
        return Err(KernelError::invalid(
            "system and force-field atom storage do not match",
        ));
    }
    let atom_count = forcefield.atom_count;
    let mut force_x = if compute_forces {
        zeroed_force_channel(atom_count)?
    } else {
        Vec::new()
    };
    let mut force_y = if compute_forces {
        zeroed_force_channel(atom_count)?
    } else {
        Vec::new()
    };
    let mut force_z = if compute_forces {
        zeroed_force_channel(atom_count)?
    } else {
        Vec::new()
    };
    let energy = evaluate_into_impl(
        system,
        forcefield,
        neighbor_pairs,
        compute_forces,
        &mut force_x,
        &mut force_y,
        &mut force_z,
    )?;
    Ok(Evaluation {
        energy,
        force_x,
        force_y,
        force_z,
    })
}

pub(crate) fn evaluate(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    compute_forces: bool,
) -> Result<Evaluation, KernelError> {
    evaluate_impl(system, forcefield, None, compute_forces)
}

pub(crate) fn evaluate_with_neighbor_pairs(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    neighbor_pairs: &[Pair],
    compute_forces: bool,
) -> Result<Evaluation, KernelError> {
    evaluate_impl(system, forcefield, Some(neighbor_pairs), compute_forces)
}

pub(crate) fn evaluate_into(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    forces: (&mut [f64], &mut [f64], &mut [f64]),
) -> Result<Energy, KernelError> {
    if !storage_is_consistent(system, forcefield) {
        return Err(KernelError::invalid(
            "system and force-field atom storage do not match",
        ));
    }
    let (force_x, force_y, force_z) = forces;
    force_x.fill(0.0);
    force_y.fill(0.0);
    force_z.fill(0.0);
    evaluate_into_impl(system, forcefield, None, true, force_x, force_y, force_z)
}

pub(crate) fn evaluate_with_neighbor_pairs_into(
    system: &System<'_>,
    forcefield: &ForceField<'_>,
    neighbor_pairs: &[Pair],
    forces: (&mut [f64], &mut [f64], &mut [f64]),
) -> Result<Energy, KernelError> {
    if !storage_is_consistent(system, forcefield) {
        return Err(KernelError::invalid(
            "system and force-field atom storage do not match",
        ));
    }
    let (force_x, force_y, force_z) = forces;
    force_x.fill(0.0);
    force_y.fill(0.0);
    force_z.fill(0.0);
    evaluate_into_impl(
        system,
        forcefield,
        Some(neighbor_pairs),
        true,
        force_x,
        force_y,
        force_z,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn squared_radius_fast_path_keeps_the_rounded_inclusive_boundary() {
        let radius = f64::from_bits(0x4016_9edc_6be4_9bff);
        let rounded_square = radius * radius;
        let boundary_squared = f64::from_bits(0x403f_fb07_75e4_29ed);

        assert_eq!(rounded_square.to_bits(), 0x403f_fb07_75e4_29ec);
        assert_eq!(boundary_squared.sqrt(), radius);
        assert!(boundary_squared > rounded_square);
        assert!(boundary_squared <= inclusive_squared_radius(radius));
    }

    #[test]
    fn periodic_cell_list_is_canonical_and_crosses_box_boundaries() {
        let position_x = [0.2, 9.8, 4.0, 6.5, 1.0];
        let position_y = [0.0; 5];
        let position_z = [0.0; 5];
        let charge = [0.1, -0.2, 0.3, -0.4, 0.5];
        let sigma = [1.0; 5];
        let epsilon = [0.05; 5];
        let system = System {
            position_x: &position_x,
            position_y: &position_y,
            position_z: &position_z,
            charge: &charge,
        };
        let forcefield = ForceField {
            atom_count: 5,
            sigma: &sigma,
            epsilon: &epsilon,
            bonds: BondSoa {
                atom_i: &[],
                atom_j: &[],
                equilibrium: &[],
                force_constant: &[],
            },
            angles: AngleSoa {
                atom_i: &[],
                atom_j: &[],
                atom_k: &[],
                equilibrium: &[],
                force_constant: &[],
            },
            torsions: TorsionSoa {
                atom_i: &[],
                atom_j: &[],
                atom_k: &[],
                atom_l: &[],
                periodicity: &[],
                phase: &[],
                amplitude: &[],
            },
            exclusions: &[],
            pair_scales: &[],
            periodic_axes_mask: 0b111,
            cell_lengths: [10.0; 3],
            cutoff: 3.0,
            switch_start: 2.5,
            dielectric: 1.0,
            screening_kappa: 0.0,
            minimum_pair_distance: 1.0e-10,
        };

        let expected = vec![
            Pair {
                atom_i: 0,
                atom_j: 1,
            },
            Pair {
                atom_i: 0,
                atom_j: 4,
            },
            Pair {
                atom_i: 1,
                atom_j: 4,
            },
            Pair {
                atom_i: 2,
                atom_j: 3,
            },
            Pair {
                atom_i: 2,
                atom_j: 4,
            },
        ];
        assert_eq!(
            periodic_neighbor_pairs(&system, &forcefield).unwrap(),
            expected
        );
        let automatic = evaluate(&system, &forcefield, true).unwrap();
        let supplied = evaluate_with_neighbor_pairs(&system, &forcefield, &expected, true).unwrap();
        for (left, right) in [
            (
                automatic.energy.harmonic_bond,
                supplied.energy.harmonic_bond,
            ),
            (
                automatic.energy.harmonic_angle,
                supplied.energy.harmonic_angle,
            ),
            (
                automatic.energy.periodic_torsion,
                supplied.energy.periodic_torsion,
            ),
            (
                automatic.energy.lennard_jones,
                supplied.energy.lennard_jones,
            ),
            (automatic.energy.coulomb, supplied.energy.coulomb),
            (automatic.energy.total, supplied.energy.total),
        ] {
            assert_eq!(left.to_bits(), right.to_bits());
        }
        for (left, right) in automatic
            .force_x
            .iter()
            .chain(&automatic.force_y)
            .chain(&automatic.force_z)
            .zip(
                supplied
                    .force_x
                    .iter()
                    .chain(&supplied.force_y)
                    .chain(&supplied.force_z),
            )
        {
            assert_eq!(left.to_bits(), right.to_bits());
        }
        let malformed = [expected[0], expected[0]];
        let error = match evaluate_with_neighbor_pairs(&system, &forcefield, &malformed, true) {
            Ok(_) => panic!("duplicate supplied neighbor pair must be rejected"),
            Err(error) => error,
        };
        assert_eq!(error.status, STATUS_INVALID_ARGUMENT);
        assert_eq!(
            error.message,
            "neighbor pairs must be unique sorted in-range canonical pairs"
        );

        let translated_x = [20.2, -0.2, 14.0, -3.5, 11.0];
        let translated = System {
            position_x: &translated_x,
            position_y: &position_y,
            position_z: &position_z,
            charge: &charge,
        };
        assert_eq!(
            periodic_neighbor_pairs(&translated, &forcefield).unwrap(),
            expected
        );
    }
}
