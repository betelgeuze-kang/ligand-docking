#include "../dynamics/sha256.hpp"
#include "../hip/provider.h"
#include "../internal.hpp"
#include "../rust/provider.h"
#include "fixed64_so3_reference.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif
#ifndef BG_ENABLE_HIP
#  define BG_ENABLE_HIP 0
#endif

namespace betelgeuze::native::docking::fixed64_indexed_so3 {
namespace {

using dynamics::Sha256;

constexpr std::size_t kAllocationCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kOrientationCount =
    BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT;
constexpr std::size_t kMaximumLigandAtoms = 512;
constexpr double kMaximumCoordinateAngstrom = 100'000.0;
constexpr double kGeometryEpsilon = 1.0e-12;
constexpr char kProfileId[] =
    "betelgeuze.engine_v2_mixed64_indexed_source_bound_so3_native/1.1.0";
constexpr char kPlacementSchema[] =
    "betelgeuze.engine_v2_native_fixed64_indexed_so3_placement/1.0.0";

struct Vec3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Quaternion final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 1.0;
};

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

struct Generated final {
    bg_native_fixed64_indexed_so3_kernel_result_v1 result{};
    std::vector<double> x;
    std::vector<double> y;
    std::vector<double> z;
};

class CanonicalHash final {
  public:
    explicit CanonicalHash(const char *domain) noexcept { string(domain); }

    void byte(uint8_t value) noexcept { hash_.update(&value, 1); }

    void u32(uint32_t value) noexcept {
        std::array<uint8_t, 4> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void u64(uint64_t value) noexcept {
        std::array<uint8_t, 8> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void size(std::size_t value) noexcept {
        u64(static_cast<uint64_t>(value));
    }

    void f64(double value) noexcept {
        if (value == 0.0) {
            value = 0.0;
        }
        uint64_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value));
        std::memcpy(&bits, &value, sizeof(bits));
        u64(bits);
    }

    void bytes(const uint8_t *values, std::size_t count) noexcept {
        size(count);
        hash_.update(values, count);
    }

    void string(const char *value) noexcept {
        bytes(
            reinterpret_cast<const uint8_t *>(value),
            std::strlen(value));
    }

    void digest(const uint8_t (&value)[32]) noexcept {
        hash_.update(value, 32);
    }

    void digest(const std::array<uint8_t, 32> &value) noexcept {
        hash_.update(value.data(), value.size());
    }

    void vec3(Vec3 value) noexcept {
        f64(value.x);
        f64(value.y);
        f64(value.z);
    }

    [[nodiscard]] std::array<uint8_t, 32> finish() noexcept {
        return hash_.finish();
    }

