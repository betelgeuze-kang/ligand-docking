#ifndef BETELGEUZE_NATIVE_DYNAMICS_SHA256_HPP
#define BETELGEUZE_NATIVE_DYNAMICS_SHA256_HPP

#include <array>
#include <cstddef>
#include <cstdint>

namespace betelgeuze::native::dynamics {

class Sha256 final {
  public:
    Sha256() noexcept;

    void update(const uint8_t *data, std::size_t size) noexcept;
    [[nodiscard]] std::array<uint8_t, 32> finish() noexcept;

  private:
    void transform(const uint8_t *block) noexcept;

    std::array<uint32_t, 8> state_{};
    std::array<uint8_t, 64> block_{};
    std::size_t block_size_ = 0;
    uint64_t byte_count_ = UINT64_C(0);
};

void hash_u32(Sha256 *hash, uint32_t value) noexcept;
void hash_u64(Sha256 *hash, uint64_t value) noexcept;
void hash_double(Sha256 *hash, double value) noexcept;

[[nodiscard]] std::array<uint8_t, 32> sha256_with_zero_range(
    const uint8_t *data,
    std::size_t size,
    std::size_t zero_offset,
    std::size_t zero_size) noexcept;

}  // namespace betelgeuze::native::dynamics

#endif  // BETELGEUZE_NATIVE_DYNAMICS_SHA256_HPP
