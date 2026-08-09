#![allow(non_local_definitions)]

use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;
use rayon::{ThreadPool, ThreadPoolBuilder};
use std::collections::{BTreeMap, HashSet};

const MAX_BATCH_SIZE: usize = 64;
const GEOMETRIC_ADMISSION_METRICS_KERNEL_ID: &str =
    "betelgeuze.engine_v2_native_geometric_admission_metrics_one/1.0.0";
const GEOMETRIC_ADMISSION_PAIR_TRAVERSAL_ORDER: &str =
    "full_cartesian_ligand_index_major_receptor_index_minor";
const MAX_GEOMETRIC_LIGAND_ATOMS: usize = 512;
const MAX_GEOMETRIC_RECEPTOR_ATOMS: usize = 4096;
const MAX_GEOMETRIC_EXACT_PAIR_COUNT: usize =
    MAX_GEOMETRIC_LIGAND_ATOMS * MAX_GEOMETRIC_RECEPTOR_ATOMS;
const MAX_GEOMETRIC_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 100_000.0;
const MIN_GEOMETRIC_VDW_RADIUS_ANGSTROM: f64 = 0.1;
const MAX_GEOMETRIC_VDW_RADIUS_ANGSTROM: f64 = 10.0;
const MAX_GEOMETRIC_POCKET_RADIUS_ANGSTROM: f64 = 1_000.0;

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

