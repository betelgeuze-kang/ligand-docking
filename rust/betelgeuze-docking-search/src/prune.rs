use crate::geometry::centroid;
use crate::model::{ReceptorAtom, SearchConfig, SearchInput};
use crate::surface::Candidate;

pub(crate) fn coarse_select(
    candidates: &mut [Candidate],
    input: &SearchInput,
    config: &SearchConfig,
) -> Vec<usize> {
    for candidate in &mut *candidates {
        let center = centroid(&candidate.coordinates_angstrom);
        let ligand_extent = candidate
            .coordinates_angstrom
            .iter()
            .zip(&input.ligand_atoms)
            .map(|(position, atom)| position.minus(center).norm() + atom.vdw_radius_angstrom)
            .fold(0.0, f64::max);
        let maximum_overlap = input
            .receptor_atoms
            .iter()
            .map(|atom| bounding_overlap(center, ligand_extent, atom))
            .fold(0.0, f64::max);
        let fit_penalty =
            candidate.anchor_fit_rmsd_angstrom / config.dual_anchor_distance_tolerance_angstrom;
        candidate.coarse_score = (1.0 - candidate.anchor_alignment_cosine)
            + fit_penalty * fit_penalty
            + config.coarse_clash_weight * maximum_overlap * maximum_overlap;
    }
    let mut selected: Vec<_> = (0..candidates.len()).collect();
    selected.sort_by(|left, right| {
        candidates[*left]
            .coarse_score
            .total_cmp(&candidates[*right].coarse_score)
            .then_with(|| candidates[*left].key.cmp(&candidates[*right].key))
    });
    selected.truncate(config.coarse_keep.min(selected.len()));
    selected
}

pub(crate) fn detailed_select(
    candidates: &mut [Candidate],
    coarse_indices: &[usize],
    input: &SearchInput,
    config: &SearchConfig,
) -> Vec<usize> {
    for &candidate_index in coarse_indices {
        let candidate = &mut candidates[candidate_index];
        let mut maximum_overlap: f64 = 0.0;
        let mut minimum_gap = f64::INFINITY;
        for (position, ligand_atom) in candidate
            .coordinates_angstrom
            .iter()
            .zip(&input.ligand_atoms)
        {
            for receptor_atom in &input.receptor_atoms {
                let distance = position.minus(receptor_atom.position_angstrom).norm();
                let gap =
                    distance - ligand_atom.vdw_radius_angstrom - receptor_atom.vdw_radius_angstrom;
                minimum_gap = minimum_gap.min(gap);
                maximum_overlap = maximum_overlap.max((-gap).max(0.0));
            }
        }
        candidate.minimum_receptor_gap_angstrom = if minimum_gap.is_finite() {
            Some(minimum_gap)
        } else {
            None
        };
        let fit_penalty =
            candidate.anchor_fit_rmsd_angstrom / config.dual_anchor_distance_tolerance_angstrom;
        candidate.detailed_score = (1.0 - candidate.anchor_alignment_cosine)
            + fit_penalty * fit_penalty
            + config.coarse_clash_weight * maximum_overlap * maximum_overlap;
    }
    let mut selected = coarse_indices.to_vec();
    selected.sort_by(|left, right| {
        candidates[*left]
            .detailed_score
            .total_cmp(&candidates[*right].detailed_score)
            .then_with(|| {
                candidates[*left]
                    .coarse_score
                    .total_cmp(&candidates[*right].coarse_score)
            })
            .then_with(|| candidates[*left].key.cmp(&candidates[*right].key))
    });
    selected.truncate(config.refinement_keep.min(selected.len()));
    selected
}

fn bounding_overlap(center: crate::Vec3, ligand_extent: f64, atom: &ReceptorAtom) -> f64 {
    let gap =
        center.minus(atom.position_angstrom).norm() - ligand_extent - atom.vdw_radius_angstrom;
    (-gap).max(0.0)
}
