use std::collections::BTreeSet;
use std::mem::size_of;

use betelgeuze_docking_search::{
    orientations, search_short_range, AnchorId, AnchorKind, CandidateKey, CandidateReason,
    CandidateStatus, LigandAnchor, LigandAtom, Orientation, PlacementMode, ReceptorAtom,
    SearchConfig, SearchError, SearchErrorCode, SearchInput, SearchResult, ShortRangeConfig,
    SurfaceId, SurfaceSample, Vec3, MAX_ANCHOR_COMBINATIONS, MAX_CANDIDATE_COORDINATES,
    MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS, MAX_EVALUATION_DETAIL_BYTES, MAX_LEDGER_PAYLOAD_BYTES,
    MAX_LIGAND_ANCHORS, MAX_LIGAND_ATOMS, MAX_PAIR_EVALUATIONS, MAX_RECEPTOR_ATOMS,
    MAX_SURFACE_SAMPLES, SEARCH_SCHEMA_ID,
};
use numpy::ndarray::Array2;
use numpy::{PyArray2, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyList};

const SEARCH_CONFIG_KEYS: [&str; 17] = [
    "orientation_count",
    "generated_candidate_limit",
    "coarse_keep",
    "refinement_keep",
    "top_k",
    "placement_clearance_angstrom",
    "dual_anchor_distance_tolerance_angstrom",
    "coarse_clash_weight",
    "refinement_steps",
    "translation_step_angstrom2_per_kcal",
    "rotation_step_per_torque",
    "maximum_translation_step_angstrom",
    "maximum_rotation_step_radians",
    "maximum_absolute_coordinate_angstrom",
    "minimum_ligand_atom_distance_angstrom",
    "minimum_receptor_clearance_scale",
    "cluster_rmsd_angstrom",
];
const SHORT_RANGE_CONFIG_KEYS: [&str; 5] = [
    "ligand_shape_force_constant_kcal_per_mol_angstrom2",
    "cutoff_angstrom",
    "switch_start_angstrom",
    "softcore_angstrom",
    "dielectric",
];
const MAX_PYTHON_BRIDGE_BYTES: usize = 64 * 1_024 * 1_024;
const PYTHON_BRIDGE_COORDINATE_ROW_BYTES: usize = 256;
const PYTHON_BRIDGE_CANDIDATE_ROW_BYTES: usize = 2_048;
const PYTHON_BRIDGE_POSE_BYTES: usize = 1_024;
const PYTHON_BRIDGE_ORIENTATION_ROW_BYTES: usize = 512;

