//! Independent stable-ranking and direct-coordinate RMSD clustering replay.

use super::{bool_from_abi, digest_present, sys, Error, ErrorCode, Result};

pub(super) fn counted_index_prefix<'a>(
    values: &'a [u32],
    count: u64,
    label: &str,
) -> Result<&'a [u32]> {
    let count = usize::try_from(count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("native fixed64 {label} count does not fit usize"),
        )
    })?;
    values.get(..count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("native fixed64 {label} count exceeds the supplied buffer"),
        )
    })
}

fn direct_coordinate_rmsd(
    coordinates: [&[f64]; 3],
    ligand_atom_count: u64,
    left_slot: usize,
    right_slot: usize,
) -> Result<f64> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD ligand denominator does not fit usize",
        )
    })?;
    if ligand_count == 0 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD ligand denominator is zero",
        ));
    }
    let left_begin = left_slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 left RMSD coordinate offset overflowed",
        )
    })?;
    let right_begin = right_slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 right RMSD coordinate offset overflowed",
        )
    })?;
    let coordinate_count = (sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize)
        .checked_mul(ligand_count)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 RMSD coordinate denominator overflowed",
            )
        })?;
    if coordinates
        .iter()
        .any(|channel| channel.len() != coordinate_count)
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD coordinate denominator is invalid",
        ));
    }
    let mut squared_sum = 0.0;
    for atom in 0..ligand_count {
        let dx = coordinates[0][left_begin + atom] - coordinates[0][right_begin + atom];
        let dy = coordinates[1][left_begin + atom] - coordinates[1][right_begin + atom];
        let dz = coordinates[2][left_begin + atom] - coordinates[2][right_begin + atom];
        if !dx.is_finite() || !dy.is_finite() || !dz.is_finite() {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 RMSD coordinate delta is non-finite",
            ));
        }
        squared_sum += dx * dx + dy * dy + dz * dz;
    }
    let rmsd = (squared_sum / ligand_count as f64).sqrt();
    if !rmsd.is_finite() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 direct-coordinate RMSD is non-finite",
        ));
    }
    Ok(rmsd)
}

