//! Independent geometric-admission evidence and receipt rederivation.

use betelgeuze_docking_search::{
    evaluate_fixed64_geometric_metrics, Fixed64GeometricInput as IndependentFixed64GeometricInput,
    Vec3,
};

use super::{
    bool_from_abi, coordinate_segment, digest_present, sys, Backend, CanonicalHasher, Error,
    ErrorCode, ExpectedPipelineReceiptGraph, Result, Sha256,
};

fn geometric_scientific_fields_are_zero(row: &sys::bg_docking_geometric_admission_row_v1) -> bool {
    row.ligand_atom_count == 0
        && row.receptor_atom_count == 0
        && row.exact_pair_count == 0
        && row.penetration_pair_count == 0
        && row.unique_ligand_penetration_atom_count == 0
        && row.unique_ligand_heavy_atom_penetration_count == 0
        && row.raw_minimum_distance_angstrom == 0.0
        && row.minimum_vdw_surface_gap_angstrom == 0.0
        && row.minimum_vdw_ratio == 0.0
        && row.sphere_overlap_proxy_angstrom3 == 0.0
        && row.pocket_escape_angstrom == 0.0
}

fn backend_numeric_tolerance(backend: Backend, expected: f64, observed: f64) -> f64 {
    let relative = match backend {
        Backend::CppCpuReference | Backend::RustCpu => 2.0e-12,
        Backend::HipSafe => 2.0e-10,
        Backend::HipFast => 2.0e-8,
        Backend::Auto => 2.0e-8,
    };
    relative * 1.0_f64.max(expected.abs()).max(observed.abs())
}

pub(super) fn numeric_matches(backend: Backend, expected: f64, observed: f64) -> bool {
    expected.is_finite()
        && observed.is_finite()
        && (expected - observed).abs() <= backend_numeric_tolerance(backend, expected, observed)
}

fn canonical_geometric_coordinate_receipt(
    coordinates: [&[f64]; 3],
    slot: usize,
    ligand_atom_count: u64,
) -> Result<Sha256> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 geometric ligand denominator does not fit usize",
        )
    })?;
    let owned = coordinate_segment(coordinates, slot, ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 geometric coordinate receipt exceeds its owned buffer",
        )
    })?;
    let mut hash = CanonicalHasher::new("betelgeuze.geometric_admission_coordinate/native-v1");
    hash.u64(slot as u64);
    hash.u64(ligand_atom_count);
    for atom in 0..ligand_count {
        hash.f64(owned.x_angstrom[atom]);
        hash.f64(owned.y_angstrom[atom]);
        hash.f64(owned.z_angstrom[atom]);
    }
    Ok(hash.finish())
}

fn hash_geometric_context(hash: &mut CanonicalHasher, graph: &ExpectedPipelineReceiptGraph) {
    hash.digest(graph.authority_input_receipt_sha256);
    hash.digest(graph.receptor_system_sha256);
    hash.digest(graph.ligand_system_sha256);
    hash.digest(graph.backend_receipt_sha256);
    hash.u32(graph.backend.as_raw() as u32);
    hash.u32(sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL as u32);
    hash.u64(graph.receptor_atom_count);
    hash.u64(graph.ligand_atom_count);
    hash.u64(graph.ligand_heavy_atom_count);
    hash.u64(graph.geometric_max_batch_exact_pair_evaluations);
    for value in graph.pocket_center_angstrom {
        hash.f64(value);
    }
    hash.f64(graph.pocket_radius_angstrom);
    hash.f64(graph.geometric_hard_rejection_minimum_vdw_ratio);
}

