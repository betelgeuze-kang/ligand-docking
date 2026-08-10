use crate::model::{
    PlacementMode, SearchConfig, SearchInput, MAX_ANCHOR_COMBINATIONS,
    MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS,
};
use crate::{SearchError, SearchErrorCode};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct AnchorPair {
    pub ligand_anchor_index: usize,
    pub surface_index: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct AnchorCombination {
    pub primary: AnchorPair,
    pub secondary: Option<AnchorPair>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct CombinationSet {
    pub combinations: Vec<AnchorCombination>,
    pub compatible_single_pair_count: usize,
    pub compatible_dual_combination_count: usize,
    pub placement_mode: PlacementMode,
}

pub(crate) fn compatible_combinations(
    input: &SearchInput,
    config: &SearchConfig,
) -> Result<CombinationSet, SearchError> {
    let mut singles = Vec::new();
    for (surface_index, surface) in input.surface_samples.iter().enumerate() {
        for (ligand_anchor_index, ligand_anchor) in input.ligand_anchors.iter().enumerate() {
            if ligand_anchor.kind.is_compatible_with(surface.anchor_kind) {
                singles.push(AnchorPair {
                    ligand_anchor_index,
                    surface_index,
                });
                if singles.len() > MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS {
                    return Err(SearchError::new(
                        SearchErrorCode::TooManyItems,
                        format!(
                            "compatible single-anchor pairs exceed the cap of {MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS}"
                        ),
                    ));
                }
            }
        }
    }
    if singles.is_empty() {
        return Err(SearchError::new(
            SearchErrorCode::NoCompatibleAnchors,
            "no ligand anchor is chemically compatible with a receptor surface sample",
        ));
    }
    singles.sort_by_key(|pair| pair_key(input, *pair));
    let compatible_single_pair_count = singles.len();

    let mut duals = Vec::new();
    for (left_index, left) in singles.iter().copied().enumerate() {
        for right in singles[left_index + 1..].iter().copied() {
            if left.ligand_anchor_index == right.ligand_anchor_index
                || left.surface_index == right.surface_index
            {
                continue;
            }
            let source_distance = ligand_anchor_position(input, left)
                .minus(ligand_anchor_position(input, right))
                .norm();
            let target_distance = surface_target(input, config, left)
                .minus(surface_target(input, config, right))
                .norm();
            if source_distance <= 1.0e-12
                || target_distance <= 1.0e-12
                || (source_distance - target_distance).abs()
                    > config.dual_anchor_distance_tolerance_angstrom
            {
                continue;
            }
            let (primary, secondary) = if pair_key(input, left) < pair_key(input, right) {
                (left, right)
            } else {
                (right, left)
            };
            duals.push(AnchorCombination {
                primary,
                secondary: Some(secondary),
            });
            if duals.len() > MAX_ANCHOR_COMBINATIONS {
                return Err(SearchError::new(
                    SearchErrorCode::TooManyItems,
                    format!(
                        "compatible dual-anchor combinations exceed the cap of {MAX_ANCHOR_COMBINATIONS}"
                    ),
                ));
            }
        }
    }
    duals.sort_by_key(|combination| {
        (
            pair_key(input, combination.primary),
            pair_key(
                input,
                combination
                    .secondary
                    .expect("dual combination has secondary"),
            ),
        )
    });
    duals.dedup();
    let compatible_dual_combination_count = duals.len();
    let (combinations, placement_mode) = if duals.is_empty() {
        (
            singles
                .into_iter()
                .map(|primary| AnchorCombination {
                    primary,
                    secondary: None,
                })
                .collect(),
            PlacementMode::SingleAnchorFallback,
        )
    } else {
        (duals, PlacementMode::DualAnchor)
    };
    if combinations.len() > MAX_ANCHOR_COMBINATIONS {
        return Err(SearchError::new(
            SearchErrorCode::TooManyItems,
            format!("anchor combinations exceed the cap of {MAX_ANCHOR_COMBINATIONS}"),
        ));
    }
    Ok(CombinationSet {
        combinations,
        compatible_single_pair_count,
        compatible_dual_combination_count,
        placement_mode,
    })
}

pub(crate) fn surface_target(
    input: &SearchInput,
    config: &SearchConfig,
    pair: AnchorPair,
) -> crate::Vec3 {
    let surface = input.surface_samples[pair.surface_index];
    // Validation already canonicalizes the semantic direction; using division
    // here avoids storing a second mutable model.
    let normal = surface
        .outward_normal
        .scale(1.0 / surface.outward_normal.norm());
    surface
        .position_angstrom
        .plus(normal.scale(config.placement_clearance_angstrom))
}

pub(crate) fn ligand_anchor_position(input: &SearchInput, pair: AnchorPair) -> crate::Vec3 {
    let anchor = input.ligand_anchors[pair.ligand_anchor_index];
    input.ligand_atoms[anchor.atom_index].position_angstrom
}

fn pair_key(input: &SearchInput, pair: AnchorPair) -> (crate::SurfaceId, crate::AnchorId) {
    (
        input.surface_samples[pair.surface_index].id,
        input.ligand_anchors[pair.ligand_anchor_index].id,
    )
}
