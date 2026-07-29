#![allow(non_local_definitions)]

use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;
use rayon::{ThreadPool, ThreadPoolBuilder};
use std::collections::{BTreeMap, HashSet};

const MAX_BATCH_SIZE: usize = 64;

#[derive(Clone, Copy)]
struct Config {
    dielectric: f64,
    pair_cutoff: f64,
    hbond_cutoff: f64,
    polar_burial_cutoff: f64,
    max_receptor_pairs: usize,
    max_ligand_pairs: usize,
    weights: [f64; 8],
}

#[pyclass(frozen)]
struct NativeScoreRow {
    #[pyo3(get)]
    terms: Vec<f64>,
    #[pyo3(get)]
    receptor_candidate_pair_count: usize,
    #[pyo3(get)]
    ligand_pair_count: usize,
    #[pyo3(get)]
    hbond_count: usize,
    #[pyo3(get)]
    hydrophobic_contact_count: usize,
    #[pyo3(get)]
    buried_polar_count: usize,
    #[pyo3(get)]
    error_code: Option<String>,
}

impl NativeScoreRow {
    fn failure(code: &str, receptor_pairs: usize, ligand_pairs: usize) -> Self {
        Self {
            terms: vec![0.0; 9],
            receptor_candidate_pair_count: receptor_pairs,
            ligand_pair_count: ligand_pairs,
            hbond_count: 0,
            hydrophobic_contact_count: 0,
            buried_polar_count: 0,
            error_code: Some(code.to_owned()),
        }
    }
}

#[pyclass]
struct NativeScorerContext {
    receptor: Vec<[f64; 3]>,
    receptor_cells: BTreeMap<(i64, i64, i64), Vec<usize>>,
    receptor_charges: Vec<f64>,
    ligand_charges: Vec<f64>,
    receptor_radii: Vec<f64>,
    ligand_radii: Vec<f64>,
    receptor_epsilons: Vec<f64>,
    ligand_epsilons: Vec<f64>,
    receptor_hydrophobic: Vec<bool>,
    ligand_hydrophobic: Vec<bool>,
    receptor_acceptors: Vec<bool>,
    ligand_acceptors: Vec<bool>,
    receptor_donor_by_hydrogen: Vec<Option<usize>>,
    ligand_donor_by_hydrogen: Vec<Option<usize>>,
    ligand_exclusions: HashSet<(usize, usize)>,
    rotor_quads: Vec<[usize; 4]>,
    reference_dihedrals: Vec<f64>,
    reference_internal_vdw: f64,
    pocket_center: [f64; 3],
    pocket_radius: f64,
    config: Config,
    pool: ThreadPool,
}

fn require_finite(values: impl Iterator<Item = f64>, name: &str) -> PyResult<()> {
    if values.into_iter().any(|value| !value.is_finite()) {
        return Err(PyValueError::new_err(format!("{name} must be finite")));
    }
    Ok(())
}

fn rows3(array: PyReadonlyArray2<'_, f64>, name: &str) -> PyResult<Vec<[f64; 3]>> {
    let view = array.as_array();
    if view.ncols() != 3 {
        return Err(PyValueError::new_err(format!(
            "{name} must have shape [N,3]"
        )));
    }
    let rows: Vec<[f64; 3]> = view
        .outer_iter()
        .map(|row| [row[0], row[1], row[2]])
        .collect();
    require_finite(rows.iter().flat_map(|row| row.iter().copied()), name)?;
    Ok(rows)
}

fn vec_f64(array: PyReadonlyArray1<'_, f64>, length: usize, name: &str) -> PyResult<Vec<f64>> {
    let values = array.as_slice()?.to_vec();
    if values.len() != length {
        return Err(PyValueError::new_err(format!("{name} length mismatch")));
    }
    require_finite(values.iter().copied(), name)?;
    Ok(values)
}

fn vec_mask(array: PyReadonlyArray1<'_, u8>, length: usize, name: &str) -> PyResult<Vec<bool>> {
    let values = array.as_slice()?;
    if values.len() != length || values.iter().any(|value| *value > 1) {
        return Err(PyValueError::new_err(format!(
            "{name} must be a binary mask"
        )));
    }
    Ok(values.iter().map(|value| *value == 1).collect())
}

