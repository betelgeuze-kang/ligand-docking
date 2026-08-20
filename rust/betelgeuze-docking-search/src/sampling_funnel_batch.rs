//! Coordinate-bearing materialization of the deterministic 512-to-64 funnel.
//!
//! The selection receipt deliberately carries identities and decisions rather
//! than molecular coordinate arrays. This module binds an exact 512-row
//! coordinate payload ledger to that receipt and copies only the selected 64
//! rows into the fixed-width layout needed by downstream native pipelines.

use std::fmt;

use crate::native_hash::CanonicalHash;
use crate::{
    native_fixed64_coordinate_sha256, NativeSamplingFunnelCandidateState,
    NativeSamplingFunnelReceipt, NativeSamplingFunnelSelectedState, Quaternion, Vec3,
    FIXED64_MAX_LIGAND_ATOMS, NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR,
    NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR,
};

pub const NATIVE_SAMPLING_FUNNEL_PAYLOAD_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_sampling_funnel_payload_batch/1.0.0";
pub const NATIVE_SAMPLING_FUNNEL_PRESELECTED_BATCH_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_sampling_funnel_preselected_batch/1.0.0";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeSamplingFunnelBatchErrorCode {
    InvalidInput,
    InputCrossWired,
    CoordinateDigestMismatch,
    InternalInvariant,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeSamplingFunnelBatchError {
    code: NativeSamplingFunnelBatchErrorCode,
    message: &'static str,
}

impl NativeSamplingFunnelBatchError {
    const fn new(code: NativeSamplingFunnelBatchErrorCode, message: &'static str) -> Self {
        Self { code, message }
    }

    #[must_use]
    pub const fn code(self) -> NativeSamplingFunnelBatchErrorCode {
        self.code
    }

    #[must_use]
    pub const fn message(self) -> &'static str {
        self.message
    }
}

impl fmt::Display for NativeSamplingFunnelBatchError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "native sampling funnel batch: {}", self.message)
    }
}

impl std::error::Error for NativeSamplingFunnelBatchError {}

#[derive(Clone, Debug, PartialEq)]
pub enum NativeSamplingFunnelPayloadRowState {
    Generated {
        source_sha256: [u8; 32],
        proposal_sha256: [u8; 32],
        coordinate_sha256: [u8; 32],
        coordinates_angstrom: Box<[Vec3]>,
        source_quaternion: Quaternion,
    },
    TypedFailure,
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeSamplingFunnelPayloadRow {
    pool_index: usize,
    state: NativeSamplingFunnelPayloadRowState,
}

impl NativeSamplingFunnelPayloadRow {
    pub fn generated(
        pool_index: usize,
        source_sha256: [u8; 32],
        proposal_sha256: [u8; 32],
        coordinates_angstrom: Vec<Vec3>,
        source_quaternion: Quaternion,
    ) -> Result<Self, NativeSamplingFunnelBatchError> {
        if pool_index >= NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR
            || digest_is_zero(source_sha256)
            || digest_is_zero(proposal_sha256)
            || coordinates_angstrom.is_empty()
            || coordinates_angstrom.len() > FIXED64_MAX_LIGAND_ATOMS
        {
            return Err(invalid(
                "generated payload identity or denominator is invalid",
            ));
        }
        let coordinate_sha256 = native_fixed64_coordinate_sha256(&coordinates_angstrom)
            .map_err(|_| invalid("generated payload coordinates are outside frozen bounds"))?;
        let source_quaternion = source_quaternion
            .canonicalized()
            .map_err(|_| invalid("generated payload quaternion is invalid"))?;
        Ok(Self {
            pool_index,
            state: NativeSamplingFunnelPayloadRowState::Generated {
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
                coordinates_angstrom: coordinates_angstrom.into_boxed_slice(),
                source_quaternion,
            },
        })
    }

    pub fn typed_failure(pool_index: usize) -> Result<Self, NativeSamplingFunnelBatchError> {
        if pool_index >= NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR {
            return Err(invalid("typed-failure payload index is out of range"));
        }
        Ok(Self {
            pool_index,
            state: NativeSamplingFunnelPayloadRowState::TypedFailure,
        })
    }

    #[must_use]
    pub const fn pool_index(&self) -> usize {
        self.pool_index
    }

    #[must_use]
    pub const fn state(&self) -> &NativeSamplingFunnelPayloadRowState {
        &self.state
    }

