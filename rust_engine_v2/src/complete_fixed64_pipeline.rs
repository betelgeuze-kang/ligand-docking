//! PyO3 boundary for the versioned native C++/Rust/HIP fixed64 pipeline.
//!
//! Python performs schema transport only. Proposal generation, geometric
//! admission, refinement, ScorerV1, pose validity, stable ranking, and RMSD
//! clustering all execute through the one safe Rust owner of the C ABI.

use std::collections::BTreeSet;

use betelgeuze_docking_search::{
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, Vec3,
};
use betelgeuze_runtime::{
    Backend, Context, ContextOptions, Fixed64AtomicFeature, Fixed64ChiralityCenter,
    Fixed64ConformerCoordinateSource, Fixed64CoordinateSource, Fixed64Donor,
    Fixed64ExactSourceEvidence, Fixed64FeatureGeometry, Fixed64FeatureKind, Fixed64Identities,
    Fixed64IndexedCoordinateSource, Fixed64Ligand, Fixed64Pair, Fixed64Pipeline,
    Fixed64PipelineContext, Fixed64PipelineReceipt, Fixed64Receptor, Fixed64RefinementMode,
    Fixed64Rotor, Fixed64RunInput, Fixed64SourceEvidence, PositionSoa, PositionSoaOwned,
};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyList};
use sha2::{Digest, Sha256};

use crate::fixed64_pipeline::{
    bool_values, decode_digest, dict_digest, dict_exact_bool, dict_f64, dict_string, dict_u32,
    dict_value, f64_values, hex_digest, index_rows, input_error, require_exact_keys, rows3,
    vec3_value,
};

pub(crate) const INPUT_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_fixed64_complete_input/1.0.0";
pub(crate) const EVIDENCE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/1.0.0";

const INPUT_KEYS: &[&str] = &[
    "schema_id",
    "consumer",
    "backend",
    "device_ordinal",
    "authority_input_receipt_sha256",
    "source_receipt_sha256",
    "proposal_sha256",
    "prepared_ligand_topology_sha256",
    "prepared_receptor_topology_sha256",
    "receptor_system_sha256",
    "ligand_system_sha256",
    "backend_receipt_sha256",
    "validity_scorer_context_receipt_sha256",
    "contact_policy_sha256",
    "ligand_coordinates_angstrom",
    "ligand_vdw_radii_angstrom",
    "ligand_heavy_atom_mask",
    "ligand_charge_elementary",
    "ligand_epsilon_kcal_per_mol",
    "ligand_hydrophobic_mask",
    "ligand_acceptor_mask",
    "receptor_coordinates_angstrom",
    "receptor_vdw_radii_angstrom",
    "receptor_charge_elementary",
    "receptor_epsilon_kcal_per_mol",
    "receptor_hydrophobic_mask",
    "receptor_acceptor_mask",
    "ligand_donors",
    "receptor_donors",
    "ligand_exclusions",
    "rotor_quads",
    "bond_pairs",
    "chirality_centers",
    "parent_atom_index",
    "rotatable_child_atom_index",
    "internal_pairs",
    "pocket_center_angstrom",
    "pocket_radius_angstrom",
    "pocket_normal",
    "v7_control_sources",
    "conformer_sources",
    "retained_sources",
    "feature_geometries",
    "feature_geometry_inventory_sha256",
    "rmsd_threshold_angstrom",
    "candidate_modes",
    "rigid_max_steps",
    "proposal_is_torsion_eligible",
    "torsion_max_steps",
    "baseline_torsion_angles_radians",
    "predeclared_refinement_policy_sha256",
    "test_only",
];

const INDEXED_SOURCE_KEYS: &[&str] = &[
    "source_index",
    "receipt_sha256",
    "proposal_sha256",
    "coordinates_angstrom",
];
const CONFORMER_SOURCE_KEYS: &[&str] = &[
    "rank",
    "receipt_sha256",
    "proposal_sha256",
    "coordinates_angstrom",
];
const FEATURE_GEOMETRY_KEYS: &[&str] = &[
    "kind",
    "allocation_feature_receipt_sha256",
    "feature_geometry_receipt_sha256",
    "atom_indices",
];

#[derive(Clone, Copy)]
enum Consumer {
    Cli,
    Benchmark,
    Api,
    ProductShadow,
}

impl Consumer {
    fn parse(value: &str) -> PyResult<Self> {
        match value {
            "cli" => Ok(Self::Cli),
            "benchmark" => Ok(Self::Benchmark),
            "api" => Ok(Self::Api),
            "product_shadow" => Ok(Self::ProductShadow),
            _ => Err(input_error("consumer is unsupported")),
        }
    }

    const fn id(self) -> &'static str {
        match self {
            Self::Cli => "cli",
            Self::Benchmark => "benchmark",
            Self::Api => "api",
            Self::ProductShadow => "product_shadow",
        }
    }

    const fn operator_second_opinion_authorized(self) -> bool {
        matches!(self, Self::ProductShadow)
    }
}

#[derive(Debug)]
struct Coordinates {
    x: Vec<f64>,
    y: Vec<f64>,
    z: Vec<f64>,
}

impl Coordinates {
    fn from_rows(rows: Vec<Vec3>) -> Self {
        let mut x = Vec::with_capacity(rows.len());
        let mut y = Vec::with_capacity(rows.len());
        let mut z = Vec::with_capacity(rows.len());
        for row in rows {
            x.push(row.x);
            y.push(row.y);
            z.push(row.z);
        }
        Self { x, y, z }
    }

    fn view(&self) -> PositionSoa<'_> {
        PositionSoa::new(&self.x, &self.y, &self.z)
    }

    fn rows(&self) -> Vec<Vec3> {
        (0..self.x.len())
            .map(|index| Vec3::new(self.x[index], self.y[index], self.z[index]))
            .collect()
    }
}

struct OwnedSource {
    evidence: Fixed64SourceEvidence,
    coordinates: Coordinates,
}

impl OwnedSource {
    fn view(&self) -> Fixed64CoordinateSource<'_> {
        Fixed64CoordinateSource {
            evidence: self.evidence,
            coordinates: self.coordinates.view(),
        }
    }
}

struct IndexedSource {
    source_index: u32,
    source: OwnedSource,
}

struct ConformerSource {
    rank: u8,
    source: OwnedSource,
}

struct FeatureGeometry {
    kind: Fixed64FeatureKind,
    allocation_feature_receipt_sha256: [u8; 32],
    feature_geometry_receipt_sha256: [u8; 32],
    atom_indices: Vec<u64>,
}