pub(super) fn canonical_geometric_row_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    producer_status: sys::bg_docking_fixed64_producer_row_status,
    coordinates: [&[f64]; 3],
    slot: usize,
    row: &sys::bg_docking_geometric_admission_row_v1,
) -> Result<Sha256> {
    let candidate_state = if producer_status == sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED {
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE
    } else {
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE
    };
    let coordinate =
        if candidate_state == sys::BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE {
            [0; 32]
        } else {
            canonical_geometric_coordinate_receipt(coordinates, slot, graph.ligand_atom_count)?
        };
    let mut hash = CanonicalHasher::new("betelgeuze.geometric_admission_row/native-v1");
    hash.string("betelgeuze.engine_v2_native_geometric_admission_row/1.0.0");
    hash_geometric_context(&mut hash, graph);
    hash.u32(candidate_state as u32);
    hash.digest(coordinate);
    hash.u32(row.slot_index);
    hash.u32(row.status as u32);
    hash.u32(row.failure_code as u32);
    hash.u32(row.decision as u32);
    hash.byte(row.rank_eligible);
    hash.u64(row.ligand_atom_count);
    hash.u64(row.receptor_atom_count);
    hash.u64(row.exact_pair_count);
    hash.u64(row.penetration_pair_count);
    hash.u64(row.unique_ligand_penetration_atom_count);
    hash.u64(row.unique_ligand_heavy_atom_penetration_count);
    hash.f64(row.raw_minimum_distance_angstrom);
    hash.f64(row.minimum_vdw_surface_gap_angstrom);
    hash.f64(row.minimum_vdw_ratio);
    hash.f64(row.sphere_overlap_proxy_angstrom3);
    hash.f64(row.pocket_escape_angstrom);
    Ok(hash.finish())
}

pub(super) fn canonical_geometric_batch_receipt(
    graph: &ExpectedPipelineReceiptGraph,
    rows: &[sys::bg_docking_fixed64_producer_row_v1],
) -> Sha256 {
    let admission_rows = rows
        .iter()
        .map(|row| row.geometric_admission)
        .collect::<Vec<_>>();
    canonical_geometric_batch_receipt_rows(graph, &admission_rows)
}