fn index_rows<const N: usize>(
    array: PyReadonlyArray2<'_, i32>,
    bounds: usize,
    name: &str,
) -> PyResult<Vec<[usize; N]>> {
    let view = array.as_array();
    if view.ncols() != N {
        return Err(PyValueError::new_err(format!(
            "{name} column count mismatch"
        )));
    }
    view.outer_iter()
        .map(|row| {
            let mut output = [0usize; N];
            for index in 0..N {
                let value = row[index];
                if value < 0 || value as usize >= bounds {
                    return Err(PyValueError::new_err(format!("{name} index out of range")));
                }
                output[index] = value as usize;
            }
            Ok(output)
        })
        .collect()
}

fn subtract(first: [f64; 3], second: [f64; 3]) -> [f64; 3] {
    [
        first[0] - second[0],
        first[1] - second[1],
        first[2] - second[2],
    ]
}

fn dot(first: [f64; 3], second: [f64; 3]) -> f64 {
    first[0] * second[0] + first[1] * second[1] + first[2] * second[2]
}

fn norm(value: [f64; 3]) -> f64 {
    dot(value, value).sqrt()
}

fn cross(first: [f64; 3], second: [f64; 3]) -> [f64; 3] {
    [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]
}

fn scale(value: [f64; 3], factor: f64) -> [f64; 3] {
    [value[0] * factor, value[1] * factor, value[2] * factor]
}

fn lj(first_epsilon: f64, second_epsilon: f64, sigma: f64, distance: f64) -> f64 {
    if distance <= 1.0e-8 {
        return 1.0e6;
    }
    let ratio = (sigma / distance).min(2.0);
    let sixth = ratio.powi(6);
    (first_epsilon * second_epsilon).sqrt() * (sixth * sixth - 2.0 * sixth)
}

fn dihedral(coordinates: &[[f64; 3]], atoms: [usize; 4]) -> Result<f64, &'static str> {
    let first = coordinates[atoms[0]];
    let second = coordinates[atoms[1]];
    let third = coordinates[atoms[2]];
    let fourth = coordinates[atoms[3]];
    let middle = subtract(third, second);
    let middle_norm = norm(middle);
    if middle_norm <= 1.0e-12 {
        return Err("degenerate_rotor_geometry");
    }
    let axis = scale(middle, 1.0 / middle_norm);
    let mut left = subtract(first, second);
    let mut right = subtract(fourth, third);
    left = subtract(left, scale(axis, dot(left, axis)));
    right = subtract(right, scale(axis, dot(right, axis)));
    let left_norm = norm(left);
    let right_norm = norm(right);
    if left_norm.min(right_norm) <= 1.0e-12 {
        return Err("degenerate_rotor_geometry");
    }
    left = scale(left, 1.0 / left_norm);
    right = scale(right, 1.0 / right_norm);
    Ok(dot(cross(left, right), axis).atan2(dot(left, right)))
}

fn hbond_reward(donor: [f64; 3], hydrogen: [f64; 3], acceptor: [f64; 3], cutoff: f64) -> f64 {
    let distance = norm(subtract(hydrogen, acceptor));
    if distance > cutoff || distance <= 1.0e-8 {
        return 0.0;
    }
    let first = subtract(donor, hydrogen);
    let second = subtract(acceptor, hydrogen);
    let denominator = norm(first) * norm(second);
    if denominator <= 1.0e-12 {
        return 0.0;
    }
    let cosine = dot(first, second) / denominator;
    let angular = ((-cosine - 0.5) / 0.5).clamp(0.0, 1.0);
    let radial = (1.0 - distance / cutoff).max(0.0);
    angular * radial
}

