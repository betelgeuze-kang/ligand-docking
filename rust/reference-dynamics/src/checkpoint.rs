use crate::model::{DynamicsError, DynamicsErrorCode, State, System};

const MAGIC: &[u8; 8] = b"BGDYNCP1";
const VERSION: u32 = 1;
const FIXED_PREFIX_BYTES: usize = 64;
const DIGEST_BYTES: usize = 32;
const BYTES_PER_PARTICLE: usize = 48;

const SHA256_INITIAL: [u32; 8] = [
    0x6A09_E667,
    0xBB67_AE85,
    0x3C6E_F372,
    0xA54F_F53A,
    0x510E_527F,
    0x9B05_688C,
    0x1F83_D9AB,
    0x5BE0_CD19,
];

const SHA256_K: [u32; 64] = [
    0x428A_2F98,
    0x7137_4491,
    0xB5C0_FBCF,
    0xE9B5_DBA5,
    0x3956_C25B,
    0x59F1_11F1,
    0x923F_82A4,
    0xAB1C_5ED5,
    0xD807_AA98,
    0x1283_5B01,
    0x2431_85BE,
    0x550C_7DC3,
    0x72BE_5D74,
    0x80DE_B1FE,
    0x9BDC_06A7,
    0xC19B_F174,
    0xE49B_69C1,
    0xEFBE_4786,
    0x0FC1_9DC6,
    0x240C_A1CC,
    0x2DE9_2C6F,
    0x4A74_84AA,
    0x5CB0_A9DC,
    0x76F9_88DA,
    0x983E_5152,
    0xA831_C66D,
    0xB003_27C8,
    0xBF59_7FC7,
    0xC6E0_0BF3,
    0xD5A7_9147,
    0x06CA_6351,
    0x1429_2967,
    0x27B7_0A85,
    0x2E1B_2138,
    0x4D2C_6DFC,
    0x5338_0D13,
    0x650A_7354,
    0x766A_0ABB,
    0x81C2_C92E,
    0x9272_2C85,
    0xA2BF_E8A1,
    0xA81A_664B,
    0xC24B_8B70,
    0xC76C_51A3,
    0xD192_E819,
    0xD699_0624,
    0xF40E_3585,
    0x106A_A070,
    0x19A4_C116,
    0x1E37_6C08,
    0x2748_774C,
    0x34B0_BCB5,
    0x391C_0CB3,
    0x4ED8_AA4A,
    0x5B9C_CA4F,
    0x682E_6FF3,
    0x748F_82EE,
    0x78A5_636F,
    0x84C8_7814,
    0x8CC7_0208,
    0x90BE_FFFA,
    0xA450_6CEB,
    0xBEF9_A3F7,
    0xC671_78F2,
];

