use betelgeuze_docking_search::Vec3;
use sha2::{Digest, Sha256 as Sha256Hasher};

use super::types::Sha256;
use super::{
    sys, Backend, Error, ErrorCode, Fixed64CoordinateSource, Fixed64PipelineContext,
    Fixed64RunInput, PositionSoa, Result, FIXED64_NATIVE_COMPONENT_BINDING_PROFILE_ID,
    FIXED64_NATIVE_PIPELINE_PROFILE_ID,
};

pub(crate) struct CanonicalHasher {
    digest: Sha256Hasher,
    transcript: Option<Vec<u8>>,
}

impl CanonicalHasher {
    pub(crate) fn new(domain: &str) -> Self {
        let mut hasher = Self {
            digest: Sha256Hasher::new(),
            transcript: None,
        };
        hasher.string(domain);
        hasher
    }

    pub(crate) fn new_recording(domain: &str) -> Self {
        let mut hasher = Self {
            digest: Sha256Hasher::new(),
            transcript: Some(Vec::new()),
        };
        hasher.string(domain);
        hasher
    }

    fn update(&mut self, bytes: &[u8]) {
        self.digest.update(bytes);
        if let Some(transcript) = &mut self.transcript {
            transcript.extend_from_slice(bytes);
        }
    }

    pub(crate) fn byte(&mut self, value: u8) {
        self.update(&[value]);
    }

    pub(crate) fn u32(&mut self, value: u32) {
        self.update(&value.to_be_bytes());
    }

    pub(crate) fn i32(&mut self, value: i32) {
        self.u32(value as u32);
    }

    pub(crate) fn u64(&mut self, value: u64) {
        self.update(&value.to_be_bytes());
    }

    pub(crate) fn usize(&mut self, value: usize) {
        self.u64(u64::try_from(value).expect("bounded native receipt length fits u64"));
    }

    pub(crate) fn f64(&mut self, value: f64) {
        let canonical = if value == 0.0 { 0.0 } else { value };
        self.u64(canonical.to_bits());
    }

    pub(crate) fn vec3(&mut self, value: Vec3) {
        self.f64(value.x);
        self.f64(value.y);
        self.f64(value.z);
    }

    pub(crate) fn bytes(&mut self, value: &[u8]) {
        self.usize(value.len());
        self.update(value);
    }

    pub(crate) fn string(&mut self, value: &str) {
        self.bytes(value.as_bytes());
    }

    pub(crate) fn digest(&mut self, value: Sha256) {
        self.update(&value);
    }

    pub(crate) fn finish(self) -> Sha256 {
        self.digest.finalize().into()
    }

    pub(crate) fn finish_recording(self) -> (Sha256, Vec<u8>) {
        let transcript = self
            .transcript
            .expect("recording canonical hasher retains its transcript");
        (self.digest.finalize().into(), transcript)
    }
}

pub(super) fn hash_f64_channel(hash: &mut CanonicalHasher, values: &[f64]) {
    hash.usize(values.len());
    for value in values {
        hash.f64(*value);
    }
}

pub(super) fn hash_u8_channel(hash: &mut CanonicalHasher, values: &[u8]) {
    hash.usize(values.len());
    for value in values {
        hash.byte(*value);
    }
}

pub(super) fn hash_u64_channel(hash: &mut CanonicalHasher, values: &[u64]) {
    hash.usize(values.len());
    for value in values {
        hash.u64(*value);
    }
}

pub(super) fn hash_i32_channel(hash: &mut CanonicalHasher, values: &[i32]) {
    hash.usize(values.len());
    for value in values {
        hash.i32(*value);
    }
}

pub(super) fn hash_u32_channel(hash: &mut CanonicalHasher, values: &[u32]) {
    hash.usize(values.len());
    for value in values {
        hash.u32(*value);
    }
}

pub(super) fn hash_bool(hash: &mut CanonicalHasher, value: bool) {
    hash.byte(u8::from(value));
}

pub(super) fn hash_position_soa_owned(hash: &mut CanonicalHasher, value: &crate::PositionSoaOwned) {
    hash_f64_channel(hash, &value.x_angstrom);
    hash_f64_channel(hash, &value.y_angstrom);
    hash_f64_channel(hash, &value.z_angstrom);
}

fn hash_rigid_v2_config(hash: &mut CanonicalHasher, config: &sys::bg_docking_rigid_v2_config_v1) {
    hash.f64(config.overlap_scale);
    hash.f64(config.maximum_step_angstrom);
    hash.f64(config.minimum_step_angstrom);
    hash.f64(config.maximum_total_translation_angstrom);
    hash.u64(config.maximum_backtracking_evaluations);
    hash.f64(config.penalty_tolerance);
    hash.f64(config.epsilon_angstrom);
}

