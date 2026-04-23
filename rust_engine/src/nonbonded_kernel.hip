#include <hip/hip_runtime.h>
#include <math.h>
#include <stdint.h>

// 🔑 핵심: 최소 거리 강제 (수치 불안정성 근본 해결)
#define MIN_R2 4.0f  // 2.0Å² (vdW 반지름 합 3.4Å의 59% - 안전한 여유)

__device__ __forceinline__
float pbc_delta(float d, float box_size) {
    return d - box_size * floorf((d + 0.5f * box_size) / box_size);
}

__device__ __forceinline__
int wrap_idx(int x, int n) {
    int r = x % n;
    return (r < 0) ? (r + n) : r;
}

__device__ __forceinline__
int flatten_cell(int cx, int cy, int cz, int gy, int gz) {
    return (cx * gy + cy) * gz + cz;
}

__device__ __forceinline__
float clampf_local(float x, float lo, float hi) {
    return fminf(fmaxf(x, lo), hi);
}

__device__ __forceinline__
float relu_local(float x) {
    return x > 0.0f ? x : 0.0f;
}

__device__ __forceinline__
float sqr_local(float x) {
    return x * x;
}

__device__ __forceinline__
float norm3_local(float x, float y, float z) {
    return sqrtf(fmaxf(x * x + y * y + z * z, 1e-12f));
}

extern "C" __global__
void nonbonded_kernel(
    const float* __restrict__ pos,
    float* __restrict__ force,
    float* __restrict__ energy,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float sigma,
    float epsilon
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;
    float xi = pos[idx*3 + 0];
    float yi = pos[idx*3 + 1];
    float zi = pos[idx*3 + 2];

    double fx = 0.0, fy = 0.0, fz = 0.0;
    double local_energy = 0.0;

    extern __shared__ float shmem[];
    float* sx = shmem;
    float* sy = sx + blockDim.x;
    float* sz = sy + blockDim.x;

    int start = replica_id * n_per_replica;
    int end = start + n_per_replica;

    const float sigma2 = sigma * sigma;
    for (int tile = start; tile < end; tile += blockDim.x) {
        int j_global = tile + threadIdx.x;
        if (j_global < end) {
            sx[threadIdx.x] = pos[j_global * 3 + 0];
            sy[threadIdx.x] = pos[j_global * 3 + 1];
            sz[threadIdx.x] = pos[j_global * 3 + 2];
        } else {
            sx[threadIdx.x] = 0.0f;
            sy[threadIdx.x] = 0.0f;
            sz[threadIdx.x] = 0.0f;
        }
        __syncthreads();

        int tile_size = end - tile;
        if (tile_size > blockDim.x) tile_size = blockDim.x;

        #pragma unroll 4
        for (int t = 0; t < tile_size; t++) {
            int local_j = (tile - start) + t;
            if (local_j == local_i) continue;

            float dx = pbc_delta(xi - sx[t], box_size);
            float dy = pbc_delta(yi - sy[t], box_size);
            float dz = pbc_delta(zi - sz[t], box_size);

            float r2 = dx*dx + dy*dy + dz*dz;
            r2 = fmaxf(r2, MIN_R2);

            float r2inv = 1.0f / r2;
            float sr2 = sigma2 * r2inv;
            float sr6 = sr2 * sr2 * sr2;
            float sr12 = sr6 * sr6;

            // F = 24e(2(sr)^12 - (sr)^6) * r_vec / r^2
            float fscale = 24.0f * epsilon * (2.0f * sr12 - sr6) * r2inv;
            fx += fscale * dx;
            fy += fscale * dy;
            fz += fscale * dz;
            local_energy += 2.0f * epsilon * (sr12 - sr6);
        }
        __syncthreads();
    }

    force[idx*3 + 0] = fx;
    force[idx*3 + 1] = fy;
    force[idx*3 + 2] = fz;
    atomicAdd(&energy[replica_id], local_energy);
}

extern "C" __global__
void nonbonded_nblist_kernel(
    const float* __restrict__ pos,
    const int64_t* __restrict__ nb_idx,
    const uint8_t* __restrict__ nb_mask,
    float* __restrict__ force,
    float* __restrict__ energy,
    int n_per_replica,
    int total_atoms,
    int max_neighbors,
    float box_size,
    float sigma,
    float epsilon
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;

    float xi = pos[idx*3 + 0];
    float yi = pos[idx*3 + 1];
    float zi = pos[idx*3 + 2];

    float fx = 0.0f, fy = 0.0f, fz = 0.0f;
    float local_energy = 0.0f;

    int row_start = idx * max_neighbors;
    int replica_start = replica_id * n_per_replica;

    const double sigma2 = (double)sigma * (double)sigma;
    #pragma unroll 4
    for (int k = 0; k < max_neighbors; k++) {
        int row_idx = row_start + k;
        if (nb_mask && nb_mask[row_idx] == 0) continue;

        int64_t n_local = nb_idx[row_idx];
        if (n_local < 0 || n_local >= n_per_replica) continue;
        if ((int)n_local == local_i) continue;

        int j = replica_start + (int)n_local;

        float xj = pos[j*3 + 0];
        float yj = pos[j*3 + 1];
        float zj = pos[j*3 + 2];

        double dx = (double)pbc_delta(xi - xj, box_size);
        double dy = (double)pbc_delta(yi - yj, box_size);
        double dz = (double)pbc_delta(zi - zj, box_size);

        double r2 = dx*dx + dy*dy + dz*dz;
        if (r2 < (double)MIN_R2) r2 = (double)MIN_R2;

        double r2inv = 1.0 / r2;
        double sr2 = sigma2 * r2inv;
        double sr6 = sr2 * sr2 * sr2;
        double sr12 = sr6 * sr6;

        double fscale = 24.0 * (double)epsilon * (2.0 * sr12 - sr6) * r2inv;
        fx += fscale * dx;
        fy += fscale * dy;
        fz += fscale * dz;
        local_energy += 2.0 * (double)epsilon * (sr12 - sr6);
    }

    force[idx*3 + 0] = (float)fx;
    force[idx*3 + 1] = (float)fy;
    force[idx*3 + 2] = (float)fz;
    atomicAdd(&energy[replica_id], (float)local_energy);
}

extern "C" __global__
void build_cell_list_kernel(
    const float* __restrict__ pos,
    int* __restrict__ cell_counts,
    int* __restrict__ cell_atoms,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float cell_size,
    int gx,
    int gy,
    int gz,
    int max_atoms_per_cell
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;

    float x = pos[idx*3 + 0];
    float y = pos[idx*3 + 1];
    float z = pos[idx*3 + 2];

    // Ensure positive wrapped coordinates before cell lookup.
    x = x - box_size * floorf(x / box_size);
    y = y - box_size * floorf(y / box_size);
    z = z - box_size * floorf(z / box_size);

    int cx = wrap_idx((int)floorf(x / cell_size), gx);
    int cy = wrap_idx((int)floorf(y / cell_size), gy);
    int cz = wrap_idx((int)floorf(z / cell_size), gz);
    int cell_id = flatten_cell(cx, cy, cz, gy, gz);

    int n_cells = gx * gy * gz;
    int base = replica_id * n_cells + cell_id;
    int slot = atomicAdd(&cell_counts[base], 1);
    if (slot < max_atoms_per_cell) {
        cell_atoms[base * max_atoms_per_cell + slot] = local_i;
    }
}