fn sha256(input: &[u8]) -> [u8; 32] {
    let bit_length = (input.len() as u64).wrapping_mul(8);
    let block_count = (input.len() + 9).div_ceil(64);
    let mut padded = vec![0_u8; block_count * 64];
    padded[..input.len()].copy_from_slice(input);
    padded[input.len()] = 0x80;
    let tail = padded.len() - 8;
    padded[tail..].copy_from_slice(&bit_length.to_be_bytes());

    let mut state = SHA256_INITIAL;
    for block in padded.chunks_exact(64) {
        let mut schedule = [0_u32; 64];
        for index in 0..16 {
            schedule[index] = u32::from_be_bytes([
                block[index * 4],
                block[index * 4 + 1],
                block[index * 4 + 2],
                block[index * 4 + 3],
            ]);
        }
        for index in 16..64 {
            let s0 = schedule[index - 15].rotate_right(7)
                ^ schedule[index - 15].rotate_right(18)
                ^ (schedule[index - 15] >> 3);
            let s1 = schedule[index - 2].rotate_right(17)
                ^ schedule[index - 2].rotate_right(19)
                ^ (schedule[index - 2] >> 10);
            schedule[index] = schedule[index - 16]
                .wrapping_add(s0)
                .wrapping_add(schedule[index - 7])
                .wrapping_add(s1);
        }

        let mut a = state[0];
        let mut b = state[1];
        let mut c = state[2];
        let mut d = state[3];
        let mut e = state[4];
        let mut f = state[5];
        let mut g = state[6];
        let mut h = state[7];
        for index in 0..64 {
            let big_sigma_1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let choose = (e & f) ^ ((!e) & g);
            let temporary_1 = h
                .wrapping_add(big_sigma_1)
                .wrapping_add(choose)
                .wrapping_add(SHA256_K[index])
                .wrapping_add(schedule[index]);
            let big_sigma_0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let majority = (a & b) ^ (a & c) ^ (b & c);
            let temporary_2 = big_sigma_0.wrapping_add(majority);
            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temporary_1);
            d = c;
            c = b;
            b = a;
            a = temporary_1.wrapping_add(temporary_2);
        }
        state[0] = state[0].wrapping_add(a);
        state[1] = state[1].wrapping_add(b);
        state[2] = state[2].wrapping_add(c);
        state[3] = state[3].wrapping_add(d);
        state[4] = state[4].wrapping_add(e);
        state[5] = state[5].wrapping_add(f);
        state[6] = state[6].wrapping_add(g);
        state[7] = state[7].wrapping_add(h);
    }

    let mut digest = [0_u8; 32];
    for (index, word) in state.iter().copied().enumerate() {
        digest[index * 4..index * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    digest
}

fn append_u64(bytes: &mut Vec<u8>, value: u64) {
    bytes.extend_from_slice(&value.to_le_bytes());
}

fn append_f64(bytes: &mut Vec<u8>, value: f64) {
    bytes.extend_from_slice(&value.to_bits().to_le_bytes());
}

fn system_fingerprint(system: &System) -> Result<[u8; 32], DynamicsError> {
    let particle_count = u64::try_from(system.particle_count()).map_err(|_| {
        DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            "particle count cannot be represented in a checkpoint",
        )
    })?;
    let constraint_count = u64::try_from(system.constraints().len()).map_err(|_| {
        DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            "constraint count cannot be represented in a checkpoint",
        )
    })?;
    let mut canonical = b"betelgeuze.reference_dynamics.system/1\0".to_vec();
    append_u64(&mut canonical, particle_count);
    for mass in system.masses_dalton() {
        append_f64(&mut canonical, *mass);
    }
    append_u64(&mut canonical, constraint_count);
    for constraint in system.constraints() {
        append_u64(
            &mut canonical,
            u64::try_from(constraint.atom_i).map_err(|_| {
                DynamicsError::new(
                    DynamicsErrorCode::CheckpointMalformed,
                    "constraint index cannot be represented in a checkpoint",
                )
            })?,
        );
        append_u64(
            &mut canonical,
            u64::try_from(constraint.atom_j).map_err(|_| {
                DynamicsError::new(
                    DynamicsErrorCode::CheckpointMalformed,
                    "constraint index cannot be represented in a checkpoint",
                )
            })?,
        );
        append_f64(&mut canonical, constraint.distance_angstrom);
    }
    match system.cell() {
        None => canonical.push(0),
        Some(cell) => {
            canonical.push(1);
            for length in cell.lengths_angstrom {
                append_f64(&mut canonical, length);
            }
            for periodic in cell.periodic_axes {
                canonical.push(u8::from(periodic));
            }
        }
    }
    Ok(sha256(&canonical))
}

fn encoded_length(particle_count: usize) -> Result<usize, DynamicsError> {
    particle_count
        .checked_mul(BYTES_PER_PARTICLE)
        .and_then(|payload| FIXED_PREFIX_BYTES.checked_add(payload))
        .and_then(|without_digest| without_digest.checked_add(DIGEST_BYTES))
        .ok_or_else(|| {
            DynamicsError::new(
                DynamicsErrorCode::CheckpointMalformed,
                "checkpoint length overflowed",
            )
        })
}

