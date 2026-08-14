//! PyO3 boundary for the versioned native C++/Rust/HIP fixed64 pipeline.
//!
//! Python performs schema transport only. Proposal generation, geometric
//! admission, refinement, ScorerV1, pose validity, stable ranking, and RMSD
//! clustering all execute through the one safe Rust owner of the C ABI.

use std::collections::BTreeSet;

use betelgeuze_docking_search::{
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, Vec3, FIXED64_MAX_LIGAND_ATOMS, FIXED64_MAX_RECEPTOR_ATOMS,
};
use betelgeuze_runtime::{
    Backend, Context, ContextOptions, Fixed64AtomicFeature, Fixed64ChiralityCenter,
    Fixed64ConformerCoordinateSource, Fixed64CoordinateSource, Fixed64Donor,
    Fixed64ExactSourceEvidence, Fixed64FeatureGeometry, Fixed64FeatureKind, Fixed64Identities,
    Fixed64IndexedCoordinateSource, Fixed64Ligand, Fixed64Pair, Fixed64Pipeline,
    Fixed64PipelineContext, Fixed64PipelineReceipt, Fixed64Receptor, Fixed64RefinementMode,
    Fixed64Rotor, Fixed64RunInput, Fixed64SourceEvidence, PositionSoa, PositionSoaOwned,
};
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyFloat, PyList, PyLong, PyString};
use sha2::{Digest, Sha256};

use crate::fixed64_pipeline::{
    bool_values, decode_digest, dict_digest, dict_exact_bool, dict_f64, dict_string, dict_u32,
    dict_value, f64_values, hex_digest, index_rows, input_error, require_exact_keys, rows3,
    vec3_value,
};

const LEGACY_INPUT_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_fixed64_complete_input/1.0.0";
pub(crate) const INPUT_SCHEMA_ID_V2: &str =
    "betelgeuze.engine_v2_native_fixed64_complete_input/2.0.0";
pub(crate) const EVIDENCE_SCHEMA_ID_V2: &str =
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/2.0.0";
pub(crate) const INPUT_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0";
pub(crate) const EVIDENCE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/3.0.0";

const MAX_V7_CONTROL_SOURCES: usize = 24;
const MAX_CONFORMER_SOURCES: usize = 7;
const MAX_RETAINED_SOURCES: usize = 4;
const MAX_ATOMIC_FEATURES: usize = 12 * 256;
const MAX_FEATURE_ATOM_INDICES: usize = FIXED64_MAX_RECEPTOR_ATOMS;
const MAX_PREPARED_INPUT_SCALAR_COUNT: usize = 8 * 1_024 * 1_024;
const PREPARED_INPUT_PROJECTION_DOMAIN: &[u8] =
    b"betelgeuze.engine-v2.native-fixed64-prepared-input-projection/v1\0";
const PREPARED_INPUT_RECEIPT_DOMAIN: &[u8] =
    b"betelgeuze.engine-v2.native-fixed64-prepared-input-receipt/v1\0";
const PREPARED_SESSION_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_prepared_session/1.0.0";
const PREPARED_SESSION_RECEIPT_DOMAIN: &[u8] =
    b"betelgeuze.engine-v2.native-fixed64-prepared-session/v1\0";

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
    "predeclared_post_refinement_admission_policy_sha256",
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum CompleteTransportVersion {
    V2,
    V3,
}

impl CompleteTransportVersion {
    const fn input_schema_id(self) -> &'static str {
        match self {
            Self::V2 => INPUT_SCHEMA_ID_V2,
            Self::V3 => INPUT_SCHEMA_ID,
        }
    }

    const fn evidence_schema_id(self) -> &'static str {
        match self {
            Self::V2 => EVIDENCE_SCHEMA_ID_V2,
            Self::V3 => EVIDENCE_SCHEMA_ID,
        }
    }

    const fn is_bounded(self) -> bool {
        matches!(self, Self::V3)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct PreparedInputBounds {
    ligand_atom_count: usize,
    receptor_atom_count: usize,
    exact_cartesian_pair_count: usize,
    scalar_count: usize,
}

struct OwnedCompletePipelineInput {
    options: ContextOptions,
    exact_evidence: Fixed64ExactSourceEvidence,
    identities: Fixed64Identities,
    ligand_coordinates: Coordinates,
    ligand_radii: Vec<f64>,
    ligand_heavy: Vec<u8>,
    ligand_charges: Vec<f64>,
    ligand_epsilon: Vec<f64>,
    ligand_hydrophobic: Vec<u8>,
    ligand_acceptor: Vec<u8>,
    ligand_donors: Vec<Fixed64Donor>,
    ligand_exclusions: Vec<Fixed64Pair>,
    rotors: Vec<Fixed64Rotor>,
    bonds: Vec<Fixed64Pair>,
    chirality_centers: Vec<Fixed64ChiralityCenter>,
    parent_atom_index: Vec<i32>,
    rotatable_child_atom_index: Vec<u64>,
    internal_pairs: Vec<Fixed64Pair>,
    receptor_coordinates: Coordinates,
    receptor_radii: Vec<f64>,
    receptor_charges: Vec<f64>,
    receptor_epsilon: Vec<f64>,
    receptor_hydrophobic: Vec<u8>,
    receptor_acceptor: Vec<u8>,
    receptor_donors: Vec<Fixed64Donor>,
    pocket_center: [f64; 3],
    pocket_radius: f64,
    exact_source: OwnedSource,
    atomic_features: Vec<Fixed64AtomicFeature>,
    v7_sources: Vec<IndexedSource>,
    conformer_sources: Vec<ConformerSource>,
    retained_sources: Vec<IndexedSource>,
    feature_geometries: Vec<FeatureGeometry>,
    feature_geometry_inventory_sha256: [u8; 32],
    pocket_normal: [f64; 3],
    rmsd_threshold_angstrom: f64,
    candidate_modes: Vec<Fixed64RefinementMode>,
    rigid_max_steps: Vec<u64>,
    torsion_eligible: Vec<u8>,
    torsion_max_steps: Vec<u64>,
    baseline_torsion_angles: Vec<f64>,
    predeclared_refinement_policy_sha256: [u8; 32],
    predeclared_post_refinement_admission_policy_sha256: [u8; 32],
    prepared_input_bounds: Option<PreparedInputBounds>,
    prepared_input_projection_sha256: Option<[u8; 32]>,
}

impl OwnedCompletePipelineInput {
    fn create_pipeline(&self) -> betelgeuze_runtime::Result<Fixed64Pipeline> {
        let context = Context::new(self.options)?;
        let scientific = Fixed64PipelineContext {
            receptor: Fixed64Receptor {
                coordinates: self.receptor_coordinates.view(),
                vdw_radius_angstrom: &self.receptor_radii,
                charge_elementary: &self.receptor_charges,
                epsilon_kcal_per_mol: &self.receptor_epsilon,
                hydrophobic_mask: &self.receptor_hydrophobic,
                acceptor_mask: &self.receptor_acceptor,
                donors: &self.receptor_donors,
            },
            ligand: Fixed64Ligand {
                reference_coordinates: self.ligand_coordinates.view(),
                vdw_radius_angstrom: &self.ligand_radii,
                heavy_atom_mask: &self.ligand_heavy,
                charge_elementary: &self.ligand_charges,
                epsilon_kcal_per_mol: &self.ligand_epsilon,
                hydrophobic_mask: &self.ligand_hydrophobic,
                acceptor_mask: &self.ligand_acceptor,
                donors: &self.ligand_donors,
                exclusions: &self.ligand_exclusions,
                rotors: &self.rotors,
                bonds: &self.bonds,
                chirality_centers: &self.chirality_centers,
                parent_atom_index: &self.parent_atom_index,
                rotatable_child_atom_index: &self.rotatable_child_atom_index,
                internal_pairs: &self.internal_pairs,
            },
            pocket_center_angstrom: self.pocket_center,
            pocket_radius_angstrom: self.pocket_radius,
            identities: self.identities,
        };
        Fixed64Pipeline::new(&context, scientific)
    }

    fn run(
        &self,
        pipeline: &Fixed64Pipeline,
    ) -> betelgeuze_runtime::Result<Fixed64PipelineReceipt> {
        let v7_views = self
            .v7_sources
            .iter()
            .map(|source| Fixed64IndexedCoordinateSource {
                source_index: source.source_index,
                source: source.source.view(),
            })
            .collect::<Vec<_>>();
        let conformer_views = self
            .conformer_sources
            .iter()
            .map(|source| Fixed64ConformerCoordinateSource {
                rank: source.rank,
                source: source.source.view(),
            })
            .collect::<Vec<_>>();
        let retained_views = self
            .retained_sources
            .iter()
            .map(|source| Fixed64IndexedCoordinateSource {
                source_index: source.source_index,
                source: source.source.view(),
            })
            .collect::<Vec<_>>();
        let feature_views = self
            .feature_geometries
            .iter()
            .map(|feature| Fixed64FeatureGeometry {
                kind: feature.kind,
                allocation_feature_receipt_sha256: feature.allocation_feature_receipt_sha256,
                atom_indices: &feature.atom_indices,
                feature_geometry_receipt_sha256: feature.feature_geometry_receipt_sha256,
            })
            .collect::<Vec<_>>();
        pipeline.run(Fixed64RunInput {
            exact_source_evidence: self.exact_evidence,
            exact_source: self.exact_source.view(),
            atomic_features: &self.atomic_features,
            v7_control_sources: &v7_views,
            conformer_sources: &conformer_views,
            retained_sources: &retained_views,
            feature_geometries: &feature_views,
            feature_geometry_inventory_sha256: self.feature_geometry_inventory_sha256,
            pocket_normal: self.pocket_normal,
            rmsd_threshold_angstrom: self.rmsd_threshold_angstrom,
            candidate_modes: &self.candidate_modes,
            rigid_max_steps: &self.rigid_max_steps,
            proposal_is_torsion_eligible: &self.torsion_eligible,
            torsion_max_steps: &self.torsion_max_steps,
            baseline_torsion_angles_radians: &self.baseline_torsion_angles,
            predeclared_refinement_policy_sha256: self.predeclared_refinement_policy_sha256,
            predeclared_post_refinement_admission_policy_sha256: self
                .predeclared_post_refinement_admission_policy_sha256,
        })
    }

    fn run_once(&self) -> betelgeuze_runtime::Result<Fixed64PipelineReceipt> {
        let pipeline = self.create_pipeline()?;
        self.run(&pipeline)
    }
}

#[pyclass(unsendable, name = "NativeFixed64PreparedSessionV1")]
struct NativeFixed64PreparedSession {
    default_consumer: Consumer,
    pipeline: Fixed64Pipeline,
    input: OwnedCompletePipelineInput,
    prepared_session_receipt_sha256: [u8; 32],
}

pub(crate) fn register(module: &PyModule) -> PyResult<()> {
    module.add_class::<NativeFixed64PreparedSession>()?;
    module.add_function(wrap_pyfunction!(
        native_fixed64_complete_pipeline_v1,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        native_fixed64_complete_pipeline_v2,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        native_fixed64_complete_pipeline_v3,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(native_fixed64_prepare_session_v1, module)?)?;
    module.add("NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID", INPUT_SCHEMA_ID)?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID_V1",
        LEGACY_INPUT_SCHEMA_ID,
    )?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID_V2",
        INPUT_SCHEMA_ID_V2,
    )?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID_V3",
        INPUT_SCHEMA_ID,
    )?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_EVIDENCE_SCHEMA_ID",
        EVIDENCE_SCHEMA_ID,
    )?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_EVIDENCE_SCHEMA_ID_V2",
        EVIDENCE_SCHEMA_ID_V2,
    )?;
    module.add(
        "NATIVE_FIXED64_COMPLETE_EVIDENCE_SCHEMA_ID_V3",
        EVIDENCE_SCHEMA_ID,
    )?;
    module.add(
        "NATIVE_FIXED64_PREPARED_SESSION_SCHEMA_ID_V1",
        PREPARED_SESSION_SCHEMA_ID,
    )?;
    Ok(())
}