pub(crate) fn register(module: &PyModule) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(docking_search_v2, module)?)?;
    Ok(())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn docking_search_v2(
    py: Python<'_>,
    source_seed_hex: &str,
    ligand_coordinates_angstrom: &PyAny,
    ligand_vdw_radii_angstrom: &PyAny,
    ligand_epsilon_kcal_per_mol: &PyAny,
    ligand_charge_elementary: &PyAny,
    ligand_anchor_ids: &PyAny,
    ligand_anchor_atom_indices: &PyAny,
    ligand_anchor_directions: &PyAny,
    ligand_anchor_kinds: &PyAny,
    receptor_coordinates_angstrom: &PyAny,
    receptor_vdw_radii_angstrom: &PyAny,
    receptor_epsilon_kcal_per_mol: &PyAny,
    receptor_charge_elementary: &PyAny,
    surface_ids: &PyAny,
    surface_positions_angstrom: &PyAny,
    surface_outward_normals: &PyAny,
    surface_anchor_kinds: &PyAny,
    search_config: &PyDict,
    short_range_config: &PyDict,
) -> PyResult<PyObject> {
    let search_config = parse_search_config(search_config)?;
    let short_range_config = parse_short_range_config(short_range_config)?;
    let ligand_count = bounded_len(
        ligand_coordinates_angstrom,
        "ligand_coordinates_angstrom",
        1,
        MAX_LIGAND_ATOMS,
    )?;
    let anchor_count = bounded_len(
        ligand_anchor_ids,
        "ligand_anchor_ids",
        1,
        MAX_LIGAND_ANCHORS,
    )?;
    let receptor_count = bounded_len(
        receptor_coordinates_angstrom,
        "receptor_coordinates_angstrom",
        0,
        MAX_RECEPTOR_ATOMS,
    )?;
    let surface_count = bounded_len(surface_ids, "surface_ids", 1, MAX_SURFACE_SAMPLES)?;
    let anchor_kinds =
        integer_values_any(ligand_anchor_kinds, "ligand_anchor_kinds", anchor_count)?;
    let surface_kinds =
        integer_values_any(surface_anchor_kinds, "surface_anchor_kinds", surface_count)?;
    let ligand_coordinates = rows3_any(
        ligand_coordinates_angstrom,
        "ligand_coordinates_angstrom",
        ligand_count,
        ligand_count,
    )?;
    let ligand_radii = f64_values_any(
        ligand_vdw_radii_angstrom,
        "ligand_vdw_radii_angstrom",
        ligand_count,
    )?;
    let ligand_epsilons = f64_values_any(
        ligand_epsilon_kcal_per_mol,
        "ligand_epsilon_kcal_per_mol",
        ligand_count,
    )?;
    let ligand_charges = f64_values_any(
        ligand_charge_elementary,
        "ligand_charge_elementary",
        ligand_count,
    )?;

    let anchor_ids = integer_values_any(ligand_anchor_ids, "ligand_anchor_ids", anchor_count)?;
    let anchor_atom_indices = integer_values_any(
        ligand_anchor_atom_indices,
        "ligand_anchor_atom_indices",
        anchor_count,
    )?;
    let anchor_directions = rows3_any(
        ligand_anchor_directions,
        "ligand_anchor_directions",
        anchor_count,
        anchor_count,
    )?;
    let receptor_coordinates = rows3_any(
        receptor_coordinates_angstrom,
        "receptor_coordinates_angstrom",
        receptor_count,
        receptor_count,
    )?;
    let receptor_radii = f64_values_any(
        receptor_vdw_radii_angstrom,
        "receptor_vdw_radii_angstrom",
        receptor_count,
    )?;
    let receptor_epsilons = f64_values_any(
        receptor_epsilon_kcal_per_mol,
        "receptor_epsilon_kcal_per_mol",
        receptor_count,
    )?;
    let receptor_charges = f64_values_any(
        receptor_charge_elementary,
        "receptor_charge_elementary",
        receptor_count,
    )?;

    let surface_ids = integer_values_any(surface_ids, "surface_ids", surface_count)?;
    let surface_positions = rows3_any(
        surface_positions_angstrom,
        "surface_positions_angstrom",
        surface_count,
        surface_count,
    )?;
    let surface_normals = rows3_any(
        surface_outward_normals,
        "surface_outward_normals",
        surface_count,
        surface_count,
    )?;
    let input = SearchInput {
        source_seed: decode_seed(source_seed_hex)?,
        ligand_atoms: ligand_coordinates
            .into_iter()
            .enumerate()
            .map(|(index, position_angstrom)| LigandAtom {
                position_angstrom,
                vdw_radius_angstrom: ligand_radii[index],
                epsilon_kcal_per_mol: ligand_epsilons[index],
                charge_elementary: ligand_charges[index],
            })
            .collect(),
        ligand_anchors: anchor_ids
            .into_iter()
            .enumerate()
            .map(|(index, id)| {
                Ok(LigandAnchor {
                    id: AnchorId(to_u32(id, "ligand_anchor_ids")?),
                    atom_index: to_index(
                        anchor_atom_indices[index],
                        ligand_count,
                        "ligand_anchor_atom_indices",
                    )?,
                    direction: anchor_directions[index],
                    kind: anchor_kind(anchor_kinds[index], "ligand_anchor_kinds")?,
                })
            })
            .collect::<PyResult<_>>()?,
        receptor_atoms: receptor_coordinates
            .into_iter()
            .enumerate()
            .map(|(index, position_angstrom)| ReceptorAtom {
                position_angstrom,
                vdw_radius_angstrom: receptor_radii[index],
                epsilon_kcal_per_mol: receptor_epsilons[index],
                charge_elementary: receptor_charges[index],
            })
            .collect(),
        surface_samples: surface_ids
            .into_iter()
            .enumerate()
            .map(|(index, id)| {
                Ok(SurfaceSample {
                    id: SurfaceId(to_u32(id, "surface_ids")?),
                    position_angstrom: surface_positions[index],
                    outward_normal: surface_normals[index],
                    anchor_kind: anchor_kind(surface_kinds[index], "surface_anchor_kinds")?,
                })
            })
            .collect::<PyResult<_>>()?,
    };
    validate_composite_preflight(&input, &search_config)?;
    let orientation_seed = input.source_seed;
    let orientation_count = search_config.orientation_count;
    let (result, orientation_material) = py
        .allow_threads(move || {
            let material = orientations(orientation_seed, orientation_count)?;
            let result = search_short_range(&input, &search_config, short_range_config)?;
            Ok::<_, SearchError>((result, material))
        })
        .map_err(search_error)?;
    result_to_python(py, &result, &orientation_material)
}

fn bounded_len(value: &PyAny, name: &str, minimum: usize, maximum: usize) -> PyResult<usize> {
    let length = value
        .len()
        .map_err(|_| PyValueError::new_err(format!("{name} must be a bounded sequence")))?;
    if !(minimum..=maximum).contains(&length) {
        return Err(PyValueError::new_err(format!(
            "{name} length must be in [{minimum},{maximum}]"
        )));
    }
    Ok(length)
}

fn rows3_any(
    value: &PyAny,
    name: &str,
    minimum_rows: usize,
    maximum_rows: usize,
) -> PyResult<Vec<Vec3>> {
    if let Ok(array) = value.extract::<PyReadonlyArray2<'_, f64>>() {
        let view = array.as_array();
        if view.ncols() != 3 || !(minimum_rows..=maximum_rows).contains(&view.nrows()) {
            return Err(PyValueError::new_err(format!(
                "{name} must have bounded shape [N,3]"
            )));
        }
        let rows: Vec<_> = view
            .outer_iter()
            .map(|row| Vec3::new(row[0], row[1], row[2]))
            .collect();
        require_finite_vec3(&rows, name)?;
        return Ok(rows);
    }
    let row_count = bounded_len(value, name, minimum_rows, maximum_rows)?;
    let mut rows = Vec::with_capacity(row_count);
    for row_index in 0..row_count {
        let row = value.get_item(row_index).map_err(|_| {
            PyValueError::new_err(format!(
                "{name} must be a float64 array or numeric sequence"
            ))
        })?;
        if row.len().ok() != Some(3) {
            return Err(PyValueError::new_err(format!(
                "{name} must have bounded shape [N,3]"
            )));
        }
        let component = |axis: usize| -> PyResult<f64> {
            row.get_item(axis)
                .and_then(PyAny::extract::<f64>)
                .map_err(|_| {
                    PyValueError::new_err(format!(
                        "{name}[{row_index}][{axis}] must be a numeric scalar"
                    ))
                })
        };
        rows.push(Vec3::new(component(0)?, component(1)?, component(2)?));
    }
    require_finite_vec3(&rows, name)?;
    Ok(rows)
}

