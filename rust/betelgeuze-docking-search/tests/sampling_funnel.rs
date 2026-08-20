use std::collections::BTreeSet;

use betelgeuze_docking_search::{
    run_native_sampling_funnel, NativeSamplingFunnelCandidate, NativeSamplingFunnelDecision,
    NativeSamplingFunnelErrorCode, NativeSamplingFunnelLane, NativeSamplingFunnelSelectedState,
    NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR, NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR,
    NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256,
};

const EXPECTED_PROFILE_CANONICAL_SHA256: [u8; 32] = [
    0x5f, 0x9a, 0x3f, 0x30, 0xdd, 0xb1, 0xcf, 0x76, 0xa6, 0x4c, 0xb6, 0x4d, 0xff, 0x67, 0x8c, 0x19,
    0x17, 0x51, 0xe2, 0xea, 0xd3, 0x68, 0xc8, 0xe9, 0xf7, 0x3f, 0x08, 0xd4, 0x4e, 0xc6, 0x9a, 0x28,
];

const EXPECTED_SELECTED_POOL_INDICES: &str =
    include_str!("fixtures/sampling_funnel_selected_indices_v1.txt");

fn digest(value: u64) -> [u8; 32] {
    let mut result = [0u8; 32];
    result[24..].copy_from_slice(&value.to_be_bytes());
    result
}

fn lane(index: usize) -> NativeSamplingFunnelLane {
    match index % 4 {
        0 => NativeSamplingFunnelLane::UniformSo3,
        1 => NativeSamplingFunnelLane::PocketSurface,
        2 => NativeSamplingFunnelLane::SingleAnchor,
        3 => NativeSamplingFunnelLane::MultiAnchor,
        _ => unreachable!(),
    }
}

fn generated_candidate(
    index: usize,
    coordinate_sha256: [u8; 32],
    minimum_vdw_ratio: f64,
    pocket_escape_angstrom: f64,
) -> NativeSamplingFunnelCandidate {
    NativeSamplingFunnelCandidate::generated(
        index,
        lane(index),
        digest(index as u64 + 1),
        digest(index as u64 + 513),
        coordinate_sha256,
        minimum_vdw_ratio,
        pocket_escape_angstrom,
        (index % 17) as f64,
        (index % 11) as f64,
        std::array::from_fn(|dimension| ((index * (dimension + 3)) % 19) as f64),
    )
    .unwrap()
}