#[pyfunction]
fn native_fixed64_complete_pipeline_v1(_py: Python<'_>, _input: &PyDict) -> PyResult<PyObject> {
    Err(input_error(
        "complete pipeline v1 is retired because it cannot bind post-refinement admission; use v3",
    ))
}

#[pyfunction]
fn native_fixed64_complete_pipeline_v2(py: Python<'_>, input: &PyDict) -> PyResult<PyObject> {
    run_complete_pipeline(py, input, CompleteTransportVersion::V2)
}

#[pyfunction]
fn native_fixed64_complete_pipeline_v3(py: Python<'_>, input: &PyDict) -> PyResult<PyObject> {
    run_complete_pipeline(py, input, CompleteTransportVersion::V3)
}

#[pyfunction]
fn native_fixed64_prepare_session_v1(input: &PyDict) -> PyResult<NativeFixed64PreparedSession> {
    let (default_consumer, input) =
        parse_complete_pipeline_input(input, CompleteTransportVersion::V3)?;
    if !matches!(
        input.options.backend,
        Backend::CppCpuReference | Backend::RustCpu
    ) {
        return Err(input_error(
            "prepared session v1 is synthetic CPU-only; HIP device execution is unauthorized",
        ));
    }
    let projection_sha256 = input.prepared_input_projection_sha256.ok_or_else(|| {
        input_error("prepared session requires a bounded prepared-input projection")
    })?;
    let pipeline = input.create_pipeline().map_err(runtime_error)?;
    let pipeline_id = Fixed64Pipeline::profile_id().map_err(runtime_error)?;
    Ok(NativeFixed64PreparedSession {
        default_consumer,
        pipeline,
        input,
        prepared_session_receipt_sha256: prepared_session_receipt_sha256(
            projection_sha256,
            pipeline_id,
        ),
    })
}

#[pymethods]
impl NativeFixed64PreparedSession {
    #[getter]
    fn schema_id(&self) -> &'static str {
        PREPARED_SESSION_SCHEMA_ID
    }

    #[getter]
    fn default_consumer(&self) -> &'static str {
        self.default_consumer.id()
    }

    #[getter]
    fn backend(&self) -> &'static str {
        backend_id(self.pipeline.backend())
    }

    #[getter]
    fn prepared_input_projection_sha256(&self) -> PyResult<String> {
        self.input
            .prepared_input_projection_sha256
            .map(hex_digest)
            .ok_or_else(|| input_error("prepared session lost its bounded input projection"))
    }

    #[getter]
    fn prepared_session_receipt_sha256(&self) -> String {
        hex_digest(self.prepared_session_receipt_sha256)
    }

    fn describe(&self, py: Python<'_>) -> PyResult<PyObject> {
        let bounds = self.input.prepared_input_bounds.ok_or_else(|| {
            input_error("prepared session lost its bounded input cardinality evidence")
        })?;
        let output = PyDict::new(py);
        output.set_item("schema_id", PREPARED_SESSION_SCHEMA_ID)?;
        output.set_item(
            "pipeline_id",
            Fixed64Pipeline::profile_id().map_err(runtime_error)?,
        )?;
        output.set_item("default_consumer", self.default_consumer.id())?;
        output.set_item("backend", backend_id(self.pipeline.backend()))?;
        output.set_item("candidate_denominator", 64)?;
        output.set_item("ligand_atom_count", bounds.ligand_atom_count)?;
        output.set_item("receptor_atom_count", bounds.receptor_atom_count)?;
        output.set_item(
            "exact_cartesian_pair_count",
            bounds.exact_cartesian_pair_count,
        )?;
        output.set_item("prepared_input_scalar_count", bounds.scalar_count)?;
        output.set_item(
            "prepared_input_scalar_limit",
            MAX_PREPARED_INPUT_SCALAR_COUNT,
        )?;
        output.set_item(
            "prepared_input_projection_sha256",
            self.prepared_input_projection_sha256()?,
        )?;
        output.set_item(
            "prepared_session_receipt_sha256",
            self.prepared_session_receipt_sha256(),
        )?;
        output.set_item("test_only", true)?;
        output.set_item("persistent_native_context", true)?;
        output.set_item("context_reused_across_runs", true)?;
        output.set_item("scientific_result_cached", false)?;
        output.set_item("session_thread_confined", true)?;
        output.set_item("result_dependent_input_consumed", false)?;
        output.set_item("reservation_authorized", false)?;
        output.set_item("molecular_execution_authorized", false)?;
        output.set_item("benchmark_execution_authorized", false)?;
        output.set_item("scientific_claim_authorized", false)?;
        output.set_item("hip_device_execution_authorized", false)?;
        output.set_item("existing_rank_auto_change_authorized", false)?;
        output.set_item("customer_pose_emission_authorized", false)?;
        output.set_item("production_claim_authorized", false)?;
        Ok(output.into())
    }

    #[pyo3(signature = (consumer=None))]
    fn run(&self, py: Python<'_>, consumer: Option<&str>) -> PyResult<PyObject> {
        let consumer = consumer
            .map(Consumer::parse)
            .transpose()?
            .unwrap_or(self.default_consumer);
        // The native pipeline is explicitly thread-confined by its context
        // lease. PyO3's unsendable class guard keeps every execution on the
        // creating Python thread, while repeated calls reuse the exact handle.
        let receipt = self.input.run(&self.pipeline).map_err(runtime_error)?;
        receipt_to_python(
            py,
            &receipt,
            consumer,
            CompleteTransportVersion::V3,
            self.input.prepared_input_bounds,
            self.input.prepared_input_projection_sha256,
        )
    }
}