fn hash_rigid_v3_config(hash: &mut CanonicalHasher, config: &sys::bg_docking_rigid_v3_config_v1) {
    hash_rigid_v2_config(hash, &config.v2);
    hash.f64(config.maximum_rotation_step_radians);
    hash.f64(config.minimum_rotation_step_radians);
    hash.f64(config.maximum_total_rotation_radians);
    hash.u64(config.maximum_rotation_steps);
    hash.f64(config.minimum_rotation_relative_penalty_reduction);
    hash.f64(config.maximum_centroid_offset_angstrom);
}

pub(super) fn canonical_admission_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    descriptor: &sys::bg_docking_geometric_admission_context_soa_v1,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_admission_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.x_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.y_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.z_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, scientific.ligand.vdw_radius_angstrom);
    hash_u8_channel(&mut hash, scientific.ligand.heavy_atom_mask);
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash.f64(descriptor.hard_rejection_minimum_vdw_ratio);
    hash.u64(descriptor.max_batch_exact_pair_evaluations);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.finish()
}

pub(super) fn canonical_refinement_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    rigid: &sys::bg_docking_rigid_refinement_context_soa_v1,
    torsion: &sys::bg_docking_torsion_v7_context_soa_v1,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(rigid.unit_system);
    hash.u64(rigid.receptor_atom_count);
    hash.u64(rigid.ligand_atom_count);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.x_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.y_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.z_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, scientific.ligand.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(rigid.pocket_radius_angstrom);
    hash_rigid_v2_config(&mut hash, &rigid.v2);
    hash_rigid_v3_config(&mut hash, &rigid.v3);
    hash_rigid_v3_config(&mut hash, &rigid.clearance_v4);
    hash.i32(torsion.unit_system);
    hash.u64(torsion.receptor_atom_count);
    hash.u64(torsion.ligand_atom_count);
    hash.u64(torsion.rotor_count);
    hash.u64(torsion.internal_pair_count);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.x_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.y_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.coordinates.z_angstrom);
    hash_f64_channel(&mut hash, scientific.receptor.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, scientific.ligand.vdw_radius_angstrom);
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash_i32_channel(&mut hash, scientific.ligand.parent_atom_index);
    hash_u64_channel(&mut hash, scientific.ligand.rotatable_child_atom_index);
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
    hash_u64_channel(&mut hash, &internal_i);
    hash_u64_channel(&mut hash, &internal_j);
    hash.f64(torsion.receptor_overlap_scale);
    hash.f64(torsion.internal_overlap_scale);
    hash.f64(torsion.internal_overlap_weight);
    hash.u64(torsion.maximum_baseline_v6_steps);
    hash.u64(torsion.maximum_torsions_evaluated);
    hash.u64(torsion.maximum_torsion_steps);
    hash.u64(torsion.maximum_backtracking_evaluations);
    hash.f64(torsion.maximum_torsion_step_radians);
    hash.f64(torsion.minimum_torsion_step_radians);
    hash.f64(torsion.maximum_total_torsion_path_radians);
    hash.f64(torsion.maximum_centroid_offset_angstrom);
    hash.f64(torsion.minimum_selected_final_receptor_penalty);
    hash.f64(torsion.maximum_selected_final_receptor_penalty);
    hash.f64(torsion.penalty_tolerance);
    hash.f64(torsion.epsilon_angstrom);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn canonical_scorer_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    descriptor: &sys::bg_docking_scorer_v1_context_soa_v1,
    receptor_donor_atom: &[u64],
    receptor_hydrogen_atom: &[u64],
    ligand_donor_atom: &[u64],
    ligand_hydrogen_atom: &[u64],
    exclusion_i: &[u64],
    exclusion_j: &[u64],
    rotor_i: &[u64],
    rotor_j: &[u64],
    rotor_k: &[u64],
    rotor_l: &[u64],
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_scorer_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    for values in [
        scientific.receptor.coordinates.x_angstrom,
        scientific.receptor.coordinates.y_angstrom,
        scientific.receptor.coordinates.z_angstrom,
        scientific.receptor.charge_elementary,
        scientific.receptor.vdw_radius_angstrom,
        scientific.receptor.epsilon_kcal_per_mol,
    ] {
        hash_f64_channel(&mut hash, values);
    }
    hash_u8_channel(&mut hash, scientific.receptor.hydrophobic_mask);
    hash_u8_channel(&mut hash, scientific.receptor.acceptor_mask);
    for values in [
        scientific.ligand.reference_coordinates.x_angstrom,
        scientific.ligand.reference_coordinates.y_angstrom,
        scientific.ligand.reference_coordinates.z_angstrom,
        scientific.ligand.charge_elementary,
        scientific.ligand.vdw_radius_angstrom,
        scientific.ligand.epsilon_kcal_per_mol,
    ] {
        hash_f64_channel(&mut hash, values);
    }
    hash_u8_channel(&mut hash, scientific.ligand.hydrophobic_mask);
    hash_u8_channel(&mut hash, scientific.ligand.acceptor_mask);
    for values in [
        receptor_donor_atom,
        receptor_hydrogen_atom,
        ligand_donor_atom,
        ligand_hydrogen_atom,
        exclusion_i,
        exclusion_j,
        rotor_i,
        rotor_j,
        rotor_k,
        rotor_l,
    ] {
        hash_u64_channel(&mut hash, values);
    }
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash_f64_channel(&mut hash, &descriptor.weights);
    hash.f64(descriptor.electrostatic_dielectric);
    hash.f64(descriptor.pair_cutoff_angstrom);
    hash.f64(descriptor.hbond_distance_max_angstrom);
    hash.f64(descriptor.polar_burial_distance_angstrom);
    hash.u64(descriptor.max_receptor_candidate_pairs);
    hash.u64(descriptor.max_ligand_pair_checks);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn canonical_validity_context_receipt(
    backend: Backend,
    device_ordinal: i32,
    scientific: Fixed64PipelineContext<'_>,
    descriptor: &sys::bg_docking_pose_validity_context_soa_v1,
    bond_i: &[u64],
    bond_j: &[u64],
    exclusion_i: &[u64],
    exclusion_j: &[u64],
    chirality_center: &[u64],
    chirality_i: &[u64],
    chirality_j: &[u64],
    chirality_k: &[u64],
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_validity_context/1.0.0");
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    for values in [
        scientific.receptor.coordinates.x_angstrom,
        scientific.receptor.coordinates.y_angstrom,
        scientific.receptor.coordinates.z_angstrom,
        scientific.receptor.vdw_radius_angstrom,
        scientific.ligand.reference_coordinates.x_angstrom,
        scientific.ligand.reference_coordinates.y_angstrom,
        scientific.ligand.reference_coordinates.z_angstrom,
        scientific.ligand.vdw_radius_angstrom,
    ] {
        hash_f64_channel(&mut hash, values);
    }
    for values in [
        bond_i,
        bond_j,
        exclusion_i,
        exclusion_j,
        chirality_center,
        chirality_i,
        chirality_j,
        chirality_k,
    ] {
        hash_u64_channel(&mut hash, values);
    }
    hash_f64_channel(&mut hash, &scientific.pocket_center_angstrom);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash.f64(descriptor.bond_length_tolerance_angstrom);
    hash.f64(descriptor.ligand_self_clash_angstrom);
    hash.f64(descriptor.receptor_ligand_clash_angstrom);
    hash.f64(descriptor.rotation_tolerance);
    hash.f64(descriptor.chirality_volume_tolerance);
    hash.f64(descriptor.severe_overlap_scale);
    hash.f64(descriptor.contact_cell_size_angstrom);
    hash.u64(descriptor.max_pair_checks);
    hash.u64(descriptor.max_cross_checks);
    hash.u64(descriptor.max_element_ligand_pair_checks);
    hash.u64(descriptor.max_element_receptor_candidate_pairs);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.scorer_context_receipt_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.digest(descriptor.contact_policy_sha256);
    hash.finish()
}

