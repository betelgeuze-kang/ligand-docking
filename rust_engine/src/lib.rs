use pyo3::prelude::*;
use std::os::raw::{c_int, c_float};

#[link(name = "nonbonded_kernel")]
extern "C" {
    fn launch_nonbonded_kernel(
        pos: *const f32,
        force: *mut f32,
        energy: *mut f32,
        n_per_replica: c_int,
        total_atoms: c_int,
        box_size: c_float,
        sigma: c_float,
        epsilon: c_float,
    ) -> c_int;
    fn launch_nonbonded_nblist_kernel(
        pos: *const f32,
        nb_idx: *const i64,
        nb_mask: *const u8,
        force: *mut f32,
        energy: *mut f32,
        n_per_replica: c_int,
        total_atoms: c_int,
        max_neighbors: c_int,
        box_size: c_float,
        sigma: c_float,
        epsilon: c_float,
    ) -> c_int;
    fn launch_nonbonded_fused_cell_kernel(
        pos: *const f32,
        cell_counts: *mut c_int,
        cell_atoms: *mut c_int,
        force: *mut f32,
        energy: *mut f32,
        n_per_replica: c_int,
        total_atoms: c_int,
        box_size: c_float,
        cutoff: c_float,
        gx: c_int,
        gy: c_int,
        gz: c_int,
        max_atoms_per_cell: c_int,
        sigma: c_float,
        epsilon: c_float,
    ) -> c_int;
    fn launch_build_neighbor_list_kernel(
        pos: *const f32,
        cell_counts: *mut c_int,
        cell_atoms: *mut c_int,
        nb_idx: *mut i64,
        nb_dist: *mut c_float,
        nb_mask: *mut u8,
        n_per_replica: c_int,
        total_atoms: c_int,
        box_size: c_float,
        cutoff: c_float,
        gx: c_int,
        gy: c_int,
        gz: c_int,
        max_atoms_per_cell: c_int,
        max_neighbors: c_int,
    ) -> c_int;
    fn launch_ligand_direct_rollout_kernel(
        pos: *mut f32,
        vel: *mut f32,
        force: *mut f32,
        energy: *mut f32,
        selected_out: *mut f32,
        pocket: *const f32,
        pocket_attract: *const f32,
        protein_repulse: *const f32,
        bond_ref: *const f32,
        noise: *const f32,
        n_per_replica: c_int,
        batch_size: c_int,
        n_protein: c_int,
        n_ligand: c_int,
        frames: c_int,
        keep_steps: *const c_int,
        n_keep: c_int,
        box_size: c_float,
        sigma: c_float,
        epsilon: c_float,
        bond_k: c_float,
        repulse_cutoff: c_float,
        max_pocket_radius: c_float,
        force_clip: c_float,
        dt: c_float,
        gamma: c_float,
    ) -> c_int;
    fn launch_idp_virtual_hbond_nblist_kernel(
        donor: *const f32,
        acceptor: *const f32,
        ca: *const f32,
        sc: *const f32,
        disorder: *const f32,
        aromatic_mask: *const u8,
        cationic_mask: *const u8,
        sticker_mask: *const u8,
        local_density: *mut f32,
        nb_idx: *const i64,
        nb_dist: *const f32,
        nb_mask: *const u8,
        force: *mut f32,
        contacts: *mut f32,
        mean_distance: *mut f32,
        n_per_replica: c_int,
        batch_size: c_int,
        max_neighbors: c_int,
        center: *const f32,
        width: *const f32,
        vh_strength: *const f32,
        env_scale: *const f32,
        vh_scale: *const f32,
        contact_gain: *const f32,
        exposure_sensitivity: *const f32,
        exposure_gain_scale: *const f32,
        llps_branch: *const f32,
        is_llps_target: *const f32,
        is_hnrn_target: *const f32,
        is_fus_target: *const f32,
        unsat_penalty: *const f32,
        stream_ptr: usize,
    ) -> c_int;
    fn launch_idp_local_density_nblist_kernel(
        nb_idx: *const i64,
        nb_dist: *const f32,
        nb_mask: *const u8,
        out_density: *mut f32,
        n_per_replica: c_int,
        batch_size: c_int,
        max_neighbors: c_int,
        min_gap: c_int,
    ) -> c_int;
    fn launch_idp_sticker_bridge_nblist_kernel(
        ca: *const f32,
        sc: *const f32,
        aromatic_mask: *const u8,
        cationic_mask: *const u8,
        sticker_mask: *const u8,
        local_density: *mut f32,
        nb_idx: *const i64,
        nb_dist: *const f32,
        nb_mask: *const u8,
        sticker_force: *mut f32,
        bridge_force: *mut f32,
        sticker_contacts: *mut f32,
        pi_pi_contacts: *mut f32,
        cation_pi_contacts: *mut f32,
        bridge_contacts: *mut f32,
        n_per_replica: c_int,
        batch_size: c_int,
        max_neighbors: c_int,
        sticker_strength: *const f32,
        bridge_strength: *const f32,
        env_scale: *const f32,
        llps_branch: *const f32,
        agg_branch: *const f32,
        helix_branch: *const f32,
        is_llps_target: *const f32,
        is_hnrn_target: *const f32,
        is_fus_target: *const f32,
        arg_fraction: *const f32,
        aromatic_fraction: *const f32,
        collect_contacts: c_int,
        stream_ptr: usize,
    ) -> c_int;
}

