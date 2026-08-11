use std::fmt;

use crate::{Vec3, FIXED64_CANDIDATE_COUNT, NATIVE_FIXED64_TOP_K_LIMIT};

pub const NATIVE_FIXED64_DIRECT_RMSD_CLUSTER_ALGORITHM_ID: &str =
    "score_ordered_first_representative_direct_binary64_rmsd/1.0.0";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeFixed64RmsdClusterErrorCode {
    InvalidInput,
    UpstreamCrossWired,
    NonFiniteDerivedValue,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeFixed64RmsdClusterError {
    code: NativeFixed64RmsdClusterErrorCode,
    message: &'static str,
}

impl NativeFixed64RmsdClusterError {
    const fn new(code: NativeFixed64RmsdClusterErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeFixed64RmsdClusterErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeFixed64RmsdClusterError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "native fixed64 RMSD clustering: {}",
            self.message
        )
    }
}

impl std::error::Error for NativeFixed64RmsdClusterError {}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeFixed64RmsdClusterInputRow {
    slot_index: usize,
    eligible: bool,
    stable_valid_rank: usize,
    coordinate_sha256: Option<[u8; 32]>,
}

impl NativeFixed64RmsdClusterInputRow {
    pub fn new(
        slot_index: usize,
        eligible: bool,
        stable_valid_rank: usize,
        coordinate_sha256: Option<[u8; 32]>,
    ) -> Result<Self, NativeFixed64RmsdClusterError> {
        if slot_index >= FIXED64_CANDIDATE_COUNT {
            return Err(cross_wired("RMSD cluster slot is outside fixed64"));
        }
        if eligible {
            if !(1..=FIXED64_CANDIDATE_COUNT).contains(&stable_valid_rank)
                || coordinate_sha256.is_none_or(|digest| digest == [0; 32])
            {
                return Err(cross_wired("eligible RMSD cluster row lacks rank identity"));
            }
        } else if stable_valid_rank != 0 || coordinate_sha256.is_some() {
            return Err(cross_wired(
                "ineligible RMSD cluster row retains ranking evidence",
            ));
        }
        Ok(Self {
            slot_index,
            eligible,
            stable_valid_rank,
            coordinate_sha256,
        })
    }

