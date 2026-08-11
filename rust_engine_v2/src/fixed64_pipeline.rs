use std::collections::BTreeSet;

use betelgeuze_docking_search::{
    native_fixed64_coordinate_sha256, native_fixed64_heavy_atom_mask_sha256,
    native_fixed64_radii_sha256, run_native_fixed64_pipeline, Fixed64Allocation,
    Fixed64AtomicFeatureEvidence, Fixed64ConformerSourceEvidence, Fixed64CoordinateSourceKind,
    Fixed64CoordinateSourcePayload, Fixed64ExactV11SourceEvidence, Fixed64FeatureGeometry,
    Fixed64FeatureGeometryInventory, Fixed64FeatureInventory, Fixed64FeatureKind,
    Fixed64GeometricInput, Fixed64IndexedSourceEvidence, Fixed64ProposalSourceBundle,
    Fixed64SourceEvidence, NativeFixed64Consumer, NativeFixed64ValidityBackend,
    NativeFixed64ValidityConfig, NativeFixed64ValidityContext, NativeScorerV1Atom,
    NativeScorerV1Backend, NativeScorerV1Config, NativeScorerV1Context, NativeScorerV1Donor, Vec3,
    FIXED64_CANDIDATE_COUNT, FIXED64_PROFILE_ID, NATIVE_FIXED64_PIPELINE_ID,
    NATIVE_FIXED64_PIPELINE_SCHEMA_ID,
};
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyList};

pub(crate) const NATIVE_FIXED64_EXACT_SOURCE_INPUT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_exact_source_input/1.0.0";
pub(crate) const NATIVE_FIXED64_PYTHON_EVIDENCE_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_python_evidence/1.0.0";

const INPUT_KEYS: [&str; 38] = [
    "schema_id",
    "consumer",
    "source_receipt_sha256",
    "proposal_sha256",
    "prepared_ligand_topology_sha256",
    "prepared_receptor_topology_sha256",
    "receptor_system_sha256",
    "ligand_system_sha256",
    "scorer_backend_receipt_sha256",
    "validity_backend_receipt_sha256",
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
    "pocket_center_angstrom",
    "pocket_radius_angstrom",
    "pocket_normal",
    "v7_control_sources",
    "conformer_sources",
    "retained_sources",
    "feature_geometries",
    "test_only",
];

const INDEXED_SOURCE_KEYS: [&str; 4] = [
    "source_index",
    "receipt_sha256",
    "proposal_sha256",
    "coordinates_angstrom",
];
const CONFORMER_SOURCE_KEYS: [&str; 4] = [
    "rank",
    "receipt_sha256",
    "proposal_sha256",
    "coordinates_angstrom",
];
const FEATURE_GEOMETRY_KEYS: [&str; 3] = ["kind", "receipt_sha256", "atom_indices"];

struct IndexedSourceInput {
    source_index: u32,
    source: Fixed64SourceEvidence,
    coordinates_angstrom: Vec<Vec3>,
}

struct ConformerSourceInput {
    rank: u8,
    source: Fixed64SourceEvidence,
    coordinates_angstrom: Vec<Vec3>,
}

struct FeatureGeometryInput {
    kind: Fixed64FeatureKind,
    receipt_sha256: [u8; 32],
    atom_indices: Vec<usize>,
}

pub(crate) fn register(module: &PyModule) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(
        native_fixed64_exact_source_pipeline_v1,
        module
    )?)?;
    module.add(
        "NATIVE_FIXED64_EXACT_SOURCE_INPUT_SCHEMA_ID",
        NATIVE_FIXED64_EXACT_SOURCE_INPUT_SCHEMA_ID,
    )?;
    module.add(
        "NATIVE_FIXED64_PYTHON_EVIDENCE_SCHEMA_ID",
        NATIVE_FIXED64_PYTHON_EVIDENCE_SCHEMA_ID,
    )?;
    Ok(())
}