pub(crate) fn register(module: &PyModule) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(
        native_fixed64_complete_pipeline_v1,
        module
    )?)?;
    module.add("NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID", INPUT_SCHEMA_ID)?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_EVIDENCE_SCHEMA_ID",
        EVIDENCE_SCHEMA_ID,
    )?;
    Ok(())
}

#[pyfunction]
fn native_fixed64_complete_pipeline_v1(py: Python<'_>, input: &PyDict) -> PyResult<PyObject> {
    require_exact_keys(input, INPUT_KEYS, "native fixed64 complete input")?;
    if dict_string(input, "schema_id")? != INPUT_SCHEMA_ID {
        return Err(input_error("complete input schema_id is unsupported"));
    }
    if !dict_exact_bool(input, "test_only")? {
        return Err(input_error(
            "complete Python bridge is synthetic/test-only and fails closed otherwise",
        ));
    }
    let consumer = Consumer::parse(dict_string(input, "consumer")?)?;
    let options = context_options(
        dict_string(input, "backend")?,
        exact_i32(dict_value(input, "device_ordinal")?, "device_ordinal")?,
    )?;

    let ligand_coordinates = Coordinates::from_rows(rows3(
        dict_value(input, "ligand_coordinates_angstrom")?,
        "ligand_coordinates_angstrom",
    )?);
    let receptor_coordinates = Coordinates::from_rows(rows3(
        dict_value(input, "receptor_coordinates_angstrom")?,
        "receptor_coordinates_angstrom",
    )?);
    let ligand_count = ligand_coordinates.x.len();
    let receptor_count = receptor_coordinates.x.len();
    let ligand_radii = f64_values(
        dict_value(input, "ligand_vdw_radii_angstrom")?,
        ligand_count,
        "ligand_vdw_radii_angstrom",
    )?;
    let receptor_radii = f64_values(
        dict_value(input, "receptor_vdw_radii_angstrom")?,
        receptor_count,
        "receptor_vdw_radii_angstrom",
    )?;
    let ligand_heavy = bool_mask(
        dict_value(input, "ligand_heavy_atom_mask")?,
        ligand_count,
        "ligand_heavy_atom_mask",
    )?;
    let ligand_charges = f64_values(
        dict_value(input, "ligand_charge_elementary")?,
        ligand_count,
        "ligand_charge_elementary",
    )?;
    let ligand_epsilon = f64_values(
        dict_value(input, "ligand_epsilon_kcal_per_mol")?,
        ligand_count,
        "ligand_epsilon_kcal_per_mol",
    )?;
    let ligand_hydrophobic = bool_mask(
        dict_value(input, "ligand_hydrophobic_mask")?,
        ligand_count,
        "ligand_hydrophobic_mask",
    )?;
    let ligand_acceptor = bool_mask(
        dict_value(input, "ligand_acceptor_mask")?,
        ligand_count,
        "ligand_acceptor_mask",
    )?;
    let receptor_charges = f64_values(
        dict_value(input, "receptor_charge_elementary")?,
        receptor_count,
        "receptor_charge_elementary",
    )?;
    let receptor_epsilon = f64_values(
        dict_value(input, "receptor_epsilon_kcal_per_mol")?,
        receptor_count,
        "receptor_epsilon_kcal_per_mol",
    )?;
    let receptor_hydrophobic = bool_mask(
        dict_value(input, "receptor_hydrophobic_mask")?,
        receptor_count,
        "receptor_hydrophobic_mask",
    )?;
    let receptor_acceptor = bool_mask(
        dict_value(input, "receptor_acceptor_mask")?,
        receptor_count,
        "receptor_acceptor_mask",
    )?;

    let ligand_donors = donors(
        dict_value(input, "ligand_donors")?,
        ligand_count,
        "ligand_donors",
    )?;
    let receptor_donors = donors(
        dict_value(input, "receptor_donors")?,
        receptor_count,
        "receptor_donors",
    )?;
    let ligand_exclusions = pairs(
        dict_value(input, "ligand_exclusions")?,
        ligand_count,
        "ligand_exclusions",
    )?;
    let rotors = rotors(dict_value(input, "rotor_quads")?, ligand_count)?;
    let bonds = pairs(dict_value(input, "bond_pairs")?, ligand_count, "bond_pairs")?;
    let chirality_centers =
        chirality_centers(dict_value(input, "chirality_centers")?, ligand_count)?;
    let parent_atom_index = exact_i32_values(
        dict_value(input, "parent_atom_index")?,
        ligand_count,
        "parent_atom_index",
    )?;
    let rotatable_child_atom_index = exact_u64_values(
        dict_value(input, "rotatable_child_atom_index")?,
        "rotatable_child_atom_index",
    )?;
    let internal_pairs = pairs(
        dict_value(input, "internal_pairs")?,
        ligand_count,
        "internal_pairs",
    )?;

    let receptor_system = dict_digest(input, "receptor_system_sha256")?;
    let ligand_system = dict_digest(input, "ligand_system_sha256")?;
    let prepared_receptor = dict_digest(input, "prepared_receptor_topology_sha256")?;
    let prepared_ligand = dict_digest(input, "prepared_ligand_topology_sha256")?;
    if receptor_system != prepared_receptor || ligand_system != prepared_ligand {
        return Err(input_error(
            "prepared topology and persistent system identities are cross-wired",
        ));
    }

    let pocket_center_vec = vec3_value(
        dict_value(input, "pocket_center_angstrom")?,
        "pocket_center_angstrom",
    )?;
    let pocket_center = [
        pocket_center_vec.x,
        pocket_center_vec.y,
        pocket_center_vec.z,
    ];
    let pocket_normal_vec = vec3_value(dict_value(input, "pocket_normal")?, "pocket_normal")?;
    let pocket_normal = [
        pocket_normal_vec.x,
        pocket_normal_vec.y,
        pocket_normal_vec.z,
    ];
    let pocket_radius = dict_f64(input, "pocket_radius_angstrom")?;

    let exact_source = OwnedSource {
        evidence: Fixed64SourceEvidence {
            receipt_sha256: dict_digest(input, "source_receipt_sha256")?,
            proposal_sha256: dict_digest(input, "proposal_sha256")?,
            coordinate_sha256: coordinate_digest(&ligand_coordinates)?,
        },
        coordinates: Coordinates {
            x: ligand_coordinates.x.clone(),
            y: ligand_coordinates.y.clone(),
            z: ligand_coordinates.z.clone(),
        },
    };
    let v7_sources = indexed_sources(
        dict_value(input, "v7_control_sources")?,
        ligand_count,
        "v7_control_sources",
    )?;
    let conformer_sources =
        conformer_sources(dict_value(input, "conformer_sources")?, ligand_count)?;
    let retained_sources = indexed_sources(
        dict_value(input, "retained_sources")?,
        ligand_count,
        "retained_sources",
    )?;
    let feature_geometries = feature_geometries(dict_value(input, "feature_geometries")?)?;
    let atomic_features = unique_atomic_features(&feature_geometries)?;

    let candidate_modes = candidate_modes(dict_value(input, "candidate_modes")?)?;
    let rigid_max_steps =
        exact_u64_values(dict_value(input, "rigid_max_steps")?, "rigid_max_steps")?;
    let torsion_eligible = bool_mask(
        dict_value(input, "proposal_is_torsion_eligible")?,
        64,
        "proposal_is_torsion_eligible",
    )?;
    let torsion_max_steps =
        exact_u64_values(dict_value(input, "torsion_max_steps")?, "torsion_max_steps")?;
    let baseline_torsion_angles = f64_values(
        dict_value(input, "baseline_torsion_angles_radians")?,
        ligand_count
            .checked_mul(64)
            .ok_or_else(|| input_error("baseline torsion denominator overflows"))?,
        "baseline_torsion_angles_radians",
    )?;
    if candidate_modes.len() != 64 || rigid_max_steps.len() != 64 || torsion_max_steps.len() != 64 {
        return Err(input_error(
            "candidate mode and refinement budgets must each contain exactly 64 values",
        ));
    }

    let exact_evidence = Fixed64ExactSourceEvidence {
        source_receipt_sha256: exact_source.evidence.receipt_sha256,
        proposal_sha256: exact_source.evidence.proposal_sha256,
        ligand_coordinate_sha256: exact_source.evidence.coordinate_sha256,
        receptor_coordinate_sha256: coordinate_digest(&receptor_coordinates)?,
        prepared_ligand_topology_sha256: prepared_ligand,
        prepared_receptor_topology_sha256: prepared_receptor,
        ligand_vdw_radii_sha256: radii_digest(&ligand_radii)?,
        ligand_heavy_atom_mask_sha256: heavy_digest(&ligand_heavy)?,
        receptor_vdw_radii_sha256: radii_digest(&receptor_radii)?,
    };
    let identities = Fixed64Identities {
        authority_input_receipt_sha256: dict_digest(input, "authority_input_receipt_sha256")?,
        receptor_system_sha256: receptor_system,
        ligand_system_sha256: ligand_system,
        backend_receipt_sha256: dict_digest(input, "backend_receipt_sha256")?,
        validity_scorer_context_receipt_sha256: dict_digest(
            input,
            "validity_scorer_context_receipt_sha256",
        )?,
        contact_policy_sha256: dict_digest(input, "contact_policy_sha256")?,
    };

    let context = Context::new(options).map_err(runtime_error)?;
    let scientific = Fixed64PipelineContext {
        receptor: Fixed64Receptor {
            coordinates: receptor_coordinates.view(),
            vdw_radius_angstrom: &receptor_radii,
            charge_elementary: &receptor_charges,
            epsilon_kcal_per_mol: &receptor_epsilon,
            hydrophobic_mask: &receptor_hydrophobic,
            acceptor_mask: &receptor_acceptor,
            donors: &receptor_donors,
        },
        ligand: Fixed64Ligand {
            reference_coordinates: ligand_coordinates.view(),
            vdw_radius_angstrom: &ligand_radii,
            heavy_atom_mask: &ligand_heavy,
            charge_elementary: &ligand_charges,
            epsilon_kcal_per_mol: &ligand_epsilon,
            hydrophobic_mask: &ligand_hydrophobic,
            acceptor_mask: &ligand_acceptor,
            donors: &ligand_donors,
            exclusions: &ligand_exclusions,
            rotors: &rotors,
            bonds: &bonds,
            chirality_centers: &chirality_centers,
            parent_atom_index: &parent_atom_index,
            rotatable_child_atom_index: &rotatable_child_atom_index,
            internal_pairs: &internal_pairs,
        },
        pocket_center_angstrom: pocket_center,
        pocket_radius_angstrom: pocket_radius,
        identities,
    };
    let pipeline = Fixed64Pipeline::new(&context, scientific).map_err(runtime_error)?;

    let v7_views = v7_sources
        .iter()
        .map(|source| Fixed64IndexedCoordinateSource {
            source_index: source.source_index,
            source: source.source.view(),
        })
        .collect::<Vec<_>>();
    let conformer_views = conformer_sources
        .iter()
        .map(|source| Fixed64ConformerCoordinateSource {
            rank: source.rank,
            source: source.source.view(),
        })
        .collect::<Vec<_>>();
    let retained_views = retained_sources
        .iter()
        .map(|source| Fixed64IndexedCoordinateSource {
            source_index: source.source_index,
            source: source.source.view(),
        })
        .collect::<Vec<_>>();
    let feature_views = feature_geometries
        .iter()
        .map(|feature| Fixed64FeatureGeometry {
            kind: feature.kind,
            allocation_feature_receipt_sha256: feature.allocation_feature_receipt_sha256,
            atom_indices: &feature.atom_indices,
            feature_geometry_receipt_sha256: feature.feature_geometry_receipt_sha256,
        })
        .collect::<Vec<_>>();
    let run = Fixed64RunInput {
        exact_source_evidence: exact_evidence,
        exact_source: exact_source.view(),
        atomic_features: &atomic_features,
        v7_control_sources: &v7_views,
        conformer_sources: &conformer_views,
        retained_sources: &retained_views,
        feature_geometries: &feature_views,
        feature_geometry_inventory_sha256: dict_digest_allow_zero(
            input,
            "feature_geometry_inventory_sha256",
        )?,
        pocket_normal,
        rmsd_threshold_angstrom: dict_f64(input, "rmsd_threshold_angstrom")?,
        candidate_modes: &candidate_modes,
        rigid_max_steps: &rigid_max_steps,
        proposal_is_torsion_eligible: &torsion_eligible,
        torsion_max_steps: &torsion_max_steps,
        baseline_torsion_angles_radians: &baseline_torsion_angles,
        predeclared_refinement_policy_sha256: dict_digest(
            input,
            "predeclared_refinement_policy_sha256",
        )?,
    };
    let receipt = pipeline.run(run).map_err(runtime_error)?;
    receipt_to_python(py, &receipt, consumer)
}