fn run_complete_pipeline(
    py: Python<'_>,
    input: &PyDict,
    transport: CompleteTransportVersion,
) -> PyResult<PyObject> {
    let (consumer, input) = parse_complete_pipeline_input(input, transport)?;
    let prepared_input_bounds = input.prepared_input_bounds;
    let prepared_input_projection_sha256 = input.prepared_input_projection_sha256;
    let receipt = py
        .allow_threads(move || input.run_once())
        .map_err(runtime_error)?;
    receipt_to_python(
        py,
        &receipt,
        consumer,
        transport,
        prepared_input_bounds,
        prepared_input_projection_sha256,
    )
}

fn parse_complete_pipeline_input(
    input: &PyDict,
    transport: CompleteTransportVersion,
) -> PyResult<(Consumer, OwnedCompletePipelineInput)> {
    if transport.is_bounded() {
        require_bounded_exact_keys(input, INPUT_KEYS, "native fixed64 complete input")?;
    } else {
        require_exact_keys(input, INPUT_KEYS, "native fixed64 complete input")?;
    }
    if dict_string(input, "schema_id")? != transport.input_schema_id() {
        return Err(input_error("complete input schema_id is unsupported"));
    }
    if !dict_exact_bool(input, "test_only")? {
        return Err(input_error(
            "complete Python bridge is synthetic/test-only and fails closed otherwise",
        ));
    }
    let consumer = Consumer::parse(dict_string(input, "consumer")?)?;
    let backend = dict_string(input, "backend")?;
    let device_ordinal = exact_i32(dict_value(input, "device_ordinal")?, "device_ordinal")?;
    let options = context_options(backend, device_ordinal)?;
    let prepared_input_bounds = transport
        .is_bounded()
        .then(|| bounded_prepared_input_preflight(input))
        .transpose()?;

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
    if prepared_input_bounds.is_some_and(|bounds| {
        bounds.ligand_atom_count != ligand_count || bounds.receptor_atom_count != receptor_count
    }) {
        return Err(input_error(
            "prepared input atom counts changed after bounded preflight",
        ));
    }
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
    // All Python-owned values have been copied above.  Parse the remaining
    // scalars before releasing the GIL, then keep proposal generation through
    // receipt production outside the Python critical section.
    let feature_geometry_inventory_sha256 =
        dict_digest_allow_zero(input, "feature_geometry_inventory_sha256")?;
    let rmsd_threshold_angstrom = dict_f64(input, "rmsd_threshold_angstrom")?;
    let predeclared_refinement_policy_sha256 =
        dict_digest(input, "predeclared_refinement_policy_sha256")?;
    let predeclared_post_refinement_admission_policy_sha256 =
        dict_digest(input, "predeclared_post_refinement_admission_policy_sha256")?;
    let prepared_input_projection_sha256 = prepared_input_bounds.map(|bounds| {
        prepared_input_projection_sha256(PreparedInputProjection {
            backend,
            device_ordinal,
            exact_evidence: &exact_evidence,
            identities: &identities,
            ligand_coordinates: &ligand_coordinates,
            ligand_radii: &ligand_radii,
            ligand_heavy: &ligand_heavy,
            ligand_charges: &ligand_charges,
            ligand_epsilon: &ligand_epsilon,
            ligand_hydrophobic: &ligand_hydrophobic,
            ligand_acceptor: &ligand_acceptor,
            ligand_donors: &ligand_donors,
            ligand_exclusions: &ligand_exclusions,
            rotors: &rotors,
            bonds: &bonds,
            chirality_centers: &chirality_centers,
            parent_atom_index: &parent_atom_index,
            rotatable_child_atom_index: &rotatable_child_atom_index,
            internal_pairs: &internal_pairs,
            receptor_coordinates: &receptor_coordinates,
            receptor_radii: &receptor_radii,
            receptor_charges: &receptor_charges,
            receptor_epsilon: &receptor_epsilon,
            receptor_hydrophobic: &receptor_hydrophobic,
            receptor_acceptor: &receptor_acceptor,
            receptor_donors: &receptor_donors,
            pocket_center,
            pocket_radius,
            pocket_normal,
            v7_sources: &v7_sources,
            conformer_sources: &conformer_sources,
            retained_sources: &retained_sources,
            feature_geometries: &feature_geometries,
            feature_geometry_inventory_sha256,
            rmsd_threshold_angstrom,
            candidate_modes: &candidate_modes,
            rigid_max_steps: &rigid_max_steps,
            torsion_eligible: &torsion_eligible,
            torsion_max_steps: &torsion_max_steps,
            baseline_torsion_angles: &baseline_torsion_angles,
            predeclared_refinement_policy_sha256,
            predeclared_post_refinement_admission_policy_sha256,
            bounds,
        })
    });
    Ok((
        consumer,
        OwnedCompletePipelineInput {
            options,
            exact_evidence,
            identities,
            ligand_coordinates,
            ligand_radii,
            ligand_heavy,
            ligand_charges,
            ligand_epsilon,
            ligand_hydrophobic,
            ligand_acceptor,
            ligand_donors,
            ligand_exclusions,
            rotors,
            bonds,
            chirality_centers,
            parent_atom_index,
            rotatable_child_atom_index,
            internal_pairs,
            receptor_coordinates,
            receptor_radii,
            receptor_charges,
            receptor_epsilon,
            receptor_hydrophobic,
            receptor_acceptor,
            receptor_donors,
            pocket_center,
            pocket_radius,
            exact_source,
            atomic_features,
            v7_sources,
            conformer_sources,
            retained_sources,
            feature_geometries,
            feature_geometry_inventory_sha256,
            pocket_normal,
            rmsd_threshold_angstrom,
            candidate_modes,
            rigid_max_steps,
            torsion_eligible,
            torsion_max_steps,
            baseline_torsion_angles,
            predeclared_refinement_policy_sha256,
            predeclared_post_refinement_admission_policy_sha256,
            prepared_input_bounds,
            prepared_input_projection_sha256,
        },
    ))
}

#[derive(Default)]
struct ScalarBudget {
    count: usize,
}

impl ScalarBudget {
    fn add(&mut self, count: usize, name: &str) -> PyResult<()> {
        self.count = self
            .count
            .checked_add(count)
            .ok_or_else(|| input_error(&format!("{name} scalar denominator overflows")))?;
        if self.count > MAX_PREPARED_INPUT_SCALAR_COUNT {
            return Err(input_error(&format!(
                "prepared input scalar count exceeds {MAX_PREPARED_INPUT_SCALAR_COUNT}"
            )));
        }
        Ok(())
    }
}