#[pyfunction]
fn native_fixed64_exact_source_pipeline_v1(py: Python<'_>, input: &PyDict) -> PyResult<PyObject> {
    require_exact_keys(input, &INPUT_KEYS, "native fixed64 exact-source input")?;
    if dict_string(input, "schema_id")? != NATIVE_FIXED64_EXACT_SOURCE_INPUT_SCHEMA_ID {
        return Err(input_error("input schema_id is unsupported"));
    }
    if !dict_exact_bool(input, "test_only")? {
        return Err(input_error(
            "exact-source Python bridge is synthetic/test-only and fails closed otherwise",
        ));
    }
    let consumer = parse_consumer(dict_string(input, "consumer")?)?;
    let ligand_coordinates = rows3(
        dict_value(input, "ligand_coordinates_angstrom")?,
        "ligand_coordinates_angstrom",
    )?;
    let receptor_coordinates = rows3(
        dict_value(input, "receptor_coordinates_angstrom")?,
        "receptor_coordinates_angstrom",
    )?;
    let ligand_count = ligand_coordinates.len();
    let receptor_count = receptor_coordinates.len();
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
    let ligand_heavy = bool_values(
        dict_value(input, "ligand_heavy_atom_mask")?,
        ligand_count,
        "ligand_heavy_atom_mask",
    )?;
    let ligand_charges = f64_values(
        dict_value(input, "ligand_charge_elementary")?,
        ligand_count,
        "ligand_charge_elementary",
    )?;
    let ligand_epsilons = f64_values(
        dict_value(input, "ligand_epsilon_kcal_per_mol")?,
        ligand_count,
        "ligand_epsilon_kcal_per_mol",
    )?;
    let ligand_hydrophobic = bool_values(
        dict_value(input, "ligand_hydrophobic_mask")?,
        ligand_count,
        "ligand_hydrophobic_mask",
    )?;
    let ligand_acceptor = bool_values(
        dict_value(input, "ligand_acceptor_mask")?,
        ligand_count,
        "ligand_acceptor_mask",
    )?;
    let receptor_charges = f64_values(
        dict_value(input, "receptor_charge_elementary")?,
        receptor_count,
        "receptor_charge_elementary",
    )?;
    let receptor_epsilons = f64_values(
        dict_value(input, "receptor_epsilon_kcal_per_mol")?,
        receptor_count,
        "receptor_epsilon_kcal_per_mol",
    )?;
    let receptor_hydrophobic = bool_values(
        dict_value(input, "receptor_hydrophobic_mask")?,
        receptor_count,
        "receptor_hydrophobic_mask",
    )?;
    let receptor_acceptor = bool_values(
        dict_value(input, "receptor_acceptor_mask")?,
        receptor_count,
        "receptor_acceptor_mask",
    )?;
    let ligand_donors = index_rows::<2>(
        dict_value(input, "ligand_donors")?,
        ligand_count,
        "ligand_donors",
    )?;
    let receptor_donors = index_rows::<2>(
        dict_value(input, "receptor_donors")?,
        receptor_count,
        "receptor_donors",
    )?;
    let ligand_exclusions = index_rows::<2>(
        dict_value(input, "ligand_exclusions")?,
        ligand_count,
        "ligand_exclusions",
    )?;
    let rotor_quads = index_rows::<4>(
        dict_value(input, "rotor_quads")?,
        ligand_count,
        "rotor_quads",
    )?;
    let bond_pairs = index_rows::<2>(dict_value(input, "bond_pairs")?, ligand_count, "bond_pairs")?;
    let chirality_centers = index_rows::<4>(
        dict_value(input, "chirality_centers")?,
        ligand_count,
        "chirality_centers",
    )?;
    let pocket_center = vec3_value(
        dict_value(input, "pocket_center_angstrom")?,
        "pocket_center_angstrom",
    )?;
    let pocket_normal = vec3_value(dict_value(input, "pocket_normal")?, "pocket_normal")?;
    let pocket_radius = dict_f64(input, "pocket_radius_angstrom")?;
    let v7_inputs = indexed_sources(
        dict_value(input, "v7_control_sources")?,
        "v7_control_sources",
    )?;
    let conformer_inputs = conformer_sources(dict_value(input, "conformer_sources")?)?;
    let retained_inputs =
        indexed_sources(dict_value(input, "retained_sources")?, "retained_sources")?;
    let feature_inputs = feature_geometries(dict_value(input, "feature_geometries")?)?;

    let exact = Fixed64ExactV11SourceEvidence {
        source_receipt_sha256: dict_digest(input, "source_receipt_sha256")?,
        proposal_sha256: dict_digest(input, "proposal_sha256")?,
        ligand_coordinate_sha256: native_fixed64_coordinate_sha256(&ligand_coordinates)
            .map_err(|error| input_error(&error.to_string()))?,
        receptor_coordinate_sha256: native_fixed64_coordinate_sha256(&receptor_coordinates)
            .map_err(|error| input_error(error.message()))?,
        prepared_ligand_topology_sha256: dict_digest(input, "prepared_ligand_topology_sha256")?,
        prepared_receptor_topology_sha256: dict_digest(input, "prepared_receptor_topology_sha256")?,
        ligand_vdw_radii_sha256: native_fixed64_radii_sha256(&ligand_radii)
            .map_err(|error| input_error(error.message()))?,
        ligand_heavy_atom_mask_sha256: native_fixed64_heavy_atom_mask_sha256(&ligand_heavy)
            .map_err(|error| input_error(error.message()))?,
        receptor_vdw_radii_sha256: native_fixed64_radii_sha256(&receptor_radii)
            .map_err(|error| input_error(error.message()))?,
    };
    let allocation = Fixed64Allocation::build(
        Fixed64FeatureInventory::new(
            exact,
            feature_inputs
                .iter()
                .map(|feature| Fixed64AtomicFeatureEvidence {
                    kind: feature.kind,
                    receipt_sha256: feature.receipt_sha256,
                })
                .collect(),
            v7_inputs
                .iter()
                .map(|source| Fixed64IndexedSourceEvidence {
                    source_index: source.source_index,
                    source: source.source,
                })
                .collect(),
            conformer_inputs
                .iter()
                .map(|source| Fixed64ConformerSourceEvidence {
                    rank: source.rank,
                    source: source.source,
                })
                .collect(),
            retained_inputs
                .iter()
                .map(|source| Fixed64IndexedSourceEvidence {
                    source_index: source.source_index,
                    source: source.source,
                })
                .collect(),
        )
        .map_err(|error| input_error(&error.to_string()))?,
    )
    .map_err(|error| input_error(&error.to_string()))?;
    let exact_payload = Fixed64CoordinateSourcePayload::new(
        Fixed64CoordinateSourceKind::ExactV11Base,
        None,
        exact.ligand_source(),
        ligand_coordinates.clone(),
    )
    .map_err(|error| input_error(error.message()))?;
    let v7_payloads = coordinate_payloads(v7_inputs, Fixed64CoordinateSourceKind::V7Control)?;
    let conformer_payloads = conformer_payloads(conformer_inputs)?;
    let retained_payloads = coordinate_payloads(
        retained_inputs,
        Fixed64CoordinateSourceKind::RetainedControl,
    )?;
    let feature_geometry_inventory = Fixed64FeatureGeometryInventory::new(
        feature_inputs
            .into_iter()
            .map(|feature| {
                Fixed64FeatureGeometry::new(
                    feature.kind,
                    feature.receipt_sha256,
                    feature.atom_indices,
                )
            })
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| input_error(error.message()))?,
    )
    .map_err(|error| input_error(error.message()))?;
    let geometric_input = Fixed64GeometricInput::new(
        ligand_radii.clone(),
        ligand_heavy,
        receptor_coordinates.clone(),
        receptor_radii.clone(),
        pocket_center,
        pocket_radius,
    )
    .map_err(|error| input_error(error.message()))?;
    let source_bundle = Fixed64ProposalSourceBundle::new(
        &allocation,
        Some(exact_payload),
        v7_payloads,
        conformer_payloads,
        retained_payloads,
        feature_geometry_inventory,
        geometric_input,
        pocket_normal,
    )
    .map_err(|error| input_error(error.message()))?;
    let ligand_atoms = atom_rows(
        &ligand_charges,
        &ligand_radii,
        &ligand_epsilons,
        &ligand_hydrophobic,
        &ligand_acceptor,
    );
    let receptor_atoms = atom_rows(
        &receptor_charges,
        &receptor_radii,
        &receptor_epsilons,
        &receptor_hydrophobic,
        &receptor_acceptor,
    );
    let scorer_context = NativeScorerV1Context::new(
        exact.source_receipt_sha256,
        dict_digest(input, "receptor_system_sha256")?,
        dict_digest(input, "ligand_system_sha256")?,
        NativeScorerV1Backend::RustCpu,
        dict_digest(input, "scorer_backend_receipt_sha256")?,
        receptor_coordinates,
        receptor_atoms,
        ligand_coordinates,
        ligand_atoms,
        donor_rows(receptor_donors),
        donor_rows(ligand_donors),
        ligand_exclusions,
        rotor_quads,
        pocket_center,
        pocket_radius,
        NativeScorerV1Config::default(),
    )
    .map_err(|error| input_error(error.message()))?;
    let validity_context = NativeFixed64ValidityContext::from_scorer_context(
        &scorer_context,
        NativeFixed64ValidityBackend::RustCpu,
        dict_digest(input, "validity_backend_receipt_sha256")?,
        dict_digest(input, "contact_policy_sha256")?,
        bond_pairs,
        chirality_centers,
        NativeFixed64ValidityConfig::default(),
    )
    .map_err(|error| input_error(error.message()))?;
    let pipeline = py
        .allow_threads(move || {
            run_native_fixed64_pipeline(source_bundle, scorer_context, validity_context)
        })
        .map_err(|error| {
            PyValueError::new_err(format!(
                "native_fixed64_pipeline_v1_{}: {}",
                error.stage().id(),
                error.message()
            ))
        })?;
    pipeline_to_python(py, &pipeline, consumer)
}

