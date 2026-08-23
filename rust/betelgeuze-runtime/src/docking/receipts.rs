use betelgeuze_docking_search::Vec3;
use sha2::{Digest, Sha256 as Sha256Hasher};

use super::types::Sha256;

pub(crate) struct CanonicalHasher {
    digest: Sha256Hasher,
    transcript: Option<Vec<u8>>,
}

impl CanonicalHasher {
    pub(crate) fn new(domain: &str) -> Self {
        let mut hasher = Self {
            digest: Sha256Hasher::new(),
            transcript: None,
        };
        hasher.string(domain);
        hasher
    }

    pub(crate) fn new_recording(domain: &str) -> Self {
        let mut hasher = Self {
            digest: Sha256Hasher::new(),
            transcript: Some(Vec::new()),
        };
        hasher.string(domain);
        hasher
    }

    fn update(&mut self, bytes: &[u8]) {
        self.digest.update(bytes);
        if let Some(transcript) = &mut self.transcript {
            transcript.extend_from_slice(bytes);
        }
    }

    pub(crate) fn byte(&mut self, value: u8) {
        self.update(&[value]);
    }

    pub(crate) fn u32(&mut self, value: u32) {
        self.update(&value.to_be_bytes());
    }

    pub(crate) fn i32(&mut self, value: i32) {
        self.u32(value as u32);
    }

    pub(crate) fn u64(&mut self, value: u64) {
        self.update(&value.to_be_bytes());
    }

    pub(crate) fn usize(&mut self, value: usize) {
        self.u64(u64::try_from(value).expect("bounded native receipt length fits u64"));
    }

    pub(crate) fn f64(&mut self, value: f64) {
        let canonical = if value == 0.0 { 0.0 } else { value };
        self.u64(canonical.to_bits());
    }

    pub(crate) fn vec3(&mut self, value: Vec3) {
        self.f64(value.x);
        self.f64(value.y);
        self.f64(value.z);
    }

    pub(crate) fn bytes(&mut self, value: &[u8]) {
        self.usize(value.len());
        self.update(value);
    }

    pub(crate) fn string(&mut self, value: &str) {
        self.bytes(value.as_bytes());
    }

    pub(crate) fn digest(&mut self, value: Sha256) {
        self.update(&value);
    }

    pub(crate) fn finish(self) -> Sha256 {
        self.digest.finalize().into()
    }

    pub(crate) fn finish_recording(self) -> (Sha256, Vec<u8>) {
        let transcript = self
            .transcript
            .expect("recording canonical hasher retains its transcript");
        (self.digest.finalize().into(), transcript)
    }
}