fn bounded_prepared_input_preflight(input: &PyDict) -> PyResult<PreparedInputBounds> {
    let mut budget = ScalarBudget::default();
    // device ordinal, pocket radius, RMSD threshold, and test-only flag are
    // fixed-width scalars; variable sequences are added below before copying.
    budget.add(4, "fixed prepared-input scalars")?;
    let ligand_atom_count = bounded_coordinate_rows(
        dict_value(input, "ligand_coordinates_angstrom")?,
        FIXED64_MAX_LIGAND_ATOMS,
        "ligand_coordinates_angstrom",
    )?;
    budget.add(
        ligand_atom_count
            .checked_mul(3)
            .ok_or_else(|| input_error("ligand coordinate denominator overflows"))?,
        "ligand_coordinates_angstrom",
    )?;
    let receptor_atom_count = bounded_coordinate_rows(
        dict_value(input, "receptor_coordinates_angstrom")?,
        FIXED64_MAX_RECEPTOR_ATOMS,
        "receptor_coordinates_angstrom",
    )?;
    budget.add(
        receptor_atom_count
            .checked_mul(3)
            .ok_or_else(|| input_error("receptor coordinate denominator overflows"))?,
        "receptor_coordinates_angstrom",
    )?;
    let exact_cartesian_pair_count = ligand_atom_count
        .checked_mul(receptor_atom_count)
        .ok_or_else(|| input_error("exact Cartesian pair denominator overflows"))?;
    let maximum_pair_count = FIXED64_MAX_LIGAND_ATOMS
        .checked_mul(FIXED64_MAX_RECEPTOR_ATOMS)
        .ok_or_else(|| input_error("fixed64 pair capacity overflows"))?;
    if exact_cartesian_pair_count > maximum_pair_count {
        return Err(input_error("exact Cartesian pair capacity exceeded"));
    }

    for name in [
        "ligand_vdw_radii_angstrom",
        "ligand_charge_elementary",
        "ligand_epsilon_kcal_per_mol",
    ] {
        bounded_f64_values(dict_value(input, name)?, ligand_atom_count, name)?;
        budget.add(ligand_atom_count, name)?;
    }
    for name in [
        "ligand_heavy_atom_mask",
        "ligand_hydrophobic_mask",
        "ligand_acceptor_mask",
    ] {
        bounded_bool_values(dict_value(input, name)?, ligand_atom_count, name)?;
        budget.add(ligand_atom_count, name)?;
    }
    for name in [
        "receptor_vdw_radii_angstrom",
        "receptor_charge_elementary",
        "receptor_epsilon_kcal_per_mol",
    ] {
        bounded_f64_values(dict_value(input, name)?, receptor_atom_count, name)?;
        budget.add(receptor_atom_count, name)?;
    }
    for name in ["receptor_hydrophobic_mask", "receptor_acceptor_mask"] {
        bounded_bool_values(dict_value(input, name)?, receptor_atom_count, name)?;
        budget.add(receptor_atom_count, name)?;
    }

    let ligand_pair_capacity = ligand_atom_count
        .checked_mul(ligand_atom_count.saturating_sub(1))
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| input_error("ligand pair capacity overflows"))?;
    for (name, width, capacity, atom_bound) in [
        ("ligand_donors", 2, ligand_atom_count, ligand_atom_count),
        (
            "receptor_donors",
            2,
            receptor_atom_count,
            receptor_atom_count,
        ),
        (
            "ligand_exclusions",
            2,
            ligand_pair_capacity,
            ligand_atom_count,
        ),
        ("rotor_quads", 4, ligand_atom_count, ligand_atom_count),
        ("bond_pairs", 2, ligand_pair_capacity, ligand_atom_count),
        ("chirality_centers", 4, ligand_atom_count, ligand_atom_count),
        ("internal_pairs", 2, ligand_pair_capacity, ligand_atom_count),
    ] {
        let row_count =
            bounded_index_rows(dict_value(input, name)?, width, capacity, atom_bound, name)?;
        budget.add(
            row_count
                .checked_mul(width)
                .ok_or_else(|| input_error(&format!("{name} scalar denominator overflows")))?,
            name,
        )?;
    }
    bounded_i32_values(
        dict_value(input, "parent_atom_index")?,
        ligand_atom_count,
        "parent_atom_index",
    )?;
    budget.add(ligand_atom_count, "parent_atom_index")?;
    let rotatable_child_count = bounded_u64_values(
        dict_value(input, "rotatable_child_atom_index")?,
        0,
        ligand_atom_count,
        "rotatable_child_atom_index",
    )?;
    budget.add(rotatable_child_count, "rotatable_child_atom_index")?;

    for name in ["pocket_center_angstrom", "pocket_normal"] {
        bounded_f64_values(dict_value(input, name)?, 3, name)?;
        budget.add(3, name)?;
    }
    for name in ["pocket_radius_angstrom", "rmsd_threshold_angstrom"] {
        exact_finite_f64(dict_value(input, name)?, name)?;
    }

    let v7_count = bounded_source_rows(
        dict_value(input, "v7_control_sources")?,
        INDEXED_SOURCE_KEYS,
        ligand_atom_count,
        MAX_V7_CONTROL_SOURCES,
        "v7_control_sources",
    )?;
    budget.add(
        source_scalar_count(v7_count, ligand_atom_count)?,
        "v7_control_sources",
    )?;
    let conformer_count = bounded_source_rows(
        dict_value(input, "conformer_sources")?,
        CONFORMER_SOURCE_KEYS,
        ligand_atom_count,
        MAX_CONFORMER_SOURCES,
        "conformer_sources",
    )?;
    budget.add(
        source_scalar_count(conformer_count, ligand_atom_count)?,
        "conformer_sources",
    )?;
    let retained_count = bounded_source_rows(
        dict_value(input, "retained_sources")?,
        INDEXED_SOURCE_KEYS,
        ligand_atom_count,
        MAX_RETAINED_SOURCES,
        "retained_sources",
    )?;
    budget.add(
        source_scalar_count(retained_count, ligand_atom_count)?,
        "retained_sources",
    )?;

    let feature_atom_index_count = bounded_feature_geometry_rows(
        dict_value(input, "feature_geometries")?,
        MAX_ATOMIC_FEATURES,
    )?;
    budget.add(feature_atom_index_count, "feature_geometries")?;

    bounded_string_values(dict_value(input, "candidate_modes")?, 64, "candidate_modes")?;
    budget.add(64, "candidate_modes")?;
    for name in ["rigid_max_steps", "torsion_max_steps"] {
        bounded_u64_values(dict_value(input, name)?, 64, 64, name)?;
        budget.add(64, name)?;
    }
    bounded_bool_values(
        dict_value(input, "proposal_is_torsion_eligible")?,
        64,
        "proposal_is_torsion_eligible",
    )?;
    budget.add(64, "proposal_is_torsion_eligible")?;
    let baseline_count = ligand_atom_count
        .checked_mul(64)
        .ok_or_else(|| input_error("baseline torsion denominator overflows"))?;
    bounded_f64_values(
        dict_value(input, "baseline_torsion_angles_radians")?,
        baseline_count,
        "baseline_torsion_angles_radians",
    )?;
    budget.add(baseline_count, "baseline_torsion_angles_radians")?;

    Ok(PreparedInputBounds {
        ligand_atom_count,
        receptor_atom_count,
        exact_cartesian_pair_count,
        scalar_count: budget.count,
    })
}

fn require_bounded_exact_keys(value: &PyDict, expected: &[&str], name: &str) -> PyResult<()> {
    if value.downcast_exact::<PyDict>().is_err() {
        return Err(input_error(&format!("{name} must be an exact dict")));
    }
    if value.len() != expected.len() {
        return Err(input_error(&format!("{name} has an invalid key schema")));
    }
    let maximum_key_bytes = expected.iter().map(|key| key.len()).max().unwrap_or(0);
    for key in value.keys().iter() {
        let key = key
            .downcast_exact::<PyString>()
            .map_err(|_| input_error(&format!("{name} keys must be exact strings")))?;
        let text = key
            .to_str()
            .map_err(|_| input_error(&format!("{name} keys must be valid UTF-8")))?;
        if text.len() > maximum_key_bytes {
            return Err(input_error(&format!(
                "{name} key length exceeds its schema"
            )));
        }
    }
    require_exact_keys(value, expected, name)
}

fn bounded_coordinate_rows(value: &PyAny, maximum: usize, name: &str) -> PyResult<usize> {
    if let Ok(array) = value.extract::<PyReadonlyArray2<'_, f64>>() {
        let view = array.as_array();
        let count = view.nrows();
        if !(1..=maximum).contains(&count) || view.ncols() != 3 {
            return Err(input_error(&format!(
                "{name} must have bounded shape [1..={maximum},3]"
            )));
        }
        if view.iter().any(|component| !component.is_finite()) {
            return Err(input_error(&format!("{name} must be finite")));
        }
        return Ok(count);
    }
    let rows = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be a float64 array or exact list")))?;
    if !(1..=maximum).contains(&rows.len()) {
        return Err(input_error(&format!(
            "{name} must have bounded shape [1..={maximum},3]"
        )));
    }
    for (row_index, row) in rows.iter().enumerate() {
        let components = row
            .downcast_exact::<PyList>()
            .map_err(|_| input_error(&format!("{name}[{row_index}] must be an exact list")))?;
        if components.len() != 3 {
            return Err(input_error(&format!(
                "{name} rows must contain exactly 3 values"
            )));
        }
        for component in components.iter() {
            exact_finite_f64(component, name)?;
        }
    }
    Ok(rows.len())
}

fn bounded_f64_values(value: &PyAny, expected: usize, name: &str) -> PyResult<()> {
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, f64>>() {
        let values = array.as_slice()?;
        if values.len() != expected || values.iter().any(|item| !item.is_finite()) {
            return Err(input_error(&format!(
                "{name} length or finite-value contract failed"
            )));
        }
        return Ok(());
    }
    let values = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be a float64 array or exact list")))?;
    if values.len() != expected {
        return Err(input_error(&format!("{name} length mismatch")));
    }
    for item in values.iter() {
        exact_finite_f64(item, name)?;
    }
    Ok(())
}

fn exact_finite_f64(value: &PyAny, name: &str) -> PyResult<f64> {
    if value.downcast_exact::<PyFloat>().is_err() && value.downcast_exact::<PyLong>().is_err() {
        return Err(input_error(&format!(
            "{name} values must be exact int or float and must not be bool"
        )));
    }
    let value = value
        .extract::<f64>()
        .map_err(|_| input_error(&format!("{name} values must be numeric")))?;
    if !value.is_finite() {
        return Err(input_error(&format!("{name} values must be finite")));
    }
    Ok(value)
}