fn pipeline_to_python(
    py: Python<'_>,
    pipeline: &betelgeuze_docking_search::NativeFixed64PipelineReceipt,
    consumer: NativeFixed64Consumer,
) -> PyResult<PyObject> {
    if !pipeline.has_valid_receipt() {
        return Err(input_error("native pipeline receipt failed verification"));
    }
    let ranking = pipeline.ranking();
    let validity = ranking.validity_batch();
    let scorer = validity.scorer_batch();
    let admission = scorer.admission();
    let proposals = admission
        .proposal_batch()
        .ok_or_else(|| input_error("native proposal evidence is absent"))?;
    let view = pipeline.consumer_view(consumer);
    if !view.verifies_against(pipeline) {
        return Err(input_error("native consumer view failed verification"));
    }

    let output = PyDict::new(py);
    output.set_item("schema_id", NATIVE_FIXED64_PYTHON_EVIDENCE_SCHEMA_ID)?;
    output.set_item("pipeline_schema_id", NATIVE_FIXED64_PIPELINE_SCHEMA_ID)?;
    output.set_item("pipeline_id", NATIVE_FIXED64_PIPELINE_ID)?;
    output.set_item("profile_id", FIXED64_PROFILE_ID)?;
    output.set_item("consumer", consumer.id())?;
    output.set_item("backend", scorer.context().backend().id())?;
    output.set_item("candidate_denominator", FIXED64_CANDIDATE_COUNT)?;
    output.set_item(
        "pipeline_receipt_sha256",
        hex_digest(pipeline.receipt_sha256()),
    )?;
    output.set_item(
        "consumer_view_receipt_sha256",
        hex_digest(view.receipt_sha256()),
    )?;
    output.set_item(
        "allocation_receipt_sha256",
        hex_digest(view.allocation_receipt_sha256()),
    )?;
    output.set_item(
        "proposal_batch_receipt_sha256",
        hex_digest(proposals.receipt_sha256()),
    )?;
    output.set_item(
        "geometric_admission_receipt_sha256",
        hex_digest(admission.receipt_sha256()),
    )?;
    output.set_item("scorer_receipt_sha256", hex_digest(scorer.receipt_sha256()))?;
    output.set_item(
        "validity_receipt_sha256",
        hex_digest(validity.receipt_sha256()),
    )?;
    output.set_item(
        "ranking_receipt_sha256",
        hex_digest(ranking.receipt_sha256()),
    )?;
    output.set_item("generated_count", pipeline.generated_count())?;
    output.set_item("accepted_count", pipeline.accepted_count())?;
    output.set_item("scored_count", pipeline.scored_count())?;
    output.set_item("evaluated_count", pipeline.evaluated_count())?;
    output.set_item("valid_count", pipeline.valid_count())?;
    output.set_item("top5_slot_indices", ranking.top5_slot_indices())?;
    output.set_item("valid_top5_slot_indices", ranking.valid_top5_slot_indices())?;
    output.set_item(
        "authority_blockers",
        pipeline
            .authority_blockers()
            .iter()
            .map(|blocker| blocker.id())
            .collect::<Vec<_>>(),
    )?;
    output.set_item("evidence_display_authorized", true)?;
    output.set_item(
        "operator_second_opinion_authorized",
        view.operator_second_opinion_authorized(),
    )?;
    output.set_item("reservation_authorized", false)?;
    output.set_item("molecular_execution_authorized", false)?;
    output.set_item("existing_rank_auto_change_authorized", false)?;
    output.set_item("customer_pose_emission_authorized", false)?;
    output.set_item("production_claim_authorized", false)?;

    let rows = PyList::empty(py);
    for slot_index in 0..FIXED64_CANDIDATE_COUNT {
        let proposal = &proposals.records()[slot_index];
        let geometric = &admission.decisions()[slot_index];
        let score = &scorer.rows()[slot_index];
        let pose_validity = &validity.rows()[slot_index];
        let rank = &ranking.records()[slot_index];
        let row = PyDict::new(py);
        row.set_item("slot_index", slot_index)?;
        row.set_item("lane", proposal.lane().id())?;
        row.set_item("proposal_status", proposal.status().id())?;
        row.set_item(
            "proposal_failure_code",
            proposal.failure_code().map(|code| code.id()),
        )?;
        row.set_item(
            "proposal_receipt_sha256",
            hex_digest(proposal.receipt_sha256()),
        )?;
        row.set_item("geometric_status", geometric.status().id())?;
        row.set_item("geometric_rank_eligible", geometric.rank_eligible())?;
        row.set_item(
            "geometric_receipt_sha256",
            hex_digest(geometric.receipt_sha256()),
        )?;
        row.set_item("scorer_status", score.status().id())?;
        row.set_item(
            "scorer_failure_code",
            score.failure().map(|failure| failure.failure_code().id()),
        )?;
        row.set_item("scorer_receipt_sha256", hex_digest(score.receipt_sha256()))?;
        if let Some(terms) = score.terms() {
            let evidence = PyDict::new(py);
            evidence.set_item("typed_vdw", terms.typed_vdw())?;
            evidence.set_item("electrostatics", terms.electrostatics())?;
            evidence.set_item("directional_hbond", terms.directional_hbond())?;
            evidence.set_item("hydrophobic_contact", terms.hydrophobic_contact())?;
            evidence.set_item("desolvation_proxy", terms.desolvation_proxy())?;
            evidence.set_item("torsion_energy", terms.torsion_energy())?;
            evidence.set_item("ligand_strain", terms.ligand_strain())?;
            evidence.set_item("weak_pocket_prior", terms.weak_pocket_prior())?;
            evidence.set_item("total_score", terms.total_score())?;
            evidence.set_item(
                "receptor_candidate_pair_count",
                terms.receptor_candidate_pair_count(),
            )?;
            evidence.set_item("ligand_pair_count", terms.ligand_pair_count())?;
            evidence.set_item("hbond_count", terms.hbond_count())?;
            evidence.set_item(
                "hydrophobic_contact_count",
                terms.hydrophobic_contact_count(),
            )?;
            evidence.set_item("buried_polar_count", terms.buried_polar_count())?;
            evidence.set_item("coordinate_sha256", hex_digest(terms.coordinate_sha256()))?;
            evidence.set_item("receipt_sha256", hex_digest(terms.receipt_sha256()))?;
            row.set_item("scorer_terms", evidence)?;
        } else {
            row.set_item("scorer_terms", py.None())?;
        }
        row.set_item("validity_status", pose_validity.status().id())?;
        row.set_item("pose_valid", pose_validity.valid())?;
        row.set_item(
            "validity_failure_code",
            pose_validity
                .failure()
                .map(|failure| failure.failure_code().id()),
        )?;
        row.set_item(
            "validity_blockers",
            pose_validity
                .result()
                .map(|result| {
                    result
                        .blockers()
                        .iter()
                        .map(|blocker| blocker.id())
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default(),
        )?;
        row.set_item(
            "validity_receipt_sha256",
            hex_digest(pose_validity.receipt_sha256()),
        )?;
        row.set_item("stable_rank", rank.stable_rank())?;
        row.set_item("stable_valid_rank", rank.stable_valid_rank())?;
        row.set_item("ranking_receipt_sha256", hex_digest(rank.receipt_sha256()))?;
        row.set_item("candidate_removed_from_denominator", false)?;
        row.set_item("result_dependent_allocation", false)?;
        row.set_item("customer_pose_emission_authorized", false)?;
        row.set_item("existing_rank_auto_change_authorized", false)?;
        row.set_item("production_claim_authorized", false)?;
        rows.append(row)?;
    }
    output.set_item("candidates", rows)?;
    Ok(output.into())
}

fn indexed_sources(value: &PyAny, name: &str) -> PyResult<Vec<IndexedSourceInput>> {
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error(&format!("{name} must be an exact list")))?;
    rows.iter()
        .enumerate()
        .map(|(offset, row)| {
            let row = row
                .downcast::<PyDict>()
                .map_err(|_| input_error(&format!("{name}[{offset}] must be a dict")))?;
            require_exact_keys(row, &INDEXED_SOURCE_KEYS, name)?;
            let source_index = dict_u32(row, "source_index")?;
            let coordinates_angstrom = rows3(
                dict_value(row, "coordinates_angstrom")?,
                "coordinates_angstrom",
            )?;
            let source = Fixed64SourceEvidence {
                receipt_sha256: dict_digest(row, "receipt_sha256")?,
                proposal_sha256: dict_digest(row, "proposal_sha256")?,
                coordinate_sha256: native_fixed64_coordinate_sha256(&coordinates_angstrom)
                    .map_err(|error| input_error(error.message()))?,
            };
            Ok(IndexedSourceInput {
                source_index,
                source,
                coordinates_angstrom,
            })
        })
        .collect()
}

fn conformer_sources(value: &PyAny) -> PyResult<Vec<ConformerSourceInput>> {
    let name = "conformer_sources";
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error("conformer_sources must be an exact list"))?;
    rows.iter()
        .enumerate()
        .map(|(offset, row)| {
            let row = row
                .downcast::<PyDict>()
                .map_err(|_| input_error(&format!("{name}[{offset}] must be a dict")))?;
            require_exact_keys(row, &CONFORMER_SOURCE_KEYS, name)?;
            let rank = dict_u8(row, "rank")?;
            let coordinates_angstrom = rows3(
                dict_value(row, "coordinates_angstrom")?,
                "coordinates_angstrom",
            )?;
            let source = Fixed64SourceEvidence {
                receipt_sha256: dict_digest(row, "receipt_sha256")?,
                proposal_sha256: dict_digest(row, "proposal_sha256")?,
                coordinate_sha256: native_fixed64_coordinate_sha256(&coordinates_angstrom)
                    .map_err(|error| input_error(error.message()))?,
            };
            Ok(ConformerSourceInput {
                rank,
                source,
                coordinates_angstrom,
            })
        })
        .collect()
}

