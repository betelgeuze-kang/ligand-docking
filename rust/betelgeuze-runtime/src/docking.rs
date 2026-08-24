//! Safe ownership for the native fixed64 docking pipeline.
//!
//! The complete native pipeline deep-copies every molecular descriptor during
//! construction. This module builds all component descriptors from one shared
//! scientific context, so safe callers cannot cross-wire admission, refinement,
//! scoring, and validity inputs or reuse the handle with another native context.

use std::collections::HashMap;
use std::ffi::CStr;
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

#[cfg(test)]
use betelgeuze_docking_search::evaluate_fixed64_geometric_metrics;
use betelgeuze_docking_search::{
    Fixed64Allocation as IndependentFixed64Allocation,
    Fixed64FeatureGeometryInventory as IndependentFixed64FeatureGeometryInventory,
    Fixed64GeometricInput as IndependentFixed64GeometricInput,
    NativeFixed64ValidityBackend as IndependentValidityBackend,
    NativeFixed64ValidityChecks as IndependentValidityChecks,
    NativeFixed64ValidityConfig as IndependentValidityConfig,
    NativeFixed64ValidityContext as IndependentValidityContext,
    NativeFixed64ValidityFailureCode as IndependentValidityFailureCode,
    NativeFixed64ValidityKernelOutcome as IndependentValidityOutcome,
    NativeFixed64ValidityMeasurements as IndependentValidityMeasurements,
    NativeRigidV2Config as IndependentRigidV2Config,
    NativeRigidV3Config as IndependentRigidV3Config, NativeScorerV1Atom as IndependentScorerAtom,
    NativeScorerV1Backend as IndependentScorerBackend,
    NativeScorerV1Config as IndependentScorerConfig,
    NativeScorerV1Context as IndependentScorerContext,
    NativeScorerV1Donor as IndependentScorerDonor,
    NativeScorerV1FailureCode as IndependentScorerFailureCode,
    NativeScorerV1KernelOutcome as IndependentScorerOutcome, Quaternion, Vec3,
    FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM,
};
use betelgeuze_sys as sys;

use super::{
    checked_count, finite, invalid, status_result, Backend, Context, ContextInner, Error,
    ErrorCode, PositionSoa, PositionSoaOwned, Result, UnitSystem,
};

mod admission;
mod context;
mod evidence;
mod ffi;
mod output_validation;
mod pipeline_evidence;
mod prepared_input;
mod preselected;
mod producer;
mod producer_replay;
mod projection;
mod ranking_clustering;
mod receipts;
mod refinement;
mod rigid;
mod scorer_validity;
mod torsion;
mod types;

use admission::{
    canonical_geometric_batch_receipt, canonical_geometric_batch_receipt_rows,
    canonical_geometric_row_receipt, numeric_matches, validate_geometric_admission_row_semantics,
};
use evidence::{
    authority_disposition, cluster_evidence, geometric_evidence, pipeline_row, producer_evidence,
    ranking_evidence, refinement_evidence, require_authority_false, rigid_evidence,
    scorer_evidence, torsion_evidence, torsion_move_evidence, validity_evidence,
};
use ffi::{
    bool_from_abi, init, preselected_component_backend, raw_coordinate_source, raw_source_evidence,
    slice_pointer, DownstreamHandleGuard, GeometricAdmissionHandleGuard, PipelineHandleGuard,
    PreselectedHandles, RankerHandleGuard, RigidHandleGuard, TorsionHandleGuard,
};
use output_validation::validate_native_outputs;
use pipeline_evidence::{
    abi_cluster_row_from_evidence, abi_geometric_row_from_evidence, abi_pipeline_row_from_evidence,
    abi_ranking_row_from_evidence, abi_refinement_row_from_evidence, abi_rigid_row_from_evidence,
    abi_scorer_row_from_evidence, abi_torsion_move_from_evidence, abi_torsion_row_from_evidence,
    abi_validity_row_from_evidence, canonical_cluster_evidence, canonical_pipeline_row_receipt,
    canonical_ranking_evidence, canonical_refinement_evidence, canonical_scorer_evidence,
    canonical_validity_evidence, validate_pipeline_receipt_bindings,
};
pub use prepared_input::Fixed64RunInput;
use prepared_input::{
    independent_allocation, independent_feature_geometry_inventory, independent_placement_source,
    validate_run_input,
};
pub use preselected::{
    Fixed64PreselectedBatchReceipts, Fixed64PreselectedPipeline, Fixed64PreselectedPipelineReceipt,
    Fixed64PreselectedPipelineRow, Fixed64PreselectedRunInput,
    FIXED64_PRESELECTED_PIPELINE_PROFILE_ID,
};
use producer::{
    canonical_generated_proposal_receipt, canonical_passthrough_placement_receipt,
    canonical_producer_batch_receipt, canonical_producer_row_receipt, fixed64_source_for_slot,
    validate_producer_row_semantics,
};
use producer_replay::{
    replay_native_placements, validate_independent_producer_placement, NativePlacementReplay,
};
pub(crate) use projection::scientific_decision_preimage;
pub use projection::{Fixed64ScientificCandidateProjection, Fixed64ScientificProjection};
use ranking_clustering::{counted_index_prefix, validate_index_evidence};
pub(crate) use receipts::CanonicalHasher;
use receipts::{
    canonical_admission_context_receipt, canonical_component_binding_receipt,
    canonical_coordinate_sha256, canonical_post_admission_policy_receipt,
    canonical_refinement_context_receipt, canonical_refinement_policy_receipt,
    canonical_scorer_context_receipt, canonical_source_bundle_receipt,
    canonical_source_payload_sha256, canonical_validity_context_receipt, hash_bool,
    hash_f64_channel, hash_position_soa_owned, hash_u32_channel,
};
use refinement::validate_refinement_evidence;
use rigid::{validate_independent_rigid_replay, validate_rigid_row_semantics};
#[cfg(test)]
use scorer_validity::independent_validity_check_mask;
use scorer_validity::validate_scorer_and_validity_evidence;
use torsion::{torsion_row_values, validate_torsion_evidence};
use types::FIXED64_NATIVE_COMPONENT_BINDING_PROFILE_ID;
pub use types::{
    Fixed64AtomicFeature, Fixed64AuthorityDisposition, Fixed64BatchReceipts,
    Fixed64ChiralityCenter, Fixed64ClusterEvidence, Fixed64ConformerCoordinateSource,
    Fixed64CoordinateSource, Fixed64Donor, Fixed64ExactSourceEvidence, Fixed64FeatureGeometry,
    Fixed64FeatureKind, Fixed64GeometricEvidence, Fixed64Identities,
    Fixed64IndexedCoordinateSource, Fixed64Ligand, Fixed64Pair, Fixed64PipelineContext,
    Fixed64PipelineReceipt, Fixed64PipelineRow, Fixed64ProducerEvidence, Fixed64RankingEvidence,
    Fixed64Receptor, Fixed64RefinementEvidence, Fixed64RefinementMode, Fixed64RigidCoordinates,
    Fixed64RigidEvidence, Fixed64RigidProfileEvidence, Fixed64Rotor, Fixed64ScorerEvidence,
    Fixed64SourceEvidence, Fixed64TorsionCoordinates, Fixed64TorsionEvidence,
    Fixed64TorsionMoveEvidence, Fixed64ValidityEvidence, Sha256,
    FIXED64_NATIVE_PIPELINE_PROFILE_ID,
};

fn digest_present(value: &Sha256) -> bool {
    value.iter().any(|byte| *byte != 0)
}

#[derive(Debug, Clone, Copy)]
struct ExpectedPipelineReceiptGraph {
    allocation_inventory_sha256: Sha256,
    allocation_receipt_sha256: Sha256,
    source_bundle_receipt_sha256: Sha256,
    admission_context_receipt_sha256: Sha256,
    refinement_context_receipt_sha256: Sha256,
    scorer_context_receipt_sha256: Sha256,
    validity_context_receipt_sha256: Sha256,
    component_binding_receipt_sha256: Sha256,
    refinement_policy_receipt_sha256: Sha256,
    post_admission_policy_receipt_sha256: Sha256,
    authority_input_receipt_sha256: Sha256,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    backend_receipt_sha256: Sha256,
    backend: Backend,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    ligand_heavy_atom_count: u64,
    geometric_max_batch_exact_pair_evaluations: u64,
    pocket_center_angstrom: [f64; 3],
    pocket_radius_angstrom: f64,
    geometric_hard_rejection_minimum_vdw_ratio: f64,
}

macro_rules! zeroed_abi_value {
    ($type:ty) => {{
        // SAFETY: Every listed ABI type is a repr(C) aggregate containing only
        // numeric fields, raw pointers, and recursively zero-valid aggregates.
        unsafe { MaybeUninit::<$type>::zeroed().assume_init() }
    }};
}

/// Owned complete fixed64 native pipeline with a lease on its creating context.
///
/// The handle is deliberately neither `Send` nor `Sync`; the native ABI
/// requires external synchronization and exact context identity.
///
/// ```compile_fail
/// use betelgeuze_runtime::Fixed64Pipeline;
/// fn require_send_sync<T: Send + Sync>() {}
/// require_send_sync::<Fixed64Pipeline>();
/// ```
pub struct Fixed64Pipeline {
    handle: NonNull<sys::bg_docking_fixed64_pipeline_v2>,
    replay_admission_handle: NonNull<sys::bg_docking_geometric_admission_v1>,
    context_lease: Rc<ContextInner>,
    backend: Backend,
    receptor_atom_count: usize,
    ligand_atom_count: usize,
    ligand_heavy_atom_count: u64,
    geometric_hard_rejection_minimum_vdw_ratio: f64,
    geometric_max_batch_exact_pair_evaluations: u64,
    geometric_input: IndependentFixed64GeometricInput,
    rigid_v2_config: IndependentRigidV2Config,
    rigid_v3_config: IndependentRigidV3Config,
    rigid_clearance_config: IndependentRigidV3Config,
    scorer_context: IndependentScorerContext,
    maximum_torsion_steps: u64,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    authority_input_receipt_sha256: Sha256,
    backend_receipt_sha256: Sha256,
    pocket_center_angstrom: [f64; 3],
    expected_admission_context_receipt_sha256: Sha256,
    expected_refinement_context_receipt_sha256: Sha256,
    expected_scorer_context_receipt_sha256: Sha256,
    expected_validity_context_receipt_sha256: Sha256,
    expected_component_binding_receipt_sha256: Sha256,
    rotatable_child_atom_indices: Vec<u64>,
    validity_exclusion_count: u64,
    validity_chirality_count: u64,
    validity_contact_cell_size_angstrom: f64,
    validity_receptor_cells: HashMap<(i64, i64, i64), u64>,
    validity_context: IndependentValidityContext,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

fn validity_cell_component(value: f64, cell_size: f64) -> Result<i64> {
    let component = (value / cell_size).floor();
    const I64_MIN_INCLUSIVE: f64 = -9_223_372_036_854_775_808.0;
    const I64_MAX_EXCLUSIVE: f64 = 9_223_372_036_854_775_808.0;
    if !component.is_finite() || !(I64_MIN_INCLUSIVE..I64_MAX_EXCLUSIVE).contains(&component) {
        return Err(invalid(
            "fixed64 receptor coordinate is outside the validity cell-key range",
        ));
    }
    Ok(component as i64)
}

fn validity_receptor_cells(
    coordinates: PositionSoa<'_>,
    cell_size: f64,
) -> Result<HashMap<(i64, i64, i64), u64>> {
    if !cell_size.is_finite() || cell_size <= 0.0 {
        return Err(invalid(
            "fixed64 validity contact-cell size must be finite and positive",
        ));
    }
    let mut cells = HashMap::new();
    for atom in 0..coordinates.x_angstrom.len() {
        let key = (
            validity_cell_component(coordinates.x_angstrom[atom], cell_size)?,
            validity_cell_component(coordinates.y_angstrom[atom], cell_size)?,
            validity_cell_component(coordinates.z_angstrom[atom], cell_size)?,
        );
        let count = cells.entry(key).or_insert(0_u64);
        *count = count.checked_add(1).ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 validity receptor-cell occupancy overflowed",
            )
        })?;
    }
    Ok(cells)
}

fn position_soa_to_vec3(coordinates: PositionSoa<'_>) -> Vec<Vec3> {
    coordinates
        .x_angstrom
        .iter()
        .zip(coordinates.y_angstrom)
        .zip(coordinates.z_angstrom)
        .map(|((x, y), z)| Vec3::new(*x, *y, *z))
        .collect()
}

fn u64_pair_to_usize(pair: Fixed64Pair, label: &str) -> Result<[usize; 2]> {
    Ok([
        usize::try_from(pair.atom_i).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} atom i does not fit usize"),
            )
        })?,
        usize::try_from(pair.atom_j).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} atom j does not fit usize"),
            )
        })?,
    ])
}

fn u64_donor_to_usize(donor: Fixed64Donor, label: &str) -> Result<IndependentScorerDonor> {
    Ok(IndependentScorerDonor {
        donor_atom_index: usize::try_from(donor.donor_atom_index).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} donor atom does not fit usize"),
            )
        })?,
        hydrogen_atom_index: usize::try_from(donor.hydrogen_atom_index).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                format!("fixed64 {label} hydrogen atom does not fit usize"),
            )
        })?,
    })
}

fn u64_rotor_to_usize(rotor: Fixed64Rotor) -> Result<[usize; 4]> {
    let convert = |value| {
        usize::try_from(value).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 scorer rotor atom does not fit usize",
            )
        })
    };
    Ok([
        convert(rotor.atom_i)?,
        convert(rotor.atom_j)?,
        convert(rotor.atom_k)?,
        convert(rotor.atom_l)?,
    ])
}

fn independent_rigid_v2_config(
    value: &sys::bg_docking_rigid_v2_config_v1,
) -> Result<IndependentRigidV2Config> {
    Ok(IndependentRigidV2Config {
        overlap_scale: value.overlap_scale,
        maximum_step_angstrom: value.maximum_step_angstrom,
        minimum_step_angstrom: value.minimum_step_angstrom,
        maximum_total_translation_angstrom: value.maximum_total_translation_angstrom,
        maximum_backtracking_evaluations: usize::try_from(value.maximum_backtracking_evaluations)
            .map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 rigid backtracking budget does not fit usize",
            )
        })?,
        penalty_tolerance: value.penalty_tolerance,
        epsilon_angstrom: value.epsilon_angstrom,
    })
}

fn independent_rigid_v3_config(
    value: &sys::bg_docking_rigid_v3_config_v1,
) -> Result<IndependentRigidV3Config> {
    Ok(IndependentRigidV3Config {
        v2: independent_rigid_v2_config(&value.v2)?,
        maximum_rotation_step_radians: value.maximum_rotation_step_radians,
        minimum_rotation_step_radians: value.minimum_rotation_step_radians,
        maximum_total_rotation_radians: value.maximum_total_rotation_radians,
        maximum_rotation_steps: usize::try_from(value.maximum_rotation_steps).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 rigid rotation budget does not fit usize",
            )
        })?,
        minimum_rotation_relative_penalty_reduction: value
            .minimum_rotation_relative_penalty_reduction,
        maximum_centroid_offset_angstrom: value.maximum_centroid_offset_angstrom,
    })
}

