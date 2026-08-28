#include "particle_mesh_ewald_composite_dynamics.hpp"

#include "../dynamics/sha256.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

namespace betelgeuze::native::composite::dynamics {
namespace {

constexpr std::array<uint8_t, 8> kPmeCompositeMagic = {
    'B', 'G', 'P', 'M', 'E', '0', '0', '1'};
constexpr std::array<uint8_t, 8> kLegacyMagic = {
    'B', 'G', 'D', 'Y', 'N', '0', '0', '1'};
constexpr uint32_t kFormatVersion = UINT32_C(1);
constexpr std::size_t kHeaderSize = 104U;
constexpr std::size_t kFingerprintOffset = 40U;
constexpr std::size_t kDigestOffset = 72U;
constexpr std::size_t kDigestSize = 32U;

uint32_t load_u32(const uint8_t *source) noexcept {
    uint32_t value = UINT32_C(0);
    for (std::size_t index = 0; index < 4U; ++index) {
        value |= static_cast<uint32_t>(source[index])
                 << static_cast<uint32_t>(index * 8U);
    }
    return value;
}

uint64_t load_u64(const uint8_t *source) noexcept {
    uint64_t value = UINT64_C(0);
    for (std::size_t index = 0; index < 8U; ++index) {
        value |= static_cast<uint64_t>(source[index])
                 << static_cast<uint32_t>(index * 8U);
    }
    return value;
}

bool constant_time_equal(
    const uint8_t *left,
    const uint8_t *right,
    std::size_t size) noexcept {
    uint8_t difference = UINT8_C(0);
    for (std::size_t index = 0; index < size; ++index) {
        difference = static_cast<uint8_t>(
            difference | static_cast<uint8_t>(left[index] ^ right[index]));
    }
    return difference == UINT8_C(0);
}

struct ByteRange final {
    std::uintptr_t begin = 0;
    std::uintptr_t end = 0;
};

bool make_byte_range(
    const void *pointer,
    std::size_t size,
    ByteRange *out_range) noexcept {
    if (pointer == nullptr || out_range == nullptr) {
        return false;
    }
    const auto begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (size > std::numeric_limits<std::uintptr_t>::max() - begin) {
        return false;
    }
    *out_range = ByteRange{begin, begin + size};
    return true;
}

bool ranges_overlap(const ByteRange &left, const ByteRange &right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

template <typename Value>
bg_status reject_vector_overlap(
    const std::vector<Value> &storage,
    const ByteRange &candidate,
    const char *message) noexcept {
    if (storage.empty()) {
        return BG_STATUS_OK;
    }
    if (storage.size() >
        std::numeric_limits<std::size_t>::max() / sizeof(Value)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite checkpoint owner storage size is not representable");
    }
    ByteRange storage_range;
    if (!make_byte_range(
            storage.data(), storage.size() * sizeof(Value), &storage_range)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite checkpoint owner storage range is not representable");
    }
    if (ranges_overlap(candidate, storage_range)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, message);
    }
    return BG_STATUS_OK;
}

bg_status reject_semantic_storage_overlap(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner,
    const ByteRange &candidate) noexcept {
    ByteRange owner_range;
    ByteRange simulation_range;
    if (!make_byte_range(&owner, sizeof(owner), &owner_range) ||
        owner.simulation == nullptr ||
        !make_byte_range(
            owner.simulation.get(), sizeof(*owner.simulation),
            &simulation_range)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite checkpoint owner range is not representable");
    }
    if (ranges_overlap(candidate, owner_range) ||
        ranges_overlap(candidate, simulation_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint bytes must not overlap the owner");
    }

    const bg_system &system = owner.simulation->system;
    const std::vector<double> *const system_channels[] = {
        &system.position_x,
        &system.position_y,
        &system.position_z,
        &system.velocity_x,
        &system.velocity_y,
        &system.velocity_z,
        &system.mass,
        &system.charge,
    };
    for (const std::vector<double> *channel : system_channels) {
        const bg_status status = reject_vector_overlap(
            *channel,
            candidate,
            "particle-mesh composite checkpoint bytes must not overlap owned particle channels");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }

    const bg_forcefield &forcefield = owner.simulation->forcefield;
    const std::vector<double> *const forcefield_double_channels[] = {
        &forcefield.sigma,
        &forcefield.epsilon,
        &forcefield.bonds.equilibrium,
        &forcefield.bonds.force_constant,
        &forcefield.angles.equilibrium,
        &forcefield.angles.force_constant,
        &forcefield.torsions.phase,
        &forcefield.torsions.amplitude,
    };
    for (const std::vector<double> *channel : forcefield_double_channels) {
        const bg_status status = reject_vector_overlap(
            *channel,
            candidate,
            "particle-mesh composite checkpoint bytes must not overlap owned force-field storage");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    const std::vector<std::size_t> *const forcefield_index_channels[] = {
        &forcefield.bonds.atom_i,
        &forcefield.bonds.atom_j,
        &forcefield.angles.atom_i,
        &forcefield.angles.atom_j,
        &forcefield.angles.atom_k,
        &forcefield.torsions.atom_i,
        &forcefield.torsions.atom_j,
        &forcefield.torsions.atom_k,
        &forcefield.torsions.atom_l,
    };
    for (const std::vector<std::size_t> *channel :
         forcefield_index_channels) {
        const bg_status status = reject_vector_overlap(
            *channel,
            candidate,
            "particle-mesh composite checkpoint bytes must not overlap owned force-field storage");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    bg_status status = reject_vector_overlap(
        forcefield.torsions.periodicity,
        candidate,
        "particle-mesh composite checkpoint bytes must not overlap owned force-field storage");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = reject_vector_overlap(
        forcefield.exclusions,
        candidate,
        "particle-mesh composite checkpoint bytes must not overlap owned force-field storage");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = reject_vector_overlap(
        forcefield.pair_scales,
        candidate,
        "particle-mesh composite checkpoint bytes must not overlap owned force-field storage");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = reject_vector_overlap(
        owner.simulation->constraints,
        candidate,
        "particle-mesh composite checkpoint bytes must not overlap owned constraint storage");
    if (status != BG_STATUS_OK) {
        return status;
    }
    return reject_vector_overlap(
        owner.direct_model.pair_rules,
        candidate,
        "particle-mesh composite checkpoint bytes must not overlap owned particle-mesh Ewald models storage");
}

bg_status validate_output_aliases(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner,
    void *buffer,
    std::size_t size,
    uint64_t *written_size) noexcept {
    if (!pointer_is_aligned(written_size)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint written-size output must be naturally aligned");
    }
    ByteRange buffer_range;
    ByteRange written_range;
    if (!make_byte_range(buffer, size, &buffer_range) ||
        !make_byte_range(
            written_size, sizeof(*written_size), &written_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint output range is not representable");
    }
    if (ranges_overlap(buffer_range, written_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint outputs must not overlap");
    }
    bg_status status = reject_semantic_storage_overlap(owner, buffer_range);
    if (status != BG_STATUS_OK) {
        return status;
    }
    return reject_semantic_storage_overlap(owner, written_range);
}

bg_status validate_scalar_output_alias(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner,
    uint64_t *output) noexcept {
    if (!pointer_is_aligned(output)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint size output must be naturally aligned");
    }
    ByteRange output_range;
    if (!make_byte_range(output, sizeof(*output), &output_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint size output range is not representable");
    }
    return reject_semantic_storage_overlap(owner, output_range);
}

bg_status validate_input_alias(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner,
    const void *buffer,
    std::size_t size) noexcept {
    ByteRange buffer_range;
    if (!make_byte_range(buffer, size, &buffer_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite checkpoint input range is not representable");
    }
    return reject_semantic_storage_overlap(owner, buffer_range);
}

void write_digest(std::vector<uint8_t> *bytes) noexcept {
    const std::array<uint8_t, 32> digest =
        betelgeuze::native::dynamics::sha256_with_zero_range(
            bytes->data(), bytes->size(), kDigestOffset, kDigestSize);
    std::copy(
        digest.begin(), digest.end(), bytes->begin() + kDigestOffset);
}

}  // namespace
}  // namespace betelgeuze::native::composite::dynamics

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_size(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    uint64_t *required_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || required_size == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite simulation and checkpoint size output must not be null");
        }
        bg_status status = validate_owner_invariant(*simulation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_scalar_output_alias(*simulation, required_size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        uint64_t local_size = UINT64_C(0);
        status = bg_simulation_checkpoint_size(
            simulation->simulation.get(), &local_size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        *required_size = local_size;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_write(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    void *buffer,
    uint64_t buffer_capacity,
    uint64_t *written_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || written_size == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite simulation and checkpoint written-size output must not be null");
        }
        bg_status status = validate_owner_invariant(*simulation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        uint64_t required_u64 = UINT64_C(0);
        status = bg_simulation_checkpoint_size(
            simulation->simulation.get(), &required_u64);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (buffer_capacity < required_u64) {
            return fail(
                BG_STATUS_BUFFER_TOO_SMALL,
                "particle-mesh composite checkpoint output buffer is too small");
        }
        if (buffer == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint output buffer must not be null");
        }
        if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
            if (required_u64 >
                static_cast<uint64_t>(
                    std::numeric_limits<std::size_t>::max())) {
                return fail(
                    BG_STATUS_CAPACITY_OVERFLOW,
                    "particle-mesh composite checkpoint size exceeds native address space");
            }
        }
        const std::size_t required =
            static_cast<std::size_t>(required_u64);
        status = validate_output_aliases(
            *simulation, buffer, required, written_size);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::vector<uint8_t> bytes(required, UINT8_C(0));
        uint64_t legacy_written = UINT64_C(0);
        status = bg_simulation_checkpoint_write(
            simulation->simulation.get(),
            bytes.data(),
            required_u64,
            &legacy_written);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (legacy_written != required_u64 || required < kHeaderSize) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "legacy checkpoint codec returned an inconsistent size");
        }
        std::copy(
            kPmeCompositeMagic.begin(), kPmeCompositeMagic.end(), bytes.begin());
        std::copy(
            simulation->static_fingerprint.begin(),
            simulation->static_fingerprint.end(),
            bytes.begin() + kFingerprintOffset);
        write_digest(&bytes);

        std::memmove(buffer, bytes.data(), required);
        *written_size = required_u64;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    const void *buffer,
    uint64_t buffer_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || buffer == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite simulation and checkpoint input buffer must not be null");
        }
        if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
            if (buffer_size >
                static_cast<uint64_t>(
                    std::numeric_limits<std::size_t>::max())) {
                return fail(
                    BG_STATUS_CAPACITY_OVERFLOW,
                    "particle-mesh composite checkpoint input size exceeds native address space");
            }
        }
        const std::size_t size = static_cast<std::size_t>(buffer_size);
        bg_status status = validate_input_alias(*simulation, buffer, size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_owner_invariant(*simulation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (size < kHeaderSize) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint input is shorter than its canonical header");
        }

        const auto *const input = static_cast<const uint8_t *>(buffer);
        std::vector<uint8_t> bytes(input, input + size);
        const std::array<uint8_t, 32> observed_digest =
            betelgeuze::native::dynamics::sha256_with_zero_range(
                bytes.data(), bytes.size(), kDigestOffset, kDigestSize);
        if (!constant_time_equal(
                observed_digest.data(),
                bytes.data() + kDigestOffset,
                kDigestSize)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint integrity digest does not match its bytes");
        }
        if (!std::equal(
                kPmeCompositeMagic.begin(), kPmeCompositeMagic.end(),
                bytes.begin()) ||
            load_u32(bytes.data() + 8U) != kFormatVersion ||
            load_u32(bytes.data() + 12U) != kHeaderSize ||
            load_u64(bytes.data() + 16U) != buffer_size) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint header is not a supported canonical format");
        }
        const uint64_t atom_count = static_cast<uint64_t>(
            simulation->simulation->system.position_x.size());
        if (load_u64(bytes.data() + 24U) != atom_count) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint particle count does not match the simulation");
        }
        uint64_t expected_size = UINT64_C(0);
        status = bg_simulation_checkpoint_size(
            simulation->simulation.get(), &expected_size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (expected_size != buffer_size) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint payload size is not canonical for its particle count");
        }
        if (!constant_time_equal(
                simulation->static_fingerprint.data(),
                bytes.data() + kFingerprintOffset,
                simulation->static_fingerprint.size())) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite checkpoint static evaluator fingerprint does not match");
        }

        std::copy(kLegacyMagic.begin(), kLegacyMagic.end(), bytes.begin());
        std::copy(
            simulation->simulation->static_fingerprint.begin(),
            simulation->simulation->static_fingerprint.end(),
            bytes.begin() + kFingerprintOffset);
        write_digest(&bytes);
        return bg_simulation_checkpoint_load(
            simulation->simulation.get(), bytes.data(), buffer_size);
    });
}
