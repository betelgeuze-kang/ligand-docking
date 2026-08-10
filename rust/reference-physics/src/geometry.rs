use crate::{OracleError, OracleErrorCode, OrthorhombicCell, Position};

pub(crate) const DEGENERATE_SQUARED_ANGSTROM2: f64 = 1.0e-24;
const ANGLE_COSINE_MARGIN: f64 = 1.0e-12;

#[derive(Clone, Copy, Debug)]
pub(crate) struct Vector3 {
    pub(crate) x: f64,
    pub(crate) y: f64,
    pub(crate) z: f64,
}

impl Vector3 {
    pub(crate) fn dot(self, other: Self) -> f64 {
        self.x * other.x + self.y * other.y + self.z * other.z
    }

    pub(crate) fn cross(self, other: Self) -> Self {
        Self {
            x: self.y * other.z - self.z * other.y,
            y: self.z * other.x - self.x * other.z,
            z: self.x * other.y - self.y * other.x,
        }
    }

    pub(crate) fn squared_norm(self) -> f64 {
        self.dot(self)
    }

    pub(crate) fn scale(self, factor: f64) -> Self {
        Self {
            x: self.x * factor,
            y: self.y * factor,
            z: self.z * factor,
        }
    }

    pub(crate) fn subtract(self, other: Self) -> Self {
        Self {
            x: self.x - other.x,
            y: self.y - other.y,
            z: self.z - other.z,
        }
    }
}

pub(crate) fn displacement(
    first: Position,
    second: Position,
    cell: Option<OrthorhombicCell>,
) -> Vector3 {
    let mut components = [
        first.x_angstrom - second.x_angstrom,
        first.y_angstrom - second.y_angstrom,
        first.z_angstrom - second.z_angstrom,
    ];
    if let Some(cell) = cell {
        for (axis, component) in components.iter_mut().enumerate() {
            if cell.periodic_axes[axis] {
                let length = cell.lengths_angstrom[axis];
                *component -= length * (*component / length + 0.5).floor();
            }
        }
    }
    Vector3 {
        x: components[0],
        y: components[1],
        z: components[2],
    }
}

pub(crate) fn angle_radians(first: Vector3, second: Vector3) -> Result<f64, OracleError> {
    let first_squared = first.squared_norm();
    let second_squared = second.squared_norm();
    if first_squared <= DEGENERATE_SQUARED_ANGSTROM2
        || second_squared <= DEGENERATE_SQUARED_ANGSTROM2
    {
        return Err(OracleError::new(
            OracleErrorCode::DegenerateAngle,
            "angle contains a zero-length arm",
        ));
    }
    let denominator = first_squared.sqrt() * second_squared.sqrt();
    let cosine = (first.dot(second) / denominator)
        .clamp(-1.0 + ANGLE_COSINE_MARGIN, 1.0 - ANGLE_COSINE_MARGIN);
    Ok(cosine.acos())
}

pub(crate) fn torsion_radians(b0: Vector3, b1: Vector3, b2: Vector3) -> Result<f64, OracleError> {
    let central_squared = b1.squared_norm();
    if central_squared <= DEGENERATE_SQUARED_ANGSTROM2 {
        return Err(OracleError::new(
            OracleErrorCode::DegenerateTorsion,
            "torsion central bond has zero length",
        ));
    }
    let axis = b1.scale(1.0 / central_squared.sqrt());
    let v = b0.subtract(axis.scale(b0.dot(axis)));
    let w = b2.subtract(axis.scale(b2.dot(axis)));
    if v.squared_norm() <= DEGENERATE_SQUARED_ANGSTROM2
        || w.squared_norm() <= DEGENERATE_SQUARED_ANGSTROM2
    {
        return Err(OracleError::new(
            OracleErrorCode::DegenerateTorsion,
            "torsion is undefined for collinear adjacent atoms",
        ));
    }
    Ok(axis.cross(v).dot(w).atan2(v.dot(w)))
}

#[cfg(test)]
mod tests {
    use super::displacement;
    use crate::{OrthorhombicCell, Position};

    #[test]
    fn minimum_image_uses_frozen_half_open_tie_rule() {
        let cell = OrthorhombicCell {
            lengths_angstrom: [10.0, 10.0, 10.0],
            periodic_axes: [true, true, false],
        };
        let positive = displacement(
            Position::new(5.0, 0.0, 0.0),
            Position::default(),
            Some(cell),
        );
        let negative = displacement(
            Position::new(-5.0, 0.0, 0.0),
            Position::default(),
            Some(cell),
        );
        assert_eq!(positive.x.to_bits(), (-5.0_f64).to_bits());
        assert_eq!(negative.x.to_bits(), (-5.0_f64).to_bits());
    }
}