extern "C" __global__
void build_neighbor_list_from_cells_kernel(
    const float* __restrict__ pos,
    const int* __restrict__ cell_counts,
    const int* __restrict__ cell_atoms,
    int64_t* __restrict__ nb_idx,
    float* __restrict__ nb_dist,
    uint8_t* __restrict__ nb_mask,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float cutoff,
    int gx,
    int gy,
    int gz,
    int max_atoms_per_cell,
    int max_neighbors
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;
    int replica_start = replica_id * n_per_replica;
    int n_cells = gx * gy * gz;

    float xi = pos[idx*3 + 0];
    float yi = pos[idx*3 + 1];
    float zi = pos[idx*3 + 2];

    float xw = xi - box_size * floorf(xi / box_size);
    float yw = yi - box_size * floorf(yi / box_size);
    float zw = zi - box_size * floorf(zi / box_size);

    int cx = wrap_idx((int)floorf(xw / cutoff), gx);
    int cy = wrap_idx((int)floorf(yw / cutoff), gy);
    int cz = wrap_idx((int)floorf(zw / cutoff), gz);
    float cutoff2 = cutoff * cutoff;
    int row_start = idx * max_neighbors;
    int write_count = 0;

    for (int dx = -1; dx <= 1; dx++) {
        int nx = wrap_idx(cx + dx, gx);
        for (int dy = -1; dy <= 1; dy++) {
            int ny = wrap_idx(cy + dy, gy);
            for (int dz = -1; dz <= 1; dz++) {
                int nz = wrap_idx(cz + dz, gz);
                int ncell = flatten_cell(nx, ny, nz, gy, gz);
                int base = replica_id * n_cells + ncell;
                int count = cell_counts[base];
                if (count > max_atoms_per_cell) count = max_atoms_per_cell;

                for (int slot = 0; slot < count; slot++) {
                    int j_local = cell_atoms[base * max_atoms_per_cell + slot];
                    if (j_local < 0 || j_local >= n_per_replica) continue;
                    if (j_local == local_i) continue;

                    int j = replica_start + j_local;
                    float xj = pos[j*3 + 0];
                    float yj = pos[j*3 + 1];
                    float zj = pos[j*3 + 2];

                    float drx = pbc_delta(xi - xj, box_size);
                    float dry = pbc_delta(yi - yj, box_size);
                    float drz = pbc_delta(zi - zj, box_size);
                    float r2 = drx*drx + dry*dry + drz*drz;

                    if (r2 < cutoff2) {
                        int limit = write_count < max_neighbors ? write_count : max_neighbors;
                        bool duplicate = false;
                        for (int t = 0; t < limit; t++) {
                            if (nb_idx[row_start + t] == (int64_t)j_local) {
                                duplicate = true;
                                break;
                            }
                        }
                        if (duplicate) continue;

                        if (write_count < max_neighbors) {
                            int out_idx = row_start + write_count;
                            nb_idx[out_idx] = (int64_t)j_local;
                            nb_dist[out_idx] = r2;
                            nb_mask[out_idx] = (uint8_t)1;
                            write_count++;
                        } else {
                            int farthest_slot = 0;
                            float farthest_r2 = nb_dist[row_start + 0];
                            for (int t = 1; t < max_neighbors; t++) {
                                float v = nb_dist[row_start + t];
                                if (v > farthest_r2) {
                                    farthest_r2 = v;
                                    farthest_slot = t;
                                }
                            }
                            if (r2 < farthest_r2) {
                                int out_idx = row_start + farthest_slot;
                                nb_idx[out_idx] = (int64_t)j_local;
                                nb_dist[out_idx] = r2;
                                nb_mask[out_idx] = (uint8_t)1;
                            }
                        }
                    }
                }
            }
        }
    }
}

extern "C" __global__
void compute_nonbonded_from_cells_kernel(
    const float* __restrict__ pos,
    const int* __restrict__ cell_counts,
    const int* __restrict__ cell_atoms,
    float* __restrict__ force,
    float* __restrict__ energy,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float cutoff,
    int gx,
    int gy,
    int gz,
    int max_atoms_per_cell,
    float sigma,
    float epsilon
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;
    int replica_start = replica_id * n_per_replica;
    int n_cells = gx * gy * gz;

    float xi = pos[idx*3 + 0];
    float yi = pos[idx*3 + 1];
    float zi = pos[idx*3 + 2];

    float xw = xi - box_size * floorf(xi / box_size);
    float yw = yi - box_size * floorf(yi / box_size);
    float zw = zi - box_size * floorf(zi / box_size);

    int cx = wrap_idx((int)floorf(xw / cutoff), gx);
    int cy = wrap_idx((int)floorf(yw / cutoff), gy);
    int cz = wrap_idx((int)floorf(zw / cutoff), gz);
    float cutoff2 = cutoff * cutoff;
    const float sigma2 = sigma * sigma;

    float fx = 0.0f, fy = 0.0f, fz = 0.0f;
    float local_energy = 0.0f;

    for (int dx = -1; dx <= 1; dx++) {
        int nx = wrap_idx(cx + dx, gx);
        for (int dy = -1; dy <= 1; dy++) {
            int ny = wrap_idx(cy + dy, gy);
            for (int dz = -1; dz <= 1; dz++) {
                int nz = wrap_idx(cz + dz, gz);
                int ncell = flatten_cell(nx, ny, nz, gy, gz);
                int base = replica_id * n_cells + ncell;
                int count = cell_counts[base];
                if (count > max_atoms_per_cell) count = max_atoms_per_cell;

                for (int slot = 0; slot < count; slot++) {
                    int j_local = cell_atoms[base * max_atoms_per_cell + slot];
                    if (j_local < 0 || j_local >= n_per_replica) continue;
                    if (j_local == local_i) continue;

                    int j = replica_start + j_local;
                    float xj = pos[j*3 + 0];
                    float yj = pos[j*3 + 1];
                    float zj = pos[j*3 + 2];

                    float drx = pbc_delta(xi - xj, box_size);
                    float dry = pbc_delta(yi - yj, box_size);
                    float drz = pbc_delta(zi - zj, box_size);
                    float r2 = drx*drx + dry*dry + drz*drz;
                    if (r2 >= cutoff2) continue;

                    r2 = fmaxf(r2, MIN_R2);
                    float r2inv = 1.0f / r2;
                    float sr2 = sigma2 * r2inv;
                    float sr6 = sr2 * sr2 * sr2;
                    float sr12 = sr6 * sr6;

                    float fscale = 24.0f * epsilon * (2.0f * sr12 - sr6) * r2inv;
                    fx += fscale * drx;
                    fy += fscale * dry;
                    fz += fscale * drz;
                    local_energy += 2.0f * epsilon * (sr12 - sr6);
                }
            }
        }
    }

    force[idx*3 + 0] = fx;
    force[idx*3 + 1] = fy;
    force[idx*3 + 2] = fz;
    atomicAdd(&energy[replica_id], local_energy);
}

