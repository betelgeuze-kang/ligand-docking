use betelgeuze_docking_search::{
    Fixed64Allocation as IndependentFixed64Allocation,
    Fixed64AtomicFeatureEvidence as IndependentFixed64AtomicFeature,
    Fixed64ConformerSourceEvidence as IndependentFixed64ConformerSource,
    Fixed64ExactV11SourceEvidence as IndependentFixed64ExactSource,
    Fixed64FeatureGeometry as IndependentFixed64FeatureGeometry,
    Fixed64FeatureGeometryInventory as IndependentFixed64FeatureGeometryInventory,
    Fixed64FeatureInventory as IndependentFixed64FeatureInventory,
    Fixed64IndexedSourceEvidence as IndependentFixed64IndexedSource,
    Fixed64PlacementSource as IndependentFixed64PlacementSource,
    Fixed64SourceEvidence as IndependentFixed64SourceEvidence,
};
use betelgeuze_sys as sys;

use super::types::{
    Fixed64AtomicFeature, Fixed64ConformerCoordinateSource, Fixed64CoordinateSource,
    Fixed64ExactSourceEvidence, Fixed64FeatureGeometry, Fixed64IndexedCoordinateSource,
    Fixed64RefinementMode, Fixed64SourceEvidence, Sha256,
};
use super::{canonical_coordinate_sha256, digest_present, position_soa_to_vec3};
use crate::{finite, invalid, Error, ErrorCode, Result};

#[derive(Debug, Clone, Copy)]
pub struct Fixed64RunInput<'a> {
    pub exact_source_evidence: Fixed64ExactSourceEvidence,
    pub exact_source: Fixed64CoordinateSource<'a>,
    pub atomic_features: &'a [Fixed64AtomicFeature],
    pub v7_control_sources: &'a [Fixed64IndexedCoordinateSource<'a>],
    pub conformer_sources: &'a [Fixed64ConformerCoordinateSource<'a>],
    pub retained_sources: &'a [Fixed64IndexedCoordinateSource<'a>],
    pub feature_geometries: &'a [Fixed64FeatureGeometry<'a>],
    pub feature_geometry_inventory_sha256: Sha256,
    pub pocket_normal: [f64; 3],
    pub rmsd_threshold_angstrom: f64,
    pub candidate_modes: &'a [Fixed64RefinementMode],
    pub rigid_max_steps: &'a [u64],
    pub proposal_is_torsion_eligible: &'a [u8],
    pub torsion_max_steps: &'a [u64],
    pub baseline_torsion_angles_radians: &'a [f64],
    pub predeclared_refinement_policy_sha256: Sha256,
    pub predeclared_post_refinement_admission_policy_sha256: Sha256,
}

fn validate_source(
    value: Fixed64CoordinateSource<'_>,
    ligand_atom_count: usize,
    label: &str,
) -> Result<()> {
    if value.coordinates.validate()? != ligand_atom_count {
        return Err(invalid(format!(
            "{label} coordinate count must match the fixed64 ligand atom count"
        )));
    }
    for (digest, name) in [
        (value.evidence.receipt_sha256, "receipt"),
        (value.evidence.proposal_sha256, "proposal"),
        (value.evidence.coordinate_sha256, "coordinate"),
    ] {
        if !digest_present(&digest) {
            return Err(invalid(format!("{label} {name} SHA-256 is absent")));
        }
    }
    if canonical_coordinate_sha256(value.coordinates) != value.evidence.coordinate_sha256 {
        return Err(invalid(format!(
            "{label} coordinate SHA-256 does not match its supplied coordinates"
        )));
    }
    Ok(())
}

