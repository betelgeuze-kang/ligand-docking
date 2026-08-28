use std::ffi::CStr;
use std::mem::MaybeUninit;
use std::ptr;

use betelgeuze_sys as sys;

use crate::direct_ewald::{
    abi_error, ensure_direct_ewald_abi_compatibility, error_from_call, initialized_error,
    plain_status, require_direct_ewald_backend, validate_cleared_error, DirectEwaldError,
    DirectEwaldModel, DirectEwaldResult,
};
use crate::{checked_count, invalid, Context, ErrorCode, ForceField, ForceSoaOwned, System};

/// Frozen short-range, direct-Ewald, and grand-total energy order.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct DirectEwaldCompositeEnergyComponents {
    pub short_harmonic_bond_kcal_per_mol: f64,
    pub short_harmonic_angle_kcal_per_mol: f64,
    pub short_periodic_torsion_kcal_per_mol: f64,
    pub short_lennard_jones_kcal_per_mol: f64,
    pub short_coulomb_kcal_per_mol: f64,
    pub short_total_kcal_per_mol: f64,
    pub ewald_real_space_kcal_per_mol: f64,
    pub ewald_reciprocal_space_kcal_per_mol: f64,
    pub ewald_self_kcal_per_mol: f64,
    pub ewald_pair_correction_kcal_per_mol: f64,
    pub ewald_total_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
}

/// Owned result of one stateless short-range + direct-Ewald call.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct DirectEwaldCompositeEvaluation {
    pub energy: DirectEwaldCompositeEnergyComponents,
    pub forces: ForceSoaOwned,
}

impl Context {
    /// Evaluate the canonical short-range force field without Coulomb and add
    /// direct Ewald from the original exact-neutral charges.
    ///
    /// Every native handle is borrowed only for this synchronous call.  HIP
    /// contexts fail closed and never fall back to a CPU evaluator.
    pub fn evaluate_direct_ewald_composite(
        &self,
        system: &System,
        forcefield: &ForceField,
        model: &DirectEwaldModel,
    ) -> DirectEwaldResult<DirectEwaldCompositeEvaluation> {
        ensure_composite_abi_compatibility()?;
        require_direct_ewald_backend(self.backend().map_err(DirectEwaldError::from)?)?;
        let count = checked_compatible_lengths(system, forcefield, model)?;

        let mut force_x = fallible_nan_buffer(count, "x")?;
        let mut force_y = fallible_nan_buffer(count, "y")?;
        let mut force_z = fallible_nan_buffer(count, "z")?;
        let mut raw_energy = initialized_composite_energy()?;
        let mut raw_forces = initialized_composite_forces()?;
        raw_forces.atom_capacity = checked_count(count).map_err(DirectEwaldError::from)?;
        raw_forces.x_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_x);
        raw_forces.y_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_y);
        raw_forces.z_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_z);
        let mut raw_error = initialized_error()?;

        // SAFETY: All four opaque handles are live and thread-confined.  The
        // initialized descriptors and three owned force spans are writable and
        // mutually disjoint for the duration of this synchronous call.
        let status = unsafe {
            sys::bg_context_evaluate_direct_ewald_composite_v1(
                self.raw_handle(),
                system.raw_handle(),
                forcefield.raw_handle(),
                model.raw_handle(),
                &mut raw_energy,
                &mut raw_forces,
                &mut raw_error,
            )
        };
        if status != sys::BG_STATUS_OK {
            return Err(error_from_call(status, &raw_error));
        }
        validate_cleared_error(&raw_error)?;
        validate_force_descriptor(
            &raw_forces,
            count,
            force_x.as_mut_ptr(),
            force_y.as_mut_ptr(),
            force_z.as_mut_ptr(),
        )?;
        if force_x
            .iter()
            .chain(&force_y)
            .chain(&force_z)
            .any(|value| !value.is_finite())
        {
            return Err(abi_error(
                "native composite evaluator returned a non-finite force",
            ));
        }
        Ok(DirectEwaldCompositeEvaluation {
            energy: energy_from_raw(raw_energy)?,
            forces: ForceSoaOwned {
                x_kcal_per_mol_angstrom: force_x,
                y_kcal_per_mol_angstrom: force_y,
                z_kcal_per_mol_angstrom: force_z,
            },
        })
    }

    /// Evaluate the same frozen composite energy without allocating or asking
    /// either native parent for force storage.
    pub fn evaluate_direct_ewald_composite_energy(
        &self,
        system: &System,
        forcefield: &ForceField,
        model: &DirectEwaldModel,
    ) -> DirectEwaldResult<DirectEwaldCompositeEnergyComponents> {
        ensure_composite_abi_compatibility()?;
        require_direct_ewald_backend(self.backend().map_err(DirectEwaldError::from)?)?;
        checked_compatible_lengths(system, forcefield, model)?;
        let mut raw_energy = initialized_composite_energy()?;
        let mut raw_error = initialized_error()?;
        // SAFETY: Every borrowed handle and descriptor is live.  A null force
        // descriptor requests the native energy-only path for both parents.
        let status = unsafe {
            sys::bg_context_evaluate_direct_ewald_composite_v1(
                self.raw_handle(),
                system.raw_handle(),
                forcefield.raw_handle(),
                model.raw_handle(),
                &mut raw_energy,
                ptr::null_mut(),
                &mut raw_error,
            )
        };
        if status != sys::BG_STATUS_OK {
            return Err(error_from_call(status, &raw_error));
        }
        validate_cleared_error(&raw_error)?;
        energy_from_raw(raw_energy)
    }
}