    #[must_use]
    pub const fn slot_index(self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn eligible(self) -> bool {
        self.eligible
    }

    #[must_use]
    pub const fn stable_valid_rank(self) -> usize {
        self.stable_valid_rank
    }

    #[must_use]
    pub const fn coordinate_sha256(self) -> Option<[u8; 32]> {
        self.coordinate_sha256
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NativeFixed64RmsdClusterRow {
    slot_index: usize,
    eligible: bool,
    representative: bool,
    top_k_representative: bool,
    stable_valid_rank: usize,
    cluster_id: usize,
    representative_slot_index: usize,
    cluster_rank: usize,
    top_k_rank: usize,
    cluster_size: usize,
    direct_rmsd_to_representative_angstrom: f64,
    coordinate_sha256: Option<[u8; 32]>,
}

impl NativeFixed64RmsdClusterRow {
    #[must_use]
    pub const fn slot_index(self) -> usize {
        self.slot_index
    }

    #[must_use]
    pub const fn eligible(self) -> bool {
        self.eligible
    }

    #[must_use]
    pub const fn representative(self) -> bool {
        self.representative
    }

    #[must_use]
    pub const fn top_k_representative(self) -> bool {
        self.top_k_representative
    }

    #[must_use]
    pub const fn stable_valid_rank(self) -> usize {
        self.stable_valid_rank
    }

    #[must_use]
    pub const fn cluster_id(self) -> usize {
        self.cluster_id
    }

    #[must_use]
    pub const fn representative_slot_index(self) -> usize {
        self.representative_slot_index
    }

    #[must_use]
    pub const fn cluster_rank(self) -> usize {
        self.cluster_rank
    }

    #[must_use]
    pub const fn top_k_rank(self) -> usize {
        self.top_k_rank
    }

    #[must_use]
    pub const fn cluster_size(self) -> usize {
        self.cluster_size
    }

    #[must_use]
    pub const fn direct_rmsd_to_representative_angstrom(self) -> f64 {
        self.direct_rmsd_to_representative_angstrom
    }

    #[must_use]
    pub const fn coordinate_sha256(self) -> Option<[u8; 32]> {
        self.coordinate_sha256
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeFixed64RmsdClusterKernelOutcome {
    rows: [NativeFixed64RmsdClusterRow; FIXED64_CANDIDATE_COUNT],
    representative_slot_indices: [usize; FIXED64_CANDIDATE_COUNT],
    cluster_count: usize,
    top_k_slot_indices: [usize; NATIVE_FIXED64_TOP_K_LIMIT],
    top_k_count: usize,
}

impl NativeFixed64RmsdClusterKernelOutcome {
    #[must_use]
    pub const fn rows(&self) -> &[NativeFixed64RmsdClusterRow; FIXED64_CANDIDATE_COUNT] {
        &self.rows
    }

    #[must_use]
    pub fn representative_slot_indices(&self) -> &[usize] {
        &self.representative_slot_indices[..self.cluster_count]
    }

    #[must_use]
    pub const fn cluster_count(&self) -> usize {
        self.cluster_count
    }

    #[must_use]
    pub fn top_k_slot_indices(&self) -> &[usize] {
        &self.top_k_slot_indices[..self.top_k_count]
    }
}

/// Greedy score-ordered direct-coordinate RMSD clustering for exactly 64 slots.
///
/// `coordinates` is candidate-major and has exactly `64 * atom_count` rows.
/// Coordinates for ineligible slots are never interpreted. Eligible rows must
/// have contiguous stable-valid ranks, which fixes traversal before any RMSD
/// result exists. The first matching representative wins; representatives and
/// the final Top-5 therefore remain stable and result-independent.
pub fn cluster_native_fixed64_direct_rmsd_kernel(
    rows: &[NativeFixed64RmsdClusterInputRow; FIXED64_CANDIDATE_COUNT],
    coordinates: &[Vec3],
    atom_count: usize,
    rmsd_threshold_angstrom: f64,
) -> Result<NativeFixed64RmsdClusterKernelOutcome, NativeFixed64RmsdClusterError> {
    if atom_count == 0
        || coordinates.len()
            != FIXED64_CANDIDATE_COUNT
                .checked_mul(atom_count)
                .ok_or_else(|| invalid("RMSD coordinate shape overflowed"))?
        || !rmsd_threshold_angstrom.is_finite()
        || rmsd_threshold_angstrom <= 0.0
    {
        return Err(invalid("RMSD cluster input shape or threshold is invalid"));
    }
    let mut ordered_slots = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut eligible_count = 0usize;
    for (expected_slot, row) in rows.iter().copied().enumerate() {
        if row.slot_index != expected_slot {
            return Err(cross_wired("RMSD cluster slot indices are cross-wired"));
        }
        if row.eligible {
            if row.stable_valid_rank == 0
                || row.stable_valid_rank > FIXED64_CANDIDATE_COUNT
                || row.coordinate_sha256.is_none_or(|digest| digest == [0; 32])
            {
                return Err(cross_wired("eligible RMSD row evidence is invalid"));
            }
            eligible_count += 1;
        } else if row.stable_valid_rank != 0 || row.coordinate_sha256.is_some() {
            return Err(cross_wired("ineligible RMSD row retains evidence"));
        }
    }
    let mut rank_seen = [false; FIXED64_CANDIDATE_COUNT];
    for row in rows.iter().copied().filter(|row| row.eligible) {
        let offset = row.stable_valid_rank - 1;
        if rank_seen[offset] {
            return Err(cross_wired("RMSD stable-valid rank is duplicated"));
        }
        rank_seen[offset] = true;
        ordered_slots[offset] = row.slot_index;
    }
    if rank_seen[..eligible_count].iter().any(|seen| !seen)
        || rank_seen[eligible_count..].iter().any(|seen| *seen)
    {
        return Err(cross_wired("RMSD stable-valid ranks are not contiguous"));
    }
    for slot in ordered_slots[..eligible_count].iter().copied() {
        if candidate_coordinates(coordinates, atom_count, slot)
            .iter()
            .any(|coordinate| !coordinate.is_finite())
        {
            return Err(invalid("eligible RMSD coordinates are non-finite"));
        }
    }

    let empty_row = NativeFixed64RmsdClusterRow {
        slot_index: 0,
        eligible: false,
        representative: false,
        top_k_representative: false,
        stable_valid_rank: 0,
        cluster_id: 0,
        representative_slot_index: 0,
        cluster_rank: 0,
        top_k_rank: 0,
        cluster_size: 0,
        direct_rmsd_to_representative_angstrom: 0.0,
        coordinate_sha256: None,
    };
    let mut output_rows = [empty_row; FIXED64_CANDIDATE_COUNT];
    for (slot, output) in output_rows.iter_mut().enumerate() {
        output.slot_index = slot;
    }
    let mut representatives = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut cluster_sizes = [0usize; FIXED64_CANDIDATE_COUNT];
    let mut cluster_count = 0usize;
    for slot in ordered_slots[..eligible_count].iter().copied() {
        let candidate = candidate_coordinates(coordinates, atom_count, slot);
        let mut assignment = None;
        for (cluster_offset, representative_slot) in
            representatives[..cluster_count].iter().copied().enumerate()
        {
            let rmsd = direct_rmsd(
                candidate,
                candidate_coordinates(coordinates, atom_count, representative_slot),
            )?;
            if rmsd <= rmsd_threshold_angstrom {
                assignment = Some((cluster_offset, representative_slot, rmsd));
                break;
            }
        }
        let (cluster_offset, representative_slot, rmsd, representative) =
            if let Some((cluster_offset, representative_slot, rmsd)) = assignment {
                (cluster_offset, representative_slot, rmsd, false)
            } else {
                representatives[cluster_count] = slot;
                let result = (cluster_count, slot, 0.0, true);
                cluster_count += 1;
                result
            };
        cluster_sizes[cluster_offset] += 1;
        output_rows[slot] = NativeFixed64RmsdClusterRow {
            slot_index: slot,
            eligible: true,
            representative,
            top_k_representative: representative && cluster_offset < NATIVE_FIXED64_TOP_K_LIMIT,
            stable_valid_rank: rows[slot].stable_valid_rank,
            cluster_id: cluster_offset + 1,
            representative_slot_index: representative_slot,
            cluster_rank: cluster_offset + 1,
            top_k_rank: if representative && cluster_offset < NATIVE_FIXED64_TOP_K_LIMIT {
                cluster_offset + 1
            } else {
                0
            },
            cluster_size: 0,
            direct_rmsd_to_representative_angstrom: canonical_zero(rmsd),
            coordinate_sha256: rows[slot].coordinate_sha256,
        };
    }
    for row in output_rows.iter_mut().filter(|row| row.eligible) {
        row.cluster_size = cluster_sizes[row.cluster_id - 1];
    }
    let mut top_k_slots = [0usize; NATIVE_FIXED64_TOP_K_LIMIT];
    let top_k_count = cluster_count.min(NATIVE_FIXED64_TOP_K_LIMIT);
    top_k_slots[..top_k_count].copy_from_slice(&representatives[..top_k_count]);
    Ok(NativeFixed64RmsdClusterKernelOutcome {
        rows: output_rows,
        representative_slot_indices: representatives,
        cluster_count,
        top_k_slot_indices: top_k_slots,
        top_k_count,
    })
}

fn candidate_coordinates(coordinates: &[Vec3], atom_count: usize, slot: usize) -> &[Vec3] {
    let start = slot * atom_count;
    &coordinates[start..start + atom_count]
}

fn direct_rmsd(left: &[Vec3], right: &[Vec3]) -> Result<f64, NativeFixed64RmsdClusterError> {
    let mut squared_sum = 0.0;
    for (left, right) in left.iter().copied().zip(right.iter().copied()) {
        let delta = left.minus(right);
        squared_sum += delta.x * delta.x + delta.y * delta.y + delta.z * delta.z;
    }
    let rmsd = (squared_sum / left.len() as f64).sqrt();
    if !rmsd.is_finite() {
        return Err(NativeFixed64RmsdClusterError::new(
            NativeFixed64RmsdClusterErrorCode::NonFiniteDerivedValue,
            "direct RMSD overflowed",
        ));
    }
    Ok(canonical_zero(rmsd))
}

fn canonical_zero(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

const fn invalid(message: &'static str) -> NativeFixed64RmsdClusterError {
    NativeFixed64RmsdClusterError::new(NativeFixed64RmsdClusterErrorCode::InvalidInput, message)
}

const fn cross_wired(message: &'static str) -> NativeFixed64RmsdClusterError {
    NativeFixed64RmsdClusterError::new(
        NativeFixed64RmsdClusterErrorCode::UpstreamCrossWired,
        message,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (
        [NativeFixed64RmsdClusterInputRow; FIXED64_CANDIDATE_COUNT],
        Vec<Vec3>,
    ) {
        let mut rows = [NativeFixed64RmsdClusterInputRow::new(0, false, 0, None).unwrap();
            FIXED64_CANDIDATE_COUNT];
        let mut coordinates = vec![Vec3::default(); FIXED64_CANDIDATE_COUNT * 2];
        for (slot, row) in rows.iter_mut().enumerate() {
            *row = NativeFixed64RmsdClusterInputRow::new(slot, false, 0, None).unwrap();
        }
        for (rank, slot) in [3usize, 1, 4, 2].into_iter().enumerate() {
            rows[slot] = NativeFixed64RmsdClusterInputRow::new(
                slot,
                true,
                rank + 1,
                Some([u8::try_from(slot + 1).unwrap(); 32]),
            )
            .unwrap();
        }
        coordinates[3 * 2] = Vec3::new(0.0, 0.0, 0.0);
        coordinates[3 * 2 + 1] = Vec3::new(1.0, 0.0, 0.0);
        coordinates[2] = Vec3::new(0.1, 0.0, 0.0);
        coordinates[3] = Vec3::new(1.1, 0.0, 0.0);
        coordinates[4 * 2] = Vec3::new(4.0, 0.0, 0.0);
        coordinates[4 * 2 + 1] = Vec3::new(5.0, 0.0, 0.0);
        coordinates[2 * 2] = Vec3::new(4.2, 0.0, 0.0);
        coordinates[2 * 2 + 1] = Vec3::new(5.2, 0.0, 0.0);
        (rows, coordinates)
    }

    #[test]
    fn direct_rmsd_clustering_is_stable_and_preserves_all_slots() {
        let (rows, coordinates) = fixture();
        let first =
            cluster_native_fixed64_direct_rmsd_kernel(&rows, &coordinates, 2, 0.25).unwrap();
        let second =
            cluster_native_fixed64_direct_rmsd_kernel(&rows, &coordinates, 2, 0.25).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.rows().len(), 64);
        assert_eq!(first.representative_slot_indices(), &[3, 4]);
        assert_eq!(first.top_k_slot_indices(), &[3, 4]);
        assert_eq!(first.rows()[3].cluster_size(), 2);
        assert_eq!(first.rows()[1].representative_slot_index(), 3);
        assert_eq!(first.rows()[4].cluster_size(), 2);
        assert_eq!(first.rows()[2].representative_slot_index(), 4);
        assert!(!first.rows()[0].eligible());
    }

    #[test]
    fn first_matching_representative_wins_at_threshold() {
        let (mut rows, mut coordinates) = fixture();
        rows[5] = NativeFixed64RmsdClusterInputRow::new(5, true, 5, Some([6; 32])).unwrap();
        coordinates[5 * 2] = Vec3::new(0.25, 0.0, 0.0);
        coordinates[5 * 2 + 1] = Vec3::new(1.25, 0.0, 0.0);
        let outcome =
            cluster_native_fixed64_direct_rmsd_kernel(&rows, &coordinates, 2, 0.25).unwrap();
        assert_eq!(outcome.rows()[5].representative_slot_index(), 3);
        assert_eq!(outcome.rows()[5].cluster_id(), 1);
        assert_eq!(
            outcome.rows()[5].direct_rmsd_to_representative_angstrom(),
            0.25
        );
    }

    #[test]
    fn rank_cross_wiring_and_nonfinite_eligible_coordinates_fail_closed() {
        let (mut rows, mut coordinates) = fixture();
        rows[1] = NativeFixed64RmsdClusterInputRow::new(1, true, 1, Some([2; 32])).unwrap();
        let error =
            cluster_native_fixed64_direct_rmsd_kernel(&rows, &coordinates, 2, 0.25).unwrap_err();
        assert_eq!(
            error.code(),
            NativeFixed64RmsdClusterErrorCode::UpstreamCrossWired
        );

        let (rows, _) = fixture();
        coordinates[3 * 2].x = f64::NAN;
        let error =
            cluster_native_fixed64_direct_rmsd_kernel(&rows, &coordinates, 2, 0.25).unwrap_err();
        assert_eq!(
            error.code(),
            NativeFixed64RmsdClusterErrorCode::InvalidInput
        );
    }
}