extern "C" __global__
void ligand_extra_force_kernel(
    const float* __restrict__ pos,
    float* __restrict__ force,
    const float* __restrict__ pocket,
    const float* __restrict__ pocket_attract,
    const float* __restrict__ protein_repulse,
    const float* __restrict__ bond_ref,
    int n_per_replica,
    int batch_size,
    int n_protein,
    int n_ligand,
    float bond_k,
    float repulse_cutoff
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total_ligand_atoms = batch_size * n_ligand;
    if (idx >= total_ligand_atoms) return;

    int replica_id = idx / n_ligand;
    int lig_local = idx - replica_id * n_ligand;
    int atom_idx = replica_id * n_per_replica + n_protein + lig_local;

    float cx = 0.0f;
    float cy = 0.0f;
    float cz = 0.0f;
    int lig_base = replica_id * n_per_replica + n_protein;
    for (int j = 0; j < n_ligand; ++j) {
        int lig_idx = lig_base + j;
        cx += pos[lig_idx * 3 + 0];
        cy += pos[lig_idx * 3 + 1];
        cz += pos[lig_idx * 3 + 2];
    }
    float inv_l = 1.0f / fmaxf((float)n_ligand, 1.0f);
    cx *= inv_l;
    cy *= inv_l;
    cz *= inv_l;

    float px = pocket[replica_id * 3 + 0];
    float py = pocket[replica_id * 3 + 1];
    float pz = pocket[replica_id * 3 + 2];
    float k_attr = pocket_attract[replica_id];

    force[atom_idx * 3 + 0] += -(cx - px) * k_attr;
    force[atom_idx * 3 + 1] += -(cy - py) * k_attr;
    force[atom_idx * 3 + 2] += -(cz - pz) * k_attr;

    if (n_protein > 0 && repulse_cutoff > 0.0f) {
        float xi = pos[atom_idx * 3 + 0];
        float yi = pos[atom_idx * 3 + 1];
        float zi = pos[atom_idx * 3 + 2];
        float cutoff = repulse_cutoff;
        float k_rep = protein_repulse[replica_id];
        float acc_x = 0.0f;
        float acc_y = 0.0f;
        float acc_z = 0.0f;
        int hit_count = 0;
        for (int p = 0; p < n_protein; ++p) {
            int p_idx = replica_id * n_per_replica + p;
            float dx = xi - pos[p_idx * 3 + 0];
            float dy = yi - pos[p_idx * 3 + 1];
            float dz = zi - pos[p_idx * 3 + 2];
            float dist = sqrtf(dx * dx + dy * dy + dz * dz);
            if (dist > 1e-6f && dist < cutoff) {
                float inv_dist = 1.0f / dist;
                float mag = k_rep * fmaxf(cutoff - dist, 0.0f) / fmaxf(cutoff, 1e-6f);
                acc_x += dx * inv_dist * mag;
                acc_y += dy * inv_dist * mag;
                acc_z += dz * inv_dist * mag;
                hit_count += 1;
            }
        }
        if (hit_count > 0) {
            float inv_hits = 1.0f / (float)hit_count;
            force[atom_idx * 3 + 0] += acc_x * inv_hits;
            force[atom_idx * 3 + 1] += acc_y * inv_hits;
            force[atom_idx * 3 + 2] += acc_z * inv_hits;
        }
    }

    if (n_ligand >= 2 && lig_local == 0) {
        int atom0 = lig_base + 0;
        int atom1 = lig_base + 1;
        float vx = pos[atom0 * 3 + 0] - pos[atom1 * 3 + 0];
        float vy = pos[atom0 * 3 + 1] - pos[atom1 * 3 + 1];
        float vz = pos[atom0 * 3 + 2] - pos[atom1 * 3 + 2];
        float d = sqrtf(vx * vx + vy * vy + vz * vz);
        d = fmaxf(d, 1e-6f);
        float ref = bond_ref[replica_id];
        float scale = -bond_k * (d - ref) / d;
        float fx = scale * vx;
        float fy = scale * vy;
        float fz = scale * vz;
        force[atom0 * 3 + 0] += fx;
        force[atom0 * 3 + 1] += fy;
        force[atom0 * 3 + 2] += fz;
        force[atom1 * 3 + 0] -= fx;
        force[atom1 * 3 + 1] -= fy;
        force[atom1 * 3 + 2] -= fz;
    }
}

extern "C" __global__
void clamp_force_kernel(
    float* __restrict__ force,
    int total_atoms,
    float clip_value
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;
    int base = idx * 3;
    force[base + 0] = fminf(fmaxf(force[base + 0], -clip_value), clip_value);
    force[base + 1] = fminf(fmaxf(force[base + 1], -clip_value), clip_value);
    force[base + 2] = fminf(fmaxf(force[base + 2], -clip_value), clip_value);
}

extern "C" __global__
void integrator_step_kernel(
    float* __restrict__ pos,
    float* __restrict__ vel,
    const float* __restrict__ force,
    const float* __restrict__ noise,
    int total_atoms,
    float dt,
    float gamma
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int base = idx * 3;
    float n0 = noise ? noise[base + 0] : 0.0f;
    float n1 = noise ? noise[base + 1] : 0.0f;
    float n2 = noise ? noise[base + 2] : 0.0f;

    vel[base + 0] += (force[base + 0] * dt) - (gamma * vel[base + 0] * dt) + n0;
    vel[base + 1] += (force[base + 1] * dt) - (gamma * vel[base + 1] * dt) + n1;
    vel[base + 2] += (force[base + 2] * dt) - (gamma * vel[base + 2] * dt) + n2;

    pos[base + 0] += vel[base + 0] * dt;
    pos[base + 1] += vel[base + 1] * dt;
    pos[base + 2] += vel[base + 2] * dt;
}

extern "C" __global__
void pocket_radius_clip_kernel(
    float* __restrict__ pos,
    const float* __restrict__ pocket,
    int n_per_replica,
    int batch_size,
    int n_protein,
    int n_ligand,
    float max_pocket_radius
) {
    int replica_id = blockIdx.x * blockDim.x + threadIdx.x;
    if (replica_id >= batch_size) return;
    if (n_ligand <= 0 || max_pocket_radius <= 0.0f) return;

    int lig_base = replica_id * n_per_replica + n_protein;
    float cx = 0.0f;
    float cy = 0.0f;
    float cz = 0.0f;
    for (int j = 0; j < n_ligand; ++j) {
        int lig_idx = lig_base + j;
        cx += pos[lig_idx * 3 + 0];
        cy += pos[lig_idx * 3 + 1];
        cz += pos[lig_idx * 3 + 2];
    }
    float inv_l = 1.0f / fmaxf((float)n_ligand, 1.0f);
    cx *= inv_l;
    cy *= inv_l;
    cz *= inv_l;

    float px = pocket[replica_id * 3 + 0];
    float py = pocket[replica_id * 3 + 1];
    float pz = pocket[replica_id * 3 + 2];
    float dx = cx - px;
    float dy = cy - py;
    float dz = cz - pz;
    float radial = sqrtf(dx * dx + dy * dy + dz * dz);
    if (radial <= max_pocket_radius || radial <= 1e-6f) return;

    float pull = fmaxf(radial - max_pocket_radius, 0.0f) / radial;
    float sx = dx * pull;
    float sy = dy * pull;
    float sz = dz * pull;
    for (int j = 0; j < n_ligand; ++j) {
        int lig_idx = lig_base + j;
        pos[lig_idx * 3 + 0] -= sx;
        pos[lig_idx * 3 + 1] -= sy;
        pos[lig_idx * 3 + 2] -= sz;
    }
}

