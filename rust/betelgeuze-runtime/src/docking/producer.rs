//! Frozen producer slot/source mapping, row semantics, and receipt authentication.

use super::{
    bool_from_abi, canonical_coordinate_sha256, canonical_source_payload_sha256,
    coordinate_segment, coordinate_segment_matches, digest_present, sys, unit_quaternion,
    CanonicalHasher, Error, ErrorCode, ExpectedPipelineReceiptGraph, Fixed64CoordinateSource,
    Fixed64RunInput, Result, Sha256,
};

pub(super) fn fixed64_lane_and_placement_for_slot(
    slot: usize,
) -> Option<(
    sys::bg_docking_fixed64_lane,
    sys::bg_docking_fixed64_producer_placement_kind,
)> {
    let (lane, placement) = match slot {
        0..=7 => (
            sys::BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH,
        ),
        8..=23 => (
            sys::BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH,
        ),
        24..=35 => (
            sys::BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3,
        ),
        36..=43 => (
            sys::BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3,
        ),
        44..=47 => (
            sys::BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        48..=51 => (
            sys::BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        52..=55 => (
            sys::BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        56..=57 => (
            sys::BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        58..=59 => (
            sys::BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR,
        ),
        60..=63 => (
            sys::BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS,
            sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH,
        ),
        _ => return None,
    };
    Some((lane, placement))
}

pub(super) fn fixed64_source_for_slot(
    input: Fixed64RunInput<'_>,
    slot: usize,
) -> Option<Fixed64CoordinateSource<'_>> {
    const CONFORMER_RANKS: [u8; 8] = [2, 3, 4, 5, 6, 7, 8, 2];
    const RETAINED_INDICES: [u32; 4] = [36, 45, 54, 63];
    match slot {
        0..=23 => input
            .v7_control_sources
            .iter()
            .find(|source| source.source_index == slot as u32)
            .map(|source| source.source),
        24..=35 | 44..=59 => Some(input.exact_source),
        36..=43 => {
            let rank = CONFORMER_RANKS[slot - 36];
            input
                .conformer_sources
                .iter()
                .find(|source| source.rank == rank)
                .map(|source| source.source)
        }
        60..=63 => {
            let source_index = RETAINED_INDICES[slot - 60];
            input
                .retained_sources
                .iter()
                .find(|source| source.source_index == source_index)
                .map(|source| source.source)
        }
        _ => None,
    }
}

fn coordinate_segment_matches_source(
    channels: [&[f64]; 3],
    slot: usize,
    source: Fixed64CoordinateSource<'_>,
) -> bool {
    coordinate_segment(channels, slot, source.coordinates.x_angstrom.len()).is_some_and(
        |observed| {
            [
                (observed.x_angstrom, source.coordinates.x_angstrom),
                (observed.y_angstrom, source.coordinates.y_angstrom),
                (observed.z_angstrom, source.coordinates.z_angstrom),
            ]
            .iter()
            .all(|(left, right)| {
                left.iter()
                    .zip(*right)
                    .all(|(left, right)| left.to_bits() == right.to_bits())
            })
        },
    )
}

pub(super) fn validate_producer_row_semantics(
    row: &sys::bg_docking_fixed64_producer_row_v1,
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
    expected_source: Option<Fixed64CoordinateSource<'_>>,
) -> Result<()> {
    let (expected_lane, expected_placement) = fixed64_lane_and_placement_for_slot(slot)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer slot is outside the frozen profile",
            )
        })?;
    let coordinates_available = bool_from_abi(
        row.coordinates_available,
        "producer coordinate availability",
    )?;
    let steric_precheck = bool_from_abi(row.steric_precheck_passed, "producer steric precheck")?;
    let source_verified = bool_from_abi(row.source_identity_verified, "producer source identity")?;
    let allocation_verified = bool_from_abi(
        row.allocation_identity_verified,
        "producer allocation identity",
    )?;
    let geometric_verified = bool_from_abi(
        row.geometric_identity_verified,
        "producer geometric identity",
    )?;
    let rank_eligible = bool_from_abi(
        row.geometric_admission.rank_eligible,
        "producer geometric rank eligibility",
    )?;
    let source_digests_present = digest_present(&row.source_payload_receipt_sha256)
        && digest_present(&row.source_proposal_sha256)
        && digest_present(&row.source_coordinate_sha256);
    let source_digests_zero = !digest_present(&row.source_payload_receipt_sha256)
        && !digest_present(&row.source_proposal_sha256)
        && !digest_present(&row.source_coordinate_sha256);
    let source_evidence_matches =
        expected_source.map_or(!source_verified && source_digests_zero, |source| {
            source_verified
                && row.source_payload_receipt_sha256
                    == canonical_source_payload_sha256(source, ligand_atom_count)
                && row.source_proposal_sha256 == source.evidence.proposal_sha256
                && row.source_coordinate_sha256 == source.evidence.coordinate_sha256
        });
    if row.reserved0 != 0
        || row.lane != expected_lane
        || row.placement_kind != expected_placement
        || !digest_present(&row.allocation_slot_receipt_sha256)
        || !allocation_verified
        || !geometric_verified
        || source_verified != source_digests_present
        || (!source_verified && !source_digests_zero)
        || !source_evidence_matches
        || steric_precheck != rank_eligible
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 producer identity evidence is inconsistent",
        ));
    }
    let quaternion = [
        row.placement_quaternion_x,
        row.placement_quaternion_y,
        row.placement_quaternion_z,
        row.placement_quaternion_w,
    ];
    match row.status {
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED => {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer ligand denominator does not fit usize",
                )
            })?;
            let output_coordinate_matches = coordinate_segment(coordinates, slot, ligand_count)
                .is_some_and(|segment| {
                    canonical_coordinate_sha256(segment) == row.output_coordinate_sha256
                });
            let exact_passthrough_evidence_matches = row.placement_kind
                != sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
                || expected_source.is_some_and(|source| {
                    quaternion == [0.0, 0.0, 0.0, 1.0]
                        && row.output_proposal_sha256 == source.evidence.proposal_sha256
                        && row.output_coordinate_sha256 == source.evidence.coordinate_sha256
                        && coordinate_segment_matches_source(coordinates, slot, source)
                });
            if row.failure_code != sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE
                || row.component_failure_code != 0
                || row.placement_kind < sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
                || row.placement_kind > sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
                || !coordinates_available
                || !source_verified
                || !digest_present(&row.placement_receipt_sha256)
                || !digest_present(&row.output_proposal_sha256)
                || !digest_present(&row.output_coordinate_sha256)
                || !unit_quaternion(quaternion)
                || !output_coordinate_matches
                || !exact_passthrough_evidence_matches
                || !coordinate_segment_matches(&coordinates, slot, ligand_atom_count, false)?
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 generated producer row retained invalid success evidence",
                ));
            }
        }
        sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE => {
            let valid_component_failure = match row.failure_code {
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE => {
                    expected_placement
                        == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
                        && (sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY
                            ..=sys::BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT)
                            .contains(&row.component_failure_code)
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE => {
                    expected_placement
                        == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
                        && (sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION
                            ..=sys::BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT)
                            .contains(&row.component_failure_code)
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE
                | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE => {
                    row.component_failure_code == 0
                        && (row.failure_code
                            != sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE
                            || expected_source.is_none())
                }
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE => {
                    expected_placement
                        == sys::BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR
                        && row.component_failure_code == 0
                }
                _ => false,
            };
            let component_placement_failed = matches!(
                row.failure_code,
                sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE
                    | sys::BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE
            );
            if !valid_component_failure
                || digest_present(&row.placement_receipt_sha256) != component_placement_failed
                || coordinates_available
                || digest_present(&row.output_proposal_sha256)
                || digest_present(&row.output_coordinate_sha256)
                || quaternion.iter().any(|value| *value != 0.0)
                || !coordinate_segment_matches(&coordinates, slot, ligand_atom_count, true)?
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 producer typed failure retained output evidence",
                ));
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 producer row status is unknown",
            ));
        }
    }
    Ok(())
}