  private:
    Sha256 hash_;
};

template <typename Type>
[[nodiscard]] bool make_range(
    const Type *pointer,
    std::size_t count,
    MemoryRange *output) noexcept {
    if (pointer == nullptr || output == nullptr || count == 0 ||
        count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return false;
    }
    const std::size_t bytes = count * sizeof(Type);
    const uintptr_t begin = reinterpret_cast<uintptr_t>(pointer);
    if (begin > std::numeric_limits<uintptr_t>::max() - bytes) {
        return false;
    }
    *output = {begin, begin + bytes};
    return true;
}

[[nodiscard]] bool overlaps(MemoryRange left, MemoryRange right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

[[nodiscard]] bool finite_coordinate(double value) noexcept {
    return std::isfinite(value) &&
           std::abs(value) <= kMaximumCoordinateAngstrom;
}

[[nodiscard]] Vec3 rotate(Quaternion quaternion, Vec3 vector) noexcept {
    const Vec3 twice_cross = {
        2.0 * (quaternion.y * vector.z - quaternion.z * vector.y),
        2.0 * (quaternion.z * vector.x - quaternion.x * vector.z),
        2.0 * (quaternion.x * vector.y - quaternion.y * vector.x),
    };
    return {
        vector.x + quaternion.w * twice_cross.x +
            quaternion.y * twice_cross.z - quaternion.z * twice_cross.y,
        vector.y + quaternion.w * twice_cross.y +
            quaternion.z * twice_cross.x - quaternion.x * twice_cross.z,
        vector.z + quaternion.w * twice_cross.z +
            quaternion.x * twice_cross.y - quaternion.y * twice_cross.x,
    };
}

[[nodiscard]] bg_status checked_count(
    uint64_t value,
    std::size_t *count) noexcept {
    if (value == 0 || value > kMaximumLigandAtoms) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "indexed SO3 ligand denominator is outside native bounds");
    }
    *count = static_cast<std::size_t>(value);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_input(
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    std::size_t *ligand_count,
    Vec3 *pocket_normal) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "indexed SO3 input size does not match ABI v1",
        "indexed SO3 input ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (input.reserved0 != 0 || !reserved_is_zero(input.reserved) ||
        !reserved_is_zero(input.source.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "indexed SO3 input reserved fields must be zero");
    }
    if (!digest_present(input.allocation_inventory_sha256) ||
        !digest_present(input.allocation_receipt_sha256) ||
        !digest_present(input.source.receipt_sha256) ||
        !digest_present(input.source.proposal_sha256) ||
        !digest_present(input.source.coordinate_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "indexed SO3 source and allocation identities must be present");
    }
    if (input.allocation_row_count != kAllocationCount ||
        input.allocation_rows == nullptr ||
        !pointer_is_aligned(input.allocation_rows) ||
        input.slot_index >= kAllocationCount) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "indexed SO3 allocation snapshot or slot is invalid");
    }
    status = fixed64_allocation::verify_snapshot(
        input.allocation_inventory_sha256,
        input.allocation_receipt_sha256,
        input.allocation_rows,
        static_cast<std::size_t>(input.allocation_row_count));
    if (status != BG_STATUS_OK) return status;
    const auto &row = input.allocation_rows[input.slot_index];
    if ((row.lane != BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3 &&
         row.lane != BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3) ||
        row.status != BG_DOCKING_FIXED64_ALLOCATION_ROW_READY ||
        row.generation_eligible != UINT8_C(1) ||
        row.generation_parent_role !=
            BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT ||
        row.so3_sequence_index < 0 ||
        row.so3_sequence_index >=
            static_cast<int32_t>(kOrientationCount) ||
        std::memcmp(
            row.generation_parent_receipt_sha256,
            input.source.receipt_sha256,
            32) != 0 ||
        std::memcmp(
            row.generation_parent_proposal_sha256,
            input.source.proposal_sha256,
            32) != 0 ||
        std::memcmp(
            row.generation_parent_coordinate_sha256,
            input.source.coordinate_sha256,
            32) != 0 ||
        (row.lane == BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3 &&
         row.selected_source_receipt_count != 0) ||
        (row.lane == BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3 &&
         (row.selected_source_receipt_count != 1 ||
          std::memcmp(
              row.selected_source_receipt_sha256[0],
              input.source.receipt_sha256,
              32) != 0))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "indexed SO3 source is cross-wired to its allocation slot");
    }
    status = checked_count(input.ligand_atom_count, ligand_count);
    if (status != BG_STATUS_OK) return status;
    const std::array<const double *, 3> channels = {
        input.source_x_angstrom,
        input.source_y_angstrom,
        input.source_z_angstrom,
    };
    for (const double *channel : channels) {
        if (channel == nullptr || !pointer_is_aligned(channel)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "indexed SO3 source channel is null or misaligned");
        }
        for (std::size_t atom = 0; atom < *ligand_count; ++atom) {
            if (!finite_coordinate(channel[atom])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "indexed SO3 source coordinate is outside native bounds");
            }
        }
    }
    Vec3 normal{};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if (!finite_coordinate(input.pocket_center_angstrom[axis]) ||
            !std::isfinite(input.pocket_normal[axis])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "indexed SO3 pocket geometry is non-finite");
        }
    }
    normal = {
        input.pocket_normal[0],
        input.pocket_normal[1],
        input.pocket_normal[2],
    };
    const double maximum =
        std::max({std::abs(normal.x), std::abs(normal.y), std::abs(normal.z)});
    if (maximum <= kGeometryEpsilon) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "indexed SO3 pocket normal is degenerate");
    }
    const double scaled_norm = std::hypot(
        std::hypot(normal.x / maximum, normal.y / maximum),
        normal.z / maximum);
    const double inverse = (1.0 / maximum) / scaled_norm;
    *pocket_normal = {
        normal.x * inverse,
        normal.y * inverse,
        normal.z * inverse,
    };
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_output(
    const bg_context &context,
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    const bg_docking_fixed64_indexed_so3_output_v1 &output,
    std::size_t ligand_count) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "indexed SO3 output size does not match ABI v1",
        "indexed SO3 output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (output.coordinate_capacity < ligand_count ||
        output.x_angstrom == nullptr || output.y_angstrom == nullptr ||
        output.z_angstrom == nullptr ||
        !pointer_is_aligned(output.x_angstrom) ||
        !pointer_is_aligned(output.y_angstrom) ||
        !pointer_is_aligned(output.z_angstrom)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "indexed SO3 output requires aligned ligand coordinate channels");
    }
    if (!std::all_of(
            std::begin(output.reserved0), std::end(output.reserved0),
            [](uint8_t value) { return value == UINT8_C(0); }) ||
        !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "indexed SO3 output reserved fields must be zero");
    }
    std::array<MemoryRange, 10> ranges{};
    if (!make_range(&context, 1, &ranges[0]) ||
        !make_range(&input, 1, &ranges[1]) ||
        !make_range(&output, 1, &ranges[2]) ||
        !make_range(input.allocation_rows, kAllocationCount, &ranges[3]) ||
        !make_range(input.source_x_angstrom, ligand_count, &ranges[4]) ||
        !make_range(input.source_y_angstrom, ligand_count, &ranges[5]) ||
        !make_range(input.source_z_angstrom, ligand_count, &ranges[6]) ||
        !make_range(output.x_angstrom, ligand_count, &ranges[7]) ||
        !make_range(output.y_angstrom, ligand_count, &ranges[8]) ||
        !make_range(output.z_angstrom, ligand_count, &ranges[9])) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "indexed SO3 descriptor range overflows host address space");
    }
    for (std::size_t left = 0; left < ranges.size(); ++left) {
        for (std::size_t right = left + 1; right < ranges.size(); ++right) {
            if (overlaps(ranges[left], ranges[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "indexed SO3 input and output ranges overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] std::array<uint8_t, 32> coordinate_sha256(
    const double *x,
    const double *y,
    const double *z,
    std::size_t count) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_coordinates/native-v1");
    hash.size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash.vec3({x[index], y[index], z[index]});
    }
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> source_seed_sha256(
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    Vec3 pocket_normal) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_indexed_so3_seed/native-v1");
    hash.digest(input.source.receipt_sha256);
    hash.digest(input.source.proposal_sha256);
    hash.digest(input.source.coordinate_sha256);
    hash.vec3({
        input.pocket_center_angstrom[0],
        input.pocket_center_angstrom[1],
        input.pocket_center_angstrom[2]});
    hash.vec3(pocket_normal);
    hash.string(kProfileId);
    return hash.finish();
}

[[nodiscard]] Generated generate_cpp(
    const bg_context &context,
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    const std::array<uint8_t, 32> &seed,
    std::size_t ligand_count,
    bg_status *out_status) {
    *out_status = BG_STATUS_OK;
    Generated generated{};
    generated.x.resize(ligand_count);
    generated.y.resize(ligand_count);
    generated.z.resize(ligand_count);
    const auto &allocation = input.allocation_rows[input.slot_index];
    generated.result.accepted_sequence_index =
        static_cast<uint32_t>(allocation.so3_sequence_index);
    Vec3 centroid{};
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        centroid.x += input.source_x_angstrom[atom];
        centroid.y += input.source_y_angstrom[atom];
        centroid.z += input.source_z_angstrom[atom];
    }
    const double inverse = 1.0 / static_cast<double>(ligand_count);
    centroid = {centroid.x * inverse, centroid.y * inverse, centroid.z * inverse};
    generated.result.source_centroid_angstrom[0] = centroid.x;
    generated.result.source_centroid_angstrom[1] = centroid.y;
    generated.result.source_centroid_angstrom[2] = centroid.z;
    bool distinct = false;
    for (std::size_t atom = 1; atom < ligand_count; ++atom) {
        const double x = input.source_x_angstrom[atom] - input.source_x_angstrom[0];
        const double y = input.source_y_angstrom[atom] - input.source_y_angstrom[0];
        const double z = input.source_z_angstrom[atom] - input.source_z_angstrom[0];
        distinct = distinct || x * x + y * y + z * z > kGeometryEpsilon;
    }
    if (!distinct) {
        generated.result.status =
            BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE;
        generated.result.failure_code =
            BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY;
        generated.x.clear();
        generated.y.clear();
        generated.z.clear();
        return generated;
    }

    bg_docking_fixed64_so3_input_v1 sequence_input{};
    sequence_input.struct_size = sizeof(sequence_input);
    sequence_input.abi_version = BG_ABI_VERSION;
    std::copy(seed.begin(), seed.end(), sequence_input.source_seed_sha256);
    std::array<bg_docking_fixed64_so3_row_v1, kOrientationCount> sequence{};
    bg_docking_fixed64_so3_output_v1 sequence_output{};
    sequence_output.struct_size = sizeof(sequence_output);
    sequence_output.abi_version = BG_ABI_VERSION;
    sequence_output.row_capacity = sequence.size();
    sequence_output.rows = sequence.data();
    const bg_status status = bg_docking_fixed64_so3_v1_generate(
        &context, &sequence_input, &sequence_output);
    if (status != BG_STATUS_OK) {
        generated.x.clear();
        generated.y.clear();
        generated.z.clear();
        *out_status = status;
        return generated;
    }
    const auto &selected = sequence[static_cast<std::size_t>(
        allocation.so3_sequence_index)];
    const Quaternion quaternion = {
        selected.quaternion_x,
        selected.quaternion_y,
        selected.quaternion_z,
        selected.quaternion_w,
    };
    const Vec3 center = {
        input.pocket_center_angstrom[0],
        input.pocket_center_angstrom[1],
        input.pocket_center_angstrom[2],
    };
    const Vec3 rotated_centroid = rotate(quaternion, centroid);
    const Vec3 translation = {
        center.x - rotated_centroid.x,
        center.y - rotated_centroid.y,
        center.z - rotated_centroid.z,
    };
    generated.result.raw_sequence_index = selected.raw_sequence_index;
    generated.result.quaternion_x = quaternion.x;
    generated.result.quaternion_y = quaternion.y;
    generated.result.quaternion_z = quaternion.z;
    generated.result.quaternion_w = quaternion.w;
    generated.result.translation_angstrom[0] = translation.x;
    generated.result.translation_angstrom[1] = translation.y;
    generated.result.translation_angstrom[2] = translation.z;
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        const Vec3 placed = rotate(
            quaternion,
            {input.source_x_angstrom[atom],
             input.source_y_angstrom[atom],
             input.source_z_angstrom[atom]});
        generated.x[atom] = placed.x + translation.x;
        generated.y[atom] = placed.y + translation.y;
        generated.z[atom] = placed.z + translation.z;
        if (!finite_coordinate(generated.x[atom]) ||
            !finite_coordinate(generated.y[atom]) ||
            !finite_coordinate(generated.z[atom])) {
            generated.result.status =
                BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE;
            generated.result.failure_code =
                BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT;
            generated.x.clear();
            generated.y.clear();
            generated.z.clear();
            return generated;
        }
    }
    generated.result.status = BG_DOCKING_FIXED64_INDEXED_SO3_PLACED;
    generated.result.failure_code =
        BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE;
    generated.result.coordinates_written = UINT8_C(1);
    return generated;
}