fn bounded_bool_values(value: &PyAny, expected: usize, name: &str) -> PyResult<()> {
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, u8>>() {
        let values = array.as_slice()?;
        if values.len() != expected || values.iter().any(|item| *item > 1) {
            return Err(input_error(&format!(
                "{name} must be a bounded binary mask"
            )));
        }
        return Ok(());
    }
    let values = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be a uint8 array or exact list")))?;
    if values.len() != expected || values.iter().any(|item| !item.is_instance_of::<PyBool>()) {
        return Err(input_error(&format!("{name} must be an exact bool list")));
    }
    Ok(())
}

fn bounded_index_rows(
    value: &PyAny,
    width: usize,
    maximum_rows: usize,
    atom_bound: usize,
    name: &str,
) -> PyResult<usize> {
    let rows = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    if rows.len() > maximum_rows {
        return Err(input_error(&format!(
            "{name} row count exceeds {maximum_rows}"
        )));
    }
    for (row_index, row) in rows.iter().enumerate() {
        let values = row
            .downcast_exact::<PyList>()
            .map_err(|_| input_error(&format!("{name}[{row_index}] must be an exact list")))?;
        if values.len() != width {
            return Err(input_error(&format!(
                "{name}[{row_index}] must contain exactly {width} indices"
            )));
        }
        for item in values.iter() {
            let index = item
                .downcast_exact::<PyLong>()
                .map_err(|_| input_error(&format!("{name} indices must be exact integers")))?
                .extract::<usize>()
                .map_err(|_| {
                    input_error(&format!(
                        "{name} indices must be exact non-negative integers"
                    ))
                })?;
            if index >= atom_bound {
                return Err(input_error(&format!("{name} atom index is out of bounds")));
            }
        }
    }
    Ok(rows.len())
}

fn bounded_i32_values(value: &PyAny, expected: usize, name: &str) -> PyResult<()> {
    let values = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    if values.len() != expected {
        return Err(input_error(&format!("{name} length mismatch")));
    }
    for item in values.iter() {
        exact_i32(item, name)?;
    }
    Ok(())
}

fn bounded_u64_values(
    value: &PyAny,
    minimum: usize,
    maximum: usize,
    name: &str,
) -> PyResult<usize> {
    let values = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    if !(minimum..=maximum).contains(&values.len()) {
        return Err(input_error(&format!(
            "{name} length must be in [{minimum},{maximum}]"
        )));
    }
    for item in values.iter() {
        if item
            .downcast_exact::<PyLong>()
            .ok()
            .and_then(|value| value.extract::<u64>().ok())
            .is_none()
        {
            return Err(input_error(&format!(
                "{name} values must be exact non-negative integers"
            )));
        }
    }
    Ok(values.len())
}

fn bounded_string_values(value: &PyAny, expected: usize, name: &str) -> PyResult<()> {
    let values = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    if values.len() != expected
        || values
            .iter()
            .any(|item| item.downcast_exact::<PyString>().is_err())
    {
        return Err(input_error(&format!(
            "{name} must contain exactly {expected} strings"
        )));
    }
    Ok(())
}

fn bounded_source_rows(
    value: &PyAny,
    expected_keys: &[&str],
    ligand_atom_count: usize,
    maximum_rows: usize,
    name: &str,
) -> PyResult<usize> {
    let rows = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    if rows.len() > maximum_rows {
        return Err(input_error(&format!(
            "{name} row count exceeds {maximum_rows}"
        )));
    }
    for (offset, item) in rows.iter().enumerate() {
        let row = item
            .downcast_exact::<PyDict>()
            .map_err(|_| input_error(&format!("{name}[{offset}] must be an exact dict")))?;
        require_bounded_exact_keys(row, expected_keys, name)?;
        let identity_key = if expected_keys == INDEXED_SOURCE_KEYS {
            "source_index"
        } else {
            "rank"
        };
        if dict_value(row, identity_key)?
            .downcast_exact::<PyLong>()
            .ok()
            .and_then(|value| value.extract::<u32>().ok())
            .is_none()
        {
            return Err(input_error(&format!(
                "{name}[{offset}].{identity_key} must be an exact non-negative integer"
            )));
        }
        let count = bounded_coordinate_rows(
            dict_value(row, "coordinates_angstrom")?,
            ligand_atom_count,
            &format!("{name}[{offset}].coordinates_angstrom"),
        )?;
        if count != ligand_atom_count {
            return Err(input_error(&format!(
                "{name}[{offset}] coordinates must match ligand atom count"
            )));
        }
    }
    Ok(rows.len())
}

fn source_scalar_count(source_count: usize, ligand_atom_count: usize) -> PyResult<usize> {
    source_count
        .checked_mul(
            ligand_atom_count
                .checked_mul(3)
                .and_then(|value| value.checked_add(1))
                .ok_or_else(|| input_error("source scalar denominator overflows"))?,
        )
        .ok_or_else(|| input_error("source scalar denominator overflows"))
}