fn f64_values_any(value: &PyAny, name: &str, length: usize) -> PyResult<Vec<f64>> {
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, f64>>() {
        let view = array.as_array();
        if view.len() != length {
            return Err(PyValueError::new_err(format!("{name} length mismatch")));
        }
        let values: Vec<_> = view.iter().copied().collect();
        require_finite_f64(&values, name)?;
        return Ok(values);
    }
    if bounded_len(value, name, length, length)? != length {
        unreachable!("bounded exact length");
    }
    let values: Vec<f64> = value.extract().map_err(|_| {
        PyValueError::new_err(format!(
            "{name} must be a float64 array or numeric sequence"
        ))
    })?;
    require_finite_f64(&values, name)?;
    Ok(values)
}

fn integer_values_any(value: &PyAny, name: &str, length: usize) -> PyResult<Vec<i64>> {
    if bounded_len(value, name, length, length)? != length {
        unreachable!("bounded exact length");
    }
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, i64>>() {
        return Ok(array.as_array().iter().copied().collect());
    }
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, i32>>() {
        return Ok(array
            .as_array()
            .iter()
            .map(|value| i64::from(*value))
            .collect());
    }
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, u32>>() {
        return Ok(array
            .as_array()
            .iter()
            .map(|value| i64::from(*value))
            .collect());
    }
    value
        .extract::<Vec<i64>>()
        .map_err(|_| PyValueError::new_err(format!("{name} must be an integer array or sequence")))
}

fn require_finite_vec3(values: &[Vec3], name: &str) -> PyResult<()> {
    if values.iter().any(|value| !value.is_finite()) {
        Err(PyValueError::new_err(format!("{name} must be finite")))
    } else {
        Ok(())
    }
}

fn require_finite_f64(values: &[f64], name: &str) -> PyResult<()> {
    if values.iter().any(|value| !value.is_finite()) {
        Err(PyValueError::new_err(format!("{name} must be finite")))
    } else {
        Ok(())
    }
}

fn decode_seed(value: &str) -> PyResult<[u8; 32]> {
    if value.len() != 64
        || value
            .bytes()
            .any(|byte| !byte.is_ascii_digit() && !(b'a'..=b'f').contains(&byte))
    {
        return Err(PyValueError::new_err(
            "source_seed_hex must be lowercase 64-hex",
        ));
    }
    let mut output = [0u8; 32];
    for (index, byte) in output.iter_mut().enumerate() {
        let offset = index * 2;
        *byte =
            (hex_nibble(value.as_bytes()[offset]) << 4) | hex_nibble(value.as_bytes()[offset + 1]);
    }
    Ok(output)
}

fn hex_nibble(value: u8) -> u8 {
    match value {
        b'0'..=b'9' => value - b'0',
        b'a'..=b'f' => value - b'a' + 10,
        _ => unreachable!("seed was validated"),
    }
}

fn to_u32(value: i64, name: &str) -> PyResult<u32> {
    u32::try_from(value)
        .map_err(|_| PyValueError::new_err(format!("{name} must contain uint32 values")))
}

fn to_index(value: i64, bound: usize, name: &str) -> PyResult<usize> {
    let index = usize::try_from(value)
        .map_err(|_| PyValueError::new_err(format!("{name} contains a negative index")))?;
    if index >= bound {
        Err(PyValueError::new_err(format!(
            "{name} contains an out-of-range index"
        )))
    } else {
        Ok(index)
    }
}

fn anchor_kind(value: i64, name: &str) -> PyResult<AnchorKind> {
    match value {
        0 => Ok(AnchorKind::HydrogenBondDonor),
        1 => Ok(AnchorKind::HydrogenBondAcceptor),
        2 => Ok(AnchorKind::Hydrophobe),
        3 => Ok(AnchorKind::Aromatic),
        4 => Ok(AnchorKind::Positive),
        5 => Ok(AnchorKind::Negative),
        _ => Err(PyValueError::new_err(format!(
            "{name} must contain only codes in [0,5]"
        ))),
    }
}