fn context_options(backend: &str, device_ordinal: i32) -> PyResult<ContextOptions> {
    match backend {
        "cpp_cpu_reference" if device_ordinal == 0 => Ok(ContextOptions::cpu_reference()),
        "rust_cpu" if device_ordinal == 0 => Ok(ContextOptions::rust_cpu()),
        "hip_safe" if device_ordinal >= 0 => Ok(ContextOptions::hip_safe(device_ordinal)),
        "hip_fast" if device_ordinal >= 0 => Ok(ContextOptions::hip_fast(device_ordinal)),
        "cpp_cpu_reference" | "rust_cpu" => {
            Err(input_error("CPU backends require device_ordinal zero"))
        }
        "hip_safe" | "hip_fast" => Err(input_error(
            "HIP backends require a non-negative device_ordinal",
        )),
        _ => Err(input_error("backend is unsupported or auto-selected")),
    }
}

fn exact_i32(value: &PyAny, name: &str) -> PyResult<i32> {
    if value.is_instance_of::<PyBool>() {
        return Err(input_error(&format!("{name} must be an exact integer")));
    }
    value
        .extract::<i32>()
        .map_err(|_| input_error(&format!("{name} must be an exact i32")))
}

fn dict_digest_allow_zero(dict: &PyDict, key: &str) -> PyResult<[u8; 32]> {
    let value = dict_string(dict, key)?;
    if value == "0".repeat(64) {
        Ok([0; 32])
    } else {
        decode_digest(value, key)
    }
}

