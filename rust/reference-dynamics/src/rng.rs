/// One Philox4x32 round multiplier.
const PHILOX_M0: u32 = 0xD251_1F53;
/// The other Philox4x32 round multiplier.
const PHILOX_M1: u32 = 0xCD9E_8D57;
const PHILOX_W0: u32 = 0x9E37_79B9;
const PHILOX_W1: u32 = 0xBB67_AE85;

fn multiply_high_low(left: u32, right: u32) -> (u32, u32) {
    let product = u64::from(left) * u64::from(right);
    ((product >> 32) as u32, product as u32)
}

/// Frozen Random123-compatible Philox4x32-10 counter transform.
#[must_use]
pub fn philox4x32_10(mut counter: [u32; 4], mut key: [u32; 2]) -> [u32; 4] {
    for _ in 0..10 {
        let (high_0, low_0) = multiply_high_low(PHILOX_M0, counter[0]);
        let (high_1, low_1) = multiply_high_low(PHILOX_M1, counter[2]);
        counter = [
            high_1 ^ counter[1] ^ key[0],
            low_1,
            high_0 ^ counter[3] ^ key[1],
            low_0,
        ];
        key[0] = key[0].wrapping_add(PHILOX_W0);
        key[1] = key[1].wrapping_add(PHILOX_W1);
    }
    counter
}

fn open_unit(value: u32) -> f64 {
    (f64::from(value) + 0.5) * (1.0 / 4_294_967_296.0)
}

/// Three independent standard-normal values for one atom and absolute step.
///
/// The 64-bit seed is the Philox key and `(absolute_step, atom_index)` is the
/// 128-bit counter. There is deliberately no stream cursor or cached spare.
#[must_use]
pub fn normal_triplet(seed: u64, absolute_step: u64, atom_index: u64) -> [f64; 3] {
    let counter = [
        absolute_step as u32,
        (absolute_step >> 32) as u32,
        atom_index as u32,
        (atom_index >> 32) as u32,
    ];
    let key = [seed as u32, (seed >> 32) as u32];
    let words = philox4x32_10(counter, key);
    let radius_0 = (-2.0 * open_unit(words[0]).ln()).sqrt();
    let angle_0 = core::f64::consts::TAU * open_unit(words[1]);
    let radius_1 = (-2.0 * open_unit(words[2]).ln()).sqrt();
    let angle_1 = core::f64::consts::TAU * open_unit(words[3]);
    [
        radius_0 * angle_0.cos(),
        radius_0 * angle_0.sin(),
        radius_1 * angle_1.cos(),
    ]
}

#[cfg(test)]
mod tests {
    use super::philox4x32_10;

    #[test]
    fn random123_zero_vector_is_frozen() {
        assert_eq!(
            philox4x32_10([0; 4], [0; 2]),
            [0x6627_E8D5, 0xE169_C58D, 0xBC57_AC4C, 0x9B00_DBD8]
        );
    }
}