fn pool() -> Vec<NativeSamplingFunnelCandidate> {
    (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
        .map(|index| generated_candidate(index, digest(index as u64 + 1025), 0.8, 1.0))
        .collect()
}

fn expected_selected_pool_indices() -> Vec<usize> {
    EXPECTED_SELECTED_POOL_INDICES
        .split_whitespace()
        .map(|value| value.parse().unwrap())
        .collect()
}

#[test]
fn rust_cpu_matches_the_frozen_python_reference_selection() {
    assert_eq!(
        NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256,
        EXPECTED_PROFILE_CANONICAL_SHA256
    );
    let first = run_native_sampling_funnel(pool()).unwrap();
    let second = run_native_sampling_funnel(pool()).unwrap();
    assert_eq!(first.input_denominator(), 512);
    assert_eq!(first.output_denominator(), 64);
    assert_eq!(first.observations().len(), 512);
    assert_eq!(first.selected_rows().len(), 64);
    assert_eq!(first.input_sha256(), second.input_sha256());
    assert_eq!(first.receipt_sha256(), second.receipt_sha256());
    assert!(first.has_valid_receipt());
    assert!(!first.fresh_128_execution_authorized());
    assert!(!first.scientific_claim_authorized());
    assert!(!first.benchmark_claim_authorized());
    assert!(!first.product_authorized());
    assert!(!first.rank_mutation_authorized());
    assert_eq!(
        first
            .selected_rows()
            .iter()
            .map(|row| row.source_pool_index().unwrap())
            .collect::<Vec<_>>(),
        expected_selected_pool_indices()
    );
    for summary in first.lane_summaries() {
        assert_eq!(summary.generated_count(), 128);
        assert_eq!(summary.typed_failure_count(), 0);
        assert_eq!(summary.hard_rejected_vdw_count(), 0);
        assert_eq!(summary.hard_rejected_pocket_count(), 0);
        assert_eq!(summary.duplicate_count(), 0);
        assert_eq!(summary.filtered_count(), 0);
        assert_eq!(summary.eligible_count(), 128);
        assert_eq!(summary.selected_count(), summary.quota());
        assert_eq!(summary.shortfall_count(), 0);
    }
}

#[test]
fn global_coordinate_duplicate_is_failure_complete_and_never_selected_twice() {
    let mut candidates = pool();
    candidates[1] = generated_candidate(1, digest(1025), 0.8, 1.0);
    let result = run_native_sampling_funnel(candidates).unwrap();
    assert_eq!(
        result.observations()[0].decision(),
        NativeSamplingFunnelDecision::Eligible
    );
    assert_eq!(
        result.observations()[1].decision(),
        NativeSamplingFunnelDecision::DuplicateCoordinate
    );
    let summary = result.lane_summary(NativeSamplingFunnelLane::PocketSurface);
    assert_eq!(summary.duplicate_count(), 1);
    assert_eq!(summary.filtered_count(), 1);
    assert_eq!(summary.eligible_count(), 127);
    let coordinates = result
        .selected_rows()
        .iter()
        .filter_map(|row| match row.state() {
            NativeSamplingFunnelSelectedState::Selected {
                coordinate_sha256, ..
            } => Some(coordinate_sha256),
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => None,
        })
        .collect::<Vec<_>>();
    assert_eq!(
        coordinates.len(),
        coordinates.iter().copied().collect::<BTreeSet<_>>().len()
    );
}

#[test]
fn typed_lane_shortfall_preserves_the_exact_64_row_output() {
    let candidates = pool()
        .into_iter()
        .enumerate()
        .map(|(index, candidate)| {
            if lane(index) == NativeSamplingFunnelLane::MultiAnchor {
                NativeSamplingFunnelCandidate::typed_failure(
                    index,
                    NativeSamplingFunnelLane::MultiAnchor,
                    "feature_missing",
                )
                .unwrap()
            } else {
                candidate
            }
        })
        .collect();
    let result = run_native_sampling_funnel(candidates).unwrap();
    assert_eq!(
        result.selected_rows().len(),
        NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
    );
    assert!(result.selected_rows()[56..].iter().all(|row| {
        row.lane() == NativeSamplingFunnelLane::MultiAnchor
            && row.state() == NativeSamplingFunnelSelectedState::LaneQuotaUnfilled
    }));
    let summary = result.lane_summary(NativeSamplingFunnelLane::MultiAnchor);
    assert_eq!(summary.generated_count(), 0);
    assert_eq!(summary.typed_failure_count(), 128);
    assert_eq!(summary.eligible_count(), 0);
    assert_eq!(summary.selected_count(), 0);
    assert_eq!(summary.shortfall_count(), 8);
}

#[test]
fn hard_geometric_rejections_are_counted_and_not_selected() {
    let mut candidates = pool();
    candidates[0] = generated_candidate(0, digest(1025), 0.1, 1.0);
    candidates[1] = generated_candidate(1, digest(1026), 0.8, 5.0);
    let result = run_native_sampling_funnel(candidates).unwrap();
    assert_eq!(
        result.observations()[0].decision(),
        NativeSamplingFunnelDecision::HardRejectVdw
    );
    assert_eq!(
        result.observations()[1].decision(),
        NativeSamplingFunnelDecision::HardRejectPocket
    );
    assert!(result.selected_rows().iter().all(|row| row
        .source_pool_index()
        .is_none_or(|index| index != 0 && index != 1)));
    assert_eq!(
        result
            .lane_summary(NativeSamplingFunnelLane::UniformSo3)
            .hard_rejected_vdw_count(),
        1
    );
    assert_eq!(
        result
            .lane_summary(NativeSamplingFunnelLane::PocketSurface)
            .hard_rejected_pocket_count(),
        1
    );
}

#[test]
fn reordered_pool_is_rejected_as_cross_wired() {
    let mut candidates = pool();
    candidates.swap(0, 1);
    let error = run_native_sampling_funnel(candidates).unwrap_err();
    assert_eq!(error.code(), NativeSamplingFunnelErrorCode::InputCrossWired);
}