impl NativeScorerContext {
    fn score_one(&self, pose: &[[f64; 3]]) -> NativeScoreRow {
        if pose.len() != self.ligand_charges.len()
            || pose.iter().flatten().any(|value| !value.is_finite())
        {
            return NativeScoreRow::failure("invalid_candidate_coordinates", 0, 0);
        }
        let mut typed_vdw_raw = 0.0;
        let mut electro_raw = 0.0;
        let mut hydrophobic_raw = 0.0;
        let mut hydrophobic_count = 0usize;
        let mut candidate_count = 0usize;
        let mut polar_buried = vec![false; pose.len()];
        let mut polar_satisfied = vec![false; pose.len()];
        let mut accepted_pairs: Vec<(usize, usize)> = Vec::new();
        for (ligand_index, coordinate) in pose.iter().copied().enumerate() {
            let center = (
                (coordinate[0] / self.config.pair_cutoff).floor() as i64,
                (coordinate[1] / self.config.pair_cutoff).floor() as i64,
                (coordinate[2] / self.config.pair_cutoff).floor() as i64,
            );
            for x in (center.0 - 1)..=(center.0 + 1) {
                for y in (center.1 - 1)..=(center.1 + 1) {
                    for z in (center.2 - 1)..=(center.2 + 1) {
                        if let Some(indices) = self.receptor_cells.get(&(x, y, z)) {
                            for receptor_index in indices.iter().copied() {
                                candidate_count += 1;
                                if candidate_count > self.config.max_receptor_pairs {
                                    return NativeScoreRow::failure(
                                        "receptor_candidate_pair_capacity_exceeded",
                                        candidate_count,
                                        0,
                                    );
                                }
                                let distance =
                                    norm(subtract(coordinate, self.receptor[receptor_index]));
                                if distance > self.config.pair_cutoff {
                                    continue;
                                }
                                accepted_pairs.push((ligand_index, receptor_index));
                                let sigma = self.ligand_radii[ligand_index]
                                    + self.receptor_radii[receptor_index];
                                typed_vdw_raw += lj(
                                    self.ligand_epsilons[ligand_index],
                                    self.receptor_epsilons[receptor_index],
                                    sigma,
                                    distance,
                                );
                                electro_raw += self.ligand_charges[ligand_index]
                                    * self.receptor_charges[receptor_index]
                                    / (self.config.dielectric * distance.max(0.5));
                                if self.ligand_hydrophobic[ligand_index]
                                    && self.receptor_hydrophobic[receptor_index]
                                    && distance <= 1.25 * sigma
                                {
                                    hydrophobic_count += 1;
                                    hydrophobic_raw += (1.0 - distance / (1.25 * sigma)).max(0.0);
                                }
                                let ligand_polar = self.ligand_acceptors[ligand_index]
                                    || self.ligand_donor_by_hydrogen.iter().any(|donor| {
                                        donor.map(|value| value == ligand_index).unwrap_or(false)
                                    });
                                if ligand_polar && distance <= self.config.polar_burial_cutoff {
                                    polar_buried[ligand_index] = true;
                                }
                            }
                        }
                    }
                }
            }
        }

        let mut hbond_raw = 0.0;
        let mut hbond_count = 0usize;
        for (ligand_index, receptor_index) in accepted_pairs.iter().copied() {
            if let Some(donor) = self.ligand_donor_by_hydrogen[ligand_index] {
                if self.receptor_acceptors[receptor_index] {
                    let reward = hbond_reward(
                        pose[donor],
                        pose[ligand_index],
                        self.receptor[receptor_index],
                        self.config.hbond_cutoff,
                    );
                    if reward > 0.0 {
                        hbond_raw += reward;
                        hbond_count += 1;
                        polar_satisfied[donor] = true;
                    }
                }
            }
            if let Some(donor) = self.receptor_donor_by_hydrogen[receptor_index] {
                if self.ligand_acceptors[ligand_index] {
                    let reward = hbond_reward(
                        self.receptor[donor],
                        self.receptor[receptor_index],
                        pose[ligand_index],
                        self.config.hbond_cutoff,
                    );
                    if reward > 0.0 {
                        hbond_raw += reward;
                        hbond_count += 1;
                        polar_satisfied[ligand_index] = true;
                    }
                }
            }
        }

        let mut internal = 0.0;
        let mut ligand_pair_count = 0usize;
        for first in 0..pose.len() {
            for second in (first + 1)..pose.len() {
                if self.ligand_exclusions.contains(&(first, second)) {
                    continue;
                }
                ligand_pair_count += 1;
                if ligand_pair_count > self.config.max_ligand_pairs {
                    return NativeScoreRow::failure(
                        "ligand_pair_capacity_exceeded",
                        candidate_count,
                        ligand_pair_count,
                    );
                }
                internal += lj(
                    self.ligand_epsilons[first],
                    self.ligand_epsilons[second],
                    self.ligand_radii[first] + self.ligand_radii[second],
                    norm(subtract(pose[first], pose[second])),
                );
            }
        }
        let strain_raw = (internal - self.reference_internal_vdw).max(0.0);
        let mut torsion_raw = 0.0;
        for (quad, reference) in self.rotor_quads.iter().zip(self.reference_dihedrals.iter()) {
            let observed = match dihedral(pose, *quad) {
                Ok(value) => value,
                Err(code) => {
                    return NativeScoreRow::failure(code, candidate_count, ligand_pair_count)
                }
            };
            let delta = (observed - reference)
                .sin()
                .atan2((observed - reference).cos());
            torsion_raw += 0.5 * (1.0 - (3.0 * delta).cos());
        }
        let centroid = [
            pose.iter().map(|row| row[0]).sum::<f64>() / pose.len() as f64,
            pose.iter().map(|row| row[1]).sum::<f64>() / pose.len() as f64,
            pose.iter().map(|row| row[2]).sum::<f64>() / pose.len() as f64,
        ];
        let pocket_raw =
            (norm(subtract(centroid, self.pocket_center)) / self.pocket_radius).powi(2);
        let buried_polar_count = polar_buried
            .iter()
            .zip(polar_satisfied.iter())
            .filter(|(buried, satisfied)| **buried && !**satisfied)
            .count();
        let raw = [
            typed_vdw_raw,
            electro_raw,
            -hbond_raw,
            -hydrophobic_raw,
            buried_polar_count as f64,
            torsion_raw,
            strain_raw,
            pocket_raw,
        ];
        let weighted: Vec<f64> = raw
            .iter()
            .zip(self.config.weights.iter())
            .map(|(value, weight)| value * weight)
            .collect();
        let total = weighted.iter().sum();
        let mut terms = weighted;
        terms.push(total);
        if terms.iter().any(|value| !value.is_finite()) {
            return NativeScoreRow::failure("nonfinite_score", candidate_count, ligand_pair_count);
        }
        NativeScoreRow {
            terms,
            receptor_candidate_pair_count: candidate_count,
            ligand_pair_count,
            hbond_count,
            hydrophobic_contact_count: hydrophobic_count,
            buried_polar_count: polar_buried.iter().filter(|value| **value).count(),
            error_code: None,
        }
    }
}