pub(super) fn validate_run_input(
    input: Fixed64RunInput<'_>,
    ligand_atom_count: usize,
    receptor_system_sha256: Sha256,
    ligand_system_sha256: Sha256,
) -> Result<()> {
    const CANDIDATE_COUNT: usize = sys::BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize;
    validate_source(input.exact_source, ligand_atom_count, "exact V1.1 source")?;
    if input.exact_source.evidence.receipt_sha256
        != input.exact_source_evidence.source_receipt_sha256
        || input.exact_source.evidence.proposal_sha256
            != input.exact_source_evidence.proposal_sha256
        || input.exact_source.evidence.coordinate_sha256
            != input.exact_source_evidence.ligand_coordinate_sha256
    {
        return Err(invalid(
            "fixed64 exact source evidence and coordinate payload are cross-wired",
        ));
    }
    for (digest, label) in [
        (
            input.exact_source_evidence.source_receipt_sha256,
            "exact source receipt",
        ),
        (
            input.exact_source_evidence.proposal_sha256,
            "exact proposal",
        ),
        (
            input.exact_source_evidence.ligand_coordinate_sha256,
            "exact ligand coordinate",
        ),
        (
            input.exact_source_evidence.receptor_coordinate_sha256,
            "exact receptor coordinate",
        ),
        (
            input.exact_source_evidence.prepared_ligand_topology_sha256,
            "prepared ligand topology",
        ),
        (
            input
                .exact_source_evidence
                .prepared_receptor_topology_sha256,
            "prepared receptor topology",
        ),
        (
            input.exact_source_evidence.ligand_vdw_radii_sha256,
            "ligand vdw radii",
        ),
        (
            input.exact_source_evidence.ligand_heavy_atom_mask_sha256,
            "ligand heavy-atom mask",
        ),
        (
            input.exact_source_evidence.receptor_vdw_radii_sha256,
            "receptor vdw radii",
        ),
        (
            input.predeclared_refinement_policy_sha256,
            "predeclared refinement policy",
        ),
        (
            input.predeclared_post_refinement_admission_policy_sha256,
            "predeclared post-refinement admission policy",
        ),
    ] {
        if !digest_present(&digest) {
            return Err(invalid(format!("fixed64 {label} SHA-256 is absent")));
        }
    }
    if input
        .exact_source_evidence
        .prepared_receptor_topology_sha256
        != receptor_system_sha256
        || input.exact_source_evidence.prepared_ligand_topology_sha256 != ligand_system_sha256
    {
        return Err(invalid(
            "fixed64 producer prepared topology identity is cross-wired",
        ));
    }
    for (source, label) in input
        .v7_control_sources
        .iter()
        .map(|source| (source.source, "V7 control source"))
        .chain(
            input
                .conformer_sources
                .iter()
                .map(|source| (source.source, "conformer source")),
        )
        .chain(
            input
                .retained_sources
                .iter()
                .map(|source| (source.source, "retained source")),
        )
    {
        validate_source(source, ligand_atom_count, label)?;
    }
    for feature in input.atomic_features {
        if !digest_present(&feature.receipt_sha256) {
            return Err(invalid("fixed64 atomic-feature receipt SHA-256 is absent"));
        }
    }
    for geometry in input.feature_geometries {
        if !digest_present(&geometry.allocation_feature_receipt_sha256)
            || !digest_present(&geometry.feature_geometry_receipt_sha256)
        {
            return Err(invalid(
                "fixed64 feature geometry receipt SHA-256 is absent",
            ));
        }
    }
    if input.feature_geometries.is_empty() {
        if digest_present(&input.feature_geometry_inventory_sha256) {
            return Err(invalid(
                "empty fixed64 feature geometry inventory must use a zero SHA-256",
            ));
        }
    } else if !digest_present(&input.feature_geometry_inventory_sha256) {
        return Err(invalid(
            "non-empty fixed64 feature geometry inventory SHA-256 is absent",
        ));
    }
    if !finite(&input.pocket_normal)
        || input
            .pocket_normal
            .iter()
            .all(|component| *component == 0.0)
        || !input.rmsd_threshold_angstrom.is_finite()
        || input.rmsd_threshold_angstrom <= 0.0
    {
        return Err(invalid(
            "fixed64 pocket normal and RMSD threshold must be finite and non-zero",
        ));
    }
    for (length, label) in [
        (input.candidate_modes.len(), "candidate modes"),
        (input.rigid_max_steps.len(), "rigid step budgets"),
        (
            input.proposal_is_torsion_eligible.len(),
            "torsion eligibility",
        ),
        (input.torsion_max_steps.len(), "torsion step budgets"),
    ] {
        if length != CANDIDATE_COUNT {
            return Err(invalid(format!(
                "fixed64 {label} must contain exactly {CANDIDATE_COUNT} values"
            )));
        }
    }
    if input
        .proposal_is_torsion_eligible
        .iter()
        .any(|value| *value > 1)
    {
        return Err(invalid(
            "fixed64 torsion eligibility must contain only 0 or 1",
        ));
    }
    let coordinate_count = ligand_atom_count
        .checked_mul(CANDIDATE_COUNT)
        .ok_or_else(|| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "fixed64 baseline torsion coordinate denominator overflows usize",
            )
        })?;
    if input.baseline_torsion_angles_radians.len() != coordinate_count
        || !finite(input.baseline_torsion_angles_radians)
    {
        return Err(invalid(
            "fixed64 baseline torsion angles must be finite and match 64 × ligand atoms",
        ));
    }
    Ok(())
}