fn exact_i32_values(value: &PyAny, expected: usize, name: &str) -> PyResult<Vec<i32>> {
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    if rows.len() != expected {
        return Err(input_error(&format!("{name} length mismatch")));
    }
    rows.iter().map(|item| exact_i32(item, name)).collect()
}

fn exact_u64_values(value: &PyAny, name: &str) -> PyResult<Vec<u64>> {
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    rows.iter()
        .map(|item| {
            if item.is_instance_of::<PyBool>() {
                return Err(input_error(&format!(
                    "{name} values must be exact non-negative integers"
                )));
            }
            item.extract::<u64>().map_err(|_| {
                input_error(&format!(
                    "{name} values must be exact non-negative integers"
                ))
            })
        })
        .collect()
}

fn bool_mask(value: &PyAny, expected: usize, name: &str) -> PyResult<Vec<u8>> {
    bool_values(value, expected, name).map(|values| values.into_iter().map(u8::from).collect())
}

fn donors(value: &PyAny, bound: usize, name: &str) -> PyResult<Vec<Fixed64Donor>> {
    index_rows::<2>(value, bound, name).map(|rows| {
        rows.into_iter()
            .map(|row| Fixed64Donor {
                donor_atom_index: row[0] as u64,
                hydrogen_atom_index: row[1] as u64,
            })
            .collect()
    })
}

fn pairs(value: &PyAny, bound: usize, name: &str) -> PyResult<Vec<Fixed64Pair>> {
    index_rows::<2>(value, bound, name).map(|rows| {
        rows.into_iter()
            .map(|row| Fixed64Pair {
                atom_i: row[0] as u64,
                atom_j: row[1] as u64,
            })
            .collect()
    })
}

fn rotors(value: &PyAny, bound: usize) -> PyResult<Vec<Fixed64Rotor>> {
    index_rows::<4>(value, bound, "rotor_quads").map(|rows| {
        rows.into_iter()
            .map(|row| Fixed64Rotor {
                atom_i: row[0] as u64,
                atom_j: row[1] as u64,
                atom_k: row[2] as u64,
                atom_l: row[3] as u64,
            })
            .collect()
    })
}

fn chirality_centers(value: &PyAny, bound: usize) -> PyResult<Vec<Fixed64ChiralityCenter>> {
    index_rows::<4>(value, bound, "chirality_centers").map(|rows| {
        rows.into_iter()
            .map(|row| Fixed64ChiralityCenter {
                center_atom: row[0] as u64,
                atom_i: row[1] as u64,
                atom_j: row[2] as u64,
                atom_k: row[3] as u64,
            })
            .collect()
    })
}

fn indexed_sources(value: &PyAny, ligand_count: usize, name: &str) -> PyResult<Vec<IndexedSource>> {
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    rows.iter()
        .enumerate()
        .map(|(offset, item)| {
            let row = item
                .downcast::<PyDict>()
                .map_err(|_| input_error(&format!("{name}[{offset}] must be an exact dict")))?;
            require_exact_keys(row, INDEXED_SOURCE_KEYS, name)?;
            Ok(IndexedSource {
                source_index: dict_u32(row, "source_index")?,
                source: source(row, ligand_count, name)?,
            })
        })
        .collect()
}

fn conformer_sources(value: &PyAny, ligand_count: usize) -> PyResult<Vec<ConformerSource>> {
    let name = "conformer_sources";
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error("conformer_sources must be an exact list"))?;
    rows.iter()
        .enumerate()
        .map(|(offset, item)| {
            let row = item
                .downcast::<PyDict>()
                .map_err(|_| input_error(&format!("{name}[{offset}] must be an exact dict")))?;
            require_exact_keys(row, CONFORMER_SOURCE_KEYS, name)?;
            let rank = dict_u32(row, "rank")?;
            Ok(ConformerSource {
                rank: u8::try_from(rank).map_err(|_| input_error("conformer rank exceeds u8"))?,
                source: source(row, ligand_count, name)?,
            })
        })
        .collect()
}

fn source(row: &PyDict, ligand_count: usize, name: &str) -> PyResult<OwnedSource> {
    let coordinates = Coordinates::from_rows(rows3(
        dict_value(row, "coordinates_angstrom")?,
        &format!("{name} coordinates"),
    )?);
    if coordinates.x.len() != ligand_count {
        return Err(input_error(&format!(
            "{name} coordinates must match the ligand atom count"
        )));
    }
    Ok(OwnedSource {
        evidence: Fixed64SourceEvidence {
            receipt_sha256: dict_digest(row, "receipt_sha256")?,
            proposal_sha256: dict_digest(row, "proposal_sha256")?,
            coordinate_sha256: coordinate_digest(&coordinates)?,
        },
        coordinates,
    })
}