fn bounded_feature_geometry_rows(value: &PyAny, maximum_rows: usize) -> PyResult<usize> {
    let rows = value
        .downcast_exact::<PyList>()
        .map_err(|_| input_error("feature_geometries must be an exact list"))?;
    if rows.len() > maximum_rows {
        return Err(input_error(&format!(
            "feature_geometries row count exceeds {maximum_rows}"
        )));
    }
    let mut atom_index_count = 0_usize;
    for (offset, item) in rows.iter().enumerate() {
        let row = item.downcast_exact::<PyDict>().map_err(|_| {
            input_error(&format!(
                "feature_geometries[{offset}] must be an exact dict"
            ))
        })?;
        require_bounded_exact_keys(row, FEATURE_GEOMETRY_KEYS, "feature_geometries")?;
        feature_kind(dict_string(row, "kind")?)?;
        let count = bounded_u64_values(
            dict_value(row, "atom_indices")?,
            1,
            MAX_FEATURE_ATOM_INDICES,
            "feature_geometries.atom_indices",
        )?;
        atom_index_count = atom_index_count
            .checked_add(count)
            .ok_or_else(|| input_error("feature geometry atom-index denominator overflows"))?;
        if atom_index_count > MAX_PREPARED_INPUT_SCALAR_COUNT {
            return Err(input_error(
                "feature geometry atom-index scalar capacity exceeded",
            ));
        }
    }
    Ok(atom_index_count)
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
    if value.downcast_exact::<PyLong>().is_err() {
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

struct PreparedInputProjection<'a> {
    backend: &'a str,
    device_ordinal: i32,
    exact_evidence: &'a Fixed64ExactSourceEvidence,
    identities: &'a Fixed64Identities,
    ligand_coordinates: &'a Coordinates,
    ligand_radii: &'a [f64],
    ligand_heavy: &'a [u8],
    ligand_charges: &'a [f64],
    ligand_epsilon: &'a [f64],
    ligand_hydrophobic: &'a [u8],
    ligand_acceptor: &'a [u8],
    ligand_donors: &'a [Fixed64Donor],
    ligand_exclusions: &'a [Fixed64Pair],
    rotors: &'a [Fixed64Rotor],
    bonds: &'a [Fixed64Pair],
    chirality_centers: &'a [Fixed64ChiralityCenter],
    parent_atom_index: &'a [i32],
    rotatable_child_atom_index: &'a [u64],
    internal_pairs: &'a [Fixed64Pair],
    receptor_coordinates: &'a Coordinates,
    receptor_radii: &'a [f64],
    receptor_charges: &'a [f64],
    receptor_epsilon: &'a [f64],
    receptor_hydrophobic: &'a [u8],
    receptor_acceptor: &'a [u8],
    receptor_donors: &'a [Fixed64Donor],
    pocket_center: [f64; 3],
    pocket_radius: f64,
    pocket_normal: [f64; 3],
    v7_sources: &'a [IndexedSource],
    conformer_sources: &'a [ConformerSource],
    retained_sources: &'a [IndexedSource],
    feature_geometries: &'a [FeatureGeometry],
    feature_geometry_inventory_sha256: [u8; 32],
    rmsd_threshold_angstrom: f64,
    candidate_modes: &'a [Fixed64RefinementMode],
    rigid_max_steps: &'a [u64],
    torsion_eligible: &'a [u8],
    torsion_max_steps: &'a [u64],
    baseline_torsion_angles: &'a [f64],
    predeclared_refinement_policy_sha256: [u8; 32],
    predeclared_post_refinement_admission_policy_sha256: [u8; 32],
    bounds: PreparedInputBounds,
}

struct PreparedProjectionHasher {
    hash: Sha256,
}

impl PreparedProjectionHasher {
    fn new() -> Self {
        let mut hash = Sha256::new();
        hash.update(PREPARED_INPUT_PROJECTION_DOMAIN);
        Self { hash }
    }

    fn field(&mut self, name: &str) {
        self.hash.update((name.len() as u64).to_be_bytes());
        self.hash.update(name.as_bytes());
    }

    fn usize(&mut self, value: usize) {
        self.hash.update((value as u64).to_be_bytes());
    }

    fn u64(&mut self, value: u64) {
        self.hash.update(value.to_be_bytes());
    }

    fn i32(&mut self, value: i32) {
        self.hash.update(value.to_be_bytes());
    }

    fn byte(&mut self, value: u8) {
        self.hash.update([value]);
    }

    fn f64(&mut self, value: f64) {
        self.hash.update(value.to_bits().to_be_bytes());
    }

    fn digest(&mut self, value: [u8; 32]) {
        self.hash.update(value);
    }

    fn string(&mut self, value: &str) {
        self.usize(value.len());
        self.hash.update(value.as_bytes());
    }

    fn f64_slice(&mut self, name: &str, values: &[f64]) {
        self.field(name);
        self.usize(values.len());
        for value in values {
            self.f64(*value);
        }
    }

    fn u8_slice(&mut self, name: &str, values: &[u8]) {
        self.field(name);
        self.usize(values.len());
        self.hash.update(values);
    }

    fn u64_slice(&mut self, name: &str, values: &[u64]) {
        self.field(name);
        self.usize(values.len());
        for value in values {
            self.u64(*value);
        }
    }

    fn i32_slice(&mut self, name: &str, values: &[i32]) {
        self.field(name);
        self.usize(values.len());
        for value in values {
            self.i32(*value);
        }
    }

    fn coordinates(&mut self, name: &str, value: &Coordinates) {
        self.field(name);
        self.usize(value.x.len());
        for index in 0..value.x.len() {
            self.f64(value.x[index]);
            self.f64(value.y[index]);
            self.f64(value.z[index]);
        }
    }

    fn donors(&mut self, name: &str, values: &[Fixed64Donor]) {
        self.field(name);
        self.usize(values.len());
        for value in values {
            self.u64(value.donor_atom_index);
            self.u64(value.hydrogen_atom_index);
        }
    }

    fn pairs(&mut self, name: &str, values: &[Fixed64Pair]) {
        self.field(name);
        self.usize(values.len());
        for value in values {
            self.u64(value.atom_i);
            self.u64(value.atom_j);
        }
    }

    fn sources(&mut self, name: &str, values: &[IndexedSource]) {
        self.field(name);
        self.usize(values.len());
        for value in values {
            self.u64(u64::from(value.source_index));
            self.source(&value.source);
        }
    }

    fn source(&mut self, value: &OwnedSource) {
        self.digest(value.evidence.receipt_sha256);
        self.digest(value.evidence.proposal_sha256);
        self.digest(value.evidence.coordinate_sha256);
        self.usize(value.coordinates.x.len());
        for index in 0..value.coordinates.x.len() {
            self.f64(value.coordinates.x[index]);
            self.f64(value.coordinates.y[index]);
            self.f64(value.coordinates.z[index]);
        }
    }

    fn finish(self) -> [u8; 32] {
        self.hash.finalize().into()
    }
}

fn prepared_input_projection_sha256(value: PreparedInputProjection<'_>) -> [u8; 32] {
    let mut hash = PreparedProjectionHasher::new();
    hash.field("schema_id");
    hash.string(INPUT_SCHEMA_ID);
    hash.field("backend");
    hash.string(value.backend);
    hash.field("device_ordinal");
    hash.i32(value.device_ordinal);

    for (name, digest) in [
        (
            "authority_input_receipt_sha256",
            value.identities.authority_input_receipt_sha256,
        ),
        (
            "source_receipt_sha256",
            value.exact_evidence.source_receipt_sha256,
        ),
        ("proposal_sha256", value.exact_evidence.proposal_sha256),
        (
            "prepared_ligand_topology_sha256",
            value.exact_evidence.prepared_ligand_topology_sha256,
        ),
        (
            "prepared_receptor_topology_sha256",
            value.exact_evidence.prepared_receptor_topology_sha256,
        ),
        (
            "receptor_system_sha256",
            value.identities.receptor_system_sha256,
        ),
        (
            "ligand_system_sha256",
            value.identities.ligand_system_sha256,
        ),
        (
            "backend_receipt_sha256",
            value.identities.backend_receipt_sha256,
        ),
        (
            "validity_scorer_context_receipt_sha256",
            value.identities.validity_scorer_context_receipt_sha256,
        ),
        (
            "contact_policy_sha256",
            value.identities.contact_policy_sha256,
        ),
    ] {
        hash.field(name);
        hash.digest(digest);
    }

    hash.coordinates("ligand_coordinates_angstrom", value.ligand_coordinates);
    hash.f64_slice("ligand_vdw_radii_angstrom", value.ligand_radii);
    hash.u8_slice("ligand_heavy_atom_mask", value.ligand_heavy);
    hash.f64_slice("ligand_charge_elementary", value.ligand_charges);
    hash.f64_slice("ligand_epsilon_kcal_per_mol", value.ligand_epsilon);
    hash.u8_slice("ligand_hydrophobic_mask", value.ligand_hydrophobic);
    hash.u8_slice("ligand_acceptor_mask", value.ligand_acceptor);
    hash.donors("ligand_donors", value.ligand_donors);
    hash.pairs("ligand_exclusions", value.ligand_exclusions);
    hash.field("rotor_quads");
    hash.usize(value.rotors.len());
    for rotor in value.rotors {
        hash.u64(rotor.atom_i);
        hash.u64(rotor.atom_j);
        hash.u64(rotor.atom_k);
        hash.u64(rotor.atom_l);
    }
    hash.pairs("bond_pairs", value.bonds);
    hash.field("chirality_centers");
    hash.usize(value.chirality_centers.len());
    for center in value.chirality_centers {
        hash.u64(center.center_atom);
        hash.u64(center.atom_i);
        hash.u64(center.atom_j);
        hash.u64(center.atom_k);
    }
    hash.i32_slice("parent_atom_index", value.parent_atom_index);
    hash.u64_slice(
        "rotatable_child_atom_index",
        value.rotatable_child_atom_index,
    );
    hash.pairs("internal_pairs", value.internal_pairs);

    hash.coordinates("receptor_coordinates_angstrom", value.receptor_coordinates);
    hash.f64_slice("receptor_vdw_radii_angstrom", value.receptor_radii);
    hash.f64_slice("receptor_charge_elementary", value.receptor_charges);
    hash.f64_slice("receptor_epsilon_kcal_per_mol", value.receptor_epsilon);
    hash.u8_slice("receptor_hydrophobic_mask", value.receptor_hydrophobic);
    hash.u8_slice("receptor_acceptor_mask", value.receptor_acceptor);
    hash.donors("receptor_donors", value.receptor_donors);

    hash.field("pocket_center_angstrom");
    for component in value.pocket_center {
        hash.f64(component);
    }
    hash.field("pocket_radius_angstrom");
    hash.f64(value.pocket_radius);
    hash.field("pocket_normal");
    for component in value.pocket_normal {
        hash.f64(component);
    }

    hash.sources("v7_control_sources", value.v7_sources);
    hash.field("conformer_sources");
    hash.usize(value.conformer_sources.len());
    for source in value.conformer_sources {
        hash.byte(source.rank);
        hash.source(&source.source);
    }
    hash.sources("retained_sources", value.retained_sources);
    hash.field("feature_geometries");
    hash.usize(value.feature_geometries.len());
    for feature in value.feature_geometries {
        hash.byte(feature_kind_id(feature.kind));
        hash.digest(feature.allocation_feature_receipt_sha256);
        hash.digest(feature.feature_geometry_receipt_sha256);
        hash.u64_slice("atom_indices", &feature.atom_indices);
    }
    hash.field("feature_geometry_inventory_sha256");
    hash.digest(value.feature_geometry_inventory_sha256);
    hash.field("rmsd_threshold_angstrom");
    hash.f64(value.rmsd_threshold_angstrom);

    hash.field("candidate_modes");
    hash.usize(value.candidate_modes.len());
    for mode in value.candidate_modes {
        hash.byte(refinement_mode_id(*mode));
    }
    hash.u64_slice("rigid_max_steps", value.rigid_max_steps);
    hash.u8_slice("proposal_is_torsion_eligible", value.torsion_eligible);
    hash.u64_slice("torsion_max_steps", value.torsion_max_steps);
    hash.f64_slice(
        "baseline_torsion_angles_radians",
        value.baseline_torsion_angles,
    );
    hash.field("predeclared_refinement_policy_sha256");
    hash.digest(value.predeclared_refinement_policy_sha256);
    hash.field("predeclared_post_refinement_admission_policy_sha256");
    hash.digest(value.predeclared_post_refinement_admission_policy_sha256);
    hash.field("test_only");
    hash.byte(1);
    hash.field("bounded_ligand_atom_count");
    hash.usize(value.bounds.ligand_atom_count);
    hash.field("bounded_receptor_atom_count");
    hash.usize(value.bounds.receptor_atom_count);
    hash.field("exact_cartesian_pair_count");
    hash.usize(value.bounds.exact_cartesian_pair_count);
    hash.field("prepared_input_scalar_count");
    hash.usize(value.bounds.scalar_count);
    hash.finish()
}

const fn refinement_mode_id(value: Fixed64RefinementMode) -> u8 {
    match value {
        Fixed64RefinementMode::V2Translation => 0,
        Fixed64RefinementMode::V3TranslationRotation => 1,
        Fixed64RefinementMode::V6BaselineV2Lane => 2,
        Fixed64RefinementMode::V6BaselineV3Lane => 3,
    }
}

fn prepared_input_receipt_sha256(
    projection_sha256: [u8; 32],
    pipeline_receipt_sha256: [u8; 32],
) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(PREPARED_INPUT_RECEIPT_DOMAIN);
    hash.update(projection_sha256);
    hash.update(pipeline_receipt_sha256);
    hash.finalize().into()
}