[[nodiscard]] bg_status provider_failure(
    int32_t raw_status,
    const char *message,
    const char *fallback) noexcept {
    return fail(
        static_cast<bg_status>(raw_status),
        message != nullptr && message[0] != '\0' ? message : fallback);
}

[[nodiscard]] bg_status generate_backend(
    const bg_context &context,
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    const std::array<uint8_t, 32> &seed,
    std::size_t ligand_count,
    Generated *generated) {
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        bg_status status = BG_STATUS_OK;
        *generated = generate_cpp(
            context, input, seed, ligand_count, &status);
        return status;
    }
    generated->x.assign(ligand_count, 0.0);
    generated->y.assign(ligand_count, 0.0);
    generated->z.assign(ligand_count, 0.0);
    bg_native_fixed64_indexed_so3_kernel_input_v1 kernel_input{};
    kernel_input.struct_size = sizeof(kernel_input);
    kernel_input.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    kernel_input.ligand_atom_count = ligand_count;
    kernel_input.source_x_angstrom = input.source_x_angstrom;
    kernel_input.source_y_angstrom = input.source_y_angstrom;
    kernel_input.source_z_angstrom = input.source_z_angstrom;
    std::copy(
        std::begin(input.pocket_center_angstrom),
        std::end(input.pocket_center_angstrom),
        kernel_input.pocket_center_angstrom);
    std::copy(seed.begin(), seed.end(), kernel_input.source_seed_sha256);
    kernel_input.sequence_index = static_cast<uint32_t>(
        input.allocation_rows[input.slot_index].so3_sequence_index);
    int32_t provider_status = BG_STATUS_BACKEND_UNAVAILABLE;
    if (context.backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_error_v1 error{};
        error.struct_size = sizeof(error);
        error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
        provider_status = bg_rust_cpu_docking_fixed64_indexed_so3_v1_place(
            &kernel_input,
            generated->x.data(),
            generated->y.data(),
            generated->z.data(),
            &generated->result,
            &error);
        return provider_status == BG_STATUS_OK
            ? BG_STATUS_OK
            : provider_failure(
                  provider_status,
                  error.message,
                  "rust_cpu indexed SO3 placement failed");
    }