extern "C" __global__
void capture_ligand_frame_kernel(
    const float* __restrict__ pos,
    float* __restrict__ selected_out,
    int n_per_replica,
    int batch_size,
    int n_protein,
    int n_ligand,
    int n_keep,
    int keep_slot
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total_ligand_atoms = batch_size * n_ligand;
    if (idx >= total_ligand_atoms) return;

    int replica_id = idx / n_ligand;
    int lig_local = idx - replica_id * n_ligand;
    int src_atom_idx = replica_id * n_per_replica + n_protein + lig_local;

    size_t dst_base = (((size_t)replica_id * (size_t)n_keep + (size_t)keep_slot) * (size_t)n_ligand + (size_t)lig_local) * 3ULL;
    size_t src_base = (size_t)src_atom_idx * 3ULL;
    selected_out[dst_base + 0] = pos[src_base + 0];
    selected_out[dst_base + 1] = pos[src_base + 1];
    selected_out[dst_base + 2] = pos[src_base + 2];
}

// CPU 런처 (동기화 제거로 속도 향상)
extern "C" int launch_nonbonded_kernel(
    const float* pos,
    float* force,
    float* energy,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float sigma,
    float epsilon
) {
    if (!pos || !force || !energy) return -1;
    
    const int threads = 256;
    const int blocks = (total_atoms + threads - 1) / threads;
    const size_t smem_bytes = (size_t)threads * 3 * sizeof(float);

    hipLaunchKernelGGL(
        nonbonded_kernel,
        dim3(blocks), dim3(threads),
        smem_bytes, 0,
        pos, force, energy,
        n_per_replica, total_atoms,
        box_size, sigma, epsilon
    );
    
    return hipGetLastError() == hipSuccess ? 0 : -2;
}

extern "C" int launch_build_neighbor_list_kernel(
    const float* pos,
    int* cell_counts,
    int* cell_atoms,
    int64_t* nb_idx,
    float* nb_dist,
    uint8_t* nb_mask,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float cutoff,
    int gx,
    int gy,
    int gz,
    int max_atoms_per_cell,
    int max_neighbors
) {
    if (!pos || !cell_counts || !cell_atoms || !nb_idx || !nb_dist || !nb_mask) return -1;
    if (n_per_replica <= 0 || total_atoms <= 0 || total_atoms % n_per_replica != 0) return -2;
    if (cutoff <= 0.0f || gx <= 0 || gy <= 0 || gz <= 0 || max_atoms_per_cell <= 0 || max_neighbors <= 0) return -3;

    int batch_size = total_atoms / n_per_replica;
    int n_cells = gx * gy * gz;
    int threads = 256;
    int blocks = (total_atoms + threads - 1) / threads;
    float cell_size = cutoff;

    hipError_t err = hipMemset(cell_counts, 0, (size_t)batch_size * (size_t)n_cells * sizeof(int));
    if (err != hipSuccess) return -4;
    err = hipMemset(nb_mask, 0, (size_t)total_atoms * (size_t)max_neighbors * sizeof(uint8_t));
    if (err != hipSuccess) return -5;
    err = hipMemset(nb_idx, 0xFF, (size_t)total_atoms * (size_t)max_neighbors * sizeof(int64_t));
    if (err != hipSuccess) return -6;
    err = hipMemset(nb_dist, 0, (size_t)total_atoms * (size_t)max_neighbors * sizeof(float));
    if (err != hipSuccess) return -9;

    hipLaunchKernelGGL(
        build_cell_list_kernel,
        dim3(blocks), dim3(threads),
        0, 0,
        pos, cell_counts, cell_atoms,
        n_per_replica, total_atoms,
        box_size, cell_size, gx, gy, gz, max_atoms_per_cell
    );
    err = hipGetLastError();
    if (err != hipSuccess) return -7;

    hipLaunchKernelGGL(
        build_neighbor_list_from_cells_kernel,
        dim3(blocks), dim3(threads),
        0, 0,
        pos, cell_counts, cell_atoms,
        nb_idx, nb_dist, nb_mask,
        n_per_replica, total_atoms,
        box_size, cutoff, gx, gy, gz, max_atoms_per_cell, max_neighbors
    );
    err = hipGetLastError();
    if (err != hipSuccess) return -8;

    return 0;
}

extern "C" int launch_nonbonded_fused_cell_kernel(
    const float* pos,
    int* cell_counts,
    int* cell_atoms,
    float* force,
    float* energy,
    int n_per_replica,
    int total_atoms,
    float box_size,
    float cutoff,
    int gx,
    int gy,
    int gz,
    int max_atoms_per_cell,
    float sigma,
    float epsilon
) {
    if (!pos || !cell_counts || !cell_atoms || !force || !energy) return -1;
    if (n_per_replica <= 0 || total_atoms <= 0 || total_atoms % n_per_replica != 0) return -2;
    if (cutoff <= 0.0f || gx <= 0 || gy <= 0 || gz <= 0 || max_atoms_per_cell <= 0) return -3;

    int batch_size = total_atoms / n_per_replica;
    int n_cells = gx * gy * gz;
    int threads = 256;
    int blocks = (total_atoms + threads - 1) / threads;
    float cell_size = cutoff;

    hipError_t err = hipMemset(cell_counts, 0, (size_t)batch_size * (size_t)n_cells * sizeof(int));
    if (err != hipSuccess) return -4;

    hipLaunchKernelGGL(
        build_cell_list_kernel,
        dim3(blocks), dim3(threads),
        0, 0,
        pos, cell_counts, cell_atoms,
        n_per_replica, total_atoms,
        box_size, cell_size, gx, gy, gz, max_atoms_per_cell
    );
    err = hipGetLastError();
    if (err != hipSuccess) return -5;

    hipLaunchKernelGGL(
        compute_nonbonded_from_cells_kernel,
        dim3(blocks), dim3(threads),
        0, 0,
        pos, cell_counts, cell_atoms, force, energy,
        n_per_replica, total_atoms,
        box_size, cutoff, gx, gy, gz, max_atoms_per_cell, sigma, epsilon
    );
    err = hipGetLastError();
    if (err != hipSuccess) return -6;

    return 0;
}

extern "C" int launch_nonbonded_nblist_kernel(
    const float* pos,
    const int64_t* nb_idx,
    const uint8_t* nb_mask,
    float* force,
    float* energy,
    int n_per_replica,
    int total_atoms,
    int max_neighbors,
    float box_size,
    float sigma,
    float epsilon
) {
    if (!pos || !nb_idx || !force || !energy) return -1;
    if (max_neighbors <= 0) return -3;

    const int threads = 256;
    const int blocks = (total_atoms + threads - 1) / threads;

    hipLaunchKernelGGL(
        nonbonded_nblist_kernel,
        dim3(blocks), dim3(threads),
        0, 0,
        pos, nb_idx, nb_mask, force, energy,
        n_per_replica, total_atoms, max_neighbors,
        box_size, sigma, epsilon
    );

    return hipGetLastError() == hipSuccess ? 0 : -2;
}

extern "C" __global__
void idp_local_density_nblist_kernel(
    const int64_t* __restrict__ nb_idx,
    const float* __restrict__ nb_dist,
    const uint8_t* __restrict__ nb_mask,
    float* __restrict__ out_density,
    int n_per_replica,
    int total_atoms,
    int max_neighbors,
    int min_gap
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;
    int local_i = idx % n_per_replica;
    int row_start = idx * max_neighbors;
    float acc = 0.0f;
    #pragma unroll 2
    for (int k = 0; k < max_neighbors; ++k) {
        int row_idx = row_start + k;
        if (nb_mask[row_idx] == 0) continue;
        int64_t n_local = nb_idx[row_idx];
        if (n_local < 0 || n_local >= n_per_replica) continue;
        int local_j = (int)n_local;
        if (local_j == local_i) continue;
        if (abs(local_j - local_i) < min_gap) continue;
        if (nb_dist[row_idx] < 8.0f) acc += 1.0f;
    }
    out_density[idx] = acc;
}

