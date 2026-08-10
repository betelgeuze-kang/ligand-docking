#include "sha256.hpp"

#include <algorithm>
#include <array>
#include <cstring>

namespace betelgeuze::native::dynamics {
namespace {

constexpr std::array<uint32_t, 64> kRoundConstants = {
    UINT32_C(0x428a2f98), UINT32_C(0x71374491), UINT32_C(0xb5c0fbcf),
    UINT32_C(0xe9b5dba5), UINT32_C(0x3956c25b), UINT32_C(0x59f111f1),
    UINT32_C(0x923f82a4), UINT32_C(0xab1c5ed5), UINT32_C(0xd807aa98),
    UINT32_C(0x12835b01), UINT32_C(0x243185be), UINT32_C(0x550c7dc3),
    UINT32_C(0x72be5d74), UINT32_C(0x80deb1fe), UINT32_C(0x9bdc06a7),
    UINT32_C(0xc19bf174), UINT32_C(0xe49b69c1), UINT32_C(0xefbe4786),
    UINT32_C(0x0fc19dc6), UINT32_C(0x240ca1cc), UINT32_C(0x2de92c6f),
    UINT32_C(0x4a7484aa), UINT32_C(0x5cb0a9dc), UINT32_C(0x76f988da),
    UINT32_C(0x983e5152), UINT32_C(0xa831c66d), UINT32_C(0xb00327c8),
    UINT32_C(0xbf597fc7), UINT32_C(0xc6e00bf3), UINT32_C(0xd5a79147),
    UINT32_C(0x06ca6351), UINT32_C(0x14292967), UINT32_C(0x27b70a85),
    UINT32_C(0x2e1b2138), UINT32_C(0x4d2c6dfc), UINT32_C(0x53380d13),
    UINT32_C(0x650a7354), UINT32_C(0x766a0abb), UINT32_C(0x81c2c92e),
    UINT32_C(0x92722c85), UINT32_C(0xa2bfe8a1), UINT32_C(0xa81a664b),
    UINT32_C(0xc24b8b70), UINT32_C(0xc76c51a3), UINT32_C(0xd192e819),
    UINT32_C(0xd6990624), UINT32_C(0xf40e3585), UINT32_C(0x106aa070),
    UINT32_C(0x19a4c116), UINT32_C(0x1e376c08), UINT32_C(0x2748774c),
    UINT32_C(0x34b0bcb5), UINT32_C(0x391c0cb3), UINT32_C(0x4ed8aa4a),
    UINT32_C(0x5b9cca4f), UINT32_C(0x682e6ff3), UINT32_C(0x748f82ee),
    UINT32_C(0x78a5636f), UINT32_C(0x84c87814), UINT32_C(0x8cc70208),
    UINT32_C(0x90befffa), UINT32_C(0xa4506ceb), UINT32_C(0xbef9a3f7),
    UINT32_C(0xc67178f2),
};

constexpr uint32_t rotate_right(uint32_t value, uint32_t count) noexcept {
    return (value >> count) | (value << (UINT32_C(32) - count));
}

uint32_t load_be_u32(const uint8_t *data) noexcept {
    return (static_cast<uint32_t>(data[0]) << 24U) |
           (static_cast<uint32_t>(data[1]) << 16U) |
           (static_cast<uint32_t>(data[2]) << 8U) |
           static_cast<uint32_t>(data[3]);
}

}  // namespace

Sha256::Sha256() noexcept
    : state_{UINT32_C(0x6a09e667), UINT32_C(0xbb67ae85),
             UINT32_C(0x3c6ef372), UINT32_C(0xa54ff53a),
             UINT32_C(0x510e527f), UINT32_C(0x9b05688c),
             UINT32_C(0x1f83d9ab), UINT32_C(0x5be0cd19)} {}

void Sha256::transform(const uint8_t *block) noexcept {
    std::array<uint32_t, 64> words{};
    for (std::size_t index = 0; index < 16; ++index) {
        words[index] = load_be_u32(block + index * 4U);
    }
    for (std::size_t index = 16; index < words.size(); ++index) {
        const uint32_t x = words[index - 15U];
        const uint32_t y = words[index - 2U];
        const uint32_t s0 = rotate_right(x, 7U) ^ rotate_right(x, 18U) ^
                            (x >> 3U);
        const uint32_t s1 = rotate_right(y, 17U) ^ rotate_right(y, 19U) ^
                            (y >> 10U);
        words[index] = words[index - 16U] + s0 + words[index - 7U] + s1;
    }

    uint32_t a = state_[0];
    uint32_t b = state_[1];
    uint32_t c = state_[2];
    uint32_t d = state_[3];
    uint32_t e = state_[4];
    uint32_t f = state_[5];
    uint32_t g = state_[6];
    uint32_t h = state_[7];
    for (std::size_t index = 0; index < words.size(); ++index) {
        const uint32_t sum1 = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^
                              rotate_right(e, 25U);
        const uint32_t choose = (e & f) ^ ((~e) & g);
        const uint32_t temporary1 =
            h + sum1 + choose + kRoundConstants[index] + words[index];
        const uint32_t sum0 = rotate_right(a, 2U) ^ rotate_right(a, 13U) ^
                              rotate_right(a, 22U);
        const uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        const uint32_t temporary2 = sum0 + majority;
        h = g;
        g = f;
        f = e;
        e = d + temporary1;
        d = c;
        c = b;
        b = a;
        a = temporary1 + temporary2;
    }
    state_[0] += a;
    state_[1] += b;
    state_[2] += c;
    state_[3] += d;
    state_[4] += e;
    state_[5] += f;
    state_[6] += g;
    state_[7] += h;
}

void Sha256::update(const uint8_t *data, std::size_t size) noexcept {
    if (data == nullptr || size == 0) {
        return;
    }
    byte_count_ += static_cast<uint64_t>(size);
    while (size > 0) {
        const std::size_t copied =
            std::min(size, block_.size() - block_size_);
        std::memcpy(block_.data() + block_size_, data, copied);
        block_size_ += copied;
        data += copied;
        size -= copied;
        if (block_size_ == block_.size()) {
            transform(block_.data());
            block_size_ = 0;
        }
    }
}

std::array<uint8_t, 32> Sha256::finish() noexcept {
    const uint64_t bit_count = byte_count_ * UINT64_C(8);
    const uint8_t one = UINT8_C(0x80);
    update(&one, 1);
    const uint8_t zero = UINT8_C(0);
    while (block_size_ != 56U) {
        update(&zero, 1);
    }
    std::array<uint8_t, 8> length{};
    for (std::size_t index = 0; index < length.size(); ++index) {
        length[7U - index] =
            static_cast<uint8_t>(bit_count >> static_cast<uint32_t>(index * 8U));
    }
    update(length.data(), length.size());

    std::array<uint8_t, 32> digest{};
    for (std::size_t word = 0; word < state_.size(); ++word) {
        const uint32_t value = state_[word];
        digest[word * 4U] = static_cast<uint8_t>(value >> 24U);
        digest[word * 4U + 1U] = static_cast<uint8_t>(value >> 16U);
        digest[word * 4U + 2U] = static_cast<uint8_t>(value >> 8U);
        digest[word * 4U + 3U] = static_cast<uint8_t>(value);
    }
    return digest;
}

void hash_u32(Sha256 *hash, uint32_t value) noexcept {
    std::array<uint8_t, 4> bytes{};
    for (std::size_t index = 0; index < bytes.size(); ++index) {
        bytes[index] =
            static_cast<uint8_t>(value >> static_cast<uint32_t>(index * 8U));
    }
    hash->update(bytes.data(), bytes.size());
}

void hash_u64(Sha256 *hash, uint64_t value) noexcept {
    std::array<uint8_t, 8> bytes{};
    for (std::size_t index = 0; index < bytes.size(); ++index) {
        bytes[index] =
            static_cast<uint8_t>(value >> static_cast<uint32_t>(index * 8U));
    }
    hash->update(bytes.data(), bytes.size());
}

void hash_double(Sha256 *hash, double value) noexcept {
    uint64_t bits = UINT64_C(0);
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    if (value == 0.0) {
        bits = UINT64_C(0);
    }
    hash_u64(hash, bits);
}

std::array<uint8_t, 32> sha256_with_zero_range(
    const uint8_t *data,
    std::size_t size,
    std::size_t zero_offset,
    std::size_t zero_size) noexcept {
    Sha256 hash;
    hash.update(data, zero_offset);
    std::array<uint8_t, 32> zeros{};
    std::size_t remaining = zero_size;
    while (remaining > 0) {
        const std::size_t count = std::min(remaining, zeros.size());
        hash.update(zeros.data(), count);
        remaining -= count;
    }
    hash.update(
        data + zero_offset + zero_size,
        size - zero_offset - zero_size);
    return hash.finish();
}

}  // namespace betelgeuze::native::dynamics