fn feature_geometries(value: &PyAny) -> PyResult<Vec<FeatureGeometry>> {
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error("feature_geometries must be an exact list"))?;
    rows.iter()
        .enumerate()
        .map(|(offset, item)| {
            let row = item.downcast::<PyDict>().map_err(|_| {
                input_error(&format!(
                    "feature_geometries[{offset}] must be an exact dict"
                ))
            })?;
            require_exact_keys(row, FEATURE_GEOMETRY_KEYS, "feature_geometries")?;
            Ok(FeatureGeometry {
                kind: feature_kind(dict_string(row, "kind")?)?,
                allocation_feature_receipt_sha256: dict_digest(
                    row,
                    "allocation_feature_receipt_sha256",
                )?,
                feature_geometry_receipt_sha256: dict_digest(
                    row,
                    "feature_geometry_receipt_sha256",
                )?,
                atom_indices: exact_u64_values(dict_value(row, "atom_indices")?, "atom_indices")?,
            })
        })
        .collect()
}

fn unique_atomic_features(features: &[FeatureGeometry]) -> PyResult<Vec<Fixed64AtomicFeature>> {
    let mut seen = BTreeSet::new();
    let mut output = Vec::with_capacity(features.len());
    for feature in features {
        let key = (
            feature_kind_id(feature.kind),
            feature.allocation_feature_receipt_sha256,
        );
        if !seen.insert(key) {
            continue;
        }
        output.push(Fixed64AtomicFeature {
            kind: feature.kind,
            receipt_sha256: feature.allocation_feature_receipt_sha256,
        });
    }
    Ok(output)
}

fn feature_kind(value: &str) -> PyResult<Fixed64FeatureKind> {
    match value {
        "ligand_donor" => Ok(Fixed64FeatureKind::LigandDonor),
        "ligand_acceptor" => Ok(Fixed64FeatureKind::LigandAcceptor),
        "receptor_donor" => Ok(Fixed64FeatureKind::ReceptorDonor),
        "receptor_acceptor" => Ok(Fixed64FeatureKind::ReceptorAcceptor),
        "ligand_positive_site" => Ok(Fixed64FeatureKind::LigandPositiveSite),
        "ligand_negative_site" => Ok(Fixed64FeatureKind::LigandNegativeSite),
        "receptor_positive_site" => Ok(Fixed64FeatureKind::ReceptorPositiveSite),
        "receptor_negative_site" => Ok(Fixed64FeatureKind::ReceptorNegativeSite),
        "ligand_aromatic_plane" => Ok(Fixed64FeatureKind::LigandAromaticPlane),
        "receptor_aromatic_plane" => Ok(Fixed64FeatureKind::ReceptorAromaticPlane),
        "ligand_shape_axis" => Ok(Fixed64FeatureKind::LigandShapeAxis),
        "pocket_shape_axis" => Ok(Fixed64FeatureKind::PocketShapeAxis),
        _ => Err(input_error("feature kind is unsupported")),
    }
}

const fn feature_kind_id(value: Fixed64FeatureKind) -> u8 {
    match value {
        Fixed64FeatureKind::LigandDonor => 0,
        Fixed64FeatureKind::LigandAcceptor => 1,
        Fixed64FeatureKind::ReceptorDonor => 2,
        Fixed64FeatureKind::ReceptorAcceptor => 3,
        Fixed64FeatureKind::LigandPositiveSite => 4,
        Fixed64FeatureKind::LigandNegativeSite => 5,
        Fixed64FeatureKind::ReceptorPositiveSite => 6,
        Fixed64FeatureKind::ReceptorNegativeSite => 7,
        Fixed64FeatureKind::LigandAromaticPlane => 8,
        Fixed64FeatureKind::ReceptorAromaticPlane => 9,
        Fixed64FeatureKind::LigandShapeAxis => 10,
        Fixed64FeatureKind::PocketShapeAxis => 11,
    }
}

fn candidate_modes(value: &PyAny) -> PyResult<Vec<Fixed64RefinementMode>> {
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error("candidate_modes must be an exact list"))?;
    rows.iter()
        .map(|item| {
            let value = item
                .extract::<&str>()
                .map_err(|_| input_error("candidate mode must be a string"))?;
            match value {
                "v2_translation" => Ok(Fixed64RefinementMode::V2Translation),
                "v3_translation_rotation" => Ok(Fixed64RefinementMode::V3TranslationRotation),
                "v6_baseline_v2_lane" => Ok(Fixed64RefinementMode::V6BaselineV2Lane),
                "v6_baseline_v3_lane" => Ok(Fixed64RefinementMode::V6BaselineV3Lane),
                _ => Err(input_error("candidate refinement mode is unsupported")),
            }
        })
        .collect()
}

fn coordinate_digest(value: &Coordinates) -> PyResult<[u8; 32]> {
    native_fixed64_coordinate_sha256(&value.rows()).map_err(|error| input_error(error.message()))
}

fn radii_digest(values: &[f64]) -> PyResult<[u8; 32]> {
    native_fixed64_radii_sha256(values).map_err(|error| input_error(error.message()))
}

fn heavy_digest(values: &[u8]) -> PyResult<[u8; 32]> {
    let values = values.iter().map(|value| *value == 1).collect::<Vec<_>>();
    native_fixed64_heavy_atom_mask_sha256(&values).map_err(|error| input_error(error.message()))
}

fn runtime_error(error: betelgeuze_runtime::Error) -> PyErr {
    input_error(&format!(
        "native_complete_pipeline_{:?}: {}",
        error.code, error.message
    ))
}

fn backend_id(value: Backend) -> &'static str {
    match value {
        Backend::Auto => "auto",
        Backend::CppCpuReference => "cpp_cpu_reference",
        Backend::RustCpu => "rust_cpu",
        Backend::HipSafe => "hip_safe",
        Backend::HipFast => "hip_fast",
    }
}

fn consumer_view_digest(receipt: &Fixed64PipelineReceipt, consumer: Consumer) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine-v2.native-fixed64-complete-consumer-view/v1\0");
    hash.update(receipt.receipts.pipeline_batch_receipt_sha256);
    hash.update((consumer.id().len() as u64).to_be_bytes());
    hash.update(consumer.id().as_bytes());
    hash.update([u8::from(consumer.operator_second_opinion_authorized())]);
    hash.update([0_u8; 7]);
    hash.finalize().into()
}