fn canonical_pocket_normal(value: [f64; 3]) -> Result<[f64; 3]> {
    const DIRECTION_RATIO_SCALE: f64 = 1_099_511_627_776.0;

    fn canonical_direction_ratio(value: f64) -> f64 {
        let magnitude = (value.abs() * DIRECTION_RATIO_SCALE + 0.5).floor();
        let quantized = magnitude.copysign(value) / DIRECTION_RATIO_SCALE;
        if quantized == 0.0 {
            0.0
        } else {
            quantized
        }
    }

    if value.iter().any(|component| {
        !component.is_finite() || component.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
    }) {
        return Err(invalid(
            "fixed64 pocket normal is outside its finite safety envelope",
        ));
    }
    let maximum = value[0].abs().max(value[1].abs()).max(value[2].abs());
    if maximum <= 1.0e-12 {
        return Err(invalid("fixed64 pocket normal is degenerate"));
    }
    let scaled = Vec3::new(
        canonical_direction_ratio(value[0] / maximum),
        canonical_direction_ratio(value[1] / maximum),
        canonical_direction_ratio(value[2] / maximum),
    );
    // This receipt boundary mirrors the native C++ `std::hypot` sequence.
    // The dev-only search oracle deliberately uses `libm`, which can differ by
    // a few ULPs and therefore must not define the ABI digest here.
    let scaled_norm = scaled.x.hypot(scaled.y).hypot(scaled.z);
    if !scaled_norm.is_finite() || scaled_norm <= 0.0 {
        return Err(invalid("fixed64 pocket normal could not be normalized"));
    }
    let inverse = 1.0 / scaled_norm;
    let mut result = [scaled.x * inverse, scaled.y * inverse, scaled.z * inverse];
    for component in &mut result {
        if *component == 0.0 {
            *component = 0.0;
        }
    }
    Ok(result)
}

impl Fixed64Pipeline {
    pub fn new(context: &Context, scientific: Fixed64PipelineContext<'_>) -> Result<Self> {
        Ok(Self::new_internal(context, scientific, false)?.0)
    }

    pub(crate) fn new_preselected(
        context: &Context,
        scientific: Fixed64PipelineContext<'_>,
    ) -> Result<(Self, PreselectedHandles)> {
        let (pipeline, handles) = Self::new_internal(context, scientific, true)?;
        Ok((
            pipeline,
            handles.ok_or_else(|| {
                Error::local(
                    ErrorCode::InternalError,
                    "preselected component construction returned no handles",
                )
            })?,
        ))
    }