fn validate_composite_preflight(input: &SearchInput, config: &SearchConfig) -> PyResult<()> {
    let ligand_count = input.ligand_atoms.len();
    let receptor_count = input.receptor_atoms.len();
    let (_, combination_count) = exact_anchor_combination_count(input, config)?;
    let possible_upper = checked_product(&[config.orientation_count, combination_count])?;
    let allocated_upper = config.generated_candidate_limit.min(possible_upper);
    let candidate_coordinates = checked_product(&[allocated_upper, ligand_count])?;
    if candidate_coordinates > MAX_CANDIDATE_COORDINATES {
        return Err(composite_error(
            "candidate coordinates exceed the composite hard cap",
        ));
    }
    let coarse_count = config.coarse_keep.min(allocated_upper);
    let refinement_count = config.refinement_keep.min(coarse_count);
    let coordinate_bytes = checked_product(&[candidate_coordinates, size_of::<Vec3>()])?;
    let row_metadata_bytes = checked_product(&[allocated_upper, 256])?;
    let maximum_detail_bytes = checked_product(&[refinement_count, MAX_EVALUATION_DETAIL_BYTES])?;
    let maximum_pose_bytes = checked_product(&[
        config.top_k.min(refinement_count),
        ligand_count,
        size_of::<Vec3>(),
    ])?;
    let ledger_payload_bytes = coordinate_bytes
        .checked_add(row_metadata_bytes)
        .and_then(|value| value.checked_add(maximum_detail_bytes))
        .and_then(|value| value.checked_add(maximum_pose_bytes))
        .ok_or_else(|| composite_error("composite ledger byte calculation overflowed"))?;
    if ledger_payload_bytes > MAX_LEDGER_PAYLOAD_BYTES {
        return Err(composite_error(
            "candidate ledger exceeds the composite byte cap",
        ));
    }
    let pose_count_upper = config.top_k.min(refinement_count);
    let python_coordinate_rows = candidate_coordinates
        .checked_add(checked_product(&[pose_count_upper, ligand_count])?)
        .ok_or_else(|| composite_error("Python bridge coordinate calculation overflowed"))?;
    let python_coordinate_bytes =
        checked_product(&[python_coordinate_rows, PYTHON_BRIDGE_COORDINATE_ROW_BYTES])?;
    let python_candidate_bytes =
        checked_product(&[allocated_upper, PYTHON_BRIDGE_CANDIDATE_ROW_BYTES])?;
    let python_pose_bytes = checked_product(&[pose_count_upper, PYTHON_BRIDGE_POSE_BYTES])?;
    let python_orientation_bytes = checked_product(&[
        config.orientation_count,
        PYTHON_BRIDGE_ORIENTATION_ROW_BYTES,
    ])?;
    let python_bridge_bytes = python_coordinate_bytes
        .checked_add(python_candidate_bytes)
        .and_then(|value| value.checked_add(python_pose_bytes))
        .and_then(|value| value.checked_add(python_orientation_bytes))
        .ok_or_else(|| composite_error("Python bridge byte calculation overflowed"))?;
    if python_bridge_bytes > MAX_PYTHON_BRIDGE_BYTES {
        return Err(composite_error(
            "Python bridge output exceeds the composite byte cap",
        ));
    }
    let ligand_receptor_pairs = checked_product(&[ligand_count, receptor_count])?;
    let ligand_shape_pairs = checked_product(&[ligand_count, ligand_count.saturating_sub(1)])? / 2;
    let evaluator_pairs_per_call = ligand_receptor_pairs
        .checked_add(ligand_shape_pairs)
        .ok_or_else(|| composite_error("composite pair calculation overflowed"))?;
    let evaluator_calls =
        checked_product(&[refinement_count, config.refinement_steps.saturating_add(1)])?;
    let work_rows = [
        candidate_coordinates,
        checked_product(&[allocated_upper, receptor_count])?,
        checked_product(&[coarse_count, ligand_receptor_pairs])?,
        checked_product(&[refinement_count, ligand_receptor_pairs])?,
        checked_product(&[refinement_count, ligand_shape_pairs])?,
        checked_product(&[evaluator_calls, evaluator_pairs_per_call])?,
    ];
    let pair_evaluations = work_rows.into_iter().try_fold(0usize, |total, value| {
        total
            .checked_add(value)
            .ok_or_else(|| composite_error("composite pair calculation overflowed"))
    })?;
    if pair_evaluations > MAX_PAIR_EVALUATIONS {
        return Err(composite_error(
            "search work exceeds the composite pair-evaluation cap",
        ));
    }
    Ok(())
}

fn exact_anchor_combination_count(
    input: &SearchInput,
    config: &SearchConfig,
) -> PyResult<(usize, usize)> {
    let mut singles = Vec::new();
    for (surface_index, surface) in input.surface_samples.iter().enumerate() {
        for (ligand_index, ligand) in input.ligand_anchors.iter().enumerate() {
            if ligand.kind.is_compatible_with(surface.anchor_kind) {
                singles.push((ligand_index, surface_index));
                if singles.len() > MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS {
                    return Err(composite_error(
                        "compatible single-anchor pairs exceed the composite hard cap",
                    ));
                }
            }
        }
    }
    let compatible_single_count = singles.len();
    let mut dual_count = 0usize;
    for (left_index, &(left_ligand, left_surface)) in singles.iter().enumerate() {
        for &(right_ligand, right_surface) in &singles[left_index + 1..] {
            if left_ligand == right_ligand || left_surface == right_surface {
                continue;
            }
            let left_anchor = input.ligand_anchors[left_ligand];
            let right_anchor = input.ligand_anchors[right_ligand];
            let source_distance = input.ligand_atoms[left_anchor.atom_index]
                .position_angstrom
                .minus(input.ligand_atoms[right_anchor.atom_index].position_angstrom)
                .norm();
            let left_target = bridge_surface_target(input, config, left_surface);
            let right_target = bridge_surface_target(input, config, right_surface);
            let target_distance = left_target.minus(right_target).norm();
            if source_distance <= 1.0e-12
                || target_distance <= 1.0e-12
                || (source_distance - target_distance).abs()
                    > config.dual_anchor_distance_tolerance_angstrom
            {
                continue;
            }
            dual_count = dual_count
                .checked_add(1)
                .ok_or_else(|| composite_error("dual-anchor count overflowed"))?;
            if dual_count > MAX_ANCHOR_COMBINATIONS {
                return Err(composite_error(
                    "compatible dual-anchor combinations exceed the composite hard cap",
                ));
            }
        }
    }
    Ok((
        compatible_single_count,
        if dual_count == 0 {
            compatible_single_count
        } else {
            dual_count
        },
    ))
}

fn bridge_surface_target(input: &SearchInput, config: &SearchConfig, surface_index: usize) -> Vec3 {
    let surface = input.surface_samples[surface_index];
    let normal_length = surface.outward_normal.norm();
    if !normal_length.is_finite() || normal_length <= 1.0e-12 {
        return surface.position_angstrom;
    }
    surface.position_angstrom.plus(
        surface
            .outward_normal
            .scale(config.placement_clearance_angstrom / normal_length),
    )
}

fn checked_product(values: &[usize]) -> PyResult<usize> {
    values.iter().try_fold(1usize, |product, value| {
        product
            .checked_mul(*value)
            .ok_or_else(|| composite_error("composite work calculation overflowed"))
    })
}