fn feature_geometries(value: &PyAny) -> PyResult<Vec<FeatureGeometryInput>> {
    let name = "feature_geometries";
    let rows = value
        .downcast::<PyList>()
        .map_err(|_| input_error("feature_geometries must be an exact list"))?;
    rows.iter()
        .enumerate()
        .map(|(offset, row)| {
            let row = row
                .downcast::<PyDict>()
                .map_err(|_| input_error(&format!("{name}[{offset}] must be a dict")))?;
            require_exact_keys(row, &FEATURE_GEOMETRY_KEYS, name)?;
            let atom_indices = dict_value(row, "atom_indices")?
                .extract::<Vec<usize>>()
                .map_err(|_| input_error("feature atom_indices must be integer indices"))?;
            Ok(FeatureGeometryInput {
                kind: feature_kind(dict_string(row, "kind")?)?,
                receipt_sha256: dict_digest(row, "receipt_sha256")?,
                atom_indices,
            })
        })
        .collect()
}

fn coordinate_payloads(
    inputs: Vec<IndexedSourceInput>,
    kind: Fixed64CoordinateSourceKind,
) -> PyResult<Vec<Fixed64CoordinateSourcePayload>> {
    inputs
        .into_iter()
        .map(|input| {
            Fixed64CoordinateSourcePayload::new(
                kind,
                Some(input.source_index),
                input.source,
                input.coordinates_angstrom,
            )
            .map_err(|error| input_error(error.message()))
        })
        .collect()
}

