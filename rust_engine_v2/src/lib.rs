#![allow(non_local_definitions)]

mod docking_v2;
mod fixed64_pipeline;

use betelgeuze_docking_search::{
    NativeScorerV1Atom, NativeScorerV1Backend, NativeScorerV1Config, NativeScorerV1Context,
    NativeScorerV1Donor, NativeScorerV1KernelOutcome, NativeScorerV1RustCpuKernel, Vec3,
};
use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;
use rayon::{ThreadPool, ThreadPoolBuilder};
use std::collections::BTreeMap;

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
    core: NativeScorerV1Context,
    ligand_atom_count: usize,
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

fn canonical_sha256(value: &str, name: &str) -> PyResult<[u8; 32]> {
    let bytes = value.as_bytes();
    if bytes.len() != 64
        || bytes
            .iter()
            .any(|byte| !byte.is_ascii_digit() && !(b'a'..=b'f').contains(byte))
    {
        return Err(PyValueError::new_err(format!(
            "{name} must be 64 lowercase hexadecimal characters"
        )));
    }
    let mut digest = [0u8; 32];
    for (index, pair) in bytes.chunks_exact(2).enumerate() {
        let high = if pair[0].is_ascii_digit() {
            pair[0] - b'0'
        } else {
            pair[0] - b'a' + 10
        };
        let low = if pair[1].is_ascii_digit() {
            pair[1] - b'0'
        } else {
            pair[1] - b'a' + 10
        };
        digest[index] = (high << 4) | low;
    }
    if digest == [0; 32] {
        return Err(PyValueError::new_err(format!(
            "{name} must not be the all-zero digest"
        )));
    }
    Ok(digest)
}