fn composite_error(detail: &str) -> PyErr {
    PyValueError::new_err(format!("docking_search_v2_composite_work_limit: {detail}"))
}

fn require_exact_keys(dict: &PyDict, expected: &[&str], name: &str) -> PyResult<()> {
    let mut observed = BTreeSet::new();
    for (key, _) in dict.iter() {
        let text = key
            .extract::<&str>()
            .map_err(|_| PyValueError::new_err(format!("{name} keys must be canonical strings")))?;
        observed.insert(text.to_owned());
    }
    let expected: BTreeSet<_> = expected.iter().map(|value| (*value).to_owned()).collect();
    if observed != expected {
        return Err(PyValueError::new_err(format!(
            "{name} has an invalid key schema"
        )));
    }
    Ok(())
}

fn dict_value<'py>(dict: &'py PyDict, key: &str) -> PyResult<&'py PyAny> {
    dict.get_item(key)?
        .ok_or_else(|| PyValueError::new_err(format!("configuration field {key} is missing")))
}

fn dict_usize(dict: &PyDict, key: &str) -> PyResult<usize> {
    let value = dict_value(dict, key)?;
    if value.is_instance_of::<PyBool>() {
        return Err(PyValueError::new_err(format!("{key} must be an integer")));
    }
    value
        .extract::<usize>()
        .map_err(|_| PyValueError::new_err(format!("{key} must be an integer")))
}

fn dict_f64(dict: &PyDict, key: &str) -> PyResult<f64> {
    let value = dict_value(dict, key)?;
    if value.is_instance_of::<PyBool>() {
        return Err(PyValueError::new_err(format!("{key} must be numeric")));
    }
    let output = value
        .extract::<f64>()
        .map_err(|_| PyValueError::new_err(format!("{key} must be numeric")))?;
    if !output.is_finite() {
        return Err(PyValueError::new_err(format!("{key} must be finite")));
    }
    Ok(output)
}

fn parse_search_config(dict: &PyDict) -> PyResult<SearchConfig> {
    require_exact_keys(dict, &SEARCH_CONFIG_KEYS, "search_config")?;
    Ok(SearchConfig {
        orientation_count: dict_usize(dict, "orientation_count")?,
        generated_candidate_limit: dict_usize(dict, "generated_candidate_limit")?,
        coarse_keep: dict_usize(dict, "coarse_keep")?,
        refinement_keep: dict_usize(dict, "refinement_keep")?,
        top_k: dict_usize(dict, "top_k")?,
        placement_clearance_angstrom: dict_f64(dict, "placement_clearance_angstrom")?,
        dual_anchor_distance_tolerance_angstrom: dict_f64(
            dict,
            "dual_anchor_distance_tolerance_angstrom",
        )?,
        coarse_clash_weight: dict_f64(dict, "coarse_clash_weight")?,
        refinement_steps: dict_usize(dict, "refinement_steps")?,
        translation_step_angstrom2_per_kcal: dict_f64(dict, "translation_step_angstrom2_per_kcal")?,
        rotation_step_per_torque: dict_f64(dict, "rotation_step_per_torque")?,
        maximum_translation_step_angstrom: dict_f64(dict, "maximum_translation_step_angstrom")?,
        maximum_rotation_step_radians: dict_f64(dict, "maximum_rotation_step_radians")?,
        maximum_absolute_coordinate_angstrom: dict_f64(
            dict,
            "maximum_absolute_coordinate_angstrom",
        )?,
        minimum_ligand_atom_distance_angstrom: dict_f64(
            dict,
            "minimum_ligand_atom_distance_angstrom",
        )?,
        minimum_receptor_clearance_scale: dict_f64(dict, "minimum_receptor_clearance_scale")?,
        cluster_rmsd_angstrom: dict_f64(dict, "cluster_rmsd_angstrom")?,
    })
}

fn parse_short_range_config(dict: &PyDict) -> PyResult<ShortRangeConfig> {
    require_exact_keys(dict, &SHORT_RANGE_CONFIG_KEYS, "short_range_config")?;
    Ok(ShortRangeConfig {
        ligand_shape_force_constant_kcal_per_mol_angstrom2: dict_f64(
            dict,
            "ligand_shape_force_constant_kcal_per_mol_angstrom2",
        )?,
        cutoff_angstrom: dict_f64(dict, "cutoff_angstrom")?,
        switch_start_angstrom: dict_f64(dict, "switch_start_angstrom")?,
        softcore_angstrom: dict_f64(dict, "softcore_angstrom")?,
        dielectric: dict_f64(dict, "dielectric")?,
    })
}

fn search_error(error: SearchError) -> PyErr {
    let code = match error.code() {
        SearchErrorCode::EmptyLigand => "empty_ligand",
        SearchErrorCode::EmptySurface => "empty_surface",
        SearchErrorCode::MissingLigandAnchor => "missing_ligand_anchor",
        SearchErrorCode::TooManyItems => "too_many_items",
        SearchErrorCode::InvalidConfiguration => "invalid_configuration",
        SearchErrorCode::NonFiniteInput => "non_finite_input",
        SearchErrorCode::InvalidRadius => "invalid_radius",
        SearchErrorCode::InvalidAtomParameter => "invalid_atom_parameter",
        SearchErrorCode::InvalidDirection => "invalid_direction",
        SearchErrorCode::AtomIndexOutOfRange => "atom_index_out_of_range",
        SearchErrorCode::DuplicateIdentifier => "duplicate_identifier",
        SearchErrorCode::NoCompatibleAnchors => "no_compatible_anchors",
        SearchErrorCode::AllocationOverflow => "allocation_overflow",
        SearchErrorCode::CompositeWorkLimit => "composite_work_limit",
        SearchErrorCode::Evaluator => "evaluator",
        SearchErrorCode::NonFiniteEvaluation => "non_finite_evaluation",
        SearchErrorCode::InternalInvariant => "internal_invariant",
        _ => "unclassified",
    };
    PyValueError::new_err(format!("docking_search_v2_{code}: {}", error.detail()))
}

