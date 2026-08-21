#include "dynamics.hpp"

#include "sha256.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

namespace betelgeuze::native::dynamics {
namespace {

constexpr std::array<uint8_t, 8> kMagic = {
    'B', 'G', 'D', 'Y', 'N', '0', '0', '1'};
constexpr uint32_t kFormatVersion = UINT32_C(1);
constexpr std::size_t kHeaderSize = 104U;
constexpr std::size_t kFingerprintOffset = 40U;
constexpr std::size_t kDigestOffset = 72U;
constexpr std::size_t kDigestSize = 32U;
constexpr std::size_t kBytesPerParticle = 6U * sizeof(double);

void store_u32(uint8_t *destination, uint32_t value) noexcept {
    for (std::size_t index = 0; index < 4U; ++index) {
        destination[index] =
            static_cast<uint8_t>(value >> static_cast<uint32_t>(index * 8U));
    }
}

void store_u64(uint8_t *destination, uint64_t value) noexcept {
    for (std::size_t index = 0; index < 8U; ++index) {
        destination[index] =
            static_cast<uint8_t>(value >> static_cast<uint32_t>(index * 8U));
    }
}

void store_double(uint8_t *destination, double value) noexcept {
    uint64_t bits = UINT64_C(0);
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    store_u64(destination, bits);
}

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

double load_double(const uint8_t *source) noexcept {
    const uint64_t bits = load_u64(source);
    double value = 0.0;
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

bool constant_time_equal(
    const uint8_t *left,
    const uint8_t *right,
    std::size_t size) noexcept {
    uint8_t difference = UINT8_C(0);
    for (std::size_t index = 0; index < size; ++index) {
        difference = static_cast<uint8_t>(difference | (left[index] ^ right[index]));
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

bg_status validate_checkpoint_output_aliases(
    const bg_simulation &simulation,
    void *buffer,
    std::size_t required,
    uint64_t *written_size) noexcept {
    ByteRange buffer_range;
    ByteRange written_range;
    ByteRange object_range;
    if (!make_byte_range(buffer, required, &buffer_range) ||
        !make_byte_range(written_size, sizeof(*written_size), &written_range) ||
        !make_byte_range(&simulation, sizeof(simulation), &object_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "checkpoint output byte range is not representable");
    }
    if (ranges_overlap(buffer_range, written_range) ||
        ranges_overlap(buffer_range, object_range) ||
        ranges_overlap(written_range, object_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "checkpoint outputs must not overlap each other or the simulation");
    }
    const std::vector<double> *const channels[] = {
        &simulation.system.position_x,
        &simulation.system.position_y,
        &simulation.system.position_z,
        &simulation.system.velocity_x,
        &simulation.system.velocity_y,
        &simulation.system.velocity_z,
        &simulation.system.mass,
        &simulation.system.charge,
    };
    for (const std::vector<double> *channel : channels) {
        if (channel->empty()) {
            continue;
        }
        ByteRange channel_range;
        if (!make_byte_range(
                channel->data(), channel->size() * sizeof(double),
                &channel_range)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "simulation channel byte range is not representable");
        }
        if (ranges_overlap(buffer_range, channel_range) ||
            ranges_overlap(written_range, channel_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint outputs must not overlap simulation-owned particle channels");
        }
    }
    return BG_STATUS_OK;
}

bg_status checked_checkpoint_size(
    const bg_simulation &simulation,
    std::size_t *out_size) noexcept {
    const std::size_t count = simulation.system.position_x.size();
    if (count >
        (std::numeric_limits<std::size_t>::max() - kHeaderSize) /
            kBytesPerParticle) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "checkpoint size exceeds native address space");
    }
    const std::size_t size = kHeaderSize + count * kBytesPerParticle;
    if constexpr (sizeof(std::size_t) > sizeof(uint64_t)) {
        if (size > static_cast<std::size_t>(UINT64_MAX)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "checkpoint size exceeds uint64");
        }
    }
    *out_size = size;
    return BG_STATUS_OK;
}

bool dynamic_storage_is_valid(const bg_simulation &simulation) noexcept {
    const std::size_t count = simulation.system.position_x.size();
    const bg_system &system = simulation.system;
    return count > 0 && system.position_y.size() == count &&
           system.position_z.size() == count && system.velocity_x.size() == count &&
           system.velocity_y.size() == count && system.velocity_z.size() == count &&
           system.mass.size() == count && system.charge.size() == count;
}

void commit_loaded_state(
    const bg_simulation &candidate,
    bg_simulation *simulation) noexcept {
    std::copy(
        candidate.system.position_x.begin(), candidate.system.position_x.end(),
        simulation->system.position_x.begin());
    std::copy(
        candidate.system.position_y.begin(), candidate.system.position_y.end(),
        simulation->system.position_y.begin());
    std::copy(
        candidate.system.position_z.begin(), candidate.system.position_z.end(),
        simulation->system.position_z.begin());
    std::copy(
        candidate.system.velocity_x.begin(), candidate.system.velocity_x.end(),
        simulation->system.velocity_x.begin());
    std::copy(
        candidate.system.velocity_y.begin(), candidate.system.velocity_y.end(),
        simulation->system.velocity_y.begin());
    std::copy(
        candidate.system.velocity_z.begin(), candidate.system.velocity_z.end(),
        simulation->system.velocity_z.begin());
    simulation->absolute_step = candidate.absolute_step;
    simulation->neighbor_list_cache = {};
}

}  // namespace
}  // namespace betelgeuze::native::dynamics