fn conformer_payloads(
    inputs: Vec<ConformerSourceInput>,
) -> PyResult<Vec<Fixed64CoordinateSourcePayload>> {
    inputs
        .into_iter()
        .map(|input| {
            Fixed64CoordinateSourcePayload::new(
                Fixed64CoordinateSourceKind::TrueConformer,
                Some(u32::from(input.rank)),
                input.source,
                input.coordinates_angstrom,
            )
            .map_err(|error| input_error(error.message()))
        })
        .collect()
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

fn atom_rows(
    charges: &[f64],
    radii: &[f64],
    epsilons: &[f64],
    hydrophobic: &[bool],
    acceptor: &[bool],
) -> Vec<NativeScorerV1Atom> {
    (0..charges.len())
        .map(|index| NativeScorerV1Atom {
            charge_elementary: charges[index],
            vdw_radius_angstrom: radii[index],
            epsilon_kcal_per_mol: epsilons[index],
            hydrophobic: hydrophobic[index],
            acceptor: acceptor[index],
        })
        .collect()
}

fn donor_rows(rows: Vec<[usize; 2]>) -> Vec<NativeScorerV1Donor> {
    rows.into_iter()
        .map(|row| NativeScorerV1Donor {
            donor_atom_index: row[0],
            hydrogen_atom_index: row[1],
        })
        .collect()
}

fn parse_consumer(value: &str) -> PyResult<NativeFixed64Consumer> {
    match value {
        "cli" => Ok(NativeFixed64Consumer::Cli),
        "benchmark" => Ok(NativeFixed64Consumer::Benchmark),
        "api" => Ok(NativeFixed64Consumer::Api),
        "product_shadow" => Ok(NativeFixed64Consumer::ProductShadow),
        _ => Err(input_error("consumer is unsupported")),
    }
}

fn require_exact_keys(dict: &PyDict, expected: &[&str], name: &str) -> PyResult<()> {
    let observed = dict
        .iter()
        .map(|(key, _)| {
            key.extract::<&str>()
                .map(str::to_owned)
                .map_err(|_| input_error("input keys must be strings"))
        })
        .collect::<PyResult<BTreeSet<_>>>()?;
    let expected = expected
        .iter()
        .map(|value| (*value).to_owned())
        .collect::<BTreeSet<_>>();
    if observed != expected {
        return Err(input_error(&format!("{name} has an invalid key schema")));
    }
    Ok(())
}

fn dict_value<'py>(dict: &'py PyDict, key: &str) -> PyResult<&'py PyAny> {
    dict.get_item(key)?
        .ok_or_else(|| input_error(&format!("input field {key} is missing")))
}

