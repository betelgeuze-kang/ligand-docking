#ifndef BETELGEUZE_NATIVE_DOCKING_FIXED64_SINGLE_ANCHOR_PROVIDER_H
#define BETELGEUZE_NATIVE_DOCKING_FIXED64_SINGLE_ANCHOR_PROVIDER_H

#include "betelgeuze/engine.h"

#include <stdint.h>

typedef struct bg_native_fixed64_single_anchor_kernel_input_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_docking_fixed64_lane lane;
    bg_docking_fixed64_anchor_kind anchor_kind;
    uint32_t lane_offset;
    uint32_t reserved0;
    uint64_t ligand_atom_count;
    const double *source_x_angstrom;
    const double *source_y_angstrom;
    const double *source_z_angstrom;
    uint64_t ligand_feature_atom_count;
    const double *ligand_feature_x_angstrom;
    const double *ligand_feature_y_angstrom;
    const double *ligand_feature_z_angstrom;
    uint64_t receptor_feature_atom_count;
    const double *receptor_feature_x_angstrom;
    const double *receptor_feature_y_angstrom;
    const double *receptor_feature_z_angstrom;
    double pocket_center_angstrom[3];
    uint64_t reserved[8];
} bg_native_fixed64_single_anchor_kernel_input_v1;

typedef struct bg_native_fixed64_single_anchor_kernel_result_v1 {
    bg_docking_fixed64_single_anchor_status status;
    bg_docking_fixed64_single_anchor_failure failure_code;
    double ligand_anchor_point_angstrom[3];
    double receptor_anchor_point_angstrom[3];
    double target_anchor_point_angstrom[3];
    double local_surface_normal[3];
    double approach_vector[3];
    double ligand_direction[3];
    double alignment_target_direction[3];
    double target_distance_angstrom;
    double twist_angle_radians;
    double quaternion_x;
    double quaternion_y;
    double quaternion_z;
    double quaternion_w;
    double translation_angstrom[3];
    uint8_t coordinates_written;
    uint8_t reserved0[7];
    uint64_t reserved[4];
} bg_native_fixed64_single_anchor_kernel_result_v1;

#endif