#if BG_HAS_HIP_SAFE_PROVIDER
    if (context.backend == BG_BACKEND_HIP_SAFE) {
        char error[BG_HIP_SAFE_ERROR_CAPACITY]{};
        provider_status = bg_hip_safe_docking_fixed64_indexed_so3_v1_place(
            context.device_ordinal,
            &kernel_input,
            generated->x.data(),
            generated->y.data(),
            generated->z.data(),
            &generated->result,
            error,
            sizeof(error));
        return provider_status == BG_STATUS_OK
            ? BG_STATUS_OK
            : provider_failure(
                  provider_status,
                  error,
                  "hip_safe indexed SO3 placement failed");
    }
#endif
#if BG_ENABLE_HIP
    if (context.backend == BG_BACKEND_HIP_FAST) {
        char error[BG_HIP_SAFE_ERROR_CAPACITY]{};
        provider_status = bg_hip_fast_docking_fixed64_indexed_so3_v1_place(
            context.device_ordinal,
            &kernel_input,
            generated->x.data(),
            generated->y.data(),
            generated->z.data(),
            &generated->result,
            error,
            sizeof(error));
        return provider_status == BG_STATUS_OK
            ? BG_STATUS_OK
            : provider_failure(
                  provider_status,
                  error,
                  "hip_fast indexed SO3 placement failed");
    }