    fn has_valid_payload(&self, ligand_atom_count: usize) -> bool {
        match &self.state {
            NativeSamplingFunnelPayloadRowState::Generated {
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
                coordinates_angstrom,
                source_quaternion,
            } => {
                !digest_is_zero(*source_sha256)
                    && !digest_is_zero(*proposal_sha256)
                    && coordinates_angstrom.len() == ligand_atom_count
                    && native_fixed64_coordinate_sha256(coordinates_angstrom)
                        .is_ok_and(|observed| observed == *coordinate_sha256)
                    && source_quaternion
                        .canonicalized()
                        .is_ok_and(|canonical| canonical == *source_quaternion)
            }
            NativeSamplingFunnelPayloadRowState::TypedFailure => true,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeSamplingFunnelPayloadBatch {
    ligand_atom_count: usize,
    rows: Box<[NativeSamplingFunnelPayloadRow]>,
    receipt_sha256: [u8; 32],
}

impl NativeSamplingFunnelPayloadBatch {
    pub fn new(
        ligand_atom_count: usize,
        rows: Vec<NativeSamplingFunnelPayloadRow>,
    ) -> Result<Self, NativeSamplingFunnelBatchError> {
        if ligand_atom_count == 0 || ligand_atom_count > FIXED64_MAX_LIGAND_ATOMS {
            return Err(invalid(
                "payload ligand denominator is outside frozen bounds",
            ));
        }
        if rows.len() != NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR {
            return Err(invalid("payload batch requires exactly 512 rows"));
        }
        for (expected_index, row) in rows.iter().enumerate() {
            if row.pool_index != expected_index {
                return Err(cross_wired("payload batch pool order is cross-wired"));
            }
            if !row.has_valid_payload(ligand_atom_count) {
                return Err(invalid(
                    "payload row failed coordinate or quaternion validation",
                ));
            }
        }
        let receipt_sha256 = payload_batch_receipt_sha256(ligand_atom_count, &rows);
        let value = Self {
            ligand_atom_count,
            rows: rows.into_boxed_slice(),
            receipt_sha256,
        };
        if !value.has_valid_receipt() {
            return Err(internal("payload batch did not self-verify"));
        }
        Ok(value)
    }

    #[must_use]
    pub const fn ligand_atom_count(&self) -> usize {
        self.ligand_atom_count
    }

    #[must_use]
    pub fn rows(&self) -> &[NativeSamplingFunnelPayloadRow] {
        &self.rows
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        self.ligand_atom_count > 0
            && self.ligand_atom_count <= FIXED64_MAX_LIGAND_ATOMS
            && self.rows.len() == NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR
            && self.rows.iter().enumerate().all(|(expected, row)| {
                row.pool_index == expected && row.has_valid_payload(self.ligand_atom_count)
            })
            && self.receipt_sha256
                == payload_batch_receipt_sha256(self.ligand_atom_count, &self.rows)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NativeSamplingFunnelPreselectedRow {
    output_index: usize,
    lane: crate::NativeSamplingFunnelLane,
    state: NativeSamplingFunnelSelectedState,
}

impl NativeSamplingFunnelPreselectedRow {
    #[must_use]
    pub const fn output_index(self) -> usize {
        self.output_index
    }

    #[must_use]
    pub const fn lane(self) -> crate::NativeSamplingFunnelLane {
        self.lane
    }

    #[must_use]
    pub const fn state(self) -> NativeSamplingFunnelSelectedState {
        self.state
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct NativeSamplingFunnelPreselectedBatch {
    ligand_atom_count: usize,
    rows: Box<[NativeSamplingFunnelPreselectedRow]>,
    x_angstrom: Box<[f64]>,
    y_angstrom: Box<[f64]>,
    z_angstrom: Box<[f64]>,
    source_quaternion_x: Box<[f64]>,
    source_quaternion_y: Box<[f64]>,
    source_quaternion_z: Box<[f64]>,
    source_quaternion_w: Box<[f64]>,
    funnel_receipt_sha256: [u8; 32],
    payload_receipt_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

impl NativeSamplingFunnelPreselectedBatch {
    #[must_use]
    pub const fn ligand_atom_count(&self) -> usize {
        self.ligand_atom_count
    }

    #[must_use]
    pub fn rows(&self) -> &[NativeSamplingFunnelPreselectedRow] {
        &self.rows
    }

    #[must_use]
    pub fn x_angstrom(&self) -> &[f64] {
        &self.x_angstrom
    }

    #[must_use]
    pub fn y_angstrom(&self) -> &[f64] {
        &self.y_angstrom
    }

    #[must_use]
    pub fn z_angstrom(&self) -> &[f64] {
        &self.z_angstrom
    }

    #[must_use]
    pub fn source_quaternion_x(&self) -> &[f64] {
        &self.source_quaternion_x
    }

    #[must_use]
    pub fn source_quaternion_y(&self) -> &[f64] {
        &self.source_quaternion_y
    }

    #[must_use]
    pub fn source_quaternion_z(&self) -> &[f64] {
        &self.source_quaternion_z
    }

    #[must_use]
    pub fn source_quaternion_w(&self) -> &[f64] {
        &self.source_quaternion_w
    }

    #[must_use]
    pub fn coordinate(&self, output_index: usize, atom_index: usize) -> Option<Vec3> {
        if output_index >= NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            || atom_index >= self.ligand_atom_count
        {
            return None;
        }
        let index = output_index
            .checked_mul(self.ligand_atom_count)?
            .checked_add(atom_index)?;
        Some(Vec3::new(
            *self.x_angstrom.get(index)?,
            *self.y_angstrom.get(index)?,
            *self.z_angstrom.get(index)?,
        ))
    }

    #[must_use]
    pub fn source_quaternion(&self, output_index: usize) -> Option<Quaternion> {
        Some(Quaternion::new(
            *self.source_quaternion_x.get(output_index)?,
            *self.source_quaternion_y.get(output_index)?,
            *self.source_quaternion_z.get(output_index)?,
            *self.source_quaternion_w.get(output_index)?,
        ))
    }

    #[must_use]
    pub const fn funnel_receipt_sha256(&self) -> [u8; 32] {
        self.funnel_receipt_sha256
    }

    #[must_use]
    pub const fn payload_receipt_sha256(&self) -> [u8; 32] {
        self.payload_receipt_sha256
    }

    #[must_use]
    pub const fn receipt_sha256(&self) -> [u8; 32] {
        self.receipt_sha256
    }

    #[must_use]
    pub const fn molecular_execution_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn benchmark_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn product_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn scientific_claim_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub const fn rank_mutation_authorized(&self) -> bool {
        false
    }

    #[must_use]
    pub fn has_valid_receipt(&self) -> bool {
        let Some(expected_coordinate_count) = self
            .ligand_atom_count
            .checked_mul(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR)
        else {
            return false;
        };
        if self.ligand_atom_count == 0
            || self.ligand_atom_count > FIXED64_MAX_LIGAND_ATOMS
            || self.rows.len() != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            || self.x_angstrom.len() != expected_coordinate_count
            || self.y_angstrom.len() != expected_coordinate_count
            || self.z_angstrom.len() != expected_coordinate_count
            || self.source_quaternion_x.len() != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            || self.source_quaternion_y.len() != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            || self.source_quaternion_z.len() != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            || self.source_quaternion_w.len() != NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR
            || digest_is_zero(self.funnel_receipt_sha256)
            || digest_is_zero(self.payload_receipt_sha256)
        {
            return false;
        }
        for (output_index, row) in self.rows.iter().enumerate() {
            if row.output_index != output_index {
                return false;
            }
            let coordinates = (0..self.ligand_atom_count)
                .map(|atom_index| self.coordinate(output_index, atom_index))
                .collect::<Option<Vec<_>>>();
            let Some(coordinates) = coordinates else {
                return false;
            };
            let Some(quaternion) = self.source_quaternion(output_index) else {
                return false;
            };
            match row.state {
                NativeSamplingFunnelSelectedState::Selected {
                    coordinate_sha256, ..
                } => {
                    if !native_fixed64_coordinate_sha256(&coordinates)
                        .is_ok_and(|observed| observed == coordinate_sha256)
                        || !quaternion
                            .canonicalized()
                            .is_ok_and(|canonical| canonical == quaternion)
                    {
                        return false;
                    }
                }
                NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => {
                    if coordinates
                        .iter()
                        .any(|coordinate| *coordinate != Vec3::default())
                        || quaternion != Quaternion::new(0.0, 0.0, 0.0, 0.0)
                    {
                        return false;
                    }
                }
            }
        }
        self.receipt_sha256 == preselected_batch_receipt_sha256(self)
    }

    #[must_use]
    pub fn verifies_against(
        &self,
        funnel: &NativeSamplingFunnelReceipt,
        payloads: &NativeSamplingFunnelPayloadBatch,
    ) -> bool {
        materialize_native_sampling_funnel_preselected_batch(funnel, payloads)
            .is_ok_and(|derived| derived == *self)
    }
}

pub fn materialize_native_sampling_funnel_preselected_batch(
    funnel: &NativeSamplingFunnelReceipt,
    payloads: &NativeSamplingFunnelPayloadBatch,
) -> Result<NativeSamplingFunnelPreselectedBatch, NativeSamplingFunnelBatchError> {
    if !funnel.has_valid_receipt() || !payloads.has_valid_receipt() {
        return Err(cross_wired("funnel or payload receipt is invalid"));
    }
    for (candidate, payload) in funnel.candidates().iter().zip(payloads.rows()) {
        if candidate.pool_index() != payload.pool_index() {
            return Err(cross_wired(
                "funnel and payload pool indices are cross-wired",
            ));
        }
        match (candidate.state(), payload.state()) {
            (
                NativeSamplingFunnelCandidateState::Generated(expected),
                NativeSamplingFunnelPayloadRowState::Generated {
                    source_sha256,
                    proposal_sha256,
                    coordinate_sha256,
                    ..
                },
            ) => {
                if expected.source_sha256() != *source_sha256
                    || expected.proposal_sha256() != *proposal_sha256
                {
                    return Err(cross_wired(
                        "funnel and payload source identity are cross-wired",
                    ));
                }
                if expected.coordinate_sha256() != *coordinate_sha256 {
                    return Err(coordinate_mismatch(
                        "funnel and payload coordinate identities differ",
                    ));
                }
            }
            (
                NativeSamplingFunnelCandidateState::TypedFailure { .. },
                NativeSamplingFunnelPayloadRowState::TypedFailure,
            ) => {}
            _ => return Err(cross_wired("funnel and payload row states are cross-wired")),
        }
    }

    let coordinate_capacity = payloads
        .ligand_atom_count
        .checked_mul(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR)
        .ok_or_else(|| internal("preselected coordinate denominator overflowed"))?;
    let mut x_angstrom = Vec::with_capacity(coordinate_capacity);
    let mut y_angstrom = Vec::with_capacity(coordinate_capacity);
    let mut z_angstrom = Vec::with_capacity(coordinate_capacity);
    let mut source_quaternion_x = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    let mut source_quaternion_y = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    let mut source_quaternion_z = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    let mut source_quaternion_w = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    let mut rows = Vec::with_capacity(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    for selected in funnel.selected_rows() {
        rows.push(NativeSamplingFunnelPreselectedRow {
            output_index: selected.output_index(),
            lane: selected.lane(),
            state: selected.state(),
        });
        match selected.state() {
            NativeSamplingFunnelSelectedState::Selected {
                source_pool_index,
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
            } => {
                let payload = payloads.rows.get(source_pool_index).ok_or_else(|| {
                    internal("selected source index escaped the payload denominator")
                })?;
                let NativeSamplingFunnelPayloadRowState::Generated {
                    source_sha256: payload_source_sha256,
                    proposal_sha256: payload_proposal_sha256,
                    coordinate_sha256: payload_coordinate_sha256,
                    coordinates_angstrom: payload_coordinates,
                    source_quaternion,
                } = &payload.state
                else {
                    return Err(internal("selected payload row is not generated"));
                };
                if source_sha256 != *payload_source_sha256
                    || proposal_sha256 != *payload_proposal_sha256
                    || coordinate_sha256 != *payload_coordinate_sha256
                {
                    return Err(cross_wired(
                        "selected payload identity changed after validation",
                    ));
                }
                for coordinate in payload_coordinates {
                    x_angstrom.push(coordinate.x);
                    y_angstrom.push(coordinate.y);
                    z_angstrom.push(coordinate.z);
                }
                source_quaternion_x.push(source_quaternion.x);
                source_quaternion_y.push(source_quaternion.y);
                source_quaternion_z.push(source_quaternion.z);
                source_quaternion_w.push(source_quaternion.w);
            }
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => {
                x_angstrom.extend(std::iter::repeat_n(0.0, payloads.ligand_atom_count));
                y_angstrom.extend(std::iter::repeat_n(0.0, payloads.ligand_atom_count));
                z_angstrom.extend(std::iter::repeat_n(0.0, payloads.ligand_atom_count));
                source_quaternion_x.push(0.0);
                source_quaternion_y.push(0.0);
                source_quaternion_z.push(0.0);
                source_quaternion_w.push(0.0);
            }
        }
    }
    let mut value = NativeSamplingFunnelPreselectedBatch {
        ligand_atom_count: payloads.ligand_atom_count,
        rows: rows.into_boxed_slice(),
        x_angstrom: x_angstrom.into_boxed_slice(),
        y_angstrom: y_angstrom.into_boxed_slice(),
        z_angstrom: z_angstrom.into_boxed_slice(),
        source_quaternion_x: source_quaternion_x.into_boxed_slice(),
        source_quaternion_y: source_quaternion_y.into_boxed_slice(),
        source_quaternion_z: source_quaternion_z.into_boxed_slice(),
        source_quaternion_w: source_quaternion_w.into_boxed_slice(),
        funnel_receipt_sha256: funnel.receipt_sha256(),
        payload_receipt_sha256: payloads.receipt_sha256,
        receipt_sha256: [0; 32],
    };
    value.receipt_sha256 = preselected_batch_receipt_sha256(&value);
    if !value.has_valid_receipt() {
        return Err(internal("preselected batch did not self-verify"));
    }
    Ok(value)
}

fn payload_batch_receipt_sha256(
    ligand_atom_count: usize,
    rows: &[NativeSamplingFunnelPayloadRow],
) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_SAMPLING_FUNNEL_PAYLOAD_BATCH_SCHEMA_ID);
    hash.usize(NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR);
    hash.usize(ligand_atom_count);
    hash.usize(rows.len());
    for row in rows {
        hash.usize(row.pool_index);
        match &row.state {
            NativeSamplingFunnelPayloadRowState::Generated {
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
                source_quaternion,
                ..
            } => {
                hash.byte(0);
                hash.digest(*source_sha256);
                hash.digest(*proposal_sha256);
                hash.digest(*coordinate_sha256);
                hash.f64(source_quaternion.x);
                hash.f64(source_quaternion.y);
                hash.f64(source_quaternion.z);
                hash.f64(source_quaternion.w);
            }
            NativeSamplingFunnelPayloadRowState::TypedFailure => hash.byte(1),
        }
    }
    hash.finish()
}

fn preselected_batch_receipt_sha256(value: &NativeSamplingFunnelPreselectedBatch) -> [u8; 32] {
    let mut hash = CanonicalHash::new(NATIVE_SAMPLING_FUNNEL_PRESELECTED_BATCH_SCHEMA_ID);
    hash.usize(NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR);
    hash.usize(value.ligand_atom_count);
    hash.digest(value.funnel_receipt_sha256);
    hash.digest(value.payload_receipt_sha256);
    for (output_index, row) in value.rows.iter().enumerate() {
        hash.usize(row.output_index);
        hash.string(row.lane.id());
        match row.state {
            NativeSamplingFunnelSelectedState::Selected {
                source_pool_index,
                source_sha256,
                proposal_sha256,
                coordinate_sha256,
            } => {
                hash.byte(0);
                hash.usize(source_pool_index);
                hash.digest(source_sha256);
                hash.digest(proposal_sha256);
                hash.digest(coordinate_sha256);
                let quaternion = value
                    .source_quaternion(output_index)
                    .expect("preselected quaternion denominator is exact");
                hash.f64(quaternion.x);
                hash.f64(quaternion.y);
                hash.f64(quaternion.z);
                hash.f64(quaternion.w);
            }
            NativeSamplingFunnelSelectedState::LaneQuotaUnfilled => hash.byte(1),
        }
    }
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.bool(false);
    hash.finish()
}

fn digest_is_zero(value: [u8; 32]) -> bool {
    value == [0; 32]
}

const fn invalid(message: &'static str) -> NativeSamplingFunnelBatchError {
    NativeSamplingFunnelBatchError::new(NativeSamplingFunnelBatchErrorCode::InvalidInput, message)
}

const fn cross_wired(message: &'static str) -> NativeSamplingFunnelBatchError {
    NativeSamplingFunnelBatchError::new(
        NativeSamplingFunnelBatchErrorCode::InputCrossWired,
        message,
    )
}

const fn coordinate_mismatch(message: &'static str) -> NativeSamplingFunnelBatchError {
    NativeSamplingFunnelBatchError::new(
        NativeSamplingFunnelBatchErrorCode::CoordinateDigestMismatch,
        message,
    )
}

const fn internal(message: &'static str) -> NativeSamplingFunnelBatchError {
    NativeSamplingFunnelBatchError::new(
        NativeSamplingFunnelBatchErrorCode::InternalInvariant,
        message,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        run_native_sampling_funnel, NativeSamplingFunnelCandidate, NativeSamplingFunnelLane,
    };

    fn digest(value: u64) -> [u8; 32] {
        let mut result = [0; 32];
        result[24..].copy_from_slice(&value.to_be_bytes());
        result
    }

    fn lane(index: usize) -> NativeSamplingFunnelLane {
        match index % 4 {
            0 => NativeSamplingFunnelLane::UniformSo3,
            1 => NativeSamplingFunnelLane::PocketSurface,
            2 => NativeSamplingFunnelLane::SingleAnchor,
            3 => NativeSamplingFunnelLane::MultiAnchor,
            _ => unreachable!(),
        }
    }

    fn coordinates(index: usize) -> Vec<Vec3> {
        let base = index as f64 * 0.01;
        vec![
            Vec3::new(base, 0.25, -0.5),
            Vec3::new(base + 1.0, 1.25, 0.5),
        ]
    }

    fn generated_candidate(index: usize) -> NativeSamplingFunnelCandidate {
        let coordinate_sha256 = native_fixed64_coordinate_sha256(&coordinates(index)).unwrap();
        NativeSamplingFunnelCandidate::generated(
            index,
            lane(index),
            digest(index as u64 + 1),
            digest(index as u64 + 513),
            coordinate_sha256,
            0.8,
            1.0,
            (index % 17) as f64,
            (index % 11) as f64,
            std::array::from_fn(|dimension| ((index * (dimension + 3)) % 19) as f64),
        )
        .unwrap()
    }

    fn generated_payload(index: usize) -> NativeSamplingFunnelPayloadRow {
        NativeSamplingFunnelPayloadRow::generated(
            index,
            digest(index as u64 + 1),
            digest(index as u64 + 513),
            coordinates(index),
            Quaternion::new(0.0, 0.0, 0.0, 1.0),
        )
        .unwrap()
    }

    fn generated_fixture() -> (
        NativeSamplingFunnelReceipt,
        NativeSamplingFunnelPayloadBatch,
    ) {
        let funnel = run_native_sampling_funnel(
            (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
                .map(generated_candidate)
                .collect(),
        )
        .unwrap();
        let payloads = NativeSamplingFunnelPayloadBatch::new(
            2,
            (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
                .map(generated_payload)
                .collect(),
        )
        .unwrap();
        (funnel, payloads)
    }

    #[test]
    fn materializes_exact_selected_payload_order_and_rederivable_receipts() {
        let (funnel, payloads) = generated_fixture();
        let first =
            materialize_native_sampling_funnel_preselected_batch(&funnel, &payloads).unwrap();
        let second =
            materialize_native_sampling_funnel_preselected_batch(&funnel, &payloads).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.rows().len(), 64);
        assert_eq!(first.x_angstrom().len(), 128);
        assert_eq!(first.y_angstrom().len(), 128);
        assert_eq!(first.z_angstrom().len(), 128);
        assert!(first.has_valid_receipt());
        assert!(first.verifies_against(&funnel, &payloads));
        assert_eq!(first.funnel_receipt_sha256(), funnel.receipt_sha256());
        assert_eq!(first.payload_receipt_sha256(), payloads.receipt_sha256());
        assert!(!first.molecular_execution_authorized());
        assert!(!first.benchmark_claim_authorized());
        assert!(!first.product_authorized());
        assert!(!first.scientific_claim_authorized());
        assert!(!first.rank_mutation_authorized());
        for (output_index, selected) in funnel.selected_rows().iter().enumerate() {
            assert_eq!(first.rows()[output_index].state(), selected.state());
            let source_pool_index = selected.source_pool_index().unwrap();
            for (atom_index, expected) in coordinates(source_pool_index).iter().enumerate() {
                assert_eq!(first.coordinate(output_index, atom_index), Some(*expected));
            }
            assert_eq!(
                first.source_quaternion(output_index),
                Some(Quaternion::new(0.0, 0.0, 0.0, 1.0))
            );
        }
    }

    #[test]
    fn coordinate_and_source_identity_cross_wiring_fail_closed() {
        let (funnel, _) = generated_fixture();
        let mut coordinate_cross_wire = (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
            .map(generated_payload)
            .collect::<Vec<_>>();
        coordinate_cross_wire[0] = NativeSamplingFunnelPayloadRow::generated(
            0,
            digest(1),
            digest(513),
            coordinates(511),
            Quaternion::new(0.0, 0.0, 0.0, 1.0),
        )
        .unwrap();
        let coordinate_cross_wire =
            NativeSamplingFunnelPayloadBatch::new(2, coordinate_cross_wire).unwrap();
        assert_eq!(
            materialize_native_sampling_funnel_preselected_batch(&funnel, &coordinate_cross_wire)
                .unwrap_err()
                .code(),
            NativeSamplingFunnelBatchErrorCode::CoordinateDigestMismatch
        );

        let mut source_cross_wire = (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
            .map(generated_payload)
            .collect::<Vec<_>>();
        source_cross_wire[0] = NativeSamplingFunnelPayloadRow::generated(
            0,
            digest(9999),
            digest(513),
            coordinates(0),
            Quaternion::new(0.0, 0.0, 0.0, 1.0),
        )
        .unwrap();
        let source_cross_wire =
            NativeSamplingFunnelPayloadBatch::new(2, source_cross_wire).unwrap();
        assert_eq!(
            materialize_native_sampling_funnel_preselected_batch(&funnel, &source_cross_wire)
                .unwrap_err()
                .code(),
            NativeSamplingFunnelBatchErrorCode::InputCrossWired
        );
    }

    #[test]
    fn typed_lane_shortfall_preserves_zeroed_fixed_width_payload_rows() {
        let candidates = (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
            .map(|index| {
                if lane(index) == NativeSamplingFunnelLane::MultiAnchor {
                    NativeSamplingFunnelCandidate::typed_failure(
                        index,
                        NativeSamplingFunnelLane::MultiAnchor,
                        "feature_missing",
                    )
                    .unwrap()
                } else {
                    generated_candidate(index)
                }
            })
            .collect();
        let payload_rows = (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
            .map(|index| {
                if lane(index) == NativeSamplingFunnelLane::MultiAnchor {
                    NativeSamplingFunnelPayloadRow::typed_failure(index).unwrap()
                } else {
                    generated_payload(index)
                }
            })
            .collect();
        let funnel = run_native_sampling_funnel(candidates).unwrap();
        let payloads = NativeSamplingFunnelPayloadBatch::new(2, payload_rows).unwrap();
        let batch =
            materialize_native_sampling_funnel_preselected_batch(&funnel, &payloads).unwrap();
        for output_index in 56..64 {
            assert_eq!(
                batch.rows()[output_index].state(),
                NativeSamplingFunnelSelectedState::LaneQuotaUnfilled
            );
            assert_eq!(batch.coordinate(output_index, 0), Some(Vec3::default()));
            assert_eq!(batch.coordinate(output_index, 1), Some(Vec3::default()));
            assert_eq!(
                batch.source_quaternion(output_index),
                Some(Quaternion::new(0.0, 0.0, 0.0, 0.0))
            );
        }
        assert!(batch.has_valid_receipt());
        assert!(batch.verifies_against(&funnel, &payloads));
    }

    #[test]
    fn payload_order_and_candidate_state_mismatches_fail_closed() {
        let mut reordered = (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
            .map(generated_payload)
            .collect::<Vec<_>>();
        reordered.swap(0, 1);
        assert_eq!(
            NativeSamplingFunnelPayloadBatch::new(2, reordered)
                .unwrap_err()
                .code(),
            NativeSamplingFunnelBatchErrorCode::InputCrossWired
        );

        let mut candidates = (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
            .map(generated_candidate)
            .collect::<Vec<_>>();
        candidates[0] = NativeSamplingFunnelCandidate::typed_failure(
            0,
            NativeSamplingFunnelLane::UniformSo3,
            "generation_failed",
        )
        .unwrap();
        let funnel = run_native_sampling_funnel(candidates).unwrap();
        let payloads = NativeSamplingFunnelPayloadBatch::new(
            2,
            (0..NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR)
                .map(generated_payload)
                .collect(),
        )
        .unwrap();
        assert_eq!(
            materialize_native_sampling_funnel_preselected_batch(&funnel, &payloads)
                .unwrap_err()
                .code(),
            NativeSamplingFunnelBatchErrorCode::InputCrossWired
        );
    }
}