extern "C" __global__
void idp_virtual_hbond_nblist_kernel(
    const float* __restrict__ donor,
    const float* __restrict__ acceptor,
    const float* __restrict__ ca,
    const float* __restrict__ sc,
    const float* __restrict__ disorder,
    const uint8_t* __restrict__ aromatic_mask,
    const uint8_t* __restrict__ cationic_mask,
    const uint8_t* __restrict__ sticker_mask,
    const float* __restrict__ local_density,
    const int64_t* __restrict__ nb_idx,
    const uint8_t* __restrict__ nb_mask,
    float* __restrict__ force,
    float* __restrict__ contacts,
    float* __restrict__ mean_distance,
    int n_per_replica,
    int total_atoms,
    int max_neighbors,
    const float* __restrict__ center,
    const float* __restrict__ width,
    const float* __restrict__ vh_strength,
    const float* __restrict__ env_scale,
    const float* __restrict__ vh_scale,
    const float* __restrict__ contact_gain,
    const float* __restrict__ exposure_sensitivity,
    const float* __restrict__ exposure_gain_scale,
    const float* __restrict__ llps_branch,
    const float* __restrict__ is_llps_target,
    const float* __restrict__ is_hnrn_target,
    const float* __restrict__ is_fus_target,
    const float* __restrict__ unsat_penalty
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;
    int row_start = idx * max_neighbors;
    int replica_start = replica_id * n_per_replica;

    float center_b = clampf_local(center[replica_id], 2.2f, 5.0f);
    float width_b = clampf_local(width[replica_id], 0.8f, 2.8f);
    float env_scale_b = env_scale[replica_id];
    float vh_scale_b = vh_scale[replica_id];
    float contact_gain_b = contact_gain[replica_id];
    float exposure_sensitivity_b = exposure_sensitivity[replica_id];
    float exposure_gain_scale_b = exposure_gain_scale[replica_id];
    float llps_branch_b = llps_branch[replica_id];
    float is_llps_target_b = is_llps_target[replica_id];
    float is_hnrn_target_b = is_hnrn_target[replica_id];
    float is_fus_target_b = is_fus_target[replica_id];
    float vh_strength_b = relu_local(vh_strength[0]);
    float unsat_penalty_b = relu_local(unsat_penalty[0]);

    int i3 = idx * 3;
    float ca_ix = ca[i3 + 0];
    float ca_iy = ca[i3 + 1];
    float ca_iz = ca[i3 + 2];
    float donor_ix = donor[i3 + 0];
    float donor_iy = donor[i3 + 1];
    float donor_iz = donor[i3 + 2];
    float acceptor_ix = acceptor[i3 + 0];
    float acceptor_iy = acceptor[i3 + 1];
    float acceptor_iz = acceptor[i3 + 2];
    float sc_ix = sc[i3 + 0];
    float sc_iy = sc[i3 + 1];
    float sc_iz = sc[i3 + 2];
    float disorder_i = disorder[idx];
    float exposure_local_i = 1.0f / (1.0f + 0.12f * local_density[idx]);
    bool aro_i = aromatic_mask[idx] != 0;
    bool cat_i = cationic_mask[idx] != 0;
    bool st_i = sticker_mask[idx] != 0;

    float fx = 0.0f;
    float fy = 0.0f;
    float fz = 0.0f;
    double contacts_acc = 0.0;
    double mean_dist_acc = 0.0;

    #pragma unroll 2
    for (int k = 0; k < max_neighbors; k++) {
        int row_idx = row_start + k;
        if (nb_mask[row_idx] == 0) continue;

        int64_t n_local = nb_idx[row_idx];
        if (n_local < 0 || n_local >= n_per_replica) continue;
        int local_j = (int)n_local;
        if (local_j == local_i) continue;
        if (abs(local_j - local_i) < 3) continue;

        int j = replica_start + local_j;
        int j3 = j * 3;

        float donor_jx = donor[j3 + 0];
        float donor_jy = donor[j3 + 1];
        float donor_jz = donor[j3 + 2];
        float acceptor_jx = acceptor[j3 + 0];
        float acceptor_jy = acceptor[j3 + 1];
        float acceptor_jz = acceptor[j3 + 2];
        float ca_jx = ca[j3 + 0];
        float ca_jy = ca[j3 + 1];
        float ca_jz = ca[j3 + 2];
        float sc_jx = sc[j3 + 0];
        float sc_jy = sc[j3 + 1];
        float sc_jz = sc[j3 + 2];
        float disorder_j = disorder[j];
        float exposure_local_j = 1.0f / (1.0f + 0.12f * local_density[j]);
        bool aro_j = aromatic_mask[j] != 0;
        bool cat_j = cationic_mask[j] != 0;
        bool st_j = sticker_mask[j] != 0;

        float d_ij = norm3_local(
            donor_ix - acceptor_jx,
            donor_iy - acceptor_jy,
            donor_iz - acceptor_jz
        );
        float d_ji = norm3_local(
            donor_jx - acceptor_ix,
            donor_jy - acceptor_iy,
            donor_jz - acceptor_iz
        );
        float d_pair = fminf(d_ij, d_ji);

        float well_z = (d_pair - center_b) / width_b;
        float well = expf(-sqr_local(well_z));
        float unsat = fmaxf(d_pair - 4.4f, 0.0f) / 4.4f;

        float pair_weight = disorder_i * disorder_j;
        float exposure_pair = exposure_local_i * exposure_local_j;
        float exposure_gain = (0.55f + exposure_sensitivity_b * exposure_pair) * exposure_gain_scale_b;

        if (is_llps_target_b > 0.5f) {
            float d_sc = norm3_local(sc_ix - sc_jx, sc_iy - sc_jy, sc_iz - sc_jz);
            float pi_pi_support = ((aro_i && aro_j) ? 1.0f : 0.0f) * expf(-sqr_local((d_sc - 9.2f) / 2.2f));
            float cation_pi_support = (((cat_i && aro_j) || (aro_i && cat_j)) ? 1.0f : 0.0f) * expf(-sqr_local((d_sc - 10.0f) / 2.6f));
            float sticker_support = ((st_i && st_j) ? 1.0f : 0.0f) * expf(-sqr_local((d_sc - 9.8f) / 2.8f));
            float llps_transfer = 0.45f * pi_pi_support + 0.85f * cation_pi_support + 0.25f * sticker_support;
            float transfer_gain = 0.18f + 0.20f * fminf(llps_branch_b, 1.0f);
            transfer_gain += 0.10f * is_hnrn_target_b + 0.06f * is_fus_target_b;
            pair_weight *= 1.0f + transfer_gain * clampf_local(llps_transfer, 0.0f, 1.6f);
            unsat *= 1.0f - 0.18f * clampf_local(llps_transfer, 0.0f, 1.0f);
        }

        pair_weight *= exposure_gain;
        float strength = vh_strength_b * env_scale_b * vh_scale_b;
        float mag = (strength * contact_gain_b * pair_weight * well - unsat_penalty_b * pair_weight * unsat);

        float drx = ca_ix - ca_jx;
        float dry = ca_iy - ca_jy;
        float drz = ca_iz - ca_jz;
        float dr_norm = norm3_local(drx, dry, drz);
        float ux = drx / dr_norm;
        float uy = dry / dr_norm;
        float uz = drz / dr_norm;

        fx += -mag * ux;
        fy += -mag * uy;
        fz += -mag * uz;

        float contact_mask = (well > 0.35f) ? 1.0f : 0.0f;
        contacts_acc += (double)contact_mask;
        mean_dist_acc += (double)d_pair * (double)contact_mask;
    }

    force[i3 + 0] = fx;
    force[i3 + 1] = fy;
    force[i3 + 2] = fz;
    atomicAdd(&contacts[replica_id], (float)contacts_acc);
    atomicAdd(&mean_distance[replica_id], (float)mean_dist_acc);
}

