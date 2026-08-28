//! Fully independent direct three-dimensional DFT used only by tests.

use crate::fft::Complex;

pub(crate) fn direct_dft_3d(values: &mut [Complex], dimensions: [usize; 3], inverse: bool) {
    let [x_count, y_count, z_count] = dimensions;
    assert_eq!(values.len(), x_count * y_count * z_count);
    let input = values.to_vec();
    let direction = if inverse { 1.0 } else { -1.0 };
    let normalization = if inverse {
        1.0 / bounded_usize_to_f64(values.len())
    } else {
        1.0
    };

    for wave_x in 0..x_count {
        for wave_y in 0..y_count {
            for wave_z in 0..z_count {
                let mut real = 0.0;
                let mut imaginary = 0.0;
                for position_x in 0..x_count {
                    for position_y in 0..y_count {
                        for position_z in 0..z_count {
                            let phase = direction
                                * core::f64::consts::TAU
                                * (bounded_usize_to_f64(wave_x) * bounded_usize_to_f64(position_x)
                                    / bounded_usize_to_f64(x_count)
                                    + bounded_usize_to_f64(wave_y)
                                        * bounded_usize_to_f64(position_y)
                                        / bounded_usize_to_f64(y_count)
                                    + bounded_usize_to_f64(wave_z)
                                        * bounded_usize_to_f64(position_z)
                                        / bounded_usize_to_f64(z_count));
                            let value =
                                input[flat_index(position_x, position_y, position_z, dimensions)];
                            let cosine = libm::cos(phase);
                            let sine = libm::sin(phase);
                            real += value.real * cosine - value.imaginary * sine;
                            imaginary += value.real * sine + value.imaginary * cosine;
                        }
                    }
                }
                values[flat_index(wave_x, wave_y, wave_z, dimensions)] =
                    Complex::new(real * normalization, imaginary * normalization);
            }
        }
    }
}

const fn flat_index(x: usize, y: usize, z: usize, dimensions: [usize; 3]) -> usize {
    (x * dimensions[1] + y) * dimensions[2] + z
}

fn bounded_usize_to_f64(value: usize) -> f64 {
    f64::from(u32::try_from(value).expect("direct-DFT test sizes fit u32"))
}