fn dict_string<'py>(dict: &'py PyDict, key: &str) -> PyResult<&'py str> {
    dict_value(dict, key)?
        .extract::<&str>()
        .map_err(|_| input_error(&format!("{key} must be a string")))
}

fn dict_exact_bool(dict: &PyDict, key: &str) -> PyResult<bool> {
    let value = dict_value(dict, key)?;
    if !value.is_instance_of::<PyBool>() {
        return Err(input_error(&format!("{key} must be an exact bool")));
    }
    value
        .extract::<bool>()
        .map_err(|_| input_error(&format!("{key} must be an exact bool")))
}

fn dict_f64(dict: &PyDict, key: &str) -> PyResult<f64> {
    let value = dict_value(dict, key)?;
    if value.is_instance_of::<PyBool>() {
        return Err(input_error(&format!("{key} must be numeric")));
    }
    let output = value
        .extract::<f64>()
        .map_err(|_| input_error(&format!("{key} must be numeric")))?;
    if !output.is_finite() {
        return Err(input_error(&format!("{key} must be finite")));
    }
    Ok(output)
}

fn dict_usize(dict: &PyDict, key: &str) -> PyResult<usize> {
    let value = dict_value(dict, key)?;
    if value.is_instance_of::<PyBool>() {
        return Err(input_error(&format!("{key} must be an integer")));
    }
    value
        .extract::<usize>()
        .map_err(|_| input_error(&format!("{key} must be an integer")))
}