fn result_to_python(
    py: Python<'_>,
    result: &SearchResult,
    orientation_material: &[Orientation],
) -> PyResult<PyObject> {
    if !result.has_valid_sha256() {
        return Err(PyValueError::new_err(
            "docking_search_v2_internal_invariant: receipt SHA-256 is invalid",
        ));
    }
    let output = PyDict::new(py);
    output.set_item("schema_id", SEARCH_SCHEMA_ID)?;
    let orientation_rows = PyList::empty(py);
    for orientation in orientation_material {
        let row = PyDict::new(py);
        row.set_item("orientation_index", orientation.orientation_index)?;
        row.set_item("raw_sequence_index", orientation.raw_sequence_index)?;
        row.set_item(
            "quaternion",
            PyList::new(
                py,
                [
                    orientation.quaternion.x,
                    orientation.quaternion.y,
                    orientation.quaternion.z,
                    orientation.quaternion.w,
                ],
            ),
        )?;
        orientation_rows.append(row)?;
    }
    output.set_item("orientation_material", orientation_rows)?;
    let rows = PyList::empty(py);
    for row in &result.candidate_rows {
        rows.append(candidate_row_to_python(py, row)?)?;
    }
    output.set_item("candidate_rows", rows)?;
    let poses = PyList::empty(py);
    for pose in &result.poses {
        let value = PyDict::new(py);
        value.set_item("rank", pose.rank)?;
        value.set_item("key", key_to_python(py, pose.key)?)?;
        value.set_item(
            "coordinates_angstrom",
            coordinates_to_python(py, &pose.coordinates_angstrom)?,
        )?;
        value.set_item("energy_kcal_per_mol", pose.energy_kcal_per_mol)?;
        value.set_item("cluster_size", pose.cluster_size)?;
        value.set_item(
            "minimum_receptor_gap_angstrom",
            pose.minimum_receptor_gap_angstrom,
        )?;
        poses.append(value)?;
    }
    output.set_item("poses", poses)?;
    output.set_item("receipt", receipt_to_python(py, &result.receipt)?)?;
    Ok(output.into())
}

fn candidate_row_to_python(
    py: Python<'_>,
    row: &betelgeuze_docking_search::CandidateRow,
) -> PyResult<PyObject> {
    let value = PyDict::new(py);
    value.set_item("slot_index", row.slot_index)?;
    value.set_item("key", key_to_python(py, row.key)?)?;
    value.set_item("placement_mode", placement_mode(row.placement_mode))?;
    value.set_item("status", candidate_status(row.status))?;
    value.set_item("reason", row.reason.map(candidate_reason))?;
    value.set_item("detail", row.detail.as_deref())?;
    value.set_item(
        "coordinates_angstrom",
        coordinates_to_python(py, &row.coordinates_angstrom)?,
    )?;
    value.set_item("anchor_fit_rmsd_angstrom", row.anchor_fit_rmsd_angstrom)?;
    value.set_item("coarse_score", row.coarse_score)?;
    value.set_item("detailed_score", row.detailed_score)?;
    value.set_item("energy_kcal_per_mol", row.energy_kcal_per_mol)?;
    value.set_item("physically_valid", row.physically_valid)?;
    value.set_item(
        "minimum_receptor_gap_angstrom",
        row.minimum_receptor_gap_angstrom,
    )?;
    value.set_item("cluster_id", row.cluster_id)?;
    value.set_item("final_rank", row.final_rank)?;
    Ok(value.into())
}

fn key_to_python(py: Python<'_>, key: CandidateKey) -> PyResult<PyObject> {
    let value = PyDict::new(py);
    value.set_item("orientation_index", key.orientation_index)?;
    value.set_item("primary_surface_id", key.primary_surface_id.0)?;
    value.set_item("primary_ligand_anchor_id", key.primary_ligand_anchor_id.0)?;
    value.set_item(
        "secondary_surface_id",
        key.secondary_surface_id.map(|id| id.0),
    )?;
    value.set_item(
        "secondary_ligand_anchor_id",
        key.secondary_ligand_anchor_id.map(|id| id.0),
    )?;
    Ok(value.into())
}

