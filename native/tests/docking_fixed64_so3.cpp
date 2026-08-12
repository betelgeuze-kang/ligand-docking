#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace {

constexpr std::size_t kCount = BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT;

struct Batch final {
    std::array<bg_docking_fixed64_so3_row_v1, kCount> rows{};
    bg_docking_fixed64_so3_output_v1 output{};
};

bg_context *make_context(bg_backend backend) {
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return nullptr;
    }
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    options.device_ordinal = 0;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != nullptr);
    return context;
}

bg_docking_fixed64_so3_input_v1 make_input(uint8_t seed_byte) {
    bg_docking_fixed64_so3_input_v1 input{};
    assert(bg_docking_fixed64_so3_input_v1_init(&input) == BG_STATUS_OK);
    std::fill(
        std::begin(input.source_seed_sha256),
        std::end(input.source_seed_sha256),
        seed_byte);
    return input;
}

Batch generate(
    const bg_context *context,
    const bg_docking_fixed64_so3_input_v1 &input) {
    Batch batch{};
    assert(bg_docking_fixed64_so3_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = batch.rows.size();
    batch.output.rows = batch.rows.data();
    assert(bg_docking_fixed64_so3_v1_generate(
               context, &input, &batch.output) == BG_STATUS_OK);
    return batch;
}

double geodesic(
    const bg_docking_fixed64_so3_row_v1 &left,
    const bg_docking_fixed64_so3_row_v1 &right) {
    const double dot = left.quaternion_x * right.quaternion_x +
                       left.quaternion_y * right.quaternion_y +
                       left.quaternion_z * right.quaternion_z +
                       left.quaternion_w * right.quaternion_w;
    const double sign = dot < 0.0 ? -1.0 : 1.0;
    const double dx = left.quaternion_x - sign * right.quaternion_x;
    const double dy = left.quaternion_y - sign * right.quaternion_y;
    const double dz = left.quaternion_z - sign * right.quaternion_z;
    const double dw = left.quaternion_w - sign * right.quaternion_w;
    const double sx = left.quaternion_x + sign * right.quaternion_x;
    const double sy = left.quaternion_y + sign * right.quaternion_y;
    const double sz = left.quaternion_z + sign * right.quaternion_z;
    const double sw = left.quaternion_w + sign * right.quaternion_w;
    return 4.0 * std::atan2(
                     std::sqrt(dx * dx + dy * dy + dz * dz + dw * dw),
                     std::sqrt(sx * sx + sy * sy + sz * sz + sw * sw));
}

void assert_semantics(
    const Batch &batch,
    bg_backend backend,
    double tolerance) {
    assert(batch.output.row_count == kCount);
    assert(batch.output.backend == backend);
    assert(batch.output.result_dependent_input_consumed == UINT8_C(0));
    assert(batch.output.denominator_preserved == UINT8_C(1));
    assert(batch.output.molecular_execution_authorized == UINT8_C(0));
    assert(batch.output.reservation_authorized == UINT8_C(0));
    assert(batch.output.benchmark_execution_authorized == UINT8_C(0));
    assert(batch.output.production_claim_authorized == UINT8_C(0));
    assert(std::any_of(
        std::begin(batch.output.batch_receipt_sha256),
        std::end(batch.output.batch_receipt_sha256),
        [](uint8_t value) { return value != UINT8_C(0); }));
    for (std::size_t index = 0; index < kCount; ++index) {
        const auto &row = batch.rows[index];
        assert(row.orientation_index == static_cast<uint32_t>(index));
        assert(row.status == BG_DOCKING_FIXED64_SO3_ROW_GENERATED);
        assert(row.failure_code == BG_DOCKING_FIXED64_SO3_FAILURE_NONE);
        assert(row.raw_sequence_index >= index);
        if (index != 0) {
            assert(row.raw_sequence_index >
                   batch.rows[index - 1U].raw_sequence_index);
        }
        const double norm = std::sqrt(
            row.quaternion_x * row.quaternion_x +
            row.quaternion_y * row.quaternion_y +
            row.quaternion_z * row.quaternion_z +
            row.quaternion_w * row.quaternion_w);
        assert(std::abs(norm - 1.0) <= tolerance);
        assert(row.norm_error <= tolerance);
        assert(row.result_dependent_input_consumed == UINT8_C(0));
        assert(row.duplicate_orientation_emitted == UINT8_C(0));
        assert(row.denominator_preserved == UINT8_C(1));
        assert(row.molecular_execution_authorized == UINT8_C(0));
        assert(row.reservation_authorized == UINT8_C(0));
        assert(row.benchmark_execution_authorized == UINT8_C(0));
        assert(row.production_claim_authorized == UINT8_C(0));
        assert(std::any_of(
            std::begin(row.row_receipt_sha256),
            std::end(row.row_receipt_sha256),
            [](uint8_t value) { return value != UINT8_C(0); }));
        for (std::size_t previous = 0; previous < index; ++previous) {
            assert(geodesic(row, batch.rows[previous]) > 1.0e-10);
        }
    }
}

void test_backend_repeat_and_semantic_parity() {
    const auto input = make_input(UINT8_C(0x5a));
    bg_context *cpp = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust = make_context(BG_BACKEND_RUST_CPU);
    assert(cpp != nullptr);
    assert(rust != nullptr);
    const Batch cpp_first = generate(cpp, input);
    const Batch cpp_second = generate(cpp, input);
    const Batch rust_first = generate(rust, input);
    const Batch rust_second = generate(rust, input);
    assert_semantics(cpp_first, BG_BACKEND_CPP_CPU_REFERENCE, 2.0e-12);
    assert_semantics(rust_first, BG_BACKEND_RUST_CPU, 2.0e-12);
    assert(std::memcmp(
               cpp_first.rows.data(),
               cpp_second.rows.data(),
               sizeof(cpp_first.rows)) == 0);
    assert(std::memcmp(
               rust_first.rows.data(),
               rust_second.rows.data(),
               sizeof(rust_first.rows)) == 0);
    assert(std::memcmp(
               cpp_first.output.batch_receipt_sha256,
               cpp_second.output.batch_receipt_sha256,
               32) == 0);
    assert(std::memcmp(
               rust_first.output.batch_receipt_sha256,
               rust_second.output.batch_receipt_sha256,
               32) == 0);
    for (std::size_t index = 0; index < kCount; ++index) {
        assert(cpp_first.rows[index].raw_sequence_index ==
               rust_first.rows[index].raw_sequence_index);
        assert(geodesic(cpp_first.rows[index], rust_first.rows[index]) <=
               2.0e-12);
    }
    bg_context_destroy(cpp);
    bg_context_destroy(rust);
}

void test_hip_parity_when_available(bg_backend backend) {
    bg_context *hip = make_context(backend);
    if (hip == nullptr) {
        return;
    }
    bg_context *rust = make_context(BG_BACKEND_RUST_CPU);
    assert(rust != nullptr);
    const auto input = make_input(UINT8_C(0xa5));
    const Batch hip_first = generate(hip, input);
    const Batch hip_second = generate(hip, input);
    const Batch reference = generate(rust, input);
    const double tolerance =
        backend == BG_BACKEND_HIP_FAST ? 2.0e-9 : 2.0e-10;
    assert_semantics(hip_first, backend, tolerance);
    assert(std::memcmp(
               hip_first.rows.data(),
               hip_second.rows.data(),
               sizeof(hip_first.rows)) == 0);
    for (std::size_t index = 0; index < kCount; ++index) {
        assert(hip_first.rows[index].raw_sequence_index ==
               reference.rows[index].raw_sequence_index);
        assert(geodesic(hip_first.rows[index], reference.rows[index]) <=
               tolerance);
    }
    bg_context_destroy(hip);
    bg_context_destroy(rust);
}

void test_source_seed_changes_sequence() {
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    const Batch left = generate(context, make_input(UINT8_C(0x11)));
    const Batch right = generate(context, make_input(UINT8_C(0x22)));
    assert(geodesic(left.rows[0], right.rows[0]) > 1.0e-6);
    assert(std::memcmp(
               left.output.batch_receipt_sha256,
               right.output.batch_receipt_sha256,
               32) != 0);
    bg_context_destroy(context);
}

void test_failure_is_transactional() {
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto input = make_input(UINT8_C(0x33));
    input.reserved[0] = UINT64_C(1);
    std::array<bg_docking_fixed64_so3_row_v1, kCount> rows{};
    std::memset(rows.data(), 0x5a, sizeof(rows));
    const auto rows_before = rows;
    bg_docking_fixed64_so3_output_v1 output{};
    assert(bg_docking_fixed64_so3_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = rows.size();
    output.rows = rows.data();
    output.row_count = UINT64_C(17);
    output.backend = BG_BACKEND_HIP_FAST;
    std::fill(
        std::begin(output.batch_receipt_sha256),
        std::end(output.batch_receipt_sha256),
        UINT8_C(0x7c));
    const auto output_before = output;
    assert(bg_docking_fixed64_so3_v1_generate(
               context, &input, &output) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(rows.data(), rows_before.data(), sizeof(rows)) == 0);
    assert(std::memcmp(&output, &output_before, sizeof(output)) == 0);

    input = make_input(UINT8_C(0));
    assert(bg_docking_fixed64_so3_v1_generate(
               context, &input, &output) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(rows.data(), rows_before.data(), sizeof(rows)) == 0);
    assert(std::memcmp(&output, &output_before, sizeof(output)) == 0);
    bg_context_destroy(context);
}

void test_context_alias_is_rejected_before_write() {
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    const auto input = make_input(UINT8_C(0x66));
    bg_docking_fixed64_so3_output_v1 output{};
    assert(bg_docking_fixed64_so3_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = kCount;
    output.rows = reinterpret_cast<bg_docking_fixed64_so3_row_v1 *>(context);
    const auto output_before = output;
    assert(bg_docking_fixed64_so3_v1_generate(
               context, &input, &output) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(&output, &output_before, sizeof(output)) == 0);
    bg_context_destroy(context);
}

void test_undersized_output_is_transactional() {
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    const auto input = make_input(UINT8_C(0x44));
    std::array<bg_docking_fixed64_so3_row_v1, kCount> rows{};
    std::memset(rows.data(), 0x6b, sizeof(rows));
    const auto rows_before = rows;
    bg_docking_fixed64_so3_output_v1 output{};
    assert(bg_docking_fixed64_so3_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = rows.size() - 1U;
    output.rows = rows.data();
    output.row_count = UINT64_C(23);
    output.backend = BG_BACKEND_HIP_SAFE;
    std::fill(
        std::begin(output.batch_receipt_sha256),
        std::end(output.batch_receipt_sha256),
        UINT8_C(0x8d));
    const auto output_before = output;
    assert(bg_docking_fixed64_so3_v1_generate(
               context, &input, &output) == BG_STATUS_BUFFER_TOO_SMALL);
    assert(std::memcmp(rows.data(), rows_before.data(), sizeof(rows)) == 0);
    assert(std::memcmp(&output, &output_before, sizeof(output)) == 0);
    bg_context_destroy(context);
}

}  // namespace

int main() {
    test_backend_repeat_and_semantic_parity();
    test_hip_parity_when_available(BG_BACKEND_HIP_SAFE);
    test_hip_parity_when_available(BG_BACKEND_HIP_FAST);
    test_source_seed_changes_sequence();
    test_failure_is_transactional();
    test_undersized_output_is_transactional();
    test_context_alias_is_rejected_before_write();
    return 0;
}
