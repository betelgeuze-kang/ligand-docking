//! Safe integration for the native direct-real-space plus particle-mesh
//! reciprocal Ewald boundary.

use std::ffi::CStr;
use std::mem::MaybeUninit;
use std::ptr;

use betelgeuze_sys as sys;

use crate::direct_ewald::{
    abi_error, ensure_direct_ewald_abi_compatibility, error_from_call, initialized_error,
    validate_cleared_error, DirectEwaldError, DirectEwaldModel, DirectEwaldResult,
};
use crate::particle_mesh_reciprocal::{
    ensure_particle_mesh_reciprocal_abi_compatibility, ParticleMeshReciprocalError,
    ParticleMeshReciprocalModel,
};
use crate::{checked_count, Backend, Context, Error, ErrorCode, System};

/// Energy components in the ABI's frozen real, reciprocal, self,
/// pair-correction, total order.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct ParticleMeshEwaldEnergyComponents {
    pub real_space_kcal_per_mol: f64,
    pub reciprocal_space_kcal_per_mol: f64,
    pub self_kcal_per_mol: f64,
    pub pair_correction_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
}

/// Owned structure-of-arrays force output from a particle-mesh Ewald call.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct ParticleMeshEwaldForceSoaOwned {
    pub x_kcal_per_mol_angstrom: Vec<f64>,
    pub y_kcal_per_mol_angstrom: Vec<f64>,
    pub z_kcal_per_mol_angstrom: Vec<f64>,
}

/// Owned result of one stateless particle-mesh Ewald evaluation.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct ParticleMeshEwaldEvaluation {
    pub energy: ParticleMeshEwaldEnergyComponents,
    pub forces: ParticleMeshEwaldForceSoaOwned,
}