#[pyclass(frozen)]
#[derive(Clone, Debug, PartialEq)]
struct NativeGeometricAdmissionMetrics {
    #[pyo3(get)]
    ligand_atom_count: usize,
    #[pyo3(get)]
    receptor_atom_count: usize,
    #[pyo3(get)]
    exact_pair_count: usize,
    #[pyo3(get)]
    raw_minimum_distance_angstrom: f64,
    #[pyo3(get)]
    minimum_vdw_surface_gap_angstrom: f64,
    #[pyo3(get)]
    minimum_vdw_ratio: f64,
    #[pyo3(get)]
    penetration_pair_count: usize,
    #[pyo3(get)]
    unique_ligand_penetration_atom_count: usize,
    #[pyo3(get)]
    unique_ligand_heavy_atom_penetration_count: usize,
    #[pyo3(get)]
    sphere_overlap_proxy_angstrom3: f64,
    #[pyo3(get)]
    pocket_escape_angstrom: f64,
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

fn bounded_geometric_rows3(
    array: PyReadonlyArray2<'_, f64>,
    maximum_count: usize,
    name: &str,
) -> PyResult<Vec<[f64; 3]>> {
    let view = array.as_array();
    if view.ncols() != 3 {
        return Err(PyValueError::new_err(format!(
            "{name} must have shape [N,3]"
        )));
    }
    if view.nrows() == 0 || view.nrows() > maximum_count {
        return Err(PyValueError::new_err(format!(
            "{name} count must be within [1,{maximum_count}]"
        )));
    }
    if view
        .iter()
        .any(|value| !value.is_finite() || value.abs() > MAX_GEOMETRIC_ABSOLUTE_COORDINATE_ANGSTROM)
    {
        return Err(PyValueError::new_err(format!(
            "{name} must be finite and within the coordinate safety envelope"
        )));
    }
    Ok(view
        .outer_iter()
        .map(|row| [row[0], row[1], row[2]])
        .collect())
}

fn vec_f64(array: PyReadonlyArray1<'_, f64>, length: usize, name: &str) -> PyResult<Vec<f64>> {
    if array.len() != length {
        return Err(PyValueError::new_err(format!("{name} length mismatch")));
    }
    let values = array.as_slice()?.to_vec();
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

fn validate_geometric_coordinates(
    coordinates: &[[f64; 3]],
    maximum_count: usize,
    name: &str,
) -> Result<(), String> {
    if coordinates.is_empty() || coordinates.len() > maximum_count {
        return Err(format!("{name} count must be within [1,{maximum_count}]"));
    }
    if coordinates
        .iter()
        .flatten()
        .any(|value| !value.is_finite() || value.abs() > MAX_GEOMETRIC_ABSOLUTE_COORDINATE_ANGSTROM)
    {
        return Err(format!(
            "{name} must be finite and within the coordinate safety envelope"
        ));
    }
    Ok(())
}

fn validate_geometric_radii(
    radii: &[f64],
    expected_count: usize,
    name: &str,
) -> Result<(), String> {
    if radii.len() != expected_count {
        return Err(format!("{name} length mismatch"));
    }
    if radii.iter().any(|radius| {
        !radius.is_finite()
            || !(MIN_GEOMETRIC_VDW_RADIUS_ANGSTROM..=MAX_GEOMETRIC_VDW_RADIUS_ANGSTROM)
                .contains(radius)
    }) {
        return Err(format!(
            "{name} must be finite and within the vdW radius safety envelope"
        ));
    }
    Ok(())
}

fn geometric_distance(left: [f64; 3], right: [f64; 3]) -> Result<f64, String> {
    let dx = left[0] - right[0];
    let dy = left[1] - right[1];
    let dz = left[2] - right[2];
    let distance = dx.hypot(dy).hypot(dz);
    if !distance.is_finite() {
        return Err("derived center distance is not finite".to_owned());
    }
    Ok(distance)
}

fn sphere_intersection_volume(
    radius_left: f64,
    radius_right: f64,
    center_distance: f64,
) -> Result<f64, String> {
    let radius_sum = radius_left + radius_right;
    if center_distance >= radius_sum {
        return Ok(0.0);
    }
    let radius_difference = (radius_left - radius_right).abs();
    let volume = if center_distance <= radius_difference {
        let smaller = radius_left.min(radius_right);
        (4.0 / 3.0) * std::f64::consts::PI * smaller.powi(3)
    } else {
        let numerator = std::f64::consts::PI
            * (radius_sum - center_distance).powi(2)
            * (center_distance.powi(2) + 2.0 * center_distance * radius_sum
                - 3.0 * radius_difference.powi(2));
        numerator / (12.0 * center_distance)
    };
    if !volume.is_finite() {
        return Err("sphere overlap proxy is not finite".to_owned());
    }
    // Near internal tangency, the analytic expression can undershoot zero by
    // a few ulps.  Python's reference implementation freezes zero as the
    // physically meaningful lower bound.
    Ok(volume.max(0.0))
}

#[allow(clippy::too_many_arguments)]
fn evaluate_geometric_admission_metrics_one(
    ligand_coordinates: &[[f64; 3]],
    ligand_vdw_radii: &[f64],
    ligand_heavy_atom_mask: &[bool],
    receptor_coordinates: &[[f64; 3]],
    receptor_vdw_radii: &[f64],
    pocket_center: [f64; 3],
    pocket_radius: f64,
) -> Result<NativeGeometricAdmissionMetrics, String> {
    validate_geometric_coordinates(
        ligand_coordinates,
        MAX_GEOMETRIC_LIGAND_ATOMS,
        "ligand_coordinates",
    )?;
    validate_geometric_coordinates(
        receptor_coordinates,
        MAX_GEOMETRIC_RECEPTOR_ATOMS,
        "receptor_coordinates",
    )?;
    validate_geometric_radii(
        ligand_vdw_radii,
        ligand_coordinates.len(),
        "ligand_vdw_radii",
    )?;
    validate_geometric_radii(
        receptor_vdw_radii,
        receptor_coordinates.len(),
        "receptor_vdw_radii",
    )?;
    if ligand_heavy_atom_mask.len() != ligand_coordinates.len() {
        return Err("ligand_heavy_atom_mask length mismatch".to_owned());
    }
    if pocket_center
        .iter()
        .any(|value| !value.is_finite() || value.abs() > MAX_GEOMETRIC_ABSOLUTE_COORDINATE_ANGSTROM)
    {
        return Err(
            "pocket_center must be finite and within the coordinate safety envelope".to_owned(),
        );
    }
    if !pocket_radius.is_finite()
        || !(0.0..=MAX_GEOMETRIC_POCKET_RADIUS_ANGSTROM).contains(&pocket_radius)
        || pocket_radius == 0.0
    {
        return Err("pocket_radius must be within the pocket safety envelope".to_owned());
    }
    let exact_pair_count = ligand_coordinates
        .len()
        .checked_mul(receptor_coordinates.len())
        .ok_or_else(|| "exact pair count overflowed".to_owned())?;
    if exact_pair_count > MAX_GEOMETRIC_EXACT_PAIR_COUNT {
        return Err("exact pair count exceeds the one-candidate safety envelope".to_owned());
    }

    let mut raw_minimum_distance = f64::INFINITY;
    let mut minimum_surface_gap = f64::INFINITY;
    let mut minimum_ratio = f64::INFINITY;
    let mut penetration_pair_count = 0usize;
    let mut penetrating_ligand_atoms = vec![false; ligand_coordinates.len()];
    let mut penetrating_heavy_ligand_atoms = vec![false; ligand_coordinates.len()];
    let mut sphere_overlap_proxy = 0.0;

    // This loop order is part of the kernel contract because it freezes the
    // floating-point overlap accumulation order as well as the denominator.
    for (ligand_index, (ligand_point, ligand_radius)) in ligand_coordinates
        .iter()
        .copied()
        .zip(ligand_vdw_radii.iter().copied())
        .enumerate()
    {
        for (receptor_point, receptor_radius) in receptor_coordinates
            .iter()
            .copied()
            .zip(receptor_vdw_radii.iter().copied())
        {
            let distance = geometric_distance(ligand_point, receptor_point)?;
            let radius_sum = ligand_radius + receptor_radius;
            let surface_gap = distance - radius_sum;
            let ratio = distance / radius_sum;
            raw_minimum_distance = raw_minimum_distance.min(distance);
            minimum_surface_gap = minimum_surface_gap.min(surface_gap);
            minimum_ratio = minimum_ratio.min(ratio);
            if distance < radius_sum {
                penetration_pair_count += 1;
                penetrating_ligand_atoms[ligand_index] = true;
                if ligand_heavy_atom_mask[ligand_index] {
                    penetrating_heavy_ligand_atoms[ligand_index] = true;
                }
                sphere_overlap_proxy +=
                    sphere_intersection_volume(ligand_radius, receptor_radius, distance)?;
                if !sphere_overlap_proxy.is_finite() {
                    return Err("sphere overlap proxy accumulation is not finite".to_owned());
                }
            }
        }
    }

    let mut pocket_escape = 0.0_f64;
    for (point, radius) in ligand_coordinates
        .iter()
        .copied()
        .zip(ligand_vdw_radii.iter().copied())
    {
        pocket_escape = pocket_escape
            .max((geometric_distance(point, pocket_center)? + radius - pocket_radius).max(0.0));
    }

    Ok(NativeGeometricAdmissionMetrics {
        ligand_atom_count: ligand_coordinates.len(),
        receptor_atom_count: receptor_coordinates.len(),
        exact_pair_count,
        raw_minimum_distance_angstrom: raw_minimum_distance,
        minimum_vdw_surface_gap_angstrom: minimum_surface_gap,
        minimum_vdw_ratio: minimum_ratio,
        penetration_pair_count,
        unique_ligand_penetration_atom_count: penetrating_ligand_atoms
            .iter()
            .filter(|penetrating| **penetrating)
            .count(),
        unique_ligand_heavy_atom_penetration_count: penetrating_heavy_ligand_atoms
            .iter()
            .filter(|penetrating| **penetrating)
            .count(),
        sphere_overlap_proxy_angstrom3: sphere_overlap_proxy,
        pocket_escape_angstrom: pocket_escape,
    })
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
#[pyo3(signature = (
    ligand_coordinates,
    *,
    ligand_vdw_radii,
    ligand_heavy_atom_mask,
    receptor_coordinates,
    receptor_vdw_radii,
    pocket_center,
    pocket_radius
))]
#[allow(clippy::too_many_arguments)]
fn geometric_admission_metrics_one(
    py: Python<'_>,
    ligand_coordinates: PyReadonlyArray2<'_, f64>,
    ligand_vdw_radii: PyReadonlyArray1<'_, f64>,
    ligand_heavy_atom_mask: PyReadonlyArray1<'_, u8>,
    receptor_coordinates: PyReadonlyArray2<'_, f64>,
    receptor_vdw_radii: PyReadonlyArray1<'_, f64>,
    pocket_center: PyReadonlyArray1<'_, f64>,
    pocket_radius: f64,
) -> PyResult<NativeGeometricAdmissionMetrics> {
    let ligand = bounded_geometric_rows3(
        ligand_coordinates,
        MAX_GEOMETRIC_LIGAND_ATOMS,
        "ligand_coordinates",
    )?;
    let receptor = bounded_geometric_rows3(
        receptor_coordinates,
        MAX_GEOMETRIC_RECEPTOR_ATOMS,
        "receptor_coordinates",
    )?;
    let ligand_radii = vec_f64(ligand_vdw_radii, ligand.len(), "ligand_vdw_radii")?;
    let receptor_radii = vec_f64(receptor_vdw_radii, receptor.len(), "receptor_vdw_radii")?;
    let heavy_atom_mask = vec_mask(
        ligand_heavy_atom_mask,
        ligand.len(),
        "ligand_heavy_atom_mask",
    )?;
    let pocket_center_slice = pocket_center.as_slice()?;
    if pocket_center_slice.len() != 3 {
        return Err(PyValueError::new_err("pocket_center must have length 3"));
    }
    let center = [
        pocket_center_slice[0],
        pocket_center_slice[1],
        pocket_center_slice[2],
    ];
    py.allow_threads(|| {
        evaluate_geometric_admission_metrics_one(
            &ligand,
            &ligand_radii,
            &heavy_atom_mask,
            &receptor,
            &receptor_radii,
            center,
            pocket_radius,
        )
    })
    .map_err(PyValueError::new_err)
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
        (
            "cargo_manifest_sha256",
            env!("BETELGEUZE_CARGO_MANIFEST_SHA256").to_owned(),
        ),
        (
            "native_pyproject_sha256",
            env!("BETELGEUZE_NATIVE_PYPROJECT_SHA256").to_owned(),
        ),
        (
            "rust_lib_sha256",
            env!("BETELGEUZE_RUST_LIB_SHA256").to_owned(),
        ),
        (
            "build_script_sha256",
            env!("BETELGEUZE_BUILD_SCRIPT_SHA256").to_owned(),
        ),
        (
            "native_build_wrapper_sha256",
            env!("BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256").to_owned(),
        ),
        ("rustc_version", env!("BETELGEUZE_RUSTC_VERSION").to_owned()),
        (
            "rustc_verbose_sha256",
            env!("BETELGEUZE_RUSTC_VERBOSE_SHA256").to_owned(),
        ),
        (
            "rustc_executable_sha256",
            env!("BETELGEUZE_RUSTC_EXECUTABLE_SHA256").to_owned(),
        ),
        ("target_triple", env!("BETELGEUZE_TARGET_TRIPLE").to_owned()),
        ("host_triple", env!("BETELGEUZE_HOST_TRIPLE").to_owned()),
        ("build_profile", env!("BETELGEUZE_BUILD_PROFILE").to_owned()),
        (
            "build_opt_level",
            env!("BETELGEUZE_BUILD_OPT_LEVEL").to_owned(),
        ),
        ("build_debug", env!("BETELGEUZE_BUILD_DEBUG").to_owned()),
        ("build_panic", env!("BETELGEUZE_RELEASE_PANIC").to_owned()),
        (
            "build_script_cfg_panic",
            env!("BETELGEUZE_BUILD_SCRIPT_CFG_PANIC").to_owned(),
        ),
        (
            "release_codegen_units",
            env!("BETELGEUZE_RELEASE_CODEGEN_UNITS").to_owned(),
        ),
        (
            "release_debug_assertions",
            env!("BETELGEUZE_RELEASE_DEBUG_ASSERTIONS").to_owned(),
        ),
        (
            "release_incremental",
            env!("BETELGEUZE_RELEASE_INCREMENTAL").to_owned(),
        ),
        ("release_lto", env!("BETELGEUZE_RELEASE_LTO").to_owned()),
        (
            "release_overflow_checks",
            env!("BETELGEUZE_RELEASE_OVERFLOW_CHECKS").to_owned(),
        ),
        ("release_panic", env!("BETELGEUZE_RELEASE_PANIC").to_owned()),
        ("release_strip", env!("BETELGEUZE_RELEASE_STRIP").to_owned()),
        ("target_arch", env!("BETELGEUZE_TARGET_ARCH").to_owned()),
        ("target_env", env!("BETELGEUZE_TARGET_ENV").to_owned()),
        (
            "target_features",
            env!("BETELGEUZE_TARGET_FEATURES").to_owned(),
        ),
        ("target_os", env!("BETELGEUZE_TARGET_OS").to_owned()),
        (
            "rustflags_sha256",
            env!("BETELGEUZE_RUSTFLAGS_SHA256").to_owned(),
        ),
        (
            "rustflags_count",
            env!("BETELGEUZE_RUSTFLAGS_COUNT").to_owned(),
        ),
        (
            "build_wrapper_control",
            env!("BETELGEUZE_BUILD_WRAPPER_CONTROL").to_owned(),
        ),
        ("build_flags", env!("BETELGEUZE_BUILD_FLAGS").to_owned()),
        ("implicit_fallback_allowed", "false".to_owned()),
        (
            "geometric_admission_metrics_kernel_id",
            GEOMETRIC_ADMISSION_METRICS_KERNEL_ID.to_owned(),
        ),
        (
            "geometric_admission_pair_traversal_order",
            GEOMETRIC_ADMISSION_PAIR_TRAVERSAL_ORDER.to_owned(),
        ),
    ])
}

