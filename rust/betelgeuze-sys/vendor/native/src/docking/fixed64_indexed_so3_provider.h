#ifndef BETELGEUZE_NATIVE_DOCKING_FIXED64_INDEXED_SO3_PROVIDER_H
#define BETELGEUZE_NATIVE_DOCKING_FIXED64_INDEXED_SO3_PROVIDER_H

#include "betelgeuze/engine.h"

#include <stdint.h>

typedef struct bg_native_fixed64_indexed_so3_kernel_input_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t ligand_atom_count;
    const double *source_x_angstrom;
    const double *source_y_angstrom;
    const double *source_z_angstrom;
    double pocket_center_angstrom[3];
    uint8_t source_seed_sha256[32];
    uint32_t sequence_index;
    uint32_t reserved0;
    uint64_t reserved[8];
} bg_native_fixed64_indexed_so3_kernel_input_v1;

typedef struct bg_native_fixed64_indexed_so3_kernel_result_v1 {
    bg_docking_fixed64_indexed_so3_status status;
    bg_docking_fixed64_indexed_so3_failure failure_code;
    uint32_t accepted_sequence_index;
    uint32_t reserved0;
    uint64_t raw_sequence_index;
    double quaternion_x;
    double quaternion_y;
    double quaternion_z;
    double quaternion_w;
    double translation_angstrom[3];
    double source_centroid_angstrom[3];
    uint8_t coordinates_written;
    uint8_t reserved1[7];
    uint64_t reserved[4];
} bg_native_fixed64_indexed_so3_kernel_result_v1;

#endif
