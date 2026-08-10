use crate::model::RankedPose;
use crate::surface::Candidate;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct ClusterAssignment {
    pub candidate_index: usize,
    pub cluster_id: usize,
    pub representative: bool,
    pub final_rank: Option<usize>,
}

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct ClusterOutcome {
    pub poses: Vec<RankedPose>,
    pub assignments: Vec<ClusterAssignment>,
    pub cluster_count: usize,
}

pub(crate) fn cluster_and_top_k(
    candidates: &[Candidate],
    valid_indices: &[usize],
    rmsd_threshold_angstrom: f64,
    top_k: usize,
) -> ClusterOutcome {
    let mut ordered = valid_indices.to_vec();
    ordered.sort_by(|left, right| {
        candidates[*left]
            .energy_kcal_per_mol
            .total_cmp(&candidates[*right].energy_kcal_per_mol)
            .then_with(|| candidates[*left].key.cmp(&candidates[*right].key))
    });
    let mut representatives: Vec<usize> = Vec::new();
    let mut member_indices: Vec<Vec<usize>> = Vec::new();
    for candidate_index in ordered {
        if let Some(cluster_index) = representatives.iter().position(|representative_index| {
            coordinate_rmsd(
                &candidates[*representative_index].coordinates_angstrom,
                &candidates[candidate_index].coordinates_angstrom,
            ) <= rmsd_threshold_angstrom
        }) {
            member_indices[cluster_index].push(candidate_index);
        } else {
            representatives.push(candidate_index);
            member_indices.push(vec![candidate_index]);
        }
    }
    let poses = representatives
        .iter()
        .copied()
        .take(top_k)
        .enumerate()
        .map(|(index, representative_index)| {
            let representative = &candidates[representative_index];
            RankedPose {
                rank: index + 1,
                key: representative.key,
                coordinates_angstrom: representative.coordinates_angstrom.clone(),
                energy_kcal_per_mol: representative.energy_kcal_per_mol,
                cluster_size: member_indices[index].len(),
                minimum_receptor_gap_angstrom: representative.minimum_receptor_gap_angstrom,
            }
        })
        .collect();
    let mut assignments = Vec::with_capacity(valid_indices.len());
    for (cluster_index, members) in member_indices.iter().enumerate() {
        for &candidate_index in members {
            let representative = candidate_index == representatives[cluster_index];
            assignments.push(ClusterAssignment {
                candidate_index,
                cluster_id: cluster_index + 1,
                representative,
                final_rank: if representative && cluster_index < top_k {
                    Some(cluster_index + 1)
                } else {
                    None
                },
            });
        }
    }
    assignments.sort_by_key(|assignment| assignment.candidate_index);
    ClusterOutcome {
        poses,
        assignments,
        cluster_count: representatives.len(),
    }
}

fn coordinate_rmsd(left: &[crate::Vec3], right: &[crate::Vec3]) -> f64 {
    if left.len() != right.len() || left.is_empty() {
        return f64::INFINITY;
    }
    let squared_sum = left
        .iter()
        .zip(right)
        .map(|(left, right)| left.minus(*right).norm_squared())
        .sum::<f64>();
    (squared_sum / left.len() as f64).sqrt()
}