#[allow(clippy::too_many_arguments)]
pub(super) fn validate_index_evidence(
    ranking: &sys::bg_docking_stable_top_k_output_v1,
    cluster: &sys::bg_docking_rmsd_cluster_output_v1,
    scorer_rows: &[sys::bg_docking_scorer_v1_row_v1],
    validity_rows: &[sys::bg_docking_pose_validity_row_v1],
    ranking_rows: &[sys::bg_docking_stable_top_k_row_v1],
    cluster_rows: &[sys::bg_docking_rmsd_cluster_row_v1],
    primary_indices: &[u32],
    valid_indices: &[u32],
    representative_indices: &[u32],
    top_k_indices: &[u32],
    rmsd_threshold_angstrom: f64,
    final_coordinates: [&[f64]; 3],
    ligand_atom_count: u64,
) -> Result<()> {
    let candidate_count = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    if scorer_rows.len() != candidate_count
        || validity_rows.len() != candidate_count
        || ranking_rows.len() != candidate_count
        || cluster_rows.len() != candidate_count
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 rank or cluster row denominator is invalid",
        ));
    }
    if !rmsd_threshold_angstrom.is_finite() || rmsd_threshold_angstrom <= 0.0 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 RMSD threshold is invalid",
        ));
    }
    let primary =
        counted_index_prefix(primary_indices, ranking.primary_index_count, "primary rank")?;
    let valid = counted_index_prefix(valid_indices, ranking.valid_index_count, "valid rank")?;
    let representatives = counted_index_prefix(
        representative_indices,
        cluster.representative_index_count,
        "cluster representative",
    )?;
    let top_k = counted_index_prefix(top_k_indices, cluster.top_k_index_count, "cluster Top-K")?;
    let mut primary_seen = vec![false; candidate_count];
    let mut previous_ranked: Option<(f64, usize)> = None;
    for (offset, raw_slot) in primary.iter().copied().enumerate() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank slot does not fit usize",
            )
        })?;
        if slot >= candidate_count || primary_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank slots are out of range or duplicated",
            ));
        }
        let row = &ranking_rows[slot];
        let score = row.total_score;
        let incorrectly_ordered = previous_ranked.is_some_and(|(previous_score, previous_slot)| {
            score < previous_score || (score == previous_score && slot < previous_slot)
        });
        if !score.is_finite()
            || incorrectly_ordered
            || !bool_from_abi(row.rank_eligible, "rank eligibility")?
            || row.stable_rank as usize != offset + 1
            || scorer_rows[slot].status != sys::BG_DOCKING_SCORER_V1_ROW_SCORED
            || score != scorer_rows[slot].total_score
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank slots disagree with scorer or ranking rows",
            ));
        }
        primary_seen[slot] = true;
        previous_ranked = Some((score, slot));
    }
    for (slot, row) in ranking_rows.iter().enumerate() {
        let rank_eligible = bool_from_abi(row.rank_eligible, "rank eligibility")?;
        if rank_eligible != primary_seen[slot]
            || rank_eligible != (scorer_rows[slot].status == sys::BG_DOCKING_SCORER_V1_ROW_SCORED)
            || (!rank_eligible && row.stable_rank != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 primary rank membership is inconsistent",
            ));
        }
    }

    let expected_valid = primary
        .iter()
        .copied()
        .filter(|raw_slot| {
            let slot = *raw_slot as usize;
            validity_rows[slot].status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
                && validity_rows[slot].passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
                && validity_rows[slot].blocker_mask == 0
        })
        .collect::<Vec<_>>();
    if valid != expected_valid.as_slice() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 valid rank order is not the validity-filtered primary order",
        ));
    }

    let mut valid_seen = vec![false; candidate_count];
    for (offset, raw_slot) in valid.iter().copied().enumerate() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank slot does not fit usize",
            )
        })?;
        if slot >= candidate_count || valid_seen[slot] || !primary_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank slots are out of range, duplicated, or unranked",
            ));
        }
        let row = &ranking_rows[slot];
        if !bool_from_abi(row.valid_rank_eligible, "valid-rank eligibility")?
            || row.stable_valid_rank as usize != offset + 1
            || validity_rows[slot].status != sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
            || validity_rows[slot].passed_check_mask != sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
            || validity_rows[slot].blocker_mask != 0
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank slots disagree with validity or ranking rows",
            ));
        }
        valid_seen[slot] = true;
    }
    for (slot, row) in ranking_rows.iter().enumerate() {
        let valid_rank_eligible = bool_from_abi(row.valid_rank_eligible, "valid-rank eligibility")?;
        let expected_valid = primary_seen[slot]
            && validity_rows[slot].status == sys::BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED
            && validity_rows[slot].passed_check_mask == sys::BG_DOCKING_POSE_VALIDITY_CHECK_ALL
            && validity_rows[slot].blocker_mask == 0;
        if valid_rank_eligible != valid_seen[slot]
            || valid_rank_eligible != expected_valid
            || (!valid_rank_eligible && row.stable_valid_rank != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid rank membership is inconsistent",
            ));
        }
    }

    let mut expected_representatives = Vec::<u32>::new();
    for raw_slot in valid.iter().copied() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 valid slot does not fit usize during cluster reconstruction",
            )
        })?;
        let mut matched = false;
        for raw_representative in &expected_representatives {
            let representative_slot = usize::try_from(*raw_representative).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 reconstructed representative does not fit usize",
                )
            })?;
            let rmsd = direct_coordinate_rmsd(
                final_coordinates,
                ligand_atom_count,
                slot,
                representative_slot,
            )?;
            let tolerance = 2.0e-12 * 1.0_f64.max(rmsd.abs());
            if rmsd <= rmsd_threshold_angstrom + tolerance {
                matched = true;
                break;
            }
        }
        if !matched {
            expected_representatives.push(raw_slot);
        }
    }
    if representatives != expected_representatives.as_slice() {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 representative order disagrees with independent stable-valid-rank reconstruction",
        ));
    }

    let mut representative_seen = vec![false; candidate_count];
    for (offset, raw_slot) in representatives.iter().copied().enumerate() {
        let slot = usize::try_from(raw_slot).map_err(|_| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 representative slot does not fit usize",
            )
        })?;
        if slot >= candidate_count || representative_seen[slot] || !valid_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 representative slots are out of range, duplicated, or invalid",
            ));
        }
        let row = &cluster_rows[slot];
        if !bool_from_abi(row.cluster_eligible, "cluster eligibility")?
            || !bool_from_abi(row.representative, "cluster representative")?
            || row.representative_slot_index as usize != slot
            || row.cluster_id as usize != offset + 1
            || row.cluster_rank as usize != offset + 1
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 representative slots disagree with cluster rows",
            ));
        }
        representative_seen[slot] = true;
    }
    let mut observed_cluster_sizes = vec![0_u32; representatives.len()];
    for (slot, row) in cluster_rows.iter().enumerate() {
        if row.reserved0 != 0 || row.reserved1 != 0 || row.reserved.iter().any(|value| *value != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 cluster row ABI shape is invalid",
            ));
        }
        let eligible = bool_from_abi(row.cluster_eligible, "cluster eligibility")?;
        let representative = bool_from_abi(row.representative, "cluster representative")?;
        if eligible != valid_seen[slot] || representative != representative_seen[slot] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 cluster membership is inconsistent",
            ));
        }
        if eligible {
            let cluster_id = usize::try_from(row.cluster_id).map_err(|_| {
                Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 cluster id does not fit usize",
                )
            })?;
            let representative_slot =
                usize::try_from(row.representative_slot_index).map_err(|_| {
                    Error::local(
                        ErrorCode::AbiMismatch,
                        "native fixed64 representative identity does not fit usize",
                    )
                })?;
            if row.status != sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED
                || row.stable_valid_rank != ranking_rows[slot].stable_valid_rank
                || cluster_id == 0
                || cluster_id > representatives.len()
                || row.cluster_rank != row.cluster_id
                || representative_slot >= candidate_count
                || !representative_seen[representative_slot]
                || representatives[cluster_id - 1] as usize != representative_slot
                || row.coordinate_sha256 != ranking_rows[slot].coordinate_sha256
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 clustered row is inconsistent with rank evidence",
                ));
            }
            let expected_rmsd = direct_coordinate_rmsd(
                final_coordinates,
                ligand_atom_count,
                slot,
                representative_slot,
            )?;
            let tolerance = 2.0e-12
                * 1.0_f64
                    .max(expected_rmsd.abs())
                    .max(row.direct_rmsd_to_representative_angstrom.abs());
            let assigned_to_first_matching_representative =
                representatives.iter().take(cluster_id - 1).all(|earlier| {
                    let Ok(earlier_slot) = usize::try_from(*earlier) else {
                        return false;
                    };
                    let Ok(earlier_rmsd) = direct_coordinate_rmsd(
                        final_coordinates,
                        ligand_atom_count,
                        slot,
                        earlier_slot,
                    ) else {
                        return false;
                    };
                    let earlier_tolerance = 2.0e-12 * 1.0_f64.max(earlier_rmsd.abs());
                    earlier_rmsd > rmsd_threshold_angstrom + earlier_tolerance
                });
            if !row.direct_rmsd_to_representative_angstrom.is_finite()
                || row.direct_rmsd_to_representative_angstrom < 0.0
                || row.direct_rmsd_to_representative_angstrom > rmsd_threshold_angstrom + tolerance
                || (row.direct_rmsd_to_representative_angstrom - expected_rmsd).abs() > tolerance
                || (representative && row.direct_rmsd_to_representative_angstrom != 0.0)
                || !assigned_to_first_matching_representative
            {
                return Err(Error::local(
                    ErrorCode::AbiMismatch,
                    "native fixed64 cluster RMSD disagrees with final coordinates",
                ));
            }
            observed_cluster_sizes[cluster_id - 1] += 1;
        } else if row.status != sys::BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID
            || row.stable_valid_rank != 0
            || row.cluster_id != 0
            || row.representative_slot_index != 0
            || row.cluster_rank != 0
            || row.top_k_rank != 0
            || row.cluster_size != 0
            || row.direct_rmsd_to_representative_angstrom != 0.0
            || digest_present(&row.coordinate_sha256)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 non-clustered row retained cluster evidence",
            ));
        }
    }
    for row in cluster_rows
        .iter()
        .filter(|row| row.status == sys::BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED)
    {
        if row.cluster_size != observed_cluster_sizes[row.cluster_id as usize - 1] {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 cluster size evidence is inconsistent",
            ));
        }
    }

    let expected_top_k_count = representatives
        .len()
        .min(sys::BG_DOCKING_STABLE_TOP_K_LIMIT as usize);
    if top_k.len() != expected_top_k_count {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 Top-K count does not contain the complete frozen prefix",
        ));
    }
    let mut top_k_seen = vec![false; candidate_count];
    for (offset, raw_slot) in top_k.iter().copied().enumerate() {
        let slot = raw_slot as usize;
        if slot >= candidate_count
            || top_k_seen[slot]
            || representatives.get(offset).copied() != Some(raw_slot)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 Top-K slots are out of range, duplicated, or reordered",
            ));
        }
        let row = &cluster_rows[slot];
        if !bool_from_abi(row.top_k_representative, "cluster Top-K representative")?
            || row.top_k_rank as usize != offset + 1
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 Top-K slots disagree with cluster rows",
            ));
        }
        top_k_seen[slot] = true;
    }
    for (slot, row) in cluster_rows.iter().enumerate() {
        let top_k_representative =
            bool_from_abi(row.top_k_representative, "cluster Top-K representative")?;
        if top_k_representative != top_k_seen[slot]
            || (!top_k_representative && row.top_k_rank != 0)
        {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 Top-K membership is inconsistent",
            ));
        }
    }
    Ok(())
}