/// Encode state as canonical little-endian bytes with topology and payload digests.
pub fn encode_checkpoint(system: &System, state: &State) -> Result<Vec<u8>, DynamicsError> {
    system.validate_state(state)?;
    let expected_length = encoded_length(system.particle_count())?;
    let mut bytes = Vec::with_capacity(expected_length);
    bytes.extend_from_slice(MAGIC);
    bytes.extend_from_slice(&VERSION.to_le_bytes());
    bytes.extend_from_slice(&0_u32.to_le_bytes());
    append_u64(
        &mut bytes,
        u64::try_from(system.particle_count()).map_err(|_| {
            DynamicsError::new(
                DynamicsErrorCode::CheckpointMalformed,
                "particle count cannot be represented in a checkpoint",
            )
        })?,
    );
    append_u64(&mut bytes, state.absolute_step);
    bytes.extend_from_slice(&system_fingerprint(system)?);
    debug_assert_eq!(bytes.len(), FIXED_PREFIX_BYTES);
    for position in &state.positions_angstrom {
        for component in position {
            append_f64(&mut bytes, *component);
        }
    }
    for velocity in &state.velocities_angstrom_per_fs {
        for component in velocity {
            append_f64(&mut bytes, *component);
        }
    }
    let digest = sha256(&bytes);
    bytes.extend_from_slice(&digest);
    debug_assert_eq!(bytes.len(), expected_length);
    Ok(bytes)
}

fn read_u32(bytes: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ])
}

fn read_u64(bytes: &[u8], offset: usize) -> u64 {
    u64::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
        bytes[offset + 5],
        bytes[offset + 6],
        bytes[offset + 7],
    ])
}

fn read_f64(bytes: &[u8], offset: &mut usize) -> f64 {
    let value = f64::from_bits(read_u64(bytes, *offset));
    *offset += 8;
    value
}

/// Decode and integrity-check canonical checkpoint bytes for exactly `system`.
pub fn decode_checkpoint(system: &System, bytes: &[u8]) -> Result<State, DynamicsError> {
    if bytes.len() < FIXED_PREFIX_BYTES + DIGEST_BYTES {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            "checkpoint is shorter than the fixed header and digest",
        ));
    }
    if &bytes[..8] != MAGIC {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            "checkpoint magic does not match",
        ));
    }
    if read_u32(bytes, 8) != VERSION {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointVersion,
            "checkpoint schema version is unsupported",
        ));
    }
    if read_u32(bytes, 12) != 0 {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            "checkpoint reserved flags must be zero",
        ));
    }
    let encoded_particles = read_u64(bytes, 16);
    let system_particles = u64::try_from(system.particle_count()).map_err(|_| {
        DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            "system particle count cannot be represented in a checkpoint",
        )
    })?;
    if encoded_particles != system_particles {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointSystemMismatch,
            "checkpoint particle count does not match the system",
        ));
    }
    let expected_length = encoded_length(system.particle_count())?;
    if bytes.len() != expected_length {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointMalformed,
            format!(
                "checkpoint has {} bytes but canonical length is {expected_length}",
                bytes.len()
            ),
        ));
    }
    let payload_end = bytes.len() - DIGEST_BYTES;
    if sha256(&bytes[..payload_end]) != bytes[payload_end..] {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointChecksum,
            "checkpoint payload digest does not match",
        ));
    }
    if system_fingerprint(system)? != bytes[32..64] {
        return Err(DynamicsError::new(
            DynamicsErrorCode::CheckpointSystemMismatch,
            "checkpoint topology fingerprint does not match the system",
        ));
    }

    let mut offset = FIXED_PREFIX_BYTES;
    let mut positions = vec![[0.0; 3]; system.particle_count()];
    let mut velocities = vec![[0.0; 3]; system.particle_count()];
    for position in &mut positions {
        for component in position {
            *component = read_f64(bytes, &mut offset);
        }
    }
    for velocity in &mut velocities {
        for component in velocity {
            *component = read_f64(bytes, &mut offset);
        }
    }
    debug_assert_eq!(offset, payload_end);
    let state = State {
        positions_angstrom: positions,
        velocities_angstrom_per_fs: velocities,
        absolute_step: read_u64(bytes, 24),
    };
    system.validate_state(&state)?;
    Ok(state)
}

#[cfg(test)]
mod tests {
    use super::sha256;

    #[test]
    fn sha256_abc_vector_is_frozen() {
        assert_eq!(
            sha256(b"abc"),
            [
                0xBA, 0x78, 0x16, 0xBF, 0x8F, 0x01, 0xCF, 0xEA, 0x41, 0x41, 0x40, 0xDE, 0x5D, 0xAE,
                0x22, 0x23, 0xB0, 0x03, 0x61, 0xA3, 0x96, 0x17, 0x7A, 0x9C, 0xB4, 0x10, 0xFF, 0x61,
                0xF2, 0x00, 0x15, 0xAD,
            ]
        );
    }
}