    fn new_internal(
        context: &Context,
        scientific: Fixed64PipelineContext<'_>,
        include_preselected: bool,
    ) -> Result<(Self, Option<PreselectedHandles>)> {
        Self::profile_id()?;
        let counts = scientific.validate()?;
        let expected_backend = context.backend()?;
        let device_ordinal = context.device_ordinal()?;
        let receptor_count = usize::try_from(counts.receptor_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 receptor atom count does not fit usize",
            )
        })?;
        let ligand_count = usize::try_from(counts.ligand_atom_count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 ligand atom count does not fit usize",
            )
        })?;

        let receptor_donor_atom = scientific
            .receptor
            .donors
            .iter()
            .map(|donor| donor.donor_atom_index)
            .collect::<Vec<_>>();
        let receptor_hydrogen_atom = scientific
            .receptor
            .donors
            .iter()
            .map(|donor| donor.hydrogen_atom_index)
            .collect::<Vec<_>>();
        let ligand_donor_atom = scientific
            .ligand
            .donors
            .iter()
            .map(|donor| donor.donor_atom_index)
            .collect::<Vec<_>>();
        let ligand_hydrogen_atom = scientific
            .ligand
            .donors
            .iter()
            .map(|donor| donor.hydrogen_atom_index)
            .collect::<Vec<_>>();
        let exclusion_i = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| pair.atom_i)
            .collect::<Vec<_>>();
        let exclusion_j = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| pair.atom_j)
            .collect::<Vec<_>>();
        let bond_i = scientific
            .ligand
            .bonds
            .iter()
            .map(|pair| pair.atom_i)
            .collect::<Vec<_>>();
        let bond_j = scientific
            .ligand
            .bonds
            .iter()
            .map(|pair| pair.atom_j)
            .collect::<Vec<_>>();
        let internal_i = scientific
            .ligand
            .internal_pairs
            .iter()
            .map(|pair| pair.atom_i)
            .collect::<Vec<_>>();
        let internal_j = scientific
            .ligand
            .internal_pairs
            .iter()
            .map(|pair| pair.atom_j)
            .collect::<Vec<_>>();
        let rotor_i = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_i)
            .collect::<Vec<_>>();
        let rotor_j = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_j)
            .collect::<Vec<_>>();
        let rotor_k = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_k)
            .collect::<Vec<_>>();
        let rotor_l = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| rotor.atom_l)
            .collect::<Vec<_>>();
        let chirality_center = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.center_atom)
            .collect::<Vec<_>>();
        let chirality_i = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.atom_i)
            .collect::<Vec<_>>();
        let chirality_j = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.atom_j)
            .collect::<Vec<_>>();
        let chirality_k = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| center.atom_k)
            .collect::<Vec<_>>();

        let mut admission = init(sys::bg_docking_geometric_admission_context_soa_v1_init)?;
        admission.receptor_atom_count = counts.receptor_atom_count;
        admission.ligand_atom_count = counts.ligand_atom_count;
        admission.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        admission.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        admission.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        admission.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        admission.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        admission.ligand_heavy_atom_mask = scientific.ligand.heavy_atom_mask.as_ptr();
        admission.pocket_center_angstrom = scientific.pocket_center_angstrom;
        admission.pocket_radius_angstrom = scientific.pocket_radius_angstrom;
        assign_shared_identities(&mut admission, scientific.identities);

        let mut rigid = init(sys::bg_docking_rigid_refinement_context_soa_v1_init)?;
        rigid.receptor_atom_count = counts.receptor_atom_count;
        rigid.ligand_atom_count = counts.ligand_atom_count;
        rigid.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        rigid.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        rigid.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        rigid.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        rigid.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        rigid.pocket_center_angstrom = scientific.pocket_center_angstrom;
        rigid.pocket_radius_angstrom = scientific.pocket_radius_angstrom;

        let mut torsion = init(sys::bg_docking_torsion_v7_context_soa_v1_init)?;
        torsion.receptor_atom_count = counts.receptor_atom_count;
        torsion.ligand_atom_count = counts.ligand_atom_count;
        torsion.rotor_count = checked_count(scientific.ligand.rotatable_child_atom_index.len())?;
        torsion.internal_pair_count = checked_count(scientific.ligand.internal_pairs.len())?;
        torsion.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        torsion.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        torsion.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        torsion.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        torsion.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        torsion.pocket_center_angstrom = scientific.pocket_center_angstrom;
        torsion.parent_atom_index = scientific.ligand.parent_atom_index.as_ptr();
        torsion.rotatable_child_atom_index =
            slice_pointer(scientific.ligand.rotatable_child_atom_index);
        torsion.internal_pair_atom_i = slice_pointer(&internal_i);
        torsion.internal_pair_atom_j = slice_pointer(&internal_j);

        let mut scorer = init(sys::bg_docking_scorer_v1_context_soa_v1_init)?;
        scorer.receptor_atom_count = counts.receptor_atom_count;
        scorer.ligand_atom_count = counts.ligand_atom_count;
        scorer.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        scorer.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        scorer.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        scorer.receptor_charge_elementary = scientific.receptor.charge_elementary.as_ptr();
        scorer.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        scorer.receptor_epsilon_kcal_per_mol = scientific.receptor.epsilon_kcal_per_mol.as_ptr();
        scorer.receptor_hydrophobic = scientific.receptor.hydrophobic_mask.as_ptr();
        scorer.receptor_acceptor = scientific.receptor.acceptor_mask.as_ptr();
        scorer.ligand_reference_x_angstrom =
            scientific.ligand.reference_coordinates.x_angstrom.as_ptr();
        scorer.ligand_reference_y_angstrom =
            scientific.ligand.reference_coordinates.y_angstrom.as_ptr();
        scorer.ligand_reference_z_angstrom =
            scientific.ligand.reference_coordinates.z_angstrom.as_ptr();
        scorer.ligand_charge_elementary = scientific.ligand.charge_elementary.as_ptr();
        scorer.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        scorer.ligand_epsilon_kcal_per_mol = scientific.ligand.epsilon_kcal_per_mol.as_ptr();
        scorer.ligand_hydrophobic = scientific.ligand.hydrophobic_mask.as_ptr();
        scorer.ligand_acceptor = scientific.ligand.acceptor_mask.as_ptr();
        scorer.receptor_donor_count = checked_count(receptor_donor_atom.len())?;
        scorer.receptor_donor_atom_index = slice_pointer(&receptor_donor_atom);
        scorer.receptor_hydrogen_atom_index = slice_pointer(&receptor_hydrogen_atom);
        scorer.ligand_donor_count = checked_count(ligand_donor_atom.len())?;
        scorer.ligand_donor_atom_index = slice_pointer(&ligand_donor_atom);
        scorer.ligand_hydrogen_atom_index = slice_pointer(&ligand_hydrogen_atom);
        scorer.ligand_exclusion_count = checked_count(exclusion_i.len())?;
        scorer.ligand_exclusion_atom_i = slice_pointer(&exclusion_i);
        scorer.ligand_exclusion_atom_j = slice_pointer(&exclusion_j);
        scorer.rotor_count = checked_count(rotor_i.len())?;
        scorer.rotor_atom_i = slice_pointer(&rotor_i);
        scorer.rotor_atom_j = slice_pointer(&rotor_j);
        scorer.rotor_atom_k = slice_pointer(&rotor_k);
        scorer.rotor_atom_l = slice_pointer(&rotor_l);
        scorer.pocket_center_angstrom = scientific.pocket_center_angstrom;
        scorer.pocket_radius_angstrom = scientific.pocket_radius_angstrom;
        scorer.authority_input_receipt_sha256 =
            scientific.identities.authority_input_receipt_sha256;
        scorer.receptor_system_sha256 = scientific.identities.receptor_system_sha256;
        scorer.ligand_system_sha256 = scientific.identities.ligand_system_sha256;
        scorer.backend_receipt_sha256 = scientific.identities.backend_receipt_sha256;

        let mut validity = init(sys::bg_docking_pose_validity_context_soa_v1_init)?;
        validity.receptor_atom_count = counts.receptor_atom_count;
        validity.ligand_atom_count = counts.ligand_atom_count;
        validity.receptor_x_angstrom = scientific.receptor.coordinates.x_angstrom.as_ptr();
        validity.receptor_y_angstrom = scientific.receptor.coordinates.y_angstrom.as_ptr();
        validity.receptor_z_angstrom = scientific.receptor.coordinates.z_angstrom.as_ptr();
        validity.receptor_vdw_radius_angstrom = scientific.receptor.vdw_radius_angstrom.as_ptr();
        validity.ligand_reference_x_angstrom =
            scientific.ligand.reference_coordinates.x_angstrom.as_ptr();
        validity.ligand_reference_y_angstrom =
            scientific.ligand.reference_coordinates.y_angstrom.as_ptr();
        validity.ligand_reference_z_angstrom =
            scientific.ligand.reference_coordinates.z_angstrom.as_ptr();
        validity.ligand_vdw_radius_angstrom = scientific.ligand.vdw_radius_angstrom.as_ptr();
        validity.bond_count = checked_count(bond_i.len())?;
        validity.bond_atom_i = slice_pointer(&bond_i);
        validity.bond_atom_j = slice_pointer(&bond_j);
        validity.ligand_exclusion_count = checked_count(exclusion_i.len())?;
        validity.ligand_exclusion_atom_i = slice_pointer(&exclusion_i);
        validity.ligand_exclusion_atom_j = slice_pointer(&exclusion_j);
        validity.chirality_center_count = checked_count(chirality_center.len())?;
        validity.chirality_center_atom = slice_pointer(&chirality_center);
        validity.chirality_atom_i = slice_pointer(&chirality_i);
        validity.chirality_atom_j = slice_pointer(&chirality_j);
        validity.chirality_atom_k = slice_pointer(&chirality_k);
        validity.pocket_center_angstrom = scientific.pocket_center_angstrom;
        validity.pocket_radius_angstrom = scientific.pocket_radius_angstrom;
        validity.authority_input_receipt_sha256 =
            scientific.identities.authority_input_receipt_sha256;
        validity.receptor_system_sha256 = scientific.identities.receptor_system_sha256;
        validity.ligand_system_sha256 = scientific.identities.ligand_system_sha256;
        validity.scorer_context_receipt_sha256 =
            scientific.identities.validity_scorer_context_receipt_sha256;
        validity.backend_receipt_sha256 = scientific.identities.backend_receipt_sha256;
        validity.contact_policy_sha256 = scientific.identities.contact_policy_sha256;
        let validity_exclusion_count = checked_count(scientific.ligand.exclusions.len())?;
        let validity_chirality_count = checked_count(scientific.ligand.chirality_centers.len())?;
        let ligand_heavy_atom_count = checked_count(
            scientific
                .ligand
                .heavy_atom_mask
                .iter()
                .filter(|value| **value != 0)
                .count(),
        )?;
        let geometric_hard_rejection_minimum_vdw_ratio = admission.hard_rejection_minimum_vdw_ratio;
        let geometric_max_batch_exact_pair_evaluations = admission.max_batch_exact_pair_evaluations;
        let maximum_torsion_steps = torsion.maximum_torsion_steps;
        let validity_contact_cell_size_angstrom = validity.contact_cell_size_angstrom;
        let validity_receptor_cells = validity_receptor_cells(
            scientific.receptor.coordinates,
            validity_contact_cell_size_angstrom,
        )?;
        let rotatable_child_atom_indices = scientific.ligand.rotatable_child_atom_index.to_vec();

        let receptor_coordinates = position_soa_to_vec3(scientific.receptor.coordinates);
        let ligand_reference_coordinates =
            position_soa_to_vec3(scientific.ligand.reference_coordinates);
        let geometric_input = IndependentFixed64GeometricInput::new(
            scientific.ligand.vdw_radius_angstrom.to_vec(),
            scientific
                .ligand
                .heavy_atom_mask
                .iter()
                .map(|value| *value != 0)
                .collect(),
            receptor_coordinates.clone(),
            scientific.receptor.vdw_radius_angstrom.to_vec(),
            Vec3::new(
                scientific.pocket_center_angstrom[0],
                scientific.pocket_center_angstrom[1],
                scientific.pocket_center_angstrom[2],
            ),
            scientific.pocket_radius_angstrom,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 geometric context rejected safe input: {error}"),
            )
        })?;
        let rigid_v2_config = independent_rigid_v2_config(&rigid.v2)?;
        let rigid_v3_config = independent_rigid_v3_config(&rigid.v3)?;
        let rigid_clearance_config = independent_rigid_v3_config(&rigid.clearance_v4)?;
        let scorer_config = IndependentScorerConfig::new(
            scorer.weights,
            scorer.electrostatic_dielectric,
            scorer.pair_cutoff_angstrom,
            scorer.hbond_distance_max_angstrom,
            scorer.polar_burial_distance_angstrom,
            usize::try_from(scorer.max_receptor_candidate_pairs).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 scorer receptor-pair capacity does not fit usize",
                )
            })?,
            usize::try_from(scorer.max_ligand_pair_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 scorer ligand-pair capacity does not fit usize",
                )
            })?,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 scorer config rejected safe input: {error}"),
            )
        })?;
        let receptor_atoms = (0..receptor_count)
            .map(|atom| IndependentScorerAtom {
                charge_elementary: scientific.receptor.charge_elementary[atom],
                vdw_radius_angstrom: scientific.receptor.vdw_radius_angstrom[atom],
                epsilon_kcal_per_mol: scientific.receptor.epsilon_kcal_per_mol[atom],
                hydrophobic: scientific.receptor.hydrophobic_mask[atom] != 0,
                acceptor: scientific.receptor.acceptor_mask[atom] != 0,
            })
            .collect::<Vec<_>>();
        let ligand_atoms = (0..ligand_count)
            .map(|atom| IndependentScorerAtom {
                charge_elementary: scientific.ligand.charge_elementary[atom],
                vdw_radius_angstrom: scientific.ligand.vdw_radius_angstrom[atom],
                epsilon_kcal_per_mol: scientific.ligand.epsilon_kcal_per_mol[atom],
                hydrophobic: scientific.ligand.hydrophobic_mask[atom] != 0,
                acceptor: scientific.ligand.acceptor_mask[atom] != 0,
            })
            .collect::<Vec<_>>();
        let receptor_donors = scientific
            .receptor
            .donors
            .iter()
            .map(|donor| u64_donor_to_usize(*donor, "receptor"))
            .collect::<Result<Vec<_>>>()?;
        let ligand_donors = scientific
            .ligand
            .donors
            .iter()
            .map(|donor| u64_donor_to_usize(*donor, "ligand"))
            .collect::<Result<Vec<_>>>()?;
        let scorer_exclusions = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| u64_pair_to_usize(*pair, "scorer exclusion"))
            .collect::<Result<Vec<_>>>()?;
        let scorer_rotors = scientific
            .ligand
            .rotors
            .iter()
            .map(|rotor| u64_rotor_to_usize(*rotor))
            .collect::<Result<Vec<_>>>()?;
        let scorer_context = IndependentScorerContext::new(
            scientific.identities.authority_input_receipt_sha256,
            scientific.identities.receptor_system_sha256,
            scientific.identities.ligand_system_sha256,
            IndependentScorerBackend::RustCpu,
            scientific.identities.backend_receipt_sha256,
            receptor_coordinates.clone(),
            receptor_atoms,
            ligand_reference_coordinates.clone(),
            ligand_atoms,
            receptor_donors,
            ligand_donors,
            scorer_exclusions,
            scorer_rotors,
            Vec3::new(
                scientific.pocket_center_angstrom[0],
                scientific.pocket_center_angstrom[1],
                scientific.pocket_center_angstrom[2],
            ),
            scientific.pocket_radius_angstrom,
            scorer_config,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 scorer context rejected safe input: {error}"),
            )
        })?;
        let validity_config = IndependentValidityConfig::new(
            validity.bond_length_tolerance_angstrom,
            validity.ligand_self_clash_angstrom,
            validity.receptor_ligand_clash_angstrom,
            validity.rotation_tolerance,
            validity.chirality_volume_tolerance,
            validity.severe_overlap_scale,
            validity.contact_cell_size_angstrom,
            usize::try_from(validity.max_pair_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity pair capacity does not fit usize",
                )
            })?,
            usize::try_from(validity.max_cross_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity cross capacity does not fit usize",
                )
            })?,
            usize::try_from(validity.max_element_ligand_pair_checks).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity element ligand capacity does not fit usize",
                )
            })?,
            usize::try_from(validity.max_element_receptor_candidate_pairs).map_err(|_| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 validity element receptor capacity does not fit usize",
                )
            })?,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 validity config rejected safe input: {error}"),
            )
        })?;
        let bond_pairs = scientific
            .ligand
            .bonds
            .iter()
            .map(|pair| u64_pair_to_usize(*pair, "bond"))
            .collect::<Result<Vec<_>>>()?;
        let excluded_pairs = scientific
            .ligand
            .exclusions
            .iter()
            .map(|pair| u64_pair_to_usize(*pair, "exclusion"))
            .collect::<Result<Vec<_>>>()?;
        let chirality_centers = scientific
            .ligand
            .chirality_centers
            .iter()
            .map(|center| {
                Ok([
                    usize::try_from(center.center_atom).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality center does not fit usize",
                        )
                    })?,
                    usize::try_from(center.atom_i).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality atom i does not fit usize",
                        )
                    })?,
                    usize::try_from(center.atom_j).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality atom j does not fit usize",
                        )
                    })?,
                    usize::try_from(center.atom_k).map_err(|_| {
                        Error::local(
                            ErrorCode::CapacityOverflow,
                            "fixed64 chirality atom k does not fit usize",
                        )
                    })?,
                ])
            })
            .collect::<Result<Vec<_>>>()?;
        let validity_context = IndependentValidityContext::new(
            scientific.identities.authority_input_receipt_sha256,
            scientific.identities.receptor_system_sha256,
            scientific.identities.ligand_system_sha256,
            scientific.identities.validity_scorer_context_receipt_sha256,
            IndependentValidityBackend::RustCpu,
            scientific.identities.backend_receipt_sha256,
            scientific.identities.contact_policy_sha256,
            ligand_reference_coordinates,
            receptor_coordinates,
            scientific.ligand.vdw_radius_angstrom.to_vec(),
            scientific.receptor.vdw_radius_angstrom.to_vec(),
            bond_pairs,
            excluded_pairs,
            chirality_centers,
            Vec3::new(
                scientific.pocket_center_angstrom[0],
                scientific.pocket_center_angstrom[1],
                scientific.pocket_center_angstrom[2],
            ),
            scientific.pocket_radius_angstrom,
            validity_config,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 validity context rejected safe input: {error}"),
            )
        })?;
        let expected_admission_context_receipt_sha256 = canonical_admission_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &admission,
        );
        let expected_refinement_context_receipt_sha256 = canonical_refinement_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &rigid,
            &torsion,
        );
        let expected_scorer_context_receipt_sha256 = canonical_scorer_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &scorer,
            &receptor_donor_atom,
            &receptor_hydrogen_atom,
            &ligand_donor_atom,
            &ligand_hydrogen_atom,
            &exclusion_i,
            &exclusion_j,
            &rotor_i,
            &rotor_j,
            &rotor_k,
            &rotor_l,
        );
        let expected_validity_context_receipt_sha256 = canonical_validity_context_receipt(
            expected_backend,
            device_ordinal,
            scientific,
            &validity,
            &bond_i,
            &bond_j,
            &exclusion_i,
            &exclusion_j,
            &chirality_center,
            &chirality_i,
            &chirality_j,
            &chirality_k,
        );
        let expected_component_binding_receipt_sha256 = canonical_component_binding_receipt(
            expected_backend,
            device_ordinal,
            expected_admission_context_receipt_sha256,
            expected_refinement_context_receipt_sha256,
            expected_scorer_context_receipt_sha256,
            expected_validity_context_receipt_sha256,
        );

        let mut handle = ptr::null_mut();
        // SAFETY: every descriptor points to validated slices that remain live
        // for this call; the native constructor deep-copies all channels.
        status_result(unsafe {
            sys::bg_docking_fixed64_pipeline_v2_create(
                context.raw_handle(),
                &admission,
                &rigid,
                &torsion,
                &scorer,
                &validity,
                &mut handle,
            )
        })?;
        let handle = NonNull::new(handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native fixed64 pipeline creation succeeded with a null handle",
            )
        })?;
        let handle = PipelineHandleGuard(handle);
        let mut raw_backend = sys::BG_BACKEND_AUTO;
        // SAFETY: handle is live and raw_backend is valid writable storage.
        status_result(unsafe {
            sys::bg_docking_fixed64_pipeline_v2_get_backend(handle.0.as_ptr(), &mut raw_backend)
        })?;
        let backend = Backend::from_raw(raw_backend)?;
        if backend != expected_backend {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline backend changed during construction",
            ));
        }
        let mut replay_admission_handle = ptr::null_mut();
        // SAFETY: the validated descriptor remains live for this call and the
        // native constructor deep-copies every molecular channel.
        status_result(unsafe {
            sys::bg_docking_geometric_admission_v1_create(
                context.raw_handle(),
                &admission,
                &mut replay_admission_handle,
            )
        })?;
        let replay_admission_handle = NonNull::new(replay_admission_handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native replay admission creation succeeded with a null handle",
            )
        })?;
        let replay_admission_handle = GeometricAdmissionHandleGuard(replay_admission_handle);
        let mut replay_backend = sys::BG_BACKEND_AUTO;
        // SAFETY: the guarded handle is live and replay_backend is writable.
        status_result(unsafe {
            sys::bg_docking_geometric_admission_v1_get_backend(
                replay_admission_handle.0.as_ptr(),
                &mut replay_backend,
            )
        })?;
        if Backend::from_raw(replay_backend)? != backend {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native replay admission backend changed during construction",
            ));
        }
        let preselected_handles = if include_preselected {
            let mut preselected_rigid_handle = ptr::null_mut();
            // SAFETY: the validated descriptor remains live for this call and the
            // native constructor deep-copies every molecular channel.
            status_result(unsafe {
                sys::bg_docking_rigid_refinement_create(
                    context.raw_handle(),
                    &rigid,
                    &mut preselected_rigid_handle,
                )
            })?;
            let preselected_rigid_handle =
                NonNull::new(preselected_rigid_handle).ok_or_else(|| {
                    Error::local(
                        ErrorCode::InternalError,
                        "native preselected rigid creation succeeded with a null handle",
                    )
                })?;
            let preselected_rigid_handle = RigidHandleGuard(preselected_rigid_handle);

            let mut preselected_torsion_handle = ptr::null_mut();
            // SAFETY: the validated descriptor remains live for this call and the
            // native constructor deep-copies every molecular channel.
            status_result(unsafe {
                sys::bg_docking_torsion_v7_create(
                    context.raw_handle(),
                    &torsion,
                    &mut preselected_torsion_handle,
                )
            })?;
            let preselected_torsion_handle =
                NonNull::new(preselected_torsion_handle).ok_or_else(|| {
                    Error::local(
                        ErrorCode::InternalError,
                        "native preselected torsion creation succeeded with a null handle",
                    )
                })?;
            let preselected_torsion_handle = TorsionHandleGuard(preselected_torsion_handle);

            let mut preselected_downstream_handle = ptr::null_mut();
            // SAFETY: both validated descriptors remain live for this call and the
            // native constructor deep-copies every molecular channel.
            status_result(unsafe {
                sys::bg_docking_fixed64_downstream_v1_create(
                    context.raw_handle(),
                    &scorer,
                    &validity,
                    &mut preselected_downstream_handle,
                )
            })?;
            let preselected_downstream_handle = NonNull::new(preselected_downstream_handle)
                .ok_or_else(|| {
                    Error::local(
                        ErrorCode::InternalError,
                        "native preselected downstream creation succeeded with a null handle",
                    )
                })?;
            let preselected_downstream_handle =
                DownstreamHandleGuard(preselected_downstream_handle);

            let mut preselected_ranker_handle = ptr::null_mut();
            // SAFETY: the output pointer is writable and the native constructor
            // binds the new ranker to the exact context backend/device.
            status_result(unsafe {
                sys::bg_docking_stable_top_k_v1_create(
                    context.raw_handle(),
                    &mut preselected_ranker_handle,
                )
            })?;
            let preselected_ranker_handle =
                NonNull::new(preselected_ranker_handle).ok_or_else(|| {
                    Error::local(
                        ErrorCode::InternalError,
                        "native preselected ranker creation succeeded with a null handle",
                    )
                })?;
            let preselected_ranker_handle = RankerHandleGuard(preselected_ranker_handle);

            for (label, observed) in [
                (
                    "rigid",
                    preselected_component_backend(|output| unsafe {
                        sys::bg_docking_rigid_refinement_get_backend(
                            preselected_rigid_handle.0.as_ptr(),
                            output,
                        )
                    })?,
                ),
                (
                    "torsion",
                    preselected_component_backend(|output| unsafe {
                        sys::bg_docking_torsion_v7_get_backend(
                            preselected_torsion_handle.0.as_ptr(),
                            output,
                        )
                    })?,
                ),
                (
                    "downstream",
                    preselected_component_backend(|output| unsafe {
                        sys::bg_docking_fixed64_downstream_v1_get_backend(
                            preselected_downstream_handle.0.as_ptr(),
                            output,
                        )
                    })?,
                ),
                (
                    "ranker",
                    preselected_component_backend(|output| unsafe {
                        sys::bg_docking_stable_top_k_v1_get_backend(
                            preselected_ranker_handle.0.as_ptr(),
                            output,
                        )
                    })?,
                ),
            ] {
                if observed != backend {
                    return Err(Error::local(
                        ErrorCode::AbiMismatch,
                        format!("native preselected {label} backend changed during construction"),
                    ));
                }
            }
            Some(PreselectedHandles {
                rigid: preselected_rigid_handle.into_inner(),
                torsion: preselected_torsion_handle.into_inner(),
                downstream: preselected_downstream_handle.into_inner(),
                ranker: preselected_ranker_handle.into_inner(),
            })
        } else {
            None
        };
        Ok((
            Self {
                handle: handle.into_inner(),
                replay_admission_handle: replay_admission_handle.into_inner(),
                context_lease: context.lease(),
                backend,
                receptor_atom_count: receptor_count,
                ligand_atom_count: ligand_count,
                ligand_heavy_atom_count,
                geometric_hard_rejection_minimum_vdw_ratio,
                geometric_max_batch_exact_pair_evaluations,
                geometric_input,
                rigid_v2_config,
                rigid_v3_config,
                rigid_clearance_config,
                scorer_context,
                maximum_torsion_steps,
                receptor_system_sha256: scientific.identities.receptor_system_sha256,
                ligand_system_sha256: scientific.identities.ligand_system_sha256,
                authority_input_receipt_sha256: scientific
                    .identities
                    .authority_input_receipt_sha256,
                backend_receipt_sha256: scientific.identities.backend_receipt_sha256,
                pocket_center_angstrom: scientific.pocket_center_angstrom,
                expected_admission_context_receipt_sha256,
                expected_refinement_context_receipt_sha256,
                expected_scorer_context_receipt_sha256,
                expected_validity_context_receipt_sha256,
                expected_component_binding_receipt_sha256,
                rotatable_child_atom_indices,
                validity_exclusion_count,
                validity_chirality_count,
                validity_contact_cell_size_angstrom,
                validity_receptor_cells,
                validity_context,
                _not_send_or_sync: PhantomData,
            },
            preselected_handles,
        ))
    }

    pub const fn backend(&self) -> Backend {
        self.backend
    }

    pub const fn receptor_atom_count(&self) -> usize {
        self.receptor_atom_count
    }

    pub const fn ligand_atom_count(&self) -> usize {
        self.ligand_atom_count
    }

    pub fn run(&self, input: Fixed64RunInput<'_>) -> Result<Fixed64PipelineReceipt> {
        const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        const TOP_K_LIMIT: usize = sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize;
        const MOVE_COUNT: usize = CANDIDATE_COUNT * sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
        validate_run_input(
            input,
            self.ligand_atom_count,
            self.receptor_system_sha256,
            self.ligand_system_sha256,
        )?;
        let raw_pocket_normal = input.pocket_normal;
        let input = Fixed64RunInput {
            pocket_normal: canonical_pocket_normal(input.pocket_normal)?,
            ..input
        };
        // The producer normalizes the caller vector once, then the indexed-SO3
        // component normalizes that canonical producer value once more. Keep
        // both stages explicit so replay uses the same frozen seed bits.
        let component_pocket_normal = canonical_pocket_normal(input.pocket_normal)?;
        let expected_sources: [Option<Fixed64CoordinateSource<'_>>; CANDIDATE_COUNT] =
            std::array::from_fn(|slot| fixed64_source_for_slot(input, slot));
        let coordinate_count = self
            .ligand_atom_count
            .checked_mul(CANDIDATE_COUNT)
            .ok_or_else(|| {
                Error::local(
                    ErrorCode::CapacityOverflow,
                    "fixed64 output coordinate denominator overflows usize",
                )
            })?;
        let coordinate_count_u64 = checked_count(coordinate_count)?;
        let receptor_atom_count_u64 = checked_count(self.receptor_atom_count)?;
        let ligand_atom_count_u64 = checked_count(self.ligand_atom_count)?;
        let expected_allocation = independent_allocation(input)?;
        let expected_feature_geometry_inventory = independent_feature_geometry_inventory(input)?;
        let source_bundle_receipt_sha256 = canonical_source_bundle_receipt(
            input,
            expected_allocation.receipt_sha256(),
            ligand_atom_count_u64,
            self.pocket_center_angstrom,
            self.authority_input_receipt_sha256,
            self.receptor_system_sha256,
            self.ligand_system_sha256,
            self.backend_receipt_sha256,
        )?;
        let refinement_policy_receipt_sha256 = canonical_refinement_policy_receipt(
            self.expected_refinement_context_receipt_sha256,
            self.expected_component_binding_receipt_sha256,
            expected_allocation.receipt_sha256(),
            input,
        );
        let post_admission_policy_receipt_sha256 = canonical_post_admission_policy_receipt(
            self.expected_admission_context_receipt_sha256,
            self.expected_component_binding_receipt_sha256,
            refinement_policy_receipt_sha256,
            expected_allocation.receipt_sha256(),
            input,
        );
        let expected_receipt_graph = ExpectedPipelineReceiptGraph {
            allocation_inventory_sha256: expected_allocation.inventory_sha256(),
            allocation_receipt_sha256: expected_allocation.receipt_sha256(),
            source_bundle_receipt_sha256,
            admission_context_receipt_sha256: self.expected_admission_context_receipt_sha256,
            refinement_context_receipt_sha256: self.expected_refinement_context_receipt_sha256,
            scorer_context_receipt_sha256: self.expected_scorer_context_receipt_sha256,
            validity_context_receipt_sha256: self.expected_validity_context_receipt_sha256,
            component_binding_receipt_sha256: self.expected_component_binding_receipt_sha256,
            refinement_policy_receipt_sha256,
            post_admission_policy_receipt_sha256,
            authority_input_receipt_sha256: self.authority_input_receipt_sha256,
            receptor_system_sha256: self.receptor_system_sha256,
            ligand_system_sha256: self.ligand_system_sha256,
            backend_receipt_sha256: self.backend_receipt_sha256,
            backend: self.backend,
            receptor_atom_count: receptor_atom_count_u64,
            ligand_atom_count: ligand_atom_count_u64,
            ligand_heavy_atom_count: self.ligand_heavy_atom_count,
            geometric_max_batch_exact_pair_evaluations: self
                .geometric_max_batch_exact_pair_evaluations,
            pocket_center_angstrom: self.pocket_center_angstrom,
            pocket_radius_angstrom: self.geometric_input.pocket_radius_angstrom(),
            geometric_hard_rejection_minimum_vdw_ratio: self
                .geometric_hard_rejection_minimum_vdw_ratio,
        };

        let exact_evidence = sys::bg_docking_fixed64_exact_source_evidence_v1 {
            source_receipt_sha256: input.exact_source_evidence.source_receipt_sha256,
            proposal_sha256: input.exact_source_evidence.proposal_sha256,
            ligand_coordinate_sha256: input.exact_source_evidence.ligand_coordinate_sha256,
            receptor_coordinate_sha256: input.exact_source_evidence.receptor_coordinate_sha256,
            prepared_ligand_topology_sha256: input
                .exact_source_evidence
                .prepared_ligand_topology_sha256,
            prepared_receptor_topology_sha256: input
                .exact_source_evidence
                .prepared_receptor_topology_sha256,
            ligand_vdw_radii_sha256: input.exact_source_evidence.ligand_vdw_radii_sha256,
            ligand_heavy_atom_mask_sha256: input
                .exact_source_evidence
                .ligand_heavy_atom_mask_sha256,
            receptor_vdw_radii_sha256: input.exact_source_evidence.receptor_vdw_radii_sha256,
            reserved: [0; 4],
        };
        let atomic_features = input
            .atomic_features
            .iter()
            .map(
                |feature| sys::bg_docking_fixed64_atomic_feature_evidence_v1 {
                    kind: feature.kind.as_raw(),
                    reserved0: 0,
                    receipt_sha256: feature.receipt_sha256,
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let v7_evidence = input
            .v7_control_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_source_evidence_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    source: raw_source_evidence(source.source.evidence),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let conformer_evidence = input
            .conformer_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_conformer_source_evidence_v1 {
                    rank: source.rank,
                    reserved0: [0; 7],
                    source: raw_source_evidence(source.source.evidence),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let retained_evidence = input
            .retained_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_source_evidence_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    source: raw_source_evidence(source.source.evidence),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let mut allocation = init(sys::bg_docking_fixed64_allocation_input_v1_init)?;
        allocation.exact_v11_source = exact_evidence;
        allocation.atomic_feature_count = checked_count(atomic_features.len())?;
        allocation.atomic_features = slice_pointer(&atomic_features);
        allocation.v7_control_source_count = checked_count(v7_evidence.len())?;
        allocation.v7_control_sources = slice_pointer(&v7_evidence);
        allocation.conformer_source_count = checked_count(conformer_evidence.len())?;
        allocation.conformer_sources = slice_pointer(&conformer_evidence);
        allocation.retained_source_count = checked_count(retained_evidence.len())?;
        allocation.retained_sources = slice_pointer(&retained_evidence);

        let exact_source = raw_coordinate_source(input.exact_source, ligand_atom_count_u64);
        let v7_sources = input
            .v7_control_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_coordinate_source_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    payload: raw_coordinate_source(source.source, ligand_atom_count_u64),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let conformer_sources = input
            .conformer_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_conformer_coordinate_source_v1 {
                    rank: source.rank,
                    reserved0: [0; 7],
                    payload: raw_coordinate_source(source.source, ligand_atom_count_u64),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let retained_sources = input
            .retained_sources
            .iter()
            .map(
                |source| sys::bg_docking_fixed64_indexed_coordinate_source_v1 {
                    source_index: source.source_index,
                    reserved0: 0,
                    payload: raw_coordinate_source(source.source, ligand_atom_count_u64),
                    reserved: [0; 2],
                },
            )
            .collect::<Vec<_>>();
        let mut feature_atom_indices = Vec::new();
        let mut feature_rows = Vec::with_capacity(input.feature_geometries.len());
        for geometry in input.feature_geometries {
            let offset = checked_count(feature_atom_indices.len())?;
            feature_atom_indices.extend_from_slice(geometry.atom_indices);
            feature_rows.push(sys::bg_docking_fixed64_feature_geometry_row_v1 {
                kind: geometry.kind.as_raw(),
                reserved0: 0,
                allocation_feature_receipt_sha256: geometry.allocation_feature_receipt_sha256,
                atom_index_offset: offset,
                atom_index_count: checked_count(geometry.atom_indices.len())?,
                feature_geometry_receipt_sha256: geometry.feature_geometry_receipt_sha256,
                reserved: [0; 4],
            });
        }
        let mut producer_input = init(sys::bg_docking_fixed64_producer_input_v1_init)?;
        producer_input.allocation_input = &allocation;
        producer_input.exact_v11_source = &exact_source;
        producer_input.v7_control_source_count = checked_count(v7_sources.len())?;
        producer_input.v7_control_sources = slice_pointer(&v7_sources);
        producer_input.conformer_source_count = checked_count(conformer_sources.len())?;
        producer_input.conformer_sources = slice_pointer(&conformer_sources);
        producer_input.retained_source_count = checked_count(retained_sources.len())?;
        producer_input.retained_sources = slice_pointer(&retained_sources);
        producer_input.feature_geometry_count = checked_count(feature_rows.len())?;
        producer_input.feature_geometry_rows = slice_pointer(&feature_rows);
        producer_input.feature_atom_index_count = checked_count(feature_atom_indices.len())?;
        producer_input.feature_atom_indices = slice_pointer(&feature_atom_indices);
        producer_input.feature_geometry_inventory_sha256 = input.feature_geometry_inventory_sha256;
        // The native producer performs the same scale-stable normalization once.
        // Preserve the caller vector here while the independent receipt graph uses
        // the once-canonicalized copy above; feeding the canonical copy to native
        // would normalize it twice and change some vectors by several ULPs.
        producer_input.pocket_normal = raw_pocket_normal;

        let raw_modes = input
            .candidate_modes
            .iter()
            .map(|mode| mode.as_raw())
            .collect::<Vec<_>>();
        let mut pipeline_input = init(sys::bg_docking_fixed64_pipeline_input_v2_init)?;
        pipeline_input.producer_input = &producer_input;
        pipeline_input.rmsd_threshold_angstrom = input.rmsd_threshold_angstrom;
        pipeline_input.candidate_mode = raw_modes.as_ptr();
        pipeline_input.rigid_max_steps = input.rigid_max_steps.as_ptr();
        pipeline_input.proposal_is_torsion_eligible = input.proposal_is_torsion_eligible.as_ptr();
        pipeline_input.torsion_max_steps = input.torsion_max_steps.as_ptr();
        pipeline_input.baseline_torsion_angles_radians =
            input.baseline_torsion_angles_radians.as_ptr();
        pipeline_input.predeclared_refinement_policy_sha256 =
            input.predeclared_refinement_policy_sha256;
        pipeline_input.predeclared_post_refinement_admission_policy_sha256 =
            input.predeclared_post_refinement_admission_policy_sha256;

        let mut producer_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1); CANDIDATE_COUNT];
        let mut producer_x = vec![0.0; coordinate_count];
        let mut producer_y = vec![0.0; coordinate_count];
        let mut producer_z = vec![0.0; coordinate_count];
        let mut producer_output = init(sys::bg_docking_fixed64_producer_output_v1_init)?;
        producer_output.row_capacity = CANDIDATE_COUNT as u64;
        producer_output.coordinate_capacity = coordinate_count_u64;
        producer_output.rows = producer_rows.as_mut_ptr();
        producer_output.x_angstrom = producer_x.as_mut_ptr();
        producer_output.y_angstrom = producer_y.as_mut_ptr();
        producer_output.z_angstrom = producer_z.as_mut_ptr();

        let mut rigid_rows =
            vec![zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1); CANDIDATE_COUNT];
        let mut rigid_coordinates: [Vec<f64>; 12] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut rigid_output = init(sys::bg_docking_rigid_refinement_output_v1_init)?;
        rigid_output.row_capacity = CANDIDATE_COUNT as u64;
        rigid_output.coordinate_capacity = coordinate_count_u64;
        rigid_output.rows = rigid_rows.as_mut_ptr();
        rigid_output.selected_x_angstrom = rigid_coordinates[0].as_mut_ptr();
        rigid_output.selected_y_angstrom = rigid_coordinates[1].as_mut_ptr();
        rigid_output.selected_z_angstrom = rigid_coordinates[2].as_mut_ptr();
        rigid_output.comparison_v2_x_angstrom = rigid_coordinates[3].as_mut_ptr();
        rigid_output.comparison_v2_y_angstrom = rigid_coordinates[4].as_mut_ptr();
        rigid_output.comparison_v2_z_angstrom = rigid_coordinates[5].as_mut_ptr();
        rigid_output.baseline_v3_x_angstrom = rigid_coordinates[6].as_mut_ptr();
        rigid_output.baseline_v3_y_angstrom = rigid_coordinates[7].as_mut_ptr();
        rigid_output.baseline_v3_z_angstrom = rigid_coordinates[8].as_mut_ptr();
        rigid_output.clearance_v4_x_angstrom = rigid_coordinates[9].as_mut_ptr();
        rigid_output.clearance_v4_y_angstrom = rigid_coordinates[10].as_mut_ptr();
        rigid_output.clearance_v4_z_angstrom = rigid_coordinates[11].as_mut_ptr();

        let mut torsion_rows =
            vec![zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1); CANDIDATE_COUNT];
        let mut torsion_moves =
            vec![zeroed_abi_value!(sys::bg_docking_torsion_v7_move_v1); MOVE_COUNT];
        let mut torsion_coordinates: [Vec<f64>; 8] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut torsion_output = init(sys::bg_docking_torsion_v7_output_v1_init)?;
        torsion_output.row_capacity = CANDIDATE_COUNT as u64;
        torsion_output.move_capacity = MOVE_COUNT as u64;
        torsion_output.coordinate_capacity = coordinate_count_u64;
        torsion_output.rows = torsion_rows.as_mut_ptr();
        torsion_output.moves = torsion_moves.as_mut_ptr();
        torsion_output.optimized_x_angstrom = torsion_coordinates[0].as_mut_ptr();
        torsion_output.optimized_y_angstrom = torsion_coordinates[1].as_mut_ptr();
        torsion_output.optimized_z_angstrom = torsion_coordinates[2].as_mut_ptr();
        torsion_output.optimized_torsion_angles_radians = torsion_coordinates[3].as_mut_ptr();
        torsion_output.final_x_angstrom = torsion_coordinates[4].as_mut_ptr();
        torsion_output.final_y_angstrom = torsion_coordinates[5].as_mut_ptr();
        torsion_output.final_z_angstrom = torsion_coordinates[6].as_mut_ptr();
        torsion_output.final_torsion_angles_radians = torsion_coordinates[7].as_mut_ptr();

        let mut scorer_rows =
            vec![zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1); CANDIDATE_COUNT];
        let mut scorer_output = init(sys::bg_docking_scorer_v1_output_v1_init)?;
        scorer_output.row_capacity = CANDIDATE_COUNT as u64;
        scorer_output.rows = scorer_rows.as_mut_ptr();
        let mut validity_rows =
            vec![zeroed_abi_value!(sys::bg_docking_pose_validity_row_v1); CANDIDATE_COUNT];
        let mut validity_output = init(sys::bg_docking_pose_validity_output_v1_init)?;
        validity_output.row_capacity = CANDIDATE_COUNT as u64;
        validity_output.rows = validity_rows.as_mut_ptr();
        let mut ranking_rows =
            vec![zeroed_abi_value!(sys::bg_docking_stable_top_k_row_v1); CANDIDATE_COUNT];
        let mut primary_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut valid_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut ranking_output = init(sys::bg_docking_stable_top_k_output_v1_init)?;
        ranking_output.row_capacity = CANDIDATE_COUNT as u64;
        ranking_output.primary_index_capacity = CANDIDATE_COUNT as u64;
        ranking_output.valid_index_capacity = CANDIDATE_COUNT as u64;
        ranking_output.rows = ranking_rows.as_mut_ptr();
        ranking_output.primary_slot_indices = primary_indices.as_mut_ptr();
        ranking_output.valid_slot_indices = valid_indices.as_mut_ptr();
        let mut cluster_rows =
            vec![zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1); CANDIDATE_COUNT];
        let mut representative_indices = vec![0_u32; CANDIDATE_COUNT];
        let mut top_k_indices = vec![0_u32; TOP_K_LIMIT];
        let mut cluster_output = init(sys::bg_docking_rmsd_cluster_output_v1_init)?;
        cluster_output.row_capacity = CANDIDATE_COUNT as u64;
        cluster_output.representative_index_capacity = CANDIDATE_COUNT as u64;
        cluster_output.top_k_index_capacity = TOP_K_LIMIT as u64;
        cluster_output.rows = cluster_rows.as_mut_ptr();
        cluster_output.representative_slot_indices = representative_indices.as_mut_ptr();
        cluster_output.top_k_slot_indices = top_k_indices.as_mut_ptr();
        let mut refinement_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1); CANDIDATE_COUNT];
        let mut final_coordinates: [Vec<f64>; 3] =
            std::array::from_fn(|_| vec![0.0; coordinate_count]);
        let mut final_quaternions: [Vec<f64>; 4] =
            std::array::from_fn(|_| vec![0.0; CANDIDATE_COUNT]);
        let mut refinement_output = init(sys::bg_docking_fixed64_refinement_output_v1_init)?;
        refinement_output.row_capacity = CANDIDATE_COUNT as u64;
        refinement_output.coordinate_capacity = coordinate_count_u64;
        refinement_output.quaternion_capacity = CANDIDATE_COUNT as u64;
        refinement_output.rows = refinement_rows.as_mut_ptr();
        refinement_output.final_x_angstrom = final_coordinates[0].as_mut_ptr();
        refinement_output.final_y_angstrom = final_coordinates[1].as_mut_ptr();
        refinement_output.final_z_angstrom = final_coordinates[2].as_mut_ptr();
        refinement_output.final_quaternion_x = final_quaternions[0].as_mut_ptr();
        refinement_output.final_quaternion_y = final_quaternions[1].as_mut_ptr();
        refinement_output.final_quaternion_z = final_quaternions[2].as_mut_ptr();
        refinement_output.final_quaternion_w = final_quaternions[3].as_mut_ptr();
        let mut post_admission_rows =
            vec![zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1); CANDIDATE_COUNT];
        let mut post_admission_output = init(sys::bg_docking_geometric_admission_output_v1_init)?;
        post_admission_output.row_capacity = CANDIDATE_COUNT as u64;
        post_admission_output.rows = post_admission_rows.as_mut_ptr();
        let mut pipeline_rows =
            vec![zeroed_abi_value!(sys::bg_docking_fixed64_pipeline_row_v2); CANDIDATE_COUNT];
        let mut pipeline_output = init(sys::bg_docking_fixed64_pipeline_output_v2_init)?;
        pipeline_output.row_capacity = CANDIDATE_COUNT as u64;
        pipeline_output.rows = pipeline_rows.as_mut_ptr();

        // SAFETY: all descriptors and output buffers remain live and uniquely
        // borrowed for the call. Their exact capacities were validated above.
        status_result(unsafe {
            sys::bg_docking_fixed64_pipeline_v2_run(
                self.context_lease.raw_handle(),
                self.handle.as_ptr(),
                &pipeline_input,
                &mut producer_output,
                &mut rigid_output,
                &mut torsion_output,
                &mut refinement_output,
                &mut post_admission_output,
                &mut scorer_output,
                &mut validity_output,
                &mut ranking_output,
                &mut cluster_output,
                &mut pipeline_output,
            )
        })?;
        let native_placement_replays = replay_native_placements(
            self.context_lease.as_ref(),
            self.replay_admission_handle,
            &allocation,
            &producer_input,
            &expected_allocation,
            expected_feature_geometry_inventory.as_ref(),
            &expected_sources,
            self.ligand_atom_count,
            self.pocket_center_angstrom,
            input.pocket_normal,
            self.backend,
        )?;
        validate_native_outputs(
            self.backend,
            &expected_receipt_graph,
            &expected_allocation,
            receptor_atom_count_u64,
            ligand_atom_count_u64,
            coordinate_count_u64,
            &producer_output,
            &rigid_output,
            &torsion_output,
            &scorer_output,
            &validity_output,
            &ranking_output,
            &cluster_output,
            &refinement_output,
            &post_admission_output,
            &pipeline_output,
            &producer_rows,
            &expected_sources,
            expected_feature_geometry_inventory.as_ref(),
            &native_placement_replays,
            component_pocket_normal,
            &rigid_rows,
            &torsion_rows,
            &torsion_moves,
            &scorer_rows,
            &validity_rows,
            &ranking_rows,
            &cluster_rows,
            &refinement_rows,
            &post_admission_rows,
            &pipeline_rows,
            &primary_indices,
            &valid_indices,
            &representative_indices,
            &top_k_indices,
            &raw_modes,
            input.rigid_max_steps,
            [
                producer_x.as_slice(),
                producer_y.as_slice(),
                producer_z.as_slice(),
            ],
            &rigid_coordinates,
            &torsion_coordinates,
            [
                final_coordinates[0].as_slice(),
                final_coordinates[1].as_slice(),
                final_coordinates[2].as_slice(),
            ],
            [
                final_quaternions[0].as_slice(),
                final_quaternions[1].as_slice(),
                final_quaternions[2].as_slice(),
                final_quaternions[3].as_slice(),
            ],
            input.rmsd_threshold_angstrom,
            self.ligand_heavy_atom_count,
            self.geometric_hard_rejection_minimum_vdw_ratio,
            &self.geometric_input,
            self.rigid_v2_config,
            self.rigid_v3_config,
            self.rigid_clearance_config,
            self.maximum_torsion_steps,
            input.proposal_is_torsion_eligible,
            input.torsion_max_steps,
            input.baseline_torsion_angles_radians,
            &self.rotatable_child_atom_indices,
            self.validity_exclusion_count,
            self.validity_chirality_count,
            self.validity_contact_cell_size_angstrom,
            &self.validity_receptor_cells,
            &self.scorer_context,
            &self.validity_context,
        )?;

        primary_indices.truncate(usize::try_from(ranking_output.primary_index_count).map_err(
            |_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "primary rank count does not fit usize",
                )
            },
        )?);
        valid_indices.truncate(usize::try_from(ranking_output.valid_index_count).map_err(
            |_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "valid rank count does not fit usize",
                )
            },
        )?);
        representative_indices.truncate(
            usize::try_from(cluster_output.representative_index_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "cluster representative count does not fit usize",
                )
            })?,
        );
        top_k_indices.truncate(usize::try_from(cluster_output.top_k_index_count).map_err(
            |_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "cluster Top-K count does not fit usize",
                )
            },
        )?);
        let [rigid_selected_x, rigid_selected_y, rigid_selected_z, rigid_comparison_v2_x, rigid_comparison_v2_y, rigid_comparison_v2_z, rigid_baseline_v3_x, rigid_baseline_v3_y, rigid_baseline_v3_z, rigid_clearance_v4_x, rigid_clearance_v4_y, rigid_clearance_v4_z] =
            rigid_coordinates;
        let [torsion_optimized_x, torsion_optimized_y, torsion_optimized_z, torsion_optimized_angles, torsion_final_x, torsion_final_y, torsion_final_z, torsion_final_angles] =
            torsion_coordinates;
        let [final_x, final_y, final_z] = final_coordinates;
        let mut receipt = Fixed64PipelineReceipt {
            backend: self.backend,
            unit_system: UnitSystem::from_raw(pipeline_output.unit_system)?,
            receptor_atom_count: self.receptor_atom_count,
            ligand_atom_count: self.ligand_atom_count,
            generated_count: pipeline_output.generated_count,
            typed_failure_count: producer_output.typed_failure_count,
            initial_admitted_count: pipeline_output.initial_admitted_count,
            refined_count: pipeline_output.refined_count,
            post_admitted_count: pipeline_output.post_admitted_count,
            post_rejected_count: pipeline_output.post_rejected_count,
            scored_count: pipeline_output.scored_count,
            valid_count: pipeline_output.valid_count,
            cluster_count: pipeline_output.cluster_count,
            producer_coordinates: super::PositionSoaOwned {
                x_angstrom: producer_x,
                y_angstrom: producer_y,
                z_angstrom: producer_z,
            },
            rigid_coordinates: Fixed64RigidCoordinates {
                selected: super::PositionSoaOwned {
                    x_angstrom: rigid_selected_x,
                    y_angstrom: rigid_selected_y,
                    z_angstrom: rigid_selected_z,
                },
                comparison_v2: super::PositionSoaOwned {
                    x_angstrom: rigid_comparison_v2_x,
                    y_angstrom: rigid_comparison_v2_y,
                    z_angstrom: rigid_comparison_v2_z,
                },
                baseline_v3: super::PositionSoaOwned {
                    x_angstrom: rigid_baseline_v3_x,
                    y_angstrom: rigid_baseline_v3_y,
                    z_angstrom: rigid_baseline_v3_z,
                },
                clearance_v4: super::PositionSoaOwned {
                    x_angstrom: rigid_clearance_v4_x,
                    y_angstrom: rigid_clearance_v4_y,
                    z_angstrom: rigid_clearance_v4_z,
                },
            },
            torsion_coordinates: Fixed64TorsionCoordinates {
                optimized: super::PositionSoaOwned {
                    x_angstrom: torsion_optimized_x,
                    y_angstrom: torsion_optimized_y,
                    z_angstrom: torsion_optimized_z,
                },
                optimized_torsion_angles_radians: torsion_optimized_angles,
                final_state: super::PositionSoaOwned {
                    x_angstrom: torsion_final_x,
                    y_angstrom: torsion_final_y,
                    z_angstrom: torsion_final_z,
                },
                final_torsion_angles_radians: torsion_final_angles,
            },
            final_coordinates: super::PositionSoaOwned {
                x_angstrom: final_x,
                y_angstrom: final_y,
                z_angstrom: final_z,
            },
            final_quaternions,
            producer_rows: producer_rows
                .iter()
                .map(producer_evidence)
                .collect::<Result<Vec<_>>>()?,
            rigid_rows: rigid_rows
                .iter()
                .map(rigid_evidence)
                .collect::<Result<Vec<_>>>()?,
            torsion_rows: torsion_rows
                .iter()
                .map(torsion_evidence)
                .collect::<Result<Vec<_>>>()?,
            torsion_moves: torsion_moves
                .iter()
                .map(torsion_move_evidence)
                .collect::<Result<Vec<_>>>()?,
            refinement_rows: refinement_rows
                .iter()
                .map(refinement_evidence)
                .collect::<Result<Vec<_>>>()?,
            post_admission_rows: post_admission_rows
                .iter()
                .map(geometric_evidence)
                .collect::<Result<Vec<_>>>()?,
            scorer_rows: scorer_rows.iter().map(scorer_evidence).collect(),
            validity_rows: validity_rows.iter().map(validity_evidence).collect(),
            ranking_rows: ranking_rows
                .iter()
                .map(ranking_evidence)
                .collect::<Result<Vec<_>>>()?,
            cluster_rows: cluster_rows
                .iter()
                .map(cluster_evidence)
                .collect::<Result<Vec<_>>>()?,
            rows: pipeline_rows
                .iter()
                .map(pipeline_row)
                .collect::<Result<Vec<_>>>()?,
            primary_slot_indices: primary_indices,
            valid_slot_indices: valid_indices,
            representative_slot_indices: representative_indices,
            top_k_slot_indices: top_k_indices,
            receipts: Fixed64BatchReceipts {
                allocation_inventory_sha256: producer_output.allocation_inventory_sha256,
                allocation_receipt_sha256: pipeline_output.allocation_receipt_sha256,
                source_bundle_receipt_sha256: pipeline_output.source_bundle_receipt_sha256,
                geometric_admission_batch_receipt_sha256: producer_output
                    .geometric_admission_batch_receipt_sha256,
                admission_context_receipt_sha256: pipeline_output.admission_context_receipt_sha256,
                refinement_context_receipt_sha256: pipeline_output
                    .refinement_context_receipt_sha256,
                scorer_context_receipt_sha256: pipeline_output.scorer_context_receipt_sha256,
                validity_context_receipt_sha256: pipeline_output.validity_context_receipt_sha256,
                component_binding_receipt_sha256: pipeline_output.component_binding_receipt_sha256,
                producer_batch_receipt_sha256: pipeline_output.producer_batch_receipt_sha256,
                refinement_policy_receipt_sha256: pipeline_output.refinement_policy_receipt_sha256,
                refinement_batch_receipt_sha256: pipeline_output.refinement_batch_receipt_sha256,
                post_admission_policy_receipt_sha256: pipeline_output
                    .post_admission_policy_receipt_sha256,
                post_admission_batch_receipt_sha256: pipeline_output
                    .post_admission_batch_receipt_sha256,
                scorer_batch_receipt_sha256: pipeline_output.scorer_batch_receipt_sha256,
                validity_batch_receipt_sha256: pipeline_output.validity_batch_receipt_sha256,
                ranking_batch_receipt_sha256: pipeline_output.ranking_batch_receipt_sha256,
                cluster_batch_receipt_sha256: pipeline_output.cluster_batch_receipt_sha256,
                pipeline_batch_receipt_sha256: pipeline_output.pipeline_batch_receipt_sha256,
            },
            authority: authority_disposition(&pipeline_output, &producer_output)?,
            scientific_projection_sha256: [0; 32],
        };
        receipt.scientific_projection_sha256 = receipt.derive_scientific_projection().sha256;
        Ok(receipt)
    }

    pub fn profile_id() -> Result<&'static str> {
        // SAFETY: the native function returns a process-lifetime NUL-terminated
        // static string or null on an ABI violation.
        let pointer = unsafe { sys::bg_docking_fixed64_pipeline_v2_profile_id() };
        if pointer.is_null() {
            return Err(Error::local(
                ErrorCode::InternalError,
                "native fixed64 pipeline profile id is null",
            ));
        }
        // SAFETY: non-null pointer follows the native static-string contract.
        let profile_id = unsafe { CStr::from_ptr(pointer) }.to_str().map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline profile id is not UTF-8",
            )
        })?;
        if profile_id != FIXED64_NATIVE_PIPELINE_PROFILE_ID {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 pipeline profile id changed",
            ));
        }
        Ok(profile_id)
    }
}