pub(super) fn canonical_producer_row_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    row: &sys::bg_docking_fixed64_producer_row_v1,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_producer_row_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2");
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(graph.source_bundle_receipt_sha256);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.u32(row.lane as u32);
    hash.u32(row.status as u32);
    hash.u32(row.failure_code as u32);
    hash.u32(row.placement_kind as u32);
    hash.u32(row.component_failure_code as u32);
    hash.u32(row.backend as u32);
    hash.u64(row.ligand_atom_count);
    hash.u64(row.coordinate_offset);
    hash.digest(row.source_payload_receipt_sha256);
    hash.digest(row.source_proposal_sha256);
    hash.digest(row.source_coordinate_sha256);
    hash.digest(row.placement_receipt_sha256);
    hash.f64(row.placement_quaternion_x);
    hash.f64(row.placement_quaternion_y);
    hash.f64(row.placement_quaternion_z);
    hash.f64(row.placement_quaternion_w);
    hash.digest(row.output_proposal_sha256);
    hash.digest(row.output_coordinate_sha256);
    hash.digest(row.geometric_admission.row_receipt_sha256);
    for value in [
        row.coordinates_available,
        row.steric_precheck_passed,
        row.source_identity_verified,
        row.allocation_identity_verified,
        row.geometric_identity_verified,
        row.result_dependent_input_consumed,
        row.fallback_allowed,
        row.multi_anchor_consumed,
        row.denominator_preserved,
        row.molecular_execution_authorized,
        row.reservation_authorized,
        row.benchmark_execution_authorized,
        row.existing_rank_auto_change_authorized,
        row.customer_pose_emission_authorized,
        row.production_claim_authorized,
        row.scientific_claim_authorized,
    ] {
        hash.byte(value);
    }
    hash.finish()
}