pub(super) fn canonical_component_binding_receipt(
    backend: Backend,
    device_ordinal: i32,
    admission: Sha256,
    refinement: Sha256,
    scorer: Sha256,
    validity: Sha256,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_component_binding/1.0.0");
    hash.string(FIXED64_NATIVE_COMPONENT_BINDING_PROFILE_ID);
    hash.i32(backend.as_raw());
    hash.i32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    hash.i32(device_ordinal);
    hash.digest(admission);
    hash.digest(refinement);
    hash.digest(scorer);
    hash.digest(validity);
    hash.finish()
}

pub(super) fn canonical_coordinate_sha256(coordinates: PositionSoa<'_>) -> Sha256 {
    let mut hasher = CanonicalHasher::new("betelgeuze.fixed64_coordinates/native-v1");
    hasher.usize(coordinates.x_angstrom.len());
    for atom in 0..coordinates.x_angstrom.len() {
        for value in [
            coordinates.x_angstrom[atom],
            coordinates.y_angstrom[atom],
            coordinates.z_angstrom[atom],
        ] {
            hasher.f64(value);
        }
    }
    hasher.finish()
}

pub(super) fn canonical_source_payload_sha256(
    source: Fixed64CoordinateSource<'_>,
    ligand_atom_count: u64,
) -> Sha256 {
    let mut hasher = CanonicalHasher::new("betelgeuze.fixed64_coordinate_source_abi/native-v1");
    hasher.digest(source.evidence.receipt_sha256);
    hasher.digest(source.evidence.proposal_sha256);
    hasher.digest(source.evidence.coordinate_sha256);
    hasher.u64(ligand_atom_count);
    hasher.byte(1);
    hasher.byte(0);
    hasher.finish()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn canonical_source_bundle_receipt(
    input: Fixed64RunInput<'_>,
    allocation_receipt_sha256: Sha256,
    ligand_atom_count: u64,
    pocket_center_angstrom: [f64; 3],
    authority_input_receipt_sha256: Sha256,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
    backend_receipt_sha256: Sha256,
) -> Result<Sha256> {
    let feature_atom_index_count = input
        .feature_geometries
        .iter()
        .try_fold(0_usize, |total, geometry| {
            total.checked_add(geometry.atom_indices.len())
        })
        .ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 feature atom denominator overflowed while deriving source bundle",
            )
        })?;
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_source_bundle_abi/native-v1");
    hash.digest(allocation_receipt_sha256);
    hash.byte(1);
    hash.digest(canonical_source_payload_sha256(
        input.exact_source,
        ligand_atom_count,
    ));
    hash.usize(input.v7_control_sources.len());
    for source in input.v7_control_sources {
        hash.u32(source.source_index);
        hash.digest(canonical_source_payload_sha256(
            source.source,
            ligand_atom_count,
        ));
    }
    hash.usize(input.conformer_sources.len());
    for source in input.conformer_sources {
        hash.byte(source.rank);
        hash.digest(canonical_source_payload_sha256(
            source.source,
            ligand_atom_count,
        ));
    }
    hash.usize(input.retained_sources.len());
    for source in input.retained_sources {
        hash.u32(source.source_index);
        hash.digest(canonical_source_payload_sha256(
            source.source,
            ligand_atom_count,
        ));
    }
    hash.usize(input.feature_geometries.len());
    hash.usize(feature_atom_index_count);
    hash.digest(input.feature_geometry_inventory_sha256);
    for value in pocket_center_angstrom {
        hash.f64(value);
    }
    for value in input.pocket_normal {
        hash.f64(value);
    }
    hash.digest(authority_input_receipt_sha256);
    hash.digest(receptor_system_sha256);
    hash.digest(ligand_system_sha256);
    hash.digest(backend_receipt_sha256);
    hash.byte(1);
    hash.byte(0);
    Ok(hash.finish())
}