fn receipt_to_python(
    py: Python<'_>,
    receipt: &betelgeuze_docking_search::SearchReceipt,
) -> PyResult<PyObject> {
    let value = PyDict::new(py);
    value.set_item("schema_id", receipt.schema_id)?;
    value.set_item("evaluator_id", receipt.evaluator_id)?;
    value.set_item(
        "evaluator_config_sha256",
        hex_sha256(receipt.evaluator_config_sha256),
    )?;
    value.set_item("config_sha256", hex_sha256(receipt.config_sha256))?;
    value.set_item("input_sha256", hex_sha256(receipt.input_sha256))?;
    value.set_item(
        "result_independent_allocation",
        receipt.result_independent_allocation,
    )?;
    value.set_item("placement_mode", placement_mode(receipt.placement_mode))?;
    value.set_item(
        "requested_orientation_count",
        receipt.requested_orientation_count,
    )?;
    value.set_item(
        "accepted_orientation_count",
        receipt.accepted_orientation_count,
    )?;
    value.set_item(
        "raw_orientation_attempt_count",
        receipt.raw_orientation_attempt_count,
    )?;
    value.set_item(
        "compatible_single_anchor_pair_count",
        receipt.compatible_single_anchor_pair_count,
    )?;
    value.set_item(
        "compatible_dual_anchor_combination_count",
        receipt.compatible_dual_anchor_combination_count,
    )?;
    value.set_item(
        "used_anchor_combination_count",
        receipt.used_anchor_combination_count,
    )?;
    value.set_item(
        "possible_candidate_slot_count",
        receipt.possible_candidate_slot_count,
    )?;
    value.set_item(
        "generated_candidate_limit",
        receipt.generated_candidate_limit,
    )?;
    value.set_item(
        "allocated_candidate_slot_count",
        receipt.allocated_candidate_slot_count,
    )?;
    value.set_item("allocation_sha256", hex_sha256(receipt.allocation_sha256))?;
    value.set_item("orientation_sha256", hex_sha256(receipt.orientation_sha256))?;
    value.set_item(
        "candidate_rows_sha256",
        hex_sha256(receipt.candidate_rows_sha256),
    )?;
    value.set_item("poses_sha256", hex_sha256(receipt.poses_sha256))?;
    value.set_item("coarse_keep_budget", receipt.coarse_keep_budget)?;
    value.set_item("coarse_kept_count", receipt.coarse_kept_count)?;
    value.set_item("refinement_keep_budget", receipt.refinement_keep_budget)?;
    value.set_item(
        "refinement_selected_count",
        receipt.refinement_selected_count,
    )?;
    value.set_item(
        "refinement_steps_per_candidate",
        receipt.refinement_steps_per_candidate,
    )?;
    value.set_item(
        "refinement_succeeded_count",
        receipt.refinement_succeeded_count,
    )?;
    value.set_item(
        "refinement_evaluator_failed_count",
        receipt.refinement_evaluator_failed_count,
    )?;
    value.set_item(
        "refinement_non_finite_failed_count",
        receipt.refinement_non_finite_failed_count,
    )?;
    value.set_item("evaluator_call_count", receipt.evaluator_call_count)?;
    value.set_item(
        "maximum_evaluator_call_count",
        receipt.maximum_evaluator_call_count,
    )?;
    value.set_item("physical_valid_count", receipt.physical_valid_count)?;
    value.set_item(
        "rejected_non_finite_coordinate_count",
        receipt.rejected_non_finite_coordinate_count,
    )?;
    value.set_item(
        "rejected_coordinate_out_of_bounds_count",
        receipt.rejected_coordinate_out_of_bounds_count,
    )?;
    value.set_item(
        "rejected_ligand_self_overlap_count",
        receipt.rejected_ligand_self_overlap_count,
    )?;
    value.set_item(
        "rejected_receptor_clash_count",
        receipt.rejected_receptor_clash_count,
    )?;
    value.set_item("cluster_count", receipt.cluster_count)?;
    value.set_item("top_k_budget", receipt.top_k_budget)?;
    value.set_item("returned_pose_count", receipt.returned_pose_count)?;
    value.set_item("receipt_sha256", hex_sha256(receipt.receipt_sha256))?;
    Ok(value.into())
}

fn coordinates_to_python(py: Python<'_>, values: &[Vec3]) -> PyResult<PyObject> {
    let coordinate_count = values
        .len()
        .checked_mul(3)
        .ok_or_else(|| composite_error("coordinate array shape overflowed"))?;
    let mut packed = Vec::with_capacity(coordinate_count);
    for value in values {
        packed.extend_from_slice(&[value.x, value.y, value.z]);
    }
    let array = Array2::from_shape_vec((values.len(), 3), packed).map_err(|_| {
        PyValueError::new_err(
            "docking_search_v2_internal_invariant: packed coordinate shape is invalid",
        )
    })?;
    Ok(PyArray2::from_owned_array(py, array).into_py(py))
}

fn placement_mode(value: PlacementMode) -> &'static str {
    match value {
        PlacementMode::DualAnchor => "dual_anchor",
        PlacementMode::SingleAnchorFallback => "single_anchor_fallback",
    }
}

fn candidate_status(value: CandidateStatus) -> &'static str {
    match value {
        CandidateStatus::CoarsePruned => "coarse_pruned",
        CandidateStatus::DetailedPruned => "detailed_pruned",
        CandidateStatus::RefinementFailed => "refinement_failed",
        CandidateStatus::PhysicalRejected => "physical_rejected",
        CandidateStatus::ClusterMember => "cluster_member",
        CandidateStatus::ClusterRepresentative => "cluster_representative",
        CandidateStatus::TopK => "top_k",
    }
}

fn candidate_reason(value: CandidateReason) -> &'static str {
    match value {
        CandidateReason::CoarseBudget => "coarse_budget",
        CandidateReason::DetailedBudget => "detailed_budget",
        CandidateReason::EvaluatorFailure => "evaluator_failure",
        CandidateReason::NonFiniteEvaluation => "non_finite_evaluation",
        CandidateReason::NonFiniteCoordinate => "non_finite_coordinate",
        CandidateReason::CoordinateOutOfBounds => "coordinate_out_of_bounds",
        CandidateReason::LigandSelfOverlap => "ligand_self_overlap",
        CandidateReason::ReceptorClash => "receptor_clash",
        CandidateReason::ClusteredIntoRepresentative => "clustered_into_representative",
        CandidateReason::TopKBudget => "top_k_budget",
    }
}