fn receipt_to_python(
    py: Python<'_>,
    receipt: &Fixed64PipelineReceipt,
    consumer: Consumer,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    output.set_item("schema_id", EVIDENCE_SCHEMA_ID)?;
    output.set_item(
        "pipeline_id",
        Fixed64Pipeline::profile_id().map_err(runtime_error)?,
    )?;
    output.set_item("consumer", consumer.id())?;
    output.set_item("backend", backend_id(receipt.backend))?;
    output.set_item("unit_system", "angstrom_kcal_mol")?;
    output.set_item("candidate_denominator", 64)?;
    output.set_item("receptor_atom_count", receipt.receptor_atom_count)?;
    output.set_item("ligand_atom_count", receipt.ligand_atom_count)?;
    output.set_item("generated_count", receipt.generated_count)?;
    output.set_item("typed_failure_count", receipt.typed_failure_count)?;
    output.set_item("initial_admitted_count", receipt.initial_admitted_count)?;
    output.set_item("refined_count", receipt.refined_count)?;
    output.set_item("scored_count", receipt.scored_count)?;
    output.set_item("valid_count", receipt.valid_count)?;
    output.set_item("cluster_count", receipt.cluster_count)?;
    output.set_item(
        "pipeline_receipt_sha256",
        hex_digest(receipt.receipts.pipeline_batch_receipt_sha256),
    )?;
    output.set_item(
        "consumer_view_receipt_sha256",
        hex_digest(consumer_view_digest(receipt, consumer)),
    )?;
    output.set_item(
        "allocation_receipt_sha256",
        hex_digest(receipt.receipts.allocation_receipt_sha256),
    )?;
    output.set_item(
        "proposal_batch_receipt_sha256",
        hex_digest(receipt.receipts.producer_batch_receipt_sha256),
    )?;
    output.set_item(
        "geometric_admission_receipt_sha256",
        hex_digest(receipt.receipts.geometric_admission_batch_receipt_sha256),
    )?;
    output.set_item(
        "scorer_receipt_sha256",
        hex_digest(receipt.receipts.scorer_batch_receipt_sha256),
    )?;
    output.set_item(
        "validity_receipt_sha256",
        hex_digest(receipt.receipts.validity_batch_receipt_sha256),
    )?;
    output.set_item(
        "ranking_receipt_sha256",
        hex_digest(receipt.receipts.ranking_batch_receipt_sha256),
    )?;
    output.set_item("primary_slot_indices", &receipt.primary_slot_indices)?;
    output.set_item("valid_slot_indices", &receipt.valid_slot_indices)?;
    output.set_item(
        "representative_slot_indices",
        &receipt.representative_slot_indices,
    )?;
    output.set_item("top_k_slot_indices", &receipt.top_k_slot_indices)?;
    output.set_item("result_dependent_input_consumed", false)?;
    output.set_item("fallback_allowed", false)?;
    output.set_item("multi_anchor_consumed", false)?;
    output.set_item("denominator_preserved", true)?;
    output.set_item("evidence_display_authorized", true)?;
    output.set_item(
        "operator_second_opinion_authorized",
        consumer.operator_second_opinion_authorized(),
    )?;
    output.set_item("reservation_authorized", false)?;
    output.set_item("molecular_execution_authorized", false)?;
    output.set_item("benchmark_execution_authorized", false)?;
    output.set_item("existing_rank_auto_change_authorized", false)?;
    output.set_item("customer_pose_emission_authorized", false)?;
    output.set_item("production_claim_authorized", false)?;
    output.set_item("scientific_claim_authorized", false)?;

    let rows = PyList::empty(py);
    for slot in 0..64 {
        rows.append(candidate_to_python(py, receipt, slot)?)?;
    }
    output.set_item("candidates", rows)?;
    Ok(output.into())
}