extern "C" __global__
void idp_sticker_bridge_nblist_kernel(
    const float* __restrict__ ca,
    const float* __restrict__ sc,
    const uint8_t* __restrict__ aromatic_mask,
    const uint8_t* __restrict__ cationic_mask,
    const uint8_t* __restrict__ sticker_mask,
    const float* __restrict__ local_density,
    const int64_t* __restrict__ nb_idx,
    const uint8_t* __restrict__ nb_mask,
    float* __restrict__ sticker_force,
    float* __restrict__ bridge_force,
    float* __restrict__ sticker_contacts,
    float* __restrict__ pi_pi_contacts,
    float* __restrict__ cation_pi_contacts,
    float* __restrict__ bridge_contacts,
    int n_per_replica,
    int total_atoms,
    int max_neighbors,
    const float* __restrict__ sticker_strength,
    const float* __restrict__ bridge_strength,
    const float* __restrict__ env_scale,
    const float* __restrict__ llps_branch,
    const float* __restrict__ agg_branch,
    const float* __restrict__ helix_branch,
    const float* __restrict__ is_llps_target,
    const float* __restrict__ is_hnrn_target,
    const float* __restrict__ is_fus_target,
    const float* __restrict__ arg_fraction,
    const float* __restrict__ aromatic_fraction,
    int collect_contacts
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total_atoms) return;

    int replica_id = idx / n_per_replica;
    int local_i = idx - replica_id * n_per_replica;
    int row_start = idx * max_neighbors;
    int replica_start = replica_id * n_per_replica;

    float env_scale_b = env_scale[replica_id];
    float llps_branch_b = llps_branch[replica_id];
    float agg_branch_b = agg_branch[replica_id];
    float helix_branch_b = helix_branch[replica_id];
    float is_llps_target_b = is_llps_target[replica_id];
    float is_hnrn_target_b = is_hnrn_target[replica_id];
    float is_fus_target_b = is_fus_target[replica_id];
    float arg_fraction_b = arg_fraction[replica_id];
    float aromatic_fraction_b = aromatic_fraction[replica_id];
    float sticker_strength_b = relu_local(sticker_strength[0]) * env_scale_b;
    float bridge_strength_b = relu_local(bridge_strength[0]) * env_scale_b;

    float llps_gain = 1.05f + 0.95f * llps_branch_b;
    float agg_gain = 0.85f + 0.65f * agg_branch_b;
    float helix_gain = 0.55f + 0.20f * helix_branch_b;
    float llps_dominant = (llps_branch_b >= fmaxf(agg_branch_b, helix_branch_b)) ? 1.0f : 0.0f;
    float llps_pair_gain = 1.0f + llps_dominant * (0.55f * fminf(aromatic_fraction_b / 0.16f, 1.5f));
    float cation_pi_gain = 1.0f + llps_dominant * (0.70f * fminf(arg_fraction_b / 0.10f, 1.5f));
    float pi_pi_gain = 1.0f + llps_dominant * (0.35f * fminf(aromatic_fraction_b / 0.16f, 1.5f));
    float sticker_gain = 1.0f + llps_dominant * (0.25f * fminf((aromatic_fraction_b + arg_fraction_b) / 0.24f, 1.5f));
    cation_pi_gain *= 1.0f + 0.35f * is_hnrn_target_b;
    pi_pi_gain *= 1.0f + 0.12f * is_hnrn_target_b + 0.28f * is_fus_target_b;
    sticker_gain *= 1.0f + 0.10f * is_hnrn_target_b + 0.12f * is_fus_target_b;
    float bridge_gain = (1.0f + 0.85f * llps_branch_b) * (1.0f + 0.55f * is_hnrn_target_b + 0.30f * is_fus_target_b);

    int i3 = idx * 3;
    float ca_ix = ca[i3 + 0];
    float ca_iy = ca[i3 + 1];
    float ca_iz = ca[i3 + 2];
    float sc_ix = sc[i3 + 0];
    float sc_iy = sc[i3 + 1];
    float sc_iz = sc[i3 + 2];
    float exposure_local_i = 1.0f / (1.0f + 0.10f * local_density[idx]);
    bool aro_i = aromatic_mask[idx] != 0;
    bool cat_i = cationic_mask[idx] != 0;
    bool st_i = sticker_mask[idx] != 0;

    float sfx = 0.0f;
    float sfy = 0.0f;
    float sfz = 0.0f;
    float bfx = 0.0f;
    float bfy = 0.0f;
    float bfz = 0.0f;
    double sticker_contacts_acc = 0.0;
    double pi_pi_contacts_acc = 0.0;
    double cation_pi_contacts_acc = 0.0;
    double bridge_contacts_acc = 0.0;

    #pragma unroll 2
    for (int k = 0; k < max_neighbors; ++k) {
        int row_idx = row_start + k;
        if (nb_mask[row_idx] == 0) continue;

        int64_t n_local = nb_idx[row_idx];
        if (n_local < 0 || n_local >= n_per_replica) continue;
        int local_j = (int)n_local;
        if (local_j == local_i) continue;
        int gap = abs(local_j - local_i);
        if (gap < 3) continue;

        int j = replica_start + local_j;
        int j3 = j * 3;
        float ca_jx = ca[j3 + 0];
        float ca_jy = ca[j3 + 1];
        float ca_jz = ca[j3 + 2];
        float sc_jx = sc[j3 + 0];
        float sc_jy = sc[j3 + 1];
        float sc_jz = sc[j3 + 2];
        float exposure_local_j = 1.0f / (1.0f + 0.10f * local_density[j]);
        float exposure_pair = exposure_local_i * exposure_local_j;
        bool aro_j = aromatic_mask[j] != 0;
        bool cat_j = cationic_mask[j] != 0;
        bool st_j = sticker_mask[j] != 0;

        float d_sc = norm3_local(sc_ix - sc_jx, sc_iy - sc_jy, sc_iz - sc_jz);
        float pi_pi_well = expf(-sqr_local((d_sc - 9.2f) / 2.1f));
        float cation_pi_well = expf(-sqr_local((d_sc - 10.0f) / 2.5f));
        float sticker_well = expf(-sqr_local((d_sc - 9.8f) / 2.7f));
        bool pi_pi = aro_i && aro_j;
        bool cation_pi = (cat_i && aro_j) || (aro_i && cat_j);
        bool aromatic_sticker = st_i && st_j;

        float sticker_mag = (
            pi_pi_gain * (0.55f * llps_gain + 0.30f * agg_gain) * (pi_pi ? 1.0f : 0.0f) * pi_pi_well
            + cation_pi_gain * (1.05f * llps_gain + 0.10f * helix_gain) * (cation_pi ? 1.0f : 0.0f) * cation_pi_well
            + llps_pair_gain * sticker_gain * (0.28f * llps_gain + 0.42f * agg_gain + 0.12f * helix_gain) * (aromatic_sticker ? 1.0f : 0.0f) * sticker_well
        );
        sticker_mag = sticker_strength_b * exposure_pair * sticker_mag;

        float sc_drx = sc_ix - sc_jx;
        float sc_dry = sc_iy - sc_jy;
        float sc_drz = sc_iz - sc_jz;
        float sc_norm = norm3_local(sc_drx, sc_dry, sc_drz);
        sfx += -sticker_mag * (sc_drx / sc_norm);
        sfy += -sticker_mag * (sc_dry / sc_norm);
        sfz += -sticker_mag * (sc_drz / sc_norm);
        if (collect_contacts) {
            if (sticker_mag > 0.02f) sticker_contacts_acc += 1.0;
            if (pi_pi && pi_pi_well > 0.4f) pi_pi_contacts_acc += 1.0;
            if (cation_pi && cation_pi_well > 0.4f) cation_pi_contacts_acc += 1.0;
        }

        if (gap < 4) continue;
        float d_ca = norm3_local(ca_ix - ca_jx, ca_iy - ca_jy, ca_iz - ca_jz);
        float bridge_support = (
            0.55f * (pi_pi ? 1.0f : 0.0f) * expf(-sqr_local((d_ca - 13.4f) / 3.0f))
            + 1.05f * (cation_pi ? 1.0f : 0.0f) * expf(-sqr_local((d_ca - 12.8f) / 2.7f))
            + 0.32f * (aromatic_sticker ? 1.0f : 0.0f) * expf(-sqr_local((d_ca - 13.1f) / 3.1f))
        );
        float bridge_mag = bridge_strength_b * bridge_gain * exposure_pair * bridge_support * is_llps_target_b;
        float ca_drx = ca_ix - ca_jx;
        float ca_dry = ca_iy - ca_jy;
        float ca_drz = ca_iz - ca_jz;
        float ca_norm = norm3_local(ca_drx, ca_dry, ca_drz);
        bfx += -bridge_mag * (ca_drx / ca_norm);
        bfy += -bridge_mag * (ca_dry / ca_norm);
        bfz += -bridge_mag * (ca_drz / ca_norm);
        if (collect_contacts && bridge_support > 0.12f) bridge_contacts_acc += 1.0;
    }

    sticker_force[i3 + 0] = sfx;
    sticker_force[i3 + 1] = sfy;
    sticker_force[i3 + 2] = sfz;
    bridge_force[i3 + 0] = bfx;
    bridge_force[i3 + 1] = bfy;
    bridge_force[i3 + 2] = bfz;
    if (collect_contacts) {
        atomicAdd(&sticker_contacts[replica_id], (float)sticker_contacts_acc);
        atomicAdd(&pi_pi_contacts[replica_id], (float)pi_pi_contacts_acc);
        atomicAdd(&cation_pi_contacts[replica_id], (float)cation_pi_contacts_acc);
        atomicAdd(&bridge_contacts[replica_id], (float)bridge_contacts_acc);
    }
}