fn native_coordinates(rows: &[[f64; 3]]) -> Vec<Vec3> {
    rows.iter()
        .map(|row| Vec3::new(row[0], row[1], row[2]))
        .collect()
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

impl NativeScorerContext {
    fn score_one(kernel: &NativeScorerV1RustCpuKernel<'_>, pose: &[[f64; 3]]) -> NativeScoreRow {
        let coordinates = pose
            .iter()
            .map(|row| Vec3::new(row[0], row[1], row[2]))
            .collect::<Vec<_>>();
        match kernel.score_coordinates(&coordinates) {
            NativeScorerV1KernelOutcome::Scored(scored) => {
                let mut terms = scored.weighted_terms().to_vec();
                terms.push(scored.total_score());
                NativeScoreRow {
                    terms,
                    receptor_candidate_pair_count: scored.receptor_candidate_pair_count(),
                    ligand_pair_count: scored.ligand_pair_count(),
                    hbond_count: scored.hbond_count(),
                    hydrophobic_contact_count: scored.hydrophobic_contact_count(),
                    buried_polar_count: scored.buried_polar_count(),
                    error_code: None,
                }
            }
            NativeScorerV1KernelOutcome::TypedFailure(failure) => NativeScoreRow::failure(
                failure.failure_code().id(),
                failure.receptor_candidate_pair_count(),
                failure.ligand_pair_count(),
            ),
        }
    }
}

#[pymethods]
impl NativeScorerContext {
    #[new]
    #[pyo3(signature = (
        authority_input_receipt_sha256,
        receptor_system_sha256,
        ligand_system_sha256,
        backend_receipt_sha256,
        receptor_coordinates,
        ligand_reference_coordinates,
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
        authority_input_receipt_sha256: &str,
        receptor_system_sha256: &str,
        ligand_system_sha256: &str,
        backend_receipt_sha256: &str,
        receptor_coordinates: PyReadonlyArray2<'_, f64>,
        ligand_reference_coordinates: PyReadonlyArray2<'_, f64>,
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
        pocket_center: PyReadonlyArray1<'_, f64>,
        pocket_radius: f64,
        config_values: PyReadonlyArray1<'_, f64>,
        weights: PyReadonlyArray1<'_, f64>,
        max_receptor_pairs: usize,
        max_ligand_pairs: usize,
        thread_count: usize,
    ) -> PyResult<Self> {
        let receptor = rows3(receptor_coordinates, "receptor_coordinates")?;
        let ligand_reference = rows3(ligand_reference_coordinates, "ligand_reference_coordinates")?;
        let receptor_count = receptor.len();
        let ligand_count = ligand_reference.len();
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
        let center_slice = pocket_center.as_slice()?;
        if center_slice.len() != 3 {
            return Err(PyValueError::new_err("pocket_center must have length 3"));
        }
        require_finite(center_slice.iter().copied(), "pocket_center")?;
        let receptor_charges = vec_f64(receptor_charges, receptor_count, "receptor_charges")?;
        let ligand_charges = vec_f64(ligand_charges, ligand_count, "ligand_charges")?;
        let receptor_radii = vec_f64(receptor_radii, receptor_count, "receptor_radii")?;
        let ligand_radii = vec_f64(ligand_radii, ligand_count, "ligand_radii")?;
        let receptor_epsilons = vec_f64(receptor_epsilons, receptor_count, "receptor_epsilons")?;
        let ligand_epsilons = vec_f64(ligand_epsilons, ligand_count, "ligand_epsilons")?;
        let receptor_hydrophobic =
            vec_mask(receptor_hydrophobic, receptor_count, "receptor_hydrophobic")?;
        let ligand_hydrophobic = vec_mask(ligand_hydrophobic, ligand_count, "ligand_hydrophobic")?;
        let receptor_acceptors =
            vec_mask(receptor_acceptors, receptor_count, "receptor_acceptors")?;
        let ligand_acceptors = vec_mask(ligand_acceptors, ligand_count, "ligand_acceptors")?;
        let receptor_atoms = (0..receptor_count)
            .map(|index| NativeScorerV1Atom {
                charge_elementary: receptor_charges[index],
                vdw_radius_angstrom: receptor_radii[index],
                epsilon_kcal_per_mol: receptor_epsilons[index],
                hydrophobic: receptor_hydrophobic[index],
                acceptor: receptor_acceptors[index],
            })
            .collect();
        let ligand_atoms = (0..ligand_count)
            .map(|index| NativeScorerV1Atom {
                charge_elementary: ligand_charges[index],
                vdw_radius_angstrom: ligand_radii[index],
                epsilon_kcal_per_mol: ligand_epsilons[index],
                hydrophobic: ligand_hydrophobic[index],
                acceptor: ligand_acceptors[index],
            })
            .collect();
        let mut receptor_donors = receptor_donor_rows
            .into_iter()
            .map(
                |[donor_atom_index, hydrogen_atom_index]| NativeScorerV1Donor {
                    donor_atom_index,
                    hydrogen_atom_index,
                },
            )
            .collect::<Vec<_>>();
        receptor_donors.sort_unstable();
        let mut ligand_donors = ligand_donor_rows
            .into_iter()
            .map(
                |[donor_atom_index, hydrogen_atom_index]| NativeScorerV1Donor {
                    donor_atom_index,
                    hydrogen_atom_index,
                },
            )
            .collect::<Vec<_>>();
        ligand_donors.sort_unstable();
        let mut scorer_weights = [0.0; 8];
        scorer_weights.copy_from_slice(weights_slice);
        let config = NativeScorerV1Config::new(
            scorer_weights,
            config_slice[0],
            config_slice[1],
            config_slice[2],
            config_slice[3],
            max_receptor_pairs,
            max_ligand_pairs,
        )
        .map_err(|error| PyValueError::new_err(error.to_string()))?;
        let core = NativeScorerV1Context::new(
            canonical_sha256(
                authority_input_receipt_sha256,
                "authority_input_receipt_sha256",
            )?,
            canonical_sha256(receptor_system_sha256, "receptor_system_sha256")?,
            canonical_sha256(ligand_system_sha256, "ligand_system_sha256")?,
            NativeScorerV1Backend::RustCpu,
            canonical_sha256(backend_receipt_sha256, "backend_receipt_sha256")?,
            native_coordinates(&receptor),
            receptor_atoms,
            native_coordinates(&ligand_reference),
            ligand_atoms,
            receptor_donors,
            ligand_donors,
            exclusions,
            rotors,
            Vec3::new(center_slice[0], center_slice[1], center_slice[2]),
            pocket_radius,
            config,
        )
        .map_err(|error| PyValueError::new_err(error.to_string()))?;
        let pool = ThreadPoolBuilder::new()
            .num_threads(thread_count)
            .build()
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(Self {
            core,
            ligand_atom_count: ligand_count,
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
            || shape[1] != self.ligand_atom_count
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
        let kernel = self
            .core
            .prepare_rust_cpu_kernel()
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(py.allow_threads(|| {
            self.pool.install(|| {
                poses
                    .par_iter()
                    .map(|pose| Self::score_one(&kernel, pose))
                    .collect()
            })
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

#[pyfunction]
fn docking_search_build_info() -> BTreeMap<&'static str, String> {
    BTreeMap::from([
        ("backend_id", "rust_cpu_required".to_owned()),
        ("backend_version", env!("CARGO_PKG_VERSION").to_owned()),
        ("crate_name", env!("CARGO_PKG_NAME").to_owned()),
        (
            "cargo_lock_sha256",
            env!("BETELGEUZE_CARGO_LOCK_SHA256").to_owned(),
        ),
        (
            "native_source_closure_sha256",
            env!("BETELGEUZE_NATIVE_SOURCE_CLOSURE_SHA256").to_owned(),
        ),
        (
            "native_source_closure_file_count",
            env!("BETELGEUZE_NATIVE_SOURCE_CLOSURE_FILE_COUNT").to_owned(),
        ),
        ("rustc_version", env!("BETELGEUZE_RUSTC_VERSION").to_owned()),
        ("target_triple", env!("BETELGEUZE_TARGET_TRIPLE").to_owned()),
        ("build_profile", env!("BETELGEUZE_BUILD_PROFILE").to_owned()),
        ("opt_level", env!("BETELGEUZE_BUILD_OPT_LEVEL").to_owned()),
        ("debug", env!("BETELGEUZE_BUILD_DEBUG").to_owned()),
        (
            "panic_strategy",
            if cfg!(panic = "abort") {
                "abort"
            } else {
                "unwind"
            }
            .to_owned(),
        ),
        (
            "build_flags",
            format!(
                "profile={},codegen-units={},debug={},lto={},opt-level={},panic={},strip={}",
                env!("BETELGEUZE_BUILD_PROFILE"),
                env!("BETELGEUZE_RELEASE_CODEGEN_UNITS"),
                env!("BETELGEUZE_BUILD_DEBUG"),
                env!("BETELGEUZE_RELEASE_LTO"),
                env!("BETELGEUZE_BUILD_OPT_LEVEL"),
                env!("BETELGEUZE_RELEASE_PANIC"),
                env!("BETELGEUZE_RELEASE_STRIP")
            ),
        ),
        (
            "cargo_features",
            if cfg!(feature = "extension-module") {
                "extension-module"
            } else {
                "none"
            }
            .to_owned(),
        ),
        ("implicit_fallback_allowed", "false".to_owned()),
        (
            "docking_search_schema_id",
            betelgeuze_docking_search::SEARCH_SCHEMA_ID.to_owned(),
        ),
        (
            "docking_search_receipt_schema_id",
            betelgeuze_docking_search::SEARCH_RECEIPT_SCHEMA_ID.to_owned(),
        ),
        (
            "docking_search_evaluator_id",
            "betelgeuze_short_range_analytic/1.0.0".to_owned(),
        ),
    ])
}

#[pymodule]
fn betelgeuze_engine_v2_native(_py: Python<'_>, module: &PyModule) -> PyResult<()> {
    module.add_class::<NativeScorerContext>()?;
    module.add_class::<NativeScoreRow>()?;
    module.add_class::<NativeGeometricAdmissionMetrics>()?;
    module.add_function(wrap_pyfunction!(build_info, module)?)?;
    module.add_function(wrap_pyfunction!(docking_search_build_info, module)?)?;
    module.add_function(wrap_pyfunction!(geometric_admission_metrics_one, module)?)?;
    module.add(
        "GEOMETRIC_ADMISSION_METRICS_KERNEL_ID",
        GEOMETRIC_ADMISSION_METRICS_KERNEL_ID,
    )?;
    module.add(
        "GEOMETRIC_ADMISSION_PAIR_TRAVERSAL_ORDER",
        GEOMETRIC_ADMISSION_PAIR_TRAVERSAL_ORDER,
    )?;
    docking_v2::register(module)?;
    fixed64_pipeline::register(module)?;
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

    #[test]
    fn geometric_and_docking_build_receipts_are_separate() {
        let geometric = build_info();
        let docking = docking_search_build_info();

        for docking_only_key in [
            "native_source_closure_sha256",
            "native_source_closure_file_count",
            "panic_strategy",
            "cargo_features",
            "docking_search_schema_id",
            "docking_search_receipt_schema_id",
            "docking_search_evaluator_id",
        ] {
            assert!(!geometric.contains_key(docking_only_key));
            assert!(docking.contains_key(docking_only_key));
        }
        for geometric_only_key in [
            "geometric_admission_metrics_kernel_id",
            "geometric_admission_pair_traversal_order",
            "native_build_wrapper_sha256",
            "rustc_executable_sha256",
        ] {
            assert!(geometric.contains_key(geometric_only_key));
            assert!(!docking.contains_key(geometric_only_key));
        }
    }
}