/// Query the immutable profile identity for the stateless composite boundary.
pub fn direct_ewald_composite_profile_id() -> DirectEwaldResult<String> {
    ensure_composite_abi_compatibility()?;
    // SAFETY: The ABI returns a process-lifetime NUL-terminated string.
    unsafe {
        let pointer = sys::bg_direct_ewald_composite_v1_profile_id();
        if pointer.is_null() {
            return Err(abi_error("native composite profile id is null"));
        }
        let value = CStr::from_ptr(pointer).to_string_lossy().into_owned();
        if value.is_empty() {
            return Err(abi_error("native composite profile id is empty"));
        }
        Ok(value)
    }
}

fn ensure_composite_abi_compatibility() -> DirectEwaldResult<()> {
    ensure_direct_ewald_abi_compatibility()?;
    // SAFETY: The identity query takes no pointers.
    let observed = unsafe { sys::bg_direct_ewald_composite_abi_version() };
    if observed == sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION {
        Ok(())
    } else {
        Err(abi_error(format!(
            "native composite ABI version {observed} does not match required version {}",
            sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION
        )))
    }
}

fn checked_compatible_lengths(
    system: &System,
    forcefield: &ForceField,
    model: &DirectEwaldModel,
) -> DirectEwaldResult<usize> {
    let count = system.len().map_err(DirectEwaldError::from)?;
    if forcefield.len().map_err(DirectEwaldError::from)? != count || model.len()? != count {
        return Err(DirectEwaldError::from(invalid(
            "composite system, force-field, and model atom counts must match",
        )));
    }
    Ok(count)
}