pub(super) fn canonical_passthrough_placement_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    row: &sys::bg_docking_fixed64_producer_row_v1,
    source: Fixed64CoordinateSource<'_>,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_passthrough_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2");
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.u32(row.lane as u32);
    hash.u32(graph.backend.as_raw() as u32);
    hash.digest(canonical_source_payload_sha256(
        source,
        graph.ligand_atom_count,
    ));
    hash.digest(source.evidence.coordinate_sha256);
    hash.byte(1);
    hash.byte(0);
    hash.finish()
}

pub(super) fn canonical_generated_proposal_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    row: &sys::bg_docking_fixed64_producer_row_v1,
    source: Fixed64CoordinateSource<'_>,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_generated_proposal_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2");
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.digest(canonical_source_payload_sha256(
        source,
        graph.ligand_atom_count,
    ));
    hash.digest(row.placement_receipt_sha256);
    hash.digest(row.output_coordinate_sha256);
    hash.byte(0);
    hash.finish()
}

pub(super) fn canonical_producer_batch_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    geometric_batch_receipt_sha256: Sha256,
    rows: &[sys::bg_docking_fixed64_producer_row_v1],
    generated_count: u64,
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.fixed64_producer_batch_abi/native-v1");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer_batch/1.1.0");
    hash.string("betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2");
    hash.u32(graph.backend.as_raw() as u32);
    hash.usize(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize);
    hash.u64(generated_count);
    hash.u64(u64::from(sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT) - generated_count);
    hash.digest(graph.allocation_inventory_sha256);
    hash.digest(graph.allocation_receipt_sha256);
    hash.digest(graph.source_bundle_receipt_sha256);
    hash.digest(geometric_batch_receipt_sha256);
    for row in rows {
        hash.digest(row.row_receipt_sha256);
    }
    for value in [0_u8, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0] {
        hash.byte(value);
    }
    hash.finish()
}
