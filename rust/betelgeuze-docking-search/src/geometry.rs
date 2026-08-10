use crate::{SearchError, SearchErrorCode};

pub(crate) const GEOMETRY_EPSILON: f64 = 1.0e-12;

/// Cartesian vector in the canonical units named by its containing field.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Vec3 {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Vec3 {
    #[must_use]
    pub const fn new(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }

    #[must_use]
    pub fn is_finite(self) -> bool {
        self.x.is_finite() && self.y.is_finite() && self.z.is_finite()
    }

    #[must_use]
    pub fn dot(self, other: Self) -> f64 {
        self.x * other.x + self.y * other.y + self.z * other.z
    }

    #[must_use]
    pub fn cross(self, other: Self) -> Self {
        Self::new(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )
    }

    #[must_use]
    pub fn norm_squared(self) -> f64 {
        self.dot(self)
    }

    #[must_use]
    pub fn norm(self) -> f64 {
        self.x.hypot(self.y).hypot(self.z)
    }

    pub(crate) fn normalized(self, label: &str) -> Result<Self, SearchError> {
        if !self.is_finite() {
            return Err(SearchError::new(
                SearchErrorCode::NonFiniteInput,
                format!("{label} must contain only finite components"),
            ));
        }
        let maximum = self.x.abs().max(self.y.abs()).max(self.z.abs());
        if maximum <= GEOMETRY_EPSILON {
            return Err(SearchError::new(
                SearchErrorCode::InvalidDirection,
                format!("{label} must be non-zero"),
            ));
        }
        let scaled = self.scale(1.0 / maximum);
        Ok(scaled.scale(1.0 / scaled.norm()))
    }

    #[must_use]
    pub fn scale(self, factor: f64) -> Self {
        Self::new(self.x * factor, self.y * factor, self.z * factor)
    }

    #[must_use]
    pub fn plus(self, other: Self) -> Self {
        Self::new(self.x + other.x, self.y + other.y, self.z + other.z)
    }

    #[must_use]
    pub fn minus(self, other: Self) -> Self {
        Self::new(self.x - other.x, self.y - other.y, self.z - other.z)
    }
}

/// Canonical `(x, y, z, w)` unit quaternion. `q` and `-q` normalize identically.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Quaternion {
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub w: f64,
}

impl Quaternion {
    #[must_use]
    pub const fn new(x: f64, y: f64, z: f64, w: f64) -> Self {
        Self { x, y, z, w }
    }

    pub fn canonicalized(self) -> Result<Self, SearchError> {
        if !self.x.is_finite() || !self.y.is_finite() || !self.z.is_finite() || !self.w.is_finite()
        {
            return Err(SearchError::new(
                SearchErrorCode::NonFiniteInput,
                "quaternion must contain only finite components",
            ));
        }
        let maximum = self
            .x
            .abs()
            .max(self.y.abs())
            .max(self.z.abs())
            .max(self.w.abs());
        if maximum <= GEOMETRY_EPSILON {
            return Err(SearchError::new(
                SearchErrorCode::InvalidDirection,
                "quaternion must be non-zero",
            ));
        }
        let scaled_norm = (self.x / maximum)
            .hypot(self.y / maximum)
            .hypot(self.z / maximum)
            .hypot(self.w / maximum);
        let norm = maximum * scaled_norm;
        let inverse = if norm.is_finite() && (norm - 1.0).abs() <= 1.0e-15 {
            1.0
        } else {
            (1.0 / maximum) / scaled_norm
        };
        let mut value = Self::new(
            self.x * inverse,
            self.y * inverse,
            self.z * inverse,
            self.w * inverse,
        );
        // Inspect (w, z, y, x), making exact pi rotations canonical too.
        for component in [value.w, value.z, value.y, value.x] {
            if component > 0.0 {
                break;
            }
            if component < 0.0 {
                value = Self::new(-value.x, -value.y, -value.z, -value.w);
                break;
            }
        }
        value.x = canonical_zero(value.x);
        value.y = canonical_zero(value.y);
        value.z = canonical_zero(value.z);
        value.w = canonical_zero(value.w);
        Ok(value)
    }

    #[must_use]
    pub fn rotate(self, vector: Vec3) -> Vec3 {
        let q = Vec3::new(self.x, self.y, self.z);
        let twice_cross = q.cross(vector).scale(2.0);
        vector
            .plus(twice_cross.scale(self.w))
            .plus(q.cross(twice_cross))
    }