#[pymethods]
impl NativeScorerContext {
    #[new]
    #[pyo3(signature = (
        receptor_coordinates,
        receptor_charges,
        ligand_charges,
        receptor_radii,
        ligand_radii,
        receptor_epsilons,
        ligand_epsilons,
        receptor_hydrophobic,
        ligand_hydrophobic,
        receptor_acceptors,
        ligand_acceptors,
        receptor_donors,
        ligand_donors,
        ligand_exclusions,
        rotor_quads,
        reference_dihedrals,
        reference_internal_vdw,
        pocket_center,
        pocket_radius,
        config_values,
        weights,
        max_receptor_pairs,
        max_ligand_pairs,
        thread_count
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        receptor_coordinates: PyReadonlyArray2<'_, f64>,
        receptor_charges: PyReadonlyArray1<'_, f64>,
        ligand_charges: PyReadonlyArray1<'_, f64>,
        receptor_radii: PyReadonlyArray1<'_, f64>,
        ligand_radii: PyReadonlyArray1<'_, f64>,
        receptor_epsilons: PyReadonlyArray1<'_, f64>,
        ligand_epsilons: PyReadonlyArray1<'_, f64>,
        receptor_hydrophobic: PyReadonlyArray1<'_, u8>,
        ligand_hydrophobic: PyReadonlyArray1<'_, u8>,
        receptor_acceptors: PyReadonlyArray1<'_, u8>,
        ligand_acceptors: PyReadonlyArray1<'_, u8>,
        receptor_donors: PyReadonlyArray2<'_, i32>,
        ligand_donors: PyReadonlyArray2<'_, i32>,
        ligand_exclusions: PyReadonlyArray2<'_, i32>,
        rotor_quads: PyReadonlyArray2<'_, i32>,
        reference_dihedrals: PyReadonlyArray1<'_, f64>,
        reference_internal_vdw: f64,
        pocket_center: PyReadonlyArray1<'_, f64>,
        pocket_radius: f64,
        config_values: PyReadonlyArray1<'_, f64>,
        weights: PyReadonlyArray1<'_, f64>,
        max_receptor_pairs: usize,
        max_ligand_pairs: usize,
        thread_count: usize,
    ) -> PyResult<Self> {
        let receptor = rows3(receptor_coordinates, "receptor_coordinates")?;
        let receptor_count = receptor.len();
        let ligand_count = ligand_charges.len();
        if receptor_count == 0 || ligand_count == 0 {
            return Err(PyValueError::new_err("atom counts must be non-zero"));
        }
        if thread_count == 0 || thread_count > 64 {
            return Err(PyValueError::new_err("thread_count must be in [1,64]"));
        }
        let config_slice = config_values.as_slice()?;
        let weights_slice = weights.as_slice()?;
        if config_slice.len() != 4 || weights_slice.len() != 8 {
            return Err(PyValueError::new_err(
                "config_values/weights shape mismatch",
            ));
        }
        require_finite(config_slice.iter().copied(), "config_values")?;
        require_finite(weights_slice.iter().copied(), "weights")?;
        if config_slice.iter().any(|value| *value <= 0.0)
            || pocket_radius <= 0.0
            || !pocket_radius.is_finite()
        {
            return Err(PyValueError::new_err("positive scorer ranges are required"));
        }
        let receptor_donor_rows =
            index_rows::<2>(receptor_donors, receptor_count, "receptor_donors")?;
        let ligand_donor_rows = index_rows::<2>(ligand_donors, ligand_count, "ligand_donors")?;
        let exclusions = index_rows::<2>(ligand_exclusions, ligand_count, "ligand_exclusions")?;
        let rotors = index_rows::<4>(rotor_quads, ligand_count, "rotor_quads")?;
        let references = reference_dihedrals.as_slice()?.to_vec();
        if references.len() != rotors.len() {
            return Err(PyValueError::new_err("reference_dihedrals length mismatch"));
        }
        require_finite(references.iter().copied(), "reference_dihedrals")?;
        let center_slice = pocket_center.as_slice()?;
        if center_slice.len() != 3 {
            return Err(PyValueError::new_err("pocket_center must have length 3"));
        }
        require_finite(center_slice.iter().copied(), "pocket_center")?;
        let config = Config {
            dielectric: config_slice[0],
            pair_cutoff: config_slice[1],
            hbond_cutoff: config_slice[2],
            polar_burial_cutoff: config_slice[3],
            max_receptor_pairs,
            max_ligand_pairs,
            weights: weights_slice.try_into().expect("checked weight length"),
        };
        let mut receptor_cells: BTreeMap<(i64, i64, i64), Vec<usize>> = BTreeMap::new();
        for (index, coordinate) in receptor.iter().copied().enumerate() {
            receptor_cells
                .entry((
                    (coordinate[0] / config.pair_cutoff).floor() as i64,
                    (coordinate[1] / config.pair_cutoff).floor() as i64,
                    (coordinate[2] / config.pair_cutoff).floor() as i64,
                ))
                .or_default()
                .push(index);
        }
        let mut receptor_donor_by_hydrogen = vec![None; receptor_count];
        for [donor, hydrogen] in receptor_donor_rows {
            receptor_donor_by_hydrogen[hydrogen] = Some(donor);
        }
        let mut ligand_donor_by_hydrogen = vec![None; ligand_count];
        for [donor, hydrogen] in ligand_donor_rows {
            ligand_donor_by_hydrogen[hydrogen] = Some(donor);
        }
        let pool = ThreadPoolBuilder::new()
            .num_threads(thread_count)
            .build()
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(Self {
            receptor,
            receptor_cells,
            receptor_charges: vec_f64(receptor_charges, receptor_count, "receptor_charges")?,
            ligand_charges: vec_f64(ligand_charges, ligand_count, "ligand_charges")?,
            receptor_radii: vec_f64(receptor_radii, receptor_count, "receptor_radii")?,
            ligand_radii: vec_f64(ligand_radii, ligand_count, "ligand_radii")?,
            receptor_epsilons: vec_f64(receptor_epsilons, receptor_count, "receptor_epsilons")?,
            ligand_epsilons: vec_f64(ligand_epsilons, ligand_count, "ligand_epsilons")?,
            receptor_hydrophobic: vec_mask(
                receptor_hydrophobic,
                receptor_count,
                "receptor_hydrophobic",
            )?,
            ligand_hydrophobic: vec_mask(ligand_hydrophobic, ligand_count, "ligand_hydrophobic")?,
            receptor_acceptors: vec_mask(receptor_acceptors, receptor_count, "receptor_acceptors")?,
            ligand_acceptors: vec_mask(ligand_acceptors, ligand_count, "ligand_acceptors")?,
            receptor_donor_by_hydrogen,
            ligand_donor_by_hydrogen,
            ligand_exclusions: exclusions.into_iter().map(|row| (row[0], row[1])).collect(),
            rotor_quads: rotors,
            reference_dihedrals: references,
            reference_internal_vdw,
            pocket_center: [center_slice[0], center_slice[1], center_slice[2]],
            pocket_radius,
            config,
            pool,
        })
    }

    fn score_batch(
        &self,
        py: Python<'_>,
        coordinates: PyReadonlyArray3<'_, f64>,
    ) -> PyResult<Vec<NativeScoreRow>> {
        let view = coordinates.as_array();
        let shape = view.shape();
        if shape.len() != 3
            || shape[0] == 0
            || shape[0] > MAX_BATCH_SIZE
            || shape[1] != self.ligand_charges.len()
            || shape[2] != 3
        {
            return Err(PyValueError::new_err(
                "coordinates must have shape [C,L,3] with C in [1,64]",
            ));
        }
        let poses: Vec<Vec<[f64; 3]>> = view
            .outer_iter()
            .map(|candidate| {
                candidate
                    .outer_iter()
                    .map(|row| [row[0], row[1], row[2]])
                    .collect()
            })
            .collect();
        Ok(py.allow_threads(|| {
            self.pool
                .install(|| poses.par_iter().map(|pose| self.score_one(pose)).collect())
        }))
    }
}