#[pymodule]
fn betelgeuze_engine_v2_native(_py: Python<'_>, module: &PyModule) -> PyResult<()> {
    module.add_class::<NativeScorerContext>()?;
    module.add_class::<NativeScoreRow>()?;
    module.add_class::<NativeGeometricAdmissionMetrics>()?;
    module.add_function(wrap_pyfunction!(build_info, module)?)?;
    module.add_function(wrap_pyfunction!(geometric_admission_metrics_one, module)?)?;
    module.add(
        "GEOMETRIC_ADMISSION_METRICS_KERNEL_ID",
        GEOMETRIC_ADMISSION_METRICS_KERNEL_ID,
    )?;
    module.add(
        "GEOMETRIC_ADMISSION_PAIR_TRAVERSAL_ORDER",
        GEOMETRIC_ADMISSION_PAIR_TRAVERSAL_ORDER,
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_close(observed: f64, expected: f64, tolerance: f64) {
        assert!(
            (observed - expected).abs() <= tolerance,
            "observed={observed:?}, expected={expected:?}, tolerance={tolerance:?}"
        );
    }

    #[test]
    fn geometric_metrics_match_frozen_full_cartesian_fixture() {
        let metrics = evaluate_geometric_admission_metrics_one(
            &[[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]],
            &[1.0, 1.0],
            &[true, false],
            &[[0.0, 0.0, 0.0], [8.0, 0.0, 0.0]],
            &[1.0, 1.0],
            [0.0, 0.0, 0.0],
            4.0,
        )
        .expect("frozen synthetic fixture must be valid");

        assert_eq!(metrics.ligand_atom_count, 2);
        assert_eq!(metrics.receptor_atom_count, 2);
        assert_eq!(metrics.exact_pair_count, 4);
        assert_eq!(metrics.raw_minimum_distance_angstrom, 0.0);
        assert_eq!(metrics.minimum_vdw_surface_gap_angstrom, -2.0);
        assert_eq!(metrics.minimum_vdw_ratio, 0.0);
        assert_eq!(metrics.penetration_pair_count, 1);
        assert_eq!(metrics.unique_ligand_penetration_atom_count, 1);
        assert_eq!(metrics.unique_ligand_heavy_atom_penetration_count, 1);
        assert_close(
            metrics.sphere_overlap_proxy_angstrom3,
            (4.0 / 3.0) * std::f64::consts::PI,
            1.0e-15,
        );
        assert_eq!(metrics.pocket_escape_angstrom, 2.0);
    }

    #[test]
    fn geometric_metrics_use_exact_partial_sphere_overlap_definition() {
        let metrics = evaluate_geometric_admission_metrics_one(
            &[[1.0, 0.0, 0.0]],
            &[1.0],
            &[false],
            &[[0.0, 0.0, 0.0]],
            &[1.0],
            [0.0, 0.0, 0.0],
            5.0,
        )
        .expect("partial-overlap fixture must be valid");

        assert_eq!(metrics.minimum_vdw_ratio, 0.5);
        assert_eq!(metrics.penetration_pair_count, 1);
        assert_eq!(metrics.unique_ligand_penetration_atom_count, 1);
        assert_eq!(metrics.unique_ligand_heavy_atom_penetration_count, 0);
        assert_close(
            metrics.sphere_overlap_proxy_angstrom3,
            5.0 * std::f64::consts::PI / 12.0,
            1.0e-15,
        );
    }

    #[test]
    fn geometric_metrics_report_zero_overlap_without_penetration() {
        let metrics = evaluate_geometric_admission_metrics_one(
            &[[3.0, 0.0, 0.0]],
            &[1.0],
            &[true],
            &[[0.0, 0.0, 0.0]],
            &[1.0],
            [0.0, 0.0, 0.0],
            5.0,
        )
        .expect("separated fixture must be valid");

        assert_eq!(metrics.raw_minimum_distance_angstrom, 3.0);
        assert_eq!(metrics.minimum_vdw_surface_gap_angstrom, 1.0);
        assert_eq!(metrics.minimum_vdw_ratio, 1.5);
        assert_eq!(metrics.penetration_pair_count, 0);
        assert_eq!(metrics.unique_ligand_penetration_atom_count, 0);
        assert_eq!(metrics.unique_ligand_heavy_atom_penetration_count, 0);
        assert_eq!(metrics.sphere_overlap_proxy_angstrom3, 0.0);
        assert_eq!(metrics.pocket_escape_angstrom, 0.0);
    }

    #[test]
    fn geometric_metrics_are_bit_stable_on_repeated_evaluation() {
        let ligand = [[0.25, -0.5, 1.25], [2.0, 0.75, -1.0]];
        let ligand_radii = [1.7, 1.2];
        let heavy = [true, false];
        let receptor = [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [-2.0, 1.0, 0.5]];
        let receptor_radii = [1.5, 1.8, 1.1];
        let first = evaluate_geometric_admission_metrics_one(
            &ligand,
            &ligand_radii,
            &heavy,
            &receptor,
            &receptor_radii,
            [0.5, 0.5, 0.5],
            4.5,
        )
        .expect("fixture must be valid");
        let second = evaluate_geometric_admission_metrics_one(
            &ligand,
            &ligand_radii,
            &heavy,
            &receptor,
            &receptor_radii,
            [0.5, 0.5, 0.5],
            4.5,
        )
        .expect("fixture must be valid");

        assert_eq!(first, second);
    }

    #[test]
    fn geometric_metrics_freeze_ligand_major_receptor_minor_overlap_accumulation() {
        let ligand = [[0.0, 0.0, 0.0], [0.125, 0.0, 0.0]];
        let ligand_radii = [10.0, 0.1];
        let receptor = [[0.0, 0.0, 0.0], [0.0625, 0.0, 0.0]];
        let receptor_radii = [10.0, 0.1];
        let metrics = evaluate_geometric_admission_metrics_one(
            &ligand,
            &ligand_radii,
            &[true, true],
            &receptor,
            &receptor_radii,
            [0.0, 0.0, 0.0],
            100.0,
        )
        .expect("fixture must be valid");
        let mut expected = 0.0;
        for (ligand_point, ligand_radius) in ligand.iter().zip(ligand_radii) {
            for (receptor_point, receptor_radius) in receptor.iter().zip(receptor_radii) {
                let distance = geometric_distance(*ligand_point, *receptor_point)
                    .expect("bounded distance must remain finite");
                if distance < ligand_radius + receptor_radius {
                    expected +=
                        sphere_intersection_volume(ligand_radius, receptor_radius, distance)
                            .expect("bounded overlap must remain finite");
                }
            }
        }
        assert_eq!(
            metrics.sphere_overlap_proxy_angstrom3.to_bits(),
            expected.to_bits()
        );
        assert_eq!(metrics.exact_pair_count, 4);
    }

    #[test]
    fn geometric_metrics_fail_closed_on_malformed_or_unbounded_inputs() {
        let valid_ligand = [[0.0, 0.0, 0.0]];
        let valid_receptor = [[2.0, 0.0, 0.0]];
        let evaluate = |ligand: &[[f64; 3]],
                        ligand_radii: &[f64],
                        heavy: &[bool],
                        receptor: &[[f64; 3]],
                        receptor_radii: &[f64],
                        center: [f64; 3],
                        radius: f64| {
            evaluate_geometric_admission_metrics_one(
                ligand,
                ligand_radii,
                heavy,
                receptor,
                receptor_radii,
                center,
                radius,
            )
        };

        assert!(evaluate(&[], &[], &[], &valid_receptor, &[1.0], [0.0; 3], 4.0).is_err());
        assert!(evaluate(
            &valid_ligand,
            &[],
            &[true],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            4.0,
        )
        .is_err());
        assert!(evaluate(
            &valid_ligand,
            &[1.0],
            &[],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            4.0,
        )
        .is_err());
        assert!(evaluate(
            &[[f64::NAN, 0.0, 0.0]],
            &[1.0],
            &[true],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            4.0,
        )
        .is_err());
        assert!(evaluate(
            &[[MAX_GEOMETRIC_ABSOLUTE_COORDINATE_ANGSTROM + 1.0, 0.0, 0.0]],
            &[1.0],
            &[true],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            4.0,
        )
        .is_err());
        assert!(evaluate(
            &valid_ligand,
            &[MIN_GEOMETRIC_VDW_RADIUS_ANGSTROM - 0.01],
            &[true],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            4.0,
        )
        .is_err());
        assert!(evaluate(
            &valid_ligand,
            &[1.0],
            &[true],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            0.0,
        )
        .is_err());
        assert!(evaluate(
            &valid_ligand,
            &[1.0],
            &[true],
            &valid_receptor,
            &[1.0],
            [0.0; 3],
            MAX_GEOMETRIC_POCKET_RADIUS_ANGSTROM + 1.0,
        )
        .is_err());
    }

    #[test]
    fn geometric_metrics_fail_closed_before_over_capacity_pair_work() {
        let too_many_ligand = vec![[0.0, 0.0, 0.0]; MAX_GEOMETRIC_LIGAND_ATOMS + 1];
        let too_many_receptor = vec![[0.0, 0.0, 0.0]; MAX_GEOMETRIC_RECEPTOR_ATOMS + 1];
        assert!(evaluate_geometric_admission_metrics_one(
            &too_many_ligand,
            &vec![1.0; too_many_ligand.len()],
            &vec![true; too_many_ligand.len()],
            &[[0.0, 0.0, 0.0]],
            &[1.0],
            [0.0; 3],
            4.0,
        )
        .is_err());
        assert!(evaluate_geometric_admission_metrics_one(
            &[[0.0, 0.0, 0.0]],
            &[1.0],
            &[true],
            &too_many_receptor,
            &vec![1.0; too_many_receptor.len()],
            [0.0; 3],
            4.0,
        )
        .is_err());
    }

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