#[pyfunction]
fn hip_add(a: Vec<f32>, b: Vec<f32>) -> PyResult<Vec<f32>> {
    if a.len() != b.len() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "input vectors must have identical length",
        ));
    }
    Ok(a.iter().zip(b.iter()).map(|(x, y)| x + y).collect())
}

#[pyfunction]
fn compute_nonbonded_gpu(
    pos_ptr: usize,
    force_ptr: usize,
    energy_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    box_size: f32,
    sigma: f32,
    epsilon: f32,
) -> PyResult<()> {
    if pos_ptr == 0 || force_ptr == 0 || energy_ptr == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }
    
    unsafe {
        let total_atoms = n_per_replica * batch_size;
        let status = launch_nonbonded_kernel(
            pos_ptr as *const f32,
            force_ptr as *mut f32,
            energy_ptr as *mut f32,
            n_per_replica as c_int,
            total_atoms as c_int,
            box_size,
            sigma,
            epsilon,
        );
        
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn compute_nonbonded_nblist_gpu(
    pos_ptr: usize,
    nb_idx_ptr: usize,
    nb_mask_ptr: usize,
    force_ptr: usize,
    energy_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    max_neighbors: usize,
    box_size: f32,
    sigma: f32,
    epsilon: f32,
) -> PyResult<()> {
    if pos_ptr == 0 || nb_idx_ptr == 0 || force_ptr == 0 || energy_ptr == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }

    unsafe {
        let total_atoms = n_per_replica * batch_size;
        let status = launch_nonbonded_nblist_kernel(
            pos_ptr as *const f32,
            nb_idx_ptr as *const i64,
            nb_mask_ptr as *const u8,
            force_ptr as *mut f32,
            energy_ptr as *mut f32,
            n_per_replica as c_int,
            total_atoms as c_int,
            max_neighbors as c_int,
            box_size,
            sigma,
            epsilon,
        );

        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP nblist kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn build_neighbor_list_gpu(
    pos_ptr: usize,
    cell_counts_ptr: usize,
    cell_atoms_ptr: usize,
    nb_idx_ptr: usize,
    nb_dist_ptr: usize,
    nb_mask_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    box_size: f32,
    cutoff: f32,
    gx: usize,
    gy: usize,
    gz: usize,
    max_atoms_per_cell: usize,
    max_neighbors: usize,
) -> PyResult<()> {
    if pos_ptr == 0 || cell_counts_ptr == 0 || cell_atoms_ptr == 0 || nb_idx_ptr == 0 || nb_dist_ptr == 0 || nb_mask_ptr == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }
    if cutoff <= 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err("cutoff must be > 0"));
    }

    unsafe {
        let total_atoms = n_per_replica * batch_size;
        let status = launch_build_neighbor_list_kernel(
            pos_ptr as *const f32,
            cell_counts_ptr as *mut c_int,
            cell_atoms_ptr as *mut c_int,
            nb_idx_ptr as *mut i64,
            nb_dist_ptr as *mut c_float,
            nb_mask_ptr as *mut u8,
            n_per_replica as c_int,
            total_atoms as c_int,
            box_size,
            cutoff,
            gx as c_int,
            gy as c_int,
            gz as c_int,
            max_atoms_per_cell as c_int,
            max_neighbors as c_int,
        );
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP neighbor-list kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn compute_nonbonded_celllist_gpu(
    pos_ptr: usize,
    cell_counts_ptr: usize,
    cell_atoms_ptr: usize,
    force_ptr: usize,
    energy_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    box_size: f32,
    cutoff: f32,
    gx: usize,
    gy: usize,
    gz: usize,
    max_atoms_per_cell: usize,
    sigma: f32,
    epsilon: f32,
) -> PyResult<()> {
    if pos_ptr == 0 || cell_counts_ptr == 0 || cell_atoms_ptr == 0 || force_ptr == 0 || energy_ptr == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }
    if cutoff <= 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err("cutoff must be > 0"));
    }

    unsafe {
        let total_atoms = n_per_replica * batch_size;
        let status = launch_nonbonded_fused_cell_kernel(
            pos_ptr as *const f32,
            cell_counts_ptr as *mut c_int,
            cell_atoms_ptr as *mut c_int,
            force_ptr as *mut f32,
            energy_ptr as *mut f32,
            n_per_replica as c_int,
            total_atoms as c_int,
            box_size,
            cutoff,
            gx as c_int,
            gy as c_int,
            gz as c_int,
            max_atoms_per_cell as c_int,
            sigma,
            epsilon,
        );
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP fused cell kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn rollout_ligand_direct_gpu(
    pos_ptr: usize,
    vel_ptr: usize,
    force_ptr: usize,
    energy_ptr: usize,
    selected_ptr: usize,
    pocket_ptr: usize,
    pocket_attr_ptr: usize,
    protein_repulse_ptr: usize,
    bond_ref_ptr: usize,
    noise_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    n_protein: usize,
    n_ligand: usize,
    frames: usize,
    keep_steps: Vec<usize>,
    box_size: f32,
    sigma: f32,
    epsilon: f32,
    bond_k: f32,
    repulse_cutoff: f32,
    max_pocket_radius: f32,
    force_clip: f32,
    dt: f32,
    gamma: f32,
) -> PyResult<()> {
    if pos_ptr == 0
        || vel_ptr == 0
        || force_ptr == 0
        || energy_ptr == 0
        || selected_ptr == 0
        || pocket_ptr == 0
        || pocket_attr_ptr == 0
        || protein_repulse_ptr == 0
        || bond_ref_ptr == 0
    {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }
    if keep_steps.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("keep_steps must be non-empty"));
    }

    let keep_steps_i32: Vec<c_int> = keep_steps
        .iter()
        .map(|&x| c_int::try_from(x).unwrap_or(c_int::MAX))
        .collect();
    let noise_ptr_final = if noise_ptr == 0 { std::ptr::null() } else { noise_ptr as *const f32 };

    unsafe {
        let status = launch_ligand_direct_rollout_kernel(
            pos_ptr as *mut f32,
            vel_ptr as *mut f32,
            force_ptr as *mut f32,
            energy_ptr as *mut f32,
            selected_ptr as *mut f32,
            pocket_ptr as *const f32,
            pocket_attr_ptr as *const f32,
            protein_repulse_ptr as *const f32,
            bond_ref_ptr as *const f32,
            noise_ptr_final,
            n_per_replica as c_int,
            batch_size as c_int,
            n_protein as c_int,
            n_ligand as c_int,
            frames as c_int,
            keep_steps_i32.as_ptr(),
            keep_steps_i32.len() as c_int,
            box_size,
            sigma,
            epsilon,
            bond_k,
            repulse_cutoff,
            max_pocket_radius,
            force_clip,
            dt,
            gamma,
        );
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP direct rollout kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn compute_idp_local_density_nblist_gpu(
    nb_idx_ptr: usize,
    nb_dist_ptr: usize,
    nb_mask_ptr: usize,
    out_density_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    max_neighbors: usize,
    min_gap: usize,
) -> PyResult<()> {
    if nb_idx_ptr == 0 || nb_dist_ptr == 0 || nb_mask_ptr == 0 || out_density_ptr == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }
    unsafe {
        let status = launch_idp_local_density_nblist_kernel(
            nb_idx_ptr as *const i64,
            nb_dist_ptr as *const f32,
            nb_mask_ptr as *const u8,
            out_density_ptr as *mut f32,
            n_per_replica as c_int,
            batch_size as c_int,
            max_neighbors as c_int,
            min_gap as c_int,
        );
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP IDP local_density kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn compute_idp_sticker_bridge_nblist_gpu(
    ca_ptr: usize,
    sc_ptr: usize,
    aromatic_mask_ptr: usize,
    cationic_mask_ptr: usize,
    sticker_mask_ptr: usize,
    local_density_ptr: usize,
    nb_idx_ptr: usize,
    nb_dist_ptr: usize,
    nb_mask_ptr: usize,
    sticker_force_ptr: usize,
    bridge_force_ptr: usize,
    sticker_contacts_ptr: usize,
    pi_pi_contacts_ptr: usize,
    cation_pi_contacts_ptr: usize,
    bridge_contacts_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    max_neighbors: usize,
    sticker_strength_ptr: usize,
    bridge_strength_ptr: usize,
    env_scale_ptr: usize,
    llps_branch_ptr: usize,
    agg_branch_ptr: usize,
    helix_branch_ptr: usize,
    is_llps_target_ptr: usize,
    is_hnrn_target_ptr: usize,
    is_fus_target_ptr: usize,
    arg_fraction_ptr: usize,
    aromatic_fraction_ptr: usize,
    collect_contacts: usize,
    stream_ptr: usize,
) -> PyResult<()> {
    if ca_ptr == 0
        || sc_ptr == 0
        || aromatic_mask_ptr == 0
        || cationic_mask_ptr == 0
        || sticker_mask_ptr == 0
        || local_density_ptr == 0
        || nb_idx_ptr == 0
        || nb_dist_ptr == 0
        || nb_mask_ptr == 0
        || sticker_force_ptr == 0
        || bridge_force_ptr == 0
        || sticker_contacts_ptr == 0
        || pi_pi_contacts_ptr == 0
        || cation_pi_contacts_ptr == 0
        || bridge_contacts_ptr == 0
        || sticker_strength_ptr == 0
        || bridge_strength_ptr == 0
        || env_scale_ptr == 0
        || llps_branch_ptr == 0
        || agg_branch_ptr == 0
        || helix_branch_ptr == 0
        || is_llps_target_ptr == 0
        || is_hnrn_target_ptr == 0
        || is_fus_target_ptr == 0
        || arg_fraction_ptr == 0
        || aromatic_fraction_ptr == 0
    {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }
    unsafe {
        let status = launch_idp_sticker_bridge_nblist_kernel(
            ca_ptr as *const f32,
            sc_ptr as *const f32,
            aromatic_mask_ptr as *const u8,
            cationic_mask_ptr as *const u8,
            sticker_mask_ptr as *const u8,
            local_density_ptr as *mut f32,
            nb_idx_ptr as *const i64,
            nb_dist_ptr as *const f32,
            nb_mask_ptr as *const u8,
            sticker_force_ptr as *mut f32,
            bridge_force_ptr as *mut f32,
            sticker_contacts_ptr as *mut f32,
            pi_pi_contacts_ptr as *mut f32,
            cation_pi_contacts_ptr as *mut f32,
            bridge_contacts_ptr as *mut f32,
            n_per_replica as c_int,
            batch_size as c_int,
            max_neighbors as c_int,
            sticker_strength_ptr as *const f32,
            bridge_strength_ptr as *const f32,
            env_scale_ptr as *const f32,
            llps_branch_ptr as *const f32,
            agg_branch_ptr as *const f32,
            helix_branch_ptr as *const f32,
            is_llps_target_ptr as *const f32,
            is_hnrn_target_ptr as *const f32,
            is_fus_target_ptr as *const f32,
            arg_fraction_ptr as *const f32,
            aromatic_fraction_ptr as *const f32,
            collect_contacts as c_int,
            stream_ptr as usize,
        );
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP IDP sticker_bridge kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pyfunction]
fn compute_idp_virtual_hbond_nblist_gpu(
    donor_ptr: usize,
    acceptor_ptr: usize,
    ca_ptr: usize,
    sc_ptr: usize,
    disorder_ptr: usize,
    aromatic_mask_ptr: usize,
    cationic_mask_ptr: usize,
    sticker_mask_ptr: usize,
    local_density_ptr: usize,
    nb_idx_ptr: usize,
    nb_dist_ptr: usize,
    nb_mask_ptr: usize,
    force_ptr: usize,
    contacts_ptr: usize,
    mean_distance_ptr: usize,
    n_per_replica: usize,
    batch_size: usize,
    max_neighbors: usize,
    center_ptr: usize,
    width_ptr: usize,
    vh_strength_ptr: usize,
    env_scale_ptr: usize,
    vh_scale_ptr: usize,
    contact_gain_ptr: usize,
    exposure_sensitivity_ptr: usize,
    exposure_gain_scale_ptr: usize,
    llps_branch_ptr: usize,
    is_llps_target_ptr: usize,
    is_hnrn_target_ptr: usize,
    is_fus_target_ptr: usize,
    unsat_penalty_ptr: usize,
    stream_ptr: usize,
) -> PyResult<()> {
    if donor_ptr == 0
        || acceptor_ptr == 0
        || ca_ptr == 0
        || sc_ptr == 0
        || disorder_ptr == 0
        || aromatic_mask_ptr == 0
        || cationic_mask_ptr == 0
        || sticker_mask_ptr == 0
        || local_density_ptr == 0
        || nb_idx_ptr == 0
        || nb_dist_ptr == 0
        || nb_mask_ptr == 0
        || force_ptr == 0
        || contacts_ptr == 0
        || mean_distance_ptr == 0
        || center_ptr == 0
        || width_ptr == 0
        || vh_strength_ptr == 0
        || env_scale_ptr == 0
        || vh_scale_ptr == 0
        || contact_gain_ptr == 0
        || exposure_sensitivity_ptr == 0
        || exposure_gain_scale_ptr == 0
        || llps_branch_ptr == 0
        || is_llps_target_ptr == 0
        || is_hnrn_target_ptr == 0
        || is_fus_target_ptr == 0
        || unsat_penalty_ptr == 0
    {
        return Err(pyo3::exceptions::PyValueError::new_err("NULL pointer"));
    }

    unsafe {
        let status = launch_idp_virtual_hbond_nblist_kernel(
            donor_ptr as *const f32,
            acceptor_ptr as *const f32,
            ca_ptr as *const f32,
            sc_ptr as *const f32,
            disorder_ptr as *const f32,
            aromatic_mask_ptr as *const u8,
            cationic_mask_ptr as *const u8,
            sticker_mask_ptr as *const u8,
            local_density_ptr as *mut f32,
            nb_idx_ptr as *const i64,
            nb_dist_ptr as *const f32,
            nb_mask_ptr as *const u8,
            force_ptr as *mut f32,
            contacts_ptr as *mut f32,
            mean_distance_ptr as *mut f32,
            n_per_replica as c_int,
            batch_size as c_int,
            max_neighbors as c_int,
            center_ptr as *const f32,
            width_ptr as *const f32,
            vh_strength_ptr as *const f32,
            env_scale_ptr as *const f32,
            vh_scale_ptr as *const f32,
            contact_gain_ptr as *const f32,
            exposure_sensitivity_ptr as *const f32,
            exposure_gain_scale_ptr as *const f32,
            llps_branch_ptr as *const f32,
            is_llps_target_ptr as *const f32,
            is_hnrn_target_ptr as *const f32,
            is_fus_target_ptr as *const f32,
            unsat_penalty_ptr as *const f32,
            stream_ptr as usize,
        );
        if status != 0 {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                format!("HIP IDP virtual_hbond kernel error: {}", status)
            ));
        }
    }
    Ok(())
}

#[pymodule]
fn ldi_arc_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hip_add, m)?)?;
    m.add_function(wrap_pyfunction!(compute_nonbonded_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(compute_nonbonded_nblist_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(build_neighbor_list_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(compute_nonbonded_celllist_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(rollout_ligand_direct_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(compute_idp_local_density_nblist_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(compute_idp_virtual_hbond_nblist_gpu, m)?)?;
    m.add_function(wrap_pyfunction!(compute_idp_sticker_bridge_nblist_gpu, m)?)?;
    Ok(())
}
