use betelgeuze_docking_search::Vec3;

use super::{Error, ErrorCode, PositionSoa, Result};

pub(super) fn position_soa_to_vec3(coordinates: PositionSoa<'_>) -> Vec<Vec3> {
    coordinates
        .x_angstrom
        .iter()
        .zip(coordinates.y_angstrom)
        .zip(coordinates.z_angstrom)
        .map(|((x, y), z)| Vec3::new(*x, *y, *z))
        .collect()
}

pub(super) fn coordinate_segment_matches(
    channels: &[&[f64]],
    slot: usize,
    ligand_atom_count: u64,
    require_zero: bool,
) -> Result<bool> {
    let ligand_count = usize::try_from(ligand_atom_count).map_err(|_| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 ligand denominator does not fit usize",
        )
    })?;
    let begin = slot.checked_mul(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 coordinate segment offset overflowed",
        )
    })?;
    let end = begin.checked_add(ligand_count).ok_or_else(|| {
        Error::local(
            ErrorCode::AbiMismatch,
            "native fixed64 coordinate segment end overflowed",
        )
    })?;
    for channel in channels {
        let segment = channel.get(begin..end).ok_or_else(|| {
            Error::local(
                ErrorCode::AbiMismatch,
                "native fixed64 coordinate segment exceeds its owned buffer",
            )
        })?;
        if segment.iter().any(|value| {
            if require_zero {
                *value != 0.0
            } else {
                !value.is_finite()
            }
        }) {
            return Ok(false);
        }
    }
    Ok(true)
}

pub(super) fn unit_quaternion(values: [f64; 4]) -> bool {
    if values.iter().any(|value| !value.is_finite()) {
        return false;
    }
    let norm = values[0].hypot(values[1]).hypot(values[2].hypot(values[3]));
    norm.is_finite() && (norm - 1.0).abs() <= 1.0e-8
}

pub(super) fn coordinate_segment<'a>(
    channels: [&'a [f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> Option<PositionSoa<'a>> {
    let begin = slot.checked_mul(ligand_count)?;
    let end = begin.checked_add(ligand_count)?;
    Some(PositionSoa::new(
        channels[0].get(begin..end)?,
        channels[1].get(begin..end)?,
        channels[2].get(begin..end)?,
    ))
}

pub(super) fn coordinate_segments_equal(
    left: [&[f64]; 3],
    right: [&[f64]; 3],
    slot: usize,
    ligand_count: usize,
) -> bool {
    let Some(left) = coordinate_segment(left, slot, ligand_count) else {
        return false;
    };
    let Some(right) = coordinate_segment(right, slot, ligand_count) else {
        return false;
    };
    [
        (left.x_angstrom, right.x_angstrom),
        (left.y_angstrom, right.y_angstrom),
        (left.z_angstrom, right.z_angstrom),
    ]
    .iter()
    .all(|(left, right)| {
        left.iter()
            .zip(*right)
            .all(|(left, right)| left.to_bits() == right.to_bits())
    })
}

pub(super) fn scalar_segments_equal(
    left: &[f64],
    right: &[f64],
    slot: usize,
    count: usize,
) -> bool {
    let Some(begin) = slot.checked_mul(count) else {
        return false;
    };
    let Some(end) = begin.checked_add(count) else {
        return false;
    };
    let (Some(left), Some(right)) = (left.get(begin..end), right.get(begin..end)) else {
        return false;
    };
    left.iter()
        .zip(right)
        .all(|(left, right)| left.to_bits() == right.to_bits())
}