#endif
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "selected backend has no indexed SO3 placement kernel; fallback is forbidden");
}

[[nodiscard]] bg_status validate_generated(
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    const Generated &generated,
    std::size_t ligand_count,
    const std::array<uint8_t, 32> &seed,
    bg_backend backend) noexcept {
    const auto &result = generated.result;
    const uint32_t expected_index = static_cast<uint32_t>(
        input.allocation_rows[input.slot_index].so3_sequence_index);
    if (result.reserved0 != 0 ||
        !std::all_of(
            std::begin(result.reserved1), std::end(result.reserved1),
            [](uint8_t value) { return value == UINT8_C(0); }) ||
        !reserved_is_zero(result.reserved) ||
        result.accepted_sequence_index != expected_index) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            "indexed SO3 backend result violates its private ABI");
    }
    const double tolerance =
        backend == BG_BACKEND_HIP_FAST
            ? 2.0e-9
            : (backend == BG_BACKEND_HIP_SAFE ? 2.0e-10 : 2.0e-12);
    const auto close = [tolerance](double observed, double expected) noexcept {
        const double scale =
            std::max({1.0, std::abs(observed), std::abs(expected)});
        return std::isfinite(observed) && std::isfinite(expected) &&
               std::abs(observed - expected) <= tolerance * scale;
    };
    const auto canonical_component = [&close](
                                         double observed,
                                         double expected) noexcept {
        return close(observed, expected) &&
               !(observed == 0.0 && std::signbit(observed));
    };

    Vec3 source_centroid{};
    bool distinct = false;
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        source_centroid.x += input.source_x_angstrom[atom];
        source_centroid.y += input.source_y_angstrom[atom];
        source_centroid.z += input.source_z_angstrom[atom];
        if (atom != 0) {
            const double x =
                input.source_x_angstrom[atom] - input.source_x_angstrom[0];
            const double y =
                input.source_y_angstrom[atom] - input.source_y_angstrom[0];
            const double z =
                input.source_z_angstrom[atom] - input.source_z_angstrom[0];
            distinct = distinct || x * x + y * y + z * z > kGeometryEpsilon;
        }
    }
    const double inverse = 1.0 / static_cast<double>(ligand_count);
    source_centroid = {
        source_centroid.x * inverse,
        source_centroid.y * inverse,
        source_centroid.z * inverse,
    };
    if (!close(result.source_centroid_angstrom[0], source_centroid.x) ||
        !close(result.source_centroid_angstrom[1], source_centroid.y) ||
        !close(result.source_centroid_angstrom[2], source_centroid.z)) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            "indexed SO3 backend source centroid is invalid");
    }

    bg_docking_fixed64_so3_input_v1 sequence_input{};
    sequence_input.struct_size = sizeof(sequence_input);
    sequence_input.abi_version = BG_ABI_VERSION;
    std::copy(seed.begin(), seed.end(), sequence_input.source_seed_sha256);
    const auto sequence = fixed64_so3::reference_rows(sequence_input);
    const auto &expected = sequence[expected_index];
    const Quaternion expected_quaternion = distinct
        ? Quaternion{
              expected.quaternion_x,
              expected.quaternion_y,
              expected.quaternion_z,
              expected.quaternion_w,
          }
        : Quaternion{0.0, 0.0, 0.0, 0.0};
    const uint64_t expected_raw_sequence_index =
        distinct ? expected.raw_sequence_index : UINT64_C(0);
    if (result.raw_sequence_index != expected_raw_sequence_index ||
        !canonical_component(result.quaternion_x, expected_quaternion.x) ||
        !canonical_component(result.quaternion_y, expected_quaternion.y) ||
        !canonical_component(result.quaternion_z, expected_quaternion.z) ||
        !canonical_component(result.quaternion_w, expected_quaternion.w)) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            "indexed SO3 backend selected a noncanonical orientation");
    }

    Vec3 expected_translation{};
    if (distinct) {
        const Vec3 rotated_centroid =
            rotate(expected_quaternion, source_centroid);
        expected_translation = {
            input.pocket_center_angstrom[0] - rotated_centroid.x,
            input.pocket_center_angstrom[1] - rotated_centroid.y,
            input.pocket_center_angstrom[2] - rotated_centroid.z,
        };
    }
    if (!close(result.translation_angstrom[0], expected_translation.x) ||
        !close(result.translation_angstrom[1], expected_translation.y) ||
        !close(result.translation_angstrom[2], expected_translation.z)) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            "indexed SO3 backend translation is invalid");
    }

    bool expected_coordinates_valid = distinct;
    if (distinct) {
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            const Vec3 rotated = rotate(
                expected_quaternion,
                {input.source_x_angstrom[atom],
                 input.source_y_angstrom[atom],
                 input.source_z_angstrom[atom]});
            const Vec3 placed = {
                rotated.x + expected_translation.x,
                rotated.y + expected_translation.y,
                rotated.z + expected_translation.z,
            };
            if (!finite_coordinate(placed.x) ||
                !finite_coordinate(placed.y) ||
                !finite_coordinate(placed.z)) {
                expected_coordinates_valid = false;
                break;
            }
        }
    }

    if (expected_coordinates_valid) {
        if (generated.x.size() != ligand_count ||
            generated.y.size() != ligand_count ||
            generated.z.size() != ligand_count) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "indexed SO3 backend omitted valid coordinate channels");
        }
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            const Vec3 rotated = rotate(
                expected_quaternion,
                {input.source_x_angstrom[atom],
                 input.source_y_angstrom[atom],
                 input.source_z_angstrom[atom]});
            const Vec3 placed = {
                rotated.x + expected_translation.x,
                rotated.y + expected_translation.y,
                rotated.z + expected_translation.z,
            };
            if (!finite_coordinate(generated.x[atom]) ||
                !finite_coordinate(generated.y[atom]) ||
                !finite_coordinate(generated.z[atom]) ||
                !close(generated.x[atom], placed.x) ||
                !close(generated.y[atom], placed.y) ||
                !close(generated.z[atom], placed.z)) {
                return fail(
                    BG_STATUS_BACKEND_ERROR,
                    "indexed SO3 backend mutated the rigid placement");
            }
        }
    }

    const auto expected_status = expected_coordinates_valid
        ? BG_DOCKING_FIXED64_INDEXED_SO3_PLACED
        : BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE;
    const auto expected_failure = !distinct
        ? BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY
        : (expected_coordinates_valid
               ? BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE
               : BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT);
    const uint8_t expected_written =
        expected_coordinates_valid ? UINT8_C(1) : UINT8_C(0);
    if (result.status != expected_status ||
        result.failure_code != expected_failure ||
        result.coordinates_written != expected_written) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            "indexed SO3 backend status does not match rederived geometry");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] std::array<uint8_t, 32> placement_receipt(
    const bg_docking_fixed64_indexed_so3_input_v1 &input,
    const Generated &generated,
    bg_backend backend,
    const std::array<uint8_t, 32> &seed,
    const std::array<uint8_t, 32> &coordinate) noexcept {
    const auto &result = generated.result;
    CanonicalHash hash("betelgeuze.fixed64_indexed_so3_abi/native-v1");
    hash.string(kPlacementSchema);
    hash.string(kProfileId);
    hash.digest(input.allocation_inventory_sha256);
    hash.digest(input.allocation_receipt_sha256);
    hash.digest(input.allocation_rows[input.slot_index].slot_receipt_sha256);
    hash.u32(input.slot_index);
    hash.u32(static_cast<uint32_t>(input.allocation_rows[input.slot_index].lane));
    hash.digest(input.source.receipt_sha256);
    hash.digest(input.source.proposal_sha256);
    hash.digest(input.source.coordinate_sha256);
    hash.digest(seed);
    hash.u32(static_cast<uint32_t>(backend));
    hash.u32(static_cast<uint32_t>(result.status));
    hash.u32(static_cast<uint32_t>(result.failure_code));
    hash.u32(result.accepted_sequence_index);
    hash.u64(result.raw_sequence_index);
    hash.f64(result.quaternion_x);
    hash.f64(result.quaternion_y);
    hash.f64(result.quaternion_z);
    hash.f64(result.quaternion_w);
    hash.vec3({
        result.translation_angstrom[0],
        result.translation_angstrom[1],
        result.translation_angstrom[2]});
    hash.vec3({
        result.source_centroid_angstrom[0],
        result.source_centroid_angstrom[1],
        result.source_centroid_angstrom[2]});
    hash.digest(coordinate);
    hash.byte(result.coordinates_written);
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    return hash.finish();
}

}  // namespace
}  // namespace betelgeuze::native::docking::fixed64_indexed_so3