#[pyfunction]
fn build_info() -> BTreeMap<&'static str, String> {
    BTreeMap::from([
        ("backend_id", "rust_cpu_required".to_owned()),
        ("backend_version", env!("CARGO_PKG_VERSION").to_owned()),
        ("crate_name", env!("CARGO_PKG_NAME").to_owned()),
        (
            "cargo_lock_sha256",
            env!("BETELGEUZE_CARGO_LOCK_SHA256").to_owned(),
        ),
        ("rustc_version", env!("BETELGEUZE_RUSTC_VERSION").to_owned()),
        ("target_triple", env!("BETELGEUZE_TARGET_TRIPLE").to_owned()),
        ("build_flags", env!("BETELGEUZE_BUILD_FLAGS").to_owned()),
        ("implicit_fallback_allowed", "false".to_owned()),
    ])
}

#[pymodule]
fn betelgeuze_engine_v2_native(_py: Python<'_>, module: &PyModule) -> PyResult<()> {
    module.add_class::<NativeScorerContext>()?;
    module.add_class::<NativeScoreRow>()?;
    module.add_function(wrap_pyfunction!(build_info, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lj_is_bounded_at_overlap() {
        assert_eq!(lj(0.12, 0.12, 3.4, 0.0), 1.0e6);
    }

    #[test]
    fn hbond_rejects_out_of_range_geometry() {
        assert_eq!(
            hbond_reward([0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [8.0, 0.0, 0.0], 3.0),
            0.0
        );
    }
}