fn prepared_session_receipt_sha256(projection_sha256: [u8; 32], pipeline_id: &str) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(PREPARED_SESSION_RECEIPT_DOMAIN);
    hash.update((pipeline_id.len() as u64).to_be_bytes());
    hash.update(pipeline_id.as_bytes());
    hash.update(projection_sha256);
    hash.finalize().into()
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

fn receipt_graph_to_python(
    py: Python<'_>,
    receipts: &betelgeuze_runtime::Fixed64BatchReceipts,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    for (name, digest) in [
        (
            "allocation_inventory_sha256",
            receipts.allocation_inventory_sha256,
        ),
        (
            "allocation_receipt_sha256",
            receipts.allocation_receipt_sha256,
        ),
        (
            "source_bundle_receipt_sha256",
            receipts.source_bundle_receipt_sha256,
        ),
        (
            "geometric_admission_batch_receipt_sha256",
            receipts.geometric_admission_batch_receipt_sha256,
        ),
        (
            "admission_context_receipt_sha256",
            receipts.admission_context_receipt_sha256,
        ),
        (
            "refinement_context_receipt_sha256",
            receipts.refinement_context_receipt_sha256,
        ),
        (
            "scorer_context_receipt_sha256",
            receipts.scorer_context_receipt_sha256,
        ),
        (
            "validity_context_receipt_sha256",
            receipts.validity_context_receipt_sha256,
        ),
        (
            "component_binding_receipt_sha256",
            receipts.component_binding_receipt_sha256,
        ),
        (
            "producer_batch_receipt_sha256",
            receipts.producer_batch_receipt_sha256,
        ),
        (
            "refinement_policy_receipt_sha256",
            receipts.refinement_policy_receipt_sha256,
        ),
        (
            "refinement_batch_receipt_sha256",
            receipts.refinement_batch_receipt_sha256,
        ),
        (
            "post_admission_policy_receipt_sha256",
            receipts.post_admission_policy_receipt_sha256,
        ),
        (
            "post_admission_batch_receipt_sha256",
            receipts.post_admission_batch_receipt_sha256,
        ),
        (
            "scorer_batch_receipt_sha256",
            receipts.scorer_batch_receipt_sha256,
        ),
        (
            "validity_batch_receipt_sha256",
            receipts.validity_batch_receipt_sha256,
        ),
        (
            "ranking_batch_receipt_sha256",
            receipts.ranking_batch_receipt_sha256,
        ),
        (
            "cluster_batch_receipt_sha256",
            receipts.cluster_batch_receipt_sha256,
        ),
        (
            "pipeline_batch_receipt_sha256",
            receipts.pipeline_batch_receipt_sha256,
        ),
    ] {
        output.set_item(name, hex_digest(digest))?;
    }
    Ok(output.into())
}