fn initialized_composite_energy(
) -> DirectEwaldResult<sys::bg_direct_ewald_composite_energy_components_v1> {
    let mut raw = MaybeUninit::<sys::bg_direct_ewald_composite_energy_components_v1>::uninit();
    // SAFETY: raw points to exact-size writable storage.
    plain_status(unsafe {
        sys::bg_direct_ewald_composite_energy_components_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_direct_ewald_composite_energy_components_v1>(),
            sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
        )
    })?;
    // SAFETY: A successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_composite_forces() -> DirectEwaldResult<sys::bg_direct_ewald_composite_force_soa_v1>
{
    let mut raw = MaybeUninit::<sys::bg_direct_ewald_composite_force_soa_v1>::uninit();
    // SAFETY: raw points to exact-size writable storage.
    plain_status(unsafe {
        sys::bg_direct_ewald_composite_force_soa_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_direct_ewald_composite_force_soa_v1>(),
            sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
        )
    })?;
    // SAFETY: A successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn energy_from_raw(
    raw: sys::bg_direct_ewald_composite_energy_components_v1,
) -> DirectEwaldResult<DirectEwaldCompositeEnergyComponents> {
    if raw.struct_size as usize
        != std::mem::size_of::<sys::bg_direct_ewald_composite_energy_components_v1>()
        || raw.abi_version != sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        return Err(abi_error(
            "native composite evaluator returned an invalid energy descriptor",
        ));
    }
    let values = [
        raw.short_harmonic_bond_kcal_per_mol,
        raw.short_harmonic_angle_kcal_per_mol,
        raw.short_periodic_torsion_kcal_per_mol,
        raw.short_lennard_jones_kcal_per_mol,
        raw.short_coulomb_kcal_per_mol,
        raw.short_total_kcal_per_mol,
        raw.ewald_real_space_kcal_per_mol,
        raw.ewald_reciprocal_space_kcal_per_mol,
        raw.ewald_self_kcal_per_mol,
        raw.ewald_pair_correction_kcal_per_mol,
        raw.ewald_total_kcal_per_mol,
        raw.total_kcal_per_mol,
    ];
    if values.iter().any(|value| !value.is_finite()) {
        return Err(abi_error(
            "native composite evaluator returned a non-finite energy",
        ));
    }
    let short_total = raw.short_harmonic_bond_kcal_per_mol
        + raw.short_harmonic_angle_kcal_per_mol
        + raw.short_periodic_torsion_kcal_per_mol
        + raw.short_lennard_jones_kcal_per_mol
        + raw.short_coulomb_kcal_per_mol;
    let ewald_total = raw.ewald_real_space_kcal_per_mol
        + raw.ewald_reciprocal_space_kcal_per_mol
        + raw.ewald_self_kcal_per_mol
        + raw.ewald_pair_correction_kcal_per_mol;
    let total = raw.short_total_kcal_per_mol + raw.ewald_total_kcal_per_mol;
    if raw.short_coulomb_kcal_per_mol.to_bits() != 0
        || short_total.to_bits() != raw.short_total_kcal_per_mol.to_bits()
        || ewald_total.to_bits() != raw.ewald_total_kcal_per_mol.to_bits()
        || total.to_bits() != raw.total_kcal_per_mol.to_bits()
    {
        return Err(abi_error(
            "native composite totals violate the frozen summation order",
        ));
    }
    Ok(DirectEwaldCompositeEnergyComponents {
        short_harmonic_bond_kcal_per_mol: raw.short_harmonic_bond_kcal_per_mol,
        short_harmonic_angle_kcal_per_mol: raw.short_harmonic_angle_kcal_per_mol,
        short_periodic_torsion_kcal_per_mol: raw.short_periodic_torsion_kcal_per_mol,
        short_lennard_jones_kcal_per_mol: raw.short_lennard_jones_kcal_per_mol,
        short_coulomb_kcal_per_mol: raw.short_coulomb_kcal_per_mol,
        short_total_kcal_per_mol: raw.short_total_kcal_per_mol,
        ewald_real_space_kcal_per_mol: raw.ewald_real_space_kcal_per_mol,
        ewald_reciprocal_space_kcal_per_mol: raw.ewald_reciprocal_space_kcal_per_mol,
        ewald_self_kcal_per_mol: raw.ewald_self_kcal_per_mol,
        ewald_pair_correction_kcal_per_mol: raw.ewald_pair_correction_kcal_per_mol,
        ewald_total_kcal_per_mol: raw.ewald_total_kcal_per_mol,
        total_kcal_per_mol: raw.total_kcal_per_mol,
    })
}

fn validate_force_descriptor(
    raw: &sys::bg_direct_ewald_composite_force_soa_v1,
    expected_count: usize,
    expected_x: *mut f64,
    expected_y: *mut f64,
    expected_z: *mut f64,
) -> DirectEwaldResult<()> {
    let expected_count = checked_count(expected_count).map_err(DirectEwaldError::from)?;
    if raw.struct_size as usize
        != std::mem::size_of::<sys::bg_direct_ewald_composite_force_soa_v1>()
        || raw.abi_version != sys::BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION
        || raw.atom_capacity != expected_count
        || raw.atom_count != expected_count
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.x_kcal_per_mol_angstrom != expected_x
        || raw.y_kcal_per_mol_angstrom != expected_y
        || raw.z_kcal_per_mol_angstrom != expected_z
        || raw.reserved != [0; 4]
    {
        Err(abi_error(
            "native composite evaluator returned an invalid force descriptor",
        ))
    } else {
        Ok(())
    }
}

fn mutable_slice_pointer<T>(values: &mut [T]) -> *mut T {
    if values.is_empty() {
        ptr::null_mut()
    } else {
        values.as_mut_ptr()
    }
}

fn fallible_nan_buffer(count: usize, channel: &str) -> DirectEwaldResult<Vec<f64>> {
    if count > (isize::MAX as usize) / std::mem::size_of::<f64>() {
        return Err(DirectEwaldError {
            status: ErrorCode::CapacityOverflow,
            code: None,
            detail: format!("composite {channel}-force capacity exceeds addressable size"),
        });
    }
    let mut values = Vec::new();
    values
        .try_reserve_exact(count)
        .map_err(|_| DirectEwaldError {
            status: ErrorCode::OutOfMemory,
            code: None,
            detail: format!("failed to allocate composite {channel}-force output"),
        })?;
    values.resize(count, f64::NAN);
    Ok(values)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn force_buffer_capacity_overflow_is_distinct_from_allocation_failure() {
        let error = fallible_nan_buffer(usize::MAX, "x")
            .expect_err("an unaddressable force capacity must fail before allocation");
        assert_eq!(error.status, ErrorCode::CapacityOverflow);
        assert_eq!(error.code, None);
    }
}