pub(super) fn canonical_refinement_policy_receipt(
    refinement_context_receipt_sha256: Sha256,
    component_binding_receipt_sha256: Sha256,
    allocation_receipt_sha256: Sha256,
    input: Fixed64RunInput<'_>,
) -> Sha256 {
    let mut hash =
        CanonicalHasher::new("betelgeuze.engine_v2_native_fixed64_refinement_policy_receipt/1.0.0");
    hash.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);
    hash.digest(refinement_context_receipt_sha256);
    hash.digest(component_binding_receipt_sha256);
    hash.digest(input.predeclared_refinement_policy_sha256);
    hash.digest(allocation_receipt_sha256);
    hash.f64(input.rmsd_threshold_angstrom);
    hash.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    for slot in 0..sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize {
        hash.i32(input.candidate_modes[slot].as_raw());
        hash.u64(input.rigid_max_steps[slot]);
        hash.byte(input.proposal_is_torsion_eligible[slot]);
        hash.u64(input.torsion_max_steps[slot]);
    }
    hash.usize(input.baseline_torsion_angles_radians.len());
    for value in input.baseline_torsion_angles_radians {
        hash.f64(*value);
    }
    hash.byte(0);
    hash.finish()
}

pub(super) fn canonical_post_admission_policy_receipt(
    admission_context_receipt_sha256: Sha256,
    component_binding_receipt_sha256: Sha256,
    refinement_policy_receipt_sha256: Sha256,
    allocation_receipt_sha256: Sha256,
    input: Fixed64RunInput<'_>,
) -> Sha256 {
    let mut hash = CanonicalHasher::new(
        "betelgeuze.engine_v2_native_fixed64_post_admission_policy_receipt/2.0.0",
    );
    hash.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);
    hash.digest(admission_context_receipt_sha256);
    hash.digest(component_binding_receipt_sha256);
    hash.digest(refinement_policy_receipt_sha256);
    hash.digest(input.predeclared_post_refinement_admission_policy_sha256);
    hash.digest(allocation_receipt_sha256);
    hash.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    hash.byte(0);
    hash.byte(0);
    hash.finish()
}
