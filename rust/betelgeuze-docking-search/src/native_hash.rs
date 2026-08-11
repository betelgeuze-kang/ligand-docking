use crate::sha256::Sha256;
use crate::Vec3;

pub(crate) struct CanonicalHash {
    inner: Sha256,
}

impl CanonicalHash {
    pub(crate) fn new(domain: &str) -> Self {
        let mut value = Self {
            inner: Sha256::new(),
        };
        value.string(domain);
        value
    }

    pub(crate) fn byte(&mut self, value: u8) {
        self.inner.update(&[value]);
    }

    pub(crate) fn bool(&mut self, value: bool) {
        self.byte(u8::from(value));
    }

    pub(crate) fn usize(&mut self, value: usize) {
        let value = u64::try_from(value).expect("native receipt sizes fit u64");
        self.u64(value);
    }

    pub(crate) fn u32(&mut self, value: u32) {
        self.inner.update(&value.to_be_bytes());
    }

    pub(crate) fn u64(&mut self, value: u64) {
        self.inner.update(&value.to_be_bytes());
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
        self.inner.update(value);
    }

    pub(crate) fn string(&mut self, value: &str) {
        self.bytes(value.as_bytes());
    }

    pub(crate) fn digest(&mut self, value: [u8; 32]) {
        self.inner.update(&value);
    }

    pub(crate) fn option<T>(&mut self, value: Option<T>, encode: impl FnOnce(&mut Self, T)) {
        self.bool(value.is_some());
        if let Some(value) = value {
            encode(self, value);
        }
    }

    pub(crate) fn finish(self) -> [u8; 32] {
        self.inner.finalize()
    }
}