fn receipt_to_python(
    py: Python<'_>,
    receipt: &Fixed64PipelineReceipt,
    consumer: Consumer,
    transport: CompleteTransportVersion,
    prepared_input_bounds: Option<PreparedInputBounds>,
    prepared_input_projection_sha256: Option<[u8; 32]>,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    output.set_item("schema_id", transport.evidence_schema_id())?;
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
    output.set_item("post_admitted_count", receipt.post_admitted_count)?;
    output.set_item("post_rejected_count", receipt.post_rejected_count)?;
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
    if transport.is_bounded() {
        let bounds = prepared_input_bounds.ok_or_else(|| {
            input_error("bounded prepared-input evidence is missing cardinality bounds")
        })?;
        let projection_sha256 = prepared_input_projection_sha256.ok_or_else(|| {
            input_error("bounded prepared-input evidence is missing its native projection")
        })?;
        output.set_item("prepared_input_bounded", true)?;
        output.set_item(
            "prepared_input_projection_sha256",
            hex_digest(projection_sha256),
        )?;
        output.set_item(
            "prepared_input_receipt_sha256",
            hex_digest(prepared_input_receipt_sha256(
                projection_sha256,
                receipt.receipts.pipeline_batch_receipt_sha256,
            )),
        )?;
        output.set_item(
            "exact_cartesian_pair_count",
            bounds.exact_cartesian_pair_count,
        )?;
        output.set_item("prepared_input_scalar_count", bounds.scalar_count)?;
        output.set_item(
            "prepared_input_scalar_limit",
            MAX_PREPARED_INPUT_SCALAR_COUNT,
        )?;
    }
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
        "post_refinement_admission_receipt_sha256",
        hex_digest(receipt.receipts.post_admission_batch_receipt_sha256),
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
    output.set_item(
        "scientific_projection_sha256",
        hex_digest(receipt.scientific_projection_sha256),
    )?;
    output.set_item(
        "receipt_graph",
        receipt_graph_to_python(py, &receipt.receipts)?,
    )?;
    output.set_item("primary_slot_indices", &receipt.primary_slot_indices)?;
    output.set_item("valid_slot_indices", &receipt.valid_slot_indices)?;
    output.set_item(
        "representative_slot_indices",
        &receipt.representative_slot_indices,
    )?;
    output.set_item("top_k_slot_indices", &receipt.top_k_slot_indices)?;
    output.set_item(
        "result_dependent_input_consumed",
        receipt.authority.result_dependent_input_consumed,
    )?;
    output.set_item("fallback_allowed", receipt.authority.fallback_allowed)?;
    output.set_item(
        "multi_anchor_consumed",
        receipt.authority.multi_anchor_consumed,
    )?;
    output.set_item(
        "denominator_preserved",
        receipt.authority.denominator_preserved,
    )?;
    output.set_item("evidence_display_authorized", true)?;
    output.set_item(
        "operator_second_opinion_authorized",
        consumer.operator_second_opinion_authorized(),
    )?;
    output.set_item(
        "reservation_authorized",
        receipt.authority.reservation_authorized,
    )?;
    output.set_item(
        "molecular_execution_authorized",
        receipt.authority.molecular_execution_authorized,
    )?;
    output.set_item(
        "benchmark_execution_authorized",
        receipt.authority.benchmark_execution_authorized,
    )?;
    output.set_item(
        "existing_rank_auto_change_authorized",
        receipt.authority.existing_rank_auto_change_authorized,
    )?;
    output.set_item(
        "customer_pose_emission_authorized",
        receipt.authority.customer_pose_emission_authorized,
    )?;
    output.set_item(
        "production_claim_authorized",
        receipt.authority.production_claim_authorized,
    )?;
    output.set_item(
        "scientific_claim_authorized",
        receipt.authority.scientific_claim_authorized,
    )?;

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
    row.set_item("component_failure_code", producer.component_failure_code)?;
    row.set_item("producer_backend", backend_id(producer.backend))?;
    row.set_item("ligand_atom_count", producer.ligand_atom_count)?;
    row.set_item("coordinate_offset", producer.coordinate_offset)?;
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
    for (name, digest) in [
        (
            "allocation_slot_receipt_sha256",
            producer.allocation_slot_receipt_sha256,
        ),
        (
            "source_payload_receipt_sha256",
            producer.source_payload_receipt_sha256,
        ),
        ("source_proposal_sha256", producer.source_proposal_sha256),
        (
            "source_coordinate_sha256",
            producer.source_coordinate_sha256,
        ),
        (
            "placement_receipt_sha256",
            producer.placement_receipt_sha256,
        ),
        ("output_proposal_sha256", producer.output_proposal_sha256),
        (
            "output_coordinate_sha256",
            producer.output_coordinate_sha256,
        ),
    ] {
        row.set_item(name, hex_digest(digest))?;
    }
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
        "penetrating_atom_count",
        producer.geometric.unique_ligand_penetration_atom_count,
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
    row.set_item(
        "post_refinement_geometric_admission",
        geometric_to_python(py, &receipt.post_admission_rows[slot])?,
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
        "rotation_orthogonality_max_error",
        validity.rotation_orthogonality_max_error,
    )?;
    validity_output.set_item("rotation_determinant", validity.rotation_determinant)?;
    validity_output.set_item(
        "max_bond_length_delta_angstrom",
        validity.max_bond_length_delta_angstrom,
    )?;
    validity_output.set_item(
        "minimum_ligand_nonbonded_distance_angstrom",
        validity.minimum_ligand_nonbonded_distance_angstrom,
    )?;
    validity_output.set_item(
        "evaluated_ligand_nonbonded_pair_count",
        validity.evaluated_ligand_nonbonded_pair_count,
    )?;
    validity_output.set_item(
        "excluded_ligand_pair_count",
        validity.excluded_ligand_pair_count,
    )?;
    validity_output.set_item(
        "minimum_receptor_ligand_distance_angstrom",
        validity.minimum_receptor_ligand_distance_angstrom,
    )?;
    validity_output.set_item(
        "evaluated_receptor_ligand_pair_count",
        validity.evaluated_receptor_ligand_pair_count,
    )?;
    validity_output.set_item(
        "minimum_declared_chiral_volume",
        validity.minimum_declared_chiral_volume,
    )?;
    validity_output.set_item(
        "declared_chirality_center_count",
        validity.declared_chirality_center_count,
    )?;
    validity_output.set_item(
        "maximum_pocket_center_distance_angstrom",
        validity.maximum_pocket_center_distance_angstrom,
    )?;
    validity_output.set_item(
        "element_vdw_ligand_pair_count",
        validity.element_vdw_ligand_pair_count,
    )?;
    validity_output.set_item(
        "element_vdw_ligand_severe_overlap_count",
        validity.element_vdw_ligand_severe_overlap_count,
    )?;
    validity_output.set_item(
        "element_vdw_ligand_minimum_distance_angstrom",
        validity.element_vdw_ligand_minimum_distance_angstrom,
    )?;
    validity_output.set_item(
        "element_vdw_ligand_minimum_ratio",
        validity.element_vdw_ligand_minimum_ratio,
    )?;
    validity_output.set_item(
        "element_vdw_receptor_candidate_pair_count",
        validity.element_vdw_receptor_candidate_pair_count,
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
        "element_vdw_receptor_cell_count",
        validity.element_vdw_receptor_cell_count,
    )?;
    validity_output.set_item(
        "element_vdw_receptor_minimum_distance_angstrom",
        validity.element_vdw_receptor_minimum_distance_angstrom,
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
    cluster_output.set_item("stable_valid_rank", cluster.stable_valid_rank)?;
    cluster_output.set_item("cluster_id", cluster.cluster_id)?;
    cluster_output.set_item(
        "representative_slot_index",
        cluster.representative_slot_index,
    )?;
    cluster_output.set_item("cluster_rank", cluster.cluster_rank)?;
    cluster_output.set_item("top_k_rank", cluster.top_k_rank)?;
    cluster_output.set_item("cluster_size", cluster.cluster_size)?;
    cluster_output.set_item(
        "direct_rmsd_to_representative_angstrom",
        cluster.direct_rmsd_to_representative_angstrom,
    )?;
    cluster_output.set_item("coordinate_sha256", hex_digest(cluster.coordinate_sha256))?;
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
        "post_admission_row_receipt_sha256",
        hex_digest(pipeline.post_admission_row_receipt_sha256),
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

fn geometric_to_python(
    py: Python<'_>,
    evidence: &betelgeuze_runtime::Fixed64GeometricEvidence,
) -> PyResult<PyObject> {
    let output = PyDict::new(py);
    output.set_item("status", evidence.status)?;
    output.set_item("failure_code", evidence.failure_code)?;
    output.set_item("decision", evidence.decision)?;
    output.set_item("rank_eligible", evidence.rank_eligible)?;
    output.set_item("ligand_atom_count", evidence.ligand_atom_count)?;
    output.set_item("receptor_atom_count", evidence.receptor_atom_count)?;
    output.set_item("exact_pair_count", evidence.exact_pair_count)?;
    output.set_item("penetration_pair_count", evidence.penetration_pair_count)?;
    output.set_item(
        "penetrating_atom_count",
        evidence.unique_ligand_penetration_atom_count,
    )?;
    output.set_item(
        "penetrating_heavy_atom_count",
        evidence.unique_ligand_heavy_atom_penetration_count,
    )?;
    output.set_item(
        "raw_minimum_distance_angstrom",
        evidence.raw_minimum_distance_angstrom,
    )?;
    output.set_item(
        "minimum_vdw_surface_gap_angstrom",
        evidence.minimum_vdw_surface_gap_angstrom,
    )?;
    output.set_item("minimum_vdw_ratio", evidence.minimum_vdw_ratio)?;
    output.set_item(
        "sphere_overlap_proxy_angstrom3",
        evidence.sphere_overlap_proxy_angstrom3,
    )?;
    output.set_item("pocket_escape_angstrom", evidence.pocket_escape_angstrom)?;
    output.set_item("receipt_sha256", hex_digest(evidence.row_receipt_sha256))?;
    Ok(output.into())
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
    output.set_item(
        "fallback_direction_step_count",
        evidence.fallback_direction_step_count,
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
    output.set_item(
        "initial_centroid_offset_angstrom",
        evidence.initial_centroid_offset_angstrom,
    )?;
    output.set_item(
        "final_centroid_offset_angstrom",
        evidence.final_centroid_offset_angstrom,
    )?;
    output.set_item(
        "maximum_centroid_offset_angstrom",
        evidence.maximum_centroid_offset_angstrom,
    )?;
    Ok(output.into())
}

fn torsion_to_python(
    py: Python<'_>,
    receipt: &Fixed64PipelineReceipt,
    slot: usize,
) -> PyResult<PyObject> {
    let row = &receipt.torsion_rows[slot];
    let start = slot
        .checked_mul(receipt.ligand_atom_count)
        .ok_or_else(|| input_error("torsion-angle offset overflowed"))?;
    let end = start
        .checked_add(receipt.ligand_atom_count)
        .ok_or_else(|| input_error("torsion-angle range overflowed"))?;
    let optimized_angles = receipt
        .torsion_coordinates
        .optimized_torsion_angles_radians
        .get(start..end)
        .ok_or_else(|| input_error("optimized torsion-angle range is absent"))?;
    let final_angles = receipt
        .torsion_coordinates
        .final_torsion_angles_radians
        .get(start..end)
        .ok_or_else(|| input_error("final torsion-angle range is absent"))?;
    let output = PyDict::new(py);
    output.set_item("status", row.status)?;
    output.set_item("failure_code", row.failure_code)?;
    output.set_item("skip_reason", row.skip_reason)?;
    output.set_item("selection_reason", row.selection_reason)?;
    output.set_item("selection_window_reachable", row.selection_window_reachable)?;
    output.set_item(
        "evaluation_stopped_after_selection_window_became_unreachable",
        row.evaluation_stopped_after_selection_window_became_unreachable,
    )?;
    output.set_item("torsion_evaluated", row.torsion_evaluated)?;
    output.set_item("torsion_variant_available", row.torsion_variant_available)?;
    output.set_item("torsion_selected", row.torsion_selected)?;
    output.set_item("torsion_step_budget", row.torsion_step_budget)?;
    output.set_item(
        "fixed_objective_evaluation_count",
        row.fixed_objective_evaluation_count,
    )?;
    output.set_item(
        "torsion_trial_objective_evaluation_count",
        row.torsion_trial_objective_evaluation_count,
    )?;
    output.set_item("evaluated_torsion_steps", row.evaluated_torsion_steps)?;
    output.set_item("accepted_torsion_steps", row.accepted_torsion_steps)?;
    output.set_item("baseline_v6_accepted_steps", row.baseline_v6_accepted_steps)?;
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
    output.set_item(
        "evaluated_total_torsion_path_radians",
        row.evaluated_total_torsion_path_radians,
    )?;
    output.set_item(
        "accepted_total_torsion_path_radians",
        row.accepted_total_torsion_path_radians,
    )?;
    output.set_item(
        "optimized_torsion_angles_radians",
        PyList::new(py, optimized_angles),
    )?;
    output.set_item(
        "final_torsion_angles_radians",
        PyList::new(py, final_angles),
    )?;
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
