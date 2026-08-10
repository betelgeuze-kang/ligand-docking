use crate::geometry::GEOMETRY_EPSILON;
use crate::model::MAX_ORIENTATIONS;
use crate::{Quaternion, SearchError, SearchErrorCode};

const LOW_DISCREPANCY_BASES: [u32; 3] = [2, 3, 5];
const GEODESIC_DUPLICATE_TOLERANCE_RADIANS: f64 = 1.0e-10;
const MAX_ATTEMPTS_PER_ORIENTATION: usize = 1_024;
const TWO_POW_64: f64 = 18_446_744_073_709_551_616.0;

/// One accepted item in the deterministic low-discrepancy SO(3) prefix.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Orientation {
    pub orientation_index: u32,
    pub raw_sequence_index: u64,
    pub quaternion: Quaternion,
}

/// Generate a canonical, geodesically de-duplicated Shoemake SO(3) sequence.
///
/// Halton bases 2/3/5 and seed-derived Cranley-Patterson shifts make every
/// shorter request an exact prefix of every longer request with the same seed.
pub fn orientations(seed: [u8; 32], count: usize) -> Result<Vec<Orientation>, SearchError> {
    if count == 0 || count > MAX_ORIENTATIONS {
        return Err(SearchError::new(
            SearchErrorCode::InvalidConfiguration,
            format!("orientation_count must be within [1, {MAX_ORIENTATIONS}]"),
        ));
    }
    let offsets = seed_offsets(seed);
    let maximum_attempts = count
        .checked_mul(MAX_ATTEMPTS_PER_ORIENTATION)
        .ok_or_else(|| {
            SearchError::new(
                SearchErrorCode::AllocationOverflow,
                "orientation attempt count overflowed",
            )
        })?;
    let mut accepted = Vec::with_capacity(count);
    for raw_index in 0..maximum_attempts {
        let quaternion = low_discrepancy_quaternion(raw_index as u64, offsets)?;
        if accepted.iter().any(|existing: &Orientation| {
            quaternion_geodesic_distance(quaternion, existing.quaternion)
                <= GEODESIC_DUPLICATE_TOLERANCE_RADIANS
        }) {
            continue;
        }
        accepted.push(Orientation {
            orientation_index: u32::try_from(accepted.len()).expect("orientation cap fits u32"),
            raw_sequence_index: raw_index as u64,
            quaternion,
        });
        if accepted.len() == count {
            return Ok(accepted);
        }
    }
    Err(SearchError::new(
        SearchErrorCode::InternalInvariant,
        "low-discrepancy sequence exhausted before reaching the requested unique prefix",
    ))
}

fn radical_inverse(mut index: u64, base: u32) -> f64 {
    let inverse_base = 1.0 / f64::from(base);
    let mut fraction = inverse_base;
    let mut value = 0.0;
    let base_u64 = u64::from(base);
    while index != 0 {
        let digit = index % base_u64;
        index /= base_u64;
        value += digit as f64 * fraction;
        fraction *= inverse_base;
    }
    value
}

fn seed_offsets(seed: [u8; 32]) -> [f64; 3] {
    let mut result = [0.0; 3];
    for (index, chunk) in seed[..24].chunks_exact(8).enumerate() {
        let bytes: [u8; 8] = chunk.try_into().expect("chunks_exact yields eight bytes");
        result[index] = u64::from_be_bytes(bytes) as f64 / TWO_POW_64;
    }
    result
}

fn low_discrepancy_quaternion(
    raw_index: u64,
    offsets: [f64; 3],
) -> Result<Quaternion, SearchError> {
    let unit = core::array::from_fn::<_, 3, _>(|index| {
        (radical_inverse(raw_index, LOW_DISCREPANCY_BASES[index]) + offsets[index]).fract()
    });
    let first_radius = (1.0 - unit[0]).max(0.0).sqrt();
    let second_radius = unit[0].max(0.0).sqrt();
    let first_angle = 2.0 * core::f64::consts::PI * unit[1];
    let second_angle = 2.0 * core::f64::consts::PI * unit[2];
    Quaternion::new(
        first_radius * first_angle.sin(),
        first_radius * first_angle.cos(),
        second_radius * second_angle.sin(),
        second_radius * second_angle.cos(),
    )
    .canonicalized()
}

fn quaternion_geodesic_distance(left: Quaternion, right: Quaternion) -> f64 {
    let dot = left.x * right.x + left.y * right.y + left.z * right.z + left.w * right.w;
    let sign = if dot < 0.0 { -1.0 } else { 1.0 };
    let dx = left.x - sign * right.x;
    let dy = left.y - sign * right.y;
    let dz = left.z - sign * right.z;
    let dw = left.w - sign * right.w;
    let sx = left.x + sign * right.x;
    let sy = left.y + sign * right.y;
    let sz = left.z + sign * right.z;
    let sw = left.w + sign * right.w;
    let difference = (dx * dx + dy * dy + dz * dz + dw * dw).sqrt();
    let sum = (sx * sx + sy * sy + sz * sz + sw * sw).sqrt();
    if difference <= GEOMETRY_EPSILON && sum <= GEOMETRY_EPSILON {
        0.0
    } else {
        4.0 * difference.atan2(sum)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn radical_inverse_has_frozen_values() {
        assert_eq!(radical_inverse(0, 2), 0.0);
        assert_eq!(radical_inverse(1, 2), 0.5);
        assert_eq!(radical_inverse(2, 2), 0.25);
        assert_eq!(radical_inverse(5, 3), 0.777_777_777_777_777_7);
    }

    #[test]
    fn every_requested_count_is_an_exact_prefix() {
        let seed = [0x5a; 32];
        let complete = orientations(seed, 64).unwrap();
        for count in 1..=64 {
            assert_eq!(orientations(seed, count).unwrap(), complete[..count]);
        }
    }

    #[test]
    fn sequence_is_canonical_unit_and_geodesically_unique() {
        let observed = orientations([0xff; 32], 128).unwrap();
        for orientation in &observed {
            let q = orientation.quaternion;
            let norm = (q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w).sqrt();
            assert!((norm - 1.0).abs() < 4.0e-15);
            assert_eq!(q, q.canonicalized().unwrap());
        }
        for (index, left) in observed.iter().enumerate() {
            for right in &observed[index + 1..] {
                assert!(
                    quaternion_geodesic_distance(left.quaternion, right.quaternion)
                        > GEODESIC_DUPLICATE_TOLERANCE_RADIANS
                );
            }
        }
    }

    #[test]
    fn count_bounds_fail_closed() {
        assert_eq!(
            orientations([0; 32], 0).unwrap_err().code(),
            SearchErrorCode::InvalidConfiguration
        );
        assert_eq!(
            orientations([0; 32], MAX_ORIENTATIONS + 1)
                .unwrap_err()
                .code(),
            SearchErrorCode::InvalidConfiguration
        );
    }
}