    pub(crate) fn from_rotation_vector(rotation: Vec3) -> Result<Self, SearchError> {
        let angle = rotation.norm();
        if angle <= GEOMETRY_EPSILON {
            return Ok(Self::new(0.0, 0.0, 0.0, 1.0));
        }
        let half = 0.5 * angle;
        let sine_over_angle = half.sin() / angle;
        Self::new(
            rotation.x * sine_over_angle,
            rotation.y * sine_over_angle,
            rotation.z * sine_over_angle,
            half.cos(),
        )
        .canonicalized()
    }

    pub(crate) fn between(source: Vec3, target: Vec3) -> Result<Self, SearchError> {
        let source = source.normalized("dual-anchor ligand vector")?;
        let target = target.normalized("dual-anchor surface vector")?;
        let cosine = source.dot(target).clamp(-1.0, 1.0);
        if cosine >= 1.0 - 1.0e-12 {
            return Ok(Self::new(0.0, 0.0, 0.0, 1.0));
        }
        if cosine <= -1.0 + 1.0e-12 {
            let mut reference = Vec3::new(1.0, 0.0, 0.0);
            if source.dot(reference).abs() > 0.9 {
                reference = Vec3::new(0.0, 1.0, 0.0);
            }
            let axis = source
                .cross(reference)
                .normalized("opposite dual-anchor rotation axis")?;
            return Self::from_rotation_vector(axis.scale(core::f64::consts::PI));
        }
        let axis = source.cross(target);
        Self::new(axis.x, axis.y, axis.z, 1.0 + cosine).canonicalized()
    }

    /// Compose rotations so `self.multiply(right)` applies `right` first.
    pub(crate) fn multiply(self, right: Self) -> Result<Self, SearchError> {
        Self::new(
            self.w * right.x + self.x * right.w + self.y * right.z - self.z * right.y,
            self.w * right.y - self.x * right.z + self.y * right.w + self.z * right.x,
            self.w * right.z + self.x * right.y - self.y * right.x + self.z * right.w,
            self.w * right.w - self.x * right.x - self.y * right.y - self.z * right.z,
        )
        .canonicalized()
    }
}

fn canonical_zero(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

pub(crate) fn centroid(points: &[Vec3]) -> Vec3 {
    let inverse = 1.0 / points.len() as f64;
    points
        .iter()
        .copied()
        .fold(Vec3::default(), Vec3::plus)
        .scale(inverse)
}

pub(crate) fn clamp_norm(vector: Vec3, maximum: f64) -> Vec3 {
    let norm = vector.norm();
    if norm > maximum {
        vector.scale(maximum / norm)
    } else {
        vector
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quaternion_sign_and_negative_zero_are_canonical() {
        let positive = Quaternion::new(1.0, -2.0, 3.0, -4.0)
            .canonicalized()
            .unwrap();
        let negative = Quaternion::new(-1.0, 2.0, -3.0, 4.0)
            .canonicalized()
            .unwrap();
        assert_eq!(positive, negative);
        let pi = Quaternion::new(-1.0, -0.0, 0.0, 0.0)
            .canonicalized()
            .unwrap();
        assert_eq!(pi, Quaternion::new(1.0, 0.0, 0.0, 0.0));
    }

    #[test]
    fn rotation_vector_rotates_without_changing_norm() {
        let quaternion =
            Quaternion::from_rotation_vector(Vec3::new(0.0, 0.0, core::f64::consts::FRAC_PI_2))
                .unwrap();
        let observed = quaternion.rotate(Vec3::new(1.0, 0.0, 0.0));
        assert!(observed.x.abs() < 1.0e-15);
        assert!((observed.y - 1.0).abs() < 1.0e-15);
        assert!((observed.norm() - 1.0).abs() < 1.0e-15);
    }

    #[test]
    fn normalization_is_stable_for_large_finite_components() {
        let observed = Vec3::new(f64::MAX, f64::MAX, 0.0)
            .normalized("large vector")
            .unwrap();
        assert!(observed.is_finite());
        assert!((observed.norm() - 1.0).abs() < 2.0e-15);
        assert!(Quaternion::new(f64::MAX, 0.0, 0.0, f64::MAX)
            .canonicalized()
            .unwrap()
            .x
            .is_finite());
    }
}
