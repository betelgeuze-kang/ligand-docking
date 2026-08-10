use crate::anchors::{ligand_anchor_position, surface_target, AnchorCombination, AnchorPair};
use crate::model::{CandidateKey, PlacementMode, SearchConfig, SearchInput};
use crate::{Orientation, Quaternion, SearchError, SearchErrorCode, Vec3};

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Candidate {
    pub slot_index: usize,
    pub key: CandidateKey,
    pub placement_mode: PlacementMode,
    pub coordinates_angstrom: Vec<Vec3>,
    pub anchor_alignment_cosine: f64,
    pub anchor_fit_rmsd_angstrom: f64,
    pub coarse_score: f64,
    pub detailed_score: f64,
    pub energy_kcal_per_mol: f64,
    pub minimum_receptor_gap_angstrom: Option<f64>,
}

pub(crate) fn place_candidates(
    input: &SearchInput,
    config: &SearchConfig,
    orientation_values: &[Orientation],
    combinations: &[AnchorCombination],
    placement_mode: PlacementMode,
) -> Result<Vec<Candidate>, SearchError> {
    let full_grid_count = orientation_values
        .len()
        .checked_mul(combinations.len())
        .ok_or_else(|| {
            SearchError::new(
                SearchErrorCode::AllocationOverflow,
                "candidate slot count overflowed",
            )
        })?;
    let allocated_count = config.generated_candidate_limit.min(full_grid_count);
    let mut candidates = Vec::with_capacity(allocated_count);
    for slot_index in 0..allocated_count {
        // A deterministic diagonal grid traversal. For every fixed orientation,
        // epoch 0..C visits every combination exactly once, so the full sequence
        // is a bijection. Every first O-slot block covers all orientations while
        // spreading those rows across the combination axis.
        let orientation_index = slot_index % orientation_values.len();
        let epoch = slot_index / orientation_values.len();
        let combination_index =
            ((orientation_index * combinations.len()) / orientation_values.len() + epoch)
                % combinations.len();
        let orientation = &orientation_values[orientation_index];
        let combination = &combinations[combination_index];
        let (rotation, translation, fit_rmsd) = if let Some(secondary) = combination.secondary {
            dual_transform(
                input,
                config,
                orientation.quaternion,
                combination.primary,
                secondary,
            )?
        } else {
            single_transform(input, config, orientation.quaternion, combination.primary)
        };
        let coordinates = input
            .ligand_atoms
            .iter()
            .map(|atom| rotation.rotate(atom.position_angstrom).plus(translation))
            .collect();
        let alignment =
            anchor_alignment(input, rotation, combination.primary, combination.secondary)?;
        let primary_anchor = input.ligand_anchors[combination.primary.ligand_anchor_index];
        let primary_surface = input.surface_samples[combination.primary.surface_index];
        let secondary_anchor = combination
            .secondary
            .map(|pair| input.ligand_anchors[pair.ligand_anchor_index]);
        let secondary_surface = combination
            .secondary
            .map(|pair| input.surface_samples[pair.surface_index]);
        candidates.push(Candidate {
            slot_index,
            key: CandidateKey {
                orientation_index: orientation.orientation_index,
                primary_surface_id: primary_surface.id,
                primary_ligand_anchor_id: primary_anchor.id,
                secondary_surface_id: secondary_surface.map(|surface| surface.id),
                secondary_ligand_anchor_id: secondary_anchor.map(|anchor| anchor.id),
            },
            placement_mode,
            coordinates_angstrom: coordinates,
            anchor_alignment_cosine: alignment,
            anchor_fit_rmsd_angstrom: fit_rmsd,
            coarse_score: f64::INFINITY,
            detailed_score: f64::INFINITY,
            energy_kcal_per_mol: f64::INFINITY,
            minimum_receptor_gap_angstrom: None,
        });
    }
    Ok(candidates)
}

fn single_transform(
    input: &SearchInput,
    config: &SearchConfig,
    rotation: Quaternion,
    pair: AnchorPair,
) -> (Quaternion, Vec3, f64) {
    let source = ligand_anchor_position(input, pair);
    let target = surface_target(input, config, pair);
    let translation = target.minus(rotation.rotate(source));
    (rotation, translation, 0.0)
}

fn dual_transform(
    input: &SearchInput,
    config: &SearchConfig,
    low_discrepancy_rotation: Quaternion,
    primary: AnchorPair,
    secondary: AnchorPair,
) -> Result<(Quaternion, Vec3, f64), SearchError> {
    let source_primary = ligand_anchor_position(input, primary);
    let source_secondary = ligand_anchor_position(input, secondary);
    let target_primary = surface_target(input, config, primary);
    let target_secondary = surface_target(input, config, secondary);
    let source_delta = source_secondary.minus(source_primary);
    let target_delta = target_secondary.minus(target_primary);
    let correction =
        Quaternion::between(low_discrepancy_rotation.rotate(source_delta), target_delta)?;
    let rotation = correction.multiply(low_discrepancy_rotation)?;
    let primary_translation = target_primary.minus(rotation.rotate(source_primary));
    let secondary_translation = target_secondary.minus(rotation.rotate(source_secondary));
    let translation = primary_translation.plus(secondary_translation).scale(0.5);
    let primary_residual = rotation
        .rotate(source_primary)
        .plus(translation)
        .minus(target_primary)
        .norm();
    let secondary_residual = rotation
        .rotate(source_secondary)
        .plus(translation)
        .minus(target_secondary)
        .norm();
    let fit_rmsd =
        ((primary_residual * primary_residual + secondary_residual * secondary_residual) * 0.5)
            .sqrt();
    Ok((rotation, translation, fit_rmsd))
}

fn anchor_alignment(
    input: &SearchInput,
    rotation: Quaternion,
    primary: AnchorPair,
    secondary: Option<AnchorPair>,
) -> Result<f64, SearchError> {
    let mut total = pair_alignment(input, rotation, primary)?;
    let mut count = 1.0;
    if let Some(pair) = secondary {
        total += pair_alignment(input, rotation, pair)?;
        count += 1.0;
    }
    Ok((total / count).clamp(-1.0, 1.0))
}

fn pair_alignment(
    input: &SearchInput,
    rotation: Quaternion,
    pair: AnchorPair,
) -> Result<f64, SearchError> {
    let anchor = input.ligand_anchors[pair.ligand_anchor_index];
    let surface = input.surface_samples[pair.surface_index];
    let anchor_direction = anchor.direction.normalized("ligand anchor direction")?;
    let normal = surface
        .outward_normal
        .normalized("surface outward normal")?;
    Ok(rotation
        .rotate(anchor_direction)
        .dot(normal.scale(-1.0))
        .clamp(-1.0, 1.0))
}