impl Context {
    /// Evaluate particle-mesh Ewald energy and forces on an explicitly
    /// requested and resolved CPU lane.
    pub fn evaluate_particle_mesh_ewald(
        &self,
        system: &System,
        direct_model: &DirectEwaldModel,
        reciprocal_model: &ParticleMeshReciprocalModel,
    ) -> DirectEwaldResult<ParticleMeshEwaldEvaluation> {
        self.require_particle_mesh_ewald_backend()?;
        ensure_particle_mesh_ewald_abi_compatibility()?;
        let count = checked_compatible_lengths(system, direct_model, reciprocal_model)?;

        let mut force_x = allocate_force_channel(count, "x")?;
        let mut force_y = allocate_force_channel(count, "y")?;
        let mut force_z = allocate_force_channel(count, "z")?;
        let mut raw_energy = initialized_energy()?;
        let mut raw_forces = initialized_forces()?;
        raw_forces.atom_capacity = checked_count(count).map_err(DirectEwaldError::from)?;
        raw_forces.x_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_x);
        raw_forces.y_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_y);
        raw_forces.z_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_z);
        let mut raw_error = initialized_error()?;

        // SAFETY: All four opaque handles are live and thread-confined. The
        // output descriptors and three force channels are writable, mutually
        // disjoint, and remain live for this synchronous call.
        let status = unsafe {
            sys::bg_context_evaluate_particle_mesh_ewald_v1(
                self.raw_handle(),
                system.raw_handle(),
                direct_model.raw_handle(),
                reciprocal_model.raw_handle(),
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
            mutable_slice_pointer(&mut force_x),
            mutable_slice_pointer(&mut force_y),
            mutable_slice_pointer(&mut force_z),
        )?;
        if force_x
            .iter()
            .chain(&force_y)
            .chain(&force_z)
            .any(|value| !value.is_finite())
        {
            return Err(abi_error(
                "native particle-mesh Ewald evaluator returned a non-finite force",
            ));
        }

        Ok(ParticleMeshEwaldEvaluation {
            energy: energy_from_raw(raw_energy)?,
            forces: ParticleMeshEwaldForceSoaOwned {
                x_kcal_per_mol_angstrom: force_x,
                y_kcal_per_mol_angstrom: force_y,
                z_kcal_per_mol_angstrom: force_z,
            },
        })
    }

    /// Evaluate particle-mesh Ewald energy without allocating force output.
    pub fn evaluate_particle_mesh_ewald_energy(
        &self,
        system: &System,
        direct_model: &DirectEwaldModel,
        reciprocal_model: &ParticleMeshReciprocalModel,
    ) -> DirectEwaldResult<ParticleMeshEwaldEnergyComponents> {
        self.require_particle_mesh_ewald_backend()?;
        ensure_particle_mesh_ewald_abi_compatibility()?;
        checked_compatible_lengths(system, direct_model, reciprocal_model)?;
        let mut raw_energy = initialized_energy()?;
        let mut raw_error = initialized_error()?;

        // SAFETY: Every borrowed handle and descriptor is live. A null force
        // descriptor selects the native energy-only path for both parents.
        let status = unsafe {
            sys::bg_context_evaluate_particle_mesh_ewald_v1(
                self.raw_handle(),
                system.raw_handle(),
                direct_model.raw_handle(),
                reciprocal_model.raw_handle(),
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

    fn require_particle_mesh_ewald_backend(&self) -> DirectEwaldResult<()> {
        // The original request is checked before model queries or force
        // allocation. Native AUTO resolution does not authorize this explicit
        // CPU-only safe API.
        require_particle_mesh_ewald_backend(self.requested_backend())?;
        let resolved = self.backend().map_err(DirectEwaldError::from)?;
        require_particle_mesh_ewald_backend(resolved)?;
        if resolved != self.requested_backend() {
            return Err(abi_error(format!(
                "native context resolved {resolved:?} after explicit {:?} request",
                self.requested_backend()
            )));
        }
        Ok(())
    }
}

/// Query the immutable native particle-mesh Ewald profile identity.
pub fn particle_mesh_ewald_profile_id() -> DirectEwaldResult<String> {
    ensure_particle_mesh_ewald_abi_compatibility()?;
    // SAFETY: The ABI returns a process-lifetime NUL-terminated string.
    unsafe {
        let pointer = sys::bg_particle_mesh_ewald_v1_profile_id();
        if pointer.is_null() {
            return Err(abi_error("native particle-mesh Ewald profile id is null"));
        }
        let value = CStr::from_ptr(pointer).to_string_lossy().into_owned();
        if value.is_empty() {
            return Err(abi_error("native particle-mesh Ewald profile id is empty"));
        }
        Ok(value)
    }
}

fn ensure_particle_mesh_ewald_abi_compatibility() -> DirectEwaldResult<()> {
    ensure_direct_ewald_abi_compatibility()?;
    ensure_particle_mesh_reciprocal_abi_compatibility().map_err(direct_error_from_reciprocal)?;
    // SAFETY: The identity query takes no pointers.
    let observed = unsafe { sys::bg_particle_mesh_ewald_abi_version() };
    if observed == sys::BG_PARTICLE_MESH_EWALD_ABI_VERSION {
        Ok(())
    } else {
        Err(abi_error(format!(
            "native particle-mesh Ewald ABI version {observed} does not match required version {}",
            sys::BG_PARTICLE_MESH_EWALD_ABI_VERSION
        )))
    }
}

fn require_particle_mesh_ewald_backend(backend: Backend) -> DirectEwaldResult<()> {
    match backend {
        Backend::CppCpuReference | Backend::RustCpu => Ok(()),
        Backend::Auto | Backend::HipFast | Backend::HipSafe => Err(DirectEwaldError {
            status: ErrorCode::UnsupportedBackend,
            code: None,
            detail: format!(
                "particle-mesh Ewald requires an explicitly requested C++ or Rust CPU backend; {backend:?} cannot fall back"
            ),
        }),
    }
}

fn checked_compatible_lengths(
    system: &System,
    direct_model: &DirectEwaldModel,
    reciprocal_model: &ParticleMeshReciprocalModel,
) -> DirectEwaldResult<usize> {
    let count = system.len().map_err(DirectEwaldError::from)?;
    let direct_count = direct_model.len()?;
    let reciprocal_count = reciprocal_model
        .len()
        .map_err(direct_error_from_reciprocal)?;
    if direct_count != count || reciprocal_count != count {
        return Err(DirectEwaldError {
            status: ErrorCode::InvalidArgument,
            code: None,
            detail: "particle-mesh Ewald system and parent model atom counts must match".to_owned(),
        });
    }
    Ok(count)
}

fn initialized_energy() -> DirectEwaldResult<sys::bg_particle_mesh_ewald_energy_components_v1> {
    let mut raw = MaybeUninit::<sys::bg_particle_mesh_ewald_energy_components_v1>::uninit();
    // SAFETY: raw addresses exact-size writable storage.
    plain_status(unsafe {
        sys::bg_particle_mesh_ewald_energy_components_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_particle_mesh_ewald_energy_components_v1>(),
            sys::BG_PARTICLE_MESH_EWALD_ABI_VERSION,
        )
    })?;
    // SAFETY: A successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn initialized_forces() -> DirectEwaldResult<sys::bg_particle_mesh_ewald_force_soa_v1> {
    let mut raw = MaybeUninit::<sys::bg_particle_mesh_ewald_force_soa_v1>::uninit();
    // SAFETY: raw addresses exact-size writable storage.
    plain_status(unsafe {
        sys::bg_particle_mesh_ewald_force_soa_v1_init(
            raw.as_mut_ptr(),
            std::mem::size_of::<sys::bg_particle_mesh_ewald_force_soa_v1>(),
            sys::BG_PARTICLE_MESH_EWALD_ABI_VERSION,
        )
    })?;
    // SAFETY: A successful initializer writes every field.
    Ok(unsafe { raw.assume_init() })
}

fn plain_status(status: sys::bg_status) -> DirectEwaldResult<()> {
    if status == sys::BG_STATUS_OK {
        Ok(())
    } else {
        Err(DirectEwaldError::from(Error::native(status)))
    }
}

fn energy_from_raw(
    raw: sys::bg_particle_mesh_ewald_energy_components_v1,
) -> DirectEwaldResult<ParticleMeshEwaldEnergyComponents> {
    if raw.struct_size as usize
        != std::mem::size_of::<sys::bg_particle_mesh_ewald_energy_components_v1>()
        || raw.abi_version != sys::BG_PARTICLE_MESH_EWALD_ABI_VERSION
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        return Err(abi_error(
            "native particle-mesh Ewald evaluator returned an invalid energy descriptor",
        ));
    }
    let values = [
        raw.real_space_kcal_per_mol,
        raw.reciprocal_space_kcal_per_mol,
        raw.self_kcal_per_mol,
        raw.pair_correction_kcal_per_mol,
        raw.total_kcal_per_mol,
    ];
    if values.iter().any(|value| !value.is_finite()) {
        return Err(abi_error(
            "native particle-mesh Ewald evaluator returned a non-finite energy",
        ));
    }
    let total = raw.real_space_kcal_per_mol
        + raw.reciprocal_space_kcal_per_mol
        + raw.self_kcal_per_mol
        + raw.pair_correction_kcal_per_mol;
    if total.to_bits() != raw.total_kcal_per_mol.to_bits() {
        return Err(abi_error(
            "native particle-mesh Ewald total violates the frozen component summation order",
        ));
    }

    Ok(ParticleMeshEwaldEnergyComponents {
        real_space_kcal_per_mol: raw.real_space_kcal_per_mol,
        reciprocal_space_kcal_per_mol: raw.reciprocal_space_kcal_per_mol,
        self_kcal_per_mol: raw.self_kcal_per_mol,
        pair_correction_kcal_per_mol: raw.pair_correction_kcal_per_mol,
        total_kcal_per_mol: raw.total_kcal_per_mol,
    })
}