pub(super) fn canonical_geometric_batch_receipt_rows(
    graph: &ExpectedPipelineReceiptGraph,
    rows: &[sys::bg_docking_geometric_admission_row_v1],
) -> Sha256 {
    let mut hash = CanonicalHasher::new("betelgeuze.geometric_admission_batch/native-v1");
    hash.string("betelgeuze.engine_v2_native_geometric_admission_batch/1.0.0");
    hash_geometric_context(&mut hash, graph);
    hash.usize(rows.len());
    for row in rows {
        hash.digest(row.row_receipt_sha256);
    }
    for value in [0_u8, 1, 0, 0, 0, 0, 0, 0, 0] {
        hash.byte(value);
    }
    hash.finish()
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_geometric_admission_row_semantics(
    row: &sys::bg_docking_geometric_admission_row_v1,
    producer_status: sys::bg_docking_fixed64_producer_row_status,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    ligand_heavy_atom_count: u64,
    exact_pair_count: u64,
    hard_rejection_minimum_vdw_ratio: f64,
    backend: Backend,
    geometric_input: &IndependentFixed64GeometricInput,
    producer_coordinates: [&[f64]; 3],
    slot: usize,
) -> Result<()> {
    let rank_eligible = bool_from_abi(row.rank_eligible, "geometric rank eligibility")?;
    if row.reserved0.iter().any(|value| *value != 0)
        || row.reserved1 != 0
        || !digest_present(&row.row_receipt_sha256)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 geometric row metadata is non-canonical",
        ));
    }
    match row.status {
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED => {
            let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 geometric ligand denominator does not fit usize",
                )
            })?;
            let owned =
                coordinate_segment(producer_coordinates, slot, ligand_count).ok_or_else(|| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 geometric coordinates exceed the owned producer buffer",
                    )
                })?;
            let independent_coordinates = (0..ligand_count)
                .map(|atom| {
                    Vec3::new(
                        owned.x_angstrom[atom],
                        owned.y_angstrom[atom],
                        owned.z_angstrom[atom],
                    )
                })
                .collect::<Vec<_>>();
            let metrics =
                evaluate_fixed64_geometric_metrics(&independent_coordinates, geometric_input)
                    .map_err(|error| {
                        Error::local(
                            ErrorCode::AbiMismatch,
                            format!("independent fixed64 geometric evaluation failed: {error}"),
                        )
                    })?;
            let values = [
                row.raw_minimum_distance_angstrom,
                row.minimum_vdw_surface_gap_angstrom,
                row.minimum_vdw_ratio,
                row.sphere_overlap_proxy_angstrom3,
                row.pocket_escape_angstrom,
            ];
            let accepted = row.minimum_vdw_ratio >= hard_rejection_minimum_vdw_ratio;
            let expected_decision = if accepted {
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
            } else {
                sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED
            };
            let penetration_counts_valid = if row.penetration_pair_count == 0 {
                row.unique_ligand_penetration_atom_count == 0
                    && row.unique_ligand_heavy_atom_penetration_count == 0
                    && row.minimum_vdw_surface_gap_angstrom >= 0.0
                    && row.sphere_overlap_proxy_angstrom3 == 0.0
            } else {
                row.unique_ligand_penetration_atom_count > 0
                    && row.minimum_vdw_surface_gap_angstrom < 0.0
                    && row.sphere_overlap_proxy_angstrom3 > 0.0
            };
            if producer_status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED
                || row.failure_code != sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE
                || row.decision != expected_decision
                || rank_eligible != accepted
                || row.ligand_atom_count != ligand_atom_count
                || row.receptor_atom_count != receptor_atom_count
                || row.exact_pair_count != exact_pair_count
                || row.penetration_pair_count > exact_pair_count
                || row.unique_ligand_penetration_atom_count > ligand_atom_count
                || row.unique_ligand_heavy_atom_penetration_count > ligand_heavy_atom_count
                || row.unique_ligand_heavy_atom_penetration_count
                    > row.unique_ligand_penetration_atom_count
                || values.iter().any(|value| !value.is_finite())
                || row.raw_minimum_distance_angstrom < 0.0
                || row.minimum_vdw_ratio < 0.0
                || row.sphere_overlap_proxy_angstrom3 < 0.0
                || row.pocket_escape_angstrom < 0.0
                || !penetration_counts_valid
                || row.ligand_atom_count != metrics.ligand_atom_count() as u64
                || row.receptor_atom_count != metrics.receptor_atom_count() as u64
                || row.exact_pair_count != metrics.exact_pair_count() as u64
                || row.penetration_pair_count != metrics.penetration_pair_count() as u64
                || row.unique_ligand_penetration_atom_count
                    != metrics.unique_ligand_penetration_atom_count() as u64
                || row.unique_ligand_heavy_atom_penetration_count
                    != metrics.unique_ligand_heavy_atom_penetration_count() as u64
                || !numeric_matches(
                    backend,
                    metrics.raw_minimum_distance_angstrom(),
                    row.raw_minimum_distance_angstrom,
                )
                || !numeric_matches(
                    backend,
                    metrics.minimum_vdw_surface_gap_angstrom(),
                    row.minimum_vdw_surface_gap_angstrom,
                )
                || !numeric_matches(backend, metrics.minimum_vdw_ratio(), row.minimum_vdw_ratio)
                || !numeric_matches(
                    backend,
                    metrics.sphere_overlap_proxy_angstrom3(),
                    row.sphere_overlap_proxy_angstrom3,
                )
                || !numeric_matches(
                    backend,
                    metrics.pocket_escape_angstrom(),
                    row.pocket_escape_angstrom,
                )
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 evaluated geometric evidence is inconsistent",
                ));
            }
        }
        sys::BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE => {
            if producer_status != sys::BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE
                || row.failure_code
                    != sys::BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE
                || row.decision != sys::BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED
                || rank_eligible
                || !geometric_scientific_fields_are_zero(row)
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 upstream geometric failure retained scientific evidence",
                ));
            }
        }
        _ => {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 geometric row status is invalid for producer output",
            ));
        }
    }
    Ok(())
}