fn hex_sha256(value: [u8; 32]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(64);
    for byte in value {
        output.push(char::from(HEX[usize::from(byte >> 4)]));
        output.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bridge_budget_input(ligand_count: usize, surface_count: usize) -> SearchInput {
        SearchInput {
            source_seed: [0x42; 32],
            ligand_atoms: (0..ligand_count)
                .map(|index| LigandAtom {
                    position_angstrom: Vec3::new(index as f64 * 0.1, 0.0, 0.0),
                    vdw_radius_angstrom: 0.5,
                    epsilon_kcal_per_mol: 0.2,
                    charge_elementary: 0.0,
                })
                .collect(),
            ligand_anchors: vec![LigandAnchor {
                id: AnchorId(7),
                atom_index: 0,
                direction: Vec3::new(1.0, 0.0, 0.0),
                kind: AnchorKind::HydrogenBondDonor,
            }],
            receptor_atoms: Vec::new(),
            surface_samples: (0..surface_count)
                .map(|index| SurfaceSample {
                    id: SurfaceId(u32::try_from(index).expect("bounded fixture index")),
                    position_angstrom: Vec3::new(10_000.0 + index as f64 * 10.0, 0.0, 0.0),
                    outward_normal: Vec3::new(1.0, 0.0, 0.0),
                    anchor_kind: AnchorKind::HydrogenBondAcceptor,
                })
                .collect(),
        }
    }

    #[test]
    fn seed_contract_is_exact_and_lowercase() {
        assert_eq!(decode_seed(&"ab".repeat(32)).unwrap(), [0xab; 32]);
        assert!(decode_seed(&"AB".repeat(32)).is_err());
        assert!(decode_seed("00").is_err());
    }

    #[test]
    fn enum_rows_are_stable_public_strings() {
        assert_eq!(placement_mode(PlacementMode::DualAnchor), "dual_anchor");
        assert_eq!(candidate_status(CandidateStatus::TopK), "top_k");
        assert_eq!(
            candidate_reason(CandidateReason::EvaluatorFailure),
            "evaluator_failure"
        );
    }

    #[test]
    fn generic_rows_validate_each_row_shape_before_extracting_components() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let wide_row = PyList::new(py, [1.0, 2.0, 3.0, 4.0]);
            let rows = PyList::new(py, [wide_row]);
            let error = rows3_any(rows, "coordinates", 1, 1).unwrap_err();
            assert!(error.to_string().contains("bounded shape [N,3]"));
        });
    }

    #[test]
    fn result_coordinates_are_packed_float64_numpy_arrays() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let output =
                coordinates_to_python(py, &[Vec3::new(1.0, 2.0, 3.0), Vec3::new(4.0, 5.0, 6.0)])
                    .unwrap();
            let array = output
                .as_ref(py)
                .extract::<PyReadonlyArray2<'_, f64>>()
                .unwrap();
            let view = array.as_array();
            assert_eq!(view.shape(), &[2, 3]);
            assert_eq!(view[[1, 2]], 6.0);
        });
    }

    // The shipped artifact identity fixes release/opt-level=3.  LLVM's debug
    // lowering of platform trig is not the product ABI and has different ULPs.
    #[cfg(not(debug_assertions))]
    #[test]
    fn public_5sis_orientation_material_has_frozen_native_identity() {
        let seed = decode_seed("5b5c5f696e68d7d3794897d7829958e3adab3e5faab386418a01496009543edd")
            .unwrap();
        let material = orientations(seed, 64).unwrap();
        let mut input = bridge_budget_input(1, 1);
        input.source_seed = seed;
        let config = SearchConfig {
            orientation_count: 64,
            generated_candidate_limit: 64,
            coarse_keep: 64,
            refinement_keep: 64,
            top_k: 1,
            refinement_steps: 0,
            ..SearchConfig::default()
        };
        let result = search_short_range(&input, &config, ShortRangeConfig::default()).unwrap();
        assert_eq!(
            hex_sha256(result.receipt.orientation_sha256),
            "006ee393989d4c99fed886492e640cd1c58c1e37f525c2cb61f52bbd64108e02"
        );

        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let output = result_to_python(py, &result, &material).unwrap();
            let output = output.as_ref(py).downcast::<PyDict>().unwrap();
            assert_eq!(output.len(), 5);
            let rows = output
                .get_item("orientation_material")
                .unwrap()
                .unwrap()
                .downcast::<PyList>()
                .unwrap();
            assert_eq!(rows.len(), 64);
            let last = rows.get_item(63).unwrap().downcast::<PyDict>().unwrap();
            assert_eq!(last.len(), 3);
            assert_eq!(
                last.get_item("orientation_index")
                    .unwrap()
                    .unwrap()
                    .extract::<u32>()
                    .unwrap(),
                63
            );
            assert_eq!(
                last.get_item("quaternion")
                    .unwrap()
                    .unwrap()
                    .downcast::<PyList>()
                    .unwrap()
                    .len(),
                4
            );
        });
    }

    #[test]
    fn exact_fallback_count_avoids_false_composite_rejection() {
        let input = bridge_budget_input(512, 129);
        let config = SearchConfig {
            orientation_count: 1,
            generated_candidate_limit: 8_192,
            coarse_keep: 1,
            refinement_keep: 1,
            top_k: 1,
            refinement_steps: 0,
            ..SearchConfig::default()
        };
        assert_eq!(
            exact_anchor_combination_count(&input, &config).unwrap(),
            (129, 129)
        );
        validate_composite_preflight(&input, &config).unwrap();
    }

    #[test]
    fn expanded_python_output_has_an_independent_hard_cap() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|_| {
            let input = bridge_budget_input(512, 1);
            let config = SearchConfig {
                orientation_count: 512,
                generated_candidate_limit: 512,
                coarse_keep: 512,
                refinement_keep: 512,
                top_k: 512,
                refinement_steps: 0,
                ..SearchConfig::default()
            };
            let error = validate_composite_preflight(&input, &config).unwrap_err();
            assert!(error.to_string().contains("Python bridge output"));
        });
    }
}
