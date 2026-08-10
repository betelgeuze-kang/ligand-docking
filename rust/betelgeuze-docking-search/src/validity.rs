use crate::model::{CandidateReason, SearchConfig, SearchInput};
use crate::surface::Candidate;

pub(crate) fn physical_validity(
    candidate: &Candidate,
    input: &SearchInput,
    config: &SearchConfig,
) -> Result<Option<f64>, CandidateReason> {
    for coordinate in &candidate.coordinates_angstrom {
        if !coordinate.is_finite() {
            return Err(CandidateReason::NonFiniteCoordinate);
        }
        if coordinate.x.abs() > config.maximum_absolute_coordinate_angstrom
            || coordinate.y.abs() > config.maximum_absolute_coordinate_angstrom
            || coordinate.z.abs() > config.maximum_absolute_coordinate_angstrom
        {
            return Err(CandidateReason::CoordinateOutOfBounds);
        }
    }
    for left_index in 0..candidate.coordinates_angstrom.len() {
        for right_index in left_index + 1..candidate.coordinates_angstrom.len() {
            let distance = candidate.coordinates_angstrom[left_index]
                .minus(candidate.coordinates_angstrom[right_index])
                .norm();
            if distance < config.minimum_ligand_atom_distance_angstrom {
                return Err(CandidateReason::LigandSelfOverlap);
            }
        }
    }
    let mut minimum_gap = f64::INFINITY;
    for (coordinate, ligand_atom) in candidate
        .coordinates_angstrom
        .iter()
        .zip(&input.ligand_atoms)
    {
        for receptor_atom in &input.receptor_atoms {
            let distance = coordinate.minus(receptor_atom.position_angstrom).norm();
            let radii = ligand_atom.vdw_radius_angstrom + receptor_atom.vdw_radius_angstrom;
            let gap = distance - radii;
            minimum_gap = minimum_gap.min(gap);
            if distance < config.minimum_receptor_clearance_scale * radii {
                return Err(CandidateReason::ReceptorClash);
            }
        }
    }
    Ok(if minimum_gap.is_finite() {
        Some(minimum_gap)
    } else {
        None
    })
}