fn dict_u32(dict: &PyDict, key: &str) -> PyResult<u32> {
    u32::try_from(dict_usize(dict, key)?).map_err(|_| input_error(&format!("{key} exceeds u32")))
}

fn dict_u8(dict: &PyDict, key: &str) -> PyResult<u8> {
    u8::try_from(dict_usize(dict, key)?).map_err(|_| input_error(&format!("{key} exceeds u8")))
}

fn dict_digest(dict: &PyDict, key: &str) -> PyResult<[u8; 32]> {
    decode_digest(dict_string(dict, key)?, key)
}

fn decode_digest(value: &str, name: &str) -> PyResult<[u8; 32]> {
    let bytes = value.as_bytes();
    if bytes.len() != 64
        || bytes
            .iter()
            .any(|byte| !byte.is_ascii_digit() && !(b'a'..=b'f').contains(byte))
    {
        return Err(input_error(&format!(
            "{name} must be 64 lowercase hexadecimal characters"
        )));
    }
    let mut output = [0_u8; 32];
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
        output[index] = (high << 4) | low;
    }
    if output == [0; 32] {
        return Err(input_error(&format!("{name} must not be all-zero")));
    }
    Ok(output)
}

fn rows3(value: &PyAny, name: &str) -> PyResult<Vec<Vec3>> {
    if let Ok(array) = value.extract::<PyReadonlyArray2<'_, f64>>() {
        let view = array.as_array();
        if view.nrows() == 0 || view.ncols() != 3 {
            return Err(input_error(&format!("{name} must have shape [N,3]")));
        }
        return view
            .outer_iter()
            .map(|row| vec3([row[0], row[1], row[2]], name))
            .collect();
    }
    let rows = value
        .extract::<Vec<Vec<f64>>>()
        .map_err(|_| input_error(&format!("{name} must be a numeric [N,3] sequence")))?;
    if rows.is_empty() || rows.iter().any(|row| row.len() != 3) {
        return Err(input_error(&format!("{name} must have shape [N,3]")));
    }
    rows.into_iter()
        .map(|row| vec3([row[0], row[1], row[2]], name))
        .collect()
}