extern "C" __global__
void idp_virtual_hbond_finalize_kernel(
    float* __restrict__ contacts,
    float* __restrict__ mean_distance,
    int batch_size
) {
    int replica_id = blockIdx.x * blockDim.x + threadIdx.x;
    if (replica_id >= batch_size) return;
    float c = contacts[replica_id];
    if (c > 0.0f) {
        mean_distance[replica_id] = mean_distance[replica_id] / c;
    } else {
        mean_distance[replica_id] = 0.0f;
    }
}

extern "C" int launch_idp_virtual_hbond_nblist_kernel(
    const float* donor,
    const float* acceptor,
    const float* ca,
    const float* sc,
    const float* disorder,
    const uint8_t* aromatic_mask,
    const uint8_t* cationic_mask,
    const uint8_t* sticker_mask,
    float* local_density,
    const int64_t* nb_idx,
    const float* nb_dist,
    const uint8_t* nb_mask,
    float* force,
    float* contacts,
    float* mean_distance,
    int n_per_replica,
    int batch_size,
    int max_neighbors,
    const float* center,
    const float* width,
    const float* vh_strength,
    const float* env_scale,
    const float* vh_scale,
    const float* contact_gain,
    const float* exposure_sensitivity,
    const float* exposure_gain_scale,
    const float* llps_branch,
    const float* is_llps_target,
    const float* is_hnrn_target,
    const float* is_fus_target,
    const float* unsat_penalty,
    uintptr_t stream_ptr
) {
    const int total_atoms = n_per_replica * batch_size;
    const int threads = 256;
    const int blocks = (total_atoms + threads - 1) / threads;
    hipError_t err = hipSuccess;
    hipStream_t stream = reinterpret_cast<hipStream_t>(stream_ptr);

    hipLaunchKernelGGL(
        idp_local_density_nblist_kernel,
        dim3(blocks), dim3(threads),
        0, stream,
        nb_idx,
        nb_dist,
        nb_mask,
        local_density,
        n_per_replica,
        total_atoms,
        max_neighbors,
        3
    );
    err = hipGetLastError();
    if (err != hipSuccess) {
        return -995 - (int)err;
    }

    err = hipMemsetAsync(contacts, 0, sizeof(float) * (size_t)batch_size, stream);
    if (err != hipSuccess) {
        return -996 - (int)err;
    }
    err = hipMemsetAsync(mean_distance, 0, sizeof(float) * (size_t)batch_size, stream);
    if (err != hipSuccess) {
        return -997 - (int)err;
    }

    hipLaunchKernelGGL(
        idp_virtual_hbond_nblist_kernel,
        dim3(blocks), dim3(threads),
        0, stream,
        donor,
        acceptor,
        ca,
        sc,
        disorder,
        aromatic_mask,
        cationic_mask,
        sticker_mask,
        local_density,
        nb_idx,
        nb_mask,
        force,
        contacts,
        mean_distance,
        n_per_replica,
        total_atoms,
        max_neighbors,
        center,
        width,
        vh_strength,
        env_scale,
        vh_scale,
        contact_gain,
        exposure_sensitivity,
        exposure_gain_scale,
        llps_branch,
        is_llps_target,
        is_hnrn_target,
        is_fus_target,
        unsat_penalty
    );

    err = hipGetLastError();
    if (err != hipSuccess) {
        return -1000 - (int)err;
    }

    const int finalize_threads = 256;
    const int finalize_blocks = (batch_size + finalize_threads - 1) / finalize_threads;
    hipLaunchKernelGGL(
        idp_virtual_hbond_finalize_kernel,
        dim3(finalize_blocks), dim3(finalize_threads),
        0, stream,
        contacts,
        mean_distance,
        batch_size
    );

    err = hipGetLastError();
    if (err != hipSuccess) {
        return -1001 - (int)err;
    }
    return 0;
}

extern "C" int launch_idp_local_density_nblist_kernel(
    const int64_t* nb_idx,
    const float* nb_dist,
    const uint8_t* nb_mask,
    float* out_density,
    int n_per_replica,
    int batch_size,
    int max_neighbors,
    int min_gap
) {
    const int total_atoms = n_per_replica * batch_size;
    const int threads = 256;
    const int blocks = (total_atoms + threads - 1) / threads;
    hipError_t err = hipMemset(out_density, 0, sizeof(float) * (size_t)total_atoms);
    if (err != hipSuccess) {
        return -1100 - (int)err;
    }
    hipLaunchKernelGGL(
        idp_local_density_nblist_kernel,
        dim3(blocks), dim3(threads),
        0, 0,
        nb_idx,
        nb_dist,
        nb_mask,
        out_density,
        n_per_replica,
        total_atoms,
        max_neighbors,
        min_gap
    );
    err = hipGetLastError();
    if (err != hipSuccess) {
        return -1101 - (int)err;
    }
    return 0;
}