using namespace betelgeuze::native;

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_indexed_so3_input_v1_init(
    bg_docking_fixed64_indexed_so3_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(bg_docking_fixed64_indexed_so3_input_v1),
            caller_abi_version,
            "indexed SO3 input initializer pointer is null",
            "indexed SO3 input initializer size does not match",
            "indexed SO3 input initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *input = bg_docking_fixed64_indexed_so3_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_indexed_so3_output_v1_init(
    bg_docking_fixed64_indexed_so3_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(bg_docking_fixed64_indexed_so3_output_v1),
            caller_abi_version,
            "indexed SO3 output initializer pointer is null",
            "indexed SO3 output initializer size does not match",
            "indexed SO3 output initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *output = bg_docking_fixed64_indexed_so3_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_indexed_so3_v1_place(
    const bg_context *context,
    const bg_docking_fixed64_indexed_so3_input_v1 *input,
    bg_docking_fixed64_indexed_so3_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_indexed_so3;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || input == nullptr || output == nullptr ||
            !pointer_is_aligned(context) || !pointer_is_aligned(input) ||
            !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "indexed SO3 context, input, and output must be non-null and aligned");
        }
        std::size_t ligand_count = 0;
        Vec3 pocket_normal{};
        bg_status status = validate_input(*input, &ligand_count, &pocket_normal);
        if (status != BG_STATUS_OK) return status;
        status = validate_output(*context, *input, *output, ligand_count);
        if (status != BG_STATUS_OK) return status;
        const auto observed_source = coordinate_sha256(
            input->source_x_angstrom,
            input->source_y_angstrom,
            input->source_z_angstrom,
            ligand_count);
        if (std::memcmp(
                observed_source.data(), input->source.coordinate_sha256, 32) != 0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "indexed SO3 source coordinate identity is invalid");
        }
        const auto seed = source_seed_sha256(*input, pocket_normal);
        Generated generated{};
        status = generate_backend(
            *context, *input, seed, ligand_count, &generated);
        if (status != BG_STATUS_OK) return status;
        status = validate_generated(
            *input, generated, ligand_count, seed, context->backend);
        if (status != BG_STATUS_OK) return status;

        std::array<uint8_t, 32> coordinate{};
        if (generated.result.coordinates_written != UINT8_C(0)) {
            coordinate = coordinate_sha256(
                generated.x.data(),
                generated.y.data(),
                generated.z.data(),
                ligand_count);
        }
        const auto receipt = placement_receipt(
            *input, generated, context->backend, seed, coordinate);

        if (generated.result.coordinates_written != UINT8_C(0)) {
            std::memcpy(
                output->x_angstrom,
                generated.x.data(),
                ligand_count * sizeof(double));
            std::memcpy(
                output->y_angstrom,
                generated.y.data(),
                ligand_count * sizeof(double));
            std::memcpy(
                output->z_angstrom,
                generated.z.data(),
                ligand_count * sizeof(double));
        }
        output->slot_index = input->slot_index;
        output->lane = input->allocation_rows[input->slot_index].lane;
        output->status = generated.result.status;
        output->failure_code = generated.result.failure_code;
        output->backend = context->backend;
        output->accepted_sequence_index =
            generated.result.accepted_sequence_index;
        output->ligand_atom_count = ligand_count;
        output->raw_sequence_index = generated.result.raw_sequence_index;
        output->quaternion_x = generated.result.quaternion_x;
        output->quaternion_y = generated.result.quaternion_y;
        output->quaternion_z = generated.result.quaternion_z;
        output->quaternion_w = generated.result.quaternion_w;
        std::copy(
            std::begin(generated.result.translation_angstrom),
            std::end(generated.result.translation_angstrom),
            output->translation_angstrom);
        std::copy(
            std::begin(generated.result.source_centroid_angstrom),
            std::end(generated.result.source_centroid_angstrom),
            output->source_centroid_angstrom);
        std::copy(seed.begin(), seed.end(), output->source_seed_sha256);
        std::copy(
            coordinate.begin(),
            coordinate.end(),
            output->output_coordinate_sha256);
        std::copy(
            receipt.begin(), receipt.end(), output->placement_receipt_sha256);
        output->coordinates_written = generated.result.coordinates_written;
        output->source_identity_verified = UINT8_C(1);
        output->allocation_identity_verified = UINT8_C(1);
        output->result_dependent_input_consumed = UINT8_C(0);
        output->denominator_preserved = UINT8_C(1);
        output->molecular_execution_authorized = UINT8_C(0);
        output->reservation_authorized = UINT8_C(0);
        output->benchmark_execution_authorized = UINT8_C(0);
        output->production_claim_authorized = UINT8_C(0);
        return BG_STATUS_OK;
    });
}