extern "C" BG_API bg_status BG_CALL bg_simulation_checkpoint_size(
    const bg_simulation *simulation,
    uint64_t *required_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || required_size == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "simulation and checkpoint size output must not be null");
        }
        std::size_t size = 0;
        const bg_status status = checked_checkpoint_size(*simulation, &size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        *required_size = static_cast<uint64_t>(size);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_simulation_checkpoint_write(
    const bg_simulation *simulation,
    void *buffer,
    uint64_t buffer_capacity,
    uint64_t *written_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || written_size == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "simulation and checkpoint written_size output must not be null");
        }
        if (!dynamic_storage_is_valid(*simulation)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "simulation dynamic storage is inconsistent");
        }
        std::size_t required = 0;
        bg_status status = checked_checkpoint_size(*simulation, &required);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (buffer_capacity < static_cast<uint64_t>(required)) {
            return fail(
                BG_STATUS_BUFFER_TOO_SMALL,
                "checkpoint output buffer is too small");
        }
        if (buffer == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint output buffer must not be null");
        }
        status = validate_checkpoint_output_aliases(
            *simulation, buffer, required, written_size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        std::vector<uint8_t> bytes(required, UINT8_C(0));
        std::copy(kMagic.begin(), kMagic.end(), bytes.begin());
        store_u32(bytes.data() + 8U, kFormatVersion);
        store_u32(bytes.data() + 12U, static_cast<uint32_t>(kHeaderSize));
        store_u64(bytes.data() + 16U, static_cast<uint64_t>(required));
        const std::size_t count = simulation->system.position_x.size();
        store_u64(bytes.data() + 24U, static_cast<uint64_t>(count));
        store_u64(bytes.data() + 32U, simulation->absolute_step);
        std::copy(
            simulation->static_fingerprint.begin(),
            simulation->static_fingerprint.end(),
            bytes.begin() + static_cast<std::ptrdiff_t>(kFingerprintOffset));

        const std::vector<double> *const channels[] = {
            &simulation->system.position_x,
            &simulation->system.position_y,
            &simulation->system.position_z,
            &simulation->system.velocity_x,
            &simulation->system.velocity_y,
            &simulation->system.velocity_z,
        };
        std::size_t offset = kHeaderSize;
        for (const std::vector<double> *channel : channels) {
            for (const double value : *channel) {
                if (!std::isfinite(value)) {
                    return fail(
                        BG_STATUS_NUMERICAL_ERROR,
                        "checkpoint dynamic state contains a non-finite value");
                }
                store_double(bytes.data() + offset, value);
                offset += sizeof(double);
            }
        }
        const std::array<uint8_t, 32> digest = sha256_with_zero_range(
            bytes.data(), bytes.size(), kDigestOffset, kDigestSize);
        std::copy(
            digest.begin(), digest.end(),
            bytes.begin() + static_cast<std::ptrdiff_t>(kDigestOffset));
        std::memmove(buffer, bytes.data(), bytes.size());
        *written_size = static_cast<uint64_t>(required);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_simulation_checkpoint_load(
    bg_simulation *simulation,
    const void *buffer,
    uint64_t buffer_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || buffer == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "simulation and checkpoint input buffer must not be null");
        }
        if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
            if (buffer_size > static_cast<uint64_t>(
                                  std::numeric_limits<std::size_t>::max())) {
                return fail(
                    BG_STATUS_CAPACITY_OVERFLOW,
                    "checkpoint input size exceeds native address space");
            }
        }
        const std::size_t size = static_cast<std::size_t>(buffer_size);
        if (size < kHeaderSize) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint input is shorter than its canonical header");
        }
        const auto *bytes = static_cast<const uint8_t *>(buffer);
        const std::array<uint8_t, 32> digest = sha256_with_zero_range(
            bytes, size, kDigestOffset, kDigestSize);
        if (!constant_time_equal(
                digest.data(), bytes + kDigestOffset, digest.size())) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint integrity digest does not match its bytes");
        }
        if (!std::equal(kMagic.begin(), kMagic.end(), bytes) ||
            load_u32(bytes + 8U) != kFormatVersion ||
            load_u32(bytes + 12U) != static_cast<uint32_t>(kHeaderSize) ||
            load_u64(bytes + 16U) != buffer_size) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint header is not a supported canonical format");
        }
        const uint64_t particle_count = load_u64(bytes + 24U);
        if (particle_count !=
            static_cast<uint64_t>(simulation->system.position_x.size())) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint particle count does not match the simulation");
        }
        std::size_t expected_size = 0;
        bg_status status = checked_checkpoint_size(*simulation, &expected_size);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (size != expected_size) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint payload size is not canonical for its particle count");
        }
        const std::array<uint8_t, 32> current_fingerprint =
            compute_static_fingerprint(*simulation);
        if (!constant_time_equal(
                current_fingerprint.data(),
                simulation->static_fingerprint.data(),
                current_fingerprint.size()) ||
            !constant_time_equal(
                bytes + kFingerprintOffset,
                current_fingerprint.data(),
                current_fingerprint.size())) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "checkpoint static forcefield/configuration fingerprint does not match");
        }

        bg_simulation candidate = *simulation;
        std::vector<double> *const channels[] = {
            &candidate.system.position_x,
            &candidate.system.position_y,
            &candidate.system.position_z,
            &candidate.system.velocity_x,
            &candidate.system.velocity_y,
            &candidate.system.velocity_z,
        };
        std::size_t offset = kHeaderSize;
        for (std::vector<double> *channel : channels) {
            for (double &value : *channel) {
                value = load_double(bytes + offset);
                offset += sizeof(double);
                if (!std::isfinite(value)) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "checkpoint dynamic state contains a non-finite value");
                }
            }
        }
        candidate.absolute_step = load_u64(bytes + 32U);
        status = validate_constraint_state(candidate);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_constraint_independence(candidate);
        if (status != BG_STATUS_OK) {
            return status;
        }
        commit_loaded_state(candidate, simulation);
        return BG_STATUS_OK;
    });
}