extern "C" int launch_idp_sticker_bridge_nblist_kernel(
    const float* ca,
    const float* sc,
    const uint8_t* aromatic_mask,
    const uint8_t* cationic_mask,
    const uint8_t* sticker_mask,
    float* local_density,
    const int64_t* nb_idx,
    const float* nb_dist,
    const uint8_t* nb_mask,
    float* sticker_force,
    float* bridge_force,
    float* sticker_contacts,
    float* pi_pi_contacts,
    float* cation_pi_contacts,
    float* bridge_contacts,
    int n_per_replica,
    int batch_size,
    int max_neighbors,
    const float* sticker_strength,
    const float* bridge_strength,
    const float* env_scale,
    const float* llps_branch,
    const float* agg_branch,
    const float* helix_branch,
    const float* is_llps_target,
    const float* is_hnrn_target,
    const float* is_fus_target,
    const float* arg_fraction,
    const float* aromatic_fraction,
    int collect_contacts,
    uintptr_t stream_ptr
) {
    const int total_atoms = n_per_replica * batch_size;
    const int threads = 256;
    const int blocks = (total_atoms + threads - 1) / threads;
    hipError_t err = hipSuccess;
    hipStream_t stream = reinterpret_cast<hipStream_t>(stream_ptr);

    hipLaunchKernelGGL(
        idp_local_density_nblist_kernel,
        dim3(blocks), dim3(threads),
        0, stream,
        nb_idx,
        nb_dist,
        nb_mask,
        local_density,
        n_per_replica,
        total_atoms,
        max_neighbors,
        4
    );
    err = hipGetLastError();
    if (err != hipSuccess) {
        return -1200 - (int)err;
    }
    if (collect_contacts != 0) {
        err = hipMemsetAsync(sticker_contacts, 0, sizeof(float) * (size_t)batch_size, stream);
        if (err != hipSuccess) return -1201 - (int)err;
        err = hipMemsetAsync(pi_pi_contacts, 0, sizeof(float) * (size_t)batch_size, stream);
        if (err != hipSuccess) return -1202 - (int)err;
        err = hipMemsetAsync(cation_pi_contacts, 0, sizeof(float) * (size_t)batch_size, stream);
        if (err != hipSuccess) return -1203 - (int)err;
        err = hipMemsetAsync(bridge_contacts, 0, sizeof(float) * (size_t)batch_size, stream);
        if (err != hipSuccess) return -1204 - (int)err;
    }

    hipLaunchKernelGGL(
        idp_sticker_bridge_nblist_kernel,
        dim3(blocks), dim3(threads),
        0, stream,
        ca,
        sc,
        aromatic_mask,
        cationic_mask,
        sticker_mask,
        local_density,
        nb_idx,
        nb_mask,
        sticker_force,
        bridge_force,
        sticker_contacts,
        pi_pi_contacts,
        cation_pi_contacts,
        bridge_contacts,
        n_per_replica,
        total_atoms,
        max_neighbors,
        sticker_strength,
        bridge_strength,
        env_scale,
        llps_branch,
        agg_branch,
        helix_branch,
        is_llps_target,
        is_hnrn_target,
        is_fus_target,
        arg_fraction,
        aromatic_fraction,
        collect_contacts
    );
    err = hipGetLastError();
    if (err != hipSuccess) {
        return -1205 - (int)err;
    }
    return 0;
}

extern "C" int launch_ligand_direct_rollout_kernel(
    float* pos,
    float* vel,
    float* force,
    float* energy,
    float* selected_out,
    const float* pocket,
    const float* pocket_attract,
    const float* protein_repulse,
    const float* bond_ref,
    const float* noise,
    int n_per_replica,
    int batch_size,
    int n_protein,
    int n_ligand,
    int frames,
    const int* keep_steps,
    int n_keep,
    float box_size,
    float sigma,
    float epsilon,
    float bond_k,
    float repulse_cutoff,
    float max_pocket_radius,
    float force_clip,
    float dt,
    float gamma
) {
    if (!pos || !vel || !force || !energy || !selected_out || !pocket || !pocket_attract || !protein_repulse || !bond_ref) return -10;
    if (n_per_replica <= 0 || batch_size <= 0 || n_protein < 0 || n_ligand <= 0 || frames <= 0) return -11;
    if (!keep_steps || n_keep <= 0) return -12;

    int total_atoms = n_per_replica * batch_size;
    int threads = 256;
    int atom_blocks = (total_atoms + threads - 1) / threads;
    int ligand_blocks = ((batch_size * n_ligand) + threads - 1) / threads;
    int batch_blocks = (batch_size + threads - 1) / threads;
    int keep_pos = 0;

    for (int step = 0; step < frames; ++step) {
        hipError_t err = hipMemset(energy, 0, (size_t)batch_size * sizeof(float));
        if (err != hipSuccess) return -20;

        int nb_status = launch_nonbonded_kernel(
            pos,
            force,
            energy,
            n_per_replica,
            total_atoms,
            box_size,
            sigma,
            epsilon
        );
        if (nb_status != 0) return -21;

        hipLaunchKernelGGL(
            ligand_extra_force_kernel,
            dim3(ligand_blocks), dim3(threads),
            0, 0,
            pos, force, pocket, pocket_attract, protein_repulse, bond_ref,
            n_per_replica, batch_size, n_protein, n_ligand, bond_k, repulse_cutoff
        );
        err = hipGetLastError();
        if (err != hipSuccess) return -22;

        if (force_clip > 0.0f) {
            hipLaunchKernelGGL(
                clamp_force_kernel,
                dim3(atom_blocks), dim3(threads),
                0, 0,
                force, total_atoms, force_clip
            );
            err = hipGetLastError();
            if (err != hipSuccess) return -23;
        }

        const float* noise_step = noise ? (noise + ((size_t)step * (size_t)total_atoms * 3ULL)) : nullptr;
        hipLaunchKernelGGL(
            integrator_step_kernel,
            dim3(atom_blocks), dim3(threads),
            0, 0,
            pos, vel, force, noise_step, total_atoms, dt, gamma
        );
        err = hipGetLastError();
        if (err != hipSuccess) return -24;

        if (max_pocket_radius > 0.0f) {
            hipLaunchKernelGGL(
                pocket_radius_clip_kernel,
                dim3(batch_blocks), dim3(threads),
                0, 0,
                pos, pocket, n_per_replica, batch_size, n_protein, n_ligand, max_pocket_radius
            );
            err = hipGetLastError();
            if (err != hipSuccess) return -25;
        }

        if (keep_pos < n_keep && step == keep_steps[keep_pos]) {
            hipLaunchKernelGGL(
                capture_ligand_frame_kernel,
                dim3(ligand_blocks), dim3(threads),
                0, 0,
                pos, selected_out, n_per_replica, batch_size, n_protein, n_ligand, n_keep, keep_pos
            );
            err = hipGetLastError();
            if (err != hipSuccess) return -26;
            keep_pos += 1;
        }
    }

    return hipGetLastError() == hipSuccess ? 0 : -27;
}