const fn independent_source_evidence(
    value: Fixed64SourceEvidence,
) -> IndependentFixed64SourceEvidence {
    IndependentFixed64SourceEvidence {
        receipt_sha256: value.receipt_sha256,
        proposal_sha256: value.proposal_sha256,
        coordinate_sha256: value.coordinate_sha256,
    }
}

pub(super) fn independent_allocation(
    input: Fixed64RunInput<'_>,
) -> Result<IndependentFixed64Allocation> {
    let exact = input.exact_source_evidence;
    let inventory = IndependentFixed64FeatureInventory::new(
        IndependentFixed64ExactSource {
            source_receipt_sha256: exact.source_receipt_sha256,
            proposal_sha256: exact.proposal_sha256,
            ligand_coordinate_sha256: exact.ligand_coordinate_sha256,
            receptor_coordinate_sha256: exact.receptor_coordinate_sha256,
            prepared_ligand_topology_sha256: exact.prepared_ligand_topology_sha256,
            prepared_receptor_topology_sha256: exact.prepared_receptor_topology_sha256,
            ligand_vdw_radii_sha256: exact.ligand_vdw_radii_sha256,
            ligand_heavy_atom_mask_sha256: exact.ligand_heavy_atom_mask_sha256,
            receptor_vdw_radii_sha256: exact.receptor_vdw_radii_sha256,
        },
        input
            .atomic_features
            .iter()
            .map(|feature| IndependentFixed64AtomicFeature {
                kind: feature.kind.as_independent(),
                receipt_sha256: feature.receipt_sha256,
            })
            .collect(),
        input
            .v7_control_sources
            .iter()
            .map(|source| IndependentFixed64IndexedSource {
                source_index: source.source_index,
                source: independent_source_evidence(source.source.evidence),
            })
            .collect(),
        input
            .conformer_sources
            .iter()
            .map(|source| IndependentFixed64ConformerSource {
                rank: source.rank,
                source: independent_source_evidence(source.source.evidence),
            })
            .collect(),
        input
            .retained_sources
            .iter()
            .map(|source| IndependentFixed64IndexedSource {
                source_index: source.source_index,
                source: independent_source_evidence(source.source.evidence),
            })
            .collect(),
    )
    .map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 allocation rejected safe input: {error}"),
        )
    })?;
    IndependentFixed64Allocation::build(inventory).map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 allocation derivation failed: {error}"),
        )
    })
}

pub(super) fn independent_feature_geometry_inventory(
    input: Fixed64RunInput<'_>,
) -> Result<Option<IndependentFixed64FeatureGeometryInventory>> {
    if input.feature_geometries.is_empty() {
        return Ok(None);
    }
    let mut features = Vec::with_capacity(input.feature_geometries.len());
    for geometry in input.feature_geometries {
        let atom_indices = geometry
            .atom_indices
            .iter()
            .copied()
            .map(|index| {
                usize::try_from(index).map_err(|_| {
                    Error::local(
                        ErrorCode::CapacityOverflow,
                        "fixed64 feature-geometry atom index does not fit usize",
                    )
                })
            })
            .collect::<Result<Vec<_>>>()?;
        let feature = IndependentFixed64FeatureGeometry::new(
            geometry.kind.as_independent(),
            geometry.allocation_feature_receipt_sha256,
            atom_indices,
        )
        .map_err(|error| {
            Error::local(
                ErrorCode::AbiMismatch,
                format!("independent fixed64 feature geometry rejected safe input: {error}"),
            )
        })?;
        if feature.receipt_sha256() != geometry.feature_geometry_receipt_sha256 {
            return Err(Error::local(
                ErrorCode::AbiMismatch,
                "fixed64 feature-geometry receipt was not independently rederived",
            ));
        }
        features.push(feature);
    }
    let inventory = IndependentFixed64FeatureGeometryInventory::new(features).map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 feature inventory rejected safe input: {error}"),
        )
    })?;
    if inventory.receipt_sha256() != input.feature_geometry_inventory_sha256 {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "fixed64 feature-geometry inventory receipt was not independently rederived",
        ));
    }
    Ok(Some(inventory))
}

pub(super) fn independent_placement_source(
    source: Fixed64CoordinateSource<'_>,
) -> Result<IndependentFixed64PlacementSource> {
    IndependentFixed64PlacementSource::new(
        independent_source_evidence(source.evidence),
        position_soa_to_vec3(source.coordinates),
    )
    .map_err(|error| {
        Error::local(
            ErrorCode::AbiMismatch,
            format!("independent fixed64 placement source rejected safe input: {error}"),
        )
    })
}