fn validate_force_descriptor(
    raw: &sys::bg_particle_mesh_ewald_force_soa_v1,
    expected_count: usize,
    expected_x: *mut f64,
    expected_y: *mut f64,
    expected_z: *mut f64,
) -> DirectEwaldResult<()> {
    let expected_count = checked_count(expected_count).map_err(DirectEwaldError::from)?;
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_particle_mesh_ewald_force_soa_v1>()
        || raw.abi_version != sys::BG_PARTICLE_MESH_EWALD_ABI_VERSION
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
            "native particle-mesh Ewald evaluator returned an invalid force descriptor",
        ))
    } else {
        Ok(())
    }
}

fn allocate_force_channel(count: usize, channel: &str) -> DirectEwaldResult<Vec<f64>> {
    if count > (isize::MAX as usize) / std::mem::size_of::<f64>() {
        return Err(DirectEwaldError {
            status: ErrorCode::CapacityOverflow,
            code: None,
            detail: format!(
                "particle-mesh Ewald {channel}-force capacity exceeds addressable size"
            ),
        });
    }
    let mut values = Vec::new();
    values
        .try_reserve_exact(count)
        .map_err(|_| DirectEwaldError {
            status: ErrorCode::OutOfMemory,
            code: None,
            detail: format!("failed to allocate particle-mesh Ewald {channel}-force output"),
        })?;
    values.resize(count, f64::NAN);
    Ok(values)
}

fn mutable_slice_pointer<T>(values: &mut [T]) -> *mut T {
    if values.is_empty() {
        ptr::null_mut()
    } else {
        values.as_mut_ptr()
    }
}

fn direct_error_from_reciprocal(error: ParticleMeshReciprocalError) -> DirectEwaldError {
    DirectEwaldError {
        status: error.status,
        code: None,
        detail: error.detail.into_owned(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unsupported_lanes_fail_closed() {
        for backend in [Backend::Auto, Backend::HipFast, Backend::HipSafe] {
            let error = require_particle_mesh_ewald_backend(backend).unwrap_err();
            assert_eq!(error.status, ErrorCode::UnsupportedBackend);
            assert_eq!(error.code, None);
            assert!(error.detail.contains("cannot fall back"));
        }
        require_particle_mesh_ewald_backend(Backend::CppCpuReference).unwrap();
        require_particle_mesh_ewald_backend(Backend::RustCpu).unwrap();
    }

    #[test]
    fn force_buffer_capacity_overflow_is_distinct_from_allocation_failure() {
        let error = allocate_force_channel(usize::MAX, "x")
            .expect_err("an unaddressable force capacity must fail before allocation");
        assert_eq!(error.status, ErrorCode::CapacityOverflow);
        assert_eq!(error.code, None);
    }
}