fn coordinate_segment_matches(
    channels: &[&[f64]],
    slot: usize,
    ligand_atom_count: u64,
    require_zero: bool,
) -> Result<bool> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 ligand denominator does not fit usize",
        )
    })?;
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 coordinate segment offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 coordinate segment end overflowed",
        )
    })?;
    for channel in channels {
        let segment = channel.get(begin..end).ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 coordinate segment exceeds its owned buffer",
            )
        })?;
        if segment.iter().any(|value| {
            if require_zero {
                *value != 0.0
            } else {
                !value.is_finite()
            }
        }) {
            return Ok(false);
        }
    }
    Ok(true)
}

fn unit_quaternion(values: [f64; 4]) -> bool {
    if values.iter().any(|value| !value.is_finite()) {
        return false;
    }
    let norm = values[0].hypot(values[1]).hypot(values[2].hypot(values[3]));
    norm.is_finite() && (norm - 1.0).abs() <= 1.0e-8
}

fn coordinate_segment<'a>(
    channels: [&'a [f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> Option<PositionSoa<'a>> {
    let begin = slot.checked_mul(ligand_count)?;
    let end = begin.checked_add(ligand_count)?;
    Some(PositionSoa::new(
        channels[0].get(begin..end)?,
        channels[1].get(begin..end)?,
        channels[2].get(begin..end)?,
    ))
}

fn coordinate_segments_equal(
    left: [&[f64]; 3],
    right: [&[f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> bool {
    let Some(left) = coordinate_segment(left, slot, ligand_count) else {
        return false;
    };
    let Some(right) = coordinate_segment(right, slot, ligand_count) else {
        return false;
    };
    [
        (left.x_angstrom, right.x_angstrom),
        (left.y_angstrom, right.y_angstrom),
        (left.z_angstrom, right.z_angstrom),
    ]
    .iter()
    .all(|(left, right)| {
        left.iter()
            .zip(*right)
            .all(|(left, right)| left.to_bits() == right.to_bits())
    })
}

fn scalar_segments_equal(left: &[f64], right: &[f64], slot: usize, count: usize) -> bool {
    let Some(begin) = slot.checked_mul(count) else {
        return false;
    };
    let Some(end) = begin.checked_add(count) else {
        return false;
    };
    let (Some(left), Some(right)) = (left.get(begin..end), right.get(begin..end)) else {
        return false;
    };
    left.iter()
        .zip(right)
        .all(|(left, right)| left.to_bits() == right.to_bits())
}

#[cfg(test)]
#[allow(clippy::items_after_test_module)]
mod output_validation_tests {
    use super::*;

    fn assign_independent_validity_measurements(
        row: &mut sys::bg_docking_pose_validity_row_v1,
        measurements: IndependentValidityMeasurements,
    ) {
        row.atom_count = measurements.atom_count() as u64;
        row.rotation_orthogonality_max_error = measurements.rotation_orthogonality_max_error();
        row.rotation_determinant = measurements.rotation_determinant();
        row.max_bond_length_delta_angstrom = measurements.max_bond_length_delta_angstrom();
        row.minimum_ligand_nonbonded_distance_angstrom =
            measurements.minimum_ligand_nonbonded_distance_angstrom();
        row.evaluated_ligand_nonbonded_pair_count =
            measurements.evaluated_ligand_nonbonded_pair_count() as u64;
        row.excluded_ligand_pair_count = measurements.excluded_ligand_pair_count() as u64;
        row.minimum_receptor_ligand_distance_angstrom =
            measurements.minimum_receptor_ligand_distance_angstrom();
        row.evaluated_receptor_ligand_pair_count =
            measurements.evaluated_receptor_ligand_pair_count() as u64;
        row.minimum_declared_chiral_volume = measurements.minimum_declared_chiral_volume();
        row.declared_chirality_center_count = measurements.declared_chirality_center_count() as u64;
        row.maximum_pocket_center_distance_angstrom =
            measurements.maximum_pocket_center_distance_angstrom();
        row.element_vdw_ligand_pair_count = measurements.element_vdw_ligand_pair_count() as u64;
        row.element_vdw_ligand_severe_overlap_count =
            measurements.element_vdw_ligand_severe_overlap_count() as u64;
        row.element_vdw_ligand_minimum_distance_angstrom =
            measurements.element_vdw_ligand_minimum_distance_angstrom();
        row.element_vdw_ligand_minimum_ratio = measurements.element_vdw_ligand_minimum_ratio();
        row.element_vdw_receptor_candidate_pair_count =
            measurements.element_vdw_receptor_candidate_pair_count() as u64;
        row.element_vdw_receptor_full_cartesian_pair_count =
            measurements.element_vdw_receptor_full_cartesian_pair_count() as u64;
        row.element_vdw_receptor_cell_count = measurements.element_vdw_receptor_cell_count() as u64;
        row.element_vdw_receptor_severe_overlap_count =
            measurements.element_vdw_receptor_severe_overlap_count() as u64;
        row.element_vdw_receptor_minimum_distance_angstrom =
            measurements.element_vdw_receptor_minimum_distance_angstrom();
        row.element_vdw_receptor_minimum_ratio = measurements.element_vdw_receptor_minimum_ratio();
    }

    struct IndexFixture {
        ranking: sys::bg_docking_stable_top_k_output_v1,
        cluster: sys::bg_docking_rmsd_cluster_output_v1,
        scorer_rows: Vec<sys::bg_docking_scorer_v1_row_v1>,
        validity_rows: Vec<sys::bg_docking_pose_validity_row_v1>,
        ranking_rows: Vec<sys::bg_docking_stable_top_k_row_v1>,
        refinement_rows: Vec<sys::bg_docking_fixed64_refinement_row_v1>,
        post_admission_rows: Vec<sys::bg_docking_geometric_admission_row_v1>,
        cluster_rows: Vec<sys::bg_docking_rmsd_cluster_row_v1>,
        primary_indices: Vec<u32>,
        valid_indices: Vec<u32>,
        representative_indices: Vec<u32>,
        top_k_indices: Vec<u32>,
        final_coordinates: [Vec<f64>; 3],
        final_quaternions: [Vec<f64>; 4],
        receptor_cells: HashMap<(i64, i64, i64), u64>,
        scorer_context: IndependentScorerContext,
        validity_context: IndependentValidityContext,
    }

    impl IndexFixture {
        fn valid() -> Self {
            let count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
            let mut scorer_rows = vec![zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1); count];
            let mut validity_rows =
                vec![zeroed_abi_value!(sys::bg_docking_pose_validity_row_v1); count];
            let mut ranking_rows =
                vec![zeroed_abi_value!(sys::bg_docking_stable_top_k_row_v1); count];
            let mut refinement_rows =
                vec![zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1); count];
            let mut post_admission_rows =
                vec![zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1); count];
            let mut cluster_rows =
                vec![zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1); count];
            let final_coordinates: [Vec<f64>; 3] = std::array::from_fn(|_| vec![0.0; count]);
            let mut final_quaternions: [Vec<f64>; 4] = std::array::from_fn(|_| vec![0.0; count]);
            final_quaternions[3].fill(1.0);
            final_quaternions[0][1] = 1.0;
            let scorer_atom = IndependentScorerAtom {
                charge_elementary: 0.0,
                vdw_radius_angstrom: 0.5,
                epsilon_kcal_per_mol: 0.1,
                hydrophobic: false,
                acceptor: false,
            };
            let scorer_context = IndependentScorerContext::new(
                [1; 32],
                [2; 32],
                [3; 32],
                IndependentScorerBackend::RustCpu,
                [5; 32],
                vec![Vec3::new(1.6, 0.0, 0.0)],
                vec![scorer_atom],
                vec![Vec3::new(0.0, 0.0, 0.0)],
                vec![scorer_atom],
                Vec::new(),
                Vec::new(),
                Vec::new(),
                Vec::new(),
                Vec3::new(0.0, 0.0, 0.0),
                10.0,
                IndependentScorerConfig::default(),
            )
            .expect("valid independent scorer fixture");
            let IndependentScorerOutcome::Scored(scorer_counts) = scorer_context
                .score_coordinates(&[Vec3::new(0.0, 0.0, 0.0)])
                .expect("fixture scorer evaluation")
            else {
                panic!("fixture scorer evaluation unexpectedly failed");
            };
            let validity_context = IndependentValidityContext::new(
                [1; 32],
                [2; 32],
                [3; 32],
                [4; 32],
                IndependentValidityBackend::RustCpu,
                [5; 32],
                [6; 32],
                vec![Vec3::new(0.0, 0.0, 0.0)],
                vec![Vec3::new(1.6, 0.0, 0.0)],
                vec![0.5],
                vec![0.5],
                Vec::new(),
                Vec::new(),
                Vec::new(),
                Vec3::new(0.0, 0.0, 0.0),
                10.0,
                IndependentValidityConfig::default(),
            )
            .expect("valid independent validity fixture");
            for slot in 0..count {
                scorer_rows[slot].slot_index = slot as u32;
                scorer_rows[slot].status = sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
                scorer_rows[slot].failure_code =
                    sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
                validity_rows[slot].slot_index = slot as u32;
                validity_rows[slot].status =
                    sys::BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE;
                validity_rows[slot].failure_code =
                    sys::BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER;
                validity_rows[slot].upstream_scorer_failure_code =
                    sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
                ranking_rows[slot].slot_index = slot as u32;
                post_admission_rows[slot].slot_index = slot as u32;
                post_admission_rows[slot].status =
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE;
                post_admission_rows[slot].failure_code =
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
                post_admission_rows[slot].decision =
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED;
                cluster_rows[slot].slot_index = slot as u32;
                cluster_rows[slot].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID;
            }
            for slot in [0_usize, 1] {
                scorer_rows[slot].status = sys::BG_DOCKING_SCORER_V1_ROW_SCORED;
                scorer_rows[slot].failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
                scorer_rows[slot].weighted_terms = scorer_counts.weighted_terms();
                scorer_rows[slot].total_score = scorer_counts.total_score();
                scorer_rows[slot].receptor_candidate_pair_count =
                    scorer_counts.receptor_candidate_pair_count() as u64;
                scorer_rows[slot].ligand_pair_count = scorer_counts.ligand_pair_count() as u64;
                scorer_rows[slot].hbond_count = scorer_counts.hbond_count() as u64;
                scorer_rows[slot].hydrophobic_contact_count =
                    scorer_counts.hydrophobic_contact_count() as u64;
                scorer_rows[slot].buried_polar_count = scorer_counts.buried_polar_count() as u64;
                ranking_rows[slot].rank_eligible = 1;
                ranking_rows[slot].stable_rank = slot as u32 + 1;
                ranking_rows[slot].total_score = scorer_counts.total_score();
                ranking_rows[slot].coordinate_sha256 = [slot as u8 + 1; 32];
                refinement_rows[slot].status =
                    sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
                post_admission_rows[slot].status =
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
                post_admission_rows[slot].failure_code =
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE;
                post_admission_rows[slot].decision =
                    sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED;
                post_admission_rows[slot].rank_eligible = 1;
            }
            validity_rows[0].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
            validity_rows[0].failure_code = sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
            validity_rows[0].upstream_scorer_failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            validity_rows[1].status = sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
            validity_rows[1].failure_code = sys::BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
            validity_rows[1].upstream_scorer_failure_code = sys::BG_DOCKING_SCORER_V1_FAILURE_NONE;
            for slot in 0..2 {
                let quaternion = Quaternion::new(
                    final_quaternions[0][slot],
                    final_quaternions[1][slot],
                    final_quaternions[2][slot],
                    final_quaternions[3][slot],
                );
                let IndependentValidityOutcome::Evaluated {
                    checks,
                    measurements,
                } = validity_context
                    .evaluate_coordinates(&[Vec3::new(0.0, 0.0, 0.0)], quaternion)
                    .expect("fixture validity evaluation")
                else {
                    panic!("fixture validity evaluation unexpectedly failed");
                };
                validity_rows[slot].passed_check_mask = independent_validity_check_mask(checks);
                validity_rows[slot].blocker_mask =
                    sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ validity_rows[slot].passed_check_mask;
                assign_independent_validity_measurements(&mut validity_rows[slot], measurements);
            }
            ranking_rows[0].valid_rank_eligible = 1;
            ranking_rows[0].stable_valid_rank = 1;
            cluster_rows[0].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
            cluster_rows[0].cluster_eligible = 1;
            cluster_rows[0].representative = 1;
            cluster_rows[0].top_k_representative = 1;
            cluster_rows[0].stable_valid_rank = 1;
            cluster_rows[0].cluster_id = 1;
            cluster_rows[0].representative_slot_index = 0;
            cluster_rows[0].cluster_rank = 1;
            cluster_rows[0].top_k_rank = 1;
            cluster_rows[0].cluster_size = 1;
            cluster_rows[0].coordinate_sha256 = ranking_rows[0].coordinate_sha256;
            let mut ranking = zeroed_abi_value!(sys::bg_docking_stable_top_k_output_v1);
            ranking.primary_index_count = 2;
            ranking.valid_index_count = 1;
            let mut cluster = zeroed_abi_value!(sys::bg_docking_rmsd_cluster_output_v1);
            cluster.representative_index_count = 1;
            cluster.top_k_index_count = 1;
            let mut primary_indices = vec![0; count];
            primary_indices[1] = 1;
            Self {
                ranking,
                cluster,
                scorer_rows,
                validity_rows,
                ranking_rows,
                refinement_rows,
                post_admission_rows,
                cluster_rows,
                primary_indices,
                valid_indices: vec![0; count],
                representative_indices: vec![0; count],
                top_k_indices: vec![0; sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize],
                final_coordinates,
                final_quaternions,
                receptor_cells: HashMap::from([((0, 0, 0), 1)]),
                scorer_context,
                validity_context,
            }
        }

        fn validate(&self) -> Result<()> {
            validate_scorer_and_validity_evidence(
                &self.scorer_rows,
                &self.validity_rows,
                &self.ranking_rows,
                &self.refinement_rows,
                &self.post_admission_rows,
                1,
                1,
                0,
                0,
                3.5,
                &self.receptor_cells,
                [
                    self.final_coordinates[0].as_slice(),
                    self.final_coordinates[1].as_slice(),
                    self.final_coordinates[2].as_slice(),
                ],
                [
                    self.final_quaternions[0].as_slice(),
                    self.final_quaternions[1].as_slice(),
                    self.final_quaternions[2].as_slice(),
                    self.final_quaternions[3].as_slice(),
                ],
                &self.scorer_context,
                &self.validity_context,
                Backend::RustCpu,
            )?;
            validate_index_evidence(
                &self.ranking,
                &self.cluster,
                &self.scorer_rows,
                &self.validity_rows,
                &self.ranking_rows,
                &self.cluster_rows,
                &self.primary_indices,
                &self.valid_indices,
                &self.representative_indices,
                &self.top_k_indices,
                2.0,
                [
                    self.final_coordinates[0].as_slice(),
                    self.final_coordinates[1].as_slice(),
                    self.final_coordinates[2].as_slice(),
                ],
                1,
            )
        }
    }

    #[test]
    fn accepts_cross_bound_rank_and_cluster_indices() {
        assert!(IndexFixture::valid().validate().is_ok());
    }

    #[test]
    fn rejects_truncated_top_k_prefix() {
        let mut truncated = IndexFixture::valid();
        truncated.cluster.top_k_index_count = 0;
        truncated.cluster_rows[0].top_k_representative = 0;
        truncated.cluster_rows[0].top_k_rank = 0;
        assert!(truncated.validate().is_err());
    }

    #[test]
    fn rejects_duplicate_or_out_of_range_rank_indices() {
        let mut duplicate = IndexFixture::valid();
        duplicate.primary_indices[1] = 0;
        assert!(duplicate.validate().is_err());

        let mut out_of_range = IndexFixture::valid();
        out_of_range.primary_indices[1] = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        assert!(out_of_range.validate().is_err());
    }

    #[test]
    fn rejects_reordered_or_component_cross_wired_indices() {
        let mut reordered = IndexFixture::valid();
        reordered.primary_indices.swap(0, 1);
        assert!(reordered.validate().is_err());

        let mut cross_wired = IndexFixture::valid();
        cross_wired.cluster_rows[0].coordinate_sha256 = [9; 32];
        assert!(cross_wired.validate().is_err());
    }

    #[test]
    fn rejects_corrupt_scorer_terms_and_failure_sentinels() {
        let mut nonfinite = IndexFixture::valid();
        nonfinite.scorer_rows[0].weighted_terms[0] = f64::NAN;
        assert!(nonfinite.validate().is_err());

        let mut inconsistent_total = IndexFixture::valid();
        inconsistent_total.scorer_rows[0].weighted_terms[0] = 0.5;
        assert!(inconsistent_total.validate().is_err());

        let mut retained_failure_score = IndexFixture::valid();
        retained_failure_score.scorer_rows[2].total_score = 7.0;
        assert!(retained_failure_score.validate().is_err());

        let mut fabricated_interaction_count = IndexFixture::valid();
        fabricated_interaction_count.scorer_rows[0].receptor_candidate_pair_count += 1;
        assert!(fabricated_interaction_count.validate().is_err());

        let mut fabricated_consistent_score = IndexFixture::valid();
        fabricated_consistent_score.scorer_rows[0].weighted_terms[0] += 0.5;
        fabricated_consistent_score.scorer_rows[0].total_score += 0.5;
        fabricated_consistent_score.ranking_rows[0].total_score += 0.5;
        assert!(fabricated_consistent_score.validate().is_err());

        let mut suppressed_success = IndexFixture::valid();
        suppressed_success.scorer_rows[0] = zeroed_abi_value!(sys::bg_docking_scorer_v1_row_v1);
        suppressed_success.scorer_rows[0].status = sys::BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
        suppressed_success.scorer_rows[0].failure_code =
            sys::BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
        assert!(suppressed_success.validate().is_err());
    }

    #[test]
    fn rejects_valid_rank_reordered_independently_of_primary_rank() {
        let mut fixture = IndexFixture::valid();
        fixture.final_quaternions[0][1] = 0.0;
        let IndependentValidityOutcome::Evaluated {
            checks,
            measurements,
        } = fixture
            .validity_context
            .evaluate_coordinates(
                &[Vec3::new(0.0, 0.0, 0.0)],
                Quaternion::new(0.0, 0.0, 0.0, 1.0),
            )
            .expect("second valid-rank fixture evaluation")
        else {
            panic!("second valid-rank fixture unexpectedly failed");
        };
        assert!(checks.all());
        fixture.validity_rows[1].passed_check_mask = independent_validity_check_mask(checks);
        fixture.validity_rows[1].blocker_mask = 0;
        assign_independent_validity_measurements(&mut fixture.validity_rows[1], measurements);
        fixture.ranking.valid_index_count = 2;
        fixture.valid_indices[0] = 1;
        fixture.valid_indices[1] = 0;
        fixture.ranking_rows[0].stable_valid_rank = 2;
        fixture.ranking_rows[1].valid_rank_eligible = 1;
        fixture.ranking_rows[1].stable_valid_rank = 1;
        assert!(fixture.validate().is_err());
    }

    #[test]
    fn rejects_valid_rank_with_inconsistent_blocker_mask() {
        let mut fixture = IndexFixture::valid();
        fixture.validity_rows[0].blocker_mask =
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH;
        assert!(fixture.validate().is_err());
    }

    #[test]
    fn rejects_self_consistent_but_unrederived_validity_bits_and_measurements() {
        let mut fabricated_bit = IndexFixture::valid();
        fabricated_bit.validity_rows[0].passed_check_mask ^=
            sys::BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS;
        fabricated_bit.validity_rows[0].blocker_mask = sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
            ^ fabricated_bit.validity_rows[0].passed_check_mask;
        fabricated_bit.ranking_rows[0].valid_rank_eligible = 0;
        fabricated_bit.ranking_rows[0].stable_valid_rank = 0;
        fabricated_bit.ranking.valid_index_count = 0;
        fabricated_bit.cluster.representative_index_count = 0;
        fabricated_bit.cluster.top_k_index_count = 0;
        fabricated_bit.cluster_rows[0] = zeroed_abi_value!(sys::bg_docking_rmsd_cluster_row_v1);
        fabricated_bit.cluster_rows[0].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID;
        assert!(fabricated_bit.validate().is_err());

        let mut fabricated_measurement = IndexFixture::valid();
        fabricated_measurement.validity_rows[0].max_bond_length_delta_angstrom = 0.01;
        assert!(fabricated_measurement.validate().is_err());
    }

    #[test]
    fn rejects_invalid_cluster_rmsd_evidence() {
        let mut nonfinite = IndexFixture::valid();
        nonfinite.cluster_rows[0].direct_rmsd_to_representative_angstrom = f64::NAN;
        assert!(nonfinite.validate().is_err());

        let mut representative_distance = IndexFixture::valid();
        representative_distance.cluster_rows[0].direct_rmsd_to_representative_angstrom = 0.5;
        assert!(representative_distance.validate().is_err());
    }

    #[test]
    fn rejects_wrong_validity_measurement_denominators() {
        let mut wrong_atom_count = IndexFixture::valid();
        wrong_atom_count.validity_rows[0].atom_count = 2;
        assert!(wrong_atom_count.validate().is_err());

        let mut wrong_receptor_pairs = IndexFixture::valid();
        wrong_receptor_pairs.validity_rows[0].evaluated_receptor_ligand_pair_count = 0;
        assert!(wrong_receptor_pairs.validate().is_err());

        let mut wrong_candidate_pairs = IndexFixture::valid();
        wrong_candidate_pairs.validity_rows[0].element_vdw_receptor_candidate_pair_count = 0;
        assert!(wrong_candidate_pairs.validate().is_err());

        let mut passed_despite_severe_overlap = IndexFixture::valid();
        passed_despite_severe_overlap.validity_rows[0].element_vdw_receptor_severe_overlap_count =
            1;
        assert!(passed_despite_severe_overlap.validate().is_err());
    }

    #[test]
    fn rejects_cluster_assignment_that_skips_an_earlier_matching_representative() {
        let mut fixture = IndexFixture::valid();
        fixture.ranking.valid_index_count = 2;
        fixture.valid_indices[1] = 1;
        fixture.validity_rows[1].passed_check_mask = sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
        fixture.validity_rows[1].blocker_mask = 0;
        fixture.ranking_rows[1].valid_rank_eligible = 1;
        fixture.ranking_rows[1].stable_valid_rank = 2;
        fixture.cluster.representative_index_count = 2;
        fixture.representative_indices[1] = 1;
        fixture.cluster_rows[1].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
        fixture.cluster_rows[1].cluster_eligible = 1;
        fixture.cluster_rows[1].representative = 1;
        fixture.cluster_rows[1].stable_valid_rank = 2;
        fixture.cluster_rows[1].cluster_id = 2;
        fixture.cluster_rows[1].representative_slot_index = 1;
        fixture.cluster_rows[1].cluster_rank = 2;
        fixture.cluster_rows[1].cluster_size = 1;
        fixture.cluster_rows[1].coordinate_sha256 = fixture.ranking_rows[1].coordinate_sha256;
        assert!(fixture.validate().is_err());
    }

    #[test]
    fn rejects_representative_list_reversed_from_stable_valid_rank_order() {
        let mut fixture = IndexFixture::valid();
        fixture.final_coordinates[0][1] = 3.0;
        fixture.final_quaternions[0][1] = 0.0;
        let IndependentValidityOutcome::Evaluated {
            checks,
            measurements,
        } = fixture
            .validity_context
            .evaluate_coordinates(
                &[Vec3::new(3.0, 0.0, 0.0)],
                Quaternion::new(0.0, 0.0, 0.0, 1.0),
            )
            .expect("far representative validity evaluation")
        else {
            panic!("far representative unexpectedly produced a typed failure");
        };
        assert!(checks.all());
        fixture.validity_rows[1].passed_check_mask = independent_validity_check_mask(checks);
        fixture.validity_rows[1].blocker_mask = 0;
        assign_independent_validity_measurements(&mut fixture.validity_rows[1], measurements);
        fixture.ranking.valid_index_count = 2;
        fixture.valid_indices[1] = 1;
        fixture.ranking_rows[1].valid_rank_eligible = 1;
        fixture.ranking_rows[1].stable_valid_rank = 2;
        fixture.cluster.representative_index_count = 2;
        fixture.cluster.top_k_index_count = 1;
        fixture.representative_indices[0] = 1;
        fixture.representative_indices[1] = 0;
        fixture.top_k_indices[0] = 1;

        fixture.cluster_rows[0].top_k_representative = 0;
        fixture.cluster_rows[0].top_k_rank = 0;
        fixture.cluster_rows[0].cluster_id = 2;
        fixture.cluster_rows[0].cluster_rank = 2;
        fixture.cluster_rows[1].status = sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
        fixture.cluster_rows[1].cluster_eligible = 1;
        fixture.cluster_rows[1].representative = 1;
        fixture.cluster_rows[1].top_k_representative = 1;
        fixture.cluster_rows[1].stable_valid_rank = 2;
        fixture.cluster_rows[1].cluster_id = 1;
        fixture.cluster_rows[1].representative_slot_index = 1;
        fixture.cluster_rows[1].cluster_rank = 1;
        fixture.cluster_rows[1].top_k_rank = 1;
        fixture.cluster_rows[1].cluster_size = 1;
        fixture.cluster_rows[1].coordinate_sha256 = fixture.ranking_rows[1].coordinate_sha256;
        assert!(fixture.validate().is_err());
    }

    #[test]
    fn rejects_component_and_pipeline_receipt_substitution() {
        let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_pipeline_row_v2);
        let component_binding = [1; 32];
        let policy = [2; 32];
        let refinement = [3; 32];
        let scorer = [4; 32];
        let validity = [5; 32];
        let ranking = [6; 32];
        let cluster = [7; 32];
        let post_policy = [8; 32];
        row.post_admission_row_receipt_sha256 = [9; 32];
        row.refinement_evidence_sha256 = refinement;
        row.scorer_evidence_sha256 = scorer;
        row.validity_evidence_sha256 = validity;
        row.ranking_evidence_sha256 = ranking;
        row.cluster_evidence_sha256 = cluster;
        row.row_receipt_sha256 = canonical_pipeline_row_receipt(
            &row,
            component_binding,
            policy,
            post_policy,
            refinement,
            scorer,
            validity,
            ranking,
            cluster,
        );
        assert!(validate_pipeline_receipt_bindings(
            &row,
            component_binding,
            policy,
            post_policy,
            refinement,
            scorer,
            validity,
            ranking,
            cluster,
        )
        .is_ok());

        let mut substituted_component = row;
        substituted_component.scorer_evidence_sha256 = [10; 32];
        assert!(validate_pipeline_receipt_bindings(
            &substituted_component,
            component_binding,
            policy,
            post_policy,
            refinement,
            scorer,
            validity,
            ranking,
            cluster,
        )
        .is_err());

        let mut substituted_row = row;
        substituted_row.row_receipt_sha256 = [11; 32];
        assert!(validate_pipeline_receipt_bindings(
            &substituted_row,
            component_binding,
            policy,
            post_policy,
            refinement,
            scorer,
            validity,
            ranking,
            cluster,
        )
        .is_err());
    }

    fn generated_producer_row(
        source: Fixed64CoordinateSource<'_>,
    ) -> sys::bg_docking_fixed64_producer_row_v1 {
        let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
        row.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
        row.failure_code = sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE;
        row.lane = sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS;
        row.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
        row.ligand_atom_count = 1;
        row.allocation_slot_receipt_sha256 = [1; 32];
        row.source_payload_receipt_sha256 = canonical_source_payload_sha256(source, 1);
        row.source_proposal_sha256 = source.evidence.proposal_sha256;
        row.source_coordinate_sha256 = source.evidence.coordinate_sha256;
        row.placement_receipt_sha256 = [5; 32];
        row.output_proposal_sha256 = row.source_proposal_sha256;
        row.output_coordinate_sha256 = row.source_coordinate_sha256;
        row.coordinates_available = 1;
        row.source_identity_verified = 1;
        row.allocation_identity_verified = 1;
        row.geometric_identity_verified = 1;
        row.denominator_preserved = 1;
        row.placement_quaternion_w = 1.0;
        row
    }

    #[test]
    fn rejects_producer_success_and_failure_sentinel_corruption() {
        let coordinates = [vec![0.0], vec![0.0], vec![0.0]];
        let views = [
            coordinates[0].as_slice(),
            coordinates[1].as_slice(),
            coordinates[2].as_slice(),
        ];
        let source_coordinates = PositionSoa::new(views[0], views[1], views[2]);
        let source = Fixed64CoordinateSource {
            evidence: Fixed64SourceEvidence {
                receipt_sha256: [2; 32],
                proposal_sha256: [3; 32],
                coordinate_sha256: canonical_coordinate_sha256(source_coordinates),
            },
            coordinates: source_coordinates,
        };
        let valid = generated_producer_row(source);
        assert!(validate_producer_row_semantics(&valid, views, 0, 1, Some(source)).is_ok());

        let mut nonunit = generated_producer_row(source);
        nonunit.placement_quaternion_w = 0.5;
        assert!(validate_producer_row_semantics(&nonunit, views, 0, 1, Some(source)).is_err());

        let mut wrong_lane = generated_producer_row(source);
        wrong_lane.lane = sys::BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS;
        assert!(validate_producer_row_semantics(&wrong_lane, views, 0, 1, Some(source)).is_err());

        let mut cross_wired_passthrough = generated_producer_row(source);
        cross_wired_passthrough.output_coordinate_sha256 = [9; 32];
        assert!(validate_producer_row_semantics(
            &cross_wired_passthrough,
            views,
            0,
            1,
            Some(source),
        )
        .is_err());

        let mut cross_wired_source = generated_producer_row(source);
        cross_wired_source.source_proposal_sha256 = [9; 32];
        assert!(
            validate_producer_row_semantics(&cross_wired_source, views, 0, 1, Some(source),)
                .is_err()
        );

        let different_coordinates = [vec![1.0], vec![0.0], vec![0.0]];
        let different_views = [
            different_coordinates[0].as_slice(),
            different_coordinates[1].as_slice(),
            different_coordinates[2].as_slice(),
        ];
        assert!(
            validate_producer_row_semantics(&valid, different_views, 0, 1, Some(source),).is_err()
        );

        let mut failure = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
        failure.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
        failure.failure_code = sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE;
        failure.lane = sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS;
        failure.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
        failure.ligand_atom_count = 1;
        failure.allocation_slot_receipt_sha256 = [1; 32];
        failure.allocation_identity_verified = 1;
        failure.geometric_identity_verified = 1;
        failure.denominator_preserved = 1;
        assert!(validate_producer_row_semantics(&failure, views, 0, 1, None).is_ok());
        let mut spurious_placement = failure;
        spurious_placement.placement_receipt_sha256 = [8; 32];
        assert!(validate_producer_row_semantics(&spurious_placement, views, 0, 1, None).is_err());
        failure.coordinates_available = 1;
        assert!(validate_producer_row_semantics(&failure, views, 0, 1, None).is_err());

        let mut indexed_failure_on_passthrough = generated_producer_row(source);
        indexed_failure_on_passthrough.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
        indexed_failure_on_passthrough.failure_code =
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE;
        indexed_failure_on_passthrough.component_failure_code =
            sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY;
        indexed_failure_on_passthrough.coordinates_available = 0;
        indexed_failure_on_passthrough.output_proposal_sha256 = [0; 32];
        indexed_failure_on_passthrough.output_coordinate_sha256 = [0; 32];
        indexed_failure_on_passthrough.placement_quaternion_w = 0.0;
        assert!(validate_producer_row_semantics(
            &indexed_failure_on_passthrough,
            views,
            0,
            1,
            Some(source),
        )
        .is_err());

        let mut feature_failure_on_passthrough = indexed_failure_on_passthrough;
        feature_failure_on_passthrough.failure_code =
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE;
        feature_failure_on_passthrough.component_failure_code = 0;
        feature_failure_on_passthrough.placement_receipt_sha256 = [0; 32];
        assert!(validate_producer_row_semantics(
            &feature_failure_on_passthrough,
            views,
            0,
            1,
            Some(source),
        )
        .is_err());

        let mut transformed_coordinates: [Vec<f64>; 3] = std::array::from_fn(|_| vec![0.0; 64]);
        let transformed_views = [
            transformed_coordinates[0].as_slice(),
            transformed_coordinates[1].as_slice(),
            transformed_coordinates[2].as_slice(),
        ];
        let mut transformed = generated_producer_row(source);
        transformed.lane = sys::BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3;
        transformed.placement_kind = sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3;
        assert!(validate_producer_row_semantics(
            &transformed,
            transformed_views,
            24,
            1,
            Some(source),
        )
        .is_ok());
        transformed_coordinates[0][24] = 1.0;
        let substituted_views = [
            transformed_coordinates[0].as_slice(),
            transformed_coordinates[1].as_slice(),
            transformed_coordinates[2].as_slice(),
        ];
        assert!(validate_producer_row_semantics(
            &transformed,
            substituted_views,
            24,
            1,
            Some(source),
        )
        .is_err());

        let mut contradicted_source_failure = generated_producer_row(source);
        contradicted_source_failure.status = sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
        contradicted_source_failure.failure_code =
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE;
        contradicted_source_failure.coordinates_available = 0;
        contradicted_source_failure.placement_receipt_sha256 = [0; 32];
        contradicted_source_failure.output_proposal_sha256 = [0; 32];
        contradicted_source_failure.output_coordinate_sha256 = [0; 32];
        contradicted_source_failure.placement_quaternion_w = 0.0;
        assert!(validate_producer_row_semantics(
            &contradicted_source_failure,
            views,
            0,
            1,
            Some(source),
        )
        .is_err());

        contradicted_source_failure.failure_code =
            sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_LIGAND_DENOMINATOR_MISMATCH;
        assert!(validate_producer_row_semantics(
            &contradicted_source_failure,
            views,
            0,
            1,
            Some(source),
        )
        .is_err());
    }

    fn accepted_geometric_fixture() -> (
        sys::bg_docking_geometric_admission_row_v1,
        IndependentFixed64GeometricInput,
        [Vec<f64>; 3],
    ) {
        let coordinates = [vec![5.0, 6.0], vec![0.0, 0.0], vec![0.0, 0.0]];
        let input = IndependentFixed64GeometricInput::new(
            vec![1.0, 1.0],
            vec![true, false],
            vec![
                Vec3::new(0.0, 0.0, 0.0),
                Vec3::new(0.0, 5.0, 0.0),
                Vec3::new(0.0, -5.0, 0.0),
            ],
            vec![1.0; 3],
            Vec3::new(5.5, 0.0, 0.0),
            10.0,
        )
        .expect("valid geometric fixture");
        let metrics = evaluate_fixed64_geometric_metrics(
            &[Vec3::new(5.0, 0.0, 0.0), Vec3::new(6.0, 0.0, 0.0)],
            &input,
        )
        .expect("valid geometric metrics");
        let mut row = zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1);
        row.status = sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
        row.failure_code = sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE;
        row.decision = sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED;
        row.rank_eligible = 1;
        row.ligand_atom_count = 2;
        row.receptor_atom_count = 3;
        row.exact_pair_count = 6;
        row.raw_minimum_distance_angstrom = metrics.raw_minimum_distance_angstrom();
        row.minimum_vdw_surface_gap_angstrom = metrics.minimum_vdw_surface_gap_angstrom();
        row.minimum_vdw_ratio = metrics.minimum_vdw_ratio();
        row.penetration_pair_count = metrics.penetration_pair_count() as u64;
        row.unique_ligand_penetration_atom_count =
            metrics.unique_ligand_penetration_atom_count() as u64;
        row.unique_ligand_heavy_atom_penetration_count =
            metrics.unique_ligand_heavy_atom_penetration_count() as u64;
        row.sphere_overlap_proxy_angstrom3 = metrics.sphere_overlap_proxy_angstrom3();
        row.pocket_escape_angstrom = metrics.pocket_escape_angstrom();
        row.row_receipt_sha256 = [1; 32];
        (row, input, coordinates)
    }

    #[test]
    fn rejects_malformed_geometric_admission_semantics() {
        let (valid, input, coordinates) = accepted_geometric_fixture();
        let views = [
            coordinates[0].as_slice(),
            coordinates[1].as_slice(),
            coordinates[2].as_slice(),
        ];
        assert!(validate_geometric_admission_row_semantics(
            &valid,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_ok());

        let mut wrong_failure = valid;
        wrong_failure.failure_code =
            sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
        assert!(validate_geometric_admission_row_semantics(
            &wrong_failure,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_err());

        let mut nonfinite = valid;
        nonfinite.sphere_overlap_proxy_angstrom3 = f64::NAN;
        assert!(validate_geometric_admission_row_semantics(
            &nonfinite,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_err());

        let mut inconsistent_penetration = valid;
        inconsistent_penetration.penetration_pair_count = 1;
        assert!(validate_geometric_admission_row_semantics(
            &inconsistent_penetration,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_err());

        let mut threshold_mismatch = valid;
        threshold_mismatch.minimum_vdw_ratio = 0.5;
        assert!(validate_geometric_admission_row_semantics(
            &threshold_mismatch,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_err());

        let mut fabricated_minimum = valid;
        fabricated_minimum.raw_minimum_distance_angstrom += 0.25;
        assert!(validate_geometric_admission_row_semantics(
            &fabricated_minimum,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_err());

        let mut upstream = zeroed_abi_value!(sys::bg_docking_geometric_admission_row_v1);
        upstream.status = sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE;
        upstream.failure_code = sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE;
        upstream.decision = sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED;
        upstream.row_receipt_sha256 = [1; 32];
        assert!(validate_geometric_admission_row_semantics(
            &upstream,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_ok());
        assert!(validate_geometric_admission_row_semantics(
            &upstream,
            sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED,
            3,
            2,
            1,
            6,
            0.55,
            Backend::RustCpu,
            &input,
            views,
            0,
        )
        .is_err());
    }

    fn valid_rigid_v2_row() -> sys::bg_docking_rigid_refinement_row_v1 {
        let mut row = zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1);
        row.status = sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
        row.failure_code = sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
        row.candidate_mode = sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
        row.selected_profile = sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION;
        row.selected.profile = sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION;
        row.selected.available = 1;
        row
    }

    #[test]
    fn rejects_malformed_rigid_refinement_semantics() {
        let coordinates: [Vec<f64>; 12] = std::array::from_fn(|_| vec![0.0]);
        let valid = valid_rigid_v2_row();
        assert!(validate_rigid_row_semantics(
            &valid,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            0,
            &coordinates,
            0,
            1,
        )
        .is_ok());

        let mut nonfinite = valid_rigid_v2_row();
        nonfinite.selected.final_penalty = f64::NAN;
        assert!(validate_rigid_row_semantics(
            &nonfinite,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            0,
            &coordinates,
            0,
            1,
        )
        .is_err());

        let mut mismatched_steps = valid_rigid_v2_row();
        mismatched_steps.selected.accepted_steps = 1;
        assert!(validate_rigid_row_semantics(
            &mismatched_steps,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            1,
            &coordinates,
            0,
            1,
        )
        .is_err());

        let mut over_budget = valid_rigid_v2_row();
        over_budget.selected.accepted_steps = 1;
        over_budget.selected.accepted_translation_steps = 1;
        assert!(validate_rigid_row_semantics(
            &over_budget,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            0,
            &coordinates,
            0,
            1,
        )
        .is_err());
    }

    #[test]
    fn rejects_rigid_coordinates_not_replayed_from_the_owned_producer_pose() {
        let producer_coordinates = [vec![0.0], vec![0.0], vec![0.0]];
        let producer_views = [
            producer_coordinates[0].as_slice(),
            producer_coordinates[1].as_slice(),
            producer_coordinates[2].as_slice(),
        ];
        let mut rigid_coordinates: [Vec<f64>; 12] = std::array::from_fn(|_| vec![0.0]);
        let geometric_input = IndependentFixed64GeometricInput::new(
            vec![0.5],
            vec![true],
            vec![Vec3::new(5.0, 0.0, 0.0)],
            vec![0.5],
            Vec3::new(0.0, 0.0, 0.0),
            10.0,
        )
        .expect("valid independent rigid replay fixture");
        let row = valid_rigid_v2_row();
        assert!(validate_independent_rigid_replay(
            Backend::RustCpu,
            &row,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            1,
            producer_views,
            &rigid_coordinates,
            0,
            1,
            &geometric_input,
            IndependentRigidV2Config::default(),
            IndependentRigidV3Config::default(),
            IndependentRigidV3Config::clearance_v4(),
        )
        .is_ok());

        rigid_coordinates[0][0] = 1.0;
        assert!(validate_independent_rigid_replay(
            Backend::RustCpu,
            &row,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            1,
            producer_views,
            &rigid_coordinates,
            0,
            1,
            &geometric_input,
            IndependentRigidV2Config::default(),
            IndependentRigidV3Config::default(),
            IndependentRigidV3Config::clearance_v4(),
        )
        .is_err());

        let mut suppressed = zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1);
        suppressed.status = sys::BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE;
        suppressed.failure_code = sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT;
        suppressed.candidate_mode = sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
        assert!(validate_independent_rigid_replay(
            Backend::RustCpu,
            &suppressed,
            sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION,
            1,
            producer_views,
            &rigid_coordinates,
            0,
            1,
            &geometric_input,
            IndependentRigidV2Config::default(),
            IndependentRigidV3Config::default(),
            IndependentRigidV3Config::clearance_v4(),
        )
        .is_err());
    }

    fn refined_torsion_fixture() -> (
        Vec<sys::bg_docking_torsion_v7_row_v1>,
        Vec<sys::bg_docking_torsion_v7_move_v1>,
    ) {
        let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        let moves_per_slot = sys::BG_DOCKING_TORSION_V7_MAX_MOVES as usize;
        let mut rows = vec![zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1); candidate_count];
        for (slot, candidate) in rows.iter_mut().enumerate() {
            candidate.slot_index = slot as u32;
            candidate.status = sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
            candidate.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE;
        }
        let mut row = zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1);
        row.status = sys::BG_DOCKING_TORSION_V7_ROW_REFINED;
        row.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_NONE;
        row.skip_reason = sys::BG_DOCKING_TORSION_V7_SKIP_NONE;
        row.selection_reason = sys::BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_OUTSIDE_WINDOW;
        row.selection_window_reachable = 1;
        row.torsion_evaluated = 1;
        row.torsion_variant_available = 1;
        row.torsion_step_budget = 1;
        row.fixed_objective_evaluation_count = 2;
        row.evaluated_torsion_steps = 1;
        row.evaluated_total_torsion_path_radians = 0.1;
        rows[0] = row;
        let mut moves = vec![
            zeroed_abi_value!(sys::bg_docking_torsion_v7_move_v1);
            candidate_count * moves_per_slot
        ];
        for (index, movement) in moves.iter_mut().enumerate() {
            movement.slot_index = (index / moves_per_slot) as u32;
            movement.move_index = (index % moves_per_slot) as u32;
        }
        moves[0].evaluated = 1;
        moves[0].rotatable_child_atom_index = 5;
        moves[0].delta_radians = 0.1;
        (rows, moves)
    }

    #[test]
    fn rejects_torsion_moves_cross_wired_from_parent_rows() {
        let (rows, moves) = refined_torsion_fixture();
        let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
        let mut rigid =
            vec![zeroed_abi_value!(sys::bg_docking_rigid_refinement_row_v1); candidate_count];
        rigid[0].status = sys::BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
        rigid[0].candidate_mode = sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE;
        let mut eligibility = vec![0_u8; candidate_count];
        eligibility[0] = 1;
        let mut max_steps = vec![0_u64; candidate_count];
        max_steps[0] = 1;
        let torsion_coordinates: [Vec<f64>; 8] =
            std::array::from_fn(|_| vec![0.0; candidate_count]);
        let rigid_coordinates: [Vec<f64>; 12] = std::array::from_fn(|_| vec![0.0; candidate_count]);
        let baseline_angles = vec![0.0; candidate_count];
        let validation = validate_torsion_evidence(
            &rows,
            &moves,
            &rigid,
            &eligibility,
            &max_steps,
            4,
            &[5],
            &torsion_coordinates,
            &rigid_coordinates,
            &baseline_angles,
            1,
        );
        assert!(validation.is_ok(), "{validation:?}");

        let mut wrong_final_coordinates = torsion_coordinates.clone();
        wrong_final_coordinates[4][0] = 1.0;
        assert!(validate_torsion_evidence(
            &rows,
            &moves,
            &rigid,
            &eligibility,
            &max_steps,
            4,
            &[5],
            &wrong_final_coordinates,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());

        let mut nonfinite_optimized = torsion_coordinates.clone();
        nonfinite_optimized[0][0] = f64::NAN;
        assert!(validate_torsion_evidence(
            &rows,
            &moves,
            &rigid,
            &eligibility,
            &max_steps,
            4,
            &[5],
            &nonfinite_optimized,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());

        let mut retained_typed_failure_coordinate = torsion_coordinates.clone();
        retained_typed_failure_coordinate[0][1] = 1.0;
        assert!(validate_torsion_evidence(
            &rows,
            &moves,
            &rigid,
            &eligibility,
            &max_steps,
            4,
            &[5],
            &retained_typed_failure_coordinate,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());

        let mut wrong_child = moves.clone();
        wrong_child[0].rotatable_child_atom_index = 6;
        assert!(validate_torsion_evidence(
            &rows,
            &wrong_child,
            &rigid,
            &eligibility,
            &max_steps,
            4,
            &[5],
            &torsion_coordinates,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());

        let mut outside_prefix = moves.clone();
        outside_prefix[1].evaluated = 1;
        outside_prefix[1].rotatable_child_atom_index = 5;
        outside_prefix[1].delta_radians = 0.1;
        assert!(validate_torsion_evidence(
            &rows,
            &outside_prefix,
            &rigid,
            &eligibility,
            &max_steps,
            4,
            &[5],
            &torsion_coordinates,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());

        let disabled = vec![0_u8; candidate_count];
        assert!(validate_torsion_evidence(
            &rows,
            &moves,
            &rigid,
            &disabled,
            &max_steps,
            4,
            &[5],
            &torsion_coordinates,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());

        let capped = vec![0_u64; candidate_count];
        assert!(validate_torsion_evidence(
            &rows,
            &moves,
            &rigid,
            &eligibility,
            &capped,
            4,
            &[5],
            &torsion_coordinates,
            &rigid_coordinates,
            &baseline_angles,
            1,
        )
        .is_err());
    }

    struct RefinementFixture {
        rows: Vec<sys::bg_docking_fixed64_refinement_row_v1>,
        producer: Vec<sys::bg_docking_fixed64_producer_row_v1>,
        rigid: Vec<sys::bg_docking_rigid_refinement_row_v1>,
        torsion: Vec<sys::bg_docking_torsion_v7_row_v1>,
        coordinates: [Vec<f64>; 3],
        quaternions: [Vec<f64>; 4],
    }

    fn valid_refinement_fixture() -> RefinementFixture {
        let mut row = zeroed_abi_value!(sys::bg_docking_fixed64_refinement_row_v1);
        row.status = sys::BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
        row.failure_stage = sys::BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE;
        row.coordinate_origin = sys::BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED;
        row.rigid_failure_code = sys::BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
        row.selected_rigid_profile = sys::BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION;
        row.downstream_candidate_state = sys::BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
        row.coordinate_available = 1;
        let coordinates: [Vec<f64>; 3] = std::array::from_fn(|_| vec![0.0]);
        row.coordinate_sha256 = canonical_coordinate_sha256(PositionSoa::new(
            &coordinates[0],
            &coordinates[1],
            &coordinates[2],
        ));
        let rigid = valid_rigid_v2_row();
        let mut producer = zeroed_abi_value!(sys::bg_docking_fixed64_producer_row_v1);
        producer.placement_quaternion_w = 1.0;
        let mut torsion = zeroed_abi_value!(sys::bg_docking_torsion_v7_row_v1);
        torsion.status = sys::BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
        torsion.failure_code = sys::BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE;
        RefinementFixture {
            rows: vec![row],
            producer: vec![producer],
            rigid: vec![rigid],
            torsion: vec![torsion],
            coordinates,
            quaternions: [vec![0.0], vec![0.0], vec![0.0], vec![1.0]],
        }
    }

    #[test]
    fn rejects_incomplete_coordinate_ready_refinement_evidence() {
        let mut fixture = valid_refinement_fixture();
        let coordinate_views = [
            fixture.coordinates[0].as_slice(),
            fixture.coordinates[1].as_slice(),
            fixture.coordinates[2].as_slice(),
        ];
        let quaternion_views = [
            fixture.quaternions[0].as_slice(),
            fixture.quaternions[1].as_slice(),
            fixture.quaternions[2].as_slice(),
            fixture.quaternions[3].as_slice(),
        ];
        assert!(validate_refinement_evidence(
            &fixture.rows,
            &fixture.producer,
            &fixture.rigid,
            &fixture.torsion,
            &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
            coordinate_views,
            coordinate_views,
            coordinate_views,
            quaternion_views,
            1,
            Backend::RustCpu,
        )
        .is_ok());

        let substituted_quaternion = [vec![1.0], vec![0.0], vec![0.0], vec![0.0]];
        assert!(validate_refinement_evidence(
            &fixture.rows,
            &fixture.producer,
            &fixture.rigid,
            &fixture.torsion,
            &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
            coordinate_views,
            coordinate_views,
            coordinate_views,
            [
                substituted_quaternion[0].as_slice(),
                substituted_quaternion[1].as_slice(),
                substituted_quaternion[2].as_slice(),
                substituted_quaternion[3].as_slice(),
            ],
            1,
            Backend::RustCpu,
        )
        .is_err());

        let mismatched_origin = [vec![1.0], vec![0.0], vec![0.0]];
        let mismatched_origin_views = [
            mismatched_origin[0].as_slice(),
            mismatched_origin[1].as_slice(),
            mismatched_origin[2].as_slice(),
        ];
        assert!(validate_refinement_evidence(
            &fixture.rows,
            &fixture.producer,
            &fixture.rigid,
            &fixture.torsion,
            &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
            mismatched_origin_views,
            coordinate_views,
            coordinate_views,
            quaternion_views,
            1,
            Backend::RustCpu,
        )
        .is_err());

        fixture.rows[0].coordinate_available = 0;
        assert!(validate_refinement_evidence(
            &fixture.rows,
            &fixture.producer,
            &fixture.rigid,
            &fixture.torsion,
            &[sys::BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION],
            coordinate_views,
            coordinate_views,
            coordinate_views,
            quaternion_views,
            1,
            Backend::RustCpu,
        )
        .is_err());
    }
}

fn assign_shared_identities(
    descriptor: &mut sys::bg_docking_geometric_admission_context_soa_v1,
    identities: Fixed64Identities,
) {
    descriptor.authority_input_receipt_sha256 = identities.authority_input_receipt_sha256;
    descriptor.receptor_system_sha256 = identities.receptor_system_sha256;
    descriptor.ligand_system_sha256 = identities.ligand_system_sha256;
    descriptor.backend_receipt_sha256 = identities.backend_receipt_sha256;
}