fn vec3_value(value: &PyAny, name: &str) -> PyResult<Vec3> {
    let values = f64_values(value, 3, name)?;
    vec3([values[0], values[1], values[2]], name)
}

fn vec3(values: [f64; 3], name: &str) -> PyResult<Vec3> {
    if values.iter().any(|value| !value.is_finite()) {
        return Err(input_error(&format!("{name} must be finite")));
    }
    Ok(Vec3::new(values[0], values[1], values[2]))
}

fn f64_values(value: &PyAny, expected: usize, name: &str) -> PyResult<Vec<f64>> {
    let values = if let Ok(array) = value.extract::<PyReadonlyArray1<'_, f64>>() {
        array.as_slice()?.to_vec()
    } else {
        value
            .extract::<Vec<f64>>()
            .map_err(|_| input_error(&format!("{name} must be a numeric sequence")))?
    };
    if values.len() != expected || values.iter().any(|value| !value.is_finite()) {
        return Err(input_error(&format!(
            "{name} length or finite-value contract failed"
        )));
    }
    Ok(values)
}

fn bool_values(value: &PyAny, expected: usize, name: &str) -> PyResult<Vec<bool>> {
    if let Ok(array) = value.extract::<PyReadonlyArray1<'_, u8>>() {
        let values = array.as_slice()?;
        if values.len() != expected || values.iter().any(|item| *item > 1) {
            return Err(input_error(&format!("{name} must be a binary mask")));
        }
        return Ok(values.iter().map(|item| *item == 1).collect());
    }
    let values = value
        .extract::<Vec<bool>>()
        .map_err(|_| input_error(&format!("{name} must be a bool sequence")))?;
    if values.len() != expected {
        return Err(input_error(&format!("{name} length mismatch")));
    }
    Ok(values)
}

fn index_rows<const N: usize>(
    value: &PyAny,
    bound: usize,
    name: &str,
) -> PyResult<Vec<[usize; N]>> {
    let rows = value
        .extract::<Vec<Vec<usize>>>()
        .map_err(|_| input_error(&format!("{name} must be an integer row sequence")))?;
    rows.into_iter()
        .map(|row| {
            if row.len() != N || row.iter().any(|index| *index >= bound) {
                return Err(input_error(&format!(
                    "{name} row width or index bound failed"
                )));
            }
            row.try_into()
                .map_err(|_| input_error(&format!("{name} row width changed")))
        })
        .collect()
}

fn hex_digest(value: [u8; 32]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(64);
    for byte in value {
        output.push(char::from(HEX[usize::from(byte >> 4)]));
        output.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }
    output
}

fn input_error(message: &str) -> PyErr {
    PyValueError::new_err(format!("native_fixed64_exact_source_input: {message}"))
}
