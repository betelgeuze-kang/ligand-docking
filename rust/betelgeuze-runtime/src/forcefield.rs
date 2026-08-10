use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::{self, NonNull};
use std::rc::Rc;

use betelgeuze_sys as sys;

use crate::{
    checked_count, ensure_abi_compatibility, invalid, status_result, Context, Error, ErrorCode,
    Result, System,
};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct AtomNonbonded {
    pub sigma_angstrom: f64,
    pub epsilon_kcal_per_mol: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HarmonicBond {
    pub atom_i: usize,
    pub atom_j: usize,
    pub equilibrium_angstrom: f64,
    pub force_constant_kcal_per_mol_angstrom2: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HarmonicAngle {
    pub atom_i: usize,
    pub atom_j: usize,
    pub atom_k: usize,
    pub equilibrium_radians: f64,
    pub force_constant_kcal_per_mol_radian2: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PeriodicTorsion {
    pub atom_i: usize,
    pub atom_j: usize,
    pub atom_k: usize,
    pub atom_l: usize,
    pub periodicity: u32,
    pub phase_radians: f64,
    pub amplitude_kcal_per_mol: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PairExclusion {
    pub atom_i: usize,
    pub atom_j: usize,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PairScale {
    pub atom_i: usize,
    pub atom_j: usize,
    pub lennard_jones_scale: f64,
    pub coulomb_scale: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OrthorhombicCell {
    pub lengths_angstrom: [f64; 3],
    pub periodic_axes: [bool; 3],
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct NonbondedSettings {
    pub cutoff_angstrom: f64,
    pub switch_start_angstrom: f64,
    pub dielectric: f64,
    pub screening_kappa_per_angstrom: f64,
    pub minimum_pair_distance_angstrom: f64,
}

impl Default for NonbondedSettings {
    fn default() -> Self {
        Self {
            cutoff_angstrom: 10.0,
            switch_start_angstrom: 8.0,
            dielectric: 1.0,
            screening_kappa_per_angstrom: 0.0,
            minimum_pair_distance_angstrom: 1.0e-6,
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct ForceFieldInput<'a> {
    pub atom_nonbonded: &'a [AtomNonbonded],
    pub bonds: &'a [HarmonicBond],
    pub angles: &'a [HarmonicAngle],
    pub torsions: &'a [PeriodicTorsion],
    pub exclusions: &'a [PairExclusion],
    pub pair_scales: &'a [PairScale],
    pub cell: Option<OrthorhombicCell>,
    pub nonbonded: NonbondedSettings,
}

impl<'a> ForceFieldInput<'a> {
    #[must_use]
    pub const fn new(atom_nonbonded: &'a [AtomNonbonded]) -> Self {
        Self {
            atom_nonbonded,
            bonds: &[],
            angles: &[],
            torsions: &[],
            exclusions: &[],
            pair_scales: &[],
            cell: None,
            nonbonded: NonbondedSettings {
                cutoff_angstrom: 10.0,
                switch_start_angstrom: 8.0,
                dielectric: 1.0,
                screening_kappa_per_angstrom: 0.0,
                minimum_pair_distance_angstrom: 1.0e-6,
            },
        }
    }
}

pub struct ForceField {
    handle: NonNull<sys::bg_forcefield>,
    _not_send_or_sync: PhantomData<Rc<()>>,
}

impl ForceField {
    pub fn new(input: ForceFieldInput<'_>) -> Result<Self> {
        ensure_abi_compatibility()?;
        if input.atom_nonbonded.is_empty() {
            return Err(invalid("a force field requires at least one atom"));
        }
        let atom_count = checked_count(input.atom_nonbonded.len())?;

        let sigma: Vec<_> = input
            .atom_nonbonded
            .iter()
            .map(|atom| atom.sigma_angstrom)
            .collect();
        let epsilon: Vec<_> = input
            .atom_nonbonded
            .iter()
            .map(|atom| atom.epsilon_kcal_per_mol)
            .collect();

        let bond_i = index_channel(input.bonds.iter().map(|row| row.atom_i))?;
        let bond_j = index_channel(input.bonds.iter().map(|row| row.atom_j))?;
        let bond_equilibrium: Vec<_> = input
            .bonds
            .iter()
            .map(|row| row.equilibrium_angstrom)
            .collect();
        let bond_force: Vec<_> = input
            .bonds
            .iter()
            .map(|row| row.force_constant_kcal_per_mol_angstrom2)
            .collect();

        let angle_i = index_channel(input.angles.iter().map(|row| row.atom_i))?;
        let angle_j = index_channel(input.angles.iter().map(|row| row.atom_j))?;
        let angle_k = index_channel(input.angles.iter().map(|row| row.atom_k))?;
        let angle_equilibrium: Vec<_> = input
            .angles
            .iter()
            .map(|row| row.equilibrium_radians)
            .collect();
        let angle_force: Vec<_> = input
            .angles
            .iter()
            .map(|row| row.force_constant_kcal_per_mol_radian2)
            .collect();

        let torsion_i = index_channel(input.torsions.iter().map(|row| row.atom_i))?;
        let torsion_j = index_channel(input.torsions.iter().map(|row| row.atom_j))?;
        let torsion_k = index_channel(input.torsions.iter().map(|row| row.atom_k))?;
        let torsion_l = index_channel(input.torsions.iter().map(|row| row.atom_l))?;
        let torsion_periodicity: Vec<_> =
            input.torsions.iter().map(|row| row.periodicity).collect();
        let torsion_phase: Vec<_> = input.torsions.iter().map(|row| row.phase_radians).collect();
        let torsion_amplitude: Vec<_> = input
            .torsions
            .iter()
            .map(|row| row.amplitude_kcal_per_mol)
            .collect();

        let exclusion_i = index_channel(input.exclusions.iter().map(|row| row.atom_i))?;
        let exclusion_j = index_channel(input.exclusions.iter().map(|row| row.atom_j))?;
        let pair_scale_i = index_channel(input.pair_scales.iter().map(|row| row.atom_i))?;
        let pair_scale_j = index_channel(input.pair_scales.iter().map(|row| row.atom_j))?;
        let pair_scale_lj: Vec<_> = input
            .pair_scales
            .iter()
            .map(|row| row.lennard_jones_scale)
            .collect();
        let pair_scale_coulomb: Vec<_> = input
            .pair_scales
            .iter()
            .map(|row| row.coulomb_scale)
            .collect();

        let mut raw = MaybeUninit::<sys::bg_forcefield_soa_v1>::uninit();
        // SAFETY: raw points to correctly sized writable storage.
        status_result(unsafe { sys::bg_forcefield_soa_v1_init(raw.as_mut_ptr()) })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw = unsafe { raw.assume_init() };
        raw.atom_count = atom_count;
        raw.sigma_angstrom = slice_pointer(&sigma);
        raw.epsilon_kcal_per_mol = slice_pointer(&epsilon);

        raw.bond_count = checked_count(input.bonds.len())?;
        raw.bond_atom_i = slice_pointer(&bond_i);
        raw.bond_atom_j = slice_pointer(&bond_j);
        raw.bond_equilibrium_angstrom = slice_pointer(&bond_equilibrium);
        raw.bond_force_constant_kcal_per_mol_angstrom2 = slice_pointer(&bond_force);

        raw.angle_count = checked_count(input.angles.len())?;
        raw.angle_atom_i = slice_pointer(&angle_i);
        raw.angle_atom_j = slice_pointer(&angle_j);
        raw.angle_atom_k = slice_pointer(&angle_k);
        raw.angle_equilibrium_radians = slice_pointer(&angle_equilibrium);
        raw.angle_force_constant_kcal_per_mol_radian2 = slice_pointer(&angle_force);

        raw.torsion_count = checked_count(input.torsions.len())?;
        raw.torsion_atom_i = slice_pointer(&torsion_i);
        raw.torsion_atom_j = slice_pointer(&torsion_j);
        raw.torsion_atom_k = slice_pointer(&torsion_k);
        raw.torsion_atom_l = slice_pointer(&torsion_l);
        raw.torsion_periodicity = slice_pointer(&torsion_periodicity);
        raw.torsion_phase_radians = slice_pointer(&torsion_phase);
        raw.torsion_amplitude_kcal_per_mol = slice_pointer(&torsion_amplitude);

        raw.exclusion_count = checked_count(input.exclusions.len())?;
        raw.exclusion_atom_i = slice_pointer(&exclusion_i);
        raw.exclusion_atom_j = slice_pointer(&exclusion_j);
        raw.pair_scale_count = checked_count(input.pair_scales.len())?;
        raw.pair_scale_atom_i = slice_pointer(&pair_scale_i);
        raw.pair_scale_atom_j = slice_pointer(&pair_scale_j);
        raw.pair_scale_lennard_jones = slice_pointer(&pair_scale_lj);
        raw.pair_scale_coulomb = slice_pointer(&pair_scale_coulomb);

        if let Some(cell) = input.cell {
            let axes_mask = periodic_axes_mask(cell.periodic_axes);
            raw.cell_lengths_angstrom = cell.lengths_angstrom;
            raw.periodic_axes_mask = axes_mask;
        }
        raw.cutoff_angstrom = input.nonbonded.cutoff_angstrom;
        raw.switch_start_angstrom = input.nonbonded.switch_start_angstrom;
        raw.dielectric = input.nonbonded.dielectric;
        raw.screening_kappa_per_angstrom = input.nonbonded.screening_kappa_per_angstrom;
        raw.minimum_pair_distance_angstrom = input.nonbonded.minimum_pair_distance_angstrom;

        let mut handle = ptr::null_mut();
        // SAFETY: Every temporary channel remains live through this call. The
        // native handle deep-copies all channels before returning.
        status_result(unsafe { sys::bg_forcefield_create(&raw, &mut handle) })?;
        let handle = NonNull::new(handle).ok_or_else(|| {
            Error::local(
                ErrorCode::InternalError,
                "native force-field creation returned a null handle",
            )
        })?;
        Ok(Self {
            handle,
            _not_send_or_sync: PhantomData,
        })
    }

    pub fn len(&self) -> Result<usize> {
        let mut count = 0_u64;
        // SAFETY: The private handle is live and count is writable.
        status_result(unsafe {
            sys::bg_forcefield_get_atom_count(self.handle.as_ptr(), &mut count)
        })?;
        usize::try_from(count).map_err(|_| {
            Error::local(
                ErrorCode::CapacityOverflow,
                "native force-field atom count exceeds usize",
            )
        })
    }

    pub fn is_empty(&self) -> Result<bool> {
        self.len().map(|length| length == 0)
    }

    pub(crate) fn raw_handle(&self) -> *mut sys::bg_forcefield {
        self.handle.as_ptr()
    }
}

impl Drop for ForceField {
    fn drop(&mut self) {
        // SAFETY: ForceField owns this non-null handle and destroys it once.
        unsafe { sys::bg_forcefield_destroy(self.handle.as_ptr()) };
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct EnergyComponents {
    pub harmonic_bond_kcal_per_mol: f64,
    pub harmonic_angle_kcal_per_mol: f64,
    pub periodic_torsion_kcal_per_mol: f64,
    pub lennard_jones_kcal_per_mol: f64,
    pub coulomb_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct ForceSoaOwned {
    pub x_kcal_per_mol_angstrom: Vec<f64>,
    pub y_kcal_per_mol_angstrom: Vec<f64>,
    pub z_kcal_per_mol_angstrom: Vec<f64>,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Evaluation {
    pub energy: EnergyComponents,
    pub forces: ForceSoaOwned,
}

impl Context {
    pub fn evaluate(&self, system: &System, forcefield: &ForceField) -> Result<Evaluation> {
        let count = system.len()?;
        if forcefield.len()? != count {
            return Err(invalid("force-field atom count must match the system"));
        }
        let mut force_x = vec![0.0; count];
        let mut force_y = vec![0.0; count];
        let mut force_z = vec![0.0; count];

        let mut raw_energy = initialized_energy()?;
        let mut raw_forces = MaybeUninit::<sys::bg_force_soa_v1>::uninit();
        // SAFETY: raw_forces points to correctly sized writable storage.
        status_result(unsafe { sys::bg_force_soa_v1_init(raw_forces.as_mut_ptr()) })?;
        // SAFETY: The successful initializer wrote every field.
        let mut raw_forces = unsafe { raw_forces.assume_init() };
        raw_forces.particle_capacity = checked_count(count)?;
        raw_forces.x_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_x);
        raw_forces.y_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_y);
        raw_forces.z_kcal_per_mol_angstrom = mutable_slice_pointer(&mut force_z);

        // SAFETY: All three opaque handles are live, descriptors are initialized,
        // and force buffers remain writable for the duration of the call.
        status_result(unsafe {
            sys::bg_context_evaluate(
                self.handle.as_ptr(),
                system.handle.as_ptr(),
                forcefield.handle.as_ptr(),
                &mut raw_energy,
                &mut raw_forces,
            )
        })?;
        if raw_forces.particle_count != checked_count(count)? {
            return Err(Error::local(
                ErrorCode::InternalError,
                "native evaluator returned an inconsistent force count",
            ));
        }
        Ok(Evaluation {
            energy: energy_from_raw(raw_energy)?,
            forces: ForceSoaOwned {
                x_kcal_per_mol_angstrom: force_x,
                y_kcal_per_mol_angstrom: force_y,
                z_kcal_per_mol_angstrom: force_z,
            },
        })
    }

    pub fn evaluate_energy(
        &self,
        system: &System,
        forcefield: &ForceField,
    ) -> Result<EnergyComponents> {
        if forcefield.len()? != system.len()? {
            return Err(invalid("force-field atom count must match the system"));
        }
        let mut raw_energy = initialized_energy()?;
        // SAFETY: Handles are live, the energy descriptor is writable, and a
        // null force descriptor explicitly requests energy-only output.
        status_result(unsafe {
            sys::bg_context_evaluate(
                self.handle.as_ptr(),
                system.handle.as_ptr(),
                forcefield.handle.as_ptr(),
                &mut raw_energy,
                ptr::null_mut(),
            )
        })?;
        energy_from_raw(raw_energy)
    }
}

fn initialized_energy() -> Result<sys::bg_energy_components_v1> {
    let mut raw = MaybeUninit::<sys::bg_energy_components_v1>::uninit();
    // SAFETY: raw points to correctly sized writable storage.
    status_result(unsafe { sys::bg_energy_components_v1_init(raw.as_mut_ptr()) })?;
    // SAFETY: The successful initializer wrote every field.
    Ok(unsafe { raw.assume_init() })
}

fn energy_from_raw(raw: sys::bg_energy_components_v1) -> Result<EnergyComponents> {
    if raw.struct_size as usize != std::mem::size_of::<sys::bg_energy_components_v1>()
        || raw.abi_version != sys::BG_ABI_VERSION
        || raw.unit_system != sys::BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || raw.reserved0 != 0
        || raw.reserved != [0; 4]
    {
        return Err(Error::local(
            ErrorCode::AbiMismatch,
            "native evaluator returned an invalid energy descriptor",
        ));
    }
    let values = [
        raw.harmonic_bond_kcal_per_mol,
        raw.harmonic_angle_kcal_per_mol,
        raw.periodic_torsion_kcal_per_mol,
        raw.lennard_jones_kcal_per_mol,
        raw.coulomb_kcal_per_mol,
        raw.total_kcal_per_mol,
    ];
    if values.iter().any(|value| !value.is_finite()) {
        return Err(Error::local(
            ErrorCode::InternalError,
            "native evaluator returned a non-finite energy",
        ));
    }
    Ok(EnergyComponents {
        harmonic_bond_kcal_per_mol: raw.harmonic_bond_kcal_per_mol,
        harmonic_angle_kcal_per_mol: raw.harmonic_angle_kcal_per_mol,
        periodic_torsion_kcal_per_mol: raw.periodic_torsion_kcal_per_mol,
        lennard_jones_kcal_per_mol: raw.lennard_jones_kcal_per_mol,
        coulomb_kcal_per_mol: raw.coulomb_kcal_per_mol,
        total_kcal_per_mol: raw.total_kcal_per_mol,
    })
}

fn periodic_axes_mask(axes: [bool; 3]) -> u32 {
    let mut mask = 0_u32;
    if axes[0] {
        mask |= sys::BG_PERIODIC_AXIS_X;
    }
    if axes[1] {
        mask |= sys::BG_PERIODIC_AXIS_Y;
    }
    if axes[2] {
        mask |= sys::BG_PERIODIC_AXIS_Z;
    }
    mask
}

fn index_channel(indices: impl Iterator<Item = usize>) -> Result<Vec<u64>> {
    indices
        .map(|index| {
            u64::try_from(index).map_err(|_| invalid("atom index does not fit native uint64"))
        })
        .collect()
}

fn slice_pointer<T>(values: &[T]) -> *const T {
    if values.is_empty() {
        ptr::null()
    } else {
        values.as_ptr()
    }
}

fn mutable_slice_pointer<T>(values: &mut [T]) -> *mut T {
    if values.is_empty() {
        ptr::null_mut()
    } else {
        values.as_mut_ptr()
    }
}
