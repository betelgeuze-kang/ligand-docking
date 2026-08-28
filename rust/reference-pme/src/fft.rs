//! Deterministic scalar complex transforms used by the reciprocal oracle.

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub(crate) struct Complex {
    pub(crate) real: f64,
    pub(crate) imaginary: f64,
}

impl Complex {
    pub(crate) const fn new(real: f64, imaginary: f64) -> Self {
        Self { real, imaginary }
    }

    pub(crate) fn norm_squared(self) -> f64 {
        self.real * self.real + self.imaginary * self.imaginary
    }

    pub(crate) fn scale(self, factor: f64) -> Self {
        Self::new(self.real * factor, self.imaginary * factor)
    }

    fn add(self, other: Self) -> Self {
        Self::new(self.real + other.real, self.imaginary + other.imaginary)
    }

    fn subtract(self, other: Self) -> Self {
        Self::new(self.real - other.real, self.imaginary - other.imaginary)
    }

    fn multiply(self, other: Self) -> Self {
        Self::new(
            self.real * other.real - self.imaginary * other.imaginary,
            self.real * other.imaginary + self.imaginary * other.real,
        )
    }
}

/// Apply the frozen separable z, y, x transform order in place.
pub(crate) fn fft_3d(values: &mut [Complex], dimensions: [usize; 3], inverse: bool) {
    transform_3d_with(values, dimensions, inverse, fft_1d);
}

fn fft_1d(values: &mut [Complex], inverse: bool) {
    let count = values.len();
    debug_assert!(count.is_power_of_two());

    let mut target = 0_usize;
    for source in 1..count {
        let mut bit = count >> 1;
        while target & bit != 0 {
            target ^= bit;
            bit >>= 1;
        }
        target ^= bit;
        if source < target {
            values.swap(source, target);
        }
    }

    let mut span = 2_usize;
    while span <= count {
        let direction = if inverse { 1.0 } else { -1.0 };
        let angle = direction * core::f64::consts::TAU / bounded_usize_to_f64(span);
        let root = Complex::new(libm::cos(angle), libm::sin(angle));
        for start in (0..count).step_by(span) {
            let mut twiddle = Complex::new(1.0, 0.0);
            for offset in 0..span / 2 {
                let even = values[start + offset];
                let odd = values[start + offset + span / 2].multiply(twiddle);
                values[start + offset] = even.add(odd);
                values[start + offset + span / 2] = even.subtract(odd);
                twiddle = twiddle.multiply(root);
            }
        }
        span *= 2;
    }

    if inverse {
        let normalization = 1.0 / bounded_usize_to_f64(count);
        for value in values {
            *value = value.scale(normalization);
        }
    }
}

fn bounded_usize_to_f64(value: usize) -> f64 {
    f64::from(u32::try_from(value).expect("validated FFT sizes fit u32"))
}

fn transform_3d_with(
    values: &mut [Complex],
    dimensions: [usize; 3],
    inverse: bool,
    transform_1d: fn(&mut [Complex], bool),
) {
    let [x_count, y_count, z_count] = dimensions;
    debug_assert_eq!(values.len(), x_count * y_count * z_count);
    let mut line = vec![Complex::default(); x_count.max(y_count).max(z_count)];

    for x in 0..x_count {
        for y in 0..y_count {
            for z in 0..z_count {
                line[z] = values[index(x, y, z, dimensions)];
            }
            transform_1d(&mut line[..z_count], inverse);
            for z in 0..z_count {
                values[index(x, y, z, dimensions)] = line[z];
            }
        }
    }
    for x in 0..x_count {
        for z in 0..z_count {
            for y in 0..y_count {
                line[y] = values[index(x, y, z, dimensions)];
            }
            transform_1d(&mut line[..y_count], inverse);
            for y in 0..y_count {
                values[index(x, y, z, dimensions)] = line[y];
            }
        }
    }
    for y in 0..y_count {
        for z in 0..z_count {
            for x in 0..x_count {
                line[x] = values[index(x, y, z, dimensions)];
            }
            transform_1d(&mut line[..x_count], inverse);
            for x in 0..x_count {
                values[index(x, y, z, dimensions)] = line[x];
            }
        }
    }
}

pub(crate) const fn index(x: usize, y: usize, z: usize, dimensions: [usize; 3]) -> usize {
    (x * dimensions[1] + y) * dimensions[2] + z
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::direct_dft::direct_dft_3d;

    #[test]
    fn radix_two_transform_matches_the_direct_dft_oracle() {
        let dimensions = [4, 8, 16];
        let input: Vec<_> = (0..dimensions.iter().product())
            .map(|index| {
                let value = bounded_usize_to_f64(index);
                Complex::new(libm::sin(0.17 * value), libm::cos(0.11 * value))
            })
            .collect();
        let mut fast = input.clone();
        let mut direct = input;
        fft_3d(&mut fast, dimensions, false);
        direct_dft_3d(&mut direct, dimensions, false);
        assert_complex_slices_close(&fast, &direct, 3.0e-12);

        fft_3d(&mut fast, dimensions, true);
        direct_dft_3d(&mut direct, dimensions, true);
        assert_complex_slices_close(&fast, &direct, 5.0e-12);
    }

    #[test]
    fn real_input_has_conjugate_symmetry_and_round_trips() {
        let dimensions = [4, 8, 4];
        let original: Vec<_> = (0..dimensions.iter().product())
            .map(|index| Complex::new(libm::sin(0.37 * bounded_usize_to_f64(index)), 0.0))
            .collect();
        let mut transformed = original.clone();
        fft_3d(&mut transformed, dimensions, false);
        for x in 0..dimensions[0] {
            for y in 0..dimensions[1] {
                for z in 0..dimensions[2] {
                    let paired = [
                        (dimensions[0] - x) % dimensions[0],
                        (dimensions[1] - y) % dimensions[1],
                        (dimensions[2] - z) % dimensions[2],
                    ];
                    let value = transformed[index(x, y, z, dimensions)];
                    let conjugate = transformed[index(paired[0], paired[1], paired[2], dimensions)];
                    assert_close(value.real, conjugate.real, 2.0e-12);
                    assert_close(value.imaginary, -conjugate.imaginary, 2.0e-12);
                }
            }
        }
        fft_3d(&mut transformed, dimensions, true);
        assert_complex_slices_close(&transformed, &original, 2.0e-12);
    }

    fn assert_complex_slices_close(left: &[Complex], right: &[Complex], tolerance: f64) {
        assert_eq!(left.len(), right.len());
        for (left, right) in left.iter().zip(right) {
            let scale = 1.0
                + left
                    .real
                    .abs()
                    .max(right.real.abs())
                    .max(left.imaginary.abs())
                    .max(right.imaginary.abs());
            assert!((left.real - right.real).abs() <= tolerance * scale);
            assert!((left.imaginary - right.imaginary).abs() <= tolerance * scale);
        }
    }

    fn assert_close(left: f64, right: f64, tolerance: f64) {
        let scale = 1.0 + left.abs().max(right.abs());
        assert!((left - right).abs() <= tolerance * scale);
    }
}