fn candidate_to_python(
    py: Python<'_>,
    receipt: &Fixed64PipelineReceipt,
    slot: usize,
) -> PyResult<PyObject> {
    let producer = &receipt.producer_rows[slot];
    let scorer = &receipt.scorer_rows[slot];
    let validity = &receipt.validity_rows[slot];
    let ranking = &receipt.ranking_rows[slot];
    let cluster = &receipt.cluster_rows[slot];
    let pipeline = &receipt.rows[slot];
    let row = PyDict::new(py);
    row.set_item("slot_index", slot)?;
    row.set_item("lane", producer.lane)?;
    row.set_item("producer_status", producer.status)?;
    row.set_item("producer_failure_code", producer.failure_code)?;
    row.set_item("placement_kind", producer.placement_kind)?;
    row.set_item("coordinates_available", producer.coordinates_available)?;
    row.set_item("steric_precheck_passed", producer.steric_precheck_passed)?;
    row.set_item(
        "source_identity_verified",
        producer.source_identity_verified,
    )?;
    row.set_item(
        "allocation_identity_verified",
        producer.allocation_identity_verified,
    )?;
    row.set_item(
        "geometric_identity_verified",
        producer.geometric_identity_verified,
    )?;
    row.set_item("denominator_preserved", producer.denominator_preserved)?;
    row.set_item("placement_quaternion", producer.placement_quaternion)?;
    row.set_item(
        "producer_row_receipt_sha256",
        hex_digest(producer.row_receipt_sha256),
    )?;

    let geometric = PyDict::new(py);
    geometric.set_item("status", producer.geometric.status)?;
    geometric.set_item("failure_code", producer.geometric.failure_code)?;
    geometric.set_item("decision", producer.geometric.decision)?;
    geometric.set_item("rank_eligible", producer.geometric.rank_eligible)?;
    geometric.set_item("ligand_atom_count", producer.geometric.ligand_atom_count)?;
    geometric.set_item(
        "receptor_atom_count",
        producer.geometric.receptor_atom_count,
    )?;
    geometric.set_item("exact_pair_count", producer.geometric.exact_pair_count)?;
    geometric.set_item(
        "penetration_pair_count",
        producer.geometric.penetration_pair_count,
    )?;
    geometric.set_item(
        "penetrating_heavy_atom_count",
        producer
            .geometric
            .unique_ligand_heavy_atom_penetration_count,
    )?;
    geometric.set_item(
        "raw_minimum_distance_angstrom",
        producer.geometric.raw_minimum_distance_angstrom,
    )?;
    geometric.set_item(
        "minimum_vdw_surface_gap_angstrom",
        producer.geometric.minimum_vdw_surface_gap_angstrom,
    )?;
    geometric.set_item("minimum_vdw_ratio", producer.geometric.minimum_vdw_ratio)?;
    geometric.set_item(
        "sphere_overlap_proxy_angstrom3",
        producer.geometric.sphere_overlap_proxy_angstrom3,
    )?;
    geometric.set_item(
        "pocket_escape_angstrom",
        producer.geometric.pocket_escape_angstrom,
    )?;
    geometric.set_item(
        "receipt_sha256",
        hex_digest(producer.geometric.row_receipt_sha256),
    )?;
    row.set_item("geometric_admission", geometric)?;

    row.set_item(
        "rigid_refinement",
        rigid_to_python(py, &receipt.rigid_rows[slot])?,
    )?;
    row.set_item("torsion_refinement", torsion_to_python(py, receipt, slot)?)?;
    row.set_item(
        "refinement",
        refinement_to_python(py, &receipt.refinement_rows[slot])?,
    )?;

    let scoring = PyDict::new(py);
    scoring.set_item("status", scorer.status)?;
    scoring.set_item("failure_code", scorer.failure_code)?;
    scoring.set_item("weighted_terms", scorer.weighted_terms)?;
    scoring.set_item("total_score", scorer.total_score)?;
    scoring.set_item(
        "receptor_candidate_pair_count",
        scorer.receptor_candidate_pair_count,
    )?;
    scoring.set_item("ligand_pair_count", scorer.ligand_pair_count)?;
    scoring.set_item("hbond_count", scorer.hbond_count)?;
    scoring.set_item(
        "hydrophobic_contact_count",
        scorer.hydrophobic_contact_count,
    )?;
    scoring.set_item("buried_polar_count", scorer.buried_polar_count)?;
    row.set_item("scorer_v1", scoring)?;

    let validity_output = PyDict::new(py);
    validity_output.set_item("status", validity.status)?;
    validity_output.set_item("failure_code", validity.failure_code)?;
    validity_output.set_item(
        "upstream_scorer_failure_code",
        validity.upstream_scorer_failure_code,
    )?;
    validity_output.set_item("passed_check_mask", validity.passed_check_mask)?;
    validity_output.set_item("blocker_mask", validity.blocker_mask)?;
    validity_output.set_item("observed_count", validity.observed_count)?;
    validity_output.set_item("atom_count", validity.atom_count)?;
    validity_output.set_item(
        "minimum_receptor_ligand_distance_angstrom",
        validity.minimum_receptor_ligand_distance_angstrom,
    )?;
    validity_output.set_item(
        "evaluated_receptor_ligand_pair_count",
        validity.evaluated_receptor_ligand_pair_count,
    )?;
    validity_output.set_item(
        "element_vdw_receptor_full_cartesian_pair_count",
        validity.element_vdw_receptor_full_cartesian_pair_count,
    )?;
    validity_output.set_item(
        "element_vdw_receptor_severe_overlap_count",
        validity.element_vdw_receptor_severe_overlap_count,
    )?;
    validity_output.set_item(
        "element_vdw_receptor_minimum_ratio",
        validity.element_vdw_receptor_minimum_ratio,
    )?;
    row.set_item("validity", validity_output)?;

    let rank = PyDict::new(py);
    rank.set_item("rank_eligible", ranking.rank_eligible)?;
    rank.set_item("valid_rank_eligible", ranking.valid_rank_eligible)?;
    rank.set_item("stable_rank", ranking.stable_rank)?;
    rank.set_item("stable_valid_rank", ranking.stable_valid_rank)?;
    rank.set_item("total_score", ranking.total_score)?;
    rank.set_item("coordinate_sha256", hex_digest(ranking.coordinate_sha256))?;
    row.set_item("ranking", rank)?;

    let cluster_output = PyDict::new(py);
    cluster_output.set_item("status", cluster.status)?;
    cluster_output.set_item("cluster_eligible", cluster.cluster_eligible)?;
    cluster_output.set_item("representative", cluster.representative)?;
    cluster_output.set_item("top_k_representative", cluster.top_k_representative)?;
    cluster_output.set_item("cluster_id", cluster.cluster_id)?;
    cluster_output.set_item("cluster_rank", cluster.cluster_rank)?;
    cluster_output.set_item("top_k_rank", cluster.top_k_rank)?;
    cluster_output.set_item("cluster_size", cluster.cluster_size)?;
    cluster_output.set_item(
        "direct_rmsd_to_representative_angstrom",
        cluster.direct_rmsd_to_representative_angstrom,
    )?;
    row.set_item("cluster", cluster_output)?;

    let lineage = PyDict::new(py);
    lineage.set_item(
        "producer_row_receipt_sha256",
        hex_digest(pipeline.producer_row_receipt_sha256),
    )?;
    lineage.set_item(
        "final_coordinate_sha256",
        hex_digest(pipeline.final_coordinate_sha256),
    )?;
    lineage.set_item(
        "refinement_evidence_sha256",
        hex_digest(pipeline.refinement_evidence_sha256),
    )?;
    lineage.set_item(
        "scorer_evidence_sha256",
        hex_digest(pipeline.scorer_evidence_sha256),
    )?;
    lineage.set_item(
        "validity_evidence_sha256",
        hex_digest(pipeline.validity_evidence_sha256),
    )?;
    lineage.set_item(
        "ranking_evidence_sha256",
        hex_digest(pipeline.ranking_evidence_sha256),
    )?;
    lineage.set_item(
        "cluster_evidence_sha256",
        hex_digest(pipeline.cluster_evidence_sha256),
    )?;
    lineage.set_item(
        "row_receipt_sha256",
        hex_digest(pipeline.row_receipt_sha256),
    )?;
    row.set_item("lineage", lineage)?;

    let coordinates = PyDict::new(py);
    coordinates.set_item(
        "producer",
        coordinate_rows(
            py,
            &receipt.producer_coordinates,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "rigid_selected",
        coordinate_rows(
            py,
            &receipt.rigid_coordinates.selected,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "rigid_comparison_v2",
        coordinate_rows(
            py,
            &receipt.rigid_coordinates.comparison_v2,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "rigid_baseline_v3",
        coordinate_rows(
            py,
            &receipt.rigid_coordinates.baseline_v3,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "rigid_clearance_v4",
        coordinate_rows(
            py,
            &receipt.rigid_coordinates.clearance_v4,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "torsion_optimized",
        coordinate_rows(
            py,
            &receipt.torsion_coordinates.optimized,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "torsion_final",
        coordinate_rows(
            py,
            &receipt.torsion_coordinates.final_state,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    coordinates.set_item(
        "final",
        coordinate_rows(
            py,
            &receipt.final_coordinates,
            slot,
            receipt.ligand_atom_count,
        )?,
    )?;
    row.set_item("coordinate_states_angstrom", coordinates)?;
    row.set_item(
        "final_quaternion",
        [
            receipt.final_quaternions[0][slot],
            receipt.final_quaternions[1][slot],
            receipt.final_quaternions[2][slot],
            receipt.final_quaternions[3][slot],
        ],
    )?;
    Ok(row.into())
}

fn coordinate_rows(
    py: Python<'_>,
    coordinates: &PositionSoaOwned,
    slot: usize,
    ligand_count: usize,
) -> PyResult<PyObject> {
    let rows = PyList::empty(py);
    let start = slot
        .checked_mul(ligand_count)
        .ok_or_else(|| input_error("candidate coordinate offset overflowed"))?;
    for index in start..start + ligand_count {
        rows.append([
            coordinates.x_angstrom[index],
            coordinates.y_angstrom[index],
            coordinates.z_angstrom[index],
        ])?;
    }
    Ok(rows.into())
}

fn rigid_to_python(
    py: Python<'_>,
    row: &betelgeuze_runtime::Fixed64RigidEvidence,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    output.set_item("status", row.status)?;
    output.set_item("failure_code", row.failure_code)?;
    output.set_item("candidate_mode", row.candidate_mode)?;
    output.set_item("selected_profile", row.selected_profile)?;
    output.set_item("baseline_duplicate_of_v2", row.baseline_duplicate_of_v2)?;
    output.set_item("clearance_evaluated", row.clearance_evaluated)?;
    output.set_item("clearance_selected", row.clearance_selected)?;
    output.set_item("selected", rigid_profile_to_python(py, &row.selected)?)?;
    output.set_item(
        "comparison_v2",
        rigid_profile_to_python(py, &row.comparison_v2)?,
    )?;
    output.set_item(
        "baseline_v3",
        rigid_profile_to_python(py, &row.baseline_v3)?,
    )?;
    output.set_item(
        "clearance_v4",
        rigid_profile_to_python(py, &row.clearance_v4)?,
    )?;
    Ok(output.into())
}

fn rigid_profile_to_python(
    py: Python<'_>,
    evidence: &betelgeuze_runtime::Fixed64RigidProfileEvidence,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    output.set_item("profile", evidence.profile)?;
    output.set_item("available", evidence.available)?;
    output.set_item("accepted_steps", evidence.accepted_steps)?;
    output.set_item(
        "accepted_translation_steps",
        evidence.accepted_translation_steps,
    )?;
    output.set_item("accepted_rotation_steps", evidence.accepted_rotation_steps)?;
    output.set_item(
        "line_search_evaluation_count",
        evidence.line_search_evaluation_count,
    )?;
    output.set_item("initial_penalty", evidence.initial_penalty)?;
    output.set_item("final_penalty", evidence.final_penalty)?;
    output.set_item(
        "total_translation_angstrom",
        evidence.total_translation_angstrom,
    )?;
    output.set_item(
        "total_rotation_vector_radians",
        evidence.total_rotation_vector_radians,
    )?;
    output.set_item(
        "total_rotation_path_radians",
        evidence.total_rotation_path_radians,
    )?;
    Ok(output.into())
}

fn torsion_to_python(
    py: Python<'_>,
    receipt: &Fixed64PipelineReceipt,
    slot: usize,
) -> PyResult<PyObject> {
    let row = &receipt.torsion_rows[slot];
    let output = PyDict::new(py);
    output.set_item("status", row.status)?;
    output.set_item("failure_code", row.failure_code)?;
    output.set_item("skip_reason", row.skip_reason)?;
    output.set_item("selection_reason", row.selection_reason)?;
    output.set_item("selection_window_reachable", row.selection_window_reachable)?;
    output.set_item("torsion_evaluated", row.torsion_evaluated)?;
    output.set_item("torsion_variant_available", row.torsion_variant_available)?;
    output.set_item("torsion_selected", row.torsion_selected)?;
    output.set_item("torsion_step_budget", row.torsion_step_budget)?;
    output.set_item("evaluated_torsion_steps", row.evaluated_torsion_steps)?;
    output.set_item("accepted_torsion_steps", row.accepted_torsion_steps)?;
    output.set_item("source_receptor_penalty", row.source_receptor_penalty)?;
    output.set_item("source_internal_penalty", row.source_internal_penalty)?;
    output.set_item("source_combined_penalty", row.source_combined_penalty)?;
    output.set_item("baseline_receptor_penalty", row.baseline_receptor_penalty)?;
    output.set_item("baseline_internal_penalty", row.baseline_internal_penalty)?;
    output.set_item("baseline_combined_penalty", row.baseline_combined_penalty)?;
    output.set_item("optimized_receptor_penalty", row.optimized_receptor_penalty)?;
    output.set_item("optimized_internal_penalty", row.optimized_internal_penalty)?;
    output.set_item("optimized_combined_penalty", row.optimized_combined_penalty)?;
    output.set_item("final_receptor_penalty", row.final_receptor_penalty)?;
    output.set_item("final_internal_penalty", row.final_internal_penalty)?;
    output.set_item("final_combined_penalty", row.final_combined_penalty)?;
    let moves = PyList::empty(py);
    for evidence in &receipt.torsion_moves[slot * 8..slot * 8 + 8] {
        let item = PyDict::new(py);
        item.set_item("move_index", evidence.move_index)?;
        item.set_item("evaluated", evidence.evaluated)?;
        item.set_item("selected", evidence.selected)?;
        item.set_item(
            "rotatable_child_atom_index",
            evidence.rotatable_child_atom_index,
        )?;
        item.set_item("delta_radians", evidence.delta_radians)?;
        item.set_item("receptor_penalty", evidence.receptor_penalty)?;
        item.set_item("internal_penalty", evidence.internal_penalty)?;
        item.set_item("combined_penalty", evidence.combined_penalty)?;
        moves.append(item)?;
    }
    output.set_item("moves", moves)?;
    Ok(output.into())
}

fn refinement_to_python(
    py: Python<'_>,
    row: &betelgeuze_runtime::Fixed64RefinementEvidence,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    output.set_item("status", row.status)?;
    output.set_item("failure_stage", row.failure_stage)?;
    output.set_item("coordinate_origin", row.coordinate_origin)?;
    output.set_item("rigid_failure_code", row.rigid_failure_code)?;
    output.set_item("torsion_v7_failure_code", row.torsion_v7_failure_code)?;
    output.set_item("selected_rigid_profile", row.selected_rigid_profile)?;
    output.set_item("downstream_candidate_state", row.downstream_candidate_state)?;
    output.set_item("torsion_v7_applicable", row.torsion_v7_applicable)?;
    output.set_item("torsion_v7_selected", row.torsion_v7_selected)?;
    output.set_item("coordinate_available", row.coordinate_available)?;
    output.set_item("coordinate_sha256", hex_digest(row.coordinate_sha256))?;
    Ok(output.into())
}
